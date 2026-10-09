import { escape } from './views.js';
import { failureLabels, recoveryButton } from './publication-recovery.js';

const results = {
  QUEUED: 'En attente', CLAIMED: 'En cours', CANCEL_REQUESTED: 'Arrêt demandé',
  CONFIRMED: 'Confirmation de l’agent', NEEDS_REVIEW: 'Incertaine · à vérifier',
  FAILED_BEFORE_PUBLICATION: 'Échec avant envoi', CANCELLED: 'Annulée',
};
const stages = {
  preflight: 'Contrôle préalable', album_media_unavailable: 'Sélection des médias',
  provider_not_ready: 'Ouverture WhatsApp', updates_navigation_failed: 'Navigation Actus',
  own_status_unavailable: 'Ouverture Mon statut', share_selection_refused: 'Destination du partage',
  contacts_preview_refused: 'Aperçu du statut', own_status_verification: 'Vérification du lot',
  complete: 'Résultat enregistré',
};
const networks = { unknown: 'Non observé', offline: 'Hors ligne', wifi: 'Wi-Fi', cellular: 'Mobile', other: 'Autre réseau' };
const methods = { recent_rows: 'Lignes récentes', recent_visible: 'Statuts récents visibles',
  sequential_recent_visible_v1: 'Tranches distinctes de statuts récents visibles', none: 'Aucune preuve quantifiée' };
const waits = {
  ADAPTER_NOT_VALIDATED: 'Moteur non pris en charge', EXECUTOR_CONFLICT: 'Plusieurs moteurs concurrents',
  ANDROID_EXECUTOR_DISABLED: 'Agent Android désactivé', SCREEN_LOCKED: 'Écran verrouillé',
  ACCESSIBILITY_REQUIRED: 'Accessibilité requise', MEDIA_PERMISSION_REQUIRED: 'Autorisation médias requise',
  WAITING_PERMISSIONS: 'Autorisations Android attendues', ANDROID_MEDIA_CAPABILITY_REQUIRED: 'Mise à jour médias Android requise',
  ANDROID_DISCONNECTED: 'Agent Android sans contact récent', WINDOWS_DISCONNECTED: 'Pont Windows sans contact récent',
};
const number = value => Number.isInteger(value) && value >= 0 ? String(value) : '—';
const lines = (...values) => values.filter(Boolean).map(value => `<span class="report-line">${escape(value)}</span>`).join('');

export function reportDate(value) {
  const date = new Date(value);
  return value && !Number.isNaN(date.valueOf()) ? new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'Africa/Douala', day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(date) : 'Non renseigné';
}

export function publicationReportRows(snapshot) {
  const reports = snapshot?.reports || [];
  const waiting = (snapshot?.schedule || []).filter(row => row.state === 'PLANNED').map(row => ({
    id: null, occurrence_id: row.id, publication: row, state: 'PLANNED',
    availability: row.availability, wait_reason: row.wait_reason, scheduled_at: row.due_at,
    page_reference: row.page_reference, diagnostics: null,
    expected_media_count: row.engine === 'intro' ? 1 : Number(row.count) + (row.engine === 'intro+multi' ? 1 : 0),
  }));
  return [...reports, ...waiting].sort((a, b) => String(b.scheduled_at || b.publication.due_at)
    .localeCompare(String(a.scheduled_at || a.publication.due_at)));
}

function resultLabel(row) {
  if (row.state !== 'PLANNED') return results[row.state] || 'État inconnu';
  return row.availability === 'NOT_SUPPORTED' ? 'Non pris en charge · aucune tentative'
    : row.availability === 'WAITING_EXECUTOR' ? 'En attente du moteur · aucune tentative'
      : 'Programmée · aucune tentative';
}

function proof(row) {
  if (row.state === 'PLANNED') return 'Aucune publication constatée';
  if (!row.diagnostics) return row.state === 'CONFIRMED'
    ? 'Confirmation historique de l’agent ; quantité et compte non documentés'
    : 'Diagnostic détaillé non disponible pour cette tentative';
  return `${row.batch_count_verified ? 'Lot quantifié par l’agent' : 'Lot non confirmé'} · ${
    row.account_verified ? 'compte vérifié par l’agent' : 'compte non vérifié'} · ${
    methods[row.diagnostics.verification_method] || methods.none}`;
}

export function renderPublicationReports(snapshot, active) {
  const rows = publicationReportRows(snapshot);
  if (!rows.length) return '<div class="empty-state">Aucune tentative ni programmation enregistrée.</div>';
  return `<p class="helper">Horaires Africa/Douala. Attendu / sélectionné / vérifié : les valeurs absentes restent inconnues. Une confirmation de l’agent ne prouve pas l’autonomie sans PC, la veille ou le bon compte.</p>
    <table class="publication-reports"><thead><tr>${['Échéance et résultat', 'Profil et destination', 'Catégorie', 'Verdict',
      'Médias A / S / V', 'Étape et version', 'Service, réseau et durée', 'Tentative', 'Preuve et reprise']
      .map(label => `<th>${escape(label)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => {
    const value = row.publication, diagnostic = row.diagnostics;
    const origin = !row.id ? 'Non tentée' : value.execution_origin === 'web_android_agent' ? 'Serveur → Android'
      : value.web_triggered ? 'Serveur → Windows' : 'Moteur local';
    const attempt = row.id ? `<a href="#attempt-${escape(row.id)}">${escape(row.id.slice(0, 8))}</a>${
      row.parent_attempt_id ? `<br><a href="#attempt-${escape(row.parent_attempt_id)}">Tentative d’origine</a>` : ''}` : '—';
    const timing = diagnostic ? `${(diagnostic.elapsed_ms / 1000).toFixed(1)} s` : 'Durée non documentée';
    const destination = row.page_reference || (value.platform === 'WhatsApp' ? 'Mon statut' : 'Page non vérifiée');
    return `<tr${row.id ? ` id="attempt-${escape(row.id)}"` : ''}><td>${lines(reportDate(row.scheduled_at || value.due_at),
      row.completed_at ? `Résultat ${reportDate(row.completed_at)}` : '')}</td>
      <td>${lines(value.device, value.platform, destination)}</td><td>${escape(value.system)}</td>
      <td>${lines(resultLabel(row), failureLabels[row.evidence] || waits[row.wait_reason] || '',
        row.evidence ? `Code : ${row.evidence}` : row.wait_reason && row.wait_reason !== 'READY' ? `Code : ${row.wait_reason}` : '')}</td>
      <td>${number(row.expected_media_count)} / ${number(diagnostic?.selected_count)} / ${number(diagnostic?.verified_count)}</td>
      <td>${lines(diagnostic ? stages[diagnostic.stage] || diagnostic.stage : 'Non documentée', diagnostic ? `Android ${diagnostic.app_version}` : '', origin)}</td>
      <td>${lines(diagnostic ? `Service ${diagnostic.service_ready ? 'actif' : 'indisponible'}` : 'Service non observé',
        `Réseau : ${networks[diagnostic?.network] || networks.unknown}`, timing)}</td>
      <td>${attempt}</td><td>${lines(proof(row))}${row.id ? recoveryButton(row, snapshot.reports, active) : ''}</td></tr>`;
  }).join('')}</tbody></table>`;
}
