import json
import logging
import os
import re
import base64
import asyncio
from typing import Dict, Any, Optional, Tuple, Union

logger = logging.getLogger("ai_service")

# Import du moteur IA unifié
try:
    from app.scraper import _ai_chat, _extract_json, get_scraping_status
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logger.error("❌ scraper.py non disponible")

# ════════════════════════════════════════════════════════════════════════
#  PROMPTS (moved from admin_services.py)
# ════════════════════════════════════════════════════════════════════════

PROMPT_PARSE_SQUAD = """Tu es un expert en football. L'admin vient de coller une liste de joueurs ou a fourni une image.
Parsez-la et structurez-la en JSON.

Critères :
- Détecte le PAYS (ex: Japon, France)
- Pour chaque joueur : Nom, Poste (G/D/M/A), Numéro de maillot (si dispo), Club
- Parsez aussi l'entraîneur principal s'il est mentionné

RETOURNE UNIQUEMENT ce JSON valide :
{
  "nation": "Nom du pays",
  "coach_name": "Prénom Nom ou null",
  "players": [
    {
      "name": "Prénom Nom",
      "position": "G|D|M|A",
      "number": 1,
      "club": "Nom du club ou null"
    }
  ]
}

Si la liste n'est pas compréhensible, retourne {} au lieu de deviner."""

PROMPT_PARSE_PRICES = """Tu es un expert en tarification des joueurs de football.
L'admin a fourni une liste de joueurs avec leurs clubs et postes.
Utilise tes connaissances pour estimer des prix Fantasy réalistes.

Critères de tarification :
- Gardien (G): 5.5–7.0
- Défenseur (D): 6.0–7.5
- Milieu (M): 6.5–8.5
- Attaquant (A): 7.0–10.0
- Stars mondiales (top 20 mondial): jusqu'à 14.0

RETOURNE UNIQUEMENT ce JSON :
{
  "pricing": [
    {
      "player_name": "Prénom Nom",
      "position": "G|D|M|A",
      "club": "Club",
      "suggested_price": 6.5,
      "reasoning": "Défenseur régulier, club de haut niveau"
    }
  ]
}"""

PROMPT_PARSE_TOURNAMENT = """Tu es un expert en tournois de football.
Parsez les données de tournoi et structurez-les.

Renvoyez UNIQUEMENT ce JSON :
{
  "tournament": {
    "name": "World Cup 2026",
    "start_date": "2026-06-11",
    "end_date": "2026-07-19"
  },
  "groups": {
    "Groupe A": ["Équipe1", "Équipe2", "Équipe3", "Équipe4"]
  },
  "matches": [
    {
      "id": "match_1",
      "group": "Groupe A",
      "date": "2026-06-11",
      "time_utc": "16:00",
      "home": "Équipe1",
      "away": "Équipe2"
    }
  ]
}
Si incomplet, laissez des champs null et continuez."""

PROMPT_PARSE_COACH = """Tu es expert en football. L'admin a fourni des données sur un entraîneur.
Structurez-les.

RETOURNE UNIQUEMENT ce JSON :
{
  "coach": {
    "name": "Prénom Nom",
    "nationality": "Pays",
    "nation_managed": "Pays qu'il gère",
    "club_history": ["Club1", "Club2"],
    "achievements": "description courte"
  }
}"""

PROMPT_PARSE_RULES = """Tu es expert en barème Fantasy Football.
L'admin a fourni un barème ou des modifications.
Structurez chaque règle.

RETOURNE UNIQUEMENT ce JSON :
{
  "rules": [
    {
      "name": "full_match_bonus",
      "description": "Joue le match complet (≥90 min)",
      "position": "G|D|M|A|ALL",
      "points": 2
    }
  ]
}"""

# Default pricing map for fallback when AI is not available or fails
DEFAULT_PRICING_MAP = {"G": 5.5, "D": 6.0, "M": 6.5, "A": 7.5}

