"""
main.py — Point d'entrée FastAPI — Fantasy Boulzazen WC 2026
=============================================================
Modifications v5 :
  - Démarrage du planificateur APScheduler au startup (@app.on_event)
  - Arrêt propre au shutdown
  - Fix multiprocessing Windows / Python 3.14 :
      le bloc if __name__ == "__main__" utilise freeze_support()
      + multiprocessing.set_start_method("spawn") protégé
  - Routes /api/auth/sync et /api/leaderboard exposent les champs
    de profil mis à jour par le script quotidien
  - L'endpoint /health expose l'état du planificateur
"""

# ── Fix multiprocessing Windows (Python 3.12+/3.14) ──────────────────
# DOIT être placé AVANT tout autre import pour éviter les crashes
# du symbole __firstlineno__ lors du rechargement de processus.
import multiprocessing
import sys

if sys.platform == "win32":
    try:
        # "spawn" évite les problèmes de fork sur Windows
        multiprocessing.set_start_method("spawn", force=False)
    except RuntimeError:
        # Déjà configuré (appel multiple) — on ignore
        pass

# ── Imports standard ──────────────────────────────────────────────────
import os
import json
import logging
import traceback
from datetime import datetime
from typing import Optional

# ── FastAPI ────────────────────────────────────────────────────────────
from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fantasy_boulzazen")

# ── Imports applicatifs (tous optionnels pour un démarrage robuste) ────

try:
    from app.database import get_db, engine, SessionLocal
    DB_AVAILABLE = True
except Exception as e:
    logger.error(f"❌ Erreur import database : {e}")
    DB_AVAILABLE = False

try:
    from app.models import (Base, User, Player, Coach, FantasyRoster,
                             PredictionScore, PredictionTableau, Complaint)
    MODELS_AVAILABLE = True
except Exception as e:
    logger.error(f"❌ Erreur import models : {e}")
    MODELS_AVAILABLE = False

try:
    from app.rules_engine import calculer_points_pronostic_score
    RULES_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  Rules engine non disponible : {e}")
    RULES_AVAILABLE = False

try:
    from app.scraper import get_all_players_market
    SCRAPER_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  Scraper non disponible : {e}")
    SCRAPER_AVAILABLE = False

try:
    from app.data_wc2026 import MATCHS_GROUPES, ENTRAINEURS, get_tous_les_matchs
    WC_DATA_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  data_wc2026 non disponible : {e}")
    WC_DATA_AVAILABLE = False
    MATCHS_GROUPES = []

try:
    from app.updater import (start_scheduler, stop_scheduler, get_scheduler_status,
                              tache_mise_a_jour_quotidienne)
    UPDATER_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  Updater non disponible : {e}")
    UPDATER_AVAILABLE = False

try:
    from jose import jwt, JWTError
    JWT_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  python-jose non disponible : {e}")
    JWT_AVAILABLE = False

# ── Création des tables BDD ───────────────────────────────────────────
if DB_AVAILABLE and MODELS_AVAILABLE:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tables BDD créées/vérifiées")
    except Exception as e:
        logger.error(f"❌ Erreur création tables : {e}")


# ══════════════════════════════════════════════════════════════════════
#  APPLICATION FASTAPI
# ══════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Fantasy Boulzazen — API WC 2026",
    description="Backend complet pour la ligue privée Fantasy Coupe du Monde",
    version="5.0.0",
)

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

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


