# Recovery, resources and interface review

Version 0.9.1 makes local-service and browser-startup failures actionable. On a failed or inconsistent response, the previous financial result, report download and bundle export remain hidden. Retry preserves keyboard focus. The financial engine is unchanged from 0.9.0 (0.1.2); the workbench health version is updated separately.

## Reproduce owned Python measurements

```sh
python -I -S tools/measure_resources.py --output my-resource-run.json
```

This standard-library command launches five owned workers with 45-second timeouts. It never calls a model, signs a transaction or uses a network service. It refuses to overwrite an existing output. Each input gets one warmup and three measured assessments; every full report must match across repeats. Source, task and source-data hashes bind the run. Imports, input preparation and controller wall time are separate from assessment latency.

On the recorded Windows/Python 3.14 machine, all 46 baselines (138 warm samples) had a maximum of 10.659 ms. The process-lifetime peak working set was 35,487,744 bytes (about 34 MiB), including Python, imports and inputs. The repeated-partial case peaked at 49.710 ms. The source-size, RPC-count and decode-depth probes were rejected with resource errors. See the exact numbers, baseline run and scope in [the evidence directory](../evidence/quality-review/).

These are single-machine measurements, not a speedup result, a universal resource bound, browser memory, model memory or an external benchmark. Allocation deltas and browser-process RSS were not measured. Do not use a clean replay as a guarantee about an agent's changed code.

## Recovery observations

The specification was saved before measurement. Owned loopback fixtures injected a catalog 503, an inconsistent report, one rotated local token and a staged Python source 503. Each recovered on the same tab and produced an actual report identical to standalone Python. A later registered amendment added stop/restart of the owned local service: the old `Failed to fetch` message was replaced by restart/retry guidance. A new service token also recovered through the existing bounded refresh path. No stale verdict/export survived these errors.

Five actual baseline and five candidate UI reports were compared in full, including actual browser WebAssembly execution. This is ten UI observations of the same synthetic partial-evidence case, not ten independent security cases. The owned four-slot HTTP capacity check returned 429 on the extra request and 200 after its incomplete clients closed; the recovered report was identical. It is not a public-network load test.

A busy-state observation verified retained Run focus and hidden exports. An attempted duplicate-activation check was inconclusive because the locator can wait for `aria-disabled` to clear; its backend counts were not preserved. No claim of duplicate-key suppression is made from that attempt. The fixture source is archived as text for inspection; GUI orchestration requires the documented browser automation environment.

## Keyboard, themes and mobile

Observed keyboard paths: visible skip link, focus at the inspection region, tab arrows/Home/End, archived-experiment dialog initial focus, Escape dismissal and focus return. Opening that dialog read archived results; no experiment was executed.

Computed flat-surface text contrast was checked in dark/light desktop and in several dark/light mobile cases. The retained valid samples had no measured threshold failures (4.5:1 normal text; 3:1 large text). At a 390 x 844 viewport, the 375 CSS-pixel document width included a 15-pixel scrollbar and had no document overflow. The native case picker accepted keyboard selection. The temporary viewport override was reset.

The file `light-mobile-contrast.json` is misnamed: its measured width is desktop. It is preserved for transparency and excluded from mobile results. The `*-mobile-390-*` records contain the actual mobile measurements. This is a same-author rendered-sample review, not full WCAG conformance, a screen-reader test, all zoom/viewport coverage or independent accessibility certification. Read-only browser evaluation restrictions were corrected in the QA method, not treated as product defects. No palette changes were justified by this review.

## CI maintenance

The ordinary four-job Ubuntu/Windows and Python 3.12/3.14 matrix pins the official checkout 7.0.1, setup-python 7.1.0 and setup-node 7.1.0 commit hashes. Checkout credential persistence and unneeded automatic package-manager caching are disabled; repository permissions remain contents-read. These actions use Node 24 (the test runtime remains Node 22). Version and runtime evidence came from official action metadata, READMEs and release pages. The optional fresh-agent workflow was updated statically and was not dispatched.

Official references: [checkout](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-python](https://github.com/actions/setup-python/releases/tag/v7.1.0), [setup-node](https://github.com/actions/setup-node/releases/tag/v7.1.0). Contrast methodology: [W3C](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

Broader asynchronous/profile coverage, independently authored evaluation and external review remain open. This work does not establish a competitive ranking, production security or a probability of winning.
