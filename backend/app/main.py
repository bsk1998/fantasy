# Fichier complet : backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.scraper import recuperer_effectif_web

app = FastAPI(title="Ligue Fantasy 2026")

# Activation du CORS pour autoriser la connexion avec ton React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Liste des équipes (tout est verrouillé par défaut)
TEAMS = [
    {"name": "France", "players": [], "status": "locked"},
    {"name": "Argentine", "players": [], "status": "locked"},
    {"name": "Maroc", "players": [], "status": "locked"}
]

@app.on_event("startup")
async def initialisation_automatique():
    """Se déclenche au démarrage pour scanner le web"""
    print("🚀 Démarrage du système de synchronisation...")
    for team in TEAMS:
        effectif = recuperer_effectif_web(team["name"])
        if effectif:
            team["players"] = effectif
            team["status"] = "open"  # Déverrouillé automatiquement
            print(f"✅ {team['name']} : Déverrouillée.")
        else:
            print(f"🔒 {team['name']} : Verrouillée (Aucune donnée trouvée).")

@app.get("/players")
async def get_players():
    # Renvoie la liste agrégée de tous les joueurs disponibles
    return [p for team in TEAMS if team["status"] == "open" for p in team["players"]]

@app.get("/teams")
async def get_teams():
    # Renvoie le statut des équipes pour afficher les cadenas dans ton UI
    return TEAMS