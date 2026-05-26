import { useState, useEffect, useCallback } from 'react';
import { useApp } from '../App';
import { API_BASE } from '../config';

// ══════════════════════════════════════════════════════════════════
//  DONNÉES STATIQUES — Structure CDM 2026
// ══════════════════════════════════════════════════════════════════

const CDM_GROUPS = {
  A: ['USA', 'Canada', 'Mexique', 'Jamaïque'],
  B: ['France', 'Belgique', 'Maroc', 'Tunisie'],
  C: ['Brésil', 'Argentine', 'Uruguay', 'Équateur'],
  D: ['Angleterre', 'Allemagne', 'Pays-Bas', 'Croatie'],
  E: ['Espagne', 'Portugal', 'Turquie', 'Grèce'],
  F: ['Japon', 'Corée du Sud', 'Australie', 'Iran'],
  G: ['Sénégal', 'Algérie', 'Nigéria', "Côte d'Ivoire"],
  H: ['Colombie', 'Pologne', 'Serbie', 'Suisse'],
  I: ['Arabie Saoudite', 'Autriche', 'Slovaquie', 'Islande'],
  J: ['Égypte', 'Pérou', 'Bolivie', 'Venezuela'],
  K: ['Costa Rica', 'Panama', 'Honduras', 'Paraguay'],
  L: ['Qatar', 'Arabie Saoudite', 'Irak', 'Syrie'],
};

const KNOCKOUT_ROUNDS = ['r32', 'r16', 'qf', 'sf'];
const ROUND_LABELS = {
  r32: '16èmes de finale',
  r16: 'Huitièmes',
  qf:  'Quarts',
  sf:  'Demi-finales',
};
const ROUND_MATCH_COUNT = { r32: 16, r16: 8, qf: 4, sf: 2 };

const ANNEXE_CATEGORIES = [
  { key: 'top3_buteurs',  label: '⚽ Top 3 Buteurs',           placeholder: 'Ex: Mbappé' },
  { key: 'top3_passeurs', label: '🎯 Top 3 Passeurs',           placeholder: 'Ex: Messi' },
  { key: 'top3_joueurs',  label: '🌟 Top 3 Meilleurs joueurs',  placeholder: 'Ex: Vinicius' },
  { key: 'top3_jeunes',   label: '🔥 Top 3 Meilleurs jeunes',   placeholder: 'Ex: Yamal' },
];

const POINTS_COLORS = { 5: 'var(--green)', 2: 'var(--warning)', 0: 'var(--text-3)' };

const buildEmptyKnockout = () => {
  const rounds = {};
  KNOCKOUT_ROUNDS.forEach(r => {
    rounds[r] = Array.from({ length: ROUND_MATCH_COUNT[r] }, (_, i) => ({
      id: `${r}_${i}`, team1: '', team2: '', winner: '',
    }));
  });
  rounds.troisieme_place = { team1: '', team2: '', winner: '' };
  rounds.finale          = { team1: '', team2: '', winner: '' };
  return rounds;
};

const buildEmptyGroups = () =>
  Object.fromEntries(Object.keys(CDM_GROUPS).map(g => [g, ['', '', '', '']]));

const buildEmptyAnnexes = () =>
  Object.fromEntries(ANNEXE_CATEGORIES.map(c => [c.key, ['', '', '']]));

// ══════════════════════════════════════════════════════════════════
//  SOUS-COMPOSANTS
// ══════════════════════════════════════════════════════════════════

function SaveChip({ status }) {
  if (!status) return null;
  const map = {
    saving: { text: '⏳', color: 'var(--text-2)' },
    saved:  { text: '✓ Enregistré', color: 'var(--green)' },
    error:  { text: '✗ Erreur', color: 'var(--danger)' },
  };
  const s = map[status];
  return (
    <span className="save-chip" style={{ color: s.color }}>{s.text}</span>
  );
}

