"""
admin_routes.py — Routes d'administration
===========================================
v4.0 — Corrections critiques :
  ✅ /ai/effectif accepte JSON body (texte) ET FormData (image)
     sans conflit de Content-Type
  ✅ /squad/inject reçoit les joueurs en body JSON (liste)
  ✅ Tous les imports présents (Optional, List, Union, etc.)
"""

import logging
import secrets
from fastapi import (
    APIRouter, HTTPException, Header, Depends,
    Query, UploadFile, File, Body, Request,
)
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

from app.admin_auth import verify_admin_credentials, generate_admin_token, verify_admin_token
from app.admin_services import inject_team_nation
from app.models import Player, Coach, TeamNation, MatchResult, User, League
from app.admin_models import AdminLog, AdminGameRule, AdminPricingTemplate
from app.database import SessionLocal

logger = logging.getLogger("admin_routes")

router = APIRouter(tags=["admin"])

# ── Instance IA centralisée ───────────────────────────────────────────────────
try:
    from app.services.ai_service import AIService
    ai_service = AIService()
    AI_ROUTES_AVAILABLE = True
except ImportError as _e:
    AI_ROUTES_AVAILABLE = False
    ai_service = None
    logger.warning("ai_service non disponible : %s", _e)


# ════════════════════════════════════════════════════════════════════
#  MODÈLES PYDANTIC
# ════════════════════════════════════════════════════════════════════

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    message: str

class AIParseResponse(BaseModel):
    status: str
    message: str
    parsed_data: Optional[Dict] = None

class SquadInjectionRequest(BaseModel):
    nation: str
    raw_squad_text: str

class PricingRequest(BaseModel):
    squad_data: Dict[str, Any]

class TournamentInjectionRequest(BaseModel):
    raw_tournament_text: str

class CoachInjectionRequest(BaseModel):
    raw_coach_text: str

class RuleUpdateRequest(BaseModel):
    rule_name: str
    description: str
    position_affected: Optional[str] = None
    points_value: int = 0
    is_active: bool = True

class RulesParseRequest(BaseModel):
    raw_rules_text: str


# ════════════════════════════════════════════════════════════════════
#  DÉPENDANCES
# ════════════════════════════════════════════════════════════════════

async def verify_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant. Format: Bearer <token>")
    token = authorization[7:]
    payload = verify_admin_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    return payload


