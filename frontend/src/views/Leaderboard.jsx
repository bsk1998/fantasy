import { useEffect, useState } from "react";
import { API_BASE } from "../config";

const MEDALS = ["🥇", "🥈", "🥉"];

export default function Leaderboard() {
  const [data,    setData]    = useState([]);
  const [sortKey, setSortKey] = useState("total");

  useEffect(() => {
    fetch(`${API_BASE}/leaderboard`)
      .then((r) => r.json())
      .then(setData)
      .catch(console.error);
  }, []);

  const sorted = [...data].sort((a, b) => b[sortKey] - a[sortKey]);

  return (
    <div className="view">
      <h2>🏆 Classement Général</h2>

      <div className="filter-bar">
        {[
          { key: "total",   label: "Global" },
          { key: "fantasy", label: "Fantasy" },
          { key: "scores",  label: "Scores" },
          { key: "bracket", label: "Bracket" },
        ].map(({ key, label }) => (
          <button
            key={key}
            className={`filter-btn ${sortKey === key ? "active" : ""}`}
            onClick={() => setSortKey(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {sorted.length === 0 ? (
        <p className="muted">Aucune donnée disponible.</p>
      ) : (
        <section className="card">
          <table className="score-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Pseudo</th>
                <th>Fantasy</th>
                <th>Scores</th>
                <th>Bracket</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((u, i) => (
                <tr key={u.username} className={i < 3 ? "podium" : ""}>
                  <td>{MEDALS[i] || i + 1}</td>
                  <td>{u.username}</td>
                  <td>{u.fantasy}</td>
                  <td>{u.scores}</td>
                  <td>{u.bracket}</td>
                  <td><strong>{u.total}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
