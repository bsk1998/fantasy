"""
main.py — Application FastAPI Fantasy Boulzazen WC 2026
========================================================
Routes principales + auth email/password + admin panel
"""

import logging
import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt as pyjwt
from sqlalchemy import text

# ────────────────────────────────────────────────────────────────────────
#  Imports internes
# ────────────────────────────────────────────────────────────────────────

try:
    from app.database import SessionLocal, engine
    from app.models import Base, User, TeamNation, Player, Coach, MatchResult, PredictionScore
    DB_AVAILABLE = True
    MODELS_AVAILABLE = True
except ImportError as e:
    DB_AVAILABLE = False
    MODELS_AVAILABLE = False
    print(f"❌ DB/Models import erreur : {e}")

try:
    from app.admin_routes import router as admin_router
    from app.admin_auth import verify_admin_token
    ADMIN_AVAILABLE = True
except ImportError as e:
    ADMIN_AVAILABLE = False
    print(f"⚠️ Admin routes non disponibles : {e}")

try:
    from app.updater import start_scheduler, get_matchs_actuels, tache_mise_a_jour_quotidienne
    UPDATER_AVAILABLE = True
except ImportError as e:
    UPDATER_AVAILABLE = False
    print(f"⚠️ Updater non disponible : {e}")

try:
    from app.scraper import get_scraping_status
    SCRAPER_AVAILABLE = True
except ImportError as e:
    SCRAPER_AVAILABLE = False
    print(f"⚠️ Scraper non disponible : {e}")

# ────────────────────────────────────────────────────────────────────────
#  Configuration
# ────────────────────────────────────────────────────────────────────────

