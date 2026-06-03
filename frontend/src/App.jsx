/**
 * App.jsx — Application React Fantasy Boulzazen WC 2026
 * ======================================================
 * Contexte utilisateur UNIQUEMENT — admin est totalement indépendant
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
//  Contexte Global — UTILISATEUR SEULEMENT (pas d'admin ici)
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
//  Provider — gestion session utilisateur uniquement
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
          const res = await apiFetch("/auth/me", {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (res.ok) {
            const userData = await res.json();
            setUser(userData);
          } else {
            // Token expiré ou invalide
            localStorage.removeItem("auth_token");
            setSession(null);
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
//  AdminAccessDot — lit directement le localStorage, sans contexte user
// ─────────────────────────────────────────────────────────────────────

function AdminAccessDot() {
  const [showMenu, setShowMenu]   = useState(false);
  const [hasToken, setHasToken]   = useState(false);

  // Vérifie le token admin depuis localStorage (indépendant du contexte user)
  useEffect(() => {
    const check = () => setHasToken(!!localStorage.getItem("admin_token"));
    check();
    // Écoute les changements de storage (connexion/déco admin dans un autre onglet)
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
//  AppContent — Layout principal
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
          {/* Admin : route indépendante — AdminPanel gère son propre état */}
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