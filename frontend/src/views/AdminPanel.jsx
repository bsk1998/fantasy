/**
 * AdminPanel.jsx — Panneau d'administration Fantasy Boulzazen WC 2026
 * ====================================================================
 * ✅ Fix 1 : ToolsSection vérifie groq_configure depuis /api/scraping/status
 * ✅ Fix 2 : UsersSection — token Bearer transmis correctement via adminFetch
 * ✅ Fix 3 : RulesSection — saveRules envoie TOUTES les règles en BDD
 * ✅ Fix 4 : SquadsSection — parse via backend /api/admin/squad/parse
 * ✅ Fix 5 : nation-chip affiche ✅ + bordure verte si effectif complet
 * ✅ Fix 6 : AdminLogin — guillemets JSX corrigés (plus de backslash-escape)
 * ✅ Étape 1.2 : POST /squads/import-from-olympics (bouton + spinner + rapport)
 * ✅ Étape 2.2 : Table effectifs éditable inline (double-clic = input, Entrée = save)
 * ✅ Ajustement : Logique de guidage et bandeau d'aide en cas d'échec d'import automatique
 */

import React, { useState, useRef, useEffect, useCallback } from "react";

// ─── Config ───────────────────────────────────────────────────────────────────
const API_BASE    = import.meta.env.VITE_API_BASE || "";
const API_TIMEOUT = 20000;

// ─── 48 nations qualifiées CDM 2026 ──────────────────────────────────────────
const NATIONS_CDM2026 = {
  "Groupe A": ["Mexique","Afrique du Sud","République de Corée","Tchéquie"],
  "Groupe B": ["Canada","Bosnie-Herzégovine","Qatar","Suisse"],
  "Groupe C": ["Brésil","Maroc","Haïti","Écosse"],
  "Groupe D": ["États-Unis d'Amérique","Paraguay","Australie","Türkiye"],
  "Groupe E": ["Allemagne","Colombie","Nouvelle-Zélande","Irak"],
  "Groupe F": ["Italie","Cameroun","Pérou","Fidji"],
  "Groupe G": ["Espagne","Algérie","Émirats Arabes Unis","Pologne"],
  "Groupe H": ["Angleterre","Égypte","Oman","Slovaquie"],
  "Groupe I": ["Portugal","Mali","Chine","Jamaïque"],
  "Groupe J": ["Pays-Bas","Côte d'Ivoire","Arabie Saoudite","Costa Rica"],
  "Groupe K": ["Argentine","Ghana","Japon","Panama"],
  "Groupe L": ["France","Nigeria","Iran","Honduras"]
};

const ALL_NATIONS = Object.values(NATIONS_CDM2026).flat();
const POSITIONS   = ["G", "D", "M", "A"];

// ─── Helpers ──────────────────────────────────────────────────────────────────
const uid = () => Math.random().toString(36).substring(2, 9);

function getAdminToken() {
  return localStorage.getItem("boulzazen_admin_token") || "";
}
function setAdminToken(t) {
  if (t) localStorage.setItem("boulzazen_admin_token", t);
  else localStorage.removeItem("boulzazen_admin_token");
}

async function adminFetch(endpoint, options = {}) {
  const token = getAdminToken();
  const headers = { ...(options.headers || {}) };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), API_TIMEOUT);

  try {
    const res = await fetch(`${API_BASE}/api/admin${endpoint}`, {
      ...options,
      headers,
      signal: controller.signal
    });
    clearTimeout(id);
    return res;
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}

// ─── Composants réutilisables UI ──────────────────────────────────────────────
function Feedback({ msg }) {
  if (!msg) return null;
  const cls = msg.type === "ok" ? "fb-ok" : msg.type === "err" ? "fb-err" : "fb-info";
  return <div className={`feedback-bar ${cls}`}>{msg.text}</div>;
}

// ════════════════════════════════════════════════════════════════════════════
//  SECTIONS DU PANEL
// ════════════════════════════════════════════════════════════════════════════

