import { useState, useEffect, useCallback, useRef } from 'react';
import { useApp } from '../App';
import { API_BASE, GROQ_API_KEY as DEFAULT_GROQ_KEY } from '../config';

// ═══════════════════════════════════════════════════════════════
//  CONFIG
// ═══════════════════════════════════════════════════════════════

const ALL_COMPLAINTS_KEY = 'boulzazen_complaints_all';
const USER_KEY_PREFIX    = 'boulzazen_complaints_user_';
const GROQ_KEY_STORAGE   = 'boulzazen_groq_api_key';
const GROQ_API_URL       = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_MODEL         = 'llama3-8b-8192';

const STATUS_CFG = {
  pending:    { label: 'En attente',  color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',  icon: '⏳' },
  processing: { label: 'En cours',    color: '#38bdf8', bg: 'rgba(56,189,248,0.12)',  icon: '🔄' },
  approved:   { label: 'Acceptée',    color: '#00e676', bg: 'rgba(0,230,118,0.12)',   icon: '✅' },
  rejected:   { label: 'Rejetée',     color: '#f43f5e', bg: 'rgba(244,63,94,0.12)',   icon: '❌' },
};

const CATEGORIES = {
  score_error:  '⚽ Erreur de score',
  points_calc:  '📊 Calcul des points',
  rule_dispute: '📋 Règle contestée',
  player_stats: '🏃 Stats incorrectes',
  roster_issue: '👥 Problème d\'effectif',
  other:        '❓ Autre',
};

const PRIORITIES = {
  low:    { label: 'Faible',  color: '#64748b' },
  medium: { label: 'Normale', color: '#f59e0b' },
  high:   { label: 'Urgente', color: '#ef4444' },
};

// ═══════════════════════════════════════════════════════════════
//  HELPERS
// ═══════════════════════════════════════════════════════════════

function loadAllComplaints() {
  try {
    return JSON.parse(localStorage.getItem(ALL_COMPLAINTS_KEY) || '[]');
  } catch { return []; }
}

function updateComplaintInStorage(id, patch) {
  try {
    const all = loadAllComplaints().map(c => c.id === id ? { ...c, ...patch } : c);
    localStorage.setItem(ALL_COMPLAINTS_KEY, JSON.stringify(all));
  } catch { /* silencieux */ }

  try {
    const owner = loadAllComplaints().find(c => c.id === id)?.user_id;
    if (owner) {
      const userKey = `${USER_KEY_PREFIX}${owner}`;
      const userList = JSON.parse(localStorage.getItem(userKey) || '[]');
      const updated = userList.map(c => c.id === id ? { ...c, ...patch } : c);
      localStorage.setItem(userKey, JSON.stringify(updated));
    }
  } catch { /* silencieux */ }
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
       + ' · ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

// ═══════════════════════════════════════════════════════════════
//  GROQ API
// ═══════════════════════════════════════════════════════════════

async function analyzeComplaintWithGroq(complaint, apiKey) {
  const systemPrompt = `Tu es l'administrateur IA d'une ligue Fantasy Football privée "Boulzazen" pour la Coupe du Monde 2026.
Tu dois analyser des réclamations de joueurs et rendre des verdicts justes et argumentés.

Règles du jeu :
- But marqué : G=+8, D=+6, M=+5, A=+4 pts
- Passe décisive : G=+6, D=+5, M=+4, A=+4 pts
- Clean Sheet : G=+5, D=+4, M=+1, A=0 pts
- Match complet (≥90min) : +2 pts / Entrée/sortie avant 90min : +1 pt
- Parades : +3 pts par tranche de 3 (gardien seulement)
- Récupérations : +3 pts par tranche de 5 (G, D, M — pas A)
- Carton jaune : -1 pt / Carton rouge : -2 pts
- Entraîneur présent : +1 pt / Victoire : +2 pts / +3 pts par 2 buts d'écart
- Max 3 joueurs de même nationalité, entraîneur sans nationalité en commun

Réponds en JSON strict :
{
  "verdict": "approved" | "rejected" | "needs_investigation",
  "confidence": 0-100,
  "summary": "Résumé en 1-2 phrases",
  "reasoning": "Analyse détaillée (3-5 phrases)",
  "action": "Action recommandée si accepté (ex: recalculer les points du joueur X)",
  "points_impact": "Estimation de l'impact sur les points (+X ou -X ou 'neutre')"
}`;

  const userPrompt = `Analyse cette réclamation :

ID: ${complaint.id}
Catégorie: ${CATEGORIES[complaint.category] || complaint.category}
Priorité: ${PRIORITIES[complaint.priority]?.label || complaint.priority}
Titre: ${complaint.title}
Description: ${complaint.description}
Match concerné: ${complaint.match_ref || 'Non précisé'}
Joueur concerné: ${complaint.player_ref || 'Non précisé'}
Soumis par: ${complaint.username}
Date: ${formatDate(complaint.created_at)}

Rends un verdict juste et équilibré.`;

  const res = await fetch(GROQ_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: GROQ_MODEL,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user',   content: userPrompt   },
      ],
      max_tokens: 500,
      temperature: 0.3,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.error?.message || `Groq API ${res.status}`);
  }

  const data = await res.json();
  const content = data.choices?.[0]?.message?.content || '';

  const match = content.match(/\{[\s\S]*\}/);
  if (!match) throw new Error('Réponse Groq invalide (pas de JSON)');
  return JSON.parse(match[0]);
}

