# EXP-0016 resource-gate review addendum

Date: 2026-10-28. Review Run `run_3d23462a014a`, Task `task_14b126da15f0`, Dispatch `ctx_15be41718969`. Repository HEAD: `5d4a8af0f83975f430922fcda03c0aef5a34734a`.

**Verdict: PASS for recording the corrected final package as BLOCKED-before-inference only.** The timestamp and execution-identity findings below were corrected by the coordinator and independently checked. No unresolved inconsistency was found in this limited addendum. This is not an output/performance review, behavioral validation, adoption decision or authorization to bypass the resource gate.

## Exact artifact binding and resolved findings

The originally supplied report used the new 14:36 UTC snapshot, but its metrics retained a 14:29 UTC scope timestamp for the new 1590 MiB value. The report also omitted the execution Task ID and exact model name, although the assignment contained them. Both findings were reported through Orca; the coordinator corrected the package and supplied replacement hashes in message `msg_50379cc9de94`. The reviewer made no package edits.

| Artifact | SHA-256 | Binding |
| --- | --- | --- |
| Initially supplied report | `8a98a1f7bb52d9c71014cd714a309321a587bad1bd4090c1e44f4cd28a61cf0d` | Supplied identity, superseded before independent rehash; not the final verdict target |
| Initially supplied metrics | `1a2510e2b81c05a3597da8dcfae8c509a5b7ea2491bafd51e6c5318815272d65` | Supplied identity, superseded before independent rehash; not the final verdict target |
| Final `docs/experiments/EXP-0016-prompt-evidence-rubric.md` | `bc08978c7e7e3469fac10b0d27f94edebf042f0e5730733b5f7cc435d022706f` | Independently rehashed from current bytes |
| Final `records/EXP-0016/metrics.json` | `f6bcab76247bf31456bd3d5dce2d8170e38c0e6988e55ad57bcb024ebb44ad32` | Independently rehashed from current bytes |

All six metric rows name the final report path and its exact final SHA-256. The pure `orchestration.complete.metrics` schema/publication validator passed with bytecode writing disabled. The free-memory metric now says 2026-10-28 14:36 UTC. Further changes to either artifact require renewed binding.

## Execution identity and resource evidence

The corrected report and the sole EXP-0016 entry in `records/assignments.json` agree on Run `run_3d23462a014a`, Task `task_305549d14771` and Dispatch `ctx_65256d02af82`. The assignment is registered in `slot3`, is not synthetic, and records requested/effective model `gpt-6.1-sol` with effective reasoning `high`.

Read-only `orca-ide orchestration worker-show --dispatch ctx_65256d02af82 --json` independently confirmed the same Run/Task/Dispatch and requested/effective launch model and effort. Its durable worker completion (`msg_71a4b5ea857a`, completed 2026-10-28T14:36:59.339Z) reports one fresh `nvidia-smi` snapshot: NVIDIA GeForce RTX 3080, **8464 MiB used, 1590 MiB free, 99% utilization**. The dispatch ran within the 14:36 UTC minute. These values agree with the final report; the earlier 14:29 UTC observation remains historical evidence in the prior review.

The required minimum is **6144 MiB free**, so 1590 MiB fails the unchanged gate. The durable worker report states that it stopped before enqueue, model import or model load; all four groups remained unexecuted, with no job/attempt IDs, resource retry or polling. The report accurately distinguishes the Dispatch's `failed` outcome caused by resource blocking from an inference failure or OOM. This reviewer did not take a replacement GPU measurement or inspect a raw GPU/process log.

At **2026-10-28T14:40:28.841283+00:00**, a SQLite connection using `mode=ro` and `PRAGMA query_only=ON` independently returned **0 EXP-0016 jobs and 0 attempts** from the documented canonical queue. Its canonical-runtime marker matched the shared queue path. The aggregate predicate covered EXP-0016 job keys, all three phases (`prompt-regression`, `independent-original`, `independent-revised`), and the exact execution Task/Dispatch; attempt counts joined those jobs. No job payloads or attempt outputs were returned. Together with the worker report and previously reviewed guards, this supports the blocked-before-inference record; it is not a forensic claim about unrelated processes.

## Reused review and limits

The code, tests, label/input separation and privacy findings in [the initial independent review](EXP-0016-independent-review.md) are reused by reference. All 14 implementation/config/test file hashes listed there still match their current bytes. The prior focused 39 MVP and 14 queue test passes, full-suite reporting qualifications, disclosed queue-test ordering failure and future exact-frame comparison requirement remain applicable; this addendum did not rerun those suites or re-review media.

The final metrics retain `behavioral_validation: not_run` and `adoption: on_hold`. Revised-prompt behavior and generation-latency/peak-VRAM values and sample sizes are null; accuracy, precision, recall, F1, false-positive rate and hourly false alarms are also null. Load time, output/parse status, action/completion judgments and behavioral effect remain unmeasured in the report. The numeric 107/14 values count software tests, four counts checked windows, and 1590 records one free-memory snapshot: none measures inference cost or performance. Zero attempts does not imply a measured zero-failure rate.

No outputs exist in the reviewed evidence for assessing q01–q06 regressions, v01–v04 behavior/completion, explanation accuracy or adoption. A future authorized inference run must satisfy the unchanged resource gate and receive its own output/comparison review. Result registration, browser verification and publication remain separate coordinator-owned steps.

Only this addendum was written. No code, labels, report, metrics, assignments, catalog or website was changed by this reviewer. No media, caches, weights, raw model responses or secrets were inspected; no inference, enqueue, GPU probe, commit, push or external-channel message was performed.
