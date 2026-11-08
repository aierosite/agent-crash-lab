# Reported ledger diagnostic · private v0.20.0 candidate

This candidate does not change the frozen v0.19.1 competition package.
The separate `token_ledger.py` wrapper leaves `token_review.py` and its v2
financial reports byte-identical. The custody UI/API and `python -I -S
token_ledger.py recording.json` use v3. Both wrapper `assessor_sha256` and
`base_assessor_sha256` are bound to the release. `token-review-v3` adds
`step.reported_ledger`:

```json
{"status":"conflict","before_difference":"0","after_difference":"3"}
```

The differences are **credit + pending + reserved − reported total liabilities**
at the two supplied endpoints. They are exact signed integer strings, including
sums larger than one U128 component. `conflict` and `matches` are conditional on
the caller declaring a single-owner whole vault. Without that declaration the
status is `not-declared`; a difference need not be an inconsistency across owners.
The browser reconstructs and checks every nested diagnostic against the original
input. It rejects missing, altered, extra or wrong-typed fields and stale v2 responses.

A known disagreement can remain visible while receipt closure, code identity,
backing or payment delivery are unknown. The financial conclusion is unchanged:
the diagnostic does not promote an inconclusive capture into a payment failure,
proved loss, authenticated state or authorization decision. The visible heading
says **The reported ledger disagrees** rather than only **Evidence is incomplete**
when the supplied single-owner numbers already contradict each other.

The study's eight registered controls preserve exact numeric endpoint facts from
Workcell's pinned public unit tests plus explicitly labelled constructed controls.
They include a partial-refund credit of10 with reported liability7, undeclared
scope, missing receipts, pending evidence and sums beyondU128. Synthetic wrapper
heights, token identity and net-only receipt events are **not** actual Workcell
transactions or chain captures. No upstream source code is copied into this study.
The original tests are at
https://github.com/dotmantissa/workcell/tree/b80bcecc1d30263662b985fc025b83233e07a173/tests
and input integrity/scope are recorded in `verification/token-ledger-study`.

These are source-informed conformance and response-boundary checks. The controls,
mapping and wrapper are ours; they are not an independent blind gold standard,
head-to-head accuracy score or evidence of superiority over Workcell. Allowance,
authorization and requested-operation success are separate axes, absent from this
custody-only diagnostic. Earlier research snapshots and their original v2 results
remain unchanged.

The original `/api/token-review` and `/api/token-catalog` remain v2.
The new UI uses the separate `/api/token-ledger-review` and
`/api/token-ledger-catalog` routes. The new POST route rejects inputs larger
than2MiB before parsing; the worker enforces the same bound. Source/fingerprint
changes do not overwrite archived reports or their original expectations.
