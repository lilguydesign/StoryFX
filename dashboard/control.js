import { request } from './api.js';
import { escape, dateLabel } from './views.js';
import { controlTitles, definitions, descriptions, fields, readFields } from './control-fields.js';
import { mountLauncher, renderLauncher } from './launch-panel.js';
import { profilesTable, changeProfileSort } from './profile-editor.js';
import { showAssociationLink } from './association-link.js';
import { failureLabels, recoveryButton, mountRecovery } from './publication-recovery.js';

let data = null, enabled = false, busy = false, editing = null, editRevision = null, selected = null;
let profileFilter = '', platformFilter = '';
const find = selector => document.querySelector(selector);
const states = { PLANNED: 'Programmée', QUEUED: 'En attente', CLAIMED: 'En cours', CONFIRMED: 'Publication confirmée', NEEDS_REVIEW: 'À vérifier', FAILED_BEFORE_PUBLICATION: 'Refusée avant publication', CANCELLED:'Annulée', CANCEL_REQUESTED:'Arrêt demandé' };
const evidenceLabels = { own_status_three_just_now: '3 images confirmées dans Mon statut', own_status_verified: 'Mon statut vérifié', provider_ui_verified: 'Publication vérifiée', result_uncertain: 'Résultat à vérifier', preflight_refused: 'Vérification préalable refusée' };

