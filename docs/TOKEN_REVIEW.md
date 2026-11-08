# Recorded token custody and user rights

Open **Token custody review** from the workbench sidebar, or open `web/token.html` on the public demo. Choose an archived example and press **Review recording**. The local workbench runs the reviewer in its server process; the static demo runs the same Python source in Pyodide. The CLI can run with Python import isolation (`-I -S`). Import accepts the separate `agent-crash-lab/token-recording-v1` format, not a native payment bundle.

The question is narrower than payment authorization: **do the recorded custody changes reconcile with the rights the vault says it owes?** A sufficient vault balance alone does not establish that rights were preserved.

## Concrete discrepancy

The historical failed-withdrawal archive reports a vault with 10,000,000 atomic token units. A withdrawal fails. The vault still holds 10,000,000, but the user's recorded rights fall from 10,000,000 to 6,000,000. Captured token events show no corresponding payment. The reviewer exposes a **4,000,000-unit entitlement discrepancy**, even though backing remains sufficient. This is a conditional inconsistency in the supplied recording, not a new finding about current production Ref Finance.

The control examples retain a successful deposit/withdrawal, a full return of a deposit, an unchanged unauthorized withdrawal, and a reserved 100-unit agent payment. A reservation preserves rights: `credit + pending + reserved` must be counted, not credit alone.

## Reproduce offline

From the release directory:

```sh
python -I -S token_review.py verification/token-study/upstream-failed-withdrawal.json
python -I -S test_token_review.py
node test_token_contract.js
```

The CLI prints a full review and exits 0 when the review completes, including a recorded inconsistency. Invalid input exits 2. **This command is not the native financial CI gate.** Existing `gate.py` behavior and native engine semantics are unchanged.

The report distinguishes `recorded-consistent`, `recorded-inconsistency` and `inconclusive`. It never says Safe. Per-step endpoint changes, gross in/out, net movement, reserved rights, backing, event receipt IDs and exact original archive pointers remain visible. Amounts stay exact integers in atomic units; no USDC identity, ticker, decimals, exchange rate or dollar value is inferred.

## Input provenance and reference

Five cases / twelve correlated transitions are selected from two public Workcell archives, pinned at [b80bcecc1d30263662b985fc025b83233e07a173](https://github.com/dotmantissa/workcell/tree/b80bcecc1d30263662b985fc025b83233e07a173/evidence):

- [Historical Ref exchange capture](https://github.com/dotmantissa/workcell/blob/b80bcecc1d30263662b985fc025b83233e07a173/evidence/wc_mw0eydrg_0c8f2c.json), SHA-256 `df812867dc62a343019d99480dcc60ed0f8639a8e6c77b66dc8d8c7449421a86`.
- [Recorded agent treasury payment](https://github.com/dotmantissa/workcell/blob/b80bcecc1d30263662b985fc025b83233e07a173/evidence/wc_mw0hwd2k_6d93f3.json), SHA-256 `f94a88ea55191172168add2c2e940fe2520ee7677b008b85dbfbf7dadd7d416c`.

Only factual protocol records and numeric summaries are extracted. Workcell source code, its checks/verdicts, expressive report content and full source archives are not redistributed here. `tools/import_token_archive.py ARCHIVE --case CASE` reproduces an extraction from an exact matching downloaded original, without fetching anything or executing competitor code. The original byte hashes and Git blob hashes were verified at collection.

`verification/token-study/registration.json` seals the plan, literal arithmetic reference, extraction source and five inputs **before implementing/evaluating the reviewer**. Source actions and balances had already been read: the study is **source-informed**, not blind. A guessed future timestamp in the first plan was corrected to the actual registration clock before implementation; the previous digest is retained. Three deliberately incorrect semantic implementations test sensitivity to ignoring reserved rights, checking backing alone, and ignoring outgoing returns.

Workcell authored the input archives. We authored extraction, reference, reviewer and evaluation. This broadens input authorship; it is **not externally authored grading, independent review, twelve independent trials, a new model inference, or a fresh contract experiment**. Do not present reference agreement as real-world accuracy.

## Interpretation and limits

For each closed, single-owner vault interval:

1. `rights = credit + pending + reserved`; require agreement with reported total liabilities.
2. Compare change in held tokens with net token events from the declared token contract's successful receipt outcomes.
3. Compare change in rights with change in custody; expose unexplained reductions or increases separately from backing.

Mint and burn are explicitly distinguished from transfer events. Foreign-emitter or failed-receipt event logs do not establish payment. Missing transactions/receipts, non-FINAL outcomes, unsupported token event semantics, unordered endpoint heights, inconsistent reported code identity or missing scope assumptions keep affected rows inconclusive. Duplicate JSON fields/receipt identities and malformed quantities are rejected.

The selected endpoints are **producer-reported summaries**, not raw state-query responses. Source SHA-256 binds bytes but does not authenticate them. We do not validate signatures, consensus, code execution, the truthfulness of token events, the completeness of a real interval, hidden account changes, or production contract behavior. Reported code identity is checked for internal consistency, not independently proven. No fresh RPC, wallet, signing, chain transaction, paid API or model request occurs during this review.

The event interpretation follows pinned primary specifications: [NEP-141](https://github.com/near/NEPs/blob/095fe98218d2272a0a285008f72bdb3e8957e613/neps/nep-0141.md), [NEP-297](https://github.com/near/NEPs/blob/095fe98218d2272a0a285008f72bdb3e8957e613/neps/nep-0297.md), [NEP-300](https://github.com/near/NEPs/blob/095fe98218d2272a0a285008f72bdb3e8957e613/neps/nep-0300.md). A one-yoctoNEAR call attachment is not the transferred token amount.

The native assessor remains byte-identical to v0.10.0. This separate reviewer does not expand `near-sandbox-2.14/native-v1` to token authorization. More token implementations, independently collected state proofs, broader agents and external review remain open work.
