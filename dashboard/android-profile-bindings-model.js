const endpoint = '/v1/control/android/profile-bindings';
const uuidPattern = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const refusedCodes = new Set(['CONFIGURATION_CHANGED', 'PROFILE_NOT_FOUND', 'ANDROID_PROFILE_ALREADY_BOUND',
  'ANDROID_PRIMARY_BINDING_REQUIRED', 'ANDROID_PROFILE_LIMIT_REACHED', 'PUBLICATION_IN_PROGRESS',
  'DEVICE_ACTIVITY_IN_PROGRESS', 'MANUAL_RECIPE_ACTIVE', 'IDEMPOTENCY_KEY_CONFLICT']);
export const bindingMessages = {
  MANUAL_RECIPE_ACTIVE: 'Une recette manuelle est active. Les associations restent en lecture seule.',
  PUBLICATION_IN_PROGRESS: 'Une publication attend son résultat. Les associations sont conservées.',
  DEVICE_ACTIVITY_IN_PROGRESS: 'Un diagnostic est en cours sur cet appareil. Attendez son résultat.',
  CONFIGURATION_CHANGED: 'Le catalogue a changé. Vérifiez les choix actualisés avant de confirmer.',
  ANDROID_PROFILE_ALREADY_BOUND: 'Ce profil possède déjà une association. Actualisez la liste.',
  ANDROID_PROFILE_LIMIT_REACHED: 'Cet appareil possède déjà 99 associations secondaires.',
};
const ensure = (value, message = 'La lecture des associations est incomplète. Actualisez la liste.') => {
  if (!value) throw Error(message);
};

