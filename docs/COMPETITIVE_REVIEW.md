# Competitive review · v0.4.0 snapshot

**Historical comparison.** The statements below describe the v0.4.0 review. v0.5.0 subsequently added the bounded live-agent experiment; v0.6.0 added [Scenario Lab](SCENARIO_LAB.md), v0.7.0 made search/reduction/CI interactive, and v0.8.0 adds a [raw-proposal study](PROPOSAL_STUDY.md) without calculator correction. v0.9.0 also fixes an order-dependent partial-evidence lower bound, with exact reproduction of the original failures and a portable synthetic study. These are original task-level implementations inspired by Workcell’s workflow; broader fresh contract execution and independent authorship remain open. Workcell still covers broader contract adapters and fresh testnet execution. The pinned heads of Workcell, HoldUp, Quittance and Tripwire were rechecked on 8 November 2026 (Tehran) and matched the revisions below. No competitor suite was executed.

[The v0.5.0 live-agent experiment and separate reference address the model and evidence gaps documented below.](LIVE_AGENT.md)

The closest overlap is **Workcell**, followed by **HoldUp**, **Quittance**, **Tripwire** and **NEXUS AiOS** for different parts of the problem. This is our evidence-based selection, not an official shortlist or ranking. The directory snapshot contained 128 public projects, 75 tagged Security; tags overlap and the event is still accepting entries.

The review read public READMEs and selected implementation files at the revisions below. We did **not** build or rerun competitors' suites. Reported test counts, AI runs and chain experiments remain their authors' claims. We additionally opened Quittance's public case and Tripwire's read-only drainer example: both returned an actual visible result, not just a landing page. This observation does not independently authenticate every upstream RPC response.

