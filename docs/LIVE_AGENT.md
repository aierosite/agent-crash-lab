# Live agent and independent reference

Qwen proposes whether to buy an inventory document. The host checks the quoted amount against the owner’s per-attempt limit before it starts a signing worker. The trial runs on an owned NEAR sandbox with fresh accounts. The worker crashes after the node returns FINAL. A naive retry sends again, while a durable pre-broadcast journal recovers the known transaction hash. An independent task can legitimately cost the same amount.

The model also proposes a SKU from calculator-provided shortage rows. The calculator corrects selections that violate the maximum-shortage and first-on-tie rule. The raw selection and correction are recorded separately. An altered merchant document can still produce the right answer for the wrong data. The owner’s original document and answer remain the reference for useful work.

The [preregistered plan](../evidence/live-agent/trial-plan.json) fixes seeds, prices, order, input documents, faults and code hashes. The archived RPC observations include finalized balance checkpoints before the episode and after each attempt. A separate Python process grades delivery and output and attributes balance changes by these windows. The oracle derives counts from nonzero balance changes because these trials permit at most one direct transfer in each serial window. Crash Lab independently walks signed transaction and receipt evidence. The verifier compares exact principal, settlement count and useful-output status per intent. [Observed local results](../verification/live-agent.json)

The trial matrix includes reversed task order, an equal-gap tie, an altered document, and an over-budget quote containing a seller instruction to buy anyway. It also executes a shorter two-attempt witness and a single-attempt control. The reduction establishes the smaller witness in this fault schedule. [Inputs and recordings](../evidence/live-agent/)

In the final local batch, the independent reference agreed on **54 of 54** checks. The eight runs recorded **41 model calls**, **18 sandbox transfers** and **seven post-FINAL worker crashes**. All six over-budget BUY proposals were blocked before they reached the worker. Twelve of fourteen required outputs passed. Both failures were the altered-document trials. The calculator corrected ten raw selections. An earlier run of the same three seeds with Qwen 1.5B and raw selection returned four correct required outputs. That comparison measures the added calculator check on these tasks.

## Reproduce

Replay all recorded comparisons with standard-library Python 3.12 or newer.

```sh
python -I -S tools/verify_live_agent.py --replay
python -I -S tools/verify_release.py --judge
```

Replay evaluates the captured inputs with the current assessor and reports both its hash and the preregistered hash. Paired runs can share one archive digest. Their chain IDs and capture pointers identify the two records within that archive. The verifier requires a completed, nonempty batch. Recorded chain IDs and first finalized merchant-balance block hashes must be distinct. It rejects a nonzero external request count or a key export flag in the capture. Fresh trial verification requires an exact preregistered assessor match.

Use the **Fresh live-agent trials** workflow in your own public fork for fresh seeds on a separate runner. It fetches the pinned Qwen GGUF, llama.cpp CPU runtime and NEAR sandbox and uses an isolated local chain for each trial. The job reports both oracle agreement and successful useful outputs. [Workflow and exact artifact URLs](../.github/workflows/fresh-agent.yml)

For a Linux or WSL run, obtain those same artifacts and install the optional signing dependency in an isolated Python environment. The runner verifies all three artifact hashes before it executes them. The model is approximately 1.12 GB and the output directory must be new.

```sh
python -m pip install -r requirements-native.txt
python tools/live_agent.py --runtime llama.tar.gz --model model.gguf --binary ./near-sandbox --output captures --seed 288013362 --seed 1641293917 --seed 302159703
python -I -S tools/verify_live_agent.py --run-dir captures
```

The browser and desktop workbench replay these captures. The verifier’s scope is the owned direct-transfer trial, with serial balance windows and declared inventory references. The case author also wrote the oracle. A separately hosted run tests reproducibility with new input seeds. Independent authorship and an external user study remain open.

Workcell covers wider contract and testnet execution and reports automatic failing-sequence reduction. This experiment adds a narrower check that couples task-bound payment accounting with useful-output verification and compares both with a separate reference. [Pinned Workcell implementation](https://github.com/dotmantissa/workcell/tree/b80bcecc1d30263662b985fc025b83233e07a173)
