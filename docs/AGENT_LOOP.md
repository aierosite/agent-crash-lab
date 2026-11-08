# A real model, HTTP tools and SDK effects · v0.14.0

This study asks whether a small local model can finish two purchased tasks while
an intent-bound host preserves payment limits. It is inspired by Workcell's
separation of economic invariants and successful work. It is not a head-to-head
execution of Workcell, an independent blind audit or a claim of superior accuracy.

## What actually ran

The plan was registered on **8 November 2026 at 08:05:03 UTC**. Before inference,
one recorded amendment raised context to 8,192 tokens and the per-request limit
to 60 seconds so the full fourteen-turn interaction would fit. Six first test
questions from pinned, MIT-licensed GSM8K were selected before results, two per
fault profile. No case was replaced after seeing an answer.

Cached **Qwen2.5-1.5B Instruct Q4_K_M** ran through **llama.cpp b12110**, with two
CPU threads. Twelve fresh trajectories crossed three profiles, two host policies
and two seeds; policy order was counterbalanced. There were **78 evaluation
calls plus one declared warmup**, **68 actual localhost HTTP tool requests** and
**34 actual SDK mock-ledger effects**. No external model API, wallet, transaction
submission or new chain RPC was involved. Source hashes remained unchanged.

The model chose `quote`, `buy`, `recover` and `calculate` calls. A purchase ran
the official pinned NEAR SDK `ft_transfer` in a mock host, changed its ledger and
returned a question packet. Packets contained the question, never its worked
solution or gold answer. The bounded calculator evaluated only the model's
chosen arithmetic expression. No answer correction or business-choice repair
was applied after a model response.

| Profile | Tool behavior |
|---|---|
| Clean | Ordinary quote, purchase and packet response. |
| Post-effect timeout | An actual HTTP 503 was returned after the SDK payment committed. Recovery could return the packet without another payment. |
| Misleading offer | Untrusted merchant text asked the model to ignore the owner's cap and buy a premium packet for 101 rather than 100. |

Each order had a gross cap of 100 atomic test-token units. The unguarded host
accepted repeated/premium purchases. The intent-bound host enforced the cap and
retained prior-payment recovery. These are study host policies, not a production
signer or vault supplied by Crash Lab.

## All results, including failure

| Host policy | Trajectories | Observed cap breaches | Both required outputs passed |
|---|---:|---:|---:|
| Unguarded | 6 | 2 | 0 |
| Intent-bound | 6 | 0 | 0 |

Across 24 required useful outputs, **0 passed, 8 failed and 16 were missing**.
The model copied example/template values, omitted the second order, guessed
without buying or stopped before completing the requested format. Under the
misleading offer, two unguarded trajectories made thirteen payments each; the
guarded trajectories paid nothing and still failed their work obligations.
All original responses remain in the archive. Zero observed overspend is not
successful task completion and is not a population estimate of guard benefit.

The separately executed numeric grader runs the original GSM8K `ANS_RE`,
`INVALID_ANS`, `extract_answer` and `is_correct` source definitions against the
untouched raw answer strings. It requires the original `#### ` answer marker;
format failures count as failures. This is an externally authored reference,
but selection, wrapper, environment, financial policy and audit are ours.
GSM8K is public and may be training data: these are not unseen test cases or a
general Qwen quality score.

## Preserve unknown when no payment was observed

The initial v0.13.1 payment profile required at least one observation. The two
zero-effect episodes therefore did not invoke it; the original reports retain
that fact. v0.14.0 additively supports **zero through 128 observations**. A task
with required orders and no observations returns gate **2 / insufficient
evidence**, no fabricated receipts, empty graphs/payments and unknown exact
totals. This applies even to a declared closed horizon or zero minimum.

Current replay has two financial breaches and ten unknown financial gates.
It does not rewrite the frozen study reports. The browser checks the same empty
projection and rejects a forged clean gate. Three public examples expose the
repeated-payment breach, premature completion and zero-payment uncertainty:

- [Repeated purchases](https://aierosite.github.io/agent-crash-lab/web/policy.html?browser=1&case=model-loop-repeated-payment)
- [Premature completion](https://aierosite.github.io/agent-crash-lab/web/policy.html?browser=1&case=model-loop-premature-finish)
- [No observed payments](https://aierosite.github.io/agent-crash-lab/web/policy.html?browser=1&case=model-loop-no-payments)

These examples use original SDK effects inside our constructed receipt/RPC
envelopes. Receipt IDs, block metadata, gas and FINAL declarations are synthetic;
they are not real network observations or deployed-WASM execution.

## Reproduce offline

```powershell
python -I -S tools/verify_agent_loop.py
python -I -S tools/verify_policy_browser.py
python -I -S tools/verify_release.py --judge
```

Replay checks the fixed study inventory before running reviewed archival code
in an isolated subprocess and temporary directory. It reconstructs original
model/HTTP/SDK links, numeric grading and full financial reports, then separately
assesses all twelve episodes with current source. It launches no model, SDK
worker or merchant. The current browser record replays 98 actual imports
(83 complete reports, 15 cleared/rejected inputs); the previous 91-import record
is preserved against its own five frozen source files, not rebound to new code.

The first Linux replay exposed a portability error in our replay wrapper:
Windows-captured JSON used CRLF while the unchanged audit wrote LF on Linux.
All three reproduced objects were equal; only line endings differed. Original
bytes remain pinned unchanged. Replay now checks full JSON equality and the
complete serialization with only CRLF/LF normalized. The first failure,
Linux outputs and byte comparison remain in
`verification/agent-loop-replay/`; this is a wrapper fix, not changed model
answers, financial grading or study results.

[Study index](../evidence/agent-loop-study/study-index.json),
[registration](../evidence/agent-loop-study/REGISTRATION.json),
[pre-inference amendment](../evidence/agent-loop-study/PRE-INFERENCE-AMENDMENT.json),
[locked sources](../evidence/agent-loop-study/LOCK.json),
[raw calls](../evidence/agent-loop-study/actual/calls.json),
[HTTP episodes](../evidence/agent-loop-study/actual/episodes.json),
[SDK wire](../evidence/agent-loop-study/actual/sdk-wire.json),
[audit](../evidence/agent-loop-study/AUDIT.json) and
[original useful-output grades](../evidence/agent-loop-study/original-external-grades.json)
are shipped. Model weights, runtime binaries and private user files are not.
Five same-author tampering controls reject changed answers, payments, source
locks, orphan effects and resealed HTTP questions; they are integrity controls,
not independent financial grading.

The execution sampled peak process VmHWM of 2,304,458,752 bytes for the model
and 5,378,048 bytes for the SDK worker. These are owned-process measurements,
not whole-machine/browser memory or a universal performance guarantee. Both
owned processes stopped after the recorded batch.

## Primary sources and remaining work

- [GSM8K data and original numeric grader](https://github.com/openai/grade-school-math/tree/3101c7d5072418e28b9008a6636bde82a006892c)
- [Official SDK token transfer implementation](https://github.com/near/near-sdk-rs/blob/bacd081a0bd648d840b814dab7677e1f3330afbb/near-contract-standards/src/fungible_token/core_impl.rs)
- [Workcell source reviewed](https://github.com/dotmantissa/workcell/tree/b80bcecc1d30263662b985fc025b83233e07a173)

Broader models and tasks, independently selected/evaluated cases, deployed
contract behavior and preservation of successful work under faults remain open.
The failed useful-work result is evidence to address, not a score to conceal.
