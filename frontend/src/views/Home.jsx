import { useState } from "react";
import { useApp } from "../App";
import Dashboard from "./Dashboard";

export default function Home() {
  const { user, setUser, setLoading, apiFetch } = useApp();

  const [mode,     setMode]     = useState("login"); // "login" | "register"
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [showPwd,  setShowPwd]  = useState(false);
  const [error,    setError]    = useState(null);
  const [info,     setInfo]     = useState(null);
  const [busy,     setBusy]     = useState(false);

  // Si connecté → afficher le dashboard
  if (user) return <Dashboard />;

  const handleSubmit = async () => {
    setError(null);
    setInfo(null);
    if (!email.trim() || !password.trim()) {
      setError("Email et mot de passe obligatoires.");
      return;
    }
    if (mode === "register" && !username.trim()) {
      setError("Pseudo obligatoire.");
      return;
    }

    setBusy(true);
    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const body     = mode === "login"
        ? { email, password }
        : { email, password, username };

      const res  = await apiFetch(endpoint, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Erreur de connexion.");
        return;
      }

      // Stocker le token si présent
      if (data.access_token) {
        localStorage.setItem("auth_token", data.access_token);
      }

      setUser(data.user || data);
    } catch (err) {
      setError("Impossible de joindre le serveur.");
    } finally {
      setBusy(false);
    }
  };

  const handleGuest = () => {
    setUser({ username: "Invité", email: "", total: 0, isGuest: true });
  };

  return (
    <div className="login-screen">
      <div className="login-bg-grid" />

      <div className="login-content">
        {/* Hero */}
        <div className="login-hero">
          <div className="login-trophy-wrap">
            <span className="login-trophy-emoji">🏆</span>
            <div className="login-trophy-glow" />
          </div>
          <div className="login-title">Boulzazen</div>
          <div className="login-subtitle">Fantasy · WC 2026</div>

          <div className="login-divider">
            <span>Ligue privée · CDM 2026</span>
          </div>
        </div>

        {/* Toggle login / register */}
        <div className="auth-mode-toggle">
          <button
            className={`auth-mode-btn ${mode === "login" ? "active" : ""}`}
            onClick={() => { setMode("login"); setError(null); }}
          >
            Connexion
          </button>
          <button
            className={`auth-mode-btn ${mode === "register" ? "active" : ""}`}
            onClick={() => { setMode("register"); setError(null); }}
          >
            Inscription
          </button>
        </div>

        {/* Carte formulaire */}
        <div className="login-card">
          {error && <div className="auth-alert error">{error}</div>}
          {info  && <div className="auth-alert success">{info}</div>}

          <div className="auth-form">
            {mode === "register" && (
              <div className="auth-field">
                <label className="auth-label">👤 Pseudo</label>
                <input
                  className="auth-input"
                  placeholder="Ton pseudo dans la ligue"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            )}

            <div className="auth-field">
              <label className="auth-label">✉️ Email</label>
              <input
                className="auth-input"
                type="email"
                placeholder="ton@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="auth-field">
              <label className="auth-label">🔒 Mot de passe</label>
              <div className="auth-input-wrap">
                <input
                  className="auth-input"
                  type={showPwd ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                />
                <button
                  className="auth-eye-btn"
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                >
                  {showPwd ? "🙈" : "👁️"}
                </button>
              </div>
            </div>

            <button
              className={`auth-submit-btn ${busy ? "loading" : ""}`}
              onClick={handleSubmit}
              disabled={busy}
            >
              {busy
                ? <><span className="btn-spinner" /> Chargement...</>
                : mode === "login" ? "Se connecter" : "Créer mon compte"
              }
            </button>
          </div>

          {/* Mode invité */}
          <div className="auth-separator"><span>ou</span></div>
          <div className="guest-form">
            <p className="login-desc" style={{ fontSize: "0.75rem", marginBottom: 8 }}>
              Accès rapide sans compte — scores non sauvegardés
            </p>
            <button
              className="auth-submit-btn guest-submit"
              onClick={handleGuest}
            >
              👀 Continuer en tant qu'invité
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}