// --- SECTION 1 : UTILISATEURS ---
function UsersSection() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fb, setFb] = useState(null);

  const showFb = (type, text) => { setFb({type, text}); setTimeout(() => setFb(null), 4000); };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/users");
      const data = await res.json();
      if (res.ok && data.status === "success") {
        setUsers(data.users || []);
      } else {
        showFb("err", data.detail || "Impossible de récupérer les utilisateurs");
      }
    } catch (e) {
      showFb("err", "Erreur réseau: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, []);

  const deleteUser = async (id, name) => {
    if (!window.confirm(`⚠️ ATTENTION ! Supprimer définitivement l'utilisateur ${name} ? Toutes ses prédictions et équipes fantasy seront effacées.`)) return;
    try {
      const res = await adminFetch(`/users/${id}`, { method: "DELETE" });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        showFb("ok", data.message);
        loadUsers();
      } else {
        showFb("err", data.detail || "Erreur lors de la suppression");
      }
    } catch (e) {
      showFb("err", "Erreur réseau: " + e.message);
    }
  };

  const syncGeneralLeague = async () => {
    try {
      showFb("info", "Synchronisation de la ligue générale...");
      const res = await adminFetch("/leagues/general/sync", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        showFb("ok", data.message);
      } else {
        showFb("err", data.detail || "Erreur de synchro");
      }
    } catch (e) {
      showFb("err", "Erreur réseau: " + e.message);
    }
  };

  const initGeneralLeague = async () => {
    try {
      showFb("info", "Création de la ligue générale...");
      const res = await adminFetch("/leagues/general", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        showFb("ok", data.message);
      } else {
        showFb("err", data.detail || "Erreur d'initialisation");
      }
    } catch (e) {
      showFb("err", "Erreur réseau: " + e.message);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", gap: "10px", marginBottom: "15px" }}>
        <button className="btn-action btn-blue" onClick={initGeneralLeague}>🛡️ Init Ligue Générale</button>
        <button className="btn-action btn-ghost" onClick={syncGeneralLeague}>🔄 Sync Ligue Générale</button>
      </div>
      <Feedback msg={fb} />
      <div className="card">
        <div className="card-title">Comptes Joueurs ({users.length})</div>
        {loading ? <p>Chargement des utilisateurs...</p> : (
          <table className="players-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Pseudo / Email</th>
                <th>Fantasy</th>
                <th>Scores</th>
                <th>Tableaux</th>
                <th>Annexes</th>
                <th>Total</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td><strong>{u.username || u.email}</strong></td>
                  <td>{u.score_fantasy} pts</td>
                  <td>{u.score_predictor_scores} pts</td>
                  <td>{u.score_predictor_tableaux} pts</td>
                  <td>{u.score_top_individuel} pts</td>
                  <td style={{ color: "var(--gold)", fontWeight: "bold" }}>{u.total} pts</td>
                  <td>
                    <button className="btn-del" onClick={() => deleteUser(u.id, u.username || u.email)}>✕ Supprimer</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// --- SECTION 2 : EFFECTIFS ---
function SquadsSection() {
  const [selectedNation, setSelectedNation] = useState(null);
  const [inputMode,    setInputMode]    = useState("text");
  const [promptText,   setPromptText]   = useState("");
  const [imageData,    setImageData]    = useState(null);
  const [imageName,    setImageName]    = useState("");
  const [drag,         setDrag]         = useState(false);
  const [players,      setPlayers]      = useState([]);
  const [coachName,    setCoachName]    = useState("");
  const [busy,         setBusy]         = useState(false);
  const [importBusy,   setImportBusy]   = useState(false);
  const [importReport, setImportReport] = useState(null);
  const [fb,           setFb]           = useState(null);
  const [filledNations, setFilledNations] = useState(new Set());
  const [loadingFilled, setLoadingFilled] = useState(false);

  // État pour l'édition inline (double-clic)
  const [editingCell, setEditingCell] = useState(null); // { id, field }
  const fileRef = useRef(null);

  const showFb = (type, text, dur = 5000) => {
    setFb({type, text}); if (dur) setTimeout(() => setFb(null), dur);
  };

  const loadFilledNations = useCallback(async () => {
    setLoadingFilled(true);
    try {
      const res = await adminFetch("/squad/filled-nations");
      const data = await res.json();
      if (res.ok && data.status === "success") {
        setFilledNations(new Set(data.filled_nations || []));
      }
    } catch (e) {
      console.error("Erreur chargement nations complètes:", e);
    } finally {
      setLoadingFilled(false);
    }
  }, []);

  useEffect(() => { loadFilledNations(); }, [loadFilledNations]);

  // ── Import Olympics Modifié ──────────────────────────────────────────────
  const importFromOlympics = async () => {
    setImportBusy(true);
    setImportReport(null);
    showFb("info", "🌐 Import depuis olympics.com en cours (peut prendre 30–60s)...", 0);
    try {
      const res  = await adminFetch("/squads/import-from-olympics", { method: "POST" });
      const data = await res.json();
      setImportReport(data);
      if (data.status === "success" || data.status === "partial") {
        showFb("ok", `✅ ${data.imported} nations importées (stratégie : ${data.strategy})`);
        await loadFilledNations();
      } else {
        // Import échoué → on suggère le fallback
        showFb("err", `❌ Import automatique impossible. Utilisez l'option "Coller texte" ci-dessous.`);
        // Sélectionner automatiquement le mode texte pour guider l'utilisateur
        setInputMode("text");
        if (!selectedNation) {
          // Afficher un prompt pour choisir une nation
          setPromptText(""); // vider pour inciter à coller
        }
      }
    } catch (e) {
      showFb("err", "Erreur réseau : " + e.message);
    } finally {
      setImportBusy(false);
    }
  };

  const handleImageDrop = useCallback((file) => {
    if (!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = e => { setImageData(e.target.result); setImageName(file.name); };
    reader.readAsDataURL(file);
  }, []);

  const addPlayer = () => setPlayers(prev => [...prev, { id: uid(), name: "", position: "M", price: 6.5 }]);

  // ── Édition inline (double-clic → input, Entrée/blur → sauvegarde) ──────
  const startEdit = (id, field) => setEditingCell({ id, field });

  const commitEdit = async (playerId, field, value, isNew) => {
    setEditingCell(null);
    setPlayers(prev => prev.map(p => p.id === playerId ? { ...p, [field]: value } : p));
    // Si joueur déjà en BDD (id numérique), PATCH via l'API (Étape 2.2)
    if (!isNew && typeof playerId === "number") {
      try {
        const body = { [field]: field === "price" ? parseFloat(value) : value };
        const res  = await adminFetch(`/players/${playerId}`, {
          method: "PATCH",
          body:   JSON.stringify(body),
        });
        if (!res.ok) {
          const d = await res.json();
          showFb("err", `❌ ${d.detail || "Erreur sauvegarde"}`);
        }
      } catch (e) {
        showFb("err", "Erreur réseau patch : " + e.message);
      }
    }
  };

  const removePlayer = (id) => setPlayers(prev => prev.filter(p => p.id !== id));

  const parseWithGroq = async () => {
    if (!selectedNation) { showFb("err", "❌ Sélectionnez une nation."); return; }
    const hasContent = inputMode === "text" ? promptText.trim().length > 5 : !!imageData;
    if (!hasContent) { showFb("err", "❌ Fournissez du texte ou une capture d'écran."); return; }
    setBusy(true);
    showFb("info", "🤖 Groq analyse les données via le backend...", 0);
    try {
      const rawText = inputMode === "text"
        ? `Nation: ${selectedNation}\n\n${promptText}`
        : `Nation: ${selectedNation}\n[IMAGE BASE64]\n${imageData}`;
      const res  = await adminFetch("/squad/parse", {
        method: "POST",
        body:   JSON.stringify({ nation: selectedNation, raw_squad_text: rawText }),
      });
      const data = await res.json();
      if (!res.ok || data.status === "error") throw new Error(data.message || data.detail || "Erreur serveur");
      const parsed = data.parsed_data;
      if (!parsed) throw new Error("Données parsées vides");
      if (parsed.coach_name) setCoachName(parsed.coach_name);
      if (parsed.players && parsed.players.length > 0) {
        setPlayers(parsed.players.map(p => ({ id: uid(), name: p.name || "", position: p.position || "M", price: p.price || 6.5 })));
        showFb("ok", data.message || `✅ ${parsed.players.length} joueurs détectés`);
      } else {
        showFb("err", "⚠️ Aucun joueur détecté — reformulez ou améliorez la capture.");
      }
    } catch (e) {
      showFb("err", "❌ Erreur : " + e.message);
    } finally { setBusy(false); }
  };

  const injectSquad = async () => {
    if (!selectedNation || players.length < 3) { showFb("err", "❌ Sélectionnez une nation et entrez au moins 3 joueurs."); return; }
    setBusy(true);
    showFb("info", "💾 Injection en base de données...", 0);
    try {
      const params = new URLSearchParams({ nation: selectedNation });
      if (coachName) params.append("coach_name", coachName);
      // Envoyer les joueurs dans le body JSON (liste)
      const res = await adminFetch(`/squad/inject?${params}`, {
        method: "POST",
        body: JSON.stringify(players.map(p => ({ name: p.name, position: p.position, price: p.price }))),
      });
      const data = await res.json();
      if (data.status === "success") {
        showFb("ok", data.message || "Effectif enregistré !");
        await loadFilledNations();
      } else {
        showFb("err", data.message || "Erreur serveur");
      }
    } catch (e) { showFb("err", "Erreur : " + e.message); }
    finally { setBusy(false); }
  };

  // ── Cellule éditable (Étape 2.2) ─────────────────────────────────────────
  const EditableCell = ({ playerId, field, value, isNew, type = "text", options }) => {
    const isEditing = editingCell?.id === playerId && editingCell?.field === field;
    const [draft, setDraft] = useState(value);
    useEffect(() => { setDraft(value); }, [value]);

    if (isEditing) {
      if (options) {
        return (
          <select
            className="pos-sel"
            autoFocus
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onBlur={() => commitEdit(playerId, field, draft, isNew)}
          >
            {options.map(o => <option key={o}>{o}</option>)}
          </select>
        );
      }
      return (
        <input
          autoFocus
          className={field === "price" ? "price-inp" : "name-inp"}
          type={type}
          step={type === "number" ? ".5" : undefined}
          min={type === "number" ? "4" : undefined}
          max={type === "number" ? "15" : undefined}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onBlur={() => commitEdit(playerId, field, type === "number" ? parseFloat(draft) || 6.5 : draft, isNew)}
          onKeyDown={e => {
            if (e.key === "Enter") commitEdit(playerId, field, type === "number" ? parseFloat(draft) || 6.5 : draft, isNew);
            if (e.key === "Escape") setEditingCell(null);
          }}
        />
      );
    }

    return (
      <span
        style={{ cursor: "pointer", borderBottom: "1px dashed var(--border2)", padding: "2px 4px" }}
        onDoubleClick={() => startEdit(playerId, field)}
        title="Double-clic pour éditer"
      >
        {value}
      </span>
    );
  };

  const posCounts = POSITIONS.reduce((acc, p) => ({ ...acc, [p]: players.filter(pl => pl.position === p).length }), {});
  const filledCount = ALL_NATIONS.filter(n => filledNations.has(n)).length;

  return (
    <div>
      <p className="page-sub">
        Sélectionnez une nation puis remplissez son effectif.{" "}
        {loadingFilled
          ? <span style={{ color: "var(--text3)" }}>Chargement...</span>
          : <span style={{ color: "var(--green)" }}>✅ {filledCount}/{ALL_NATIONS.length} nations complètes</span>
        }
      </p>
      <Feedback msg={fb} />

      {/* ── BOUTON IMPORT OLYMPICS ── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">🌐 Import depuis olympics.com</div>
        <p style={{ fontSize: ".8rem", color: "var(--text2)", marginBottom: 12, lineHeight: 1.6 }}>
          Scrape automatiquement les effectifs officiels publiés sur olympics.com.
          Utilise HTTP direct, puis l'IA si la page est bloquée.
        </p>
        <button
          className="btn-action btn-blue"
          onClick={importFromOlympics}
          disabled={importBusy}
          style={{ width: "100%" }}
        >
          {importBusy
            ? <><span className="spinner" /> Import en cours (HTTP + IA)...</>
            : "🌐 Importer depuis olympics.com"
          }
        </button>

        {importReport && (
          <div style={{
            marginTop: 12,
            background: importReport.status === "success" ? "rgba(0,255,170,.07)" : "rgba(255,204,68,.07)",
            border: `1px solid ${importReport.status === "success" ? "rgba(0,255,170,.25)" : "rgba(255,204,68,.25)"}`,
            borderRadius: 8, padding: "10px 14px",
            fontSize: ".78rem", lineHeight: 1.6,
          }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>
              Rapport d'import — stratégie : <em>{importReport.strategy}</em>
            </div>
            <div>✅ {importReport.imported} nation(s) importée(s)</div>
            {importReport.nations?.slice(0, 8).map(n => (
              <div key={n.nation} style={{ color: "var(--text2)", paddingLeft: 8 }}>
                • {n.nation} : {n.players} joueurs{n.coach ? `, coach : ${n.coach}` : ""}
              </div>
            ))}
            {importReport.errors?.length > 0 && (
              <div style={{ color: "var(--red)", marginTop: 6 }}>
                ⚠️ Erreurs : {importReport.errors.slice(0, 3).join(" · ")}
              </div>
            )}
            {!importReport.imported && (
              <div style={{ color: "var(--gold)", marginTop: 6 }}>
                ℹ️ {importReport.message}
              </div>
            )}
          </div>
        )}

        {/* BANDEAU D'AIDE EN CAS D'ÉCHEC */}
        {importReport && importReport.status === "error" && (
          <div style={{
            marginTop: 12,
            background: "rgba(255,200,50,.07)",
            border: "1px solid rgba(255,200,50,.3)",
            borderRadius: 8, padding: "12px 14px",
            fontSize: ".78rem", lineHeight: 1.7,
          }}>
            <div style={{ fontWeight: 700, color: "var(--gold)", marginBottom: 6 }}>
              💡 Comment importer manuellement ?
            </div>
            <ol style={{ margin: 0, paddingLeft: 18, color: "var(--text2)" }}>
              <li>Ouvrez <a href="https://www.olympics.com/fr/infos/coupe-du-monde-2026-composition-equipes-selections-liste-joueurs" target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>cette page olympics.com</a> dans votre navigateur</li>
              <li>Attendez que la page soit complètement chargée</li>
              <li>Sélectionnez tout le texte (<strong>Ctrl+A</strong>)</li>
              <li>Copiez (<strong>Ctrl+C</strong>)</li>
              <li>Choisissez une nation ci-dessous, collez dans le champ texte et cliquez <strong>Parser avec Groq</strong></li>
            </ol>
          </div>
        )}
      </div>

      {/* ── SÉLECTION NATION ── */}
      <div className="card">
        <div className="card-title">Sélection de la nation</div>
        {Object.entries(NATIONS_CDM2026).map(([group, nations]) => (
          <div key={group}>
            <div className="group-label">{group}</div>
            <div className="nation-grid">
              {nations.map(n => {
                const isFilled   = filledNations.has(n);
                const isSelected = selectedNation === n;
                return (
                  <button key={n}
                    className={`nation-chip ${isSelected ? "selected" : ""} ${isFilled ? "filled" : ""}`}
                    onClick={() => { setSelectedNation(n); setPlayers([]); setCoachName(""); setFb(null); }}>
                    {isFilled && <span className="nation-chip-check">✅</span>}
                    {n}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {selectedNation && (
        <>
          <div className="card">
            <div className="card-title">Remplissage Groq IA — <span>{selectedNation}</span></div>
            <div className="upload-tabs">
              <button className={`upload-tab ${inputMode === "text" ? "active" : ""}`} onClick={() => setInputMode("text")}>✏️ Texte</button>
              <button className={`upload-tab ${inputMode === "image" ? "active" : ""}`} onClick={() => setInputMode("image")}>📷 Capture</button>
            </div>
            {inputMode === "text"
              ? <div className="field">
                  <label>Texte de l'effectif</label>
                  <textarea placeholder={`Collez la liste de ${selectedNation} ici...`} value={promptText} onChange={e => setPromptText(e.target.value)} style={{ minHeight: 160 }} />
                </div>
              : <div className="field">
                  <div className={`upload-zone ${drag ? "drag" : ""}`}
                    onDragOver={e => { e.preventDefault(); setDrag(true); }}
                    onDragLeave={() => setDrag(false)}
                    onDrop={e => { e.preventDefault(); setDrag(false); handleImageDrop(e.dataTransfer.files[0]); }}
                    onClick={() => fileRef.current?.click()}>
                    <div style={{ fontSize: "2rem" }}>📷</div>
                    <p>Glissez une capture ou cliquez</p>
                    {imageName && <p style={{ color: "var(--green)", fontSize: ".75rem", marginTop: 6 }}>✅ {imageName}</p>}
                    <input ref={fileRef} type="file" accept="image/*" style={{ display: "none" }} onChange={e => handleImageDrop(e.target.files[0])} />
                  </div>
                  {imageData && <img src={imageData} alt="preview" style={{ maxHeight: 200, maxWidth: "100%", marginTop: 8, borderRadius: 6 }} />}
                </div>
            }
            <div className="field row-2">
              <div>
                <label>Entraîneur (optionnel)</label>
                <input className="inp" placeholder="Prénom Nom" value={coachName} onChange={e => setCoachName(e.target.value)} />
              </div>
              <div style={{ display: "flex", alignItems: "flex-end" }}>
                <button className="btn-action btn-blue" style={{ width: "100%" }} onClick={parseWithGroq} disabled={busy}>
                  {busy ? <><span className="spinner" /> Analyse...</> : "🤖 Parser avec Groq"}
                </button>
              </div>
            </div>
          </div>

          {/* ── TABLE ÉDITABLE INLINE ── */}
          <div className="card">
            <div className="card-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>Effectif — {selectedNation} <span>({players.length} joueurs)</span></span>
              <div style={{ display: "flex", gap: 6 }}>
                {POSITIONS.map(p => (
                  <span key={p} style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: ".68rem", color: "var(--text2)" }}>
                    <span className={`pos-b ${p}`}>{p}</span>{posCounts[p]}
                  </span>
                ))}
              </div>
            </div>
            <p style={{ fontSize: ".72rem", color: "var(--text3)", marginBottom: 10 }}>
              💡 Double-clic sur une cellule pour l'éditer · Entrée pour valider
            </p>
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
                  {players.map((p, i) => {
                    const isNew = typeof p.id === "string"; // uid() = string, BDD = number
                    return (
                      <tr key={p.id}>
                        <td style={{ color: "var(--text3)", fontSize: ".72rem", width: 28 }}>{i + 1}</td>
                        <td>
                          <EditableCell playerId={p.id} field="name" value={p.name} isNew={isNew} />
                        </td>
                        <td>
                          <EditableCell playerId={p.id} field="position" value={p.position} isNew={isNew} options={POSITIONS} />
                        </td>
                        <td>
                          <EditableCell playerId={p.id} field="price" value={p.price} isNew={isNew} type="number" />
                        </td>
                        <td>
                          <button className="btn-del" onClick={() => removePlayer(p.id)}>✕</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div style={{ textAlign: "center", padding: "32px", color: "var(--text3)", fontSize: ".82rem" }}>
                Aucun joueur — utilisez le parsing Groq ou ajoutez manuellement.
              </div>
            )}
            <button className="btn-add-row" onClick={addPlayer}>+ Ajouter un joueur</button>
            <div className="actions-strip">
              <button className="btn-action btn-green" onClick={injectSquad} disabled={busy || players.length < 3}>
                {busy ? <><span className="spinner" /> Injection...</> : "💾 Enregistrer en BDD"}
              </button>
              <button className="btn-action btn-ghost" onClick={() => { setPlayers([]); setCoachName(""); }}>Réinitialiser</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// --- SECTION 3 : CALENDRIER & RÉSULTATS ---
function MatchesSection() {
  const [home, setHome] = useState("");
  const [away, setAway] = useState("");
  const [mdate, setMdate] = useState("");
  const [mgroup, setMgroup] = useState("Groupe A");
  const [fb, setFb] = useState(null);
  const [busy, setBusy] = useState(false);

  const showFb = (type, text) => { setFb({type, text}); setTimeout(() => setFb(null), 4000); };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!home || !away || !mdate) return;
    setBusy(true);
    try {
      const q = new URLSearchParams({ home, away, match_date: mdate, match_group: mgroup });
      const res = await adminFetch(`/match/add?${q}`, { method: "POST" });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        showFb("ok", data.message);
        setHome(""); setAway("");
      } else {
        showFb("err", data.detail || "Erreur lors de l'ajout");
      }
    } catch (e) {
      showFb("err", "Erreur réseau : " + e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: "500px" }}>
      <div className="card-title">Ajouter un match planifié</div>
      <Feedback msg={fb} />
      <form onSubmit={handleAdd}>
        <div className="field">
          <label>Équipe Domicile</label>
          <select className="pos-sel" style={{ width: "100%", height: "38px" }} value={home} onChange={e => setHome(e.target.value)} required>
            <option value="">-- Choisir --</option>
            {ALL_NATIONS.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Équipe Extérieur</label>
          <select className="pos-sel" style={{ width: "100%", height: "38px" }} value={away} onChange={e => setAway(e.target.value)} required>
            <option value="">-- Choisir --</option>
            {ALL_NATIONS.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div className="field row-2">
          <div>
            <label>Date et Heure</label>
            <input className="inp" type="datetime-local" value={mdate} onChange={e => setMdate(e.target.value)} required />
          </div>
          <div>
            <label>Phase / Groupe</label>
            <select className="pos-sel" style={{ width: "100%", height: "38px" }} value={mgroup} onChange={e => setMgroup(e.target.value)}>
              {Object.keys(NATIONS_CDM2026).map(g => <option key={g} value={g}>{g}</option>)}
              <option value="16e de finale">16e de finale</option>
              <option value="8e de finale">8e de finale</option>
              <option value="Quart de finale">Quart de finale</option>
              <option value="Demi-finale">Demi-finale</option>
              <option value="Finale">Finale</option>
            </select>
          </div>
        </div>
        <button className="btn-action btn-green" type="submit" style={{ width: "100%", marginTop: "10px" }} disabled={busy}>
          {busy ? "Enregistrement..." : "➕ Ajouter le match"}
        </button>
      </form>
    </div>
  );
}

// --- SECTION 4 : REGLES DU JEU ---
function RulesSection() {
  const [rawRules, setRawRules] = useState("");
  const [rules, setRules] = useState([]);
  const [busy, setBusy] = useState(false);
  const [fb, setFb] = useState(null);

  const showFb = (type, text) => { setFb({type, text}); setTimeout(() => setFb(null), 4000); };

  const loadRules = async () => {
    try {
      const res = await adminFetch("/rules");
      const data = await res.json();
      if (res.ok && data.status === "success") setRules(data.rules || []);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { loadRules(); }, []);

  const parseRulesText = async () => {
    if (!rawRules.trim()) return;
    setBusy(true);
    showFb("info", "Analyse des règles par l'IA...");
    try {
      const res = await adminFetch("/rules/parse", {
        method: "POST",
        body: JSON.stringify({ raw_rules_text: rawRules })
      });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        setRules(data.rules.map(r => ({
          id: uid(), rule_name: r.name, description: r.description,
          position_affected: r.position || null, points_value: r.points || 0, is_active: true
        })));
        showFb("ok", `✅ ${data.rules.length} règles extraites.`);
      } else {
        showFb("err", data.message || "Erreur d'analyse");
      }
    } catch (e) { showFb("err", e.message); }
    finally { setBusy(false); }
  };

  const saveRules = async () => {
    if (rules.length === 0) return;
    setBusy(true);
    showFb("info", "Sauvegarde de toutes les règles...");
    try {
      let successCount = 0;
      for (const r of rules) {
        const res = await adminFetch("/rules/update", {
          method: "POST",
          body: JSON.stringify({
            rule_name: r.rule_name || r.name,
            description: r.description,
            position_affected: r.position_affected || r.position || null,
            points_value: parseInt(r.points_value || r.points) || 0,
            is_active: r.is_active !== false
          })
        });
        if (res.ok) successCount++;
      }
      showFb("ok", `✅ ${successCount}/${rules.length} règles enregistrées avec succès en BDD.`);
      loadRules();
    } catch (e) { showFb("err", e.message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <div className="card">
        <div className="card-title">Parser le barème de points via IA</div>
        <div className="field">
          <textarea
            placeholder="Collez le texte brut contenant vos règles de points..."
            value={rawRules}
            onChange={e => setRawRules(e.target.value)}
            style={{ minHeight: "100px" }}
          />
        </div>
        <button className="btn-action btn-blue" onClick={parseRulesText} disabled={busy}>🤖 Extraire le barème structuré</button>
      </div>
      <Feedback msg={fb} />
      <div className="card">
        <div className="card-title">Barème Actif en Base de Données ({rules.length})</div>
        <table className="players-table">
          <thead>
            <tr>
              <th>Nom de l'action</th>
              <th>Description</th>
              <th>Poste ciblé</th>
              <th>Valeur Points</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r, i) => (
              <tr key={r.id || i}>
                <td><strong>{r.rule_name || r.name}</strong></td>
                <td>{r.description}</td>
                <td><span className={`pos-b ${r.position_affected || "TOUS"}`}>{r.position_affected || "TOUS"}</span></td>
                <td style={{ color: "var(--green)", fontWeight: "bold" }}>{r.points_value || r.points} pts</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rules.length > 0 && (
          <button className="btn-action btn-green" onClick={saveRules} style={{ width: "100%", marginTop: "15px" }} disabled={busy}>
            💾 Confirmer & Appliquer toutes les règles en BDD
          </button>
        )}
      </div>
    </div>
  );
}

// --- SECTION 5 : OUTILS & LOGS ---
function ToolsSection() {
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/scraping/status`)
      .then(res => res.json())
      .then(data => setStatus(data))
      .catch(e => console.error(e));

    setLoading(true);
    adminFetch("/logs?limit=30")
      .then(res => res.json())
      .then(data => { if (data.status === "success") setLogs(data.logs || []); })
      .catch(e => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="card row-2" style={{ gap: "20px" }}>
        <div>
          <div className="card-title">Statut Serveur & IA</div>
          <p style={{ fontSize: ".85rem", marginBottom: "6px" }}>
            Moteur de scraping : {status?.scraper_status === "functional"
              ? <span style={{ color: "var(--green)" }}>🟢 Opérationnel</span>
              : <span>⚪ Inconnu</span>}
          </p>
          <p style={{ fontSize: ".85rem" }}>
            Configuration Groq (Backend) : {status?.groq_configured
              ? <span style={{ color: "var(--green)" }}>🔒 Configurée (.env)</span>
              : <span style={{ color: "var(--red)" }}>❌ Manquante</span>}
          </p>
        </div>
      </div>
      <div className="card">
        <div className="card-title">Logs d'activité Admin (30 derniers)</div>
        {loading ? <p>Chargement des audits...</p> : (
          <div style={{ maxHeight: "350px", overflowY: "auto", fontSize: ".8rem", fontFamily: "monospace", background: "var(--bg)", padding: "10px", borderRadius: "6px", border: "1px solid var(--border)" }}>
            {logs.map(l => (
              <div key={l.id} style={{ marginBottom: "6px", borderBottom: "1px dashed var(--border2)", paddingBottom: "4px" }}>
                <span style={{ color: "var(--text3)" }}>[{l.timestamp?.substring(11, 19)}]</span>{" "}
                <span style={{ color: "var(--gold)", fontWeight: "bold" }}>{l.action.toUpperCase()}</span>{" "}
                <span style={{ color: "var(--text2)" }}>({l.target})</span> — {l.details}
              </div>
            ))}
            {logs.length === 0 && <p style={{ color: "var(--text3)" }}>Aucune action logguée.</p>}
          </div>
        )}
      </div>
    </div>
  );
}

// --- LOGIN FORM ---
function AdminLogin({ onLoginSuccess }) {
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const res = await fetch(`${API_BASE}/api/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user, password: pass })
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        setAdminToken(data.access_token);
        onLoginSuccess(data.access_token);
        window.dispatchEvent(new Event("storage"));
      } else {
        setErr(data.detail || "Identifiants invalides");
      }
    } catch (e) {
      setErr("Erreur réseau de communication avec l'API admin");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-box" onSubmit={submit}>
        <div className="login-logo">Fantasy <span>⚡</span> Admin</div>
        <div>
          <label>Pseudo</label>
          <input className="inp" type="text" placeholder="admin" value={user} onChange={e => setUser(e.target.value)} required />
        </div>
        <div>
          <label>Mot de passe</label>
          <input className="inp" type="password" placeholder="••••••" value={pass} onChange={e => setPass(e.target.value)} required />
        </div>
        {err && <p className="err-msg">⚠ {err}</p>}
        <button className="btn-primary" type="submit" disabled={busy}>
          {busy
            ? <><span className="spinner" style={{ borderTopColor: "#fff" }} /> Connexion...</>
            : "Se connecter"
          }
        </button>
        <p className="hint">admin / admin00</p>
      </form>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
//  EXPORT COMPOSANT PRINCIPAL
// ════════════════════════════════════════════════════════════════════════════

export default function AdminPanel() {
  const [token, setToken] = useState(() => getAdminToken());
  const [tab, setTab] = useState("squads");

  const handleLogout = () => {
    setAdminToken(null); setToken("");
    window.dispatchEvent(new Event("storage"));
  };

  if (!token) {
    return <AdminLogin onLoginSuccess={t => setToken(t)} />;
  }

  return (
    <div className="admin-layout">
      <aside className="admin-aside">
        <div className="admin-brand">Boulzazen <span>⚡</span> Admin</div>
        <nav className="admin-nav">
          <button className={`nav-item ${tab === "squads" ? "active" : ""}`} onClick={() => setTab("squads")}>🏃‍♂️ Effectifs & Scraping</button>
          <button className={`nav-item ${tab === "users" ? "active" : ""}`} onClick={() => setTab("users")}>👥 Gestion Utilisateurs</button>
          <button className={`nav-item ${tab === "matches" ? "active" : ""}`} onClick={() => setTab("matches")}>📅 Calendrier Matches</button>
          <button className={`nav-item ${tab === "rules" ? "active" : ""}`} onClick={() => setTab("rules")}>📜 Barème de Points</button>
          <button className={`nav-item ${tab === "tools" ? "active" : ""}`} onClick={() => setTab("tools")}>⚙️ Serveur & Audits</button>
        </nav>
        <div style={{ padding: "0 15px", marginTop: "auto" }}>
          <button className="btn-logout" onClick={handleLogout}>🚪 Déconnexion</button>
        </div>
      </aside>

      <main className="admin-main">
        <header className="admin-header">
          <h1>
            {tab === "squads"  && "🏃‍♂️ Gestion des Effectifs & Scrapers"}
            {tab === "users"   && "👥 Comptes Utilisateurs & Synchro"}
            {tab === "matches" && "📅 Planification du Calendrier"}
            {tab === "rules"   && "📜 Barème de Points & Règles IA"}
            {tab === "tools"   && "⚙️ Outils Système & Logs d'Audit"}
          </h1>
        </header>

        <section className="admin-body">
          {tab === "squads"  && <SquadsSection />}
          {tab === "users"   && <UsersSection />}
          {tab === "matches" && <MatchesSection />}
          {tab === "rules"   && <RulesSection />}
          {tab === "tools"   && <ToolsSection />}
        </section>
      </main>
    </div>
  );
}