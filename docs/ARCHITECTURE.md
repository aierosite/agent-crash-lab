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

- `agent_crash_lab.py`: unchanged original pure assessor; 31 engineering quotas, exact amount math, strict JSON/pointer/source binding. It has no ambient IO or signing authority.
- `workbench.py`: loopback HTTP adapter. Reads only named bundled scenarios; custom bundles provide bytes rather than server file paths. Runs the actual assessor on every request. Exports raw inputs and reports.
- `web/`: dependency-free responsive inspector. Two result axes and scope are visible separately. Causal witnesses expose actual source pointers. Untrusted labels are escaped. Input rejection clears prior verdicts.
- `gate.py`: explicit CI policy layered over the report, without changing the assessor's exit semantics.
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

Local workbench limits: 9MiB request body, at most four concurrent assessment jobs, finite core quotas, 10s read timeout, explicit loopback Host/Origin and session token. These are engineering bounds, not a formal denial-of-service proof or an OS sandbox. No authentication/hosting promise is made for public networks.
