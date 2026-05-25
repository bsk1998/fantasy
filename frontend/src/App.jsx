import React, { useState, useEffect } from "react";
import { supabase } from './supabaseClient';

export default function App() {
  const [screen, setScreen] = useState("home");
  const [user, setUser] = useState(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setUser(session.user);
        setScreen("modes");
      }
    });
  }, []);

  const handleGoogleLogin = async () => {
    await supabase.auth.signInWithOAuth({ provider: 'google' });
  };

  return (
    <div style={styles.mobileWrapper}>
      {/* ÉCRAN HOME */}
      {screen === "home" && (
        <div style={styles.containerCenter}>
          <h1 style={styles.heroTitle}>IA FANTASY</h1>
          <button onClick={() => setScreen("login")} style={styles.btnPrimary}>JOUER</button>
        </div>
      )}

      {/* ÉCRAN LOGIN */}
      {screen === "login" && (
        <div style={styles.containerCenter}>
          <h2 style={styles.title}>Connexion</h2>
          <button onClick={handleGoogleLogin} style={styles.btnGoogle}>Google</button>
          <button onClick={() => setScreen("modes")} style={styles.btnSecondary}>Invité</button>
        </div>
      )}

      {/* ÉCRAN MODES */}
      {screen === "modes" && (
        <div style={styles.container}>
          <div style={styles.header}>
            <span style={styles.userBadge}>{user ? user.email.split('@')[0] : "Invité"}</span>
            <button onClick={() => setScreen("home")} style={styles.logoutBtn}>✕</button>
          </div>
          <h2 style={styles.title}>Choisis ton mode</h2>
          <div style={styles.modeCard} onClick={() => setScreen("fantasy")}>🏆 FANTASY LEAGUE</div>
          <div style={styles.modeCard} onClick={() => setScreen("pronos")}>📊 PRONOS MATCHS</div>
          <div style={styles.modeCard} onClick={() => setScreen("tournoi")}>🏁 PRONOS TOURNOI</div>
        </div>
      )}

      {/* MODES DE JEU */}
      {["fantasy", "pronos", "tournoi"].includes(screen) && (
        <div style={styles.container}>
          <button onClick={() => setScreen("modes")} style={styles.backBtn}>← Retour</button>
          <h2 style={styles.title}>{screen.toUpperCase()}</h2>
          <div style={styles.placeholder}>Interface de {screen} en cours de construction</div>
        </div>
      )}
    </div>
  );
}

const styles = {
  mobileWrapper: { width: "100vw", height: "100vh", maxWidth: "480px", margin: "0 auto", backgroundColor: "#0f172a", color: "white", overflowY: "auto", fontFamily: "sans-serif" },
  container: { padding: "20px" },
  containerCenter: { padding: "20px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%" },
  header: { display: "flex", justifyContent: "space-between", marginBottom: "20px" },
  title: { fontSize: "1.5rem", marginBottom: "20px" },
  heroTitle: { fontSize: "3rem", background: "linear-gradient(to right, #38bdf8, #818cf8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" },
  btnPrimary: { width: "100%", padding: "15px", borderRadius: "10px", border: "none", backgroundColor: "#3b82f6", color: "white", cursor: "pointer" },
  btnGoogle: { width: "100%", padding: "15px", borderRadius: "10px", border: "none", backgroundColor: "white", color: "black", marginBottom: "10px", cursor: "pointer" },
  btnSecondary: { width: "100%", padding: "15px", borderRadius: "10px", border: "1px solid white", backgroundColor: "transparent", color: "white", cursor: "pointer" },
  modeCard: { padding: "20px", backgroundColor: "#1e293b", borderRadius: "15px", marginBottom: "15px", cursor: "pointer", border: "1px solid #334155", textAlign: "center", fontWeight: "bold" },
  backBtn: { background: "none", border: "none", color: "white", fontSize: "1.2rem", cursor: "pointer", marginBottom: "10px" },
  logoutBtn: { background: "none", border: "none", color: "white", cursor: "pointer" },
  userBadge: { backgroundColor: "#334155", padding: "5px 12px", borderRadius: "20px", fontSize: "0.8rem" },
  placeholder: { marginTop: "50px", textAlign: "center", color: "#64748b" }
};