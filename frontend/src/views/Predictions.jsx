/* ═══════════════════════════════════════════════════════════════════
   PREDICTIONS — CSS COMPLÉMENTAIRE (à importer dans index.css)
   Tous les blocs de classes utilisés dans Predictions.jsx
   ═══════════════════════════════════════════════════════════════════ */

/* ── HEADER PRÉDICTIONS ───────────────────────────────────────────── */
.pred-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 12px;
}

.pred-header h2 { margin: 0; font-size: 1.3rem; letter-spacing: 0.1em; }

.pred-subtitle {
  font-size: 0.72rem; color: var(--text-3);
  font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; margin-top: 2px;
}

.pred-progress-pill {
  display: flex; align-items: baseline; gap: 2px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 50px; padding: 5px 12px;
  flex-shrink: 0;
}

.pp-val   { font-family: 'Rajdhani', sans-serif; font-size: 1.3rem; font-weight: 700; color: var(--green); }
.pp-sep   { font-size: 0.9rem; color: var(--text-3); margin: 0 1px; }
.pp-total { font-size: 1rem; font-weight: 700; color: var(--text-2); }
.pp-label { font-size: 0.65rem; color: var(--text-3); font-weight: 600; margin-left: 3px; letter-spacing: 0.06em; }

/* ── ONGLETS ──────────────────────────────────────────────────────── */
.pred-tabs {
  display: flex; gap: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 50px; padding: 3px;
}

.pred-tab-btn {
  flex: 1; background: none; border: none;
  color: var(--text-2); padding: 8px 10px;
  font-size: 0.78rem; font-weight: 700;
  border-radius: 50px; transition: all 0.15s;
  white-space: nowrap; cursor: pointer;
  letter-spacing: 0.02em;
}

.pred-tab-btn.active {
  background: var(--surface-3);
  color: var(--text);
  border: 1px solid var(--border-light);
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}

/* ── TAB CONTENT ─────────────────────────────────────────────────── */
.tab-content { display: flex; flex-direction: column; gap: 10px; }

/* ── MATCH ROW CARD (onglet Scores) ──────────────────────────────── */
.match-row-card {
  padding: 11px 14px;
  border-bottom: 1px solid rgba(30,48,87,0.45);
  display: flex; flex-direction: column; gap: 5px;
}
.match-row-card:last-child { border-bottom: none; }
.match-row-card.locked { opacity: 0.6; }
.match-row-card.finished { background: rgba(255,255,255,0.02); }

.mrg-meta {
  display: flex; align-items: center; gap: 6px;
  font-size: 0.65rem; font-weight: 600;
  letter-spacing: 0.06em; text-transform: uppercase;
  flex-wrap: wrap;
}

.mrg-group { color: var(--accent); }
.mrg-date  { color: var(--text-3); }
.mrg-lock  { color: var(--warning); font-size: 0.6rem; }
.mrg-pts   { margin-left: auto; font-weight: 800; font-size: 0.72rem; }

.mrg-main {
  display: grid; grid-template-columns: 1fr auto 1fr;
  align-items: center; gap: 8px;
}

.team-side {
  font-size: 0.85rem; font-weight: 700;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.team-side.home { text-align: right; }
.team-side.away { text-align: left; }

.score-inputs-block {
  display: flex; align-items: center; gap: 5px;
  justify-content: center;
}

.score-input-field {
  width: 38px; height: 38px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text); font-size: 1rem; font-weight: 800;
  text-align: center; outline: none; padding: 0;
  transition: border-color 0.15s;
  -webkit-appearance: none; -moz-appearance: textfield;
}
.score-input-field:focus { border-color: var(--accent); }
.score-input-field::-webkit-inner-spin-button,
.score-input-field::-webkit-outer-spin-button { -webkit-appearance: none; }
.score-input-field.disabled { opacity: 0.4; cursor: not-allowed; }

.score-divider { font-size: 1.1rem; font-weight: 800; color: var(--text-2); }

.score-result {
  display: flex; align-items: center; gap: 6px;
  font-family: 'Rajdhani', sans-serif;
  font-size: 1.4rem; font-weight: 700; color: var(--green);
}

.mrg-footer {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 6px; margin-top: 2px;
}

.mrg-prev-prono {
  font-size: 0.68rem; color: var(--text-3); font-style: italic;
}

.mrg-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }

.mrg-save-btn {
  background: var(--surface-2);
  border: 1px solid var(--border-light);
  border-radius: 6px; padding: 5px 12px;
  color: var(--text-2); font-size: 0.75rem; font-weight: 700;
  cursor: pointer; transition: all 0.15s;
  white-space: nowrap;
}
.mrg-save-btn:hover:not(:disabled) { border-color: var(--green); color: var(--green); }
.mrg-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── GROUPES DE MATCHS ───────────────────────────────────────────── */
.matches-group { display: flex; flex-direction: column; }

.matches-group-title {
  padding: 8px 14px 5px;
  font-size: 0.65rem; font-weight: 800;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent);
  border-bottom: 1px solid var(--border);
  background: rgba(56,189,248,0.04);
}

/* ── GROUP ACCORDION (onglet Tableau) ────────────────────────────── */
.group-accordion {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: border-color 0.15s;
}
.group-accordion.open { border-color: var(--border-light); }

.ga-header {
  display: flex; align-items: center;
  width: 100%; background: none; border: none;
  padding: 10px 12px; cursor: pointer;
  gap: 8px; text-align: left;
}

.ga-title {
  font-size: 0.88rem; font-weight: 700;
  color: var(--text); min-width: 70px;
  letter-spacing: 0.04em;
}

