/**
 * username.js — Utilitaire de nettoyage et formatage des pseudos Fantasy Boulzazen
 *
 * Logique de priorité :
 *   1. user_metadata.username (défini à l'inscription)
 *   2. user_metadata.full_name (premier mot seulement)
 *   3. email → partie avant le '@' → nettoyage → majuscule initiale → troncature
 *
 * Exemples de transformation depuis l'email :
 *   "amar.boushaki@gmail.com"   → "Amar"
 *   "john_doe_123@outlook.com"  → "John"
 *   "m.ali@yahoo.fr"            → "M"  (1 lettre = acceptable)
 *   "player-1-boulzazen@test.fr"→ "Player"
 */

/**
 * Extrait un pseudo court et propre depuis une session Supabase.
 *
 * @param {Object|null} session       - Objet session Supabase (ou null)
 * @param {number}      [maxLength=20] - Longueur maximale du pseudo retourné
 * @returns {string} Pseudo formaté, jamais vide (fallback = "Joueur")
 */
export function getDisplayUsername(session, maxLength = 20) {
  if (!session) return "Joueur";

  const meta  = session?.user?.user_metadata || {};
  const email = session?.user?.email || "";

  // ── Priorité 1 : username explicite (défini à l'inscription) ──────────────
  if (meta.username && typeof meta.username === "string") {
    const cleaned = nettoyerPseudo(meta.username, maxLength);
    if (cleaned.length >= 1) return cleaned;
  }

  // ── Priorité 2 : full_name (ex: Google OAuth ou mise à jour de profil) ────
  if (meta.full_name && typeof meta.full_name === "string") {
    // Prendre uniquement le premier prénom
    const prenom = meta.full_name.trim().split(/\s+/)[0];
    const cleaned = nettoyerPseudo(prenom, maxLength);
    if (cleaned.length >= 1) return cleaned;
  }

  // ── Priorité 3 : email → extraction + nettoyage ───────────────────────────
  if (email) {
    const pseudoDepuisEmail = extrairePseudoDepuisEmail(email, maxLength);
    if (pseudoDepuisEmail.length >= 1) return pseudoDepuisEmail;
  }

  return "Joueur"; // Dernier recours
}

/**
 * Extrait et nettoie un pseudo depuis une adresse email.
 * Prend la partie avant le '@', sépare sur les délimiteurs courants
 * (point, tiret, underscore, chiffres en début), met une majuscule initiale.
 *
 * @param {string} email
 * @param {number} maxLength
 * @returns {string}
 */
function extrairePseudoDepuisEmail(email, maxLength) {
  // Extraire la partie locale (avant le @)
  const partieLocale = email.split("@")[0] || "";

  // Séparer sur les délimiteurs courants et prendre le premier segment non vide
  // Ex: "amar.boushaki" → ["amar", "boushaki"] → "amar"
  // Ex: "john_doe_123"  → ["john", "doe", "123"] → "john"
  // Ex: "m.ali"         → ["m", "ali"] → "m"
  const segments = partieLocale
    .split(/[.\-_\s]+/)
    .map((s) => s.replace(/[^a-zA-ZÀ-ÿ0-9]/g, "")) // Garder lettres + chiffres
    .filter((s) => s.length > 0);

  // Prendre le premier segment qui commence par une lettre (ignorer les segments numériques)
  const meilleurSegment =
    segments.find((s) => /^[a-zA-ZÀ-ÿ]/.test(s)) ||
    segments[0] ||
    partieLocale;

  return nettoyerPseudo(meilleurSegment, maxLength);
}

/**
 * Nettoie un pseudo brut :
 * - Supprime les caractères spéciaux non alphabétiques (sauf tiret)
 * - Met une majuscule à la première lettre
 * - Convertit le reste en minuscules
 * - Tronque à maxLength caractères
 *
 * @param {string} pseudo
 * @param {number} maxLength
 * @returns {string}
 */
export function nettoyerPseudo(pseudo, maxLength = 20) {
  if (!pseudo || typeof pseudo !== "string") return "";

  const propre = pseudo
    .trim()
    // Supprimer les caractères spéciaux sauf lettres, chiffres, tiret
    .replace(/[^a-zA-ZÀ-ÿ0-9\-]/g, "")
    // Supprimer les tirets en début et fin
    .replace(/^[-]+|[-]+$/g, "");

  if (!propre) return "";

  // Majuscule initiale + minuscules pour le reste
  const formate =
    propre.charAt(0).toUpperCase() + propre.slice(1).toLowerCase();

  return formate.slice(0, maxLength);
}

/**
 * Génère les initiales d'un pseudo (pour les avatars).
 * Ex: "Karim" → "K" | "Jean-Pierre" → "JP"
 *
 * @param {string} pseudo
 * @returns {string} 1 à 2 lettres majuscules
 */
export function getInitiales(pseudo) {
  if (!pseudo) return "?";

  const mots = pseudo.trim().split(/[\s\-]+/).filter(Boolean);

  if (mots.length === 0) return "?";
  if (mots.length === 1) return mots[0].charAt(0).toUpperCase();

  // Deux premières lettres des deux premiers mots
  return (
    mots[0].charAt(0).toUpperCase() + mots[1].charAt(0).toUpperCase()
  );
}

/**
 * Construit un objet profil utilisateur complet depuis la session Supabase.
 * Centralize toute la logique d'extraction du profil en un seul endroit.
 *
 * @param {Object|null} session - Session Supabase
 * @returns {{ username: string, email: string, initiales: string, supabaseId: string|null }}
 */
export function buildUserProfile(session) {
  if (!session) {
    return {
      username:   "Joueur",
      email:      "",
      initiales:  "?",
      supabaseId: null,
    };
  }

  const username   = getDisplayUsername(session);
  const email      = session?.user?.email || "";
  const initiales  = getInitiales(username);
  const supabaseId = session?.user?.id || null;

  return { username, email, initiales, supabaseId };
}