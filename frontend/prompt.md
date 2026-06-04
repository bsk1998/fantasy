agis comme le meilleur devloppeur au monde, tu me donne les fichiers complets pres à etre coller . 
je veux : 
Problème 1 — Ajout d'effectifs via prompt Groq :
Dans AdminPanel.jsx, la section SquadsSection appelle https://api.anthropic.com/v1/messages directement depuis le frontend sans clé API (et sans header x-api-key). C'est pour ça que ça ne marche pas. Il faut passer par le backend FastAPI qui utilise déjà Groq via admin_services.py.  
Dans SquadsSection, l'appel à https://api.anthropic.com/v1/messages est remplacé par un appel au backend FastAPI /api/admin/squad/parse qui utilise Groq via admin_services.py.

Problème 2 — Design du bouton de sélection avec couleur si effectif complet :
Il faut ajouter un indicateur visuel sur chaque nation chip selon si elle a un effectif complet (joueurs + entraîneur).
Les nation-chip affichent un indicateur vert (✅ + bordure verte) si la nation a un effectif complet (joueurs + entraîneur) via un état filledNations chargé depuis le backend.



il reste à : corriger : admin_routes.py a une fonction get_filled_nations en double, ce qui fera crasher FastAPI au démarrage.
