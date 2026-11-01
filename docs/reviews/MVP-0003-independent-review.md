# MVP-0003 independent final review

Of 45 original videos, **0 completed whole-source MVP analysis, 43 are unsupported, 2 were not run, 0 failed during analysis, and 0 are partial**. **No accuracy was measured; not all videos were analyzed.** All 45 originals were raw-decoded for inventory and native-clock auditing, which is separate from MVP execution.

2026-11-01. **Verdict: accepted as an accurate inventory, truth audit and resource-blocked execution report; the requested whole-video accuracy evaluation remains incomplete.** No blocking discrepancy was found in the frozen public reports, metrics or three local no-result evaluations. This verdict does not approve model performance, generalization, real-time operation, browser delivery or deployment.

Run `run_3d23462a014a`, review Task `task_fab8e35059b0`, Dispatch `ctx_ff97b9668598`. Scope follows `AGENTS.md`, `CODEX_MVP_EVALUATE_ALL.md`, the frozen protocol and the [initial independent review](MVP-ALL-protocol-review.md). The coordinator confirmed the public-file freeze, then announced the final report-only table addition and renewed freeze in message `msg_e00ef064b626`. That addition was inspected before these bindings were recorded. The reviewer changed only this document and ignored local `runtime/MVP-ALL/final-review/` evidence; no inference, GPU job, analysis edit, media upload, nested worker, registration or push was performed.

## Exact reviewed public bytes

| File | SHA256 |
|---|---|
| `docs/experiments/MVP-0003-results.md` | `ac8e2e85a15a0e246026e7d880c67b4f997fbc2209cfcddb1f8be49b0c8c3935` |
| `records/MVP-0003/metrics.json` | `2685b6f01b097daabd09388bd7365eeb0955a252a2a172bf0ddb6516603bf365` |
| `docs/MVP_FULL_EVALUATION.md` | `ff361935e490f750dbe983e16c1c2c30a53be62801567996c6e1ec6f400e3864` |

These hashes bind this verdict to those exact files. Subsequent changes require a corresponding review update. UI/Git delivery is explicitly deferred to the separate delivery record.

## Inventory, preservation and execution

- Independently enumerated the original directories and verified all **45 unique video SHA256 values, 45 corresponding official JSON hashes and every original metadata/annotation row**. There are no duplicate source bytes or unpaired labels. All 53 original annotation rows remain in the inventory and all three truth variants; no source disappears because it is unsupported or unexecuted.
- Inspected all 45 complete native-clock artifacts, checking source bindings, integer PTS ordering and deltas, time bases, frame counts and first/last timestamps. They record **184,300 decoded frames and 6,143.466866666664 video-stream seconds**. This review audited those complete decoder records and current source hashes; it did not perform another full media decode. The decoder-function hash still matches the inventory after truth-only adapter revisions.
- The inventory keeps ten documented development/audit sources and 35 with incomplete prior-use/camera history. The latter are not blind tests or proven new-camera samples. Site/session independence is unresolved; `cctv_distribution` is not substituted for camera identity. Crops, earlier windows and comparison videos do not increase the source count.
- **E01_006 has two separate limitations:** the official 4,011 frames disagree with 4,006 decoded frames, leaving its reference timing unresolved; its native `30000/1001` rate and non-30fps PTS spacing are unsupported by the frozen pipeline. Neither issue is silently corrected, and neither means a negative video. Its approximate 119–132-second non-event candidate remains excluded from verified-negative masks.
- Only 007/C3 and 030/C6 have admitted whole-source configurations, totaling **299.1 seconds / 8,973 frames**. No compatible whole-source detector cache is admitted. Their historical partial caches cannot supply current whole-video results. The other 43 sources retain explicit unsupported reasons: seven known-camera sources outside the admitted configurations, 35 unresolved camera/configuration bindings, and 006's native-timing limitation.
- The ledger, plan and execution-support report agree on all 45 IDs, source hashes and statuses. The recorded resource gate saw **848 MiB free against the required 6,144 MiB**, with 99% GPU utilization. 007 was blocked before launch; 030 was not attempted after that shared resource block. There are **zero recorded pipeline starts, new detector jobs, detector/tracker/CPU-path frames and inference retries**. These are execution counts, not successful zero-alert outcomes.
- Rechecked all **58 frozen execution inputs** and **89 analysis/queue dependencies** against current bytes and the frozen `f05d430458150c9b63e04aa9caf93cb85ee18cae` Git blobs. The difference from requested baseline `548ff7098045f9efc5bd2edfd5ce61431a5e210e` in the analysis/queue trees is the added evaluator, not changed analysis rules. Before/after queue snapshots and the live canonical queue have identical **50 job / 50 attempt rows**.

## Truth and no-result scoring

