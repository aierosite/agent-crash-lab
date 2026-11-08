# From an agent episode to a CI decision

For the concise interactive path, see [Inspect → reduce → CI](WORKFLOW.md). The CI panel exports the exact current input as `episode.json`; the displayed gate matches the CLI. A saved episode tests that recording, not a new agent build.

Use Crash Lab when a retry can spend twice or when a paid API can return a wrong answer. Capture and evaluate one episode in a test environment before promoting an agent change. It is an inspector, not a payment gateway.

For caller-supplied token RPC bodies, use the [passive capture workflow](PASSIVE_CAPTURE.md).
It retains original bytes, explicit owner assignments and uninterpretable replies,
then builds the existing token-policy input without making a network request.
Its financial gate does not grade useful work; the native episode contract below
retains separate required-output checks.

## Try the complete contract first

```sh
python -I -S tools/export_bundle.py double-payment episode.json
python -I -S gate.py --bundle episode.json
# exit 1: useful answers passed, but A committed 0.2 against its 0.1 authority

python -I -S tools/export_bundle.py durable-recovery episode.json
python -I -S gate.py --bundle episode.json
# exit 0: both independently declared tasks stay within scope and output passes
```

The UI can import that same `episode.json`, inspect causal source pointers and export the report. The UI, HTTP endpoint and CI gate validate the original bundle bytes with the same Python decoder. The decoder accepts UTF-8, UTF-16 and UTF-32, with or without a byte order mark. Use UTF-8 for portable files. Duplicate JSON members, nonstandard number literals and malformed encodings are rejected. Re-exporting an imported bundle preserves the original file bytes. The inner task and source strings retain their separate UTF-8 and hash rules. The file limit is 9 MiB. The outer decoder also caps structure at 4,096 tokens before parsing. Each whole quoted string, bracket, brace and comma counts once. Whitespace outside strings is skipped. This limit applies to the envelope and leaves the inner evidence limits separate. The CLI exporter uses UTF-8 with CRLF line endings on Windows and Linux so the generated catalog matches the staged file byte for byte. The embedded task and source bytes stay exact. The browser displays directional and other control characters in evidence labels as Unicode escapes. The Raw panel divides very long text into display sections to keep scrolling responsive. Use Find next in Raw report for case-sensitive matches across those sections. The search wraps after the last match and keeps focus on the control used. Placement runs in the next animation frame so the report can settle. Editing, resetting, or submitting again cancels any pending placement. In a very short window, the focused control may be above the visible result. The next Tab or Shift+Tab reveals the newly focused control without smooth scrolling. Pointed in-page links can scroll smoothly when the browser permits normal motion. For search terms longer than 65,536 UTF-16 code units, browsers with CSS Highlights color the full match and move to its start. Other browsers use standard text selection. Copy JSON still exports the original report text. Payment rows use the exact report identity when opening receipts. Finding and payment links place related receipts first. Every receipt remains available and open details stay open when switching proof routes. Citation file names and pointers use the original receipt order. In Useful work, Review unresolved output opens the first unresolved required output without changing the primary finding. No recorded answer means the observation was read and had no answer field. Answer not verified means the report could not establish an answer. An unverified source pointer identifies the attempted lookup. Trust & scope and Raw report show the full diagnostics. Import retains keyboard focus while inspection runs. Choosing a new file clears the previous inspection immediately, including when reading fails or the file exceeds the size limit. The primary control opens the file picker when corrected input is required. A malformed bundle needs corrected input. A task rejected by the evaluator still has a downloadable report. After a temporary inspection failure, Retry inspection keeps the selected detail panel. The Run control and its live status show browser startup progress. The workbench shows results and enables downloads after validating the response and rendering the report. An unreadable evaluator response clears the result and offers a retry. Invalid JSON or Unicode in a bundle has an explicit correction message. Rejected and failed reports from the evaluator still have their own downloads. A partial response offers Retry inspection. The payment and useful work cards carry any interpretation notes. Raw JSON and citation previews show readable escapes, while Copy JSON and downloads retain the original report, citation or bundle bytes. When the browser worker message protocol changes, version both the worker URL in `web/app.js` and the script URL in `web/index.html`. Verify an already-open browser tab after reloading.

Reports keep exact numbers across the CLI, local inspector and browser replay. An observed integer outside -9007199254740991 through 9007199254740991 uses the same exact_json_number descriptor as a decimal. Its digits are a string, and its exponent is zero. The evaluator compares the original values and export preserves input bytes. The 2 MiB compact report limit applies after this representation is built. An expanded report that exceeds it returns resource_report.

## Verify a receipt citation offline

Open **Allowed installments**, choose **Review 2 linked actions** and expand the second principal action for intent A. Use **Save citation** in that row and **Export bundle** on the same case. This example has two 0.05 NEAR actions in one receipt. The receipt ID alone does not distinguish them.

