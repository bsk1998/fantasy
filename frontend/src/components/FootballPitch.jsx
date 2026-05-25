/**
 * FootballPitch — Affiche l'équipe sélectionnée sur un terrain de football.
 * Les joueurs sont répartis selon la formation choisie.
 */

// Répartition des joueurs par formation (rangs de bas en haut : G, D, M, A)
const FORMATION_LAYOUT = {
  "4-3-3":    [1, 4, 3, 3],
  "4-4-2":    [1, 4, 4, 2],
  "3-5-2":    [1, 3, 5, 2],
  "4-2-3-1":  [1, 4, 2, 3, 1],
  "5-3-2":    [1, 5, 3, 2],
};

const ROW_LABELS = {
  0: "G",
  1: "D",
  2: "M",
  3: "A",
  4: "A",
};

export default function FootballPitch({ roster, formation }) {
  const layout = FORMATION_LAYOUT[formation] || FORMATION_LAYOUT["4-3-3"];

  // Répartir les 11 titulaires selon la formation
  const titulaires = roster.slice(0, 11);
  let playerIndex = 0;
  const rows = layout.map((count) => {
    const row = titulaires.slice(playerIndex, playerIndex + count);
    playerIndex += count;
    return row;
  });

  const bench = roster.slice(11, 15);

  return (
    <div className="pitch-wrapper">
      <div className="pitch">
        {/* Lignes de terrain */}
        <div className="pitch-center-circle" />
        <div className="pitch-center-line" />

        {/* Joueurs sur le terrain */}
        {rows.map((row, rowIdx) => (
          <div key={rowIdx} className="pitch-row">
            {row.map((player, i) => (
              <div key={player?.id || i} className="pitch-player">
                <div className="pitch-player-dot" />
                <span className="pitch-player-name">
                  {player ? player.name.split(" ").pop() : "—"}
                </span>
              </div>
            ))}
            {/* Emplacements vides si le joueur n'est pas encore sélectionné */}
            {Array.from({ length: layout[rowIdx] - row.length }).map((_, i) => (
              <div key={`empty-${i}`} className="pitch-player empty">
                <div className="pitch-player-dot empty" />
                <span className="pitch-player-name muted">Vide</span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Banc de touche */}
      <div className="bench">
        <span className="bench-label">🪑 Banc :</span>
        {bench.length > 0
          ? bench.map((p) => (
              <span key={p.id} className="bench-player">{p.name}</span>
            ))
          : <span className="muted">Aucun remplaçant sélectionné</span>
        }
      </div>
    </div>
  );
}
