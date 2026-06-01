"""
updater.py — Orchestrateur sync + calcul de points Fantasy Boulzazen WC 2026
=============================================================================
v6.0 — Groq natif, sans Playwright, compatible Render free tier
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.rules_engine import (
    calculer_points_joueur,
    calculer_points_entraineur,
    calculer_points_pronostic_score,
)
from app.scraper import (
    scraping_complet,
    scraper_effectifs_tous,
    auto_fill_equipe,
    analyser_plainte_ia,
    calculer_points_ia as _groq_pts,
)

logger = logging.getLogger("fantasy_updater")

# ── État global ───────────────────────────────────────────────────────────────
_scheduler: Any = None
_sync_lock = asyncio.Lock()
_derniere_maj: str | None = None
_matchs_en_memoire: list[dict] = []
_classements_en_memoire: dict = {}
_stats_derniere_sync: dict = {
    "matchs_scraped": 0,
    "joueurs_recalcules": 0,
    "effectifs_nouveaux": 0,
    "nations_deverrouillees": [],
    "timestamp": None,
    "erreurs": [],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
#  TABLES RUNTIME
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_runtime_tables(db: Session) -> None:
    """Crée les tables dynamiques si elles n'existent pas."""
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS match_results (
            match_id       TEXT PRIMARY KEY,
            display_order  INTEGER DEFAULT 0,
            home           TEXT NOT NULL,
            away           TEXT NOT NULL,
            match_group    TEXT,
            round          TEXT DEFAULT 'group_stage',
            match_date     TEXT,
            venue          TEXT,
            home_score     INTEGER,
            away_score     INTEGER,
            status         TEXT DEFAULT 'scheduled',
            is_finished    INTEGER DEFAULT 0,
            is_locked      INTEGER DEFAULT 0,
            player_stats   TEXT DEFAULT '[]',
            last_updated   TEXT NOT NULL
        )
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS group_standings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name     TEXT NOT NULL,
            team           TEXT NOT NULL,
            points         INTEGER DEFAULT 0,
            played         INTEGER DEFAULT 0,
            wins           INTEGER DEFAULT 0,
            draws          INTEGER DEFAULT 0,
            losses         INTEGER DEFAULT 0,
            goals_for      INTEGER DEFAULT 0,
            goals_against  INTEGER DEFAULT 0,
            goal_diff      INTEGER DEFAULT 0,
            qualified      INTEGER DEFAULT 0,
            last_updated   TEXT NOT NULL,
            UNIQUE(group_name, team)
        )
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event      TEXT NOT NULL,
            details    TEXT,
            created_at TEXT NOT NULL
        )
    """))
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
#  SYNC MATCHS
# ══════════════════════════════════════════════════════════════════════════════

def _sync_matchs(matchs: list[dict], db: Session) -> int:
    """Persist les matchs en BDD (upsert)."""
    import json as _json
    _ensure_runtime_tables(db)
    updated = 0
    now = _utc_now()

    for m in matchs:
        if not m.get("home") or not m.get("away"):
            continue
        player_stats_json = _json.dumps(m.get("player_stats", []), ensure_ascii=False)
        db.execute(text("""
            INSERT INTO match_results
                (match_id, display_order, home, away, match_group, round, match_date,
                 venue, home_score, away_score, status, is_finished, is_locked,
                 player_stats, last_updated)
            VALUES
                (:mid, :ord, :home, :away, :grp, :round, :date,
                 :venue, :hs, :as, :status, :fin, :lock, :stats, :now)
            ON CONFLICT(match_id) DO UPDATE SET
                display_order = excluded.display_order,
                home          = excluded.home,
                away          = excluded.away,
                match_group   = excluded.match_group,
                round         = excluded.round,
                match_date    = excluded.match_date,
                venue         = excluded.venue,
                home_score    = COALESCE(excluded.home_score, match_results.home_score),
                away_score    = COALESCE(excluded.away_score, match_results.away_score),
                status        = excluded.status,
                is_finished   = excluded.is_finished,
                is_locked     = excluded.is_locked,
                player_stats  = CASE
                    WHEN excluded.is_finished = 1 THEN excluded.player_stats
                    ELSE match_results.player_stats
                END,
                last_updated  = excluded.last_updated
        """), {
            "mid":    str(m.get("id", "")),
            "ord":    m.get("display_order", 0) or 0,
            "home":   m["home"],
            "away":   m["away"],
            "grp":    m.get("group"),
            "round":  m.get("round", "group_stage"),
            "date":   m.get("date"),
            "venue":  m.get("venue"),
            "hs":     m.get("home_score"),
            "as_":    m.get("away_score"),
            "status": m.get("status", "scheduled"),
            "fin":    1 if m.get("is_finished") else 0,
            "lock":   1 if m.get("is_locked") else 0,
            "stats":  player_stats_json,
            "now":    now,
        })
        updated += 1

    db.commit()
    return updated


def _sync_classements(classements: dict, db: Session) -> int:
    """Persist les classements de groupes."""
    _ensure_runtime_tables(db)
    updated = 0
    now = _utc_now()

    for group_name, rows in (classements or {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            team = row.get("team") or row.get("equipe")
            if not team:
                continue
            db.execute(text("""
                INSERT INTO group_standings
                    (group_name, team, points, played, wins, draws, losses,
                     goals_for, goals_against, goal_diff, qualified, last_updated)
                VALUES
                    (:gn, :team, :pts, :pld, :w, :d, :l, :gf, :ga, :diff, :qual, :now)
                ON CONFLICT(group_name, team) DO UPDATE SET
                    points        = excluded.points,
                    played        = excluded.played,
                    wins          = excluded.wins,
                    draws         = excluded.draws,
                    losses        = excluded.losses,
                    goals_for     = excluded.goals_for,
                    goals_against = excluded.goals_against,
                    goal_diff     = excluded.goal_diff,
                    qualified     = excluded.qualified,
                    last_updated  = excluded.last_updated
            """), {
                "gn":   group_name,
                "team": team,
                "pts":  row.get("points", 0),
                "pld":  row.get("played", 0),
                "w":    row.get("won") or row.get("wins", 0),
                "d":    row.get("drawn") or row.get("draws", 0),
                "l":    row.get("lost") or row.get("losses", 0),
                "gf":   row.get("goals_for", 0),
                "ga":   row.get("goals_against", 0),
                "diff": row.get("goal_diff", 0),
                "qual": 1 if row.get("qualified") else 0,
                "now":  now,
            })
            updated += 1

    db.commit()
    return updated


# ══════════════════════════════════════════════════════════════════════════════
#  SYNC EFFECTIFS
# ══════════════════════════════════════════════════════════════════════════════

def _sync_effectifs(effectifs: list[dict], db: Session) -> tuple[int, list[str]]:
    """
    Synchronise les effectifs en BDD.
    Retourne (nb_joueurs_insérés, nations_déverrouillées).
    """
    from app.models import Player, Coach, TeamNation

    nations_ok: list[str] = []
    inserted = 0
    now = _utc_now()

    for squad in effectifs:
        nation = squad.get("nation", "").strip()
        if not nation:
            continue

        # Upsert TeamNation
        team = db.query(TeamNation).filter(TeamNation.name == nation).first()
        if not team:
            team = TeamNation(name=nation)
            db.add(team)
        team.squad_status    = squad.get("squad_status", "definitive")
        team.is_locked       = bool(squad.get("is_locked", False))
        team.coach_name      = squad.get("coach_name")
        team.last_updated    = now
        db.flush()

        # Coach
        coach_name = (squad.get("coach_name") or "").strip()
        if coach_name:
            coach = db.query(Coach).filter(
                Coach.name == coach_name,
                Coach.nationality == squad.get("coach_nationality", nation)
            ).first()
            if not coach:
                coach = Coach(
                    name=coach_name,
                    nationality=squad.get("coach_nationality", nation),
                    team_name=nation,
                    price=float(squad.get("coach_price", 5.0)),
                    is_confirmed=True,
                    status="present",
                )
                db.add(coach)

        # Joueurs
        for p_data in squad.get("players", []):
            p_name = (p_data.get("name") or "").strip()
            if not p_name:
                continue

            player = db.query(Player).filter(
                Player.name == p_name,
                Player.nationality == nation
            ).first()

            if not player:
                player = Player(name=p_name, nationality=nation)
                db.add(player)

            player.position     = (p_data.get("position") or "M").upper()
            player.team_id      = team.id
            player.price        = float(p_data.get("price", 6.0))
            player.is_confirmed = True
            player.goals        = player.goals or 0
            player.assists      = player.assists or 0
            player.points_total = player.points_total or 0
            inserted += 1

        if not team.is_locked:
            nations_ok.append(nation)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur commit effectifs : {e}")

    return inserted, nations_ok


# ══════════════════════════════════════════════════════════════════════════════
#  CALCUL POINTS COMPLET
# ══════════════════════════════════════════════════════════════════════════════

def _calculer_points_joueur_depuis_stats(stats: dict, position: str) -> int:
    """Convertit les stats de match en points Fantasy via le moteur local."""
    try:
        result = calculer_points_joueur(
            stats={
                "minutes":     stats.get("minutes_played", 0),
                "buts":        stats.get("goals", 0),
                "passes":      stats.get("assists", 0),
                "clean_sheet": stats.get("clean_sheet", False),
                "parades":     stats.get("saves", 0),
                "recups":      stats.get("ball_recoveries", 0),
                "jaune":       stats.get("yellow_cards", 0),
                "rouge":       stats.get("red_cards", 0),
            },
            position=position,
        )
        return result["total"]
    except Exception:
        return 0


def _calculer_points_coach_depuis_match(
    home_score: int, away_score: int,
    coach_is_home: bool,
    sub_goals: int = 0, sub_assists: int = 0,
) -> int:
    """Calcule les points de l'entraîneur pour un match."""
    try:
        if coach_is_home:
            buts_marques = home_score
            buts_encaisses = away_score
        else:
            buts_marques = away_score
            buts_encaisses = home_score

        is_win  = buts_marques > buts_encaisses
        is_loss = buts_marques < buts_encaisses

        result = calculer_points_entraineur({
            "status":          "present",
            "buts_marques":    buts_marques,
            "buts_encaisses":  buts_encaisses,
            "is_win":          is_win,
            "is_loss":         is_loss,
            "buts_banc":       sub_goals,
            "passes_banc":     sub_assists,
            "jaune": 0, "rouge": 0,
        })
        return result["total"]
    except Exception:
        return 0


