# Native unlock during a paused manual recipe

The Windows/USB publication scheduler remains paused throughout this validation.
Previously the native unlock permission required an enabled scheduler, even when
the owner had explicitly started an Android manual recipe. A locked phone therefore
could not reach the ready state needed for the first explicit publication.

The read-only permission now recognizes the first step of the exact owner's active
Android recipe for 90 seconds after its explicit start. An idempotent repeated start
does not renew this window. It requires the unchanged catalog revision, the exact
bound profile, a fresh device heartbeat, Android 0.4.18 or newer, the existing media
capabilities, no installation hold, no pending publication or diagnostic job, a
disabled scheduler, and a READY recipe with no requested steps. An active recipe
that fails these guards cannot fall back to scheduled unlock permission.

The existing authenticated owner, agent binding, device revocation, global opt-in,
locally encrypted PIN and one-attempt native unlock guards remain in force. The API
returns only a boolean; it never reads a PIN, queues work, publishes, changes a
binding, changes a scheduler or retries an uncertain receipt. Publication still
requires a separate explicit manual step launch on an unlocked, ready phone.

Scope: WhatsApp first-step validation only. This change provides no Facebook,
account identity, sleep, network-switch or autonomous scheduling validation.

Rollback: restore the previous committed backend release. No schema change or
data rewrite is needed. Retain all recipe, job, receipt and installation-hold audit
records. The installed APK does not need changing for this permission correction.

Synthetic tests cover inert reads, draft/start/cancel/release, expiry, clock rollback,
owner revocation, profile/revision changes, missing capabilities, stale heartbeat,
already requested/uncertain steps, installation exclusion and cooldown. Physical
unlock and the remaining large-lot publication require separate recorded evidence.
