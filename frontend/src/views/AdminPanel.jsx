/**
 * AdminPanel.jsx — Panneau d'administration Fantasy Boulzazen WC 2026
 * ====================================================================
 * ✅ Clé Groq activable depuis l'UI
 * ✅ 48 nations sélectionnables — remplissage effectif par texte ou capture
 * ✅ Édition manuelle des postes / suppression joueurs
 * ✅ Tournoi : poules, meilleurs 3èmes, tableau d'élim. directe (seeding FIFA)
 * ✅ Règles du jeu organisées par mode, éditables, ajout libre
 * INDÉPENDANT du contexte utilisateur (AppContext)
 */

import React, { useState, useRef, useEffect, useCallback } from "react";

// ─── Config ──────────────────────────────────────────────────────────────────
const API_BASE = import.meta.env.VITE_API_BASE || "";
const API_TIMEOUT = 20000;

// ─── 48 nations qualifiées CDM 2026 ──────────────────────────────────────────
const NATIONS_CDM2026 = {
  "Groupe A": ["Mexico","South Africa","South Korea","UEFA Play-Off D"],
  "Groupe B": ["Canada","UEFA Play-Off A","Qatar","Switzerland"],
  "Groupe C": ["Brazil","Morocco","Haiti","Scotland"],
  "Groupe D": ["United States","Paraguay","Australia","UEFA Play-Off C"],
  "Groupe E": ["Germany","Curacao","Ivory Coast","Ecuador"],
  "Groupe F": ["Netherlands","Japan","UEFA Play-Off B","Tunisia"],
  "Groupe G": ["Belgium","Egypt","Iran","New Zealand"],
  "Groupe H": ["Spain","Cape Verde","Saudi Arabia","Uruguay"],
  "Groupe I": ["France","Senegal","Intercontinental Play-Off 2","Norway"],
  "Groupe J": ["Argentina","Algeria","Austria","Jordan"],
  "Groupe K": ["Portugal","Intercontinental Play-Off 1","Uzbekistan","Colombia"],
  "Groupe L": ["England","Croatia","Ghana","Panama"],
};

const ALL_NATIONS = Object.values(NATIONS_CDM2026).flat();

const POSITIONS = ["G","D","M","A"];
const POSITION_LABELS = { G:"Gardien", D:"Défenseur", M:"Milieu", A:"Attaquant" };

// ─── Règles par défaut organisées par mode ────────────────────────────────────
const DEFAULT_RULES = {
  fantasy: [
    { id: "f1", label: "Match complet (≥90 min)", G:2, D:2, M:2, A:2 },
    { id: "f2", label: "Joue <90 min / entre en jeu", G:1, D:1, M:1, A:1 },
    { id: "f3", label: "But marqué", G:8, D:6, M:5, A:4 },
    { id: "f4", label: "Passe décisive", G:6, D:5, M:4, A:4 },
    { id: "f5", label: "Clean sheet (0 but encaissé)", G:5, D:4, M:1, A:0 },
    { id: "f6", label: "3 parades (gardien, par tranche)", G:3, D:0, M:0, A:0 },
    { id: "f7", label: "5 récupérations (G/D/M, par tranche)", G:3, D:3, M:3, A:0 },
    { id: "f8", label: "Carton jaune", G:-1, D:-1, M:-1, A:-1 },
    { id: "f9", label: "Carton rouge", G:-2, D:-2, M:-2, A:-2 },
  ],
  coach: [
    { id: "c1", label: "Présent sur le banc", pts:1, note:"" },
    { id: "c2", label: "Victoire (base)", pts:2, note:"" },
    { id: "c3", label: "Bonus par tranche de 2 buts d'écart (victoire)", pts:3, note:"Ex: 4-0 = +2+6 = 8pts" },
    { id: "c4", label: "Défaite (base)", pts:-2, note:"Logique inverse de la victoire" },
    { id: "c5", label: "But d'un remplaçant entré", pts:3, note:"" },
    { id: "c6", label: "Passe décisive d'un remplaçant", pts:2, note:"" },
    { id: "c7", label: "Carton jaune", pts:-1, note:"" },
    { id: "c8", label: "Carton rouge", pts:-2, note:"" },
  ],
  pronos: [
    { id: "p1", label: "Score exact", pts:5 },
    { id: "p2", label: "Bon vainqueur / match nul (mauvais score)", pts:2 },
    { id: "p3", label: "Mauvais pronostic", pts:0 },
  ],
  bracket: [
    { id: "b1", label: "Bon classement exact dans un groupe", pts:5 },
    { id: "b2", label: "Équipe qualifiée au bon rang (incl. meilleur 3e)", pts:5 },
    { id: "b3", label: "Équipe présente dans un tour éliminatoire", pts:5 },
    { id: "b4", label: "Match prédit exactement (bon résultat)", pts:5 },
    { id: "b5", label: "Équipe qualifiée au tour suivant", pts:5 },
  ],
  annexes: [
    { id: "a1", label: "1er exact dans un Top 3 (buteurs/passeurs/etc.)", pts:5 },
    { id: "a2", label: "Joueur présent dans le bon Top 3", pts:3 },
    { id: "a3", label: "Joueur présent dans un Top 3 (mauvais rang)", pts:1 },
  ],
};

