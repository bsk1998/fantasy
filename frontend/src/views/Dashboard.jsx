import { useState, useEffect } from 'react';
import { useApp } from '../App';
import { API_BASE } from '../config';

const TrophyIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <polyline points="8,21 12,21 16,21"/><line x1="12" y1="17" x2="12" y2="21"/>
    <path d="M7 4h10v7a5 5 0 01-10 0z"/>
    <path d="M5 4H3v4a4 4 0 004 4"/><path d="M19 4h2v4a4 4 0 01-4 4"/>
  </svg>
);

const BoltIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
  </svg>
);

const StarIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
    <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/>
  </svg>
);

const ChartIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/>
  </svg>
);

const RefreshIcon = ({ spinning }) => (
  <svg
    width="13" height="13" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
    style={{ animation: spinning ? 'spin 1s linear infinite' : 'none' }}
  >
    <polyline points="23,4 23,10 17,10"/>
    <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
  </svg>
);

const MEDALS  = ['🥇', '🥈', '🥉'];
const MEDALS_COLORS = ['#ffd700', '#94a3b8', '#b5703a'];

function getRankSuffix(n) {
  if (n === 1) return 'er';
  return 'ème';
}

function ScoreCard({ label, value, icon, color, sublabel }) {
  return (
    <div className="score-mode-card" style={{ '--card-accent': color }}>
      <div className="smc-icon" style={{ color }}>{icon}</div>
      <div className="smc-body">
        <div className="smc-label">{label}</div>
        <div className="smc-value" style={{ color }}>{value ?? 0}</div>
        {sublabel && <div className="smc-sub">{sublabel}</div>}
      </div>
    </div>
  );
}

