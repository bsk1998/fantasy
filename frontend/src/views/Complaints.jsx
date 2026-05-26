import { useState, useEffect, useCallback } from 'react';
import { useApp } from '../App';

// ═══════════════════════════════════════════════════════════════
//  CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const CATEGORIES = [
  { id: 'score_error',  label: 'Erreur de score',     icon: '⚽', desc: 'Résultat de match incorrect' },
  { id: 'points_calc',  label: 'Calcul des points',   icon: '📊', desc: 'Points Fantasy erronés' },
  { id: 'rule_dispute', label: 'Règle contestée',     icon: '📋', desc: 'Application incorrecte d\'une règle' },
  { id: 'player_stats', label: 'Stats incorrectes',   icon: '🏃', desc: 'Statistiques joueur erronées' },
  { id: 'roster_issue', label: 'Problème d\'effectif',icon: '👥', desc: 'Souci avec mon équipe Fantasy' },
  { id: 'other',        label: 'Autre',                icon: '❓', desc: 'Autre type de réclamation' },
];

const PRIORITIES = [
  { id: 'low',    label: 'Faible',  color: '#64748b' },
  { id: 'medium', label: 'Normale', color: '#f59e0b' },
  { id: 'high',   label: 'Urgente', color: '#ef4444' },
];

const STATUS_CFG = {
  pending:    { label: 'En attente',  color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',  icon: '⏳' },
  processing: { label: 'En cours',    color: '#38bdf8', bg: 'rgba(56,189,248,0.12)',  icon: '🔄' },
  approved:   { label: 'Acceptée',    color: '#00e676', bg: 'rgba(0,230,118,0.12)',   icon: '✅' },
  rejected:   { label: 'Rejetée',     color: '#f43f5e', bg: 'rgba(244,63,94,0.12)',   icon: '❌' },
};

const STORAGE_KEY_PREFIX = 'boulzazen_complaints_user_';
const ALL_COMPLAINTS_KEY  = 'boulzazen_complaints_all';

// ═══════════════════════════════════════════════════════════════
//  HELPERS STORAGE
// ═══════════════════════════════════════════════════════════════

function loadUserComplaints(userId) {
  try {
    return JSON.parse(localStorage.getItem(`${STORAGE_KEY_PREFIX}${userId}`) || '[]');
  } catch { return []; }
}

function saveUserComplaint(userId, complaint) {
  // Sauvegarde dans la liste perso
  const userList = loadUserComplaints(userId);
  userList.unshift(complaint);
  localStorage.setItem(`${STORAGE_KEY_PREFIX}${userId}`, JSON.stringify(userList));

  // Sauvegarde dans la liste globale (visible par l'admin)
  try {
    const all = JSON.parse(localStorage.getItem(ALL_COMPLAINTS_KEY) || '[]');
    all.unshift(complaint);
    localStorage.setItem(ALL_COMPLAINTS_KEY, JSON.stringify(all));
  } catch { /* silencieux */ }

  return userList;
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
       + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

// ═══════════════════════════════════════════════════════════════
//  COMPOSANTS INLINE
// ═══════════════════════════════════════════════════════════════

function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.pending;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: cfg.bg, color: cfg.color,
      border: `1px solid ${cfg.color}40`,
      borderRadius: 50, padding: '3px 10px',
      fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.04em',
      whiteSpace: 'nowrap',
    }}>
      {cfg.icon} {cfg.label}
    </span>
  );
}

function PriorityDot({ priority }) {
  const p = PRIORITIES.find(x => x.id === priority) || PRIORITIES[1];
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8,
      borderRadius: '50%', background: p.color,
      boxShadow: `0 0 6px ${p.color}80`, flexShrink: 0,
    }} title={`Priorité : ${p.label}`} />
  );
}

// ═══════════════════════════════════════════════════════════════
//  FORMULAIRE NOUVELLE PLAINTE
// ═══════════════════════════════════════════════════════════════

