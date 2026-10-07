# Publication batch verification

The native Android executor shares one `ACTION_SEND_MULTIPLE` intent containing
exactly the configured number of readable image URIs. The WhatsApp recipient
label `1 selected` means one own-status destination, not one image. A job is
confirmed only after the own-status view provides the expected image count.
An uncertain send remains in review and is never automatically repeated.

Android 0.4.11 prepares the provider by dismissing an open notification shade
through Android's dedicated Accessibility action, available from API 31.
It checks that the device is unlocked and that Android advertises the action.
It never substitutes Back in an unknown app or dismisses a keyguard challenge.
A failure here remains a pre-send failure under the existing retry rules.

The legacy Python multi engine now reads Gallery's actual selection counter
after each click. It preserves an initially selected thumbnail, avoids known
selected thumbnails, and refuses non-increasing or ambiguous counters. It never
silently reduces a requested batch to the album's smaller size. Android's share
sheet must then acknowledge the same batch size before a destination is chosen.
An unfamiliar Gallery/share-sheet layout stops the operation for inspection.
These checks prove selection and handoff size, not Facebook delivery or page
identity. Facebook and TikTok still require a separately validated executor.

The bounded maintenance observation retains expected counts and classifications
for confirmed, waiting, late, failed, uncertain and unvalidated planned rows.
Unsupported rows cannot disappear behind successful WhatsApp results. Four
hours of observations do not by themselves prove unplugged natural sleep.
The observer performs no sends, retries, cancellations or configuration writes.

Local encrypted Direct Boot credentials remain the reboot mechanism. A remote
backup would be a separate owner-authenticated recovery feature; it cannot
replace local access to the first-unlock credential and its encryption key.
This release does not upload any PIN to Supabase.

Validation: synthetic batch/toggle/truncation and observation tests, Android
unit tests/lint/build/signature checks, followed by an observed scheduled batch
on the pilot phone. Physical results and remaining hardware limitations belong
in the private delivery report; do not infer them from a successful build.
