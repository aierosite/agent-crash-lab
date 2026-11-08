# Official SDK execution conformance · v0.13.1

This study addresses an implementation-evidence gap: the payment profile had
been checked against official source and constructed examples, without running
the SDK itself. It adds execution of the actual pinned Rust resolver. It does
not turn the complete evaluation into independent blind grading.

## What actually ran

- Official `near/near-sdk-rs` revision `bacd081a0bd648d840b814dab7677e1f3330afbb`,
  standards package 5.30.1, with Rust 1.95.0. The first build used a Windows Git
  archive with CRLF line endings. All 407 actual compiled files were checked
  against that archive after execution. A portable checkout correctly failed
  that strict byte check before executing anything because it used canonical LF.
  Both inventories and the first failure are retained; every difference was
  verified as CRLF-only. The fresh execution command checks canonical Git-blob
  bytes, verified independently for each archived member with `git show PIN:path`,
  before and after its build. No SDK logic was patched.
- The upstream `fungible_token` test filter passed 12 event tests: six fungible
  and six non-fungible tests, because the latter names contain that substring.
  These test event serialization; they are not 12 upstream resolver scenarios.
- A separate owned harness called `ft_transfer_call` and `ft_resolve_transfer`
  on the real SDK struct and mock host for 162 registered combinations. It saved
  literal return values, original emitted strings, created mock call arguments
  and before/after ledger state. A fresh invocation of the same binary repeated
  the entire 338,357-byte output exactly.

Inputs cover 1, 100 and u128 maximum; accepted, partial, full and above-transfer
unused values; failed promises, malformed JSON, numeric rather than string U128,
UTF-16 and UTF-8 BOM bytes; three receiver-balance states; and present/absent
sender ledger registration. Some boundary combinations intentionally coincide:
the count is executions, not distinct behavior or independent samples.

## Financial reference and result

The SDK's actual ledger deltas provide refund and supply burn; its actual return
value supplies `used`. Independently of the inspector, the adapter checks ledger
conservation, unchanged sink balance, receiver reduction = refund + burn and
returned used = original transfer minus refund. It then compares amount, refund,
burn, used, payer cost and non-refunded/non-burned allocation with Crash Lab.

The first unchanged v0.13.0 inspector matched all 162 projections. No engine bug
or accuracy improvement was found in this study. Another 28 controls cover a
declared allowed payment, cap excess despite refunds, forbidden burn, settlement
shortfall, missing resolver, equal-price independent orders and edited log bytes
under an old input fingerprint. The first full reports remain reproducible from
the frozen original inspector, separately from checking the current inspector.

Two public examples preserve actual SDK event strings. The burn example pays
100, reports SDK used/cost 100 and burns 50, leaving allocation 50. Its study
policy forbids burn, so it fails that term. The accepted example permits an
ordinary allocation of 100. Neither example is a network transaction.

## Reproduce

Offline, standard-library replay from the repository or ZIP:

```sh
python -I -S tools/verify_sdk_study.py
```

This replays **saved SDK outputs**; it does not run Rust. For fresh execution,
use Linux with Git and Rust 1.95.0 available. The opt-in command fetches the
official pinned source and locked crates, compiles tests/harness, runs the SDK,
checks source integrity and compares fresh output with both original SDK facts
and the current inspector. It creates a new workspace and retains full logs.
It never installs tools, starts a node, connects a wallet or submits a transaction.

```sh
python -I -S tools/run_sdk_study.py --execute \
  --workspace /tmp/my-new-crash-lab-sdk-study --output sdk-run.json
```

The workspace and output must not already exist. The separate `Execute pinned
SDK conformance` workflow uses the same command; ordinary acceptance CI runs
offline replay. A successful offline replay must never be labelled a fresh SDK
execution. The runtime application has no Rust dependency.

## Boundaries and provenance

The harness directly injects the receiver's remaining balance, a balancing sink
and sender registration before resolver execution. Those states were not produced
by a live receiver agent or executed receiver contract. Its mock-created calls
are checked, but receipt IDs, callback data-ID mapping, block/gas metadata and the
FINAL/RPC envelope are our synthetic adapter. Exact emitted event strings and
SDK function arguments are preserved. The UI deliberately labels this source
synthetic and explains the distinction in the source note.

SDK authorship is external; parameter selection, adapter, policies and grading
are ours and source-informed. No real agent, deployed WASM, consensus proof,
independent blind accuracy estimate or head-to-head Workcell execution is
established. Retained recipient balance and useful work remain separate from
settlement allocation. Broader end-to-end agent evaluation is still open.

Artifacts: [registration](../verification/sdk-study/REGISTRATION.json),
[case commitment](../verification/sdk-study/CASE-REGISTRATION.json),
[original SDK outputs](../verification/sdk-study/sdk-original.json),
[first comparisons](../verification/sdk-study/first-comparison.json),
[source integrity](../verification/sdk-study/source-integrity.json),
[Rust harness](../verification/sdk-study/harness/src/main.rs).
The upstream source is [pinned here](https://github.com/near/near-sdk-rs/tree/bacd081a0bd648d840b814dab7677e1f3330afbb);
its MIT and Apache licenses are retained with the study.