The reviewer independently reconstructed both official index interpretations from integer native PTS and original annotation rows, including same-gate interval merging and original-row lineage. Each yields **52 resolved reference intervals plus one timing-unresolved original record**. All references are unexecuted. There is no prediction-selected removal or missed-event review selection because no current predictions exist. The 0/1-based ambiguity and the fixed half-open endpoint interpretation remain assumptions, not newly established annotation semantics.

The reviewed variant preserves **four unresolved positive windows/recording contexts and zero precisely bounded positive events**. Repeated 030 observations remain one context; 007's approximate onset observations do not become precise event bounds. The 031 incomplete-at-end observation is retained and not transferred to 030 or converted to a negative label.

The **11 reviewed-negative masks** match their existing user-review scopes and provenance hashes. Their per-gate union is **62.13333333333333 available gate-seconds**, including 52.13333333333333 in the two supported sources; overlapping 007 waiting windows are counted once. The waiting mask ends at its reviewed clip boundary rather than being extended through an adjacent positive-context window. Official variants carry only compatible, explicitly user-reviewed negative masks, with conflict separation preserved; unlabeled time is never inferred negative.

Each of the three manifests contains **45 unique sources**, retains its truth rows and execution reasons, and has empty current prediction lists with zero processed seconds. Recomputing with the unchanged evaluator reproduces all three reports exactly, including input and evaluator hashes. Suspicion and automatic confirmation remain separate, as do evidence matching and first-notice evaluation.

| Quantity | Reviewed interpretation |
|---|---|
| Eligible complete sources / analyzed normal exposure | `0 / 0 gate-seconds` |
| Precision, recall, F1, scored-subset performance and alarm rate | `null` / unmeasured; no performance denominator |
| Internal TP/FP/FN/first-notice counts | Empty accounting sums of `0`; not observed zero errors or zero misses |
| Official inventory reference coverage | `0/52`, separately for each index variant; execution/reference accounting, not detector recall |
| Additional timing-unresolved official records | `1`, retained separately from the 52 resolved references |
| Reviewed positive-context accounting | `4 unresolved`; not four precisely timed incidents or a substitute recall denominator |

No meaningful F1 range, detection delay, first-confirmation quality, suspicion-release success or model throughput can be inferred. The fixed scorer's initial-review limitation concerning F1 range output remains; no range is invented for this empty execution set. The recorded 589.665280-second sum of raw decode elapsed times is inventory cost, not inference FPS. Unmeasured model costs remain null. Observation closure and ordinary passage are not counted as successful releases.

## Revised guards and verification

The initial review's full-frame, cached-CPU and notification-export findings are addressed by the wrapper/adapter guards: complete native partitions are required, GPU blocking applies to work requiring new detection, and exported first-notice tuples must equal the current card/timeline stream. Individual confirmation evidence is not propagated from a confirmed card to its unresolved members. These safeguards are tested, but their successful use on new whole-source pipeline outputs remains unverified because this execution produced none.

The reviewer ran **9/9 runner tests**, then **31/31 final adapter tests**, and targeted both existing scorer cases for early suspicion and early confirmation: both passed, preserving an early false notice even when later evidence matches a positive event. An earlier 29-test adapter pass is retained as revision history and is not added to the final suite count. The reported **131 unique tests = 26 scorer + 31 adapter + 9 runner + 46 MVP pipeline + 19 frontend**; the two targeted scorer reruns belong to those 26. The initial scorer log and execution/data-worker validation receipts support the remaining suite results; this reviewer did not rerun unchanged pipeline/frontend suites or represent their prior pass as new inference.

| Final reviewed implementation | SHA256 |
|---|---|
| `scripts/mvp_full_run.py` | `8e3bdfa5859bbdb4d95bb1ecd817c5a7f3f60c77d86a516b2b7be799fbade9de` |
| `scripts/mvp_full_evaluation_adapter.py` | `d7996ef1138aa84d3c973edf0b8b985dbd623cb3ce331f3ef14fb4e6330ca5a0` |
| `tests/test_mvp_full_run.py` | `6f4c8aebaf8632897b90e1940900cd99520cec7c380a129bcdadbedd919343a4` |
| `tests/test_mvp_full_evaluation_adapter.py` | `ac48baf76d18c8bb9ebc447b4ed068aee27860f786534b07882692b53c609578` |

Local evidence includes `audit.py`, `artifact-audit.json`, the runner/adapter/early-notice logs and `final-binding.json` under `runtime/MVP-ALL/final-review/`. The audit checks every source/label/clock, execution bindings, queue rows, truth conversion and report reproduction. Public review contains aggregate facts and bindings only; original media and detailed truth remain local.

To complete the accuracy objective, a future active dispatch must preserve this blocked record, prepare a compatible freeze for the then-current execution HEAD, obtain sufficient resources, run supported originals completely through the canonical queue, and audit actual per-evidence and first-notice outputs before scoring. Even successful 007/030 execution would leave 43 unsupported sources. **The present result certifies the reported limitation, not whole-video analysis completion or model accuracy.**
