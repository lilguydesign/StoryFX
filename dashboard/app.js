import { request, PilotError } from "./api.js";
import { demoData } from "./demo.js";
import { renderMetrics, renderDevices, renderJobs, renderImport, dateLabel } from "./views.js";
import { mountControl, loadControl, enableControl } from './control.js';
import { controlTitles } from './control-fields.js';

const state = { data: null, demo: false, authenticated: false, busy: false, session: 0 };
const find = selector => document.querySelector(selector);
const titles = { overview: "Vue d’ensemble", devices: "Appareils", activity: "Activité", migration: "Migration", library: "Bibliothèque", ...controlTitles };
function notice(message, error = false) {
  find("#notice").textContent = message;
  find("#notice").classList.toggle("error", error);
  find("#notice").hidden = !message;
}
function operational() { return state.authenticated && !state.demo && !state.busy; }
function render() {
  renderMetrics(state.data);
  renderDevices(state.data, operational());
  renderJobs(state.data, operational());
  document.querySelectorAll("[data-action]").forEach(button => { button.disabled = !operational(); });
  find("#refresh-button").disabled = !operational();
  find("#import-button").disabled = !operational();
  find("#login-button").disabled = state.busy;
  find("#login-button").hidden = state.authenticated;
  find("#logout-button").hidden = !state.authenticated;
  find("#logout-button").disabled = state.busy;
  find("#demo-button").textContent = state.demo ? "Quitter la démonstration" : "Voir la démonstration ↗";
  const banner = find("#environment-banner");
  banner.classList.toggle("demo", state.demo);
  banner.querySelector("strong").textContent = state.demo ? "Données de démonstration" : "Pilote privé · Internet";
  banner.querySelector("span:last-child").textContent = state.demo ? "Aperçu fictif en lecture seule. Aucun appareil réel n’est connecté à cette vue." : "Commandes via Windows ou le pilote Android WhatsApp images activé sur le téléphone. Synchronisation des albums en dernier.";
  find("#connection-label").textContent = state.demo ? "◌ Démonstration" : state.authenticated ? "● Session propriétaire" : "○ Session inactive";
  find("#last-refresh").textContent = state.demo ? "Données fictives · aucun accès au serveur" : state.data?.server_time ? `Dernière lecture · ${dateLabel(state.data.server_time)}` : "Aucune donnée serveur chargée";
}
function section(name) {
  if (!Object.hasOwn(titles, name)) return;
  document.querySelectorAll(".section-pane").forEach(pane => { pane.hidden = pane.id !== `pane-${name}`; });
  document.querySelectorAll(".nav-item").forEach(button => {
    const active = button.dataset.section === name;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  find("#section-title").textContent = titles[name];
}
function disconnect() {
  state.session += 1;
  state.authenticated = false;
  state.demo = false;
  state.data = null;
  enableControl(false);
  find("#pair-code").textContent = "";
  find("#pair-dialog").close();
  find("#diagnostic-dialog").close();
  find("#revoke-dialog").close();
  find("#cancel-dialog").close();
  find("#import-result").textContent = "";
  render();
}
function failed(error) {
  if (error instanceof PilotError && error.kind === "unauthorized") { disconnect(); location.replace("/login/"); }
  notice(error instanceof PilotError ? error.message : "L’action n’a pas pu être terminée. Réessayez après actualisation.", true);
}
async function refresh() {
  const session = state.session;
  const data = await request("/v1/dashboard");
  if (session !== state.session) return;
  if (data?.mode !== "diagnostic_only" || !Array.isArray(data.devices) || !Array.isArray(data.jobs)) throw new PilotError("forbidden");
  state.data = data;
  await loadControl();
}
async function action(work) {
  if (!operational()) return;
  state.busy = true;
  notice("");
  render();
  try { await work(); }
  catch (error) { failed(error); }
  finally { state.busy = false; render(); }
}

mountControl(notice);
find("#session-form").addEventListener("submit", event => {
  event.preventDefault(); location.assign("/login/");
});
find("#logout-button").addEventListener("click", () => action(async () => {
  await request("/v1/auth/logout", { method: "POST", body: {} });
  disconnect(); location.replace("/login/");
}));
find("#demo-button").addEventListener("click", () => {
  if (state.busy) return;
  const enter = !state.demo;
  disconnect();
  state.demo = enter;
  state.data = enter ? demoData() : null;
  notice("");
  render();
});
find("#theme-toggle").addEventListener("click", () => {
  const light = document.documentElement.dataset.theme !== "light";
  document.documentElement.dataset.theme = light ? "light" : "dark";
  find("#theme-toggle").setAttribute("aria-label", `Activer le thème ${light ? "sombre" : "clair"}`);
  find("#theme-toggle").textContent = light ? "☾" : "☼";
});
document.querySelectorAll("[data-section], [data-go]").forEach(button => button.addEventListener("click", () => section(button.dataset.section || button.dataset.go)));
find("#status-filter").addEventListener("change", () => renderJobs(state.data, operational()));
find("#refresh-button").addEventListener("click", () => action(async () => { await refresh(); notice("Les données du pilote ont été actualisées."); }));
find("#import-button").addEventListener("click", () => action(async () => {
  const preview = await request("/v1/import-preview", { method: "POST", body: {} });
  if (preview.dry_run !== true || preview.activation_allowed !== false) throw new PilotError("forbidden");
  renderImport(preview);
}));
document.querySelectorAll('[data-action="pair"]').forEach(button => button.addEventListener("click", () => action(async () => {
  find("#pair-code").textContent = "Compte FormaFX";
  find("#pair-expiry").textContent = "Dans StoryFX Android, choisissez Connecter mon compte, puis validez ce téléphone.";
  find("#pair-dialog").showModal();
})));
document.querySelectorAll('[data-action="diagnostic"]').forEach(button => button.addEventListener("click", () => {
  if (!operational()) return;
  const devices = state.data.devices.filter(device => !device.revoked);
  if (!devices.length) { notice("Associez d’abord un appareil au pilote."); return; }
  const select = find("#diagnostic-device");
  select.replaceChildren(...devices.map(device => new Option(device.name, device.id)));
  const local = new Date(Date.now() + 60000);
  local.setMinutes(local.getMinutes() - local.getTimezoneOffset());
  find("#diagnostic-time").value = local.toISOString().slice(0, 16);
  find("#diagnostic-dialog").showModal();
}));
find("#diagnostic-form").addEventListener("submit", event => {
  event.preventDefault();
  action(async () => {
    const scheduled = new Date(find("#diagnostic-time").value);
    if (Number.isNaN(scheduled.valueOf())) throw new PilotError("invalid");
    await request("/v1/diagnostics", { method: "POST", body: {
      device_id: find("#diagnostic-device").value,
      scheduled_at: scheduled.toISOString(),
      expires_at: new Date(scheduled.valueOf() + 30 * 60000).toISOString(),
    } });
    find("#diagnostic-dialog").close();
    await refresh();
    notice("La tâche de diagnostic a été enregistrée. Elle attend la récupération par l’agent.");
  });
});
let revocationTarget = null;
let cancellationTarget = null;
find("#device-cards").addEventListener("click", event => {
  const button = event.target.closest("[data-revoke]");
  if (!button || !operational()) return;
  revocationTarget = state.data.devices.find(device => device.id === button.dataset.revoke);
  if (!revocationTarget) return;
  find("#revoke-name").textContent = revocationTarget.name;
  find("#revoke-dialog").showModal();
});
find("#confirm-revoke").addEventListener("click", () => {
  if (!revocationTarget || !operational()) return;
  const id = revocationTarget.id;
  action(async () => {
    await request(`/v1/devices/${encodeURIComponent(id)}/revoke`, { method: "POST", body: {} });
    find("#revoke-dialog").close();
    revocationTarget = null;
    await refresh();
    notice("L’accès de l’appareil a été révoqué.");
  });
});
document.querySelectorAll("#recent-jobs, #all-jobs").forEach(table => table.addEventListener("click", event => {
  const button = event.target.closest("[data-cancel]");
  if (!button || !operational()) return;
  cancellationTarget = state.data.jobs.find(job => job.id === button.dataset.cancel);
  if (!cancellationTarget) return;
  find("#cancel-name").textContent = `Test de liaison · ${String(cancellationTarget.id).slice(0, 12)}`;
  find("#cancel-dialog").showModal();
}));
find("#confirm-cancel").addEventListener("click", () => {
  if (!cancellationTarget || !operational()) return;
  const id = cancellationTarget.id;
  action(async () => {
    await request(`/v1/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST", body: {} });
    find("#cancel-dialog").close();
    cancellationTarget = null;
    await refresh();
    notice("La tâche de diagnostic a été annulée.");
  });
});
window.addEventListener("pagehide", disconnect);
setInterval(() => {
  if (operational() && document.visibilityState === "visible") action(refresh);
}, 30000);
if (new URLSearchParams(window.location.search).get("demo") === "1") {
  state.demo = true;
  state.data = demoData();
}
render();

if (!state.demo) {
  state.busy = true;
  request("/v1/auth/session").then(async session => {
    find("#session-help").textContent = `Connecté avec ${session.user.email}. Accès propriétaire FormaFX actif.`;
    await refresh(); state.authenticated = true; enableControl(true);
  }).catch(() => location.replace("/login/")).finally(() => { state.busy = false; render(); });
}