class AIService:
    def __init__(self):
        if not AI_AVAILABLE:
            logger.warning("AIService initialisé mais moteur IA non disponible.")
        self.ai_available = AI_AVAILABLE
        # Check if Groq/Gemini are actually configured in .env
        self.groq_configured = bool(os.getenv("GROQ_API_KEY"))
        self.gemini_configured = bool(os.getenv("GEMINI_API_KEY"))

    def _get_messages_for_ai_chat(self, system_prompt: str, user_content: Union[str, bytes]) -> list[Dict]:
        """
        Prepares messages for _ai_chat, handling base64 image data.
        user_content can be a string (text) or bytes (base64 image).
        """
        if isinstance(user_content, bytes): # Assuming base64 image data
            # For vision models, we embed the image directly.
            # Assuming user_content is already base64 encoded bytes for the image
            encoded_image = base64.b64encode(user_content).decode('utf-8')
            # Determine mime type (simple heuristic, might need improvement)
            mime_type = "image/jpeg" # Default
            if encoded_image.startswith("/9j/"): mime_type = "image/jpeg"
            elif encoded_image.startswith("iVBORw0KGgo"): mime_type = "image/png"
            elif encoded_image.startswith("R0lGOD"): mime_type = "image/gif"

            return [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"}},
                    {"type": "text", "text": "Extrais les informations de cette image."} # Generic text for vision models
                ]},
            ]
        else: # Text content
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ]

    async def parse_squad_list(self, raw_text_or_image: Union[str, bytes]) -> Tuple[Optional[Dict], str]:
        """Parse une liste de joueurs (texte ou image base64)."""
        if not raw_text_or_image or (isinstance(raw_text_or_image, str) and len(raw_text_or_image.strip()) < 10):
            return None, "❌ Liste vide ou trop courte"

        if not self.ai_available or not (self.groq_configured or self.gemini_configured):
            return None, "❌ Moteur IA non disponible ou non configuré (GROQ_API_KEY ou GEMINI_API_KEY dans .env)"

        messages = self._get_messages_for_ai_chat(PROMPT_PARSE_SQUAD, raw_text_or_image)

        text = await _ai_chat(
            messages=messages,
            max_tokens=2000,
            temperature=0.1,
            prefer_powerful=True if isinstance(raw_text_or_image, bytes) else False # Prefer powerful for images
        )
        result = _extract_json(text or "")

        if not result or not result.get("nation"):
            return None, "❌ Impossible de parser cette liste. Vérifiez le format."
        if not result.get("players") or len(result["players"]) < 3:
            return None, "❌ Trop peu de joueurs détectés. Copiez la liste complète."

        msg = f"✅ {result['nation']} : {len(result['players'])} joueurs détectés"
        if result.get("coach_name"):
            msg += f" | Coach: {result['coach_name']}"
        return result, msg

    async def estimate_player_prices(self, squad_dict: Dict) -> Tuple[Dict, str]:
        """Estime les prix pour tous les joueurs du squad."""
        if not squad_dict or not squad_dict.get("players"):
            return {}, "❌ Squad vide"

        players_text = "\n".join([
            f"- {p['name']} ({p['position']}) #{p.get('number', '?')} du {p.get('club', 'unknown')}"
            for p in squad_dict["players"]
        ])

        if not self.ai_available or not (self.groq_configured or self.gemini_configured):
            # Fallback prix par défaut
            result = {
                "pricing": [
                    {
                        "player_name": p["name"],
                        "position": p["position"],
                        "club": p.get("club", "Unknown"),
                        "suggested_price": DEFAULT_PRICING_MAP.get(p["position"], 6.5),
                        "reasoning": f"Prix par défaut pour {p['position']}"
                    }
                    for p in squad_dict["players"]
                ]
            }
            return result, f"⚠️ Tarification par défaut (IA indisponible ou non configurée)"

        messages = self._get_messages_for_ai_chat(PROMPT_PARSE_PRICES, players_text)

        text = await _ai_chat(
            messages=messages,
            max_tokens=2000,
            temperature=0.1,
            prefer_powerful=True,
        )
        result = _extract_json(text or "")

        if not result or not result.get("pricing"):
            result = {
                "pricing": [
                    {
                        "player_name": p["name"],
                        "position": p["position"],
                        "club": p.get("club", "Unknown"),
                        "suggested_price": DEFAULT_PRICING_MAP.get(p["position"], 6.5),
                        "reasoning": f"Prix par défaut pour {p['position']}"
                    }
                    for p in squad_dict["players"]
                ]
            }
            return result, f"⚠️ Tarification par défaut ({len(result['pricing'])} joueurs)"

        return result, f"✅ Tarification : {len(result['pricing'])} joueurs évalués"

    async def parse_tournament_data(self, raw_text: str) -> Tuple[Optional[Dict], str]:
        """Parse les données de tournoi."""
        if not raw_text or len(raw_text.strip()) < 20:
            return None, "❌ Texte d'entrée vide ou trop court"

        if not self.ai_available or not (self.groq_configured or self.gemini_configured):
            return None, "❌ Moteur IA non disponible ou non configuré"

        messages = self._get_messages_for_ai_chat(PROMPT_PARSE_TOURNAMENT, raw_text)

        text = await _ai_chat(
            messages=messages,
            max_tokens=3000,
            prefer_powerful=True,
        )
        result = _extract_json(text or "")

        if not result:
            return None, "❌ Impossible de parser les données de tournoi"

        tournament = result.get("tournament", {})
        groups = result.get("groups", {})
        matches = result.get("matches", [])

        msg = f"✅ Tournoi : {tournament.get('name', 'Unknown')}"
        if groups:   msg += f" | {len(groups)} groupes"
        if matches:  msg += f" | {len(matches)} matchs"
        return result, msg

    async def parse_coach_data(self, raw_text: str) -> Tuple[Optional[Dict], str]:
        """Parse les données d'un entraîneur."""
        if not raw_text or len(raw_text.strip()) < 5:
            return None, "❌ Texte vide"

        if not self.ai_available or not (self.groq_configured or self.gemini_configured):
            return None, "❌ Moteur IA non disponible ou non configuré"

        messages = self._get_messages_for_ai_chat(PROMPT_PARSE_COACH, raw_text)

        text = await _ai_chat(
            messages=messages,
            max_tokens=1000,
            fast=True,
        )
        result = _extract_json(text or "")

        if not result or not result.get("coach"):
            return None, "❌ Impossible de parser l'entraîneur"

        coach = result["coach"]
        return result, f"✅ Entraîneur : {coach.get('name', 'Unknown')} ({coach.get('nation_managed')})"

    async def parse_rules(self, raw_text: str) -> Tuple[Optional[Dict], str]:
        """Parse les règles du jeu."""
        if not raw_text or len(raw_text.strip()) < 10:
            return None, "❌ Texte vide"

        if not self.ai_available or not (self.groq_configured or self.gemini_configured):
            return None, "❌ Moteur IA non disponible ou non configuré"

        messages = self._get_messages_for_ai_chat(PROMPT_PARSE_RULES, raw_text)

        text = await _ai_chat(
            messages=messages,
            max_tokens=1500,
            temperature=0.1,
        )
        result = _extract_json(text or "")

        if not result or not result.get("rules"):
            return None, "❌ Impossible de parser les règles"

        return result, f"✅ {len(result['rules'])} règles parsées"
