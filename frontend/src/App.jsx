import { useState, useEffect, createContext, useContext } from 'react';
import { supabase } from './supabaseClient';
import { API_BASE } from './config';
import Dashboard from './views/Dashboard';
import MyTeam from './views/MyTeam';
import Predictions from './views/Predictions';
import Leaderboard from './views/Leaderboard';

// ─── Context global de l'application ─────────────────────────────────────────
export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

// ─── Navigation bottom bar ────────────────────────────────────────────────────
const NAV_ITEMS = [
  { id: 'dashboard',   icon: 'HOME',    label: 'Accueil'     },
  { id: 'myteam',      icon: 'PITCH',   label: 'Mon Équipe'  },
  { id: 'predictions', icon: 'TARGET',  label: 'Pronos'      },
  { id: 'leaderboard', icon: 'TROPHY',  label: 'Classement'  },
];

// ─── Icônes SVG inline (zéro dépendance externe) ─────────────────────────────
const Icon = ({ name, size = 22 }) => {
  const icons = {
    HOME: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9,22 9,12 15,12 15,22"/>
      </svg>
    ),
    PITCH: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>
        <line x1="12" y1="2" x2="12" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/>
      </svg>
    ),
    TARGET: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
      </svg>
    ),
    TROPHY: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <polyline points="8,21 12,21 16,21"/><line x1="12" y1="17" x2="12" y2="21"/>
        <path d="M7,4H17V11A5,5,0,0,1,7,11Z"/>
        <path d="M5,4H3V8A4,4,0,0,0,7,12"/><path d="M19,4H21V8A4,4,0,0,1,17,12"/>
      </svg>
    ),
    LOGOUT: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/>
        <polyline points="16,17 21,12 16,7"/><line x1="21" y1="12" x2="9" y2="12"/>
      </svg>
    ),
    BOLT: (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
      </svg>
    ),
  };
  return icons[name] ?? null;
};
export { Icon };

// ══════════════════════════════════════════════════════════════════════════════
//  ÉCRANS SPÉCIAUX
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

function LoginScreen({ onLogin, error }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    await onLogin();
    setLoading(false);
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
          <div className="login-divider">
            <span>LIGUE PRIVÉE</span>
          </div>
        </div>

        <div className="login-card">
          <p className="login-desc">Connecte-toi pour rejoindre la ligue, gérer ton équipe et voir le classement en temps réel.</p>
          {error && <div className="login-error">{error}</div>}
          <button
            className={`login-btn-google ${loading ? 'loading' : ''}`}
            onClick={handleClick}
            disabled={loading}
          >
            {loading ? (
              <span className="btn-spinner" />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            )}
            {!loading && 'Continuer avec Google'}
          </button>
          <p className="login-hint">Accès réservé aux membres de la ligue</p>
        </div>
      </div>
    </div>
  );
}

function SyncScreen() {
  const steps = [
    '🔌 Connexion au serveur...',
    '📡 Scraping des résultats...',
    '🧮 Recalcul des points...',
    '🏆 Mise à jour du classement...',
  ];
  const [step, setStep] = useState(0);

  useEffect(() => {
    const iv = setInterval(() => {
      setStep(s => (s + 1) % steps.length);
    }, 700);
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
  const [session, setSession]       = useState(null);
  const [user, setUser]             = useState(null);
  const [screen, setScreen]         = useState('splash');
  const [activeTab, setActiveTab]   = useState('dashboard');
  const [syncData, setSyncData]     = useState(null);
  const [loginError, setLoginError] = useState(null);

  // ── Auth listener ────────────────────────────────────────────────────────
  useEffect(() => {
    let splashTimer;

    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s);
      if (s) {
        triggerSync(s);
      } else {
        splashTimer = setTimeout(() => setScreen('login'), 1800);
      }
    });

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
        }
      }
    );

    return () => {
      clearTimeout(splashTimer);
      subscription.unsubscribe();
    };
  }, []);

  // ── Lazy Loading — Cœur de l'architecture ────────────────────────────────
  const triggerSync = async (s) => {
    setScreen('syncing');
    try {
      const res = await fetch(`${API_BASE}/auth/sync`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${s.access_token}`,
        },
        body: JSON.stringify({
          user_id: s.user.id,
          email:   s.user.email,
          username: s.user.user_metadata?.full_name?.split(' ')[0]
                    || s.user.email?.split('@')[0],
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
        setSyncData(data.sync_info);
      } else {
        throw new Error('sync_failed');
      }
    } catch {
      // Fallback gracieux — on continue avec les données de session
      setUser({
        username: s.user.user_metadata?.full_name?.split(' ')[0]
                  || s.user.email?.split('@')[0],
        email:    s.user.email,
        score_fantasy: 0,
        score_pronos_scores: 0,
        score_bracket: 0,
        total: 0,
      });
    } finally {
      setScreen('app');
    }
  };

  const handleLogin = async () => {
    setLoginError(null);
    try {
      await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: window.location.origin },
      });
    } catch {
      setLoginError('Erreur de connexion. Réessaie.');
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  // ── Context ──────────────────────────────────────────────────────────────
  const ctx = { user, setUser, session, syncData, handleLogout, API_BASE };

  // ── Routing ───────────────────────────────────────────────────────────────
  if (screen === 'splash')   return <SplashScreen />;
  if (screen === 'login')    return <LoginScreen onLogin={handleLogin} error={loginError} />;
  if (screen === 'syncing')  return <SyncScreen />;

  return (
    <AppContext.Provider value={ctx}>
      <div className="app-shell">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <header className="app-header">
          <div className="header-brand">
            <span className="header-ball">⚽</span>
            <div>
              <div className="header-title">BOULZAZEN</div>
              <div className="header-subtitle">WC 2026</div>
            </div>
          </div>
          <button className="header-user-pill" onClick={handleLogout} title="Se déconnecter">
            <span className="pill-name">{user?.username}</span>
            <span className="pill-score">{(user?.total ?? 0).toLocaleString()} pts</span>
          </button>
        </header>

        {/* ── Vue active ──────────────────────────────────────────────────── */}
        <main className="app-content">
          {activeTab === 'dashboard'   && <Dashboard />}
          {activeTab === 'myteam'      && <MyTeam />}
          {activeTab === 'predictions' && <Predictions />}
          {activeTab === 'leaderboard' && <Leaderboard />}
        </main>

        {/* ── Bottom Navigation ───────────────────────────────────────────── */}
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