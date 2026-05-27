/**
 * App.jsx — Application principale Fantasy Boulzazen WC 2026
 * ─────────────────────────────────────────────────────────────
 * Modifications v5 :
 *  - Intégration de l'utilitaire getDisplayName (username.js)
 *  - Cache local (localStorage) : user + leaderboard persistés
 *    → Chargement immédiat en mode dégradé si le backend est hors ligne
 *  - État de synchronisation visuel transmis via le Context global
 *    (syncStatus : 'idle' | 'syncing' | 'ok' | 'degraded' | 'offline')
 *  - Fallback gracieux : l'app reste utilisable même sans backend
 */

import { useState, useEffect, createContext, useContext } from 'react';
import { supabase } from './supabaseClient';
import { API_BASE, ADMIN_EMAILS } from './config';
import { getDisplayNameFromMeta, getDisplayName } from './utils/username';
import Dashboard    from './views/Dashboard';
import MyTeam       from './views/MyTeam';
import Predictions  from './views/Predictions';
import Leaderboard  from './views/Leaderboard';
import Complaints   from './views/Complaints';
import AdminPanel   from './views/AdminPanel';

// ─── Clés du cache localStorage ───────────────────────────────
const CACHE_USER_KEY        = 'boulzazen_cache_user';
const CACHE_LEADERBOARD_KEY = 'boulzazen_cache_leaderboard';
const CACHE_TTL_MS          = 1000 * 60 * 30; // 30 minutes

// ─── Context global ────────────────────────────────────────────
export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

// ─── Helper fetch API ──────────────────────────────────────────
export const apiFetch = (path, options = {}) =>
  fetch(`${API_BASE}/api${path}`, options);

// ─── Navigation ────────────────────────────────────────────────
const NAV_ITEMS = [
  { id: 'dashboard',   icon: 'HOME',   label: 'Accueil'    },
  { id: 'myteam',      icon: 'PITCH',  label: 'Équipe'     },
  { id: 'predictions', icon: 'TARGET', label: 'Pronos'     },
  { id: 'leaderboard', icon: 'TROPHY', label: 'Classement' },
  { id: 'complaints',  icon: 'FLAG',   label: 'Plaintes'   },
];

// ═══════════════════════════════════════════════════════════════
//  CACHE HELPERS
// ═══════════════════════════════════════════════════════════════

/** Sauvegarde une valeur dans le cache avec timestamp. */
function cacheSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify({ ts: Date.now(), value }));
  } catch (e) {
    // Quota dépassé ou mode privé — on ignore silencieusement
  }
}

/** Lit le cache. Retourne null si absent ou expiré. */
function cacheGet(key, ttlMs = CACHE_TTL_MS) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const { ts, value } = JSON.parse(raw);
    if (Date.now() - ts > ttlMs) return null; // expiré
    return value;
  } catch {
    return null;
  }
}

/** Supprime une entrée du cache. */
function cacheDel(key) {
  try { localStorage.removeItem(key); } catch { /* silencieux */ }
}

// ═══════════════════════════════════════════════════════════════
//  ICÔNES SVG INLINE
// ═══════════════════════════════════════════════════════════════