export function createProfileBindingsModel({request, storage, canOperate, changed = () => {},
  invalidSession = () => {}, uuid = () => crypto.randomUUID(),
  serialize = (key, work) => {
    ensure(globalThis.navigator?.locks, 'Ce navigateur ne permet pas de protéger les demandes concurrentes.');
    return navigator.locks.request(key, work);
  }}) {
  let owner = null, epoch = 0, sequence = 0, snapshot = null, reading = false, acting = false, error = '';
  let fresh = false;
  const key = () => `storyfx.android-profile-actions.v1.${owner}`;
  const live = token => token === epoch && Boolean(owner);
  function journal() {
    if (!owner) return null;
    const value = JSON.parse(storage.getItem(key()) || 'null');
    if (value) {
      ensure(['add', 'remove'].includes(value.kind) && Number.isInteger(value.body?.revision));
      if (value.kind === 'add') ensure(uuidPattern.test(value.body.client_key) &&
        uuidPattern.test(value.body.device_id) && uuidPattern.test(value.body.profile_id) && value.body.platform === 'Facebook');
      else ensure(uuidPattern.test(value.id));
    }
    return value;
  }
  function save(value) {
    const encoded = JSON.stringify(value);
    storage.setItem(key(), encoded);
    ensure(storage.getItem(key()) === encoded, 'La clé de reprise ne peut pas être conservée. Aucune demande envoyée.');
  }
  const held = () => Boolean(snapshot?.recipes.active_recipe_id || snapshot?.recipes.recipes.some(r => r.lock_held));
  function view() {
    let pending = null, storageError = '';
    try { pending = journal(); } catch { storageError = 'Le journal de reprise est illisible. Aucune mutation autorisée.'; }
    return {snapshot, pending, reading, acting, error: storageError || error, owner: Boolean(owner),
      held: held(), mutable: Boolean(owner && canOperate() && fresh && !reading && !acting && !held() && !storageError),
      resumable: Boolean(fresh && pending && !pending.refused)};
  }
  const emit = () => changed(view());
  function session(value) {
    if (owner === value) return;
    owner = value; epoch++; sequence++; snapshot = null; fresh = false; reading = false; acting = false; error = '';
    emit();
  }
  async function verifyOwner(token) {
    const value = await request('/v1/auth/session');
    if (!live(token)) return false;
    if (value?.user?.id !== owner || value.access !== 'formafx_active_owner') {
      session(null); invalidSession(); return false;
    }
    return true;
  }
  function validate(catalog, bindings, recipes) {
    ensure(Number.isInteger(catalog.revision) && catalog.revision === bindings.revision &&
      Array.isArray(catalog.collections?.profiles) && Array.isArray(bindings.bindings) &&
      Array.isArray(bindings.devices) && Array.isArray(bindings.primary_profile_ids) &&
      Array.isArray(recipes.recipes) && Object.hasOwn(recipes, 'active_recipe_id') &&
      bindings.capabilities?.facebook?.ready === false);
    ensure(bindings.devices.every(d => uuidPattern.test(d.device_id) && uuidPattern.test(d.primary_profile_id) &&
      typeof d.name === 'string' && typeof d.primary_profile === 'string' && d.revoked === false));
    ensure(bindings.primary_profile_ids.every(id => uuidPattern.test(id)) &&
      bindings.bindings.every(b => uuidPattern.test(b.id) && uuidPattern.test(b.client_key) &&
        uuidPattern.test(b.device_id) && uuidPattern.test(b.profile_id) && b.platform === 'Facebook' &&
        typeof b.active === 'boolean' && b.ready === false));
  }
  function reconcile(bindings) {
    const pending = journal();
    if (!pending) return;
    const found = bindings.find(b => pending.kind === 'add' ? b.client_key === pending.body.client_key : b.id === pending.id);
    if (!found) return;
    if (pending.kind === 'add') {
      ensure(found.device_id === pending.body.device_id && found.profile_id === pending.body.profile_id && found.platform === 'Facebook');
      save(null); // A withdrawn receipt is resolved too; never reactivate it implicitly.
    } else if (!found.active) save(null);
  }
  async function load() {
    if (!owner) return false;
    const token = epoch, read = ++sequence;
    reading = true; fresh = false; error = ''; emit();
    try {
      if (!await verifyOwner(token)) return false;
      const [catalog, bindings, recipes] = await Promise.all([
        request('/v1/control'), request(endpoint), request('/v1/control/recipes')]);
      if (!live(token) || read !== sequence || !await verifyOwner(token)) return false;
      if (!live(token) || read !== sequence) return false;
      validate(catalog, bindings, recipes);
      reconcile(bindings.bindings);
      snapshot = {catalog, bindings, recipes}; fresh = true;
      return true;
    } catch (failure) {
      if (live(token) && read === sequence) {
        error = bindingMessages[failure.code] || 'Lecture indisponible. Les demandes en attente sont conservées.';
        if (['unauthorized', 'forbidden'].includes(failure.kind)) { session(null); invalidSession(); }
      }
      return false;
    } finally { if (live(token) && read === sequence) { reading = false; emit(); } }
  }
  function choices() {
    if (!snapshot) return {devices: [], profiles: []};
    const {catalog, bindings} = snapshot;
    const reserved = new Set([...bindings.primary_profile_ids,
      ...bindings.bindings.filter(b => b.active).map(b => b.profile_id)]);
    return {devices: bindings.devices, profiles: catalog.collections.profiles.filter(p =>
      uuidPattern.test(p.id) && p.enabled !== false && !reserved.has(p.id))};
  }
  async function mutate(kind, selection = {}) {
    if (!owner || !canOperate() || reading || acting) return;
    const token = epoch, storageKey = key();
    acting = true; error = ''; emit();
    try {
      await serialize(storageKey, async () => {
        if (!live(token) || !await load() || !live(token)) return;
        ensure(!held(), bindingMessages.MANUAL_RECIPE_ACTIVE);
        let pending = journal();
        if (kind === 'discard') {
          ensure(pending?.refused, 'Une demande incertaine doit conserver sa clé.');
          save(null); return;
        }
        if (kind === 'resume') ensure(pending && !pending.refused);
        else {
          ensure(!pending, 'Vérifiez la demande précédente avant une nouvelle association.');
          ensure(selection.revision === snapshot.catalog.revision, bindingMessages.CONFIGURATION_CHANGED);
          if (kind === 'add') {
            const available = choices();
            ensure(available.devices.some(d => d.device_id === selection.device_id) &&
              available.profiles.some(p => p.id === selection.profile_id), 'Choisissez un appareil et un profil disponibles.');
            pending = {kind, body: {client_key: uuid(), device_id: selection.device_id,
              profile_id: selection.profile_id, revision: selection.revision, platform: 'Facebook'}};
          } else {
            ensure(kind === 'remove' && selection.confirmed === true &&
              snapshot.bindings.bindings.some(b => b.id === selection.id && b.active), 'Confirmez le retrait de cette association.');
            pending = {kind, id: selection.id, body: {revision: selection.revision}};
          }
          save(pending); // Persist before the POST, including across reload or a lost response.
        }
        if (!live(token) || !canOperate()) return;
        try {
          await request(pending.kind === 'add' ? endpoint : `${endpoint}/${encodeURIComponent(pending.id)}/remove`,
            {method: 'POST', body: pending.body});
        } catch (failure) {
          if (!live(token)) return;
          if (refusedCodes.has(failure.code)) save({...pending, refused: failure.code});
          error = bindingMessages[failure.code] || 'Résultat à vérifier. La même demande est conservée, sans nouvel envoi automatique.';
        }
        if (live(token)) {
          const message = error;
          await load();
          if (live(token) && journal()) error ||= message || 'La demande reste à vérifier.';
        }
      });
    } catch (failure) {
      if (live(token)) error = failure.message || 'Action indisponible. Actualisez la liste.';
    } finally { if (live(token)) { acting = false; emit(); } }
  }
  return {session, load, mutate, view, choices, render: emit};
}
