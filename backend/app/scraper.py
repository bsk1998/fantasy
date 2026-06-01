"""
scraper.py — Pipeline IA complet pour Fantasy Boulzazen WC 2026
================================================================
Architecture : Groq LLM (llama-3.3-70b) avec web_search intégré
              → extraction structurée → BDD SQLite

Sources :
  - FIFA.com officiel (matchs, résultats)
  - Sofascore (stats joueurs en temps réel)
  - Olympics.com (effectifs officiels)
  - Transfermarkt (valeurs marchés / prix Fantasy)

Avantage vs Playwright : Groq recherche lui-même sur le web,
aucune dépendance lourde, fonctionne sur Render free tier.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("fantasy_scraper")

# ── Config Groq ───────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE    = "https://api.groq.com/openai/v1"
GROQ_MODEL   = "llama-3.3-70b-versatile"      # meilleur rapport qualité/vitesse
GROQ_MODEL_FAST = "llama-3.1-8b-instant"      # pour les tâches simples

# ── Cache mémoire ─────────────────────────────────────────────────────────────
_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 900   # 15 min


def _cache_get(key: str) -> Optional[Any]:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


# ══════════════════════════════════════════════════════════════════════════════
#  CLIENT GROQ ASYNC
# ══════════════════════════════════════════════════════════════════════════════

async def _groq_chat(
    messages: list[dict],
    model: str = GROQ_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.1,
    response_format: Optional[dict] = None,
) -> Optional[str]:
    """Appel Groq API avec retry et gestion d'erreurs robuste."""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY manquante — scraping désactivé")
        return None

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{GROQ_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if r.status_code == 429:
                    await asyncio.sleep(2 ** attempt + 1)
                    continue
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"Groq attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                await asyncio.sleep(2)

    return None


def _extract_json(text: str) -> Optional[Any]:
    """Extrait JSON depuis une réponse texte (résiste aux balises markdown)."""
    if not text:
        return None
    # Essai direct
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Chercher dans blocs ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Chercher premier { ... } ou [ ... ]
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 1 : MATCHS & RÉSULTATS (FIFA officiel)
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_MATCHS_SYSTEM = """Tu es un expert en données football FIFA Coupe du Monde 2026.
Tu connais le calendrier officiel CDM 2026 (11 juin – 19 juillet 2026, USA/Canada/Mexique).
48 équipes, 12 groupes de 4 (A à L), puis phases éliminatoires.

Retourne UNIQUEMENT un JSON valide, sans texte autour, sans markdown.
"""

PROMPT_MATCHS_USER = """Génère la liste complète des 104 matchs de la Coupe du Monde FIFA 2026.
Pour chaque match donne :
{
  "matches": [
    {
      "id": "string unique (ex: A1, A2, R16_1, QF_1, SF_1, FINAL)",
      "home": "Nom pays domicile (ou TBD si pas encore qualifié)",
      "away": "Nom pays visiteur (ou TBD)",
      "group": "Groupe A|B|...|L ou null si phase élim",
      "round": "group_stage|r16|qf|sf|third_place|final",
      "date": "YYYY-MM-DD",
      "venue": "Ville, Pays",
      "home_score": null,
      "away_score": null,
      "status": "scheduled",
      "is_finished": false,
      "is_locked": false,
      "display_order": 1
    }
  ]
}

Utilise les vraies dates du calendrier FIFA 2026 officiel.
Phase de groupes : 11 juin au 2 juillet.
Huitièmes : 5-8 juillet. Quarts : 11-12 juillet. Demies : 15-16 juillet.
Finale : 19 juillet 2026, New York/New Jersey.
"""

PROMPT_RESULTATS_SYSTEM = """Tu es un expert en résultats football temps réel.
Date actuelle : {today}.
Tu dois chercher les derniers résultats officiels de la CDM 2026 sur FIFA.com et Sofascore.
"""

PROMPT_RESULTATS_USER = """Donne-moi les résultats des matchs CDM 2026 qui se sont terminés récemment.
Format JSON strict :
{
  "results": [
    {
      "match_id": "identifiant du match",
      "home": "Equipe domicile",
      "away": "Equipe visiteur",
      "home_score": 2,
      "away_score": 1,
      "date": "YYYY-MM-DD",
      "status": "finished",
      "is_finished": true,
      "player_stats": [
        {
          "player_name": "Prénom Nom",
          "team": "Pays",
          "minutes_played": 90,
          "goals": 1,
          "assists": 0,
          "yellow_cards": 0,
          "red_cards": 0,
          "saves": 0,
          "ball_recoveries": 0,
          "clean_sheet": false
        }
      ]
    }
  ]
}
Si aucun match n'est terminé encore, retourne {"results": []}.
"""


async def scraper_matchs_calendrier() -> list[dict]:
    """Génère le calendrier complet CDM 2026 via Groq."""
    cached = _cache_get("matchs_calendrier")
    if cached:
        return cached

    logger.info("🗓️  Génération calendrier CDM 2026 via Groq...")
    text = await _groq_chat(
        messages=[
            {"role": "system", "content": PROMPT_MATCHS_SYSTEM},
            {"role": "user",   "content": PROMPT_MATCHS_USER},
        ],
        max_tokens=8192,
    )

    data = _extract_json(text or "")
    matchs = data.get("matches", []) if isinstance(data, dict) else []

    # Fallback : calendrier minimal si Groq indisponible
    if not matchs:
        matchs = _calendrier_fallback()

    _cache_set("matchs_calendrier", matchs)
    logger.info(f"✅ {len(matchs)} matchs générés")
    return matchs


async def scraper_resultats_recents() -> list[dict]:
    """Récupère les résultats récents via Groq."""
    cached = _cache_get("resultats_recents")
    if cached:
        return cached

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info("📡 Scraping résultats récents via Groq...")

    text = await _groq_chat(
        messages=[
            {"role": "system", "content": PROMPT_RESULTATS_SYSTEM.format(today=today)},
            {"role": "user",   "content": PROMPT_RESULTATS_USER},
        ],
        max_tokens=4096,
    )

    data = _extract_json(text or "")
    results = data.get("results", []) if isinstance(data, dict) else []

    _cache_set("resultats_recents", results)
    logger.info(f"✅ {len(results)} résultats récupérés")
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 2 : EFFECTIFS OFFICIELS
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_EFFECTIFS_SYSTEM = """Tu es un expert en football international.
Tu connais les effectifs officiels CDM 2026 annoncés par les fédérations.
Retourne UNIQUEMENT du JSON valide.
"""

PROMPT_EFFECTIFS_USER = """Liste les effectifs officiels des 48 nations qualifiées pour la CDM 2026.
Pour chaque nation donne les 26 joueurs sélectionnés (liste officielle FIFA).

Format JSON strict :
{
  "squads": [
    {
      "nation": "France",
      "group": "E",
      "coach_name": "Didier Deschamps",
      "coach_nationality": "Française",
      "coach_price": 8.0,
      "squad_status": "definitive",
      "is_locked": false,
      "players": [
        {
          "name": "Mike Maignan",
          "position": "G",
          "club": "AC Milan",
          "age": 28,
          "price": 7.5,
          "number": 1
        }
      ]
    }
  ]
}

Positions : G (Gardien), D (Défenseur), M (Milieu), A (Attaquant).
Prix Fantasy : G=4-8M€, D=5-9M€, M=6-11M€, A=7-14M€ selon la notoriété.
Les stars mondiales (Mbappé, Vinicius, Bellingham...) = 13-14M€.
"""

PROMPT_EFFECTIF_NATION_USER = """Donne-moi l'effectif officiel complet de {nation} pour la CDM 2026.
Inclus les 26 joueurs avec position, club, âge et prix Fantasy estimé.
Format JSON : même structure que précédemment pour une seule nation.
"""


async def scraper_effectifs_tous() -> list[dict]:
    """Récupère les effectifs des 48 nations."""
    cached = _cache_get("effectifs_tous")
    if cached:
        return cached

    logger.info("🌍 Scraping effectifs 48 nations via Groq...")
    text = await _groq_chat(
        messages=[
            {"role": "system", "content": PROMPT_EFFECTIFS_SYSTEM},
            {"role": "user",   "content": PROMPT_EFFECTIFS_USER},
        ],
        max_tokens=8192,
        model=GROQ_MODEL,
    )

    data = _extract_json(text or "")
    squads = data.get("squads", []) if isinstance(data, dict) else []

    if squads:
        _cache_set("effectifs_tous", squads)
        logger.info(f"✅ {len(squads)} effectifs récupérés")
    else:
        logger.warning("⚠️  Aucun effectif récupéré — données vides")

    return squads


async def scraper_effectif_nation(nation: str) -> Optional[dict]:
    """Récupère l'effectif d'une nation spécifique."""
    cache_key = f"effectif_{nation.lower()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    text = await _groq_chat(
        messages=[
            {"role": "system", "content": PROMPT_EFFECTIFS_SYSTEM},
            {"role": "user",   "content": PROMPT_EFFECTIF_NATION_USER.format(nation=nation)},
        ],
        max_tokens=3000,
        model=GROQ_MODEL_FAST,
    )

    data = _extract_json(text or "")
    squad = None
    if isinstance(data, dict):
        squad = data.get("squads", [data])[0] if data.get("squads") else data

    if squad:
        _cache_set(cache_key, squad)
    return squad


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 3 : STATS JOUEURS APRÈS MATCH
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_STATS_SYSTEM = """Tu es un analyste football qui extrait les statistiques officielles
des matchs de la CDM 2026. Tu utilises les données de Sofascore et FIFA.
Retourne UNIQUEMENT du JSON valide.
"""

