"""
main.py — API FastAPI complète — Fantasy Boulzazen WC 2026
Tech Lead : Architecture Lazy Loading + Supabase JWT Auth

Endpoints implémentés :
  POST  /auth/sync                   ← Trigger recalcul au login (Lazy Loading)
  GET   /players                     ← Marché des joueurs
  GET   /coaches                     ← Marché des entraîneurs
  GET   /teams                       ← Statut des équipes (verrouillé/ouvert)
  GET   /leaderboard                 ← Classement général (tous modes)
  GET   /matches                     ← Liste des matchs pour pronostics
  POST  /predictions/score           ← Sauvegarder pronostics de scores
  GET   /predictions/score/{user_id} ← Récupérer pronostics d'un utilisateur
  POST  /fantasy/roster              ← Sauvegarder l'équipe Fantasy
  GET   /fantasy/roster/{user_id}    ← Récupérer l'équipe Fantasy
  GET   /fantasy/autofill            ← Auto-Fill intelligent (budget + contraintes)
  POST  /admin/recalculate           ← Recalcul manuel des scores (admin)
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.models import Base, User, Player, Coach, FantasyRoster, PredictionScore, PredictionTableau
from app.scraper import recuperer_resultats_matchs, recuperer_stats_joueurs
from app.rules_engine import (
    calculer_points_joueur,
    calculer_points_entraineur,
    calculer_points_pronostic_score,
    calculer_score_global_utilisateur,
)

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fantasy_boulzazen")

# ─── Création des tables au démarrage ─────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── App FastAPI ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fantasy Boulzazen — API WC 2026",
    description="Backend complet pour la ligue privée Fantasy Coupe du Monde",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # En prod : remplacer par l'URL Vercel/Netlify exacte
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Config Supabase ──────────────────────────────────────────────────────────
# Récupère le JWT secret depuis les variables d'environnement.
# Sur Render.com : ajoute SUPABASE_JWT_SECRET dans les variables d'env.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://selkpaowxwjjfteadjvz.supabase.co")


# ══════════════════════════════════════════════════════════════════════════════
#  MODÈLES PYDANTIC — Corps des requêtes
# ══════════════════════════════════════════════════════════════════════════════

class SyncRequest(BaseModel):
    user_id: str
    email: str
    username: Optional[str] = None

class PredictionScorePayload(BaseModel):
    user_id: str
    match_id: int
    predicted_home: int
    predicted_away: int

class RosterPayload(BaseModel):
    user_id: str
    player_ids: list[int]          # 15 joueurs maximum
    coach_id: Optional[int] = None
    formation: str = "4-3-3"

class AutoFillRequest(BaseModel):
    budget: float = 100.0
    formation: str = "4-3-3"
    locked_player_ids: list[int] = []   # Joueurs déjà sélectionnés à conserver


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH — Vérification JWT Supabase
# ══════════════════════════════════════════════════════════════════════════════

async def verify_supabase_token(authorization: str = Header(default=None)) -> dict:
    """
    Middleware d'authentification : vérifie le JWT Supabase envoyé
    dans le header Authorization: Bearer <token>.

    En développement, si SUPABASE_JWT_SECRET n'est pas défini,
    le token est accepté sans vérification (mode dev uniquement).
    """
    if not SUPABASE_JWT_SECRET:
        # Mode développement : pas de vérif crypto
        logger.warning("⚠️  SUPABASE_JWT_SECRET non défini — Auth désactivée (mode dev)")
        return {"sub": "dev-user", "email": "dev@boulzazen.local"}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant ou invalide.",
        )

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as e:
        logger.error(f"JWT invalide : {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expiré ou invalide.",
        )


# ══════════════════════════════════════════════════════════════════════════════
#  LAZY LOADING — Le cœur de l'architecture
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/sync")
async def sync_on_login(
    body: SyncRequest,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """
    Endpoint déclenché automatiquement à CHAQUE connexion d'un utilisateur.

    Séquence Lazy Loading :
      1. Upsert de l'utilisateur en base
      2. Scraping des derniers résultats et stats
      3. Recalcul des points Fantasy de tous les joueurs mis à jour
      4. Recalcul des pronostics de score pour les matchs terminés
      5. Retour du profil utilisateur à jour + classement

    Ce design évite un serveur de background constant :
    la mise à jour se produit à la demande, à chaque connexion.
    """
    logger.info(f"🔄 Sync au login : {body.email}")

    # ── Étape 1 : Upsert utilisateur ──────────────────────────────────────────
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        user = User(
            username=body.username or body.email.split("@")[0],
            email=body.email,
            hashed_password="",  # Auth déléguée à Supabase
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"✨ Nouvel utilisateur créé : {user.username}")
    else:
        logger.info(f"👤 Utilisateur existant : {user.username}")

    # ── Étape 2 : Scraping des résultats récents ──────────────────────────────
    resultats_nouveaux = []
    stats_joueurs_nouveau = []
    try:
        resultats_nouveaux = recuperer_resultats_matchs()
        stats_joueurs_nouveau = recuperer_stats_joueurs()
        logger.info(f"📡 Scraping : {len(resultats_nouveaux)} matchs, {len(stats_joueurs_nouveau)} joueurs")
    except Exception as e:
        logger.warning(f"⚠️  Scraping échoué (données cached utilisées) : {e}")

    # ── Étape 3 : Recalcul des points Fantasy ─────────────────────────────────
    joueurs_mis_a_jour = 0
    for stats_raw in stats_joueurs_nouveau:
        joueur = db.query(Player).filter(Player.id == stats_raw.get("player_id")).first()
        if joueur:
            result = calculer_points_joueur(
                stats={
                    "minutes":     stats_raw.get("minutes", 0),
                    "buts":        stats_raw.get("goals", 0),
                    "passes":      stats_raw.get("assists", 0),
                    "clean_sheet": stats_raw.get("clean_sheet", False),
                    "parades":     stats_raw.get("saves", 0),
                    "recups":      stats_raw.get("recoveries", 0),
                    "jaune":       stats_raw.get("yellow_cards", 0),
                    "rouge":       stats_raw.get("red_cards", 0),
                },
                position=joueur.position,
            )
            joueur.points_total = result["total"]
            joueur.goals    = stats_raw.get("goals", joueur.goals)
            joueur.assists  = stats_raw.get("assists", joueur.assists)
            joueurs_mis_a_jour += 1

    if joueurs_mis_a_jour > 0:
        db.commit()
        logger.info(f"✅ {joueurs_mis_a_jour} joueurs recalculés")

    # ── Étape 4 : Recalcul des pronostics de score ────────────────────────────
    pronos_calculés = 0
    for match in resultats_nouveaux:
        if match.get("is_finished") and match.get("home_score") is not None:
            pronos_du_match = (
                db.query(PredictionScore)
                .filter(
                    PredictionScore.match_id == match["id"],
                    PredictionScore.points_earned == 0,  # Pas encore calculé
                )
                .all()
            )
            for prono in pronos_du_match:
                pts = calculer_points_pronostic_score(
                    prono.predicted_home_score,
                    prono.predicted_away_score,
                    match["home_score"],
                    match["away_score"],
                )
                prono.points_earned = pts
                pronos_calculés += 1

    if pronos_calculés > 0:
        db.commit()
        logger.info(f"✅ {pronos_calculés} pronostics de score calculés")

    # ── Étape 5 : Mise à jour du score Fantasy de l'utilisateur ──────────────
    roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
    if roster:
        fantasy_pts = sum(p.points_total for p in roster.players)
        if roster.coach:
            fantasy_pts += roster.coach.points_total
        user.score_fantasy = fantasy_pts

    prono_pts = (
        db.query(PredictionScore)
        .filter(PredictionScore.user_id == user.id)
        .with_entities(PredictionScore.points_earned)
        .all()
    )
    user.score_predictor_scores = sum(p.points_earned for p in prono_pts)
    db.commit()

    return {
        "status": "synced",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "score_fantasy": user.score_fantasy,
            "score_pronos_scores": user.score_predictor_scores,
            "score_bracket": user.score_predictor_tableaux,
            "total": user.score_fantasy + user.score_predictor_scores + user.score_predictor_tableaux,
        },
        "sync_info": {
            "matchs_scraped": len(resultats_nouveaux),
            "joueurs_recalculés": joueurs_mis_a_jour,
            "pronos_calculés": pronos_calculés,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  JOUEURS & COACHES — Marché
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/players")
async def get_players(
    position: Optional[str] = None,
    nationality: Optional[str] = None,
    max_price: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """
    Retourne la liste des joueurs disponibles pour le marché Fantasy.
    Supporte les filtres : poste, nationalité, prix maximum.
    """
    query = db.query(Player)

    if position and position != "ALL":
        query = query.filter(Player.position == position.upper())
    if nationality:
        query = query.filter(Player.nationality.ilike(f"%{nationality}%"))
    if max_price is not None:
        query = query.filter(Player.price <= max_price)

    players = query.order_by(Player.price.desc()).all()

    # Si la BDD est vide → retourner les données de base du scraper
    if not players:
        from app.scraper import recuperer_effectif_web
        players_data = []
        for team_name in EQUIPES_CDM_2026:
            effectif = recuperer_effectif_web(team_name)
            if effectif:
                players_data.extend(effectif)
        return players_data

    return [
        {
            "id": p.id,
            "name": p.name,
            "position": p.position,
            "nationality": p.nationality,
            "price": p.price,
            "goals": p.goals,
            "assists": p.assists,
            "points_total": p.points_total,
            "is_confirmed": p.is_confirmed,
        }
        for p in players
    ]


@app.get("/coaches")
async def get_coaches(db: Session = Depends(get_db)):
    """
    Retourne la liste des entraîneurs disponibles.
    Rappel de la règle : l'entraîneur ne peut pas partager
    la nationalité d'aucun joueur de l'équipe Fantasy.
    """
    coaches = db.query(Coach).all()

    if not coaches:
        # Données de base si BDD vide
        return COACHES_CDM_2026_DATA

    return [
        {
            "id": c.id,
            "name": c.name,
            "nationality": c.nationality,
            "price": c.price,
            "wins": c.wins,
            "losses": c.losses,
            "points_total": c.points_total,
            "status": c.status,
        }
        for c in coaches
    ]


@app.get("/teams")
async def get_teams(db: Session = Depends(get_db)):
    """Retourne le statut de toutes les équipes (ouvertes/verrouillées)."""
    from app.scraper import recuperer_effectif_web

    teams_status = []
    for team_name in EQUIPES_CDM_2026:
        effectif = recuperer_effectif_web(team_name)
        teams_status.append({
            "name": team_name,
            "players": effectif or [],
            "status": "open" if effectif else "locked",
            "player_count": len(effectif) if effectif else 0,
        })

    return teams_status


# ══════════════════════════════════════════════════════════════════════════════
#  LEADERBOARD — Classement général
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/leaderboard")
async def get_leaderboard(db: Session = Depends(get_db)):
    """
    Retourne le classement général de la ligue privée,
    trié par score total décroissant.
    Inclut le détail par mode (fantasy, scores, bracket, annexes).
    """
    users = db.query(User).all()

    leaderboard = []
    for u in users:
        total = (
            u.score_fantasy
            + u.score_predictor_scores
            + u.score_predictor_tableaux
            + u.score_top_individuel
        )
        leaderboard.append({
            "username": u.username,
            "fantasy": u.score_fantasy,
            "scores": u.score_predictor_scores,
            "bracket": u.score_predictor_tableaux,
            "annexes": u.score_top_individuel,
            "total": total,
        })

    leaderboard.sort(key=lambda x: x["total"], reverse=True)

    # Ajouter le rang
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard


# ══════════════════════════════════════════════════════════════════════════════
#  MATCHS — Liste pour pronostics
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/matches")
async def get_matches():
    """
    Retourne la liste des matchs de la Coupe du Monde 2026.
    Actuellement : données statiques de la phase de poules.
    À connecter au scraper pour les données live.
    """
    return MATCHS_CDM_2026


# ══════════════════════════════════════════════════════════════════════════════
#  PRONOSTICS — Scores des matchs
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/predictions/score")
async def save_score_prediction(
    payload: PredictionScorePayload,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """
    Sauvegarde ou met à jour le pronostic de score d'un utilisateur.
    Vérifie que le match n'est pas encore commencé avant d'accepter.
    """
    user = db.query(User).filter(User.id == int(payload.user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    # Vérifier si le match est déjà commencé (protection anti-triche)
    match_data = next((m for m in MATCHS_CDM_2026 if m["id"] == payload.match_id), None)
    if match_data and match_data.get("is_locked", False):
        raise HTTPException(
            status_code=400,
            detail="Ce match a déjà commencé, les pronostics sont verrouillés.",
        )

    # Upsert du pronostic
    prono = (
        db.query(PredictionScore)
        .filter(
            PredictionScore.user_id == user.id,
            PredictionScore.match_id == payload.match_id,
        )
        .first()
    )

    if prono:
        prono.predicted_home_score = payload.predicted_home
        prono.predicted_away_score = payload.predicted_away
        prono.points_earned = 0  # Reset en attente du résultat réel
    else:
        prono = PredictionScore(
            user_id=user.id,
            match_id=payload.match_id,
            predicted_home_score=payload.predicted_home,
            predicted_away_score=payload.predicted_away,
            points_earned=0,
        )
        db.add(prono)

    db.commit()
    return {"status": "saved", "match_id": payload.match_id}


@app.get("/predictions/score/{user_id}")
async def get_score_predictions(
    user_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """Retourne tous les pronostics de score d'un utilisateur avec leurs points."""
    pronos = db.query(PredictionScore).filter(PredictionScore.user_id == user_id).all()

    return [
        {
            "match_id": p.match_id,
            "predicted_home": p.predicted_home_score,
            "predicted_away": p.predicted_away_score,
            "points_earned": p.points_earned,
        }
        for p in pronos
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  FANTASY ROSTER — Équipe du joueur
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/fantasy/roster")
async def save_roster(
    payload: RosterPayload,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """
    Sauvegarde l'équipe Fantasy d'un utilisateur.
    Valide :
      - 15 joueurs maximum
      - Budget ≤ 100M
      - Max 3 joueurs par nationalité
      - Entraîneur sans joueur de sa nationalité
    """
    if len(payload.player_ids) > 15:
        raise HTTPException(status_code=400, detail="Maximum 15 joueurs autorisés.")

    players = db.query(Player).filter(Player.id.in_(payload.player_ids)).all()

    if len(players) != len(payload.player_ids):
        raise HTTPException(status_code=400, detail="Un ou plusieurs joueurs introuvables.")

    # ── Validation budget ──────────────────────────────────────────────────────
    total_prix = sum(p.price for p in players)
    coach = None
    if payload.coach_id:
        coach = db.query(Coach).filter(Coach.id == payload.coach_id).first()
        if not coach:
            raise HTTPException(status_code=400, detail="Entraîneur introuvable.")
        total_prix += coach.price

    if total_prix > 100.0:
        raise HTTPException(
            status_code=400,
            detail=f"Budget dépassé : {total_prix:.1f}M€ pour un maximum de 100M€.",
        )

    # ── Validation nationalités ────────────────────────────────────────────────
    from collections import Counter
    nat_count = Counter(p.nationality for p in players)
    for nat, count in nat_count.items():
        if count > 3:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum 3 joueurs par nationalité — {nat} : {count} joueurs.",
            )

    # ── Validation conflit Coach / Nationalité ────────────────────────────────
    if coach:
        nationalities_in_roster = {p.nationality for p in players}
        if coach.nationality in nationalities_in_roster:
            raise HTTPException(
                status_code=400,
                detail=f"L'entraîneur ({coach.name}) partage la nationalité de joueurs dans l'équipe.",
            )

    # ── Upsert du roster ──────────────────────────────────────────────────────
    user = db.query(User).filter(User.id == int(payload.user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
    if roster:
        roster.players = players
        roster.coach_id = payload.coach_id
        roster.current_formation = payload.formation
        roster.remaining_budget = round(100.0 - total_prix, 2)
    else:
        roster = FantasyRoster(
            user_id=user.id,
            coach_id=payload.coach_id,
            current_formation=payload.formation,
            remaining_budget=round(100.0 - total_prix, 2),
        )
        roster.players = players
        db.add(roster)

    db.commit()
    return {
        "status": "saved",
        "player_count": len(players),
        "remaining_budget": round(100.0 - total_prix, 2),
        "formation": payload.formation,
    }


@app.get("/fantasy/roster/{user_id}")
async def get_roster(
    user_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """Retourne le roster complet d'un utilisateur avec les stats et points."""
    roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user_id).first()

    if not roster:
        return {"players": [], "coach": None, "formation": "4-3-3", "remaining_budget": 100.0}

    players_data = [
        {
            "id": p.id,
            "name": p.name,
            "position": p.position,
            "nationality": p.nationality,
            "price": p.price,
            "goals": p.goals,
            "assists": p.assists,
            "points_total": p.points_total,
        }
        for p in roster.players
    ]

    coach_data = None
    if roster.coach:
        coach_data = {
            "id": roster.coach.id,
            "name": roster.coach.name,
            "nationality": roster.coach.nationality,
            "price": roster.coach.price,
            "points_total": roster.coach.points_total,
        }

    return {
        "players": players_data,
        "coach": coach_data,
        "formation": roster.current_formation,
        "remaining_budget": roster.remaining_budget,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  AUTO-FILL — Remplissage automatique intelligent
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/fantasy/autofill")
async def autofill_roster(
    budget: float = 100.0,
    formation: str = "4-3-3",
    db: Session = Depends(get_db),
):
    """
    Génère automatiquement une équipe de 15 joueurs + 1 entraîneur
    en respectant TOUTES les contraintes :
      - Budget ≤ 100M
      - Max 3 joueurs par nationalité
      - Entraîneur sans conflit de nationalité
      - 15 joueurs (selon la formation + 4 remplaçants)

    Stratégie : sélection greedy par rapport points/prix décroissant.
    """
    formation_slots = FORMATION_SLOTS.get(formation, FORMATION_SLOTS["4-3-3"])

    all_players = db.query(Player).filter(Player.price <= budget).order_by(
        (Player.points_total / Player.price).desc()  # Meilleur ratio points/prix
    ).all()

    selected = []
    budget_restant = budget
    nat_count: dict[str, int] = {}
    slots_restants = dict(formation_slots)
    # 4 remplaçants (1G, 1D, 1M, 1A)
    bench_slots = {"G": 1, "D": 1, "M": 1, "A": 1}

    # Combiner titulaires + banc
    total_slots = {pos: slots_restants.get(pos, 0) + bench_slots.get(pos, 0)
                   for pos in ["G", "D", "M", "A"]}

    for joueur in all_players:
        if len(selected) >= 15:
            break
        if total_slots.get(joueur.position, 0) <= 0:
            continue
        if joueur.price > budget_restant:
            continue
        if nat_count.get(joueur.nationality, 0) >= 3:
            continue

        selected.append(joueur)
        budget_restant -= joueur.price
        nat_count[joueur.nationality] = nat_count.get(joueur.nationality, 0) + 1
        total_slots[joueur.position] -= 1

    # Sélection de l'entraîneur : meilleur points_total sans conflit nationalité
    selected_nationalities = {p.nationality for p in selected}
    all_coaches = db.query(Coach).order_by(Coach.points_total.desc()).all()
    selected_coach = None
    for coach in all_coaches:
        if coach.nationality not in selected_nationalities and coach.price <= budget_restant:
            selected_coach = coach
            budget_restant -= coach.price
            break

    return {
        "players": [
            {
                "id": p.id, "name": p.name, "position": p.position,
                "nationality": p.nationality, "price": p.price,
                "points_total": p.points_total,
            }
            for p in selected
        ],
        "coach": {
            "id": selected_coach.id, "name": selected_coach.name,
            "nationality": selected_coach.nationality, "price": selected_coach.price,
        } if selected_coach else None,
        "total_price": round(budget - budget_restant, 2),
        "remaining_budget": round(budget_restant, 2),
        "formation": formation,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — Recalcul manuel
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/admin/recalculate")
async def manual_recalculate(
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_supabase_token),
):
    """
    Recalcul complet de TOUS les scores de TOUS les utilisateurs.
    À utiliser après une correction manuelle de données.
    """
    users = db.query(User).all()
    updated = 0

    for user in users:
        roster = db.query(FantasyRoster).filter(FantasyRoster.user_id == user.id).first()
        if roster:
            fantasy_pts = sum(p.points_total for p in roster.players)
            if roster.coach:
                fantasy_pts += roster.coach.points_total
            user.score_fantasy = fantasy_pts

        prono_pts = (
            db.query(PredictionScore)
            .filter(PredictionScore.user_id == user.id)
            .all()
        )
        user.score_predictor_scores = sum(p.points_earned for p in prono_pts)
        updated += 1

    db.commit()
    logger.info(f"🔁 Recalcul admin : {updated} utilisateurs mis à jour")
    return {"status": "recalculated", "users_updated": updated}


# ══════════════════════════════════════════════════════════════════════════════
#  DONNÉES STATIQUES — Référentiel CDM 2026
# ══════════════════════════════════════════════════════════════════════════════

FORMATION_SLOTS = {
    "4-3-3":  {"G": 1, "D": 4, "M": 3, "A": 3},
    "4-4-2":  {"G": 1, "D": 4, "M": 4, "A": 2},
    "3-5-2":  {"G": 1, "D": 3, "M": 5, "A": 2},
    "4-2-3-1":{"G": 1, "D": 4, "M": 5, "A": 1},
    "5-3-2":  {"G": 1, "D": 5, "M": 3, "A": 2},
}

EQUIPES_CDM_2026 = [
    # Groupe A (USA/Canada/Mexique)
    "USA", "Canada", "Mexique",
    # Groupes confirmés
    "France", "Brésil", "Argentine", "Angleterre", "Allemagne",
    "Espagne", "Portugal", "Pays-Bas", "Belgique", "Maroc",
    "Sénégal", "Japon", "Corée du Sud", "Australie", "Algérie",
    "Tunisie", "Égypte", "Nigeria", "Côte d'Ivoire",
    "Uruguay", "Colombie", "Équateur",
    "Pologne", "Croatie", "Serbie", "Suisse", "Autriche",
    "Turquie", "Grèce", "Slovaquie",
    "Iran", "Arabie Saoudite", "Japon",
    "Nouvelle-Zélande",
]

COACHES_CDM_2026_DATA = [
    {"id": 1,  "name": "Didier Deschamps",     "nationality": "Français",     "price": 8.0, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 2,  "name": "Lionel Scaloni",        "nationality": "Argentin",     "price": 9.0, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 3,  "name": "Luís Enrique",          "nationality": "Espagnol",     "price": 7.5, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 4,  "name": "Gareth Southgate",      "nationality": "Anglais",      "price": 7.0, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 5,  "name": "Julian Nagelsmann",     "nationality": "Allemand",     "price": 7.5, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 6,  "name": "Roberto Martinez",      "nationality": "Espagnol",     "price": 6.5, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 7,  "name": "Dorival Júnior",        "nationality": "Brésilien",    "price": 8.5, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 8,  "name": "Roberto De Zerbi",      "nationality": "Italien",      "price": 7.0, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 9,  "name": "Walid Regragui",        "nationality": "Marocain",     "price": 7.0, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 10, "name": "Aliou Cissé",           "nationality": "Sénégalais",   "price": 6.0, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 11, "name": "Vahid Halilhodžić",     "nationality": "Bosnien",      "price": 5.5, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
    {"id": 12, "name": "Hajime Moriyasu",       "nationality": "Japonais",     "price": 6.0, "wins": 0, "losses": 0, "points_total": 0, "status": "present"},
]

# Matchs CDM 2026 — Phase de poules (données préliminaires)
# Structure complète à alimenter avec le scraper avant le tournoi
MATCHS_CDM_2026 = [
    {"id": 1,  "home": "USA",       "away": "Canada",    "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 2,  "home": "Mexique",   "away": "Pérou",     "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 3,  "home": "France",    "away": "Belgique",  "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 4,  "home": "Angleterre","away": "Espagne",   "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 5,  "home": "Brésil",    "away": "Argentine", "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 6,  "home": "Allemagne", "away": "Portugal",  "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 7,  "home": "Maroc",     "away": "Sénégal",   "group": "Groupe D", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 8,  "home": "Algérie",   "away": "Tunisie",   "group": "Groupe D", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 9,  "home": "Japon",     "away": "Corée",     "group": "Groupe E", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 10, "home": "Pays-Bas",  "away": "Croatie",   "group": "Groupe E", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 11, "home": "Uruguay",   "away": "Colombie",  "group": "Groupe F", "date": "2026-06-16", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    {"id": 12, "home": "Pologne",   "away": "Suisse",    "group": "Groupe F", "date": "2026-06-16", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
]