export const Icon = ({ name, size = 22 }) => {
  const icons = {
    HOME: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
        <polyline points="9,22 9,12 15,12 15,22"/>
      </svg>
    ),
    PITCH: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="10"/>
        <circle cx="12" cy="12" r="3"/>
        <line x1="12" y1="2" x2="12" y2="22"/>
        <line x1="2" y1="12" x2="22" y2="12"/>
      </svg>
    ),
    TARGET: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="10"/>
        <circle cx="12" cy="12" r="6"/>
        <circle cx="12" cy="12" r="2"/>
      </svg>
    ),
    TROPHY: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <polyline points="8,21 12,21 16,21"/>
        <line x1="12" y1="17" x2="12" y2="21"/>
        <path d="M7 4h10v7a5 5 0 01-10 0z"/>
        <path d="M5 4H3v4a4 4 0 004 4"/>
        <path d="M19 4h2v4a4 4 0 01-4 4"/>
      </svg>
    ),
    FLAG: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/>
        <line x1="4" y1="22" x2="4" y2="15"/>
      </svg>
    ),
    ADMIN: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
    ),
    BOLT: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
      </svg>
    ),
    EYE: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
    ),
    EYE_OFF: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/>
        <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/>
        <line x1="1" y1="1" x2="23" y2="23"/>
      </svg>
    ),
    USER: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
      </svg>
    ),
    LOCK: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0110 0v4"/>
      </svg>
    ),
    MAIL: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
        <polyline points="22,6 12,13 2,6"/>
      </svg>
    ),
    WIFI_OFF: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <line x1="1" y1="1" x2="23" y2="23"/>
        <path d="M16.72 11.06A10.94 10.94 0 0119 12.55"/>
        <path d="M5 12.55a10.94 10.94 0 015.17-2.39"/>
        <path d="M10.71 5.05A16 16 0 0122.56 9"/>
        <path d="M1.42 9a15.91 15.91 0 014.7-2.88"/>
        <path d="M8.53 16.11a6 6 0 016.95 0"/>
        <circle cx="12" cy="20" r="1" fill="currentColor"/>
      </svg>
    ),
    CHECK: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
        <polyline points="20,6 9,17 4,12"/>
      </svg>
    ),
  };
  return icons[name] ?? null;
};

// ═══════════════════════════════════════════════════════════════
//  HASH ERROR SUPABASE
// ═══════════════════════════════════════════════════════════════

function parseHashError() {
  if (typeof window === 'undefined') return null;
  const hash = window.location.hash;
  if (!hash || !hash.includes('error=')) return null;
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  return {
    error:     params.get('error'),
    errorCode: params.get('error_code'),
    errorDesc: params.get('error_description')?.replace(/\+/g, ' '),
  };
}

function clearHashFromURL() {
  if (typeof window !== 'undefined' && window.history?.replaceState) {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }
}

const HASH_ERROR_MESSAGES = {
  otp_expired:         '⏰ Le lien de confirmation a expiré. Reconnecte-toi et demande un nouveau lien.',
  access_denied:       '🚫 Accès refusé. Le lien est invalide ou a déjà été utilisé.',
  email_not_confirmed: '📧 Confirme ton email avant de te connecter.',
};

// ═══════════════════════════════════════════════════════════════
//  SPLASH SCREEN
// ═══════════════════════════════════════════════════════════════

