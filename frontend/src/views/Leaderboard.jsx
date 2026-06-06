/**
 * Leaderboard.jsx — Classement général Fantasy Boulzazen WC 2026
 * ================================================================
 * ✅ Confidentiel par conception : on affiche UNIQUEMENT les scores,
 *    jamais les compositions d'équipe ou les pronostics des autres.
 * ✅ Fix : normalisation des champs (scores/score_predictor_scores)
 *          pour compatibilité avec les deux formats de réponse API.
 * ✅ Fix : ajout du préfixe /api pour le proxy Vite en développement.
 */

import { useEffect, useState, useCallback } from "react";
import { API_BASE } from "../config";
import { useApp } from "../App";

const MEDALS = ["🥇", "🥈", "🥉"];
const MEDALS_COLORS = ["#ffd700", "#94a3b8", "#b5703a"];

const SORT_OPTIONS = [
  { key: "total",   label: "🌍 Global"  },
  { key: "fantasy", label: "⚽ Fantasy" },
  { key: "scores",  label: "🎯 Scores"  },
  { key: "bracket", label: "🗺️ Bracket" },
  { key: "annexes", label: "🎖️ Annexes" },
];

/**
 * Normalise une entrée du leaderboard pour avoir des champs cohérents,
 * quelle que soit la version de l'API qui répond.
 */
function normalizeEntry(u) {
  const fantasy  = u.fantasy  ?? u.score_fantasy            ?? 0;
  const scores   = u.scores   ?? u.score_predictor_scores   ?? 0;
  const bracket  = u.bracket  ?? u.score_predictor_tableaux ?? 0;
  const annexes  = u.annexes  ?? u.score_top_individuel     ?? 0;
  const total    = u.total    ?? (fantasy + scores + bracket + annexes);
  return {
    username: u.username || u.email || "—",
    fantasy,
    scores,
    bracket,
    annexes,
    total,
  };
}

