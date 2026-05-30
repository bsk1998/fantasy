# 🎮 Fantasy Boulzazen WC 2026 — Démarrage ULTRA rapide

> Application Fantasy League complète pour la Coupe du Monde 2026  
> **Démarrage en 1 clic** — Pas besoin de terminal !

---

## 🚀 Lancer l'application

### 📌 Windows
**Double-cliquez sur :** `OUVRIR-APPLICATION.bat`

```batch
OUVRIR-APPLICATION.bat
```

### 🍎 macOS / 🐧 Linux
**Ouvrez un terminal et exécutez :**

```bash
bash run.sh
```

### 🐍 Tous les OS (Python)
```bash
python run.py
```

---

## ✨ Ce qui se passe automatiquement

✅ **Vérifie** Python 3.9+ et Node.js 16+  
✅ **Crée** le virtualenv Python  
✅ **Installe** les dépendances (pip + npm)  
✅ **Génère** les fichiers `.env` manquants  
✅ **Démarre** le backend FastAPI (port 8000)  
✅ **Démarre** le frontend Vite (port 5173)  
✅ **Ouvre** automatiquement le navigateur  

**Durée totale :** ~30-60 secondes selon votre connexion internet

---

## 🌐 Accès immédiat

Une fois le launcher terminé, vous accédez à :

| Service | URL | Description |
|---------|-----|-------------|
| **Application Web** | http://localhost:5173 | Interface Fantasy complète |
| **Backend API** | http://localhost:8000 | API REST FastAPI |
| **API Documentation** | http://localhost:8000/docs | Swagger UI interactive |
| **Health Check** | http://localhost:8000/health | État du système |

### Ouvrir sur un telephone Android

1. Lancez `run.bat` sur le PC.
2. Gardez les fenetres ouvertes.
3. Connectez le telephone Android au meme Wi-Fi que le PC.
4. Ouvrez l'adresse affichee dans la console, par exemple `http://192.168.1.20:5173`.
5. Dans Chrome Android, menu puis `Ajouter a l'ecran d'accueil` pour avoir un raccourci.

Si l'adresse Android ne s'ouvre pas, autorisez Python/Node.js dans le pare-feu Windows pour les reseaux prives.

Pour que des amis jouent sans etre sur le meme Wi-Fi, utilisez le guide [MOBILE-PUBLIC.md](MOBILE-PUBLIC.md). Il faut deployer le backend sur Internet et envoyer l'URL publique du frontend aux joueurs.

---

## 🎮 Première utilisation

1. **Connectez-vous** avec un email (Supabase mock en dev)
2. **Créez votre équipe** : sélectionnez 15 joueurs + 1 entraîneur
3. **Pronostiques** : prédisez les scores des matchs
4. **Tableau** : complétez l'arbre du tournoi
5. **Classement** : suivez votre position en temps réel

---

## ⚙️ Configuration optionnelle

### Variables d'environnement importantes

**Backend** (`backend/.env`) :
```env
# Base de données
DATABASE_URL=sqlite:///./fantasy_wc2026.db

# Authentification Supabase (optionnel en dev)
SUPABASE_JWT_SECRET=dev-secret-key-for-development-only

# IA Groq pour scraping (optionnel)
GROQ_API_KEY=

# CORS
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

**Frontend** (`frontend/.env`) :
```env
# Backend API
VITE_API_BASE=http://localhost:8000

# Supabase (optionnel)
VITE_SUPABASE_URL=https://example.supabase.co
VITE_SUPABASE_ANON_KEY=example-anon-key
```

---

## ❓ Dépannage

### ❌ "Python not found"
→ Installez Python 3.9+ : https://python.org

### ❌ "Node.js not found"  
→ Installez Node.js 16+ : https://nodejs.org

### ❌ Port déjà utilisé (8000 ou 5173)
```bash
# Linux/macOS
lsof -i :8000
lsof -i :5173

# Windows
netstat -ano | findstr :8000
netstat -ano | findstr :5173
```

### ❌ Les services ne démarrent pas
Essayez manuellement dans 2 terminaux :

**Terminal 1 (Backend)** :
```bash
cd backend
source venv/bin/activate    # bash/zsh/sh
# ou
venv\Scripts\activate       # Windows

uvicorn app.main:app --reload
```

**Terminal 2 (Frontend)** :
```bash
cd frontend
npm run dev
```

### ❌ "Module not found" ou autres erreurs Python
```bash
cd backend
source venv/bin/activate       # Linux/macOS
# ou
venv\Scripts\activate          # Windows

