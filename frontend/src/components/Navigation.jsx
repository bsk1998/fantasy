import { useNavigate, useLocation } from "react-router-dom";
import { useApp } from "../App";

const TABS = [
  { key: "/",            label: "Accueil", icon: "🏠" },
  { key: "/team",        label: "Équipe",  icon: "⚽" },
  { key: "/predictions", label: "Pronos",  icon: "🎯" },
  { key: "/leaderboard", label: "Classmt", icon: "🏆" },
];

export default function Navigation() {
  const navigate  = useNavigate();
  const location  = useLocation();
  const { user }  = useApp();

  return (
    <nav className="bottom-nav">
      {TABS.map((tab) => {
        const isActive = location.pathname === tab.key;
        const isLocked = (tab.key === "/team" || tab.key === "/predictions") && !user;

        return (
          <button
            key={tab.key}
            className={`nav-btn ${isActive ? "active" : ""}`}
            onClick={() => !isLocked && navigate(tab.key)}
            title={isLocked ? "Connexion requise" : tab.label}
          >
            <div className="nav-icon-wrap">
              <span style={{ fontSize: "1.3rem" }}>{tab.icon}</span>
              {isActive && <span className="nav-active-dot" />}
            </div>
            <span className="nav-label">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}