async def _recalculer_tous_utilisateurs(db: Session, matchs_termines: list[dict]) -> int:
    """Recalcule les points Fantasy de tous les utilisateurs."""
    from app.models import User, FantasyRoster, Player, Coach, PredictionScore

    matchs_idx = {
        str(m.get("id", "")): m
        for m in matchs_termines
        if m.get("is_finished") and m.get("home_score") is not None
    }

    updated = 0
    for user in db.query(User).all():
        try:
            # Points Fantasy
            roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
            fantasy_pts = 0

            if roster:
                # Recalcul joueurs
                for player in roster.players:
                    total_pts = 0
                    for m in matchs_termines:
                        for ps in m.get("player_stats", []):
                            if _names_match(ps.get("player_name", ""), player.name):
                                pts = _calculer_points_joueur_depuis_stats(ps, player.position or "M")
                                total_pts += pts
                    player.points_total = total_pts
                    fantasy_pts += total_pts

                # Recalcul coach
                if roster.coach:
                    coach = roster.coach
                    coach_pts = 0
                    for m in matchs_termines:
                        h, a = m.get("home", ""), m.get("away", "")
                        hs, ass = m.get("home_score", 0) or 0, m.get("away_score", 0) or 0
                        coach_nat = (coach.nationality or "").lower()
                        if coach_nat in h.lower():
                            coach_pts += _calculer_points_coach_depuis_match(hs, ass, True)
                        elif coach_nat in a.lower():
                            coach_pts += _calculer_points_coach_depuis_match(hs, ass, False)
                    coach.points_total = coach_pts
                    fantasy_pts += coach_pts

            user.score_fantasy = fantasy_pts

            # Points pronostics
            prono_pts = 0
            for prono in db.query(PredictionScore).filter(PredictionScore.user_id == user.id).all():
                m = matchs_idx.get(str(prono.match_id))
                if m:
                    pts = calculer_points_pronostic_score(
                        prono.predicted_home_score,
                        prono.predicted_away_score,
                        m["home_score"],
                        m["away_score"],
                    )
                    prono.points_earned = pts
                prono_pts += prono.points_earned or 0
            user.score_predictor_scores = prono_pts
            updated += 1

        except Exception as e:
            logger.warning(f"Erreur recalcul user {user.id}: {e}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Commit recalcul: {e}")

    return updated


