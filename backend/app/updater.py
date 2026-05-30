"""
updater.py — Orchestrateur de mises à jour automatiques pour Fantasy Boulzazen WC 2026
v5.1 — Fix : ajout des alias start_scheduler / stop_scheduler / get_scheduler_status
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger("fantasy_updater")

# ── APScheduler ───────────────────────────────────────────────────────────────
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    logger.warning("apscheduler non installé — pip install apscheduler==3.10.4")
    SCHEDULER_AVAILABLE = False

# ── Scraper ───────────────────────────────────────────────────────────────────
try:
    from app.scraper import (scraping_complet, detecter_nouvelles_listes,
                             scraper_effectifs_olympics, convertir_effectif_pour_db,
                             get_all_players_market)
    SCRAPER_AVAILABLE = True
except ImportError:
    try:
        from scraper import (scraping_complet, detecter_nouvelles_listes,
                             scraper_effectifs_olympics, convertir_effectif_pour_db,
                             get_all_players_market)
        SCRAPER_AVAILABLE = True
    except ImportError:
        logger.warning("Module scraper non disponible")
        SCRAPER_AVAILABLE = False

# ── Base de données ───────────────────────────────────────────────────────────
try:
    from app.database import SessionLocal
    from app.models import User, Player, Coach, FantasyRoster, PredictionScore
    DB_AVAILABLE = True
except ImportError:
    try:
        from database import SessionLocal
        from models import User, Player, Coach, FantasyRoster, PredictionScore
        DB_AVAILABLE = True
    except ImportError:
        logger.warning("Base de données non disponible pour updater")
        DB_AVAILABLE = False

# ── Rules engine ──────────────────────────────────────────────────────────────
try:
    from app.rules_engine import calculer_points_pronostic_score
    RULES_AVAILABLE = True
except ImportError:
    try:
        from rules_engine import calculer_points_pronostic_score
        RULES_AVAILABLE = True
    except ImportError:
        RULES_AVAILABLE = False

# ── État global en mémoire ────────────────────────────────────────────────────
_derniere_mise_a_jour: Optional[str] = None
_matchs_en_memoire: list = []
_classements_en_memoire: dict = {}
_statistiques_derniere_sync = {
    "matchs_scraped": 0,
    "joueurs_recalcules": 0,
    "effectifs_nouveaux": 0,
    "timestamp": None,
    "erreurs": [],
}
_scheduler: Optional[any] = None


# ─────────────────────────────────────────────────────────────────────────────
#  SYNC BDD
# ─────────────────────────────────────────────────────────────────────────────

def _sync_matchs_en_db(matchs: list, db) -> int:
    from sqlalchemy import text
    mis_a_jour = 0
    for match in matchs:
        if not match.get("is_finished"):
            continue
        try:
            db.execute(
                text("""
                    INSERT OR REPLACE INTO match_results
                    (match_id, home_score, away_score, is_finished)
                    VALUES (:mid, :hs, :as, 1)
                """),
                {"mid": match["id"], "hs": match.get("home_score"), "as": match.get("away_score")}
            )
            mis_a_jour += 1
        except Exception:
            pass
    return mis_a_jour


def _sync_effectifs_en_db(effectifs_nouveaux: list, db) -> int:
    inseres = 0
    for effectif in effectifs_nouveaux:
        if not effectif.get("is_definitive"):
            continue
        for joueur_data in effectif.get("joueurs", []):
            try:
                existing = db.query(Player).filter(
                    Player.name == joueur_data["name"],
                    Player.nationality == joueur_data["nationality"],
                ).first()
                if not existing:
                    db.add(Player(
                        name=joueur_data["name"], position=joueur_data["position"],
                        nationality=joueur_data["nationality"], price=joueur_data.get("price", 6.0),
                        is_confirmed=True, goals=0, assists=0, points_total=0,
                    ))
                    inseres += 1
                else:
                    existing.is_confirmed = True
            except Exception as e:
                logger.warning(f"Erreur insertion joueur {joueur_data.get('name')}: {e}")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur commit effectifs : {e}")
    return inseres


# ─────────────────────────────────────────────────────────────────────────────
#  RECALCUL POINTS
# ─────────────────────────────────────────────────────────────────────────────

def _recalculer_points_tous_utilisateurs(db, matchs_termines: list) -> int:
    mis_a_jour = 0
    matchs_index = {
        m["id"]: m for m in matchs_termines
        if m.get("is_finished") and m.get("home_score") is not None
    }
    try:
        users = db.query(User).all()
    except Exception as e:
        logger.error(f"Impossible de récupérer les utilisateurs : {e}")
        return 0

    for user in users:
        try:
            fantasy_pts = 0
            roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
            if roster:
                fantasy_pts = sum((p.points_total or 0) for p in roster.players)
                if roster.coach:
                    fantasy_pts += (roster.coach.points_total or 0)
            user.score_fantasy = fantasy_pts

            pronos = db.query(PredictionScore).filter(PredictionScore.user_id == user.id).all()
            total_pronos_pts = 0
            for prono in pronos:
                match_reel = matchs_index.get(prono.match_id)
                if match_reel and RULES_AVAILABLE:
                    pts = calculer_points_pronostic_score(
                        prono.predicted_home_score, prono.predicted_away_score,
                        match_reel["home_score"], match_reel["away_score"],
                    )
                    if prono.points_earned != pts:
                        prono.points_earned = pts
                total_pronos_pts += (prono.points_earned or 0)
            user.score_predictor_scores = total_pronos_pts
            mis_a_jour += 1
        except Exception as e:
            logger.warning(f"Erreur recalcul user {user.id} : {e}")
            continue

    try:
        db.commit()
        logger.info(f"✅ Recalcul terminé : {mis_a_jour} utilisateurs mis à jour")
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur commit recalcul : {e}")
    return mis_a_jour


# ─────────────────────────────────────────────────────────────────────────────
#  TÂCHE QUOTIDIENNE
# ─────────────────────────────────────────────────────────────────────────────

async def tache_mise_a_jour_quotidienne():
    global _derniere_mise_a_jour, _matchs_en_memoire, _classements_en_memoire
    global _statistiques_derniere_sync

    debut = time.time()
    logger.info(f"🔄 [{datetime.utcnow().isoformat()}] Début mise à jour quotidienne...")
    stats = {
        "matchs_scraped": 0, "joueurs_recalcules": 0,
        "effectifs_nouveaux": 0, "timestamp": datetime.utcnow().isoformat(), "erreurs": [],
    }

    try:
        if SCRAPER_AVAILABLE:
            resultats = await scraping_complet()
            matchs      = resultats.get("matchs", [])
            classements = resultats.get("classements", {})
            effectifs   = resultats.get("effectifs", [])
            resume      = resultats.get("resume", {})
            _matchs_en_memoire    = matchs
            _classements_en_memoire = classements
            stats["matchs_scraped"] = resume.get("matchs_scraped", 0)
            stats["effectifs_nouveaux"] = len(effectifs)
        else:
            matchs = []
            effectifs = []

        if DB_AVAILABLE and matchs:
            db = None
            try:
                db = SessionLocal()
                if effectifs:
                    nb_inseres = _sync_effectifs_en_db(effectifs, db)
                    logger.info(f"📋 {nb_inseres} nouveaux joueurs insérés en BDD")
                matchs_termines = [m for m in matchs if m.get("is_finished")]
                nb_users = _recalculer_points_tous_utilisateurs(db, matchs_termines)
                stats["joueurs_recalcules"] = nb_users
            except Exception as e:
                logger.error(f"❌ Erreur sync BDD : {e}")
                stats["erreurs"].append(str(e))
            finally:
                if db:
                    try: db.close()
                    except Exception: pass

        _derniere_mise_a_jour = datetime.utcnow().isoformat()
        _statistiques_derniere_sync = stats
        duree = round(time.time() - debut, 2)
        logger.info(f"✅ Mise à jour terminée en {duree}s")

    except Exception as e:
        logger.error(f"❌ Erreur fatale tâche quotidienne : {e}")
        stats["erreurs"].append(f"Fatal: {str(e)}")
        _statistiques_derniere_sync = stats


# ─────────────────────────────────────────────────────────────────────────────
#  SYNC AU LOGIN
# ─────────────────────────────────────────────────────────────────────────────

async def sync_au_login(user_email: str, db) -> dict:
    logger.info(f"🔌 Sync login pour : {user_email}")
    matchs_disponibles = _matchs_en_memoire if _matchs_en_memoire else []
    matchs_termines = [m for m in matchs_disponibles if m.get("is_finished")]
    nb_pronos_recalcules = 0

    if DB_AVAILABLE and db:
        try:
            user = db.query(User).filter(User.email == user_email).first()
            if user and matchs_termines:
                nb_pronos_recalcules = _recalculer_points_tous_utilisateurs(db, matchs_termines)
        except Exception as e:
            logger.warning(f"Sync login erreur : {e}")

    return {
        "matchs_en_memoire": len(matchs_disponibles),
        "matchs_termines":   len(matchs_termines),
        "pronos_calcules":   nb_pronos_recalcules,
        "derniere_maj":      _derniere_mise_a_jour,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  LIFECYCLE HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

async def startup_handler():
    global _scheduler
    logger.info("🚀 Démarrage du moteur de mise à jour Fantasy Boulzazen...")
    asyncio.create_task(_premiere_sync())

    if SCHEDULER_AVAILABLE:
        _scheduler = AsyncIOScheduler(timezone="UTC")
        _scheduler.add_job(
            tache_mise_a_jour_quotidienne,
            trigger=CronTrigger(hour=6, minute=0),
            id="maj_quotidienne",
            name="Mise à jour quotidienne WC 2026",
            replace_existing=True,
            max_instances=1,
        )
        _scheduler.start()
        logger.info("✅ Planificateur APScheduler démarré (tâche quotidienne à 06:00 UTC)")
    else:
        logger.warning("⚠️ APScheduler non disponible — installez apscheduler==3.10.4")


async def _premiere_sync():
    await asyncio.sleep(5)
    logger.info("🔄 Première synchronisation de démarrage...")
    try:
        await tache_mise_a_jour_quotidienne()
    except Exception as e:
        logger.error(f"Erreur première sync : {e}")


async def shutdown_handler():
    global _scheduler
    if _scheduler and SCHEDULER_AVAILABLE:
        _scheduler.shutdown(wait=False)
        logger.info("🛑 Planificateur APScheduler arrêté proprement")


# ─────────────────────────────────────────────────────────────────────────────
#  ALIAS PUBLICS — requis par main.py
# ─────────────────────────────────────────────────────────────────────────────

def start_scheduler():
    """Alias synchrone : démarre le scheduler (appelé dans on_startup FastAPI)."""
    loop = None
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Contexte async (normal avec FastAPI) — créer une tâche
            asyncio.ensure_future(startup_handler())
        else:
            loop.run_until_complete(startup_handler())
    except RuntimeError:
        # Pas de boucle active — on crée une nouvelle
        asyncio.run(startup_handler())


def stop_scheduler():
    """Alias synchrone : arrête le scheduler (appelé dans on_shutdown FastAPI)."""
    global _scheduler
    if _scheduler and SCHEDULER_AVAILABLE:
        try:
            _scheduler.shutdown(wait=False)
        except Exception as e:
            logger.warning(f"Erreur arrêt scheduler : {e}")


def get_scheduler_status() -> dict:
    """Retourne l'état courant du scheduler et les stats de la dernière sync."""
    return {
        **_statistiques_derniere_sync,
        "derniere_mise_a_jour": _derniere_mise_a_jour,
        "scheduler_actif": _scheduler is not None and SCHEDULER_AVAILABLE,
        "available": SCHEDULER_AVAILABLE,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  ACCESSEURS MÉMOIRE
# ─────────────────────────────────────────────────────────────────────────────

def get_matchs_actuels() -> list:
    """Retourne les matchs scrappés en mémoire (ou liste vide)."""
    return _matchs_en_memoire if _matchs_en_memoire else []


def get_stats_sync() -> dict:
    """Alias de get_scheduler_status pour compatibilité avec les anciens imports."""
    return get_scheduler_status()