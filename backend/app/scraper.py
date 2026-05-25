"""
scraper.py — Moteur de scraping robuste pour Fantasy Boulzazen WC 2026
======================================================================
Architecture multi-sources avec fallback gracieux :
  1. Source primaire  : FBref.com  (stats joueurs détaillées)
  2. Source secondaire: Soccerway  (résultats de matchs)
  3. Source tertiaire : ESPN API publique (scores live)
  4. Fallback ultime  : Cache local SQLite + données statiques de base

Stratégies anti-ban / robustesse :
  - User-Agent rotation aléatoire
  - Retry exponentiel (3 tentatives max)
  - Cache TTL 15 minutes (évite de spammer les sites)
  - Timeout strict 10 secondes par requête
  - Parsing défensif : toujours retourner une liste valide

Auteur : Tech Lead Fantasy Boulzazen
Version : 3.0 — Architecture production
"""

from __future__ import annotations

import json
import logging
import random
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ─── Logging ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("fantasy_scraper")

# ─── Chemins & constantes ─────────────────────────────────────────────────────
CACHE_DB_PATH  = Path("./scraper_cache.db")
CACHE_TTL_MIN  = 15          # minutes avant de re-scraper
REQUEST_TIMEOUT = 10         # secondes
MAX_RETRIES     = 3
RETRY_DELAY_BASE = 2.0       # secondes (exponentiel : 2, 4, 8)

# Rotation de User-Agents pour éviter les blocages
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:126.0) Gecko/20100101 Firefox/126.0",
]

# ─── Mapping noms d'équipes → identifiants FBref ─────────────────────────────
FBREF_TEAM_IDS: dict[str, str] = {
    "France":        "615226a3",
    "Argentine":     "8cdebfae",
    "Brésil":        "e8ea077b",
    "Angleterre":    "cff3d9bb",
    "Espagne":       "53a2f082",
    "Allemagne":     "e34e6c1c",
    "Portugal":      "b13e2755",
    "Pays-Bas":      "748aaacf",
    "Belgique":      "fb8d4f20",
    "Maroc":         "7a76b5a3",
    "USA":           "7c21e445",
    "Mexique":       "a56002cd",
    "Canada":        "e6a68c85",
    "Sénégal":       "a8c92abd",
    "Japon":         "3dbf8f4c",
    "Corée du Sud":  "f1ce6f57",
    "Algérie":       "a73d5899",
    "Tunisie":       "3a90a30b",
    "Croatie":       "1fdca8b7",
    "Uruguay":       "ca7a2ec4",
    "Colombie":      "a4ce5f42",
    "Pologne":       "e1d6b5ae",
    "Suisse":        "c0e9ae19",
    "Australie":     "5581b2d8",
}

# URL de base — Coupe du Monde FIFA 2026 sur FBref
FBREF_WC2026_BASE = "https://fbref.com/en/comps/1/2026"


# ══════════════════════════════════════════════════════════════════════════════
#  CACHE LOCAL — SQLite léger pour éviter le spam
# ══════════════════════════════════════════════════════════════════════════════