pip install -r requirements.txt
```

---

## 📦 Prérequis (installés automatiquement)

- **Python** ≥ 3.9 : https://python.org
- **Node.js** ≥ 16 : https://nodejs.org

Les deux doivent être dans votre PATH (testé avec `python --version` et `node --version`)

---

## 🗂️ Structure du projet

```
fantasy-wc2026/
├── run.py              ← Launcher Python (tous OS)
├── run.sh              ← Launcher Bash (Linux/macOS)
├── run.bat             ← Launcher Batch (Windows)
├── QUICKSTART.md       ← Ce fichier
│
├── backend/
│   ├── app/
│   │   ├── main.py          (FastAPI)
│   │   ├── models.py        (SQLAlchemy ORM)
│   │   ├── database.py      (Connexion BDD)
│   │   ├── scraper.py       (Playwright + Groq)
│   │   ├── updater.py       (APScheduler)
│   │   └── rules_engine.py  (Calcul points)
│   ├── requirements.txt
│   ├── .env                 (Auto-généré)
│   └── .env.example         (Template)
│
└── frontend/
    ├── src/
    │   ├── main.jsx
    │   ├── App.jsx
    │   ├── views/
    │   │   ├── Dashboard.jsx
    │   │   ├── MyTeam.jsx
    │   │   ├── Predictions.jsx
    │   │   ├── Leaderboard.jsx
    │   │   └── AdminPanel.jsx
    │   └── components/
    ├── package.json
    ├── .env                 (Auto-généré)
    └── .env.example         (Template)
```

---

## 🎮 Modes de jeu

| Mode | Points | Détails |
|------|--------|----------|
| **Fantasy League** | Auto-calculé | 15 joueurs + 1 entraîneur, budget 100M€ |
| **Pronostics Scores** | +5 ou +2 | Prédire les scores exacts des matchs |
| **Tableau Tournoi** | +5 chacun | Phases éliminatoires (8èmes, quarts, etc.) |
| **Top Individuels** | Variable | Buteurs, passeurs, jeunes, joueurs |

---

## 🧮 Barème Fantasy

| Action | G | D | M | A | Notes |
|--------|---|---|---|---|-------|
| **Titulaire** (≥90 min) | +2 | +2 | +2 | +2 | Apparition minimum 90 min |
| **Remplaçant** (<90 min) | +1 | +1 | +1 | +1 | Entre 1 et 89 minutes |
| **But marqué** | +8 | +6 | +5 | +4 | Par but |
| **Passe décisive** | +6 | +5 | +4 | +4 | Par passe |
| **Clean Sheet** | +5 | +4 | +1 | — | Aucun but encaissé |
| **3 parades** | +3 | — | — | — | Gardien seulement |
| **Carton jaune** | -1 | -1 | -1 | -1 | Par carton |
| **Carton rouge** | -2 | -2 | -2 | -2 | Expulsion |

### Entraîneur
- **Présent** : +1 pt
- **Victoire** : +2 pts de base
- **+3 pts** par tranche de 2 buts d'écart (ex: victoire 4-0 = 2+6 = 8 pts)
- **But remplaçant** : +3 pts
- **Passe remplaçant** : +2 pts

---

## 🌐 Déploiement Production

### Backend → Render.com
1. Créer un **Web Service**, sélectionner le repo, dossier `backend/`
2. Commande : `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Env vars : `DATABASE_URL`, `SUPABASE_JWT_SECRET`, `GROQ_API_KEY`, `ALLOWED_ORIGINS`

### Frontend → Vercel
1. Créer un projet, sélectionner le repo, dossier `frontend/`
2. Build command : `npm run build`
3. Output directory : `dist`
4. Env var : `VITE_API_BASE` = URL du backend en production

---

## 📞 Support & Issues

- **API Documentation** : http://localhost:8000/docs (Swagger UI)
- **Health Check** : http://localhost:8000/health
- **Logs** : Consultez la sortie console du launcher

---

## 📜 Licence

MIT — Libre d'usage pour la Coupe du Monde 2026 🏆

---

## 🎯 À venir

- [ ] Scraping temps réel des matchs (Playwright + Groq)
- [ ] Mise à jour automatique des points
- [ ] Intégration Supabase en production
- [ ] Dark mode amélioré
- [ ] Push notifications

---

**Bon jeu ! ⚽🎮**

*Créé avec ❤️ pour les fans de Fantasy Football*
