# A 60–90 second demo

[Watch the 72-second captioned walkthrough](agent-crash-lab-demo.mp4)

This published video shows the original v0.2.0 appearance. The current v0.2.2 report interface and refreshed screenshots present the same recorded experiments and unchanged assessor.

The attached walkthrough uses actual UI captures of the running local workbench. It is a frame-based walkthrough, not a continuous screen recording and not a live-model execution. Every numerical result is from an actual local assessment or the documented fresh native experiment.

1. **Problem (0–12s)** — “Your agent finished the task. Did it pay twice?” Open the first scenario. Its correct answer is C03 / 17 units. A actually paid0.2 against0.1; independent B paid its allowed0.1.
2. **Control (12–25s)** — Switch to Recover without repaying. Both workers actually crashed after FINAL; the durable reference re-fetches its known transaction. A and B each pay0.1, both outputs pass.
3. **Evidence (25–40s)** — Open Causal evidence, expand a payment. Show transaction, receipt, containing outcome, action index and bound source pointer.
4. **Useful work (40–53s)** — Paid, wrong answer: financial scope can be within while actual output fails. This is why a payment receipt is not a task-completion oracle.
5. **Reproduction (53–70s)** — Native comparison lists actual crash exits, five sends, the stopped nodes and evidence hash. Export/import bundles or run the three test commands. No wallet or API key needed.

Published X demo: https://x.com/Amiinjalili/status/2117754340073230518

> An agent can finish the task and still pay twice. We built Agent Crash Lab at NEAR HACKATHON: actual local NEAR crash/restart receipts, payment limits AND useful-output checks. Try it: https://github.com/aierosite/agent-crash-lab @NEARProtocol #NEARHackathon

The actual 72-second video is attached to that post. The owner authorized publication through this account. Neither the post nor the video claims a production audit or live-model benchmark.
