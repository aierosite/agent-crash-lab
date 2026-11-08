# Native receipt journals · v0.19.0

This view checks supplied local-runtime receipts against explicit caller payment
intent. It separates merchant payment, principal refunds, receipt-operation
closure and whole-process transcript completion. A missing final reply does not
make an already delivered payment safe to repeat. A returned principal amount
does not mean the merchant was paid. No result authorizes an automatic retry.

## What actually ran

The four installed examples are captured from **eight externally SIGKILLed owned
processes**, two fresh-process sets at four predeclared boundaries. The runner
uses a local TestDB/Genesis and unsigned incoming receipts with an empty signed
transaction vector. A synchronized block-result journal and labelled research
marker are written before a cooperative pause; a parent validates the owned
process identity and kills it. This is a controlled process interruption, not an
unexpected crash, database restart, disk power-loss or consensus experiment.

| Boundary | Merchant payment | Principal refund | Operation | Whole transcript |
|---|---|---|---|---|
| Before payment executes | Unknown | None observed | Open | Incomplete |
| After payment, before final reply | Arrived | None | Closed | Incomplete |
| Failed payment, before principal refund | Failed | Pending | Open | Incomplete |
| After principal refund | Failed | Returned to payer | Closed | Incomplete |

All balances are fictional atomic fixture units. Gas purchase credits and gas
refunds are distinct from payment principal. The actual captures had zero
internal congestion bytes; positive/missing queue and torn-tail cases are
**constructed controls**, not additional observed runtime conditions. Repeated
setup blocks and methods are not separate benchmark cases.

## Source and evaluation boundaries

The runtime source is [nearcore at bc4e9e8](https://github.com/near/nearcore/tree/bc4e9e8cfb03d9e82f027883055624e18576993e),
workspace 2.14.0, protocol88, Wasmtime45.0.0. The externally authored target is
[Veto at 3431439](https://github.com/Bronxydrone/Veto/tree/3431439d2bbedaa13dd377dedcd6c6f7c698a6ae).
Its pinned 307,028-byte Wasm SHA256 is
`1c5f5d30d292d660166b1e5b89a0173f70ecc5e714e1da3aaca5c9a3aece92e6`.
No target Wasm/source, third-party runtime source or 93MB research executable is
redistributed in this view. Generated journal observations, caller policies,
references and audit records are included. [Original capture source, manifest/lock and historical assessor](../verification/receipt-journal/capture-source/README.md)
are shipped for inspection with exact provenance. The full dependency-source
audit and runtime build remain a separate sealed local study; the default viewer
does not rebuild them. The archived Cargo manifest describes the original
path-bound research environment, not an independently tested portable rebuild.

The exact-integer reference, parser and browser projection are same-author and
source-informed. They are **not independent blind grading**. An external target
author does not make our evaluator independent. No fair executed head-to-head
against Workcell, authenticated-chain capture, fresh model-driven native loop,
arbitrary FT callback or positive-congestion experiment is claimed here.

## Reproduce a review

Python 3.12+ standard library is enough:

```sh
python -I -S receipt_journal.py --journal verification/receipt-journal/journals/after-payment-before-ack-set-1.jsonl --policy verification/receipt-journal/policies/after-payment-before-ack.json
python -I -S test_receipt_journal.py
python -I -S test_journal_http.py
node test_journal_contract.js
node test_journal_cancellation.js
```

Default CLI exit0 means a review was produced. Add `--gate` for the declared
payment check: 0 met, 1 known failure, 2 not established. This gate is neither a
whole-task verdict nor a source-authenticity certificate. Missing observed
amounts are `null`, never invented zeroes. Known failures survive incomplete
capture. The original malformed-outcome acceptances and corrected controls are
preserved separately in `verification/receipt-journal/BOUNDARY-AUDIT.json`.

The finite profile supports an ordinary root FunctionCall, native Transfer
children and system gas/principal refunds. Data dependencies, cross-contract
callbacks and custom refund routing are rejected. The journal must be nonempty
UTF-8 JSONL, at most4MiB/512 complete records; payment intent is at most16KiB.
An unfinished final line is excluded and reported, not silently completed.

## Local API and browser boundary

Start `python -I -S workbench.py --port 0`; open its printed loopback address and
choose **Receipt journal**. `/api/native-journal-catalog` provides source/sample
hashes. `/api/native-journal-input?case=before-payment&part=journal` serves only
installed data (`part=policy` serves the matching raw intent). It accepts no
filesystem path. `POST /api/native-journal-review` uses the existing local
session token and same-origin restriction, with this data-only envelope:

```json
{"format":"agent-crash-lab/native-journal-bundle-v1","journal_utf8":"exact original JSONL text","policy_utf8":"exact original payment intent text"}
```

The9MiB HTTP transport bound is separate from the inner file bounds. Duplicate
keys, invalid Unicode, unexpected fields and non-text inputs are rejected. CRLF
intent bytes and the original journal are retained and can be downloaded.

Browser mode runs the two checked Python sources in pinned Pyodide0.29.5.
That is **Python replay in WebAssembly**, not contract-Wasm execution. The
response guard binds both source hashes and both original input hashes. Its
BigInt receipt projection checks every returned assessment field, including
payment/refund states, pending IDs, nulls, closure, limits and the known-failure
gate. It is a response-consistency boundary, not a second implementation of all
runtime/conservation checks or an independent oracle. Installed examples also
match a whole-report digest. Cancelled and stale async results are discarded.

The release manifest and validation asset distinguish source tests, extracted
ZIP checks, actual UI/native/browser replay and CI/deployment observations.
The frozen v0.18.1 competition snapshot remains available; this successor does
not revise the application or imply independent evaluation. A reviewer can
inspect the preserved sources and repeat the offline checks without running
the original Rust capture experiment.
