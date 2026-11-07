# Generate → reduce → replay

Scenario Lab tests the payment/output inspector with explicit counterfactual episodes. It varies transaction order and count, transfer actions, exact amounts, independent task limits and inventory-output faults. It constructs new inputs from an owned archived receipt topology. It does **not** execute contracts, sign transactions, authenticate history or discover arbitrary contract interfaces.

## Run

Python 3.12+, standard library only. From the repository root, use new output directories:

```sh
python -I -S tools/scenario_lab.py search --seed 42 --cases 12 --out generated-42
python -I -S tools/scenario_lab.py shrink --blueprint generated-42/case-1/blueprint.json --budget 128 --out reduced-42
python -I -S tools/scenario_lab.py replay --blueprint reduced-42/reduced/blueprint.json --bundle reduced-42/reduced/bundle.json --out replayed-42
```

Each case includes `blueprint.json`, an importable `bundle.json`, the oracle's `expected.json`, the actual `report.json` and `comparison.json`. Open the [browser inspector](https://aierosite.github.io/agent-crash-lab/web/?browser=1) or local workbench and **Import bundle** to inspect the same episode. `summary.json` records completion; a run header alone is not proof of completion or a live process. Existing output directories are rejected without modification.

`search` exits **0** when the assessor agrees with every planned expectation. This includes correctly diagnosed violations and correctly unresolved inputs. It is a test-verification result, **not** a claim that every generated episode was safe. Its `gates` and `aggregateEpisodeGate` separately record actual episode outcomes. A reference mismatch exits **2** and never counts as a successful finding.

`replay` and `shrink` return the actual episode gate: **0** within declared scope with required work passed; **1** observed violation or failed required output; **2** inconclusive, invalid input or reference disagreement. Thus the second and third commands above are expected to exit **1**. Replay retains the exact original outer bundle bytes, including their encoding/formatting. Only timing metadata may differ; the deterministic core report should match when its source hash matches.

## The reference

`episode_oracle.py` reads the versioned blueprint, never an assessor report. It imports neither the assessor nor the workbench. CLI and local-workbench comparisons launch it in a separate Python process with `-I -S`, checks its source digest and uses bounded input and a timeout. It calculates principal per intent, the number of distinct positive-settlement transactions, and the declared output-fault expectation independently of receipt traversal.

The generator and oracle were written by the same project author. Separate implementation/process execution is not independent authorship, a blind benchmark or an external audit. The same-author, source-informed acceptance tests include hand-calculated controls that distinguish multiple actions in one transaction, separate equal-price intentions, permitted installments, zero/free work and positive payments with wrong or absent output.

## Reduction contract

The original authority and output reference stay byte-equivalent at the blueprint level. A named predicate such as `constraint:A-merchant` must survive every accepted reduction. For a financial finding, useful outputs must stay passed. For an output finding, payment constraints must stay within scope, and an originally paid output must retain a positive payment. A different failure, a malformed report, an inconclusive result or oracle disagreement cannot substitute for the original predicate.

The reducer tries deleting transactions/actions, then lowering amounts within a finite assessment budget. It checks single deletions again against the final result before setting `deletionMinimal: true`. Exhausting the budget leaves that claim unproven. No globally minimal counterexample is claimed. `reduction.json` records every attempted candidate, acceptance decision and input digest.

## Scope and limits

- All generated bundles say `synthetic` and declare `counterfactual` authority. Their packets explicitly say they are not signed transactions. Template digests, generator/oracle source digests and a blueprint digest are recorded; these are consistency bindings, not signatures.
- The initial generator covers serialized native Transfer episodes and a finite inventory-output task. It does not add FT/rebasing accounting, arbitrary actors, asynchronous fault families or a new consensus/signature verifier.
- Changing the seed creates new values, structures and orderings within this declared family. This is not a claim of unseen real-world security accuracy.
- Archived Qwen calls and actual sandbox transfers remain a separate [experiment](LIVE_AGENT.md). Generating or reducing these inputs makes no new model call or network transaction.
- [Workcell](https://github.com/dotmantissa/workcell/tree/b80bcecc1d30263662b985fc025b83233e07a173) informed the search/reduction/replay workflow. Its broader contract adapters and fresh testnet executions are different capabilities. This implementation does not copy its source or claim feature parity.

The fifth offline judge suite, `test_scenario_lab.py`, checks generation determinism and variation, a separately executed oracle, allowed-work controls, reduction preservation/budget, exact replay, input errors and no-overwrite behavior.

The oracle uses 1-256 UTF-8 bytes for document identity markers and 1-128 bytes for SKU text, rejecting invalid Unicode scalar text. The finite Lab profile allows 1-8 rows. [Reproduce the evaluation and deliberate-defect checks](EVALUATION.md).

The [interactive workflow](WORKFLOW.md) also generates and reduces fresh inputs in the browser. Its reference runs as a separate oracle module in the same WebAssembly runtime, with no process isolation; the interface states this difference. The same-author and counterfactual limitations apply to both modes.
