"""
admin_auth.py — Authentification admin basique
================================================
Pseudo : admin
Mot de passe : admin00

Génère un JWT simple valide pour 24h.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import jwt

logger = logging.getLogger("admin_auth")

ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY", "fantasy-boulzazen-secret-2026-xyz")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin00"
ADMIN_JWT_EXPIRY_HOURS = 24


def verify_admin_credentials(username: str, password: str) -> bool:
    """Vérifie pseudo/mdp admin."""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def generate_admin_token(username: str) -> str:
    """Génère un JWT valide 24h."""
    payload = {
        "sub": username,
        "type": "admin",
        "exp": datetime.utcnow() + timedelta(hours=ADMIN_JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, ADMIN_SECRET, algorithm="HS256")


def verify_admin_token(token: str) -> Optional[dict]:
    """Vérifie et décode le JWT. Retourne le payload ou None."""
    try:
        payload = jwt.decode(token, ADMIN_SECRET, algorithms=["HS256"])
        if payload.get("type") == "admin":
            return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Admin token expiré")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Admin token invalide : {e}")
    return None


def check_admin_token(auth_header: Optional[str]) -> bool:
    """Extrait et vérifie le token du header Authorization."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    token = auth_header[7:]
    return verify_admin_token(token) is not None