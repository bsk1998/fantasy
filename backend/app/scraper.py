"""
scraper.py — Pipeline IA Fantasy Boulzazen WC 2026
====================================================
v7.0 — Double moteur IA : Groq (rapide) + Gemini (puissant)
       - Groq   : llama-3.3-70b-versatile  (principal)
       - Gemini : gemini-2.0-flash-exp      (fallback / tâches lourdes)
       - AI_PROVIDER=auto → Groq d'abord, Gemini si Groq échoue
       - AI_PROVIDER=groq / gemini → force un seul moteur
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("fantasy_scraper")

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AI_PROVIDER    = os.getenv("AI_PROVIDER", "auto").lower()   # auto | groq | gemini

GROQ_BASE       = "https://api.groq.com/openai/v1"
GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_MODEL_FAST = "llama-3.1-8b-instant"

GEMINI_BASE        = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL       = "gemini-2.0-flash-exp"      # le plus puissant disponible gratuitement
GEMINI_MODEL_FAST  = "gemini-1.5-flash"           # plus rapide pour les tâches simples

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


def get_scraping_status() -> dict:
    """Retourne le statut des deux moteurs IA."""
    return {
        "groq_configure":   bool(GROQ_API_KEY),
        "gemini_configure": bool(GEMINI_API_KEY),
        "ai_provider":      AI_PROVIDER,
        "active_model":     _get_active_provider_name(),
    }


def _get_active_provider_name() -> str:
    if AI_PROVIDER == "gemini":
        return f"Gemini ({GEMINI_MODEL})" if GEMINI_API_KEY else "⚠️ Gemini non configuré"
    if AI_PROVIDER == "groq":
        return f"Groq ({GROQ_MODEL})" if GROQ_API_KEY else "⚠️ Groq non configuré"
    # auto
    if GROQ_API_KEY:
        suffix = f" + Gemini fallback ({GEMINI_MODEL})" if GEMINI_API_KEY else ""
        return f"Groq ({GROQ_MODEL}){suffix}"
    if GEMINI_API_KEY:
        return f"Gemini ({GEMINI_MODEL}) [Groq absent]"
    return "⚠️ Aucune clé IA configurée"


# ══════════════════════════════════════════════════════════════════════════════
#  CLIENTS IA
# ══════════════════════════════════════════════════════════════════════════════

async def _groq_chat(
    messages: list[dict],
    model: str = GROQ_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> Optional[str]:
    """Appel Groq API avec retry."""
    if not GROQ_API_KEY:
        return None
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
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
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"Groq attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                await asyncio.sleep(2)
    return None


async def _gemini_chat(
    messages: list[dict],
    model: str = GEMINI_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> Optional[str]:
    """
    Appel Gemini API (Google AI Studio).
    Convertit le format OpenAI → Gemini contents.
    """
    if not GEMINI_API_KEY:
        return None

    # Convertir messages OpenAI → Gemini format
    contents = []
    system_text = ""
    for m in messages:
        role = m.get("role", "user")
        text = m.get("content", "")
        if role == "system":
            system_text = text          # Gemini gère le system via systemInstruction
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": text}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": text}]})

    # Si pas de contents mais un system text, l'ajouter comme user
    if not contents and system_text:
        contents.append({"role": "user", "parts": [{"text": system_text}]})

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system_text and contents:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}

    url = f"{GEMINI_BASE}/models/{model}:generateContent?key={GEMINI_API_KEY}"

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                r = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                if r.status_code == 429:
                    await asyncio.sleep(3 ** attempt + 1)
                    continue
                r.raise_for_status()
                data = r.json()
                # Extraire le texte de la réponse Gemini
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
        except Exception as e:
            logger.warning(f"Gemini attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                await asyncio.sleep(2)
    return None


async def _ai_chat(
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.1,
    prefer_powerful: bool = False,   # True = préférer Gemini pour tâches complexes
    fast: bool = False,              # True = utiliser le modèle rapide
) -> Optional[str]:
    """
    Moteur IA unifié.
    - auto    : Groq d'abord, Gemini en fallback
    - groq    : Groq uniquement
    - gemini  : Gemini uniquement
    - prefer_powerful=True : Gemini d'abord si disponible (pour effectifs 48 nations, etc.)
    """
    groq_model   = GROQ_MODEL_FAST if fast else GROQ_MODEL
    gemini_model = GEMINI_MODEL_FAST if fast else GEMINI_MODEL

    provider = AI_PROVIDER

    # Si tâche lourde ET Gemini disponible, on le préfère même en mode "auto"
    if prefer_powerful and GEMINI_API_KEY and provider == "auto":
        provider = "gemini_first"

    if provider == "groq":
        result = await _groq_chat(messages, model=groq_model, max_tokens=max_tokens, temperature=temperature)
        if not result:
            logger.warning("Groq indisponible — aucun fallback configuré (AI_PROVIDER=groq)")
        return result

    if provider == "gemini":
        result = await _gemini_chat(messages, model=gemini_model, max_tokens=max_tokens, temperature=temperature)
        if not result:
            logger.warning("Gemini indisponible — aucun fallback configuré (AI_PROVIDER=gemini)")
        return result

    if provider == "gemini_first":
        # Gemini d'abord (tâche lourde), Groq en fallback
        result = await _gemini_chat(messages, model=gemini_model, max_tokens=max_tokens, temperature=temperature)
        if result:
            logger.info("IA: Gemini (tâche complexe)")
            return result
        logger.warning("Gemini échoué → fallback Groq")
        result = await _groq_chat(messages, model=groq_model, max_tokens=max_tokens, temperature=temperature)
        if result:
            logger.info("IA: Groq (fallback depuis Gemini)")
        return result

    # auto (défaut) : Groq d'abord, Gemini en fallback
    if GROQ_API_KEY:
        result = await _groq_chat(messages, model=groq_model, max_tokens=max_tokens, temperature=temperature)
        if result:
            logger.debug("IA: Groq")
            return result
        logger.warning("Groq échoué → fallback Gemini")

    if GEMINI_API_KEY:
        result = await _gemini_chat(messages, model=gemini_model, max_tokens=max_tokens, temperature=temperature)
        if result:
            logger.info("IA: Gemini (fallback)")
        return result

    logger.error("Aucune clé IA disponible (GROQ_API_KEY et GEMINI_API_KEY absentes)")
    return None


def _extract_json(text: str) -> Optional[Any]:
    """Extrait JSON depuis une réponse texte (résiste aux balises markdown)."""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 1 : MATCHS & RÉSULTATS
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
Tu dois chercher les derniers résultats officiels de la CDM 2026.
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
    """Génère le calendrier complet CDM 2026 via IA."""
    cached = _cache_get("matchs_calendrier")
    if cached:
        return cached

    logger.info("🗓️  Génération calendrier CDM 2026 via IA...")
    text = await _ai_chat(
        messages=[
            {"role": "system", "content": PROMPT_MATCHS_SYSTEM},
            {"role": "user",   "content": PROMPT_MATCHS_USER},
        ],
        max_tokens=8192,
        prefer_powerful=True,   # 104 matchs = tâche lourde → Gemini si dispo
    )

    data = _extract_json(text or "")
    matchs = data.get("matches", []) if isinstance(data, dict) else []

    if not matchs:
        matchs = _calendrier_fallback()

    _cache_set("matchs_calendrier", matchs)
    logger.info(f"✅ {len(matchs)} matchs générés")
    return matchs


async def scraper_resultats_recents() -> list[dict]:
    """Récupère les résultats récents via IA."""
    cached = _cache_get("resultats_recents")
    if cached:
        return cached

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info("📡 Scraping résultats récents via IA...")

    text = await _ai_chat(
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
      "group": "I",
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
    """Récupère les effectifs des 48 nations. Utilise Gemini si dispo (tâche lourde)."""
    cached = _cache_get("effectifs_tous")
    if cached:
        return cached

    logger.info("🌍 Scraping effectifs 48 nations via IA...")
    text = await _ai_chat(
        messages=[
            {"role": "system", "content": PROMPT_EFFECTIFS_SYSTEM},
            {"role": "user",   "content": PROMPT_EFFECTIFS_USER},
        ],
        max_tokens=8192,
        prefer_powerful=True,   # 48 nations = tâche lourde → Gemini préféré
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
    cache_key = f"effectif_{nation.lower().replace(' ', '_')}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    text = await _ai_chat(
        messages=[
            {"role": "system", "content": PROMPT_EFFECTIFS_SYSTEM},
            {"role": "user",   "content": PROMPT_EFFECTIF_NATION_USER.format(nation=nation)},
        ],
        max_tokens=3000,
        fast=True,
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
des matchs de la CDM 2026. Retourne UNIQUEMENT du JSON valide.
"""

