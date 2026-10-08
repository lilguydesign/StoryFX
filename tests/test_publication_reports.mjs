import assert from 'node:assert/strict';
import { publicationReportRows, renderPublicationReports, reportDate } from '../dashboard/publication-reports.js';

const planned = { id: 'occurrence', due_at: '2026-10-08T02:40:00Z', device: 'Validation technique',
  platform: 'Facebook', system: 'Validation technique', engine: 'intro+multi', count: 11,
  state: 'PLANNED', availability: 'NOT_SUPPORTED', wait_reason: 'ADAPTER_NOT_VALIDATED',
  album: 'private-album-must-not-be-in-report', album2: 'private-album-must-not-be-in-report' };
const old = { id: 'historical-attempt', state: 'CONFIRMED', evidence: 'own_status_verified',
  publication: { ...planned, platform: 'WhatsApp' }, scheduled_at: planned.due_at,
  expected_media_count: 12, diagnostics: null };
const recent = { ...old, id: 'new-attempt', parent_attempt_id: old.id,
  diagnostics: { expected_count: 12, selected_count: 12, verified_count: 12, stage: 'own_status_verification',
    app_version: '0.4.14', service_ready: true, network: 'wifi', elapsed_ms: 12500,
    verification_method: 'recent_rows' }, batch_count_verified: true, account_verified: false };
const snapshot = { schedule: [planned], reports: [old, recent] };
assert.equal(publicationReportRows(snapshot).length, 3);
const html = renderPublicationReports(snapshot, false);
assert.match(html, /Non pris en charge · aucune tentative/);
assert.match(html, /12 \/ — \/ —/);
assert.match(html, /12 \/ 12 \/ 12/);
assert.match(html, /quantité et compte non documentés/);
assert.match(html, /compte non vérifié/);
assert.match(html, /href="#attempt-historical-attempt"/);
assert.match(html, /Africa\/Douala/);
assert.match(reportDate(planned.due_at), /03:40:00/);
assert.doesNotMatch(html, /private-album/);
assert.match(renderPublicationReports({ schedule: [{ ...planned, system: '<script>unsafe</script>' }], reports: [] }, false), /&lt;script&gt;/);
assert.match(renderPublicationReports(null, false), /Aucune tentative/);
const waitingHtml = renderPublicationReports({ schedule: [{ ...planned, execution_origin: 'web_android_agent' }], reports: [] }, false);
assert.match(waitingHtml, /Non tentée/);
assert.doesNotMatch(waitingHtml, /Serveur → Android/);
console.log('publication report rendering: passed');
