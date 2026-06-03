/**
 * AdminPanel.jsx — Panneau d'administration autonome
 * ===================================================
 * ⚠️  COMPLÈTEMENT INDÉPENDANT du contexte utilisateur (AppContext)
 *     - Gère son propre token JWT dans localStorage["admin_token"]
 *     - N'utilise PAS useApp(), session, user, etc.
 *     - Clé localStorage séparée : "admin_token" ≠ "auth_token" (user)
 */

import React, { useState } from "react";
import "./AdminPanel.css";

const API_TIMEOUT = 12000;
// Lecture directe de la variable Vite — pas de dépendance au contexte
const API_BASE = import.meta.env.VITE_API_BASE || "";

// ─────────────────────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────────────────────

function getAdminToken() {
  return localStorage.getItem("admin_token") || "";
}

function setAdminToken(token) {
  if (token) {
    localStorage.setItem("admin_token", token);
  } else {
    localStorage.removeItem("admin_token");
  }
}

async function adminFetch(path, options = {}) {
  const token = getAdminToken();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

  try {
    const res = await fetch(`${API_BASE}/api/admin${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return res;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}

// ─────────────────────────────────────────────────────────────────────
//  Formulaire de login admin
// ─────────────────────────────────────────────────────────────────────

function AdminLogin({ onLoginSuccess }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [busy,     setBusy]     = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);

    try {
      const res = await fetch(`${API_BASE}/api/admin/login`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ username: username.trim(), password }),
        signal:  AbortSignal.timeout(API_TIMEOUT),
      });

      let data;
      try { data = await res.json(); }
      catch { setError("Réponse serveur invalide."); setBusy(false); return; }

      if (res.ok && data.access_token) {
        setAdminToken(data.access_token);
        // Déclenche l'event storage pour que AdminAccessDot se mette à jour
        window.dispatchEvent(new Event("storage"));
        onLoginSuccess(data.access_token);
      } else {
        setError(data.detail || data.message || "Identifiants incorrects.");
      }
    } catch (err) {
      if (err.name === "AbortError" || err.name === "TimeoutError") {
        setError("Timeout — le serveur ne répond pas. Vérifiez que le backend tourne.");
      } else {
        setError(`Erreur réseau : ${err.message}`);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="admin-login-container">
      <div className="admin-login-box">
        <h2>🔐 Admin Panel</h2>
        <form onSubmit={handleLogin}>
          <input
            type="text"
            placeholder="Pseudo admin"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={busy}
            autoComplete="username"
            required
          />
          <input
            type="password"
            placeholder="Mot de passe"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={busy}
            autoComplete="current-password"
            required
          />
          <button type="submit" disabled={busy}>
            {busy ? "Connexion en cours..." : "Se connecter"}
          </button>
          {error && <p className="error">⚠️ {error}</p>}
        </form>
        <p style={{ marginTop: 16, fontSize: "0.75rem", color: "#888", textAlign: "center" }}>
          Login admin : <strong>admin</strong> / mdp : <strong>admin00</strong>
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  Panneau principal admin
// ─────────────────────────────────────────────────────────────────────

function AdminDashboard({ token, onLogout }) {
  const [activeTab,    setActiveTab]    = useState("squad");
  const [squadNation,  setSquadNation]  = useState("");
  const [squadRawText, setSquadRawText] = useState("");
  const [parsedSquad,  setParsedSquad]  = useState(null);
  const [pricing,      setPricing]      = useState(null);
  const [tournamentText, setTournamentText] = useState("");
  const [busy,         setBusy]         = useState(false);
  const [feedback,     setFeedback]     = useState(null);

  const showFeedback = (msg, type = "info") => {
    setFeedback({ msg, type });
    setTimeout(() => setFeedback(null), 4000);
  };

  // ── Vérification du token au montage ──
  React.useEffect(() => {
    adminFetch("/status")
      .then((res) => { if (!res.ok) onLogout(); })
      .catch(onLogout);
  }, []);

  const handleParseSquad = async () => {
    if (!squadRawText.trim()) { showFeedback("Collez une liste de joueurs.", "error"); return; }
    setBusy(true);
    try {
      const res  = await adminFetch("/squad/parse", {
        method: "POST",
        body:   JSON.stringify({ nation: squadNation, raw_squad_text: squadRawText }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setParsedSquad(data.parsed_data);
        showFeedback(data.message, "success");

        // Estimation des prix
        const priceRes  = await adminFetch("/squad/estimate-prices", {
          method: "POST",
          body:   JSON.stringify({ squad_data: data.parsed_data }),
        });
        const priceData = await priceRes.json();
        if (priceData.status === "success") setPricing(priceData.pricing);
      } else {
        showFeedback(data.message || "Erreur parsing.", "error");
      }
    } catch (err) {
      showFeedback(`Erreur : ${err.message}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleInjectSquad = async () => {
    if (!parsedSquad) return;
    setBusy(true);
    try {
      const params = new URLSearchParams({ nation: parsedSquad.nation || squadNation });
      if (parsedSquad.coach_name) params.append("coach_name", parsedSquad.coach_name);
      const res  = await adminFetch(`/squad/inject?${params}`);
      const data = await res.json();
      showFeedback(data.message, data.status === "success" ? "success" : "error");
    } catch (err) {
      showFeedback(`Erreur : ${err.message}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleForceScraping = async () => {
    setBusy(true);
    try {
      const res  = await fetch(`${API_BASE}/api/admin/force-scraping`, {
        method:  "POST",
        headers: { Authorization: `Bearer ${token}` },
        signal:  AbortSignal.timeout(API_TIMEOUT),
      });
      const data = await res.json();
      showFeedback(data.message || "Scraping lancé.", res.ok ? "success" : "error");
    } catch (err) {
      showFeedback(`Erreur : ${err.message}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const TABS = [
    { id: "squad",      label: "📋 Effectifs" },
    { id: "tournament", label: "🏆 Tournoi" },
    { id: "rules",      label: "📏 Règles" },
    { id: "tools",      label: "🛠️ Outils" },
  ];

  return (
    <div className="admin-container">
      <header className="admin-header">
        <h1>⚙️ Admin Panel — Fantasy Boulzazen</h1>
        <button onClick={onLogout} className="logout-btn">
          Déconnexion
        </button>
      </header>

      {feedback && (
        <div style={{
          margin: "0 0 16px",
          padding: "10px 16px",
          borderRadius: 6,
          background: feedback.type === "success" ? "#d4edda" : feedback.type === "error" ? "#f8d7da" : "#d1ecf1",
          color: feedback.type === "success" ? "#155724" : feedback.type === "error" ? "#721c24" : "#0c5460",
          fontSize: "0.85rem",
        }}>
          {feedback.msg}
        </div>
      )}

      <div className="admin-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? "active" : ""}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── EFFECTIFS ── */}
      {activeTab === "squad" && (
        <div className="admin-section">
          <h2>📋 Gestion des Effectifs</h2>
          <div className="admin-form">
            <label>Pays</label>
            <input
              type="text"
              placeholder="ex: France, Algérie, Maroc..."
              value={squadNation}
              onChange={(e) => setSquadNation(e.target.value)}
            />
            <label>Liste des joueurs (copier-coller depuis un site officiel)</label>
            <textarea
              placeholder="Copiez une liste de joueurs..."
              value={squadRawText}
              onChange={(e) => setSquadRawText(e.target.value)}
              rows={10}
            />
            <button onClick={handleParseSquad} className="parse-btn" disabled={busy}>
              {busy ? "Analyse en cours..." : "🤖 Parser avec Groq"}
            </button>
          </div>

          {parsedSquad && (
            <div className="parsed-result">
              <h3>✅ Squad : {parsedSquad.nation}</h3>
              <p>Coach : {parsedSquad.coach_name || "N/A"}</p>
              <p>Joueurs détectés : {parsedSquad.players?.length || 0}</p>
              {pricing && (
                <div className="pricing-preview">
                  <h4>Tarification estimée :</h4>
                  <ul>
                    {pricing.slice(0, 5).map((p, i) => (
                      <li key={i}>{p.player_name} ({p.position}) → {p.suggested_price}M€</li>
                    ))}
                    {pricing.length > 5 && <li>... +{pricing.length - 5} autres</li>}
                  </ul>
                </div>
              )}
              <button className="inject-btn" onClick={handleInjectSquad} disabled={busy}>
                ✅ Injecter en base de données
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── TOURNOI ── */}
      {activeTab === "tournament" && (
        <div className="admin-section">
          <h2>🏆 Gestion du Tournoi</h2>
          <div className="admin-form">
            <label>Calendrier / données du tournoi (texte libre)</label>
            <textarea
              placeholder="Collez le calendrier ou les résultats CDM 2026..."
              value={tournamentText}
              onChange={(e) => setTournamentText(e.target.value)}
              rows={12}
            />
            <button className="parse-btn" disabled={busy}>
              {busy ? "Parsing..." : "🤖 Parser Tournoi via Groq"}
            </button>
          </div>
        </div>
      )}

      {/* ── RÈGLES ── */}
      {activeTab === "rules" && (
        <div className="admin-section">
          <h2>📏 Barème Fantasy</h2>
          <table className="rules-table">
            <thead>
              <tr><th>Action</th><th>G</th><th>D</th><th>M</th><th>A</th></tr>
            </thead>
            <tbody>
              {[
                ["Match complet (≥90 min)", "+2", "+2", "+2", "+2"],
                ["Entrée/sortie (<90 min)", "+1", "+1", "+1", "+1"],
                ["But marqué",              "+8", "+6", "+5", "+4"],
                ["Passe décisive",           "+6", "+5", "+4", "+4"],
                ["Clean Sheet",              "+5", "+4", "+1", "—"],
                ["3 parades (gardien)",      "+3", "—",  "—",  "—"],
                ["5 récupérations (G/D/M)",  "+3", "+3", "+3", "—"],
                ["Carton jaune",             "-1", "-1", "-1", "-1"],
                ["Carton rouge",             "-2", "-2", "-2", "-2"],
              ].map(([action, g, d, m, a]) => (
                <tr key={action}>
                  <td>{action}</td>
                  <td>{g}</td><td>{d}</td><td>{m}</td><td>{a}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="admin-form" style={{ marginTop: 20 }}>
            <h3>Entraîneur</h3>
            <ul style={{ paddingLeft: 20, lineHeight: 2 }}>
              <li>Présent sur le banc : <strong>+1 pt</strong></li>
              <li>Victoire : <strong>+2 pts</strong> de base</li>
              <li>+3 pts par tranche de 2 buts d'écart (ex: 4-0 = +8 pts)</li>
              <li>Défaite : logique inverse</li>
              <li>But d'un remplaçant : <strong>+3 pts</strong></li>
              <li>Passe d'un remplaçant : <strong>+2 pts</strong></li>
            </ul>
          </div>
        </div>
      )}

      {/* ── OUTILS ── */}
      {activeTab === "tools" && (
        <div className="admin-section">
          <h2>🛠️ Outils de maintenance</h2>
          <div className="admin-form">
            <h3>Synchronisation des données</h3>
            <p style={{ color: "#666", fontSize: "0.9rem", marginBottom: 12 }}>
              Force le scraping Groq des résultats CDM 2026 et recalcule les points.
            </p>
            <button className="parse-btn" onClick={handleForceScraping} disabled={busy}>
              {busy ? "Scraping en cours..." : "🔄 Forcer le scraping"}
            </button>
          </div>
          <div className="admin-form" style={{ marginTop: 24 }}>
            <h3>Statut système</h3>
            <p style={{ color: "#666", fontSize: "0.85rem" }}>
              Consultez <a href="/api/health" target="_blank" rel="noopener">/api/health</a> et{" "}
              <a href="/api/scraping/status" target="_blank" rel="noopener">/api/scraping/status</a>
              {" "}pour le statut complet.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  Composant racine — gère connexion/déconnexion admin
// ─────────────────────────────────────────────────────────────────────

export default function AdminPanel() {
  // État local uniquement — pas d'AppContext
  const [token, setToken] = useState(() => getAdminToken());

  const handleLoginSuccess = (newToken) => {
    setToken(newToken);
  };

  const handleLogout = () => {
    setAdminToken(null);
    setToken("");
    // Déclenche l'event storage pour que AdminAccessDot se mette à jour
    window.dispatchEvent(new Event("storage"));
  };

  if (!token) {
    return <AdminLogin onLoginSuccess={handleLoginSuccess} />;
  }

  return <AdminDashboard token={token} onLogout={handleLogout} />;
}