def _names_match(name_a: str, name_b: str) -> bool:
    """Comparaison souple de noms de joueurs."""
    def normalize(n: str) -> str:
        import unicodedata, re
        n = unicodedata.normalize("NFD", n.lower())
        n = "".join(c for c in n if not unicodedata.combining(c))
        return re.sub(r"[^a-z]", "", n)

    a, b = normalize(name_a), normalize(name_b)
    if a == b:
        return True
    # Comparaison par nom de famille
    parts_a = a.split()
    parts_b = b.split()
    if parts_a and parts_b:
        return parts_a[-1] == parts_b[-1] and len(parts_a[-1]) > 3

    return False


# ══════════════════════════════════════════════════════════════════════════════
#  SYNC OFFICIELLE
# ══════════════════════════════════════════════════════════════════════════════

async def _executer_sync_officielle(db: Session) -> dict[str, Any]:
    """Pipeline complet : scraping + BDD + recalcul."""
    global _derniere_maj, _matchs_en_memoire, _classements_en_memoire, _stats_derniere_sync

    debut = time.time()
    erreurs: list[str] = []

    try:
        # 1. Scraping Groq
        resultats = await scraping_complet()
        matchs     = resultats.get("matchs", [])
        classements = resultats.get("classements", {})

        # 2. Effectifs (si BDD vide)
        from app.models import Player
        nb_players = db.query(Player).count()
        effectifs = []
        if nb_players < 100:
            logger.info("🏃 Chargement effectifs (BDD vide)...")
            effectifs = await scraper_effectifs_tous()

        # 3. Sync BDD
        nb_matchs = _sync_matchs(matchs, db) if matchs else 0
        _sync_classements(classements, db)
        nb_joueurs, nations_ok = _sync_effectifs(effectifs, db) if effectifs else (0, [])

        # 4. Recalcul points
        matchs_termines = [m for m in matchs if m.get("is_finished")]
        nb_users = await _recalculer_tous_utilisateurs(db, matchs_termines)

        # 5. Mise à jour état global
        _matchs_en_memoire     = matchs
        _classements_en_memoire = classements
        _derniere_maj = _utc_now()

        _stats_derniere_sync = {
            "matchs_scraped":         len(matchs),
            "matchs_enregistres":     nb_matchs,
            "joueurs_recalcules":     nb_users,
            "effectifs_nouveaux":     nb_joueurs,
            "nations_deverrouillees": nations_ok,
            "timestamp":              _derniere_maj,
            "duration_seconds":       round(time.time() - debut, 2),
            "erreurs":                erreurs,
        }

        logger.info(
            f"✅ Sync OK — {len(matchs)} matchs, {nb_joueurs} joueurs, "
            f"{nb_users} users recalculés en {_stats_derniere_sync['duration_seconds']}s"
        )

    except Exception as e:
        logger.exception("Erreur sync officielle")
        erreurs.append(str(e))
        _stats_derniere_sync["erreurs"] = erreurs

    return _stats_derniere_sync


