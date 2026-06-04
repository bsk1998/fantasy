/**
 * App.jsx — Application React Fantasy Boulzazen WC 2026
 * ======================================================
 * Fix : session conservée si backend temporairement indisponible
 *       (token effacé uniquement sur vraie erreur 401, pas sur erreur réseau)
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
//  Contexte Global — UTILISATEUR SEULEMENT
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
//  Provider
// ─────────────────────────────────────────────────────────────────────

function AppProvider({ children }) {
  const [user,         setUser]         = useState(null);
  const [loading,      setLoading]      = useState(true);
  const [session,      setSession]      = useState(null);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    const initApp = async () => {
      try {
        const token = localStorage.getItem("auth_token");
        if (token) {
          setSession({ access_token: token });
          try {
            const res = await apiFetch("/auth/me", {
              headers: { Authorization: `Bearer ${token}` },
            });

            if (res.ok) {
              const userData = await res.json();
              setUser(userData);
              // Mise en cache locale pour la résilience réseau
              localStorage.setItem("cached_user", JSON.stringify(userData));
            } else if (res.status === 401) {
              // Token véritablement expiré ou invalide — on déconnecte
              localStorage.removeItem("auth_token");
              localStorage.removeItem("cached_user");
              setSession(null);
            }
            // Pour tout autre code HTTP (5xx), on conserve la session
            // sans écraser les données en cache
          } catch (networkErr) {
            // Erreur réseau : backend inaccessible ou hors ligne
            // On restaure l'utilisateur depuis le cache plutôt que de déconnecter
            console.warn("[App] Backend inaccessible, restauration depuis le cache");
            const cachedRaw = localStorage.getItem("cached_user");
            if (cachedRaw) {
              try {
                setUser(JSON.parse(cachedRaw));
              } catch {
                // Cache corrompu — on reste déconnecté
              }
            }
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