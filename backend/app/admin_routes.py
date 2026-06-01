"""Routes admin FastAPI — authentification, gestion équipes, configuration règles."""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Header, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.admin_auth import (
    verify_admin_credentials, create_admin_token, verify_admin_token,
    get_admin_from_request
)
from app.admin_services import (
    parse_squad_list_with_groq, estimate_player_prices,
    parse_tournament_from_text, validate_rules,
    DEFAULT_FANTASY_RULES, DEFAULT_PREDICTOR_RULES, DEFAULT_BRACKET_RULES
)
from app.database import SessionLocal
from app.models import (
    TeamNation, Player, Coach, MatchResult, User
)
from app.admin_models import AdminLog, GameRules, TournamentMetadata

logger = logging.getLogger("admin_routes")

router = APIRouter(prefix="/admin", tags=["admin"])


# ════════════════════════════════════════════════════════════════════════
#  MODÈLES PYDANTIC POUR LES REQUÊTES
# ════════════════════════════════════════════════════════════════════════

class AdminLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int = 24


class SquadImportRequest(BaseModel):
    nation: str  # Ex: "France"
    position: str  # "G", "D", "M", "A"
    raw_players_text: str  # Texte collé par l'admin


class CoachSetRequest(BaseModel):
    nation: str
    coach_name: str
    nationality: Optional[str] = None
    price: Optional[float] = None


class TournamentCreateRequest(BaseModel):
    tournament_name: str
    official_url: Optional[str] = None
    raw_tournament_text: str  # Texte/captures


class RulesUpdateRequest(BaseModel):
    rule_type: str  # 'fantasy_points', 'predictor_scores', 'predictor_tableau'
    rules_data: Dict[str, Any]  # Structure JSON des règles


