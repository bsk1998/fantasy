"""
main.py — Fantasy Boulzazen WC 2026 · Backend FastAPI complet
==============================================================
v5.0 — Corrections critiques :
  ✅ App FastAPI complète (plus un simple patch)
  ✅ Lifespan APScheduler (startup/shutdown propre)
  ✅ Toutes les routes : auth, players, coaches, matches,
     fantasy, predictions, leaderboard, scraping, admin
  ✅ Optional importé partout
  ✅ Sync au login (lazy loading)
  ✅ CORS configuré depuis .env
"""

from __future__ import annotations

import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import (
    Depends, FastAPI, HTTPException, Header,
    Query, Body, status as http_status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

# ── Config ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fantasy_main")

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "dev-secret-key-for-development-only")
ALLOWED_ORIGINS_RAW = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:4173",
)
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

# ── Imports internes (avec fallbacks gracieux) ─────────────────────────────

DB_AVAILABLE = False
try:
    from app.database import SessionLocal, engine, get_db
    from app.models import (
        Base, Coach, Complaint, FantasyRoster, GroupStanding,
        League, MatchResult, Player, PredictionAnnexes,
        PredictionScore, PredictionTableau, SyncLog,
        TeamNation, User, roster_player, user_league,
    )
    Base.metadata.create_all(bind=engine)
    DB_AVAILABLE = True
    logger.info("✅ Base de données initialisée")
except Exception as _db_err:
    logger.error("❌ DB indisponible : %s", _db_err)

SCRAPER_AVAILABLE = False
get_scraping_status_fn = lambda: {}
try:
    from app.scraper import get_scraping_status as get_scraping_status_fn
    SCRAPER_AVAILABLE = True
except ImportError:
    pass

UPDATER_AVAILABLE = False
startup_handler = shutdown_handler = lambda: None  # sync no-ops par défaut
get_matchs_actuels = lambda: []
get_stats_sync = lambda: {"scheduler_actif": False}
sync_au_login_fn = None

try:
    from app.updater import (
        startup_handler,      # type: ignore[assignment]
        shutdown_handler,     # type: ignore[assignment]
        get_matchs_actuels,   # type: ignore[assignment]
        get_stats_sync,       # type: ignore[assignment]
        sync_au_login as sync_au_login_fn,  # type: ignore[assignment]
    )
    UPDATER_AVAILABLE = True
    logger.info("✅ Updater/scheduler chargé")
except ImportError as _up_err:
    logger.warning("⚠️  Updater non disponible : %s", _up_err)

ADMIN_AVAILABLE = False
try:
    from app.admin_routes import router as admin_router
    from app.admin_models import AdminLog, AdminGameRule, AdminPricingTemplate
    ADMIN_AVAILABLE = True
except ImportError:
    pass

# ── Auth helpers ───────────────────────────────────────────────────────────

