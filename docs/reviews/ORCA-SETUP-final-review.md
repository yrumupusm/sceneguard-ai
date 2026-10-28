# SceneGuard Orca setup — final narrow R4 review

Review date: 2026-10-28. **R4 resolved for the controlled CPU-smoke acceptance contract.** Review status: `accepted_for_comparison`, limited to this correction. No new blocking finding was identified in the requested changes. This verdict does not establish live setup acceptance or authorize experiments.

Reviewed HEAD: `83e6fd7e3e508d4c3a6f69a7b570b11bbe5a6bb7`, initially clean. Integration commit `b05c6a861f52f938a85398d65dfc0bb30f9d95a4` and reviewed HEAD both resolve to tree `a8171c66e6f67c9d24624f5869ee93721048d22a`; `git diff --exit-code HEAD b05c6a8` returned 0 with no differences. References below describe this source tree before the report-only commit.

Run `run_3d23462a014a`; Task `task_715d3de8b377`; Dispatch `ctx_93637ad8e5d9`. Effective reviewer model/effort was not independently established in this review; the coordinator owns invocation evidence. No nested workers were used.

## Scope and evidence

Reviewed the changes to `orchestration/smoke.py` and the four fixtures in `tests_orca/test_smoke.py` against R4 in [the recheck](ORCA-SETUP-recheck.md). Consulted public queue/service code only to interpret identity and stop semantics. Evidence is local source inspection and synthetic temporary fixtures; no private runtime, media, original outputs, credentials, models, GPU, browser, or live lab service was accessed. Native Orca operations were limited to its guide and this dispatch's communication.

Only this report is changed. Both earlier independent reports remain intact. HANDOFF, LOCAL_SETUP_REPORT, the full suite, live acceptance, preservation checks, integration and publication remain coordinator-owned under the explicit one-report assignment.

## R4 disposition

| Required behavior | Evidence and conclusion |
| --- | --- |
| Owned services alive before stop | `smoke.py:23–28,44,57` requires both web and projection `identity_matches` to be exactly true, first before enqueue and again before stop. `lab.py:19–29,45–46` ties this to the saved PID/start-ticks/boot identity and excludes exited/zombie processes. The missing-services fixture confirms rejection before submission. |
| Exact running attempt and child before and after stop | `smoke.py:30–36,58–66` requires a running attempt for the submitted job and `process_state(child_pid, child_identity) == 'live'` on both sides, then compares attempt IDs. `queue.py:52–62` treats missing, mismatched or unverifiable identity as non-live. The completed-first fixture now rejects the original false-positive route before calling stop. |
| Child completion after the entire stop | `smoke.py:60–76` records both stop boundaries, reads the same attempt's result file, checks the child PID and requires `child.started_at <= web_stop_at < web_stopped_at < child.finished_at <= attempt.finished_at`, with final status succeeded. `lab.py:47–65` waits for owned service exit or raises. The helper therefore uses child completion, not merely the later supervisor/DB timestamp. The successful fixture exercises completion at 102 after stop ends at 101; the early-completion fixture rejects completion at 99. |
| No pass on inconclusive overlap or degraded restart | The result begins with `passed: false` and `state: inconclusive`; only the end of the successful path changes these (`smoke.py:20,77–93`). Restart must report both started and connected, and three catalog reads must succeed without additional attempts. The degraded fixture retains failure and an error. |
| Failure evidence retained | Ordinary exceptions inside the guarded operation record the error and recovery guidance, re-raise, and write the accumulated receipt in `finally` (`smoke.py:90–102`). The negative fixtures read back these temporary failure receipts. Existing result files are rejected before any overwrite (`16–18`). |
| Old restart tag rejected | `smoke.py:42–43` rejects the existing job key even if its job is terminal and the result file is absent. This prevents a previous completed attempt from being reused as fresh overlap evidence. This branch was inspected, not directly exercised by the four fixtures. |
| Queue idle guard | Both restart and queue smoke reject queued/running/unknown jobs before submitting new work (`smoke.py:39–41,111–113`). This closes the previously missing initial guard in queue smoke. These branches were inspected, not directly exercised by the four fixtures. |

The helper compares attempt IDs across stop and checks each snapshot's child identity against the live process; it does not separately compare the two child PID/identity tuples. This is sufficient under the current queue contract: `supervise_once` records one child tuple for an attempt (`queue.py:321–324`), and an explicit retry creates a new attempt. It does not protect against external rewriting of that row, which is outside controlled smoke use.

## Test execution

Only the assigned command was run, with the requested bound:

```sh
timeout 30s /home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m unittest discover -s tests_orca -p test_smoke.py -v
```

**4 tests passed in 0.012 seconds; exit 0.** This is fixture-suite duration, not service or inference performance.

- `test_already_finished_attempt_cannot_prove_overlap`
- `test_early_child_completion_and_degraded_restart_are_not_success` (two subcases)
- `test_live_attempt_crossing_entire_stop_is_required`
- `test_missing_owned_services_refuses_mock_submission`

The fixtures use `TemporaryDirectory` and mock queue access, process creation, service calls, process liveness, clock reads and HTTP requests. No extra inline tests, full-suite execution or live acceptance were performed. Temporary fixture data was disposed; ignored Python bytecode caches remain outside the report commit.

The first sandboxed `orca-ide skills get orchestration` returned `WSL ... UtilBindVsockAnyPort ... socket failed 1`. The same command succeeded through normal scoped automatic approval review. No safeguards were disabled or runtime reset performed.

## Remaining limitations and handoff

The four fixtures do not directly test a child becoming dead/unknown after stop, a changed attempt ID, equality at the completion boundary, old-tag rejection, busy-queue rejection, cleanup timeout, or receipt-write failure. Those guards are supported here by code inspection, not additional runtime evidence. Process liveness is mocked in this suite; actual process identity, shutdown, restart connectivity and queue survival still require the coordinator's live check and separate 32-test run.

The workload still sleeps for two seconds rather than using a synchronization barrier. A slow stop or delayed scheduler can yield an inconclusive run; this is now a conservative refusal to pass. Operators must inspect the saved receipt and choose a fresh tag, without automatic replay. The idle check is a snapshot, so smoke still assumes exclusive controlled queue use and no concurrent submissions or service control.

Receipt persistence covers ordinary exceptions after queue construction; configuration/runtime initialization failures occur before the guarded block, and process termination or filesystem/cleanup errors can prevent the final write. The write is not atomic. This is not a crash-durable reporting guarantee. Queue-smoke's broader cleanup, unbounded `check_output` calls and assertion-based checks remain as noted in the earlier report and were not expanded into a new audit.

The coordinator can close R4 for this exact implementation while separately evaluating live evidence. R1–R3 dispositions remain those of the preserved recheck, not fresh findings from this narrow review. Setup completion, effective role entitlement, original-environment preservation and historical experiment validity remain separate decisions.
