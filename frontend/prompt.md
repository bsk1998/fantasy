Chantier 1 — Import depuis olympics.com
Étape 1.1 — Créer un scraper Python dans backend/app/scraper.py avec httpx + BeautifulSoup qui récupère les joueurs et entraîneurs depuis l'URL olympics.com.
Étape 1.2 — Ajouter un endpoint dans admin_routes.py :
pythonPOST /api/admin/squads/import-from-olympics
Qui lance le scraper, parse les données, et les insère en base avec un flag source = "olympics".
Étape 1.3 — Ajouter un bouton "Importer depuis olympics.com" dans AdminPanel.jsx avec un retour visuel (spinner + rapport d'import).

Chantier 2 — Édition manuelle
Étape 2.1 — Ajouter 2 endpoints :
pythonPATCH /api/admin/players/{id}   # nom, poste, prix, nation
PATCH /api/admin/coaches/{id}   # nom, prix, nation
Étape 2.2 — Dans AdminPanel.jsx, transformer le tableau des effectifs en table éditable inline (double-clic = champ input, Entrée = sauvegarde).

Chantier 3 — Fix IA + calcul des points
Étape 3.1 (priorité absolue) — Déboguer Gemini :
Dans le fichier qui initialise ai_service, vérifie qu'il lit bien la variable :
pythongemini_api_key = os.getenv("GEMINI_API_KEY")
Et que GEMINI_API_KEY dans ton .env est sans espaces autour du =. Teste avec :
bashcd backend && python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GEMINI_API_KEY')[:10])"
Étape 3.2 — Créer une fonction fetch_sofascore_stats(match_id) qui utilise l'API SofaScore ou un scraper pour récupérer les stats d'un match (buts, passes, cartons, minutes jouées).
Étape 3.3 — Créer calculate_fantasy_points(player_stats, rules) appelé par Groq/Gemini avec les stats et les règles de ton jeu.
Étape 3.4 — Endpoint de recalcul :
pythonPOST /api/admin/points/recalculate   # recalcule tout
PATCH /api/admin/points/{player_id}  # override manuel admin
Étape 3.5 — Scheduler (APScheduler ou cron) qui déclenche le recalcul automatiquement après chaque match du tournoi.


voilà où on sait arreter :
- chantier 1 normalemnt est fini, et je ne peux pas importer depuis le site.