try:
    from jose import JWTError, jwt as _jose_jwt  # type: ignore
    def _create_token(data: dict, expires_hours: int = 72) -> str:
        payload = {**data, "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours)}
        return _jose_jwt.encode(payload, SUPABASE_JWT_SECRET, algorithm="HS256")

    def _verify_token(token: str) -> Optional[dict]:
        try:
            return _jose_jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
        except JWTError:
            return None
except ImportError:
    import base64, hashlib, hmac, json as _json

    def _create_token(data: dict, expires_hours: int = 72) -> str:  # type: ignore[misc]
        payload = {**data, "exp": int((datetime.now(timezone.utc) + timedelta(hours=expires_hours)).timestamp())}
        header  = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
        body    = base64.urlsafe_b64encode(_json.dumps(payload).encode()).rstrip(b"=").decode()
        sig     = base64.urlsafe_b64encode(
            hmac.new(SUPABASE_JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
        ).rstrip(b"=").decode()
        return f"{header}.{body}.{sig}"

    def _verify_token(token: str) -> Optional[dict]:  # type: ignore[misc]
        try:
            parts = token.split(".")
            if len(parts) != 3: return None
            pad  = lambda s: s + "=" * (-len(s) % 4)
            return _json.loads(base64.urlsafe_b64decode(pad(parts[1])))
        except Exception:
            return None

try:
    from passlib.context import CryptContext  # type: ignore
    _pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hash_password   = lambda p: _pwd_ctx.hash(p)
    verify_password = lambda plain, hashed: _pwd_ctx.verify(plain, hashed)
except ImportError:
    import hashlib
    hash_password   = lambda p: hashlib.sha256(p.encode()).hexdigest()  # type: ignore[misc]
    verify_password = lambda plain, hashed: hashlib.sha256(plain.encode()).hexdigest() == hashed  # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════════════
#  LIFESPAN — startup / shutdown
# ══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🟢 Démarrage Fantasy Boulzazen API v5.0")
    try:
        await startup_handler()
    except Exception as exc:
        logger.warning("Scheduler non démarré : %s", exc)
    yield
    logger.info("🔴 Arrêt Fantasy Boulzazen API")
    try:
        await shutdown_handler()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Fantasy Boulzazen — API WC 2026",
    description="Backend complet pour la ligue privée Fantasy Coupe du Monde 2026",
    version="5.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monter le routeur admin
if ADMIN_AVAILABLE:
    app.include_router(admin_router, prefix="/api/admin")
    logger.info("✅ Routes admin montées")


# ══════════════════════════════════════════════════════════════════════════════
#  DÉPENDANCES
# ══════════════════════════════════════════════════════════════════════════════

def get_db_session():
    if not DB_AVAILABLE:
        raise HTTPException(503, "Base de données indisponible")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization[7:]


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db_session),
) -> User:
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(401, "Token manquant")
    payload = _verify_token(token)
    if not payload:
        raise HTTPException(401, "Token invalide ou expiré")
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(401, "Token sans identifiant utilisateur")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(401, "Utilisateur introuvable")
    return user


def get_optional_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db_session),
) -> Optional[User]:
    try:
        return get_current_user(authorization, db)
    except HTTPException:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    email: str
    password: str
    username: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RosterSaveRequest(BaseModel):
    user_id: Any
    player_ids: List[int]
    coach_id: Optional[int] = None
    formation: str = "4-3-3"
    remaining_budget: float = 100.0

class PredictionScoreRequest(BaseModel):
    user_id: Any
    match_id: str
    predicted_home: int
    predicted_away: int

class BracketSaveRequest(BaseModel):
    user_id: Any
    bracket_data: dict

class AnnexesSaveRequest(BaseModel):
    user_id: Any
    annexes: dict

class ComplaintCreateRequest(BaseModel):
    category: str
    priority: str = "medium"
    title: str
    description: str
    match_id: Optional[str] = None
    player_id: Optional[int] = None
    stat_claimed: Optional[str] = None

class LeagueCreateRequest(BaseModel):
    name: str
    password: Optional[str] = None
    is_public: bool = False
    max_members: int = 20

class LeagueJoinRequest(BaseModel):
    invite_code: str
    password: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _user_to_dict(user: User) -> dict:
    total = (
        (user.score_fantasy or 0)
        + (user.score_predictor_scores or 0)
        + (user.score_predictor_tableaux or 0)
        + (user.score_top_individuel or 0)
    )
    return {
        "id":                        user.id,
        "email":                     user.email or "",
        "username":                  user.username or "",
        "score_fantasy":             user.score_fantasy or 0,
        "score_predictor_scores":    user.score_predictor_scores or 0,
        "score_predictor_tableaux":  user.score_predictor_tableaux or 0,
        "score_top_individuel":      user.score_top_individuel or 0,
        "fantasy":                   user.score_fantasy or 0,
        "scores":                    user.score_predictor_scores or 0,
        "bracket":                   user.score_predictor_tableaux or 0,
        "annexes":                   user.score_top_individuel or 0,
        "total":                     total,
    }


