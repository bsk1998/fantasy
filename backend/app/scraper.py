"""
scraper.py — Pipeline Groq Sofascore + Olympics pour Fantasy Boulzazen WC 2026
================================================================================

Architecture :
  1. Playwright (async) pour charger JS → HTML complet
  2. Fallback httpx + BeautifulSoup si Playwright échoue
  3. Groq IA pour structurer le texte brut en JSON propre
  4. Synchronisation BDD atomique via _sync_to_db()
  5. Cache intelligent avec versioning pour le frontend
"""

import asyncio
import logging
import json
import os
import time
import re
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger("fantasy_scraper")

# ── Imports optionnels ────────────────────────────────────────────────────────
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning("⚠️  Playwright non installé — pip install playwright")
    PLAYWRIGHT_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    logger.warning("⚠️  httpx non installé — pip install httpx")
    HTTPX_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    logger.warning("⚠️  BeautifulSoup4 non installé — pip install beautifulsoup4")
    BS4_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    logger.warning("⚠️  Groq non installé — pip install groq")
    GROQ_AVAILABLE = False

# ── Configuration ─────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama3-8b-8192"

# URLs sources officielles
URL_SOFASCORE = "https://www.sofascore.com/fr/football/tournament/world/world-championship/16#id:58210"
URL_OLYMPICS = "https://www.olympics.com/fr/infos/coupe-du-monde-2026-composition-equipes-selections-liste-joueurs"

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Cache en mémoire {key: (timestamp, data)}
_cache: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes

# Singleton Playwright
_playwright_browser: Optional[Browser] = None

# Métadonnées de scraping
_scraping_status = {
    "sofascore": {"last_at": None, "status": "pending", "items": 0, "error": None},
    "olympics": {"last_at": None, "status": "pending", "items": 0, "error": None},
    "data_version_hash": None,
}


# ════════════════════════════════════════════════════════════════════════════════
#  GESTION NAVIGATEUR PLAYWRIGHT
# ════════════════════════════════════════════════════════════════════════════════

async def _get_playwright_browser() -> Optional[Browser]:
    """Initialise ou retourne le navigateur Playwright singleton."""
    global _playwright_browser
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    if _playwright_browser is None:
        try:
            playwright = await async_playwright().start()
            _playwright_browser = await playwright.chromium.launch(headless=True)
            logger.info("✅ Navigateur Playwright initialisé (headless)")
        except Exception as e:
            logger.error(f"❌ Erreur Playwright : {e}")
            return None
    
    return _playwright_browser


async def _close_playwright_browser() -> None:
    """Ferme le navigateur Playwright."""
    global _playwright_browser
    if _playwright_browser:
        try:
            await _playwright_browser.close()
            _playwright_browser = None
            logger.info("✅ Navigateur Playwright fermé")
        except Exception as e:
            logger.error(f"⚠️  Erreur fermeture Playwright : {e}")


# ════════════════════════════════════════════════════════════════════════════════
#  RÉCUPÉRATION HTML
# ════════════════════════════════════════════════════════════════════════════════

async def _fetch_url_playwright(url: str, timeout_ms: int = 35000) -> Optional[str]:
    """Récupère HTML avec Playwright (JS rendu)."""
    browser = await _get_playwright_browser()
    if not browser:
        return None

    page = None
    try:
        page = await browser.new_page()
        await page.set_extra_http_headers(HTTP_HEADERS)
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        await asyncio.sleep(2)  # Attendre scripts async
        html = await page.content()
        logger.info(f"✅ Playwright: {url[:50]}...")
        return html
    except Exception as e:
        logger.warning(f"⚠️  Playwright échoue: {e}")
        return None
    finally:
        if page:
            try:
                await page.close()
            except:
                pass


