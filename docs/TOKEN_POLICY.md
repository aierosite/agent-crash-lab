# Token payment policy · v0.14.0

Use the payment-terms page from the workbench, the CLI, or an exact-byte input
bundle. The same Python inspector runs locally and in the browser worker;
the browser separately reconstructs the supported financial projection before
accepting a result. This response boundary is not an independent external grader.

## Question and scope

Given exact policy and recorded execution bytes, did the supplied payments
meet each declared order's gross limit, recipient, refund-burn allowance and
minimum settlement? This is a conditional offline assessment under
`near-nep141-sdk-receipts/v1`, not a transaction authorizer or a whole-agent
safety result. Amounts are atomic token units; decimals, tickers and USD are
not inferred.

The profile supports `ft_transfer`, atomic batches of that method, and a
single `ft_transfer_call` with NEAR SDK-style receiver and resolver receipts.
The owner explicitly assigns a payment receipt and its creation subtree to
an intent. Overlapping assignments are rejected. Equal prices are not used
to identify an order or callback.

For a transfer-call, receipt bodies, creator/predecessor/executor identities,
method arguments, returned promise chain and callback data IDs are checked.
The receiver may return another promise. Mixed asynchronous batches and
missing, conflicting or uninterpretable causal evidence remain unknown.
Compatible FINAL fragments merge; identical physical facts count once.

## Three amounts that must not be confused

For initial transfer A, actual refund R and refund burn B:

- Gross committed payment is A, before refunds. Incoming topups cannot offset it.
- Payer cost and the SDK resolver's reported used amount are A − R.
- Non-refunded, non-burned allocation is A − R − B.

For example, transfer 100, refund 0 and burn 80 means cost 100 but settlement
20. A minimum settlement of 50 fails even though the resolver returns 100.
A declared gross cap of 50 is exceeded by a transfer of 100 even if the
receiver later returns most of it.

Settlement does not prove the recipient retained the tokens or performed
useful work. Sender deletion in the synthetic examples means absence from
the token contract's balance ledger, not deletion of a NEAR wallet/account.
The refund's sufficiency cannot be checked without a receiver-balance
reference. Native-payment inspection and task-output checks remain separate.

## Inputs and results

`agent-crash-lab/token-task-v1` contains profile, unsigned declared authority,
exact evidence SHA-256, network, token contract, payer, a finite horizon,
per-intent constraints and explicit receipt bindings.
`agent-crash-lab/token-execution-v1` contains source declarations and bounded
read-only status request/response observations. Each input must be nonempty,
strict UTF-8 JSON no larger than 2 MiB, without duplicate members, fractional
numeric metadata or invalid Unicode. Financial amounts are decimal strings.

The observations array permits zero through 128 entries. Zero observations with
declared orders remains gate 2: no graphs/payments or exact amounts are invented,
even if the owner declares a closed horizon. [The actual model study](AGENT_LOOP.md)
preserves two originally unassessed zero-payment episodes and separately replays
them with this additive profile support.

The report binds assessor, primitives and both input fingerprints. It states
the source claim, authority, interpretation profile and horizon explicitly.
Known breaches take precedence over unrelated missing evidence. Missing
causal descendants prevent an exact settlement claim; a missing unrelated
branch does not erase a known payment, though the overall source can remain
incomplete. A malformed FINAL observation is validated atomically before it
can contribute facts to an existing graph.

```powershell
python -I -S token_policy.py path/to/task.json path/to/evidence.json
python -I -S token_policy.py path/to/task.json path/to/evidence.json --gate
python -I -S test_token_policy.py
node test_policy_contract.js
python -I -S tools/measure_policy_resources.py --output policy-resources.json
```

The normal CLI exits 0 when assessment completes. `--gate` uses 0 for declared
terms met, 1 for a known breach/failed settlement requirement, and 2 for
insufficient evidence. Invalid input exits 2. Gate 0 never authorizes sending
funds. An `agent-crash-lab/token-policy-bundle-v1` contains exact `task_utf8`
and `evidence_utf8` strings, never server paths. The local candidate endpoint
is `/api/token-policy`; browser execution uses the same fingerprinted Python
source in a WebAssembly worker. The bundle itself is limited to 2 MiB.

## Evidence and remaining work

The portable reference contains 18 previously registered, source-informed
cases: 16 synthetic SDK-style histories and two wrappers around our saved
read-only public archival testnet observations. Another 51 controls are
explicitly labeled post-baseline or post-result. Their references and grader
are ours. The SDK and Workcell code were not executed in this study. No new
contract, model, signing, transaction or mainnet operation occurs in replay.

The exact prior prototype reports, four reproduced integration failures,
six malformed-envelope/atomic-merge failures and semantic ablation plans
are retained. Three encoding controls exposed Python's incorrect byte-encoding
autodetection for SDK hook output; UTF-16/32 and UTF-8 BOM data now follow the
SDK invalid-output branch. A separate non-UTF8 resolver control stays unknown.
These are source-informed parser/profile checks; the Rust SDK was not executed
in that initial v0.13.0 study. The separate [v0.13.1 SDK conformance study](SDK_CONFORMANCE.md)
subsequently executed the unchanged official resolver in a mock host and preserves
its original outputs, injected-state assumptions and constructed-adapter limits.
Pre-publication boundary checks also preserve five financial counterfeits
accepted by an initial browser guard. Explicit null receipt fields no longer
inherit defaults for omitted fields. RPC response IDs require presence,
supported scalar type and exact type matching; an explicit null ID remains
supported. Current guard checks reject all six constructed invalid financial
responses even after their inspector hashes are rebound to current code.
These checks are protocol/reference and boundary evidence;
they are not an independent blind end-to-end accuracy estimate.

Inspired by Workcell's scenario search, reduction, replay and separate
economic invariants, this work keeps gross authorization, settlement and
successful permitted payments distinct. Static source review does not
establish feature superiority over Workcell. The interface accepts exact
bundles, shows source/authority claims, opens original receipt/log strings,
and clears old results on an invalid import. Large batches share source panels;
their text is materialized only while open. Diagnostic prose is bounded display
text, not a premise for the financial conclusion. The guard verifies its shape
and underlying uncertainty, not the exact wording of every exception message.

Remaining work includes additional justified execution profiles and broader
independently authored end-to-end evaluation. No release is justified by test
count alone. The case count is not an accuracy estimate. Network authenticity,
source-to-WASM equivalence, generic ledger rights and useful work remain outside
this payment profile.

## Primary references

- [Workcell source reviewed at b80bcecc](https://github.com/dotmantissa/workcell/tree/b80bcecc1d30263662b985fc025b83233e07a173)
- [Pinned NEAR SDK resolver](https://github.com/near/near-sdk-rs/blob/bacd081a0bd648d840b814dab7677e1f3330afbb/near-contract-standards/src/fungible_token/core_impl.rs)
- [Receiver PromiseOrValue interface](https://github.com/near/near-sdk-rs/blob/bacd081a0bd648d840b814dab7677e1f3330afbb/near-contract-standards/src/fungible_token/receiver.rs)
- [U128 representation](https://github.com/near/near-sdk-rs/blob/bacd081a0bd648d840b814dab7677e1f3330afbb/near-sdk-core/src/json_types/integers.rs)
- [RPC transaction status](https://docs.near.org/api/rpc/transactions)
- [Event format](https://github.com/near/NEPs/blob/095fe98218d2272a0a285008f72bdb3e8957e613/neps/nep-0300.md)
