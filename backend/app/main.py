"""
main.py — Fantasy Boulzazen API WC 2026 v6.0
=============================================
Groq IA natif · Sans Playwright · Render free tier compatible
"""

import multiprocessing
import sys

if sys.platform == "win32":
    try:
        multiprocessing.set_start_method("spawn", force=False)
    except RuntimeError:
        pass

import json
import logging
import os
import traceback
import unicodedata
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("fantasy_boulzazen")

# ── Imports applicatifs ───────────────────────────────────────────────────────
try:
    from app.database import get_db, engine, SessionLocal
    DB_AVAILABLE = True
except Exception as e:
    logger.error(f"❌ Database: {e}")
    DB_AVAILABLE = False

try:
    from app.models import (
        Base, User, Player, Coach, FantasyRoster, TeamNation,
        PredictionScore, PredictionTableau, PredictionAnnexes, Complaint,
    )
    MODELS_AVAILABLE = True
except Exception as e:
    logger.error(f"❌ Models: {e}")
    MODELS_AVAILABLE = False

try:
    from app.rules_engine import calculer_points_pronostic_score
    RULES_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  Rules engine: {e}")
    RULES_AVAILABLE = False

try:
    from app.updater import (
        start_scheduler, stop_scheduler, get_scheduler_status,
        tache_mise_a_jour_quotidienne, sync_au_login,
    )
    UPDATER_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  Updater: {e}")
    UPDATER_AVAILABLE = False

try:
    from app.routes_ia import router as ia_router
    IA_ROUTES_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  Routes IA: {e}")
    IA_ROUTES_AVAILABLE = False

try:
    from jose import jwt, JWTError
    JWT_AVAILABLE = True
except Exception:
    JWT_AVAILABLE = False

# ── Création tables ───────────────────────────────────────────────────────────
if DB_AVAILABLE and MODELS_AVAILABLE:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tables BDD créées/vérifiées")
    except Exception as e:
        logger.error(f"❌ Création tables: {e}")

# ══════════════════════════════════════════════════════════════════════════════
#  APP FASTAPI
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Fantasy Boulzazen — API WC 2026",
    description="Backend Fantasy League CDM 2026 avec Groq IA",
    version="6.0.0",
)

# Middleware : strip /api prefix
@app.middleware("http")
async def strip_api_prefix(request, call_next):
    path = request.scope.get("path", "")
    if path.startswith("/api/"):
        request.scope["path"] = path[4:]
    return await call_next(request)