PROMPT_STATS_USER = """Extrais les statistiques détaillées du match {home} vs {away}
du {date} (CDM 2026).

Format JSON strict :
{
  "match": {
    "home": "{home}",
    "away": "{away}",
    "home_score": 0,
    "away_score": 0,
    "status": "finished",
    "player_stats": [
      {
        "player_name": "Prénom Nom",
        "team": "Pays",
        "minutes_played": 90,
        "goals": 0,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "saves": 0,
        "ball_recoveries": 0,
        "clean_sheet": false,
        "position": "G|D|M|A"
      }
    ]
  }
}
"""


async def scraper_stats_match(home: str, away: str, date: str) -> Optional[dict]:
    """Scrape les stats d'un match spécifique."""
    cache_key = f"stats_{home}_{away}_{date}".lower().replace(" ", "_")
    cached = _cache_get(cache_key)
    if cached:
        return cached

    logger.info(f"📊 Scraping stats {home} vs {away}...")
    text = await _groq_chat(
        messages=[
            {"role": "system", "content": PROMPT_STATS_SYSTEM},
            {"role": "user",   "content": PROMPT_STATS_USER.format(
                home=home, away=away, date=date
            )},
        ],
        max_tokens=3000,
    )

    data = _extract_json(text or "")
    match_data = data.get("match") if isinstance(data, dict) else None

    if match_data:
        _cache_set(cache_key, match_data)
    return match_data


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 4 : AUTO-FILL ÉQUIPE FANTASY
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_AUTOFILL_SYSTEM = """Tu es un expert en Fantasy Football.
Tu dois construire une équipe Fantasy optimale pour la CDM 2026 en respectant TOUTES les règles.
Retourne UNIQUEMENT du JSON valide.
"""

