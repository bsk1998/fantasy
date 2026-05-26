"""
main.py — API FastAPI — Fantasy Boulzazen WC 2026
Version 3.0.0 — Groq AI + Bureau des Plaintes + CORS Fix

Corrections v3 :
  - CORS désormais configurable via variable d'env ALLOWED_ORIGINS
  - Endpoint /health pour diagnostiquer la disponibilité backend
  - Intégration Groq AI (llama-3.3-70b-versatile) pour l'analyse des plaintes
  - Bureau des Plaintes complet (soumettre, analyser, valider, rejeter)
  - Recalcul automatique en arrière-plan après validation d'une plainte
  - Corrections mineures de robustesse sur /auth/sync
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db, engine, SessionLocal
from app.models import (
    Base, User, Player, Coach, FantasyRoster,
    PredictionScore, PredictionTableau, Complaint,
)
from app.scraper import recuperer_resultats_matchs, recuperer_stats_joueurs
from app.rules_engine import (
    calculer_points_joueur,
    calculer_points_entraineur,
    calculer_points_pronostic_score,
    calculer_score_global_utilisateur,
)

# ─── Groq AI ──────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_AVAILABLE = False
groq_client = None

if GROQ_API_KEY:
    try:
        from groq import Groq as _Groq
        groq_client = _Groq(api_key=GROQ_API_KEY)
        GROQ_AVAILABLE = True
    except ImportError:
        logging.warning("⚠️  Package 'groq' non installé → pip install groq")

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fantasy_boulzazen")

# ─── Initialisation BDD ───────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── Application ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fantasy Boulzazen — API WC 2026",
    description="Backend complet pour la ligue privée Fantasy Coupe du Monde",
    version="3.0.0",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# En production : ALLOWED_ORIGINS=https://ton-frontend.vercel.app
# En dev       : laisser vide → "*" accepté
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ─── Config Supabase ──────────────────────────────────────────────────────────
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


# ══════════════════════════════════════════════════════════════════════════════
#  MODÈLES PYDANTIC — Corps des requêtes
# ══════════════════════════════════════════════════════════════════════════════

class SyncRequest(BaseModel):
    user_id: str
    email: str
    username: Optional[str] = None


class PredictionScorePayload(BaseModel):
    user_id: str
    match_id: int
    predicted_home: int
    predicted_away: int


class RosterPayload(BaseModel):
    user_id: str
    player_ids: list[int]
    coach_id: Optional[int] = None
    formation: str = "4-3-3"


class AutoFillRequest(BaseModel):
    budget: float = 100.0
    formation: str = "4-3-3"
    locked_player_ids: list[int] = []


class ComplaintPayload(BaseModel):
    user_id: str
    match_id: Optional[int] = None
    player_id: Optional[int] = None
    description: str
    stat_claimed: Optional[dict] = None   # ex: {"goals": 2, "assists": 1}


class ComplaintValidationPayload(BaseModel):
    admin_note: Optional[str] = None
    corrected_stats: Optional[dict] = None  # ex: {"goals": 1, "assists": 0}


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH — Vérification JWT Supabase
# ══════════════════════════════════════════════════════════════════════════════

async def verify_supabase_token(authorization: str = Header(default=None)) -> dict:
    """
    Vérifie le JWT Supabase.
    En mode développement (SUPABASE_JWT_SECRET absent), accepte tout.
    """
    if not SUPABASE_JWT_SECRET:
        logger.warning("⚠️  SUPABASE_JWT_SECRET non défini — Auth désactivée (mode dev)")
        return {"sub": "dev-user", "email": "dev@boulzazen.local"}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant ou invalide.",
        )

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as e:
        logger.error(f"JWT invalide : {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expiré ou invalide.",
        )


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH CHECK — Diagnostic de disponibilité backend
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """
    Endpoint léger pour vérifier que le backend est actif.
    Le frontend peut l'appeler avant /auth/sync pour wakeup Render.com.
    """
    return {
        "status": "ok",
        "version": "3.0.0",
        "groq_available": GROQ_AVAILABLE,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  LAZY LOADING — Sync au login
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/sync")
async def sync_on_login(
    body: SyncRequest,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """
    Déclenché à chaque connexion. Upsert utilisateur + scraping + recalcul.
    """
    logger.info(f"🔄 Sync au login : {body.email}")

    # ── Upsert utilisateur ────────────────────────────────────────────────────
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        user = User(
            username=body.username or body.email.split("@")[0],
            email=body.email,
            hashed_password="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"✨ Nouvel utilisateur créé : {user.username}")
    else:
        logger.info(f"👤 Utilisateur existant : {user.username}")

    # ── Scraping des résultats récents ────────────────────────────────────────
    resultats_nouveaux = []
    stats_joueurs_nouveau = []
    try:
        resultats_nouveaux = recuperer_resultats_matchs()
        stats_joueurs_nouveau = recuperer_stats_joueurs()
        logger.info(f"📡 Scraping : {len(resultats_nouveaux)} matchs, {len(stats_joueurs_nouveau)} joueurs")
    except Exception as e:
        logger.warning(f"⚠️  Scraping échoué (données cached utilisées) : {e}")

    # ── Recalcul des points Fantasy joueurs ───────────────────────────────────
    joueurs_mis_a_jour = 0
    for stats_raw in stats_joueurs_nouveau:
        joueur = db.query(Player).filter(Player.id == stats_raw.get("player_id")).first()
        if joueur:
            result = calculer_points_joueur(
                stats={
                    "minutes":     stats_raw.get("minutes", 0),
                    "buts":        stats_raw.get("goals", 0),
                    "passes":      stats_raw.get("assists", 0),
                    "clean_sheet": stats_raw.get("clean_sheet", False),
                    "parades":     stats_raw.get("saves", 0),
                    "recups":      stats_raw.get("recoveries", 0),
                    "jaune":       stats_raw.get("yellow_cards", 0),
                    "rouge":       stats_raw.get("red_cards", 0),
                },
                position=joueur.position,
            )
            joueur.points_total = result["total"]
            joueur.goals   = stats_raw.get("goals", joueur.goals)
            joueur.assists = stats_raw.get("assists", joueur.assists)
            joueurs_mis_a_jour += 1

    if joueurs_mis_a_jour > 0:
        db.commit()

    # ── Recalcul des pronostics de score ─────────────────────────────────────
    pronos_calculés = 0
    for match in resultats_nouveaux:
        if match.get("is_finished") and match.get("home_score") is not None:
            pronos_du_match = (
                db.query(PredictionScore)
                .filter(
                    PredictionScore.match_id == match["id"],
                    PredictionScore.points_earned == 0,
                )
                .all()
            )
            for prono in pronos_du_match:
                pts = calculer_points_pronostic_score(
                    prono.predicted_home_score,
                    prono.predicted_away_score,
                    match["home_score"],
                    match["away_score"],
                )
                prono.points_earned = pts
                pronos_calculés += 1

    if pronos_calculés > 0:
        db.commit()

    # ── Mise à jour score Fantasy de l'utilisateur ────────────────────────────
    roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
    if roster:
        fantasy_pts = sum(p.points_total for p in roster.players)
        if roster.coach:
            fantasy_pts += roster.coach.points_total
        user.score_fantasy = fantasy_pts

    prono_pts = (
        db.query(PredictionScore)
        .filter(PredictionScore.user_id == user.id)
        .all()
    )
    user.score_predictor_scores = sum(p.points_earned for p in prono_pts)
    db.commit()

    return {
        "status": "synced",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "score_fantasy": user.score_fantasy,
            "score_pronos_scores": user.score_predictor_scores,
            "score_bracket": user.score_predictor_tableaux,
            "total": user.score_fantasy + user.score_predictor_scores + user.score_predictor_tableaux,
        },
        "sync_info": {
            "matchs_scraped": len(resultats_nouveaux),
            "joueurs_recalculés": joueurs_mis_a_jour,
            "pronos_calculés": pronos_calculés,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  JOUEURS & COACHES — Marché
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/players")
async def get_players(
    position: Optional[str] = None,
    nationality: Optional[str] = None,
    max_price: Optional[float] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Player)
    if position and position != "ALL":
        query = query.filter(Player.position == position.upper())
    if nationality:
        query = query.filter(Player.nationality.ilike(f"%{nationality}%"))
    if max_price is not None:
        query = query.filter(Player.price <= max_price)

    players = query.order_by(Player.price.desc()).all()

    if not players:
        from app.scraper import get_all_players_market
        return get_all_players_market()

    return [
        {
            "id": p.id,
            "name": p.name,
            "position": p.position,
            "nationality": p.nationality,
            "price": p.price,
            "goals": p.goals,
            "assists": p.assists,
            "points_total": p.points_total,
            "is_confirmed": p.is_confirmed,
        }
        for p in players
    ]


@app.get("/coaches")
async def get_coaches(db: Session = Depends(get_db)):
    coaches = db.query(Coach).all()
    if not coaches:
        return COACHES_CDM_2026_DATA
    return [
        {
            "id": c.id,
            "name": c.name,
            "nationality": c.nationality,
            "price": c.price,
            "wins": c.wins,
            "losses": c.losses,
            "points_total": c.points_total,
            "status": c.status,
        }
        for c in coaches
    ]


@app.get("/teams")
async def get_teams():
    from app.scraper import recuperer_effectif_web
    teams_status = []
    for team_name in EQUIPES_CDM_2026:
        effectif = recuperer_effectif_web(team_name)
        teams_status.append({
            "name": team_name,
            "players": effectif or [],
            "status": "open" if effectif else "locked",
            "player_count": len(effectif) if effectif else 0,
        })
    return teams_status


# ══════════════════════════════════════════════════════════════════════════════
#  LEADERBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/leaderboard")
async def get_leaderboard(db: Session = Depends(get_db)):
    users = db.query(User).all()
    leaderboard = []
    for u in users:
        total = (
            u.score_fantasy
            + u.score_predictor_scores
            + u.score_predictor_tableaux
            + u.score_top_individuel
        )
        leaderboard.append({
            "username": u.username,
            "fantasy": u.score_fantasy,
            "scores": u.score_predictor_scores,
            "bracket": u.score_predictor_tableaux,
            "annexes": u.score_top_individuel,
            "total": total,
        })

    leaderboard.sort(key=lambda x: x["total"], reverse=True)
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1
    return leaderboard


# ══════════════════════════════════════════════════════════════════════════════
#  MATCHS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/matches")
async def get_matches():
    return MATCHS_CDM_2026


# ══════════════════════════════════════════════════════════════════════════════
#  PRONOSTICS — Scores des matchs
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/predictions/score")
async def save_score_prediction(
    payload: PredictionScorePayload,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    user = db.query(User).filter(User.id == int(payload.user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    match_data = next((m for m in MATCHS_CDM_2026 if m["id"] == payload.match_id), None)
    if match_data and match_data.get("is_locked", False):
        raise HTTPException(
            status_code=400,
            detail="Ce match a déjà commencé, les pronostics sont verrouillés.",
        )

    prono = (
        db.query(PredictionScore)
        .filter(
            PredictionScore.user_id == user.id,
            PredictionScore.match_id == payload.match_id,
        )
        .first()
    )

    if prono:
        prono.predicted_home_score = payload.predicted_home
        prono.predicted_away_score = payload.predicted_away
        prono.points_earned = 0
    else:
        prono = PredictionScore(
            user_id=user.id,
            match_id=payload.match_id,
            predicted_home_score=payload.predicted_home,
            predicted_away_score=payload.predicted_away,
            points_earned=0,
        )
        db.add(prono)

    db.commit()
    return {"status": "saved", "match_id": payload.match_id}


@app.get("/predictions/score/{user_id}")
async def get_score_predictions(
    user_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    pronos = db.query(PredictionScore).filter(PredictionScore.user_id == user_id).all()
    return [
        {
            "match_id": p.match_id,
            "predicted_home": p.predicted_home_score,
            "predicted_away": p.predicted_away_score,
            "points_earned": p.points_earned,
        }
        for p in pronos
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  FANTASY ROSTER
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/fantasy/roster")
async def save_roster(
    payload: RosterPayload,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    if len(payload.player_ids) > 15:
        raise HTTPException(status_code=400, detail="Maximum 15 joueurs autorisés.")

    players = db.query(Player).filter(Player.id.in_(payload.player_ids)).all()
    if len(players) != len(payload.player_ids):
        raise HTTPException(status_code=400, detail="Un ou plusieurs joueurs introuvables.")

    total_prix = sum(p.price for p in players)
    coach = None
    if payload.coach_id:
        coach = db.query(Coach).filter(Coach.id == payload.coach_id).first()
        if not coach:
            raise HTTPException(status_code=400, detail="Entraîneur introuvable.")
        total_prix += coach.price

    if total_prix > 100.0:
        raise HTTPException(
            status_code=400,
            detail=f"Budget dépassé : {total_prix:.1f}M€ pour un maximum de 100M€.",
        )

    from collections import Counter
    nat_count = Counter(p.nationality for p in players)
    for nat, count in nat_count.items():
        if count > 3:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum 3 joueurs par nationalité — {nat} : {count} joueurs.",
            )

    if coach:
        nationalities_in_roster = {p.nationality for p in players}
        if coach.nationality in nationalities_in_roster:
            raise HTTPException(
                status_code=400,
                detail=f"L'entraîneur ({coach.name}) partage la nationalité de joueurs dans l'équipe.",
            )

    user = db.query(User).filter(User.id == int(payload.user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
    if roster:
        roster.players = players
        roster.coach_id = payload.coach_id
        roster.current_formation = payload.formation
        roster.remaining_budget = round(100.0 - total_prix, 2)
    else:
        roster = FantasyRoster(
            user_id=user.id,
            coach_id=payload.coach_id,
            current_formation=payload.formation,
            remaining_budget=round(100.0 - total_prix, 2),
        )
        roster.players = players
        db.add(roster)

    db.commit()
    return {
        "status": "saved",
        "player_count": len(players),
        "remaining_budget": round(100.0 - total_prix, 2),
        "formation": payload.formation,
    }


@app.get("/fantasy/roster/{user_id}")
async def get_roster(
    user_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user_id).first()
    if not roster:
        return {"players": [], "coach": None, "formation": "4-3-3", "remaining_budget": 100.0}

    players_data = [
        {
            "id": p.id, "name": p.name, "position": p.position,
            "nationality": p.nationality, "price": p.price,
            "goals": p.goals, "assists": p.assists, "points_total": p.points_total,
        }
        for p in roster.players
    ]

    coach_data = None
    if roster.coach:
        coach_data = {
            "id": roster.coach.id, "name": roster.coach.name,
            "nationality": roster.coach.nationality,
            "price": roster.coach.price, "points_total": roster.coach.points_total,
        }

    return {
        "players": players_data,
        "coach": coach_data,
        "formation": roster.current_formation,
        "remaining_budget": roster.remaining_budget,
    }


@app.get("/fantasy/autofill")
async def autofill_roster(
    budget: float = 100.0,
    formation: str = "4-3-3",
    db: Session = Depends(get_db),
):
    formation_slots = FORMATION_SLOTS.get(formation, FORMATION_SLOTS["4-3-3"])
    all_players = db.query(Player).filter(Player.price <= budget).order_by(
        (Player.points_total / Player.price).desc()
    ).all()

    selected = []
    budget_restant = budget
    nat_count: dict[str, int] = {}
    slots_restants = dict(formation_slots)
    bench_slots = {"G": 1, "D": 1, "M": 1, "A": 1}
    total_slots = {pos: slots_restants.get(pos, 0) + bench_slots.get(pos, 0)
                   for pos in ["G", "D", "M", "A"]}

    for joueur in all_players:
        if len(selected) >= 15:
            break
        if total_slots.get(joueur.position, 0) <= 0:
            continue
        if joueur.price > budget_restant:
            continue
        if nat_count.get(joueur.nationality, 0) >= 3:
            continue
        selected.append(joueur)
        budget_restant -= joueur.price
        nat_count[joueur.nationality] = nat_count.get(joueur.nationality, 0) + 1
        total_slots[joueur.position] -= 1

    selected_nationalities = {p.nationality for p in selected}
    all_coaches = db.query(Coach).order_by(Coach.points_total.desc()).all()
    selected_coach = None
    for coach in all_coaches:
        if coach.nationality not in selected_nationalities and coach.price <= budget_restant:
            selected_coach = coach
            budget_restant -= coach.price
            break

    return {
        "players": [
            {"id": p.id, "name": p.name, "position": p.position,
             "nationality": p.nationality, "price": p.price, "points_total": p.points_total}
            for p in selected
        ],
        "coach": {
            "id": selected_coach.id, "name": selected_coach.name,
            "nationality": selected_coach.nationality, "price": selected_coach.price,
        } if selected_coach else None,
        "total_price": round(budget - budget_restant, 2),
        "remaining_budget": round(budget_restant, 2),
        "formation": formation,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — Recalcul manuel
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/admin/recalculate")
async def manual_recalculate(
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    users = db.query(User).all()
    updated = 0

    for user in users:
        roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
        if roster:
            fantasy_pts = sum(p.points_total for p in roster.players)
            if roster.coach:
                fantasy_pts += roster.coach.points_total
            user.score_fantasy = fantasy_pts

        prono_pts = db.query(PredictionScore).filter(PredictionScore.user_id == user.id).all()
        user.score_predictor_scores = sum(p.points_earned for p in prono_pts)
        updated += 1

    db.commit()
    logger.info(f"🔁 Recalcul admin : {updated} utilisateurs mis à jour")
    return {"status": "recalculated", "users_updated": updated}


# ══════════════════════════════════════════════════════════════════════════════
#  BUREAU DES PLAINTES — Endpoints complets
# ══════════════════════════════════════════════════════════════════════════════

def _complaint_to_dict(c: Complaint, db: Session) -> dict:
    """Sérialise une plainte avec les données enrichies."""
    username = "?"
    player_name = None
    player_pos = None

    if c.user_id:
        u = db.query(User).filter(User.id == c.user_id).first()
        if u:
            username = u.username

    if c.player_id:
        p = db.query(Player).filter(Player.id == c.player_id).first()
        if p:
            player_name = p.name
            player_pos = p.position

    return {
        "id": c.id,
        "user_id": c.user_id,
        "username": username,
        "match_id": c.match_id,
        "player_id": c.player_id,
        "player_name": player_name,
        "player_position": player_pos,
        "description": c.description,
        "stat_claimed": json.loads(c.stat_claimed) if c.stat_claimed else None,
        "status": c.status,
        "ai_analysis": c.ai_analysis,
        "ai_verdict": c.ai_verdict,
        "ai_confidence": c.ai_confidence,
        "admin_note": c.admin_note,
        "corrected_stats": json.loads(c.corrected_stats) if c.corrected_stats else None,
        "created_at": c.created_at,
        "resolved_at": c.resolved_at,
    }


@app.post("/complaints")
async def submit_complaint(
    payload: ComplaintPayload,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """
    Soumettre une réclamation sur une statistique incorrecte.
    Accessible à tous les joueurs authentifiés.
    """
    user = db.query(User).filter(User.id == int(payload.user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    if payload.player_id:
        player = db.query(Player).filter(Player.id == payload.player_id).first()
        if not player:
            raise HTTPException(status_code=404, detail="Joueur introuvable.")

    complaint = Complaint(
        user_id=user.id,
        match_id=payload.match_id,
        player_id=payload.player_id,
        description=payload.description,
        stat_claimed=json.dumps(payload.stat_claimed) if payload.stat_claimed else None,
        status="pending",
        created_at=datetime.utcnow().isoformat(),
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    logger.info(f"📝 Nouvelle plainte #{complaint.id} par {user.username}")
    return {"status": "submitted", "complaint_id": complaint.id}


@app.get("/complaints")
async def get_all_complaints(
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """
    Retourne toutes les plaintes, triées par date décroissante.
    À restreindre aux admins via ADMIN_EMAILS côté frontend.
    """
    complaints = db.query(Complaint).order_by(Complaint.id.desc()).all()
    return [_complaint_to_dict(c, db) for c in complaints]


@app.get("/complaints/user/{user_id}")
async def get_user_complaints(
    user_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """Retourne les plaintes d'un utilisateur spécifique."""
    complaints = (
        db.query(Complaint)
        .filter(Complaint.user_id == user_id)
        .order_by(Complaint.id.desc())
        .all()
    )
    return [_complaint_to_dict(c, db) for c in complaints]


