import { request } from './api.js';
import { escape, dateLabel } from './views.js';
import { mediaSummary } from './media-plan.js';

let draft = {mode:'auto',start_time:'05:00',end_time:'',profiles:[],platforms:['WhatsApp']};
let preview = null, pending = null;
let profilesInitialized = false;
const find = selector => document.querySelector(selector);
const labels = {QUEUED:'Publication mise en attente',CLAIMED:'Publication en cours',CONFIRMED:'Publication confirmée',NEEDS_REVIEW:'Résultat à vérifier',
  FAILED_BEFORE_PUBLICATION:'Refusée avant publication',SCHEDULER_STARTED:'Scheduler démarré',SCHEDULER_STOPPED:'Scheduler arrêté',
  SCHEDULER_PAUSED:'Scheduler suspendu : compte ou configuration à vérifier',STOP_REQUESTED:'Arrêt demandé ; tâches en attente annulées'};
const reasons = {READY:'Prête',ALREADY_REQUESTED:'Déjà demandée / confirmée : ignorée',ADAPTER_NOT_VALIDATED:'Moteur non validé : exclue',WINDOWS_DISCONNECTED:'Téléphone ou agent compatible indisponible'};
const schedulerWait = status => ({AUTH_UNAVAILABLE:'Le contrôle FormaFX est temporairement indisponible. Nouvelle vérification automatique, sans publication tant que l’accès n’est pas validé.',RATE_LIMITED:'Le contrôle FormaFX limite momentanément les requêtes. Nouvelle vérification automatique dans cinq minutes au maximum.'}[status.wait_reason] || 'En attente du moteur ou des téléphones.');
const clock = value => new Intl.DateTimeFormat('fr-FR',{timeZone:'Africa/Douala',hour:'2-digit',minute:'2-digit',hour12:false}).format(value ? new Date(value) : new Date());

function body(snapshot) {
  return {revision:snapshot.revision,profiles:draft.profiles,platforms:draft.platforms,
    start_time:draft.start_time,end_time:draft.end_time || null};
}

function previewTable(value) {
  if (!value) return '<p class="helper">Prévisualisez le rattrapage avant de lancer.</p>';
  return `<p class="helper">${dateLabel(value.from_at)} → ${dateLabel(value.until)} · ${value.eligible_count} prête(s).</p><div class="table-scroll"><table><thead><tr><th>Heure</th><th>Profil</th><th>Système</th><th>Mode et médias</th><th>Vérification</th></tr></thead><tbody>${value.rows.map(row=>`<tr><td>${escape(row.local_time)}</td><td>${escape(row.device)}</td><td>${escape(row.system)}</td><td>${escape(mediaSummary(row))}</td><td>${escape(reasons[row.reason] || row.reason)}</td></tr>`).join('')}</tbody></table></div>`;
}