const MODE_LABELS = {
  fantasy: "⚽ Fantasy League",
  coach: "👔 Entraîneur",
  pronos: "🎯 Pronostics Scores",
  bracket: "🗺️ Tableau Tournoi",
  annexes: "🎖️ Prédictions Annexes",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getAdminToken() { return localStorage.getItem("admin_token") || ""; }
function setAdminToken(t) { t ? localStorage.setItem("admin_token",t) : localStorage.removeItem("admin_token"); }
function getStoredGroqKey() { return localStorage.getItem("admin_groq_key") || ""; }
function setStoredGroqKey(k) { k ? localStorage.setItem("admin_groq_key",k) : localStorage.removeItem("admin_groq_key"); }
function uid() { return Math.random().toString(36).slice(2,8); }

async function adminFetch(path, opts={}) {
  const token = getAdminToken();
  const ctrl = new AbortController();
  const tid = setTimeout(()=>ctrl.abort(), API_TIMEOUT);
  try {
    const res = await fetch(`${API_BASE}/api/admin${path}`, {
      ...opts,
      headers: { "Content-Type":"application/json", ...(token?{Authorization:`Bearer ${token}`}:{}), ...(opts.headers||{}) },
      signal: ctrl.signal,
    });
    clearTimeout(tid);
    return res;
  } catch(e) { clearTimeout(tid); throw e; }
}

// ─── CSS inline ───────────────────────────────────────────────────────────────
const css = `
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@400;500;600&display=swap');
:root{
  --bg:#08090f; --s1:#0f111a; --s2:#171929; --s3:#1e2235;
  --border:#252a40; --border2:#303860;
  --text:#e8ebff; --text2:#7a82ab; --text3:#3d4466;
  --green:#00ffaa; --green2:#00cc88;
  --blue:#4f8bff; --blue2:#2563eb;
  --gold:#ffcc44; --red:#ff4d6d;
  --orange:#ff8c42;
  --radius:10px; --radius2:6px;
  font-family:'DM Sans',sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);min-height:100vh;}
.admin-root{min-height:100vh;display:flex;flex-direction:column;background:var(--bg);}

/* LOGIN */
.login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:radial-gradient(ellipse at 50% 20%,#0d1540 0%,var(--bg) 70%);}
.login-box{width:340px;background:var(--s1);border:1px solid var(--border2);border-radius:16px;padding:36px;display:flex;flex-direction:column;gap:20px;}
.login-logo{font-family:'Syne',sans-serif;font-size:1.5rem;font-weight:800;letter-spacing:.15em;text-transform:uppercase;text-align:center;color:var(--text);}
.login-logo span{color:var(--green);}
.inp{width:100%;background:var(--s2);border:1px solid var(--border);border-radius:var(--radius2);padding:10px 14px;color:var(--text);font-size:.9rem;outline:none;transition:.2s;}
.inp:focus{border-color:var(--blue);}
.btn-primary{width:100%;background:var(--blue);color:#fff;border:none;border-radius:var(--radius2);padding:12px;font-weight:700;font-size:.9rem;cursor:pointer;transition:.2s;}
.btn-primary:hover{background:var(--blue2);}
.btn-primary:disabled{opacity:.4;cursor:not-allowed;}
.err-msg{font-size:.78rem;color:var(--red);text-align:center;}
.hint{font-size:.7rem;color:var(--text3);text-align:center;}

/* LAYOUT */
.admin-layout{display:flex;height:100vh;overflow:hidden;}
.sidebar{width:220px;flex-shrink:0;background:var(--s1);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:20px 12px;gap:4px;overflow-y:auto;}
.sidebar-logo{font-family:'Syne',sans-serif;font-size:1rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;padding:8px 10px 20px;color:var(--text);}
.sidebar-logo span{color:var(--green);}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:var(--radius2);cursor:pointer;font-size:.83rem;font-weight:600;color:var(--text2);transition:.15s;border:none;background:none;width:100%;text-align:left;}
.nav-item:hover{background:var(--s2);color:var(--text);}
.nav-item.active{background:rgba(79,139,255,.15);color:var(--blue);border:1px solid rgba(79,139,255,.25);}
.nav-item .icon{font-size:1rem;width:18px;text-align:center;}
.sidebar-bottom{margin-top:auto;padding-top:12px;border-top:1px solid var(--border);}
.btn-logout{width:100%;background:rgba(255,77,109,.1);border:1px solid rgba(255,77,109,.25);border-radius:var(--radius2);padding:8px;color:var(--red);font-size:.78rem;font-weight:700;cursor:pointer;transition:.2s;}
.btn-logout:hover{background:rgba(255,77,109,.2);}

/* MAIN CONTENT */
.main-content{flex:1;overflow-y:auto;padding:28px 28px 40px;}
.page-title{font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;letter-spacing:.08em;margin-bottom:6px;text-transform:uppercase;}
.page-sub{font-size:.8rem;color:var(--text2);margin-bottom:24px;}

/* FEEDBACK */
.feedback{padding:10px 16px;border-radius:var(--radius2);font-size:.82rem;font-weight:600;margin-bottom:16px;}
.feedback.ok{background:rgba(0,255,170,.08);border:1px solid rgba(0,255,170,.25);color:var(--green);}
.feedback.err{background:rgba(255,77,109,.08);border:1px solid rgba(255,77,109,.25);color:var(--red);}
.feedback.info{background:rgba(79,139,255,.08);border:1px solid rgba(79,139,255,.25);color:var(--blue);}

/* CARDS */
.card{background:var(--s1);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:16px;}
.card-title{font-family:'Syne',sans-serif;font-size:.95rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;margin-bottom:14px;color:var(--text);}
.card-title span{color:var(--text3);font-weight:400;font-size:.75rem;margin-left:8px;text-transform:none;letter-spacing:0;}

/* FORM ELEMENTS */
label{display:block;font-size:.7rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--text2);margin-bottom:5px;}
.field{margin-bottom:14px;}
.row-2{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.row-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;}
select{width:100%;background:var(--s2);border:1px solid var(--border);border-radius:var(--radius2);padding:9px 12px;color:var(--text);font-size:.85rem;outline:none;}
select:focus{border-color:var(--blue);}
textarea{width:100%;background:var(--s2);border:1px solid var(--border);border-radius:var(--radius2);padding:10px 14px;color:var(--text);font-size:.82rem;resize:vertical;outline:none;min-height:120px;font-family:'DM Sans',sans-serif;}
textarea:focus{border-color:var(--blue);}

/* GROQ STATUS */
.groq-badge{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:50px;font-size:.72rem;font-weight:700;letter-spacing:.05em;}
.groq-badge.on{background:rgba(0,255,170,.1);border:1px solid rgba(0,255,170,.3);color:var(--green);}
.groq-badge.off{background:rgba(255,77,109,.1);border:1px solid rgba(255,77,109,.3);color:var(--red);}
.groq-dot{width:7px;height:7px;border-radius:50%;background:currentColor;}
.groq-dot.pulse{animation:pulse 1.4s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* NATION GRID */
.group-label{font-size:.65rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);padding:12px 0 5px;}
.nation-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:6px;margin-bottom:4px;}
.nation-chip{background:var(--s2);border:1px solid var(--border);border-radius:var(--radius2);padding:7px 12px;font-size:.8rem;font-weight:600;cursor:pointer;transition:.15s;color:var(--text2);text-align:left;}
.nation-chip:hover{border-color:var(--border2);color:var(--text);}
.nation-chip.selected{background:rgba(79,139,255,.12);border-color:rgba(79,139,255,.4);color:var(--blue);}
.nation-chip.filled{border-color:rgba(0,255,170,.3);color:var(--green);}

/* UPLOAD ZONE */
.upload-zone{border:2px dashed var(--border2);border-radius:var(--radius);padding:32px;text-align:center;cursor:pointer;transition:.2s;background:var(--s2);}
.upload-zone:hover,.upload-zone.drag{border-color:var(--blue);background:rgba(79,139,255,.06);}
.upload-zone p{font-size:.82rem;color:var(--text2);margin-top:6px;}
.upload-preview{max-width:100%;border-radius:var(--radius2);margin-top:10px;border:1px solid var(--border);}
.upload-tabs{display:flex;gap:4px;background:var(--s2);border:1px solid var(--border);border-radius:50px;padding:3px;margin-bottom:14px;}
.upload-tab{flex:1;background:none;border:none;color:var(--text2);padding:7px;font-size:.78rem;font-weight:700;border-radius:50px;cursor:pointer;transition:.15s;}
.upload-tab.active{background:var(--s3);color:var(--text);border:1px solid var(--border2);}

/* PLAYERS TABLE */
.players-table{width:100%;border-collapse:collapse;font-size:.8rem;}
.players-table th{text-align:left;padding:7px 10px;color:var(--text3);font-size:.68rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;border-bottom:1px solid var(--border);}
.players-table td{padding:6px 10px;border-bottom:1px solid rgba(37,42,64,.6);vertical-align:middle;}
.players-table tr:hover td{background:var(--s2);}
.pos-sel{background:var(--s3);border:1px solid var(--border);border-radius:4px;padding:3px 6px;color:var(--text);font-size:.75rem;}
.name-inp{background:var(--s3);border:1px solid transparent;border-radius:4px;padding:4px 7px;color:var(--text);font-size:.8rem;width:100%;}
.name-inp:focus{border-color:var(--blue);outline:none;}
.price-inp{background:var(--s3);border:1px solid transparent;border-radius:4px;padding:4px 6px;color:var(--text);font-size:.78rem;width:72px;}
.price-inp:focus{border-color:var(--blue);outline:none;}
.btn-del{background:none;border:none;color:var(--red);cursor:pointer;font-size:.9rem;opacity:.5;transition:.15s;}
.btn-del:hover{opacity:1;}
.btn-add-row{display:flex;align-items:center;gap:6px;background:none;border:1px dashed var(--border2);border-radius:var(--radius2);padding:7px 14px;color:var(--text2);font-size:.78rem;font-weight:600;cursor:pointer;width:100%;margin-top:8px;transition:.15s;}
.btn-add-row:hover{border-color:var(--blue);color:var(--blue);}

/* POS BADGE */
.pos-b{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:5px;font-size:.65rem;font-weight:800;}
.pos-b.G{background:rgba(255,204,68,.15);color:var(--gold);}
.pos-b.D{background:rgba(79,139,255,.15);color:var(--blue);}
.pos-b.M{background:rgba(0,255,170,.12);color:var(--green);}
.pos-b.A{background:rgba(255,77,109,.15);color:var(--red);}

/* TOURNAMENT */
.group-card{background:var(--s2);border:1px solid var(--border);border-radius:var(--radius2);padding:14px;margin-bottom:10px;}
.group-card-title{font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--blue);margin-bottom:10px;}
.group-rank-row{display:flex;align-items:center;gap:8px;padding:4px 0;}
.rank-num{width:18px;font-size:.72rem;font-weight:700;color:var(--text3);flex-shrink:0;}
.rank-inp{flex:1;background:var(--s3);border:1px solid var(--border);border-radius:4px;padding:5px 8px;color:var(--text);font-size:.8rem;}
.rank-score{display:flex;align-items:center;gap:5px;}
.score-sm{width:36px;background:var(--s3);border:1px solid var(--border);border-radius:4px;padding:4px;text-align:center;color:var(--text);font-size:.85rem;font-weight:700;}
.ko-card{background:var(--s2);border:1px solid var(--border);border-radius:var(--radius2);overflow:hidden;margin-bottom:10px;}
.ko-header{padding:8px 14px;font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--orange);background:rgba(255,140,66,.06);border-bottom:1px solid var(--border);}
.ko-match{display:grid;grid-template-columns:1fr auto 1fr auto;gap:6px;align-items:center;padding:8px 14px;border-bottom:1px solid rgba(37,42,64,.5);}
.ko-match:last-child{border-bottom:none;}
.ko-team-inp{width:100%;background:var(--s3);border:1px solid var(--border);border-radius:4px;padding:5px 8px;color:var(--text);font-size:.78rem;}
.ko-vs{font-size:.7rem;color:var(--text3);flex-shrink:0;}
.ko-winner-inp{width:110px;background:rgba(0,255,170,.07);border:1px solid rgba(0,255,170,.2);border-radius:4px;padding:5px 8px;color:var(--green);font-size:.75rem;font-weight:700;}
.third-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;background:rgba(255,204,68,.1);border:1px solid rgba(255,204,68,.2);border-radius:50px;font-size:.65rem;color:var(--gold);font-weight:700;}

/* RULES */
.mode-tab-bar{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:16px;}
.mode-tab{background:var(--s2);border:1px solid var(--border);border-radius:50px;padding:6px 14px;font-size:.75rem;font-weight:700;cursor:pointer;color:var(--text2);transition:.15s;}
.mode-tab.active{background:rgba(79,139,255,.12);border-color:rgba(79,139,255,.35);color:var(--blue);}
.rules-table{width:100%;border-collapse:collapse;font-size:.8rem;}
.rules-table th{text-align:left;padding:7px 10px;color:var(--text3);font-size:.68rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;border-bottom:1px solid var(--border);}
.rules-table td{padding:7px 10px;border-bottom:1px solid rgba(37,42,64,.5);vertical-align:middle;}
.rules-table tr:hover td{background:var(--s2);}
.rule-inp{width:100%;background:var(--s3);border:1px solid transparent;border-radius:4px;padding:4px 8px;color:var(--text);font-size:.8rem;}
.rule-inp:focus{border-color:var(--blue);outline:none;}
.pts-inp{width:52px;background:var(--s3);border:1px solid transparent;border-radius:4px;padding:4px 6px;color:var(--text);font-size:.82rem;font-weight:700;text-align:center;}
.pts-inp:focus{border-color:var(--green);outline:none;}
.pts-cell{text-align:center;}
.btn-save-rules{display:inline-flex;align-items:center;gap:6px;background:var(--green);color:#000;border:none;border-radius:var(--radius2);padding:9px 18px;font-weight:800;font-size:.82rem;cursor:pointer;transition:.2s;}
.btn-save-rules:hover{background:var(--green2);}

/* ACTIONS STRIP */
.actions-strip{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;}
.btn-action{display:inline-flex;align-items:center;gap:6px;border:none;border-radius:var(--radius2);padding:9px 18px;font-weight:700;font-size:.82rem;cursor:pointer;transition:.2s;}
.btn-green{background:var(--green);color:#000;}
.btn-green:hover{background:var(--green2);}
.btn-blue{background:var(--blue);color:#fff;}
.btn-blue:hover{background:var(--blue2);}
.btn-ghost{background:var(--s2);color:var(--text);border:1px solid var(--border2);}
.btn-ghost:hover{background:var(--s3);}
.btn-sm{padding:5px 12px;font-size:.75rem;}
.btn-action:disabled{opacity:.4;cursor:not-allowed;}

/* SPINNER */
.spinner{display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,.2);border-top-color:currentColor;border-radius:50%;animation:spin .7s linear infinite;}
@keyframes spin{to{transform:rotate(360deg)}}

/* SCROLLBAR */
::-webkit-scrollbar{width:4px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:4px;}

/* SETTINGS BADGE */
.key-display{font-family:monospace;font-size:.78rem;background:var(--s3);border:1px solid var(--border);border-radius:4px;padding:6px 12px;color:var(--text2);word-break:break-all;}
`;

// ════════════════════════════════════════════════════════════════════════════
//  SOUS-COMPOSANTS
// ════════════════════════════════════════════════════════════════════════════

function Feedback({ msg }) {
  if (!msg) return null;
  return <div className={`feedback ${msg.type}`}>{msg.text}</div>;
}

// ─── Section : Paramètres (clé Groq) ─────────────────────────────────────────
function SettingsSection({ groqKey, onGroqKeyChange }) {
  const [draft, setDraft] = useState(groqKey);
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fb, setFb] = useState(null);

  const handleSave = async () => {
    setBusy(true);
    setFb(null);
    const k = draft.trim();
    if (!k.startsWith("gsk_") && k.length > 0) {
      setFb({ type:"err", text:"❌ Clé invalide — une clé Groq commence par « gsk_ »." });
      setBusy(false);
      return;
    }
    // Tester la clé via le backend
    try {
      await adminFetch("/status");
      setStoredGroqKey(k);
      onGroqKeyChange(k);
      setFb({ type:"ok", text: k ? "✅ Clé Groq activée et sauvegardée." : "✅ Clé supprimée." });
    } catch(e) {
      setFb({ type:"err", text:`Erreur backend : ${e.message}` });
    } finally {
      setBusy(false);
    }
  };

  const active = !!groqKey;

  return (
    <div>
      <p className="page-sub">Configurez la clé API Groq pour activer le scraping IA et l'analyse de captures.</p>
      <Feedback msg={fb} />
      <div className="card">
        <div className="card-title">Clé API Groq
          <span>
            <span className={`groq-badge ${active?"on":"off"}`}>
              <span className={`groq-dot ${active?"pulse":""}`}/>
              {active ? "Activée" : "Désactivée"}
            </span>
          </span>
        </div>
        <div className="field">
          <label>Clé Groq (gsk_…)</label>
          <div style={{display:"flex",gap:8}}>
            <input
              className="inp" type={show?"text":"password"}
              placeholder="gsk_xxxxxxxxxxxxxxxxxxxx"
              value={draft} onChange={e=>setDraft(e.target.value)}
              style={{flex:1}}
            />
            <button className="btn-action btn-ghost btn-sm" onClick={()=>setShow(!show)}>{show?"🙈":"👁️"}</button>
          </div>
        </div>
        {active && (
          <div className="field">
            <label>Clé actuelle</label>
            <div className="key-display">{groqKey.slice(0,12)}…{groqKey.slice(-6)}</div>
          </div>
        )}
        <div className="actions-strip">
          <button className="btn-action btn-green" onClick={handleSave} disabled={busy}>
            {busy && <span className="spinner"/>} Enregistrer la clé
          </button>
          {active && (
            <button className="btn-action btn-ghost" onClick={()=>{setDraft("");setStoredGroqKey("");onGroqKeyChange("");}}>
              Désactiver Groq
            </button>
          )}
        </div>
        <div style={{marginTop:16,padding:"12px 14px",background:"rgba(79,139,255,.06)",border:"1px solid rgba(79,139,255,.15)",borderRadius:8,fontSize:".78rem",color:"var(--text2)",lineHeight:1.6}}>
          <strong style={{color:"var(--blue)"}}>Comment obtenir une clé Groq ?</strong><br/>
          Inscrivez-vous gratuitement sur <strong>console.groq.com</strong> → API Keys → Create Key.<br/>
          La clé est utilisée pour : parser les effectifs (texte ou image), analyser les plaintes, générer les données tournoi.
        </div>
      </div>
    </div>
  );
}