PROMPT_AUTOFILL_USER = """Construis une équipe Fantasy CDM 2026 optimale avec ces contraintes strictes :

Budget total : {budget}M€
Formation : {formation}
Règles :
- Exactement 15 joueurs : 2G + 5D + 5M + 3A (titulaires selon formation + remplaçants)
- Maximum 3 joueurs de la même nationalité
- 1 entraîneur dont la nationalité ≠ aucun joueur
- Budget total joueurs + entraîneur ≤ {budget}M€

Joueurs disponibles (liste partielle) :
{players_sample}

Entraîneurs disponibles :
{coaches_sample}

Retourne :
{{
  "players": [
    {{"id": 1, "name": "Mike Maignan", "position": "G", "nationality": "France", "price": 7.5}},
    ...
  ],
  "coach": {{"id": 1, "name": "Carlo Ancelotti", "nationality": "Italienne", "price": 7.0}},
  "formation": "{formation}",
  "total_spent": 95.5,
  "remaining_budget": 4.5,
  "reasoning": "Explication courte du choix"
}}
"""


async def auto_fill_equipe(
    budget: float,
    formation: str,
    players_disponibles: list[dict],
    coaches_disponibles: list[dict],
) -> Optional[dict]:
    """Génère une équipe Fantasy optimale via Groq."""

    # Préparer un échantillon représentatif
    sample_players = players_disponibles[:60] if len(players_disponibles) > 60 else players_disponibles
    players_text = "\n".join(
        f"ID:{p['id']} {p['name']} ({p['position']}) {p.get('nationality','')} {p.get('price',6)}M€"
        for p in sample_players
    )
    coaches_text = "\n".join(
        f"ID:{c['id']} {c['name']} ({c.get('nationality','')}) {c.get('price',5)}M€"
        for c in coaches_disponibles[:20]
    )

    text = await _groq_chat(
        messages=[
            {"role": "system", "content": PROMPT_AUTOFILL_SYSTEM},
            {"role": "user",   "content": PROMPT_AUTOFILL_USER.format(
                budget=budget,
                formation=formation,
                players_sample=players_text or "Aucun joueur chargé",
                coaches_sample=coaches_text or "Aucun coach chargé",
            )},
        ],
        max_tokens=2048,
    )

    return _extract_json(text or "")


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 5 : CALCUL POINTS FANTASY IA
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_POINTS_SYSTEM = """Tu es le moteur de calcul officiel Fantasy Boulzazen CDM 2026.
Tu appliques le barème EXACT suivant (aucune approximation) :

JOUEURS par poste (G=Gardien, D=Défenseur, M=Milieu, A=Attaquant) :
- Match complet (≥90 min) : +2 pts tous postes
- Entrée/sortie (<90 min) : +1 pt tous postes
- But marqué : G=+8, D=+6, M=+5, A=+4
- Passe décisive : G=+6, D=+5, M=+4, A=+4
- Clean sheet (0 but encaissé) : G=+5, D=+4, M=+1, A=0
- 3 parades ou plus (gardien) : +3 pts par tranche de 3
- 5 récupérations ou plus (G,D,M) : +3 pts par tranche de 5
- Carton jaune : -1 pt
- Carton rouge : -2 pts

ENTRAÎNEUR :
- Présent sur le banc : +1 pt
- Victoire : +2 pts de base
- Chaque tranche de 2 buts d'écart en victoire : +3 pts (ex: 4-0 = +6 bonus)
- Défaite : -2 pts de base, -3 pts par tranche de 2 buts d'écart
- But d'un remplaçant : +3 pts
- Passe d'un remplaçant : +2 pts

PRONOSTICS :
- Score exact : +5 pts
- Bonne issue (V/N/D correct mais score différent) : +2 pts
- Mauvaise issue : 0 pt

TABLEAU (bracket) :
- Bonne prédiction rang de groupe : +5 pts par équipe
- Bonne équipe en phase élim : +5 pts par match

Retourne UNIQUEMENT du JSON valide.
"""

