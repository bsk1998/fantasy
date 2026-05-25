const POSITION_COLORS = { G: "#f59e0b", D: "#3b82f6", M: "#10b981", A: "#ef4444" };

export default function PlayerCard({ player, selected, onToggle }) {
  const color = POSITION_COLORS[player.position] || "#6b7280";

  return (
    <div
      className={`player-card ${selected ? "selected" : ""}`}
      onClick={onToggle}
      style={{ borderLeftColor: color }}
    >
      <div className="player-card-header">
        <span className="pos-badge" style={{ background: color }}>
          {player.position}
        </span>
        <span className="player-name">{player.name}</span>
      </div>
      <div className="player-card-body">
        <span className="player-nat">{player.nationality}</span>
        <span className="player-price">💰 {player.price}M€</span>
        <span className="player-pts">⭐ {player.points_total} pts</span>
      </div>
      <div className="player-card-stats">
        <span>⚽ {player.goals}</span>
        <span>🎯 {player.assists}</span>
      </div>
    </div>
  );
}
