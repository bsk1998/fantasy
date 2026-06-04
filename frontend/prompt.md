agis comme le meilleur devloppeur au monde, tu me donne les fichiers complets pres à etre coller . 
je veux : 
- regle le probleme de cle api dans le frotend car sa m'affiche que aucune cle api est disponible Problem 1 - API Key in frontend:
Looking at frontend/src/views/AdminPanel.jsx, in SettingsSection, there's a Groq key management. The issue mentioned in the previous frontend/prompt.md was that SquadsSection was calling https://api.anthropic.com/v1/messages directly. But that was already fixed in the current AdminPanel.jsx. However, looking at the current code in SettingsSection, the groqKey is stored in localStorage via getStoredGroqKey(). The problem "aucune clé API est disponible" - this could mean:

The GROQ_API_KEY in the backend .env is empty
The frontend is showing "no API key available" somewhere

Wait, looking more carefully - in frontend/src/config.js:
jsexport const GROQ_API_KEY = import.meta.env.VITE_GROQ_API_KEY || "";
And in the .env.production.example:
VITE_GROQ_API_KEY=
The issue is probably that when the admin tries to use Groq features, it shows "no API key available". Looking at ToolsSection:
js{!groqKey&&<p style={{fontSize:".72rem",color:"var(--red)",marginTop:8}}>⚠ Clé Groq requise (configurée dans le backend .env)</p>}
And in SquadsSection, the groqKey is passed as prop but the actual parsing goes through the backend now. The groqKey in AdminPanel comes from localStorage.getItem("admin_groq_key") - which is stored on the frontend side.

- apres chaque ouverture de l'app on se trouve dans l'ecrant login
- les informations des autres utulisateurs sont afficher uniquement dans le menu ligue
- regle le probleme du module utulisateur dans le mode admin, il affiche ni les compts inscrit ni les parametre de suprimer les comptes
- quand je veux ajouter des regles sa ne s'enregistre pas

( j'ai fais certains et continue toi le reste )