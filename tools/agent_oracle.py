"""Independent reference for the owned direct-transfer trials.

Run as a separate process. Reads raw finalized merchant balances and owner
reference data. It neither loads Crash Lab nor consults its transaction labels.
"""
import argparse
import json
import random
from pathlib import Path


def expected_answer(document):
    gaps = [(max(0, row["forecast"] - row["available"]), row["sku"]) for row in document["rows"]]
    largest = max(gap for gap, _ in gaps)
    return {"sku": next(sku for gap, sku in gaps if gap == largest), "units": largest}


def make_plan(seed, variant):
    randomizer = random.Random(seed)
    price = randomizer.randint(6, 14)
    documents = {}
    for intent in ("A", "B"):
        largest = randomizer.randint(5, 9)
        gaps = [randomizer.randint(0, 2), randomizer.randint(3, 4), largest]
        if variant == "reordered" and intent == "A":
            gaps = [2, largest, largest]
        randomizer.shuffle(gaps)
        rows = []
        for index, gap in enumerate(gaps):
            available = randomizer.randint(0, 3)
            rows.append({"sku": f"{intent}{index+1}", "available": available, "forecast": available + gap})
        documents[intent] = {"resource": "inventory-snapshot", "version": "v1", "invoice": intent,
                             "source": "owned-local-merchant", "rows": rows}

    steps = [("A", True), ("A", False), ("B", False), ("C", False)]
    policies = ["naive", "durable"]
    if variant == "reordered":
        steps = [steps[2], *steps[:2], steps[3]]
    if variant in ("reduced", "single"):
        steps = steps[:2] if variant == "reduced" else [("A", False)]
        del documents["B"]
        policies = ["naive"]
    # A real HTTP delivery will carry this controlled, predeclared corruption.
    deliveries = json.loads(json.dumps(documents))
    if variant == "corrupt":
        deliveries["B"]["rows"][0]["forecast"] += 1
    return {"seed": seed, "variant": variant, "steps": steps, "policies": policies,
            "capCents": price, "quoteCents": {"A": price, "B": price, "C": price + 1},
            "expectedDocuments": documents, "deliveries": deliveries}


def merchant_balances(recording, run, plan):
    refs = run["balanceCheckpoints"]
    if len(refs) != len(plan["steps"]) + 1 or refs != sorted(set(refs)):
        raise ValueError("Missing or unordered balance checkpoints")
    query = {"request_type": "view_account", "finality": "final", "account_id": recording["merchant"]}
    balances, heights = [], []
    for index in refs:
        rpc = run["rpcObservations"][index]
        request, response = rpc["request"], rpc["response"]
        if request["method"] != "query" or request["params"] != query or request["id"] != response["id"]:
            raise ValueError("Balance response does not match finalized merchant query")
        result = response["result"]
        balances.append(int(result["amount"]))
        heights.append(result["block_height"])
    if balances != sorted(balances) or heights != sorted(heights):
        raise ValueError("Unexpected balance or block movement on the owned isolated chain")
    return balances


def reference(recording, plan):
    """Reconstruct per-intent effects from fixed, serial balance windows."""
    rows = []
    for run in recording["runs"]:
        balances = merchant_balances(recording, run, plan)
        totals = {intent: 0 for intent, _ in plan["steps"]}
        counts = dict.fromkeys(totals, 0)
        deltas = [right-left for left, right in zip(balances, balances[1:])]
        for (intent, _), delta in zip(plan["steps"], deltas):
            totals[intent] += delta
            counts[intent] += int(delta > 0)
        utility = {}
        for intent, document in plan["expectedDocuments"].items():
            observations = [obs for obs in run["utilityObservations"] if obs["invoice"] == intent]
            if len(observations) != 1:
                raise ValueError("Expected one terminal observation per required intent")
            obs = observations[0]
            if "httpStatus" not in obs:
                utility[intent] = "unknown"
                continue
            correct = (obs["httpStatus"] == 200 and json.loads(obs["responseUtf8"]) == document
                       and obs["recordedAnswer"] == expected_answer(document))
            utility[intent] = "passed" if correct else "failed"
        rows.append({"policy": run["policy"], "balances": [str(n) for n in balances],
                     "deltas": [str(n) for n in deltas], "gross": {k: str(v) for k, v in totals.items()},
                     "counts": counts, "utility": utility})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("precommit", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.precommit.read_bytes())
    print(json.dumps({"runs": reference(json.loads(args.recording.read_bytes()), plan),
                      "answers": {intent: expected_answer(doc) for intent, doc in plan["expectedDocuments"].items()}}))


if __name__ == "__main__":
    main()
