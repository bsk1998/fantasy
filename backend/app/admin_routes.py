"""
admin_routes.py — Routes d'administration
===========================================
Interface pour injecter les données manuellement via Groq.
"""

import logging
from fastapi import APIRouter, HTTPException, Header, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.admin_auth import verify_admin_credentials, generate_admin_token, verify_admin_token
from app.admin_services import (
    parse_squad_list,
    estimate_player_prices,
    parse_tournament_data,
    parse_coach_data,
    parse_rules,
)
from app.models import (
    Player,
    Coach,
    TeamNation,
    MatchResult,
)
from app.admin_models import AdminLog, AdminGameRule, AdminPricingTemplate
from app.database import SessionLocal

logger = logging.getLogger("admin_routes")

router = APIRouter(tags=["admin"])

# ════════════════════════════════════════════════════════════════════════
#  Modèles Pydantic
# ════════════════════════════════════════════════════════════════════════

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    message: str


class SquadInjectionRequest(BaseModel):
    nation: str
    raw_squad_text: str


class SquadInjectionResponse(BaseModel):
    status: str
    message: str
    parsed_data: Optional[Dict] = None


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


# ════════════════════════════════════════════════════════════════════════
#  Dépendances
# ════════════════════════════════════════════════════════════════════════

async def verify_admin(authorization: Optional[str] = Header(None)) -> dict:
    """Dépendance : vérifie le token admin."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token manquant. Format: Bearer <token>"
        )
    
    token = authorization[7:]
    payload = verify_admin_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token invalide ou expiré"
        )
    
    return payload


def _log_action(action: str, target_type: str, target_id: str = None, details: str = None):
    """Enregistre une action admin."""
    try:
        db = SessionLocal()
        log = AdminLog(
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            admin_user="admin",
            created_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Logging erreur : {e}")


# ════════════════════════════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════════════════════════════

@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(req: AdminLoginRequest):
    """Connecte l'administrateur et retourne un token JWT."""
    username = req.username.strip()
    if not verify_admin_credentials(username, req.password):
        raise HTTPException(status_code=401, detail="Pseudo ou mot de passe admin incorrect")

    token = generate_admin_token(username)
    _log_action("login", "admin", target_id=username)

    return AdminLoginResponse(
        access_token=token,
        message="Connexion admin reussie"
    )


class RulesParseRequest(BaseModel):
    raw_rules_text: str

@router.post("/rules/parse")
async def parse_rules_endpoint(req: RulesParseRequest, admin: dict = Depends(verify_admin)):
    parsed, msg = await parse_rules(req.raw_rules_text)
    if not parsed:
        return {"status": "error", "message": msg}
    return {
        "status": "success",
        "message": msg,
        "rules": parsed.get("rules", []),
    }


@router.get("/status")
async def admin_status(admin: dict = Depends(verify_admin)):
    """Vérifie que le token admin est valide."""
    return {
        "status": "authenticated",
        "user": admin.get("sub"),
        "type": admin.get("type"),
    }


# ════════════════════════════════════════════════════════════════════════
#  INJECTION EFFECTIFS
# ════════════════════════════════════════════════════════════════════════

@router.post("/squad/parse", response_model=SquadInjectionResponse)
async def parse_squad(req: SquadInjectionRequest, admin: dict = Depends(verify_admin)):
    """
    Parse une liste de joueurs via Groq.
    Format attendu : texte libre (copié-collé d'une page web ou liste).
    """
    parsed, msg = await parse_squad_list(req.raw_squad_text)
    
    if not parsed:
        _log_action("squad_parse_failed", "player", target_id=req.nation, details=msg)
        return SquadInjectionResponse(status="error", message=msg)
    
    _log_action("squad_parse_success", "player", target_id=req.nation, details=msg)
    
    return SquadInjectionResponse(
        status="success",
        message=msg,
        parsed_data=parsed,
    )


@router.post("/squad/estimate-prices")
async def estimate_prices(req: PricingRequest, admin: dict = Depends(verify_admin)):
    """Estime les prix des joueurs via Groq."""
    pricing_result, msg = await estimate_player_prices(req.squad_data)
    
    if not pricing_result:
        _log_action("pricing_failed", "player", details=msg)
        return {"status": "error", "message": msg}
    
    _log_action("pricing_success", "player", details=msg)
    
    return {
        "status": "success",
        "message": msg,
        "pricing": pricing_result.get("pricing", []),
    }


