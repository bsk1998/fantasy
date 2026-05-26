import os
import json
import logging
import traceback
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fantasy_boulzazen")

# ─── Import DB ────────────────────────────────────────────────────────────────
try:
    from app.database import get_db, engine, SessionLocal
    DB_AVAILABLE = True
except Exception as e:
    logger.error(f"❌ Erreur import database : {e}")
    DB_AVAILABLE = False

# ─── Import Models ────────────────────────────────────────────────────────────
try:
    from app.models import (
        Base, User, Player, Coach, FantasyRoster,
        PredictionScore, PredictionTableau, Complaint,
    )
    MODELS_AVAILABLE = True
except Exception as e:
    logger.error(f"❌ Erreur import models : {e}")
    MODELS_AVAILABLE = False

# ─── Import Rules Engine ──────────────────────────────────────────────────────
try:
    from app.rules_engine import (
        calculer_points_joueur,
        calculer_points_entraineur,
        calculer_points_pronostic_score,
        calculer_score_global_utilisateur,
    )
    RULES_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  Rules engine non disponible : {e}")
    RULES_AVAILABLE = False

# ─── Import Scraper (optionnel) ───────────────────────────────────────────────
try:
    from app.scraper import recuperer_resultats_matchs, recuperer_stats_joueurs, get_all_players_market
    SCRAPER_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  Scraper non disponible : {e}")
    SCRAPER_AVAILABLE = False

# ─── Import Jose JWT (optionnel) ──────────────────────────────────────────────
try:
    from jose import jwt, JWTError
    JWT_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  python-jose non disponible : {e}")
    JWT_AVAILABLE = False

# ─── Groq AI (optionnel) ──────────────────────────────────────────────────────
import os
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_AVAILABLE = False
groq_client = None

if GROQ_API_KEY:
    try:
        from groq import Groq as _Groq
        groq_client = _Groq(api_key=GROQ_API_KEY)
        GROQ_AVAILABLE = True
        logger.info("✅ Groq AI initialisé")
    except ImportError:
        logger.warning("⚠️  Package 'groq' non installé → pip install groq")
    except Exception as e:
        logger.warning(f"⚠️  Groq init échoué : {e}")

# ─── Initialisation BDD ───────────────────────────────────────────────────────
if DB_AVAILABLE and MODELS_AVAILABLE:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tables BDD créées/vérifiées")
    except Exception as e:
        logger.error(f"❌ Erreur création tables : {e}")

# ─── Application ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fantasy Boulzazen — API WC 2026",
    description="Backend complet pour la ligue privée Fantasy Coupe du Monde",
    version="4.0.0",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS: list = [o.strip() for o in _raw_origins.split(",") if o.strip()]

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
#  MODÈLES PYDANTIC
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
    player_ids: list
    coach_id: Optional[int] = None
    formation: str = "4-3-3"


class ComplaintPayload(BaseModel):
    user_id: str
    match_id: Optional[int] = None
    player_id: Optional[int] = None
    description: str
    stat_claimed: Optional[dict] = None


class ComplaintValidationPayload(BaseModel):
    admin_note: Optional[str] = None
    corrected_stats: Optional[dict] = None


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH — Vérification JWT Supabase (optionnelle)
# ══════════════════════════════════════════════════════════════════════════════