function NewComplaintForm({ user, onSubmitted, onCancel }) {
  const [form, setForm] = useState({
    category:    '',
    priority:    'medium',
    title:       '',
    description: '',
    match_ref:   '',
    player_ref:  '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [errors,     setErrors]     = useState({});

  const update = (field, val) => {
    setForm(f => ({ ...f, [field]: val }));
    setErrors(e => ({ ...e, [field]: null }));
  };

  const validate = () => {
    const errs = {};
    if (!form.category)              errs.category    = 'Sélectionnez une catégorie';
    if (!form.title.trim())          errs.title       = 'Le titre est obligatoire';
    if (form.title.length > 80)      errs.title       = 'Maximum 80 caractères';
    if (!form.description.trim())    errs.description = 'La description est obligatoire';
    if (form.description.length < 20)errs.description = 'Minimum 20 caractères';
    return errs;
  };

  const handleSubmit = async () => {
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }

    setSubmitting(true);
    await new Promise(r => setTimeout(r, 600)); // simulation légère

    const complaint = {
      id:           `C-${Date.now().toString(36).toUpperCase()}`,
      ...form,
      title:        form.title.trim(),
      description:  form.description.trim(),
      match_ref:    form.match_ref.trim(),
      player_ref:   form.player_ref.trim(),
      user_id:      user?.id || 'anonymous',
      username:     user?.username || 'Anonyme',
      status:       'pending',
      created_at:   new Date().toISOString(),
      admin_response: null,
      resolved_at:  null,
    };

    const updated = saveUserComplaint(user?.id || 'anonymous', complaint);
    setSubmitting(false);
    onSubmitted(updated);
  };

  const selCat = CATEGORIES.find(c => c.id === form.category);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* En-tête formulaire */}
      <div style={{
        background: 'rgba(56,189,248,0.06)',
        border: '1px solid rgba(56,189,248,0.2)',
        borderRadius: 10, padding: '10px 14px',
        fontSize: '0.8rem', color: 'var(--text-2)', lineHeight: 1.5,
      }}>
        📌 Les plaintes sont examinées par l'administrateur. Soyez précis et factuels.
        Les points peuvent être recalculés si la plainte est acceptée.
      </div>

      {/* Catégorie */}
      <div>
        <label style={labelStyle}>Type de réclamation *</label>
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr',
          gap: 6, marginTop: 6,
        }}>
          {CATEGORIES.map(cat => (
            <button key={cat.id} type="button"
              onClick={() => update('category', cat.id)}
              style={{
                background: form.category === cat.id
                  ? 'rgba(0,230,118,0.1)' : 'var(--surface-2)',
                border: `1px solid ${form.category === cat.id ? 'var(--green)' : 'var(--border)'}`,
                borderRadius: 8, padding: '8px 10px',
                cursor: 'pointer', textAlign: 'left',
                transition: 'all 0.15s',
              }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text)' }}>
                {cat.icon} {cat.label}
              </div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginTop: 2 }}>
                {cat.desc}
              </div>
            </button>
          ))}
        </div>
        {errors.category && <FieldError msg={errors.category} />}
      </div>

      {/* Priorité */}
      <div>
        <label style={labelStyle}>Priorité</label>
        <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
          {PRIORITIES.map(p => (
            <button key={p.id} type="button"
              onClick={() => update('priority', p.id)}
              style={{
                flex: 1, padding: '7px 0',
                background: form.priority === p.id ? `${p.color}22` : 'var(--surface-2)',
                border: `1px solid ${form.priority === p.id ? p.color : 'var(--border)'}`,
                borderRadius: 8, cursor: 'pointer',
                color: form.priority === p.id ? p.color : 'var(--text-2)',
                fontSize: '0.78rem', fontWeight: 700,
                transition: 'all 0.15s',
              }}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Titre */}
      <div>
        <label style={labelStyle}>Titre de la réclamation * <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>({form.title.length}/80)</span></label>
        <input
          type="text" maxLength={80}
          placeholder="Ex : Score France-Belgique erroné (Match 5)"
          value={form.title}
          onChange={e => update('title', e.target.value)}
          style={{ ...inputStyle, borderColor: errors.title ? 'var(--danger)' : 'var(--border)' }}
        />
        {errors.title && <FieldError msg={errors.title} />}
      </div>

      {/* Description */}
      <div>
        <label style={labelStyle}>Description détaillée * <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>({form.description.length} car.)</span></label>
        <textarea
          rows={5}
          placeholder="Décrivez précisément le problème constaté, les preuves disponibles et ce que vous attendez comme correction..."
          value={form.description}
          onChange={e => update('description', e.target.value)}
          style={{ ...inputStyle, resize: 'vertical', minHeight: 100, borderColor: errors.description ? 'var(--danger)' : 'var(--border)' }}
        />
        {errors.description && <FieldError msg={errors.description} />}
      </div>

      {/* Références optionnelles */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <label style={labelStyle}>Réf. Match (optionnel)</label>
          <input
            type="text" placeholder="Ex : Match 5 · FRA-BEL"
            value={form.match_ref}
            onChange={e => update('match_ref', e.target.value)}
            style={inputStyle}
          />
        </div>
        <div>
          <label style={labelStyle}>Joueur concerné (optionnel)</label>
          <input
            type="text" placeholder="Ex : K. Mbappé"
            value={form.player_ref}
            onChange={e => update('player_ref', e.target.value)}
            style={inputStyle}
          />
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, paddingTop: 4 }}>
        <button type="button" onClick={onCancel}
          style={{
            flex: 1, padding: '12px', background: 'var(--surface-2)',
            border: '1px solid var(--border)', borderRadius: 8,
            color: 'var(--text-2)', fontWeight: 700, fontSize: '0.88rem',
            cursor: 'pointer', transition: 'all 0.15s',
          }}>
          Annuler
        </button>
        <button type="button" onClick={handleSubmit} disabled={submitting}
          style={{
            flex: 2, padding: '12px',
            background: submitting ? 'var(--surface-2)' : 'var(--green)',
            border: 'none', borderRadius: 8,
            color: submitting ? 'var(--text-2)' : '#000',
            fontWeight: 800, fontSize: '0.9rem',
            cursor: submitting ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
          {submitting
            ? <><Spinner /> Envoi en cours...</>
            : '📨 Soumettre la réclamation'}
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  CARTE PLAINTE
// ═══════════════════════════════════════════════════════════════

function ComplaintCard({ complaint, expanded, onToggle }) {
  const cat = CATEGORIES.find(c => c.id === complaint.category) || CATEGORIES[CATEGORIES.length - 1];

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 12, overflow: 'hidden',
      transition: 'border-color 0.15s',
      borderColor: expanded ? 'var(--border-light)' : 'var(--border)',
    }}>
      {/* Header */}
      <button type="button" onClick={onToggle}
        style={{
          width: '100%', background: 'none', border: 'none',
          padding: '12px 14px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 10,
          textAlign: 'left',
        }}>

        <PriorityDot priority={complaint.priority} />

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            fontSize: '0.85rem', fontWeight: 700, color: 'var(--text)',
            overflow: 'hidden',
          }}>
            <span style={{ fontSize: '0.9rem' }}>{cat.icon}</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {complaint.title}
            </span>
          </div>
          <div style={{
            display: 'flex', gap: 8, alignItems: 'center',
            marginTop: 4, fontSize: '0.68rem', color: 'var(--text-3)',
          }}>
            <span>#{complaint.id}</span>
            <span>·</span>
            <span>{formatDate(complaint.created_at)}</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusBadge status={complaint.status} />
          <span style={{ color: 'var(--text-3)', fontSize: '0.75rem' }}>
            {expanded ? '▲' : '▼'}
          </span>
        </div>
      </button>

      {/* Corps expandé */}
      {expanded && (
        <div style={{
          padding: '0 14px 14px',
          borderTop: '1px solid var(--border)',
          paddingTop: 12,
          display: 'flex', flexDirection: 'column', gap: 10,
        }}>

          {/* Description */}
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 4 }}>
              Description
            </div>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-2)', lineHeight: 1.6, margin: 0 }}>
              {complaint.description}
            </p>
          </div>

          {/* Références */}
          {(complaint.match_ref || complaint.player_ref) && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {complaint.match_ref && (
                <span style={tagStyle('#38bdf8')}>🎯 {complaint.match_ref}</span>
              )}
              {complaint.player_ref && (
                <span style={tagStyle('#a78bfa')}>👤 {complaint.player_ref}</span>
              )}
            </div>
          )}

          {/* Réponse admin */}
          {complaint.admin_response && (
            <div style={{
              background: complaint.status === 'approved'
                ? 'rgba(0,230,118,0.07)' : 'rgba(244,63,94,0.07)',
              border: `1px solid ${complaint.status === 'approved' ? 'rgba(0,230,118,0.25)' : 'rgba(244,63,94,0.25)'}`,
              borderRadius: 8, padding: '10px 12px',
            }}>
              <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-3)', marginBottom: 4, letterSpacing: '0.07em', textTransform: 'uppercase' }}>
                👮 Réponse de l'administrateur
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-2)', margin: 0, lineHeight: 1.6 }}>
                {complaint.admin_response}
              </p>
              {complaint.resolved_at && (
                <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginTop: 6 }}>
                  Traité le {formatDate(complaint.resolved_at)}
                </div>
              )}
            </div>
          )}

          {complaint.status === 'pending' && (
            <div style={{
              fontSize: '0.75rem', color: 'var(--text-3)',
              fontStyle: 'italic', textAlign: 'center',
            }}>
              ⏳ En attente de traitement par l'administrateur
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  VUE PRINCIPALE
// ═══════════════════════════════════════════════════════════════

export default function Complaints() {
  const { user } = useApp();

  const [view,       setView]       = useState('list'); // 'list' | 'new'
  const [complaints, setComplaints] = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [expanded,   setExpanded]   = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');
  const [successMsg,   setSuccessMsg]   = useState(null);

  const userId = user?.id || 'anonymous';

  const loadComplaints = useCallback(() => {
    const list = loadUserComplaints(userId);
    setComplaints(list);
    setLoading(false);
  }, [userId]);

  useEffect(() => { loadComplaints(); }, [loadComplaints]);

  const handleSubmitted = (updatedList) => {
    setComplaints(updatedList);
    setView('list');
    setSuccessMsg('✅ Réclamation soumise avec succès ! L\'admin examinera votre dossier.');
    setTimeout(() => setSuccessMsg(null), 5000);
  };

  const filtered = filterStatus === 'all'
    ? complaints
    : complaints.filter(c => c.status === filterStatus);

  const counts = {
    all:        complaints.length,
    pending:    complaints.filter(c => c.status === 'pending').length,
    processing: complaints.filter(c => c.status === 'processing').length,
    approved:   complaints.filter(c => c.status === 'approved').length,
    rejected:   complaints.filter(c => c.status === 'rejected').length,
  };

  if (loading) {
    return <div className="loading-spinner">Chargement des plaintes...</div>;
  }

  return (
    <div className="view" style={{ gap: 12 }}>

      {/* ── HEADER ─────────────────────────────────────────── */}
      <div style={{
        background: 'linear-gradient(135deg, #1a0d2e 0%, #0d1526 100%)',
        border: '1px solid var(--border)',
        borderRadius: 14, padding: '16px 14px',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -20, right: -20,
          width: 100, height: 100,
          background: 'radial-gradient(circle, rgba(167,139,250,0.15) 0%, transparent 70%)',
          borderRadius: '50%', pointerEvents: 'none',
        }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.2rem', letterSpacing: '0.08em' }}>
              🚩 Bureau des Plaintes
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: 'var(--text-2)' }}>
              Soumettre une réclamation · Ligue Boulzazen
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-3)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Total
            </div>
            <div style={{ fontFamily: 'Rajdhani, sans-serif', fontSize: '1.8rem', fontWeight: 700, color: '#a78bfa', lineHeight: 1 }}>
              {counts.all}
            </div>
          </div>
        </div>

        {/* Stats rapides */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 6, marginTop: 12,
        }}>
          {[
            { key: 'pending',    label: 'Attente', ...STATUS_CFG.pending    },
            { key: 'processing', label: 'En cours',...STATUS_CFG.processing },
            { key: 'approved',   label: 'Acceptées',...STATUS_CFG.approved  },
            { key: 'rejected',   label: 'Rejetées', ...STATUS_CFG.rejected  },
          ].map(s => (
            <div key={s.key} style={{
              background: s.bg, border: `1px solid ${s.color}30`,
              borderRadius: 8, padding: '6px 8px', textAlign: 'center',
            }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, fontFamily: 'Rajdhani, sans-serif', color: s.color, lineHeight: 1 }}>
                {counts[s.key]}
              </div>
              <div style={{ fontSize: '0.6rem', color: s.color, opacity: 0.8, marginTop: 2, letterSpacing: '0.05em' }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── MESSAGE DE SUCCÈS ───────────────────────────────── */}
      {successMsg && (
        <div style={{
          background: 'rgba(0,230,118,0.08)',
          border: '1px solid rgba(0,230,118,0.3)',
          borderRadius: 8, padding: '10px 14px',
          fontSize: '0.82rem', color: 'var(--green)',
          lineHeight: 1.4,
        }}>
          {successMsg}
        </div>
      )}

      {/* ── FORMULAIRE NOUVELLE PLAINTE ─────────────────────── */}
      {view === 'new' ? (
        <div className="card" style={{ padding: 16 }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 14,
          }}>
            <h3 style={{ margin: 0, fontFamily: 'Rajdhani, sans-serif', fontSize: '1.05rem', letterSpacing: '0.07em' }}>
              📝 Nouvelle Réclamation
            </h3>
            <button type="button" onClick={() => setView('list')}
              style={{
                background: 'var(--surface-2)', border: '1px solid var(--border)',
                borderRadius: 6, width: 28, height: 28, cursor: 'pointer',
                color: 'var(--text-2)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.9rem',
              }}>✕</button>
          </div>
          <NewComplaintForm
            user={user}
            onSubmitted={handleSubmitted}
            onCancel={() => setView('list')}
          />
        </div>
      ) : (
        <>
          {/* ── BOUTON NOUVELLE PLAINTE ──────────────────────── */}
          <button type="button" onClick={() => setView('new')}
            style={{
              width: '100%', padding: '13px',
              background: 'linear-gradient(135deg, rgba(167,139,250,0.15), rgba(56,189,248,0.1))',
              border: '1px solid rgba(167,139,250,0.35)',
              borderRadius: 10, cursor: 'pointer',
              color: '#c4b5fd', fontWeight: 800, fontSize: '0.9rem',
              letterSpacing: '0.04em', transition: 'all 0.2s',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>
            🚩 Déposer une nouvelle réclamation
          </button>

          {/* ── FILTRES ──────────────────────────────────────── */}
          {complaints.length > 0 && (
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              {[
                { key: 'all',        label: `Toutes (${counts.all})` },
                { key: 'pending',    label: `Attente (${counts.pending})` },
                { key: 'processing', label: `En cours (${counts.processing})` },
                { key: 'approved',   label: `Acceptées (${counts.approved})` },
                { key: 'rejected',   label: `Rejetées (${counts.rejected})` },
              ].map(f => (
                <button key={f.key} type="button"
                  onClick={() => setFilterStatus(f.key)}
                  className={`filter-btn ${filterStatus === f.key ? 'active' : ''}`}
                  style={{ fontSize: '0.72rem', padding: '5px 11px' }}>
                  {f.label}
                </button>
              ))}
            </div>
          )}

          {/* ── LISTE DES PLAINTES ───────────────────────────── */}
          {complaints.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🏳️</div>
              <h4>Aucune réclamation</h4>
              <p>Vous n'avez pas encore soumis de plainte. Si vous constatez une erreur dans les scores ou les points, utilisez le bouton ci-dessus.</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🔍</div>
              <h4>Aucun résultat</h4>
              <p>Aucune plainte ne correspond au filtre sélectionné.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {filtered.map(c => (
                <ComplaintCard
                  key={c.id}
                  complaint={c}
                  expanded={expanded === c.id}
                  onToggle={() => setExpanded(expanded === c.id ? null : c.id)}
                />
              ))}
            </div>
          )}

          {/* ── NOTE D'INFORMATION ──────────────────────────── */}
          <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 10, padding: '12px 14px',
          }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-3)', fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 8 }}>
              📋 Comment ça marche ?
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                ['🚩', 'Soumettez', 'Déposez votre réclamation avec tous les détails'],
                ['🔄', 'Examen',    'L\'admin analyse avec l\'IA et rend un verdict'],
                ['✅', 'Correction','Si acceptée, les points sont recalculés'],
              ].map(([icon, title, desc]) => (
                <div key={title} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <span style={{ fontSize: '1rem', flexShrink: 0 }}>{icon}</span>
                  <div>
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text)' }}>{title} — </span>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>{desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  STYLES RÉUTILISABLES
// ═══════════════════════════════════════════════════════════════

const labelStyle = {
  display: 'block',
  fontSize: '0.72rem', fontWeight: 700,
  letterSpacing: '0.07em', textTransform: 'uppercase',
  color: 'var(--text-2)', marginBottom: 4,
};

const inputStyle = {
  width: '100%', padding: '10px 12px',
  background: 'var(--surface-2)',
  border: '1px solid var(--border)',
  borderRadius: 8, color: 'var(--text)',
  fontSize: '0.88rem', fontFamily: 'inherit',
  outline: 'none', boxSizing: 'border-box',
  transition: 'border-color 0.2s',
};

const tagStyle = (color) => ({
  display: 'inline-flex', alignItems: 'center',
  background: `${color}15`, border: `1px solid ${color}35`,
  borderRadius: 50, padding: '3px 10px',
  fontSize: '0.72rem', fontWeight: 600, color: color,
  whiteSpace: 'nowrap',
});

function FieldError({ msg }) {
  return (
    <div style={{ fontSize: '0.72rem', color: 'var(--danger)', marginTop: 4 }}>
      ⚠ {msg}
    </div>
  );
}

function Spinner() {
  return (
    <span style={{
      display: 'inline-block', width: 14, height: 14,
      border: '2px solid rgba(0,0,0,0.2)',
      borderTopColor: '#000', borderRadius: '50%',
      animation: 'spin 0.7s linear infinite',
    }} />
  );
}