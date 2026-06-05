"""
admin_services.py — Services admin pour injection de données
=============================================================
v2.0 — Utilise le moteur IA unifié (Groq + Gemini) depuis scraper.py
"""

import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("admin_services")

# Import du moteur IA unifié (sera maintenant géré par ai_service)
# L'IA est maintenant centralisée dans ai_service.py
# La logique de _call_ai_sync n'est plus pertinente ici car toutes les opérations AI
# passent par ai_service et sont appelées de manière asynchrone par les routes Fastapi.

# ════════════════════════════════════════════════════════════════════════
#  FONCTIONS PUBLIQUES (précédemment parse_*, maintenant pour l'injection DB)
# ════════════════════════════════════════════════════════════════════════

# Toutes les fonctions de parsing IA sont déplacées vers ai_service.py
# Ce fichier se concentrera sur la logique d'injection en base de données
# (Phase 3 du plan).