export function mountControl(notice) {
  const nav = find('.nav-list');
  for (const [name, title] of Object.entries(controlTitles)) {
    nav.insertAdjacentHTML('beforeend', `<button class="nav-item" data-section="${name}"><span aria-hidden="true">${name === 'launch' ? '▷' : '≋'}</span>${escape(title)}</button>`);
    find('.session-panel').insertAdjacentHTML('beforebegin', `<section class="section-pane" id="pane-${name}" hidden><div class="page-heading"><div><span class="eyebrow">STORYFX · CONTRÔLE</span><h1>${escape(title)}.</h1><p>${escape(descriptions[name])}</p></div>${definitions[name] ? `<button class="button primary" data-create="${name}">＋ Ajouter</button>` : ''}</div><section class="panel"><div class="table-scroll" id="control-${name}"></div></section></section>`);
  }
  document.body.insertAdjacentHTML('beforeend', `
    <dialog id="setting-dialog"><form method="dialog" class="dialog-close"><button class="icon-button" aria-label="Fermer">×</button></form><h2 id="setting-title"></h2><form id="setting-form"><div id="setting-fields" class="control-fields"></div><p class="helper">Les changements sont enregistrés pour votre compte. Ils ne lancent aucune publication.</p><button class="button primary full" type="submit">Enregistrer</button><button class="button secondary full" type="button" id="setting-remove">Supprimer cette référence</button></form></dialog>
    <dialog id="launch-dialog"><form method="dialog" class="dialog-close"><button class="icon-button" aria-label="Fermer">×</button></form><h2>Lancer cette publication</h2><p id="launch-preview"></p><p class="helper">Une seule tentative. Le statut ou la page configurée sera publié réellement. Le téléphone et son agent compatible doivent être disponibles.</p><button class="button primary full" id="launch-confirm">Lancer la publication réelle</button></dialog>
    <dialog id="windows-dialog"><form method="dialog" class="dialog-close"><button class="icon-button" aria-label="Fermer">×</button></form><h2>Connecter le moteur Windows</h2><p>Cet identifiant temporaire associe uniquement le moteur de ce PC à votre compte. Démarrez le connecteur StoryFX puis collez sa demande. Son accès reste chiffré sur Windows. Cette association concerne Windows. Le pilote Android se configure séparément dans StoryFX sur le téléphone. Aucun code de déverrouillage à saisir ici.</p><form id="windows-form"><label>Identifiant de demande<input name="request_id" required pattern="[a-fA-F0-9-]{36}" autocomplete="off"></label><button class="button primary full">Autoriser ce connecteur</button></form></dialog>`);
  const action = async work => {
    if (!enabled || busy) return;
    busy = true; render();
    try { await work(); await loadControl(); notice('Les données StoryFX ont été actualisées.'); }
    catch (error) { notice(error.message || 'Action indisponible.', true); }
    finally { busy = false; render(); }
  };
  document.addEventListener('click', event => {
    const create = event.target.closest('[data-create]');
    const edit = event.target.closest('[data-setting]');
    const launch = event.target.closest('[data-publication]');
    const windows = event.target.closest('[data-windows]');
    const duplicate = event.target.closest('[data-profile-duplicate]');
    if (!enabled || busy) return;
    if (event.target.closest('[data-control-refresh]')) action(async()=>{});
    if (event.target.closest('[data-paste-serial]')) {
      navigator.clipboard.readText().then(value=>{find('#setting-form').elements.adb_serial.value=value.trim();}).catch(()=>notice('Collez le numéro de série dans le champ avec Ctrl+V.',true));
    }
    if (duplicate) {
      const original=data.collections.profiles.find(value=>value.id === duplicate.dataset.profileDuplicate);
      const value={...original,name:original.name+' copie'}; delete value.id;
      editing={collection:'profiles',value}; editRevision=data.revision;
      find('#setting-title').textContent='Dupliquer · Profils';
      find('#setting-fields').innerHTML=fields('profiles',value,data.collections);
      find('#setting-remove').hidden=true; find('#setting-dialog').showModal();
    }
    if (create || edit) {
      const collection = create?.dataset.create || edit.dataset.collection;
      const value = edit ? data.collections[collection].find(item => item.id === edit.dataset.setting) : {};
      editing = { collection, value }; editRevision = data.revision;
      find('#setting-title').textContent = `${create ? 'Créer' : 'Modifier'} · ${controlTitles[collection]}`;
      find('#setting-fields').innerHTML = fields(collection, value, data.collections);
      find('#setting-remove').hidden = !value.id;
      find('#setting-dialog').showModal();
    }
    if (launch) {
      selected = data.schedule.find(item => item.id === launch.dataset.publication);
      editRevision = data.revision;
      find('#launch-preview').textContent = `${selected.device} · ${selected.platform} · ${selected.system} · ${selected.local_time} Douala · ${selected.count} image(s) · ${selected.album2 || selected.album}${selected.page_name ? ` · ${selected.page_name}` : ' · Statut personnel'}`;
      find('#launch-dialog').showModal();
    }
    if (windows) find('#windows-dialog').showModal();
  });
  find('#setting-form').addEventListener('submit', event => {
    event.preventDefault(); action(async () => {
      const { collection, value } = editing;
      await request(`/v1/control/settings/${collection}${value.id ? `/${value.id}` : ''}`, {
        method: value.id ? 'PUT' : 'POST', body: { revision: editRevision, value: readFields(collection, event.target),
          ...(collection === 'profiles' ? {propagate_device:!!event.target.elements.propagate_device?.checked,propagate_serial:!!event.target.elements.propagate_serial?.checked} : {}) },
      }); find('#setting-dialog').close();
    });
  });
  find('#setting-remove').addEventListener('click', () => action(async () => {
    if (!confirm('Supprimer cette référence ? Une référence utilisée par une matrice sera conservée.')) return;
    await request(`/v1/control/settings/${editing.collection}/${editing.value.id}/remove`, { method: 'POST', body: { revision: editRevision } });
    find('#setting-dialog').close();
  }));
  find('#launch-confirm').addEventListener('click', () => action(async () => {
    await request('/v1/control/launch', { method: 'POST', body: { occurrence_id: selected.id, revision: editRevision } });
    find('#launch-dialog').close();
  }));
  find('#windows-form').addEventListener('submit', event => {
    event.preventDefault(); action(async () => {
      await request('/v1/control/windows/approve', { method: 'POST', body: { request_id: event.target.elements.request_id.value.trim() } });
      find('#windows-dialog').close();
    });
  });
  mountLauncher({getSnapshot:()=>data,perform:action,notice,redraw:render});
  mountRecovery({snapshot:()=>data,perform:action});
  render();
  document.addEventListener('change', event => {
    if (changeProfileSort(event)) {render();return;}
    if (event.target.matches('[data-profile-filter]')) profileFilter = event.target.value;
    else if (event.target.matches('[data-platform-filter]')) platformFilter = event.target.value;
    else return;
    render();
  });
}

