/**
 * username.js — Utilitaire de nettoyage et formatage des pseudos Fantasy Boulzazen
 * v2.0 — Fix : ajout de getDisplayNameFromMeta et getDisplayName (requis par App.jsx)
 */

/**
 * Extrait un pseudo court et propre depuis une session Supabase.
 */
export function getDisplayUsername(session, maxLength = 20) {
  if (!session) return "Joueur";
  const meta  = session?.user?.user_metadata || {};
  const email = session?.user?.email || "";

  if (meta.username && typeof meta.username === "string") {
    const cleaned = nettoyerPseudo(meta.username, maxLength);
    if (cleaned.length >= 1) return cleaned;
  }

  if (meta.full_name && typeof meta.full_name === "string") {
    const prenom = meta.full_name.trim().split(/\s+/)[0];
    const cleaned = nettoyerPseudo(prenom, maxLength);
    if (cleaned.length >= 1) return cleaned;
  }

  if (email) {
    const pseudoDepuisEmail = extrairePseudoDepuisEmail(email, maxLength);
    if (pseudoDepuisEmail.length >= 1) return pseudoDepuisEmail;
  }

  return "Joueur";
}

/**
 * getDisplayNameFromMeta — requis par App.jsx
 * Construit un pseudo depuis les user_metadata + email Supabase
 * sans avoir besoin d'un objet session complet.
 *
 * @param {Object} meta  - session.user.user_metadata
 * @param {string} email - session.user.email
 * @returns {string}
 */
export function getDisplayNameFromMeta(meta = {}, email = "") {
  const fakeSession = { user: { user_metadata: meta, email } };
  return getDisplayUsername(fakeSession);
}

/**
 * getDisplayName — requis par App.jsx
 * Retourne le pseudo d'affichage depuis un objet user (retourné par l'API /auth/sync).
 *
 * @param {Object|null} userObj - { username, display_name, email, ... }
 * @returns {string}
 */
export function getDisplayName(userObj) {
  if (!userObj) return "Joueur";

  // Priorité : username > display_name > email > "Joueur"
  if (userObj.username && typeof userObj.username === "string") {
    const cleaned = nettoyerPseudo(userObj.username, 24);
    if (cleaned.length >= 1) return cleaned;
  }

  if (userObj.display_name && typeof userObj.display_name === "string") {
    const cleaned = nettoyerPseudo(userObj.display_name, 24);
    if (cleaned.length >= 1) return cleaned;
  }

  if (userObj.email) {
    return extrairePseudoDepuisEmail(userObj.email, 20);
  }

  return "Joueur";
}

// ─── Helpers internes ─────────────────────────────────────────────────────────

function extrairePseudoDepuisEmail(email, maxLength) {
  const partieLocale = email.split("@")[0] || "";
  const segments = partieLocale
    .split(/[.\-_\s]+/)
    .map((s) => s.replace(/[^a-zA-ZÀ-ÿ0-9]/g, ""))
    .filter((s) => s.length > 0);
  const meilleurSegment =
    segments.find((s) => /^[a-zA-ZÀ-ÿ]/.test(s)) || segments[0] || partieLocale;
  return nettoyerPseudo(meilleurSegment, maxLength);
}

export function nettoyerPseudo(pseudo, maxLength = 20) {
  if (!pseudo || typeof pseudo !== "string") return "";
  const propre = pseudo
    .trim()
    .replace(/[^a-zA-ZÀ-ÿ0-9\-]/g, "")
    .replace(/^[-]+|[-]+$/g, "");
  if (!propre) return "";
  const formate = propre.charAt(0).toUpperCase() + propre.slice(1).toLowerCase();
  return formate.slice(0, maxLength);
}

export function getInitiales(pseudo) {
  if (!pseudo) return "?";
  const mots = pseudo.trim().split(/[\s\-]+/).filter(Boolean);
  if (mots.length === 0) return "?";
  if (mots.length === 1) return mots[0].charAt(0).toUpperCase();
  return mots[0].charAt(0).toUpperCase() + mots[1].charAt(0).toUpperCase();
}

export function buildUserProfile(session) {
  if (!session) return { username: "Joueur", email: "", initiales: "?", supabaseId: null };
  const username   = getDisplayUsername(session);
  const email      = session?.user?.email || "";
  const initiales  = getInitiales(username);
  const supabaseId = session?.user?.id || null;
  return { username, email, initiales, supabaseId };
}