function LeaderboardRow({ entry, index, currentUsername }) {
  const isSelf = entry.username === currentUsername;
  const medal  = MEDALS[index];
  const isPodium = index < 3;

  return (
    <div className={`lb-row ${isPodium ? 'is-podium' : ''} ${isSelf ? 'is-self' : ''}`}>
      <div className="lb-row-rank">
        {medal || <span className="lb-row-num">{index + 1}</span>}
      </div>
      <div className="lb-row-info">
        <span className="lb-row-name">
          {entry.username}
          {isSelf && <span className="self-badge">Toi</span>}
        </span>
        <div className="lb-row-breakdown">
          <span style={{ color: 'var(--green)' }}>⚡ {entry.fantasy ?? 0}</span>
          <span style={{ color: 'var(--accent)' }}>🎯 {entry.scores ?? entry.score_predictor_scores ?? 0}</span>
          <span style={{ color: 'var(--gold)' }}>🗺️ {entry.bracket ?? entry.score_predictor_tableaux ?? 0}</span>
        </div>
      </div>
      <div className="lb-row-total" style={{ color: isPodium ? MEDALS_COLORS[index] : 'var(--text)' }}>
        {entry.total ?? 0}
        <span className="lb-row-pts">pts</span>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user, syncData } = useApp();

  const [leaderboard, setLeaderboard] = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [refreshing,  setRefreshing]  = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [userRank,    setUserRank]    = useState(null);
  const [error,       setError]       = useState(null);

  const fetchLeaderboard = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      // ✅ FIX : ajout du préfixe /api pour le proxy Vite
      const res = await fetch(`${API_BASE}/api/leaderboard`);
      if (!res.ok) throw new Error(`Erreur ${res.status}`);
      const data = await res.json();
      const sorted = Array.isArray(data)
        ? [...data].sort((a, b) => (b.total ?? 0) - (a.total ?? 0))
        : [];
      setLeaderboard(sorted);
      setLastUpdated(new Date());

      if (user?.username) {
        const idx = sorted.findIndex(e => e.username === user.username);
        setUserRank(idx >= 0 ? idx + 1 : null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchLeaderboard(); }, []);

  const displayTotal = user?.total ?? 0;

  const updatedStr = lastUpdated
    ? lastUpdated.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    : null;

  const top3 = leaderboard.slice(0, 3);

  return (
    <div className="view dashboard-view">

      <div className="dash-hero">
        <div className="dash-hero-top">
          <div className="dash-hero-left">
            <div className="dash-welcome">Bienvenue,</div>
            <div className="dash-username">{user?.username ?? '—'}</div>
            {userRank && (
              <div className="dash-rank">
                <TrophyIcon />
                <span>{userRank}{getRankSuffix(userRank)} sur {leaderboard.length}</span>
              </div>
            )}
          </div>
          <div className="dash-hero-total">
            <div className="dash-total-label">Score total</div>
            <div className="dash-total-val">{displayTotal.toLocaleString()}</div>
            <div className="dash-total-unit">pts</div>
          </div>
        </div>

        <div className="dash-scores-grid">
          <ScoreCard
            label="Fantasy"
            value={user?.score_fantasy ?? user?.fantasy ?? 0}
            icon={<BoltIcon />}
            color="var(--green)"
            sublabel="équipe"
          />
          <ScoreCard
            label="Pronos"
            value={user?.score_pronos_scores ?? user?.scores ?? 0}
            icon={<ChartIcon />}
            color="var(--accent)"
            sublabel="scores"
          />
          <ScoreCard
            label="Tableau"
            value={user?.score_bracket ?? user?.bracket ?? 0}
            icon={<StarIcon />}
            color="var(--gold)"
            sublabel="bracket"
          />
          <ScoreCard
            label="Annexes"
            value={user?.score_annexes ?? user?.annexes ?? 0}
            icon="🎖️"
            color="#a78bfa"
            sublabel="bonus"
          />
        </div>
      </div>

      {syncData && (
        <div className="sync-info-banner">
          <BoltIcon />
          <span>
            Synchronisé — {syncData.matchs_scraped ?? 0} matchs · {syncData.joueurs_recalculés ?? 0} joueurs · {syncData.pronos_calculés ?? 0} pronos
          </span>
          {updatedStr && <span className="sync-time">{updatedStr}</span>}
        </div>
      )}

      <div className="dash-section-header">
        <h3>🏆 Classement de la Ligue</h3>
        <button
          className={`refresh-btn ${refreshing ? 'spinning' : ''}`}
          onClick={() => fetchLeaderboard(true)}
          disabled={refreshing}
          title="Actualiser"
        >
          <RefreshIcon spinning={refreshing} />
          {refreshing ? 'Màj...' : 'Actualiser'}
        </button>
      </div>

      {error && (
        <div className="dash-error">
          ⚠️ {error} — Le backend est peut-être hors ligne.
        </div>
      )}

      {loading && !error && (
        <div className="loading-spinner">Chargement du classement...</div>
      )}

      {!loading && !error && top3.length > 0 && (
        <div className="dash-podium">
          {top3[1] && (
            <div className="podium-card second">
              <div className="podium-medal">🥈</div>
              <div className="podium-name">{top3[1].username}</div>
              <div className="podium-pts" style={{ color: '#94a3b8' }}>{top3[1].total ?? 0} pts</div>
              <div className="podium-bar" style={{ height: 50, background: '#94a3b8' }} />
            </div>
          )}
          {top3[0] && (
            <div className="podium-card first">
              <div className="podium-crown">👑</div>
              <div className="podium-medal">🥇</div>
              <div className="podium-name">{top3[0].username}</div>
              <div className="podium-pts" style={{ color: 'var(--gold)' }}>{top3[0].total ?? 0} pts</div>
              <div className="podium-bar" style={{ height: 70, background: 'var(--gold)' }} />
            </div>
          )}
          {top3[2] && (
            <div className="podium-card third">
              <div className="podium-medal">🥉</div>
              <div className="podium-name">{top3[2].username}</div>
              <div className="podium-pts" style={{ color: '#b5703a' }}>{top3[2].total ?? 0} pts</div>
              <div className="podium-bar" style={{ height: 36, background: '#b5703a' }} />
            </div>
          )}
        </div>
      )}

      {!loading && !error && leaderboard.length > 0 && (
        <div className="card dash-lb-card">
          {leaderboard.map((entry, i) => (
            <LeaderboardRow
              key={entry.username}
              entry={entry}
              index={i}
              currentUsername={user?.username}
            />
          ))}
        </div>
      )}

      {!loading && !error && leaderboard.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">🏟️</div>
          <h4>Ligue vide</h4>
          <p>Aucun joueur n'a encore rejoint la ligue. Partagez le lien d'invitation !</p>
        </div>
      )}

      <div className="card dash-rules-hint">
        <div className="rules-hint-title">📋 Rappel du barème</div>
        <div className="rules-hint-grid">
          <div className="rule-item">
            <span className="rule-icon" style={{ color: 'var(--green)' }}>⚡</span>
            <span className="rule-text"><strong>Fantasy</strong> — Points joueurs + entraîneur</span>
          </div>
          <div className="rule-item">
            <span className="rule-icon" style={{ color: 'var(--accent)' }}>🎯</span>
            <span className="rule-text"><strong>Pronos</strong> — Score exact +5 / Bonne issue +2</span>
          </div>
          <div className="rule-item">
            <span className="rule-icon" style={{ color: 'var(--gold)' }}>🗺️</span>
            <span className="rule-text"><strong>Tableau</strong> — +5 pts par bonne prédiction</span>
          </div>
          <div className="rule-item">
            <span className="rule-icon" style={{ color: '#a78bfa' }}>🎖️</span>
            <span className="rule-text"><strong>Annexes</strong> — Top 3 buteurs/passeurs/joueurs</span>
          </div>
        </div>
      </div>

    </div>
  );
}