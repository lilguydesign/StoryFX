# Manual recipe receipt projection

Native receipts retain their immutable core diagnostics and observation proof in
separate owner-scoped tables. Recipe progress and the five-minute cooldown now
join both parts for the same owner and attempt, just as the report view does.

A complete sequential receipt can therefore close its existing recipe without
another publication. Missing, partial or foreign-owner proof still blocks
release. Legacy small batches remain compatible without observation rows.
No stored result, scheduler, device binding or publication eligibility is changed.

Synthetic API tests reproduce the previous blocked projection and verify closure,
cooldown, owner isolation, incomplete-proof refusal and byte-preserved receipts.
This projection fix does not validate Facebook, sleep, network changes or autonomy.
