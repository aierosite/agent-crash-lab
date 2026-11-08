# Raw proposals: money within limits, work unfinished

Eight fixed local-model trajectories, registered before inference on **8 November 2026 at 00:16:03 UTC**, exercise an over-budget offer, a legitimate A purchase, A retry with an exact paid-invoice journal, independent same-price B, and inventory answers when the guarded host delivered a document. The plan includes the prompts, inputs, selection, grammars, seeds, source and artifact hashes. One amendment added process identity and graceful shutdown before any model calls; selection and prompts were unchanged.

This addresses a gap left by the earlier [native/model experiment](LIVE_AGENT.md), which disclosed ten calculator-corrected selections. Here raw answers stay raw. The study does not replace or relabel that earlier experiment.

## Observed outcomes

| Measure | Result |
|---|---:|
| Fixed trajectories completed / omitted | 8 / 0 |
| Evaluation calls / declared warmup | 40 / 1 |
| Decision proposals / policy-compliant proposals | 32 / 20 |
| Over-budget BUY proposals | 0 |
| Repeat BUY with a paid-invoice journal | 0 |
| Independent B BUY proposals | 4 / 8 |
| Delivered answer calls / raw answers correct for delivered data | 8 / 1 |
| Required outputs: passed / failed / unknown | **1 / 7 / 8** |
| Trajectories with both required outputs passed | **0 / 8** |

No outputs were repaired, resampled or dropped. Eight optional answer calls were absent because the guarded trajectory never delivered those documents. The model never chose RECOVER. Skipping a legitimate purchase or recovery can avoid spending while leaving required work incomplete. The three displayed examples are post-study illustrations; all eight trajectories remain in the archive and replay.

The two financial projections were identical in every trajectory. This batch provides **no fresh financial-violation sensitivity or guard-benefit estimate**. Historical native violation evidence and generated synthetic controls are separate datasets.

## What is real, and what is constructed

- **Actual observation:** local Qwen2.5-1.5B-Instruct Q4_K_M inference through owned llama.cpp b12110 on CPU; raw requests, returned text/token counts, timestamps and guarded host events. The owned model process exited and its temporary staging directory was removed.
- **Constructed projection:** transaction IDs, packet bytes, RPC/receipt bodies and native payment effects. They were built from an owned archived receipt topology using the frozen v0.7.0 builder. No wallet, signer, chain node, mainnet or testnet transaction ran in this study.
- **Delivery adapter:** documents went directly into in-memory model inputs. `httpStatus: 200` in a utility observation encodes delivery for the inspector; it is not a captured merchant HTTP request.
- **Two policies:** `unprotected` and `guarded` both reuse proposals from the same guarded trajectory. They are correlated counterfactual projections, **not two fresh model runs or a causal treatment/control experiment**.
- **Reference:** a separately implemented and separately executed Python process reconstructs host state and computes inventory answers from the locked inputs and raw responses. The author/operator is the same. This is neither independent authorship nor an external blind audit.
- **Resources:** two CPU threads, context 2048, parallelism one. Peak RSS was not captured; the attempted later observation found that the owned process had already stopped. Model file size is not a memory-use measurement. No full packet-level traffic audit was performed.

## Reproduce without downloading a model

From a trusted copy of this release, with Python 3.12+:

```sh
python -I -S tools/verify_proposal_study.py --replay
python -I -S test_proposal_study.py
```

The verifier first checks the byte-pinned study index, registration, raw observations and locked sources. Only then does it run the reviewed separate reference with `-I -S`. With `--replay`, it explicitly reassesses all 16 archived projections with the current inspector. It compares reference assertions and the full historical report SHA256 after normalizing only the declared engine version to 0.1.1. Every other report field must match. Actual current hashes, normalized historical hashes and both source hashes are reported separately. Without `--replay`, a changed assessor source is rejected; the recorded model run is never relabeled as a fresh run. Exit **0** means agreement of inspector and evidence; the episode gates remain fourteen **1** results and two **2** results. There are **64 financial + 32 output assertions across 16 correlated projections of eight trajectories**, not 96 independent trials.

The tests include nine pre-inference synthetic model-double controls, which are explicitly rejected as actual inference. They cover always-buy overspending/retry, legitimate B, skip-all, perfect proposals, tie/zero inventory, wrong answers, malformed answers, source and trace tampering. Five packaged controls additionally check full replay, altered raw/task/source files, a rewritten index, changes to actual host/model records and the three workbench examples. Default replay launches no model or network service.

To export an example through the existing bundle workflow:

```sh
python -I -S tools/export_bundle.py proposal-missing-work episode.json
python -I -S gate.py --bundle episode.json
```

The second command exits **2**: A's answer passed, B's required output is unknown. Both financial constraints remain within scope; partial work is not a clean pass. Browser inspection executes the same Python assessor through WebAssembly, with origin text **Recorded Qwen · synthetic payments**. Replay in either UI mode calls no model.

## Review the archive

[Study index](../evidence/proposal-study/study-index.json) binds all captured files. [Registration](../evidence/proposal-study/locked-plan.json), [amendment](../evidence/proposal-study/AMENDMENTS.json), [raw calls](../evidence/proposal-study/actual/calls.json), [host events](../evidence/proposal-study/actual/cases.json), [execution record](../evidence/proposal-study/actual/execution.json), [runtime log](../evidence/proposal-study/actual/runtime.log) and the three locked study sources retain exact original bytes. The registration's `baseRoot` is historical operator metadata; the portable replay does not use or execute that path. The archived `bind.py` and `local_trial.py` are provenance source, never invoked by default judge replay.

The [original audit](../evidence/proposal-study/original-audit.json) records ten actual-data tampering controls. Hashes make local changes detectable against a trusted index; they do not authenticate capture origin, model honesty, consensus or third-party identity.

Artifacts: [Qwen pinned model repository](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9), model SHA256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`; [llama.cpp b12110](https://github.com/ggml-org/llama.cpp/releases/tag/b12110), cached Ubuntu archive SHA256 `368227edcc229be5f9bed16a2223d79b5e41d0ac2e19bcf5825e82291c060e55`. Already cached files were used; release downloads contain no model weights or runtime binaries.
