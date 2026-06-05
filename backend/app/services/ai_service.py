"""
ai_service.py — Moteur IA unifié pour l'admin Fantasy Boulzazen
================================================================
v3.0 — Corrections :
  ✅ Gestion image bytes → base64 pour Groq et Gemini Vision
  ✅ Prompt PARSE_SQUAD renforcé (positions GK/DEF/MID/ATT → G/D/M/A)
  ✅ Fallback robuste si aucun modèle vision disponible
  ✅ Méthodes cohérentes avec admin_routes.py
"""

import json
import logging
import os
import re
import base64
from typing import Dict, Any, Optional, Tuple, Union

logger = logging.getLogger("ai_service")

try:
    from app.scraper import _ai_chat, _extract_json, get_scraping_status, GROQ_API_KEY, GEMINI_API_KEY
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    GROQ_API_KEY = ""
    GEMINI_API_KEY = ""
    logger.error("❌ scraper.py non disponible — ai_service en mode dégradé")

# ════════════════════════════════════════════════════════════════════════
#  PROMPTS
# ════════════════════════════════════════════════════════════════════════

PROMPT_PARSE_SQUAD_SYSTEM = """Tu es un expert en football international. 
Ta mission : extraire et structurer une liste de joueurs depuis un texte ou une image.

RÈGLES STRICTES :
- Normalise les postes : goalkeeper/GK/gardien → "G" | defender/DEF/défenseur → "D" | midfielder/MID/milieu → "M" | attacker/ATT/attaquant → "A"
- Détecte le nom du pays/équipe nationale
- Extrait le nom de l'entraîneur si présent
- Retourne UNIQUEMENT du JSON valide, jamais de texte autour

FORMAT DE SORTIE OBLIGATOIRE :
{
  "nation": "Nom du pays",
  "coach_name": "Prénom Nom ou null",
  "players": [
    {
      "name": "Prénom Nom",
      "position": "G|D|M|A",
      "number": 1,
      "club": "Nom du club ou null",
      "suggested_price": 6.5
    }
  ]
}

Si la liste est incompréhensible, retourne {} et rien d'autre."""

PROMPT_PARSE_SQUAD_USER_TEXT = """Voici la liste de joueurs à parser. Extrais toutes les informations disponibles.
Si la nation n'est pas mentionnée, laisse "nation" à null.

LISTE :
{raw_text}"""

PROMPT_PARSE_SQUAD_USER_IMAGE = """Analyse cette image qui contient une liste de joueurs ou un effectif de football.
Extrais tous les joueurs visibles, leur poste, numéro et club si disponibles.
Identifie l'équipe nationale si visible."""

PROMPT_PARSE_PRICES = """Tu es expert en tarification Fantasy Football.
Estime les prix en millions d'euros pour ces joueurs selon leur niveau réel.

Barème :
- Gardien (G): 5.0–7.5 | Stars: jusqu'à 9.0
- Défenseur (D): 5.5–8.0 | Stars: jusqu'à 10.0
- Milieu (M): 6.0–9.0 | Stars: jusqu'à 12.0
- Attaquant (A): 6.5–10.0 | Stars mondiales: jusqu'à 14.0

RETOURNE UNIQUEMENT ce JSON :
{
  "pricing": [
    {
      "player_name": "Prénom Nom",
      "position": "G|D|M|A",
      "club": "Club",
      "suggested_price": 6.5,
      "reasoning": "Explication courte"
    }
  ]
}"""

PROMPT_PARSE_TOURNAMENT = """Tu es expert en tournois de football. 
Analyse ce texte et structure les données du tournoi.

RETOURNE UNIQUEMENT ce JSON :
{
  "tournament": { "name": "...", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD" },
  "groups": { "Groupe A": ["Équipe1", "Équipe2", "Équipe3", "Équipe4"] },
  "matches": [{ "id": "...", "group": "...", "date": "YYYY-MM-DD", "home": "...", "away": "..." }]
}"""

PROMPT_PARSE_COACH = """Tu es expert en football. Extrais les infos de cet entraîneur.

RETOURNE UNIQUEMENT ce JSON :
{
  "coach": {
    "name": "Prénom Nom",
    "nationality": "Pays",
    "nation_managed": "Pays géré",
    "achievements": "description courte"
  }
}"""