.ga-preview {
  display: flex; gap: 4px; align-items: center; flex: 1;
  flex-wrap: wrap;
}

.ga-team-chip {
  font-size: 0.65rem; font-weight: 700;
  border: 1px solid var(--border);
  border-radius: 4px; padding: 1px 6px;
  color: var(--text-2); white-space: nowrap;
}

.ga-dots { font-size: 0.7rem; color: var(--text-3); }

.ga-arrow { color: var(--text-3); font-size: 0.65rem; flex-shrink: 0; }

.ga-body { padding: 10px 12px; border-top: 1px solid var(--border); }

.ga-hint {
  font-size: 0.72rem; color: var(--text-3); margin-bottom: 8px;
  font-style: italic;
}

.ga-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 6px;
}

.ga-pos {
  width: 40px; text-align: center;
  font-size: 0.7rem; font-weight: 800;
  border: 1px solid;
  border-radius: 4px; padding: 2px 4px;
  flex-shrink: 0; letter-spacing: 0.04em;
}

.ga-select {
  flex: 1; padding: 7px 8px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 6px; color: var(--text);
  font-size: 0.8rem; outline: none;
  transition: border-color 0.15s;
}
.ga-select:focus { border-color: var(--accent); }

.ga-arrows { display: flex; flex-direction: column; gap: 2px; }
.ga-arrows button {
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 4px; width: 22px; height: 22px;
  font-size: 0.6rem; cursor: pointer; color: var(--text-2);
  display: flex; align-items: center; justify-content: center;
  transition: all 0.1s;
}
.ga-arrows button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.ga-arrows button:disabled { opacity: 0.3; cursor: not-allowed; }

/* ── KNOCKOUT SECTION ────────────────────────────────────────────── */
.ko-section { display: flex; flex-direction: column; gap: 10px; }

.ko-round {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 12px;
  display: flex; flex-direction: column; gap: 6px;
}

.ko-round-label {
  font-size: 0.7rem; font-weight: 800;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--accent); margin-bottom: 4px;
}

.ko-match {
  display: flex; align-items: center; gap: 6px;
  flex-wrap: wrap;
}

.ko-match.finale-match { background: rgba(255,215,0,0.04); padding: 6px; border-radius: 8px; }

.ko-input {
  flex: 1; min-width: 80px;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 6px; padding: 7px 8px;
  color: var(--text); font-size: 0.8rem; outline: none;
  transition: border-color 0.15s;
}
.ko-input:focus { border-color: var(--accent); }
.ko-input::placeholder { color: var(--text-3); font-size: 0.72rem; }

.ko-vs { color: var(--text-3); font-size: 0.75rem; font-weight: 700; flex-shrink: 0; }

.ko-select-winner {
  flex: 1; min-width: 100px;
  background: var(--surface-2); border: 1px solid var(--border-light);
  border-radius: 6px; padding: 7px 8px;
  color: var(--green); font-size: 0.8rem; font-weight: 700;
  outline: none; transition: border-color 0.15s;
}
.ko-select-winner:focus { border-color: var(--green); }

/* ── SECTION TITLE BRACKET ───────────────────────────────────────── */
.bracket-section-title {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 0;
}

.bracket-section-title span:first-child {
  font-family: 'Rajdhani', sans-serif;
  font-size: 1.05rem; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
}

.bst-pts {
  font-size: 0.65rem; font-weight: 700;
  color: var(--accent); letter-spacing: 0.06em;
  text-transform: uppercase;
}

/* ── GROUPS GRID ──────────────────────────────────────────────────── */
.groups-grid {
  display: flex; flex-direction: column; gap: 6px;
}

/* ── ANNEXES ──────────────────────────────────────────────────────── */
.annexe-block {
  display: flex; flex-direction: column; gap: 8px;
  padding: 12px 14px;
}

.annexe-title {
  font-size: 0.88rem; font-weight: 700;
  color: var(--text); margin-bottom: 4px;
  letter-spacing: 0.04em;
}

.annexe-row {
  display: flex; align-items: center; gap: 10px;
}

.annexe-pos {
  width: 28px; text-align: center;
  font-size: 0.78rem; font-weight: 800;
  color: var(--gold); flex-shrink: 0;
}

.annexe-input {
  flex: 1; padding: 8px 10px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 6px; color: var(--text);
  font-size: 0.85rem; outline: none;
  transition: border-color 0.15s;
}
.annexe-input:focus { border-color: var(--accent); }
.annexe-input::placeholder { color: var(--text-3); font-size: 0.75rem; }

/* ── SAVE BAR ─────────────────────────────────────────────────────── */
.pred-save-bar {
  display: flex; align-items: center; gap: 10px;
  padding-top: 4px;
}

.save-chip {
  font-size: 0.78rem; font-weight: 700;
  min-width: 90px; text-align: right;
  flex-shrink: 0;
  transition: color 0.3s ease;
}

/* ── ERREUR ───────────────────────────────────────────────────────── */
.pred-error {
  background: rgba(244,63,94,0.08);
  border: 1px solid rgba(244,63,94,0.25);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  font-size: 0.82rem; color: var(--danger);
  line-height: 1.5;
}

/* ── SYNC INDICATOR (header) ─────────────────────────────────────── */
.sync-indicator {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--sync-color, transparent);
  flex-shrink: 0;
}

.sync-indicator.sync-pulse {
  animation: syncBlink 1s ease-in-out infinite;
}

.sync-indicator.sync-ok {
  box-shadow: 0 0 6px var(--sync-color);
}

.sync-indicator.sync-degraded {
  animation: syncBlink 2s ease-in-out infinite;
}

.sync-indicator.sync-offline { opacity: 0.7; }

@keyframes syncBlink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.3; }
}