async def _fetch_url_httpx(url: str, timeout: int = 20) -> Optional[str]:
    """Fallback httpx (sans JS)."""
    if not HTTPX_AVAILABLE:
        return None

    try:
        async with httpx.AsyncClient(
            headers=HTTP_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            logger.info(f"✅ httpx: {url[:50]}...")
            return response.text
    except Exception as e:
        logger.warning(f"⚠️  httpx échoue: {e}")
        return None


async def _fetch_url(url: str) -> Optional[str]:
    """Récupère HTML : Playwright → httpx fallback."""
    html = await _fetch_url_playwright(url)
    if html:
        return html
    logger.info(f"🔄 Fallback httpx pour : {url[:50]}...")
    return await _fetch_url_httpx(url)


# ════════════════════════════════════════════════════════════════════════════════
#  NETTOYAGE HTML
# ════════════════════════════════════════════════════════════════════════════════

def _nettoyer_html(html: str) -> str:
    """Extrait le texte utile du HTML."""
    if not BS4_AVAILABLE:
        return html[:4000]

    soup = BeautifulSoup(html, "html.parser")
    
    for tag in soup(["script", "style", "nav", "footer", "head", "iframe", "noscript"]):
        tag.decompose()

    texte = soup.get_text(separator="\n", strip=True)
    lignes = [l for l in texte.splitlines() if l.strip()]
    return "\n".join(lignes)[:4000]


# ════════════════════════════════════════════════════════════════════════════════
#  APPELS GROQ IA
# ════════════════════════════════════════════════════════════════════════════════

def _appeler_groq(prompt_systeme: str, contenu: str, max_tokens: int = 2000) -> Optional[Dict[str, Any]]:
    """Envoie du texte à Groq pour extraction JSON."""
    if not GROQ_AVAILABLE or not GROQ_API_KEY:
        logger.warning("⚠️  Groq non disponible")
        return None

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": contenu},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
        )
        texte_reponse = completion.choices[0].message.content
        match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', texte_reponse)
        if match:
            return json.loads(match.group(0))
        else:
            logger.warning("❌ Groq n'a pas retourné de JSON valide")
            return None
    except json.JSONDecodeError as e:
        logger.error(f"❌ Erreur parsing JSON Groq : {e}")
    except Exception as e:
        logger.error(f"❌ Erreur appel Groq : {e}")
    
    return None


# ════════════════════════════════════════════════════════════════════════════════
#  SCRAPING SOFASCORE
# ══════════════��═════════════════════════════════════════════════════════════════

PROMPT_SOFASCORE = """Tu es un extracteur de données football expert. Analyse ce contenu HTML/texte de Sofascore
et extrais TOUTES les données disponibles au format JSON strict suivant (UNIQUEMENT le JSON, sans texte autour) :
{
  "matches": [{
    "id": "string_unique",
    "home": "Nom équipe domicile",
    "away": "Nom équipe extérieure",
    "group": "Groupe A|B|C|etc (null si phase élim)",
    "round": "group_stage|r16|qf|sf|third_place|final",
    "date": "YYYY-MM-DD",
    "kickoff_utc": "ISO8601",
    "home_score": "int|null",
    "away_score": "int|null",
    "status": "scheduled|live|finished",
    "player_stats": [{
      "player_name": "Nom",
      "team": "Équipe",
      "goals": "int",
      "assists": "int",
      "yellow_cards": "int",
      "red_cards": "int",
      "minutes_played": "int",
      "saves": "int|null",
      "ball_recoveries": "int|null",
      "clean_sheet": "bool|null"
    }]
  }],
  "group_standings": {
    "Groupe A": [{
      "team": "Pays",
      "played": "int",
      "won": "int",
      "drawn": "int",
      "lost": "int",
      "goals_for": "int",
      "goals_against": "int",
      "goal_diff": "int",
      "points": "int"
    }]
  }
}
Retourne UNIQUEMENT le JSON valide."""


async def scraper_sofascore() -> Dict[str, Any]:
    """Scrape Sofascore pour matchs et classements."""
    logger.info("🌐 Scraping Sofascore en cours...")
    
    cache_key = "sofascore_data"
    cached = _cache.get(cache_key)
    if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
        logger.info("✅ Sofascore depuis cache")
        return cached[1]

    html = await _fetch_url(URL_SOFASCORE)
    if not html:
        logger.warning("⚠️  Sofascore inaccessible")
        return {}

    texte_propre = _nettoyer_html(html)
    resultat = _appeler_groq(PROMPT_SOFASCORE, texte_propre, max_tokens=3500)

    if resultat:
        _cache[cache_key] = (time.time(), resultat)
        _scraping_status["sofascore"]["items"] = len(resultat.get("matches", []))
        logger.info(f"✅ Sofascore: {_scraping_status['sofascore']['items']} matchs")
        return resultat

    return {}