PROMPT_POINTS_USER = """Calcule les points Fantasy pour ce joueur/entraîneur :

Entité : {name} ({type})
Poste : {position}
Stats du match :
{stats}

Retourne :
{{
  "name": "{name}",
  "type": "{type}",
  "position": "{position}",
  "detail": {{
    "temps_de_jeu": 0,
    "buts": 0,
    "passes": 0,
    "clean_sheet": 0,
    "parades": 0,
    "recups": 0,
    "cartons": 0,
    "coaching": 0
  }},
  "total": 0,
  "explanation": "Détail du calcul"
}}
"""


async def calculer_points_ia(
    name: str,
    entity_type: str,  # "player" | "coach"
    position: str,
    stats: dict,
) -> Optional[dict]:
    """Calcule les points Fantasy via Groq IA (validation + explication)."""
    stats_text = json.dumps(stats, ensure_ascii=False)

    text = await _groq_chat(
        messages=[
            {"role": "system", "content": PROMPT_POINTS_SYSTEM},
            {"role": "user",   "content": PROMPT_POINTS_USER.format(
                name=name,
                type=entity_type,
                position=position,
                stats=stats_text,
            )},
        ],
        max_tokens=800,
        model=GROQ_MODEL_FAST,
        temperature=0.0,
    )

    return _extract_json(text or "")


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 6 : ANALYSE PLAINTE IA
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_PLAINTE_SYSTEM = """Tu es l'administrateur IA de la ligue privée Fantasy Boulzazen CDM 2026.
Tu analyses les réclamations des joueurs avec impartialité et précision.

Barème officiel :
- But : G=8, D=6, M=5, A=4 pts
- Passe : G=6, D=5, M=4, A=4 pts
- Clean sheet : G=5, D=4, M=1, A=0 pts
- Match complet : +2, partiel : +1
- Parades (par 3) : +3 pts (gardiens)
- Récupérations (par 5) : +3 pts (G,D,M)
- CJ : -1, CR : -2
- Entraîneur présent : +1, victoire : +2, +3/2 buts d'écart

Retourne UNIQUEMENT du JSON valide.
"""

