"""
main.py — Application FastAPI Fantasy Boulzazen WC 2026
========================================================
Routes principales + auth email/password + admin panel
"""

import logging
import os
import asyncio
import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fantasy_api")
logging.getLogger("admin_auth").setLevel(logging.INFO)

from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from sqlalchemy import text


class SimpleJWT:
    @staticmethod
    def encode(payload: dict, secret: str, algorithm: str = "HS256") -> str:
        header = {"alg": algorithm, "typ": "JWT"}
        signing_input = ".".join([
            SimpleJWT._b64url(json.dumps(header, separators=(",", ":")).encode()),
            SimpleJWT._b64url(json.dumps(payload, separators=(",", ":")).encode()),
        ])
        signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        return f"{signing_input}.{SimpleJWT._b64url(signature)}"

    @staticmethod
    def decode(token: str, secret: str, algorithms=None) -> dict:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid token format")
            header_b64, payload_b64, signature_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}"
            expected = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(SimpleJWT._b64url(expected), signature_b64):
                raise ValueError("Invalid token signature")
            payload = json.loads(SimpleJWT._b64url_decode(payload_b64))
            exp = payload.get("exp")
            if exp is not None:
                if isinstance(exp, str):
                    exp = int(exp)
                if int(exp) < int(datetime.utcnow().timestamp()):
                    raise ValueError("Expired token")
            return payload
        except (ValueError, IndexError) as e:
            raise ValueError(f"Token decode error: {e}")

    @staticmethod
    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding)


pyjwt = SimpleJWT

# ────────────────────────────────────────────────────────────────
#  Imports internes
# ────────────────────────────────────────────────────────────────

try:
    from app.database import SessionLocal, engine
    from app.models import (
        Base, User, TeamNation, Player, Coach, MatchResult, PredictionScore,
        PredictionTableau, PredictionAnnexes, FantasyRoster, League,
        GroupStanding, SyncLog, Complaint,
    )
    from app.simulation_data import (
        build_fallback_coaches, build_fallback_matches, build_fallback_players,
        build_fallback_teams,
    )
    from app.admin_models import AdminTournamentConfig
    from app import admin_models  # noqa: F401
    DB_AVAILABLE = True
    MODELS_AVAILABLE = True
    logger.info("✅ DB + Models importés avec succès")
except ImportError as e:
    DB_AVAILABLE = False
    MODELS_AVAILABLE = False
    logger.error(f"❌ DB/Models import erreur : {e}")

try:
    from app.admin_routes import router as admin_router
    from app.admin_auth import verify_admin_token
    ADMIN_AVAILABLE = True
    logger.info("✅ Admin routes importées")
except ImportError as e:
    ADMIN_AVAILABLE = False
    logger.error(f"❌ Erreur import routes admin : {e}")

try:
    from app.updater import start_scheduler, get_matchs_actuels, tache_mise_a_jour_quotidienne
    UPDATER_AVAILABLE = True
except ImportError as e:
    UPDATER_AVAILABLE = False
    logger.warning(f"⚠️  Updater non disponible : {e}")

try:
    from app.scraper import get_scraping_status
    SCRAPER_AVAILABLE = True
except ImportError as e:
    SCRAPER_AVAILABLE = False
    logger.warning(f"⚠️  Scraper non disponible : {e}")

# ────────────────────────────────────────────────────────────────
#  Configuration
# ────────────────────────────────────────────────────────────────

API_BASE     = os.getenv("API_BASE", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
JWT_SECRET   = os.getenv("JWT_SECRET", "fantasy-secret-2026")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
IS_PROD      = bool(os.getenv("PRODUCTION", ""))

security = HTTPBearer(auto_error=False)

# ────────────────────────────────────────────────────────────────
#  Lifespan
# ────────────────────────────────────────────────────────────────

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

# ────────────────────────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────────────────────────

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
    except Exception as e:
        logger.warning(f"❌ Token decode erreur : {e}")
        return None


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def _verify_password(password: str, stored_password: str) -> bool:
    if not stored_password:
        return False
    if not stored_password.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password, stored_password)
    try:
        _, salt, expected = stored_password.split("$", 2)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return hmac.compare_digest(digest, expected)