async def verify_supabase_token(authorization: str = Header(default=None)) -> dict:
    """
    Vérifie le JWT Supabase.
    En mode développement (SUPABASE_JWT_SECRET absent), accepte tout.
    """
    if not SUPABASE_JWT_SECRET:
        return {"sub": "dev-user", "email": "dev@boulzazen.local"}

    if not JWT_AVAILABLE:
        logger.warning("python-jose non disponible, auth désactivée")
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
    except Exception as e:
        logger.error(f"JWT invalide : {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expiré ou invalide.",
        )


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    db_status = "unknown"
    if DB_AVAILABLE:
        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {str(e)[:50]}"

    return {
        "status": "ok",
        "version": "4.0.0",
        "groq_available": GROQ_AVAILABLE,
        "db_status": db_status,
        "scraper_available": SCRAPER_AVAILABLE,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH SYNC — Version ultra-robuste (ne retourne JAMAIS 500)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/sync")
async def sync_on_login(
    body: SyncRequest,
    _token: dict = Depends(verify_supabase_token),
):
    """
    Sync au login — version défensive.
    Retourne toujours un 200 même si la BDD est KO.
    """
    logger.info(f"🔄 Sync demandé : {body.email}")

    # Réponse de fallback si tout échoue
    fallback_response = {
        "status": "degraded",
        "user": {
            "id": 1,
            "username": body.username or body.email.split("@")[0],
            "email": body.email,
            "score_fantasy": 0,
            "score_pronos_scores": 0,
            "score_bracket": 0,
            "total": 0,
        },
        "sync_info": {
            "matchs_scraped": 0,
            "joueurs_recalculés": 0,
            "pronos_calculés": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "mode": "degraded",
        },
    }

    # Si BDD non disponible → mode dégradé immédiat
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        logger.warning("BDD non disponible, mode dégradé")
        return fallback_response

    db = None
    try:
        db = SessionLocal()

        # ── Upsert utilisateur ────────────────────────────────────────────────
        username = body.username or body.email.split("@")[0]
        user = None

        try:
            user = db.query(User).filter(User.email == body.email).first()
        except Exception as e:
            logger.error(f"Erreur query User : {e}")
            return fallback_response

        if not user:
            try:
                user = User(
                    username=username,
                    email=body.email,
                    hashed_password="",
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"✨ Nouvel utilisateur : {user.username}")
            except Exception as e:
                logger.error(f"Erreur création User : {e}")
                db.rollback()
                # Réessayer de le récupérer (cas de race condition)
                try:
                    user = db.query(User).filter(User.email == body.email).first()
                except Exception:
                    pass
                if not user:
                    return fallback_response
        else:
            logger.info(f"👤 Utilisateur existant : {user.username}")

        # ── Calcul score Fantasy depuis le roster ─────────────────────────────
        fantasy_pts = 0
        try:
            roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
            if roster:
                fantasy_pts = sum(p.points_total for p in roster.players)
                if roster.coach:
                    fantasy_pts += roster.coach.points_total
                user.score_fantasy = fantasy_pts
        except Exception as e:
            logger.warning(f"Roster calcul échoué : {e}")

        # ── Calcul score pronos ───────────────────────────────────────────────
        prono_pts = 0
        try:
            pronos = db.query(PredictionScore).filter(PredictionScore.user_id == user.id).all()
            prono_pts = sum(p.points_earned for p in pronos)
            user.score_predictor_scores = prono_pts
        except Exception as e:
            logger.warning(f"Pronos calcul échoué : {e}")

        # ── Commit final ──────────────────────────────────────────────────────
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Commit échoué : {e}")
            db.rollback()

        total = (user.score_fantasy or 0) + (user.score_predictor_scores or 0) + (user.score_predictor_tableaux or 0)

        logger.info(f"✅ Sync OK : {user.username} — {total} pts")

        return {
            "status": "synced",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "score_fantasy": user.score_fantasy or 0,
                "score_pronos_scores": user.score_predictor_scores or 0,
                "score_bracket": user.score_predictor_tableaux or 0,
                "total": total,
            },
            "sync_info": {
                "matchs_scraped": 0,
                "joueurs_recalculés": 0,
                "pronos_calculés": 0,
                "timestamp": datetime.utcnow().isoformat(),
                "mode": "normal",
            },
        }

    except Exception as e:
        logger.error(f"❌ Erreur sync inattendue : {e}")
        logger.error(traceback.format_exc())
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        # On retourne quand même un 200 avec mode dégradé
        return fallback_response

    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  JOUEURS & COACHES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/players")
