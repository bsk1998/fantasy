# Application mobile publique

Pour que tes amis utilisent l'application sans etre sur le meme Wi-Fi, il faut une URL publique. Une adresse `localhost` ou `192.168.x.x` marche seulement sur ton PC ou ton Wi-Fi.

## Option recommandee : PWA installable Android

1. Deployer le backend sur Render avec le dossier `backend/`.
   - Build command : `pip install -r requirements.txt`
   - Start command : `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Variables : voir `backend/.env.production.example`

2. Copier l'URL Render du backend, par exemple :
   `https://fantasy-boulzazen-api.onrender.com`

3. Deployer le frontend sur Vercel avec le dossier `frontend/`.
   - Build command : `npm run build`
   - Output directory : `dist`
   - Variable : `VITE_API_BASE=https://fantasy-boulzazen-api.onrender.com`

4. Mettre dans Render :
   `ALLOWED_ORIGINS=https://votre-frontend.vercel.app`

5. Envoyer l'URL Vercel aux amis.
   Ils ouvrent le lien, entrent juste un pseudo, puis jouent directement.
   Sur Android : ouvrir dans Chrome, menu, puis `Ajouter a l'ecran d'accueil`.

Le projet contient deja `manifest.webmanifest`, `icon.svg` et `vercel.json`, donc Android affichera l'application comme une app installee. Le mode invite garde la session sur le telephone : au prochain clic, le joueur revient directement dans l'app.

## APK plus tard

Un APK Android est possible apres avoir une URL publique stable. Le plus simple est de generer un APK/TWA avec PWABuilder a partir de l'URL Vercel.