// ═══════════════════════════════════════════════════════════════
//  COMPOSANTS
// ═══════════════════════════════════════════════════════════════

function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.pending;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      background: cfg.bg, color: cfg.color,
      border: `1px solid ${cfg.color}40`,
      borderRadius: 50, padding: '2px 8px',
      fontSize: '0.68rem', fontWeight: 700,
      whiteSpace: 'nowrap',
    }}>
      {cfg.icon} {cfg.label}
    </span>
  );
}

function Spinner({ size = 16, color = 'var(--accent)' }) {
  return (
    <span style={{
      display: 'inline-block', width: size, height: size,
      border: `2px solid ${color}30`,
      borderTopColor: color, borderRadius: '50%',
      animation: 'spin 0.7s linear infinite', flexShrink: 0,
    }} />
  );
}

// ─── Carte Analyse IA ─────────────────────────────────────────
function AIAnalysis({ analysis, onApply }) {
  if (!analysis) return null;

  const vcfg = {
    approved:           { color: '#00e676', bg: 'rgba(0,230,118,0.08)',  icon: '✅', label: 'VALIDER' },
    rejected:           { color: '#f43f5e', bg: 'rgba(244,63,94,0.08)', icon: '❌', label: 'REJETER' },
    needs_investigation:{ color: '#f59e0b', bg: 'rgba(245,158,11,0.08)',icon: '🔍', label: 'INVESTIGUER' },
  }[analysis.verdict] || { color: '#64748b', bg: 'transparent', icon: '❓', label: '?' };

  const confColor = analysis.confidence >= 80 ? '#00e676' : analysis.confidence >= 50 ? '#f59e0b' : '#f43f5e';

  return (
    <div style={{
      background: vcfg.bg,
      border: `1px solid ${vcfg.color}30`,
      borderRadius: 10, padding: '12px 14px',
      display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            background: vcfg.color, color: '#000',
            borderRadius: 6, padding: '2px 8px',
            fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.05em',
          }}>
            IA · {vcfg.icon} {vcfg.label}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>Confiance :</span>
          <span style={{ fontSize: '0.82rem', fontWeight: 800, color: confColor }}>
            {analysis.confidence}%
          </span>
        </div>
      </div>

      <div>
        <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 4 }}>
          Verdict IA
        </div>
        <p style={{ fontSize: '0.82rem', color: 'var(--text)', margin: 0, lineHeight: 1.6 }}>
          {analysis.summary}
        </p>
      </div>

      <div>
        <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 4 }}>
          Analyse
        </div>
        <p style={{ fontSize: '0.78rem', color: 'var(--text-2)', margin: 0, lineHeight: 1.6 }}>
          {analysis.reasoning}
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {analysis.action && (
          <div style={{
            flex: 1, background: 'rgba(255,255,255,0.04)', borderRadius: 6,
            padding: '6px 10px',
          }}>
            <div style={{ fontSize: '0.63rem', color: 'var(--text-3)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              Action
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-2)', marginTop: 2 }}>
              {analysis.action}
            </div>
          </div>
        )}
        {analysis.points_impact && (
          <div style={{
            background: 'rgba(255,255,255,0.04)', borderRadius: 6,
            padding: '6px 10px', minWidth: 80, textAlign: 'center',
          }}>
            <div style={{ fontSize: '0.63rem', color: 'var(--text-3)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              Impact pts
            </div>
            <div style={{ fontSize: '0.88rem', fontWeight: 800, color: vcfg.color, marginTop: 2 }}>
              {analysis.points_impact}
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 6 }}>
        <button type="button" onClick={() => onApply('approved', analysis)}
          style={actionBtn('#00e676')}>
          ✅ Accepter
        </button>
        <button type="button" onClick={() => onApply('rejected', analysis)}
          style={actionBtn('#f43f5e')}>
          ❌ Rejeter
        </button>
      </div>
    </div>
  );
}

const actionBtn = (color) => ({
  flex: 1, padding: '9px 0',
  background: `${color}18`,
  border: `1px solid ${color}50`,
  borderRadius: 7, cursor: 'pointer',
  color: color, fontWeight: 700, fontSize: '0.8rem',
  transition: 'all 0.15s',
});

// ─── Carte Plainte Admin ──────────────────────────────────────
function AdminComplaintCard({ complaint, groqKey, onUpdate }) {
  const [expanded,   setExpanded]   = useState(false);
  const [analyzing,  setAnalyzing]  = useState(false);
  const [analysis,   setAnalysis]   = useState(null);
  const [aiError,    setAiError]    = useState(null);
  const [adminNote,  setAdminNote]  = useState(complaint.admin_response || '');
  const [saving,     setSaving]     = useState(false);

  const handleAnalyze = async () => {
    if (!groqKey) { setAiError('Clé API Groq requise'); return; }
    setAnalyzing(true);
    setAiError(null);
    try {
      const result = await analyzeComplaintWithGroq(complaint, groqKey);
      setAnalysis(result);
    } catch (err) {
      setAiError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleApply = (status, aiResult) => {
    const response = aiResult
      ? `[IA Groq · ${aiResult.confidence}% confiance]\n\n${aiResult.reasoning}\n\nAction : ${aiResult.action || 'Aucune action requise'}`
      : adminNote;

    const patch = {
      status,
      admin_response: response || adminNote || 'Traité par l\'administrateur.',
      resolved_at: new Date().toISOString(),
    };

    updateComplaintInStorage(complaint.id, patch);
    onUpdate(complaint.id, patch);
    setExpanded(false);
  };

  const handleManualSave = (status) => {
    setSaving(true);
    const patch = {
      status,
      admin_response: adminNote || `Statut modifié : ${STATUS_CFG[status]?.label}`,
      resolved_at: new Date().toISOString(),
    };
    updateComplaintInStorage(complaint.id, patch);
    setTimeout(() => {
      onUpdate(complaint.id, patch);
      setSaving(false);
      setExpanded(false);
    }, 400);
  };

  const priorityCfg = PRIORITIES[complaint.priority] || PRIORITIES.medium;

  return (
    <div style={{
      background: 'var(--surface)',
      border: `1px solid ${expanded ? 'var(--border-light)' : 'var(--border)'}`,
      borderRadius: 12, overflow: 'hidden',
      transition: 'border-color 0.2s',
    }}>
      <button type="button" onClick={() => setExpanded(o => !o)}
        style={{
          width: '100%', background: 'none', border: 'none',
          padding: '11px 12px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 9,
          textAlign: 'left',
        }}>

        <span style={{
          display: 'inline-block', width: 8, height: 8,
          borderRadius: '50%', background: priorityCfg.color,
          flexShrink: 0,
        }} />

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: '0.82rem', fontWeight: 700, color: 'var(--text)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{ flexShrink: 0, fontSize: '0.78rem', color: 'var(--text-3)' }}>
              #{complaint.id}
            </span>
            {complaint.title}
          </div>
          <div style={{
            fontSize: '0.68rem', color: 'var(--text-3)', marginTop: 3,
            display: 'flex', gap: 8, alignItems: 'center',
          }}>
            <span>👤 {complaint.username}</span>
            <span>·</span>
            <span>{formatDate(complaint.created_at)}</span>
            <span>·</span>
            <span>{CATEGORIES[complaint.category] || '❓'}</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <StatusBadge status={complaint.status} />
          <span style={{ color: 'var(--text-3)', fontSize: '0.7rem' }}>
            {expanded ? '▲' : '▼'}
          </span>
        </div>
      </button>

      {expanded && (
        <div style={{
          padding: '0 12px 12px',
          borderTop: '1px solid var(--border)',
          paddingTop: 12,
          display: 'flex', flexDirection: 'column', gap: 10,
        }}>
          <div style={{
            background: 'var(--surface-2)', borderRadius: 8, padding: '10px 12px',
          }}>
            <div style={sectionLabel}>Description</div>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-2)', margin: 0, lineHeight: 1.6 }}>
              {complaint.description}
            </p>
            {(complaint.match_ref || complaint.player_ref) && (
              <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                {complaint.match_ref  && <Tag color="#38bdf8">🎯 {complaint.match_ref}</Tag>}
                {complaint.player_ref && <Tag color="#a78bfa">👤 {complaint.player_ref}</Tag>}
              </div>
            )}
          </div>

          {complaint.status === 'pending' && (
            <>
              <button type="button" onClick={handleAnalyze}
                disabled={analyzing || !groqKey}
                style={{
                  width: '100%', padding: '10px',
                  background: analyzing ? 'var(--surface-2)' : 'rgba(56,189,248,0.1)',
                  border: `1px solid ${groqKey ? 'rgba(56,189,248,0.4)' : 'var(--border)'}`,
                  borderRadius: 8, cursor: groqKey ? 'pointer' : 'not-allowed',
                  color: groqKey ? 'var(--accent)' : 'var(--text-3)',
                  fontWeight: 700, fontSize: '0.82rem',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  transition: 'all 0.15s',
                }}>
                {analyzing
                  ? <><Spinner size={14} color="var(--accent)" /> Analyse en cours (Groq IA)...</>
                  : !groqKey
                    ? '🔑 Clé Groq requise (voir ⚙️ Paramètres)'
                    : '🤖 Analyser avec Groq IA'}
              </button>

              {aiError && (
                <div style={{
                  background: 'rgba(244,63,94,0.08)',
                  border: '1px solid rgba(244,63,94,0.3)',
                  borderRadius: 7, padding: '8px 12px',
                  fontSize: '0.78rem', color: 'var(--danger)',
                }}>
                  ⚠ Erreur Groq : {aiError}
                </div>
              )}

              {analysis && (
                <AIAnalysis analysis={analysis} onApply={handleApply} />
              )}

              <div>
                <div style={sectionLabel}>Réponse manuelle (optionnel)</div>
                <textarea rows={3}
                  placeholder="Tapez votre réponse manuelle..."
                  value={adminNote}
                  onChange={e => setAdminNote(e.target.value)}
                  style={{
                    width: '100%', padding: '8px 10px',
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    borderRadius: 7, color: 'var(--text)',
                    fontSize: '0.82rem', fontFamily: 'inherit',
                    resize: 'vertical', outline: 'none',
                    boxSizing: 'border-box', minHeight: 70,
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: 6 }}>
                <button type="button"
                  onClick={() => handleManualSave('approved')}
                  disabled={saving}
                  style={manualBtn('#00e676')}>
                  {saving ? <Spinner size={12} color="#00e676" /> : '✅'} Accepter
                </button>
                <button type="button"
                  onClick={() => handleManualSave('rejected')}
                  disabled={saving}
                  style={manualBtn('#f43f5e')}>
                  {saving ? <Spinner size={12} color="#f43f5e" /> : '❌'} Rejeter
                </button>
                <button type="button"
                  onClick={() => handleManualSave('processing')}
                  disabled={saving}
                  style={manualBtn('#38bdf8')}>
                  🔄 En cours
                </button>
              </div>
            </>
          )}

          {complaint.status !== 'pending' && complaint.admin_response && (
            <div style={{
              background: complaint.status === 'approved'
                ? 'rgba(0,230,118,0.07)' : 'rgba(244,63,94,0.07)',
              border: `1px solid ${complaint.status === 'approved' ? 'rgba(0,230,118,0.25)' : 'rgba(244,63,94,0.25)'}`,
              borderRadius: 8, padding: '10px 12px',
            }}>
              <div style={sectionLabel}>Réponse admin</div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-2)', margin: 0, lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                {complaint.admin_response}
              </p>
            </div>
          )}

          {complaint.status !== 'pending' && (
            <button type="button"
              onClick={() => {
                updateComplaintInStorage(complaint.id, { status: 'pending', admin_response: null, resolved_at: null });
                onUpdate(complaint.id, { status: 'pending', admin_response: null, resolved_at: null });
              }}
              style={{
                padding: '6px 12px', background: 'none',
                border: '1px solid var(--border)', borderRadius: 6,
                color: 'var(--text-3)', fontSize: '0.72rem', cursor: 'pointer',
              }}>
              ↩ Remettre en attente
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Stats Panel ──────────────────────────────────────────────
function StatsCard({ label, value, color, icon }) {
  return (
    <div style={{
      background: `${color}10`,
      border: `1px solid ${color}25`,
      borderRadius: 10, padding: '10px 12px',
      display: 'flex', flexDirection: 'column', gap: 3,
    }}>
      <div style={{ fontSize: '1.2rem' }}>{icon}</div>
      <div style={{ fontFamily: 'Rajdhani, sans-serif', fontSize: '1.6rem', fontWeight: 700, color, lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: '0.68rem', color, opacity: 0.8, fontWeight: 700, letterSpacing: '0.06em' }}>
        {label}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  COMPOSANT PRINCIPAL
// ═══════════════════════════════════════════════════════════════

export default function AdminPanel() {
  const { user, session, isAdmin } = useApp();

  const [complaints,    setComplaints]    = useState([]);
  const [loading,       setLoading]       = useState(true);
  const [filterStatus,  setFilterStatus]  = useState('pending');
  const [filterSearch,  setFilterSearch]  = useState('');

  // ── Clé Groq : priorité localStorage, sinon clé par défaut du config ──────
  const [groqKey, setGroqKey] = useState(() => {
    const stored = localStorage.getItem(GROQ_KEY_STORAGE);
    if (stored) return stored;
    // Pré-remplir avec la clé par défaut et la sauvegarder
    if (DEFAULT_GROQ_KEY) {
      localStorage.setItem(GROQ_KEY_STORAGE, DEFAULT_GROQ_KEY);
      return DEFAULT_GROQ_KEY;
    }
    return '';
  });

  const [showKeyInput,  setShowKeyInput]  = useState(false);
  const [tempKey,       setTempKey]       = useState('');
  const [keyVisible,    setKeyVisible]    = useState(false);
  const [recalcStatus,  setRecalcStatus]  = useState(null);
  const [recalcLoading, setRecalcLoading] = useState(false);
  const [activeTab,     setActiveTab]     = useState('complaints');

  const loadComplaints = useCallback(() => {
    const all = loadAllComplaints().sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    setComplaints(all);
    setLoading(false);
  }, []);

  useEffect(() => { loadComplaints(); }, [loadComplaints]);

  if (!isAdmin) {
    return (
      <div className="view">
        <div style={{
          background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.3)',
          borderRadius: 12, padding: 24, textAlign: 'center',
        }}>
          <div style={{ fontSize: '3rem', marginBottom: 12 }}>🚫</div>
          <h3 style={{ color: 'var(--danger)', margin: '0 0 8px' }}>Accès refusé</h3>
          <p style={{ color: 'var(--text-2)', fontSize: '0.85rem', margin: 0 }}>
            Cette section est réservée aux administrateurs de la ligue.
          </p>
        </div>
      </div>
    );
  }

  const handleUpdate = (id, patch) => {
    setComplaints(prev => prev.map(c => c.id === id ? { ...c, ...patch } : c));
  };

  const handleSaveGroqKey = () => {
    if (tempKey.trim()) {
      setGroqKey(tempKey.trim());
      localStorage.setItem(GROQ_KEY_STORAGE, tempKey.trim());
    }
    setShowKeyInput(false);
    setTempKey('');
  };

  const handleDeleteGroqKey = () => {
    setGroqKey('');
    localStorage.removeItem(GROQ_KEY_STORAGE);
  };

  const handleRecalculate = async () => {
    setRecalcLoading(true);
    setRecalcStatus(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/recalculate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
        },
      });
      if (!res.ok) throw new Error(`Erreur ${res.status}`);
      const data = await res.json();
      setRecalcStatus({ ok: true, msg: `✅ Recalcul terminé — ${data.users_updated ?? '?'} utilisateurs mis à jour.` });
    } catch (err) {
      setRecalcStatus({ ok: false, msg: `❌ Erreur : ${err.message}` });
    } finally {
      setRecalcLoading(false);
      setTimeout(() => setRecalcStatus(null), 6000);
    }
  };

  const filtered = complaints.filter(c => {
    const matchStatus = filterStatus === 'all' || c.status === filterStatus;
    const q = filterSearch.toLowerCase();
    const matchSearch = !q || c.title.toLowerCase().includes(q) ||
                        c.username.toLowerCase().includes(q) ||
                        c.description.toLowerCase().includes(q);
    return matchStatus && matchSearch;
  });

  const counts = {
    all:        complaints.length,
    pending:    complaints.filter(c => c.status === 'pending').length,
    processing: complaints.filter(c => c.status === 'processing').length,
    approved:   complaints.filter(c => c.status === 'approved').length,
    rejected:   complaints.filter(c => c.status === 'rejected').length,
  };

  return (
    <div className="view" style={{ gap: 10 }}>

      {/* ── HEADER ADMIN ───────────────────────────────────── */}
      <div style={{
        background: 'linear-gradient(135deg, #1a0826 0%, #0d1526 100%)',
        border: '1px solid rgba(167,139,250,0.25)',
        borderRadius: 14, padding: '14px',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -30, right: -20,
          width: 120, height: 120,
          background: 'radial-gradient(circle, rgba(167,139,250,0.2) 0%, transparent 70%)',
          borderRadius: '50%', pointerEvents: 'none',
        }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: 'rgba(167,139,250,0.15)', border: '1px solid rgba(167,139,250,0.3)',
              borderRadius: 50, padding: '3px 10px', marginBottom: 8,
              fontSize: '0.68rem', fontWeight: 700, color: '#c4b5fd', letterSpacing: '0.06em',
            }}>
              🛡️ PANNEAU ADMINISTRATEUR
            </div>

            {/* Badge clé Groq active */}
            {groqKey && (
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 5,
                background: 'rgba(0,230,118,0.1)', border: '1px solid rgba(0,230,118,0.3)',
                borderRadius: 50, padding: '2px 10px', marginBottom: 8, marginLeft: 6,
                fontSize: '0.65rem', fontWeight: 700, color: 'var(--green)',
              }}>
                🤖 Groq IA · Actif
              </div>
            )}

            <h2 style={{ margin: 0, fontSize: '1.2rem', letterSpacing: '0.08em', lineHeight: 1.2 }}>
              Admin · Ligue Boulzazen
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '0.72rem', color: 'var(--text-2)' }}>
              {user?.username} · WC 2026
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Plaintes
            </div>
            <div style={{ fontFamily: 'Rajdhani, sans-serif', fontSize: '2rem', fontWeight: 700, color: '#a78bfa', lineHeight: 1 }}>
              {counts.all}
            </div>
            {counts.pending > 0 && (
              <div style={{ fontSize: '0.68rem', color: '#f59e0b', fontWeight: 700 }}>
                {counts.pending} en attente
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── ONGLETS ────────────────────────────────────────── */}
      <div style={{
        display: 'flex', gap: 4,
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 50, padding: 3,
      }}>
        {[
          { key: 'complaints', label: `🚩 Plaintes${counts.pending > 0 ? ` (${counts.pending})` : ''}` },
          { key: 'stats',      label: '📊 Statistiques' },
          { key: 'settings',   label: '⚙️ Paramètres' },
        ].map(tab => (
          <button key={tab.key} type="button"
            onClick={() => setActiveTab(tab.key)}
            style={{
              flex: 1, background: activeTab === tab.key ? 'var(--surface-3)' : 'none',
              border: activeTab === tab.key ? '1px solid var(--border-light)' : '1px solid transparent',
              borderRadius: 50, padding: '7px 6px',
              color: activeTab === tab.key ? 'var(--text)' : 'var(--text-3)',
              fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
              transition: 'all 0.15s', whiteSpace: 'nowrap',
            }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ════════════════════════════════════════════════════
          TAB : PLAINTES
          ════════════════════════════════════════════════ */}
      {activeTab === 'complaints' && (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <input type="text"
              placeholder="🔍 Rechercher par titre, joueur, description..."
              value={filterSearch}
              onChange={e => setFilterSearch(e.target.value)}
              style={{
                width: '100%', padding: '9px 12px',
                background: 'var(--surface-2)', border: '1px solid var(--border)',
                borderRadius: 8, color: 'var(--text)', fontSize: '0.82rem',
                fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box',
              }}
            />
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              {[
                { key: 'all',        label: `Toutes (${counts.all})` },
                { key: 'pending',    label: `⏳ Attente (${counts.pending})` },
                { key: 'processing', label: `🔄 En cours (${counts.processing})` },
                { key: 'approved',   label: `✅ Acceptées (${counts.approved})` },
                { key: 'rejected',   label: `❌ Rejetées (${counts.rejected})` },
              ].map(f => (
                <button key={f.key} type="button"
                  onClick={() => setFilterStatus(f.key)}
                  className={`filter-btn ${filterStatus === f.key ? 'active' : ''}`}
                  style={{ fontSize: '0.7rem', padding: '4px 10px' }}>
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="loading-spinner">Chargement des plaintes...</div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                {filterStatus === 'pending' ? '🎉' : '🔍'}
              </div>
              <h4>{filterStatus === 'pending' ? 'Aucune plainte en attente' : 'Aucun résultat'}</h4>
              <p>{filterStatus === 'pending'
                ? 'Toutes les réclamations ont été traitées !'
                : 'Essayez un autre filtre ou terme de recherche.'}</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {filtered.map(c => (
                <AdminComplaintCard
                  key={c.id}
                  complaint={c}
                  groqKey={groqKey}
                  onUpdate={handleUpdate}
                />
              ))}
            </div>
          )}

          <div style={{ paddingTop: 4 }}>
            {recalcStatus && (
              <div style={{
                background: recalcStatus.ok ? 'rgba(0,230,118,0.08)' : 'rgba(244,63,94,0.08)',
                border: `1px solid ${recalcStatus.ok ? 'rgba(0,230,118,0.3)' : 'rgba(244,63,94,0.3)'}`,
                borderRadius: 8, padding: '8px 12px', marginBottom: 8,
                fontSize: '0.8rem', color: recalcStatus.ok ? 'var(--green)' : 'var(--danger)',
              }}>
                {recalcStatus.msg}
              </div>
            )}
            <button type="button" onClick={handleRecalculate} disabled={recalcLoading}
              style={{
                width: '100%', padding: '12px',
                background: recalcLoading ? 'var(--surface-2)' : 'rgba(56,189,248,0.1)',
                border: '1px solid rgba(56,189,248,0.3)',
                borderRadius: 10, cursor: recalcLoading ? 'not-allowed' : 'pointer',
                color: recalcLoading ? 'var(--text-3)' : 'var(--accent)',
                fontWeight: 700, fontSize: '0.88rem',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                transition: 'all 0.15s',
              }}>
              {recalcLoading ? <><Spinner size={14} color="var(--accent)" /> Recalcul en cours...</>
                : '🔁 Recalculer tous les points (backend)'}
            </button>
          </div>
        </>
      )}

      {/* ════════════════════════════════════════════════════
          TAB : STATISTIQUES
          ════════════════════════════════════════════════ */}
      {activeTab === 'stats' && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <StatsCard label="TOTAL" value={counts.all}          color="#a78bfa" icon="🚩" />
            <StatsCard label="ATTENTE" value={counts.pending}    color="#f59e0b" icon="⏳" />
            <StatsCard label="ACCEPTÉES" value={counts.approved} color="#00e676" icon="✅" />
            <StatsCard label="REJETÉES" value={counts.rejected}  color="#f43f5e" icon="❌" />
          </div>

          {counts.all > 0 && (
            <div style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 12, padding: 14,
            }}>
              <div style={sectionLabel}>Taux de résolution</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                {[
                  { label: 'Acceptées', value: counts.approved, color: '#00e676' },
                  { label: 'Rejetées',  value: counts.rejected, color: '#f43f5e' },
                  { label: 'En cours',  value: counts.processing + counts.pending, color: '#f59e0b' },
                ].map(({ label, value, color }) => (
                  <div key={label}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', marginBottom: 3 }}>
                      <span style={{ color: 'var(--text-2)' }}>{label}</span>
                      <span style={{ color, fontWeight: 700 }}>
                        {value} ({Math.round((value / counts.all) * 100)}%)
                      </span>
                    </div>
                    <div style={{ height: 6, background: 'var(--surface-2)', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${Math.round((value / counts.all) * 100)}%`,
                        background: color, borderRadius: 3,
                        transition: 'width 0.5s ease',
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 12, padding: 14,
          }}>
            <div style={sectionLabel}>Par catégorie</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 8 }}>
              {Object.entries(CATEGORIES).map(([key, label]) => {
                const n = complaints.filter(c => c.category === key).length;
                if (!n) return null;
                return (
                  <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--text-2)' }}>{label}</span>
                    <span style={{ color: 'var(--text)', fontWeight: 700 }}>{n}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* ════════════════════════════════════════════════════
          TAB : PARAMÈTRES
          ════════════════════════════════════════════════ */}
      {activeTab === 'settings' && (
        <>
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 12, padding: 14,
            display: 'flex', flexDirection: 'column', gap: 12,
          }}>
            <div>
              <h3 style={{ margin: '0 0 4px', fontFamily: 'Rajdhani, sans-serif', fontSize: '1rem', letterSpacing: '0.07em' }}>
                🤖 Groq IA — Clé API
              </h3>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-2)', lineHeight: 1.5 }}>
                Modèle actif :{' '}
                <code style={{ background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 4, fontSize: '0.75rem' }}>
                  {GROQ_MODEL}
                </code>
              </p>
            </div>

            {groqKey ? (
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
                  Clé active ✅
                </div>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'rgba(0,230,118,0.07)',
                  border: '1px solid rgba(0,230,118,0.25)',
                  borderRadius: 8, padding: '8px 12px',
                }}>
                  <span style={{ flex: 1, fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--green)', letterSpacing: '0.05em' }}>
                    {keyVisible ? groqKey : groqKey.slice(0, 8) + '••••••••' + groqKey.slice(-4)}
                  </span>
                  <button type="button"
                    onClick={() => setKeyVisible(v => !v)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', fontSize: '0.8rem' }}>
                    {keyVisible ? '🙈' : '👁️'}
                  </button>
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                  <button type="button" onClick={() => { setTempKey(groqKey); setShowKeyInput(true); }}
                    style={settingsBtn('var(--accent)')}>
                    ✏️ Modifier
                  </button>
                  <button type="button" onClick={handleDeleteGroqKey}
                    style={settingsBtn('var(--danger)')}>
                    🗑️ Supprimer
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <div style={{
                  background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
                  borderRadius: 7, padding: '8px 12px', marginBottom: 10,
                  fontSize: '0.75rem', color: '#f59e0b',
                }}>
                  ⚠ Aucune clé API Groq configurée.
                </div>
                {!showKeyInput && (
                  <button type="button" onClick={() => setShowKeyInput(true)}
                    style={{
                      width: '100%', padding: '10px',
                      background: 'rgba(56,189,248,0.1)', border: '1px solid rgba(56,189,248,0.3)',
                      borderRadius: 8, cursor: 'pointer',
                      color: 'var(--accent)', fontWeight: 700, fontSize: '0.85rem',
                    }}>
                    🔑 Configurer la clé Groq API
                  </button>
                )}
              </div>
            )}

            {showKeyInput && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                  Nouvelle clé
                </div>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <input
                    type={keyVisible ? 'text' : 'password'}
                    placeholder="gsk_..."
                    value={tempKey}
                    onChange={e => setTempKey(e.target.value)}
                    style={{
                      width: '100%', padding: '10px 40px 10px 12px',
                      background: 'var(--surface-2)', border: '1px solid var(--accent)',
                      borderRadius: 8, color: 'var(--text)',
                      fontFamily: 'monospace', fontSize: '0.82rem',
                      outline: 'none', boxSizing: 'border-box',
                    }}
                  />
                  <button type="button" onClick={() => setKeyVisible(v => !v)}
                    style={{
                      position: 'absolute', right: 10,
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: 'var(--text-3)', fontSize: '0.9rem',
                    }}>
                    {keyVisible ? '🙈' : '👁️'}
                  </button>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button type="button" onClick={() => { setShowKeyInput(false); setTempKey(''); }}
                    style={settingsBtn('var(--text-3)')}>
                    Annuler
                  </button>
                  <button type="button" onClick={handleSaveGroqKey} disabled={!tempKey.trim()}
                    style={settingsBtn('var(--green)')}>
                    💾 Enregistrer
                  </button>
                </div>
              </div>
            )}
          </div>

          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 12, padding: 14,
            display: 'flex', flexDirection: 'column', gap: 10,
          }}>
            <h3 style={{ margin: 0, fontFamily: 'Rajdhani, sans-serif', fontSize: '1rem', letterSpacing: '0.07em' }}>
              🗑️ Gestion des données
            </h3>
            <button type="button"
              onClick={() => {
                if (!window.confirm('Supprimer TOUTES les plaintes ? Cette action est irréversible.')) return;
                localStorage.removeItem(ALL_COMPLAINTS_KEY);
                setComplaints([]);
              }}
              style={{
                padding: '10px', background: 'rgba(244,63,94,0.08)',
                border: '1px solid rgba(244,63,94,0.3)', borderRadius: 8,
                cursor: 'pointer', color: 'var(--danger)',
                fontWeight: 700, fontSize: '0.82rem',
              }}>
              ⚠️ Vider toutes les plaintes
            </button>
            <button type="button" onClick={loadComplaints}
              style={{
                padding: '10px', background: 'rgba(56,189,248,0.08)',
                border: '1px solid rgba(56,189,248,0.25)', borderRadius: 8,
                cursor: 'pointer', color: 'var(--accent)',
                fontWeight: 700, fontSize: '0.82rem',
              }}>
              🔄 Recharger les plaintes
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  STYLES
// ═══════════════════════════════════════════════════════════════

const sectionLabel = {
  fontSize: '0.68rem', fontWeight: 700,
  letterSpacing: '0.07em', textTransform: 'uppercase',
  color: 'var(--text-3)',
};

const manualBtn = (color) => ({
  flex: 1, padding: '8px 0',
  background: `${color}15`, border: `1px solid ${color}40`,
  borderRadius: 7, cursor: 'pointer',
  color: color, fontWeight: 700, fontSize: '0.76rem',
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
  transition: 'all 0.15s',
});

const settingsBtn = (color) => ({
  flex: 1, padding: '8px 0',
  background: `${color}15`, border: `1px solid ${color}35`,
  borderRadius: 7, cursor: 'pointer',
  color: color, fontWeight: 700, fontSize: '0.78rem',
  transition: 'all 0.15s',
});

function Tag({ color, children }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      background: `${color}15`, border: `1px solid ${color}35`,
      borderRadius: 50, padding: '2px 9px',
      fontSize: '0.7rem', fontWeight: 600, color: color,
      whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  );
}