# ════════════════════════════════════════════════════════════════════════════════
#  SCRAPING OLYMPICS (EFFECTIFS)
# ════════════════════════════════════════════════════════════════════════════════

PROMPT_OLYMPICS = """Tu es un extracteur d'effectifs de football expert. Analyse ce contenu HTML/texte
et extrais pour chaque nation dont la liste est visible (UNIQUEMENT le JSON, pas de texte) :
{
  "squads": [{
    "nation": "Nom du pays en français",
    "squad_status": "definitive|provisoire|non_publiee",
    "is_locked": "bool (true si non_publiee ou provisoire)",
    "coach_name": "Nom Prénom|null",
    "players": [{
      "name": "Prénom Nom",
      "position": "G|D|M|A",
      "club": "Nom club|null",
      "number": "int|null"
    }]
  }]
}
RÈGLE CRITIQUE : n'inclure une nation que si au moins UN joueur est lisible dans le texte.
Retourne UNIQUEMENT le JSON valide."""


async def scraper_effectifs_olympics() -> List[Dict[str, Any]]:
    """Scrape Olympics pour effectifs officiels."""
    logger.info("🌐 Scraping Olympics (effectifs) en cours...")
    
    cache_key = "olympics_squads"
    cached = _cache.get(cache_key)
    if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
        logger.info("✅ Olympics depuis cache")
        return cached[1]

    html = await _fetch_url(URL_OLYMPICS)
    if not html:
        logger.warning("⚠️  Olympics inaccessible")
        return []

    texte_propre = _nettoyer_html(html)
    resultat = _appeler_groq(PROMPT_OLYMPICS, texte_propre, max_tokens=3000)

    if resultat and isinstance(resultat.get("squads"), list):
        squads = resultat["squads"]
        _cache[cache_key] = (time.time(), squads)
        _scraping_status["olympics"]["items"] = len(squads)
        logger.info(f"✅ Olympics: {len(squads)} effectifs")
        return squads

    return []


# ════════════════════════════════════════════════════════════════════════════════
#  SYNCHRONISATION BDD
# ════════════════════════════════════════════════════════════════════════════════