PROMPT_STATS_USER = """Extrais les statistiques détaillées du match {home} vs {away}
du {date} (CDM 2026).

Format JSON strict :
{{
  "match": {{
    "home": "{home}",
    "away": "{away}",
    "home_score": 0,
    "away_score": 0,
    "status": "finished",
    "player_stats": [
      {{
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
      }}
    ]
  }}
}}
"""


async def scraper_stats_match(home: str, away: str, date: str) -> Optional[dict]:
    """Scrape les stats d'un match spécifique."""
    cache_key = f"stats_{home}_{away}_{date}".lower().replace(" ", "_")
    cached = _cache_get(cache_key)
    if cached:
        return cached

    logger.info(f"📊 Scraping stats {home} vs {away}...")
    text = await _ai_chat(
        messages=[
            {"role": "system", "content": PROMPT_STATS_SYSTEM},
            {"role": "user",   "content": PROMPT_STATS_USER.format(home=home, away=away, date=date)},
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
    """Génère une équipe Fantasy optimale via IA."""
    sample_players = players_disponibles[:60] if len(players_disponibles) > 60 else players_disponibles
    players_text = "\n".join(
        f"ID:{p['id']} {p['name']} ({p['position']}) {p.get('nationality','')} {p.get('price',6)}M€"
        for p in sample_players
    )
    coaches_text = "\n".join(
        f"ID:{c['id']} {c['name']} ({c.get('nationality','')}) {c.get('price',5)}M€"
        for c in coaches_disponibles[:20]
    )

    text = await _ai_chat(
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
- Carton jaune : -1 pt / Carton rouge : -2 pts

ENTRAÎNEUR :
- Présent sur le banc : +1 pt
- Victoire : +2 pts de base
- Chaque tranche de 2 buts d'écart en victoire : +3 pts
- Défaite : -2 pts de base
- But d'un remplaçant : +3 pts / Passe d'un remplaçant : +2 pts

Retourne UNIQUEMENT du JSON valide.
"""

PROMPT_POINTS_USER = """Calcule les points Fantasy pour :

Entité : {name} ({type})
Poste : {position}
Stats du match :
{stats}

Retourne :
{{
  "name": "{name}",
  "type": "{type}",
  "position": "{position}",
  "detail": {{"temps_de_jeu": 0, "buts": 0, "passes": 0, "clean_sheet": 0, "parades": 0, "recups": 0, "cartons": 0, "coaching": 0}},
  "total": 0,
  "explanation": "Détail du calcul"
}}
"""


async def calculer_points_ia(
    name: str,
    entity_type: str,
    position: str,
    stats: dict,
) -> Optional[dict]:
    """Calcule les points Fantasy via IA (validation + explication)."""
    stats_text = json.dumps(stats, ensure_ascii=False)
    text = await _ai_chat(
        messages=[
            {"role": "system", "content": PROMPT_POINTS_SYSTEM},
            {"role": "user",   "content": PROMPT_POINTS_USER.format(
                name=name, type=entity_type, position=position, stats=stats_text,
            )},
        ],
        max_tokens=800,
        fast=True,
        temperature=0.0,
    )
    return _extract_json(text or "")


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 6 : ANALYSE PLAINTE IA
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_PLAINTE_SYSTEM = """Tu es l'administrateur IA de la ligue privée Fantasy Boulzazen CDM 2026.
Tu analyses les réclamations des joueurs avec impartialité et précision.
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
    """Analyse une réclamation Fantasy via IA."""
    text = await _ai_chat(
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
        fast=True,
        temperature=0.2,
    )
    return _extract_json(text or "")


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 7 : CLASSEMENTS GROUPES
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

    text = await _ai_chat(
        messages=[
            {"role": "system", "content": "Tu es expert CDM 2026. JSON uniquement."},
            {"role": "user",   "content": PROMPT_CLASSEMENTS_USER},
        ],
        max_tokens=4096,
        fast=True,
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
    """Pipeline complet : calendrier + résultats + classements."""
    logger.info(f"🚀 Scraping complet CDM 2026 — moteur : {_get_active_provider_name()}")
    debut = time.time()

    resultats_task, classements_task, matchs_task = await asyncio.gather(
        scraper_resultats_recents(),
        scraper_classements_groupes(),
        scraper_matchs_calendrier(),
        return_exceptions=True,
    )

    matchs      = matchs_task      if isinstance(matchs_task, list)      else []
    resultats   = resultats_task   if isinstance(resultats_task, list)    else []
    classements = classements_task if isinstance(classements_task, dict)  else {}

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
        "effectifs":   [],
        "resume": {
            "matchs_scraped":     len(matchs),
            "resultats_nouveaux": len(resultats),
            "groupes":            len(classements),
            "duree_secondes":     duree,
            "moteur_ia":          _get_active_provider_name(),
        },
    }


async def close_browser() -> None:
    pass


async def get_all_players_market() -> list[dict]:
    squads = await scraper_effectifs_tous()
    players = []
    pid = 1
    for squad in squads:
        for player in squad.get("players", []):
            players.append({
                "id":           pid,
                "name":         player.get("name", ""),
                "position":     player.get("position", "M"),
                "nationality":  squad.get("nation", ""),
                "price":        float(player.get("price", 6.0)),
                "club":         player.get("club", ""),
                "is_confirmed": True,
                "goals":        0,
                "assists":      0,
                "points_total": 0,
            })
            pid += 1
    return players


# ══════════════════════════════════════════════════════════════════════════════
#  CALENDRIER FALLBACK (si aucune IA disponible)
# ══════════════════════════════════════════════════════════════════════════════

def _calendrier_fallback() -> list[dict]:
    from datetime import date, timedelta
    start = date(2026, 6, 11)
    matchs = []
    mid = 1
    for round_name, label, count in [
        ("r16","R16",16), ("qf","QF",8),
        ("sf","SF",4), ("third_place","3P",1), ("final","FIN",1)
    ]:
        for i in range(count // 2 if round_name not in ("final","third_place") else 1):
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