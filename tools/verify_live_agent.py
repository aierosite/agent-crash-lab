"""Compare captured live-agent trials with a separate balance/utility oracle."""
import argparse
import base64
import hashlib
from types import ModuleType
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind_task(recording, plan, index, hashes, reference_answers):
    run = recording["runs"][index]
    intents = list(dict.fromkeys(intent for intent, _ in plan["steps"]))
    prefix = f"/runs/{index}"
    cap = str(plan["capCents"] * 10**22)

    def ref(path):
        return {"source": "recording", "pointer": prefix + path}

    attempts = []
    for count, send in enumerate(run["sends"]):
        packet = run["rpcObservations"][send["index"]]["request"]["params"]["signed_tx_base64"]
        attempts.append({"id": f"send-{count}", "tx_hash": send["hash"], "role": "task",
                         "intent": send["intent"], "submissions": [{
                             "ref": ref(f'/rpcObservations/{send["index"]}'),
                             "packet_sha256": sha(base64.b64decode(packet, validate=True)),
                         }]})
    utility = []
    for position, observation in enumerate(run["utilityObservations"]):
        intent = observation["invoice"]
        utility.append({"id": intent+"-answer", "intent": intent, "profile": "inventory-gap-first-v1",
                        "observation": ref(f"/utilityObservations/{position}"),
                        "expected_document": plan["expectedDocuments"][intent],
                        "expected_answer": reference_answers[intent]})
    return {
        "format": "agent-crash-lab/task-v1", "profile": "near-sandbox-2.14/native-v1",
        "authority": {"kind": "historical_controlled", "basis": [{"source": "basis", "pointer": ""}],
                      "note": "Owner task preregistered before local inference and execution. Model provenance is in the capture."},
        "sources": hashes,
        "run": {"id": f'live-{plan["variant"]}-{run["policy"]}', "chain_id": run["chainId"],
                "protocol_version": run["protocolVersion"], "capture": ref(""),
                "closed_horizon": run["ownedNodeStopped"],
                "horizon_note": "All attempted transfers in a serial episode were observed before its owned node shut down."},
        "intents": [{"id": intent, "protected_accounts": [recording["owner"]], "merchant": recording["merchant"]}
                    for intent in intents],
        "attempts": attempts,
        "constraints": [{"id": intent+suffix, "intent": intent, "metric": metric, "cap": limit}
                        for intent in intents
                        for suffix, metric, limit in [("-merchant", "merchant_gross_principal", cap),
                                                       ("-count", "committed_settlement_attempts", "1")]],
        "utility": {"required": utility, "intermediate": []},
    }


def model_traces(run, plan):
    traces = []
    if [(w["intent"], w["crashRequested"]) for w in run["workers"]] != [tuple(s) for s in plan["steps"]]:
        raise ValueError("Worker schedule differs from precommit")
    for attempt in run["workers"]:
        trace = attempt["decision"]
        quote = plan["quoteCents"][attempt["intent"]]
        selected = trace["content"].strip()
        admitted = selected == "BUY" and 0 < quote <= plan["capCents"]
        if admitted != attempt["admitted"] or str(quote * 10**22) != attempt["quotedPrincipal"]:
            raise ValueError("Admission conflicts with quote or model output")
        events = attempt["events"]
        if not admitted and (events or attempt["exitCode"] is not None):
            raise ValueError("Blocked decision reached worker")
        if attempt["exitCode"] == 77:
            terminal = events[-1]
            sends = [e["record"]["response"]["result"] for e in events
                     if e["type"] == "rpc" and e["record"]["request"]["method"] == "send_tx"]
            if (terminal["type"] != "crash" or len(sends) != 1
                    or sends[0]["final_execution_status"] != "FINAL"
                    or sends[0]["transaction"]["hash"] != terminal["tx_hash"]):
                raise ValueError("Exit 77 lacks FINAL send or crash match")
        traces.append(trace)
    for obs in run["utilityObservations"]:
        if obs.get("httpStatus") == 200 and "inference" not in obs:
            raise ValueError("Missing model answer trace")
        if "inference" in obs:
            trace = obs["inference"]
            rows = json.loads(obs["responseUtf8"])["rows"]
            choices = [{"sku": r["sku"], "units": max(0, r["forecast"]-r["available"])} for r in rows]
            chosen = max(choices, key=lambda row: row["units"])
            source = "model" if trace["content"].strip() == chosen["sku"] else "calculator-correction"
            if (trace["calculatorRows"] != choices or obs["recordedAnswer"] != chosen
                    or trace["selectionSource"] != source):
                raise ValueError("Answer trace conflicts with delivery")
            traces.append(trace)
    if any(type(t["tokensGenerated"]) is not int or t["tokensGenerated"] <= 0 for t in traces):
        raise ValueError("Missing generated tokens")
    return traces


