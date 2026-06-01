from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, JSON, Table, DateTime
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

user_league = Table(
    'user_league', Base.metadata,
    Column('user_id',  Integer, ForeignKey('users.id')),
    Column('league_id',Integer, ForeignKey('leagues.id'))
)

roster_player = Table(
    'roster_player', Base.metadata,
    Column('roster_id', Integer, ForeignKey('fantasy_rosters.id')),
    Column('player_id', Integer, ForeignKey('players.id')),
    Column('is_titulaire', Boolean, default=True)
)

class User(Base):
    __tablename__ = 'users'
    id                       = Column(Integer, primary_key=True, index=True)
    username                 = Column(String, unique=True, index=True)
    email                    = Column(String, unique=True, index=True)
    hashed_password          = Column(String)
    score_fantasy            = Column(Integer, default=0)
    score_predictor_scores   = Column(Integer, default=0)
    score_predictor_tableaux = Column(Integer, default=0)
    score_top_individuel     = Column(Integer, default=0)

    roster             = relationship("FantasyRoster",  uselist=False, back_populates="owner")
    predictions_scores = relationship("PredictionScore", back_populates="user")
    prediction_tableau = relationship("PredictionTableau", uselist=False, back_populates="user")
    complaints         = relationship("Complaint", back_populates="user", foreign_keys="Complaint.user_id")
    # ✅ AJOUTÉ : back_populates pour les ligues
    leagues            = relationship("League", secondary=user_league, back_populates="members")


# ✅ CLASSE LEAGUE MISE À JOUR (version 6.0)
class League(Base):
    __tablename__ = 'leagues'
    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(50), nullable=False)
    invite_code   = Column(String(8), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)           # None = ligue publique
    created_by    = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at    = Column(String, default=lambda: datetime.utcnow().isoformat())
    is_public     = Column(Boolean, default=False)
    max_members   = Column(Integer, default=20)

    creator = relationship("User", foreign_keys=[created_by])
    members = relationship("User", secondary=user_league, back_populates="leagues")


class TeamNation(Base):
    """Représente une nation avec son effectif et statut de publication."""
    __tablename__ = 'team_nations'
    id                 = Column(Integer, primary_key=True, index=True)
    name               = Column(String, unique=True, index=True)
    group              = Column(String, nullable=True)
    squad_status       = Column(String, default="non_publiee")
    is_locked          = Column(Boolean, default=True)
    squad_published_at = Column(String, nullable=True)
    coach_name         = Column(String, nullable=True)
    last_updated       = Column(String)

    players = relationship("Player", back_populates="team")


class Player(Base):
    __tablename__ = 'players'
    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String, index=True)
    position       = Column(String)
    nationality    = Column(String, index=True)
    team_id        = Column(Integer, ForeignKey('team_nations.id'), nullable=True)
    team           = relationship("TeamNation", back_populates="players")
    price          = Column(Float, default=6.0)
    is_confirmed   = Column(Boolean, default=False)
    minutes_played = Column(Integer, default=0)
    goals          = Column(Integer, default=0)
    assists        = Column(Integer, default=0)
    clean_sheets   = Column(Integer, default=0)
    saves          = Column(Integer, default=0)
    ball_recoveries= Column(Integer, default=0)
    yellow_cards   = Column(Integer, default=0)
    red_cards      = Column(Integer, default=0)
    points_total   = Column(Integer, default=0)
    last_stat_update= Column(String, nullable=True)


class Coach(Base):
    __tablename__ = 'coaches'
    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String)
    nationality      = Column(String)
    team_name        = Column(String, unique=True)
    price            = Column(Float, default=5.0)
    is_confirmed     = Column(Boolean, default=False)
    wins             = Column(Integer, default=0)
    losses           = Column(Integer, default=0)
    goals_diff_bonus = Column(Integer, default=0)
    sub_goals        = Column(Integer, default=0)
    sub_assists      = Column(Integer, default=0)
    yellow_cards     = Column(Integer, default=0)
    red_cards        = Column(Integer, default=0)
    status           = Column(String, default="present")
    points_total     = Column(Integer, default=0)
    last_stat_update = Column(String, nullable=True)


