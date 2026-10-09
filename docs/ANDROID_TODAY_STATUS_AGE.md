# Native WhatsApp Today timestamp baseline

The .18 manual eleven-media attempt selected eleven items but sent no slice. It
failed before publication after waiting for its baseline: five existing complete
rows used the physically observed `Today, 5:58 AM` format, which was unknown to
the structural diagnostic. Four Yesterday rows were recognized. The original
receipt and zero-send sequential proof are retained; no uncertain job is replayed.

.19 recognizes exact Today timestamps against the device-local clock, including
the observed English twelve-hour form and French/English twenty-four-hour forms.
Two full displayed minutes must have elapsed. Future, ambiguous bare clocks,
malformed dates and unsupported text remain unknown; there is no midnight wrap.
The change only classifies an existing completed row as aged. It does not claim
account identity, stable media identity, total status count or publication proof.
All other baseline and per-slice guards remain in place. A device clock change
or an inconsistent provider display remains a limitation of timestamp evidence.

Five synthetic tests cover the physical format, two-minute boundary, midnight,
noon, future times, Unicode spaces, malformed/ambiguous text and proof limits.
Physical validation and large-batch publication are separate pending checks.
Rollback is the signed .18 APK, preserving application data and journal receipts
under the existing installation hold and idle checks. Facebook, sleep, network
switching and autonomous scheduling remain unverified.
