// Offline Edge smoke: intercept every request with synthetic data or local source bytes.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile, mkdir, mkdtemp} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const {chromium} = createRequire(import.meta.url)(process.argv[2] || 'playwright');
const source = new URL('../dashboard/', import.meta.url);
const output = new URL('../delivery/android-profile-bindings-ui/', import.meta.url);
const origin = 'http://127.0.0.1:47829';
const id = n => `10000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const device = id(1), primary = id(2), profile = id(3);
let owner = 'owner-a', held = false, lose = 'after', records = [];
const posts = [], errors = [];
await mkdir(output, {recursive: true});
const temporaryProfile = await mkdtemp(fileURLToPath(new URL('edge-profile-', output)));
const context = await chromium.launchPersistentContext(temporaryProfile, {channel: 'msedge', headless: true,
  viewport: {width: 1440, height: 1080}});
const page = await context.newPage();
page.on('pageerror', error => errors.push(error.message));
await context.route('**/*', async route => {
  const req = route.request(), url = new URL(req.url()), path = url.pathname;
  if (url.origin !== origin) return route.abort();
  const json = value => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(value)});
  if (path.startsWith('/v1/')) {
    const ours = owner === 'owner-a';
    if (path === '/v1/auth/session') return json({authenticated: true, user: {id: owner, email: 'validation@example.invalid'}, access: 'formafx_active_owner'});
    if (path === '/v1/auth/logout') return json({});
    if (path === '/v1/dashboard') return json({mode: 'diagnostic_only', devices: ours ? [{id: device, name: 'Validation technique', revoked: false}] : [], jobs: [], metrics: {}});
    if (path === '/v1/control') return json({revision: 3, nodes: [], reports: [], terminal: [], schedule: [],
      scheduler: {enabled: false, dispatch_held: held}, collections: {
        profiles: ours ? [{id: primary, name: 'Principal', enabled: true}, {id: profile, name: 'Validation technique secondaire', enabled: true}] : [],
        albums: [], systems: [], pages: [], locators: [], matrix: []}});
    if (path === '/v1/control/recipes') return json({recipes: [], active_recipe_id: held ? id(9) : null});
    if (path === '/v1/control/android/profile-bindings' && req.method() === 'GET') return json({revision: 3,
      capabilities: {facebook: {ready: false, reason: 'ADAPTER_NOT_VALIDATED'}}, bindings: ours ? records : [],
      primary_profile_ids: ours ? [primary] : [], devices: ours ? [{device_id: device, name: 'Validation technique',
        primary_profile_id: primary, primary_profile: 'Principal', revoked: false}] : []});
    if (path.startsWith('/v1/control/android/profile-bindings') && req.method() === 'POST') {
      const body = req.postDataJSON(); posts.push({path, body});
      assert.equal(held, false);
      if (lose === 'before') { lose = null; return route.abort('failed'); }
      let result;
      if (path.endsWith('/remove')) { result = records.find(b => path.includes(b.id)); result.active = false; }
      else {
        result = records.find(b => b.client_key === body.client_key);
        if (!result) { result = {id: id(records.length + 20), ...body, profile: 'Validation technique secondaire', active: true, enabled: true, ready: false}; records.push(result); }
      }
      if (lose === 'after') { lose = null; return route.abort('failed'); }
      return json(result);
    }
    return route.fulfill({status: 404, contentType: 'application/json', body: '{}'});
  }
  const relative = path === '/' ? 'index.html' : path === '/login/' ? 'login/index.html' : path.slice(1);
  if (relative.includes('..')) return route.abort();
  try {
    const body = await readFile(new URL(relative, source));
    const ext = relative.split('.').pop(), type = {html: 'text/html', js: 'text/javascript', css: 'text/css', svg: 'image/svg+xml', png: 'image/png'}[ext];
    return route.fulfill({status: 200, contentType: type || 'application/octet-stream', body});
  } catch { return route.fulfill({status: 404, body: ''}); }
});
const panel = page.locator('#android-profile-bindings');
const refresh = panel.locator('[data-apb="refresh"]').first();
const waitReady = () => page.waitForFunction(() => {
  const panel = document.querySelector('#android-profile-bindings');
  return panel && !panel.textContent.includes('Vérification des appareils') && !panel.querySelector('[data-apb="refresh"]').disabled;
});
async function selectProfile() {
  await panel.locator('[name="device"]').selectOption(device);
  await panel.locator('[name="profile"]').selectOption(profile);
}
try {
  await page.goto(origin); await page.locator('[data-section="devices"]').click();
  await waitReady();
  assert.match(await panel.innerText(), /Adaptateur Facebook natif non validé/);
  assert.equal(await panel.locator(`[name="profile"] option[value="${primary}"]`).count(), 0);
  await selectProfile();
  await panel.locator('[data-apb-form="add"] button[type="submit"]').click();
  await page.waitForFunction(() => document.querySelector('.apb-history').textContent.includes('Associée'));
  assert.equal(posts.length, 1); assert.equal(await panel.locator('.apb-pending').count(), 0);
  held = true; await refresh.click(); await waitReady();
  assert.equal(await panel.locator('[name="device"]').isDisabled(), true);
  assert.equal(await panel.locator('[name="binding"]').isDisabled(), true);
  held = false; await refresh.click(); await waitReady();
  await panel.locator('[name="binding"]').selectOption(records[0].id);
  assert.equal(await panel.locator('[data-apb-form="remove"] button[type="submit"]').isDisabled(), true);
  await panel.locator('[data-apb-confirm]').check();
  await panel.locator('[data-apb-form="remove"] button[type="submit"]').click();
  await page.waitForFunction(() => document.querySelector('.apb-history').textContent.includes('Retirée'));
  assert.equal(records.length, 1); assert.equal(posts.length, 2);
  lose = 'before'; await selectProfile();
  await panel.locator('[data-apb-form="add"] button[type="submit"]').click();
  await page.waitForFunction(() => document.querySelector('[data-apb="resume"]')?.disabled === false);
  const uncertain = posts[2].body;
  await page.reload(); await page.locator('[data-section="devices"]').click(); await waitReady();
  assert.equal(posts.length, 3, 'Reload never retries');
  await panel.locator('[data-apb="resume"]').click();
  await page.waitForFunction(() => !document.querySelector('.apb-pending'));
  assert.deepEqual(posts[3].body, uncertain);
  await mkdir(output, {recursive: true});
  await page.screenshot({path: fileURLToPath(new URL('desktop-dark.png', output)), fullPage: true});
  await page.locator('#theme-toggle').click();
  await page.screenshot({path: fileURLToPath(new URL('desktop-light.png', output)), fullPage: true});
  await page.setViewportSize({width: 390, height: 844});
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
  await page.screenshot({path: fileURLToPath(new URL('mobile-light.png', output)), fullPage: true});
  await page.locator('#theme-toggle').click();
  await page.screenshot({path: fileURLToPath(new URL('mobile-dark.png', output)), fullPage: true});
  await page.setViewportSize({width: 1440, height: 1080});
  owner = 'owner-b'; await refresh.click();
  await page.waitForFunction(() => document.querySelector('#connection-label').textContent.includes('inactive'));
  assert.doesNotMatch(await panel.innerText(), /Validation technique secondaire/);
  assert.equal(posts.length, 4);
  await page.goto(origin + '/?demo=1'); await page.locator('[data-section="devices"]').click();
  assert.equal(await panel.locator('[name="device"]').isDisabled(), true);
  assert.equal(posts.length, 4); assert.deepEqual(errors, []);
  console.log('Offline Edge UI passed: add, lost reply/reload, stable key, soft removal, lock, account/demo gates, desktop/mobile and both themes.');
} finally { await context.close(); }
