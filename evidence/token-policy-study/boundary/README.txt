Pre-publication response-boundary corrections

The interface/* captures and original package from the earlier development step predate these corrections. They are retained as history, not presented as the current inspector's reports. Their inspector fingerprint is d22312838aa7652c943742b95641fcfc8ea661c2cf16e0567019c5cb90fa9cbd. The final current-source browser import record is verification/token-policy/browser-verified.json, with exact module, primitive, guard, UI and shared-codec fingerprints and91 actually operated imports. tools/verify_policy_browser.py replays it offline; it does not launch a browser or independently grade correctness.

The initial guard accepted five of six constructed invalid financial responses: explicit-null input IDs and output edges were aliased to omitted fields; a null receipt-list inherited an omitted-list fallback; invalid Boolean/missing RPC IDs were accepted. One Boolean/numeric mismatch was already rejected by the old JS guard, while the old Python reader accepted it. An explicit-null RPC ID is a positive control and remains supported. All six invalid responses are rejected by the current guard after resealing only their inspector hashes to current code, so changed hashes do not count as semantic detection.

A subsequent wire check, preserved separately in ../wire, reproduced three additional bad-response acceptances: result and error together, null error and Boolean error code, each before a valid FINAL observation. The corrected profile enforces result/error exclusivity and the error object's integer code/string message. Valid transient errors and compatible pending observations remain covered by earlier positive controls. These are separate source-informed development baselines, not an unseen benchmark or an external audit.

Primary protocol reference: https://www.jsonrpc.org/specification
No new RPC requests, financial transactions, SDK executions or model calls were used for these controls.
