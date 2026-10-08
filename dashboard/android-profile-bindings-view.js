import {escape} from './views.js';

const options = (values, selected, id, label) => values.map(value =>
  `<option value="${escape(id(value))}" ${id(value) === selected ? 'selected' : ''}>${escape(label(value))}</option>`).join('');

export function renderProfileBindings(state, choices, selected) {
  const disabled = !state.mutable || Boolean(state.pending) ? 'disabled' : '';
  const list = state.snapshot?.bindings.bindings || [];
  const deviceName = id => state.snapshot?.bindings.devices.find(d => d.device_id === id)?.name || 'Appareil indisponible';
  const title = b => `${deviceName(b.device_id)} · ${b.profile || 'Profil retiré du catalogue'}`;
  const currentDevice = choices.devices.find(d => d.device_id === selected.device);
  return `<div class="apb-heading"><div><span class="eyebrow">ASSOCIATIONS ANDROID</span>
    <h2 id="android-profiles-title">Profils Facebook supplémentaires</h2></div>
    <button type="button" class="button secondary" data-apb="refresh"
      ${!state.owner || state.reading || state.acting ? 'disabled' : ''}>↻ Actualiser</button></div>
    <p class="apb-capability"><span aria-hidden="true">◌</span> Adaptateur Facebook natif non validé.
      Associer ou retirer un profil ne publie rien et ne démarre aucune programmation.</p>
    ${!state.owner ? '<p class="helper">Disponible avec une session propriétaire active. La démonstration reste en lecture seule.</p>' : ''}
    ${state.held ? '<p class="apb-status" role="status">Une recette manuelle est active : les associations sont en lecture seule.</p>' : ''}
    ${state.error ? `<p class="apb-error" role="alert">${escape(state.error)}</p>` : ''}
    ${state.reading ? '<p class="helper" role="status">Vérification des appareils, profils et associations…</p>' : ''}
    ${state.pending ? `<div class="apb-pending" role="status"><strong>Demande précédente à vérifier</strong>
      <p>Sa clé de reprise est conservée. Une actualisation recherche son reçu sans refaire la demande.</p>
      <button type="button" class="button secondary" data-apb="refresh" ${state.reading || state.acting ? 'disabled' : ''}>Vérifier le résultat</button>
      ${state.pending.refused ? `<button type="button" class="button secondary" data-apb="discard" ${!state.mutable ? 'disabled' : ''}>Fermer la demande refusée</button>` :
        `<button type="button" class="button secondary" data-apb="resume" ${!state.mutable || !state.resumable ? 'disabled' : ''}>Reprendre la même demande</button>`}</div>` : ''}
    <div class="apb-forms"><form data-apb-form="add">
      <h3>Associer un profil existant</h3>
      <label>Téléphone déjà associé<select name="device" data-apb-select="device" required ${disabled}>
        <option value="">Choisir un téléphone</option>${options(choices.devices, selected.device, d => d.device_id, d => d.name)}</select></label>
      <p class="helper">${currentDevice ? `Profil principal conservé : ${escape(currentDevice.primary_profile)}.` : 'Le profil principal WhatsApp reste inchangé.'}</p>
      <label>Profil Facebook du catalogue<select name="profile" data-apb-select="profile" required ${disabled}>
        <option value="">Choisir un profil</option>${options(choices.profiles, selected.profile, p => p.id, p => p.name)}</select></label>
      <p class="helper">Les profils principaux, désactivés ou déjà associés sont exclus.</p>
      <button class="button primary" type="submit" ${disabled || !selected.device || !selected.profile ? 'disabled' : ''}>＋ Associer pour Facebook</button>
    </form><form data-apb-form="remove">
      <h3>Retirer une association</h3>
      <label>Association Facebook active<select name="binding" data-apb-select="binding" required ${disabled}>
        <option value="">Choisir une association</option>${options(list.filter(b => b.active), selected.binding, b => b.id, title)}</select></label>
      <label class="apb-confirm"><input type="checkbox" data-apb-confirm ${selected.confirmed ? 'checked' : ''} ${disabled}>
        Je confirme le retrait de cette association Facebook.</label>
      <p class="helper">Le reçu de retrait reste dans l’historique. Le profil, le téléphone et les tâches sont conservés.</p>
      <button class="button secondary" type="submit" ${disabled || !selected.binding || !selected.confirmed ? 'disabled' : ''}>Retirer l’association sélectionnée</button>
    </form></div>
    <div class="apb-history"><h3>Associations et retraits</h3>
      ${list.length ? `<div class="table-scroll"><table><thead><tr><th>Téléphone</th><th>Profil</th><th>Association</th><th>Publication native</th></tr></thead><tbody>
        ${list.map(b => `<tr><td>${escape(deviceName(b.device_id))}</td><td>${escape(b.profile || 'Profil supprimé')}</td>
          <td>${b.active ? b.enabled ? 'Associée' : 'Associée · profil désactivé' : 'Retirée'}</td><td>Non validée</td></tr>`).join('')}
        </tbody></table></div>` : '<p class="helper">Aucune association secondaire chargée.</p>'}</div>`;
}
