# Preserve a caller's raw payment observations

`token_capture.py` turns supplied request/response files and an explicit owner
policy into the existing payment-policy input. It makes **no network request**,
signs nothing and needs no additional dependency. It helps connect a caller's
agent to the inspector; it is not a payment gateway or an authenticity proof.

## Start with the constructed example

```sh
python -I -S token_capture.py check verification/capture-study/allowed
# exit 0: declared payment terms met, within the supported profile
python -I -S token_capture.py check verification/capture-study/excess
# exit 1: known spending excess
python -I -S token_capture.py check verification/capture-study/incomplete
# exit 2: a raw provider reply is unparsed; the horizon stays open
python -I -S token_capture.py check verification/capture-study/excess-and-unparsed
# exit 1: a known excess survives unrelated missing evidence
```

These are clearly **synthetic** SDK-style receipt fixtures, not fresh network
observations. Each directory contains exact raw inputs, its index and a generated
`payment-bundle.json`. Import that bundle in the existing Payment terms page.
The CLI/local/browser inspector produces the same full financial report.

## Create your own capture

Declare authority and expected terms before execution. Use the example's
`policy-template.json` as a schema reference, replacing its accounts, intent
limits and explicit transaction/action-receipt assignments. The template uses
`agent-crash-lab/token-policy-template-v1`; it contains the existing token-task
fields except the evidence hash, which the capture builder derives. It cannot
silently rebind an already sealed `token-task-v1` input. Amounts are atomic token
units. Matching prices do not associate a receipt with an order.

Save your existing caller's raw `tx`/`tx_status` JSON request and response bodies
as files. Then, from the release directory, for two observations:

```sh
python -I -S token_capture.py create --policy policy-template.json --source-kind owner-recording --source-note "Bodies supplied by my owned test recorder; origin is not independently authenticated." --observation attempt-1 request-1.json response-1.json --observation attempt-2 request-2.json response-2.json --output new-capture
python -I -S token_capture.py check new-capture
```

The parent directory must exist. The output directory must be new; existing data
is never replaced. Use `synthetic` for constructed data. `owner-recording` and
`public-archival-rpc` are **caller claims**, not verified origin classifications.
If creation is interrupted, partial raw files remain; an absent/broken index is
not a valid capture, and a retry must use a new output path.

The module API is `create(directory, template_raw, source, records)` and
`review(directory)`. A record is `(id, request_bytes, response_bytes)`; `review`
returns `(review_dict, bundle_bytes_or_none)`. API misuse/file failures raise
`CaptureError`/`OSError`; an unsupported policy can instead produce a retained
capture with a rejected assessment. The CLI prints a structured result and uses
the assessment's 0/1/2 gate as its exit code. Successful file creation and a clean
financial result are different signals.

## Invalid replies are evidence too

The original policy and all raw request/response bytes remain unchanged, with
SHA-256 and safe generated paths. Strict UTF-8, duplicate-member and integer
decoding occurs before a response enters the existing JSON evidence profile.
HTML, non-UTF8 or unsupported pair shapes remain listed under
`uninterpreted_records`; no replacement RPC error or payment event is invented.

When a pair cannot be interpreted, only parsed observations enter the financial
profile. The derived policy is explicitly forced to an **open horizon** and the
source/horizon notes disclose the subset. This cannot yield gate 0. Known excess
may still yield gate 1. An unsupported policy/report or exceeded output bound
returns a rejected gate 2 while retaining the original bytes. It does not acquire
a clean report by omitting the problem.

`supported_records` maps the derived observation index to the original capture
record index/ID. A financial pointer `/observations/N/response/result/...` maps
through that entry to the original `raw/NNN-response.json`, then to `/result/...`
in that strict JSON file. The checker verifies original bytes even when an edit
changes only whitespace, and checks the stored export against a fresh rebuild.
It rejects unsafe descriptor paths and symlinks.

An otherwise valid note can already use its full 2048-character allowance. If an
adapter suffix would exceed that limit, the derived report explicitly refers to
the complete original note in `capture.json` or `policy-template.json`; it does
not silently truncate the original or turn a known breach into a rejected
assessment. This prototype counterexample was reproduced before correction.

## Limits and evidence

The bounds are 128 pairs, 2 MiB per raw input, 8 MiB aggregate original bytes,
and 2 MiB each for the generated input bundle and financial report. The existing
financial profile, trust assumptions and 0/1/2 semantics are unchanged. Use OS
CPU/RAM isolation for genuinely hostile files as well. No process/network signer
or arbitrary external evaluator is loaded by this module.

Fingerprints detect changes relative to the supplied index; an attacker who
rewrites all inputs and the index can create another internally consistent
capture. This does not authenticate consensus, prove complete recording,
establish retained recipient balance or grade useful work. The original owner
declarations are trusted inputs, including a closed-horizon assertion when every
record is interpretable. [Financial profile](TOKEN_POLICY.md).

The workflow checks cover allowed installments and independent equal-price
orders, excess, malformed raw replies, reindexed source pointers, changed raw
bytes/exports, path/record collisions, symlinks and resource bounds. The local
Windows run could not create symlinks; the separate Linux run exercised them.
Four actual public browser imports matched Python full reports. These are
source-informed engineering controls, not a blind financial benchmark or a new
model/chain run. `tools/verify_capture.py` replays that compatibility evidence
offline; it does not launch a browser.
