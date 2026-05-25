from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, JSON, Table
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# Table d'association pour les ligues privées entre amis
user_league = Table(
    'user_league', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('league_id', Integer, ForeignKey('leagues.id'))
)

# Table d'association pour l'équipe Fantasy de 15 joueurs + 1 entraîneur
roster_player = Table(
    'roster_player', Base.metadata,
    Column('roster_id', Integer, ForeignKey('fantasy_rosters.id')),
    Column('player_id', Integer, ForeignKey('players.id')),
    Column('is_titulaire', Boolean, default=True)
)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # Scores cumulés pour les 3 types de jeux
    score_fantasy = Column(Integer, default=0)
    score_predictor_scores = Column(Integer, default=0)
    score_predictor_tableaux = Column(Integer, default=0)
    score_top_individuel = Column(Integer, default=0)

    roster = relationship("FantasyRoster", uselist=False, back_populates="owner")
    predictions_scores = relationship("PredictionScore", back_populates="user")
    prediction_tableau = relationship("PredictionTableau", uselist=False, back_populates="user")

class League(Base):
    __tablename__ = 'leagues'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    invite_code = Column(String, unique=True)
    users = relationship("User", secondary=user_league)

class TeamNation(Base):
    """
    Nouvelle table permettant de suivre le statut de validation de la liste
    de chaque pays (Ex: France: 'officielle', Algérie: 'provisoire')
    """
    __tablename__ = 'team_nations'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)  # Nom du pays
    group = Column(String)  # Groupe (A, B, C...)
    squad_status = Column(String, default="provisoire")  # 'provisoire' ou 'officielle'
    last_updated = Column(String)  # Date de dernière vérification

class Player(Base):
    __tablename__ = 'players'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)  # 'G', 'D', 'M', 'A'
    nationality = Column(String, index=True)
    price = Column(Float)
    
    # SYSTEME DE VERIFICATION : Indique si le joueur est confirmé dans les 26 officiels
    is_confirmed = Column(Boolean, default=False)
    
    # Statistiques réelles accumulées pendant le tournoi
    minutes_played = Column(Integer, default=0)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    clean_sheets = Column(Boolean, default=False)
    saves = Column(Integer, default=0)
    ball_recoveries = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    points_total = Column(Integer, default=0)

class Coach(Base):
    __tablename__ = 'coaches'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    nationality = Column(String)
    price = Column(Float, default=5.0)
    is_confirmed = Column(Boolean, default=False) # Entraîneur confirmé ou non
    
    # Stats réelles de l'entraîneur
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_diff_bonus = Column(Integer, default=0)
    sub_goals = Column(Integer, default=0)
    sub_assists = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    status = Column(String, default="present")
    points_total = Column(Integer, default=0)

class FantasyRoster(Base):
    __tablename__ = 'fantasy_rosters'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    coach_id = Column(Integer, ForeignKey('coaches.id'), nullable=True)
    current_formation = Column(String, default="4-3-3")
    remaining_budget = Column(Float, default=100.0)

    owner = relationship("User", back_populates="roster")
    players = relationship("Player", secondary=roster_player)
    coach = relationship("Coach")

class PredictionScore(Base):
    __tablename__ = 'prediction_scores'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    match_id = Column(Integer)
    predicted_home_score = Column(Integer)
    predicted_away_score = Column(Integer)
    points_earned = Column(Integer, default=0)

    user = relationship("User", back_populates="predictions_scores")

class PredictionTableau(Base):
    __tablename__ = 'prediction_tableaux'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    bracket_data = Column(JSON)
    points_earned = Column(Integer, default=0)

    user = relationship("User", back_populates="prediction_tableau")