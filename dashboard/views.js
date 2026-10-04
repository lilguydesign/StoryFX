const statuses = {
  QUEUED: ["En attente", "waiting"], CLAIMED: ["Réservée", "running"],
  STARTED: ["En cours", "running"], DIAGNOSTIC_CONFIRMED: ["Diagnostic confirmé", ""],
  NEEDS_REVIEW: ["À vérifier", "error"], EXPIRED: ["Expirée", "muted"], CANCELLED: ["Annulée", "muted"],
};
export const escape = value => String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
const count = value => Number.isSafeInteger(value) && value >= 0 ? value.toLocaleString("fr-FR") : "—";
export function dateLabel(value) {
  const date = new Date(value);
  return value && !Number.isNaN(date.valueOf()) ? date.toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "Non renseigné";
}
function recent(device) { return device.last_seen && Date.now() - new Date(device.last_seen).valueOf() < 120000; }
function battery(device) {
  return Number.isInteger(device.battery_percent) && device.battery_percent >= 0 && device.battery_percent <= 100 ? `${device.battery_percent} %` : "Non renseignée";
}
function deviceState(device) {
  if (device.revoked) return '<span class="badge error">Accès révoqué</span>';
  if (device.screen_locked === true) return '<span class="badge waiting">Écran verrouillé</span>';
  return recent(device) ? '<span class="badge">Contact récent</span>' : '<span class="badge muted">Contact ancien</span>';
}
function empty(title, description) { return `<div class="empty-state"><strong>${escape(title)}</strong>${escape(description)}</div>`; }

export function renderMetrics(data) {
  const values = data?.metrics || {};
  const definitions = [
    ["Appareils associés", values.devices, "▯", "Identités d’installation", ""],
    ["Tâches enregistrées", values.total_jobs, "≋", "Historique du pilote", ""],
    ["Diagnostics confirmés", values.completed, "✓", "Liaison validée par l’agent", ""],
    ["Résultats à vérifier", values.needs_review, "!", "Attention requise", "metric-review"],
  ];
  document.querySelector("#metrics").innerHTML = definitions.map(([label, value, icon, note, extra]) => `<article class="metric ${extra}"><div class="metric-top"><span>${label}</span><span class="metric-icon" aria-hidden="true">${icon}</span></div><div class="metric-value">${count(value)}</div><div class="metric-bottom">${note}</div></article>`).join("");
  document.querySelector("#nav-devices").textContent = count(values.devices);
}

export function renderDevices(data, operational) {
  const devices = Array.isArray(data?.devices) ? data.devices : [];
  document.querySelector("#device-preview").innerHTML = devices.length ? devices.slice(0, 3).map(device => `<article class="device-row"><span class="phone-icon" aria-hidden="true">▯</span><div class="device-info"><strong class="device-name">${escape(device.name)}</strong><div class="device-sub">Dernier contact : ${escape(dateLabel(device.last_seen))}</div></div><div class="device-meta">${deviceState(device)}<span>Batterie · ${battery(device)}</span></div></article>`).join("") : empty("Aucun appareil chargé", "Connectez-vous ou ouvrez la démonstration pour découvrir le pilote.");
  document.querySelector("#device-cards").innerHTML = devices.length ? devices.map(device => `<article class="panel device-card"><div class="device-card-top"><span class="phone-icon" aria-hidden="true">▯</span>${deviceState(device)}</div><h2>${escape(device.name)}</h2><dl><dt>Dernier contact</dt><dd>${escape(dateLabel(device.last_seen))}</dd><dt>Batterie</dt><dd>${battery(device)}</dd><dt>Écran</dt><dd>${device.screen_locked === true ? "Verrouillé" : device.screen_locked === false ? "Déverrouillé" : "Non renseigné"}</dd><dt>Exécuteur</dt><dd>${["diagnostic", "diagnostic_only"].includes(device.executor) ? "Diagnostic uniquement" : "Non validé"}</dd></dl><button class="button secondary" data-revoke="${escape(device.id)}" ${!operational || device.revoked ? "disabled" : ""}>${device.revoked ? "Accès révoqué" : "Révoquer l’accès"}</button></article>`).join("") : empty("Vos appareils apparaîtront ici", "Enrôlez un agent Android pour associer un appareil à cet espace.");
}

function jobTable(jobs, devices, operational) {
  if (!jobs.length) return empty("Aucune tâche à afficher", "Les diagnostics et leurs résultats apparaîtront dans cet historique.");
  const names = new Map(devices.map(device => [device.id, device.name]));
  const rows = jobs.map(job => {
    const [label, color] = statuses[job.status] || ["État inconnu", "muted"];
    const kind = job.kind === "diagnostic" ? "Test de liaison" : "Type non disponible";
    const cancellable = job.kind === "diagnostic" && ["QUEUED", "CLAIMED", "STARTED", "NEEDS_REVIEW"].includes(job.status);
    const control = cancellable ? `<button class="text-button cancel-task" data-cancel="${escape(job.id)}" ${operational ? "" : "disabled"}>Annuler</button>` : "—";
    return `<tr><td><strong>${kind}</strong><span class="task-sub">${escape(String(job.id).slice(0, 12))}</span></td><td>${escape(names.get(job.device_id) || "Appareil non renseigné")}</td><td>${escape(dateLabel(job.scheduled_at))}</td><td><span class="badge ${color}">${label}</span></td><td>${count(job.attempt)}</td><td>${control}</td></tr>`;
  }).join("");
  return `<table><caption class="visually-hidden">Tâches de diagnostic et états remontés par le serveur</caption><thead><tr><th scope="col">Tâche</th><th scope="col">Appareil</th><th scope="col">Programmation</th><th scope="col">État</th><th scope="col">Tentatives</th><th scope="col">Action</th></tr></thead><tbody>${rows}</tbody></table>`;
}

export function renderJobs(data, operational = false) {
  const jobs = Array.isArray(data?.jobs) ? data.jobs : [];
  const devices = Array.isArray(data?.devices) ? data.devices : [];
  const filter = document.querySelector("#status-filter").value;
  document.querySelector("#recent-jobs").innerHTML = jobTable(jobs.slice(0, 6), devices, operational);
  document.querySelector("#all-jobs").innerHTML = jobTable(jobs.filter(job => filter === "all" || job.status === filter), devices, operational);
}

export function renderImport(preview) {
  const labels = { profiles: "Profils historiques", enabled_devices: "Appareils activés", disabled_devices: "Appareils désactivés", systems: "Systèmes référencés", matrix_rows: "Lignes de programmation", albums: "Albums référencés", preview_jobs: "Tâches dans l’aperçu", warnings_count: "Points à vérifier" };
  const raw = preview?.stats || {};
  const stats = { ...raw, profiles: raw.profiles ?? raw.profiles_total, enabled_devices: raw.enabled_devices ?? raw.profiles_enabled, preview_jobs: raw.preview_jobs ?? raw.jobs_preview, warnings_count: raw.warnings_count ?? (Array.isArray(preview?.warnings) ? preview.warnings.length : undefined) };
  const entries = Object.entries(labels).filter(([key]) => Number.isSafeInteger(stats[key]) && stats[key] >= 0);
  const result = document.querySelector("#import-result");
  if (!entries.length) {
    result.textContent = "Aperçu reçu. Aucun compteur compatible n’est disponible.";
    return;
  }
  result.innerHTML = `<div class="import-stats">${entries.map(([key, label]) => `<div class="import-stat"><strong>${count(stats[key])}</strong><span>${label}</span></div>`).join("")}</div><p class="helper">Lecture seule effectuée. Aucune activation et aucune publication.</p>`;
}
