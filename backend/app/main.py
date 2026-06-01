"""
main.py — Application FastAPI Fantasy Boulzazen WC 2026
========================================================
Routes principales + intégration admin panel
"""

import logging
import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

import jwt
from sqlalchemy import text

# ────────────────────────────────────────────────────────────────────────
#  Imports internes
# ────────────────────────────────────────────────────────────────────────

try:
    from app.db import SessionLocal, engine, Base
    from app.models import (
        User, League, TeamNation, Player, Coach, MatchResult,
        GroupStanding, FantasyRoster, PredictionScore,
        PredictionTableau, PredictionAnnexes, Complaint
    )
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

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
JWT_SECRET = os.getenv("JWT_SECRET", "fantasy-secret-2026")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ────────────────────────────────────────────────────────────────────────
#  Événements Lifespan
# ────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup et shutdown events."""
    # ──── STARTUP ────
    logger.info("🚀 Fantasy Boulzazen WC 2026 — Démarrage...")

    # Créer les tables
    if DB_AVAILABLE and MODELS_AVAILABLE:
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Base de données initialisée")
        except Exception as e:
            logger.error(f"❌ DB init erreur : {e}")

    # Vérifier Groq
    groq_ok = await _verifier_groq()

    # Démarrer le scheduler si disponible
    if UPDATER_AVAILABLE:
        try:
            start_scheduler()
            logger.info("✅ Scheduler démarré")
        except Exception as e:
            logger.error(f"❌ Scheduler erreur : {e}")

    # Scraping initial si DB vide
    if groq_ok and DB_AVAILABLE:
        try:
            db = SessionLocal()
            count = db.execute(text("SELECT COUNT(*) FROM match_results")).scalar()
            if count == 0:
                logger.info("🔄 DB vide + Groq disponible → scraping initial...")
                asyncio.create_task(_scraping_initial())
            db.close()
        except Exception:
            pass

    logger.info(
        f"✨ Fantasy Boulzazen démarré | "
        f"DB={DB_AVAILABLE} | Groq={'✅' if groq_ok else '❌'} | "
        f"Admin={ADMIN_AVAILABLE} | Updater={UPDATER_AVAILABLE}"
    )

    yield  # Application tourne ici

    # ──── SHUTDOWN ────
    logger.info("🛑 Arrêt de l'application...")


# ────────────────────────────────────────────────────────────────────────
#  Vérification Groq
# ────────────────────────────────────────────────────────────────────────

