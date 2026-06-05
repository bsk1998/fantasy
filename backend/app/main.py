"""
Patch à appliquer dans main.py — Remplacer UNIQUEMENT la route /api/scraping/status
Cherche : @app.get("/api/scraping/status")
Remplace tout le bloc jusqu'au return par ce qui suit.
"""

# ─── COLLER CE BLOC EN REMPLACEMENT DE @app.get("/api/scraping/status") ──────

SCRAPING_STATUS_ROUTE = '''
@app.get("/api/scraping/status")
async def scraping_status():
    """Statut des moteurs IA et de la base de données."""
    status_data = {}
    if SCRAPER_AVAILABLE:
        try:
            status_data = get_scraping_status()
        except Exception:
            pass

    mem_matchs = 0
    if UPDATER_AVAILABLE:
        try:
            mem_matchs = len(get_matchs_actuels())
        except Exception:
            pass

    db_matchs, db_coaches, db_players = 0, 0, 0
    if DB_AVAILABLE:
        db = None
        try:
            db = SessionLocal()
            db_matchs  = db.execute(text("SELECT COUNT(*) FROM match_results")).scalar() or 0
            db_coaches = db.query(Coach).count()
            db_players = db.query(Player).count()
        except Exception:
            pass
        finally:
            if db:
                db.close()

    return {
        # Données moteur IA
        "sources":             status_data,
        "groq_configure":      status_data.get("groq_configure",   bool(os.getenv("GROQ_API_KEY"))),
        "gemini_configure":    status_data.get("gemini_configure",  bool(os.getenv("GEMINI_API_KEY"))),
        "ai_provider":         status_data.get("ai_provider",      os.getenv("AI_PROVIDER", "auto")),
        "active_model":        status_data.get("active_model",     "—"),
        # Données BDD
        "matchs_memoire":      mem_matchs,
        "matchs_db":           db_matchs,
        "coaches_db":          db_coaches,
        "players_db":          db_players,
        # Flags modules
        "groq_installed":      SCRAPER_AVAILABLE,
        "admin_installed":     ADMIN_AVAILABLE,
        "updater_installed":   UPDATER_AVAILABLE,
        "db_available":        DB_AVAILABLE,
    }
'''