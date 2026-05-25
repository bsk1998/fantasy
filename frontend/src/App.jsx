import { useState, useEffect, createContext, useContext } from 'react';
import { supabase } from './supabaseClient';
import { API_BASE } from './config';
import Dashboard from './views/Dashboard';
import MyTeam from './views/MyTeam';
import Predictions from './views/Predictions';
import Leaderboard from './views/Leaderboard';

// ─── Context global ────────────────────────────────────────────────────────
export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

// ─── Navigation ────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { id: 'dashboard',   icon: 'HOME',   label: 'Accueil'    },
  { id: 'myteam',      icon: 'PITCH',  label: 'Équipe'     },
  { id: 'predictions', icon: 'TARGET', label: 'Pronos'     },
  { id: 'leaderboard', icon: 'TROPHY', label: 'Classement' },
];

// ─── Icônes SVG inline ─────────────────────────────────────────────────────
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
  };
  return icons[name] ?? null;
};

// ══════════════════════════════════════════════════════════════════════════════
//  SPLASH SCREEN
// ══════════════════════════════════════════════════════════════════════════════

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

// ══════════════════════════════════════════════════════════════════════════════
//  LOGIN / REGISTER SCREEN — Email + Mot de passe (100% Supabase Auth gratuit)
// ══════════════════════════════════════════════════════════════════════════════

