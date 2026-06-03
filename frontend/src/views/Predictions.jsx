import { useEffect, useMemo, useState } from "react";
import { useApp } from "../App";
import { ANNEXES, KNOCKOUT_ROUNDS, WC2026_GROUPS, buildFallbackMatches } from "../worldCup2026";

const GROUPS = WC2026_GROUPS;

const emptyAnnexes = ANNEXES.reduce((acc, [key]) => {
  acc[key] = ["", "", ""];
  return acc;
}, {});

export default function Predictions() {
  const { user, session, apiFetch } = useApp();
  const [activeTab, setActiveTab] = useState("scores");
  const [matches, setMatches] = useState([]);
  const [scorePredictions, setScorePredictions] = useState({});
  const [groupRanks, setGroupRanks] = useState(() =>
    Object.fromEntries(Object.entries(GROUPS).map(([group, teams]) => [group, teams]))
  );
  const [knockout, setKnockout] = useState({});
  const [annexes, setAnnexes] = useState(emptyAnnexes);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const authHeaders = useMemo(() => ({
    "Content-Type": "application/json",
    ...((session?.access_token || localStorage.getItem("auth_token"))
      ? { Authorization: `Bearer ${session?.access_token || localStorage.getItem("auth_token")}` }
      : {}),
  }), [session?.access_token]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const res = await apiFetch("/matches");
        const data = await res.json();
        const list = Array.isArray(data) ? data : (data.data || []);
        if (!cancelled) setMatches(list.length >= 72 ? list : buildFallbackMatches());
      } catch {
        if (!cancelled) setMatches(buildFallbackMatches());
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [apiFetch]);

  const userId = user?.id || session?.user?.email || "";
  const completedScoreCount = Object.values(scorePredictions)
    .filter((p) => p.home !== "" && p.away !== "").length;

  const updateScore = (matchId, side, value) => {
    const normalized = value === "" ? "" : Math.max(0, Number(value));
    setScorePredictions((prev) => ({
      ...prev,
      [matchId]: { home: "", away: "", ...(prev[matchId] || {}), [side]: normalized },
    }));
  };

  const saveScore = async (match) => {
    const prediction = scorePredictions[match.id];
    if (!userId || !prediction || prediction.home === "" || prediction.away === "") {
      setStatus({ type: "error", text: "Complète le score avant de sauvegarder." });
      return;
    }

    setStatus({ type: "info", text: "Sauvegarde du score..." });
    if (!authHeaders.Authorization) {
      localStorage.setItem("guest_score_predictions", JSON.stringify(scorePredictions));
      setStatus({ type: "success", text: "Score garde en local pour le mode invite." });
      return;
    }
    try {
      const res = await apiFetch("/predictions/score", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          user_id: userId,
          match_id: match.id,
          predicted_home: Number(prediction.home),
          predicted_away: Number(prediction.away),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Sauvegarde refusee.");
      }
      setStatus({ type: "success", text: "Score sauvegardé." });
    } catch {
      setStatus({ type: "error", text: "Impossible de sauvegarder ce score." });
    }
  };

  const moveGroupTeam = (group, index, delta) => {
    setGroupRanks((prev) => {
      const next = [...prev[group]];
      const target = index + delta;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return { ...prev, [group]: next };
    });
  };

  const updateKnockout = (round, index, field, value) => {
    setKnockout((prev) => ({
      ...prev,
      [round]: {
        ...(prev[round] || {}),
        [index]: { ...((prev[round] || {})[index] || {}), [field]: value },
      },
    }));
  };

  const saveBracket = async () => {
    if (!userId) return;
    setStatus({ type: "info", text: "Sauvegarde du tableau..." });
    if (!authHeaders.Authorization) {
      localStorage.setItem("guest_bracket_prediction", JSON.stringify({ groups: groupRanks, knockout }));
      setStatus({ type: "success", text: "Tableau garde en local pour le mode invite." });
      return;
    }
    try {
      const res = await apiFetch("/predictions/bracket", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ user_id: userId, bracket_data: { groups: groupRanks, knockout } }),
      });
      if (!res.ok) throw new Error("Sauvegarde refusee.");
      setStatus({ type: "success", text: "Tableau sauvegardé." });
    } catch {
      setStatus({ type: "error", text: "Impossible de sauvegarder le tableau." });
    }
  };

  const saveAnnexes = async () => {
    if (!userId) return;
    setStatus({ type: "info", text: "Sauvegarde des annexes..." });
    if (!authHeaders.Authorization) {
      localStorage.setItem("guest_annexes_prediction", JSON.stringify(annexes));
      setStatus({ type: "success", text: "Annexes gardees en local pour le mode invite." });
      return;
    }
    try {
      const res = await apiFetch("/predictions/annexes", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ user_id: userId, annexes }),
      });
      if (!res.ok) throw new Error("Sauvegarde refusee.");
      setStatus({ type: "success", text: "Annexes sauvegardées." });
    } catch {
      setStatus({ type: "error", text: "Impossible de sauvegarder les annexes." });
    }
  };

  const matchesByGroup = matches.reduce((acc, match) => {
    const key = match.group || "Matchs";
    acc[key] = [...(acc[key] || []), match];
    return acc;
  }, {});

  return (
    <div className="view predictions-view">
      <div className="pred-header">
        <div>
          <h2>Pronostics</h2>
          <p className="pred-subtitle">Scores, tableau et bonus</p>
        </div>
        <div className="pred-progress-pill">
          <span className="pp-val">{completedScoreCount}</span>
          <span className="pp-sep">/</span>
          <span className="pp-total">{matches.length}</span>
          <span className="pp-label">scores</span>
        </div>
      </div>

      <div className="pred-tabs">
        {[
          ["scores", "Scores"],
          ["bracket", "Tableau"],
          ["annexes", "Annexes"],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`pred-tab-btn ${activeTab === key ? "active" : ""}`}
            onClick={() => setActiveTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {status && <div className={`pred-status ${status.type}`}>{status.text}</div>}

      {activeTab === "scores" && (
        <section className="card tab-content">
          {loading && <p className="muted">Chargement des matchs...</p>}
          {!loading && matches.length === 0 && <p className="muted">Aucun match disponible.</p>}
          {Object.entries(matchesByGroup).map(([group, groupMatches]) => (
            <div className="matches-group" key={group}>
              <div className="matches-group-title">{group}</div>
              {groupMatches.map((match) => {
                const pred = scorePredictions[match.id] || { home: "", away: "" };
                return (
                  <div className={`match-row-card ${match.is_locked ? "locked" : ""}`} key={match.id}>
                    <div className="mrg-meta">
                      <span className="mrg-date">{match.date}</span>
                      {match.is_locked && <span className="mrg-lock">Verrouillé</span>}
                    </div>
                    <div className="mrg-main">
                      <span className="team-side home">{match.home}</span>
                      <div className="score-inputs-block">
                        <input
                          className="score-input-field"
                          inputMode="numeric"
                          type="number"
                          min="0"
                          value={pred.home}
                          disabled={match.is_locked}
                          onChange={(event) => updateScore(match.id, "home", event.target.value)}
                        />
                        <span className="score-divider">-</span>
                        <input
                          className="score-input-field"
                          inputMode="numeric"
                          type="number"
                          min="0"
                          value={pred.away}
                          disabled={match.is_locked}
                          onChange={(event) => updateScore(match.id, "away", event.target.value)}
                        />
                      </div>
                      <span className="team-side away">{match.away}</span>
                    </div>
                    <div className="mrg-footer">
                      <span className="mrg-prev-prono">Exact +5, vainqueur/nul +2</span>
                      <button className="mrg-save-btn" type="button" onClick={() => saveScore(match)}>
                        Sauver
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </section>
      )}

      {activeTab === "bracket" && (
        <section className="tab-content">
          <div className="bracket-section-title">
            <span>Phase de groupes</span>
            <span className="bst-pts">+5 par rang exact</span>
          </div>
          <div className="groups-grid">
            {Object.entries(groupRanks).map(([group, teams]) => (
              <div className="group-accordion open" key={group}>
                <div className="ga-header">
                  <span className="ga-title">{group}</span>
                  <div className="ga-preview">
                    {teams.slice(0, 4).map((team) => <span className="ga-team-chip" key={team}>{team}</span>)}
                  </div>
                </div>
                <div className="ga-body">
                  {teams.map((team, index) => (
                    <div className="ga-row" key={team}>
                      <span className="ga-pos">{index + 1}</span>
                      <select
                        className="ga-select"
                        value={team}
                        onChange={(event) => {
                          const selected = event.target.value;
                          setGroupRanks((prev) => ({
                            ...prev,
                            [group]: prev[group].map((value, i) => i === index ? selected : value),
                          }));
                        }}
                      >
                        {GROUPS[group].map((option) => <option key={option}>{option}</option>)}
                      </select>
                      <div className="ga-arrows">
                        <button type="button" onClick={() => moveGroupTeam(group, index, -1)}>↑</button>
                        <button type="button" onClick={() => moveGroupTeam(group, index, 1)}>↓</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="bracket-section-title">
            <span>Élimination directe</span>
            <span className="bst-pts">Présence, match, qualifié</span>
          </div>
          <div className="ko-section">
            {KNOCKOUT_ROUNDS.map(([round, label, count]) => (
              <div className="ko-round" key={round}>
                <div className="ko-round-label">{label}</div>
                {Array.from({ length: count }).map((_, index) => {
                  const match = (knockout[round] || {})[index] || {};
                  return (
                    <div className={`ko-match ${round === "final" ? "finale-match" : ""}`} key={`${round}-${index}`}>
                      <input className="ko-input" placeholder="Équipe 1" value={match.home || ""} onChange={(e) => updateKnockout(round, index, "home", e.target.value)} />
                      <span className="ko-vs">vs</span>
                      <input className="ko-input" placeholder="Équipe 2" value={match.away || ""} onChange={(e) => updateKnockout(round, index, "away", e.target.value)} />
                      <input className="ko-select-winner" placeholder="Qualifié" value={match.winner || ""} onChange={(e) => updateKnockout(round, index, "winner", e.target.value)} />
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          <div className="pred-save-bar">
            <button className="auth-submit-btn" type="button" onClick={saveBracket}>Sauvegarder le tableau</button>
          </div>
        </section>
      )}

      {activeTab === "annexes" && (
        <section className="card tab-content">
          {ANNEXES.map(([key, label]) => (
            <div className="annexe-block" key={key}>
              <div className="annexe-title">{label}</div>
              {[0, 1, 2].map((index) => (
                <div className="annexe-row" key={`${key}-${index}`}>
                  <span className="annexe-pos">#{index + 1}</span>
                  <input
                    className="annexe-input"
                    value={annexes[key][index]}
                    placeholder="Nom du joueur"
                    onChange={(event) => {
                      const values = [...annexes[key]];
                      values[index] = event.target.value;
                      setAnnexes((prev) => ({ ...prev, [key]: values }));
                    }}
                  />
                </div>
              ))}
            </div>
          ))}
          <div className="pred-save-bar">
            <button className="auth-submit-btn" type="button" onClick={saveAnnexes}>Sauvegarder les annexes</button>
          </div>
        </section>
      )}
    </div>
  );
}