function SplashScreen() {
  return (
    <div className="splash-screen">
      <div className="splash-content">
        <div className="splash-badge">
          <span className="splash-flag">🌍</span>
        </div>
        <h1 className="splash-title">BOULZAZEN</h1>
        <p className="splash-sub">FANTASY LEAGUE · WC 2026</p>
        <div className="splash-loader">
          <div className="loader-bar" />
        </div>
      </div>
      <div className="splash-particles">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="particle" style={{ '--i': i }} />
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  AUTH SCREEN
// ═══════════════════════════════════════════════════════════════

function AuthScreen({ onSuccess, initialError }) {
  const [mode,         setMode]         = useState('login');
  const [email,        setEmail]        = useState('');
  const [password,     setPassword]     = useState('');
  const [username,     setUsername]     = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState(initialError || null);
  const [success,      setSuccess]      = useState(null);

  useEffect(() => { if (initialError) setError(initialError); }, [initialError]);

  const validateForm = () => {
    if (!email.trim() || !email.includes('@')) return 'Adresse email invalide.';
    if (password.length < 6) return 'Le mot de passe doit contenir au moins 6 caractères.';
    if (mode === 'register' && username.trim().length < 2)
      return 'Le pseudo doit contenir au moins 2 caractères.';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null); setSuccess(null);
    const ve = validateForm();
    if (ve) { setError(ve); return; }
    setLoading(true);
    try {
      if (mode === 'login') {
        const { data, error: authError } = await supabase.auth.signInWithPassword({
          email: email.trim().toLowerCase(), password,
        });
        if (authError) {
          const map = {
            'Invalid login credentials': 'Email ou mot de passe incorrect.',
            'Email not confirmed':       'Confirme ton email avant de te connecter.',
            'Too many requests':         'Trop de tentatives. Attends quelques minutes.',
          };
          throw new Error(map[authError.message] || authError.message);
        }
        if (data?.session) onSuccess(data.session);
      } else {
        const { data, error: authError } = await supabase.auth.signUp({
          email: email.trim().toLowerCase(), password,
          options: { data: { username: username.trim(), full_name: username.trim() } },
        });
        if (authError) {
          const map = { 'User already registered': 'Cet email est déjà utilisé. Connecte-toi.' };
          throw new Error(map[authError.message] || authError.message);
        }
        if (data?.user && !data?.session) {
          setSuccess('✅ Compte créé ! Vérifie ta boîte mail pour confirmer.');
          setMode('login');
        } else if (data?.session) {
          onSuccess(data.session);
        }
      }
    } catch (err) {
      setError(err.message || 'Une erreur est survenue.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-bg-grid" />
      <div className="login-content">
        <div className="login-hero">
          <div className="login-trophy-wrap">
            <span className="login-trophy-emoji">🏆</span>
            <div className="login-trophy-glow" />
          </div>
          <h1 className="login-title">BOULZAZEN</h1>
          <p className="login-subtitle">FANTASY · PRONOS · WC 2026</p>
          <div className="login-divider"><span>LIGUE PRIVÉE</span></div>
        </div>

        <div className="login-card">
          <div className="auth-mode-toggle">
            <button className={`auth-mode-btn ${mode === 'login' ? 'active' : ''}`}
              onClick={() => { setMode('login'); setError(null); setSuccess(null); }} type="button">
              Connexion
            </button>
            <button className={`auth-mode-btn ${mode === 'register' ? 'active' : ''}`}
              onClick={() => { setMode('register'); setError(null); setSuccess(null); }} type="button">
              Inscription
            </button>
          </div>

          {error   && <div className="auth-alert error">{error}</div>}
          {success && <div className="auth-alert success">{success}</div>}

          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            {mode === 'register' && (
              <div className="auth-field">
                <label className="auth-label"><Icon name="USER" size={14} /> Pseudo</label>
                <input type="text" className="auth-input" placeholder="Ton pseudo dans la ligue"
                  value={username} onChange={e => setUsername(e.target.value)}
                  maxLength={24} autoComplete="username" required />
              </div>
            )}
            <div className="auth-field">
              <label className="auth-label"><Icon name="MAIL" size={14} /> Email</label>
              <input type="email" className="auth-input" placeholder="ton@email.com"
                value={email} onChange={e => setEmail(e.target.value)}
                autoComplete="email" inputMode="email" required />
            </div>
            <div className="auth-field">
              <label className="auth-label"><Icon name="LOCK" size={14} /> Mot de passe</label>
              <div className="auth-input-wrap">
                <input type={showPassword ? 'text' : 'password'} className="auth-input"
                  placeholder={mode === 'register' ? 'Min. 6 caractères' : '••••••••'}
                  value={password} onChange={e => setPassword(e.target.value)}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required />
                <button type="button" className="auth-eye-btn" onClick={() => setShowPassword(s => !s)}>
                  <Icon name={showPassword ? 'EYE_OFF' : 'EYE'} size={16} />
                </button>
              </div>
            </div>
            <button type="submit" className={`auth-submit-btn ${loading ? 'loading' : ''}`} disabled={loading}>
              {loading ? <span className="btn-spinner" />
                : mode === 'login' ? '🚀 Se connecter' : '⚽ Créer mon compte'}
            </button>
          </form>

          {mode === 'login' && (
            <button type="button" className="auth-forgot-btn" onClick={async () => {
              if (!email.trim()) { setError('Entre ton email ci-dessus.'); return; }
              setLoading(true);
              const { error: e } = await supabase.auth.resetPasswordForEmail(
                email.trim().toLowerCase(),
                { redirectTo: `${window.location.origin}/reset-password` }
              );
              setLoading(false);
              if (e) setError("Erreur lors de l'envoi.");
              else setSuccess('📧 Email de réinitialisation envoyé !');
            }}>
              Mot de passe oublié ?
            </button>
          )}
          <p className="login-hint">
            {mode === 'login' ? 'Accès réservé aux membres de la ligue'
              : 'Inscription libre — rejoins la ligue Boulzazen'}
          </p>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  SYNC SCREEN
// ═══════════════════════════════════════════════════════════════

function SyncScreen() {
  const steps = [
    '🔌 Connexion au serveur...',
    '📡 Vérification du compte...',
    '🧮 Recalcul des points...',
    '🏆 Mise à jour du classement...',
  ];
  const [step, setStep] = useState(0);
  useEffect(() => {
    const iv = setInterval(() => setStep(s => (s + 1) % steps.length), 700);
    return () => clearInterval(iv);
  }, []);
  return (
    <div className="sync-screen">
      <div className="sync-content">
        <div className="sync-icon"><Icon name="BOLT" size={40} /></div>
        <h2 className="sync-title">Synchronisation</h2>
        <p className="sync-step">{steps[step]}</p>
        <div className="sync-progress">
          <div className="sync-bar" style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  INDICATEUR DE SYNC (petit voyant en header)
// ═══════════════════════════════════════════════════════════════

/**
 * Affiche un indicateur visuel discret de l'état de synchronisation.
 * syncStatus : 'idle' | 'syncing' | 'ok' | 'degraded' | 'offline'
 */
function SyncIndicator({ syncStatus }) {
  if (!syncStatus || syncStatus === 'idle') return null;

  const cfg = {
    syncing:  { cls: 'sync-pulse',    title: 'Synchronisation en cours...',  color: 'var(--accent)' },
    ok:       { cls: 'sync-ok',       title: 'Données à jour',               color: 'var(--green)'  },
    degraded: { cls: 'sync-degraded', title: 'Mode dégradé (backend lent)',   color: 'var(--warning)'},
    offline:  { cls: 'sync-offline',  title: 'Hors ligne — données en cache', color: 'var(--danger)' },
  }[syncStatus] ?? { cls: '', title: '', color: 'transparent' };

  return (
    <span
      className={`sync-indicator ${cfg.cls}`}
      title={cfg.title}
      aria-label={cfg.title}
      style={{ '--sync-color': cfg.color }}
    />
  );
}

// ═══════════════════════════════════════════════════════════════
//  HELPER FALLBACK USER
// ═══════════════════════════════════════════════════════════════

function buildFallbackUser(session) {
  const meta  = session?.user?.user_metadata || {};
  const email = session?.user?.email || '';
  return {
    username:            getDisplayNameFromMeta(meta, email),
    email,
    id:                  session?.user?.id || null,
    score_fantasy:       0,
    score_pronos_scores: 0,
    score_bracket:       0,
    score_annexes:       0,
    total:               0,
  };
}

// ═══════════════════════════════════════════════════════════════
//  APP PRINCIPALE
// ═══════════════════════════════════════════════════════════════

export default function App() {
  const [session,    setSession]    = useState(null);
  const [user,       setUser]       = useState(null);
  const [screen,     setScreen]     = useState('splash');
  const [activeTab,  setActiveTab]  = useState('dashboard');
  const [syncData,   setSyncData]   = useState(null);
  const [syncStatus, setSyncStatus] = useState('idle');
  const [hashError,  setHashError]  = useState(null);

  // ── Hash error Supabase ─────────────────────────────────────
  useEffect(() => {
    const err = parseHashError();
    if (err) {
      clearHashFromURL();
      const msg = HASH_ERROR_MESSAGES[err.errorCode] || err.errorDesc || `Erreur : ${err.error}`;
      setHashError(msg);
    }
  }, []);

  // ── Auth listener ───────────────────────────────────────────
  useEffect(() => {
    let splashTimer;

    supabase.auth.getSession().then(({ data: { session: s } }) => {
      if (s) {
        setSession(s);
        triggerSync(s);
      } else {
        // Tente de charger le cache même sans session (lecture seule)
        const cachedUser = cacheGet(CACHE_USER_KEY);
        if (cachedUser) {
          devLog('📦 Utilisateur chargé depuis le cache (sans session)');
        }
        splashTimer = setTimeout(() => setScreen('login'), 1800);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, s) => {
        if (event === 'SIGNED_IN' && s) {
          clearTimeout(splashTimer);
          setSession(s);
          await triggerSync(s);
        } else if (event === 'SIGNED_OUT') {
          // Nettoie le cache au logout pour éviter la fuite de données
          cacheDel(CACHE_USER_KEY);
          cacheDel(CACHE_LEADERBOARD_KEY);
          setUser(null); setSyncData(null); setSession(null);
          setSyncStatus('idle');
          setScreen('login');
        } else if (event === 'TOKEN_REFRESHED' && s) {
          setSession(s);
        } else if (event === 'PASSWORD_RECOVERY') {
          setHashError('🔑 Entre ton nouveau mot de passe ci-dessous.');
          setScreen('login');
        }
      }
    );

    return () => { clearTimeout(splashTimer); subscription.unsubscribe(); };
  }, []);

  // ═══════════════════════════════════════════════════════════
  //  SYNC PRINCIPAL
  // ═══════════════════════════════════════════════════════════

  const triggerSync = async (s) => {
    setScreen('syncing');
    setSyncStatus('syncing');

    // ── Nom d'affichage depuis les metadata Supabase ───────────
    const meta     = s.user?.user_metadata || {};
    const email    = s.user?.email || '';
    const username = getDisplayNameFromMeta(meta, email);

    // ── Tentative de chargement du cache AVANT l'appel réseau ──
    // → L'app est utilisable immédiatement si le backend répond lentement
    const cachedUser = cacheGet(CACHE_USER_KEY);
    if (cachedUser) {
      devLog('📦 Données utilisateur chargées depuis le cache (affichage immédiat)');
      setUser(cachedUser);
    }

    try {
      const controller = new AbortController();
      const timeoutId  = setTimeout(() => controller.abort(), 12000);

      const res = await fetch(`${API_BASE}/api/auth/sync`, {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${s.access_token}`,
        },
        body: JSON.stringify({
          user_id:  s.user.id,
          email,
          username,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();

        if (data?.user) {
          // ── Nettoyage du nom via l'utilitaire ────────────────
          const cleanedUser = {
            ...data.user,
            username: getDisplayName(data.user),
          };

          setUser(cleanedUser);
          setSyncData(data.sync_info);

          // ── Mise en cache pour le mode hors-ligne ────────────
          cacheSet(CACHE_USER_KEY, cleanedUser);

          setSyncStatus(data.status === 'degraded' ? 'degraded' : 'ok');
          devLog(`✅ Sync OK — mode: ${data.status}, user: ${cleanedUser.username}`);
        } else {
          // Réponse inattendue mais pas d'erreur HTTP
          const fb = buildFallbackUser(s);
          setUser(fb);
          cacheSet(CACHE_USER_KEY, fb);
          setSyncStatus('degraded');
          devLog('⚠️ Sync: réponse sans user, fallback');
        }
      } else {
        // Erreur HTTP — on utilise le cache s'il existe, sinon fallback
        devLog(`⚠️ Sync API ${res.status}`);
        if (!cachedUser) {
          const fb = buildFallbackUser(s);
          setUser(fb);
          cacheSet(CACHE_USER_KEY, fb);
        }
        setSyncStatus('degraded');
      }

    } catch (err) {
      const isTimeout = err.name === 'AbortError';
      devLog(isTimeout ? '⚠️ Sync timeout (12s)' : `⚠️ Sync réseau: ${err.message}`);

      // ── Mode hors-ligne : on charge le cache ─────────────────
      if (!cachedUser) {
        const fb = buildFallbackUser(s);
        setUser(fb);
        cacheSet(CACHE_USER_KEY, fb);
      }
      setSyncStatus('offline');
    } finally {
      setScreen('app');
    }
  };

  const handleAuthSuccess = (s) => { setSession(s); triggerSync(s); };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    cacheDel(CACHE_USER_KEY);
    cacheDel(CACHE_LEADERBOARD_KEY);
    setUser(null); setSyncData(null); setSession(null);
    setSyncStatus('idle');
    setScreen('login');
  };

  const isAdmin = ADMIN_EMAILS.includes(session?.user?.email || '');

  // ── Nom affiché (toujours propre) ────────────────────────────
  const displayName = user ? getDisplayName(user) : '—';

  // ── Context ─────────────────────────────────────────────────
  const ctx = {
    user,
    setUser,
    session,
    syncData,
    syncStatus,
    handleLogout,
    API_BASE,
    apiFetch,
    isAdmin,
    // Expose les helpers cache pour les vues enfants (ex: Dashboard)
    cacheSet,
    cacheGet,
    CACHE_LEADERBOARD_KEY,
  };

  const navItems = isAdmin
    ? [...NAV_ITEMS, { id: 'admin', icon: 'ADMIN', label: 'Admin' }]
    : NAV_ITEMS;

  // ── Routing ──────────────────────────────────────────────────
  if (screen === 'splash')  return <SplashScreen />;
  if (screen === 'login')   return <AuthScreen onSuccess={handleAuthSuccess} initialError={hashError} />;
  if (screen === 'syncing') return <SyncScreen />;

  return (
    <AppContext.Provider value={ctx}>
      <div className="app-shell">

        {/* ── HEADER ──────────────────────────────────────────── */}
        <header className="app-header">
          <div className="header-brand">
            <span className="header-ball">⚽</span>
            <div>
              <div className="header-title">BOULZAZEN</div>
              <div className="header-subtitle">WC 2026</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* Indicateur de synchronisation visuel */}
            <SyncIndicator syncStatus={syncStatus} />

            <button className="header-user-pill" onClick={handleLogout} title="Se déconnecter">
              <span className="pill-name">{displayName}</span>
              <span className="pill-score">{(user?.total ?? 0).toLocaleString()} pts</span>
            </button>
          </div>
        </header>

        {/* ── VUE ACTIVE ──────────────────────────────────────── */}
        <main className="app-content">
          {activeTab === 'dashboard'   && <Dashboard />}
          {activeTab === 'myteam'      && <MyTeam />}
          {activeTab === 'predictions' && <Predictions />}
          {activeTab === 'leaderboard' && <Leaderboard />}
          {activeTab === 'complaints'  && <Complaints />}
          {activeTab === 'admin'       && isAdmin && <AdminPanel />}
        </main>

        {/* ── BOTTOM NAV ──────────────────────────────────────── */}
        <nav className="bottom-nav">
          {navItems.map(item => (
            <button
              key={item.id}
              className={`nav-btn ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => setActiveTab(item.id)}
            >
              <span className="nav-icon-wrap">
                <Icon name={item.icon} size={20} />
                {activeTab === item.id && <span className="nav-active-dot" />}
              </span>
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </nav>

      </div>
    </AppContext.Provider>
  );
}

// ── Logger silencieux en prod ──────────────────────────────────
function devLog(msg) {
  if (import.meta.env.DEV) console.log(`[App] ${msg}`);
}