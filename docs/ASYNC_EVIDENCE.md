# Partial observations must not change a financial verdict by order

Engine **0.1.2**, released with **v0.9.0**, fixes a reproduced lower-bound error. Without a structurally complete `FINAL` view, the old engine chose the partial view with the most receipt bodies. Equal-size views could prove different effects. Reordering them could change a known subtotal and even turn **breached** into **unknown**. The error did not demonstrate a clean pass; it could hide a provable violation behind uncertainty.

In the displayed **Partial evidence, proven excess** control, two compatible constructed observations prove distinct finalized effects of **6 and 2 yoctoNEAR**, against a **5-yoctoNEAR** cap. The correct lower bound is **8**. A complete total is still unknown. The old engine could report 6 or 2 depending on order; the latter missed the provable excess.

![Synthetic partial evidence: at least 8 against a 5-yoctoNEAR cap](async-evidence.jpg)

## What the correction does

The engine combines compatible observations by receipt/outcome identity, preserving each physical source pointer. A terminal outcome can replace an `Unknown` placeholder. Duplicate observations do not duplicate effects. The combined receipt ancestry is validated again: incompatible parents or cycles fail closed for that transaction. An unrelated, complete task B remains separately assessable.

This is **lower-bound aggregation**, not invented finality. A partial effect requires its matching declared finalized-block anchor before it is counted as committed. Combining partial views never creates a complete `FINAL` view, an exact total or a closed horizon. When a complete supported `FINAL` view already exists, the established complete-view path remains in use. Receipt bodies and their terminal outcomes may come from different compatible observations, with separate `action_ref` and `outcome_ref` pointers retained.

[Official NEAR RPC documentation](https://docs.near.org/api/rpc/transactions) distinguishes inclusion finality from completion of all receipts, including refunds, and notes that receipt details can be incomplete. Our complementary fragments are constructed inputs motivated by that distinction. We do not claim these exact payloads were observed from a node. Declared owner/reference/capture trust still applies; hashes and synthetic final-head records do not authenticate consensus or signatures.

## Reproduce both the original error and the correction

With Python 3.12+, no third-party package, model or credentials:

```sh
python -I -S tools/verify_async_study.py
python -I -S test_async_evidence.py
```

The verifier checks the pinned archive, reconstructs every input byte-for-byte using the portable pure builder, and executes the recorded original engine alongside the current engine. A separately executed original reference computes expected financial projections from each locked plan. All original full report hashes must reproduce; current hashes must match the validated correction.

| Registered selection | Original 0.1.1 | Current 0.1.2 |
|---|---:|---:|
| Plans | 32 | Same 32 |
| Correlated order/duplicate variants | 96 | Same 96 |
| Matches to the separate reference | 84 | **96** |
| Disagreements | **12** | 0 |
| Plans whose financial projection depended on order/duplicates | **6** | 0 |

These are **32 synthetic plans with three correlated variants each**, not 96 independent trials or an external accuracy estimate. The author knew the assessor source. Registration preceded the first assessment of these cases; controls developed after discovery are labeled separately. The archive retains the original failures, frozen original assessor, registration and construction/reference sources. The default verifier never executes the archived `register.py` or starts a model, node, signer or network request.

## Controls and limits

The eight registered families cover complementary finalized fragments, one/no matching anchor, repeated identity, growing partial views, complete `FINAL`, open horizon and conflicting identity. Each uses zero, tight-budget, permitted and u128-boundary amounts. Correct required outputs and independent B are held fixed to isolate financial behavior.

Five hand-calculated reference controls were checked before the study. Four post-discovery development tests cover incompatible combined ancestry, pending-to-terminal upgrades in either order, body/outcome evidence split across views, and unrelated final heads. Four deliberate source defects restore the old selection, accept unanchored effects, invent completeness or ignore identity conflict; the suite detects each. Tampered registration/reference/old-engine bytes fail before archived code is executed.

The 43 prior baseline reports remain identical except for the explicitly declared engine version. The [raw-model study](PROPOSAL_STUDY.md) now requires `--replay` when the engine source changes. Only its report version is normalized for historical hash comparison; all other report fields must still match. Actual current and historical-normalized hashes, and both engine source hashes, are separate. Model responses and registered input bytes remain unchanged. Derived current Scenario Lab reports are regenerated; the v0.8.0 versions remain archived beside them.

This study does not add fresh native execution, general contract adapters, token/bridge coverage, an external author, or an external blind evaluation. It corrects the supported inspector's behavior on explicitly synthetic partial evidence. Workcell's broader fresh contract-execution scope is not established by these results.

## Three short reviewer paths

- **Partial evidence, proven excess:** at least 8 against 5; breach remains proven, total remains unknown, both outputs pass.
- **Unfinalized is unknown:** no matching finalized anchors for A; A stays unknown, complete independent B remains within scope.
- **Complete, allowed control:** full supported `FINAL` evidence gives exactly 5 against 5; both tasks and outputs pass.

Export any displayed case using **Keep this run in CI**, or:

```sh
python -I -S tools/export_bundle.py async-partial-union episode.json
python -I -S gate.py --bundle episode.json
```

The second command exits **1** for the proven breach. `async-unfinalized` exits **2**; `async-allowed` exits **0**. A verifier's exit 0 means reproduction/agreement, not that every intentionally adverse episode passed.

Evidence: [registration](../evidence/async-study/registration.json), [pinned archive index](../evidence/async-study/index.json), [original results](../evidence/async-study/original-results.json), [current reproduction](../verification/async-study.json). All data are local controlled or explicitly constructed evidence; there is no production-security guarantee or ranking claim.
