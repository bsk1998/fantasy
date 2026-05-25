from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# ─── Configuration de la connexion ────────────────────────────────────────────
# Par défaut : SQLite local pour le développement
# En production (Render.com), remplace DATABASE_URL par l'URL PostgreSQL fournie
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./fantasy_wc2026.db"
)

# Correction nécessaire pour PostgreSQL sur Render (préfixe postgres:// → postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ─── Moteur SQLAlchemy ────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

# ─── Session Factory ──────────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ─── Dépendance FastAPI ───────────────────────────────────────────────────────
def get_db():
    """Générateur de session à injecter dans les endpoints FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