function LeaderboardRow({ entry, index, currentUsername }) {
  const isSelf   = entry.username === currentUsername;
  const isPodium = index < 3;
  const medal    = MEDALS[index];

  return (
    <tr
      style={{
        background: isSelf
          ? "rgba(0,230,118,0.05)"
          : isPodium
            ? "rgba(255,255,255,0.02)"
            : "transparent",
        borderLeft: isSelf ? "2px solid var(--green)" : "2px solid transparent",
      }}
    >
      {/* Rang */}
      <td style={{ padding: "10px 8px", textAlign: "center", fontSize: "1.1rem" }}>
        {medal || <span style={{ color: "var(--text-3)", fontSize: "0.82rem" }}>{index + 1}</span>}
      </td>

      {/* Pseudo */}
      <td style={{ padding: "10px 8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontWeight: 700, fontSize: "0.88rem" }}>
            {entry.username}
          </span>
          {isSelf && (
            <span style={{
              background: "rgba(0,230,118,0.15)",
              border: "1px solid rgba(0,230,118,0.3)",
              borderRadius: 50, padding: "1px 7px",
              fontSize: "0.6rem", fontWeight: 700,
              color: "var(--green)", letterSpacing: "0.05em",
              flexShrink: 0,
            }}>
              Toi
            </span>
          )}
        </div>
        {/* Détail par mode — visible pour tous (que les scores, pas les équipes) */}
        <div style={{
          display: "flex", gap: 8,
          fontSize: "0.68rem", color: "var(--text-2)",
          marginTop: 3, flexWrap: "wrap",
        }}>
          <span style={{ color: "var(--green)" }}>⚡ {entry.fantasy}</span>
          <span style={{ color: "var(--accent)" }}>🎯 {entry.scores}</span>
          <span style={{ color: "var(--gold)" }}>🗺️ {entry.bracket}</span>
          <span style={{ color: "#a78bfa" }}>🎖️ {entry.annexes}</span>
        </div>
      </td>

      {/* Total */}
      <td style={{ padding: "10px 8px", textAlign: "right" }}>
        <span style={{
          fontFamily: "Rajdhani, sans-serif",
          fontSize: isPodium ? "1.3rem" : "1.15rem",
          fontWeight: 700,
          color: isPodium ? MEDALS_COLORS[index] : "var(--text)",
        }}>
          {entry.total}
        </span>
        <div style={{ fontSize: "0.6rem", color: "var(--text-3)", letterSpacing: "0.08em" }}>
          pts
        </div>
      </td>
    </tr>
  );
}

export default function Leaderboard() {
  const { user } = useApp();

  const [raw,      setRaw]      = useState([]);
  const [sortKey,  setSortKey]  = useState("total");
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [lastSync, setLastSync] = useState(null);

  const fetchLeaderboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/leaderboard`);
      if (!res.ok) throw new Error(`Erreur ${res.status}`);
      const data = await res.json();
      setRaw(Array.isArray(data) ? data : []);
      setLastSync(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchLeaderboard(); }, [fetchLeaderboard]);

  // Normaliser + trier
  const sorted = raw
    .map(normalizeEntry)
    .sort((a, b) => (b[sortKey] ?? 0) - (a[sortKey] ?? 0));

  const top3 = sorted.slice(0, 3);

  const currentUsername = user?.username || "";

  return (
    <div className="view">

      {/* ── TITRE ── */}
      <div style={{
        background: "linear-gradient(135deg, #0b1e45 0%, #071530 100%)",
        border: "1px solid var(--border)",
        borderRadius: 14, padding: "16px 14px",
        position: "relative", overflow: "hidden",
      }}>
        <div style={{
          position: "absolute", top: -20, right: -10,
          width: 100, height: 100,
          background: "radial-gradient(circle, rgba(255,215,0,0.1) 0%, transparent 70%)",
          borderRadius: "50%", pointerEvents: "none",
        }}/>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.2rem", letterSpacing: "0.08em" }}>
              🏆 Classement Général
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "0.72rem", color: "var(--text-2)" }}>
              Scores cumulés · Tous les modes
            </p>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "Rajdhani, sans-serif", fontSize: "1.8rem", fontWeight: 700, color: "var(--gold)", lineHeight: 1 }}>
              {sorted.length}
            </div>
            <div style={{ fontSize: "0.65rem", color: "var(--text-3)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
              joueurs
            </div>
          </div>
        </div>
        {lastSync && (
          <div style={{
            marginTop: 10, fontSize: "0.68rem", color: "var(--text-3)",
            display: "flex", alignItems: "center", gap: 6,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)", display: "inline-block" }}/>
            Mis à jour à {lastSync.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
          </div>
        )}
      </div>

      {/* ── PODIUM ── */}
      {!loading && !error && top3.length >= 2 && (
        <div style={{
          display: "flex", alignItems: "flex-end", justifyContent: "center",
          gap: 6, padding: "0 4px",
        }}>
          {/* 2e place */}
          {top3[1] && (
            <div style={{
              flex: 1,
              background: "var(--surface)",
              border: "1px solid rgba(148,163,184,0.3)",
              borderRadius: "var(--radius) var(--radius) 0 0",
              padding: "10px 6px 0",
              textAlign: "center",
            }}>
              <div style={{ fontSize: "1.4rem" }}>🥈</div>
              <div style={{ fontSize: "0.75rem", fontWeight: 800, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {top3[1].username}
              </div>
              <div style={{ fontFamily: "Rajdhani, sans-serif", fontSize: "1rem", fontWeight: 700, color: "#94a3b8", marginBottom: 4 }}>
                {top3[1].total} pts
              </div>
              <div style={{ height: 50, background: "#94a3b8", borderRadius: "3px 3px 0 0", opacity: 0.4 }}/>
            </div>
          )}

          {/* 1re place */}
          {top3[0] && (
            <div style={{
              flex: 1.2,
              background: "linear-gradient(180deg, rgba(255,215,0,0.07) 0%, var(--surface) 100%)",
              border: "1px solid rgba(255,215,0,0.4)",
              borderRadius: "var(--radius) var(--radius) 0 0",
              padding: "10px 6px 0",
              textAlign: "center",
              position: "relative",
            }}>
              <div style={{ position: "absolute", top: -18, fontSize: "1.2rem" }}>👑</div>
              <div style={{ fontSize: "1.4rem" }}>🥇</div>
              <div style={{ fontSize: "0.8rem", fontWeight: 800, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {top3[0].username}
              </div>
              <div style={{ fontFamily: "Rajdhani, sans-serif", fontSize: "1.1rem", fontWeight: 700, color: "var(--gold)", marginBottom: 4 }}>
                {top3[0].total} pts
              </div>
              <div style={{ height: 70, background: "var(--gold)", borderRadius: "3px 3px 0 0", opacity: 0.4 }}/>
            </div>
          )}

          {/* 3e place */}
          {top3[2] && (
            <div style={{
              flex: 1,
              background: "var(--surface)",
              border: "1px solid rgba(181,112,58,0.3)",
              borderRadius: "var(--radius) var(--radius) 0 0",
              padding: "10px 6px 0",
              textAlign: "center",
            }}>
              <div style={{ fontSize: "1.4rem" }}>🥉</div>
              <div style={{ fontSize: "0.75rem", fontWeight: 800, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {top3[2].username}
              </div>
              <div style={{ fontFamily: "Rajdhani, sans-serif", fontSize: "1rem", fontWeight: 700, color: "#b5703a", marginBottom: 4 }}>
                {top3[2].total} pts
              </div>
              <div style={{ height: 36, background: "#b5703a", borderRadius: "3px 3px 0 0", opacity: 0.4 }}/>
            </div>
          )}
        </div>
      )}

      {/* ── FILTRES DE TRI ── */}
      <div className="filter-bar">
        {SORT_OPTIONS.map(({ key, label }) => (
          <button
            key={key}
            className={`filter-btn ${sortKey === key ? "active" : ""}`}
            onClick={() => setSortKey(key)}
          >
            {label}
          </button>
        ))}
        <button
          className="filter-btn"
          onClick={fetchLeaderboard}
          disabled={loading}
          style={{ marginLeft: "auto" }}
        >
          {loading ? "⏳" : "🔄"}
        </button>
      </div>

      {/* ── ÉTATS ── */}
      {loading && (
        <div className="loading-spinner">Chargement du classement...</div>
      )}

      {error && !loading && (
        <div style={{
          background: "rgba(244,63,94,0.08)",
          border: "1px solid rgba(244,63,94,0.25)",
          borderRadius: "var(--radius-sm)",
          padding: "10px 14px",
          fontSize: "0.8rem", color: "var(--danger)",
        }}>
          ⚠️ {error} — Le backend est peut-être hors ligne.
        </div>
      )}

      {!loading && !error && sorted.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">🏟️</div>
          <h4>Ligue vide</h4>
          <p>Aucun joueur inscrit pour le moment. Partagez le lien de l'application !</p>
        </div>
      )}

      {/* ── TABLE COMPLÈTE ── */}
      {!loading && !error && sorted.length > 0 && (
        <section className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="score-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th style={{ padding: "8px 8px", width: 40, textAlign: "center" }}>#</th>
                <th style={{ padding: "8px 8px" }}>Joueur</th>
                <th style={{ padding: "8px 8px", textAlign: "right" }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((entry, i) => (
                <LeaderboardRow
                  key={entry.username}
                  entry={entry}
                  index={i}
                  currentUsername={currentUsername}
                />
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* ── NOTE CONFIDENTIALITÉ ── */}
      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm)",
        padding: "10px 14px",
        fontSize: "0.72rem", color: "var(--text-3)",
        lineHeight: 1.5,
        display: "flex", gap: 8,
      }}>
        <span>🔒</span>
        <span>
          Seuls les <strong style={{ color: "var(--text-2)" }}>scores totaux</strong> sont visibles ici.
          Les compositions d'équipes et pronostics détaillés des autres joueurs restent confidentiels jusqu'à la fin du tournoi.
        </span>
      </div>

    </div>
  );
}