async def _verifier_groq() -> bool:
    """Vérifie que la clé Groq est valide et que le modèle répond."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        logger.warning(
            "⚠️  GROQ_API_KEY manquante dans .env — "
            "le scraping automatique est désactivé. "
            "Ajoutez GROQ_API_KEY=gsk_... dans backend/.env"
        )
        return False
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": "Réponds juste: OK"}],
            max_tokens=5,
        )
        if resp.choices[0].message.content.strip():
            logger.info("✅ Groq API opérationnelle")
            return True
    except Exception as e:
        logger.error(f"❌ Groq API erreur : {e}")
    return False


async def _scraping_initial():
    """Scraping différé de 5s pour laisser le serveur démarrer."""
    await asyncio.sleep(5)
    if UPDATER_AVAILABLE:
        try:
            await tache_mise_a_jour_quotidienne()
        except Exception as e:
            logger.error(f"Scraping initial erreur : {e}")


# ────────────────────────────────────────────────────────────────────────
#  Initialisation FastAPI
# ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Fantasy Boulzazen WC 2026",
    description="Ligue Fantasy Football + Pronostics CDM 2026",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────────────────────────────────────────────
#  Inclusion des routeurs
# ────────────────────────────────────────────────────────────────────────

if ADMIN_AVAILABLE:
    app.include_router(admin_router)
    logger.info("✅ Admin routes incluses")

# ────────────────────────────────────────────────────────────────────────
#  ROUTES PUBLIQUES — DONNÉES
# ────────────────────────────────────────────────────────────────────────

@app.get("/api/matches")
async def get_matches():
    """Retourne la liste des matchs."""
    # Niveau 1 : mémoire live (scraping récent)
    if UPDATER_AVAILABLE:
        try:
            live = get_matchs_actuels()
            if live:
                return live
        except Exception as e:
            logger.warning(f"get_matchs_actuels erreur : {e}")

    # Niveau 2 : DB
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

    # Niveau 3 : DB vide, scraping en cours
    return {
        "data": [],
        "message": "Données en cours de chargement — scraping Groq en attente",
        "groq_actif": bool(os.getenv("GROQ_API_KEY")),
    }


@app.get("/api/coaches")
async def get_coaches():
    """Retourne la liste des entraîneurs."""
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {
            "data": [],
            "message": "Entraîneurs en cours de chargement depuis Olympics via Groq",
        }
    
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

    return {
        "data": [],
        "message": "Entraîneurs en cours de chargement depuis Olympics via Groq",
    }


@app.get("/api/players")
async def get_players(
    position:    Optional[str]   = None,
    nationality: Optional[str]   = None,
    max_price:   Optional[float] = None,
):
    """Retourne la liste des joueurs avec filtres."""
    if not DB_AVAILABLE or not MODELS_AVAILABLE:
        return {
            "data": [],
            "message": "Joueurs en cours de chargement depuis Olympics via Groq",
        }
    
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
            return {
                "data": [],
                "message": "Joueurs en cours de chargement depuis Olympics via Groq",
            }
        
        return [{
            "id":           p.id,
            "name":         p.name,
            "position":     p.position,
            "nationality":  p.nationality,
            "price":        p.price,
            "club":         p.club,
            "goals":        p.goals,
            "assists":      p.assists,
            "points_total": p.points_total,
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
        return {
            "data": [],
            "message": "Nations en cours de chargement",
        }
    
    db = None
    try:
        db = SessionLocal()
        teams = db.query(TeamNation).all()
        
        return [{
            "id":           t.id,
            "name":         t.name,
            "is_confirmed": t.is_confirmed,
            "is_locked":    getattr(t, 'is_locked', True),
            "flag":         t.flag or "🏴",
        } for t in teams]
    except Exception as e:
        logger.error(f"GET /teams : {e}")
        return {"data": [], "message": str(e)}
    finally:
        if db:
            db.close()


# ────────────────────────────────────────────────────────────────────────
#  ROUTES DE DEBUG / STATUS
# ────────────────────────────────────────────────────────────────────────

@app.get("/api/scraping/status")
async def scraping_status():
    """Retourne l'état du scraping (pour debugging)."""
    status_data = {}
    
    if SCRAPER_AVAILABLE:
        try:
            status_data = get_scraping_status()
        except Exception as e:
            logger.error(f"get_scraping_status erreur : {e}")
    
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
        "sources":         status_data,
        "matchs_memoire":  mem_matchs,
        "matchs_db":       db_matchs,
        "coaches_db":      db_coaches,
        "players_db":      db_players,
        "groq_configure":  bool(os.getenv("GROQ_API_KEY")),
        "groq_installed":  SCRAPER_AVAILABLE,
        "admin_installed": ADMIN_AVAILABLE,
        "updater_installed": UPDATER_AVAILABLE,
    }


@app.post("/api/admin/force-scraping")
async def force_scraping(authorization: Optional[str] = Header(None)):
    """Déclenche immédiatement un scraping complet Groq → DB (admin seulement)."""
    # Vérifier token admin
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token manquant")
    
    token = authorization[7:]
    payload = verify_admin_token(token)
    if not payload:
        raise HTTPException(401, "Token invalide")
    
    if not UPDATER_AVAILABLE:
        raise HTTPException(503, "Updater non disponible")
    
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(400, "GROQ_API_KEY manquante dans .env")
    
    try:
        await tache_mise_a_jour_quotidienne()
        return {"status": "ok", "message": "Scraping lancé avec succès"}
    except Exception as e:
        logger.error(f"Force scraping erreur : {e}")
        raise HTTPException(500, str(e))


@app.get("/api/health")
async def health_check():
    """Health check pour orchestration."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "db": "✅" if DB_AVAILABLE else "❌",
        "admin": "✅" if ADMIN_AVAILABLE else "⚠️",
        "updater": "✅" if UPDATER_AVAILABLE else "⚠️",
    }


# ────────────────────────────────────────────────────────────────────────
#  ROUTES DE TEST / DOCUMENTATION
# ────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Route racine — redirection vers la doc."""
    return {
        "message": "🎮 Fantasy Boulzazen WC 2026",
        "docs": f"{API_BASE}/docs",
        "admin_panel": f"{FRONTEND_URL}/admin",
    }


@app.get("/api/info")
async def api_info():
    """Informations sur l'API."""
    return {
        "app": "Fantasy Boulzazen WC 2026",
        "version": "1.0.0",
        "api_base": API_BASE,
        "frontend_url": FRONTEND_URL,
        "features": {
            "fantasy_league": True,
            "predictions_score": True,
            "predictions_bracket": True,
            "predictions_annexes": True,
            "admin_panel": ADMIN_AVAILABLE,
            "groq_integration": bool(GROQ_API_KEY),
            "automatic_scraping": UPDATER_AVAILABLE,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )