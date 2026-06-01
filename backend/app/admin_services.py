"""
admin_services.py — Services admin pour injection de données
=============================================================
Utilise Groq pour parser les données injectées manuellement.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
import os

logger = logging.getLogger("admin_services")

# Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.error("❌ groq non installé")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama3-8b-8192"


# ════════════════════════════════════════════════════════════════════════
#  APPEL GROQ POUR PARSING
# ════════════════════════════════════════════════════════════════════════

def _call_groq(system_prompt: str, user_content: str, max_tokens: int = 2000) -> Optional[Dict]:
    """
    Appelle Groq pour parser du contenu utilisateur.
    Retourne le JSON structuré ou None.
    """
    if not GROQ_AVAILABLE or not GROQ_API_KEY:
        logger.error("Groq non disponible")
        return None

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
        )
        
        text = response.choices[0].message.content or ""
        # Extraire le JSON de la réponse
        match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text)
        if match:
            return json.loads(match.group(0))
        
        logger.warning(f"Groq n'a pas retourné de JSON valide : {text[:200]}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error : {e}")
        return None
    except Exception as e:
        logger.error(f"Groq API error : {e}")
        return None


# ════════════════════════════════════════════════════════════════════════
#  PARSING EFFECTIFS (JOUEURS)
# ════════════════════════════════════════════════════════════════════════

PROMPT_PARSE_SQUAD = """Tu es un expert en football. L'admin vient de coller une liste de joueurs.
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
      "number": 1 ou null,
      "club": "Nom du club ou null"
    }
  ]
}

Si la liste n'est pas compréhensible, retourne {} au lieu de deviner."""

PROMPT_PARSE_PRICES = """Tu es un expert en tarification des joueurs de football.
L'admin a fourni une liste de joueurs avec leurs clubs et postes.
Utilise tes connaissances pour estimer des prix Fantasy réalistes (6.0 à 8.5).

Critères de tarification :
- Gardien (G): 5.5–6.5
- Défenseur (D): 6.0–7.0
- Milieu (M): 6.5–7.5
- Attaquant (A): 7.0–8.5

Facteurs : performance internationale, réputation, club (elite vs autres).

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


async def parse_squad_list(raw_text: str) -> Tuple[Optional[Dict], str]:
    """
    Parse une liste de joueurs copée-collée.
    Retourne (dict structuré, message utilisateur).
    """
    if not raw_text or len(raw_text.strip()) < 10:
        return None, "❌ Liste vide ou trop courte"

    result = _call_groq(PROMPT_PARSE_SQUAD, raw_text, max_tokens=2000)
    
    if not result or not result.get("nation"):
        return None, "❌ Impossible de parser cette liste. Vérifiez le format."
    
    if not result.get("players") or len(result["players"]) < 3:
        return None, "❌ Trop peu de joueurs détectés. Copiez la liste complète."
    
    msg = f"✅ {result['nation']} : {len(result['players'])} joueurs détectés"
    if result.get("coach_name"):
        msg += f" | Coach: {result['coach_name']}"
    
    return result, msg


async def estimate_player_prices(squad_dict: Dict) -> Tuple[Dict, str]:
    """
    Estime les prix pour tous les joueurs du squad.
    Retourne (dict avec pricing, message).
    """
    if not squad_dict or not squad_dict.get("players"):
        return {}, "❌ Squad vide"
    
    # Préparer le texte pour Groq
    players_text = "\n".join([
        f"- {p['name']} ({p['position']}) #{p.get('number', '?')} du {p.get('club', 'unknown')}"
        for p in squad_dict["players"]
    ])
    
    result = _call_groq(PROMPT_PARSE_PRICES, players_text, max_tokens=2000)
    
    if not result or not result.get("pricing"):
        # Fallback : prix par défaut selon poste
        pricing_map = {"G": 5.5, "D": 6.0, "M": 6.5, "A": 7.5}
        result = {
            "pricing": [
                {
                    "player_name": p["name"],
                    "position": p["position"],
                    "club": p.get("club", "Unknown"),
                    "suggested_price": pricing_map.get(p["position"], 6.5),
                    "reasoning": f"Prix par défaut pour {p['position']}"
                }
                for p in squad_dict["players"]
            ]
        }
        return result, f"⚠️ Tarification par défaut ({len(result['pricing'])} joueurs)"
    
    msg = f"✅ Tarification : {len(result['pricing'])} joueurs évalués"
    return result, msg


# ════════════════════════════════════════════════════════════════════════
#  PARSING TOURNOI / MATCHS
# ════════════════════════════════════════════════════════════════════════

PROMPT_PARSE_TOURNAMENT = """Tu es un expert en tournois de football.
L'admin a fourni des captures d'écran ou un texte décrivant un tournoi.
Parsez les données et structurez-les.

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


async def parse_tournament_data(raw_text: str) -> Tuple[Optional[Dict], str]:
    """
    Parse les données de tournoi (matchs, groupes, dates).
    Retourne (dict structuré, message).
    """
    if not raw_text or len(raw_text.strip()) < 20:
        return None, "❌ Texte d'entrée vide ou trop court"
    
    result = _call_groq(PROMPT_PARSE_TOURNAMENT, raw_text, max_tokens=3000)
    
    if not result:
        return None, "❌ Impossible de parser les données de tournoi"
    
    tournament = result.get("tournament", {})
    groups = result.get("groups", {})
    matches = result.get("matches", [])
    
    msg = f"✅ Tournoi : {tournament.get('name', 'Unknown')}"
    if groups:
        msg += f" | {len(groups)} groupes"
    if matches:
        msg += f" | {len(matches)} matchs"
    
    return result, msg


# ════════════════════════════════════════════════════════════════════════
#  PARSING ENTRAÎNEUR
# ════════════════════════════════════════════════════════════════════════

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


async def parse_coach_data(raw_text: str) -> Tuple[Optional[Dict], str]:
    """Parse les données d'un entraîneur."""
    if not raw_text or len(raw_text.strip()) < 5:
        return None, "❌ Texte vide"
    
    result = _call_groq(PROMPT_PARSE_COACH, raw_text, max_tokens=1000)
    
    if not result or not result.get("coach"):
        return None, "❌ Impossible de parser l'entraîneur"
    
    coach = result["coach"]
    msg = f"✅ Entraîneur : {coach.get('name', 'Unknown')} ({coach.get('nation_managed')})"
    return result, msg


# ════════════════════════════════════════════════════════════════════════
#  PARSING RÈGLES
# ════════════════════════════════════════════════════════════════════════

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


async def parse_rules(raw_text: str) -> Tuple[Optional[Dict], str]:
    """Parse les règles du jeu."""
    if not raw_text or len(raw_text.strip()) < 10:
        return None, "❌ Texte vide"
    
    result = _call_groq(PROMPT_PARSE_RULES, raw_text, max_tokens=1500)
    
    if not result or not result.get("rules"):
        return None, "❌ Impossible de parser les règles"
    
    rules = result["rules"]
    msg = f"✅ {len(rules)} règles parsées"
    return result, msg