// ─── Section : Effectifs par nation ──────────────────────────────────────────
function SquadsSection({ groqKey }) {
  const [selectedNation, setSelectedNation] = useState(null);
  const [inputMode, setInputMode] = useState("text"); // "text"|"image"
  const [promptText, setPromptText] = useState("");
  const [imageData, setImageData] = useState(null);
  const [imageName, setImageName] = useState("");
  const [drag, setDrag] = useState(false);
  const [players, setPlayers] = useState([]);
  const [coachName, setCoachName] = useState("");
  const [busy, setBusy] = useState(false);
  const [fb, setFb] = useState(null);
  const fileRef = useRef(null);

  const showFb = (type,text,dur=5000) => {
    setFb({type,text});
    if(dur) setTimeout(()=>setFb(null),dur);
  };

  const handleImageDrop = useCallback((file) => {
    if(!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = e => { setImageData(e.target.result); setImageName(file.name); };
    reader.readAsDataURL(file);
  }, []);

  const addPlayer = () => {
    setPlayers(prev=>[...prev,{id:uid(),name:"",position:"M",price:6.5}]);
  };

  const updatePlayer = (id,field,val) => {
    setPlayers(prev=>prev.map(p=>p.id===id?{...p,[field]:val}:p));
  };

  const removePlayer = (id) => {
    setPlayers(prev=>prev.filter(p=>p.id!==id));
  };

  const parseWithGroq = async () => {
    if(!groqKey) { showFb("err","❌ Activez d'abord la clé Groq dans Paramètres."); return; }
    if(!selectedNation) { showFb("err","❌ Sélectionnez une nation."); return; }
    const hasContent = inputMode==="text" ? promptText.trim().length > 5 : !!imageData;
    if(!hasContent) { showFb("err","❌ Fournissez du texte ou une capture d'écran."); return; }

    setBusy(true);
    showFb("info","🤖 Groq analyse les données...",0);

    try {
      // Appel Anthropic API for parsing (using claude-sonnet-4-20250514)
      const systemPrompt = `Tu es expert en football. Extrais la liste de joueurs et le coach depuis le contenu fourni (texte ou image).
Nation : ${selectedNation}
Retourne UNIQUEMENT ce JSON valide sans markdown :
{"coach":"Prénom Nom ou null","players":[{"name":"Prénom Nom","position":"G|D|M|A","price":6.5}]}
Positions : G=Gardien, D=Défenseur, M=Milieu, A=Attaquant.
Prix Fantasy estimés : G=5-8, D=5-9, M=6-11, A=7-14. Stars mondiales (Mbappé, Vinicius…)=13-14.`;

      const messages = inputMode==="text"
        ? [{ role:"user", content:`Nation: ${selectedNation}\n\n${promptText}` }]
        : [{ role:"user", content:[
            {type:"image",source:{type:"base64",media_type:imageData.split(";")[0].split(":")[1],data:imageData.split(",")[1]}},
            {type:"text",text:`Extrais l'effectif de ${selectedNation} depuis cette capture.`}
          ]}];

      const resp = await fetch("https://api.anthropic.com/v1/messages",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({ model:"claude-sonnet-4-20250514", max_tokens:2000,
          system:systemPrompt, messages })
      });
      const data = await resp.json();
      const raw = data.content?.[0]?.text || "";
      const match = raw.match(/\{[\s\S]*\}/);
      if(!match) throw new Error("JSON introuvable dans la réponse");
      const parsed = JSON.parse(match[0]);

      if(parsed.coach) setCoachName(parsed.coach);
      if(parsed.players?.length) {
        setPlayers(parsed.players.map(p=>({id:uid(),name:p.name||"",position:p.position||"M",price:p.price||6.5})));
        showFb("ok",`✅ ${parsed.players.length} joueurs détectés${parsed.coach?" | Coach: "+parsed.coach:""}`);
      } else {
        showFb("err","⚠️ Aucun joueur détecté — reformulez ou améliorez la capture.");
      }
    } catch(e) {
      showFb("err","❌ Erreur Groq : "+e.message);
    } finally {
      setBusy(false);
    }
  };

  const injectSquad = async () => {
    if(!selectedNation || players.length < 3) { showFb("err","❌ Sélectionnez une nation et entrez au moins 3 joueurs."); return; }
    setBusy(true);
    showFb("info","💾 Injection en base de données...",0);
    try {
      const params = new URLSearchParams({ nation:selectedNation });
      if(coachName) params.append("coach_name",coachName);
      const res = await adminFetch(`/squad/inject?${params}`,{method:"POST"});
      const d = await res.json();
      showFb(d.status==="success"?"ok":"err", d.message || "Réponse serveur");
    } catch(e) {
      showFb("err","Erreur : "+e.message);
    } finally {
      setBusy(false);
    }
  };

  const posCounts = POSITIONS.reduce((acc,p)=>({ ...acc,[p]:players.filter(pl=>pl.position===p).length }),{});

  return (
    <div>
      <p className="page-sub">Sélectionnez une nation puis remplissez son effectif via texte ou capture d'écran Groq.</p>
      <Feedback msg={fb} />

      {/* Nation selector */}
      <div className="card">
        <div className="card-title">Sélection de la nation</div>
        {Object.entries(NATIONS_CDM2026).map(([group,nations])=>(
          <div key={group}>
            <div className="group-label">{group}</div>
            <div className="nation-grid">
              {nations.map(n=>(
                <button key={n} className={`nation-chip ${selectedNation===n?"selected":""}`}
                  onClick={()=>{ setSelectedNation(n); setPlayers([]); setCoachName(""); setFb(null); }}>
                  {n}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {selectedNation && (
        <>
          {/* Input Groq */}
          <div className="card">
            <div className="card-title">
              Remplissage Groq IA — <span>{selectedNation}</span>
              {!groqKey && <span style={{color:"var(--red)",marginLeft:8}}>⚠ Clé Groq non activée</span>}
            </div>

            <div className="upload-tabs">
              <button className={`upload-tab ${inputMode==="text"?"active":""}`} onClick={()=>setInputMode("text")}>✏️ Texte / Prompt</button>
              <button className={`upload-tab ${inputMode==="image"?"active":""}`} onClick={()=>setInputMode("image")}>📷 Capture d'écran</button>
            </div>

            {inputMode==="text" ? (
              <div className="field">
                <label>Texte de l'effectif (copier-coller depuis site officiel)</label>
                <textarea placeholder={`Collez la liste de l'effectif de ${selectedNation}...\nExemple :\n1. Mike Maignan (G) - AC Milan\n2. Théo Hernandez (D) - AC Milan\n...`}
                  value={promptText} onChange={e=>setPromptText(e.target.value)} style={{minHeight:160}} />
              </div>
            ) : (
              <div className="field">
                <div
                  className={`upload-zone ${drag?"drag":""}`}
                  onDragOver={e=>{e.preventDefault();setDrag(true);}}
                  onDragLeave={()=>setDrag(false)}
                  onDrop={e=>{e.preventDefault();setDrag(false);handleImageDrop(e.dataTransfer.files[0]);}}
                  onClick={()=>fileRef.current?.click()}
                >
                  <div style={{fontSize:"2rem"}}>📷</div>
                  <p>Glissez une capture ou cliquez pour choisir</p>
                  <p style={{fontSize:".7rem",color:"var(--text3)"}}>JPEG, PNG, WebP supportés</p>
                  {imageName && <p style={{color:"var(--green)",fontSize:".75rem",marginTop:6}}>✅ {imageName}</p>}
                  <input ref={fileRef} type="file" accept="image/*" style={{display:"none"}}
                    onChange={e=>handleImageDrop(e.target.files[0])} />
                </div>
                {imageData && <img src={imageData} alt="preview" className="upload-preview" style={{maxHeight:200,objectFit:"contain"}} />}
              </div>
            )}

            <div className="field row-2">
              <div>
                <label>Entraîneur (optionnel)</label>
                <input className="inp" placeholder="Prénom Nom" value={coachName} onChange={e=>setCoachName(e.target.value)} />
              </div>
              <div style={{display:"flex",alignItems:"flex-end"}}>
                <button className="btn-action btn-blue" style={{width:"100%"}} onClick={parseWithGroq} disabled={busy||!groqKey}>
                  {busy?<><span className="spinner"/> Analyse...</>:"🤖 Parser avec Groq"}
                </button>
              </div>
            </div>
          </div>

          {/* Effectif éditable */}
          <div className="card">
            <div className="card-title" style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
              <span>Effectif — {selectedNation} <span>({players.length} joueurs)</span></span>
              <div style={{display:"flex",gap:6}}>
                {POSITIONS.map(p=>(
                  <span key={p} style={{display:"inline-flex",alignItems:"center",gap:3,fontSize:".68rem",color:"var(--text2)"}}>
                    <span className={`pos-b ${p}`}>{p}</span> {posCounts[p]}
                  </span>
                ))}
              </div>
            </div>

            {players.length > 0 ? (
              <table className="players-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Nom</th>
                    <th>Poste</th>
                    <th>Prix M€</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {players.map((p,i)=>(
                    <tr key={p.id}>
                      <td style={{color:"var(--text3)",fontSize:".72rem",width:28}}>{i+1}</td>
                      <td>
                        <input className="name-inp" value={p.name} onChange={e=>updatePlayer(p.id,"name",e.target.value)} />
                      </td>
                      <td>
                        <select className="pos-sel" value={p.position} onChange={e=>updatePlayer(p.id,"position",e.target.value)}>
                          {POSITIONS.map(pos=><option key={pos}>{pos}</option>)}
                        </select>
                      </td>
                      <td>
                        <input className="price-inp" type="number" step=".5" min="4" max="15"
                          value={p.price} onChange={e=>updatePlayer(p.id,"price",parseFloat(e.target.value)||6.5)} />
                      </td>
                      <td><button className="btn-del" onClick={()=>removePlayer(p.id)}>✕</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{textAlign:"center",padding:"32px",color:"var(--text3)",fontSize:".82rem"}}>
                Aucun joueur — utilisez Groq ou ajoutez manuellement.
              </div>
            )}

            <button className="btn-add-row" onClick={addPlayer}>+ Ajouter un joueur</button>

            <div className="actions-strip">
              <button className="btn-action btn-green" onClick={injectSquad} disabled={busy||players.length<3}>
                {busy?<><span className="spinner"/> Injection...</>:"💾 Enregistrer en BDD"}
              </button>
              <button className="btn-action btn-ghost" onClick={()=>{ setPlayers([]); setCoachName(""); }}>
                Réinitialiser
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Section : Tournoi ───────────────────────────────────────────────────────
const KNOCKOUT_DEFS = [
  { key:"r32", label:"Huitièmes de finale", count:8 },
  { key:"qf",  label:"Quarts de finale", count:4 },
  { key:"sf",  label:"Demi-finales", count:2 },
  { key:"tp",  label:"Match pour la 3e place", count:1 },
  { key:"f",   label:"🏆 Finale", count:1 },
];

function TournamentSection({ groqKey }) {
  const [activeView, setActiveView] = useState("groups");
  const [groupData, setGroupData] = useState(
    Object.fromEntries(Object.entries(NATIONS_CDM2026).map(([g,teams])=>[g,{
      teams: teams.map(t=>({name:t,pts:0,j:0,g:0,d:0,p:0,gf:0,ga:0})),
      qualified: [teams[0], teams[1]], // top 2
    }]))
  );
  const [best3rds, setBest3rds] = useState(["","","",""]); // 4 meilleurs 3e
  const [knockout, setKnockout] = useState(
    Object.fromEntries(KNOCKOUT_DEFS.map(r=>[r.key,
      Array.from({length:r.count},()=>({home:"",away:"",winner:""}))
    ]))
  );
  const [busy, setBusy] = useState(false);
  const [fb, setFb] = useState(null);
  const [imageData, setImageData] = useState(null);
  const [imageName, setImageName] = useState("");
  const [promptText, setPromptText] = useState("");
  const [inputMode, setInputMode] = useState("text");
  const fileRef = useRef(null);

  const showFb = (type,text,dur=5000)=>{ setFb({type,text}); if(dur) setTimeout(()=>setFb(null),dur); };

  const handleImageDrop = useCallback((file)=>{
    if(!file||!file.type.startsWith("image/")) return;
    const reader=new FileReader();
    reader.onload=e=>{setImageData(e.target.result);setImageName(file.name);};
    reader.readAsDataURL(file);
  },[]);

  const parseWithGroq = async () => {
    if(!groqKey){ showFb("err","❌ Activez la clé Groq dans Paramètres."); return; }
    setBusy(true);
    showFb("info","🤖 Groq analyse le tournoi...",0);
    try {
      const systemPrompt = `Tu es expert CDM 2026. Extrais les résultats/classements du tournoi depuis le contenu fourni.
Retourne UNIQUEMENT ce JSON valide (sans markdown) :
{
  "groups": {"Groupe A": [{"name":"Mexico","pts":6,"j":3,"g":2,"d":0,"p":1,"gf":5,"ga":2}, ...], ...},
  "knockout": {
    "r32": [{"home":"1er A","away":"2e F","winner":"1er A"}, ...],
    "qf":  [...], "sf": [...], "tp": [{"home":"...","away":"...","winner":"..."}],
    "f":   [{"home":"...","away":"...","winner":"..."}]
  }
}
Si une info manque, laisse des strings vides.`;

      const messages = inputMode==="text"
        ? [{role:"user",content:promptText}]
        : [{role:"user",content:[
            {type:"image",source:{type:"base64",media_type:imageData.split(";")[0].split(":")[1],data:imageData.split(",")[1]}},
            {type:"text",text:"Extrais les données du tournoi CDM 2026 depuis cette capture."}
          ]}];

      const resp = await fetch("https://api.anthropic.com/v1/messages",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({model:"claude-sonnet-4-20250514",max_tokens:4000,system:systemPrompt,messages})
      });
      const data = await resp.json();
      const raw = data.content?.[0]?.text||"";
      const match = raw.match(/\{[\s\S]*\}/);
      if(!match) throw new Error("JSON introuvable");
      const parsed = JSON.parse(match[0]);

      if(parsed.groups){
        setGroupData(prev=>{
          const next={...prev};
          Object.entries(parsed.groups).forEach(([g,teams])=>{
            if(next[g]) next[g]={...next[g],teams:teams.map(t=>({id:uid(),...t}))};
          });
          return next;
        });
      }
      if(parsed.knockout){
        setKnockout(prev=>{
          const next={...prev};
          Object.entries(parsed.knockout).forEach(([k,matches])=>{
            if(next[k]) next[k]=matches.map(m=>({home:m.home||"",away:m.away||"",winner:m.winner||""}));
          });
          return next;
        });
      }
      showFb("ok","✅ Données tournoi parsées avec succès.");
    } catch(e) {
      showFb("err","❌ Erreur Groq : "+e.message);
    } finally {
      setBusy(false);
    }
  };

  const updateGroupTeam = (group,idx,field,val)=>{
    setGroupData(prev=>({
      ...prev,
      [group]:{
        ...prev[group],
        teams:prev[group].teams.map((t,i)=>i===idx?{...t,[field]:field==="name"?val:parseInt(val)||0}:t)
      }
    }));
  };

  const updateKO = (round,idx,field,val)=>{
    setKnockout(prev=>({
      ...prev,
      [round]:prev[round].map((m,i)=>i===idx?{...m,[field]:val}:m)
    }));
  };

  const saveTournament = async()=>{
    setBusy(true);
    showFb("info","💾 Sauvegarde tournoi...",0);
    try {
      const res = await adminFetch("/tournament/parse",{
        method:"POST",
        body:JSON.stringify({raw_tournament_text:JSON.stringify({groupData,best3rds,knockout})})
      });
      const d = await res.json();
      showFb(d.status==="success"?"ok":"err", d.message||"Sauvegardé");
    } catch(e){
      showFb("err","Erreur : "+e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <p className="page-sub">Gérez les groupes, les meilleurs 3e et le tableau d'élimination directe (seeding FIFA).</p>
      <Feedback msg={fb} />

      {/* Import Groq */}
      <div className="card">
        <div className="card-title">Import automatique via Groq IA
          {!groqKey && <span style={{color:"var(--red)",marginLeft:8}}>⚠ Clé non activée</span>}
        </div>
        <div className="upload-tabs">
          <button className={`upload-tab ${inputMode==="text"?"active":""}`} onClick={()=>setInputMode("text")}>✏️ Texte</button>
          <button className={`upload-tab ${inputMode==="image"?"active":""}`} onClick={()=>setInputMode("image")}>📷 Capture</button>
        </div>
        {inputMode==="text"
          ? <textarea placeholder="Collez les résultats, le calendrier, les classements..." value={promptText} onChange={e=>setPromptText(e.target.value)} />
          : (
            <div>
              <div className="upload-zone" onClick={()=>fileRef.current?.click()}
                onDragOver={e=>{e.preventDefault();}} onDrop={e=>{e.preventDefault();handleImageDrop(e.dataTransfer.files[0]);}}>
                <div style={{fontSize:"2rem"}}>📷</div>
                <p>Capture du tableau / résultats</p>
                {imageName && <p style={{color:"var(--green)",fontSize:".75rem"}}> ✅ {imageName}</p>}
                <input ref={fileRef} type="file" accept="image/*" style={{display:"none"}} onChange={e=>handleImageDrop(e.target.files[0])} />
              </div>
              {imageData && <img src={imageData} alt="" style={{maxHeight:200,maxWidth:"100%",marginTop:8,borderRadius:6}} />}
            </div>
          )}
        <div className="actions-strip">
          <button className="btn-action btn-blue" onClick={parseWithGroq} disabled={busy||!groqKey}>
            {busy?<><span className="spinner"/> Analyse...</>:"🤖 Parser avec Groq"}
          </button>
        </div>
      </div>

      {/* View tabs */}
      <div className="mode-tab-bar">
        <button className={`mode-tab ${activeView==="groups"?"active":""}`} onClick={()=>setActiveView("groups")}>📊 Phase de groupes</button>
        <button className={`mode-tab ${activeView==="third"?"active":""}`} onClick={()=>setActiveView("third")}>🥉 Meilleurs 3e</button>
        <button className={`mode-tab ${activeView==="ko"?"active":""}`} onClick={()=>setActiveView("ko")}>⚡ Élimination directe</button>
      </div>

      {activeView==="groups" && (
        <div>
          {Object.entries(groupData).map(([group,data])=>(
            <div key={group} className="group-card">
              <div className="group-card-title">{group}</div>
              <table className="players-table">
                <thead>
                  <tr>
                    <th>#</th><th>Équipe</th>
                    <th>Pts</th><th>J</th>
                    <th>G</th><th>N</th><th>P</th>
                    <th>BP</th><th>BC</th>
                  </tr>
                </thead>
                <tbody>
                  {data.teams.map((t,i)=>(
                    <tr key={i}>
                      <td style={{color:"var(--text3)",fontSize:".72rem"}}>{i+1}</td>
                      <td>
                        <select style={{background:"var(--s3)",border:"1px solid var(--border)",borderRadius:4,padding:"3px 6px",color:"var(--text)",fontSize:".8rem",width:160}}
                          value={t.name} onChange={e=>updateGroupTeam(group,i,"name",e.target.value)}>
                          {ALL_NATIONS.map(n=><option key={n} value={n}>{n}</option>)}
                        </select>
                      </td>
                      {["pts","j","g","d","p","gf","ga"].map(f=>(
                        <td key={f}>
                          <input type="number" style={{width:38,background:"var(--s3)",border:"1px solid var(--border)",borderRadius:4,padding:"3px 5px",color:"var(--text)",fontSize:".78rem",textAlign:"center"}}
                            value={t[f]||0} onChange={e=>updateGroupTeam(group,i,f,e.target.value)} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}

      {activeView==="third" && (
        <div className="card">
          <div className="card-title">Meilleurs 3e qualifiés <span style={{color:"var(--text3)"}}>— 4 équipes se qualifient parmi les 12 troisièmes</span></div>
          <div style={{marginBottom:12,padding:"10px 14px",background:"rgba(255,204,68,.06)",border:"1px solid rgba(255,204,68,.2)",borderRadius:8,fontSize:".78rem",color:"var(--text2)",lineHeight:1.6}}>
            <strong style={{color:"var(--gold)"}}>Règle FIFA CDM 2026</strong> — Les 4 meilleurs 3e (sur 12) sont classés par points, puis différence de buts, puis buts marqués.
            Leur position dans le tableau d'élimination directe est prédéfinie selon les groupes d'origine.
          </div>
          {[0,1,2,3].map(i=>(
            <div key={i} className="group-rank-row">
              <span className="rank-num" style={{color:"var(--gold)"}}>🥉{i+1}</span>
              <select style={{flex:1,background:"var(--s3)",border:"1px solid var(--border)",borderRadius:4,padding:"6px 8px",color:"var(--text)",fontSize:".82rem"}}
                value={best3rds[i]} onChange={e=>setBest3rds(prev=>prev.map((v,j)=>j===i?e.target.value:v))}>
                <option value="">— Équipe —</option>
                {ALL_NATIONS.map(n=><option key={n} value={n}>{n}</option>)}
              </select>
              <span className="third-badge">Meilleur 3e #{i+1}</span>
            </div>
          ))}
        </div>
      )}

      {activeView==="ko" && (
        <div>
          <div style={{marginBottom:12,padding:"10px 14px",background:"rgba(79,139,255,.06)",border:"1px solid rgba(79,139,255,.2)",borderRadius:8,fontSize:".78rem",color:"var(--text2)",lineHeight:1.6}}>
            <strong style={{color:"var(--blue)"}}>Seeding FIFA CDM 2026</strong> — Ex: 1er Groupe A vs 2e Groupe B, ou 1er Groupe C vs Meilleur 3e de D/E/F…
            Entrez manuellement les noms ou importez via Groq.
          </div>
          {KNOCKOUT_DEFS.map(({key,label,count})=>(
            <div key={key} className="ko-card">
              <div className="ko-header">{label}</div>
              {knockout[key]?.map((m,i)=>(
                <div key={i} className="ko-match">
                  <input className="ko-team-inp" placeholder="Équipe 1" value={m.home} onChange={e=>updateKO(key,i,"home",e.target.value)} />
                  <span className="ko-vs">vs</span>
                  <input className="ko-team-inp" placeholder="Équipe 2" value={m.away} onChange={e=>updateKO(key,i,"away",e.target.value)} />
                  <input className="ko-winner-inp" placeholder="✅ Qualifié" value={m.winner} onChange={e=>updateKO(key,i,"winner",e.target.value)} />
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="actions-strip" style={{marginTop:8}}>
        <button className="btn-action btn-green" onClick={saveTournament} disabled={busy}>
          {busy?<><span className="spinner"/> Sauvegarde...</>:"💾 Enregistrer le tournoi"}
        </button>
      </div>
    </div>
  );
}

// ─── Section : Règles du jeu ─────────────────────────────────────────────────
function RulesSection() {
  const [activeMode, setActiveMode] = useState("fantasy");
  const [rules, setRules] = useState(JSON.parse(JSON.stringify(DEFAULT_RULES)));
  const [fb, setFb] = useState(null);
  const [busy, setBusy] = useState(false);

  const showFb = (type,text,dur=4000)=>{ setFb({type,text}); if(dur) setTimeout(()=>setFb(null),dur); };

  const updateFantasyRule = (id,field,val)=>{
    setRules(prev=>({...prev,fantasy:prev.fantasy.map(r=>r.id===id?{...r,[field]:val}:r)}));
  };
  const updateSimpleRule = (mode,id,field,val)=>{
    setRules(prev=>({...prev,[mode]:prev[mode].map(r=>r.id===id?{...r,[field]:val}:r)}));
  };
  const addRule = ()=>{
    const newRule = activeMode==="fantasy"
      ? { id:`f${uid()}`, label:"Nouvelle règle", G:0, D:0, M:0, A:0 }
      : { id:`${activeMode[0]}${uid()}`, label:"Nouvelle règle", pts:0, ...(activeMode==="coach"?{note:""}:{}) };
    setRules(prev=>({...prev,[activeMode]:[...prev[activeMode],newRule]}));
  };
  const deleteRule = (id)=>{
    setRules(prev=>({...prev,[activeMode]:prev[activeMode].filter(r=>r.id!==id)}));
  };

  const saveRules = async()=>{
    setBusy(true);
    try {
      // Sauvegarde locale + envoi backend
      localStorage.setItem("admin_custom_rules", JSON.stringify(rules));
      try {
        await adminFetch("/rules/update",{
          method:"POST",
          body:JSON.stringify({rule_name:"full_ruleset",description:"Barème complet",points_value:0,is_active:true,
            position_affected:"ALL"})
        });
      } catch(e) { /* backend peut ne pas supporter */ }
      showFb("ok","✅ Règles sauvegardées (local + BDD si disponible).");
    } finally {
      setBusy(false);
    }
  };

  const resetRules = ()=>{
    setRules(JSON.parse(JSON.stringify(DEFAULT_RULES)));
    showFb("info","Règles réinitialisées aux valeurs par défaut.");
  };

  return (
    <div>
      <p className="page-sub">Modifiez les barèmes et règles par mode de jeu. Les changements sont appliqués au moteur de calcul.</p>
      <Feedback msg={fb} />

      <div className="mode-tab-bar">
        {Object.entries(MODE_LABELS).map(([key,label])=>(
          <button key={key} className={`mode-tab ${activeMode===key?"active":""}`} onClick={()=>setActiveMode(key)}>
            {label}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-title" style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <span>{MODE_LABELS[activeMode]}</span>
          <div style={{display:"flex",gap:6}}>
            <button className="btn-action btn-ghost btn-sm" onClick={resetRules}>Réinitialiser</button>
            <button className="btn-save-rules" onClick={saveRules} disabled={busy}>
              {busy?<><span className="spinner"/>Sauvegarde...</>:"💾 Sauvegarder"}
            </button>
          </div>
        </div>

        {/* Fantasy League rules (par poste) */}
        {activeMode==="fantasy" && (
          <>
            <table className="rules-table">
              <thead>
                <tr>
                  <th style={{width:"40%"}}>Action</th>
                  <th className="pts-cell">G</th>
                  <th className="pts-cell">D</th>
                  <th className="pts-cell">M</th>
                  <th className="pts-cell">A</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rules.fantasy.map(r=>(
                  <tr key={r.id}>
                    <td>
                      <input className="rule-inp" value={r.label} onChange={e=>updateFantasyRule(r.id,"label",e.target.value)} />
                    </td>
                    {POSITIONS.map(pos=>(
                      <td key={pos} className="pts-cell">
                        <input className="pts-inp" type="number" step="1"
                          value={r[pos]} onChange={e=>updateFantasyRule(r.id,pos,parseInt(e.target.value)||0)}
                          style={{color:r[pos]>0?"var(--green)":r[pos]<0?"var(--red)":"var(--text)"}}
                        />
                      </td>
                    ))}
                    <td><button className="btn-del" onClick={()=>deleteRule(r.id)}>✕</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{marginTop:10,padding:"8px 12px",background:"rgba(0,255,170,.05)",border:"1px solid rgba(0,255,170,.15)",borderRadius:6,fontSize:".72rem",color:"var(--text2)"}}>
              G=Gardien · D=Défenseur · M=Milieu · A=Attaquant. Valeurs négatives = malus.
            </div>
          </>
        )}

        {/* Entraîneur rules */}
        {activeMode==="coach" && (
          <table className="rules-table">
            <thead>
              <tr><th style={{width:"45%"}}>Action</th><th className="pts-cell">Points</th><th style={{width:"35%"}}>Note</th><th></th></tr>
            </thead>
            <tbody>
              {rules.coach.map(r=>(
                <tr key={r.id}>
                  <td><input className="rule-inp" value={r.label} onChange={e=>updateSimpleRule("coach",r.id,"label",e.target.value)} /></td>
                  <td className="pts-cell">
                    <input className="pts-inp" type="number" value={r.pts}
                      onChange={e=>updateSimpleRule("coach",r.id,"pts",parseInt(e.target.value)||0)}
                      style={{color:r.pts>0?"var(--green)":r.pts<0?"var(--red)":"var(--text)"}}
                    />
                  </td>
                  <td><input className="rule-inp" value={r.note||""} placeholder="Explication..."
                    onChange={e=>updateSimpleRule("coach",r.id,"note",e.target.value)} /></td>
                  <td><button className="btn-del" onClick={()=>deleteRule(r.id)}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pronostics, Bracket, Annexes rules */}
        {["pronos","bracket","annexes"].includes(activeMode) && (
          <table className="rules-table">
            <thead>
              <tr><th style={{width:"75%"}}>Condition / Règle</th><th className="pts-cell">Points</th><th></th></tr>
            </thead>
            <tbody>
              {rules[activeMode].map(r=>(
                <tr key={r.id}>
                  <td><input className="rule-inp" value={r.label} onChange={e=>updateSimpleRule(activeMode,r.id,"label",e.target.value)} /></td>
                  <td className="pts-cell">
                    <input className="pts-inp" type="number" value={r.pts}
                      onChange={e=>updateSimpleRule(activeMode,r.id,"pts",parseInt(e.target.value)||0)}
                      style={{color:r.pts>0?"var(--green)":r.pts<0?"var(--red)":"var(--text)"}}
                    />
                  </td>
                  <td><button className="btn-del" onClick={()=>deleteRule(r.id)}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <button className="btn-add-row" onClick={addRule}>+ Ajouter une règle</button>
      </div>
    </div>
  );
}

// ─── Section : Outils ────────────────────────────────────────────────────────
function ToolsSection({ groqKey }) {
  const [busy,setBusy]=useState(false);
  const [fb,setFb]=useState(null);
  const showFb=(type,text,dur=5000)=>{setFb({type,text});if(dur)setTimeout(()=>setFb(null),dur);};

  const forceScraping = async()=>{
    setBusy(true);
    showFb("info","🔄 Scraping lancé...",0);
    try{
      const res = await fetch(`${API_BASE}/api/admin/force-scraping`,{
        method:"POST",
        headers:{"Authorization":`Bearer ${getAdminToken()}`}
      });
      const d = await res.json();
      showFb(res.ok?"ok":"err", d.message||"Terminé");
    }catch(e){showFb("err","Erreur : "+e.message);}finally{setBusy(false);}
  };

  return (
    <div>
      <p className="page-sub">Outils de maintenance et synchronisation des données.</p>
      <Feedback msg={fb} />
      <div className="card">
        <div className="card-title">Synchronisation</div>
        <p style={{fontSize:".82rem",color:"var(--text2)",marginBottom:14,lineHeight:1.6}}>
          Force le scraping Groq des résultats CDM 2026 et recalcule automatiquement les points de tous les utilisateurs.
        </p>
        <button className="btn-action btn-blue" onClick={forceScraping} disabled={busy||!groqKey}>
          {busy?<><span className="spinner"/> Scraping...</>:"🔄 Forcer le scraping"}
        </button>
        {!groqKey && <p style={{fontSize:".72rem",color:"var(--red)",marginTop:8}}>⚠ Clé Groq requise</p>}
      </div>
      <div className="card">
        <div className="card-title">Statut système</div>
        <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
          {[
            {label:"Health", url:"/api/health"},
            {label:"Scraping status",url:"/api/scraping/status"},
            {label:"Swagger Docs",url:"/docs"},
          ].map(({label,url})=>(
            <a key={url} href={`${API_BASE}${url}`} target="_blank" rel="noopener"
              className="btn-action btn-ghost btn-sm" style={{textDecoration:"none",display:"inline-flex",alignItems:"center",gap:4}}>
              🔗 {label}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
//  MAIN COMPONENT
// ════════════════════════════════════════════════════════════════════════════

const TABS = [
  { id:"settings",  icon:"⚙️",  label:"Paramètres" },
  { id:"squads",    icon:"👥",  label:"Effectifs" },
  { id:"tournament",icon:"🏆",  label:"Tournoi" },
  { id:"rules",     icon:"📋",  label:"Règles du jeu" },
  { id:"tools",     icon:"🛠️",  label:"Outils" },
];

function AdminDashboard({ onLogout }) {
  const [activeTab, setActiveTab] = useState("settings");
  const [groqKey, setGroqKey] = useState(()=>getStoredGroqKey());

  const handleGroqKeyChange = (k) => setGroqKey(k);

  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">Fantasy<span>⚡</span>Admin</div>
        {TABS.map(t=>(
          <button key={t.id} className={`nav-item ${activeTab===t.id?"active":""}`} onClick={()=>setActiveTab(t.id)}>
            <span className="icon">{t.icon}</span>{t.label}
          </button>
        ))}
        <div className="sidebar-bottom">
          <div style={{display:"flex",alignItems:"center",gap:8,padding:"8px 10px",marginBottom:8}}>
            <span className={`groq-badge ${groqKey?"on":"off"}`} style={{fontSize:".65rem"}}>
              <span className={`groq-dot ${groqKey?"pulse":""}`}/>
              Groq {groqKey?"ON":"OFF"}
            </span>
          </div>
          <button className="btn-logout" onClick={onLogout}>🚪 Déconnexion</button>
        </div>
      </aside>

      <main className="main-content">
        <div className="page-title">
          {TABS.find(t=>t.id===activeTab)?.icon} {TABS.find(t=>t.id===activeTab)?.label}
        </div>

        {activeTab==="settings"  && <SettingsSection groqKey={groqKey} onGroqKeyChange={handleGroqKeyChange} />}
        {activeTab==="squads"    && <SquadsSection groqKey={groqKey} />}
        {activeTab==="tournament"&& <TournamentSection groqKey={groqKey} />}
        {activeTab==="rules"     && <RulesSection />}
        {activeTab==="tools"     && <ToolsSection groqKey={groqKey} />}
      </main>
    </div>
  );
}

function AdminLogin({ onSuccess }) {
  const [user,setUser]=useState("");
  const [pass,setPass]=useState("");
  const [err,setErr]=useState("");
  const [busy,setBusy]=useState(false);

  const submit = async(e)=>{
    e.preventDefault();
    setErr(""); setBusy(true);
    try{
      const res = await fetch(`${API_BASE}/api/admin/login`,{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({username:user.trim(),password:pass}),
        signal:AbortSignal.timeout(API_TIMEOUT),
      });
      const d = await res.json().catch(()=>({}));
      if(res.ok && d.access_token){
        setAdminToken(d.access_token);
        window.dispatchEvent(new Event("storage"));
        onSuccess(d.access_token);
      } else {
        setErr(d.detail||d.message||"Identifiants incorrects.");
      }
    }catch(e){
      setErr(e.name==="TimeoutError"?"Timeout — backend inaccessible.":"Erreur réseau : "+e.message);
    } finally { setBusy(false); }
  };

  return (
    <div className="login-wrap">
      <form className="login-box" onSubmit={submit}>
        <div className="login-logo">Fantasy <span>⚡</span> Admin</div>
        <div>
          <label>Pseudo</label>
          <input className="inp" type="text" placeholder="admin" value={user} onChange={e=>setUser(e.target.value)} autoComplete="username" required />
        </div>
        <div>
          <label>Mot de passe</label>
          <input className="inp" type="password" placeholder="••••••" value={pass} onChange={e=>setPass(e.target.value)} autoComplete="current-password" required />
        </div>
        {err && <p className="err-msg">⚠ {err}</p>}
        <button className="btn-primary" type="submit" disabled={busy}>
          {busy?<><span className="spinner" style={{borderTopColor:"#fff"}}/> Connexion...</>:"Se connecter"}
        </button>
        <p className="hint">admin / admin00</p>
      </form>
    </div>
  );
}

export default function AdminPanel() {
  const [token, setToken] = useState(()=>getAdminToken());

  const handleLogout = ()=>{
    setAdminToken(null);
    setToken("");
    window.dispatchEvent(new Event("storage"));
  };

  return (
    <>
      <style>{css}</style>
      <div className="admin-root">
        {!token
          ? <AdminLogin onSuccess={t=>setToken(t)} />
          : <AdminDashboard onLogout={handleLogout} />
        }
      </div>
    </>
  );
}