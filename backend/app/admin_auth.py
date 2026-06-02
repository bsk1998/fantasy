"""
admin_auth.py — Authentification admin basique
================================================
Pseudo : admin
Mot de passe : admin00

Génère un JWT simple valide pour 24h.
"""

import os
import logging
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Optional

try:
    import jwt
    ExpiredTokenError = jwt.ExpiredSignatureError
    InvalidTokenError = jwt.InvalidTokenError
except ImportError:
    class ExpiredTokenError(Exception):
        pass

    class InvalidTokenError(Exception):
        pass

    class LocalJWT:
        @staticmethod
        def encode(payload: dict, secret: str, algorithm: str = "HS256") -> str:
            serializable = payload.copy()
            for key in ("exp", "iat"):
                if isinstance(serializable.get(key), datetime):
                    serializable[key] = int(serializable[key].timestamp())

            header = {"alg": algorithm, "typ": "JWT"}
            signing_input = ".".join([
                LocalJWT._b64url(json.dumps(header, separators=(",", ":")).encode()),
                LocalJWT._b64url(json.dumps(serializable, separators=(",", ":")).encode()),
            ])
            signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
            return f"{signing_input}.{LocalJWT._b64url(signature)}"

        @staticmethod
        def decode(token: str, secret: str, algorithms=None) -> dict:
            try:
                header_b64, payload_b64, signature_b64 = token.split(".")
            except ValueError as exc:
                raise InvalidTokenError("Token malforme") from exc

            signing_input = f"{header_b64}.{payload_b64}"
            expected = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(LocalJWT._b64url(expected), signature_b64):
                raise InvalidTokenError("Signature invalide")

            payload = json.loads(LocalJWT._b64url_decode(payload_b64))
            exp = payload.get("exp")
            if exp is not None and int(exp) < int(datetime.utcnow().timestamp()):
                raise ExpiredTokenError("Token expire")
            return payload

        @staticmethod
        def _b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        @staticmethod
        def _b64url_decode(data: str) -> bytes:
            padding = "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode(data + padding)

    jwt = LocalJWT

logger = logging.getLogger("admin_auth")

ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY", "fantasy-boulzazen-secret-2026-xyz")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin00"
ADMIN_JWT_EXPIRY_HOURS = 24


def verify_admin_credentials(username: str, password: str) -> bool:
    """Vérifie pseudo/mdp admin."""
    is_valid = username == ADMIN_USERNAME and password == ADMIN_PASSWORD
    if not is_valid:
        logger.warning(f"Tentative de connexion admin échouée pour utilisateur: '{username}'")
    else:
        logger.info(f"Connexion admin réussie pour utilisateur: '{username}'")
    return is_valid


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
    except ExpiredTokenError:
        logger.warning("Admin token expiré")
    except InvalidTokenError as e:
        logger.warning(f"Admin token invalide : {e}")
    return None


def check_admin_token(auth_header: Optional[str]) -> bool:
    """Extrait et vérifie le token du header Authorization."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    token = auth_header[7:]
    return verify_admin_token(token) is not None
