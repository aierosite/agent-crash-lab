# One episode, from inspection to a CI decision

## Inspect a captured agent run

1. Open the [browser workbench](https://aierosite.github.io/agent-crash-lab/web/?browser=1) or run `python -I -S launch.py` from the release directory.
2. **Import bundle** selects an existing `bundle-v1` recording. Payment authority and useful-output checks stay separate. Follow the finding to the linked receipt or required output, then review **Trust & scope** for unresolved evidence and assumptions.
3. Open **Keep this run in CI**. Download **episode.json** and place it beside `gate.py` in the release directory. Copy or select the displayed command:

```sh
python -I -S gate.py --bundle episode.json
```

The panel displays the expected exit code for the inspected input: **0** within declared scope with required work passed, **1** observed policy breach or failed output, **2** inconclusive/rejected. A known failure takes precedence over uncertainty elsewhere. Missing evidence never becomes success. The downloaded input retains the original imported bytes, including outer encoding and whitespace.

A saved fixture verifies only that recorded episode. To test a changed agent, run its own controlled capture harness again and supply the new episode. An old recording cannot establish that new agent code is safe. The [binding contract](INTEGRATION.md#bind-your-own-test-episode) requires owner authority and a meaningful task reference declared before execution; this inspector does not discover authorization or authenticate a public-chain history.

## Explore a newly generated finding

1. Open **Scenario Lab**, leave seed **42** and **6** cases, then choose **Generate & check**. This actually generates and evaluates new counterfactual inputs. Cases 0 and 4 are allowed controls, case 3 is unknown, and other cases show observed failures. Each case is listed separately; agreement with the reference does not mean every episode is safe.
2. Case 1 is selected as an eligible finding. A commits more than its fixed authority while both required outputs pass. Choose another case to inspect its actual report. An allowed or unknown control without an eligible single-axis finding has **Reduce finding** disabled.
3. Use a reduction budget of **128**, then choose **Reduce finding**. The original four transactions/nine actions reduce to one transaction/one action: **5 yoctoNEAR against the same 4-yoctoNEAR cap**. Required outputs still pass. The interface shows the preserved predicate, trial count and the limited minimality result. A budget of **1** stops earlier and explicitly leaves minimality unproven.
4. **Inspect original** and **Inspect reduced** switch between the actual inputs. **Save blueprint** and **Save reduction trace** let another reviewer repeat the operation. **Keep this run in CI** exports the currently inspected original or reduced input. Its expected gate remains 1 while the finding persists.

The reducer cannot substitute a different failure or change the authority/reference. It preserves successful complementary controls and an originally positive payment when reducing an output failure. Single-deletion minimality is not a globally smallest counterexample.

An arbitrary imported recording has no generated blueprint. Importing one, or selecting an archived case, clears reduction context. The inspector does not invent a blueprint for a real recording or label a packaged replay as a fresh search. Existing generated cases remain selectable as their own synthetic inputs.

## Execution modes and bounds

| Surface | Assessment | Blueprint reference |
|---|---|---|
| Local Python workbench | Actual local inspection | Separate Python process with `-I -S` |
| Static browser demo | Actual Python in WebAssembly | Separate original oracle module in the same browser runtime; no process isolation |

The interface states the mode. Both modes use the same original generator and reducer and produce matching core reports for the checked inputs. The oracle, generator and tests share the project author; this is not independent authorship or an external audit. Generated IDs and packets are synthetic and explicitly labeled. No model call, signing, wallet operation or chain transaction occurs.

The interactive search accepts a uint32 seed and 1–12 cases. Reduction accepts a blueprint and a budget of 1–128 assessments. A 15-second limit is checked before each assessment; a local oracle call also has its own five-second timeout. An incomplete operation cannot certify a finding or minimality. Use the [offline CLI](SCENARIO_LAB.md) for its larger stated budgets and saved per-trial outputs.

The local HTTP routes keep the existing loopback Host/Origin, session-token, content-type, 9 MiB body and four-job capacity checks. They accept no output path, executable source, shell command or external URL. Inputs and reductions remain in memory until a user downloads them. Browser execution stages catalog-pinned project source and an owned archived receipt topology; these consistency hashes do not authenticate financial history.

## Observed checks

The [workflow verification record](../verification/workflow.json) separates HTTP tests, source-informed regressions, actual browser interactions and remaining limitations. Six generated cases plus two reduction budgets matched complete CLI report hashes in local Python and browser WebAssembly. Downloaded allowed/failing/unknown inputs gave actual CLI exits 0/1/2 in both modes. A BOM/CRLF archived model capture retained its exact input bytes through both UI exports. Responsive/keyboard/busy/error-recovery checks are disclosed separately from financial correctness.
