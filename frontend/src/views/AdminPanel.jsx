import React, { useState } from "react";
import "./AdminPanel.css";

export default function AdminPanel() {
  const [token, setToken] = useState(localStorage.getItem("admin_token") || "");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [activeTab, setActiveTab] = useState("squad");

  // Squad Management
  const [squadNation, setSquadNation] = useState("");
  const [squaddrawText, setSquadRawText] = useState("");
  const [parsedSquad, setParsedSquad] = useState(null);
  const [pricing, setPricing] = useState(null);

  // Tournament Management
  const [tournamentText, setTournamentText] = useState("");

  const API_BASE = import.meta.env.VITE_API_BASE || "";

  // ════════════════════════════════════════════════════════════════════
  //  LOGIN
  // ════════════════════════════════════════════════════════════════════

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError("");

    try {
      const res = await fetch(`${API_BASE}/api/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (res.ok) {
        const data = await res.json();
        console.log("Admin login successful:", data); // Log succès
        setToken(data.access_token);
        localStorage.setItem("admin_token", data.access_token);
        setUsername("");
        setPassword("");
      } else {
        const err = await res.json();
        console.error("Admin login failed:", res.status, err); // Log échec avec statut et erreur
        setLoginError(err.detail || "Connexion échouée");
      }
    } catch (err) {
      console.error("Admin login network error:", err); // Log erreurs réseau
      setLoginError(err.message);
    }
  };

  const handleLogout = () => {
    setToken("");
    localStorage.removeItem("admin_token");
  };

  if (!token) {
    return (
      <div className="admin-login-container">
        <div className="admin-login-box">
          <h2>🔐 Admin Panel</h2>
          <form onSubmit={handleLogin}>
            <input
              type="text"
              placeholder="Pseudo"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <input
              type="password"
              placeholder="Mot de passe"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button type="submit">Connexion</button>
            {loginError && <p className="error">{loginError}</p>}
          </form>
        </div>
      </div>
    );
  }

  // ════════════════════════════════════════════════════════════════════
  //  SQUAD PARSING
  // ════════════════════════════════════════════════════════════════════

  const handleParseSquad = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/squad/parse`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          nation: squadNation,
          raw_squad_text: squaddrawText,
        }),
      });

      const data = await res.json();
      if (data.status === "success") {
        setParsedSquad(data.parsed_data);
        // Estimer les prix
        const pricingRes = await fetch(
          `${API_BASE}/api/admin/squad/estimate-prices`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ squad_data: data.parsed_data }),
          }
        );
        const pricingData = await pricingRes.json();
        if (pricingData.status === "success") {
          setPricing(pricingData.pricing);
        }
      } else {
        alert(data.message);
      }
    } catch (err) {
      alert(`Erreur : ${err.message}`);
    }
  };

  // ════════════════════════════════════════════════════════════════════
  //  ADMIN INTERFACE
  // ════════════════════════════════════════════════════════════════════

  return (
    <div className="admin-container">
      <header className="admin-header">
        <h1>⚙️ Admin Panel</h1>
        <button onClick={handleLogout} className="logout-btn">
          Déconnexion
        </button>
      </header>

      <div className="admin-tabs">
        <button
          className={activeTab === "squad" ? "active" : ""}
          onClick={() => setActiveTab("squad")}
        >
          📋 Effectifs
        </button>
        <button
          className={activeTab === "tournament" ? "active" : ""}
          onClick={() => setActiveTab("tournament")}
        >
          🏆 Tournoi
        </button>
        <button
          className={activeTab === "rules" ? "active" : ""}
          onClick={() => setActiveTab("rules")}
        >
          📏 Règles
        </button>
      </div>

      {/* EFFECTIFS TAB */}
      {activeTab === "squad" && (
        <div className="admin-section">
          <h2>📋 Gestion des Effectifs</h2>

          <div className="admin-form">
            <label>Pays</label>
            <input
              type="text"
              placeholder="ex: Japon"
              value={squadNation}
              onChange={(e) => setSquadNation(e.target.value)}
            />

            <label>Liste des joueurs (copier-coller)</label>
            <textarea
              placeholder="Copiez une liste de joueurs depuis un site officiel..."
              value={squaddrawText}
              onChange={(e) => setSquadRawText(e.target.value)}
              rows={10}
            />

            <button onClick={handleParseSquad} className="parse-btn">
              🤖 Parser avec Groq
            </button>
          </div>

          {parsedSquad && (
            <div className="parsed-result">
              <h3>✅ Squad parsée : {parsedSquad.nation}</h3>
              <p>Coach : {parsedSquad.coach_name || "N/A"}</p>
              <p>Joueurs : {parsedSquad.players.length}</p>

              {pricing && (
                <div className="pricing-preview">
                  <h4>Tarification Groq :</h4>
                  <ul>
                    {pricing.slice(0, 5).map((p, i) => (
                      <li key={i}>
                        {p.player_name} ({p.position}) → {p.suggested_price}€
                      </li>
                    ))}
                    {pricing.length > 5 && <li>... +{pricing.length - 5}</li>}
                  </ul>
                </div>
              )}

              <button className="inject-btn">✅ Injecter en BD</button>
            </div>
          )}
        </div>
      )}

      {/* TOURNAMENT TAB */}
      {activeTab === "tournament" && (
        <div className="admin-section">
          <h2>🏆 Gestion du Tournoi</h2>

          <div className="admin-form">
            <label>Texte/URLs du tournoi (CDM 2026)</label>
            <textarea
              placeholder="Collez le calendrier complet ou les captures d'écran OCRisées..."
              value={tournamentText}
              onChange={(e) => setTournamentText(e.target.value)}
              rows={12}
            />

            <button className="parse-btn">🤖 Parser Tournoi</button>
          </div>
        </div>
      )}

      {/* RULES TAB */}
      {activeTab === "rules" && (
        <div className="admin-section">
          <h2>📏 Barème Fantasy</h2>

          <div className="admin-form">
            <h3>Règles actuelles</h3>
            <table className="rules-table">
              <thead>
                <tr>
                  <th>Règle</th>
                  <th>Positions</th>
                  <th>Points</th>
                  <th>Actif</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>But marqué</td>
                  <td>G/D/M/A</td>
                  <td>4/6/5/4</td>
                  <td>✅</td>
                </tr>
                <tr>
                  <td>Match complet</td>
                  <td>ALL</td>
                  <td>2</td>
                  <td>✅</td>
                </tr>
                <tr>
                  <td>Clean Sheet</td>
                  <td>D/G</td>
                  <td>4/5</td>
                  <td>✅</td>
                </tr>
              </tbody>
            </table>

            <label>Nouvelle règle</label>
            <input placeholder="Nom de la règle" type="text" />
            <input placeholder="Valeur points" type="number" />
            <button className="save-btn">💾 Ajouter</button>
          </div>
        </div>
      )}
    </div>
  );
}
