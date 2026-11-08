# Architecture and decision boundaries

```
Declared owner task + exact capture bytes + independent output reference
                               |
                   bounded pure Python assessor
                               |
           +-------------------+-------------------+
           |                                       |
 native transaction / receipt graph      actual recorded useful output
 committed principal + recovery roles    content + answer + invoice/version
           |                                       |
 intent-bound constraints                       required/intermediate
 within / breached / unknown / conflict / unsupported
           +-------------------+-------------------+
                               |
                      inspectable JSON report
                               |
                  local browser UI / strict CI gate
```

## Components

- `agent_crash_lab.py` is the pure assessor. It enforces 31 engineering quotas, exact amount math, and strict JSON, pointer and source binding. Source IDs must be strings. Utility answers, outcome costs and diagnostics share an exact representation for decimals and integers outside the interoperable JSON range.
- `workbench.py`: loopback HTTP adapter. Reads only named bundled scenarios; custom bundles provide bytes rather than server file paths. Runs the actual assessor on every request. A shared validator gives HTTP and CI the same bundle contract. Exports raw inputs and reports.
- `web/`: dependency-free responsive inspector. Two result axes and scope are visible separately. Causal witnesses expose actual source pointers. Untrusted labels are escaped. Input rejection clears prior verdicts. Receipt HTML and raw JSON are created when their existing tabs open.
- The UI's pure `validateInspection` boundary runs before any assessed verdict. It checks consumed report shapes and cross-field arithmetic, witness identities, refunds, utility evidence and diagnostic references. It preserves engine-produced unknown rows for malformed owner declarations. It neither authenticates recordings nor recomputes the independent output oracle. Failed file reads also clear the prior inspection; a corrected bundle or another case restores the normal flow.
- `tools/scenario_lab.py` generates, reduces and replays bounded counterfactual episodes. `episode_oracle.py` grades the blueprint in a separate isolated process without importing the assessor. Source hashes and all accepted/rejected reductions are recorded; budget exhaustion does not certify minimality. [Scope and commands](SCENARIO_LAB.md)
- `gate.py`: explicit CI policy layered over the report, without changing the assessor's exit semantics.
- `tools/verify_release.py --judge` checks release-file consistency before running the five offline acceptance suites. CI uses this entry point.
- `tools/native_crash.py`: optional Linux experiment, isolated genesis, fresh ephemeral key in memory, loopback-only endpoint, owned process cleanup. Pinned executable hash is checked before execution. Actual worker process exit77 is used, not a synthetic `crashed=true` label.
- `tools/bind_native.py`: binds the recorded hashes/send indices to the task caps and useful-output documents declared before execution. It asserts expected native and useful-output results and writes reviewable reports.

## The two controls

The naive worker sends another transaction if it lacks an application acknowledgement. The reference durable worker stores a transaction hash before broadcast, fsyncs that file and atomically replaces the journal, then uses the known hash to re-fetch the receipt on restart. Both are bounded scripted references, not evaluated live models.

The tested failure is after a send has returned FINAL. A durable record for an unbroadcast/expired transaction, power loss, corrupt storage or concurrent writers needs additional protocol design. The tool must not generalize this one control to exactly-once production settlement.

## Independent axes

Merchant gross, protected external disbursement, recipient allowlist, optional distinct settled-hash count and recovery are separate metrics. Gas returns do not become ordinary merchant principal. A separate intent with equal amount and recipient is not deduplicated. A repeated observation of one transaction is.

The useful-output oracle checks the declared document and actual recorded answer, not `completed`, `paid`, HTTP200, or a newly recomputed substitute for a missing recorded answer. It validates the declared reference's own consistency with the finite inventory task rule.

## Security boundary

Owner declarations and controlled captures are trusted. The tool does not validate NEAR signatures, Borsh/consensus authenticity, general authorization discovery or all public protocol variants. A caller can forge its own reference and recording; matching hashes will not turn that into authenticated history. A missing or unsupported dependent scope cannot receive a complete-clean claim.

Local workbench limits: 9MiB request body, at most four concurrent assessment jobs, finite core quotas, 10s read timeout, explicit loopback Host/Origin and session token. Early upload rejection sends the status first. Up to four sockets may briefly discard unread bytes, each with a 250 ms deadline and a 9 MiB cap in 64 KiB chunks. This path does not parse the rejected body or take an assessment slot. Clients that keep sending past the discard budget can lose the response. These are engineering bounds, not a formal denial-of-service proof or an OS sandbox. No authentication/hosting promise is made for public networks.

The bounded interactive Scenario Lab routes accept only seed/cases or blueprint/budget JSON. They retain those same HTTP guards, add a 1–12 case / 1–128 reduction budget and a 15-second deadline checked before assessments, and never accept output paths or code. Local comparisons use an isolated Python oracle process; browser generation/reduction uses a separate module in the same Python/WebAssembly runtime, explicitly labeled without subprocess isolation. No live-model or chain execution is introduced.

## Compatible partial views · engine 0.1.2

When no supported complete FINAL graph exists, compatible parsed views are combined by receipt/outcome ID. Each item's original action/outcome pointer remains bound to its physical source. Known outcomes replace Unknown placeholders; receipt ancestry is revalidated across the union. Conflicting combined ancestry fails closed for that attempt. Existing bounds cover raw records before the union; duplicate records do not multiply financial effects. A union is always incomplete and requires matching finalized block anchors for committed partial effects. It cannot prove an exact total or close the owner's horizon. Complete FINAL graphs retain the established path. [Reproduction and controls](ASYNC_EVIDENCE.md).