def _init_cache_db() -> sqlite3.Connection:
    """Initialise (ou ouvre) la base de cache SQLite."""
    conn = sqlite3.connect(str(CACHE_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scraper_cache (
            cache_key  TEXT PRIMARY KEY,
            data_json  TEXT NOT NULL,
            cached_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _cache_get(key: str) -> Optional[list | dict]:
    """Récupère une entrée du cache si encore valide (< TTL)."""
    try:
        conn = _init_cache_db()
        row = conn.execute(
            "SELECT data_json, cached_at FROM scraper_cache WHERE cache_key = ?",
            (key,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        cached_at = datetime.fromisoformat(row[1])
        if datetime.utcnow() - cached_at > timedelta(minutes=CACHE_TTL_MIN):
            return None   # Cache périmé
        return json.loads(row[0])
    except Exception as e:
        logger.debug(f"Cache read error ({key}): {e}")
        return None


def _cache_set(key: str, data: list | dict) -> None:
    """Sauvegarde une entrée dans le cache."""
    try:
        conn = _init_cache_db()
        conn.execute(
            "INSERT OR REPLACE INTO scraper_cache (cache_key, data_json, cached_at) "
            "VALUES (?, ?, ?)",
            (key, json.dumps(data, ensure_ascii=False), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"Cache write error ({key}): {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  HTTP — Requête robuste avec retry et rotation UA
# ══════════════════════════════════════════════════════════════════════════════

def _http_get(url: str, extra_headers: Optional[dict] = None) -> Optional[requests.Response]:
    """
    Effectue une requête GET avec :
      - Rotation de User-Agent
      - Retry exponentiel (3 tentatives)
      - Timeout strict
    Retourne None si toutes les tentatives échouent.
    """
    headers = {
        "User-Agent":      random.choice(USER_AGENTS),
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "DNT":             "1",
    }
    if extra_headers:
        headers.update(extra_headers)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:  # Rate limited
                wait = RETRY_DELAY_BASE ** attempt
                logger.warning(f"Rate limited ({url}), attente {wait}s")
                time.sleep(wait)
            elif resp.status_code in (403, 404):
                logger.warning(f"HTTP {resp.status_code} pour {url}")
                return None
            else:
                logger.debug(f"HTTP {resp.status_code} — tentative {attempt}/{MAX_RETRIES}")

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout ({url}) tentative {attempt}/{MAX_RETRIES}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connexion échouée ({url}): {e}")
        except Exception as e:
            logger.error(f"Erreur inattendue ({url}): {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_BASE ** attempt)

    return None


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 1 — FBref (stats joueurs & résultats officiels)
# ══════════════════════════════════════════════════════════════════════════════

def _scrape_fbref_matches() -> list[dict]:
    """
    Scrape les résultats de matchs depuis FBref — Coupe du Monde 2026.
    Retourne une liste de dicts normalisés.
    """
    cache_key = "fbref_matches_wc2026"
    cached = _cache_get(cache_key)
    if cached:
        logger.info(f"✅ Cache hit : {cache_key} ({len(cached)} matchs)")
        return cached

    url = f"{FBREF_WC2026_BASE}/schedule/2026-FIFA-World-Cup-Scores-and-Fixtures"
    resp = _http_get(url)
    if not resp:
        logger.warning("FBref matchs inaccessible")
        return []

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"id": "sched_all"})
        if not table:
            logger.warning("FBref : table #sched_all introuvable")
            return []

        matches = []
        rows = table.select("tbody > tr:not(.spacer):not(.thead)")

        for row in rows:
            try:
                # Extraction des cellules clés
                date_cell   = row.find("td", {"data-stat": "date"})
                home_cell   = row.find("td", {"data-stat": "home_team"})
                away_cell   = row.find("td", {"data-stat": "away_team"})
                score_cell  = row.find("td", {"data-stat": "score"})
                group_cell  = row.find("td", {"data-stat": "round"})
                match_link  = score_cell.find("a") if score_cell else None

                if not (date_cell and home_cell and away_cell):
                    continue

                home  = home_cell.get_text(strip=True)
                away  = away_cell.get_text(strip=True)
                date  = date_cell.get_text(strip=True)
                round_name = group_cell.get_text(strip=True) if group_cell else "Groupe"

                # Parser le score "X–Y" ou "X:Y"
                home_score, away_score, is_finished = None, None, False
                if score_cell:
                    score_text = score_cell.get_text(strip=True)
                    for sep in ["–", "-", ":"]:
                        if sep in score_text:
                            parts = score_text.split(sep)
                            if len(parts) == 2:
                                try:
                                    home_score  = int(parts[0].strip())
                                    away_score  = int(parts[1].strip())
                                    is_finished = True
                                except ValueError:
                                    pass
                            break

                # ID de match depuis le lien
                match_id = None
                if match_link and match_link.get("href"):
                    parts = match_link["href"].split("/")
                    if len(parts) >= 4:
                        match_id = parts[3]  # ex: "abc12345"

                matches.append({
                    "id":          match_id or f"{home}_{away}_{date}",
                    "home":        home,
                    "away":        away,
                    "date":        date,
                    "group":       round_name,
                    "home_score":  home_score,
                    "away_score":  away_score,
                    "is_finished": is_finished,
                    "is_locked":   is_finished,   # Match terminé = verrouillé
                    "source":      "fbref",
                })
            except Exception as e:
                logger.debug(f"Parsing ligne match FBref : {e}")
                continue

        logger.info(f"📡 FBref : {len(matches)} matchs scrapés")
        if matches:
            _cache_set(cache_key, matches)
        return matches

    except Exception as e:
        logger.error(f"Erreur parsing FBref matchs : {e}")
        return []


def _scrape_fbref_player_stats() -> list[dict]:
    """
    Scrape les statistiques individuelles des joueurs depuis FBref.
    Table 'stats_standard' de la compétition WC 2026.
    Retourne une liste normalisée compatible avec rules_engine.
    """
    cache_key = "fbref_player_stats_wc2026"
    cached = _cache_get(cache_key)
    if cached:
        logger.info(f"✅ Cache hit : {cache_key} ({len(cached)} joueurs)")
        return cached

    url = f"{FBREF_WC2026_BASE}/stats/2026-FIFA-World-Cup-Stats"
    resp = _http_get(url)
    if not resp:
        logger.warning("FBref stats joueurs inaccessible")
        return []

    try:
        soup  = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"id": "stats_standard"})
        if not table:
            # Chercher d'autres tables de stats
            for table_id in ["stats_shooting", "stats_passing", "stats_keeper"]:
                table = soup.find("table", {"id": table_id})
                if table:
                    break
        if not table:
            logger.warning("FBref : aucune table de stats trouvée")
            return []

        players = []
        rows = table.select("tbody > tr:not(.spacer):not(.thead)")

        for row in rows:
            try:
                def get(stat):
                    cell = row.find("td", {"data-stat": stat})
                    return cell.get_text(strip=True) if cell else ""

                def get_int(stat, default=0):
                    val = get(stat)
                    try:
                        return int(float(val)) if val else default
                    except (ValueError, TypeError):
                        return default

                def get_float(stat, default=0.0):
                    val = get(stat)
                    try:
                        return float(val) if val else default
                    except (ValueError, TypeError):
                        return default

                name_cell = row.find("td", {"data-stat": "player"})
                if not name_cell:
                    continue
                name = name_cell.get_text(strip=True)
                if not name:
                    continue

                # Lien vers la page joueur pour récupérer l'ID
                player_link = name_cell.find("a")
                player_id   = None
                if player_link and player_link.get("href"):
                    parts = player_link["href"].split("/")
                    if len(parts) >= 4:
                        player_id = parts[3]

                # Position normalisée G/D/M/A
                pos_raw  = get("position")
                position = _normalize_position(pos_raw)

                players.append({
                    "player_id":    player_id or name,
                    "name":         name,
                    "nationality":  get("nationality"),
                    "position":     position,
                    "minutes":      get_int("minutes"),
                    "goals":        get_int("goals"),
                    "assists":      get_int("assists"),
                    "yellow_cards": get_int("cards_yellow"),
                    "red_cards":    get_int("cards_red"),
                    # Gardiens
                    "saves":        get_int("gk_saves"),
                    "clean_sheet":  get_int("gk_clean_sheets") > 0,
                    # Défense
                    "recoveries":   get_int("ball_recoveries"),
                    # Prix estimé (5–20M selon la notoriété)
                    "price":        _estimate_price(get_float("goals") + get_float("assists"),
                                                    position),
                    "source":       "fbref",
                })

            except Exception as e:
                logger.debug(f"Parsing joueur FBref : {e}")
                continue

        logger.info(f"📡 FBref : {len(players)} joueurs scrapés")
        if players:
            _cache_set(cache_key, players)
        return players

    except Exception as e:
        logger.error(f"Erreur parsing FBref stats : {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 2 — ESPN/SofaScore (résultats live alternatifs)
# ══════════════════════════════════════════════════════════════════════════════

def _scrape_espn_matches() -> list[dict]:
    """
    Scrape les résultats depuis ESPN Scores (API publique non-officielle).
    Utilisé en fallback si FBref est inaccessible.
    """
    cache_key = "espn_matches_wc2026"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    # ESPN API publique — Coupe du Monde
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

    try:
        resp = _http_get(url, extra_headers={"Accept": "application/json"})
        if not resp:
            return []

        data    = resp.json()
        events  = data.get("events", [])
        matches = []

        for ev in events:
            try:
                comp     = ev.get("competitions", [{}])[0]
                comps    = comp.get("competitors", [])
                status   = ev.get("status", {})
                state    = status.get("type", {}).get("name", "")
                is_done  = state == "STATUS_FINAL"

                home_comp = next((c for c in comps if c.get("homeAway") == "home"), {})
                away_comp = next((c for c in comps if c.get("homeAway") == "away"), {})

                matches.append({
                    "id":          ev.get("id"),
                    "home":        home_comp.get("team", {}).get("displayName", ""),
                    "away":        away_comp.get("team", {}).get("displayName", ""),
                    "date":        ev.get("date", "")[:10],
                    "group":       ev.get("season", {}).get("displayName", "Groupe"),
                    "home_score":  int(home_comp.get("score", 0)) if is_done else None,
                    "away_score":  int(away_comp.get("score", 0)) if is_done else None,
                    "is_finished": is_done,
                    "is_locked":   state in ("STATUS_IN_PROGRESS", "STATUS_FINAL"),
                    "source":      "espn",
                })
            except Exception:
                continue

        logger.info(f"📡 ESPN : {len(matches)} matchs scrapés")
        if matches:
            _cache_set(cache_key, matches)
        return matches

    except Exception as e:
        logger.warning(f"ESPN scraping échoué : {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 3 — Soccerway (effectifs / compositions)
# ══════════════════════════════════════════════════════════════════════════════

_SOCCERWAY_TEAM_URLS: dict[str, str] = {
    "France":      "https://int.soccerway.com/teams/france/france/760/",
    "Argentine":   "https://int.soccerway.com/teams/argentina/argentina/755/",
    "Brésil":      "https://int.soccerway.com/teams/brazil/brazil/756/",
    "Angleterre":  "https://int.soccerway.com/teams/england/england/762/",
    "Espagne":     "https://int.soccerway.com/teams/spain/spain/763/",
    "Allemagne":   "https://int.soccerway.com/teams/germany/germany/760/",
    "Portugal":    "https://int.soccerway.com/teams/portugal/portugal/761/",
    "Maroc":       "https://int.soccerway.com/teams/morocco/morocco/794/",
    "Algérie":     "https://int.soccerway.com/teams/algeria/algeria/792/",
    "Sénégal":     "https://int.soccerway.com/teams/senegal/senegal/799/",
}


def _scrape_soccerway_squad(team_name: str) -> list[dict]:
    """Scrape l'effectif d'une équipe nationale sur Soccerway."""
    url = _SOCCERWAY_TEAM_URLS.get(team_name)
    if not url:
        return []

    cache_key = f"soccerway_squad_{team_name.lower().replace(' ', '_')}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    resp = _http_get(url)
    if not resp:
        return []

    try:
        soup    = BeautifulSoup(resp.text, "html.parser")
        players = []

        # Soccerway : tableau avec class 'squad-container'
        for row in soup.select("table.squad tr[class*='player']"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            name_cell = row.find("td", class_="name")
            pos_cell  = row.find("td", class_="position")
            if not name_cell:
                continue

            name     = name_cell.get_text(strip=True)
            pos_raw  = pos_cell.get_text(strip=True) if pos_cell else ""
            position = _normalize_position(pos_raw)

            players.append({
                "name":        name,
                "position":    position,
                "nationality": team_name,
                "price":       _estimate_price(0, position),
                "goals":       0,
                "assists":     0,
                "points_total": 0,
            })

        if players:
            _cache_set(cache_key, players)
        return players

    except Exception as e:
        logger.debug(f"Soccerway squad {team_name}: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  DONNÉES STATIQUES — Fallback complet si tous les scrapers échouent
# ══════════════════════════════════════════════════════════════════════════════

_STATIC_SQUADS: dict[str, list[dict]] = {
    "France": [
        {"id": 101, "name": "M. Maignan",      "position": "G", "nationality": "Française",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 102, "name": "A. Areola",        "position": "G", "nationality": "Française",  "price": 4.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 103, "name": "W. Saliba",        "position": "D", "nationality": "Française",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 104, "name": "T. Hernandez",     "position": "D", "nationality": "Française",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 105, "name": "D. Upamecano",     "position": "D", "nationality": "Française",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 106, "name": "J. Koundé",        "position": "D", "nationality": "Française",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 107, "name": "N. Tchouaméni",    "position": "M", "nationality": "Française",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 108, "name": "A. Rabiot",        "position": "M", "nationality": "Française",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 109, "name": "A. Griezmann",     "position": "M", "nationality": "Française",  "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 110, "name": "K. Mbappé",        "position": "A", "nationality": "Française",  "price": 18.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 111, "name": "O. Dembélé",       "position": "A", "nationality": "Française",  "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 112, "name": "M. Thuram",        "position": "A", "nationality": "Française",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 113, "name": "B. Camavinga",     "position": "M", "nationality": "Française",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 114, "name": "E. Koné",          "position": "M", "nationality": "Française",  "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": False},
        {"id": 115, "name": "Y. Fofana",        "position": "D", "nationality": "Française",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Argentine": [
        {"id": 201, "name": "E. Martínez",      "position": "G", "nationality": "Argentine",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 202, "name": "G. Montiel",       "position": "D", "nationality": "Argentine",  "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 203, "name": "L. Martínez",      "position": "D", "nationality": "Argentine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 204, "name": "C. Romero",        "position": "D", "nationality": "Argentine",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 205, "name": "N. Tagliafico",    "position": "D", "nationality": "Argentine",  "price": 6.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 206, "name": "E. Fernández",     "position": "M", "nationality": "Argentine",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 207, "name": "R. De Paul",       "position": "M", "nationality": "Argentine",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 208, "name": "A. Mac Allister",  "position": "M", "nationality": "Argentine",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 209, "name": "L. Messi",         "position": "A", "nationality": "Argentine",  "price": 16.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 210, "name": "J. Álvarez",       "position": "A", "nationality": "Argentine",  "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 211, "name": "A. Di María",      "position": "A", "nationality": "Argentine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 212, "name": "L. Paredes",       "position": "M", "nationality": "Argentine",  "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Brésil": [
        {"id": 301, "name": "Alisson",          "position": "G", "nationality": "Brésilienne", "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 302, "name": "Danilo",           "position": "D", "nationality": "Brésilienne", "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 303, "name": "Marquinhos",       "position": "D", "nationality": "Brésilienne", "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 304, "name": "Gabriel Magalhães","position": "D", "nationality": "Brésilienne", "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 305, "name": "Casemiro",         "position": "M", "nationality": "Brésilienne", "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 306, "name": "Lucas Paquetá",    "position": "M", "nationality": "Brésilienne", "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 307, "name": "B. Guimarães",     "position": "M", "nationality": "Brésilienne", "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 308, "name": "Vini Jr.",         "position": "A", "nationality": "Brésilienne", "price": 16.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 309, "name": "Rodrygo",          "position": "A", "nationality": "Brésilienne", "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 310, "name": "Raphinha",         "position": "A", "nationality": "Brésilienne", "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 311, "name": "Endrick",          "position": "A", "nationality": "Brésilienne", "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Angleterre": [
        {"id": 401, "name": "J. Pickford",      "position": "G", "nationality": "Anglaise",   "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 402, "name": "K. Walker",        "position": "D", "nationality": "Anglaise",   "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 403, "name": "H. Maguire",       "position": "D", "nationality": "Anglaise",   "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 404, "name": "J. Gomez",         "position": "D", "nationality": "Anglaise",   "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 405, "name": "L. Shaw",          "position": "D", "nationality": "Anglaise",   "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 406, "name": "D. Rice",          "position": "M", "nationality": "Anglaise",   "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 407, "name": "J. Bellingham",    "position": "M", "nationality": "Anglaise",   "price": 14.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 408, "name": "P. Foden",         "position": "M", "nationality": "Anglaise",   "price": 12.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 409, "name": "H. Kane",          "position": "A", "nationality": "Anglaise",   "price": 13.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 410, "name": "B. Saka",          "position": "A", "nationality": "Anglaise",   "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 411, "name": "M. Salah",         "position": "A", "nationality": "Anglaise",   "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": False},
    ],
    "Espagne": [
        {"id": 501, "name": "U. Simón",         "position": "G", "nationality": "Espagnole",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 502, "name": "D. Carvajal",      "position": "D", "nationality": "Espagnole",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 503, "name": "A. Laporte",       "position": "D", "nationality": "Espagnole",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 504, "name": "R. Le Normand",    "position": "D", "nationality": "Espagnole",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 505, "name": "M. Cucurella",     "position": "D", "nationality": "Espagnole",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 506, "name": "R. Merino",        "position": "M", "nationality": "Espagnole",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 507, "name": "P. Gavi",          "position": "M", "nationality": "Espagnole",  "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 508, "name": "P. Barrios",       "position": "M", "nationality": "Espagnole",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 509, "name": "L. Yamal",         "position": "A", "nationality": "Espagnole",  "price": 13.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 510, "name": "A. Morata",        "position": "A", "nationality": "Espagnole",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 511, "name": "N. Williams",      "position": "A", "nationality": "Espagnole",  "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Allemagne": [
        {"id": 601, "name": "M. ter Stegen",    "position": "G", "nationality": "Allemande",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 602, "name": "J. Kimmich",       "position": "D", "nationality": "Allemande",  "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 603, "name": "A. Rüdiger",       "position": "D", "nationality": "Allemande",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 604, "name": "J. Tah",           "position": "D", "nationality": "Allemande",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 605, "name": "M. Mittelstädt",   "position": "D", "nationality": "Allemande",  "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 606, "name": "T. Müller",        "position": "M", "nationality": "Allemande",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 607, "name": "J. Musiala",       "position": "M", "nationality": "Allemande",  "price": 13.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 608, "name": "F. Wirtz",         "position": "M", "nationality": "Allemande",  "price": 13.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 609, "name": "K. Havertz",       "position": "A", "nationality": "Allemande",  "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 610, "name": "N. Füllkrug",      "position": "A", "nationality": "Allemande",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 611, "name": "L. Gnonto",        "position": "A", "nationality": "Allemande",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": False},
    ],
    "Portugal": [
        {"id": 701, "name": "D. Costa",         "position": "G", "nationality": "Portugaise", "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 702, "name": "D. Dalot",         "position": "D", "nationality": "Portugaise", "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 703, "name": "R. Dias",          "position": "D", "nationality": "Portugaise", "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 704, "name": "P. Magalhães",     "position": "D", "nationality": "Portugaise", "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 705, "name": "N. Mendes",        "position": "D", "nationality": "Portugaise", "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 706, "name": "V. Fernandes",     "position": "M", "nationality": "Portugaise", "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 707, "name": "R. Neves",         "position": "M", "nationality": "Portugaise", "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 708, "name": "J. Palhinha",      "position": "M", "nationality": "Portugaise", "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 709, "name": "C. Ronaldo",       "position": "A", "nationality": "Portugaise", "price": 14.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 710, "name": "R. Leão",          "position": "A", "nationality": "Portugaise", "price": 12.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 711, "name": "G. Ramos",         "position": "A", "nationality": "Portugaise", "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Maroc": [
        {"id": 801, "name": "Y. Bounou",        "position": "G", "nationality": "Marocaine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 802, "name": "A. Hakimi",        "position": "D", "nationality": "Marocaine",  "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 803, "name": "R. Aguerd",        "position": "D", "nationality": "Marocaine",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 804, "name": "N. Mazraoui",      "position": "D", "nationality": "Marocaine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 805, "name": "S. Amrabat",       "position": "M", "nationality": "Marocaine",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 806, "name": "I. Ziyech",        "position": "M", "nationality": "Marocaine",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 807, "name": "A. Ounahi",        "position": "M", "nationality": "Marocaine",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 808, "name": "Y. En-Nesyri",     "position": "A", "nationality": "Marocaine",  "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 809, "name": "H. Dari",          "position": "D", "nationality": "Marocaine",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 810, "name": "S. Benrahma",      "position": "A", "nationality": "Marocaine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Algérie": [
        {"id": 901, "name": "R. M'Bolhi",       "position": "G", "nationality": "Algérienne", "price": 5.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 902, "name": "A. Mandi",         "position": "D", "nationality": "Algérienne", "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 903, "name": "D. Benlamri",      "position": "D", "nationality": "Algérienne", "price": 5.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 904, "name": "H. Bennacer",      "position": "M", "nationality": "Algérienne", "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 905, "name": "A. Mahrez",        "position": "A", "nationality": "Algérienne", "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 906, "name": "B. Bounedjah",     "position": "A", "nationality": "Algérienne", "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 907, "name": "Y. Atal",          "position": "D", "nationality": "Algérienne", "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 908, "name": "S. Feghouli",      "position": "M", "nationality": "Algérienne", "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 909, "name": "A. Slimani",       "position": "A", "nationality": "Algérienne", "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Sénégal": [
        {"id": 1001, "name": "E. Mendy",        "position": "G", "nationality": "Sénégalaise","price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1002, "name": "K. Koulibaly",    "position": "D", "nationality": "Sénégalaise","price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1003, "name": "A. Gaye",         "position": "D", "nationality": "Sénégalaise","price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1004, "name": "P. Gueye",        "position": "M", "nationality": "Sénégalaise","price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1005, "name": "S. Mané",         "position": "A", "nationality": "Sénégalaise","price": 12.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1006, "name": "B. Diallo",       "position": "M", "nationality": "Sénégalaise","price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1007, "name": "N. Jackson",      "position": "A", "nationality": "Sénégalaise","price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1008, "name": "L. Balde",        "position": "D", "nationality": "Sénégalaise","price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Japon": [
        {"id": 1101, "name": "S. Gonda",        "position": "G", "nationality": "Japonaise",  "price": 6.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1102, "name": "H. Sakai",        "position": "D", "nationality": "Japonaise",  "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1103, "name": "K. Itakura",      "position": "D", "nationality": "Japonaise",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1104, "name": "W. Endo",         "position": "M", "nationality": "Japonaise",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1105, "name": "D. Mitoma",       "position": "A", "nationality": "Japonaise",  "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1106, "name": "A. Ueda",         "position": "A", "nationality": "Japonaise",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1107, "name": "K. Kamada",       "position": "M", "nationality": "Japonaise",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_position(raw: str) -> str:
    """Normalise une position brute en G / D / M / A."""
    raw = raw.upper().strip()
    if not raw:
        return "M"  # Défaut milieu si inconnu
    # FBref : GK, DF, MF, FW + variantes multiples (ex: "MF,FW")
    # Soccerway : Goalkeeper, Defender, Midfielder, Forward
    if any(k in raw for k in ("GK", "GOAL", "PORTIER", "KEEPER")):
        return "G"
    if any(k in raw for k in ("DF", "DEF", "BACK", "DEFENDER", "DEFENS")):
        return "D"
    if any(k in raw for k in ("FW", "FOR", "ATTACK", "AVANT", "WINGER", "STRIК")):
        return "A"
    if any(k in raw for k in ("MF", "MID", "MILIEU", "MIDFIELD")):
        return "M"
    # Cas multi-position FBref (ex: "MF,FW") — prendre la première
    first = raw.split(",")[0].strip()
    return _normalize_position(first) if first != raw else "M"


def _estimate_price(performance_score: float, position: str) -> float:
    """
    Estime le prix d'un joueur (5–20M€) basé sur ses performances
    et son poste, pour initialisation de la BDD.
    """
    base_prices = {"G": 6.0, "D": 7.0, "M": 8.0, "A": 9.0}
    base  = base_prices.get(position, 7.0)
    bonus = min(performance_score * 0.5, 10.0)
    price = round(base + bonus, 1)
    return max(4.5, min(price, 20.0))


# ══════════════════════════════════════════════════════════════════════════════
#  API PUBLIQUE — Fonctions exportées (utilisées par main.py)
# ══════════════════════════════════════════════════════════════════════════════

def recuperer_resultats_matchs() -> list[dict]:
    """
    Point d'entrée principal pour récupérer les résultats de matchs.
    Cascade de sources :
      1. FBref (données officielles)
      2. ESPN (fallback live)
      3. Liste statique WC 2026 (ultime fallback)

    Retourne TOUJOURS une liste valide, même vide.
    Format de sortie :
    {
        id, home, away, date, group,
        home_score, away_score,
        is_finished, is_locked, source
    }
    """
    logger.info("🔄 Récupération des résultats de matchs...")

    # Tentative 1 : FBref
    try:
        matches = _scrape_fbref_matches()
        if matches:
            logger.info(f"✅ FBref : {len(matches)} matchs récupérés")
            return matches
    except Exception as e:
        logger.warning(f"FBref matchs échoué : {e}")

    # Tentative 2 : ESPN
    try:
        matches = _scrape_espn_matches()
        if matches:
            logger.info(f"✅ ESPN : {len(matches)} matchs récupérés")
            return matches
    except Exception as e:
        logger.warning(f"ESPN matchs échoué : {e}")

    # Fallback : données statiques WC 2026
    logger.warning("⚠️  Tous les scrapers ont échoué — données statiques utilisées")
    return _get_static_matches()


def recuperer_stats_joueurs() -> list[dict]:
    """
    Point d'entrée principal pour récupérer les stats individuelles.
    Cascade : FBref → Soccerway → données statiques.

    Format de sortie :
    {
        player_id, name, nationality, position,
        minutes, goals, assists,
        clean_sheet, saves, recoveries,
        yellow_cards, red_cards,
        price, source
    }
    """
    logger.info("🔄 Récupération des statistiques joueurs...")

    # Tentative 1 : FBref stats complètes
    try:
        stats = _scrape_fbref_player_stats()
        if stats:
            logger.info(f"✅ FBref : {len(stats)} joueurs avec stats")
            return stats
    except Exception as e:
        logger.warning(f"FBref stats joueurs échoué : {e}")

    # Fallback : données statiques avec stats à zéro (début de tournoi)
    logger.warning("⚠️  Stats joueurs : fallback vers données statiques")
    all_players = []
    counter = 0
    for team_name, squad in _STATIC_SQUADS.items():
        for player in squad:
            counter += 1
            all_players.append({
                "player_id":    player.get("id", counter),
                "name":         player["name"],
                "nationality":  player["nationality"],
                "position":     player["position"],
                "minutes":      0,
                "goals":        player.get("goals", 0),
                "assists":      player.get("assists", 0),
                "clean_sheet":  False,
                "saves":        0,
                "recoveries":   0,
                "yellow_cards": 0,
                "red_cards":    0,
                "price":        player.get("price", 7.0),
                "source":       "static",
            })
    return all_players


def recuperer_effectif_web(team_name: str) -> Optional[list[dict]]:
    """
    Récupère l'effectif d'une équipe nationale spécifique.
    Cascade : Soccerway → données statiques.

    Retourne None si l'équipe est inconnue, liste vide si scraping échoué.
    """
    # Données statiques en priorité (rapide, fiable)
    if team_name in _STATIC_SQUADS:
        static_squad = _STATIC_SQUADS[team_name]
        logger.info(f"📋 Effectif statique {team_name} : {len(static_squad)} joueurs")
        return static_squad

    # Tentative Soccerway si équipe non en statique
    try:
        squad = _scrape_soccerway_squad(team_name)
        if squad:
            return squad
    except Exception as e:
        logger.debug(f"Soccerway {team_name} : {e}")

    logger.info(f"🔒 Équipe inconnue ou non scrapable : {team_name}")
    return None


def get_all_players_market() -> list[dict]:
    """
    Retourne la liste complète de tous les joueurs du marché Fantasy,
    agrégée depuis toutes les équipes disponibles.
    Utilisé pour peupler le marché dans main.py au démarrage.
    """
    all_players = []
    seen_names  = set()

    for team_name, squad in _STATIC_SQUADS.items():
        for player in squad:
            name_key = player["name"].lower().strip()
            if name_key not in seen_names:
                seen_names.add(name_key)
                all_players.append({**player, "team": team_name})

    logger.info(f"🛒 Marché Fantasy : {len(all_players)} joueurs disponibles")
    return all_players


def get_match_details(match_id: str) -> Optional[dict]:
    """
    Récupère les détails complets d'un match spécifique (stats par joueur).
    Utilisé pour le calcul post-match des points Fantasy.
    """
    cache_key = f"match_details_{match_id}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    url = f"https://fbref.com/en/matches/{match_id}/"
    resp = _http_get(url)
    if not resp:
        return None

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        details = {"match_id": match_id, "players": []}

        # Extraire les stats des deux équipes
        for table_id in ["stats_a", "stats_b"]:
            stats_table = soup.find("table", {"id": f"stats_{table_id}_summary"})
            if not stats_table:
                continue
            for row in stats_table.select("tbody > tr:not(.spacer)"):
                name_cell = row.find("td", {"data-stat": "player"})
                if not name_cell:
                    continue

                def g(stat):
                    cell = row.find("td", {"data-stat": stat})
                    val  = cell.get_text(strip=True) if cell else "0"
                    try:
                        return int(float(val or "0"))
                    except (ValueError, TypeError):
                        return 0

                details["players"].append({
                    "name":         name_cell.get_text(strip=True),
                    "minutes":      g("minutes"),
                    "goals":        g("goals"),
                    "assists":      g("assists"),
                    "yellow_cards": g("cards_yellow"),
                    "red_cards":    g("cards_red"),
                    "saves":        g("gk_saves"),
                    "recoveries":   g("ball_recoveries"),
                })

        if details["players"]:
            _cache_set(cache_key, details)
        return details

    except Exception as e:
        logger.error(f"Détails match {match_id} : {e}")
        return None


def force_refresh_cache() -> dict:
    """
    Vide le cache local pour forcer un re-scraping complet.
    Utile pour la route /admin/recalculate.
    """
    try:
        conn = _init_cache_db()
        deleted = conn.execute("DELETE FROM scraper_cache").rowcount
        conn.commit()
        conn.close()
        logger.info(f"🗑️  Cache vidé : {deleted} entrées supprimées")
        return {"deleted": deleted, "status": "cache_cleared"}
    except Exception as e:
        logger.error(f"Erreur vidage cache : {e}")
        return {"deleted": 0, "status": "error", "detail": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
#  MATCHS STATIQUES — Structure complète WC 2026 (fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _get_static_matches() -> list[dict]:
    """Retourne la liste statique complète des matchs WC 2026."""
    return [
        # ── Groupes USA / Canada / Mexique ──────────────────────────────────
        {"id": 1,  "home": "USA",       "away": "Canada",       "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 2,  "home": "Mexique",   "away": "Jamaïque",     "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 3,  "home": "Canada",    "away": "Jamaïque",     "group": "Groupe A", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 4,  "home": "USA",       "away": "Mexique",      "group": "Groupe A", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        # ── Groupe B ─────────────────────────────────────────────────────────
        {"id": 5,  "home": "France",    "away": "Belgique",     "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 6,  "home": "Maroc",     "away": "Tunisie",      "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 7,  "home": "France",    "away": "Maroc",        "group": "Groupe B", "date": "2026-06-16", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 8,  "home": "Belgique",  "away": "Tunisie",      "group": "Groupe B", "date": "2026-06-16", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        # ── Groupe C ─────────────────────────────────────────────────────────
        {"id": 9,  "home": "Brésil",    "away": "Argentine",    "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 10, "home": "Uruguay",   "away": "Équateur",     "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 11, "home": "Brésil",    "away": "Uruguay",      "group": "Groupe C", "date": "2026-06-17", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 12, "home": "Argentine", "away": "Équateur",     "group": "Groupe C", "date": "2026-06-17", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        # ── Groupe D ─────────────────────────────────────────────────────────
        {"id": 13, "home": "Angleterre","away": "Allemagne",    "group": "Groupe D", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 14, "home": "Pays-Bas",  "away": "Croatie",      "group": "Groupe D", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 15, "home": "Angleterre","away": "Pays-Bas",     "group": "Groupe D", "date": "2026-06-17", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 16, "home": "Allemagne", "away": "Croatie",      "group": "Groupe D", "date": "2026-06-17", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        # ── Groupe E ─────────────────────────────────────────────────────────
        {"id": 17, "home": "Espagne",   "away": "Portugal",     "group": "Groupe E", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 18, "home": "Turquie",   "away": "Grèce",        "group": "Groupe E", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 19, "home": "Espagne",   "away": "Turquie",      "group": "Groupe E", "date": "2026-06-18", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 20, "home": "Portugal",  "away": "Grèce",        "group": "Groupe E", "date": "2026-06-18", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        # ── Groupe F ─────────────────────────────────────────────────────────
        {"id": 21, "home": "Japon",     "away": "Corée du Sud", "group": "Groupe F", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 22, "home": "Australie", "away": "Iran",         "group": "Groupe F", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        # ── Groupe G ─────────────────────────────────────────────────────────
        {"id": 23, "home": "Sénégal",   "away": "Algérie",      "group": "Groupe G", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 24, "home": "Nigéria",   "away": "Côte d'Ivoire","group": "Groupe G", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        # ── Groupe H ─────────────────────────────────────────────────────────
        {"id": 25, "home": "Colombie",  "away": "Pologne",      "group": "Groupe H", "date": "2026-06-16", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
        {"id": 26, "home": "Serbie",    "away": "Suisse",       "group": "Groupe H", "date": "2026-06-16", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False, "source": "static"},
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  DIAGNOSTIC — Script de test autonome
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    print("\n" + "=" * 60)
    print("  DIAGNOSTIC SCRAPER — Fantasy Boulzazen WC 2026")
    print("=" * 60)

    print("\n[1/3] Test récupération des matchs...")
    matches = recuperer_resultats_matchs()
    print(f"  → {len(matches)} matchs récupérés")
    if matches:
        m = matches[0]
        print(f"  → Exemple : {m['home']} vs {m['away']} ({m['date']}) — Source: {m.get('source')}")

    print("\n[2/3] Test stats joueurs...")
    stats = recuperer_stats_joueurs()
    print(f"  → {len(stats)} joueurs avec stats")
    if stats:
        s = stats[0]
        print(f"  → Exemple : {s['name']} ({s['position']}) — {s['goals']} buts — Source: {s.get('source')}")

    print("\n[3/3] Test effectif France...")
    squad = recuperer_effectif_web("France")
    if squad:
        print(f"  → {len(squad)} joueurs dans l'effectif France")
        print(f"  → Exemple : {squad[0]['name']} ({squad[0]['position']}) — {squad[0]['price']}M€")
    else:
        print("  → Effectif France non disponible")

    print("\n✅ Diagnostic terminé")
    print("=" * 60)