export async function loadControl() { data = await request('/v1/control'); render(); }
export function enableControl(value) { enabled = value; if (!value) data = null; render(); }
function table(headers, rows) {
  return rows.length ? `<table><thead><tr>${headers.map(text => `<th>${escape(text)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table>` : '<div class="empty-state">Aucune donnée enregistrée.</div>';
}
function render() {
  if (!find('#control-profiles')) return;
  const active = enabled && !busy && data;
  document.querySelectorAll('[data-create]').forEach(button => { button.disabled = !active; });
  for (const name of Object.keys(definitions)) {
    if (name === 'profiles') {find('#control-profiles').innerHTML=profilesTable(data,active);continue;}
    const columns = definitions[name].filter(([key]) => !['xpath', 'label', 'album_size', 'kind', 'page'].includes(key));
    find(`#control-${name}`).innerHTML = table([...columns.map(([, label]) => label), ''], (data?.collections[name] || []).map(value => [
      ...columns.map(([key]) => escape(Array.isArray(value[key]) ? value[key].join(', ') : typeof value[key] === 'boolean' ? (value[key] ? 'Oui' : 'Non') : value[key])),
      `<button class="text-button" data-setting="${value.id}" data-collection="${name}" ${active ? '' : 'disabled'}>Modifier</button>`,
    ]));
  }
  const filtered = (data?.schedule || []).filter(value => (!profileFilter || value.device === profileFilter) && (!platformFilter || value.platform === platformFilter));
  const rows = filtered.map(value => {
    const connected = data.nodes.filter(node => node.connected && node.profiles.includes(value.device)).length === 1;
    return [escape(value.local_time), escape(value.device), escape(value.platform), escape(value.system), escape(value.album2 || value.album), escape(value.count),
      `<span class="badge ${value.state === 'NEEDS_REVIEW' ? 'error' : ''}">${escape(states[value.state] || value.state)}</span>`,
      `<button class="text-button" data-publication="${value.id}" ${active && connected && value.state === 'PLANNED' ? '' : 'disabled'}>Lancer</button>`];
  });
  const options = (values, current, label) => [['', label], ...values.map(value => [value, value])].map(([value, text]) => `<option value="${escape(value)}" ${value === current ? 'selected' : ''}>${escape(text)}</option>`).join('');
  const filters = `<div class="control-filters"><label>Profil<select data-profile-filter>${options((data?.collections.profiles || []).map(value => value.name), profileFilter, 'Tous les profils')}</select></label><label>Plateforme<select data-platform-filter>${options(['WhatsApp', 'Facebook', 'Instagram', 'TikTok'], platformFilter, 'Toutes les plateformes')}</select></label></div>`;
  for (const name of ['launch', 'programming']) find(`#control-${name}`).innerHTML =
    `<p class="helper control-help">Africa/Douala · ${escape(filtered.length)} / ${escape(data?.schedule.length || 0)} occurrences aujourd’hui · ${data?.nodes.some(node => node.connected) ? 'Agent de publication prêt' : 'Aucun agent de publication prêt'}</p><button class="button secondary" data-windows ${active ? '' : 'disabled'}>Connecter Windows</button>` + filters + table(['Heure', 'Profil', 'Plateforme', 'Système', 'Album', 'Images', 'État', ''], rows);
  find('#control-reports').innerHTML = table(['Date', 'Profil', 'Plateforme', 'Système', 'Résultat', 'Origine', 'Preuve', 'Reprise'], (data?.reports || []).map(value => [
    escape(dateLabel(value.completed_at || value.created_at)), escape(value.publication.device), escape(value.publication.platform), escape(value.publication.system),
    escape(states[value.state] || value.state), value.publication.execution_origin === 'web_android_agent' ? 'Web → Android' : value.publication.web_triggered ? 'Web → Windows' : 'Moteur local', escape(evidenceLabels[value.evidence] || failureLabels[value.evidence] || 'En attente'),
    recoveryButton(value, data.reports, active),
  ]));
  renderLauncher(data,active);
  showAssociationLink(active);
}
