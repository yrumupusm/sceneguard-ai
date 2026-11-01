# MVP-0004 independent final review

Of 45 original videos, **2 have verified whole-source MVP analysis, 43 remain unsupported, and 0 are failed, partial or not run**. **The whole-inventory accuracy objective remains incomplete.**

2026-11-01. **Verdict: accepted as an accurate limited development-source execution and reference-scoring report, with two observed early false suspicion notices and unresolved reviewed-positive timing.** No blocking discrepancy was found in the frozen public reports, metrics or three local evaluations. This verdict does not approve general model quality, new-camera performance, real-time operation, browser delivery or deployment.

Run `run_3d23462a014a`, review Task `task_c40ce69c4451`, Dispatch `ctx_03e951985fb5`. Scope follows `AGENTS.md`, `CODEX_MVP_EVALUATE_ALL.md`, the frozen MVP-ALL protocol and the [MVP-0003 independent review](MVP-0003-independent-review.md). MVP-0003 remains the preserved resource-blocked result; MVP-0004 reviews new execution in separate output paths. The coordinator explicitly froze the public result and metrics in message `msg_e3e811b641da`, also identifying `docs/MVP_FULL_EVALUATION.md` as the full report with adjusted relative links. All three files were inspected and bound below after that freeze.

## Exact reviewed public bytes

| File | SHA256 |
|---|---|
| `docs/experiments/MVP-0004-results.md` | `953cb97d5a5dbd102fa6b77ee7011bc5bade8b1701abda4f666593cf8179f592` |
| `records/MVP-0004/metrics.json` | `b8261c027607dde30b41e19d74f3df10a77939757215c15eb3d90999fd99c29c` |
| `docs/MVP_FULL_EVALUATION.md` | `6f1cba21019e21652b9799629869a23875e71d6e2f677fc16633e26b54fed1b5` |

These hashes bind this verdict to the exact reviewed files. Subsequent changes require corresponding review updates. Both public 45-row tables agree with the original inventory's IDs, durations, frame counts and annotation counts. All 27 public metrics agree with their cited saved execution/scoring sources, whose hashes also match. Git/browser delivery remains separately recorded by the coordinator.

## Execution and evidence findings

- All **89 analysis/queue dependency hashes** match the previous frozen plan and current files. Detector settings, original source-list hash, admitted profiles, queue runtime and analysis/baseline revisions are unchanged. The current ledger retains all **45 unique original IDs**, their source bindings and **43 explicit unsupported rows**.
- 007 has completed with **4,171 frames / 139.033333 seconds**. Its detector cache, tracking, CPU image paths, source evidence and final evidence each exactly match the entire already-audited native PTS sequence, including frame zero. No additional media decoding was needed for this review. The request uses the whole original and fresh canonical-queue detection; stage artifact bindings and current evidence extraction pass.
- 007 has **18 original candidates, one card, two individually confirmed evidence rows, one first suspicion notice, one first confirmation notice and no release**. The two confirmation points belong to their own actual evidence states; they are not two people or two independently matched incidents. Sixteen other evidence rows do not inherit confirmation merely because their card is confirmed.
- The first suspicion notice at **55.633333 seconds falls inside the already user-reviewed 52.5–57.5-second normal interval**. Later card evidence matches both frozen official positive interpretations, but that does not erase the early normal-time notice. No repeat user question is needed for this known interval. The confirmation notice at **72.133333 seconds** lies inside both official references.
- The 007 pipeline wall cost is **504.020552 seconds**, separately from its detector post-warmup loop cost of **261.187643 seconds** and CPU image-path wall cost of **78.908673 seconds**. These stages overlap the pipeline wall accounting and must not be added to it. Native evidence timestamps are logical decision times in an offline run, not measured notification delivery latency.
- 030 has completed with **4,802 frames / 160.066667 seconds**, with every native timestamp verified across the same five output paths. It has **73 candidates, one confirmed card, three individually confirmed evidence rows and no release**. Its first suspicion at **53.133333 seconds** lies inside the already reviewed **50–55-second normal mask**; its first confirmation is **92.733333 seconds**. The new whole-run first suspicion must not be replaced by the old partial-run 86-second notice. Pipeline wall cost is **665.192095 seconds**, with a separately scoped detector loop of **315.414419 seconds**.
- Both runs together cover **8,973 frames / 299.1 source seconds**. Prior queue **50 job / 50 attempt rows are unchanged**; exactly two new jobs and two first attempts succeeded under the assigned execution dispatch. Both pipelines record fresh paths, decisions and evidence, with no prior output substitution. All **102 prior local evaluation artifacts** remain byte-identical; the MVP-0003 public result, metrics and full-evaluation snapshot retain their original reviewed hashes.

The model metadata identifies the same FCOS COCO weight, FP32, batch size one, ten warmup frames, no sampling and no ground-truth loading. Its post-warmup loop throughput is **15.969362 FPS / 15.224415 FPS** for 007/030; those are measured loop rates including decode, preprocessing, inference and output work, not pure model throughput. Both record PyTorch peak allocated **455,169,536 bytes (434.083 MiB)** and reserved **497,025,024 bytes (474 MiB)**, which are process allocator values rather than total GPU occupancy. Separate model setup/loading cost is not measured. Pipeline CPU seconds exclude the detector child. The two pipeline wall times sum to **1,169.212647 seconds / 299.1 source seconds = 3.909103 times source duration**; stage costs overlap that total and are not added again.

