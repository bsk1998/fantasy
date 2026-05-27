// ─── URL du backend FastAPI ────────────────────────────────────────────────
// En dev : proxy Vite (requêtes relatives /api → localhost:8000)
// En prod : variable VITE_API_BASE doit pointer vers le backend Render.com
const isProd = import.meta.env.PROD;

export const API_BASE = isProd
  ? (import.meta.env.VITE_API_BASE || "https://fantasy-boulzazen-api.onrender.com")
  : "";  // vide → proxy Vite intercepte /api/*

// Supabase (centralisé ici — utilisé si import.meta.env indisponible)
export const SUPABASE_URL      = import.meta.env.VITE_SUPABASE_URL      || "https://selkpaowxwjjfteadjvz.supabase.co";
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";

// Groq AI — analyse plaintes admin
export const GROQ_API_KEY = import.meta.env.VITE_GROQ_API_KEY || "";

// ─── Admins de la ligue ───────────────────────────────────────────────────
// ⚠️  MODIFIER ICI : mettre les vrais emails des administrateurs
export const ADMIN_EMAILS = [
  "admin@boulzazen.local",
  // "ton_email@gmail.com",   ← décommenter et remplacer par ton vrai email
];