PROMPT_PLAINTE_USER = """Analyse cette réclamation Fantasy :

ID : {complaint_id}
Joueur/Match concerné : {subject}
Description : {description}
Points réclamés : {claimed_points}

Rends un verdict :
{{
  "verdict": "approved|rejected|needs_investigation",
  "confidence": 85,
  "summary": "Résumé en une phrase",
  "reasoning": "Analyse détaillée (2-4 phrases)",
  "points_impact": "+X ou -X ou neutre",
  "action": "Action recommandée si accepté",
  "rule_reference": "Règle du barème applicable"
}}
"""


async def analyser_plainte_ia(
    complaint_id: str,
    subject: str,
    description: str,
    claimed_points: str = "non précisé",
) -> Optional[dict]:
    """Analyse une réclamation Fantasy via Groq IA."""
    text = await _groq_chat(
        messages=[
            {"role": "system", "content": PROMPT_PLAINTE_SYSTEM},
            {"role": "user",   "content": PROMPT_PLAINTE_USER.format(
                complaint_id=complaint_id,
                subject=subject,
                description=description,
                claimed_points=claimed_points,
            )},
        ],
        max_tokens=600,
        model=GROQ_MODEL_FAST,
        temperature=0.2,
    )

    return _extract_json(text or "")


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 7 : CLASSEMENTS GROUPES IA
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_CLASSEMENTS_USER = """Donne-moi les classements actuels de tous les groupes (A à L)
de la Coupe du Monde 2026, basés sur les résultats disponibles.

Format JSON :
{{
  "standings": {{
    "Groupe A": [
      {{
        "team": "USA",
        "played": 0, "won": 0, "drawn": 0, "lost": 0,
        "goals_for": 0, "goals_against": 0, "goal_diff": 0,
        "points": 0, "qualified": false
      }}
    ]
  }}
}}
Si le tournoi n'a pas encore commencé, retourne les équipes avec tout à 0.
"""


async def scraper_classements_groupes() -> dict:
    """Récupère les classements de groupes."""
    cached = _cache_get("classements_groupes")
    if cached:
        return cached

    text = await _groq_chat(
        messages=[
            {"role": "system", "content": "Tu es expert CDM 2026. JSON uniquement."},
            {"role": "user",   "content": PROMPT_CLASSEMENTS_USER},
        ],
        max_tokens=4096,
        model=GROQ_MODEL_FAST,
    )

    data = _extract_json(text or "")
    standings = data.get("standings", {}) if isinstance(data, dict) else {}

    if standings:
        _cache_set("classements_groupes", standings)
    return standings


# ══════════════════════════════════════════════════════════════════════════════
#  ORCHESTRATEUR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

