import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';
import { useApp } from '../App';
import { FALLBACK_COACHES, FALLBACK_PLAYERS } from '../worldCup2026';

const nationKey = (value = '') => {
  const raw = value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  const aliases = {
    francaise: 'france', francais: 'france',
    bresilienne: 'bresil', bresilien: 'bresil',
    anglaise: 'angleterre', anglais: 'angleterre',
    espagnole: 'espagne', espagnol: 'espagne',
    algerienne: 'algerie', algerien: 'algerie',
    marocaine: 'maroc', marocain: 'maroc',
    senegalaise: 'senegal', senegalais: 'senegal',
  };
  return aliases[raw] || raw;
};

export default function MyTeam() {
  const { user, session } = useApp();
  const [players, setPlayers] = useState([]);
  const [coaches, setCoaches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState(null);
  const [error, setError] = useState(null);
  const [saveStatus, setSaveStatus] = useState(null);

  const [roster, setRoster] = useState([]);
  const [selectedCoach, setSelectedCoach] = useState(null);
  const [formation, setFormation] = useState('4-3-3');
  const [budget, setBudget] = useState(100.0);

  const [search, setSearch] = useState('');
  const [selectedPosition, setSelectedPosition] = useState('ALL');
  const [marketType, setMarketType] = useState('players');

  useEffect(() => {
    const loadMarketData = async () => {
      try {
        const [resPlayers, resCoaches] = await Promise.all([
          fetch(`${API_BASE}/api/players`),
          fetch(`${API_BASE}/api/coaches`),
        ]);

        const dataPlayers = await resPlayers.json();
        const dataCoaches = await resCoaches.json();

        // Les routes retournent soit un tableau soit {data:[], message:"..."}
        const playersList = Array.isArray(dataPlayers)
          ? dataPlayers
          : (dataPlayers.data || []);
        const coachesList = Array.isArray(dataCoaches)
          ? dataCoaches
          : (dataCoaches.data || []);

        // Message de chargement si données vides
        const loadingMsg = (!Array.isArray(dataPlayers) && dataPlayers.message)
          || (!Array.isArray(dataCoaches) && dataCoaches.message)
          || null;

        setPlayers(playersList.length ? playersList : FALLBACK_PLAYERS);
        setCoaches(coachesList.length ? coachesList : FALLBACK_COACHES);
        setLoadingMessage(
          loadingMsg && (!playersList.length || !coachesList.length)
            ? `${loadingMsg} Simulation locale active en attendant les donnees officielles.`
            : loadingMsg
        );

      } catch (err) {
        console.error(err);
        setPlayers(FALLBACK_PLAYERS);
        setCoaches(FALLBACK_COACHES);
        setLoadingMessage('Backend indisponible: simulation locale active.');
      } finally {
        setLoading(false);
      }
    };
    loadMarketData();
  }, []);

  const roundToTwo = (num) => +(Math.round(num + "e+2") + "e-2");
  const getCountryCount = (nationality) => roster.filter(p => nationKey(p.nationality) === nationKey(nationality)).length;

  const handleBuyPlayer = (player) => {
    if (roster.find(p => p.id === player.id)) return;
    if (roster.length >= 15) return alert("Ton effectif est complet (15 joueurs max) !");
    if (budget - player.price < 0) return alert("Budget insuffisant !");
    if (getCountryCount(player.nationality) >= 3) return alert(`Limite : Max 3 joueurs (${player.nationality}) !`);
    if (selectedCoach && nationKey(selectedCoach.nationality) === nationKey(player.nationality)) return alert(`Conflit nationalité Coach.`);

    setRoster(prev => [...prev, player]);
    setBudget(prev => roundToTwo(prev - player.price));
  };

  const handleSellPlayer = (player) => {
    setRoster(prev => prev.filter(p => p.id !== player.id));
    setBudget(prev => roundToTwo(prev + player.price));
  };

  const handleSelectCoach = (coach) => {
    if (selectedCoach && selectedCoach.id === coach.id) {
      setBudget(prev => roundToTwo(prev + coach.price));
      setSelectedCoach(null);
      return;
    }
    const nationalitiesInRoster = roster.map(p => nationKey(p.nationality));
    if (nationalitiesInRoster.includes(nationKey(coach.nationality))) return alert(`Conflit Joueur/Coach (${coach.nationality}).`);
    if (budget - coach.price < 0) return alert("Budget insuffisant coach.");

    const refund = selectedCoach ? selectedCoach.price : 0;
    setSelectedCoach(coach);
    setBudget(prev => roundToTwo(prev + refund - coach.price));
  };

  const autoFillRoster = () => {
    const formations = {
      '4-3-3': { G: 1, D: 4, M: 3, A: 3 },
      '4-4-2': { G: 1, D: 4, M: 4, A: 2 },
      '3-5-2': { G: 1, D: 3, M: 5, A: 2 }
    };
    const bench = { G: 1, D: 1, M: 1, A: 1 };
    const required = Object.fromEntries(Object.entries(formations[formation]).map(([pos, qty]) => [pos, qty + bench[pos]]));
    const picked = [];
    const counts = {};
    let coachForAutofill = selectedCoach;
    const coachReserve = coachForAutofill?.price || Math.min(...coaches.map(c => c.price), 0);
    let remaining = 100 - coachReserve;

    const addPlayer = (player) => {
      const key = nationKey(player.nationality);
      if (picked.some(p => p.id === player.id)) return false;
      if ((counts[key] || 0) >= 3) return false;
      if (coachForAutofill && nationKey(coachForAutofill.nationality) === key) return false;
      if (remaining - player.price < 0) return false;
      picked.push(player);
      counts[key] = (counts[key] || 0) + 1;
      remaining = roundToTwo(remaining - player.price);
      return true;
    };

    Object.entries(required).forEach(([pos, qty]) => {
      for (const player of players.filter(p => p.position === pos).sort((a, b) => a.price - b.price)) {
        if (picked.filter(p => p.position === pos).length >= qty) break;
        addPlayer(player);
      }
    });

    for (const player of players.filter(p => !picked.some(x => x.id === p.id)).sort((a, b) => a.price - b.price)) {
      if (picked.length >= 15) break;
      addPlayer(player);
    }

    if (picked.length < 15) {
      setSaveStatus({ type: 'error', text: 'Auto-Fill impossible avec le marché actuel.' });
      return;
    }

    if (!coachForAutofill) {
      coachForAutofill = [...coaches]
        .sort((a, b) => a.price - b.price)
        .find(coach => coach.price <= remaining && !picked.some(p => nationKey(p.nationality) === nationKey(coach.nationality)));
      if (!coachForAutofill) {
        setSaveStatus({ type: 'error', text: 'Auto-Fill impossible: aucun entraîneur compatible.' });
        return;
      }
      remaining = roundToTwo(remaining - Math.max(0, coachForAutofill.price - coachReserve));
    }

    setRoster(picked);
    setSelectedCoach(coachForAutofill);
    setBudget(remaining);
    setSaveStatus({ type: 'success', text: 'Équipe remplie automatiquement.' });
  };

  const saveRoster = async () => {
    setSaveStatus(null);
    if (roster.length !== 15 || !selectedCoach) {
      setSaveStatus({ type: 'error', text: 'Il faut 15 joueurs et 1 entraîneur.' });
      return;
    }

    const token = session?.access_token || localStorage.getItem('auth_token');
    if (!token) {
      localStorage.setItem('guest_fantasy_roster', JSON.stringify({
        player_ids: roster.map(p => p.id),
        coach_id: selectedCoach.id,
        formation,
        remaining_budget: budget
      }));
      setSaveStatus({ type: 'success', text: 'Equipe gardee en local pour le mode invite.' });
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/fantasy/roster`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          user_id: user?.id || session?.user?.email,
          player_ids: roster.map(p => p.id),
          coach_id: selectedCoach.id,
          formation,
          remaining_budget: budget
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Sauvegarde refusée.');
      setBudget(data.remaining_budget ?? budget);
      setSaveStatus({ type: 'success', text: 'Équipe sauvegardée.' });
    } catch (err) {
      setSaveStatus({ type: 'error', text: err.message });
    }
  };

  const slots = {
    '4-3-3': { D: 4, M: 3, A: 3 },
    '4-4-2': { D: 4, M: 4, A: 2 },
    '3-5-2': { D: 3, M: 5, A: 2 }
  }[formation];

  const renderPitchRow = (pos, maxSlots) => {
    const assignedPlayers = roster.filter(p => p.position === pos);
    const rowItems = [];

    for (let i = 0; i < maxSlots; i++) {
      if (assignedPlayers[i]) {
        const player = assignedPlayers[i];
        rowItems.push(
          <div key={`${pos}-${i}`} className="pitch-player-slot assigned" onClick={() => handleSellPlayer(player)} title="Retirer">
            <div className="jersey-icon">{player.name.split(' ').pop().substring(0,3).toUpperCase()}</div>
            <span className="player-name-pitch">{player.name.split(' ').pop()}</span>
          </div>
        );
      } else {
        rowItems.push(
          <div key={`${pos}-${i}`} className="pitch-player-slot empty" onClick={() => { setMarketType('players'); setSelectedPosition(pos); }}>
            <span className="add-icon">+</span>
            <span className="player-name-pitch empty">Vide</span>
          </div>
        );
      }
    }
    return rowItems;
  };

  const filteredPlayers = players.filter(player => {
    const matchesSearch = player.name.toLowerCase().includes(search.toLowerCase()) ||
                          player.nationality.toLowerCase().includes(search.toLowerCase());
    const matchesPosition = selectedPosition === 'ALL' || player.position === selectedPosition;
    return matchesSearch && matchesPosition;
  });

  if (loading) return <div className="muted" style={{textAlign:'center', marginTop:'5rem'}}>Chargement...</div>;

  return (
    <div className="view fantasy-view">

      {/* BANNER Groq en cours de chargement */}
      {loadingMessage && (
        <div className="sync-info-banner" style={{ margin: '8px 12px 0' }}>
          🔄 {loadingMessage}
        </div>
      )}

      {/* HEADER */}
      <div className="view-header-card">
        <div>
          <h2>Gestion de l'Équipe Fantasy</h2>
          <div className="formation-selector">
            <label>Tactique :</label>
            <select value={formation} onChange={(e) => setFormation(e.target.value)}>
              {['4-3-3', '4-4-2', '3-5-2'].map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
        </div>
        <div className="budget-counter">
          <span className="label">Budget</span>
          <h3 className={budget < 10 ? 'danger' : 'green'}>{budget} M€</h3>
        </div>
      </div>

      <div className="fantasy-actions">
        <button className="mrg-save-btn" type="button" onClick={autoFillRoster}>Auto-Fill</button>
        <button className="auth-submit-btn compact" type="button" onClick={saveRoster}>Sauvegarder</button>
      </div>
      {saveStatus && <div className={`pred-status ${saveStatus.type}`}>{saveStatus.text}</div>}

      <div className="fantasy-main-layout">

        {/* TERRAIN */}
        <div className="pitch-section">
          <div className="real-pitch">
            <div className="goal-area top"></div>
            <div className="penalty-area top"></div>
            <div className="penalty-spot top"></div>
            <div className="center-circle"></div>
            <div className="center-line"></div>
            <div className="penalty-spot bottom"></div>
            <div className="penalty-area bottom"></div>
            <div className="goal-area bottom"></div>

            <div className="coach-spot-wrapper">
              {selectedCoach ? (
                <div className="badge coach-badge active" onClick={() => handleSelectCoach(selectedCoach)} title="Retirer Coach">
                  👔 {selectedCoach.name} <span className="danger">×</span>
                </div>
              ) : (
                <div className="coach-spot-empty" onClick={() => setMarketType('coaches')}>+ Coach</div>
              )}
            </div>

            <div className="pitch-row attack-line">{renderPitchRow('A', slots.A)}</div>
            <div className="pitch-row midfield-line">{renderPitchRow('M', slots.M)}</div>
            <div className="pitch-row defense-line">{renderPitchRow('D', slots.D)}</div>
            <div className="pitch-row goalkeeper-line">{renderPitchRow('G', 1)}</div>
          </div>

          <div className="bench">
            <span className="bench-label">Effectif ({roster.length}/15)</span>
            {roster.map(p => (
              <span key={p.id} className="bench-player" onClick={() => handleSellPlayer(p)}>{p.name}</span>
            ))}
          </div>
        </div>

        {/* MARCHÉ */}
        <div className="market-section card">
          <div className="tab-bar">
            <button className={marketType === 'players' ? 'active' : ''} onClick={() => setMarketType('players')}>Joueurs</button>
            <button className={marketType === 'coaches' ? 'active' : ''} onClick={() => setMarketType('coaches')}>Coaches</button>
          </div>

          <div className="market-content custom-scrollbar">
            {marketType === 'players' ? (
              <>
                <div className="market-filters">
                  <input type="text" className="score-input search" placeholder="🔍 Nom, pays..." value={search} onChange={(e) => setSearch(e.target.value)}/>
                  <div className="filter-bar pos">
                    {['ALL', 'G', 'D', 'M', 'A'].map(pos => (
                      <button key={pos} onClick={() => setSelectedPosition(pos)} className={`filter-btn pos ${selectedPosition === pos ? 'active' : ''}`}>{pos}</button>
                    ))}
                  </div>
                </div>

                {players.length === 0 && loadingMessage && (
                  <div className="empty-state" style={{ padding: '24px 16px' }}>
                    <div className="empty-state-icon">⏳</div>
                    <h4>Joueurs en chargement</h4>
                    <p>Groq scrape les effectifs depuis Olympics. Réessayez dans 30–60 secondes.</p>
                  </div>
                )}

                <div className="market-list">
                  {filteredPlayers.map(player => {
                    const isBought = roster.find(p => p.id === player.id);
                    const countryLimitReached = getCountryCount(player.nationality) >= 3 && !isBought;
                    const coachConflict = selectedCoach && nationKey(selectedCoach.nationality) === nationKey(player.nationality);
                    const isDisabled = countryLimitReached || coachConflict;

                    return (
                      <div key={player.id} className={`market-item player ${isBought ? 'bought' : ''} ${isDisabled ? 'disabled' : ''}`}
                        onClick={() => { if (isBought) handleSellPlayer(player); else if (!isDisabled) handleBuyPlayer(player); }}>
                        <div className="item-details">
                          <span className={`pos-badge ${player.position}`}>{player.position}</span>
                          <span className="item-name">{player.name}</span>
                          <span className="muted item-sub">{player.nationality}</span>
                          {countryLimitReached && <span className="danger tag">(Max 3)</span>}
                          {coachConflict && <span className="danger tag">(Pays bloqué par Coach)</span>}
                        </div>
                        <div className="item-action">
                          {isBought ? 'Vendre' : `${player.price} M€`}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <>
                {coaches.length === 0 && loadingMessage && (
                  <div className="empty-state" style={{ padding: '24px 16px' }}>
                    <div className="empty-state-icon">⏳</div>
                    <h4>Entraîneurs en chargement</h4>
                    <p>Groq scrape les entraîneurs depuis Olympics. Réessayez dans 30–60 secondes.</p>
                  </div>
                )}
                <div className="market-list">
                  {coaches.map(coach => {
                    const isSelected = selectedCoach && selectedCoach.id === coach.id;
                    const hasPlayerConflict = roster.map(p => nationKey(p.nationality)).includes(nationKey(coach.nationality));
                    const isDisabled = hasPlayerConflict && !isSelected;

                    return (
                      <div key={coach.id} className={`market-item coach ${isSelected ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}`}
                        onClick={() => !isDisabled && handleSelectCoach(coach)}>
                        <div className="item-details">
                          <span className="item-name">👔 {coach.name}</span>
                          <span className="muted item-sub">Sélectionneur : {coach.nationality}</span>
                          {hasPlayerConflict && !isSelected && <span className="danger tag">(Conflit Joueur)</span>}
                        </div>
                        <div className="item-action">
                          {isSelected ? 'Retirer' : `${coach.price} M€`}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