def _player_to_dict(p: Player) -> dict:
    return {
        "id":           p.id,
        "name":         p.name or "",
        "position":     p.position or "M",
        "nationality":  p.nationality or "",
        "club":         p.club or "",
        "number":       p.number,
        "price":        p.price or 6.0,
        "is_confirmed": p.is_confirmed or False,
        "goals":        p.goals or 0,
        "assists":      p.assists or 0,
        "points_total": p.points_total or 0,
    }


def _coach_to_dict(c: Coach) -> dict:
    return {
        "id":           c.id,
        "name":         c.name or "",
        "nationality":  c.nationality or "",
        "team_name":    c.team_name or "",
        "price":        c.price or 5.0,
        "is_confirmed": c.is_confirmed or False,
        "wins":         c.wins or 0,
        "losses":       c.losses or 0,
        "points_total": c.points_total or 0,
        "status":       c.status or "present",
    }


def _match_to_dict(m: MatchResult) -> dict:
    return {
        "id":          m.sofascore_id or str(m.id),
        "home":        m.home or "",
        "away":        m.away or "",
        "group":       m.group,
        "round":       m.round or "group_stage",
        "date":        m.date or "",
        "home_score":  m.home_score,
        "away_score":  m.away_score,
        "status":      m.status or "scheduled",
        "is_finished": m.is_finished or False,
        "is_locked":   m.is_locked or False,
        "player_stats": m.player_stats or [],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — HEALTH & STATUS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
@app.get("/api/health")
async def health():
    return {
        "status":    "ok",
        "version":   "5.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db":        DB_AVAILABLE,
        "updater":   UPDATER_AVAILABLE,
        "scraper":   SCRAPER_AVAILABLE,
        "admin":     ADMIN_AVAILABLE,
    }


@app.get("/api/scraping/status")
async def scraping_status():
    status_data: dict = {}
    if SCRAPER_AVAILABLE:
        try:
            status_data = get_scraping_status_fn()
        except Exception:
            pass

    mem_matchs = 0
    if UPDATER_AVAILABLE:
        try:
            mem_matchs = len(get_matchs_actuels())
        except Exception:
            pass

    db_matchs = db_coaches = db_players = 0
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
        "groq_configure":    status_data.get("groq_configure",  bool(os.getenv("GROQ_API_KEY"))),
        "gemini_configure":  status_data.get("gemini_configure",bool(os.getenv("GEMINI_API_KEY"))),
        "ai_provider":       status_data.get("ai_provider",     os.getenv("AI_PROVIDER", "auto")),
        "active_model":      status_data.get("active_model",    "—"),
        "matchs_memoire":    mem_matchs,
        "matchs_db":         db_matchs,
        "coaches_db":        db_coaches,
        "players_db":        db_players,
        "groq_installed":    SCRAPER_AVAILABLE,
        "admin_installed":   ADMIN_AVAILABLE,
        "updater_installed": UPDATER_AVAILABLE,
        "db_available":      DB_AVAILABLE,
    }


@app.get("/api/sync-status")
async def sync_status():
    stats = get_stats_sync()
    return {
        "status":               "ok",
        "scheduler_actif":      stats.get("scheduler_actif", False),
        "derniere_mise_a_jour": stats.get("derniere_mise_a_jour"),
        "matchs_scraped":       stats.get("matchs_scraped", 0),
        "joueurs_recalcules":   stats.get("joueurs_recalcules", 0),
        "effectifs_nouveaux":   stats.get("effectifs_nouveaux", 0),
        "timestamp":            stats.get("timestamp"),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — AUTHENTIFICATION
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db_session)):
    if db.query(User).filter(User.email == req.email.lower()).first():
        raise HTTPException(400, "Cet email est déjà utilisé.")
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(400, "Ce pseudo est déjà pris.")

    user = User(
        email=req.email.lower(),
        username=req.username,
        hashed_password=hash_password(req.password),
        score_fantasy=0,
        score_predictor_scores=0,
        score_predictor_tableaux=0,
        score_top_individuel=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Ajouter à la Ligue Générale si elle existe
    try:
        league = db.query(League).filter(League.name == "Ligue Générale Boulzazen").first()
        if league and user not in league.members:
            league.members.append(user)
            db.commit()
    except Exception:
        pass

    token = _create_token({"sub": str(user.id), "email": user.email})
    return {"access_token": token, "token_type": "bearer", "user": _user_to_dict(user)}


@app.post("/api/auth/login")
async def login(req: LoginRequest, db: Session = Depends(get_db_session)):
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.hashed_password or ""):
        raise HTTPException(401, "Email ou mot de passe incorrect.")

    # Sync lazy au login
    if UPDATER_AVAILABLE and sync_au_login_fn:
        try:
            await sync_au_login_fn(user.email, db)
            db.refresh(user)
        except Exception as exc:
            logger.warning("Sync au login échouée : %s", exc)

    token = _create_token({"sub": str(user.id), "email": user.email})
    return {"access_token": token, "token_type": "bearer", "user": _user_to_dict(user)}