1. Parse the outer bundle JSON. For each entry in the citation's `sources` map, hash the UTF-8 bytes of the matching decoded `sources_utf8` string. Compare the SHA-256 value with the citation and the binding in `task_utf8` before parsing the inner source.
2. Run `python -I -S gate.py --bundle episode.json`. Compare the citation's `run_id` and `core_sha256` with `report.scope.run_id` and `execution.coreSha256`. Find `fact_id` in `report.native_facts` and match its action index and both source references.
3. Resolve `action_ref.pointer` and `outcome_ref.pointer` in the named sources. Check that both refer to the same recorded RPC result, that its transaction hash equals the fact's `tx_hash`, and that the receipt outcome's ID and executor match the fact's `receipt_id` and `to`. [JSON Pointer evaluation](https://www.rfc-editor.org/rfc/rfc6901.html#section-4)
4. Select the action by provenance.
   - For `observed`, the action pointer identifies a receipt body. Match its `receipt_id` to the outcome ID and its predecessor and receiver to the fact's `from` and `to`. Select `receipt.Action.actions[action_index]`. In Allowed installments the second transfer has index 1 and a deposit of 50000000000000000000000 yoctoNEAR.
   - For `derived_initial`, the Source field says **From transaction**. The action pointer identifies the transaction. Check that the signer and receiver are the same account and that this account matches both fact accounts and the receipt executor. The root `transaction_outcome` must match the transaction hash and signer and name the cited outcome as its sole child. Confirm that the child's body is absent from `receipts`. Select `transaction.actions[action_index]`. [NEAR transaction status with receipts](https://docs.near.org/api/rpc/transactions#transaction-status-with-receipts)
5. For a transfer or function call, match its deposit to the fact's requested amount. Read the recorded outcome and the report's execution state and finality before interpreting the committed amount. The gate evaluates the separate policy and useful-output checks.

The `self-function-deposit` entry in `BASELINES.json` names the archived task and source files for a self-call example. In a bundle made from those files, rows 1 and 2 both point to transaction action 0 and request 0.1 NEAR. The first commits and the second rolls back. The citation format and the row number are the same for both source types.

Browser downloads name the curated case and artifact type. Imported files use a short prefix of the input file's SHA-256. The name omits the original filename and run ID. The number in a collapsed action matches its citation filename and stays fixed when linked actions move. Action index inside the row is the zero-based index in that receipt. A receipt summary shows a committed amount only when the outcome and finality are established in the report. A known amount at a recorded final head can appear alongside incomplete coverage. The requested amount in the opened row is a separate field. An invalid receipt amount displays Amount unavailable. An incomplete receipt binding leaves the row metadata visible and suppresses Save citation for that row. Use the offline steps above to resolve both pointers against the bundle. Use the report and full source hashes for verification.

The citation identifies bytes and a specific action within them. The assessment assumes the capture's origin and the owner's declarations. A matching hash cannot authenticate the capture or establish network consensus.

## Bind your own test episode

1. Declare the task owner, allowed recipients, per-intent principal/count limits, recovery obligations and required output **before execution**. Set a meaningful reference rather than deriving the expected answer from the agent's own reply.
2. Collect exact raw recording bytes, native transactions/receipt bodies/outcomes, scoped inventory and recorded task outputs. The supported profile is the finite owned near-sandbox 2.14/protocol 88 profile documented in [ARCHITECTURE.md](ARCHITECTURE.md), not arbitrary public RPC output.
3. Bind the source byte hashes in the owner container. Use the exported bundle's contract: `format`, `task_utf8`, `sources_utf8`, optional `classification`. UTF-8 strings preserve the original source bytes; do not parse/reformat a capture after hashing it.
4. Inspect the report and fail CI on an observed breach/output failure. Treat missing, conflicted, unsupported or rejected evidence as inconclusive, not success. Extend a protocol adapter only with new profile-specific evidence and controls.

`gate.py` exits **0** for fully concluded declared checks, **1** for an observed breach or required-output failure, **2** for rejected/inconclusive evidence or absent financial authority and no observed failure. A known failure takes precedence over uncertainty elsewhere. A task without a required-output obligation does not gain one from the UI.

## Small example

The owner authorizes task A to spend 0.1 NEAR for an inventory answer. A worker pays, reaches FINAL, then exits before storing its acknowledgement. A naive restart pays again. The answer is correct, but A spent 0.2. Independent task B is also priced at 0.1 and is legitimate. Global amount matching would confuse these tasks; receipt/intent binding distinguishes them.

This demonstrates the recorded process-crash window. A pre-broadcast hash journal controls that window; it is not proof of exactly-once settlement under every fault. Never turn a passed replay into permission to move real funds.
