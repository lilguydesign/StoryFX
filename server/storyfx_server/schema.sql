CREATE TABLE IF NOT EXISTS devices (
 id TEXT PRIMARY KEY, installation_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 android_version TEXT NOT NULL, credential_hash TEXT NOT NULL UNIQUE,
 revoked INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, last_seen REAL,
 battery_percent INTEGER, screen_locked INTEGER NOT NULL DEFAULT 1,
 executor TEXT NOT NULL DEFAULT 'diagnostic', app_version TEXT
);
CREATE TABLE IF NOT EXISTS pairings (
 code_hash TEXT PRIMARY KEY, expires_at REAL NOT NULL, used_at REAL
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, occurrence_key TEXT NOT NULL UNIQUE,
 device_id TEXT NOT NULL REFERENCES devices(id), kind TEXT NOT NULL CHECK(kind='diagnostic'),
 status TEXT NOT NULL, scheduled_at REAL NOT NULL, expires_at REAL NOT NULL,
 created_at REAL NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
 lease_hash TEXT, lease_expires_at REAL, last_event_at REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_device ON jobs(device_id)
 WHERE status IN ('CLAIMED', 'STARTED');
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
 device_id TEXT NOT NULL REFERENCES devices(id), payload_hash TEXT NOT NULL,
 stage TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS throttles (
 bucket TEXT PRIMARY KEY, window_start REAL NOT NULL, count INTEGER NOT NULL
);
