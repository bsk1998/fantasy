# ⚽ Fantasy Gaming WC 2026 — Boulzazen

Ligue privée Fantasy + Pronostics + Tableau pour la Coupe du Monde 2026.
Design dark / UEFA Gaming / Mobile-First · React (Vite) + FastAPI + Supabase.

---

## 📋 Plan d'action exécuté

### ✅ Bugs critiques corrigés
1. **`data_wc2026.py` créé** — 48 matchs CDM 2026 + entraîneurs (11 juin au 24 juin)
2. **`updater.py` fixé** — alias `start_scheduler()`, `stop_scheduler()`, `get_scheduler_status()` ajoutés
3. **`username.js` fixé** — exports `getDisplayNameFromMeta` et `getDisplayName` ajoutés
4. **`requirements.txt` mis à jour** — `httpx==0.27.0` et `apscheduler==3.10.4` ajoutés
5. **`predictions-extra.css` créé** — tous les styles CSS manquants pour `Predictions.jsx`
6. **`supabaseClient.js` sécurisé** — lit les clés depuis `import.meta.env` (variables Vite)
7. **`config.js` mis à jour** — `ADMIN_EMAILS` à configurer avec votre vrai email

---

## 🗂️ Structure du projet

```
fantasy-wc2026/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── data_wc2026.py    ← ✅ CRÉÉ (48 matchs CDM + entraîneurs)
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── rules_engine.py
│   │   ├── scraper.py
│   │   └── updater.py        ← ✅ FIXÉ (alias start/stop/status)
│   ├── .env.example          ← ✅ CRÉÉ (template config)
│   └── requirements.txt      ← ✅ MIS À JOUR (httpx + apscheduler)
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── .env.example           ← ✅ CRÉÉ (template config)
    └── src/
        ├── main.jsx           ← ✅ FIXÉ (importe predictions-extra.css)
        ├── App.jsx
        ├── index.css
        ├── predictions-extra.css  ← ✅ CRÉÉ (CSS manquants)
        ├── config.js          ← ✅ FIXÉ (ADMIN_EMAILS à configurer)
        ├── supabaseClient.js  ← ✅ FIXÉ (variables d'env sécurisées)
        ├── components/
        │   ├── FootballPitch.jsx
        │   └── PlayerCard.jsx
        ├── utils/
        │   └── username.js    ← ✅ FIXÉ (exports manquants ajoutés)
        └── views/
            ├── AdminPanel.jsx
            ├── Complaints.jsx
            ├── Dashboard.jsx
            ├── Leaderboard.jsx
            ├── MyTeam.jsx
            └── Predictions.jsx
```

---

## 🚀 Installation & Lancement

### Étape 1 — Configuration (5 min)

```bash
# Backend
cp backend/.env.example backend/.env
# → Éditer backend/.env : mettre SUPABASE_JWT_SECRET et GROQ_API_KEY

# Frontend  
cp frontend/.env.example frontend/.env
# → Les clés Supabase sont déjà pré-remplies dans .env.example
```

### Étape 2 — Backend (Python ≥ 3.10)

```bash
cd backend

# Créer le venv
python -m venv venv
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate          # Windows

# Installer les dépendances (httpx + apscheduler inclus)
pip install -r requirements.txt

# Lancer
uvicorn app.main:app --reload
```

API disponible sur http://localhost:8000  
Documentation Swagger : http://localhost:8000/docs  
Health check : http://localhost:8000/health

### Étape 3 — Frontend (Node ≥ 18)

```bash
cd frontend
npm install
npm run dev
```

Interface sur http://localhost:5173

---

## ⚙️ Configuration ADMIN_EMAILS

Dans `frontend/src/config.js`, remplacer `admin@boulzazen.local` par votre vrai email :

```js
export const ADMIN_EMAILS = [
  "votre_email@gmail.com",
];
```

---

## 🎮 Modes de jeu

| Mode | Description | Points |
|------|-------------|--------|
| **Fantasy League** | 15 joueurs + 1 entraîneur, budget 100M | Calcul automatique |
| **Pronostics Scores** | Score exact de chaque match | +5 / +2 / 0 |
| **Tableau Tournoi** | Arbre complet CDM 2026 | +5 par bonne prédiction |
| **Prédictions Annexes** | Top 3 buteurs/passeurs/joueurs/jeunes | Défini en fin de tournoi |

---

## 🧮 Barème Fantasy

| Action | G | D | M | A |
|--------|---|---|---|---|
| Match complet (≥90 min) | +2 | +2 | +2 | +2 |
| Joue <90 min | +1 | +1 | +1 | +1 |
| But | +8 | +6 | +5 | +4 |
| Passe déc. | +6 | +5 | +4 | +4 |
| Clean Sheet | +5 | +4 | +1 | — |
| 3 parades | +3 | — | — | — |
| 5 récupérations | +3 | +3 | +3 | — |
| Carton jaune | -1 | -1 | -1 | -1 |
| Carton rouge | -2 | -2 | -2 | -2 |

### Entraîneur
- Présent sur le banc : **+1 pt**
- Victoire : **+2 pts** de base
- +3 pts par tranche de 2 buts d'écart (ex: 4-0 = +2+6 = 8 pts)
- Défaite : logique inverse (-2, -3 par tranche)
- But d'un remplaçant : **+3 pts** | Passe déc. d'un remplaçant : **+2 pts**

---

## 🌐 Déploiement Production

### Backend → Render.com
1. Nouveau service Web Service, dossier `backend/`
2. Commande : `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Variables d'environnement : `DATABASE_URL`, `SUPABASE_JWT_SECRET`, `GROQ_API_KEY`, `ALLOWED_ORIGINS`

### Frontend → Vercel
1. Nouveau projet, dossier `frontend/`
2. Build command : `npm run build` | Output : `dist`
3. Variables d'environnement : `VITE_API_BASE` (URL du backend Render)