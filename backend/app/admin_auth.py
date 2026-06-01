"""Authentification admin simple et sécurisée (JWT basique)."""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
from fastapi import HTTPException, status
from jose import JWTError, jwt

logger = logging.getLogger("admin_auth")

# Credentials admin codés en dur pour démo — à remplacer par DB en production
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin00")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "super-secret-admin-key-change-in-production")
ADMIN_TOKEN_EXPIRY = int(os.getenv("ADMIN_TOKEN_EXPIRY_HOURS", "24"))  # heures


def hash_password(password: str) -> str:
    """Hash simple du mot de passe (SHA256)."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    """Vérifie le mot de passe."""
    return hash_password(plain) == hashed


def verify_admin_credentials(username: str, password: str) -> bool:
    """Vérifie les identifiants admin."""
    if username != ADMIN_USERNAME:
        logger.warning(f"❌ Tentative login admin avec username invalide : {username}")
        return False
    if password != ADMIN_PASSWORD:  # Comparaison simple pour démo
        logger.warning(f"❌ Tentative login admin avec mot de passe invalide")
        return False
    logger.info(f"✅ Admin login réussi : {username}")
    return True


def create_admin_token(username: str) -> str:
    """Crée un JWT pour l'admin."""
    payload = {
        "sub": username,
        "type": "admin",
        "exp": datetime.utcnow() + timedelta(hours=ADMIN_TOKEN_EXPIRY),
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, ADMIN_SECRET_KEY, algorithm="HS256")
    logger.info(f"✅ Token admin créé pour : {username}")
    return token


def verify_admin_token(token: str) -> Optional[str]:
    """
    Vérifie un JWT admin et retourne le username si valide.
    Retourne None si invalide ou expiré.
    """
    try:
        payload = jwt.decode(token, ADMIN_SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "admin":
            return None
        return payload.get("sub")
    except JWTError as e:
        logger.warning(f"❌ Token admin invalide : {e}")
        return None


def get_admin_from_request(authorization_header: str) -> Optional[str]:
    """
    Extrait et valide le token admin du header 'Authorization: Bearer <token>'.
    Retourne l'username si valide, None sinon.
    """
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return None
    token = authorization_header[7:]
    return verify_admin_token(token)
