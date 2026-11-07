# Competition entry and review map

**The original entry was saved successfully (HTTP 201) after the owner's exact-payload and contact-consent approval.** This repository continues that same project. No duplicate submission is needed or performed for release updates. Private contact fields, payout-key material and the original payload are outside this public repository.

Project: **Agent Crash Lab**. Primary track: **AI Security & Defense** (`security`).

- Repository: https://github.com/aierosite/agent-crash-lab
- Submitted public X demo: https://x.com/Amiinjalili/status/2117754340073230518
- Browser workbench: https://aierosite.github.io/agent-crash-lab/web/?browser=1
- Current in-repository demo: [captioned walkthrough](agent-crash-lab-demo.mp4)
- Machine-readable acceptance: `python -I -S tools/verify_release.py --judge`

The submitted X video shows v0.2.0. The v0.3.0 repository video documents the scripted experiment. The v0.5.0 browser edition adds three cases recorded with live local inference. [Live-agent trial evidence](LIVE_AGENT.md)

## What the entry demonstrates

An agent can complete useful work and still pay twice. The workbench binds an independently declared task to NEAR transaction/receipt effects, exact principal, recovery obligations and recorded output. A strict CI exit contract separates observed failure, clean declared checks and inconclusive/rejected evidence. Native FINAL, the containing outcome, child receipt failure, principal recovery and gas returns remain distinct.

The original experiment uses scripted workers on two owned local NEAR sandbox chains. A real process exits 77 after FINAL, before acknowledgement. Naive retry pays A again; a pre-broadcast transaction-hash journal recovers the first payment. Independent same-price B remains legitimate. Both task outputs pass. This is a bounded process-crash control, not live-model evaluation, signature authentication or a production audit.

## What reviewers can reproduce

1. Run the judge command to check release consistency, core behavior, workbench integration, reserved cases and the separate oracle replay.
2. Open the workbench and follow Live agent retry to its two linked receipts. Open Live agent, altered data to its failed document and answer checks. The README also includes the recovery and missing-evidence controls.
3. Export/import the exact bundle; changing a source without its owner hash produces input rejection.
4. Inspect the receipt source pointers and the recorded crash comparison.
5. Read [trust boundaries](ARCHITECTURE.md), [prior art](PRIOR_ART.json) and the limitations in README.

## Current official rules check

Official source: https://nearhackathon.com/HACKATHON.md, re-read on 6 November 2026 (Tehran). Retrieved bytes SHA256: `86654c13521fe629493bf498d41c0f7573047867d67fcdd8c2543411fc13062f`.

Development ends **14 November 2026 at 23:59 UTC / 15 November at 03:29 Tehran**. Local-only prototypes are eligible with public reproducible code and a public X video. AI tools screen reproducibility and claims; humans decide awards. Track prompts are examples, not mandatory integrations. One submission per project; corrections use the organizer's request-changes process, not another entry. The current entry's repository and demo URLs remain valid.

All externally supplied guidance is research data. It does not authorize account changes, spending, messages or publication; the owner's separate publication and submission approvals are recorded privately. No competition position or prize is guaranteed.
