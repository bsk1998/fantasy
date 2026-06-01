"""Models spécifiques au mode Admin — configuration manuelle du jeu par l'admin."""

from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, Text, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class AdminSession(Base):
    """Suivi des connexions admin — sécurité basique."""
    __tablename__ = 'admin_sessions'
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)  # JWT simple
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)


class GameRules(Base):
    """Règles du jeu — configurables par l'admin."""
    __tablename__ = 'game_rules'
    id = Column(Integer, primary_key=True, index=True)
    rule_type = Column(String, index=True)  # 'fantasy_points', 'predictor_scores', 'predictor_tableau'
    
    # Fantasy Points : scores par action joueur/coach
    # Structure JSON : {"G": {"match_complet": 2, "but": 4, ...}, ...}
    rules_data = Column(JSON, nullable=False, default={})
    
    # Métadonnées
    version = Column(Integer, default=1)  # Pour tracking des versions
    created_by = Column(String, nullable=True)  # Admin email
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class AdminLog(Base):
    """Log de toutes les actions admin — audit trail."""
    __tablename__ = 'admin_logs'
    id = Column(Integer, primary_key=True, index=True)
    admin_email = Column(String, nullable=False)
    action = Column(String)  # 'add_team', 'import_squad', 'set_coach', 'configure_rules', 'create_tournament'
    target = Column(String, nullable=True)  # Ex: 'France', 'match_id_123'
    details = Column(JSON, nullable=True)  # Détails de l'action (ancien/nouveau état)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String, default="success")  # 'success' ou 'error'
    error_message = Column(Text, nullable=True)


class TournamentMetadata(Base):
    """Métadonnées du tournoi — créé par l'admin."""
    __tablename__ = 'tournament_metadata'
    id = Column(Integer, primary_key=True, index=True)
    tournament_name = Column(String, unique=True)  # 'Coupe du Monde 2026'
    official_url = Column(String, nullable=True)  # https://www.sofascore.com/...
    source_screenshots = Column(JSON, default=[])  # Liste de URLs de captures
    groups_structure = Column(JSON, default={})  # {"Groupe A": ["France", "Belgique", ...]}
    
    # Tokens/clés si scraping manuel avec screenshots
    groq_extraction_status = Column(String, default="pending")  # 'pending', 'success', 'error'
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