export function mountLauncher({getSnapshot,perform,notice,redraw}) {
  find('#pane-launch .panel').insertAdjacentHTML('beforebegin','<section class="panel launch-controls" id="launch-controls"></section>');
  find('#pane-launch').insertAdjacentHTML('beforeend','<section class="panel terminal-panel"><div class="terminal-heading"><div><h2>Terminal d’activité</h2><p class="helper">Journal privé des commandes et résultats. Effacer masque l’affichage et conserve les rapports.</p></div><div class="terminal-actions"><button class="button secondary" data-terminal-copy>⧉ Copier le terminal</button><button class="button secondary" data-terminal-clear>⌫ Effacer</button></div></div><pre id="control-terminal" tabindex="0" aria-label="Terminal d’activité StoryFX"></pre></section>');
  document.body.insertAdjacentHTML('beforeend','<dialog id="scheduler-dialog"><form method="dialog" class="dialog-close"><button class="icon-button" aria-label="Fermer">×</button></form><h2 id="scheduler-dialog-title"></h2><div id="scheduler-review"></div><p class="helper">Publications réelles sur les profils choisis. Aucune occurrence déjà demandée ne sera rejouée. Associez le moteur Windows ou activez le pilote Android pour les images WhatsApp. Android attend un écran allumé et déverrouillé, les photos autorisées et le service Accessibilité actif.</p><button class="button primary full" id="scheduler-confirm">Démarrer les publications</button></dialog>');
  document.addEventListener('change',event=> {
    if (!event.target.closest('#launch-controls')) return;
    const input=event.target;
    if (input.name === 'mode' || input.name === 'start_time' || input.name === 'end_time') draft[input.name]=input.value;
    if (input.name === 'scheduler-profile') draft.profiles=[...document.querySelectorAll('[name="scheduler-profile"]:checked')].map(x=>x.value);
    if (input.name === 'scheduler-platform') draft.platforms=[...document.querySelectorAll('[name="scheduler-platform"]:checked')].map(x=>x.value);
    preview=null; redraw();
  });
  document.addEventListener('input',event=> {
    if (event.target.closest('#launch-controls') && ['start_time','end_time'].includes(event.target.name)) {
      draft[event.target.name]=event.target.value;
    }
  });
  document.addEventListener('click',async event=> {
    const button=event.target.closest('[data-scheduler-action],[data-terminal-copy],[data-terminal-clear]');
    if (!button || button.disabled) return;
    try {
      if (button.hasAttribute('data-terminal-copy')) {
        await navigator.clipboard.writeText(find('#control-terminal').textContent); notice('Terminal copié.'); return;
      }
      if (button.hasAttribute('data-terminal-clear')) {
        perform(()=>request('/v1/control/terminal/clear',{method:'POST',body:{}})); return;
      }
      const action=button.dataset.schedulerAction;
      if (action === 'stop' || action === 'stop-jobs') {
        perform(()=>request(action === 'stop' ? '/v1/control/scheduler/stop' : '/v1/control/stop',
          {method:'POST',body:action === 'stop' ? {} : {stop_scheduler:true}})); return;
      }
      const snapshot=getSnapshot();
      if (!snapshot || !draft.profiles.length || !draft.platforms.length) {notice('Sélectionnez au moins un profil et une plateforme.',true); return;}
      const windowBody=body(snapshot);
      if (action === 'start' && draft.mode === 'auto') {
        windowBody.start_time=clock(snapshot.server_time); windowBody.end_time=null;
      }
      preview=await request('/v1/control/catchup/preview',{method:'POST',body:windowBody});
      redraw();
      if (action === 'preview') return;
      pending={path:action === 'start' ? '/v1/control/scheduler/start' : '/v1/control/catchup/launch',
        body:action === 'start' ? {...body(snapshot),mode:draft.mode,end_time:null} : {...windowBody,end_time:clock(preview.until)}};
      find('#scheduler-dialog-title').textContent=action === 'start' ? 'Démarrer le scheduler' : 'Lancer le rattrapage';
      find('#scheduler-review').innerHTML=`<p>${escape(draft.profiles.join(', '))} · ${escape(draft.platforms.join(', '))}</p><p>${action === 'start' ? draft.mode === 'auto' ? 'Mode automatique : horaires à partir de maintenant.' : 'Rattrapage manuel, puis retour à l’heure actuelle.' : 'Rattrapage de l’intervalle choisi uniquement.'}</p>`+previewTable(preview);
      find('#scheduler-confirm').disabled=action !== 'start' && !preview.eligible_count;
      find('#scheduler-dialog').showModal();
    } catch (error) {notice(error.message || 'Commande indisponible.',true);}
  });
  find('#scheduler-confirm').addEventListener('click',()=> {
    if (!pending) return;
    const command=pending; pending=null;
    perform(async()=> {await request(command.path,{method:'POST',body:command.body});find('#scheduler-dialog').close();preview=null;});
  });
}

