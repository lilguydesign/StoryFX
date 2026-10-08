// Synthetic browser smoke. Every browser request is intercepted; no API or phone is contacted.
// node --experimental-default-type=module tests/test_manual_recipe_ui.mjs <path-to-playwright>
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, mkdir, mkdtemp } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2] || 'playwright');
const dashboard = new URL('../dashboard/', import.meta.url);
const output = new URL('../.runtime/manual-recipe-ui/', import.meta.url);
const origin = 'http://127.0.0.1:47771';
const row = { id: '10000000-0000-4000-8000-000000000001', name: 'Validation technique', device: 'Validation technique',
  platform: 'WhatsApp', system: 'Validation technique', engine: 'intro+multi', count: 11,
  album: 'Introduction synthétique', album2: 'Lot synthétique', enabled: true };
const recipeId = '20000000-0000-4000-8000-000000000002', stepId = '30000000-0000-4000-8000-000000000003';
const secondStep = '30000000-0000-4000-8000-000000000004';
const secondRow = { ...row, id: '10000000-0000-4000-8000-000000000005' };
const extraRows = [6, 7, 8].map(index => ({ ...row, id: `10000000-0000-4000-8000-00000000000${index}` }));
let owner = 'owner-one', recipe = null, job = null, loseLaunch = true, loseDraft = true;
const posts = [], errors = [];
await mkdir(output, { recursive: true });
const profile = await mkdtemp(fileURLToPath(new URL('edge-profile-', output)));
const context = await chromium.launchPersistentContext(profile, { channel: 'msedge', headless: true,
  viewport: { width: 1440, height: 1080 } });
