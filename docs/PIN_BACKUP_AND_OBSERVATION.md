# Android recovery and publication observation

Android 0.4.12 offers explicit save, availability, restore and removal of a
profile PIN in Supabase Vault. The installation must be authenticated, bound
to the requested profile and owned by an active FormaFX principal owner.
The live database gate checks PriceFX, confirmed account and suspension state.
The private reference table is inaccessible to anonymous/authenticated SQL
roles. Only the owner-scoped RPC can access the corresponding Vault secret.
PINs must never be included in CLI arguments, logs, reports, public data,
diagnostics, source, screenshots or archives. Transport uses HTTPS. No
service-role credential is added. A restored PIN does not enable publications
or boot unlock; both consent gates remain independent.

The local encrypted PIN remains the boot-time source. Remote recovery needs
Internet, a valid account session and an associated installation. It cannot
recover a lost installation before the first device unlock and login.

The bounded observer opens SQLite in read-only/query-only mode, performs no
network requests and has no ADB/Appium dependency. Private configuration
selects one owner and explicit profiles, with a maximum seven-day window.
A dedicated server timer runs it every thirty minutes; local Codex reads the
private server artifact when available. Repeated collection in the same slot
is idempotent. The final read includes fifteen minutes of completion tolerance.
After completion, a marker prevents further service execution.

The observer preserves each snapshot, highest retry depth and uncertain
results. It never claims, sends, retries, cancels or changes scheduler state.
Connection is measured using Internet heartbeats with twenty-minute tolerance,
including diagnostics for a phone whose publication channel is disabled.
Unsupported formats and schedules outside the active scheduler are distinct
from send failures. WhatsApp agent confirmation records the configured batch
size; legacy confirmation alone does not prove a Facebook page or image count.
Facebook/TikTok native executors remain unimplemented. USB absence, natural
sleep and network changes are not inferred from a healthy HTTP response.

Installation: deploy a verified committed release, apply the transactional
Vault migration, then run deploy/install_observation.py with private scope
JSON on stdin. Verify an actual observation artifact and timer status.
Rollback: restore the previous StoryFX release; stop/disable only
storyfx-observation.timer if its collector is faulty. Preserve observations,
Vault entries, local PINs and the publication scheduler. Revoke execution of
storyfx_pin_backup_v1 if the new backup endpoint must be withdrawn; do not
delete recovery secrets or broaden Vault grants.