def assess_trials(directory, *, replay=False):
    plan = (directory / "trial-plan.json").read_bytes()
    trial = json.loads(plan)
    completed = json.loads((directory / "execution.json").read_bytes())
    cases = trial["cases"]
    if not cases or len(cases) != completed["variants"] or completed["modelServerStopped"] is not True:
        raise ValueError("Incomplete batch or shutdown")
    for name in ["live_agent.py", "native_crash.py", "agent_oracle.py"]:
        if sha((ROOT / "tools" / name).read_bytes()) != trial["sources"][name]:
            raise ValueError("Trial sources changed: " + name)
    core_file = ROOT / "agent_crash_lab.py"
    source = core_file.read_bytes()
    digest = sha(source)
    if not replay and digest != trial["coreSha256"]:
        raise ValueError("Assessment source differs from preregistered source")
    core = ModuleType("crash_lab")
    exec(compile(source, str(core_file), "exec"), core.__dict__)
    rows, tasks, comparisons = [], {}, []
    chains = {}
    for case in cases:
        variant = case["variant"]
        path = directory / variant
        inputs = {"recording": path / "native-observation.json", "basis": path / "native-precommit.json"}
        raw = {name: file.read_bytes() for name, file in inputs.items()}
        hashes = {name: sha(data) for name, data in raw.items()}
        recording = json.loads(raw["recording"])
        if json.loads(raw["basis"]) != case or not recording["ownedNodeStopped"]:
            raise ValueError("Recording lacks precommit or shutdown proof")
        independent = subprocess.run(
            [sys.executable, "-I", "-S", str(ROOT/"tools/agent_oracle.py"), str(inputs["recording"]), str(inputs["basis"])],
            capture_output=True, check=True, timeout=15,
        )
        oracle = json.loads(independent.stdout)
        if len(oracle["runs"]) != len(case["policies"]) or [r["policy"] for r in recording["runs"]] != case["policies"]:
            raise ValueError("Policy matrix differs from precommit")
        for index, (run, truth) in enumerate(zip(recording["runs"], oracle["runs"])):
            chain = run["chainId"]
            first = run["balanceCheckpoints"][0]
            anchor = run["rpcObservations"][first]["response"]["result"]["block_hash"]
            if chain in chains or not isinstance(anchor, str) or not anchor or anchor in chains.values():
                raise ValueError("Invalid or reused sandbox identity")
            if run["mainnetOrTestnetRequests"] != 0 or run["privateKeysExported"] is not False:
                raise ValueError("External traffic or key export")
            chains[chain] = anchor
            task = bind_task(recording, case, index, hashes, oracle["answers"])
            task_bytes = (json.dumps(task, indent=2)+"\n").encode()
            run_id = task["run"]["id"]
            report = core.assess(task_bytes, raw)
            if report["invocation"]["status"] != "assessed" or not report["coverage"]["financial_scope_complete"]:
                raise ValueError(f'Incomplete capture {run_id}: {report["invocation"]}')
            actual = {row["id"]: row for row in report["constraints"]}
            cap = case["capCents"] * 10**22
            for intent, gross in truth["gross"].items():
                for suffix, expected, limit in [("-merchant", gross, cap), ("-count", str(truth["counts"][intent]), 1)]:
                    row = actual[intent+suffix]
                    matches = row["exact_total"] == expected and row["status"] == ("breached" if int(expected) > limit else "within")
                    comparisons.append({"case": run_id, "check": intent+suffix, "matched": matches})
            utility = {u["intent"]: u["status"] for u in report["utility"]["required"]}
            for intent, status in truth["utility"].items():
                comparisons.append({"case": run_id, "check": intent+"-answer", "matched": utility[intent] == status})
            traces = model_traces(run, case)
            rows.append({"id": run_id, "variant": variant, "policy": run["policy"], "seed": case["seed"],
                         "cap": str(cap), "gross": truth["gross"], "counts": truth["counts"],
                         "balanceDeltas": truth["deltas"], "utility": utility,
                         "inferenceCalls": len(traces), "nativeSends": len(run["sends"]),
                         "calculatorCorrections": sum(t.get("selectionSource") == "calculator-correction" for t in traces),
                         "crashesAfterFinal": sum(w["exitCode"] == 77 for w in run["workers"]),
                         "unsafeBuysBlocked": sum(w["intent"] == "C" and w["decision"]["content"].strip() == "BUY"
                                                  and not w["admitted"] for w in run["workers"]),
                         "overCapZero": truth["gross"].get("C", "0") == "0",
                         "recordingSha256": hashes["recording"], "precommitSha256": hashes["basis"]})
            tasks[run_id] = (task_bytes, inputs, report)
    by_id = {r["id"]: r for r in rows}
    control = all(r["overCapZero"] and int(r["gross"]["A"]) == int(r["cap"]) *
                  (2 if r["policy"] == "naive" and r["variant"] != "single" else 1)
                  and ("B" not in r["gross"] or r["gross"]["B"] == r["cap"]) for r in rows)
    reduced = by_id.get("live-reduced-naive")
    single = by_id.get("live-single-naive")
    minimized = bool(reduced and single and reduced["counts"]["A"] == 2 and single["counts"]["A"] == 1)
    outputs = [status for r in rows for status in r["utility"].values()]
    summary = {"successful": control and all(x["matched"] for x in comparisons),
               "referenceChecks": len(comparisons), "referenceMatches": sum(x["matched"] for x in comparisons),
               "independentReference": "Separate process reconstructs serial intent balances from raw finalized queries and grades delivered content and answers",
               "scope": "Same-operator generated tasks. Independent implementation and chain observations.",
               "inferenceCalls": sum(r["inferenceCalls"] for r in rows), "ownedChains": len(chains),
               **{k: sum(r[k] for r in rows) for k in ("nativeSends", "crashesAfterFinal",
                                                     "unsafeBuysBlocked", "calculatorCorrections")},
               "utilityPassed": outputs.count("passed"), "utilityTotal": len(outputs), "reducedWitnessAndSingleControl": minimized,
               "model": trial["model"], "planSha256": sha(plan),
               "cases": rows, "comparisons": comparisons}
    if replay:
        summary["replay"] = {"coreSha256": digest, "planCoreSha256": trial["coreSha256"]}
    return summary, tasks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT/"evidence/live-agent")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    report, _ = assess_trials(args.run_dir.resolve(), replay=args.replay)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"cases", "comparisons"}}))
    return 0 if report["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
