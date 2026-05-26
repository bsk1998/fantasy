import React, { useState, useEffect } from 'react';

export default function MyTeam() {
  const [players, setPlayers] = useState([]);
  const [coaches, setCoaches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
          fetch('http://127.0.0.1:8000/players'),
          fetch('http://127.0.0.1:8000/coaches')
        ]);

        if (!resPlayers.ok || !resCoaches.ok) throw new Error("Échec du chargement du mercato.");

        const dataPlayers = await resPlayers.json();
        const dataCoaches = await resCoaches.json();

        setPlayers(Array.isArray(dataPlayers) ? dataPlayers : []);
        setCoaches(Array.isArray(dataCoaches) ? dataCoaches : []);
      } catch (err) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadMarketData();
  }, []);

  const roundToTwo = (num) => +(Math.round(num + "e+2") + "e-2");
  const getCountryCount = (nationality) => roster.filter(p => p.nationality === nationality).length;

  const handleBuyPlayer = (player) => {
    if (roster.find(p => p.id === player.id)) return;
    if (roster.length >= 15) return alert("Ton effectif est complet (15 joueurs max) !");
    if (budget - player.price < 0) return alert("Budget insuffisant !");
    if (getCountryCount(player.nationality) >= 3) return alert(`Limite : Max 3 joueurs (${player.nationality}) !`);
    if (selectedCoach && selectedCoach.nationality === player.nationality) return alert(`Conflit nationalité Coach.`);

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
    const nationalitiesInRoster = roster.map(p => p.nationality);
    if (nationalitiesInRoster.includes(coach.nationality)) return alert(`Conflit Joueur/Coach (${coach.nationality}).`);
    if (budget - coach.price < 0) return alert("Budget insuffisant coach.");

    const refund = selectedCoach ? selectedCoach.price : 0;
    setSelectedCoach(coach);
    setBudget(prev => roundToTwo(prev + refund - coach.price));
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
      
      {/* HEADER : COMPTEURS & CONTROLES */}
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

      {/* DISPOSITION MAIN GRILLE (CÔTE À CÔTE DESKTOP, EMPILÉ MOBILE) */}
      <div className="fantasy-main-layout">
        
        {/* TERRAIN DU COMPOSANT (COTE GAUCHE) */}
        <div className="pitch-section">
          <div className="real-pitch">
            
            {/* LIGNES & ZONE DE BUTS (DECORATION) */}
            <div className="goal-area top"></div>
            <div className="penalty-area top"></div>
            <div className="penalty-spot top"></div>
            <div className="center-circle"></div>
            <div className="center-line"></div>
            <div className="penalty-spot bottom"></div>
            <div className="penalty-area bottom"></div>
            <div className="goal-area bottom"></div>

            {/* ENTRAÎNEUR (POSITION FIXE) */}
            <div className="coach-spot-wrapper">
              {selectedCoach ? (
                <div className="badge coach-badge active" onClick={() => handleSelectCoach(selectedCoach)} title="Retirer Coach">
                  👔 {selectedCoach.name} <span className="danger">×</span>
                </div>
              ) : (
                <div className="coach-spot-empty" onClick={() => setMarketType('coaches')}>+ Coach</div>
              )}
            </div>

            {/* LIGNES DE JOUEURS */}
            <div className="pitch-row attack-line">{renderPitchRow('A', slots.A)}</div>
            <div className="pitch-row midfield-line">{renderPitchRow('M', slots.M)}</div>
            <div className="pitch-row defense-line">{renderPitchRow('D', slots.D)}</div>
            <div className="pitch-row goalkeeper-line">{renderPitchRow('G', 1)}</div>
          </div>

          {/* BANC DES REMPLAÇANTS */}
          <div className="bench">
            <span className="bench-label">Effectif ({roster.length}/15)</span>
            {roster.map(p => (
              <span key={p.id} className="bench-player" onClick={() => handleSellPlayer(p)}>{p.name}</span>
            ))}
          </div>
        </div>

        {/* MARCHÉ EMBARQUÉ (COTE DROIT DESKTOP, EMPILÉ MOBILE) */}
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

                {/* LISTE DES JOUEURS */}
                <div className="market-list">
                  {filteredPlayers.map(player => {
                    const isBought = roster.find(p => p.id === player.id);
                    const countryLimitReached = getCountryCount(player.nationality) >= 3 && !isBought;
                    const coachConflict = selectedCoach && selectedCoach.nationality === player.nationality;
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
              /* LISTE DES ENTRAÎNEURS */
              <div className="market-list">
                {coaches.map(coach => {
                  const isSelected = selectedCoach && selectedCoach.id === coach.id;
                  const hasPlayerConflict = roster.map(p => p.nationality).includes(coach.nationality);
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
            )}
          </div>
        </div>

      </div>
    </div>
  );
}s