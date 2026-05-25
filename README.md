# ⚽ Fantasy Gaming WC 2026

Application web Full-Stack pour gérer un **Fantasy League personnalisé** de la Coupe du Monde 2026, avec pronostics de scores et de tableau final.

---

## 🗂️ Structure du projet

```
fantasy-gaming-wc2026/
├── backend/
│   ├── app/
│   │   ├── __init__.py       ← Package Python
│   │   ├── database.py       ← Connexion SQLAlchemy (SQLite local / PostgreSQL prod)
│   │   ├── models.py         ← Schémas BDD (Joueurs, Entraîneurs, Pronostics...)
│   │   ├── rules_engine.py   ← Calcul des points selon les règles personnalisées
│   │   ├── scraper.py        ← Récupération des scores (FBref / API-Football)
│   │   └── main.py           ← Endpoints FastAPI
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css
        ├── config.js             ← URL du backend
        ├── components/
        │   ├── PlayerCard.jsx    ← Carte joueur sélectionnable
        │   └── FootballPitch.jsx ← Terrain interactif
        └── views/
            ├── Dashboard.jsx     ← Accueil + Top 5
            ├── MyTeam.jsx        ← Constructeur d'équipe Fantasy
            ├── Predictions.jsx   ← Pronostics scores & bracket
            └── Leaderboard.jsx   ← Classements
```

---

## 🚀 Installation & Lancement

### Backend (FastAPI + Python)

```bash
cd backend

# 1. Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate          # Windows

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer le serveur (port 8000)
uvicorn app.main:app --reload
```

L'API sera disponible sur : http://localhost:8000
Documentation Swagger : http://localhost:8000/docs

---

### Frontend (React + Vite)

```bash
cd frontend

# 1. Installer les dépendances
npm install

# 2. Lancer en mode développement (port 5173)
npm run dev
```

L'interface sera disponible sur : http://localhost:5173

---

## 🌐 Déploiement en production

### Backend sur Render.com
1. Crée un nouveau service **Web Service** sur Render
2. Pointe sur le dossier `backend/`
3. Commande de démarrage : `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Ajoute la variable d'environnement `DATABASE_URL` avec l'URL PostgreSQL de Render

### Frontend sur Vercel ou Netlify
1. Crée un nouveau projet, pointe sur le dossier `frontend/`
2. Build command : `npm run build`
3. Output directory : `dist`
4. Ajoute la variable d'environnement `VITE_API_BASE` avec l'URL de ton backend Render

---

## 🧮 Règles des points

### Joueurs

| Action                    | G  | D  | M  | A  |
|---------------------------|----|----|----|----|
| Match complet (≥ 90 min)  | +2 | +2 | +2 | +2 |
| Entré ou sorti avant 90e  | +1 | +1 | +1 | +1 |
| But marqué                | +8 | +6 | +5 | +4 |
| Passe décisive            | +6 | +5 | +4 | +4 |
| Clean Sheet               | +5 | +4 | +1 | —  |
| 3 parades                 | +3 | —  | —  | —  |
| 5 récupérations           | +3 | +3 | +3 | —  |
| Carton jaune              | -1 | -1 | -1 | -1 |
| Carton rouge              | -2 | -2 | -2 | -2 |

### Entraîneur

| Action                         | Points          |
|--------------------------------|-----------------|
| Présent sur le banc            | +1              |
| Victoire                       | +2              |
| Victoire avec 2+ buts d'écart  | +3 par tranche de 2 buts |
| Défaite                        | -2              |
| Défaite avec 2+ buts d'écart   | -3 par tranche de 2 buts |
| But d'un remplaçant entré      | +3              |
| Passe déc. d'un remplaçant     | +2              |
| Carton jaune                   | -1              |
| Carton rouge                   | -2              |
| Suspendu                       | 0 (aucun point) |

---

## 🔧 Configuration

Édite `frontend/src/config.js` pour changer l'URL du backend :
```js
export const API_BASE = "https://ton-backend.onrender.com";
```

Crée un fichier `.env` dans `backend/` pour la production :
```env
DATABASE_URL=postgresql://user:password@host/dbname
```
