Analyse l'intégralité de mon projet React (Vite) + FastAPI et trouve la cause exacte de ces erreurs :

1. Frontend :

POST http://localhost:8000/api/admin/login

→ 404 Not Found

2. Backend :

http://localhost:8000/docs

→ "Failed to load API definition"

http://localhost:8000/openapi.json

→ 500 Internal Server Error

Le proxy Vite a déjà été corrigé (suppression du rewrite qui retirait /api), donc le problème ne vient plus du proxy.

Je veux que tu inspectes tout le backend :

- main.py

- admin_routes.py

- tous les APIRouter()

- tous les app.include_router()

- tous les modèles Pydantic/BaseModel

- tous les response_model=

- tous les Depends()

- tous les imports

Identifie précisément :

- le ou les fichiers responsables

- les lignes fautives

- pourquoi /openapi.json retourne 500

- pourquoi /api/admin/login retourne 404

- le correctif complet prêt à copier-coller

Je ne veux pas des hypothèses. Analyse le projet entier et donne la cause réelle avec le code corrigé.