# ══════════════════════════════════════════════════════════════════════════════
#  API PUBLIQUE
# ══════════════════════════════════════════════════════════════════════════════

async def sync_au_login(user_email: str, db: Session) -> dict[str, Any]:
    """Sync déclenchée au login utilisateur."""
    async with _sync_lock:
        try:
            stats = await _executer_sync_officielle(db)
            from app.models import User
            user = db.query(User).filter(User.email == user_email).first()
            return {
                **stats,
                "user_id":    user.id if user else None,
                "derniere_maj": _derniere_maj,
            }
        except Exception as exc:
            logger.exception("Sync login impossible pour %s", user_email)
            return {
                "matchs_scraped": 0, "joueurs_recalcules": 0,
                "effectifs_nouveaux": 0, "nations_deverrouillees": [],
                "erreurs": [str(exc)], "derniere_maj": _derniere_maj,
            }


async def tache_mise_a_jour_quotidienne() -> None:
    """Tâche planifiée APScheduler."""
    db = SessionLocal()
    try:
        async with _sync_lock:
            await _executer_sync_officielle(db)
    finally:
        db.close()


async def auto_fill_equipe_utilisateur(
    budget: float,
    formation: str,
    db: Session,
) -> Optional[dict]:
    """Auto-fill équipe Fantasy via Groq IA."""
    from app.models import Player, Coach

    players = [
        {"id": p.id, "name": p.name, "position": p.position,
         "nationality": p.nationality, "price": p.price}
        for p in db.query(Player).filter(Player.is_confirmed == True).all()
    ]
    coaches = [
        {"id": c.id, "name": c.name, "nationality": c.nationality, "price": c.price}
        for c in db.query(Coach).filter(Coach.is_confirmed == True).all()
    ]

    return await auto_fill_equipe(budget, formation, players, coaches)


async def analyser_plainte(complaint_id: str, subject: str, description: str) -> Optional[dict]:
    """Analyse une plainte via Groq IA."""
    return await analyser_plainte_ia(complaint_id, subject, description)


# ── Scheduler ─────────────────────────────────────────────────────────────────

async def startup_handler() -> None:
    global _scheduler
    if _scheduler:
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        _scheduler = AsyncIOScheduler(timezone="UTC")
        _scheduler.add_job(
            tache_mise_a_jour_quotidienne,
            trigger=CronTrigger(hour=6, minute=0),
            id="maj_officielle_wc2026",
            max_instances=1,
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("✅ Scheduler APScheduler démarré (06:00 UTC)")
    except ImportError:
        logger.warning("⚠️  apscheduler non installé")


async def shutdown_handler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def start_scheduler() -> None:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(startup_handler())
        else:
            loop.run_until_complete(startup_handler())
    except RuntimeError:
        asyncio.run(startup_handler())


def stop_scheduler() -> None:
    if _scheduler:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass


def get_scheduler_status() -> dict:
    return {
        **_stats_derniere_sync,
        "derniere_mise_a_jour": _derniere_maj,
        "scheduler_actif":      _scheduler is not None,
        "available":            True,
    }


def get_matchs_actuels() -> list[dict]:
    return _matchs_en_memoire


def get_stats_sync() -> dict:
    return get_scheduler_status()