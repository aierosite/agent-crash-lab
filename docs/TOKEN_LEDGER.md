# Reported ledger diagnostic · v0.20.0

The immutable v0.19.1 competition snapshot remains available.
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
They include a partial-refund credit of 10 with reported liability 7, undeclared
scope, missing receipts, pending evidence and sums beyond U128. Synthetic wrapper
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
than 2 MiB before parsing; the worker enforces the same bound. Source/fingerprint
changes do not overwrite archived reports or their original expectations.

## Reproduce the explanation-boundary fix

The original published v0.19.1 browser validator accepted a forged nonempty
explanation while leaving its financial conclusion inconclusive. The exact old
source is preserved as text with its commit/hash. Eight valid reports still
validate; six fixed forged-explanation controls reproduce the old acceptance
and are rejected by the current validator. This is post-discovery reproduction,
not unseen attacks or independent accuracy. The new boundary reconstructs every
expected reason from the exact supplied input and declared finite semantics.

```sh
node test_token_ledger_contract.js
python -I -S test_token_ledger.py
```

Open the [constructed example](https://aierosite.github.io/agent-crash-lab/web/token.html?browser=1&case=declared-ledger-conflict)
and click **Review recording**. The separate new GET route is
`/api/token-ledger-recording`; its catalog adds this ninth labelled example.
The legacy catalog and recording route retain their original eight cases.
