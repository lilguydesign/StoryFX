import {request} from './api.js';
import {createProfileBindingsModel} from './android-profile-bindings-model.js';
import {renderProfileBindings} from './android-profile-bindings-view.js';

export function mountProfileBindings({canOperate, invalidSession}) {
  const panel = document.createElement('section');
  panel.className = 'panel android-profile-bindings';
  panel.id = 'android-profile-bindings';
  panel.setAttribute('aria-labelledby', 'android-profiles-title');
  document.querySelector('#pane-devices').append(panel);
  let selected = {device: '', profile: '', binding: '', confirmed: false};
  let client;
  function render() {
    if (!client) return;
    const choices = client.choices(), state = client.view();
    if (!choices.devices.some(d => d.device_id === selected.device)) selected.device = '';
    if (!choices.profiles.some(p => p.id === selected.profile)) selected.profile = '';
    if (!state.snapshot?.bindings.bindings.some(b => b.id === selected.binding && b.active)) {
      selected.binding = ''; selected.confirmed = false;
    }
    panel.innerHTML = renderProfileBindings(state, choices, selected);
  }
  const storage = {getItem: key => window.localStorage.getItem(key),
    setItem: (key, value) => window.localStorage.setItem(key, value)};
  client = createProfileBindingsModel({request, storage, canOperate, invalidSession, changed: render});
  panel.addEventListener('change', event => {
    const field = event.target.dataset.apbSelect;
    if (field) { selected[field] = event.target.value; if (field === 'binding') selected.confirmed = false; }
    if (event.target.hasAttribute('data-apb-confirm')) selected.confirmed = event.target.checked;
    render();
  });
  panel.addEventListener('click', event => {
    const action = event.target.closest('[data-apb]')?.dataset.apb;
    if (action === 'refresh') client.load();
    else if (action) client.mutate(action);
  });
  panel.addEventListener('submit', event => {
    event.preventDefault();
    const kind = event.target.dataset.apbForm, revision = client.view().snapshot?.catalog.revision;
    if (kind === 'add') client.mutate(kind, {revision, device_id: selected.device, profile_id: selected.profile});
    if (kind === 'remove') client.mutate(kind, {revision, id: selected.binding, confirmed: selected.confirmed});
  });
  render();
  return {load: client.load, render, session(owner) {
    selected = {device: '', profile: '', binding: '', confirmed: false}; client.session(owner);
  }};
}