def _create_user_token(user: "User") -> str:
    now = datetime.utcnow()
    return pyjwt.encode(
        {
            "sub": user.email,
            "user_id": user.id,
            "exp": int((now + timedelta(days=7)).timestamp()),
            "iat": int(now.timestamp()),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

# ────────────────────────────────────────────────────────────────
#  Initialisation FastAPI
# ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Fantasy Boulzazen WC 2026",
    description="Ligue Fantasy Football + Pronostics CDM 2026",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────
# Liste explicite d'origines autorisées
_allowed_origins = [
    FRONTEND_URL,
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# Ajout des origines depuis la variable d'environnement ALLOWED_ORIGINS
_env_origins = os.getenv("ALLOWED_ORIGINS", "")
if _env_origins:
    for _o in _env_origins.split(","):
        _o = _o.strip()
        if _o and _o not in _allowed_origins:
            _allowed_origins.append(_o)

if not IS_PROD:
    # En développement : accepte toutes les origines du réseau local (192.168.x.x)
    # via allow_origin_regex — nécessaire pour accès depuis téléphone/autre PC
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_origin_regex=r"http://192\.168\.\d+\.\d+(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("✅ CORS dev : origines LAN 192.168.x.x acceptées")
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if ADMIN_AVAILABLE:
    app.include_router(admin_router, prefix="/api/admin")
    logger.info("✅ Admin routes montées sur /api/admin")

# ────────────────────────────────────────────────────────────────
#  ROUTES AUTH UTILISATEUR
# ────────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def register(request: Request):
    """Inscription email / password / username."""
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

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
            hashed_password=_hash_password(password),
            score_fantasy=0,
            score_predictor_scores=0,
            score_predictor_tableaux=0,
            score_top_individuel=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = _create_user_token(user)
        logger.info(f"✅ Nouvel utilisateur inscrit : {email}")
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Register erreur : {e}")
        raise HTTPException(500, "Erreur lors de l'inscription")
    finally:
        db.close()


@app.post("/api/auth/login")
async def login(request: Request):
    """Connexion email / password."""
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        raise HTTPException(400, "Email et mot de passe requis")

    if not DB_AVAILABLE:
        raise HTTPException(503, "Base de données indisponible — vérifiez les logs du backend")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not _verify_password(password, user.hashed_password):
            logger.warning(f"⚠️ Tentative de connexion échouée : {email}")
            raise HTTPException(401, "Email ou mot de passe incorrect")

        if not user.hashed_password.startswith("pbkdf2_sha256$"):
            user.hashed_password = _hash_password(password)
            db.commit()

        token = _create_user_token(user)
        total = (
            (user.score_fantasy or 0)
            + (user.score_predictor_scores or 0)
            + (user.score_predictor_tableaux or 0)
            + (user.score_top_individuel or 0)
        )
        logger.info(f"✅ Connexion réussie : {email}")
        return {
            "access_token": token,
            "user": {
                "id":       user.id,
                "email":    user.email,
                "username": user.username,
                "total":    total,
                "score_fantasy":            user.score_fantasy or 0,
                "score_predictor_scores":   user.score_predictor_scores or 0,
                "score_predictor_tableaux": user.score_predictor_tableaux or 0,
                "score_top_individuel":     user.score_top_individuel or 0,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login erreur : {e}")
        raise HTTPException(500, "Erreur lors de la connexion")
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


# ────────────────────────────────────────────────────────────────
#  ROUTES DONNÉES PUBLIQUES
# ────────────────────────────────────────────────────────────────

@app.get("/api/matches")
async def get_matches():
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
                SELECT id, sofascore_id, home, away, "group" AS match_group,
                       date AS match_date, home_score, away_score,
                       status, is_locked, round
                FROM match_results
                ORDER BY id
            """)).mappings().all()
            if rows:
                return [{
                    "id":          r["sofascore_id"] or str(r["id"]),
                    "home":        r["home"],
                    "away":        r["away"],
                    "group":       r["match_group"],
                    "date":        r["match_date"],
                    "home_score":  r["home_score"],
                    "away_score":  r["away_score"],
                    "is_finished": (r["status"] or "").lower() in {"finished", "played", "closed"},
                    "is_locked":   bool(r["is_locked"]),
                    "status":      r["status"] or "scheduled",
                } for r in rows]
        except Exception as e:
            logger.error(f"GET /matches DB : {e}")
        finally:
            if db:
                db.close()

    return build_fallback_matches()


@app.get("/api/coaches")
async def get_coaches():
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return build_fallback_coaches()
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
    return build_fallback_coaches()


@app.get("/api/players")
async def get_players(
    position:    Optional[str]   = None,
    nationality: Optional[str]   = None,
    max_price:   Optional[float] = None,
):
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return build_fallback_players()
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
            return build_fallback_players()
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
        return build_fallback_players()
    finally:
        if db:
            db.close()


@app.get("/api/teams")
async def get_teams():
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return build_fallback_teams()
    db = None
    try:
        db = SessionLocal()
        teams = db.query(TeamNation).all()
        if not teams:
            return build_fallback_teams()
        return [{
            "id":           t.id,
            "name":         t.name,
            "is_confirmed": getattr(t, "is_confirmed", True),
            "is_locked":    getattr(t, "is_locked", True),
            "flag":         getattr(t, "flag", "🏴"),
        } for t in teams]
    except Exception as e:
        logger.error(f"GET /teams : {e}")
        return build_fallback_teams()
    finally:
        if db:
            db.close()


@app.get("/api/leaderboard")
async def get_leaderboard():
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


# ────────────────────────────────────────────────────────────────
#  ROUTES PRÉDICTIONS
# ────────────────────────────────────────────────────────────────

@app.get("/api/predictions/score")
async def get_user_prediction_scores(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")
    if not DB_AVAILABLE:
        return JSONResponse(content=[], status_code=200)
    db = SessionLocal()
    try:
        user_id = payload.get("user_id")
        predictions = db.query(PredictionScore).filter(PredictionScore.user_id == user_id).all()
        return [{
            "match_id": p.match_id,
            "predicted_home_score": p.predicted_home_score,
            "predicted_away_score": p.predicted_away_score,
            "is_locked": p.is_locked,
        } for p in predictions]
    finally:
        db.close()


@app.post("/api/predictions/score")
async def save_prediction_score(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")

    data = await request.json()
    match_id = str(data.get("match_id", ""))
    predicted_home = data.get("predicted_home")
    predicted_away = data.get("predicted_away")

    if predicted_home is None or predicted_away is None:
        raise HTTPException(400, "Scores manquants")

    if not DB_AVAILABLE:
        return {"status": "ok", "message": "Mode sans BDD"}

    db = SessionLocal()
    try:
        user_id = payload.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "Utilisateur introuvable")

        match_info = db.query(MatchResult).filter(MatchResult.sofascore_id == match_id).first()
        if match_info and match_info.is_locked:
            raise HTTPException(423, "Ce match est verrouillé.")

        existing = db.query(PredictionScore).filter(
            PredictionScore.user_id == user.id,
            PredictionScore.match_id == match_id,
        ).first()

        if existing:
            if existing.is_locked:
                raise HTTPException(423, "Ce pronostic est verrouillé")
            existing.predicted_home_score = int(predicted_home)
            existing.predicted_away_score = int(predicted_away)
        else:
            db.add(PredictionScore(
                user_id=user.id,
                match_id=match_id,
                predicted_home_score=int(predicted_home),
                predicted_away_score=int(predicted_away),
                points_earned=0,
                is_locked=False,
            ))

        db.commit()
        return {"status": "ok", "message": "Pronostic sauvegardé"}
    finally:
        db.close()


@app.get("/api/predictions/bracket")
async def get_user_prediction_bracket(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")
    if not DB_AVAILABLE:
        return JSONResponse(content={}, status_code=200)
    db = SessionLocal()
    try:
        user_id = payload.get("user_id")
        prediction = db.query(PredictionTableau).filter(PredictionTableau.user_id == user_id).first()
        return prediction.bracket_data if prediction else {}
    finally:
        db.close()


@app.post("/api/predictions/bracket")
async def save_bracket(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")

    data = await request.json()
    if not DB_AVAILABLE:
        return {"status": "ok", "message": "Tableau reçu en mode simulation"}

    db = SessionLocal()
    try:
        user_id = payload.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "Utilisateur introuvable")

        tournament_config = db.query(AdminTournamentConfig).first()
        if tournament_config and tournament_config.start_date:
            try:
                tournament_start = datetime.fromisoformat(tournament_config.start_date)
                if datetime.utcnow() >= tournament_start:
                    raise HTTPException(423, "Tableau verrouillé après le début du tournoi.")
            except ValueError:
                pass

        bracket_data = data.get("bracket_data") or data
        existing = db.query(PredictionTableau).filter(PredictionTableau.user_id == user.id).first()
        if existing:
            existing.bracket_data = bracket_data
        else:
            db.add(PredictionTableau(user_id=user.id, bracket_data=bracket_data, points_earned=0))
        db.commit()
        return {"status": "ok", "message": "Tableau sauvegardé"}
    finally:
        db.close()


@app.get("/api/predictions/annexes")
async def get_user_prediction_annexes(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")
    if not DB_AVAILABLE:
        return JSONResponse(content={}, status_code=200)
    db = SessionLocal()
    try:
        user_id = payload.get("user_id")
        prediction = db.query(PredictionAnnexes).filter(PredictionAnnexes.user_id == user_id).first()
        return prediction.annexes_data if prediction else {}
    finally:
        db.close()


@app.post("/api/predictions/annexes")
async def save_annexes(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")

    data = await request.json()
    if not DB_AVAILABLE:
        return {"status": "ok", "message": "Annexes reçues en mode simulation"}

    db = SessionLocal()
    try:
        user_id = payload.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "Utilisateur introuvable")

        annexes_data = data.get("annexes") or data
        existing = db.query(PredictionAnnexes).filter(PredictionAnnexes.user_id == user.id).first()
        if existing:
            existing.annexes_data = annexes_data
        else:
            db.add(PredictionAnnexes(user_id=user.id, annexes_data=annexes_data, points_earned=0))
        db.commit()
        return {"status": "ok", "message": "Annexes sauvegardées"}
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────
#  ROUTES FANTASY ROSTER
# ────────────────────────────────────────────────────────────────

@app.get("/api/fantasy/roster")
async def get_user_roster(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")

    if not DB_AVAILABLE:
        return JSONResponse(content={
            "player_ids": [], "players_data": [], "coach_id": None,
            "coach_data": None, "current_formation": "4-3-3", "remaining_budget": 100.0,
        }, status_code=200)

    db = SessionLocal()
    try:
        user_id = payload.get("user_id")
        roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user_id).first()
        if not roster:
            return JSONResponse(content={
                "player_ids": [], "players_data": [], "coach_id": None,
                "coach_data": None, "current_formation": "4-3-3", "remaining_budget": 100.0,
            }, status_code=200)

        players_in_roster = [{
            "id": p.id, "name": p.name, "position": p.position,
            "nationality": p.nationality, "price": p.price, "club": p.club,
        } for p in roster.players]

        coach_in_roster = None
        if roster.coach:
            coach_in_roster = {
                "id": roster.coach.id, "name": roster.coach.name,
                "nationality": roster.coach.nationality, "price": roster.coach.price,
            }

        return {
            "player_ids": [p.id for p in roster.players],
            "players_data": players_in_roster,
            "coach_id": roster.coach_id,
            "coach_data": coach_in_roster,
            "current_formation": roster.current_formation,
            "remaining_budget": roster.remaining_budget,
        }
    finally:
        db.close()


@app.post("/api/fantasy/roster")
async def save_roster(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        raise HTTPException(401, "Token manquant")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide")

    data = await request.json()
    if not DB_AVAILABLE:
        return {"status": "ok", "message": "Équipe reçue en mode simulation", "remaining_budget": data.get("remaining_budget", 0)}

    db = SessionLocal()
    try:
        user_id = payload.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "Utilisateur introuvable")

        player_ids = [int(pid) for pid in data.get("player_ids", []) if str(pid).isdigit()]
        coach_id = data.get("coach_id")

        players = db.query(Player).filter(Player.id.in_(player_ids)).all() if player_ids else []
        coach = db.query(Coach).filter(Coach.id == coach_id).first() if coach_id else None

        total_cost = sum(p.price for p in players) + (coach.price if coach else 0.0)
        remaining = round(100.0 - total_cost, 2)

        if remaining < 0:
            raise HTTPException(400, "Budget dépassé.")

        roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
        if not roster:
            roster = FantasyRoster(user_id=user.id)
            db.add(roster)
        roster.current_formation = data.get("formation") or "4-3-3"
        roster.remaining_budget = remaining
        roster.players = players
        roster.coach_id = coach.id if coach else None

        db.commit()
        return {"status": "ok", "message": "Équipe sauvegardée", "remaining_budget": remaining}
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────
#  ROUTES STATUS / HEALTH
# ────────────────────────────────────────────────────────────────

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
        "db_available":      DB_AVAILABLE,
    }


@app.post("/api/admin/force-scraping")
async def force_scraping(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token manquant")
    token = authorization[7:]
    payload = verify_admin_token(token) if ADMIN_AVAILABLE else None
    if not payload:
        raise HTTPException(401, "Token admin invalide")
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
        "models":    "✅" if MODELS_AVAILABLE else "❌",
        "admin":     "✅" if ADMIN_AVAILABLE else "⚠️",
        "updater":   "✅" if UPDATER_AVAILABLE else "⚠️",
    }


@app.get("/")
async def root():
    return {
        "message":     "🎮 Fantasy Boulzazen WC 2026",
        "docs":        f"{API_BASE}/docs",
        "health":      f"{API_BASE}/api/health",
        "admin_panel": f"{FRONTEND_URL}/admin",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)