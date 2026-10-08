import assert from 'node:assert/strict';
import { createRecipeClient } from '../dashboard/recipe-client.js';
import { canLaunch, eligibleRow, eligibleRows, expectedMedia } from '../dashboard/recipe-model.js';
import { renderRecipeView } from '../dashboard/recipe-view.js';

const row = { id: '10000000-0000-4000-8000-000000000001', name: 'Validation technique', device: 'Validation technique',
  platform: 'WhatsApp', engine: 'intro+multi', count: 11, album: 'Introduction synthétique', album2: 'Lot synthétique', enabled: true };
const recipeId = '20000000-0000-4000-8000-000000000002', stepId = '30000000-0000-4000-8000-000000000003';
const snapshot = { revision: 3, collections: { matrix: [row], profiles: [{ name: row.device, enabled: true }] } };
const step = { id: stepId, publication: row, expected_media_count: 12, job_id: null, verified: false, state: 'PENDING' };
const recipe = { id: recipeId, state: 'READY', lock_held: true, next_step_id: stepId, steps: [step] };
assert.equal(expectedMedia(row), 12);
assert.equal(expectedMedia({ ...row, engine: 'intro', count: 30 }), 1);
assert.equal(expectedMedia({ ...row, engine: 'multi', count: 30 }), 30);
for (const change of [{ engine: 'intro+multi', count: 30 }, { count: 0 }, { count: '3' }, { engine: 'unknown' }])
  assert.equal(expectedMedia({ ...row, ...change }), null);
for (const change of [{ platform: 'Facebook' }, { enabled: false }, { page: 'CM' }, { page_name: 'Page' }, { album: '' }])
  assert.equal(eligibleRow({ ...row, ...change }), false);
assert.deepEqual(eligibleRows({ ...snapshot, collections: { ...snapshot.collections, profiles: [{ name: row.device, enabled: false }] } }), []);
assert.equal(canLaunch(recipe), true);
for (const state of ['DRAFT', 'DRAINING', 'IN_PROGRESS', 'COOLDOWN', 'BLOCKED', 'PASSED', 'CANCELLED', 'RELEASED'])
  assert.equal(canLaunch({ ...recipe, state, next_allowed_at: '2000-01-01T00:00:00Z' }), false, 'Elapsed local time must never authorize a step');
for (const change of [{ external_pending: true }, { lock_held: false }, { block_reason: 'RECIPE_BLOCKED' }, { steps: [{ ...step, job_id: 'job' }] }])
  assert.equal(canLaunch({ ...recipe, ...change }), false);
const html = renderRecipeView({ snapshot, recipes: [recipe], selectedId: recipeId, active: true });
assert.match(html, /12 média\(s\) au total/);
assert.match(html, /Facebook : adaptateur natif indisponible/);
assert.match(html, /non vérifiable par ce serveur/);
assert.match(html, /aucun renvoi automatique/);
assert.match(renderRecipeView({ snapshot: { ...snapshot, collections: { ...snapshot.collections, matrix: [{ ...row, name: '<script>unsafe</script>' }] } }, active: true }), /&lt;script&gt;/);
assert.match(renderRecipeView({ recipes: [{ ...recipe, state: 'COOLDOWN' }], selectedId: recipeId, active: true }), /data-recipe-action="launch" disabled/);