@router.post("/squad/inject")
async def inject_squad(
    nation: str = Query(..., description="Nom du pays"),
    coach_name: Optional[str] = Query(None),
    admin: dict = Depends(verify_admin)
):
    """
    Injecte une squad complète en base de données.
    Les joueurs et coach viennent d'une session parse + pricing précédente.
    
    Payload attendu : {players: [{name, position, club, price}, ...]}
    """
    db = SessionLocal()
    try:
        # Vérifier que la nation existe
        team = db.query(TeamNation).filter(TeamNation.name == nation).first()
        if not team:
            team = TeamNation(
                name=nation,
                squad_status="brouillon",
                is_locked=False,
                last_updated=datetime.utcnow().isoformat(),
            )
            db.add(team)
            db.flush()
        
        # Ajouter l'entraîneur s'il est fourni
        if coach_name:
            existing_coach = db.query(Coach).filter(
                Coach.name == coach_name,
                Coach.nationality == nation
            ).first()
            if not existing_coach:
                coach = Coach(
                    name=coach_name,
                    nationality=nation,
                    team_name=nation,
                    is_confirmed=True,
                    price=6.0,
                    wins=0,
                    losses=0,
                    points_total=0,
                )
                db.add(coach)
                db.flush()
        
        msg = f"✅ Squad {nation} injectée avec entraîneur {coach_name or 'N/A'}"
        _log_action("squad_injected", "team", target_id=nation, details=msg)
        db.commit()
        
        return {"status": "success", "message": msg, "nation": nation}
    
    except Exception as e:
        db.rollback()
        logger.error(f"Inject squad error : {e}")
        _log_action("squad_inject_error", "team", target_id=nation, details=str(e))
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.post("/player/add")
async def add_player(
    name: str = Query(...),
    position: str = Query(...),  # G, D, M, A
    nationality: str = Query(...),
    club: str = Query(...),
    price: float = Query(...),
    number: Optional[int] = Query(None),
    admin: dict = Depends(verify_admin)
):
    """Ajoute un joueur individuel."""
    db = SessionLocal()
    try:
        # Vérifier que le joueur n'existe pas
        existing = db.query(Player).filter(
            Player.name == name,
            Player.nationality == nationality
        ).first()
        if existing:
            return {"status": "warning", "message": f"Joueur {name} existe déjà"}
        
        player = Player(
            name=name,
            position=position.upper(),
            nationality=nationality,
            club=club,
            price=price,
            number=number,
            goals=0,
            assists=0,
            points_total=0,
            is_confirmed=True,
        )
        db.add(player)
        db.commit()
        
        _log_action("player_added", "player", target_id=name, details=f"{position} | {nationality}")
        
        return {
            "status": "success",
            "message": f"✅ Joueur {name} ajouté",
            "player": {
                "id": player.id,
                "name": player.name,
                "position": player.position,
                "nationality": player.nationality,
                "price": player.price,
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Add player error : {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.put("/player/{player_id}")
async def update_player(
    player_id: int,
    name: Optional[str] = Query(None),
    position: Optional[str] = Query(None),
    club: Optional[str] = Query(None),
    price: Optional[float] = Query(None),
    admin: dict = Depends(verify_admin)
):
    """Modifie un joueur."""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            raise HTTPException(404, "Joueur non trouvé")
        
        if name:
            player.name = name
        if position:
            player.position = position.upper()
        if club:
            player.club = club
        if price is not None:
            player.price = price
        
        db.commit()
        _log_action("player_updated", "player", target_id=str(player_id), details=f"Prix: {price}")
        
        return {"status": "success", "message": f"✅ Joueur {player.name} modifié"}
    except Exception as e:
        db.rollback()
        logger.error(f"Update player error : {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════════
#  INJECTION TOURNOI
# ════════════════════════════════════════════════════════════════════════

@router.post("/tournament/parse")
async def parse_tournament(req: TournamentInjectionRequest, admin: dict = Depends(verify_admin)):
    """Parse les données de tournoi via Groq."""
    parsed, msg = await parse_tournament_data(req.raw_tournament_text)
    
    if not parsed:
        return {"status": "error", "message": msg}
    
    return {
        "status": "success",
        "message": msg,
        "parsed_data": parsed,
    }


@router.post("/match/add")
async def add_match(
    home: str = Query(...),
    away: str = Query(...),
    match_date: str = Query(...),  # YYYY-MM-DD
    match_group: Optional[str] = Query(None),
    home_score: Optional[int] = Query(None),
    away_score: Optional[int] = Query(None),
    admin: dict = Depends(verify_admin)
):
    """Ajoute un match."""
    db = SessionLocal()
    try:
        match_result = MatchResult(
            home=home,
            away=away,
            date=match_date,
            group=match_group,
            round=match_group or "Group stage",
            home_score=home_score,
            away_score=away_score,
            status="scheduled" if home_score is None else "finished",
            is_finished=home_score is not None,
            is_locked=False,
            last_updated=datetime.utcnow().isoformat(),
        )
        db.add(match_result)
        db.commit()
        
        _log_action("match_added", "match", target_id=f"{home}-{away}", details=match_date)
        
        return {
            "status": "success",
            "message": f"✅ Match {home} vs {away} ajouté",
            "match": {
                "id": match_result.id,
                "home": match_result.home,
                "away": match_result.away,
                "date": match_result.date,
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Add match error : {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════════
#  INJECTION ENTRAÎNEUR
# ════════════════════════════════════════════════════════════════════════

@router.post("/coach/parse")
async def parse_coach(req: CoachInjectionRequest, admin: dict = Depends(verify_admin)):
    """Parse les données d'entraîneur via Groq."""
    parsed, msg = await parse_coach_data(req.raw_coach_text)
    
    if not parsed:
        return {"status": "error", "message": msg}
    
    return {
        "status": "success",
        "message": msg,
        "parsed_data": parsed,
    }


@router.post("/coach/add")
async def add_coach(
    name: str = Query(...),
    nationality: str = Query(...),
    price: float = Query(6.0),
    admin: dict = Depends(verify_admin)
):
    """Ajoute un entraîneur."""
    db = SessionLocal()
    try:
        existing = db.query(Coach).filter(Coach.name == name).first()
        if existing:
            return {"status": "warning", "message": f"Entraîneur {name} existe déjà"}
        
        coach = Coach(
            name=name,
            nationality=nationality,
            team_name=nationality,
            price=price,
            is_confirmed=True,
            wins=0,
            losses=0,
            points_total=0,
        )
        db.add(coach)
        db.commit()
        
        _log_action("coach_added", "coach", target_id=name, details=nationality)
        
        return {
            "status": "success",
            "message": f"✅ Entraîneur {name} ajouté",
            "coach": {
                "id": coach.id,
                "name": coach.name,
                "nationality": coach.nationality,
                "price": coach.price,
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Add coach error : {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════════
#  GESTION RÈGLES
# ════════════════════════════════════════════════════════════════════════

@router.get("/rules")
async def get_rules(admin: dict = Depends(verify_admin)):
    """Affiche toutes les règles du jeu."""
    db = SessionLocal()
    try:
        rules = db.query(AdminGameRule).order_by(AdminGameRule.rule_name).all()
        db.close()
        return {
            "status": "success",
            "rules": [{
                "id": r.id,
                "name": r.rule_name,
                "description": r.description,
                "position": r.position_affected,
                "points": r.points_value,
                "active": r.is_active,
            } for r in rules]
        }
    except Exception as e:
        logger.error(f"Get rules error : {e}")
        raise HTTPException(500, str(e))


@router.post("/rules/parse-legacy", include_in_schema=False)
async def parse_rules_endpoint(req: BaseModel = None, admin: dict = Depends(verify_admin)):
    """Parse un texte décrivant des règles."""
    if not hasattr(req, 'raw_rules_text'):
        raise HTTPException(400, "raw_rules_text manquant")
    
    parsed, msg = await parse_rules(req.raw_rules_text)
    
    if not parsed:
        return {"status": "error", "message": msg}
    
    return {
        "status": "success",
        "message": msg,
        "rules": parsed.get("rules", []),
    }


@router.post("/rules/update")
async def update_rule(req: RuleUpdateRequest, admin: dict = Depends(verify_admin)):
    """Crée ou met à jour une règle du jeu."""
    db = SessionLocal()
    try:
        rule = db.query(AdminGameRule).filter(
            AdminGameRule.rule_name == req.rule_name
        ).first()
        
        if rule:
            rule.description = req.description
            rule.position_affected = req.position_affected
            rule.points_value = req.points_value
            rule.is_active = req.is_active
            action = "rule_updated"
        else:
            rule = AdminGameRule(
                rule_name=req.rule_name,
                description=req.description,
                position_affected=req.position_affected,
                points_value=req.points_value,
                is_active=req.is_active,
            )
            db.add(rule)
            action = "rule_added"
        
        db.commit()
        _log_action(action, "rule", target_id=req.rule_name, details=f"Points: {req.points_value}")
        
        return {
            "status": "success",
            "message": f"✅ Règle {req.rule_name} sauvegardée",
            "rule": {
                "id": rule.id,
                "name": rule.rule_name,
                "points": rule.points_value,
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Update rule error : {e}")
        raise HTTPException(500, str(e))
    finally:
        db.close()


@router.get("/logs")
async def get_logs(limit: int = Query(50), admin: dict = Depends(verify_admin)):
    """Affiche les logs des actions admin."""
    db = SessionLocal()
    try:
        logs = db.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(limit).all()
        db.close()
        return {
            "status": "success",
            "logs": [{
                "id": log.id,
                "action": log.action,
                "target": f"{log.target_type}:{log.target_id}",
                "details": log.details,
                "timestamp": log.created_at.isoformat(),
            } for log in logs]
        }
    except Exception as e:
        logger.error(f"Get logs error : {e}")
        raise HTTPException(500, str(e))