class MatchResult(Base):
    __tablename__ = 'match_results'
    id           = Column(Integer, primary_key=True, index=True)
    sofascore_id = Column(String, unique=True, index=True)
    home         = Column(String)
    away         = Column(String)
    group        = Column(String, nullable=True)
    round        = Column(String)
    date         = Column(String)
    kickoff_utc  = Column(String)
    home_score   = Column(Integer, nullable=True)
    away_score   = Column(Integer, nullable=True)
    status       = Column(String)
    player_stats = Column(JSON, default={})
    is_locked    = Column(Boolean, default=False)
    last_updated = Column(String)


class GroupStanding(Base):
    __tablename__ = 'group_standings'
    id            = Column(Integer, primary_key=True, index=True)
    group_name    = Column(String, index=True)
    team          = Column(String)
    played        = Column(Integer, default=0)
    won           = Column(Integer, default=0)
    drawn         = Column(Integer, default=0)
    lost          = Column(Integer, default=0)
    goals_for     = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    goal_diff     = Column(Integer, default=0)
    points        = Column(Integer, default=0)
    last_updated  = Column(String)


class FantasyRoster(Base):
    __tablename__ = 'fantasy_rosters'
    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey('users.id'))
    coach_id          = Column(Integer, ForeignKey('coaches.id'), nullable=True)
    current_formation = Column(String, default="4-3-3")
    remaining_budget  = Column(Float, default=100.0)
    owner   = relationship("User",    back_populates="roster")
    players = relationship("Player",  secondary=roster_player)
    coach   = relationship("Coach")


class PredictionScore(Base):
    __tablename__ = 'prediction_scores'
    id                   = Column(Integer, primary_key=True, index=True)
    user_id              = Column(Integer, ForeignKey('users.id'))
    match_id             = Column(String)
    predicted_home_score = Column(Integer)
    predicted_away_score = Column(Integer)
    points_earned        = Column(Integer, default=0)
    is_locked            = Column(Boolean, default=False)
    user = relationship("User", back_populates="predictions_scores")


class PredictionTableau(Base):
    __tablename__ = 'prediction_tableaux'
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey('users.id'))
    bracket_data  = Column(JSON)
    points_earned = Column(Integer, default=0)
    user = relationship("User", back_populates="prediction_tableau")


class PredictionAnnexes(Base):
    __tablename__ = 'prediction_annexes'
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey('users.id'), unique=True)
    annexes_data  = Column(JSON)
    points_earned = Column(Integer, default=0)


class Complaint(Base):
    __tablename__ = 'complaints'
    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey('users.id'), nullable=False)
    match_id         = Column(String, nullable=True)
    player_id        = Column(Integer, ForeignKey('players.id'), nullable=True)
    description      = Column(String, nullable=False)
    stat_claimed     = Column(String, nullable=True)
    status           = Column(String, default="pending", nullable=False)
    ai_analysis      = Column(String, nullable=True)
    ai_verdict       = Column(String, nullable=True)
    ai_confidence    = Column(Integer, nullable=True)
    admin_note       = Column(String, nullable=True)
    corrected_stats  = Column(String, nullable=True)
    created_at       = Column(String, nullable=False)
    resolved_at      = Column(String, nullable=True)
    user   = relationship("User",   back_populates="complaints", foreign_keys=[user_id])
    player = relationship("Player", foreign_keys=[player_id])


class ScrapingMetadata(Base):
    __tablename__ = 'scraping_metadata'
    id                = Column(Integer, primary_key=True, index=True)
    source            = Column(String, unique=True)
    last_scrape_at    = Column(String)
    last_success_at   = Column(String, nullable=True)
    items_scraped     = Column(Integer, default=0)
    status            = Column(String)
    error_message     = Column(String, nullable=True)
    data_version_hash = Column(String, nullable=True)