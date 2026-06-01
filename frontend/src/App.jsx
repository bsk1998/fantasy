/**
 * App.jsx — Application React Fantasy Boulzazen WC 2026
 * ======================================================
 * Contexte global + routing + admin panel discret
 */

import React, { createContext, useContext, useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import "./App.css";

// ─────────────────────────────────────────────────────────────────────
//  Components
// ─────────────────────────────────────────────────────────────────────

import Header from "./components/Header";
import Navigation from "./components/Navigation";
import Home from "./views/Home";
import MyTeam from "./views/MyTeam";
import Predictions from "./views/Predictions";
import Leaderboard from "./views/Leaderboard";
import AdminPanel from "./views/AdminPanel";

// ─────────────────────────────────────────────────────────────────────
//  Configuration
// ─────────────────────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// ─────────────────────────────────────────────────────────────────────
//  Contexte Global App
// ─────────────────────────────────────────────────────────────────────

export const AppContext = createContext();

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp doit être utilisé dans AppProvider");
  }
  return context;
};

export const apiFetch = (path, options = {}) =>
  fetch(`${API_BASE}/api${path}`, options);

// ─────────────────────────────────────────────────────────────────────
//  Provider
// ─────────────────────────────────────────────────────────────────────

function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dataVersion, setDataVersion] = useState(localStorage.getItem("dataVersion") || "");
  const [adminToken, setAdminToken] = useState(localStorage.getItem("admin_token") || "");
  const [notification, setNotification] = useState(null);

  // Initialisation au mount
  useEffect(() => {
const initApp = async () => {
  try {
    // Récupérer la session depuis localStorage si elle existe
    const token = localStorage.getItem("auth_token");
    if (token) {
      const res = await apiFetch("/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
      } else {
        localStorage.removeItem("auth_token");
      }
    }
  } catch (err) {
    logger.error("Init erreur:", err);
  } finally {
    setLoading(false);
  }
};

    initApp();
  }, []);

  const notify = (message, type = "info", duration = 3000) => {
    setNotification({ message, type });
    if (duration > 0) {
      setTimeout(() => setNotification(null), duration);
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user_email");
  };

  const value = {
    user,
    setUser,
    loading,
    setLoading,
    dataVersion,
    setDataVersion,
    adminToken,
    setAdminToken,
    notification,
    notify,
    logout,
    apiFetch,
    API_BASE,
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  Logger Helper
// ─────────────────────────────────────────────────────────────────────

function logger(msg) {
  const isDev = import.meta.env.DEV;
  if (isDev) {
    console.log(`[App] ${msg}`);
  }
}

logger.warn = (msg) => console.warn(`[App] ⚠️  ${msg}`);
logger.error = (msg) => console.error(`[App] ❌ ${msg}`);

// ─────────────────────────────────────────────────────────────────────
//  Admin Dot (accès discret au panel)
// ─────────────────────────────────────────────────────────────────────

function AdminAccessDot() {
  const { adminToken } = useApp();
  const [showMenu, setShowMenu] = useState(false);

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
          {adminToken ? (
            <>
              <a href="/admin" className="admin-menu-link">
                📋 Admin Panel
              </a>
              <button
                className="admin-menu-logout"
                onClick={() => {
                  localStorage.removeItem("admin_token");
                  window.location.href = "/";
                }}
              >
                🚪 Logout
              </button>
            </>
          ) : (
            <a href="/admin" className="admin-menu-link">
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
    error: "toast-error",
    warning: "toast-warning",
    info: "toast-info",
  }[notification.type] || "toast-info";

  return (
    <div className={`notification-toast ${bgClass}`}>
      {notification.message}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  Main App Component
// ─────────────────────────────────────────────────────────────────────

function AppContent() {
  const { loading, user } = useApp();

  if (loading) {
    return (
      <div className="app-loading">
        <div className="spinner"></div>
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
          <Route
            path="/leaderboard"
            element={<Leaderboard />}
          />
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