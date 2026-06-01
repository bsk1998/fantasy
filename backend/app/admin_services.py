"""Services pour le mode admin — parsing IA, gestion équipes/règles, etc."""

import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from groq import Groq
import os

logger = logging.getLogger("admin_services")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama3-8b-8192"


# ════════════════════════════════════════════════════════════════════════
#  PARSING EFFECTIFS — Admin colle une liste, Groq l'organise
# ════════════════════════════════════════════════════════════════════════

PROMPT_PARSE_SQUAD = """Tu es un extracteur d'effectif de football.
L'admin a collé une liste de joueurs (noms, postes, clubs, numéros).
Extrais et RETOURNE UNIQUEMENT un JSON valide :
{
  "joueurs": [
    {
      "name": "Prénom Nom",
      "position": "G|D|M|A",
      "club": "Nom du club",
      "number": null
    }
  ]
}
Ne retourne que le JSON, rien d'autre.
"""


def parse_squad_list_with_groq(raw_text: str) -> Tuple[List[Dict], Optional[str]]:
    """
    Prend du texte brut (copié par l'admin) et l'IA le parse en liste de joueurs.
    Retourne : (liste_joueurs, error_message)
    """
    if not GROQ_API_KEY:
        return [], "❌ GROQ_API_KEY manquante"

    try:
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": PROMPT_PARSE_SQUAD},
                {"role": "user", "content": raw_text},
            ],
            max_tokens=2000,
            temperature=0.1,
        )
        texte = resp.choices[0].message.content or ""
        match = re.search(r"\{[\s\S]*\}", texte)
        if not match:
            return [], f"⚠️ Groq n'a pas retourné de JSON. Réponse : {texte[:200]}"
        
        data = json.loads(match.group(0))
        joueurs = data.get("joueurs", [])
        logger.info(f"✅ Parse squad : {len(joueurs)} joueurs extraits")
        return joueurs, None
    except json.JSONDecodeError as e:
        return [], f"❌ JSON parse erreur : {e}"
    except Exception as e:
        return [], f"❌ Groq erreur : {e}"


# ════════════════════════════════════════════════════════════════════════
#  ESTIMATION DE PRIX — Groq estime les prix Fantasy par poste/performance
# ════════════════════════════════════════════════════════════════════════

PROMPT_ESTIMATE_PRICES = """Tu es un expert en valorisation Fantasy Football.
L'admin donne une liste de joueurs avec postes/clubs.
Estime les prix Fantasy (5.0 à 20.0 €) selon :
  - Poste (G: 5.5, D: 6.0, M: 7.0, A: 7.5)
  - Réputation du club et du joueur
  - Potentiel CDM 2026

RETORNE UNIQUEMENT un JSON :
{
  "prix_estimations": [
    {"name": "Prénom Nom", "position": "G", "estimated_price": 8.5}
  ]
}
Rien d'autre.
"""


def estimate_player_prices(joueurs: List[Dict]) -> Tuple[List[Dict], Optional[str]]:
    """
    Prend une liste de joueurs (nom, position, club) et estime les prix.
    Groq enrichit les prix basés sur le club/réputation.
    """
    if not GROQ_API_KEY:
        # Fallback : prix par défaut par poste
        prix_defaut = {"G": 5.5, "D": 6.0, "M": 7.0, "A": 7.5}
        for j in joueurs:
            j["price"] = prix_defaut.get(j.get("position", "M"), 6.0)
        return joueurs, None

    try:
        # Formatter les joueurs pour Groq
        liste_txt = "\n".join([
            f"- {j.get('name')} ({j.get('position', 'M')}) @ {j.get('club', 'Club inconnu')}"
            for j in joueurs
        ])

        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": PROMPT_ESTIMATE_PRICES},
                {"role": "user", "content": liste_txt},
            ],
            max_tokens=2000,
            temperature=0.3,  # Peu de variation pour cohérence
        )
        texte = resp.choices[0].message.content or ""
        match = re.search(r"\{[\s\S]*\}", texte)
        if not match:
            return [], f"⚠️ Groq n'a pas retourné de JSON de prix"
        
        data = json.loads(match.group(0))
        estimations = data.get("prix_estimations", [])
        
        # Mapper les prix estimés aux joueurs
        prix_map = {e["name"]: e["estimated_price"] for e in estimations}
        for j in joueurs:
            j["price"] = prix_map.get(j.get("name"), 6.0)
        
        logger.info(f"✅ Prix estimés pour {len(joueurs)} joueurs")
        return joueurs, None
    except Exception as e:
        return [], f"❌ Erreur estimation prix : {e}"


