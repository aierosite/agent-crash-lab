# From an agent episode to a CI decision

Use Crash Lab when a retry can spend twice or when a paid API can return a wrong answer. Capture and evaluate one episode in a test environment before promoting an agent change. It is an inspector, not a payment gateway.

## Try the complete contract first

```sh
python -I -S tools/export_bundle.py double-payment episode.json
python -I -S gate.py --bundle episode.json
# exit 1: useful answers passed, but A committed 0.2 against its 0.1 authority

python -I -S tools/export_bundle.py durable-recovery episode.json
python -I -S gate.py --bundle episode.json
# exit 0: both independently declared tasks stay within scope and output passes
```

The UI can import that same `episode.json`, inspect causal source pointers and export the actual report. The browser edition and desktop route invoke the same Python `assess_bundle` validator. Unknown outer fields and non-string source data are rejected by both.

## Bind your own test episode

1. Declare the task owner, allowed recipients, per-intent principal/count limits, recovery obligations and required output **before execution**. Set a meaningful reference rather than deriving the expected answer from the agent's own reply.
2. Collect exact raw recording bytes, native transactions/receipt bodies/outcomes, scoped inventory and recorded task outputs. The supported profile is the finite owned near-sandbox 2.14/protocol 88 profile documented in [ARCHITECTURE.md](ARCHITECTURE.md), not arbitrary public RPC output.
3. Bind the source byte hashes in the owner container. Use the exported bundle's contract: `format`, `task_utf8`, `sources_utf8`, optional `classification`. UTF-8 strings preserve the original source bytes; do not parse/reformat a capture after hashing it.
4. Inspect the report and fail CI on an observed breach/output failure. Treat missing, conflicted, unsupported or rejected evidence as inconclusive, not success. Extend a protocol adapter only with new profile-specific evidence and controls.

`gate.py` exits **0** for fully concluded declared checks, **1** for an observed breach or required-output failure, **2** for rejected/inconclusive evidence or absent financial authority and no observed failure. A known failure takes precedence over uncertainty elsewhere. A task without a required-output obligation does not gain one from the UI.

## Small example

The owner authorizes task A to spend 0.1 NEAR for an inventory answer. A worker pays, reaches FINAL, then exits before storing its acknowledgement. A naive restart pays again. The answer is correct, but A spent 0.2. Independent task B is also priced at 0.1 and is legitimate. Global amount matching would confuse these tasks; receipt/intent binding distinguishes them.

This demonstrates the recorded process-crash window. A pre-broadcast hash journal controls that window; it is not proof of exactly-once settlement under every fault. Never turn a passed replay into permission to move real funds.