const memory = new Map();
const storage = { getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value) };
let calls = [], sequence = 0, lostDraft = true, lostLaunch = true, draft = null, job = null;
const fakeRequest = async (path, options = {}) => {
  calls.push({ path, ...structuredClone(options) });
  if (!options.method) return path.endsWith(recipeId) ? (draft || recipe) : { recipes: draft ? [draft] : [], active_recipe_id: null };
  if (path === '/v1/control/recipes') {
    draft ||= { ...recipe, state: 'DRAFT', lock_held: false, client_key: options.body.client_key };
    assert.equal(options.body.client_key, draft.client_key);
    if (lostDraft) { lostDraft = false; throw Error('Synthetic response lost after draft commit'); }
    return draft;
  }
  if (path.endsWith('/launch')) {
    job ||= { job_id: 'job-one', key: options.body.client_key };
    assert.equal(options.body.client_key, job.key);
    if (lostLaunch) { lostLaunch = false; throw Error('Synthetic response lost after job commit'); }
    return { ...job, recipe: { ...recipe, state: 'IN_PROGRESS', steps: [{ ...step, job_id: job.job_id }] } };
  }
  return recipe;
};
const options = { request: fakeRequest, storage, owner: 'owner-one', uuid: () => `40000000-0000-4000-8000-${String(++sequence).padStart(12, '0')}` };
let client = createRecipeClient(options);
await client.list(); await client.detail(recipeId);
assert.equal(calls.filter(call => call.method === 'POST').length, 0);
await assert.rejects(client.create(3, [row.id]));
assert.throws(() => client.recomposeDraft(), /reste à vérifier/, 'An ambiguous timeout never authorizes a new draft key');
const storedDraft = client.journal().draft;
client = createRecipeClient(options); // Reload: the original request body must survive.
await client.create(999, ['different-row']);
const drafts = calls.filter(call => call.path === '/v1/control/recipes' && call.method === 'POST');
assert.deepEqual(drafts[1].body, drafts[0].body);
assert.deepEqual(drafts[0].body, storedDraft);
assert.equal(sequence, 1);
await assert.rejects(client.launch(recipeId, stepId));
client = createRecipeClient(options);
const beforeRead = calls.filter(call => call.method === 'POST').length;
client.reconcile([{ ...recipe, state: 'READY' }]);
await client.list(); await client.detail(recipeId);
assert.equal(calls.filter(call => call.method === 'POST').length, beforeRead, 'Reads never replay a pending publication');
assert.equal(client.journal().pending, `${recipeId}:${stepId}`);
await assert.rejects(client.launch(recipeId, 'other-step'), /précédente/);
await client.launch(recipeId, stepId);
assert.equal(client.journal().pending, null);
const launches = calls.filter(call => call.path.endsWith('/launch'));
assert.equal(launches.length, 2);
assert.deepEqual(launches[0].body, launches[1].body);
assert.equal(job.job_id, 'job-one');
assert.equal(sequence, 1, 'A step key cannot change between tabs or reloads');
assert.deepEqual(createRecipeClient({ ...options, owner: 'owner-two' }).journal(), { draft: null, launches: {}, pending: null });
assert.doesNotMatch([...memory.values()].join(''), /synthétique|Validation technique/);

const reject = createRecipeClient({ ...options, request: async () => { throw Error('RECIPE_COOLDOWN'); } });
await assert.rejects(reject.launch(recipeId, stepId));
reject.reconcile([{ ...recipe, state: 'BLOCKED' }]);
assert.equal(reject.journal().pending, `${recipeId}:${stepId}`);
reject.reconcile([{ ...recipe, state: 'CANCELLED' }]);
assert.equal(reject.journal().pending, null, 'Reliable cancelled state forbids future launch and releases local pending');
assert.equal(reject.journal().launches[`${recipeId}:${stepId}`], stepId, 'Cancellation never rotates a publication key');
assert.equal(calls.filter(call => call.method === 'POST').length, beforeRead + 1, 'Reconciliation never sends');
await assert.rejects(reject.create(4, [row.id]));
assert.equal(reject.journal().draft.revision, 4, 'A rejected then cancelled step cannot permanently block future drafts');

let attempted = 0;
const blocked = createRecipeClient({ ...options, storage: { getItem: () => null, setItem: () => { throw Error('Unavailable storage'); } },
  request: async () => { attempted++; } });
await assert.rejects(blocked.create(3, [row.id]));
await assert.rejects(blocked.launch(recipeId, stepId));
assert.equal(attempted, 0, 'Never send if an idempotency key cannot be persisted first');
const stale = createRecipeClient({ ...options, owner: 'owner-stale', request: async () => { throw Object.assign(Error('Changed'), { code: 'CONFIGURATION_CHANGED' }); } });
await assert.rejects(stale.create(3, [row.id]));
assert.equal(stale.journal().draft_refused, 'CONFIGURATION_CHANGED');
stale.recomposeDraft();
assert.equal(stale.journal().draft, null);
await assert.rejects(stale.create(4, [row.id]));
assert.equal(stale.journal().draft.revision, 4, 'A definite pre-creation refusal permits an explicit new draft');
console.log('manual recipes: eligibility, proof gates, owner isolation, lost receipts and safe cancellation passed');