function AuthScreen({ onSuccess }) {
  const [mode,         setMode]         = useState('login');    // 'login' | 'register'
  const [email,        setEmail]        = useState('');
  const [password,     setPassword]     = useState('');
  const [username,     setUsername]     = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState(null);
  const [success,      setSuccess]      = useState(null);

  // Validation côté client
  const validateForm = () => {
    if (!email.trim() || !email.includes('@')) {
      return 'Adresse email invalide.';
    }
    if (password.length < 6) {
      return 'Le mot de passe doit contenir au moins 6 caractères.';
    }
    if (mode === 'register' && username.trim().length < 2) {
      return 'Le pseudo doit contenir au moins 2 caractères.';
    }
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);

    try {
      if (mode === 'login') {
        // ── Connexion ───────────────────────────────────────────────────────
        const { data, error: authError } = await supabase.auth.signInWithPassword({
          email:    email.trim().toLowerCase(),
          password: password,
        });

        if (authError) {
          // Messages d'erreur traduits en français
          const errorMap = {
            'Invalid login credentials': 'Email ou mot de passe incorrect.',
            'Email not confirmed':       'Confirme ton email avant de te connecter.',
            'Too many requests':         'Trop de tentatives. Attends quelques minutes.',
          };
          throw new Error(errorMap[authError.message] || authError.message);
        }

        if (data?.session) {
          onSuccess(data.session);
        }

      } else {
        // ── Inscription ─────────────────────────────────────────────────────
        const { data, error: authError } = await supabase.auth.signUp({
          email:    email.trim().toLowerCase(),
          password: password,
          options: {
            data: {
              username: username.trim(),
              full_name: username.trim(),
            },
          },
        });

        if (authError) {
          const errorMap = {
            'User already registered': 'Cet email est déjà utilisé. Connecte-toi.',
            'Password should be at least 6 characters': 'Mot de passe trop court (6 caractères min).',
          };
          throw new Error(errorMap[authError.message] || authError.message);
        }

        // Si email de confirmation requis (selon config Supabase)
        if (data?.user && !data?.session) {
          setSuccess('✅ Compte créé ! Vérifie ta boîte mail pour confirmer.');
          setMode('login');
        } else if (data?.session) {
          // Auto-connexion sans confirmation email (désactivé dans Supabase Dashboard)
          onSuccess(data.session);
        }
      }
    } catch (err) {
      setError(err.message || 'Une erreur est survenue. Réessaie.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-bg-grid" />

      <div className="login-content">
        {/* ── HERO ─────────────────────────────────────────────── */}
        <div className="login-hero">
          <div className="login-trophy-wrap">
            <span className="login-trophy-emoji">🏆</span>
            <div className="login-trophy-glow" />
          </div>
          <h1 className="login-title">BOULZAZEN</h1>
          <p className="login-subtitle">FANTASY · PRONOS · WC 2026</p>
          <div className="login-divider">
            <span>LIGUE PRIVÉE</span>
          </div>
        </div>

        {/* ── CARD FORMULAIRE ────────────────────────────────── */}
        <div className="login-card">

          {/* Toggle Login / Register */}
          <div className="auth-mode-toggle">
            <button
              className={`auth-mode-btn ${mode === 'login' ? 'active' : ''}`}
              onClick={() => { setMode('login'); setError(null); setSuccess(null); }}
              type="button"
            >
              Connexion
            </button>
            <button
              className={`auth-mode-btn ${mode === 'register' ? 'active' : ''}`}
              onClick={() => { setMode('register'); setError(null); setSuccess(null); }}
              type="button"
            >
              Inscription
            </button>
          </div>

          {/* Messages */}
          {error   && <div className="auth-alert error">{error}</div>}
          {success && <div className="auth-alert success">{success}</div>}

          {/* Formulaire */}
          <form onSubmit={handleSubmit} className="auth-form" noValidate>

            {/* Pseudo — uniquement à l'inscription */}
            {mode === 'register' && (
              <div className="auth-field">
                <label className="auth-label">
                  <Icon name="USER" size={14} />
                  Pseudo
                </label>
                <input
                  type="text"
                  className="auth-input"
                  placeholder="Ton pseudo dans la ligue"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  maxLength={24}
                  autoComplete="username"
                  required
                />
              </div>
            )}

            {/* Email */}
            <div className="auth-field">
              <label className="auth-label">
                <Icon name="MAIL" size={14} />
                Email
              </label>
              <input
                type="email"
                className="auth-input"
                placeholder="ton@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                autoComplete="email"
                inputMode="email"
                required
              />
            </div>

            {/* Mot de passe */}
            <div className="auth-field">
              <label className="auth-label">
                <Icon name="LOCK" size={14} />
                Mot de passe
              </label>
              <div className="auth-input-wrap">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="auth-input"
                  placeholder={mode === 'register' ? 'Min. 6 caractères' : '••••••••'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  required
                />
                <button
                  type="button"
                  className="auth-eye-btn"
                  onClick={() => setShowPassword(s => !s)}
                  aria-label="Afficher/masquer le mot de passe"
                >
                  <Icon name={showPassword ? 'EYE_OFF' : 'EYE'} size={16} />
                </button>
              </div>
            </div>

            {/* Bouton submit */}
            <button
              type="submit"
              className={`auth-submit-btn ${loading ? 'loading' : ''}`}
              disabled={loading}
            >
              {loading
                ? <span className="btn-spinner" />
                : mode === 'login' ? '🚀 Se connecter' : '⚽ Créer mon compte'
              }
            </button>
          </form>

          {/* Lien mot de passe oublié */}
          {mode === 'login' && (
            <button
              type="button"
              className="auth-forgot-btn"
              onClick={async () => {
                if (!email.trim()) {
                  setError('Entre ton email ci-dessus pour réinitialiser ton mot de passe.');
                  return;
                }
                setLoading(true);
                const { error: resetError } = await supabase.auth.resetPasswordForEmail(
                  email.trim().toLowerCase(),
                  { redirectTo: `${window.location.origin}/reset-password` }
                );
                setLoading(false);
                if (resetError) {
                  setError('Erreur lors de l\'envoi. Vérifie ton email.');
                } else {
                  setSuccess('📧 Email de réinitialisation envoyé !');
                }
              }}
            >
              Mot de passe oublié ?
            </button>
          )}

          <p className="login-hint">
            {mode === 'login'
              ? 'Accès réservé aux membres de la ligue'
              : 'Inscription libre — rejoins la ligue Boulzazen'}
          </p>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
//  SYNC SCREEN
// ══════════════════════════════════════════════════════════════════════════════

function SyncScreen() {
  const steps = [
    '🔌 Connexion au serveur...',
    '📡 Scraping des résultats...',
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
        <div className="sync-icon">
          <Icon name="BOLT" size={40} />
        </div>
        <h2 className="sync-title">Synchronisation</h2>
        <p className="sync-step">{steps[step]}</p>
        <div className="sync-progress">
          <div className="sync-bar" style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
//  APP PRINCIPALE
// ══════════════════════════════════════════════════════════════════════════════

export default function App() {
  const [session,      setSession]      = useState(null);
  const [user,         setUser]         = useState(null);
  const [screen,       setScreen]       = useState('splash');
  const [activeTab,    setActiveTab]    = useState('dashboard');
  const [syncData,     setSyncData]     = useState(null);

  // ── Auth listener ─────────────────────────────────────────────────────────
  useEffect(() => {
    let splashTimer;

    // Vérifier la session existante au chargement
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      if (s) {
        setSession(s);
        triggerSync(s);
      } else {
        splashTimer = setTimeout(() => setScreen('login'), 1800);
      }
    });

    // Écouter les changements d'état auth
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, s) => {
        setSession(s);
        if (event === 'SIGNED_IN' && s) {
          clearTimeout(splashTimer);
          await triggerSync(s);
        } else if (event === 'SIGNED_OUT') {
          setUser(null);
          setSyncData(null);
          setScreen('login');
        } else if (event === 'TOKEN_REFRESHED' && s) {
          setSession(s);
        }
      }
    );

    return () => {
      clearTimeout(splashTimer);
      subscription.unsubscribe();
    };
  }, []);

  // ── Lazy Loading — Sync au login ──────────────────────────────────────────
  const triggerSync = async (s) => {
    setScreen('syncing');
    try {
      const username = s.user?.user_metadata?.username
                    || s.user?.user_metadata?.full_name?.split(' ')[0]
                    || s.user?.email?.split('@')[0]
                    || 'Joueur';

      const res = await fetch(`${API_BASE}/auth/sync`, {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${s.access_token}`,
        },
        body: JSON.stringify({
          user_id:  s.user.id,
          email:    s.user.email,
          username: username,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
        setSyncData(data.sync_info);
      } else {
        throw new Error(`sync_failed_${res.status}`);
      }
    } catch (err) {
      // Fallback gracieux — on ne bloque pas l'accès si le backend est down
      console.warn('Sync backend indisponible, mode dégradé :', err.message);
      setUser({
        username: s.user?.user_metadata?.username
                 || s.user?.email?.split('@')[0]
                 || 'Joueur',
        email:           s.user.email,
        score_fantasy:   0,
        score_pronos_scores: 0,
        score_bracket:   0,
        total:           0,
      });
    } finally {
      setScreen('app');
    }
  };

  const handleAuthSuccess = (s) => {
    setSession(s);
    triggerSync(s);
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setSyncData(null);
    setScreen('login');
  };

  // ── Context ───────────────────────────────────────────────────────────────
  const ctx = { user, setUser, session, syncData, handleLogout, API_BASE };

  // ── Routing ───────────────────────────────────────────────────────────────
  if (screen === 'splash')  return <SplashScreen />;
  if (screen === 'login')   return <AuthScreen onSuccess={handleAuthSuccess} />;
  if (screen === 'syncing') return <SyncScreen />;

  return (
    <AppContext.Provider value={ctx}>
      <div className="app-shell">

        {/* ── HEADER ──────────────────────────────────────────────────────── */}
        <header className="app-header">
          <div className="header-brand">
            <span className="header-ball">⚽</span>
            <div>
              <div className="header-title">BOULZAZEN</div>
              <div className="header-subtitle">WC 2026</div>
            </div>
          </div>
          <button
            className="header-user-pill"
            onClick={handleLogout}
            title="Se déconnecter"
          >
            <span className="pill-name">{user?.username ?? '—'}</span>
            <span className="pill-score">
              {(user?.total ?? 0).toLocaleString()} pts
            </span>
          </button>
        </header>

        {/* ── VUE ACTIVE ──────────────────────────────────────────────────── */}
        <main className="app-content">
          {activeTab === 'dashboard'   && <Dashboard />}
          {activeTab === 'myteam'      && <MyTeam />}
          {activeTab === 'predictions' && <Predictions />}
          {activeTab === 'leaderboard' && <Leaderboard />}
        </main>

        {/* ── BOTTOM NAV ──────────────────────────────────────────────────── */}
        <nav className="bottom-nav">
          {NAV_ITEMS.map(item => (
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