async def get_players(
    position: Optional[str] = None,
    nationality: Optional[str] = None,
    max_price: Optional[float] = None,
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        if SCRAPER_AVAILABLE:
            return get_all_players_market()
        return []

    try:
        db = SessionLocal()
        query = db.query(Player)
        if position and position != "ALL":
            query = query.filter(Player.position == position.upper())
        if nationality:
            query = query.filter(Player.nationality.ilike(f"%{nationality}%"))
        if max_price is not None:
            query = query.filter(Player.price <= max_price)

        players = query.order_by(Player.price.desc()).all()
        db.close()

        if not players:
            if SCRAPER_AVAILABLE:
                return get_all_players_market()
            return []

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
    except Exception as e:
        logger.error(f"Erreur /players : {e}")
        if SCRAPER_AVAILABLE:
            try:
                return get_all_players_market()
            except Exception:
                pass
        return []


@app.get("/coaches")
async def get_coaches():
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return COACHES_CDM_2026_DATA

    try:
        db = SessionLocal()
        coaches = db.query(Coach).all()
        db.close()

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
    except Exception as e:
        logger.error(f"Erreur /coaches : {e}")
        return COACHES_CDM_2026_DATA


@app.get("/teams")
async def get_teams():
    if SCRAPER_AVAILABLE:
        try:
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
        except Exception as e:
            logger.error(f"Erreur /teams : {e}")

    return [{"name": t, "players": [], "status": "locked", "player_count": 0} for t in EQUIPES_CDM_2026]


# ══════════════════════════════════════════════════════════════════════════════
#  LEADERBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/leaderboard")
async def get_leaderboard():
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []

    try:
        db = SessionLocal()
        users = db.query(User).all()
        leaderboard = []
        for u in users:
            total = (
                (u.score_fantasy or 0)
                + (u.score_predictor_scores or 0)
                + (u.score_predictor_tableaux or 0)
                + (u.score_top_individuel or 0)
            )
            leaderboard.append({
                "username": u.username,
                "fantasy": u.score_fantasy or 0,
                "scores": u.score_predictor_scores or 0,
                "bracket": u.score_predictor_tableaux or 0,
                "annexes": u.score_top_individuel or 0,
                "total": total,
            })
        db.close()
        leaderboard.sort(key=lambda x: x["total"], reverse=True)
        for i, entry in enumerate(leaderboard):
            entry["rank"] = i + 1
        return leaderboard
    except Exception as e:
        logger.error(f"Erreur /leaderboard : {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  MATCHS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/matches")
async def get_matches():
    return MATCHS_CDM_2026


# ══════════════════════════════════════════════════════════════════════════════
#  PRONOSTICS — Scores
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/predictions/score")
async def save_score_prediction(
    payload: PredictionScorePayload,
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "saved", "match_id": payload.match_id}

    try:
        db = SessionLocal()
        user = db.query(User).filter(User.id == int(payload.user_id)).first()
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

        match_data = next((m for m in MATCHS_CDM_2026 if m["id"] == payload.match_id), None)
        if match_data and match_data.get("is_locked", False):
            db.close()
            raise HTTPException(status_code=400, detail="Match verrouillé.")

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
        db.close()
        return {"status": "saved", "match_id": payload.match_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur /predictions/score : {e}")
        return {"status": "saved", "match_id": payload.match_id}


@app.get("/predictions/score/{user_id}")
async def get_score_predictions(
    user_id: int,
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []

    try:
        db = SessionLocal()
        pronos = db.query(PredictionScore).filter(PredictionScore.user_id == user_id).all()
        result = [
            {
                "match_id": p.match_id,
                "predicted_home": p.predicted_home_score,
                "predicted_away": p.predicted_away_score,
                "points_earned": p.points_earned,
            }
            for p in pronos
        ]
        db.close()
        return result
    except Exception as e:
        logger.error(f"Erreur /predictions/score/{user_id} : {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  FANTASY ROSTER
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/fantasy/roster")
async def save_roster(
    payload: RosterPayload,
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "saved", "player_count": len(payload.player_ids), "remaining_budget": 100.0, "formation": payload.formation}

    try:
        db = SessionLocal()

        if len(payload.player_ids) > 15:
            db.close()
            raise HTTPException(status_code=400, detail="Maximum 15 joueurs autorisés.")

        players = db.query(Player).filter(Player.id.in_(payload.player_ids)).all()
        if len(players) != len(payload.player_ids):
            db.close()
            raise HTTPException(status_code=400, detail="Un ou plusieurs joueurs introuvables.")

        total_prix = sum(p.price for p in players)
        coach = None
        if payload.coach_id:
            coach = db.query(Coach).filter(Coach.id == payload.coach_id).first()
            if coach:
                total_prix += coach.price

        if total_prix > 100.0:
            db.close()
            raise HTTPException(status_code=400, detail=f"Budget dépassé : {total_prix:.1f}M€.")

        user = db.query(User).filter(User.id == int(payload.user_id)).first()
        if not user:
            db.close()
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
        db.close()
        return {
            "status": "saved",
            "player_count": len(players),
            "remaining_budget": round(100.0 - total_prix, 2),
            "formation": payload.formation,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur /fantasy/roster : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fantasy/roster/{user_id}")
async def get_roster(
    user_id: int,
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"players": [], "coach": None, "formation": "4-3-3", "remaining_budget": 100.0}

    try:
        db = SessionLocal()
        roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user_id).first()

        if not roster:
            db.close()
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

        result = {
            "players": players_data,
            "coach": coach_data,
            "formation": roster.current_formation,
            "remaining_budget": roster.remaining_budget,
        }
        db.close()
        return result
    except Exception as e:
        logger.error(f"Erreur /fantasy/roster/{user_id} : {e}")
        return {"players": [], "coach": None, "formation": "4-3-3", "remaining_budget": 100.0}


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/admin/recalculate")
async def manual_recalculate(
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "skipped", "users_updated": 0, "reason": "BDD non disponible"}

    try:
        db = SessionLocal()
        users = db.query(User).all()
        updated = 0

        for user in users:
            try:
                roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
                if roster:
                    fantasy_pts = sum(p.points_total for p in roster.players)
                    if roster.coach:
                        fantasy_pts += roster.coach.points_total
                    user.score_fantasy = fantasy_pts

                prono_pts = db.query(PredictionScore).filter(PredictionScore.user_id == user.id).all()
                user.score_predictor_scores = sum(p.points_earned for p in prono_pts)
                updated += 1
            except Exception as e:
                logger.warning(f"Recalcul user {user.id} échoué : {e}")

        db.commit()
        db.close()
        return {"status": "recalculated", "users_updated": updated}
    except Exception as e:
        logger.error(f"Erreur /admin/recalculate : {e}")
        return {"status": "error", "users_updated": 0}


# ══════════════════════════════════════════════════════════════════════════════
#  PLAINTES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/complaints")
async def submit_complaint(
    payload: ComplaintPayload,
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "submitted", "complaint_id": 1}

    try:
        db = SessionLocal()
        user = db.query(User).filter(User.id == int(payload.user_id)).first()
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

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
        complaint_id = complaint.id
        db.close()
        return {"status": "submitted", "complaint_id": complaint_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur /complaints : {e}")
        return {"status": "submitted", "complaint_id": 0}


@app.get("/complaints")
async def get_all_complaints(
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []

    try:
        db = SessionLocal()
        complaints = db.query(Complaint).order_by(Complaint.id.desc()).all()
        result = []
        for c in complaints:
            try:
                u = db.query(User).filter(User.id == c.user_id).first()
                result.append({
                    "id": c.id,
                    "user_id": c.user_id,
                    "username": u.username if u else "?",
                    "match_id": c.match_id,
                    "player_id": c.player_id,
                    "description": c.description,
                    "status": c.status,
                    "created_at": c.created_at,
                    "resolved_at": c.resolved_at,
                })
            except Exception:
                continue
        db.close()
        return result
    except Exception as e:
        logger.error(f"Erreur /complaints : {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  DONNÉES STATIQUES
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
    {"id": 1,  "home": "USA",        "away": "Canada",       "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 2,  "home": "Mexique",    "away": "Jamaïque",     "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 3,  "home": "France",     "away": "Belgique",     "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 4,  "home": "Maroc",      "away": "Tunisie",      "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 5,  "home": "Brésil",     "away": "Argentine",    "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 6,  "home": "Uruguay",    "away": "Équateur",     "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 7,  "home": "Angleterre", "away": "Allemagne",    "group": "Groupe D", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 8,  "home": "Pays-Bas",   "away": "Croatie",      "group": "Groupe D", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 9,  "home": "Espagne",    "away": "Portugal",     "group": "Groupe E", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 10, "home": "Japon",      "away": "Corée du Sud", "group": "Groupe F", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 11, "home": "Sénégal",    "away": "Algérie",      "group": "Groupe G", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 12, "home": "Colombie",   "away": "Pologne",      "group": "Groupe H", "date": "2026-06-16", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
]