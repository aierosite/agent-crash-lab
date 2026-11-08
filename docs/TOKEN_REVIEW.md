# Token custody, user rights and operation references

Open **Token custody review** from the workbench sidebar, select a recording and press **Review recording**. Local mode runs Python in the workbench server. The static demo runs the same source in pinned Pyodide. Both inspect saved inputs; neither submits a transaction or calls a model.

The input remains `agent-crash-lab/token-recording-v1`. Version 0.12 returns **`agent-crash-lab/token-review-v2`**. Native core 0.1.2, native report and `gate.py` semantics remain unchanged.

## Correct event owners and complete report evidence · v0.12.1

NEP-300 mint and burn use **`owner_id`**. Transfer uses `old_owner_id` and `new_owner_id`. Version 0.12 incorrectly applied the transfer field names to mint/burn, and its constructed test helper repeated that error. It could miss a valid mint/burn or attribute one to an account named by an extra transfer-style alias. Both the assessor and browser guard now derive the normalized owner from the standard's canonical field. Mint/burn remain custody changes, never payment delivery.

Eight unchanged serialized event examples come from the [official SDK's test assertions](https://github.com/near/near-sdk-rs/blob/bacd081a0bd648d840b814dab7677e1f3330afbb/near-contract-standards/src/fungible_token/events.rs) and [NEP-300](https://github.com/near/NEPs/blob/095fe98218d2272a0a285008f72bdb3e8957e613/neps/nep-0300.md). Fifteen derived owner contexts and four constructed alias controls expose eleven disagreements in the old parser; the correction matches all nineteen declared projections. These are source-informed conformance contexts, not nineteen independent trials or a broad accuracy estimate. The SDK's serialized expectations have external authorship; the state/receipt envelopes and direction reference are ours. No SDK or competitor code is executed. One normative burn example has a trailing comma: its invalid text is retained, not silently repaired or counted as a valid vector.

The browser also reconstructs the **whole** event projection and ignored-log count from the input. Checking only that reported events occur in the source allowed two offsetting transfers to be omitted. The old guard also accepted a fabricated complete response for uninterpretable token-event evidence. Both original counterexamples and frozen sources are replayed. The corrected guard rejects omissions and promotion of incomplete event, identity, interval or liability evidence, while preserving valid full reports. Embedded event JSON checks duplicate/escaped duplicate keys, exact integer metadata, bounds and Unicode before interpretation.

Select **Official mint event**, **Official burn event** or **Official batch transfer** for a constructed envelope around the official event text. These examples are explicitly synthetic; they are not deployment observations. Run:

```sh
python -I -S tools/verify_event_study.py
node test_event_contract.js
```

The offline verifier reproduces twenty-one original reports, compares the nineteen projections and checks three interpretation mutants. The Node suite separately reproduces the two historical guard acceptances and rejects the same counterexamples in the corrected guard. Later parser/scope controls are post-result engineering checks, not a blind holdout. Registration, complete old reports, source fingerprints and method notes are under `verification/event-study`.

## A measured difference is not automatically lost entitlement

The old v1 field `entitlement_reduction` used a change in vault surplus. A constructed capital top-up exposed the mistake: held tokens rose from 100 to 200, rights stayed 100, and the capture contained an incoming transfer of 100. V1 labeled 100 as entitlement reduction even though rights did not fall. A payout plus a separate top-up exposed the same causal ambiguity.

V2 separates measurements:

| Field | Meaning |
| --- | --- |
| `parity_difference` | Change in held tokens minus change in declared rights, signed. Capital, fees or reallocations can change it. |
| `transfer_out` | Successful `ft_transfer` events crossing out of the vault. Self transfers, mint and burn are not delivery. |
| `rights_debit_without_transfer` | Nonnegative rights debit not covered even by total outward transfers. A writeoff/burn may need a different operation reference; this alone is not an authorization verdict. |
| `backing_shortfall` | Largest observed endpoint liability shortfall. It is not an estimate of new loss. |
| `ledger_relation` | Matched, different or unknown net changes. |

Results are `recorded-parity`, `recorded-gap`, `recorded-evidence-conflict` or `inconclusive`. A gap does not itself prove a failed obligation. Matching net changes do not prove successful delivery. The UI no longer labels a capital top-up lost rights or calls assignment of existing surplus new unfunded money.

The frozen v1 reviewer remains in `verification/token-study/frozen-review-v1.py.txt`, with the original five-case literal reference and sealed inputs. Tests reproduce its capital-top-up label before checking the correction. The old reference's limited numeric/parity projection remains reproducible, with explicit translation of the new descriptive labels. This is a semantic/schema correction, not a newly independent accuracy result.

## Separate source observations and explicit payout references

For two **exact recording hashes**, press **Replay source check**. It checks a separately collected public archival dataset and a stated operation reference. The result is bound to the selected recording hash, verifier source hash, dataset hash and complete nested expected response. Editing an import or retaining the same case ID cannot inherit another file's corroboration. Changed selection, failed imports and rejected source responses clear the old view.

The source collection on 8 November 2026 made **25 sequential, read-only public testnet requests** to `https://archival-rpc.testnet.near.org`: one status, four block headers, eight account/code-identity reads, eight raw storage reads, two transaction-status reads and two status-with-receipts reads. No keys, credentials, signing, contract invocation, transfers, mainnet or paid endpoints were used. The collector is not part of the runtime; tests and replay do not repeat those requests.

The source checker compares four before/after points, eight deployed-code identities and two transaction outcome projections. An original Borsh reader decodes the stored token and rights values; it does not call or execute competitor contracts. Receipt action bodies bind the payout method, amount and recipient to its receipt outcome. The two artifact/storage profiles are deliberately pinned: a historical Ref exchange capture and Workcell's recorded treasury fixture. This is not a generic state decoder or proof of source-to-WASM compilation.

| Selected interval | Explicit reference | Observation |
| --- | --- | --- |
| Historical owner withdrawal | When the token payout fails without delivery, preserve the user's rights. | The root succeeds, the child `ft_transfer` fails, held tokens stay 10,000,000, and rights fall 10,000,000 to 6,000,000. Reference failed. |
| Recorded reserved agent payout | Deliver prior reserved 100 to the recorded owner and debit that amount once. | The transfer settles and rights fall 1,000 to 900. Reference passed. |

The first operation-plan wording incorrectly assumed the **root transaction** failed. Source inspection showed root success with a failed child. `OPERATION-REFERENCE-AMENDMENT.json` records the correction before implementing the operation grader. Root success is not completed payout. Missing relevant receipt bodies keep the operation reference inconclusive while other source comparisons remain available.

The initial offline reader accepted five invalid resealed controls: an embedded RPC result error, a duplicate receipt and float representations of query height, header height and transaction gas. The original source and 11/16 result are retained. The corrected reader rejects 16/16, and additional receipt-binding controls and semantic mutants cover the root-success shortcut and omission of reserved rights. Hashes are resealed in these controls so the semantic bindings are tested beyond file integrity alone.

## Reproduce offline

From the release directory:

```sh
python -I -S token_review.py verification/token-study/upstream-failed-withdrawal.json
python -I -S tools/verify_token_rpc.py
python -I -S test_token_review.py
python -I -S test_token_rpc.py
node test_token_contract.js
node test_source_contract.js
```

`token_review.py` prints a completed descriptive review with exit 0, including a gap. The source verifier exits 0 for a successful fixed-study replay, **including the expected failed security reference**; inspect `operationReference.status`. Invalid input/source files exit 2. Neither command replaces the native financial gate.

The raw request/response bytes, byte hashes, source plans, first/corrected reader sources and controls are under `verification/rpc-study`. `tools/verify_token_rpc.py --captures DIRECTORY --recordings DIRECTORY --output FILE` supports offline verification of this documented two-case study. It does not contact a node. In the browser, setup and staged-file loading still use HTTP/CDN; `replayNetworkCalls: 0` describes the offline Python verifier, and no live chain RPC is issued by replay.

## Authorship, coverage and trust

Five original cases / twelve correlated transitions are factual extracts from two Workcell public archives at [b80bcecc1d30263662b985fc025b83233e07a173](https://github.com/dotmantissa/workcell/tree/b80bcecc1d30263662b985fc025b83233e07a173/evidence):

- [Historical Ref capture](https://github.com/dotmantissa/workcell/blob/b80bcecc1d30263662b985fc025b83233e07a173/evidence/wc_mw0eydrg_0c8f2c.json), SHA-256 `df812867dc62a343019d99480dcc60ed0f8639a8e6c77b66dc8d8c7449421a86`.
- [Recorded agent payment](https://github.com/dotmantissa/workcell/blob/b80bcecc1d30263662b985fc025b83233e07a173/evidence/wc_mw0hwd2k_6d93f3.json), SHA-256 `f94a88ea55191172168add2c2e940fe2520ee7677b008b85dbfbf7dadd7d416c`.

`tools/import_token_archive.py ARCHIVE --case CASE` reproduces an extraction from an exact matching original, without fetching or executing anything. Only factual protocol records and numeric summaries are distributed. Competitor code, verdicts, expressive full reports and full original archives are not copied into the product or executed. Static source/ABI inspection informed our original storage reader.

Workcell authored the original input archives; we collected the new RPC responses and authored extraction, readers, references, grader and evaluation. This broadens data provenance but is **not externally authored grading, a blind audit, independent trials, a new model/contract run, or a real-world accuracy estimate**. The source selection and expected producer values were known before collection. The recipient-balance check was added after raw keys were inspected; it is disclosed as corroboration, not a preregistered holdout.

The public node is trusted. Matching queries are not cryptographic state proofs, verified signatures, a light-client consensus check, source-to-binary equivalence, proof of interval exclusivity or an audit of production Ref Finance. The stored fixtures may be obsolete or synthetic in purpose; no production vulnerability is asserted. Three original examples still rely solely on their producer summaries. No ticker, decimals, USDC identity, exchange rate or dollar value is inferred.

Technical primary references: [NEAR public providers](https://docs.near.org/api/rpc/providers), [transaction and receipt-status semantics](https://docs.near.org/api/rpc/transactions), [raw account/contract queries](https://docs.near.org/api/rpc/contracts), [Borsh specification](https://borsh.io/), and pinned [NEP-141](https://github.com/near/NEPs/blob/095fe98218d2272a0a285008f72bdb3e8957e613/neps/nep-0141.md), [NEP-297](https://github.com/near/NEPs/blob/095fe98218d2272a0a285008f72bdb3e8957e613/neps/nep-0297.md), [NEP-300](https://github.com/near/NEPs/blob/095fe98218d2272a0a285008f72bdb3e8957e613/neps/nep-0300.md). A one-yoctoNEAR attachment is not the token amount.

Broader owner-declared token authorization/operation models, independently authored evaluation, fresh permitted agent experiments and external review remain open. This release does not close the long-term goal.
