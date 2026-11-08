# Causal principal recovery

The recovery view keeps each failed payment separate. Required principal, proven return and proven elsewhere amounts are shown by generating parent, with links to the actual parent/refund actions. Gas returns are excluded. Rows can be scrolled with arrow keys on small screens. Identical amounts and destinations do not merge two different obligations. The original inspector engine is unchanged (0.1.2).

## Two archived conditions, not twelve native trials

This archive was produced on 3 November 2026, before the final product evaluator. It contains one owned protocol-88 sandbox chain, two signed root attempts and two conditions using the deliberately unrestricted official test contract:

| Condition | Native observation | Allowed recovery | Other recipient |
| --- | --- | ---: | ---: |
| RF01 | Two failed 0.1 NEAR children; two distinct successful principal refunds | 0.2 NEAR | 0 |
| RF02 | Same amounts; the second child has an explicit different refund destination | 0.1 NEAR | 0.1 NEAR |

The pre-product plan allowed only the vault as a recovery recipient. Raw account queries independently show vault/outsider deltas of 0/0 in RF01 and -0.1/+0.1 NEAR in RF02; the caller paid gas separately. The verifier rereads those query results and the failed-parent/generated-refund/body/outcome links, rather than trusting only derived summary flags. Four principal refund identities and ten system-receipt roles are checked. The original capture bytes, public transaction signatures, plan and separate same-operator reread are preserved. No private keys were exported in that archive. Hashes establish byte consistency, not consensus authentication or external provenance.

The current study has twelve source-informed inputs over those two conditions: a combined scope, two separately declared policy scopes, missing-body views, complementary partial views, one visible allowed/diverted refund, an unanchored projection, an invalid extra view and a structurally consistent identity-conflict control. The other archived condition is explicitly declared unrelated in a single-condition scope; it is not asserted safe. Reconstructed owner policies are assessment declarations, not historical customer promises.

The partial views, visibility masks and block-anchor records are **constructed**. They were not returned by a node and do not constitute new execution. The original archive contains no required task/model output; the interface says Not required and exit-0 text does not invent a passed output.

## Reproduce the study

```sh
python -I -S tools/verify_recovery_study.py
python -I -S tools/verify_recovery_study.py --output my-recovery-replay.json
python -I -S tools/export_bundle.py sibling-refunds-returned episode.json
python -I -S gate.py --bundle episode.json
# exit 0 for this explicitly scoped recovery policy; no output obligation declared
```

The standard-library verifier uses exact sealed source bytes to reconstruct all three registration stages. It reruns the separate original plan-level reference, rereads raw balances/roles, reproduces full frozen-engine report hashes and the three deliberately changed inspector implementations. The changed implementations omit generating-parent association, ignore the refund recipient or hide a known partial-evidence breach. They are mutation controls, not deployed vulnerabilities. No network, model, signing or chain call is made. A changed current engine requires an explicit reassessment; historical reports are never silently replaced. Existing output files are not overwritten.

The primary example uses RF01 alone for exit 0 and RF02 alone for exit 1. The partial example keeps RF01 assessable while RF02 remains inconclusive, exit 2. This verifies scoped preservation without claiming independent episodes or an agent success rate. The legacy baseline summary covers merchant totals; these new recovery assertions are enforced by the dedicated replay suite and browser contract, rather than a fabricated merchant-total golden value.

## The first reference error remains visible

Initial registration: `registration.json`. A prospective pre-evaluation amendment changed constructed partial requests to `wait_until: NONE` and strengthened direct raw-query checks: `registration-amended.json`. Both original source snapshots and inputs remain available.

The first engine evaluation agreed with ten of eleven expectations. One extra view changed the refund receiver while keeping the old outcome executor. It was structurally invalid, so the inspector rejected that view and preserved the existing valid conclusive diversion evidence while losing complete coverage. The original reference had incorrectly expected a native-identity conflict.

`reference-correction.json` records the post-result correction. It distinguishes an invalid extra view from a structurally consistent identity disagreement, and prospectively adds the latter control. The corrected reference agrees with twelve of twelve inputs. **This is a reference/fixture correction, not an inspector accuracy improvement.** The tool also reproduces the original one-disagreement result and every original report digest. No failed initial result was erased or relabeled as a blind holdout.

## Response and interface checks

A separate counterexample showed that the published v0.9.1 browser contract accepted the same recovery-parent identity twice. The candidate rejects it before drawing a recovery row or summary. Distinct sibling obligations remain valid. The Node contract suite exercises the actual browser validator and leaves accepted reports unchanged.

Actual local-Python and WebAssembly checks compare complete reports for all three curated examples and an imported malformed owner policy. That malformed declaration stays unknown without crashing the valid recovery display. Actual downloaded CI inputs are executed with the CLI for gates 0, 1 and 2. Receipt links were checked from opened source metadata, rather than assuming display order equals report-array order. Mobile checks cover a 390 x 844 viewport, two themes and keyboard scrolling; they do not establish full WCAG compliance.

## Scope and sources

This is a same-author, source-informed study of archived native data and correlated projections. A separate implementation/process is not independent authorship or an external blind audit. No new native/model run, wallet, payment or production contract test occurred. Broader adapters and independent evaluation remain open; no competitive ranking is inferred.

The pinned nearcore source was reviewed at [receipt.rs](https://github.com/near/nearcore/blob/bc4e9e8cfb03d9e82f027883055624e18576993e/core/primitives/src/receipt.rs). The full upstream source file is not redistributed here; its reviewed digest is recorded in `PROVENANCE.json`. The fresh tag lookup timed out and was not treated as new version verification. Current official documentation: [refunds](https://near.github.io/nearcore/RuntimeSpec/Refunds.html), [transaction finality and incomplete receipts](https://docs.near.org/api/rpc/transactions). Workcell's failed-payout entitlement checks motivated this focus; its broader fresh contract execution is not claimed by this replay study.