PROMPT_PARSE_RULES = """Tu es expert en barème Fantasy Football. Structure ces règles.

RETOURNE UNIQUEMENT ce JSON :
{
  "rules": [
    { "name": "rule_id", "description": "...", "position": "G|D|M|A|ALL", "points": 2 }
  ]
}"""

DEFAULT_PRICING = {"G": 5.5, "D": 6.0, "M": 6.5, "A": 7.5}


# ════════════════════════════════════════════════════════════════════════
#  SERVICE IA
# ════════════════════════════════════════════════════════════════════════

class AIService:
    def __init__(self):
        self.ai_available      = AI_AVAILABLE
        self.groq_configured   = bool(os.getenv("GROQ_API_KEY"))
        self.gemini_configured = bool(os.getenv("GEMINI_API_KEY"))

    def _is_ready(self) -> bool:
        return self.ai_available and (self.groq_configured or self.gemini_configured)

    def _not_ready_msg(self) -> str:
        if not self.ai_available:
            return "❌ Moteur IA non disponible (scraper.py introuvable)"
        return "❌ Aucune clé IA configurée (GROQ_API_KEY ou GEMINI_API_KEY dans .env)"

    def _build_messages_for_image(self, system_prompt: str, image_bytes: bytes) -> list:
        """
        Construit les messages pour un modèle vision.
        Groq supporte les images via URL data: dans le format OpenAI.
        """
        encoded = base64.b64encode(image_bytes).decode("utf-8")

        # Détection du type MIME
        mime_type = "image/jpeg"
        if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            mime_type = "image/png"
        elif image_bytes[:4] == b"GIF8":
            mime_type = "image/gif"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime_type = "image/webp"

        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                    },
                    {"type": "text", "text": PROMPT_PARSE_SQUAD_USER_IMAGE},
                ],
            },
        ]

    # ── parse_squad_list ────────────────────────────────────────────────

    async def parse_squad_list(
        self, raw_input: Union[str, bytes]
    ) -> Tuple[Optional[Dict], str]:
        """
        Parse une liste de joueurs depuis du texte ou des bytes d'image.
        Retourne (parsed_dict, message).
        """
        if not raw_input:
            return None, "❌ Input vide"
        if not self._is_ready():
            return None, self._not_ready_msg()

        is_image = isinstance(raw_input, bytes)

        if is_image:
            if len(raw_input) < 100:
                return None, "❌ Image trop petite ou corrompue"
            messages = self._build_messages_for_image(PROMPT_PARSE_SQUAD_SYSTEM, raw_input)
            logger.info("parse_squad_list: mode IMAGE (%d octets)", len(raw_input))
        else:
            if len(raw_input.strip()) < 10:
                return None, "❌ Texte trop court"
            messages = [
                {"role": "system", "content": PROMPT_PARSE_SQUAD_SYSTEM},
                {"role": "user",   "content": PROMPT_PARSE_SQUAD_USER_TEXT.format(raw_text=raw_input)},
            ]
            logger.info("parse_squad_list: mode TEXTE (%d chars)", len(raw_input))

        text = await _ai_chat(
            messages=messages,
            max_tokens=3000,
            temperature=0.1,
            prefer_powerful=is_image,  # Gemini Vision si image
        )

        result = _extract_json(text or "")
        if not result:
            return None, "❌ L'IA n'a pas retourné de JSON valide. Reformulez ou améliorez la capture."
        if not result.get("players"):
            return None, "❌ Aucun joueur détecté. Vérifiez que la liste est lisible."
        if len(result["players"]) < 3:
            return None, "❌ Trop peu de joueurs (< 3). Fournissez une liste plus complète."

        nb = len(result["players"])
        msg = f"✅ {result.get('nation', 'Équipe inconnue')} : {nb} joueurs parsés"
        if result.get("coach_name"):
            msg += f" | Entraîneur : {result['coach_name']}"
        return result, msg

    # ── estimate_player_prices ──────────────────────────────────────────

    async def estimate_player_prices(
        self, squad_dict: Dict
    ) -> Tuple[Dict, str]:
        players = squad_dict.get("players") or []
        if not players:
            return {}, "❌ Squad vide"

        if not self._is_ready():
            # Fallback sans IA
            pricing = [
                {
                    "player_name":     p.get("name", ""),
                    "position":        p.get("position", "M"),
                    "club":            p.get("club") or "Inconnu",
                    "suggested_price": DEFAULT_PRICING.get(p.get("position", "M"), 6.5),
                    "reasoning":       "Prix par défaut (IA indisponible)",
                }
                for p in players
            ]
            return {"pricing": pricing}, f"⚠️ {len(pricing)} joueurs tarifés par défaut"

        players_text = "\n".join(
            f"- {p.get('name','')} ({p.get('position','M')}) — {p.get('club','?')}"
            for p in players
        )
        messages = [
            {"role": "system", "content": PROMPT_PARSE_PRICES},
            {"role": "user",   "content": players_text},
        ]
        text   = await _ai_chat(messages=messages, max_tokens=2000, temperature=0.1, prefer_powerful=True)
        result = _extract_json(text or "")

        if not result or not result.get("pricing"):
            # Fallback
            pricing = [
                {
                    "player_name":     p.get("name", ""),
                    "position":        p.get("position", "M"),
                    "club":            p.get("club") or "Inconnu",
                    "suggested_price": DEFAULT_PRICING.get(p.get("position", "M"), 6.5),
                    "reasoning":       "Prix par défaut",
                }
                for p in players
            ]
            return {"pricing": pricing}, f"⚠️ {len(pricing)} joueurs tarifés par défaut (IA sans résultat)"

        return result, f"✅ {len(result['pricing'])} joueurs tarifés par l'IA"

    # ── parse_tournament_data ───────────────────────────────────────────

    async def parse_tournament_data(self, raw_text: str) -> Tuple[Optional[Dict], str]:
        if not raw_text or len(raw_text.strip()) < 20:
            return None, "❌ Texte trop court"
        if not self._is_ready():
            return None, self._not_ready_msg()

        messages = [
            {"role": "system", "content": PROMPT_PARSE_TOURNAMENT},
            {"role": "user",   "content": raw_text},
        ]
        text   = await _ai_chat(messages=messages, max_tokens=3000, prefer_powerful=True)
        result = _extract_json(text or "")
        if not result:
            return None, "❌ Impossible de parser les données du tournoi"

        tournament = result.get("tournament", {})
        groups     = result.get("groups", {})
        matches    = result.get("matches", [])
        msg = f"✅ {tournament.get('name', 'Tournoi')} parsé"
        if groups:  msg += f" | {len(groups)} groupes"
        if matches: msg += f" | {len(matches)} matchs"
        return result, msg

    # ── parse_coach_data ────────────────────────────────────────────────

    async def parse_coach_data(self, raw_text: str) -> Tuple[Optional[Dict], str]:
        if not raw_text or len(raw_text.strip()) < 5:
            return None, "❌ Texte vide"
        if not self._is_ready():
            return None, self._not_ready_msg()

        messages = [
            {"role": "system", "content": PROMPT_PARSE_COACH},
            {"role": "user",   "content": raw_text},
        ]
        text   = await _ai_chat(messages=messages, max_tokens=800, fast=True)
        result = _extract_json(text or "")
        if not result or not result.get("coach"):
            return None, "❌ Impossible de parser l'entraîneur"

        coach = result["coach"]
        return result, f"✅ Entraîneur : {coach.get('name', '?')} ({coach.get('nation_managed', '?')})"

    # ── parse_rules ─────────────────────────────────────────────────────

    async def parse_rules(self, raw_text: str) -> Tuple[Optional[Dict], str]:
        if not raw_text or len(raw_text.strip()) < 10:
            return None, "❌ Texte vide"
        if not self._is_ready():
            return None, self._not_ready_msg()

        messages = [
            {"role": "system", "content": PROMPT_PARSE_RULES},
            {"role": "user",   "content": raw_text},
        ]
        text   = await _ai_chat(messages=messages, max_tokens=1500, temperature=0.1)
        result = _extract_json(text or "")
        if not result or not result.get("rules"):
            return None, "❌ Impossible de parser les règles"

        return result, f"✅ {len(result['rules'])} règles parsées"