## New semantic-review scope

030 contains **48 candidate updates from 56.033333 to 83.466667 seconds** outside existing precise reviewed masks. They are silent updates in the same continuing card, not 48 new notifications or established false incidents. Its continuous gate-activity episode begins at 52.366667 seconds and eventually closes at 101.3 seconds after the final gate observation at 98.3 seconds. That long grouping makes the distinction between eventual event matching and first-notice correctness especially important.

The coordinator reports **one pending user question** for the new 030 56–84-second activity. Already reviewed 007/030 normal-first-notice scenes and the known positive contexts need no repeat question. The newly exposed interval remains unreviewed until a user response establishes a limited observation; neither model output nor the eventual positive card supplies negative truth for its earlier updates. Any later truth revision must remain separate from this frozen baseline. The pending observation does not block acceptance of a report that explicitly preserves this uncertainty. Local case IDs and timestamps are recorded in `independent-review/new-review-cases.json`.

## Reproduced scores and their limits

All three manifests retain the exact frozen truth and mask rows for all 45 unique sources. Their execution bindings point to the two new full runs, their predictions equal the actual candidate/individual-confirmation export, and their first-notice streams equal the actual notifying timeline entries. Recomputing with the unchanged scorer reproduces all three reports exactly, including input/evaluator hashes. There is no later-positive substitution for earlier notices, no confirmed-card propagation to unresolved evidence, and no historical partial-run substitution.

| Quantity | Official 0-based reference | Official 1-based reference | Reviewed truth |
|---|---|---|---|
| Complete development sources | 2 | 2 | 2 |
| Suspicion TP / FP / FN | 2 / 0 / 0 | 2 / 0 / 0 | 0 / 0 / 0 accounting; 2 unresolved predictions |
| Confirmation TP / FP / FN | 2 / 0 / 0 | 2 / 0 / 0 | 0 / 0 / 0 accounting; 2 unresolved predictions |
| Event precision / resolved-reference recall / F1 | 1 / 1 / 1, only these 2 cards and 2 executed references | Same restricted result | null / null / null |
| Reference coverage across all originals | 2 / 52; 1 additional unresolved record | 2 / 52; 1 additional unresolved record | 4 unresolved positive contexts; no precise positive bounds |
| False first suspicion notices | 2 | 2 | 2 |
| False first confirmation notices in reviewed normal masks | 0 | 0 | 0; both confirmation notices lack precise reviewed-positive bounds |

The observed normal exposure is **52.133333 gate-seconds (0.868889 gate-minutes)**: 39.6 seconds from 007 and 12.533333 seconds from 030. Thus the raw **2 false suspicion notices** correspond to **138.107417 per verified-normal gate-hour**. This short-exposure conversion is not a measured operating-hour rate. The two normal-time first notices are 2/2 of all suspicion notices despite both cards eventually receiving official-reference TP credit. Zero false confirmation notices in this short normal exposure does not establish general confirmation safety.

The reviewed variant has no precisely bounded positive events, so its zero TP/FP/FN sums are not observed perfect detection or proof of no misses. Its precision bounds span 0–1 and are uninformative; no meaningful reviewed F1 range or recall is established. The 50 resolved official references outside the two executed sources remain unexecuted rather than being classified as detector false negatives or silently discarded. The 2/52 inventory coverage is 3.846154%, separate from executed-reference recall.

First matching suspicion evidence is 65.233333 seconds for 007 and 89.1 seconds for 030. Relative to official starts, offsets are 2.133333 / 0.166667 seconds under 0-based interpretation and 2.166667 / 0.2 seconds under 1-based interpretation. First confirmations have corresponding reference offsets 9.033333 / 3.8 and 9.066667 / 3.833333 seconds. **All precise behavioral detection-delay fields remain null** because official reference starts and qualitative user observations do not establish precise behavioral onset. No release success, person count, legal access determination, new-camera generalization or real-time delivery result follows from these scores.

The previous inventory/truth audit is reused rather than repeated: **184,300 frames / 6,143.4668667 seconds across 45 originals**, 52 resolved official references plus one unresolved record for each index interpretation, 62.133333 available reviewed-normal gate-seconds, and four unresolved reviewed-positive contexts. Only the two admitted development sources can contribute complete execution here; the other 43 remain in coverage accounting. Unreviewed time remains unreviewed.

Local read-only artifact checks, exact score reproduction and final bindings are recorded under `runtime/MVP-ALL-execution-v2/independent-review/`. The previously reviewed 131 unique tests remain prior verification; this reviewer did not rerun unchanged suites or count artifact checks as model inference. The review adds actual-run coverage and export checks that could not be performed for MVP-0003, whose execution was resource-blocked.

The reviewer owns only that ignored directory and this document. No inference, GPU job, analysis-module edit, cloud pixel transfer, nested worker, registration or push was performed by the reviewer. **The accepted result is two fully executed development sources with accurate limitations, not completion of all 45 videos or successful suppression of normal-approach alarms.**