@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return _user_to_dict(current_user)


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — JOUEURS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/players")
async def get_players(
    position: Optional[str] = Query(None),
    nationality: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db_session),
):
    q = db.query(Player).filter(Player.is_confirmed == True)
    if position:
        q = q.filter(Player.position == position.upper())
    if nationality:
        q = q.filter(Player.nationality.ilike(f"%{nationality}%"))
    if search:
        q = q.filter(
            Player.name.ilike(f"%{search}%") |
            Player.nationality.ilike(f"%{search}%")
        )

    players = q.order_by(Player.nationality, Player.position, Player.name).all()
    if not players:
        # Fallback : déclencher scraping si BDD vide
        return JSONResponse(
            status_code=200,
            content={
                "data": [],
                "message": "Effectifs en cours de chargement via l'IA. Revenez dans 30-60s.",
                "count": 0,
            },
        )
    return [_player_to_dict(p) for p in players]


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — ENTRAÎNEURS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/coaches")
async def get_coaches(db: Session = Depends(get_db_session)):
    coaches = db.query(Coach).filter(Coach.is_confirmed == True).all()
    if not coaches:
        return JSONResponse(
            status_code=200,
            content={
                "data": [],
                "message": "Entraîneurs en cours de chargement via l'IA. Revenez dans 30-60s.",
                "count": 0,
            },
        )
    return [_coach_to_dict(c) for c in coaches]


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — MATCHS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/matches")
async def get_matches(db: Session = Depends(get_db_session)):
    # Priorité 1 : données en mémoire (scraping récent)
    if UPDATER_AVAILABLE:
        mem = get_matchs_actuels()
        if mem:
            return mem

    # Priorité 2 : base de données
    try:
        rows = db.execute(text("""
            SELECT match_id, home, away, match_group, round, match_date,
                   venue, home_score, away_score, status, is_finished,
                   is_locked, player_stats, display_order
            FROM match_results
            ORDER BY display_order, match_date
        """)).fetchall()
        if rows:
            import json as _json
            result = []
            for r in rows:
                result.append({
                    "id":           r[0],
                    "home":         r[1],
                    "away":         r[2],
                    "group":        r[3],
                    "round":        r[4],
                    "date":         r[5],
                    "venue":        r[6],
                    "home_score":   r[7],
                    "away_score":   r[8],
                    "status":       r[9],
                    "is_finished":  bool(r[10]),
                    "is_locked":    bool(r[11]),
                    "player_stats": _json.loads(r[12] or "[]"),
                    "display_order": r[13] or 0,
                })
            return result
    except Exception:
        pass

    # Priorité 3 : données ORM
    matches = db.query(MatchResult).order_by(MatchResult.date).all()
    if matches:
        return [_match_to_dict(m) for m in matches]

    return []


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — EQUIPES NATIONALES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/teams")
async def get_teams(db: Session = Depends(get_db_session)):
    teams = db.query(TeamNation).all()
    return [
        {
            "id":           t.id,
            "name":         t.name,
            "group":        t.group,
            "squad_status": t.squad_status,
            "is_locked":    t.is_locked,
            "coach_name":   t.coach_name,
        }
        for t in teams
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — CLASSEMENTS GROUPES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/standings")
async def get_standings(db: Session = Depends(get_db_session)):
    try:
        rows = db.execute(text("""
            SELECT group_name, team, points, played, wins, draws, losses,
                   goals_for, goals_against, goal_diff, qualified
            FROM group_standings
            ORDER BY group_name, points DESC, goal_diff DESC
        """)).fetchall()
        result: dict = {}
        for r in rows:
            g = r[0]
            if g not in result:
                result[g] = []
            result[g].append({
                "team":           r[1], "points":        r[2],
                "played":         r[3], "won":           r[4],
                "drawn":          r[5], "lost":          r[6],
                "goals_for":      r[7], "goals_against": r[8],
                "goal_diff":      r[9], "qualified":     bool(r[10]),
            })
        return result
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — FANTASY ROSTER
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/fantasy/roster")
async def save_roster(
    req: RosterSaveRequest,
    db: Session = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if not current_user:
        raise HTTPException(401, "Connexion requise pour sauvegarder l'équipe.")
    if len(req.player_ids) != 15:
        raise HTTPException(400, f"Il faut exactement 15 joueurs (reçu {len(req.player_ids)}).")

    # Récupérer les joueurs
    players = db.query(Player).filter(Player.id.in_(req.player_ids)).all()
    if len(players) != 15:
        raise HTTPException(400, "Certains joueurs sont introuvables.")

    # Vérification : max 3 joueurs par nationalité
    from collections import Counter
    nat_counts = Counter(p.nationality for p in players)
    for nat, count in nat_counts.items():
        if count > 3:
            raise HTTPException(400, f"Max 3 joueurs par nation ({nat}: {count}).")

    # Vérification entraîneur
    coach: Optional[Coach] = None
    if req.coach_id:
        coach = db.query(Coach).filter(Coach.id == req.coach_id).first()
        if not coach:
            raise HTTPException(400, "Entraîneur introuvable.")
        from app.models import Player as P
        player_nats = {(p.nationality or "").lower() for p in players}
        if (coach.nationality or "").lower() in player_nats:
            raise HTTPException(
                400,
                f"L'entraîneur ({coach.nationality}) ne peut pas avoir de joueurs de sa nationalité dans l'effectif."
            )

    # Upsert du roster
    roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == current_user.id).first()
    if not roster:
        roster = FantasyRoster(user_id=current_user.id)
        db.add(roster)

    roster.players          = players
    roster.coach_id         = req.coach_id
    roster.current_formation = req.formation
    roster.remaining_budget  = req.remaining_budget

    db.commit()
    db.refresh(roster)

    return {
        "status":           "ok",
        "message":          "Équipe sauvegardée.",
        "remaining_budget": roster.remaining_budget,
    }


@app.get("/api/fantasy/roster")
async def get_roster(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == current_user.id).first()
    if not roster:
        return {"players": [], "coach": None, "formation": "4-3-3", "remaining_budget": 100.0}

    return {
        "players":          [_player_to_dict(p) for p in roster.players],
        "coach":            _coach_to_dict(roster.coach) if roster.coach else None,
        "formation":        roster.current_formation or "4-3-3",
        "remaining_budget": roster.remaining_budget or 100.0,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — PRÉDICTIONS SCORES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/predictions/score")
async def save_prediction_score(
    req: PredictionScoreRequest,
    db: Session = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if not current_user:
        raise HTTPException(401, "Connexion requise.")

    # Vérifier que le match n'est pas verrouillé
    try:
        row = db.execute(
            text("SELECT is_locked FROM match_results WHERE match_id = :mid"),
            {"mid": str(req.match_id)},
        ).first()
        if row and row[0]:
            raise HTTPException(403, "Ce match est verrouillé.")
    except HTTPException:
        raise
    except Exception:
        pass

    existing = db.query(PredictionScore).filter(
        PredictionScore.user_id == current_user.id,
        PredictionScore.match_id == str(req.match_id),
    ).first()

    if existing:
        if existing.is_locked:
            raise HTTPException(403, "Pronostic verrouillé.")
        existing.predicted_home_score = req.predicted_home
        existing.predicted_away_score = req.predicted_away
    else:
        pred = PredictionScore(
            user_id=current_user.id,
            match_id=str(req.match_id),
            predicted_home_score=req.predicted_home,
            predicted_away_score=req.predicted_away,
            points_earned=0,
        )
        db.add(pred)

    db.commit()
    return {"status": "ok", "message": "Pronostic sauvegardé."}


@app.get("/api/predictions/scores")
async def get_my_predictions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    preds = db.query(PredictionScore).filter(
        PredictionScore.user_id == current_user.id
    ).all()
    return [
        {
            "match_id":    p.match_id,
            "home":        p.predicted_home_score,
            "away":        p.predicted_away_score,
            "points":      p.points_earned or 0,
            "is_locked":   p.is_locked or False,
        }
        for p in preds
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — BRACKET
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/predictions/bracket")
async def save_bracket(
    req: BracketSaveRequest,
    db: Session = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if not current_user:
        raise HTTPException(401, "Connexion requise.")

    existing = db.query(PredictionTableau).filter(
        PredictionTableau.user_id == current_user.id
    ).first()

    if existing:
        existing.bracket_data = req.bracket_data
    else:
        bracket = PredictionTableau(
            user_id=current_user.id,
            bracket_data=req.bracket_data,
            points_earned=0,
        )
        db.add(bracket)

    db.commit()
    return {"status": "ok", "message": "Tableau sauvegardé."}


@app.get("/api/predictions/bracket")
async def get_bracket(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    bracket = db.query(PredictionTableau).filter(
        PredictionTableau.user_id == current_user.id
    ).first()
    return {"bracket_data": bracket.bracket_data if bracket else {}}


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — ANNEXES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/predictions/annexes")
async def save_annexes(
    req: AnnexesSaveRequest,
    db: Session = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if not current_user:
        raise HTTPException(401, "Connexion requise.")

    existing = db.query(PredictionAnnexes).filter(
        PredictionAnnexes.user_id == current_user.id
    ).first()

    if existing:
        existing.annexes_data = req.annexes
    else:
        ann = PredictionAnnexes(
            user_id=current_user.id,
            annexes_data=req.annexes,
            points_earned=0,
        )
        db.add(ann)

    db.commit()
    return {"status": "ok", "message": "Annexes sauvegardées."}


@app.get("/api/predictions/annexes")
async def get_annexes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    ann = db.query(PredictionAnnexes).filter(
        PredictionAnnexes.user_id == current_user.id
    ).first()
    return {"annexes": ann.annexes_data if ann else {}}


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — LEADERBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/leaderboard")
async def get_leaderboard(db: Session = Depends(get_db_session)):
    users = db.query(User).all()
    result = sorted([_user_to_dict(u) for u in users], key=lambda x: x["total"], reverse=True)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — LIGUES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/leagues")
async def create_league(
    req: LeagueCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    invite_code = secrets.token_hex(4).upper()
    league = League(
        name=req.name,
        invite_code=invite_code,
        created_by=current_user.id,
        is_public=req.is_public,
        max_members=req.max_members,
        created_at=datetime.utcnow().isoformat(),
    )
    if req.password:
        league.password_hash = hash_password(req.password)

    db.add(league)
    db.flush()
    league.members.append(current_user)
    db.commit()
    db.refresh(league)

    return {
        "id":          league.id,
        "name":        league.name,
        "invite_code": league.invite_code,
        "is_public":   league.is_public,
    }


@app.post("/api/leagues/join")
async def join_league(
    req: LeagueJoinRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    league = db.query(League).filter(League.invite_code == req.invite_code.upper()).first()
    if not league:
        raise HTTPException(404, "Ligue introuvable avec ce code.")
    if current_user in league.members:
        raise HTTPException(400, "Vous êtes déjà membre de cette ligue.")
    if len(league.members) >= (league.max_members or 20):
        raise HTTPException(400, "Cette ligue est complète.")
    if league.password_hash and req.password:
        if not verify_password(req.password, league.password_hash):
            raise HTTPException(401, "Mot de passe incorrect.")
    elif league.password_hash and not req.password:
        raise HTTPException(401, "Mot de passe requis.")

    league.members.append(current_user)
    db.commit()
    return {"status": "ok", "message": f"Vous avez rejoint « {league.name} »."}


@app.get("/api/leagues/my")
async def my_leagues(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    return [
        {
            "id":           lg.id,
            "name":         lg.name,
            "invite_code":  lg.invite_code,
            "member_count": len(lg.members),
            "is_public":    lg.is_public,
        }
        for lg in current_user.leagues
    ]


@app.get("/api/leagues/{league_id}/ranking")
async def league_ranking(
    league_id: int,
    db: Session = Depends(get_db_session),
):
    league = db.query(League).filter(League.id == league_id).first()
    if not league:
        raise HTTPException(404, "Ligue introuvable.")
    members = sorted([_user_to_dict(u) for u in league.members], key=lambda x: x["total"], reverse=True)
    return {"league": {"id": league.id, "name": league.name}, "ranking": members}


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — PLAINTES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/complaints")
async def create_complaint(
    req: ComplaintCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    complaint = Complaint(
        user_id=current_user.id,
        category=req.category,
        priority=req.priority,
        title=req.title[:80],
        description=req.description,
        match_id=req.match_id,
        player_id=req.player_id,
        stat_claimed=req.stat_claimed,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    # Analyse IA optionnelle
    if UPDATER_AVAILABLE:
        try:
            from app.updater import analyser_plainte
            analysis = await analyser_plainte(
                str(complaint.id), req.title, req.description
            )
            if analysis:
                complaint.ai_analysis = analysis.get("reasoning", "")
                complaint.ai_verdict  = analysis.get("verdict", "")
                complaint.ai_confidence = int(analysis.get("confidence", 0))
                db.commit()
        except Exception:
            pass

    return {
        "id":     complaint.id,
        "status": complaint.status,
        "ai_verdict": complaint.ai_verdict,
    }


@app.get("/api/complaints/my")
async def my_complaints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    complaints = db.query(Complaint).filter(
        Complaint.user_id == current_user.id
    ).order_by(Complaint.created_at.desc()).all()

    return [
        {
            "id":            c.id,
            "category":      c.category,
            "priority":      c.priority,
            "title":         c.title,
            "status":        c.status,
            "ai_verdict":    c.ai_verdict,
            "ai_confidence": c.ai_confidence,
            "admin_note":    c.admin_note,
            "created_at":    c.created_at.isoformat() if c.created_at else None,
            "resolved_at":   c.resolved_at.isoformat() if c.resolved_at else None,
        }
        for c in complaints
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — SCRAPING FORCÉ (admin uniquement)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/admin/force-scraping")
async def force_scraping(authorization: Optional[str] = Header(None)):
    # Vérification token admin
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(401, "Token admin requis.")

    if ADMIN_AVAILABLE:
        from app.admin_auth import verify_admin_token
        payload = verify_admin_token(token)
        if not payload:
            raise HTTPException(401, "Token admin invalide.")
    else:
        # Fallback : accepter n'importe quel token valide
        payload = _verify_token(token)
        if not payload:
            raise HTTPException(401, "Token invalide.")

    if not UPDATER_AVAILABLE:
        raise HTTPException(503, "Updater non disponible.")

    db = SessionLocal()
    try:
        from app.updater import _executer_sync_officielle  # type: ignore
        stats = await _executer_sync_officielle(db)
        return {"status": "ok", "message": "Scraping terminé.", **stats}
    except Exception as exc:
        raise HTTPException(500, f"Erreur scraping : {exc}")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
#  GESTIONNAIRE D'ERREURS GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Erreur non gérée : %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur.", "error": str(exc)},
    )