function MatchRow({ match, savedPrediction, onSave }) {
  const [home, setHome] = useState('');
  const [away, setAway] = useState('');
  const [status, setStatus] = useState(null);

  useEffect(() => {
    if (savedPrediction) {
      setHome(String(savedPrediction.predicted_home ?? ''));
      setAway(String(savedPrediction.predicted_away ?? ''));
    }
  }, [savedPrediction]);

  const isLocked    = match.is_locked;
  const isFinished  = match.is_finished;
  const realHome    = match.home_score;
  const realAway    = match.away_score;
  const pts         = savedPrediction?.points_earned;

  const handleSave = async () => {
    if (home === '' || away === '') return;
    setStatus('saving');
    const err = await onSave(match.id, parseInt(home), parseInt(away));
    setStatus(err ? 'error' : 'saved');
    setTimeout(() => setStatus(null), 2500);
  };

  return (
    <div className={`match-row-card ${isLocked ? 'locked' : ''} ${isFinished ? 'finished' : ''}`}>
      <div className="mrg-meta">
        <span className="mrg-group">{match.group}</span>
        <span className="mrg-date">{match.date}</span>
        {isLocked   && <span className="mrg-lock">🔒 Verrouillé</span>}
        {isFinished && pts != null && (
          <span className="mrg-pts" style={{ color: POINTS_COLORS[pts] ?? 'var(--text-2)' }}>
            +{pts} pts
          </span>
        )}
      </div>

      <div className="mrg-main">
        <div className="team-side home">{match.home}</div>

        <div className="score-inputs-block">
          {isFinished ? (
            <div className="score-result">
              <span>{realHome}</span>
              <span className="score-divider">–</span>
              <span>{realAway}</span>
            </div>
          ) : (
            <>
              <input
                type="number" min="0" max="99"
                className={`score-input-field ${isLocked ? 'disabled' : ''}`}
                value={home}
                onChange={e => setHome(e.target.value.replace(/\D/, ''))}
                disabled={isLocked}
              />
              <span className="score-divider">–</span>
              <input
                type="number" min="0" max="99"
                className={`score-input-field ${isLocked ? 'disabled' : ''}`}
                value={away}
                onChange={e => setAway(e.target.value.replace(/\D/, ''))}
                disabled={isLocked}
              />
            </>
          )}
        </div>

        <div className="team-side away">{match.away}</div>
      </div>

      {!isLocked && !isFinished && (
        <div className="mrg-footer">
          {savedPrediction && (
            <span className="mrg-prev-prono">
              Ton prono : {savedPrediction.predicted_home}–{savedPrediction.predicted_away}
            </span>
          )}
          <div className="mrg-actions">
            <SaveChip status={status} />
            <button
              className="mrg-save-btn"
              onClick={handleSave}
              disabled={home === '' || away === '' || status === 'saving'}
            >
              Sauvegarder
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function GroupAccordion({ groupKey, teams, ranking, onChange }) {
  const [open, setOpen] = useState(false);

  const moveUp = (i) => {
    if (i === 0) return;
    const next = [...ranking];
    [next[i - 1], next[i]] = [next[i], next[i - 1]];
    onChange(groupKey, next);
  };

  const moveDown = (i) => {
    if (i === ranking.length - 1) return;
    const next = [...ranking];
    [next[i], next[i + 1]] = [next[i + 1], next[i]];
    onChange(groupKey, next);
  };

  const rankColors = ['var(--green)', 'var(--accent)', 'var(--warning)', 'var(--danger)'];
  const rankLabels = ['1er', '2ème', '3ème', '4ème'];

  return (
    <div className={`group-accordion ${open ? 'open' : ''}`}>
      <button className="ga-header" onClick={() => setOpen(o => !o)}>
        <span className="ga-title">Groupe {groupKey}</span>
        <div className="ga-preview">
          {teams.slice(0, 2).map((t, i) => (
            <span key={i} className="ga-team-chip" style={{ borderColor: rankColors[i] }}>
              {ranking[i] || t}
            </span>
          ))}
          <span className="ga-dots">···</span>
        </div>
        <span className="ga-arrow">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="ga-body">
          <p className="ga-hint">Glissez ou réordonnez le classement prédit du groupe.</p>
          {ranking.map((team, i) => (
            <div key={i} className="ga-row">
              <span className="ga-pos" style={{ color: rankColors[i], borderColor: rankColors[i] }}>
                {rankLabels[i]}
              </span>
              <select
                className="ga-select"
                value={team}
                onChange={e => {
                  const next = [...ranking];
                  next[i] = e.target.value;
                  onChange(groupKey, next);
                }}
              >
                <option value="">— Choisir —</option>
                {teams.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <div className="ga-arrows">
                <button onClick={() => moveUp(i)}   disabled={i === 0}>▲</button>
                <button onClick={() => moveDown(i)} disabled={i === ranking.length - 1}>▼</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function KnockoutRound({ roundKey, matches, onChange }) {
  return (
    <div className="ko-round">
      <div className="ko-round-label">{ROUND_LABELS[roundKey]}</div>
      {matches.map((match, i) => (
        <div key={match.id} className="ko-match">
          <input
            className="ko-input"
            placeholder="Équipe 1"
            value={match.team1}
            onChange={e => onChange(roundKey, i, 'team1', e.target.value)}
          />
          <span className="ko-vs">vs</span>
          <input
            className="ko-input"
            placeholder="Équipe 2"
            value={match.team2}
            onChange={e => onChange(roundKey, i, 'team2', e.target.value)}
          />
          <select
            className="ko-select-winner"
            value={match.winner}
            onChange={e => onChange(roundKey, i, 'winner', e.target.value)}
          >
            <option value="">Vainqueur ?</option>
            {match.team1 && <option value={match.team1}>{match.team1}</option>}
            {match.team2 && <option value={match.team2}>{match.team2}</option>}
          </select>
        </div>
      ))}
    </div>
  );
}

function AnnexeRow({ catKey, label, placeholder, values, onChange }) {
  return (
    <div className="annexe-block card">
      <div className="annexe-title">{label}</div>
      {[0, 1, 2].map(i => (
        <div key={i} className="annexe-row">
          <span className="annexe-pos">#{i + 1}</span>
          <input
            className="score-input annexe-input"
            placeholder={i === 0 ? placeholder : `${i + 1}ème joueur`}
            value={values[i] ?? ''}
            onChange={e => {
              const next = [...values];
              next[i] = e.target.value;
              onChange(catKey, next);
            }}
          />
        </div>
      ))}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
//  COMPOSANT PRINCIPAL
// ══════════════════════════════════════════════════════════════════
export default function Predictions() {
  const { user, session } = useApp();

  const [activeTab, setActiveTab] = useState('scores');

  const [matches,          setMatches]          = useState([]);
  const [savedPredictions, setSavedPredictions] = useState({});
  const [loadingMatches,   setLoadingMatches]   = useState(true);
  const [matchError,       setMatchError]       = useState(null);

  const [groups,        setGroups]        = useState(buildEmptyGroups);
  const [knockout,      setKnockout]      = useState(buildEmptyKnockout);
  const [bracketSaving, setBracketSaving] = useState(false);
  const [bracketStatus, setBracketStatus] = useState(null);

  const [annexes,        setAnnexes]        = useState(buildEmptyAnnexes);
  const [annexesSaving,  setAnnexesSaving]  = useState(false);
  const [annexesStatus,  setAnnexesStatus]  = useState(null);

  useEffect(() => {
    setGroups(
      Object.fromEntries(
        Object.entries(CDM_GROUPS).map(([g, teams]) => [g, [...teams]])
      )
    );
  }, []);

  const authHeaders = useCallback(() => ({
    'Content-Type': 'application/json',
    ...(session?.access_token
      ? { Authorization: `Bearer ${session.access_token}` }
      : {}),
  }), [session]);

  // ✅ FIX : tous les fetch utilisent maintenant le préfixe /api
  useEffect(() => {
    const load = async () => {
      setLoadingMatches(true);
      setMatchError(null);
      try {
        const [resMatches, resPronos] = await Promise.all([
          fetch(`${API_BASE}/api/matches`),
          user?.id
            ? fetch(`${API_BASE}/api/predictions/score/${user.id}`, { headers: authHeaders() })
            : Promise.resolve(null),
        ]);

        if (!resMatches.ok) throw new Error(`Erreur matchs : ${resMatches.status}`);
        const matchData = await resMatches.json();
        setMatches(Array.isArray(matchData) ? matchData : []);

        if (resPronos?.ok) {
          const pronoData = await resPronos.json();
          const byMatchId = Object.fromEntries(
            (Array.isArray(pronoData) ? pronoData : []).map(p => [p.match_id, p])
          );
          setSavedPredictions(byMatchId);
        }
      } catch (err) {
        setMatchError(err.message);
      } finally {
        setLoadingMatches(false);
      }
    };
    load();
  }, [user?.id]);

  const handleSaveScore = useCallback(async (matchId, home, away) => {
    if (!user?.id) return 'no_user';
    try {
      const res = await fetch(`${API_BASE}/api/predictions/score`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          user_id: String(user.id),
          match_id: matchId,
          predicted_home: home,
          predicted_away: away,
        }),
      });
      if (!res.ok) throw new Error();
      setSavedPredictions(prev => ({
        ...prev,
        [matchId]: { ...prev[matchId], predicted_home: home, predicted_away: away, match_id: matchId },
      }));
      return null;
    } catch {
      return 'error';
    }
  }, [user?.id, authHeaders]);

  const handleGroupChange = useCallback((groupKey, newRanking) => {
    setGroups(prev => ({ ...prev, [groupKey]: newRanking }));
  }, []);

  const handleKnockoutChange = useCallback((roundKey, matchIdx, field, value) => {
    setKnockout(prev => {
      const round = Array.isArray(prev[roundKey]) ? [...prev[roundKey]] : { ...prev[roundKey] };
      if (Array.isArray(round)) {
        round[matchIdx] = { ...round[matchIdx], [field]: value };
      } else {
        round[field] = value;
      }
      return { ...prev, [roundKey]: round };
    });
  }, []);

  const handleFinalChange = useCallback((matchKey, field, value) => {
    setKnockout(prev => ({
      ...prev,
      [matchKey]: { ...prev[matchKey], [field]: value },
    }));
  }, []);

  const handleSaveBracket = async () => {
    if (!user?.id) return;
    setBracketSaving(true);
    setBracketStatus(null);
    try {
      const res = await fetch(`${API_BASE}/api/predictions/bracket`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          user_id: String(user.id),
          bracket_data: { groupes: groups, ...knockout },
        }),
      });
      setBracketStatus(res.ok ? 'saved' : 'error');
    } catch {
      setBracketStatus('error');
    } finally {
      setBracketSaving(false);
      setTimeout(() => setBracketStatus(null), 3000);
    }
  };

  const handleAnnexeChange = useCallback((catKey, newValues) => {
    setAnnexes(prev => ({ ...prev, [catKey]: newValues }));
  }, []);

  const handleSaveAnnexes = async () => {
    if (!user?.id) return;
    setAnnexesSaving(true);
    setAnnexesStatus(null);
    try {
      const res = await fetch(`${API_BASE}/api/predictions/annexes`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ user_id: String(user.id), annexes }),
      });
      setAnnexesStatus(res.ok ? 'saved' : 'error');
    } catch {
      setAnnexesStatus('error');
    } finally {
      setAnnexesSaving(false);
      setTimeout(() => setAnnexesStatus(null), 3000);
    }
  };

  const matchesByGroup = matches.reduce((acc, m) => {
    const g = m.group || 'Autre';
    if (!acc[g]) acc[g] = [];
    acc[g].push(m);
    return acc;
  }, {});

  const pronosRemplis  = Object.keys(savedPredictions).length;
  const totalMatchs    = matches.filter(m => !m.is_finished && !m.is_locked).length;

  return (
    <div className="predictions-view">

      <div className="pred-header">
        <div>
          <h2>🎯 Pronostics</h2>
          <p className="pred-subtitle">WC 2026 — Ligue Boulzazen</p>
        </div>
        <div className="pred-progress-pill">
          <span className="pp-val">{pronosRemplis}</span>
          <span className="pp-sep">/</span>
          <span className="pp-total">{totalMatchs}</span>
          <span className="pp-label">matchs</span>
        </div>
      </div>

      <div className="pred-tabs">
        {[
          { key: 'scores',  label: '📊 Scores' },
          { key: 'bracket', label: '🗺️ Tableau' },
          { key: 'annexes', label: '🎖️ Annexes' },
        ].map(tab => (
          <button
            key={tab.key}
            className={`pred-tab-btn ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'scores' && (
        <div className="tab-content fade-in">
          <div className="predictions-card">
            <div className="predictions-instructions">
              ✅ Score exact = <strong>+5 pts</strong> · Bonne issue = <strong>+2 pts</strong> · Mauvais pronostic = <strong>0 pt</strong>
            </div>

            {loadingMatches && (
              <div className="loading-spinner">Chargement des matchs...</div>
            )}

            {matchError && (
              <div className="pred-error">
                ⚠️ {matchError}
                <br /><span style={{ fontSize: '0.75rem', opacity: 0.7 }}>Vérifiez que le backend est démarré.</span>
              </div>
            )}

            {!loadingMatches && !matchError && matches.length === 0 && (
              <div className="empty-state" style={{ padding: '32px' }}>
                <div className="empty-state-icon">📭</div>
                <h4>Aucun match disponible</h4>
                <p>Les matchs seront ajoutés avant le coup d'envoi de la compétition.</p>
              </div>
            )}

            {!loadingMatches && Object.entries(matchesByGroup).map(([groupName, groupMatches]) => (
              <div key={groupName} className="matches-group">
                <div className="matches-group-title">{groupName}</div>
                {groupMatches.map(match => (
                  <MatchRow
                    key={match.id}
                    match={match}
                    savedPrediction={savedPredictions[match.id]}
                    onSave={handleSaveScore}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'bracket' && (
        <div className="tab-content fade-in">

          <div className="bracket-section-title">
            <span>Phase de Groupes</span>
            <span className="bst-pts">+5 pts par classement exact</span>
          </div>

          <div className="groups-grid">
            {Object.keys(CDM_GROUPS).map(g => (
              <GroupAccordion
                key={g}
                groupKey={g}
                teams={CDM_GROUPS[g]}
                ranking={groups[g] ?? [...CDM_GROUPS[g]]}
                onChange={handleGroupChange}
              />
            ))}
          </div>

          <div className="bracket-section-title" style={{ marginTop: 8 }}>
            <span>Phase Éliminatoire</span>
            <span className="bst-pts">+5 pts présence · +5 match · +5 vainqueur</span>
          </div>

          <div className="ko-section">
            {KNOCKOUT_ROUNDS.map(r => (
              <KnockoutRound
                key={r}
                roundKey={r}
                matches={knockout[r]}
                onChange={handleKnockoutChange}
              />
            ))}

            <div className="ko-round">
              <div className="ko-round-label" style={{ color: 'var(--warning)' }}>🥉 Match 3ème place</div>
              <div className="ko-match">
                <input className="ko-input" placeholder="Équipe 1"
                  value={knockout.troisieme_place?.team1 ?? ''}
                  onChange={e => handleFinalChange('troisieme_place', 'team1', e.target.value)} />
                <span className="ko-vs">vs</span>
                <input className="ko-input" placeholder="Équipe 2"
                  value={knockout.troisieme_place?.team2 ?? ''}
                  onChange={e => handleFinalChange('troisieme_place', 'team2', e.target.value)} />
                <select className="ko-select-winner"
                  value={knockout.troisieme_place?.winner ?? ''}
                  onChange={e => handleFinalChange('troisieme_place', 'winner', e.target.value)}>
                  <option value="">Vainqueur ?</option>
                  {knockout.troisieme_place?.team1 && <option value={knockout.troisieme_place.team1}>{knockout.troisieme_place.team1}</option>}
                  {knockout.troisieme_place?.team2 && <option value={knockout.troisieme_place.team2}>{knockout.troisieme_place.team2}</option>}
                </select>
              </div>
            </div>

            <div className="ko-round">
              <div className="ko-round-label" style={{ color: 'var(--gold)' }}>🏆 FINALE</div>
              <div className="ko-match finale-match">
                <input className="ko-input" placeholder="Finaliste 1"
                  value={knockout.finale?.team1 ?? ''}
                  onChange={e => handleFinalChange('finale', 'team1', e.target.value)} />
                <span className="ko-vs">⚽</span>
                <input className="ko-input" placeholder="Finaliste 2"
                  value={knockout.finale?.team2 ?? ''}
                  onChange={e => handleFinalChange('finale', 'team2', e.target.value)} />
                <select className="ko-select-winner"
                  value={knockout.finale?.winner ?? ''}
                  onChange={e => handleFinalChange('finale', 'winner', e.target.value)}>
                  <option value="">Champion du Monde ?</option>
                  {knockout.finale?.team1 && <option value={knockout.finale.team1}>{knockout.finale.team1}</option>}
                  {knockout.finale?.team2 && <option value={knockout.finale.team2}>{knockout.finale.team2}</option>}
                </select>
              </div>
            </div>
          </div>

          <div className="pred-save-bar">
            <SaveChip status={bracketStatus} />
            <button
              className="btn-save-predictions"
              onClick={handleSaveBracket}
              disabled={bracketSaving}
            >
              {bracketSaving ? '⏳ Sauvegarde...' : '💾 Sauvegarder le tableau'}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'annexes' && (
        <div className="tab-content fade-in">
          <div className="predictions-card" style={{ padding: '12px 14px 4px' }}>
            <p className="predictions-instructions">
              Pronostiquez les <strong>Top 3</strong> de chaque catégorie avant le coup d'envoi.
              Bonne place exacte = <strong>+5 pts</strong> · Dans le Top 3 = <strong>+2 pts</strong>
            </p>
          </div>

          {ANNEXE_CATEGORIES.map(cat => (
            <AnnexeRow
              key={cat.key}
              catKey={cat.key}
              label={cat.label}
              placeholder={cat.placeholder}
              values={annexes[cat.key]}
              onChange={handleAnnexeChange}
            />
          ))}

          <div className="pred-save-bar">
            <SaveChip status={annexesStatus} />
            <button
              className="btn-save-predictions"
              onClick={handleSaveAnnexes}
              disabled={annexesSaving}
            >
              {annexesSaving ? '⏳ Sauvegarde...' : '💾 Sauvegarder les prédictions'}
            </button>
          </div>
        </div>
      )}

    </div>
  );
}