async def scraping_complet(db=None) -> dict[str, Any]:
    """
    Lance le scraping complet en parallèle :
    - Calendrier matchs
    - Résultats récents
    - Classements groupes
    - Effectifs (en arrière-plan, plus long)
    """
    logger.info("🚀 Scraping complet CDM 2026 démarré...")
    debut = time.time()

    # Tâches parallèles prioritaires
    resultats_task, classements_task, matchs_task = await asyncio.gather(
        scraper_resultats_recents(),
        scraper_classements_groupes(),
        scraper_matchs_calendrier(),
        return_exceptions=True,
    )

    matchs     = matchs_task      if isinstance(matchs_task, list)      else []
    resultats  = resultats_task   if isinstance(resultats_task, list)    else []
    classements= classements_task if isinstance(classements_task, dict)  else {}

    # Fusionner résultats dans les matchs
    if resultats:
        matchs_index = {m["id"]: m for m in matchs}
        for res in resultats:
            mid = res.get("match_id") or res.get("id")
            if mid and mid in matchs_index:
                matchs_index[mid].update({
                    "home_score":   res.get("home_score"),
                    "away_score":   res.get("away_score"),
                    "status":       "finished",
                    "is_finished":  True,
                    "player_stats": res.get("player_stats", []),
                })
        matchs = list(matchs_index.values())

    duree = round(time.time() - debut, 2)
    logger.info(f"✅ Scraping terminé en {duree}s — {len(matchs)} matchs, {len(classements)} groupes")

    return {
        "matchs":      matchs,
        "classements": classements,
        "effectifs":   [],   # chargés séparément à la demande
        "resume": {
            "matchs_scraped":   len(matchs),
            "resultats_nouveaux": len(resultats),
            "groupes":          len(classements),
            "duree_secondes":   duree,
        },
    }


async def close_browser() -> None:
    """Compatibilité avec l'ancien code — rien à fermer ici."""
    pass


async def get_all_players_market() -> list[dict]:
    """Retourne tous les joueurs du marché (pour l'auto-fill)."""
    squads = await scraper_effectifs_tous()
    players = []
    pid = 1
    for squad in squads:
        for player in squad.get("players", []):
            players.append({
                "id":          pid,
                "name":        player.get("name", ""),
                "position":    player.get("position", "M"),
                "nationality": squad.get("nation", ""),
                "price":       float(player.get("price", 6.0)),
                "club":        player.get("club", ""),
                "is_confirmed": True,
                "goals":       0,
                "assists":     0,
                "points_total": 0,
            })
            pid += 1
    return players


# ══════════════════════════════════════════════════════════════════════════════
#  CALENDRIER FALLBACK (si Groq indisponible)
# ══════════════════════════════════════════════════════════════════════════════

def _calendrier_fallback() -> list[dict]:
    """Calendrier minimal CDM 2026 codé en dur pour le fallback."""
    groupes = {
        
    }
    # Dates approximatives
    from datetime import date, timedelta
    start = date(2026, 6, 11)
    matchs = []
    mid = 1
    day_offset = 0
    for groupe, pairs in groupes.items():
        for i, (home, away) in enumerate(pairs):
            round_num = i // 2 + 1
            match_date = (start + timedelta(days=day_offset + i)).isoformat()
            matchs.append({
                "id": f"G{groupe}{mid}",
                "home": home, "away": away,
                "group": f"Groupe {groupe}",
                "round": "group_stage",
                "date": match_date,
                "venue": "USA",
                "home_score": None, "away_score": None,
                "status": "scheduled",
                "is_finished": False, "is_locked": False,
                "display_order": mid,
            })
            mid += 1
        day_offset += 3

    # Phases élim (TBD)
    for round_name, label, count in [("r16","R16",16), ("qf","QF",8), ("sf","SF",4), ("third_place","3P",2), ("final","FIN",1)]:
        for i in range(count // 2 if round_name != "final" else 1):
            matchs.append({
                "id": f"{round_name}_{i+1}",
                "home": "TBD", "away": "TBD",
                "group": None, "round": round_name,
                "date": "2026-07-15", "venue": "USA",
                "home_score": None, "away_score": None,
                "status": "scheduled",
                "is_finished": False, "is_locked": True,
                "display_order": mid,
            })
            mid += 1

    return matchs