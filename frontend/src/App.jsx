/**
 * App.jsx — Application React Fantasy Boulzazen WC 2026
 * ======================================================
 * Fix : user initialisé depuis le cache dès le montage (évite l'écran login)
 *       Token effacé uniquement sur vraie erreur 401
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

// ─────────────────────────────────────────────────────────────────────
//  Provider
// ─────────────────────────────────────────────────────────────────────

function AppProvider({ children }) {
  // ✅ Fix session : on initialise user depuis le cache IMMÉDIATEMENT
  // pour éviter l'écran de login à chaque refresh
  const [user,         setUser]         = useState(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) return null;
    return readCachedUser();   // peut être null si premier lancement
  });
  const [loading,      setLoading]      = useState(true);
  const [session,      setSession]      = useState(() => {
    const token = localStorage.getItem("auth_token");
    return token ? { access_token: token } : null;
  });
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    const initApp = async () => {
      try {
        const token = localStorage.getItem("auth_token");
        if (token) {
          try {
            const res = await apiFetch("/auth/me", {
              headers: { Authorization: `Bearer ${token}` },
            });

            if (res.ok) {
              const userData = await res.json();
              setUser(userData);
              setSession("authenticated"); // Ajouté
              localStorage.setItem("cached_user", JSON.stringify(userData));
              // eslint-disable-next-line no-console
              console.info("Session restaurée via token."); // Ajouté
            } else if (res.status === 401 || res.status === 403) { // Modification: ajout 403
              // Token véritablement expiré ou accès refusé — on déconnecte
              // eslint-disable-next-line no-console
              console.warn("Token JWT invalide ou expiré, déconnexion.");
              logout(); // Remplacement par appel à logout()
            } else {
              // Pour d'autres erreurs (ex: 500 serveur), on ne déconnecte pas forcément l'utilisateur
              // On garde le token en espérant que le problème soit temporaire ou externe à l'auth
              // eslint-disable-next-line no-console
              console.error(`Erreur de validation du token (${res.status}), session maintenue pour l'instant.`);
            }
          } catch (networkErr) {
            // Erreur réseau : le cache est déjà chargé dans l'état initial
            console.warn("[App] Backend inaccessible, session conservée depuis le cache");
          }
        }
      } catch (err) {
        console.error("[App] Init erreur:", err);
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