def get_current_admin(authorization: Optional[str] = Header(None)) -> str:
    """
    Dépendance FastAPI pour vérifier l'authentification admin.
    Retourne l'username si valide, sinon lève une exception 401.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header manquant"
        )
    username = get_admin_from_request(authorization)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré"
        )
    return username


def log_admin_action(db: Session, admin: str, action: str, target: Optional[str] = None,
                     details: Optional[Dict] = None, error: Optional[str] = None):
    """
    Enregistre une action admin dans l'audit trail.
    """
    try:
        log = AdminLog(
            admin_email=admin,
            action=action,
            target=target,
            details=details,
            status="error" if error else "success",
            error_message=error,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Erreur log admin : {e}")


# ════════════════════════════════════════════════════════════════════════
#  1. AUTHENTIFICATION ADMIN
# ════════════════════════════════════════════════════════════════════════

@router.post("/login", response_model=TokenResponse)
async def admin_login(credentials: AdminLogin):
    """
    POST /admin/login
    Corps : {"username": "admin", "password": "admin00"}
    Retourne : {"access_token": "...", "token_type": "bearer", "expires_in_hours": 24}
    """
    if not verify_admin_credentials(credentials.username, credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants admin invalides"
        )
    token = create_admin_token(credentials.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_hours": 24
    }


# ════════════════════════════════════════════════════════════════════════
#  2. IMPORT D'EFFECTIF — Admin colle une liste, Groq la parse
# ════════════════════════════════════════════════════════════════════════

@router.post("/squads/import")
async def import_squad(req: SquadImportRequest, admin: str = Depends(get_current_admin)):
    """
    POST /admin/squads/import
    Corps : {
      "nation": "France",
      "position": "G",
      "raw_players_text": "Maignan, Milan\nAreola, West Ham\n..."
    }
    
    1. Parse le texte avec Groq
    2. Estime les prix
    3. Sauvegarde en BD
    """
    db = SessionLocal()
    try:
        # Vérifier que l'équipe existe
        nation = db.query(TeamNation).filter(
            TeamNation.name.ilike(req.nation)
        ).first()
        if not nation:
            raise HTTPException(400, f"Équipe '{req.nation}' non trouvée en BD")
        
        # Parse avec Groq
        joueurs_parses, err = parse_squad_list_with_groq(req.raw_players_text)
        if err:
            log_admin_action(db, admin, "squad_import", req.nation, error=err)
            raise HTTPException(400, err)
        
        # Estimer les prix
        joueurs_avec_prix, err = estimate_player_prices(joueurs_parses)
        if err:
            logger.warning(f"⚠️ Estimation prix échouée : {err}, utilise prix par défaut")
        
        # Filtrer par position demandée
        joueurs_filtered = [
            j for j in joueurs_avec_prix
            if j.get("position", "M").upper() == req.position.upper()
        ]
        
        # Sauvegarder en BD
        added_players = []
        for j in joueurs_filtered:
            player = Player(
                name=j.get("name", "Joueur"),
                position=j.get("position", "M").upper(),
                nationality=req.nation,
                price=j.get("price", 6.0),
                is_confirmed=True,
                goals=0,
                assists=0,
                clean_sheets=False,
                yellow_cards=0,
                red_cards=0,
                points_total=0,
            )
            db.add(player)
            added_players.append(j["name"])
        
        db.commit()
        
        # Log l'action
        log_admin_action(
            db, admin, "squad_import", req.nation,
            {"position": req.position, "joueurs_ajoutes": added_players}
        )
        
        logger.info(f"✅ {len(added_players)} joueurs importés pour {req.nation} - {req.position}")
        return {
            "status": "success",
            "nation": req.nation,
            "position": req.position,
            "joueurs_ajoutes": added_players,
            "count": len(added_players)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_admin_action(db, admin, "squad_import", req.nation, error=str(e))
        raise HTTPException(500, f"Erreur import squad : {e}")
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════════
#  3. SET COACH — Admin ajoute/modifie l'entraîneur
# ════════════════════════════════════════════════════════════════════════

@router.post("/coaches/set")
async def set_coach(req: CoachSetRequest, admin: str = Depends(get_current_admin)):
    """
    POST /admin/coaches/set
    Corps : {
      "nation": "France",
      "coach_name": "Didier Deschamps",
      "nationality": "Française",
      "price": 5.5
    }
    """
    db = SessionLocal()
    try:
        # Vérifier nation
        nation = db.query(TeamNation).filter(
            TeamNation.name.ilike(req.nation)
        ).first()
        if not nation:
            raise HTTPException(400, f"Équipe '{req.nation}' non trouvée")
        
        # Vérifier ou créer l'entraîneur
        coach = db.query(Coach).filter(
            Coach.name == req.coach_name
        ).first()
        
        if coach:
            # Mise à jour
            coach.nationality = req.nationality or coach.nationality
            coach.price = req.price or coach.price
            coach.is_confirmed = True
        else:
            # Création
            coach = Coach(
                name=req.coach_name,
                nationality=req.nationality or "Inconnu",
                price=req.price or 5.0,
                is_confirmed=True,
            )
            db.add(coach)
        
        db.commit()
        
        log_admin_action(
            db, admin, "set_coach", req.nation,
            {"coach": req.coach_name, "price": req.price}
        )
        
        logger.info(f"✅ Entraîneur défini : {req.coach_name} pour {req.nation}")
        return {
            "status": "success",
            "nation": req.nation,
            "coach": req.coach_name,
            "price": coach.price
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_admin_action(db, admin, "set_coach", req.nation, error=str(e))
        raise HTTPException(500, f"Erreur set coach : {e}")
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════════
#  4. CRÉATION TOURNOI — Admin fournit le site/captures, Groq l'analyse
# ════════════════════════════════════════════════════════════════════════

@router.post("/tournaments/create")
async def create_tournament(req: TournamentCreateRequest, admin: str = Depends(get_current_admin)):
    """
    POST /admin/tournaments/create
    Corps : {
      "tournament_name": "Coupe du Monde 2026",
      "official_url": "https://www.sofascore.com/...",
      "raw_tournament_text": "Texte ou contenu capturé du site"
    }
    
    Groq extrait matchs et groupes, qu'on peut ensuite éditer.
    """
    db = SessionLocal()
    try:
        # Parse le tournoi
        tournament_data, err = parse_tournament_from_text(req.raw_tournament_text)
        if err:
            log_admin_action(db, admin, "create_tournament", req.tournament_name, error=err)
            raise HTTPException(400, err)
        
        # Créer l'entrée tournoi en BD
        tournament = TournamentMetadata(
            tournament_name=req.tournament_name,
            official_url=req.official_url,
            groups_structure=tournament_data.get("groups", {}),
            created_by=admin,
        )
        db.add(tournament)
        db.commit()
        
        # Créer les équipes du tournoi
        all_teams = []
        for group_name, teams in tournament_data.get("groups", {}).items():
            for team_name in teams:
                existing = db.query(TeamNation).filter(
                    TeamNation.name.ilike(team_name)
                ).first()
                if not existing:
                    team = TeamNation(
                        name=team_name,
                        group=group_name,
                    )
                    db.add(team)
                all_teams.append(team_name)
        
        # Créer les matchs
        for match_data in tournament_data.get("matches", []):
            match = MatchResult(
                home=match_data.get("home", ""),
                away=match_data.get("away", ""),
                match_group=match_data.get("group"),
                match_date=match_data.get("date"),
                status=match_data.get("status", "scheduled"),
            )
            db.add(match)
        
        db.commit()
        
        log_admin_action(
            db, admin, "create_tournament", req.tournament_name,
            {"groups": len(tournament_data.get('groups', {})),
             "matches": len(tournament_data.get('matches', [])),
             "teams": all_teams}
        )
        
        logger.info(f"✅ Tournoi créé : {req.tournament_name}")
        return {
            "status": "success",
            "tournament": req.tournament_name,
            "groups": tournament_data.get("groups", {}),
            "matches_count": len(tournament_data.get("matches", [])),
            "teams_count": len(all_teams)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_admin_action(db, admin, "create_tournament", req.tournament_name, error=str(e))
        raise HTTPException(500, f"Erreur création tournoi : {e}")
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════════
#  5. GESTION DES RÈGLES — Admin configure les points du jeu
# ════════════════════════════════════════════════════════════════════════

@router.get("/rules/{rule_type}")
async def get_rules(rule_type: str, admin: str = Depends(get_current_admin)):
    """
    GET /admin/rules/fantasy_points
    GET /admin/rules/predictor_scores
    GET /admin/rules/predictor_tableau
    
    Retourne les règles actuelles pour ce type.
    """
    db = SessionLocal()
    try:
        rules = db.query(GameRules).filter(
            GameRules.rule_type == rule_type,
            GameRules.is_active == True
        ).order_by(GameRules.updated_at.desc()).first()
        
        if rules:
            return {
                "rule_type": rule_type,
                "rules": rules.rules_data,
                "version": rules.version,
                "updated_at": rules.updated_at.isoformat()
            }
        else:
            # Retourner les valeurs par défaut
            defaults = {
                "fantasy_points": DEFAULT_FANTASY_RULES,
                "predictor_scores": DEFAULT_PREDICTOR_RULES,
                "predictor_tableau": DEFAULT_BRACKET_RULES,
            }
            return {
                "rule_type": rule_type,
                "rules": defaults.get(rule_type, {}),
                "version": 0,
                "note": "Valeurs par défaut (pas encore sauvegardées)"
            }
    finally:
        db.close()


@router.post("/rules/{rule_type}")
async def update_rules(rule_type: str, req: RulesUpdateRequest,
                       admin: str = Depends(get_current_admin)):
    """
    POST /admin/rules/fantasy_points
    Corps : {
      "rule_type": "fantasy_points",
      "rules_data": {
        "G": {"match_complet": 2, "but": 4, ...},
        ...
      }
    }
    """
    db = SessionLocal()
    try:
        # Valider
        is_valid, err = validate_rules(req.rules_data)
        if not is_valid:
            log_admin_action(db, admin, f"update_rules_{rule_type}", error=err)
            raise HTTPException(400, f"Règles invalides : {err}")
        
        # Désactiver les anciennes règles
        old_rules = db.query(GameRules).filter(
            GameRules.rule_type == rule_type
        ).all()
        for rule in old_rules:
            rule.is_active = False
        
        # Créer les nouvelles
        new_rules = GameRules(
            rule_type=rule_type,
            rules_data=req.rules_data,
            created_by=admin,
            version=1 + (max([r.version for r in old_rules], default=0))
        )
        db.add(new_rules)
        db.commit()
        
        log_admin_action(
            db, admin, f"update_rules_{rule_type}",
            {"version": new_rules.version}
        )
        
        logger.info(f"✅ Règles mises à jour : {rule_type} v{new_rules.version}")
        return {
            "status": "success",
            "rule_type": rule_type,
            "version": new_rules.version,
            "updated_at": new_rules.updated_at.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_admin_action(db, admin, f"update_rules_{rule_type}", error=str(e))
        raise HTTPException(500, f"Erreur mise à jour règles : {e}")
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════════
#  6. AUDIT TRAIL — Voir les actions admin
# ════════════════════════════════════════════════════════════════════════

@router.get("/logs")
async def get_admin_logs(admin: str = Depends(get_current_admin), limit: int = 50):
    """
    GET /admin/logs?limit=50
    Retourne les 50 dernières actions admin.
    """
    db = SessionLocal()
    try:
        logs = db.query(AdminLog).order_by(
            AdminLog.created_at.desc()
        ).limit(limit).all()
        
        return {
            "logs": [
                {
                    "timestamp": log.created_at.isoformat(),
                    "admin": log.admin_email,
                    "action": log.action,
                    "target": log.target,
                    "status": log.status,
                    "details": log.details,
                }
                for log in logs
            ]
        }
    finally:
        db.close()


@router.get("/status")
async def admin_status(admin: str = Depends(get_current_admin)):
    """
    GET /admin/status
    Retourne l'état actuel du système admin (nombre d'équipes, matchs, joueurs, etc.).
    """
    db = SessionLocal()
    try:
        num_teams = db.query(TeamNation).count()
        num_players = db.query(Player).count()
        num_coaches = db.query(Coach).count()
        num_matches = db.query(MatchResult).count()
        num_users = db.query(User).count()
        
        return {
            "status": "operational",
            "admin_user": admin,
            "stats": {
                "teams": num_teams,
                "players": num_players,
                "coaches": num_coaches,
                "matches": num_matches,
                "users": num_users,
            }
        }
    finally:
        db.close()
