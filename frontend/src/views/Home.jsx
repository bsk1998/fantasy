import { useEffect, useState } from "react";
import { useApp } from "../App";
import Dashboard from "./Dashboard";

const KNOWN_EMAILS_KEY = "known_user_emails";
const API_TIMEOUT = 10000; // 10 secondes

function readKnownEmails() {
  try {
    return JSON.parse(localStorage.getItem(KNOWN_EMAILS_KEY) || "[]");
  } catch {
    return [];
  }
}

function rememberKnownEmail(value) {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return [];

  const next = [normalized, ...readKnownEmails().filter((item) => item !== normalized)].slice(0, 8);
  localStorage.setItem(KNOWN_EMAILS_KEY, JSON.stringify(next));
  localStorage.setItem("user_email", normalized);
  return next;
}

export default function Home() {
  const { user, setUser, setSession, apiFetch } = useApp();

  const [mode,     setMode]     = useState("login");
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [showPwd,  setShowPwd]  = useState(false);
  const [error,    setError]    = useState(null);
  const [info,     setInfo]     = useState(null);
  const [busy,     setBusy]     = useState(false);
  const [showKnownEmails, setShowKnownEmails] = useState(false);
  const [knownEmails, setKnownEmails] = useState(() => readKnownEmails());

  useEffect(() => {
    setKnownEmails(readKnownEmails());
  }, []);

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

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

      const res  = await apiFetch(endpoint, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(body),
        signal:  controller.signal,
      });

      clearTimeout(timeoutId);

      let data;
      try {
        data = await res.json();
      } catch (e) {
        setError("Réponse serveur invalide.");
        return;
      }

      if (!res.ok) {
        setError(data.detail || data.message || "Erreur de connexion.");
        return;
      }

      if (data.access_token) {
        localStorage.setItem("auth_token", data.access_token);
        setSession({ access_token: data.access_token });
      }

      setKnownEmails(rememberKnownEmail(email));
      setUser(data.user || data);
    } catch (err) {
      if (err.name === "AbortError") {
        setError("Timeout de connexion. Le serveur n'a pas répondu à temps.");
      } else {
        setError(`Erreur réseau: ${err.message || "Impossible de joindre le serveur."}`);
        console.error("Auth error:", err);
      }
    } finally {
      setBusy(false);
    }
  };

  const handleGuest = () => {
    setSession(null);
    setUser({ username: "Invité", email: "", total: 0, isGuest: true });
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
          <div className="login-title">Boulzazen</div>
          <div className="login-subtitle">Fantasy · WC 2026</div>

          <div className="login-divider">
            <span>Ligue privée · CDM 2026</span>
          </div>
        </div>

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
                  disabled={busy}
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
                disabled={busy}
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
                  onKeyDown={(e) => e.key === "Enter" && !busy && handleSubmit()}
                  disabled={busy}
                />
                <button
                  className="auth-eye-btn"
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  disabled={busy}
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

            <button
              className="known-emails-toggle"
              type="button"
              onClick={() => {
                setKnownEmails(readKnownEmails());
                setShowKnownEmails((value) => !value);
              }}
              disabled={busy}
            >
              Emails sur cet appareil
            </button>

            {showKnownEmails && (
              <div className="known-emails-panel">
                {knownEmails.length > 0 ? (
                  knownEmails.map((item) => (
                    <button
                      className="known-email-item"
                      type="button"
                      key={item}
                      onClick={() => {
                        setEmail(item);
                        setShowKnownEmails(false);
                      }}
                      disabled={busy}
                    >
                      {item}
                    </button>
                  ))
                ) : (
                  <p>Aucun email enregistre sur cet appareil.</p>
                )}
              </div>
            )}
          </div>

          <div className="auth-separator"><span>ou</span></div>
          <div className="guest-form">
            <p className="login-desc" style={{ fontSize: "0.75rem", marginBottom: 8 }}>
              Accès rapide sans compte — scores non sauvegardés
            </p>
            <button
              className="auth-submit-btn guest-submit"
              onClick={handleGuest}
              disabled={busy}
            >
              👀 Continuer en tant qu'invité
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
