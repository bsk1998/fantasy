import { useApp } from "../App";

export default function Header() {
  const { user } = useApp();

  return (
    <header className="app-header">
      <div className="header-brand">
        <span className="header-ball">⚽</span>
        <div>
          <div className="header-title">Boulzazen</div>
          <div className="header-subtitle">WC 2026</div>
        </div>
      </div>

      {user && (
        <div className="header-user-pill">
          <span className="pill-name">{user.username || user.email}</span>
          <span className="pill-score">{user.total ?? 0} pts</span>
        </div>
      )}
    </header>
  );
}