# CORS
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Routes IA
if IA_ROUTES_AVAILABLE:
    app.include_router(ia_router)
    logger.info("✅ Routes IA montées sur /ia/*")

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    logger.info("🚀 Fantasy Boulzazen API v6.0 — démarrage (Groq IA)")
    if UPDATER_AVAILABLE:
        try:
            start_scheduler()
        except Exception as e:
            logger.error(f"❌ Scheduler: {e}")
    import os as _os
    groq_key = _os.getenv("GROQ_API_KEY", "")
    logger.info(
        f"   Groq={'✅ configuré' if groq_key else '❌ MANQUANT — ajoutez GROQ_API_KEY'}"
        f" | DB={DB_AVAILABLE} | Updater={UPDATER_AVAILABLE}"
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if UPDATER_AVAILABLE:
        try:
            stop_scheduler()
        except Exception:
            pass
    logger.info("🛑 API arrêtée")


# ══════════════════════════════════════════════════════════════════════════════
#  PYDANTIC MODELS
# ══════════════════════════════════════════════════════════════════════════════

class SyncRequest(BaseModel):
    user_id:  str
    email:    str
    username: Optional[str] = None

class PredictionScorePayload(BaseModel):
    user_id:        str
    match_id:       str
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
    match_id:     Optional[str]  = None
    player_id:    Optional[int]  = None
    description:  str
    stat_claimed: Optional[dict] = None

class ManualUpdatePayload(BaseModel):
    confirm: bool = False


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

import re as _re

def _make_unique_username(base: str, db) -> str:
    username  = _re.sub(r"[^a-zA-Z0-9_\-]", "_", base[:24]) or "joueur"
    candidate = username
    counter   = 2
    while True:
        if not db.query(User).filter(User.username == candidate).first():
            return candidate
        candidate = f"{username}_{counter}"
        counter  += 1
        if counter > 999:
            import random
            return f"{username}_{random.randint(1000,9999)}"


def _build_fallback_user(body: SyncRequest) -> dict:
    username = body.username or body.email.split("@")[0]
    return {
        "status": "degraded",
        "user": {
            "id": None, "username": username, "email": body.email,
            "score_fantasy": 0, "score_pronos_scores": 0,
            "score_bracket": 0, "score_annexes": 0, "total": 0,
        },
        "sync_info": {"mode": "degraded"},
    }


def _nation_key(value: str | None) -> str:
    raw = (value or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_val = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    aliases = {
        "francaise": "france", "francais": "france",
        "bresilienne": "bresil", "bresilien": "bresil",
        "anglaise": "angleterre", "anglais": "angleterre",
        "espagnole": "espagne", "espagnol": "espagne",
        "algerienne": "algerie", "algerien": "algerie",
        "marocaine": "maroc", "marocain": "maroc",
        "italienne": "italie", "italien": "italie",
    }
    return aliases.get(ascii_val, ascii_val)


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════════════

async def verify_supabase_token(authorization: str = Header(default=None)) -> dict:
    if not SUPABASE_JWT_SECRET:
        return {"sub": "dev-user", "email": "dev@boulzazen.local"}
    if not JWT_AVAILABLE:
        return {"sub": "dev-user", "email": "dev@boulzazen.local"}
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token manquant.")
    token = authorization.split(" ", 1)[1]
    # Guest sessions
    if token == "guest-local-session":
        return {"sub": "guest", "email": "guest@boulzazen.local"}
    try:
        return jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"],
                          options={"verify_aud": False})
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide.")


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH
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

    scheduler_info = get_scheduler_status() if UPDATER_AVAILABLE else {"available": False}
    groq_key = bool(os.getenv("GROQ_API_KEY", ""))

    return {
        "status":           "ok",
        "version":          "6.0.0",
        "db_status":        db_status,
        "groq_configured":  groq_key,
        "groq_model":       "llama-3.3-70b-versatile",
        "updater":          scheduler_info,
        "ia_routes":        IA_ROUTES_AVAILABLE,
        "timestamp":        datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH SYNC
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/sync")
async def sync_on_login(
    body: SyncRequest,
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return _build_fallback_user(body)

    db = None
    try:
        db   = SessionLocal()
        user = db.query(User).filter(User.email == body.email).first()

        if not user:
            uname = _make_unique_username(body.username or body.email.split("@")[0], db)
            try:
                user = User(
                    username=uname, email=body.email, hashed_password="",
                    score_fantasy=0, score_predictor_scores=0,
                    score_predictor_tableaux=0, score_top_individuel=0,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            except IntegrityError:
                db.rollback()
                user = db.query(User).filter(User.email == body.email).first()
                if not user:
                    return _build_fallback_user(body)

        if body.username and body.username.strip() != user.username:
            try:
                nu = _make_unique_username(body.username.strip(), db)
                if not db.query(User).filter(User.username == nu, User.id != user.id).first():
                    user.username = nu
            except Exception:
                pass

        sync_info = {}
        if UPDATER_AVAILABLE:
            try:
                sync_info = await sync_au_login(body.email, db)
            except Exception as e:
                logger.warning(f"Sync updater: {e}")

        total = sum([
            user.score_fantasy or 0,
            user.score_predictor_scores or 0,
            user.score_predictor_tableaux or 0,
            user.score_top_individuel or 0,
        ])

        try:
            db.commit()
        except Exception:
            db.rollback()

        return {
            "status": "synced",
            "user": {
                "id":                  user.id,
                "username":            user.username,
                "email":               user.email,
                "score_fantasy":       user.score_fantasy or 0,
                "score_pronos_scores": user.score_predictor_scores or 0,
                "score_bracket":       user.score_predictor_tableaux or 0,
                "score_annexes":       user.score_top_individuel or 0,
                "total":               total,
            },
            "sync_info": {
                **sync_info,
                "timestamp": datetime.utcnow().isoformat(),
                "mode":      "groq_realtime",
            },
        }

    except Exception as e:
        logger.error(f"❌ Sync {body.email}: {e}\n{traceback.format_exc()}")
        if db:
            try: db.rollback()
            except Exception: pass
        return _build_fallback_user(body)
    finally:
        if db:
            try: db.close()
            except Exception: pass


# ══════════════════════════════════════════════════════════════════════════════
#  PLAYERS & COACHES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/players")
async def get_players(
    position:    Optional[str]   = None,
    nationality: Optional[str]   = None,
    max_price:   Optional[float] = None,
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []
    try:
        db    = SessionLocal()
        query = db.query(Player).filter(Player.is_confirmed == True)
        if position and position != "ALL":
            query = query.filter(Player.position == position.upper())
        if nationality:
            query = query.filter(Player.nationality.ilike(f"%{nationality}%"))
        if max_price is not None:
            query = query.filter(Player.price <= max_price)
        players = query.order_by(Player.price.desc()).all()
        result = [
            {"id": p.id, "name": p.name, "position": p.position,
             "nationality": p.nationality, "price": p.price,
             "goals": p.goals, "assists": p.assists,
             "points_total": p.points_total, "is_confirmed": True}
            for p in players
        ]
        db.close()
        return result
    except Exception as e:
        logger.error(f"GET /players: {e}")
        return []


@app.get("/coaches")
async def get_coaches():
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []
    try:
        db = SessionLocal()
        coaches = db.query(Coach).filter(Coach.is_confirmed == True).all()
        result = [
            {"id": c.id, "name": c.name, "nationality": c.nationality,
             "price": c.price, "wins": c.wins, "losses": c.losses,
             "points_total": c.points_total, "status": c.status}
            for c in coaches
        ]
        db.close()
        return result
    except Exception as e:
        logger.error(f"GET /coaches: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  MATCHES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/matches")
async def get_matches():
    """Retourne les matchs depuis BDD (peuplée par Groq au premier login)."""
    if not DB_AVAILABLE:
        return []
    db = None
    try:
        db = SessionLocal()
        # Vérifier si la table existe et a des données
        try:
            rows = db.execute(text("""
                SELECT match_id, home, away, match_group, round, match_date,
                       home_score, away_score, is_finished, is_locked, status,
                       display_order, venue
                FROM match_results
                ORDER BY COALESCE(display_order, 0), COALESCE(match_date, ''), match_id
            """)).mappings().all()
        except Exception:
            rows = []

        if not rows:
            # BDD vide → lancer scraping du calendrier
            logger.info("📅 Aucun match en BDD — génération via Groq...")
            from app.scraper import scraper_matchs_calendrier
            from app.updater import _sync_matchs, _ensure_runtime_tables
            _ensure_runtime_tables(db)
            matchs = await scraper_matchs_calendrier()
            _sync_matchs(matchs, db)
            rows = db.execute(text("""
                SELECT match_id, home, away, match_group, round, match_date,
                       home_score, away_score, is_finished, is_locked, status,
                       display_order, venue
                FROM match_results
                ORDER BY COALESCE(display_order, 0), COALESCE(match_date, ''), match_id
            """)).mappings().all()

        return [
            {
                "id":           row["match_id"],
                "home":         row["home"],
                "away":         row["away"],
                "group":        row["match_group"],
                "round":        row["round"],
                "date":         row["match_date"],
                "venue":        row["venue"],
                "home_score":   row["home_score"],
                "away_score":   row["away_score"],
                "is_finished":  bool(row["is_finished"]),
                "is_locked":    bool(row["is_locked"]),
                "status":       row["status"],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"GET /matches: {e}")
        return []
    finally:
        if db:
            db.close()


@app.get("/standings")
async def get_standings():
    """Retourne les classements de groupes."""
    if not DB_AVAILABLE:
        return {}
    db = None
    try:
        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT group_name, team, points, played, wins, draws, losses,
                       goals_for, goals_against, goal_diff, qualified
                FROM group_standings
                ORDER BY group_name, points DESC, goal_diff DESC
            """)).mappings().all()
        except Exception:
            rows = []

        result: dict = {}
        for row in rows:
            gn = row["group_name"]
            if gn not in result:
                result[gn] = []
            result[gn].append({
                "team":          row["team"],
                "points":        row["points"],
                "played":        row["played"],
                "won":           row["wins"],
                "drawn":         row["draws"],
                "lost":          row["losses"],
                "goals_for":     row["goals_for"],
                "goals_against": row["goals_against"],
                "goal_diff":     row["goal_diff"],
                "qualified":     bool(row["qualified"]),
            })
        return result
    except Exception as e:
        logger.error(f"GET /standings: {e}")
        return {}
    finally:
        if db:
            db.close()


# ══════════════════════════════════════════════════════════════════════════════
#  LEADERBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/leaderboard")
async def get_leaderboard():
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []
    try:
        db    = SessionLocal()
        users = db.query(User).all()
        lb    = []
        for u in users:
            total = sum([
                u.score_fantasy or 0,
                u.score_predictor_scores or 0,
                u.score_predictor_tableaux or 0,
                u.score_top_individuel or 0,
            ])
            lb.append({
                "username": u.username,
                "fantasy":  u.score_fantasy or 0,
                "scores":   u.score_predictor_scores or 0,
                "bracket":  u.score_predictor_tableaux or 0,
                "annexes":  u.score_top_individuel or 0,
                "total":    total,
            })
        db.close()
        lb.sort(key=lambda x: x["total"], reverse=True)
        for i, entry in enumerate(lb):
            entry["rank"] = i + 1
        return lb
    except Exception as e:
        logger.error(f"GET /leaderboard: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  PREDICTIONS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/predictions/score")
async def save_score_prediction(
    payload: PredictionScorePayload,
    _token: dict = Depends(verify_supabase_token),
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "saved", "match_id": payload.match_id}
    try:
        db   = SessionLocal()
        user = db.query(User).filter(User.email == payload.user_id).first()
        if not user:
            try:
                user = db.query(User).filter(User.id == int(payload.user_id)).first()
            except (ValueError, TypeError):
                pass
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

        prono = (db.query(PredictionScore)
                 .filter(PredictionScore.user_id == user.id,
                          PredictionScore.match_id == str(payload.match_id))
                 .first())
        if prono:
            prono.predicted_home_score = payload.predicted_home
            prono.predicted_away_score = payload.predicted_away
        else:
            prono = PredictionScore(
                user_id=user.id, match_id=str(payload.match_id),
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
        logger.error(f"POST /predictions/score: {e}")
        return {"status": "saved", "match_id": payload.match_id}


@app.get("/predictions/score/{user_id}")
async def get_score_predictions(user_id: int, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []
    try:
        db    = SessionLocal()
        pronos = db.query(PredictionScore).filter(PredictionScore.user_id == user_id).all()
        result = [
            {"match_id": p.match_id,
             "predicted_home": p.predicted_home_score,
             "predicted_away": p.predicted_away_score,
             "points_earned":  p.points_earned}
            for p in pronos
        ]
        db.close()
        return result
    except Exception as e:
        return []


@app.post("/predictions/bracket")
async def save_bracket(payload: BracketPayload, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "saved"}
    try:
        db   = SessionLocal()
        user = db.query(User).filter(User.email == payload.user_id).first()
        if not user:
            try:
                user = db.query(User).filter(User.id == int(payload.user_id)).first()
            except (ValueError, TypeError):
                pass
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
        return {"status": "saved"}


@app.post("/predictions/annexes")
async def save_annexes(payload: AnnexesPayload, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "saved"}
    try:
        db   = SessionLocal()
        user = db.query(User).filter(User.email == payload.user_id).first()
        if not user:
            try:
                user = db.query(User).filter(User.id == int(payload.user_id)).first()
            except (ValueError, TypeError):
                pass
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        record = db.query(PredictionAnnexes).filter(PredictionAnnexes.user_id == user.id).first()
        if record:
            record.annexes_data = payload.annexes
        else:
            db.add(PredictionAnnexes(user_id=user.id, annexes_data=payload.annexes, points_earned=0))
        db.commit()
        db.close()
        return {"status": "saved"}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "saved"}


# ══════════════════════════════════════════════════════════════════════════════
#  FANTASY ROSTER
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/fantasy/roster")
async def save_roster(payload: RosterPayload, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "saved", "player_count": len(payload.player_ids),
                "remaining_budget": 100.0, "formation": payload.formation}
    try:
        db = SessionLocal()
        if len(payload.player_ids) != 15:
            db.close()
            raise HTTPException(status_code=400, detail="L'effectif doit contenir exactement 15 joueurs.")
        if len(set(payload.player_ids)) != 15:
            db.close()
            raise HTTPException(status_code=400, detail="Pas de doublons autorisés.")

        players = (db.query(Player)
                   .filter(Player.id.in_(payload.player_ids), Player.is_confirmed == True)
                   .all())
        if len(players) != len(payload.player_ids):
            db.close()
            raise HTTPException(status_code=400, detail="Joueur(s) introuvable(s).")

        nat_counts: dict = {}
        for p in players:
            k = _nation_key(p.nationality)
            nat_counts[k] = nat_counts.get(k, 0) + 1
        over = [k for k, v in nat_counts.items() if v > 3]
        if over:
            db.close()
            raise HTTPException(status_code=400, detail=f"Max 3 joueurs par nation : {', '.join(over)}")

        total = sum(p.price for p in players)
        coach = None
        if payload.coach_id:
            coach = db.query(Coach).filter(Coach.id == payload.coach_id, Coach.is_confirmed == True).first()
            if not coach:
                db.close()
                raise HTTPException(status_code=400, detail="Entraîneur introuvable.")
            if any(_nation_key(p.nationality) == _nation_key(coach.nationality) for p in players):
                db.close()
                raise HTTPException(status_code=400, detail="Conflit nationalité coach/joueur.")
            total += coach.price

        if total > 100.0:
            db.close()
            raise HTTPException(status_code=400, detail=f"Budget dépassé : {total:.1f}M€")

        user = db.query(User).filter(User.email == payload.user_id).first()
        if not user:
            try:
                user = db.query(User).filter(User.id == int(payload.user_id)).first()
            except (ValueError, TypeError):
                pass
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

        roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
        if roster:
            roster.players = players
            roster.coach_id = payload.coach_id
            roster.current_formation = payload.formation
            roster.remaining_budget  = round(100.0 - total, 2)
        else:
            roster = FantasyRoster(
                user_id=user.id, coach_id=payload.coach_id,
                current_formation=payload.formation,
                remaining_budget=round(100.0 - total, 2),
            )
            roster.players = players
            db.add(roster)

        db.commit()
        db.close()
        return {"status": "saved", "player_count": len(players),
                "remaining_budget": round(100.0 - total, 2), "formation": payload.formation}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POST /fantasy/roster: {e}")
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
        return {"players": [], "coach": None, "formation": "4-3-3", "remaining_budget": 100.0}


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/admin/recalculate")
async def manual_recalculate(_token: dict = Depends(verify_supabase_token)):
    if UPDATER_AVAILABLE:
        try:
            await tache_mise_a_jour_quotidienne()
            return {"status": "recalculated", "mode": "groq_full_update"}
        except Exception as e:
            logger.error(f"Recalcul manuel: {e}")
    return {"status": "skipped", "reason": "updater_unavailable"}


@app.post("/admin/update-now")
async def trigger_update(
    payload: ManualUpdatePayload,
    _token: dict = Depends(verify_supabase_token),
):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm=true requis")
    if not UPDATER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Updater non disponible")
    await tache_mise_a_jour_quotidienne()
    return {"status": "ok", "message": "Mise à jour Groq lancée."}


@app.get("/sync-status")
async def get_sync_status():
    stats = get_scheduler_status() if UPDATER_AVAILABLE else {"available": False}
    return {"status": "ok", **stats}


# ══════════════════════════════════════════════════════════════════════════════
#  COMPLAINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/complaints")
async def submit_complaint(payload: ComplaintPayload, _token: dict = Depends(verify_supabase_token)):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"status": "submitted", "complaint_id": 1}
    try:
        db   = SessionLocal()
        user = db.query(User).filter(User.email == payload.user_id).first()
        if not user:
            try:
                user = db.query(User).filter(User.id == int(payload.user_id)).first()
            except (ValueError, TypeError):
                pass
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        complaint = Complaint(
            user_id=user.id, match_id=str(payload.match_id) if payload.match_id else None,
            player_id=payload.player_id, description=payload.description,
            stat_claimed=json.dumps(payload.stat_claimed) if payload.stat_claimed else None,
            status="pending", created_at=datetime.utcnow().isoformat(),
        )
        db.add(complaint)
        db.commit()
        db.refresh(complaint)
        cid = complaint.id
        db.close()
        return {"status": "submitted", "complaint_id": cid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POST /complaints: {e}")
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
            u = db.query(User).filter(User.id == c.user_id).first()
            result.append({
                "id": c.id, "user_id": c.user_id,
                "username": u.username if u else "?",
                "match_id": c.match_id, "player_id": c.player_id,
                "description": c.description, "status": c.status,
                "created_at": c.created_at, "resolved_at": c.resolved_at,
            })
        db.close()
        return result
    except Exception as e:
        logger.error(f"GET /complaints: {e}")
        return []


# ── Entrypoint direct ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    multiprocessing.freeze_support()
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
        workers=1,
        log_level="info",
    )