# ══════════════════════════════════════════════════════════════════════
#  LIFECYCLE — Startup / Shutdown
# ══════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def on_startup() -> None:
    """
    Démarrage de l'application :
      - Lance le planificateur de mises à jour automatiques
      - Log les capacités disponibles
    """
    logger.info("🚀 Fantasy Boulzazen API v5.0 — démarrage")

    if UPDATER_AVAILABLE:
        try:
            start_scheduler()
        except Exception as e:
            # Ne pas laisser un échec du scheduler crasher toute l'API
            logger.error(f"❌ Impossible de démarrer le scheduler : {e}")
    else:
        logger.warning("⚠️  Updater non disponible — mises à jour auto désactivées.")

    logger.info(
        f"   DB={DB_AVAILABLE} | Scraper={SCRAPER_AVAILABLE} | "
        f"WC_Data={WC_DATA_AVAILABLE} | Updater={UPDATER_AVAILABLE} | "
        f"JWT={'configuré' if SUPABASE_JWT_SECRET else 'dev (non vérifié)'}"
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Arrêt propre : stoppe le planificateur APScheduler."""
    if UPDATER_AVAILABLE:
        try:
            stop_scheduler()
        except Exception as e:
            logger.warning(f"⚠️  Arrêt scheduler : {e}")
    logger.info("🛑 Fantasy Boulzazen API — arrêt")


# ══════════════════════════════════════════════════════════════════════
#  PYDANTIC MODELS
# ══════════════════════════════════════════════════════════════════════

class SyncRequest(BaseModel):
    user_id:  str
    email:    str
    username: Optional[str] = None

class PredictionScorePayload(BaseModel):
    user_id:        str
    match_id:       int
    predicted_home: int
    predicted_away: int

class BracketPayload(BaseModel):
    user_id:      str
    bracket_data: dict

class AnnexesPayload(BaseModel):
    user_id:  str
    annexes:  dict

class RosterPayload(BaseModel):
    user_id:    str
    player_ids: list
    coach_id:   Optional[int] = None
    formation:  str = "4-3-3"

class ComplaintPayload(BaseModel):
    user_id:      str
    match_id:     Optional[int]  = None
    player_id:    Optional[int]  = None
    description:  str
    stat_claimed: Optional[dict] = None

class ManualUpdatePayload(BaseModel):
    """Payload pour déclencher une mise à jour manuelle via l'admin."""
    confirm: bool = False


# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════

import re

def _make_unique_username(base: str, db) -> str:
    username  = re.sub(r'[^a-zA-Z0-9_\-]', '_', base[:24]) or "joueur"
    candidate = username
    counter   = 2
    while True:
        try:
            if not db.query(User).filter(User.username == candidate).first():
                return candidate
            candidate = f"{username}_{counter}"
            counter  += 1
            if counter > 999:
                import random
                return f"{username}_{random.randint(1000, 9999)}"
        except Exception:
            return f"{username}_{counter}"


def _build_fallback_user(body: SyncRequest) -> dict:
    username = body.username or body.email.split("@")[0]
    return {
        "status": "degraded",
        "user": {
            "id":                  None,
            "username":            username,
            "email":               body.email,
            "score_fantasy":       0,
            "score_pronos_scores": 0,
            "score_bracket":       0,
            "total":               0,
        },
        "sync_info": {
            "matchs_scraped":     0,
            "joueurs_recalcules": 0,
            "pronos_calcules":    0,
            "timestamp":          datetime.utcnow().isoformat(),
            "mode":               "degraded",
        },
    }


# ══════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════

async def verify_supabase_token(authorization: str = Header(default=None)) -> dict:
    if not SUPABASE_JWT_SECRET:
        return {"sub": "dev-user", "email": "dev@boulzazen.local"}
    if not JWT_AVAILABLE:
        return {"sub": "dev-user", "email": "dev@boulzazen.local"}
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token d'authentification manquant.")
    token = authorization.split(" ", 1)[1]
    try:
        return jwt.decode(token, SUPABASE_JWT_SECRET,
                          algorithms=["HS256"], options={"verify_aud": False})
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token expiré ou invalide.")


# ══════════════════════════════════════════════════════════════════════
#  HEALTH
# ══════════════════════════════════════════════════════════════════════

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

    scheduler_status = get_scheduler_status() if UPDATER_AVAILABLE else {"available": False}

    return {
        "status":           "ok",
        "version":          "5.0.0",
        "db_status":        db_status,
        "scraper_available": SCRAPER_AVAILABLE,
        "wc_data_available": WC_DATA_AVAILABLE,
        "updater":           scheduler_status,
        "jwt_configured":   bool(SUPABASE_JWT_SECRET),
        "timestamp":        datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
#  AUTH SYNC
# ══════════════════════════════════════════════════════════════════════

@app.post("/auth/sync")
async def sync_on_login(
    body: SyncRequest,
    _token: dict = Depends(verify_supabase_token),
):
    """
    Synchronise l'utilisateur Supabase avec la BDD locale.
    - Crée le compte si nécessaire
    - Met à jour le username si différent
    - Recalcule les points Fantasy + Pronos
    - Retourne le profil complet avec les champs mis à jour
      par le script de mise à jour quotidienne
    """
    logger.info(f"🔄 Sync demandé pour : {body.email}")

    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return _build_fallback_user(body)

    db = None
    pronos = []
    try:
        db   = SessionLocal()
        user = None

        # ── 1. Chercher l'utilisateur ─────────────────────────────
        try:
            user = db.query(User).filter(User.email == body.email).first()
        except Exception as e:
            logger.error(f"Query User échouée : {e}")
            return _build_fallback_user(body)

        # ── 2. Créer si absent ────────────────────────────────────
        if not user:
            base_uname = (body.username or body.email.split("@")[0])
            uname      = _make_unique_username(base_uname, db)
            try:
                user = User(
                    username=uname, email=body.email, hashed_password="",
                    score_fantasy=0, score_predictor_scores=0,
                    score_predictor_tableaux=0, score_top_individuel=0,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"✨ Nouvel utilisateur : {user.username}")
            except IntegrityError:
                db.rollback()
                user = db.query(User).filter(User.email == body.email).first()
                if not user:
                    return _build_fallback_user(body)
            except Exception as e:
                db.rollback()
                logger.error(f"Création User échouée : {e}")
                return _build_fallback_user(body)

        # ── 3. Mettre à jour le username si fourni ────────────────
        if body.username and body.username.strip() and body.username.strip() != user.username:
            try:
                nu = _make_unique_username(body.username.strip(), db)
                if not db.query(User).filter(User.username == nu, User.id != user.id).first():
                    user.username = nu
            except Exception:
                pass

        # ── 4. Recalcul Fantasy ───────────────────────────────────
        fantasy_pts = 0
        try:
            roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
            if roster:
                fantasy_pts = sum((p.points_total or 0) for p in roster.players)
                if roster.coach:
                    fantasy_pts += (roster.coach.points_total or 0)
                user.score_fantasy = fantasy_pts
        except Exception as e:
            logger.warning(f"Recalcul roster user {user.id} : {e}")

        # ── 5. Recalcul Pronos ────────────────────────────────────
        prono_pts = 0
        try:
            pronos    = db.query(PredictionScore).filter(PredictionScore.user_id == user.id).all()
            prono_pts = sum((p.points_earned or 0) for p in pronos)
            user.score_predictor_scores = prono_pts
        except Exception as e:
            logger.warning(f"Recalcul pronos user {user.id} : {e}")

        # ── 6. Commit ─────────────────────────────────────────────
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Commit sync : {e}")

        # ── 7. Réponse ────────────────────────────────────────────
        total = (
            (user.score_fantasy              or 0)
            + (user.score_predictor_scores   or 0)
            + (user.score_predictor_tableaux or 0)
            + (user.score_top_individuel     or 0)
        )

        return {
            "status": "synced",
            "user": {
                "id":                  user.id,
                "username":            user.username,
                "email":               user.email,
                "score_fantasy":       user.score_fantasy              or 0,
                "score_pronos_scores": user.score_predictor_scores     or 0,
                "score_bracket":       user.score_predictor_tableaux   or 0,
                "score_annexes":       user.score_top_individuel       or 0,
                "total":               total,
            },
            "sync_info": {
                "matchs_scraped":     0,
                "joueurs_recalcules": 0,
                "pronos_calcules":    len(pronos),
                "timestamp":          datetime.utcnow().isoformat(),
                "mode":               "normal",
            },
        }

    except Exception as e:
        logger.error(f"❌ Sync inattendue {body.email} : {e}\n{traceback.format_exc()}")
        if db:
            try: db.rollback()
            except Exception: pass
        return _build_fallback_user(body)
    finally:
        if db:
            try: db.close()
            except Exception: pass


# ══════════════════════════════════════════════════════════════════════
#  PLAYERS & COACHES
# ══════════════════════════════════════════════════════════════════════

@app.get("/players")
async def get_players(
    position:  Optional[str]   = None,
    nationality: Optional[str] = None,
    max_price: Optional[float] = None,
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        if SCRAPER_AVAILABLE:
            return get_all_players_market()
        return []
    try:
        db    = SessionLocal()
        query = db.query(Player)
        if position and position != "ALL":
            query = query.filter(Player.position == position.upper())
        if nationality:
            query = query.filter(Player.nationality.ilike(f"%{nationality}%"))
        if max_price is not None:
            query = query.filter(Player.price <= max_price)
        players = query.order_by(Player.price.desc()).all()
        db.close()
        if not players and SCRAPER_AVAILABLE:
            return get_all_players_market()
        return [
            {"id": p.id, "name": p.name, "position": p.position,
             "nationality": p.nationality, "price": p.price,
             "goals": p.goals, "assists": p.assists,
             "points_total": p.points_total, "is_confirmed": p.is_confirmed}
            for p in players
        ]
    except Exception as e:
        logger.error(f"GET /players : {e}")
        return get_all_players_market() if SCRAPER_AVAILABLE else []


@app.get("/coaches")
async def get_coaches():
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return _coaches_statiques()
    try:
        db = SessionLocal()
        coaches = db.query(Coach).all()
        db.close()
        if not coaches:
            return _coaches_statiques()
        return [
            {"id": c.id, "name": c.name, "nationality": c.nationality,
             "price": c.price, "wins": c.wins, "losses": c.losses,
             "points_total": c.points_total, "status": c.status}
            for c in coaches
        ]
    except Exception as e:
        logger.error(f"GET /coaches : {e}")
        return _coaches_statiques()


def _coaches_statiques() -> list:
    """Retourne les entraîneurs depuis data_wc2026 si BDD vide."""
    if not WC_DATA_AVAILABLE:
        return []
    result = []
    for i, (nation, info) in enumerate(ENTRAINEURS.items(), start=1):
        result.append({
            "id": i, "name": info["nom"], "nationality": info["nationalite"],
            "price": info["prix"], "wins": 0, "losses": 0,
            "points_total": 0, "status": "present",
        })
    return result


# ══════════════════════════════════════════════════════════════════════
#  LEADERBOARD
# ══════════════════════════════════════════════════════════════════════

@app.get("/leaderboard")
async def get_leaderboard():
    """
    Retourne le classement de la ligue avec les scores mis à jour
    par le script de mise à jour quotidienne.
    """
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []
    try:
        db    = SessionLocal()
        users = db.query(User).all()
        lb    = []
        for u in users:
            total = (
                (u.score_fantasy              or 0)
                + (u.score_predictor_scores   or 0)
                + (u.score_predictor_tableaux or 0)
                + (u.score_top_individuel     or 0)
            )
            lb.append({
                "username": u.username,
                "fantasy":  u.score_fantasy              or 0,
                "scores":   u.score_predictor_scores     or 0,
                "bracket":  u.score_predictor_tableaux   or 0,
                "annexes":  u.score_top_individuel       or 0,
                "total":    total,
            })
        db.close()
        lb.sort(key=lambda x: x["total"], reverse=True)
        for i, entry in enumerate(lb):
            entry["rank"] = i + 1
        return lb
    except Exception as e:
        logger.error(f"GET /leaderboard : {e}")
        return []


# ══════════════════════════════════════════════════════════════════════
#  MATCHES
# ══════════════════════════════════════════════════════════════════════

@app.get("/matches")
async def get_matches():
    """Retourne les matchs depuis data_wc2026 si disponible, sinon statiques."""
    if WC_DATA_AVAILABLE:
        # Format compatible avec l'ancien frontend
        return [
            {
                "id":          m["id"],
                "home":        m["domicile"],
                "away":        m["exterieur"],
                "group":       m["groupe"],
                "date":        m["date"],
                "is_locked":   m["is_locked"],
                "home_score":  m.get("score_dom"),
                "away_score":  m.get("score_ext"),
                "is_finished": m["is_finished"],
            }
            for m in MATCHS_GROUPES
        ]
    return _MATCHS_STATIQUES


# ── Matchs statiques fallback ─────────────────────────────────────────
_MATCHS_STATIQUES = [
    {"id": 1,  "home": "USA",       "away": "Canada",      "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 2,  "home": "Mexique",   "away": "Jamaïque",    "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 5,  "home": "France",    "away": "Belgique",    "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 6,  "home": "Maroc",     "away": "Tunisie",     "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 9,  "home": "Brésil",    "away": "Argentine",   "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 13, "home": "Angleterre","away": "Allemagne",   "group": "Groupe D", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 17, "home": "Espagne",   "away": "Portugal",    "group": "Groupe E", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 21, "home": "Japon",     "away": "Corée du Sud","group": "Groupe F", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 23, "home": "Sénégal",   "away": "Algérie",     "group": "Groupe G", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
]


# ══════════════════════════════════════════════════════════════════════
#  PREDICTIONS
# ══════════════════════════════════════════════════════════════════════

@app.post("/predictions/score")
async def save_score_prediction(
    payload: PredictionScorePayload,
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "saved", "match_id": payload.match_id}
    try:
        db   = SessionLocal()
        user = None
        try:
            user = db.query(User).filter(User.id == int(payload.user_id)).first()
        except (ValueError, TypeError):
            user = db.query(User).filter(User.email == payload.user_id).first()

        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

        prono = (db.query(PredictionScore)
                   .filter(PredictionScore.user_id == user.id,
                            PredictionScore.match_id == payload.match_id)
                   .first())
        if prono:
            prono.predicted_home_score = payload.predicted_home
            prono.predicted_away_score = payload.predicted_away
        else:
            prono = PredictionScore(
                user_id=user.id, match_id=payload.match_id,
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
        logger.error(f"POST /predictions/score : {e}")
        return {"status": "saved", "match_id": payload.match_id}


@app.get("/predictions/score/{user_id}")
async def get_score_predictions(user_id: int, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []
    try:
        db    = SessionLocal()
        pronos = db.query(PredictionScore).filter(PredictionScore.user_id == user_id).all()
        result = [
            {"match_id": p.match_id, "predicted_home": p.predicted_home_score,
             "predicted_away": p.predicted_away_score, "points_earned": p.points_earned}
            for p in pronos
        ]
        db.close()
        return result
    except Exception as e:
        logger.error(f"GET /predictions/score/{user_id} : {e}")
        return []


@app.post("/predictions/bracket")
async def save_bracket(payload: BracketPayload, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "saved"}
    try:
        db   = SessionLocal()
        user = None
        try:
            user = db.query(User).filter(User.id == int(payload.user_id)).first()
        except (ValueError, TypeError):
            user = db.query(User).filter(User.email == payload.user_id).first()
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        tableau = db.query(PredictionTableau).filter(PredictionTableau.user_id == user.id).first()
        if tableau:
            tableau.bracket_data = payload.bracket_data
        else:
            tableau = PredictionTableau(user_id=user.id, bracket_data=payload.bracket_data, points_earned=0)
            db.add(tableau)
        db.commit()
        db.close()
        return {"status": "saved"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POST /predictions/bracket : {e}")
        return {"status": "saved"}


@app.post("/predictions/annexes")
async def save_annexes(payload: AnnexesPayload, _token: dict = Depends(verify_supabase_token)):
    return {"status": "saved", "message": "Pronostics annexes enregistrés"}


# ══════════════════════════════════════════════════════════════════════
#  FANTASY ROSTER
# ══════════════════════════════════════════════════════════════════════

@app.post("/fantasy/roster")
async def save_roster(payload: RosterPayload, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "saved", "player_count": len(payload.player_ids),
                "remaining_budget": 100.0, "formation": payload.formation}
    try:
        db = SessionLocal()
        if len(payload.player_ids) > 15:
            db.close()
            raise HTTPException(status_code=400, detail="Maximum 15 joueurs autorisés.")
        players = db.query(Player).filter(Player.id.in_(payload.player_ids)).all()
        if len(players) != len(payload.player_ids):
            db.close()
            raise HTTPException(status_code=400, detail="Joueur(s) introuvable(s).")
        total = sum(p.price for p in players)
        coach = None
        if payload.coach_id:
            coach = db.query(Coach).filter(Coach.id == payload.coach_id).first()
            if coach: total += coach.price
        if total > 100.0:
            db.close()
            raise HTTPException(status_code=400, detail=f"Budget dépassé : {total:.1f}M€.")
        user = None
        try:
            user = db.query(User).filter(User.id == int(payload.user_id)).first()
        except (ValueError, TypeError):
            user = db.query(User).filter(User.email == payload.user_id).first()
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
        if roster:
            roster.players = players; roster.coach_id = payload.coach_id
            roster.current_formation = payload.formation
            roster.remaining_budget  = round(100.0 - total, 2)
        else:
            roster = FantasyRoster(user_id=user.id, coach_id=payload.coach_id,
                                   current_formation=payload.formation,
                                   remaining_budget=round(100.0 - total, 2))
            roster.players = players
            db.add(roster)
        db.commit(); db.close()
        return {"status": "saved", "player_count": len(players),
                "remaining_budget": round(100.0 - total, 2), "formation": payload.formation}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POST /fantasy/roster : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fantasy/roster/{user_id}")
async def get_roster(user_id: int, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"players": [], "coach": None, "formation": "4-3-3", "remaining_budget": 100.0}
    try:
        db     = SessionLocal()
        roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user_id).first()
        if not roster:
            db.close()
            return {"players": [], "coach": None, "formation": "4-3-3", "remaining_budget": 100.0}
        players_data = [
            {"id": p.id, "name": p.name, "position": p.position,
             "nationality": p.nationality, "price": p.price,
             "goals": p.goals, "assists": p.assists, "points_total": p.points_total}
            for p in roster.players
        ]
        coach_data = None
        if roster.coach:
            c = roster.coach
            coach_data = {"id": c.id, "name": c.name, "nationality": c.nationality,
                          "price": c.price, "points_total": c.points_total}
        result = {"players": players_data, "coach": coach_data,
                  "formation": roster.current_formation, "remaining_budget": roster.remaining_budget}
        db.close()
        return result
    except Exception as e:
        logger.error(f"GET /fantasy/roster/{user_id} : {e}")
        return {"players": [], "coach": None, "formation": "4-3-3", "remaining_budget": 100.0}


# ══════════════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════════════

@app.post("/admin/recalculate")
async def manual_recalculate(_token: dict = Depends(verify_supabase_token)):
    """Recalcule manuellement tous les scores (déclenche les 4 tâches)."""
    if UPDATER_AVAILABLE:
        try:
            tache_mise_a_jour_quotidienne()
            return {"status": "recalculated", "mode": "full_update"}
        except Exception as e:
            logger.error(f"Recalcul manuel échoué : {e}")

    # Fallback : recalcul scores seul
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "skipped", "users_updated": 0}
    try:
        db = SessionLocal()
        users = db.query(User).all()
        updated = 0
        for user in users:
            try:
                roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
                if roster:
                    fp = sum((p.points_total or 0) for p in roster.players)
                    if roster.coach: fp += (roster.coach.points_total or 0)
                    user.score_fantasy = fp
                pronos = db.query(PredictionScore).filter(PredictionScore.user_id == user.id).all()
                user.score_predictor_scores = sum((p.points_earned or 0) for p in pronos)
                updated += 1
            except Exception: pass
        db.commit(); db.close()
        return {"status": "recalculated", "users_updated": updated}
    except Exception as e:
        logger.error(f"POST /admin/recalculate : {e}")
        return {"status": "error", "users_updated": 0}


@app.post("/admin/update-now")
async def trigger_update_now(
    payload: ManualUpdatePayload,
    _token: dict = Depends(verify_supabase_token),
):
    """
    Déclenche immédiatement la tâche de mise à jour planifiée.
    Utile pour tester sans attendre 24h.
    """
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Passez confirm=true pour lancer la mise à jour.")
    if not UPDATER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Updater non disponible.")
    try:
        tache_mise_a_jour_quotidienne()
        return {"status": "ok", "message": "Mise à jour manuelle lancée avec succès."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════
#  COMPLAINTS
# ══════════════════════════════════════════════════════════════════════

@app.post("/complaints")
async def submit_complaint(payload: ComplaintPayload, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "submitted", "complaint_id": 1}
    try:
        db   = SessionLocal()
        user = None
        try:
            user = db.query(User).filter(User.id == int(payload.user_id)).first()
        except (ValueError, TypeError):
            user = db.query(User).filter(User.email == payload.user_id).first()
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        complaint = Complaint(
            user_id=user.id, match_id=payload.match_id, player_id=payload.player_id,
            description=payload.description,
            stat_claimed=json.dumps(payload.stat_claimed) if payload.stat_claimed else None,
            status="pending", created_at=datetime.utcnow().isoformat(),
        )
        db.add(complaint); db.commit(); db.refresh(complaint)
        cid = complaint.id; db.close()
        return {"status": "submitted", "complaint_id": cid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POST /complaints : {e}")
        return {"status": "submitted", "complaint_id": 0}


@app.get("/complaints")
async def get_all_complaints(_token: dict = Depends(verify_supabase_token)):
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
                    "id": c.id, "user_id": c.user_id,
                    "username": u.username if u else "?",
                    "match_id": c.match_id, "player_id": c.player_id,
                    "description": c.description, "status": c.status,
                    "created_at": c.created_at, "resolved_at": c.resolved_at,
                })
            except Exception: continue
        db.close()
        return result
    except Exception as e:
        logger.error(f"GET /complaints : {e}")
        return []


# ══════════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE DIRECT (python main.py)
# ══════════════════════════════════════════════════════════════════════
#
# IMPORTANT : Ce bloc garantit le bon fonctionnement sur Windows avec
# Python 3.12+ / 3.14 en évitant la duplication de processus qui
# provoque les crashes de symboles __firstlineno__.
#
# Pour lancer en développement : uvicorn app.main:app --reload
# Pour lancer en production    : uvicorn app.main:app --host 0.0.0.0 --port $PORT
#
if __name__ == "__main__":
    # freeze_support() est nécessaire pour les exécutables PyInstaller
    # et les applications Windows multi-processus
    multiprocessing.freeze_support()

    import uvicorn

    # En production, désactiver le reload pour éviter le double-démarrage
    # du scheduler. En dev, utiliser : uvicorn app.main:app --reload
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,            # ← False ici pour éviter le double-processus
        log_level="info",
        workers=1,               # ← 1 seul worker pour APScheduler
    )