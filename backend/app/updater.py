"""
Orchestrateur de synchronisation officielle.

Chaque appel de sync_au_login execute une synchronisation fraiche des sources
FIFA/Olympics. Aucune donnee sportive locale n'est utilisee comme fallback:
si une source ne confirme pas une information, elle n'est pas creee.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.database import SessionLocal
from app.models import Coach, FantasyRoster, Player, PredictionScore, TeamNation, User
from app.rules_engine import calculer_points_pronostic_score
from app.scraper import scraping_complet

logger = logging.getLogger("fantasy_updater")

_scheduler: AsyncIOScheduler | None = None
_sync_lock = asyncio.Lock()
_derniere_mise_a_jour: str | None = None
_matchs_en_memoire: list[dict[str, Any]] = []
_classements_en_memoire: dict[str, list[dict[str, Any]]] = {}
_statistiques_derniere_sync: dict[str, Any] = {
    "matchs_scraped": 0,
    "joueurs_recalcules": 0,
    "effectifs_nouveaux": 0,
    "timestamp": None,
    "erreurs": [],
}


def _utc_now() -> str:
    return datetime.utcnow().isoformat()


def _ensure_runtime_tables(db) -> None:
    """Cree les tables dynamiques qui stockent les faits officiels scrapes."""
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS match_results (
                match_id TEXT PRIMARY KEY,
                display_order INTEGER,
                home TEXT NOT NULL,
                away TEXT NOT NULL,
                match_group TEXT,
                match_date TEXT,
                home_score INTEGER,
                away_score INTEGER,
                status TEXT,
                is_finished INTEGER DEFAULT 0,
                is_locked INTEGER DEFAULT 0,
                qualified_teams TEXT,
                last_updated TEXT NOT NULL
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS group_standings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL,
                team TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                goals_for INTEGER DEFAULT 0,
                goals_against INTEGER DEFAULT 0,
                goal_diff INTEGER DEFAULT 0,
                qualified INTEGER DEFAULT 0,
                last_updated TEXT NOT NULL,
                UNIQUE(group_name, team)
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS source_syncs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
    )
    db.commit()


def _normalize(value: str | None) -> str:
    import re
    import unicodedata

    raw = (value or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_value = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_value = re.sub(r"[^a-z0-9]+", " ", ascii_value).strip()
    aliases = {
        "usa": "etats unis",
        "united states": "etats unis",
        "francaise": "france",
        "francais": "france",
        "bresilienne": "bresil",
        "bresilien": "bresil",
        "anglaise": "angleterre",
        "anglais": "angleterre",
        "espagnole": "espagne",
        "espagnol": "espagne",
        "algerienne": "algerie",
        "algerien": "algerie",
        "marocaine": "maroc",
        "marocain": "maroc",
        "senegalaise": "senegal",
        "senegalais": "senegal",
    }
    return aliases.get(ascii_value, ascii_value)


def _sync_matchs_en_db(matchs: list[dict[str, Any]], db) -> int:
    """Persiste les matchs visibles sur FIFA."""
    import json

    _ensure_runtime_tables(db)
    updated = 0
    now = _utc_now()
    for match in matchs:
        if not match.get("home") or not match.get("away"):
            continue
        db.execute(
            text(
                """
                INSERT INTO match_results (
                    match_id, display_order, home, away, match_group, match_date,
                    home_score, away_score, status, is_finished, is_locked,
                    qualified_teams, last_updated
                )
                VALUES (
                    :match_id, :display_order, :home, :away, :match_group, :match_date,
                    :home_score, :away_score, :status, :is_finished, :is_locked,
                    :qualified_teams, :last_updated
                )
                ON CONFLICT(match_id) DO UPDATE SET
                    display_order=excluded.display_order,
                    home=excluded.home,
                    away=excluded.away,
                    match_group=excluded.match_group,
                    match_date=excluded.match_date,
                    home_score=excluded.home_score,
                    away_score=excluded.away_score,
                    status=excluded.status,
                    is_finished=excluded.is_finished,
                    is_locked=excluded.is_locked,
                    qualified_teams=excluded.qualified_teams,
                    last_updated=excluded.last_updated
                """
            ),
            {
                "match_id": str(match.get("id")),
                "display_order": match.get("order") or 0,
                "home": match["home"],
                "away": match["away"],
                "match_group": match.get("group"),
                "match_date": match.get("date"),
                "home_score": match.get("home_score"),
                "away_score": match.get("away_score"),
                "status": match.get("status") or "unknown",
                "is_finished": 1 if match.get("is_finished") else 0,
                "is_locked": 1 if match.get("is_locked") else 0,
                "qualified_teams": json.dumps(match.get("qualified_teams") or [], ensure_ascii=False),
                "last_updated": now,
            },
        )
        updated += 1
    db.commit()
    return updated


def _sync_classements_en_db(classements: dict[str, list[dict[str, Any]]], db) -> int:
    """Persiste les classements officiels FIFA."""
    _ensure_runtime_tables(db)
    updated = 0
    now = _utc_now()
    for group_name, rows in (classements or {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            team = row.get("equipe") or row.get("team")
            if not team:
                continue
            db.execute(
                text(
                    """
                    INSERT INTO group_standings (
                        group_name, team, points, played, wins, draws, losses,
                        goals_for, goals_against, goal_diff, qualified, last_updated
                    )
                    VALUES (
                        :group_name, :team, :points, :played, :wins, :draws, :losses,
                        :goals_for, :goals_against, :goal_diff, :qualified, :last_updated
                    )
                    ON CONFLICT(group_name, team) DO UPDATE SET
                        points=excluded.points,
                        played=excluded.played,
                        wins=excluded.wins,
                        draws=excluded.draws,
                        losses=excluded.losses,
                        goals_for=excluded.goals_for,
                        goals_against=excluded.goals_against,
                        goal_diff=excluded.goal_diff,
                        qualified=excluded.qualified,
                        last_updated=excluded.last_updated
                    """
                ),
                {
                    "group_name": group_name,
                    "team": team,
                    "points": row.get("points") or 0,
                    "played": row.get("joues") or row.get("played") or 0,
                    "wins": row.get("gagnes") or row.get("wins") or 0,
                    "draws": row.get("nuls") or row.get("draws") or 0,
                    "losses": row.get("perdus") or row.get("losses") or 0,
                    "goals_for": row.get("buts_pour") or row.get("goals_for") or 0,
                    "goals_against": row.get("buts_contre") or row.get("goals_against") or 0,
                    "goal_diff": row.get("diff") or row.get("goal_diff") or 0,
                    "qualified": 1 if row.get("qualified") else 0,
                    "last_updated": now,
                },
            )
            updated += 1
    db.commit()
    return updated


def _nations_officielles(matchs: list[dict[str, Any]], classements: dict[str, list[dict[str, Any]]]) -> set[str]:
    """Construit la liste des nations visibles sur FIFA pour appliquer le verrou."""
    nations: set[str] = set()
    for match in matchs:
        for key in ("home", "away"):
            if match.get(key):
                nations.add(match[key])
        for team in match.get("qualified_teams") or []:
            nations.add(team)
    for rows in (classements or {}).values():
        for row in rows:
            team = row.get("equipe") or row.get("team")
            if team:
                nations.add(team)
    return nations


def _sync_effectifs_et_verrous(
    effectifs: list[dict[str, Any]],
    matchs: list[dict[str, Any]],
    classements: dict[str, list[dict[str, Any]]],
    db,
) -> int:
    """
    Deverrouille uniquement les nations avec liste definitive Olympics.
    Les autres nations connues restent verrouillees et sans effectif selectionnable.
    """
    now = _utc_now()
    official_nations = _nations_officielles(matchs, classements)
    published_by_key = {_normalize(e.get("nation")): e for e in effectifs if e.get("is_definitive")}
    all_keys = {_normalize(n): n for n in official_nations}
    for effectif in effectifs:
        if effectif.get("nation"):
            all_keys[_normalize(effectif["nation"])] = effectif["nation"]

    for nation_key, nation_name in all_keys.items():
        team = db.query(TeamNation).filter(TeamNation.name == nation_name).first()
        if not team:
            team = TeamNation(name=nation_name, group=None)
            db.add(team)
        team.squad_status = "definitive" if nation_key in published_by_key else "locked"
        team.last_updated = now

    players = db.query(Player).all()
    for player in players:
        if _normalize(player.nationality) not in published_by_key:
            db.delete(player)

    coaches = db.query(Coach).all()
    for coach in coaches:
        if _normalize(coach.nationality) not in published_by_key:
            db.delete(coach)

    inserted_or_updated = 0
    for effectif in published_by_key.values():
        nation = effectif["nation"]
        for joueur in effectif.get("joueurs", []):
            existing = (
                db.query(Player)
                .filter(Player.name == joueur["name"], Player.nationality == nation)
                .first()
            )
            if not existing:
                existing = Player(name=joueur["name"], nationality=nation)
                db.add(existing)
            existing.position = joueur.get("position") or "M"
            existing.price = joueur.get("price") or 6.0
            existing.is_confirmed = True
            existing.goals = existing.goals or 0
            existing.assists = existing.assists or 0
            existing.points_total = existing.points_total or 0
            inserted_or_updated += 1

        entraineur = (effectif.get("entraineur") or "").strip()
        if entraineur:
            coach = db.query(Coach).filter(Coach.name == entraineur, Coach.nationality == nation).first()
            if not coach:
                coach = Coach(name=entraineur, nationality=nation)
                db.add(coach)
            coach.price = coach.price or 5.0
            coach.is_confirmed = True
            coach.status = "present"

    db.commit()
    return inserted_or_updated


def _recalculer_points_tous_utilisateurs(db, matchs_termines: list[dict[str, Any]]) -> int:
    """Recalcule fantasy et pronostics a partir des faits reels disponibles."""
    matchs_index = {
        str(m["id"]): m
        for m in matchs_termines
        if m.get("is_finished") and m.get("home_score") is not None and m.get("away_score") is not None
    }
    updated = 0
    for user in db.query(User).all():
        roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
        fantasy_pts = 0
        if roster:
            fantasy_pts = sum((p.points_total or 0) for p in roster.players)
            if roster.coach:
                fantasy_pts += roster.coach.points_total or 0
        user.score_fantasy = fantasy_pts

        prono_pts = 0
        for prono in db.query(PredictionScore).filter(PredictionScore.user_id == user.id).all():
            match = matchs_index.get(str(prono.match_id))
            if match:
                prono.points_earned = calculer_points_pronostic_score(
                    prono.predicted_home_score,
                    prono.predicted_away_score,
                    match["home_score"],
                    match["away_score"],
                )
            prono_pts += prono.points_earned or 0
        user.score_predictor_scores = prono_pts
        updated += 1
    db.commit()
    return updated


async def _executer_sync_officielle(db) -> dict[str, Any]:
    """Execute Playwright + Groq puis applique les resultats a la BDD."""
    global _derniere_mise_a_jour, _matchs_en_memoire, _classements_en_memoire
    global _statistiques_derniere_sync

    debut = time.time()
    resultats = await scraping_complet()
    matchs = resultats.get("matchs", [])
    classements = resultats.get("classements", {})
    effectifs = resultats.get("effectifs", [])

    matchs_db = _sync_matchs_en_db(matchs, db) if matchs else 0
    classements_db = _sync_classements_en_db(classements, db) if classements else 0
    joueurs_db = _sync_effectifs_et_verrous(effectifs, matchs, classements, db)
    users_updated = _recalculer_points_tous_utilisateurs(
        db,
        [m for m in matchs if m.get("is_finished")],
    )

    _matchs_en_memoire = matchs
    _classements_en_memoire = classements
    _derniere_mise_a_jour = _utc_now()
    _statistiques_derniere_sync = {
        "matchs_scraped": len(matchs),
        "matchs_enregistres": matchs_db,
        "classements_enregistres": classements_db,
        "joueurs_recalcules": users_updated,
        "effectifs_nouveaux": len(effectifs),
        "nations_deverrouillees": resultats.get("nations_deverrouillees", []),
        "timestamp": _derniere_mise_a_jour,
        "duration_seconds": round(time.time() - debut, 2),
        "erreurs": [],
    }
    return _statistiques_derniere_sync


async def sync_au_login(user_email: str, db) -> dict[str, Any]:
    """Synchronisation temps reel declenchee par /auth/sync."""
    async with _sync_lock:
        try:
            stats = await _executer_sync_officielle(db)
            user = db.query(User).filter(User.email == user_email).first()
            return {
                **stats,
                "user_id": user.id if user else None,
                "derniere_maj": _derniere_mise_a_jour,
            }
        except Exception as exc:
            logger.exception("Sync officielle au login impossible pour %s", user_email)
            _statistiques_derniere_sync["erreurs"] = [str(exc)]
            return {
                "matchs_scraped": 0,
                "matchs_enregistres": 0,
                "classements_enregistres": 0,
                "joueurs_recalcules": 0,
                "effectifs_nouveaux": 0,
                "pronos_calcules": 0,
                "derniere_maj": _derniere_mise_a_jour,
                "erreurs": [str(exc)],
            }


async def tache_mise_a_jour_quotidienne() -> None:
    """Sync planifiee; elle utilise la meme logique que le login."""
    db = SessionLocal()
    try:
        async with _sync_lock:
            await _executer_sync_officielle(db)
    finally:
        db.close()


async def startup_handler() -> None:
    """Demarre le scheduler quotidien sans lancer de scraping concurrent au boot."""
    global _scheduler
    if _scheduler:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        tache_mise_a_jour_quotidienne,
        trigger=CronTrigger(hour=6, minute=0),
        id="maj_officielle_wc2026",
        name="Synchronisation officielle WC 2026",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()


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
        _scheduler.shutdown(wait=False)


def get_scheduler_status() -> dict[str, Any]:
    return {
        **_statistiques_derniere_sync,
        "derniere_mise_a_jour": _derniere_mise_a_jour,
        "scheduler_actif": _scheduler is not None,
        "available": True,
    }


def get_matchs_actuels() -> list[dict[str, Any]]:
    return _matchs_en_memoire


def get_stats_sync() -> dict[str, Any]:
    return get_scheduler_status()