def _log_action(action: str, target_type: str, target_id: str = None, details: str = None):
    try:
        db = SessionLocal()
        log = AdminLog(
            action=action, target_type=target_type, target_id=target_id,
            details=details, admin_user="admin", created_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Logging erreur : {e}")


# ════════════════════════════════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════════════════════════════════

@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(req: AdminLoginRequest):
    username = req.username.strip()
    if not verify_admin_credentials(username, req.password):
        raise HTTPException(status_code=401, detail="Pseudo ou mot de passe admin incorrect")
    token = generate_admin_token(username)
    _log_action("login", "admin", target_id=username)
    return AdminLoginResponse(access_token=token, message="Connexion admin reussie")


@router.get("/status")
async def admin_status(admin: dict = Depends(verify_admin)):
    return {"status": "authenticated", "user": admin.get("sub"), "type": admin.get("type")}


# ════════════════════════════════════════════════════════════════════
#  GESTION UTILISATEURS
# ════════════════════════════════════════════════════════════════════

@router.get("/users")
async def list_users(admin: dict = Depends(verify_admin)):
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        result = []
        for u in users:
            total = (
                (u.score_fantasy or 0)
                + (u.score_predictor_scores or 0)
                + (u.score_predictor_tableaux or 0)
                + (u.score_top_individuel or 0)
            )
            result.append({
                "id":                        u.id,
                "username":                  u.username or "",
                "email":                     u.email or "",
                "score_fantasy":             u.score_fantasy or 0,
                "score_predictor_scores":    u.score_predictor_scores or 0,
                "score_predictor_tableaux":  u.score_predictor_tableaux or 0,
                "score_top_individuel":      u.score_top_individuel or 0,
                "total":                     total,
            })
        return {"status": "success", "users": result, "count": len(result)}
    except Exception as e:
        logger.error(f"list_users error : {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(verify_admin)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, f"Utilisateur #{user_id} introuvable")
        username = user.username or user.email
        _log_action("user_deleted", "user", target_id=str(user_id), details=username)
        from sqlalchemy import text as sql_text
        for stmt, params in [
            ("DELETE FROM prediction_scores WHERE user_id = :uid",    {"uid": user_id}),
            ("DELETE FROM prediction_tableaux WHERE user_id = :uid",  {"uid": user_id}),
            ("DELETE FROM prediction_annexes WHERE user_id = :uid",   {"uid": user_id}),
            ("DELETE FROM complaints WHERE user_id = :uid",           {"uid": user_id}),
            ("DELETE FROM roster_player WHERE roster_id IN (SELECT id FROM fantasy_rosters WHERE user_id = :uid)", {"uid": user_id}),
            ("DELETE FROM fantasy_rosters WHERE user_id = :uid",      {"uid": user_id}),
            ("DELETE FROM user_league WHERE user_id = :uid",          {"uid": user_id}),
        ]:
            db.execute(sql_text(stmt), params)
        db.delete(user)
        db.commit()
        return {"status": "success", "message": f"✅ Compte {username} supprimé définitivement."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"delete_user error : {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════
#  LIGUE GÉNÉRALE
# ════════════════════════════════════════════════════════════════════

@router.post("/leagues/general")
async def create_general_league(admin: dict = Depends(verify_admin)):
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.name == "Ligue Générale Boulzazen").first()
        if not league:
            invite_code = secrets.token_hex(4).upper()
            league = League(
                name="Ligue Générale Boulzazen",
                invite_code=invite_code,
                is_public=True,
                max_members=9999,
                created_at=datetime.utcnow().isoformat(),
            )
            db.add(league)
            db.flush()
        all_users = db.query(User).all()
        already_member_ids = {u.id for u in league.members}
        added = 0
        for u in all_users:
            if u.id not in already_member_ids:
                league.members.append(u)
                added += 1
        db.commit()
        db.refresh(league)
        _log_action("general_league_created", "league", target_id=str(league.id),
                    details=f"{len(league.members)} membres")
        return {
            "status":       "success",
            "message":      f"✅ Ligue Générale créée/mise à jour — {len(league.members)} membres, {added} ajoutés.",
            "league_id":    league.id,
            "invite_code":  league.invite_code,
            "member_count": len(league.members),
        }
    except Exception as e:
        db.rollback()
        logger.error(f"create_general_league error : {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.get("/leagues/general")
async def get_general_league_ranking(admin: dict = Depends(verify_admin)):
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.name == "Ligue Générale Boulzazen").first()
        if not league:
            return {"status": "not_found", "message": "La Ligue Générale n'existe pas encore.", "members": []}

        members_data = []
        for u in league.members:
            fantasy  = u.score_fantasy or 0
            scores   = u.score_predictor_scores or 0
            bracket  = u.score_predictor_tableaux or 0
            annexes  = u.score_top_individuel or 0
            total    = fantasy + scores + bracket + annexes
            members_data.append({
                "id": u.id, "username": u.username or u.email, "email": u.email,
                "fantasy": fantasy, "scores": scores, "bracket": bracket,
                "annexes": annexes, "total": total,
            })

        def ranked(entries, key):
            sorted_entries = sorted(entries, key=lambda x: x[key], reverse=True)
            for i, e in enumerate(sorted_entries):
                e[f"rank_{key}"] = i + 1
            return sorted_entries

        return {
            "status":          "success",
            "league_id":       league.id,
            "invite_code":     league.invite_code,
            "member_count":    len(members_data),
            "global_ranking":  ranked([dict(m) for m in members_data], "total"),
            "fantasy_ranking": ranked([dict(m) for m in members_data], "fantasy"),
            "scores_ranking":  ranked([dict(m) for m in members_data], "scores"),
            "bracket_ranking": ranked([dict(m) for m in members_data], "bracket"),
            "annexes_ranking": ranked([dict(m) for m in members_data], "annexes"),
        }
    except Exception as e:
        logger.error(f"get_general_league_ranking error : {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.post("/leagues/general/sync")
async def sync_general_league(admin: dict = Depends(verify_admin)):
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.name == "Ligue Générale Boulzazen").first()
        if not league:
            raise HTTPException(404, "La Ligue Générale n'existe pas encore.")
        all_users = db.query(User).all()
        already_member_ids = {u.id for u in league.members}
        added = 0
        for u in all_users:
            if u.id not in already_member_ids:
                league.members.append(u)
                added += 1
        db.commit()
        return {"status": "success", "message": f"✅ {added} nouveaux membres ajoutés.", "total": len(league.members)}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════
#  ENDPOINT IA UNIVERSEL — POST /ai/effectif
#  ✅ CORRIGÉ : accepte JSON body (texte) ET multipart/form-data (image)
#               sans forcer Content-Type côté client
# ════════════════════════════════════════════════════════════════════

@router.post("/ai/effectif", response_model=AIParseResponse)
async def ai_effectif(
    request: Request,
    admin: dict = Depends(verify_admin),
):
    """
    Endpoint universel IA — parsing d'effectif.

    Deux modes détectés automatiquement selon Content-Type :

    MODE TEXTE (application/json) :
        Body JSON : {"nation": "France", "raw_text": "Gardien: Mike Maignan..."}

    MODE IMAGE (multipart/form-data) :
        Champs : file=<image>, nation=<string optionnel>

    Pas besoin de spécifier le mode côté client — le backend le détecte seul.
    """
    if not AI_ROUTES_AVAILABLE or ai_service is None:
        raise HTTPException(503, "Moteur IA non disponible.")
    if not (ai_service.groq_configured or ai_service.gemini_configured):
        raise HTTPException(503, "Aucune clé IA configurée (GROQ_API_KEY ou GEMINI_API_KEY dans .env).")

    content_type = request.headers.get("content-type", "")
    raw_input: Optional[Union[str, bytes]] = None
    nation: Optional[str] = None

    # ── Détection automatique du mode ────────────────────────────────────────
    if "multipart/form-data" in content_type:
        # Mode image
        try:
            form = await request.form()
            nation = form.get("nation") or None
            file_obj = form.get("file")
            if file_obj is None:
                raise HTTPException(400, "Champ 'file' manquant dans le FormData.")
            if not hasattr(file_obj, "read"):
                raise HTTPException(400, "Le champ 'file' n'est pas un fichier.")
            ct = getattr(file_obj, "content_type", "") or ""
            if not ct.startswith("image/"):
                raise HTTPException(400, f"Type de fichier non supporté : {ct}. Envoyez une image.")
            raw_input = await file_obj.read()
            logger.info("ai_effectif: mode IMAGE (%d octets, nation=%s)", len(raw_input), nation)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Erreur lecture FormData : {e}")

    elif "application/json" in content_type:
        # Mode texte — body JSON
        try:
            body = await request.json()
            nation    = body.get("nation") or None
            raw_input = (body.get("raw_text") or "").strip()
            if not raw_input:
                raise HTTPException(400, "Champ 'raw_text' manquant ou vide dans le JSON body.")
            logger.info("ai_effectif: mode TEXTE JSON (%d chars, nation=%s)", len(raw_input), nation)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Erreur lecture JSON body : {e}")

    else:
        # Fallback — essayer de lire comme JSON quand même
        try:
            body = await request.json()
            nation    = body.get("nation") or None
            raw_input = (body.get("raw_text") or "").strip()
            if raw_input:
                logger.info("ai_effectif: mode TEXTE fallback (%d chars)", len(raw_input))
            else:
                raise HTTPException(
                    400,
                    "Content-Type non reconnu. Envoyez application/json avec {raw_text} "
                    "ou multipart/form-data avec un champ file."
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                415,
                "Content-Type non supporté. Utilisez application/json (texte) "
                "ou multipart/form-data (image)."
            )

    # ── Appel IA ──────────────────────────────────────────────────────────────
    try:
        parsed_data, msg = await ai_service.parse_squad_list(raw_input)
    except Exception as exc:
        logger.exception("ai_effectif: erreur parse_squad_list")
        raise HTTPException(500, f"Erreur IA : {exc}")

    if not parsed_data:
        _log_action("ai_effectif_parse_failed", "ai_squad", target_id=nation or "N/A", details=msg)
        return AIParseResponse(status="error", message=msg)

    # Forcer la nation si fournie et non détectée par l'IA
    if nation and not parsed_data.get("nation"):
        parsed_data["nation"] = nation

    _log_action("ai_effectif_parse_success", "ai_squad",
                target_id=parsed_data.get("nation", "N/A"), details=msg)
    return AIParseResponse(status="success", message=msg, parsed_data=parsed_data)


# ════════════════════════════════════════════════════════════════════
#  INJECTION EFFECTIFS — POST /squad/inject
#  ✅ CORRIGÉ : reçoit les joueurs en body JSON (List[Dict])
# ════════════════════════════════════════════════════════════════════

@router.post("/squad/inject")
async def inject_squad(
    nation: str = Query(..., description="Nom du pays"),
    coach_name: Optional[str] = Query(None),
    players_data: List[Dict] = Body(..., description="Liste des joueurs"),
    admin: dict = Depends(verify_admin),
):
    """
    Injecte l'effectif d'une nation en base.

    Query params : nation=France&coach_name=Deschamps
    Body JSON    : [{"name": "Mbappé", "position": "A", "price": 14.0}, ...]
    """
    if not nation.strip():
        raise HTTPException(400, "Le nom de la nation est obligatoire.")
    if not players_data or len(players_data) < 3:
        raise HTTPException(400, "Minimum 3 joueurs requis.")

    db = SessionLocal()
    try:
        result = inject_team_nation(db, nation.strip(), coach_name, players_data)
        msg = (
            f"✅ Effectif {nation} injecté : "
            f"{result['players_inserted']} joueurs"
            + (f", entraîneur : {result['coach']}" if result["coach"] else "")
            + f" ({result['players_deleted']} anciens supprimés)"
        )
        _log_action("squad_injected", "team", target_id=nation, details=msg)
        return {"status": "success", "message": msg, **result}
    except Exception as e:
        db.rollback()
        logger.error(f"inject_squad error: {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.get("/squad/filled-nations")
async def get_filled_nations(admin: dict = Depends(verify_admin)):
    db = SessionLocal()
    try:
        filled = []
        nations = db.query(TeamNation).all()
        for nation in nations:
            has_players = db.query(Player).filter(
                Player.nationality == nation.name, Player.is_confirmed == True
            ).first()
            has_coach = db.query(Coach).filter(
                Coach.team_name == nation.name, Coach.is_confirmed == True
            ).first()
            if has_players and has_coach:
                filled.append(nation.name)
        return {"status": "success", "filled_nations": filled}
    except Exception as e:
        logger.error(f"get_filled_nations error: {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.post("/squad/estimate-prices")
async def estimate_prices(req: PricingRequest, admin: dict = Depends(verify_admin)):
    if not ai_service:
        return {"status": "error", "message": "IA non disponible"}
    pricing_result, msg = await ai_service.estimate_player_prices(req.squad_data)
    if not pricing_result:
        _log_action("pricing_failed", "player", details=msg)
        return {"status": "error", "message": msg}
    _log_action("pricing_success", "player", details=msg)
    return {"status": "success", "message": msg, "pricing": pricing_result.get("pricing", [])}


# ════════════════════════════════════════════════════════════════════
#  JOUEURS
# ════════════════════════════════════════════════════════════════════

@router.post("/player/add")
async def add_player(
    name: str = Query(...), position: str = Query(...), nationality: str = Query(...),
    club: str = Query(...), price: float = Query(...), number: Optional[int] = Query(None),
    admin: dict = Depends(verify_admin),
):
    db = SessionLocal()
    try:
        existing = db.query(Player).filter(Player.name == name, Player.nationality == nationality).first()
        if existing:
            return {"status": "warning", "message": f"Joueur {name} existe déjà"}
        player = Player(
            name=name, position=position.upper(), nationality=nationality,
            club=club, price=price, number=number, goals=0, assists=0,
            points_total=0, is_confirmed=True,
        )
        db.add(player)
        db.commit()
        _log_action("player_added", "player", target_id=name, details=f"{position} | {nationality}")
        return {"status": "success", "message": f"✅ Joueur {name} ajouté",
                "player": {"id": player.id, "name": player.name,
                           "position": player.position, "nationality": player.nationality,
                           "price": player.price}}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.put("/player/{player_id}")
async def update_player(
    player_id: int,
    name: Optional[str] = Query(None), position: Optional[str] = Query(None),
    club: Optional[str] = Query(None), price: Optional[float] = Query(None),
    admin: dict = Depends(verify_admin),
):
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            raise HTTPException(404, "Joueur non trouvé")
        if name:     player.name     = name
        if position: player.position = position.upper()
        if club:     player.club     = club
        if price is not None: player.price = price
        db.commit()
        _log_action("player_updated", "player", target_id=str(player_id))
        return {"status": "success", "message": f"✅ Joueur {player.name} modifié"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════
#  TOURNOI
# ════════════════════════════════════════════════════════════════════

@router.post("/tournament/parse")
async def parse_tournament(req: TournamentInjectionRequest, admin: dict = Depends(verify_admin)):
    if not ai_service:
        return {"status": "error", "message": "IA non disponible"}
    parsed, msg = await ai_service.parse_tournament_data(req.raw_tournament_text)
    if not parsed:
        return {"status": "error", "message": msg}
    return {"status": "success", "message": msg, "parsed_data": parsed}


@router.post("/match/add")
async def add_match(
    home: str = Query(...), away: str = Query(...), match_date: str = Query(...),
    match_group: Optional[str] = Query(None), home_score: Optional[int] = Query(None),
    away_score: Optional[int] = Query(None), admin: dict = Depends(verify_admin),
):
    db = SessionLocal()
    try:
        match_result = MatchResult(
            home=home, away=away, date=match_date, group=match_group,
            round=match_group or "Group stage",
            home_score=home_score, away_score=away_score,
            status="scheduled" if home_score is None else "finished",
            is_finished=home_score is not None, is_locked=False,
            last_updated=datetime.utcnow().isoformat(),
        )
        db.add(match_result)
        db.commit()
        _log_action("match_added", "match", target_id=f"{home}-{away}", details=match_date)
        return {"status": "success", "message": f"✅ Match {home} vs {away} ajouté",
                "match": {"id": match_result.id, "home": match_result.home, "away": match_result.away}}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════
#  ENTRAÎNEURS
# ════════════════════════════════════════════════════════════════════

@router.post("/coach/parse")
async def parse_coach(req: CoachInjectionRequest, admin: dict = Depends(verify_admin)):
    if not ai_service:
        return {"status": "error", "message": "IA non disponible"}
    parsed, msg = await ai_service.parse_coach_data(req.raw_coach_text)
    if not parsed:
        return {"status": "error", "message": msg}
    return {"status": "success", "message": msg, "parsed_data": parsed}


@router.post("/coach/add")
async def add_coach(
    name: str = Query(...), nationality: str = Query(...),
    price: float = Query(6.0), admin: dict = Depends(verify_admin),
):
    db = SessionLocal()
    try:
        existing = db.query(Coach).filter(Coach.name == name).first()
        if existing:
            return {"status": "warning", "message": f"Entraîneur {name} existe déjà"}
        coach = Coach(
            name=name, nationality=nationality, team_name=nationality,
            price=price, is_confirmed=True, wins=0, losses=0, points_total=0,
        )
        db.add(coach)
        db.commit()
        _log_action("coach_added", "coach", target_id=name, details=nationality)
        return {"status": "success", "message": f"✅ Entraîneur {name} ajouté",
                "coach": {"id": coach.id, "name": coach.name,
                          "nationality": coach.nationality, "price": coach.price}}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════
#  RÈGLES
# ════════════════════════════════════════════════════════════════════

@router.post("/rules/parse")
async def parse_rules_endpoint(req: RulesParseRequest, admin: dict = Depends(verify_admin)):
    if not ai_service:
        return {"status": "error", "message": "IA non disponible"}
    parsed, msg = await ai_service.parse_rules(req.raw_rules_text)
    if not parsed:
        return {"status": "error", "message": msg}
    return {"status": "success", "message": msg, "rules": parsed.get("rules", [])}


@router.get("/rules")
async def get_rules(admin: dict = Depends(verify_admin)):
    db = SessionLocal()
    try:
        rules = db.query(AdminGameRule).order_by(AdminGameRule.rule_name).all()
        return {"status": "success", "rules": [
            {"id": r.id, "name": r.rule_name, "description": r.description,
             "position": r.position_affected, "points": r.points_value, "active": r.is_active}
            for r in rules
        ]}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.post("/rules/update")
async def update_rule(req: RuleUpdateRequest, admin: dict = Depends(verify_admin)):
    db = SessionLocal()
    try:
        rule = db.query(AdminGameRule).filter(AdminGameRule.rule_name == req.rule_name).first()
        if rule:
            rule.description       = req.description
            rule.position_affected = req.position_affected
            rule.points_value      = req.points_value
            rule.is_active         = req.is_active
            action = "rule_updated"
        else:
            rule = AdminGameRule(
                rule_name=req.rule_name, description=req.description,
                position_affected=req.position_affected,
                points_value=req.points_value, is_active=req.is_active,
            )
            db.add(rule)
            action = "rule_added"
        db.commit()
        _log_action(action, "rule", target_id=req.rule_name, details=f"Points: {req.points_value}")
        return {"status": "success", "message": f"✅ Règle {req.rule_name} sauvegardée",
                "rule": {"id": rule.id, "name": rule.rule_name, "points": rule.points_value}}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════
#  LOGS
# ════════════════════════════════════════════════════════════════════

@router.get("/logs")
async def get_logs(limit: int = Query(50), admin: dict = Depends(verify_admin)):
    db = SessionLocal()
    try:
        logs = db.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(limit).all()
        return {"status": "success", "logs": [
            {"id": log.id, "action": log.action,
             "target": f"{log.target_type}:{log.target_id}",
             "details": log.details, "timestamp": log.created_at.isoformat()}
            for log in logs
        ]}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        db.close()