logger = logging.getLogger("fantasy_api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

API_BASE    = os.getenv("API_BASE", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
JWT_SECRET  = os.getenv("JWT_SECRET", "fantasy-secret-2026")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

security = HTTPBearer(auto_error=False)

# ────────────────────────────────────────────────────────────────────────
#  Événements Lifespan
# ────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Fantasy Boulzazen WC 2026 — Démarrage...")

    if DB_AVAILABLE and MODELS_AVAILABLE:
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Base de données initialisée")
        except Exception as e:
            logger.error(f"❌ DB init erreur : {e}")

    groq_ok = await _verifier_groq()

    if UPDATER_AVAILABLE:
        try:
            start_scheduler()
            logger.info("✅ Scheduler démarré")
        except Exception as e:
            logger.error(f"❌ Scheduler erreur : {e}")

    if groq_ok and DB_AVAILABLE:
        try:
            db = SessionLocal()
            try:
                count = db.execute(text("SELECT COUNT(*) FROM match_results")).scalar()
            except Exception:
                count = 0
            finally:
                db.close()
            if count == 0:
                logger.info("🔄 DB vide + Groq disponible → scraping initial...")
                asyncio.create_task(_scraping_initial())
        except Exception:
            pass

    logger.info(
        f"✨ Fantasy Boulzazen démarré | "
        f"DB={DB_AVAILABLE} | Groq={'✅' if groq_ok else '❌'} | "
        f"Admin={ADMIN_AVAILABLE} | Updater={UPDATER_AVAILABLE}"
    )

    yield

    logger.info("🛑 Arrêt de l'application...")


# ────────────────────────────────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────────────────────────────────

async def _verifier_groq() -> bool:
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        logger.warning("⚠️  GROQ_API_KEY manquante — scraping désactivé")
        return False
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": "OK"}],
            max_tokens=5,
        )
        if resp.choices[0].message.content.strip():
            logger.info("✅ Groq API opérationnelle")
            return True
    except Exception as e:
        logger.error(f"❌ Groq API erreur : {e}")
    return False


async def _scraping_initial():
    await asyncio.sleep(5)
    if UPDATER_AVAILABLE:
        try:
            await tache_mise_a_jour_quotidienne()
        except Exception as e:
            logger.error(f"Scraping initial erreur : {e}")


def _decode_token(token: str) -> Optional[dict]:
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────────
#  Initialisation FastAPI
# ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Fantasy Boulzazen WC 2026",
    description="Ligue Fantasy Football + Pronostics CDM 2026",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ADMIN_AVAILABLE:
    app.include_router(admin_router)
    logger.info("✅ Admin routes incluses")


# ────────────────────────────────────────────────────────────────────────
#  ROUTES AUTH
# ────────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def register(request: Request):
    """Inscription email / password / username."""
    data     = await request.json()
    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    username = (data.get("username") or "").strip()

    if not email or not password or not username:
        raise HTTPException(400, "Email, mot de passe et pseudo sont requis")
    if len(password) < 4:
        raise HTTPException(400, "Mot de passe trop court (min 4 caractères)")

    if not DB_AVAILABLE:
        raise HTTPException(503, "Base de données indisponible")

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(409, "Cet email est déjà utilisé")
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(409, "Ce pseudo est déjà pris")

        user = User(
            email=email,
            username=username,
            hashed_password=password,   # ⚠️ en prod : hasher avec bcrypt
            score_fantasy=0,
            score_predictor_scores=0,
            score_predictor_tableaux=0,
            score_top_individuel=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = pyjwt.encode(
            {"sub": email, "user_id": user.id},
            JWT_SECRET, algorithm="HS256"
        )
        return {
            "access_token": token,
            "user": {
                "id":       user.id,
                "email":    user.email,
                "username": user.username,
                "total":    0,
                "score_fantasy": 0,
                "score_predictor_scores": 0,
            },
        }
    finally:
        db.close()


@app.post("/api/auth/login")
async def login(request: Request):
    """Connexion email / password."""
    data     = await request.json()
    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        raise HTTPException(400, "Email et mot de passe requis")

    if not DB_AVAILABLE:
        raise HTTPException(503, "Base de données indisponible")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or user.hashed_password != password:
            raise HTTPException(401, "Email ou mot de passe incorrect")

        token = pyjwt.encode(
            {"sub": email, "user_id": user.id},
            JWT_SECRET, algorithm="HS256"
        )
        total = (
            (user.score_fantasy or 0)
            + (user.score_predictor_scores or 0)
            + (user.score_predictor_tableaux or 0)
            + (user.score_top_individuel or 0)
        )
        return {
            "access_token": token,
            "user": {
                "id":       user.id,
                "email":    user.email,
                "username": user.username,
                "total":    total,
                "score_fantasy":           user.score_fantasy or 0,
                "score_predictor_scores":  user.score_predictor_scores or 0,
                "score_predictor_tableaux":user.score_predictor_tableaux or 0,
                "score_top_individuel":    user.score_top_individuel or 0,
            },
        }
    finally:
        db.close()


@app.get("/api/auth/me")
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Retourne l'utilisateur connecté depuis son JWT."""
    if not credentials:
        raise HTTPException(401, "Token manquant")

    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide ou expiré")

    email = payload.get("sub")
    if not email or not DB_AVAILABLE:
        raise HTTPException(401, "Token invalide")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(404, "Utilisateur introuvable")

        total = (
            (user.score_fantasy or 0)
            + (user.score_predictor_scores or 0)
            + (user.score_predictor_tableaux or 0)
            + (user.score_top_individuel or 0)
        )
        return {
            "id":       user.id,
            "email":    user.email,
            "username": user.username,
            "total":    total,
            "score_fantasy":            user.score_fantasy or 0,
            "score_predictor_scores":   user.score_predictor_scores or 0,
            "score_predictor_tableaux": user.score_predictor_tableaux or 0,
            "score_top_individuel":     user.score_top_individuel or 0,
        }
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────────────
#  ROUTES DONNÉES PUBLIQUES
# ────────────────────────────────────────────────────────────────────────

@app.get("/api/matches")
async def get_matches():
    """Retourne la liste des matchs (3 niveaux de fallback)."""
    if UPDATER_AVAILABLE:
        try:
            live = get_matchs_actuels()
            if live:
                return live
        except Exception as e:
            logger.warning(f"get_matchs_actuels erreur : {e}")

    if DB_AVAILABLE:
        db = None
        try:
            db = SessionLocal()
            rows = db.execute(text("""
                SELECT match_id, display_order, home, away, match_group,
                       match_date, home_score, away_score,
                       status, is_finished, is_locked
                FROM match_results
                ORDER BY COALESCE(display_order, 9999), match_id
            """)).mappings().all()
            if rows:
                return [{
                    "id":          r["match_id"],
                    "home":        r["home"],
                    "away":        r["away"],
                    "group":       r["match_group"],
                    "date":        r["match_date"],
                    "home_score":  r["home_score"],
                    "away_score":  r["away_score"],
                    "is_finished": bool(r["is_finished"]),
                    "is_locked":   bool(r["is_locked"]),
                    "status":      r["status"] or "scheduled",
                } for r in rows]
        except Exception as e:
            logger.error(f"GET /matches DB : {e}")
        finally:
            if db:
                db.close()

    return {
        "data": [],
        "message": "Données en cours de chargement — scraping Groq en attente",
        "groq_actif": bool(os.getenv("GROQ_API_KEY")),
    }


@app.get("/api/coaches")
async def get_coaches():
    """Retourne la liste des entraîneurs."""
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"data": [], "message": "Entraîneurs en cours de chargement"}

    db = None
    try:
        db = SessionLocal()
        coaches = db.query(Coach).filter(Coach.is_confirmed == True).all()
        if coaches:
            return [{
                "id":           c.id,
                "name":         c.name,
                "nationality":  c.nationality,
                "price":        c.price,
                "wins":         c.wins or 0,
                "losses":       c.losses or 0,
                "points_total": c.points_total or 0,
                "status":       c.status or "present",
            } for c in coaches]
    except Exception as e:
        logger.error(f"GET /coaches : {e}")
    finally:
        if db:
            db.close()

    return {"data": [], "message": "Entraîneurs en cours de chargement"}


@app.get("/api/players")
async def get_players(
    position:    Optional[str]   = None,
    nationality: Optional[str]   = None,
    max_price:   Optional[float] = None,
):
    """Retourne la liste des joueurs avec filtres."""
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"data": [], "message": "Joueurs en cours de chargement"}

    db = None
    try:
        db = SessionLocal()
        query = db.query(Player).filter(Player.is_confirmed == True)
        if position and position != "ALL":
            query = query.filter(Player.position == position.upper())
        if nationality:
            query = query.filter(Player.nationality.ilike(f"%{nationality}%"))
        if max_price is not None:
            query = query.filter(Player.price <= max_price)

        players = query.order_by(Player.price.desc()).all()
        if not players:
            return {"data": [], "message": "Joueurs en cours de chargement"}

        return [{
            "id":           p.id,
            "name":         p.name,
            "position":     p.position,
            "nationality":  p.nationality,
            "price":        p.price,
            "club":         getattr(p, "club", None),
            "goals":        p.goals or 0,
            "assists":      p.assists or 0,
            "points_total": p.points_total or 0,
            "is_confirmed": p.is_confirmed,
        } for p in players]
    except Exception as e:
        logger.error(f"GET /players : {e}")
        return {"data": [], "message": str(e)}
    finally:
        if db:
            db.close()


