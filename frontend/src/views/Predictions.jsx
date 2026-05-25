import React, { useState } from 'react';

export default function Predictions() {
  const [activeTab, setActiveTab] = useState('scores');
  
  // Données mockées en attendant ta route API /matches
  const [matches, setMatches] = useState([
    { id: 1, home: 'USA', away: 'Canada', group: 'Groupe A', homeScore: '', awayScore: '' },
    { id: 2, home: 'Mexique', away: 'Guatemala', group: 'Groupe A', homeScore: '', awayScore: '' },
    { id: 3, home: 'France', away: 'Belgique', group: 'Groupe B', homeScore: '', awayScore: '' },
    { id: 4, home: 'Angleterre', away: 'Espagne', group: 'Groupe B', homeScore: '', awayScore: '' },
    { id: 5, home: 'Brésil', away: 'Argentine', group: 'Groupe C', homeScore: '', awayScore: '' },
    { id: 6, home: 'Allemagne', away: 'Portugal', group: 'Groupe C', homeScore: '', awayScore: '' },
  ]);

  const handleScoreChange = (matchId, side, value) => {
    // Permet uniquement les chiffres ou vide
    if (value !== '' && !/^\d+$/.test(value)) return;

    setMatches(prevMatches =>
      prevMatches.map(match =>
        match.id === matchId ? { ...match, [side]: value } : match
      )
    );
  };

  const handleSave = () => {
    // Logique de sauvegarde (ex: POST vers /api/predictions/score)
    alert('Vos pronostics ont été enregistrés avec succès !');
    console.log('Données envoyées :', matches);
  };

  return (
    <div className="predictions-view">
      
      {/* EN-TÊTE DE LA VUE */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.6rem' }}>🎯 Mode Pronostics</h2>
        
        {/* SOUS-ONGLETS INTERNES */}
        <div className="sub-tab-bar">
          <button className={activeTab === 'scores' ? 'active' : ''} onClick={() => setActiveTab('scores')}>
            📊 Scores des matchs
          </button>
          <button className={activeTab === 'bracket' ? 'active' : ''} onClick={() => setActiveTab('bracket')}>
            🗺️ Tableau final
          </button>
        </div>
      </div>

      {activeTab === 'scores' ? (
        <div className="predictions-card">
          <p className="predictions-instructions">
            Entrez vos scores prédits avant le coup d'envoi de chaque match pour accumuler des points.
          </p>

          {/* LISTE DES MATCHS EN GRILLE STABLE */}
          <div className="matches-list">
            {matches.map(match => (
              <div key={match.id} className="match-row-card">
                
                {/* Équipe à Domicile */}
                <div className="team-side home">{match.home}</div>
                
                {/* Inputs de Scores centraux */}
                <div className="score-inputs-block">
                  <input
                    type="text"
                    maxLength="2"
                    className="score-input-field"
                    value={match.homeScore}
                    onChange={(e) => handleScoreChange(match.id, 'homeScore', e.target.value)}
                  />
                  <span className="score-divider">–</span>
                  <input
                    type="text"
                    maxLength="2"
                    className="score-input-field"
                    value={match.awayScore}
                    onChange={(e) => handleScoreChange(match.id, 'awayScore', e.target.value)}
                  />
                </div>
                
                {/* Équipe Extérieure */}
                <div className="team-side away">{match.away}</div>
                
                {/* Badge de Poule / Groupe */}
                <div className="group-tag-badge">{match.group}</div>

              </div>
            ))}
          </div>

          {/* BOUTON ENREGISTRER */}
          <button className="btn-save-predictions" onClick={handleSave}>
            💾 Sauvegarder les pronostics
          </button>
        </div>
      ) : (
        /* VUE BRACKET DU TABLEAU */
        <div className="predictions-card" style={{ textAlign: 'center', padding: '3rem 1rem', color: '#94a3b8' }}>
          <h3>🗺️ Phase à élimination directe</h3>
          <p>Le module de l'arbre complet du tableau final de la Coupe du Monde sera disponible après la phase de poules.</p>
        </div>
      )}
    </div>
  );
}