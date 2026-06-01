"""
admin_models.py — Modèles pour l'administration
================================================
Étend les modèles existants avec des champs supplémentaires.
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from datetime import datetime
from app.models import Base


class AdminLog(Base):
    """Logs des actions admin."""
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String, nullable=False)  # "add_team", "edit_player", etc.
    target_type = Column(String, nullable=False)  # "team", "player", "coach", "match", "rule"
    target_id = Column(String, nullable=True)
    details = Column(Text, nullable=True)  # JSON ou description
    admin_user = Column(String, default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AdminLog {self.action} on {self.target_type}>"


class AdminPricingTemplate(Base):
    """Template de prix pour les joueurs (par position et performance)."""
    __tablename__ = "admin_pricing_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position = Column(String, nullable=False)  # G, D, M, A
    base_price = Column(Float, default=6.0)
    
    # Ajustements selon performance
    adjustment_for_tier = Column(String, nullable=True)  # "elite", "strong", "regular", "emerging"
    adjusted_price = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PricingTemplate {self.position} : {self.base_price}>"


class AdminGameRule(Base):
    """Règles du jeu (barème fantasy, bonus/malus)."""
    __tablename__ = "admin_game_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String, unique=True, nullable=False)  # "full_match_bonus", "goal", "yellow_card", etc.
    description = Column(String, nullable=True)
    position_affected = Column(String, nullable=True)  # "G|D|M|A" ou "ALL"
    points_value = Column(Integer, nullable=False)  # Ex: +4 pour un but
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Rule {self.rule_name} : {self.points_value}pt>"


class AdminTournamentConfig(Base):
    """Configuration du tournoi."""
    __tablename__ = "admin_tournament_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tournament_name = Column(String, default="World Cup 2026")
    start_date = Column(String, nullable=True)  # YYYY-MM-DD
    end_date = Column(String, nullable=True)
    
    # Source externe (URL ou description)
    external_data_source = Column(String, nullable=True)  # URL ou "manual_input"
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<TournamentConfig {self.tournament_name}>"