@app.get("/api/teams")
async def get_teams():
    """Retourne la liste des nations."""
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {"data": [], "message": "Nations en cours de chargement"}

    db = None
    try:
        db = SessionLocal()
        teams = db.query(TeamNation).all()
        return [{
            "id":           t.id,
            "name":         t.name,
            "is_confirmed": getattr(t, "is_confirmed", True),
            "is_locked":    getattr(t, "is_locked", True),
            "flag":         getattr(t, "flag", "🏴"),
        } for t in teams]
    except Exception as e:
        logger.error(f"GET /teams : {e}")
        return {"data": [], "message": str(e)}
    finally:
        if db:
            db.close()


@app.get("/api/leaderboard")
async def get_leaderboard():
    """Retourne le classement général."""
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return []

    db = None
    try:
        db = SessionLocal()
        users = db.query(User).all()
        result = []
        for u in users:
            fantasy  = u.score_fantasy or 0
            scores   = u.score_predictor_scores or 0
            bracket  = u.score_predictor_tableaux or 0
            annexes  = u.score_top_individuel or 0
            total    = fantasy + scores + bracket + annexes
            result.append({
                "username": u.username or u.email,
                "fantasy":  fantasy,
                "scores":   scores,
                "bracket":  bracket,
                "annexes":  annexes,
                "total":    total,
            })
        return sorted(result, key=lambda x: x["total"], reverse=True)
    except Exception as e:
        logger.error(f"GET /leaderboard : {e}")
        return []
    finally:
        if db:
            db.close()


# ────────────────────────────────────────────────────────────────────────
#  ROUTES PRÉDICTIONS
# ────────────────────────────────────────────────────────────────────────