const page = await context.newPage();
page.on('pageerror', error => errors.push(error.message));
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url()), path = url.pathname;
  if (url.origin !== origin) { await route.abort(); return; }
  const json = value => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(value) });
  if (path.startsWith('/v1/')) {
    const body = request.postDataJSON();
    if (request.method() === 'POST') posts.push({ path, body });
    if (path === '/v1/auth/session') return json({ authenticated: true, access: 'formafx_active_owner', user: { id: owner, email: 'validation@example.invalid' } });
    if (path === '/v1/auth/logout') return json({});
    if (path === '/v1/control/android/profile-bindings' && request.method() === 'GET') return json({revision: 3,
      devices: [], primary_profile_ids: [], bindings: [], capabilities: {facebook: {ready: false, reason: 'ADAPTER_NOT_VALIDATED'}}});
    if (path === '/v1/dashboard') return json({ mode: 'diagnostic_only', devices: [], jobs: [], metrics: {} });
    if (path === '/v1/control') return json({ revision: 3, server_time: '2026-10-08T12:00:00Z', nodes: [], reports: [], terminal: [],
      scheduler: { enabled: false, dispatch_held: Boolean(recipe?.lock_held && owner === 'owner-one') },
      collections: { profiles: owner === 'owner-one' ? [{ id: row.id, name: row.device, enabled: true }] : [],
        matrix: owner === 'owner-one' ? [row, secondRow, ...extraRows, { ...row, id: 'facebook-row', platform: 'Facebook' }] : [],
        pages: [], systems: [], albums: [], locators: [] },
      schedule: [{ ...row, id: 'scheduled-occurrence', local_time: '13:00', state: 'PLANNED', availability: 'READY' }] });
    if (path === '/v1/control/recipes' && request.method() === 'GET')
      return json({ recipes: recipe && owner === 'owner-one' ? [recipe] : [], active_recipe_id: recipe?.lock_held && owner === 'owner-one' ? recipe.id : null });
    if (path === '/v1/control/recipes' && request.method() === 'POST') {
      recipe ||= { id: recipeId, client_key: body.client_key, revision: body.revision, executor: 'android', state: 'DRAFT',
        created_at: '2026-10-08T12:00:00Z', lock_held: false, next_step_id: stepId, external_pending: false, block_reason: null,
        steps: [stepId, secondStep].map((id, index) => ({ id, position: index + 1, row_id: [row, secondRow][index].id, publication: [row, secondRow][index],
          expected_media_count: 12, job_id: null, state: 'PENDING', verified: false })) };
      if (loseDraft) { loseDraft = false; return route.abort(); }
      return json(recipe);
    }
    if (path === `/v1/control/recipes/${recipeId}`) return json(recipe);
    if (path.endsWith('/start')) { recipe.state = 'READY'; recipe.lock_held = true; return json(recipe); }
    if (path.endsWith('/launch')) {
      if (job) assert.equal(body.client_key, job.key, 'No new key may replace a lost receipt');
      job ||= { id: 'only-job', key: body.client_key };
      if (loseLaunch) { loseLaunch = false; return route.abort(); }
      recipe.state = 'IN_PROGRESS'; recipe.steps[0].job_id = job.id;
      return json({ job_id: job.id, occurrence_id: 'synthetic-only', state: 'QUEUED', recipe });
    }
    if (path.endsWith('/cancel')) { recipe.state = 'CANCELLED'; return json(recipe); }
    if (path.endsWith('/release')) { recipe.state = 'RELEASED'; recipe.lock_held = false; return json(recipe); }
    throw Error(`Unexpected synthetic API route ${path}`);
  }
  if (path.startsWith('/login')) return route.fulfill({ contentType: 'text/html', body: '<h1>Connexion de validation</h1>' });
  const relative = path === '/' ? 'index.html' : path.slice(1);
  if (relative.includes('..') || !/^[a-zA-Z0-9_./-]+$/.test(relative)) return route.abort();
  const type = relative.endsWith('.js') ? 'text/javascript' : relative.endsWith('.css') ? 'text/css' : relative.endsWith('.svg') ? 'image/svg+xml' : 'text/html';
  try { return route.fulfill({ contentType: type, body: await readFile(new URL(relative, dashboard)) }); }
  catch { return route.fulfill({ status: 404, body: '' }); }
});
const action = name => page.locator(`[data-recipe-action="${name}"]`);
const waitEnabled = selector => page.waitForFunction(value => {
  const element = document.querySelector(value); return element && !element.disabled;
}, selector);
try {
  await page.goto(origin);
  await page.locator('[data-section="launch"]').click();
  await waitEnabled('[data-recipe-row]');
  const menuCount = await page.locator('.nav-item').count();
  assert.equal(menuCount, 14, 'All five existing overview menus and nine control menus remain');
  assert.equal(await page.locator('[data-recipe-row]').count(), 5, 'No Facebook native choice');
  assert.equal(posts.length, 0, 'Loading cannot start any action');
  await page.locator(`[data-recipe-row="${row.id}"]`).check();
  await page.locator(`[data-recipe-row="${secondRow.id}"]`).check();
  await action('create').click();
  await waitEnabled('[data-recipe-action="start"]');
  assert.equal(posts.length, 1, 'A lost draft receipt is reconciled only by GET');
  await action('start').click();
  assert.equal(await page.locator('#recipe-confirm').isDisabled(), true);
  assert.match(await page.locator('#recipe-dialog').innerText(), /non.*vérification|ne constitue pas une vérification/);
  assert.equal(posts.length, 1, 'Opening a review cannot start the recipe');
  await page.locator('#recipe-pause-ack').check();
  await page.locator('#recipe-confirm').click();
  await waitEnabled('[data-recipe-action="launch"]');
  assert.deepEqual(posts[1].body, {});
  assert.equal(await page.locator('[data-scheduler-action="start"]').isDisabled(), true);
  assert.equal(await page.locator('[data-scheduler-action="catchup"]').isDisabled(), true);
  assert.equal(await page.locator('#control-launch [data-publication]').isDisabled(), true);
  await action('launch').click();
  assert.match(await page.locator('#recipe-review').innerText(), /12 média\(s\) au total/);
  assert.match(await page.locator('#recipe-review').innerText(), /Mon statut WhatsApp/);
  assert.equal(job, null, 'Review must precede a real launch request');
  await page.locator('#recipe-confirm').click();
  await page.waitForFunction(() => document.querySelector('#manual-recipes').textContent.includes('Une réponse de publication manque'));
  await page.reload();
  await page.locator('[data-section="launch"]').click();
  await waitEnabled('[data-recipe-action="launch"]');
  assert.equal(posts.filter(value => value.path.endsWith('/launch')).length, 1, 'Reload cannot replay a lost launch');
  await action('launch').click();
  await page.locator('#recipe-confirm').click();
  await page.waitForFunction(() => document.querySelector('#manual-recipes').textContent.includes('Publication en cours'));
  const launches = posts.filter(value => value.path.endsWith('/launch'));
  assert.equal(launches.length, 2);
  assert.deepEqual(launches[0].body, launches[1].body);
  assert.equal(job.id, 'only-job');
  recipe.state = 'COOLDOWN'; recipe.next_step_id = secondStep;
  recipe.next_allowed_at = '2000-01-01T00:00:00Z'; // Even a past deadline cannot itself launch or enable.
  recipe.steps[0].verified = true; recipe.steps[0].state = 'CONFIRMED';
  recipe.steps[0].completed_at = '2026-10-08T12:00:00Z';
  await action('refresh').click();
  await page.waitForFunction(() => document.querySelector('#manual-recipes').textContent.includes('Intervalle entre les lots'));
  assert.equal(await action('launch').isDisabled(), true);
  const countBeforeClock = posts.length;
  await page.clock.install(); await page.clock.fastForward(310_000);
  assert.equal(posts.length, countBeforeClock, 'Polling and elapsed time cannot POST or advance');
  await mkdir(output, { recursive: true });
  await page.screenshot({ path: fileURLToPath(new URL('desktop-dark.png', output)), fullPage: true });
  await page.locator('#theme-toggle').click();
  await page.screenshot({ path: fileURLToPath(new URL('desktop-light.png', output)), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: fileURLToPath(new URL('mobile-light.png', output)), fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true);
  await page.locator('#theme-toggle').click();
  await page.screenshot({ path: fileURLToPath(new URL('mobile-dark.png', output)), fullPage: true });
  await page.clock.resume();
  await page.setViewportSize({ width: 1440, height: 1080 });
  await waitEnabled('[data-recipe-action="cancel"]');
  await action('cancel').click(); await page.locator('#recipe-confirm').click();
  await waitEnabled('[data-recipe-action="release"]');
  await action('release').click();
  assert.match(await page.locator('#recipe-dialog-description').innerText(), /laisse la programmation arrêtée/);
  await page.locator('#recipe-confirm').click();
  await page.waitForFunction(() => document.querySelector('#manual-recipes').textContent.includes('Recette clôturée'));
  const preparation = page.locator('#manual-recipes details');
  const summary = preparation.locator('summary');
  if (!await preparation.evaluate(element => element.open)) await summary.click();
  const beforeSelection = posts.length;
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 1000));
  for (const value of [row, secondRow, ...extraRows]) {
    const choice = page.locator(`[data-recipe-row="${value.id}"]`);
    await choice.check();
    assert.equal(await preparation.evaluate(element => element.open), true, 'Choosing a row must keep the form open');
    assert.equal(await choice.evaluate(element => document.activeElement === element), true, 'Checkbox focus survives its redraw');
    await page.clock.runFor(30_000);
    await page.waitForFunction(() => !document.querySelector('#refresh-button').disabled);
    assert.equal(await preparation.evaluate(element => element.open), true, 'Server polling must keep the form open');
    assert.equal(await choice.isChecked(), true);
    assert.equal(await choice.evaluate(element => document.activeElement === element), true, 'Polling preserves the same row focus');
  }
  assert.equal(await page.locator('[data-recipe-row]:checked').count(), 5);
  assert.equal(posts.length, beforeSelection, 'Selecting five rows and polling never POSTs');
  await summary.click();
  await page.clock.runFor(30_000);
  await page.waitForFunction(() => !document.querySelector('#refresh-button').disabled);
  assert.equal(await preparation.evaluate(element => element.open), false, 'An intentionally closed form stays closed');
  assert.equal(await summary.evaluate(element => document.activeElement === element), true);
  await page.locator('#theme-toggle').focus();
  await page.clock.runFor(30_000);
  await page.waitForFunction(() => !document.querySelector('#refresh-button').disabled);
  assert.equal(await page.locator('#theme-toggle').evaluate(element => document.activeElement === element), true, 'Polling does not steal focus outside the form');
  await page.evaluate(async () => {
    const { enableControl } = await import('/control.js'); enableControl(false);
  });
  assert.equal(await preparation.evaluate(element => element.open), true, 'Session reset restores the empty form default');
  assert.equal(await page.locator('[data-recipe-row]:checked').count(), 0);
  await page.clock.resume();
  await page.locator('#logout-button').click();
  await page.waitForURL('**/login/');
  owner = 'owner-two'; await page.goto(origin);
  await page.locator('[data-section="launch"]').click();
  await waitEnabled('[data-recipe-action="refresh"]');
  assert.equal(await page.locator('[data-recipe-row]').count(), 0);
  assert.doesNotMatch(await page.locator('#manual-recipes').innerText(), /Introduction synthétique|Publication en cours/);
  assert.equal(posts.filter(value => value.path.endsWith('/launch')).length, 2);
  assert.deepEqual(errors, []);
  console.log('Edge synthetic recipe UI: review, lost receipt, reload, no auto-send, themes/mobile, form polling/focus and account isolation passed');
} finally { await context.close(); }
