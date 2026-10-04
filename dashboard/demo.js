export function demoData() {
  const now = Date.now();
  const iso = minutes => new Date(now + minutes * 60000).toISOString();
  return {
    mode: "diagnostic_only",
    server_time: iso(0),
    devices: [
      { id: "demo-s23", name: "Galaxy S23 · Démonstration", last_seen: iso(-1), battery_percent: 86, screen_locked: false, revoked: false, executor: "diagnostic_only" },
      { id: "demo-s20", name: "Galaxy S20 · Démonstration", last_seen: iso(-4), battery_percent: 64, screen_locked: true, revoked: false, executor: "diagnostic_only" },
      { id: "demo-spare", name: "Appareil secondaire · Démonstration", last_seen: iso(-90), battery_percent: 43, screen_locked: false, revoked: false, executor: "diagnostic_only" },
    ],
    jobs: [
      { id: "demo-task-01", device_id: "demo-s23", kind: "diagnostic", status: "DIAGNOSTIC_CONFIRMED", scheduled_at: iso(-5), expires_at: iso(25), created_at: iso(-6), attempt: 1 },
      { id: "demo-task-02", device_id: "demo-s20", kind: "diagnostic", status: "QUEUED", scheduled_at: iso(15), expires_at: iso(45), created_at: iso(-3), attempt: 0 },
      { id: "demo-task-03", device_id: "demo-spare", kind: "diagnostic", status: "NEEDS_REVIEW", scheduled_at: iso(-50), expires_at: iso(-20), created_at: iso(-55), attempt: 1 },
    ],
    metrics: { devices: 3, total_jobs: 3, completed: 1, waiting: 1, needs_review: 1 },
  };
}