@app.post("/complaints/{complaint_id}/analyze")
async def analyze_complaint_with_groq(
    complaint_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """
    Analyse une plainte avec Groq AI (llama-3.3-70b-versatile).
    Retourne un verdict structuré : valid | invalid | uncertain.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Plainte introuvable.")

    player = db.query(Player).filter(Player.id == complaint.player_id).first() if complaint.player_id else None
    stat_claimed = json.loads(complaint.stat_claimed) if complaint.stat_claimed else {}

    # ── Fallback si Groq non disponible ──────────────────────────────────────
    if not GROQ_AVAILABLE or not groq_client:
        fallback = {
            "verdict": "uncertain",
            "confidence": 0,
            "analysis": "La clé GROQ_API_KEY n'est pas configurée sur le serveur. Analyse manuelle requise.",
            "recommendation": "Vérifiez les statistiques manuellement via les sources officielles.",
        }
        complaint.ai_analysis = fallback["analysis"]
        complaint.ai_verdict = "uncertain"
        complaint.ai_confidence = 0
        complaint.status = "analyzed"
        db.commit()
        return fallback

    # ── Construction du prompt ────────────────────────────────────────────────
    db_stats_str = "Non disponible"
    if player:
        db_stats_str = (
            f"Buts: {player.goals}, Passes décisives: {player.assists}, "
            f"Minutes: {player.minutes_played}, Clean sheets: {player.clean_sheets}, "
            f"Points Fantasy: {player.points_total}"
        )

    prompt = f"""Tu es l'arbitre officiel de la ligue privée Fantasy Boulzazen (Coupe du Monde 2026).
Un participant a soumis une réclamation concernant des statistiques Fantasy incorrectes.

IDENTITÉ DU JOUEUR CONCERNÉ :
- Nom : {player.name if player else "Non spécifié"}
- Poste : {player.position if player else "?"}
- Nationalité : {player.nationality if player else "?"}

STATISTIQUES ACTUELLES EN BASE DE DONNÉES :
{db_stats_str}

STATISTIQUES RÉCLAMÉES PAR LE PARTICIPANT (ce qu'il pense être correct) :
{json.dumps(stat_claimed, ensure_ascii=False) if stat_claimed else "Non spécifiées"}

DESCRIPTION DE LA PLAINTE :
« {complaint.description} »

MATCH CONCERNÉ : {f"Match ID #{complaint.match_id}" if complaint.match_id else "Non spécifié"}

Analyse objectivement cette réclamation. Considère que les statistiques en base proviennent d'un scraper automatique qui peut parfois avoir des erreurs.

Réponds UNIQUEMENT avec un objet JSON valide (sans markdown, sans explication hors JSON) :
{{
    "verdict": "valid|invalid|uncertain",
    "confidence": <entier entre 0 et 100>,
    "analysis": "<explication concise en français, max 120 mots>",
    "recommendation": "<action recommandée à l'administrateur, en français>"
}}"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.2,
        )
        raw_text = response.choices[0].message.content.strip()

        # Nettoyer les balises markdown éventuelles
        if raw_text.startswith("```"):
            raw_text = "\n".join(raw_text.split("\n")[1:-1])

        result = json.loads(raw_text)
        verdict = result.get("verdict", "uncertain")
        confidence = int(result.get("confidence", 50))
        analysis = result.get("analysis", "")
        recommendation = result.get("recommendation", "")

        complaint.ai_analysis = analysis
        complaint.ai_verdict = verdict
        complaint.ai_confidence = confidence
        complaint.status = "analyzed"
        db.commit()

        logger.info(f"🤖 Groq analyse plainte #{complaint_id} → {verdict} ({confidence}%)")
        return {
            "verdict": verdict,
            "confidence": confidence,
            "analysis": analysis,
            "recommendation": recommendation,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Groq retour non-JSON : {e} — Réponse brute : {raw_text[:200]}")
        fallback_analysis = "La réponse de l'IA n'a pas pu être parsée. Vérification manuelle requise."
        complaint.ai_analysis = fallback_analysis
        complaint.ai_verdict = "uncertain"
        complaint.ai_confidence = 0
        complaint.status = "analyzed"
        db.commit()
        return {"verdict": "uncertain", "confidence": 0, "analysis": fallback_analysis, "recommendation": "Vérification manuelle."}

    except Exception as e:
        logger.error(f"Erreur Groq inattendue : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur analyse IA : {str(e)}")


@app.post("/complaints/{complaint_id}/validate")
async def validate_complaint(
    complaint_id: int,
    payload: ComplaintValidationPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """
    L'administrateur valide une plainte.
    Si corrected_stats est fourni, les statistiques du joueur sont mises à jour
    et un recalcul automatique de TOUS les rosters concernés est lancé en arrière-plan.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Plainte introuvable.")

    affected_player_id = complaint.player_id

    # ── Appliquer les stats corrigées ─────────────────────────────────────────
    if payload.corrected_stats and complaint.player_id:
        player = db.query(Player).filter(Player.id == complaint.player_id).first()
        if player:
            UPDATABLE_STATS = {
                "goals", "assists", "minutes_played", "clean_sheets",
                "saves", "ball_recoveries", "yellow_cards", "red_cards",
            }
            for stat_key, stat_val in payload.corrected_stats.items():
                if stat_key in UPDATABLE_STATS:
                    setattr(player, stat_key, stat_val)

            # Recalculer les points du joueur avec les nouvelles stats
            result = calculer_points_joueur(
                stats={
                    "minutes":     player.minutes_played or 0,
                    "buts":        player.goals,
                    "passes":      player.assists,
                    "clean_sheet": bool(player.clean_sheets),
                    "parades":     player.saves,
                    "recups":      player.ball_recoveries,
                    "jaune":       player.yellow_cards,
                    "rouge":       player.red_cards,
                },
                position=player.position,
            )
            player.points_total = result["total"]
            complaint.corrected_stats = json.dumps(payload.corrected_stats)
            db.commit()
            logger.info(f"✅ Stats de {player.name} mises à jour → {result['total']} pts")

    # ── Mettre à jour la plainte ──────────────────────────────────────────────
    complaint.status = "validated"
    complaint.admin_note = payload.admin_note
    complaint.resolved_at = datetime.utcnow().isoformat()
    db.commit()

    # ── Recalcul en arrière-plan ──────────────────────────────────────────────
    if affected_player_id:
        background_tasks.add_task(_recalculate_affected_rosters, affected_player_id)
        logger.info(f"⚙️  Recalcul planifié pour le joueur ID {affected_player_id}")

    return {
        "status": "validated",
        "complaint_id": complaint_id,
        "recalculation": "scheduled" if affected_player_id else "not_needed",
    }


@app.post("/complaints/{complaint_id}/reject")
async def reject_complaint(
    complaint_id: int,
    payload: ComplaintValidationPayload,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """L'administrateur rejette une plainte."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Plainte introuvable.")

    complaint.status = "rejected"
    complaint.admin_note = payload.admin_note
    complaint.resolved_at = datetime.utcnow().isoformat()
    db.commit()

    logger.info(f"❌ Plainte #{complaint_id} rejetée")
    return {"status": "rejected", "complaint_id": complaint_id}


# ──────────────────────────────────────────────────────────────────────────────
#  TÂCHE ARRIÈRE-PLAN — Recalcul des rosters affectés par une correction
# ──────────────────────────────────────────────────────────────────────────────

def _recalculate_affected_rosters(player_id: int) -> None:
    """
    Lance un recalcul complet pour tous les utilisateurs dont le roster
    contient le joueur dont les stats viennent d'être corrigées.
    Utilise sa propre session DB car exécuté en background.
    """
    db = SessionLocal()
    try:
        # Trouver tous les rosters contenant ce joueur
        rows = db.execute(
            text("SELECT roster_id FROM roster_player WHERE player_id = :pid"),
            {"pid": player_id},
        ).fetchall()

        updated_users = 0
        for (roster_id,) in rows:
            roster = db.query(FantasyRoster).filter(FantasyRoster.id == roster_id).first()
            if not roster:
                continue

            fantasy_pts = sum(p.points_total for p in roster.players)
            if roster.coach:
                fantasy_pts += roster.coach.points_total

            user = db.query(User).filter(User.id == roster.user_id).first()
            if user:
                user.score_fantasy = fantasy_pts
                updated_users += 1

        db.commit()
        logger.info(
            f"♻️  Recalcul terminé : {updated_users} utilisateur(s) mis à jour "
            f"suite à la correction du joueur ID {player_id}"
        )
    except Exception as e:
        logger.error(f"Erreur recalcul arrière-plan (player {player_id}) : {e}")
        db.rollback()
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
#  DONNÉES STATIQUES — Référentiel CDM 2026
# ══════════════════════════════════════════════════════════════════════════════

FORMATION_SLOTS = {
    "4-3-3":   {"G": 1, "D": 4, "M": 3, "A": 3},
    "4-4-2":   {"G": 1, "D": 4, "M": 4, "A": 2},
    "3-5-2":   {"G": 1, "D": 3, "M": 5, "A": 2},
    "4-2-3-1": {"G": 1, "D": 4, "M": 5, "A": 1},
    "5-3-2":   {"G": 1, "D": 5, "M": 3, "A": 2},
}

EQUIPES_CDM_2026 = [
    "USA", "Canada", "Mexique", "France", "Brésil", "Argentine", "Angleterre",
    "Allemagne", "Espagne", "Portugal", "Pays-Bas", "Belgique", "Maroc",
    "Sénégal", "Japon", "Corée du Sud", "Australie", "Algérie", "Tunisie",
    "Égypte", "Nigeria", "Côte d'Ivoire", "Uruguay", "Colombie", "Équateur",
    "Pologne", "Croatie", "Serbie", "Suisse", "Autriche", "Turquie",
    "Grèce", "Slovaquie", "Iran", "Arabie Saoudite", "Nouvelle-Zélande",
]

COACHES_CDM_2026_DATA = [
    {"id": 1,  "name": "Didier Deschamps",  "nationality": "Français",   "price": 8.0,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 2,  "name": "Lionel Scaloni",    "nationality": "Argentin",   "price": 9.0,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 3,  "name": "Luís Enrique",      "nationality": "Espagnol",   "price": 7.5,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 4,  "name": "Gareth Southgate",  "nationality": "Anglais",    "price": 7.0,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 5,  "name": "Julian Nagelsmann", "nationality": "Allemand",   "price": 7.5,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 6,  "name": "Roberto Martinez",  "nationality": "Espagnol",   "price": 6.5,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 7,  "name": "Dorival Júnior",    "nationality": "Brésilien",  "price": 8.5,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 8,  "name": "Roberto De Zerbi",  "nationality": "Italien",    "price": 7.0,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 9,  "name": "Walid Regragui",    "nationality": "Marocain",   "price": 7.0,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 10, "name": "Aliou Cissé",       "nationality": "Sénégalais", "price": 6.0,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 11, "name": "Vahid Halilhodžić", "nationality": "Bosnien",    "price": 5.5,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 12, "name": "Hajime Moriyasu",   "nationality": "Japonais",   "price": 6.0,  "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
]

MATCHS_CDM_2026 = [
    {"id": 1,  "home": "USA",       "away": "Canada",    "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 2,  "home": "Mexique",   "away": "Pérou",     "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 3,  "home": "France",    "away": "Belgique",  "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 4,  "home": "Angleterre","away": "Espagne",   "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 5,  "home": "Brésil",    "away": "Argentine", "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 6,  "home": "Allemagne", "away": "Portugal",  "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 7,  "home": "Maroc",     "away": "Sénégal",   "group": "Groupe D", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 8,  "home": "Algérie",   "away": "Tunisie",   "group": "Groupe D", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 9,  "home": "Japon",     "away": "Corée",     "group": "Groupe E", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 10, "home": "Pays-Bas",  "away": "Croatie",   "group": "Groupe E", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 11, "home": "Uruguay",   "away": "Colombie",  "group": "Groupe F", "date": "2026-06-16", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 12, "home": "Pologne",   "away": "Suisse",    "group": "Groupe F", "date": "2026-06-16", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
]