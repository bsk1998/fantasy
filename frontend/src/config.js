// ─── URL du backend FastAPI ────────────────────────────────────────────────
//
// STRATÉGIE :
//   • En développement  : on utilise le proxy Vite (/api → localhost:8000)
//     → Évite tous les problèmes CORS en dev, aucune config supplémentaire.
//   • En production     : VITE_API_BASE doit pointer vers le backend Render.com
//     Ex : https://fantasy-boulzazen-api.onrender.com
//
// Pour activer le mode prod local sans proxy, crée un .env.local :
//   VITE_API_BASE=http://localhost:8000
//
const isProd = import.meta.env.PROD;

export const API_BASE = isProd
  ? (import.meta.env.VITE_API_BASE || "https://fantasy-boulzazen-api.onrender.com")
  : ""; // Chaîne vide = requêtes relatives → proxy Vite intercepte /api/*

// Supabase — exposé ici pour centralisation (même valeur que supabaseClient.js)
export const SUPABASE_URL = "https://selkpaowxwjjfteadjvz.supabase.co";
export const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlbGtwYW93eHdqamZ0ZWFkanZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk2NDI0NjksImV4cCI6MjA5NTIxODQ2OX0.c2_RCi7Qn9pvNzPcAG8Lcd1SMKBFzthBactVizFHJ9w";

// IDs admin Supabase (liste blanche des emails autorisés à voir le panel admin)
// À adapter avec les vrais emails des admins de la ligue
export const ADMIN_EMAILS = [
  "admin@boulzazen.local",
  // Ajouter ici les emails admin réels
];