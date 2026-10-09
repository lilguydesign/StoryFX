# Native manual quantity evidence, contract 1

Android 0.4.18 supports owner-requested WhatsApp recipes of 10–30 media through
bounded slices. Automatic scheduling does not gain this capability. Facebook
and TikTok remain unavailable. The backend advertises contract 1 explicitly;
without it, the agent refuses a large job before selecting or sending media.

The agent draws the entire exact album once, without replacement, then keeps
that immutable URI list in memory. Its SHA-256 fingerprint stays only in the
encrypted Android journal. The existing selection policy prefers different
known capture days before reusing one. It does not simulate Gallery scrolling;
unknown dates or too few distinct days cannot guarantee different days.

Each slice contains at most nine media. An introductory video remains the
first separate slice. Before each send, the agent saves durable intent. It
requires an own-list row-zero witness with no pending, unknown-age or fresh
rows; before subsequent slices, at least the previous slice's quantity must
be visibly aged. An empty own-status home is allowed only before the first
slice. The provider still must show only the owner's status destination.

Each slice must independently satisfy the existing single-view recent-visible
quantity proof. Positions from different screens are never unioned. The final
receipt uses `sequential_recent_visible_v1`, ordered planned and verified
counts, bounded monotonic timing and baseline counts. This measures visible
quantity only: it does not identify media, verify the account, establish a
provider total, or validate autonomous operation, sleep or disconnected USB.

A crash, ambiguity, lost response, expiry or persistence failure stops the
whole lot. No slice is reconstructed or retried. Previously uncertain and
confirmed jobs retain their exact receipts. Partial evidence remains uncertain.
The job is bounded by 780 seconds from claim, below the existing 900-second
server lease. After backend rollback, the new receipt remains pending locally;
the agent cannot strip the separated proof to obtain an old-style acceptance.

Validation: synthetic Android and server checks exercise slice ordering,
durable intent, no replay, deadline, partial proof, immutable API receipts and
old receipt compatibility. Physical large-lot validation remains required.
Rollback: previous backend and official APK pointer; preserve all encrypted
reservations and installation holds. A rollback never replays media.
