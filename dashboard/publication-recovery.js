import { request } from './api.js';
import { escape } from './views.js';

const safeFailures = new Set(['album_media_unavailable', 'provider_not_ready', 'updates_navigation_failed', 'own_status_unavailable']);
export const failureLabels = {
  album_media_unavailable: 'Album ou images indisponibles', provider_not_ready: 'Ouverture de WhatsApp impossible',
  updates_navigation_failed: 'Accès aux mises à jour impossible', own_status_unavailable: 'Mon statut non vérifiable',
  share_selection_refused: 'Sélection du statut refusée', contacts_preview_refused: 'Aperçu Contacts non vérifiable',
};
export function recoveryButton(report, reports, active) {
  const retryable = report.state === 'FAILED_BEFORE_PUBLICATION' && safeFailures.has(report.evidence) &&
    report.publication.execution_origin === 'web_android_agent' &&
    !reports.some(value => value.publication.retry_parent === report.id);
  return retryable ? `<button class="text-button" data-publication-retry="${escape(report.id)}" ${active ? '' : 'disabled'}>Réessayer après correction</button>` : '—';
}
export function mountRecovery({ snapshot, perform }) {
  document.body.insertAdjacentHTML('beforeend', `<dialog id="recovery-dialog"><form method="dialog" class="dialog-close"><button class="icon-button" aria-label="Fermer">×</button></form><h2>Réessayer la publication</h2><p id="recovery-preview"></p><p class="helper">Cette tentative s’est arrêtée avant tout envoi. Corrigez la cause sur le téléphone avant de reprendre. La même planification et les mêmes destinataires sont conservés. Les résultats incertains et les publications confirmées ne sont jamais rejoués.</p><button class="button primary full" id="recovery-confirm">Relancer la publication réelle</button></dialog>`);
  let selected = null, revision = null;
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-publication-retry]');
    if (!button || button.disabled) return;
    const data = snapshot(); selected = data.reports.find(value => value.id === button.dataset.publicationRetry);
    if (!selected) return;
    revision = data.revision;
    document.querySelector('#recovery-preview').textContent = `${selected.publication.device} · ${selected.publication.count} image(s) · ${selected.publication.album2 || selected.publication.album} · Statut personnel`;
    document.querySelector('#recovery-dialog').showModal();
  });
  document.querySelector('#recovery-confirm').addEventListener('click', () => perform(async () => {
    await request(`/v1/control/jobs/${selected.id}/retry`, {method:'POST', body:{revision}});
    document.querySelector('#recovery-dialog').close();
  }));
}