async def _sync_to_db(sofascore_data: Dict, olympics_data: List, db) -> None:
    """Synchronise les données scrappées dans la BD de manière atomique."""
    from app.models import MatchResult, Player, Coach, TeamNation, GroupStanding, ScrapingMetadata
    from sqlalchemy import delete
    
    logger.info("🔄 Synchronisation BDD en cours...")
    
    try:
        # ── Synchroniser matchs Sofascore ──
        if sofascore_data.get("matches"):
            for match_data in sofascore_data["matches"]:
                match = db.query(MatchResult).filter(
                    MatchResult.sofascore_id == match_data["id"]
                ).first()
                
                if not match:
                    match = MatchResult(sofascore_id=match_data["id"])
                    db.add(match)
                
                match.home = match_data.get("home")
                match.away = match_data.get("away")
                match.group = match_data.get("group")
                match.round = match_data.get("round", "group_stage")
                match.date = match_data.get("date")
                match.kickoff_utc = match_data.get("kickoff_utc")
                match.home_score = match_data.get("home_score")
                match.away_score = match_data.get("away_score")
                match.status = match_data.get("status", "scheduled")
                match.player_stats = match_data.get("player_stats", {})
                match.last_updated = datetime.utcnow().isoformat()

        # ── Synchroniser classements groupes ──
        if sofascore_data.get("group_standings"):
            for group_name, standings in sofascore_data["group_standings"].items():
                for team_data in standings:
                    standing = db.query(GroupStanding).filter(
                        GroupStanding.group_name == group_name,
                        GroupStanding.team == team_data.get("team")
                    ).first()
                    
                    if not standing:
                        standing = GroupStanding(
                            group_name=group_name,
                            team=team_data.get("team")
                        )
                        db.add(standing)
                    
                    standing.played = team_data.get("played", 0)
                    standing.won = team_data.get("won", 0)
                    standing.drawn = team_data.get("drawn", 0)
                    standing.lost = team_data.get("lost", 0)
                    standing.goals_for = team_data.get("goals_for", 0)
                    standing.goals_against = team_data.get("goals_against", 0)
                    standing.goal_diff = team_data.get("goal_diff", 0)
                    standing.points = team_data.get("points", 0)
                    standing.last_updated = datetime.utcnow().isoformat()

        # ── Synchroniser effectifs Olympics ──
        for squad_data in olympics_data:
            nation = squad_data.get("nation")
            
            team_nation = db.query(TeamNation).filter(
                TeamNation.name == nation
            ).first()
            
            if not team_nation:
                team_nation = TeamNation(name=nation)
                db.add(team_nation)
            
            squad_status = squad_data.get("squad_status", "non_publiee")
            team_nation.squad_status = squad_status
            team_nation.is_locked = squad_data.get("is_locked", True)
            team_nation.coach_name = squad_data.get("coach_name")
            team_nation.last_updated = datetime.utcnow().isoformat()
            
            if squad_status == "definitive":
                team_nation.squad_published_at = datetime.utcnow().isoformat()
            
            db.flush()  # Créer team_nation.id si nouveau
            
            # ── Synchroniser joueurs ──
            # Supprimer les anciens joueurs si changement de statut
            if squad_status == "definitive":
                db.query(Player).filter(Player.team_id == team_nation.id).delete()
            
            for player_data in squad_data.get("players", []):
                player = db.query(Player).filter(
                    Player.name == player_data.get("name"),
                    Player.team_id == team_nation.id
                ).first()
                
                if not player:
                    player = Player(
                        name=player_data.get("name"),
                        team_id=team_nation.id
                    )
                    db.add(player)
                
                player.position = player_data.get("position", "M")
                player.nationality = nation
                player.is_confirmed = True
                player.price = _estimer_prix(player_data.get("position", "M"))
                player.last_stat_update = datetime.utcnow().isoformat()

        # ── Mettre à jour métadonnées ──
        for source in ["sofascore", "olympics"]:
            metadata = db.query(ScrapingMetadata).filter(
                ScrapingMetadata.source == source
            ).first()
            
            if not metadata:
                metadata = ScrapingMetadata(source=source)
                db.add(metadata)
            
            metadata.last_scrape_at = datetime.utcnow().isoformat()
            metadata.last_success_at = datetime.utcnow().isoformat()
            metadata.status = "success"
            metadata.items_scraped = _scraping_status[source]["items"]
            metadata.data_version_hash = _compute_data_version_hash(db)

        db.commit()
        logger.info("✅ Synchronisation BDD réussie")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur sync BDD : {e}")
        raise


def _estimer_prix(poste: str) -> float:
    """Estime le prix Fantasy par poste."""
    poste_norm = poste.upper() if poste else "M"
    prix = {"G": 5.5, "D": 6.0, "M": 7.0, "A": 7.5}
    return prix.get(poste_norm, 6.0)


def _compute_data_version_hash(db) -> str:
    """Calcule un hash pour invalider le cache client si les données changent."""
    from app.models import Player, MatchResult, TeamNation
    
    players_count = db.query(Player).count()
    matches_count = db.query(MatchResult).count()
    teams_count = db.query(TeamNation).count()
    
    data_str = f"{players_count}_{matches_count}_{teams_count}"
    return hashlib.md5(data_str.encode()).hexdigest()[:8]


# ════════════════════════════════════════════════════════════════════════════════
#  ORCHESTRATEUR
# ════════════════════════════════════════════════════════════════════════════════

async def scraping_complet(db=None) -> Dict[str, Any]:
    """Lance le scraping complet de toutes les sources."""
    logger.info("🚀 Scraping complet lancé...")
    
    try:
        # Récupérer les données
        sofascore_data = await scraper_sofascore()
        olympics_data = await scraper_effectifs_olympics()
        
        # Synchroniser en BD si session fournie
        if db:
            await _sync_to_db(sofascore_data, olympics_data, db)
        
        return {
            "sofascore": sofascore_data,
            "olympics": olympics_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur scraping complet : {e}")
        return {}


def get_scraping_status() -> Dict[str, Any]:
    """Retourne le statut du dernier scraping."""
    return {
        "sofascore": _scraping_status["sofascore"],
        "olympics": _scraping_status["olympics"],
        "data_version_hash": _scraping_status["data_version_hash"],
    }


async def cleanup():
    """Cleanup au shutdown."""
    await _close_playwright_browser()