# ════════════════════════════════════════════════════════════════════════
#  PARSING TOURNOI — Admin donne site + captures, Groq extrait matchs/groupes
# ════════════════════════════════════════════════════════════════════════

PROMPT_PARSE_TOURNAMENT = """Tu es un extracteur de données de tournoi football.
L'admin a fourni des captures d'écran ou du texte d'un site officiel.
Extrais UNIQUEMENT un JSON valide :
{
  "groups": {
    "Groupe A": ["Équipe1", "Équipe2", "Équipe3", "Équipe4"]
  },
  "matches": [
    {
      "id": "unique_id",
      "home": "Équipe",
      "away": "Équipe",
      "group": "Groupe A ou null",
      "date": "YYYY-MM-DD",
      "status": "scheduled"
    }
  ]
}
Rien d'autre.
"""


def parse_tournament_from_text(raw_text: str) -> Tuple[Dict, Optional[str]]:
    """
    Parse un texte/images de tournoi (groupes + matchs).
    Retourne : (dict avec 'groups' et 'matches', error_message)
    """
    if not GROQ_API_KEY:
        return {"groups": {}, "matches": []}, "❌ GROQ_API_KEY manquante"

    try:
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": PROMPT_PARSE_TOURNAMENT},
                {"role": "user", "content": raw_text},
            ],
            max_tokens=3000,
            temperature=0.1,
        )
        texte = resp.choices[0].message.content or ""
        match = re.search(r"\{[\s\S]*\}", texte)
        if not match:
            return {}, f"⚠️ Groq n'a pas retourné de JSON de tournoi"
        
        data = json.loads(match.group(0))
        logger.info(f"✅ Parse tournoi : {len(data.get('groups', {}))} groupes, {len(data.get('matches', []))} matchs")
        return data, None
    except Exception as e:
        return {}, f"❌ Erreur parsing tournoi : {e}"


# ════════════════════════════════════════════════════════════════════════
#  GESTION DES RÈGLES — Admin peut créer/modifier les points par action
# ════════════════════════════════════════════════════════════════════════

DEFAULT_FANTASY_RULES = {
    "G": {
        "match_complet": 2,
        "joue": 1,
        "but": 4,
        "passe_decisive": 6,
        "clean_sheet": 5,
        "parade_par_3": 3,
        "recuperations_par_5": 3,
        "hat_trick_bonus": 5,
        "carton_jaune": -1,
        "carton_rouge": -2,
    },
    "D": {
        "match_complet": 2,
        "joue": 1,
        "but": 6,
        "passe_decisive": 5,
        "clean_sheet": 4,
        "recuperations_par_5": 3,
        "hat_trick_bonus": 5,
        "carton_jaune": -1,
        "carton_rouge": -2,
    },
    "M": {
        "match_complet": 2,
        "joue": 1,
        "but": 5,
        "passe_decisive": 4,
        "recuperations_par_5": 3,
        "hat_trick_bonus": 5,
        "carton_jaune": -1,
        "carton_rouge": -2,
    },
    "A": {
        "match_complet": 2,
        "joue": 1,
        "but": 4,
        "passe_decisive": 4,
        "hat_trick_bonus": 5,
        "carton_jaune": -1,
        "carton_rouge": -2,
    },
}

DEFAULT_PREDICTOR_RULES = {
    "score_exact": 5,
    "bonne_issue": 2,
    "mauvaise_issue": 0,
}

DEFAULT_BRACKET_RULES = {
    "equipe_correcte": 10,
    "gagnant_correct": 5,
}


def validate_rules(rules: Dict) -> Tuple[bool, Optional[str]]:
    """
    Valide que les règles sont bien formées (clés correctes, valeurs numériques).
    """
    if not isinstance(rules, dict):
        return False, "Rules doit être un dict"
    
    for position, actions in rules.items():
        if position not in ["G", "D", "M", "A"]:
            return False, f"Position invalide : {position}"
        if not isinstance(actions, dict):
            return False, f"Actions pour {position} doit être un dict"
        for action, points in actions.items():
            if not isinstance(points, (int, float)):
                return False, f"Points pour {action} doit être un nombre"
    
    return True, None