export function renderLauncher(snapshot, active) {
  if (!find('#launch-controls')) return;
  const profiles=snapshot?.collections.profiles || [];
  if (!profilesInitialized && profiles.length) {draft.profiles=profiles.filter(value=>['JK650_S23','JK657_S23+'].includes(value.name)).map(value=>value.name);profilesInitialized=true;}
  const status=snapshot?.scheduler || {enabled:false};
  const disabled=active ? '' : 'disabled';
  const choices=(name,values,selected)=>values.map(value=>`<label class="choice"><input type="checkbox" name="${name}" value="${escape(value)}" ${selected.includes(value) ? 'checked' : ''} ${disabled}>${escape(value)}</label>`).join('');
  find('#launch-controls').innerHTML=`<div class="terminal-heading"><h2>Pilotage de la programmation</h2><span class="badge ${status.enabled ? 'success' : ''}">${status.enabled ? 'Scheduler actif' : 'Scheduler arrêté'}</span></div>
    <p class="helper">Heure PC : ${clock()} · Heure serveur : ${clock(snapshot?.server_time)} · Africa/Douala. Le serveur horodate les commandes ; un agent Windows ou Android compatible exécute les publications.</p>
    <fieldset><legend>Profils à piloter</legend><div class="profile-choices">${choices('scheduler-profile',profiles.map(x=>x.name),draft.profiles)}</div></fieldset>
    <fieldset><legend>Plateformes</legend><div class="profile-choices">${choices('scheduler-platform',['WhatsApp','Facebook','Instagram','TikTok'],draft.platforms)}</div></fieldset>
    <div class="control-filters"><label>Temps scheduler<select name="mode" ${disabled}><option value="auto" ${draft.mode === 'auto' ? 'selected' : ''}>Auto · heure actuelle</option><option value="manual" ${draft.mode === 'manual' ? 'selected' : ''}>Manuel · rattrapage puis automatique</option></select><small class="field-help">Le mode manuel reprend les heures passées à partir de l’heure choisie, puis suit les prochaines échéances.</small></label>
    <label>Début du rattrapage<input type="time" name="start_time" value="${escape(draft.start_time)}" ${disabled}></label><label>Fin du rattrapage<input type="time" name="end_time" value="${escape(draft.end_time)}" ${disabled}><small class="field-help">Laissez vide pour utiliser l’heure actuelle. Une heure future est refusée.</small></label></div>
    <div class="scheduler-actions"><button class="button primary" data-scheduler-action="start" ${active && !status.enabled ? '' : 'disabled'}>▷ Démarrer scheduler</button><button class="button danger" data-scheduler-action="stop" ${active && status.enabled ? '' : 'disabled'}>■ Arrêter scheduler</button><button class="button secondary" data-scheduler-action="preview" ${disabled}>Prévisualiser le rattrapage</button><button class="button secondary" data-scheduler-action="catchup" ${disabled}>▷ Lancer le rattrapage</button><button class="button danger" data-scheduler-action="stop-jobs" ${disabled}>■ Stopper les tâches</button></div>
    <p class="helper">Arrêter le scheduler bloque ses prochains départs et annule sa file en attente. Stopper annule aussi les demandes manuelles en attente ; une action déjà envoyée à l’application sociale peut se terminer. Appium n’est pas interrompu.</p>${status.enabled ? `<p class="helper">Profils actifs : ${escape((status.profiles || []).join(', '))}. ${status.wait_reason ? escape(schedulerWait(status)) : ''}</p>` : ''}<div id="catchup-preview">${previewTable(preview)}</div>`;
  const terminal=(snapshot?.terminal || []).map(row=>`[${clock(row.time)}] ${labels[row.kind] || 'Événement'}${row.profile ? ' · '+row.profile : ''}${row.system ? ' · '+row.system : ''}`).join('\n');
  find('#control-terminal').textContent=terminal || 'Aucune activité enregistrée.';
  document.querySelectorAll('[data-terminal-clear],[data-terminal-copy]').forEach(button=>{button.disabled=!active;});
}
