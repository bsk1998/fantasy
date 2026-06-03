"""
supabase_client.py — Client Supabase service-role pour Fantasy Boulzazen
=========================================================================
Toutes les fonctions CRUD vers Supabase.
Le backend utilise la clé SERVICE ROLE → bypass du RLS.
Ne jamais exposer SUPABASE_SERVICE_ROLE_KEY côté frontend.

Variables d'environnement requises :
  SUPABASE_URL              → https://xxxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY → eyJhbGci… (clé service_role, PAS la anon key)
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("supabase_client")

SUPABASE_URL         = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

SUPABASE_AVAILABLE = False
_client = None

try:
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        from supabase import create_client          # type: ignore
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        SUPABASE_AVAILABLE = True
        logger.info("✅ Supabase connecté (%s)", SUPABASE_URL)
    else:
        logger.warning(
            "⚠️  SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant — "
            "toutes les données sont stockées uniquement en SQLite."
        )
except ImportError:
    logger.warning("⚠️  supabase-py non installé : pip install supabase")
except Exception as exc:
    logger.error("❌ Supabase init : %s", exc)


def _sb():
    """Retourne le client ou None."""
    return _client


# ══════════════════════════════════════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════════════════════════════════════

def sb_create_user(sqlite_id: int, email: str, username: str, hashed_password: str) -> Optional[dict]:
    """
    Crée l'utilisateur dans Supabase avec le même id que SQLite.
    Cela garantit que les deux bases restent synchronisées sur le même identifiant.
    """
    if not _client:
        return None
    try:
        res = _client.table("users").insert({
            "id":                       sqlite_id,
            "email":                    email,
            "username":                 username,
            "hashed_password":          hashed_password,
            "score_fantasy":            0,
            "score_predictor_scores":   0,
            "score_predictor_tableaux": 0,
            "score_top_individuel":     0,
        }).execute()
        return res.data[0] if res.data else None
    except Exception as exc:
        logger.error("sb_create_user: %s", exc)
        return None


def sb_get_user_by_email(email: str) -> Optional[dict]:
    if not _client:
        return None
    try:
        res = _client.table("users").select("*").eq("email", email).maybe_single().execute()
        return res.data
    except Exception as exc:
        logger.debug("sb_get_user_by_email (%s): %s", email, exc)
        return None


def sb_get_user_by_id(user_id: int) -> Optional[dict]:
    if not _client:
        return None
    try:
        res = _client.table("users").select("*").eq("id", user_id).maybe_single().execute()
        return res.data
    except Exception as exc:
        logger.error("sb_get_user_by_id: %s", exc)
        return None


def sb_update_scores(user_id: int, scores: dict) -> bool:
    """
    Écrase les scores de l'utilisateur dans Supabase.
    scores = { "score_fantasy": 120, "score_predictor_scores": 45, … }
    """
    if not _client:
        return False
    try:
        _client.table("users").update(scores).eq("id", user_id).execute()
        return True
    except Exception as exc:
        logger.error("sb_update_scores (user_id=%s): %s", user_id, exc)
        return False


def sb_list_users() -> list:
    if not _client:
        return []
    try:
        res = _client.table("users").select(
            "id, username, email, score_fantasy, score_predictor_scores, "
            "score_predictor_tableaux, score_top_individuel"
        ).execute()
        rows = res.data or []
        for u in rows:
            u["total"]   = sum(u.get(k, 0) or 0 for k in (
                "score_fantasy", "score_predictor_scores",
                "score_predictor_tableaux", "score_top_individuel",
            ))
            u["fantasy"] = u.get("score_fantasy", 0) or 0
            u["scores"]  = u.get("score_predictor_scores", 0) or 0
            u["bracket"] = u.get("score_predictor_tableaux", 0) or 0
            u["annexes"] = u.get("score_top_individuel", 0) or 0
        return sorted(rows, key=lambda x: x["total"], reverse=True)
    except Exception as exc:
        logger.error("sb_list_users: %s", exc)
        return []


def sb_delete_user(user_id: int) -> bool:
    if not _client:
        return False
    try:
        _client.table("users").delete().eq("id", user_id).execute()
        return True
    except Exception as exc:
        logger.error("sb_delete_user: %s", exc)
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  LIGUE GÉNÉRALE
# ══════════════════════════════════════════════════════════════════════════════

def sb_get_general_league() -> Optional[dict]:
    if not _client:
        return None
    try:
        res = (
            _client.table("leagues")
            .select("*")
            .eq("name", "Ligue Générale Boulzazen")
            .maybe_single()
            .execute()
        )
        return res.data
    except Exception:
        return None


def sb_get_or_create_general_league() -> Optional[dict]:
    """Crée la Ligue Générale si elle n'existe pas encore."""
    league = sb_get_general_league()
    if league:
        return league
    if not _client:
        return None
    try:
        # Récupérer le prochain id depuis SQLite (simple compteur)
        import time
        league_id = int(time.time()) % 1_000_000  # id unique temporel
        res = _client.table("leagues").insert({
            "id":          league_id,
            "name":        "Ligue Générale Boulzazen",
            "invite_code": secrets.token_hex(4).upper(),
            "is_public":   True,
            "max_members": 9999,
        }).execute()
        created = res.data[0] if res.data else None
        logger.info("✅ Ligue Générale créée dans Supabase (id=%s)", league_id)
        return created
    except Exception as exc:
        logger.error("sb_get_or_create_general_league: %s", exc)
        return None