@app.post("/api/predictions/score")
async def save_prediction_score(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Sauvegarde un pronostic de score."""
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")

    data = await request.json()
    match_id       = str(data.get("match_id", ""))
    predicted_home = data.get("predicted_home")
    predicted_away = data.get("predicted_away")

    if predicted_home is None or predicted_away is None:
        raise HTTPException(400, "Scores manquants")

    if not DB_AVAILABLE:
        return {"status": "ok", "message": "Mode sans BDD — non persisté"}

    db = SessionLocal()
    try:
        email = payload.get("sub")
        user  = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(404, "Utilisateur introuvable")

        existing = db.query(PredictionScore).filter(
            PredictionScore.user_id  == user.id,
            PredictionScore.match_id == match_id,
        ).first()

        if existing:
            if existing.is_locked:
                raise HTTPException(423, "Ce pronostic est verrouillé")
            existing.predicted_home_score = int(predicted_home)
            existing.predicted_away_score = int(predicted_away)
        else:
            pred = PredictionScore(
                user_id=user.id,
                match_id=match_id,
                predicted_home_score=int(predicted_home),
                predicted_away_score=int(predicted_away),
                points_earned=0,
                is_locked=False,
            )
            db.add(pred)

        db.commit()
        return {"status": "ok", "message": "Pronostic sauvegardé"}
    finally:
        db.close()


@app.post("/api/predictions/bracket")
async def save_bracket(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Sauvegarde le tableau de tournoi."""
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")

    data = await request.json()
    return {"status": "ok", "message": "Tableau reçu"}


@app.post("/api/predictions/annexes")
async def save_annexes(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Sauvegarde les prédictions annexes."""
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")

    data = await request.json()
    return {"status": "ok", "message": "Annexes reçues"}


# ────────────────────────────────────────────────────────────────────────
#  ROUTES FANTASY ROSTER
# ────────────────────────────────────────────────────────────────────────

@app.post("/api/fantasy/roster")
async def save_roster(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Sauvegarde l'équipe Fantasy d'un utilisateur."""
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")

    data = await request.json()
    return {"status": "ok", "message": "Équipe sauvegardée", "remaining_budget": 0}


# ────────────────────────────────────────────────────────────────────────
#  ROUTES STATUS / HEALTH
# ────────────────────────────────────────────────────────────────────────

@app.get("/api/scraping/status")
async def scraping_status():
    status_data = {}
    if SCRAPER_AVAILABLE:
        try:
            status_data = get_scraping_status()
        except Exception:
            pass

    mem_matchs = 0
    if UPDATER_AVAILABLE:
        try:
            mem_matchs = len(get_matchs_actuels())
        except Exception:
            pass

    db_matchs, db_coaches, db_players = 0, 0, 0
    if DB_AVAILABLE:
        db = None
        try:
            db = SessionLocal()
            db_matchs  = db.execute(text("SELECT COUNT(*) FROM match_results")).scalar() or 0
            db_coaches = db.query(Coach).count()
            db_players = db.query(Player).count()
        except Exception:
            pass
        finally:
            if db:
                db.close()

    return {
        "sources":           status_data,
        "matchs_memoire":    mem_matchs,
        "matchs_db":         db_matchs,
        "coaches_db":        db_coaches,
        "players_db":        db_players,
        "groq_configure":    bool(os.getenv("GROQ_API_KEY")),
        "groq_installed":    SCRAPER_AVAILABLE,
        "admin_installed":   ADMIN_AVAILABLE,
        "updater_installed": UPDATER_AVAILABLE,
    }


@app.post("/api/admin/force-scraping")
async def force_scraping(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token manquant")
    token = authorization[7:]
    payload = verify_admin_token(token) if ADMIN_AVAILABLE else None
    if not payload:
        raise HTTPException(401, "Token invalide")
    if not UPDATER_AVAILABLE:
        raise HTTPException(503, "Updater non disponible")
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(400, "GROQ_API_KEY manquante")
    try:
        await tache_mise_a_jour_quotidienne()
        return {"status": "ok", "message": "Scraping lancé"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/health")
async def health_check():
    return {
        "status":    "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "db":        "✅" if DB_AVAILABLE else "❌",
        "admin":     "✅" if ADMIN_AVAILABLE else "⚠️",
        "updater":   "✅" if UPDATER_AVAILABLE else "⚠️",
    }


@app.get("/")
async def root():
    return {
        "message":     "🎮 Fantasy Boulzazen WC 2026",
        "docs":        f"{API_BASE}/docs",
        "admin_panel": f"{FRONTEND_URL}/admin",
    }


@app.get("/api/info")
async def api_info():
    return {
        "app":     "Fantasy Boulzazen WC 2026",
        "version": "1.0.0",
        "features": {
            "fantasy_league":       True,
            "predictions_score":    True,
            "predictions_bracket":  True,
            "predictions_annexes":  True,
            "admin_panel":          ADMIN_AVAILABLE,
            "groq_integration":     bool(GROQ_API_KEY),
            "automatic_scraping":   UPDATER_AVAILABLE,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)