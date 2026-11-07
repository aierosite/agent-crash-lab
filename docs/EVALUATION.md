# What the evaluation does — and does not prove

The v0.6.1 evaluation checks whether this inspector distinguishes allowed work, observed payment/output violations and unresolved evidence within its declared native-transfer/inventory profile. It also checks whether the test controls detect deliberate implementation defects. It does not estimate general agent accuracy, prove arbitrary contract safety or rank this project above another implementation.

## Reproduce on the current source

Python 3.12+, standard library only, no credentials:

```sh
python -I -S tools/evaluate_suite.py --out evaluation-run
```

Use a new output directory. `run.json` means started; only `results.json` records a completed run. The command never overwrites an existing directory. It writes every generated blueprint, bundle, oracle expectation, actual report and comparison, plus the manual controls and all mutation outcomes. Source digests are checked again before completion. Source changes during the run prevent certification.

Exit **0** means all 192 comparisons, 11 controls, nine mutation checks and 56 domain samples agree with their specified expectations. It includes correctly reported failures and unknowns; it does not mean all evaluated episodes are safe. Exit **1** means the completed evaluation found disagreement or an undetected/crashing mutation. Exit **2** means the evaluation could not complete, including an existing output directory or incompatible source. A partial run has no completed results.

The evaluator executes reviewed Python source, including the local inspector, oracle and in-memory mutated assessor copies. `--source PATH` selects another reviewed checkout of this same project. It is not an upload interface for untrusted code. Mutations never alter source files on disk.

## Selection before results

The [selection record](../evidence/evaluation/selection.json) preserves the original registration time, source commit, relevant frozen source hashes and the SHA-256 of the original prospective plan. The original study used the byte-verified v0.6.0 release, commit `5b13536d2e9dadaad035a94c305e17b50bc880b8`, before changing the oracle. Sixteen seeds were derived from `SHA256("acl-q04-v0.6.0-eval:" + decimal(i))`, `i = 0..15`, taking the first four bytes as a big-endian unsigned integer. Every seed used case indices 0 through 11. No cases were excluded after observing their result.

The generator and assessment source were already known to the author. The seed list was prospective relative to execution, not an external blind sample. After this study these selections are regression data, not unseen evaluation data. The structural family still uses the same owned archived receipt topology.

To repeat the original study, obtain the exact v0.6.0 release into a separate directory, then run the current evaluator with `--source PATH_TO_V0_6_0 --out original-evaluation`. Exit **1** and 16 domain disagreements are expected: the old oracle's marker bound was wrong. The remaining specified checks should pass. The [original result](../verification/evaluation-v0.6.0.json) is retained rather than replaced with a green result. Timing and provenance-dependent report hashes can differ with harness/source versions; compare the declared semantics and source digests.

## Observed results

| Check | Frozen v0.6.0 | After the oracle correction |
|---|---:|---:|
| Selected generated comparisons agreeing | 192/192 | 192/192 |
| Distinct transaction/action structural shapes | 140 | 140 |
| Allowed / violation or failed output / unknown gates | 64 / 96 / 32 | 64 / 96 / 32 |
| Hand-calculated controls agreeing | 11/11 | 11/11 |
| Deliberate semantic mutations detected without a crash | 9/9 | 9/9 |
| Marker/SKU domain disagreements | 16/56 | 0/56 |

The [current replay result](../verification/evaluation-current.json) records exact source hashes and all per-case outcomes. No fresh model call, signing or network transaction was used. The pure assessment engine is unchanged by the oracle fix.

The manual controls independently specify equal-price intents, multiple actions in one transaction, allowed installments, duplicate payments, wrong/absent output, zero/free work, missing receipt context, an open financial horizon and repeated observation of the same transaction. Incomplete evidence must not turn into a complete zero total; a known breach must still take precedence over a different intent's uncertainty.

The nine mutations change actual assessor/workbench source in memory: remove intent filtering, count actions as hashes, erase financial incompleteness, count zero transfers as settlements, accept a wrong answer, pass an unresolved gate, deduplicate equal-priced independent payments, treat equality with a cap as a breach, and ignore altered content. Each mutation has named killing controls. Crashes are recorded separately and cannot count as successful detection. This is adequacy against these nine faults, not a mutation score for all possible bugs.

## The fixed discrepancy

The core reference accepts identity markers containing 1–256 **UTF-8 bytes**. The old separate oracle instead accepted up to 128 **characters**. It rejected valid 129/256-byte ASCII markers and accepted 260-byte four-byte Unicode text and lone surrogates. Across four marker fields that produced 16 disagreements. The oracle now validates encoded byte length and Unicode scalar text directly, using a separate implementation. SKU text remains limited to 128 UTF-8 bytes; Lab documents remain limited to eight rows. Error messages state the applicable byte limit.

## Remaining evidence limits

The oracle, controls, generator, mutation definitions and evaluator share a project author. Process isolation and separate calculations do not provide independent authorship or an external audit. Passing planned synthetic cases is not proof of performance on unseen agent deployments. Fresh contract execution, broader asynchronous/payment families, additional separately authored controls and a guided capture-to-CI workflow remain separate work. Workcell's broader contract adapters and fresh-execution search are not replicated by this offline study.
