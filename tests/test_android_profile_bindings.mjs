// Synthetic HTTP/storage contracts only. No browser, account or device is contacted.
import assert from 'node:assert/strict';
import {createProfileBindingsModel} from '../dashboard/android-profile-bindings-model.js';
import {renderProfileBindings} from '../dashboard/android-profile-bindings-view.js';

const id = n => `10000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const device = id(1), primary = id(2), profile = id(3), binding = id(4);
function setup() {
  const memory = new Map(), posts = [];
  let owner = 'owner-a', sequence = 10, minted = 0, invalid = 0, postHook = null, getHook = null;
  const catalog = {revision: 3, collections: {profiles: [
    {id: primary, name: 'Principal', enabled: true}, {id: profile, name: 'Validation technique', enabled: true}]}};
  const bindings = {revision: 3, bindings: [], capabilities: {facebook: {ready: false}},
    devices: [{device_id: device, name: 'Validation technique', primary_profile_id: primary,
      primary_profile: 'Principal', revoked: false}], primary_profile_ids: [primary]};
  const recipes = {recipes: [], active_recipe_id: null};
  const stored = {getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value)};
  const row = body => ({id: binding, ...body, active: true, enabled: true, ready: false, profile: 'Validation technique'});
  async function request(path, options = {}) {
    if (path === '/v1/auth/session') return {user: {id: owner}, access: 'formafx_active_owner'};
    if (options.method) {
      posts.push({path, body: structuredClone(options.body)});
      if (postHook) return postHook(path, options.body);
      if (path.endsWith('/remove')) { bindings.bindings[0].active = false; return bindings.bindings[0]; }
      const created = row(options.body); bindings.bindings.push(created); return created;
    }
    if (getHook) { const result = await getHook(path); if (result !== undefined) return result; }
    return structuredClone(path === '/v1/control' ? catalog : path.endsWith('/recipes') ? recipes : bindings);
  }
  const create = () => createProfileBindingsModel({request, storage: stored, canOperate: () => true,
    uuid: () => { minted++; return id(sequence++); }, serialize: async (_key, work) => work(),
    invalidSession: () => invalid++});
  const model = create(); model.session(owner);
  return {model, create, catalog, bindings, recipes, posts, row, memory,
    selection: {revision: 3, device_id: device, profile_id: profile},
    owner: value => { owner = value; }, post: value => { postHook = value; }, get: value => { getHook = value; },
    minted: () => minted, invalid: () => invalid};
}

let cases = 0;
async function test(name, run) { await run(); cases++; console.log(`PASS ${name}`); }

await test('Canonical choices exclude primary and active secondary, never infer device from name', async () => {
  const f = setup(); await f.model.load();
  assert.deepEqual(f.model.choices().profiles.map(p => p.id), [profile]);
  delete f.bindings.devices; await f.model.load();
  assert.equal(f.model.view().mutable, false);
  assert.equal(f.posts.length, 0);
});
await test('Lost response after commit reconciles by fresh GET without another POST or UUID', async () => {
  const f = setup(); await f.model.load();
  f.post((_path, body) => { f.bindings.bindings.push(f.row(body)); throw Error('Synthetic lost response'); });
  await f.model.mutate('add', f.selection);
  assert.equal(f.posts.length, 1); assert.equal(f.minted(), 1); assert.equal(f.model.view().pending, null);
});
await test('Unknown outcome survives reload; only explicit same-body resumption is allowed', async () => {
  const f = setup(); await f.model.load(); f.post(() => { throw Error('Synthetic transport failure'); });
  await f.model.mutate('add', f.selection);
  const original = f.posts[0].body;
  await f.model.mutate('add', f.selection);
  assert.equal(f.posts.length, 1); assert.equal(f.minted(), 1);
  const resumed = f.create(); resumed.session('owner-a'); await resumed.load();
  assert.deepEqual(resumed.view().pending.body, original);
  f.post(null); await resumed.mutate('resume');
  assert.deepEqual(f.posts[1].body, original); assert.equal(f.minted(), 1);
  assert.equal(resumed.view().pending, null);
});
await test('Failed fresh read cannot authorize resumption or erase an uncertain journal', async () => {
  const f = setup(); await f.model.load(); f.post(() => { throw Error('Synthetic response lost'); });
  await f.model.mutate('add', f.selection);
  f.get(() => { throw Error('Synthetic GET failure'); }); await f.model.load();
  assert.equal(f.model.view().mutable, false); assert.ok(f.model.view().pending);
  await f.model.mutate('resume'); assert.equal(f.posts.length, 1);
});
await test('Fresh manual recipe lock blocks association and soft removal before POST', async () => {
  const f = setup(); await f.model.load(); f.recipes.active_recipe_id = id(20);
  await f.model.mutate('add', f.selection);
  assert.equal(f.posts.length, 0); assert.equal(f.minted(), 0); assert.equal(f.model.view().held, true);
});
await test('Removal requires current explicit confirmation and reconciles a lost withdrawal receipt', async () => {
  const f = setup(); f.bindings.bindings.push(f.row({client_key: id(30), device_id: device, profile_id: profile, platform: 'Facebook'}));
  await f.model.load(); await f.model.mutate('remove', {revision: 3, id: binding, confirmed: false});
  assert.equal(f.posts.length, 0);
  f.post(() => { f.bindings.bindings[0].active = false; throw Error('Synthetic withdrawal response lost'); });
  await f.model.mutate('remove', {revision: 3, id: binding, confirmed: true});
  assert.equal(f.posts.length, 1); assert.equal(f.model.view().pending, null);
  assert.equal(f.bindings.bindings.length, 1);
});
await test('Owner changed on the server clears visible data and prevents POST', async () => {
  const f = setup(); await f.model.load(); f.owner('owner-b');
  await f.model.mutate('add', f.selection);
  assert.equal(f.posts.length, 0); assert.equal(f.invalid(), 1);
  assert.equal(f.model.view().snapshot, null); assert.equal(f.model.view().owner, false);
});
await test('An old account read cannot repaint data after an epoch change', async () => {
  const f = setup(); let release, seen;
  const started = new Promise(resolve => { seen = resolve; });
  f.get(path => path === '/v1/control' ? new Promise(resolve => { release = resolve; seen(); }) : undefined);
  const old = f.model.load(); await started;
  f.owner('owner-b'); f.model.session('owner-b'); f.get(null);
  f.catalog.collections.profiles = []; f.bindings.devices = []; f.bindings.primary_profile_ids = [];
  await f.model.load(); release({revision: 3, collections: {profiles: [{id: profile, name: 'OLD PRIVATE VALUE'}]}});
  await old;
  assert.deepEqual(f.model.view().snapshot.catalog.collections.profiles, []);
});
await test('Stale form revision cannot silently target a changed catalog', async () => {
  const f = setup(); await f.model.load(); f.catalog.revision = f.bindings.revision = 4;
  await f.model.mutate('add', f.selection);
  assert.equal(f.posts.length, 0); assert.equal(f.minted(), 0);
});
await test('Definitive refusal retains its key until fresh read and explicit dismissal', async () => {
  const f = setup(); await f.model.load();
  f.post(() => { const e = Error('Synthetic refusal'); e.code = 'CONFIGURATION_CHANGED'; throw e; });
  await f.model.mutate('add', f.selection); assert.equal(f.minted(), 1);
  await f.model.mutate('add', f.selection); assert.equal(f.minted(), 1);
  await f.model.mutate('discard'); assert.equal(f.model.view().pending, null);
  f.post(null); await f.model.mutate('add', f.selection); assert.equal(f.minted(), 2);
});
await test('Demo/inactive gate sends nothing and labels never become HTML', async () => {
  const f = setup(); await f.model.load(); f.model.session(null);
  await f.model.mutate('add', f.selection); assert.equal(f.posts.length, 0);
  const state = {owner: true, mutable: true, snapshot: {bindings: {devices: [], bindings: [
    {device_id: device, profile: '<script>private</script>', active: true, enabled: true}]}}};
  const html = renderProfileBindings(state, {devices: [], profiles: []}, {});
  assert.match(html, /&lt;script&gt;/); assert.doesNotMatch(html, /<script>/);
  assert.match(html, /Adaptateur Facebook natif non validé/); assert.doesNotMatch(html, /data-publication|\/launch/);
});
await test('Unavailable durable storage blocks mutation without breaking initialization', async () => {
  let posts = 0;
  const model = createProfileBindingsModel({request: async (_path, options) => {
    if (options?.method) posts++; return {};
  }, storage: {getItem() { throw Error('Synthetic storage denied'); }}, canOperate: () => true});
  model.session('owner-a');
  assert.equal(model.view().mutable, false);
  assert.match(model.view().error, /journal de reprise/);
  assert.equal(posts, 0);
});
await test('A revoked owner authorization clears previously visible associations', async () => {
  const f = setup(); await f.model.load();
  f.get(() => { const failure = Error('Synthetic authorization revoked'); failure.kind = 'forbidden'; throw failure; });
  await f.model.load();
  assert.equal(f.model.view().snapshot, null); assert.equal(f.model.view().owner, false);
  assert.equal(f.invalid(), 1); assert.equal(f.posts.length, 0);
});
console.log(`${cases} synthetic association tests passed`);