def sb_add_user_to_general_league(user_id: int) -> bool:
    """
    Ajoute l'utilisateur à la Ligue Générale.
    Appelé automatiquement à l'inscription.
    """
    if not _client:
        return False
    league = sb_get_or_create_general_league()
    if not league:
        logger.warning("sb_add_user_to_general_league: impossible de créer/trouver la ligue")
        return False
    try:
        _client.table("user_leagues").upsert(
            {"user_id": user_id, "league_id": league["id"]},
            on_conflict="user_id,league_id",
        ).execute()
        logger.info("✅ User %s ajouté à la Ligue Générale (Supabase)", user_id)
        return True
    except Exception as exc:
        logger.error("sb_add_user_to_general_league: %s", exc)
        return False


def sb_sync_all_users_to_general_league() -> int:
    """Ajoute TOUS les utilisateurs Supabase à la Ligue Générale."""
    if not _client:
        return 0
    league = sb_get_or_create_general_league()
    if not league:
        return 0
    try:
        users_res = _client.table("users").select("id").execute()
        users = users_res.data or []
        already_res = (
            _client.table("user_leagues")
            .select("user_id")
            .eq("league_id", league["id"])
            .execute()
        )
        already_ids = {r["user_id"] for r in (already_res.data or [])}
        added = 0
        for u in users:
            if u["id"] not in already_ids:
                _client.table("user_leagues").insert({
                    "user_id":   u["id"],
                    "league_id": league["id"],
                }).execute()
                added += 1
        return added
    except Exception as exc:
        logger.error("sb_sync_all_users_to_general_league: %s", exc)
        return 0


# ══════════════════════════════════════════════════════════════════════════════
#  FANTASY ROSTER
# ══════════════════════════════════════════════════════════════════════════════

def sb_save_roster(
    user_id: int,
    player_ids: list,
    coach_id,
    formation: str,
    remaining_budget: float,
) -> bool:
    if not _client:
        return False
    try:
        _client.table("fantasy_rosters").upsert(
            {
                "user_id":          user_id,
                "player_ids":       player_ids,
                "coach_id":         coach_id,
                "formation":        formation,
                "remaining_budget": remaining_budget,
            },
            on_conflict="user_id",
        ).execute()
        return True
    except Exception as exc:
        logger.error("sb_save_roster: %s", exc)
        return False


def sb_get_roster(user_id: int) -> Optional[dict]:
    if not _client:
        return None
    try:
        res = (
            _client.table("fantasy_rosters")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return res.data
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  PRÉDICTIONS
# ══════════════════════════════════════════════════════════════════════════════

def sb_save_prediction_score(user_id: int, match_id: str, home: int, away: int) -> bool:
    if not _client:
        return False
    try:
        _client.table("prediction_scores").upsert(
            {
                "user_id":              user_id,
                "match_id":             match_id,
                "predicted_home_score": home,
                "predicted_away_score": away,
            },
            on_conflict="user_id,match_id",
        ).execute()
        return True
    except Exception as exc:
        logger.error("sb_save_prediction_score: %s", exc)
        return False


def sb_save_bracket(user_id: int, bracket_data: dict) -> bool:
    if not _client:
        return False
    try:
        _client.table("prediction_tableaux").upsert(
            {"user_id": user_id, "bracket_data": bracket_data},
            on_conflict="user_id",
        ).execute()
        return True
    except Exception as exc:
        logger.error("sb_save_bracket: %s", exc)
        return False


def sb_save_annexes(user_id: int, annexes_data: dict) -> bool:
    if not _client:
        return False
    try:
        _client.table("prediction_annexes").upsert(
            {"user_id": user_id, "annexes_data": annexes_data},
            on_conflict="user_id",
        ).execute()
        return True
    except Exception as exc:
        logger.error("sb_save_annexes: %s", exc)
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  APPROBATION RÉSULTATS — Écrase les totaux
# ══════════════════════════════════════════════════════════════════════════════

def sb_save_approved_result(
    match_id: str,
    source_url: str,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    player_stats: list,
) -> bool:
    """Sauvegarde un résultat approuvé par l'admin dans Supabase."""
    if not _client:
        return False
    try:
        _client.table("approved_match_results").upsert(
            {
                "match_id":     match_id,
                "source_url":   source_url,
                "home_team":    home_team,
                "away_team":    away_team,
                "home_score":   home_score,
                "away_score":   away_score,
                "player_stats": player_stats,
            },
            on_conflict="match_id",
        ).execute()
        return True
    except Exception as exc:
        logger.error("sb_save_approved_result: %s", exc)
        return False


def sb_bulk_overwrite_user_scores(user_scores: list[dict]) -> int:
    """
    Écrase les scores Fantasy de plusieurs utilisateurs en une fois.
    user_scores = [{"id": 1, "score_fantasy": 120, ...}, ...]
    Retourne le nombre d'utilisateurs mis à jour.
    """
    if not _client or not user_scores:
        return 0
    updated = 0
    for row in user_scores:
        uid = row.pop("id", None)
        if uid is None:
            continue
        try:
            _client.table("users").update(row).eq("id", uid).execute()
            updated += 1
        except Exception as exc:
            logger.error("sb_bulk_overwrite_user_scores (user %s): %s", uid, exc)
    return updated