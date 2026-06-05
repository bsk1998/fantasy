"""
admin_services.py — Services admin pour injection de données
=============================================================
v3.0 — inject_team_nation centralisé + nettoyage positions
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger("admin_services")

# ════════════════════════════════════════════════════════════════════════
#  NORMALISATION DES POSITIONS
# ════════════════════════════════════════════════════════════════════════

POSITION_MAP = {
    # Gardiens
    "goalkeeper": "G", "gardien": "G", "portero": "G", "gk": "G", "por": "G",
    # Défenseurs
    "defender": "D", "defenseur": "D", "defensa": "D", "def": "D", "cb": "D",
    "lb": "D", "rb": "D", "rwb": "D", "lwb": "D",
    # Milieux
    "midfielder": "M", "milieu": "M", "centrocampista": "M", "mid": "M",
    "cm": "M", "cdm": "M", "cam": "M", "lm": "M", "rm": "M",
    # Attaquants
    "attacker": "A", "attaquant": "A", "delantero": "A", "att": "A",
    "fw": "A", "cf": "A", "lw": "A", "rw": "A", "st": "A",
}


def normalize_position(raw: str) -> str:
    """Convertit n'importe quelle chaîne de poste en G/D/M/A."""
    if not raw:
        return "M"
    clean = raw.strip().lower().replace("-", "").replace(" ", "")
    # Déjà normalisé
    if clean.upper() in ("G", "D", "M", "A"):
        return clean.upper()
    return POSITION_MAP.get(clean, "M")


# ════════════════════════════════════════════════════════════════════════
#  INJECTION BASE DE DONNÉES
# ════════════════════════════════════════════════════════════════════════

def inject_team_nation(db, team_name: str, coach_name: Optional[str], players: List[Dict]) -> Dict[str, Any]:
    """
    Injecte (ou met à jour) l'effectif d'une nation en base de données.

    Logique :
    - Crée ou récupère la TeamNation
    - Supprime les anciens joueurs de l'équipe (reset propre)
    - Insère les nouveaux joueurs
    - Crée ou met à jour l'entraîneur si fourni
    - Maintient la relation TeamNation → Players

    Retourne un dict avec le résultat (nb joueurs, coach, etc.)
    """
    from app.models import Player, Coach, TeamNation

    now = datetime.utcnow().isoformat()

    # ── 1. Upsert TeamNation ──────────────────────────────────────────
    team = db.query(TeamNation).filter(TeamNation.name == team_name).first()
    if not team:
        team = TeamNation(name=team_name, last_updated=now)
        db.add(team)

    team.squad_status = "definitive"
    team.is_locked    = False
    team.last_updated = now
    if coach_name:
        team.coach_name = coach_name
    db.flush()

    # ── 2. Supprimer anciens joueurs de cette équipe ──────────────────
    old_players = db.query(Player).filter(
        Player.nationality == team_name,
        Player.is_confirmed == True
    ).all()
    deleted_count = len(old_players)
    for p in old_players:
        db.delete(p)
    db.flush()

    # ── 3. Insérer nouveaux joueurs ───────────────────────────────────
    inserted = 0
    for p_data in players:
        name = (p_data.get("name") or "").strip()
        if not name:
            continue

        position = normalize_position(p_data.get("position") or "M")

        # Prix : suggéré par l'IA ou fallback par poste
        default_prices = {"G": 5.5, "D": 6.0, "M": 6.5, "A": 7.5}
        price = float(p_data.get("price") or p_data.get("suggested_price") or default_prices.get(position, 6.5))

        player = Player(
            name=name,
            position=position,
            nationality=team_name,
            team_id=team.id,
            club=p_data.get("club") or None,
            number=p_data.get("number") or None,
            price=price,
            is_confirmed=True,
            goals=0,
            assists=0,
            points_total=0,
            last_stat_update=now,
        )
        db.add(player)
        inserted += 1

    # ── 4. Coach ──────────────────────────────────────────────────────
    coach_result = None
    if coach_name and coach_name.strip():
        coach_name = coach_name.strip()
        coach = db.query(Coach).filter(Coach.team_name == team_name).first()
        if not coach:
            coach = Coach(
                name=coach_name,
                nationality=team_name,
                team_name=team_name,
                price=float(p_data.get("coach_price", 6.0)) if players else 6.0,
                is_confirmed=True,
                status="present",
                wins=0,
                losses=0,
                points_total=0,
            )
            db.add(coach)
        else:
            coach.name = coach_name
            coach.is_confirmed = True
        coach_result = coach_name

    # ── 5. Commit ──────────────────────────────────────────────────────
    db.commit()

    return {
        "nation":         team_name,
        "players_deleted": deleted_count,
        "players_inserted": inserted,
        "coach":          coach_result,
    }


# ════════════════════════════════════════════════════════════════════════
#  PARSING LEGACY (conservé pour compatibilité, délégue à ai_service)
# ════════════════════════════════════════════════════════════════════════

def parse_squad_list(raw_text: str):
    """Legacy wrapper — utiliser ai_service.parse_squad_list() directement."""
    logger.warning("parse_squad_list() legacy appelé — préférer ai_service")
    return None, "Utilisez ai_service.parse_squad_list()"


def estimate_player_prices(squad_data: Dict):
    """Legacy wrapper."""
    return None, "Utilisez ai_service.estimate_player_prices()"


def parse_tournament_data(raw_text: str):
    """Legacy wrapper."""
    return None, "Utilisez ai_service.parse_tournament_data()"


def parse_coach_data(raw_text: str):
    """Legacy wrapper."""
    return None, "Utilisez ai_service.parse_coach_data()"


def parse_rules(raw_text: str):
    """Legacy wrapper."""
    return None, "Utilisez ai_service.parse_rules()"