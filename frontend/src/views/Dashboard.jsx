import React, { useState, useEffect } from 'react';

export default function Dashboard() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/leaderboard');
        if (!response.ok) {
          throw new Error(`Erreur serveur : ${response.status}`);
        }
        const data = await response.json();
        setLeaderboard(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error("Erreur fetch leaderboard:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchLeaderboard();
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <p>Chargement du tableau de bord...</p>
      </div>
    );
  }

  return (
    <div className="view">
      <div className="card">
        <h2>Tableau de Bord</h2>
        <p className="subtitle">Suivez les performances en direct de votre groupe d'amis</p>
      </div>

      <div className="card">
        <h3>🏆 Top de la Ligue</h3>
        
        {Array.isArray(leaderboard) && leaderboard.length > 0 ? (
          <table className="score-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Pseudo</th>
                <th>Fantasy</th>
                <th>Pronos</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map((player, index) => {
                const isPodium = index < 3;
                return (
                  <tr key={index} className={isPodium ? 'podium' : ''}>
                    <td>
                      {index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : index + 1}
                    </td>
                    <td style={{ fontWeight: isPodium ? '700' : 'normal' }}>
                      {player.username}
                    </td>
                    <td>{player.score_fantasy} pts</td>
                    <td>{player.score_predictor_scores} pts</td>
                    <td style={{ fontWeight: '700', color: 'var(--accent)' }}>
                      {player.total} pts
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="muted" style={{ textAlign: 'center', fontStyle: 'italic', padding: '1rem' }}>
            Aucune donnée de classement disponible.
          </p>
        )}
      </div>
    </div>
  );
}