| Project / pinned source | Where it is ahead of Crash Lab | Scope and what we actually checked |
|---|---|---|
| [Workcell](https://github.com/dotmantissa/workcell/tree/b80bcecc1d30263662b985fc025b83233e07a173) | Generated action search, failing-sequence reduction, vulnerable/fixed contract replay, restricted treasury and an actual local-model policy path. Closest financial-testing prior art. | Read `src/invariants.ts`, `src/agent-policy.ts` and the evidence index. Independent liabilities/backing, entitlement and successful-payout controls are implemented; we do not claim to invent these. Its 30 testnet cases and local inference are author-reported, not rerun here. Directory-to-repository association is probable from the matching author/project, not an independently authenticated identity. |
| [HoldUp](https://github.com/sadrax4/holdup/tree/30ed05396d47cac76c23f436118f1a19d2c1d62d) | A practical hold/cancel/release workflow, deployed vault and investigation with live models reported by the author. Clear user consequence: stop a suspicious payment before release. | Selected vault source and README Status/ScamBench sections read. Reported 1,273 tests are not our result. Its README explicitly says the published benchmark is not a clean holdout; cached AI answers/scoring scripts are not all shipped. We do not translate those counts into a comparative accuracy score. |
| [Quittance](https://github.com/AustinChris1/quittance/tree/c2f8b286a18947d234b6c01e66c0b8656e09234f) | A real support problem, cross-chain receipt reconciliation and a public no-install interface. Excellent path from a transaction to an explanation and a next step. | Selected `classify.ts` rules read. The public $193K example rendered DELIVERED, source links, quote/minimum reconciliation and explicit public-RPC limitations. We did not pay, connect a wallet or verify its complete chain-data collection independently. It is mainly entered in other tracks, but is relevant receipt/UX prior art. |
| [Tripwire](https://github.com/Afar88/tripwire/tree/63c9dd2f8535ee2638d373109ccd216ab5088827) | Accessible read-only checker, testnet risk registry, guarded spending and optional AI second opinion. Preventive controls complement our after-execution inspector. | The hosted labelled demo-drainer returned BLOCK, risk 95/100 and a registry reason. Read `checker/src/outlayer-approver.ts`: decision mapping exists, while `submitVote` explicitly throws as a dry-run stub. That limit does not negate the separately deployed registry/vault. |
| [NEXUS AiOS](https://github.com/ykbojak-alt/nexus-aios/tree/0f6ed1c03144fa06529a1ecceabd0d2f3041c0c7) | A visible bid → work → verification → escrow payout lifecycle and a short judge path with linked transaction hashes. | README live-run/judge sections, command-policy JSON and selected escrow source inspected. Its demo is described as replaying a prior testnet run, not fresh execution on every view. We did not execute its agent workflow or independently resolve its eight transaction hashes. |

## The contribution we can defend

Crash Lab asks **two independent questions about one declared task**: did native effects stay within the owner's authority, and did recorded useful output satisfy its separately declared reference? A receipt can settle correctly while the task overspends. A correctly priced payment can buy a wrong answer. Equal-price task B, permitted installments, failed recoveries and unresolved receipt bodies prevent simple "two hashes = duplicate" shortcuts.

This is a narrow contribution alongside existing financial invariants, receipt reconciliation and guards. It does not make Crash Lab a stronger enforcement contract, general agent benchmark or more original project than every entrant. Our main recorded workers are scripted, not live-model agents. The core trusts the declared owner/reference and capture authenticity, within a finite sandbox protocol profile.

## Changes made after this review

1. **No-install inspection:** the public browser edition executes the exact unchanged Python assessor and shared bundle validator in a Web Worker. It is not a JavaScript rewrite or a precomputed result viewer. Desktop use remains standard-library-only.
2. **Checkable parity:** 19 previous bundles and eight curated scenarios produced reports identical to desktop; additional checks cover malformed shape, changed source bytes, export/reimport and the recorded native comparison. [Observed browser checks](../verification/browser-python.json) identify the runtime and evidence boundary.
3. **Deployment consistency:** the browser stages only catalogued files and checks their exact byte sizes/SHA256 before loading them. This detects partial/stale deployment; it is not a signature or proof of website/CDN authenticity.
4. **Clear integration and review:** a [capture-to-CI guide](INTEGRATION.md), explicit trust notice and direct browser/offline entry points reduce reviewer friction. Existing saved entry and X demo links remain intact.

## Official implementation execution added in v0.13.1

The official pinned NEAR SDK resolver now has actual Rust mock-host execution
evidence: 162 registered combinations matched the existing payment inspector,
with 28 policy/evidence controls and preserved first outputs. No engine fix was
needed. An opt-in fresh execution command and separate SDK CI workflow complement
offline replay. [Exact method and provenance limits](SDK_CONFORMANCE.md).
This addresses SDK implementation conformance, while independent end-to-end agent
grading, deployed-WASM behavior and a head-to-head Workcell run remain unproven.

## Workcell-inspired evidence workflow in v0.16.0

Workcell's public head was rechecked on 8 November 2026 at
`b80bcecc1d30263662b985fc025b83233e07a173`, unchanged from the source inspected
above. Its [architecture](https://github.com/dotmantissa/workcell/blob/b80bcecc1d30263662b985fc025b83233e07a173/docs/ARCHITECTURE.md)
separates backing, entitlement and successful authorized payout, preserves
uncertain executions, and binds replay to exact artifacts. We apply those useful
principles to our different task-level inspector; no Workcell code is copied.

| Principle | Concrete Crash Lab evidence | Remaining distinction |
|---|---|---|
| Useful payment and financial limits are separate | Six recorded billing trajectories satisfy the original external bill-utility predicate; three unguarded traces nevertheless breach the separately declared cap. Three protected traces retain one bill payment. | One fixed invoice/seed and a combined guard; not blind evaluation or a causal ablation. |
| Reproduce the original execution evidence | Sealed raw model/HTTP/SDK records, unchanged external predicate ASTs, full original/current report comparison, and opt-in fresh replay of all 30 recorded SDK calls. | Official SDK mock-host execution, not deployed WASM, signatures or authenticated consensus. |
| Make the failure easy to inspect | Four exact browser/CLI examples include the full repeated-payment trace, protected trace, a two-debit recorded prefix, and the unfinished native-tool attempt. | The prefix is a derived witness with an open horizon, not Workcell-style fresh contract shrinking or a global minimum. |
| Incomplete work cannot silently become success | The native failure stays unknown; the planned injection cases are explicitly labelled unexposed because the model never read the invoice. | No injection-defense result or universal agent-safety claim. |

[Billing methods, complete results and replay commands](BILLING_STUDY.md).
The next evidence priorities are actual injection exposure, additional tasks and
models, and independently authored blind cases. Workcell's broader fresh
contract adapters and contract-sequence reduction remain a real coverage gap;
more local test counts cannot establish comparative superiority.

## Recorded model exposure and paired review in v0.17.0

The new installed-run view replays six source-informed invoice traces across
three explicit context profiles and two policies. It exposes bill utility,
payment terms and finish separately. Four attack cases demonstrably received
the context. A role-spoof trace pays its bill and also an unauthorized fee; the
protected counterpart denies that fee. Their first three model inputs and tool
requests match before the different HTTP outcome. This is a post-hoc descriptive
comparison of preserved records, not a causal role-token or population result.

The plain fee-notice pair remains a failure of work in both variants: ten reads,
zero payments and no finish. Such a case cannot become a clean combined review
because no debit occurred. Both Python and the read-only browser port reproduce
full original audit/reference/payment objects; browser predicates share one
interpreter while local grading uses a subprocess. [Complete evidence and limits](RECORDED_AGENTS.md).

This extends the Workcell-inspired vulnerable/protected evidence workflow to
recorded task-level model decisions. It does not close the gaps in contract
adapter breadth, fresh deployed execution or independent blind evaluation.

## Remaining gaps

v0.14.0 adds a registered real local-model → HTTP tools → official SDK mock-ledger
loop, retaining all twelve trajectories and their failures. Of 24 required
useful outputs, none passed; two unguarded runs breached caps, while guarded
runs still failed their work. The numeric reference/grader is externally
authored GSM8K, but the wrapper, selection and financial grading remain ours.
This improves inspectable end-to-end evidence, not independent blind evaluation
or a head-to-head Workcell result. Workcell's public head remained b80bcecc when
rechecked on 8 November 2026. [Complete methods and negative results](AGENT_LOOP.md).

The v0.13.0 token-policy component applies the Workcell-inspired distinction between economic invariants to arbitrary supplied per-order policies. Gross commitment, recipient, burned refund and minimum SDK settlement are separate; allowed split payments, independent equal-price intents and returned promises remain supported. It follows recorded body/data-ID relations rather than treating root success or equal amounts as delivery. A Python inspector, a separately implemented browser response boundary and exact-input replay form one workflow. This is original source-informed implementation and grading, not an independently executed comparison with Workcell or a claim that Workcell lacks these capabilities. The two additional historical transaction-status observations are public-node reads, not fresh contract execution or authenticated consensus.

- **Broader live-agent/generalization evidence:** the archived native/model trials, earlier inference-only study and v0.14.0 real HTTP/SDK loop cover bounded local cases. The earlier study found 1/16 successful raw outputs; the new loop found 0/24 and two cap breaches. Receipt envelopes around SDK mock effects remain constructed. Independent authorship, an external blind evaluation and an external adopter study remain unproven. Source-informed regressions are not an unseen benchmark.
- **Network scope:** our actual payment evidence is owned local NEAR execution, not a fresh public-network deployment. The assessor does not authenticate consensus or signatures and does not accept arbitrary chain/contract profiles.
- **Prevention:** the tool diagnoses an episode; it cannot intercept a signer or enforce a vault rule. That is a complementary system, not a missing switch in this inspector.
- **Browser runtime trust:** the optional browser version downloads pinned Pyodide from jsDelivr and needs a modern WebAssembly-capable browser. Assessment inputs are not posted to a server by our code. For a runtime without CDN execution, use the offline ZIP and local Python.
- **Outcome:** there is no evidence-based way to promise first place, estimate win probability or infer judges' scores from repository test counts.

We made no competitor-directed transactions, registrations, messages or payments. The raw-proposal study records local inference only; the later agent-loop study adds actual local HTTP tools and SDK mock-ledger effects, without transactions or chain consensus. No production audit is implied.
