# Current 60-second walkthrough

[Watch the v0.3.0 captioned repository demo](agent-crash-lab-demo.mp4)

This updated video uses actual UI captures from the running v0.3.0 workbench. It is a frame-based walkthrough, not a continuous screen recording. The original native experiment was recorded on 3 November 2026; the UI re-assesses those exact bytes locally. No live model, wallet connection or new public-chain transaction is shown or implied.

| Time | Visible action/result |
|---|---|
| 0–10s | Open Double payment: a scripted worker finished useful work after a real crash/restart. |
| 10–20s | A committed 0.2 NEAR against 0.1; B legitimately committed 0.1. Both recorded outputs passed. |
| 20–30s | Recover without repaying: the bounded journal control re-fetches its known payment; both A and B commit 0.1. |
| 30–40s | Open a causal receipt: transaction, receipt, execution/finality and bound source pointers. |
| 40–50s | Paid, wrong answer: financial checks can pass while recorded output fails its independent reference. |
| 50–60s | Recorded native comparison: two owned chains, five sends, actual process exit 77/restart, scripted workers and stopped nodes. |

The journal is a reference for the tested post-FINAL process crash, not an exactly-once production protocol. Receipt hashes establish local consistency, not authenticated consensus. See README and ARCHITECTURE.md for full trust boundaries.

## Interactive browser edition · v0.4.0

[Run the same Python core without installing it locally](https://aierosite.github.io/agent-crash-lab/web/?browser=1). The runtime download and optional CDN trust are explained in README. The 60-second video above remains the accurately labelled v0.3.0 UI walkthrough; the underlying recordings/core are unchanged.

## Submitted public demo

[The original 72-second X post](https://x.com/Amiinjalili/status/2117754340073230518) remains the demo URL of the already-saved competition entry. It shows v0.2.0. Updating this repository video does not replace that X attachment or create another submission. The core assessment and underlying recorded experiment remain unchanged.

The published post identifies NEAR HACKATHON and includes @NEARProtocol and #NEARHackathon. The owner's publication approval and exact entry confirmation are retained outside this public repository.
