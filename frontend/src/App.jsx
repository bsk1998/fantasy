/**
 * App.jsx — Application React Fantasy Boulzazen WC 2026
 * ======================================================
 * Fix session : user initialisé depuis le cache dès le montage (évite l'écran login)
 * Token effacé UNIQUEMENT sur vraie erreur 401 — jamais sur erreur réseau/5xx
 */

import React, { createContext, useContext, useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { API_BASE } from "./config";
import "./App.css";

import Header from "./components/Header";
import Navigation from "./components/Navigation";
import Home from "./views/Home";
import MyTeam from "./views/MyTeam";
import Predictions from "./views/Predictions";
import Leaderboard from "./views/Leaderboard";
import AdminPanel from "./views/AdminPanel";

// ─────────────────────────────────────────────────────────────────────
//  Contexte Global
// ─────────────────────────────────────────────────────────────────────

export const AppContext = createContext();

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp doit être utilisé dans AppProvider");
  return context;
};

export const apiFetch = (path, options = {}) =>
  fetch(`${API_BASE}/api${path}`, options);

// ─────────────────────────────────────────────────────────────────────
//  Helpers cache
// ─────────────────────────────────────────────────────────────────────

function readCachedUser() {
  try {
    const raw = localStorage.getItem("cached_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeCachedUser(userData) {
  try {
    localStorage.setItem("cached_user", JSON.stringify(userData));
  } catch {
    // silencieux
  }
}

// ─────────────────────────────────────────────────────────────────────
//  Provider
// ─────────────────────────────────────────────────────────────────────

function AppProvider({ children }) {
  /**
   * INIT IMMÉDIAT depuis le cache :
   * Si un token existe en localStorage, on charge le user depuis le cache
   * AVANT même que /api/auth/me réponde.
   * Ça évite le flash "écran login" à chaque refresh.
   */
  const [user, setUser] = useState(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) return null;
    return readCachedUser(); // peut être null au tout premier lancement
  });

  const [loading, setLoading] = useState(true);

  const [session, setSession] = useState(() => {
    const token = localStorage.getItem("auth_token");
    return token ? { access_token: token } : null;
  });

  const [notification, setNotification] = useState(null);
  const [syncData, setSyncData] = useState(null);

  useEffect(() => {
    const initApp = async () => {
      try {
        const token = localStorage.getItem("auth_token");

        if (!token) {
          // Pas de token → pas connecté, pas besoin d'appel réseau
          setLoading(false);
          return;
        }

        try {
          const res = await apiFetch("/auth/me", {
            headers: { Authorization: `Bearer ${token}` },
          });

          if (res.ok) {
            // ✅ Token valide → on met à jour le cache et l'état
            const userData = await res.json();
            setUser(userData);
            writeCachedUser(userData);
          } else if (res.status === 401) {
            // ✅ Token vraiment expiré/invalide → déconnexion propre
            localStorage.removeItem("auth_token");
            localStorage.removeItem("cached_user");
            setSession(null);
            setUser(null);
          }
          // Pour tout autre code HTTP (5xx, 502, 503...) :
          // On NE touche PAS à l'état. Le cache chargé lors du useState() reste valide.
        } catch {
          // Erreur réseau (backend hors ligne, timeout...) :
          // On NE touche PAS à l'état non plus. L'utilisateur reste connecté via le cache.
          console.warn("[App] Backend inaccessible — session conservée depuis le cache.");
        }
      } catch (err) {
        console.error("[App] Init erreur inattendue:", err);
      } finally {
        setLoading(false);
      }
    };

    initApp();
  }, []);

  const notify = (message, type = "info", duration = 3000) => {
    setNotification({ message, type });
    if (duration > 0) setTimeout(() => setNotification(null), duration);
  };

  const logout = () => {
    setUser(null);
    setSession(null);
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user_email");
    localStorage.removeItem("cached_user");
  };

  return (
    <AppContext.Provider value={{
      user, setUser,
      session, setSession,
      loading, setLoading,
      notification, notify,
      syncData, setSyncData,
      logout, apiFetch, API_BASE,
    }}>
      {children}
    </AppContext.Provider>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  AdminAccessDot
// ─────────────────────────────────────────────────────────────────────

function AdminAccessDot() {
  const [showMenu, setShowMenu] = useState(false);
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    const check = () => setHasToken(!!localStorage.getItem("admin_token"));
    check();
    window.addEventListener("storage", check);
    return () => window.removeEventListener("storage", check);
  }, []);

  const handleAdminLogout = () => {
    localStorage.removeItem("admin_token");
    setHasToken(false);
    setShowMenu(false);
    window.location.href = "/";
  };

  return (
    <div className="admin-dot">
      <button
        className="admin-access-btn"
        title="Admin Panel"
        onClick={() => setShowMenu(!showMenu)}
      >
        ⚙️
      </button>

      {showMenu && (
        <div className="admin-dot-menu">
          {hasToken ? (
            <>
              <a href="/admin" className="admin-menu-link" onClick={() => setShowMenu(false)}>
                📋 Admin Panel
              </a>
              <button className="admin-menu-logout" onClick={handleAdminLogout}>
                🚪 Déco Admin
              </button>
            </>
          ) : (
            <a href="/admin" className="admin-menu-link" onClick={() => setShowMenu(false)}>
              🔐 Admin Login
            </a>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  Notification Toast
// ─────────────────────────────────────────────────────────────────────

function NotificationToast() {
  const { notification } = useApp();
  if (!notification) return null;

  const bgClass = {
    success: "toast-success",
    error:   "toast-error",
    warning: "toast-warning",
    info:    "toast-info",
  }[notification.type] || "toast-info";

  return (
    <div className={`notification-toast ${bgClass}`}>
      {notification.message}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  AppContent
// ─────────────────────────────────────────────────────────────────────

function AppContent() {
  const { loading, user } = useApp();

  if (loading) {
    return (
      <div className="app-loading">
        <div className="spinner" />
        <p>Chargement de Fantasy Boulzazen...</p>
      </div>
    );
  }

  return (
    <div className="app-container">
      <Header />
      <Navigation />
      <AdminAccessDot />
      <NotificationToast />

      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route
            path="/team"
            element={user ? <MyTeam /> : <Navigate to="/" replace />}
          />
          <Route
            path="/predictions"
            element={user ? <Predictions /> : <Navigate to="/" replace />}
          />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/admin" element={<AdminPanel />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  App Root
// ─────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <Router>
      <AppProvider>
        <AppContent />
      </AppProvider>
    </Router>
  );
}