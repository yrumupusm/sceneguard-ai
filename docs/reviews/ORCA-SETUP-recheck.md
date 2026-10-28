# SceneGuard Orca setup — independent recheck

Review date: 2026-10-28. **R1 resolved; R2 resolved; R3 resolved. Overall verdict: `needs_revision` for the newly reviewed acceptance helper (R4 below).** The requested review is complete. This is not setup adoption, permission for new experiments, or evidence of a failed production queue.

Exact reviewed HEAD: **`318dc91254e7f16529cb8ce246538d9042c9646a`**, initially clean. Integration commit **`9ec289da0dfdd8090497535962579bbcd1353406`** and reviewed HEAD both resolve to source tree **`bb0fbe4b4f65b16332f0d576aa0b014da33c232c`**. Locations below refer to that tree, before this report-only commit. The previous `ORCA-SETUP-independent-review.md` remains unchanged.

Run `run_3d23462a014a`; Task `task_fe187221831e`; Dispatch `ctx_122e03a75ad2`. Effective reviewer model/effort is not independently established by this report; invocation evidence remains the coordinator's responsibility. No nested workers were launched.

## Scope and evidence

Read repository instructions and project/setup contracts, the earlier review, changes to `webapp/app.py`, `orchestration/lab.py`, `orchestration/orca_adapter.py`, catalog/binding records and regression tests, and all of the previously unreviewed `orchestration/smoke.py`. Queue implementation was consulted to interpret the smoke helper. Evidence below is local code inspection, public-file hashing, and synthetic temporary fixtures with mocked process/service/HTTP calls.

No private runtime, source media, images, original outputs, credentials, models, GPU, browser, or live lab services were accessed. Native Orca use was limited to the authorized guide and dispatch communication. Only this new report is owned and changed by the reviewer; HANDOFF, LOCAL_SETUP_REPORT, implementation, live acceptance, preservation, integration and publication belong to the coordinator.

## Previous findings

| Finding | Verdict | Evidence |
| --- | --- | --- |
| R1: refreshed import can make an old review appear current | **Resolved** | `webapp/app.py:137–174` compares actual report/metrics/review bytes with a separate review-owned binding. Missing/invalid binding is unverified, mismatches are stale, and the old review remains visible with an explicit re-review warning. Metrics parsing and hashing use one read. `orchestration/catalog.py:118` registers the binding path but never writes the binding. The re-import regression updates catalog hashes while retaining the old binding and confirms stale review, preserved opinion and one metrics read. |
| R2: startup can report a dead projection as started | **Resolved** | `orchestration/lab.py:75–111` generates a launch ID, passes it to the adapter, checks both process identities during readiness and immediately before returning, and requires a current-launch receipt with a Boolean connection state. Reader exit raises a partial-start error with saved ownership retained. A disconnected current receipt returns `degraded`, not connected success. Both new startup regressions passed. |
| R3: FIFO open can block before regular-file rejection | **Resolved** | `webapp/app.py:45–50` opens the final component with `O_NONBLOCK`, retains descriptor-based `O_NOFOLLOW` traversal, and rejects non-regular descriptors. The bounded FIFO subprocess regression passed, as did endpoint rejection and unavailable evidence checks. Existing range, HEAD and symlink tests also passed. |

All seven public report/metrics pairs were independently hashed again: each matches both its current catalog hash and its reviewed-source binding. The historical review bytes also match `review_sha256`. This verifies the binding against public bytes, not the private measurement sources or the correctness of the historical experiments.

For the adapter, two additional mocked receipts confirmed that a valid empty worker list produces a connected observation and a missing `result` produces a disconnected `KeyError` observation; both preserve `fixture-launch` and match the atomically written JSON. No native fleet polling or live adapter service was run. The adapter still invokes only native `worker-list`; no lifecycle mutation was added. The broadened exception list is not exhaustive schema validation (for example, a non-object nested value can still raise `AttributeError`); no current native schema failure was observed.

## R4 — Medium / P2: web-restart smoke can pass without an in-flight job crossing the stop

**Remaining concrete blocker to using this helper as acceptance evidence.** Locations: `orchestration/smoke.py:27–47`.

`restart_smoke` waits only for an attempt with a non-null `child_pid`. Completed attempts retain that field. It then records `web_stop_at`, calls stop, checks eventual success, restarts the services and writes `passed: true`. It never requires the selected attempt to be running at the stop boundary or verifies `job_finished_at > web_stop_at`. Scheduler delay or resuming after a previous incomplete smoke can therefore satisfy the check with a job already finished before the stop. A successful stop response can also occur when no service is registered; the helper has no pre-stop service-liveness assertion. These are acceptance-evidence gaps, not proof that web stop actually terminates queue work.

**Observed deterministic fixture:** a temporary config and mocked queue returned an idle initial job list, followed by the same completed attempt (`job_id='fixture-job'`, `child_pid=123`, `status='succeeded'`, `finished_at=99.0`) for the start wait and subsequent reads. Mocked time was `100.0`; service calls returned stopped/started receipts, process communication completed, and three mocked HTTP reads returned 200. The unmodified function wrote and returned:

```json
{"passed": true, "web_stop_at": 100.0, "job_finished_at": 99.0, "queue_status_after_web_stop": "succeeded"}
```

The fixture used `TemporaryDirectory`, `unittest.mock.patch` for `Queue`, `subprocess.Popen`, `service`, `time.time`, and `urllib.request.urlopen`; no process or service was started by this check. The returned result was explicitly asserted to have `passed` true and `job_finished_at < web_stop_at`.

**Requested correction:** require evidence of live owned services before the stop and an exact running mock attempt at the stop boundary, then prove its completion occurs after the relevant stop boundary. Prefer a controlled synthetic synchronization point over relying on the two-second sleep. Return inconclusive/failure when overlap was not exercised, retain the observations, and add a regression for the completed-before-stop case. A degraded projection restart should remain explicitly degraded rather than be used as connected-service acceptance. Coordinator-owned live evidence can be evaluated separately; this reviewer did not inspect any such receipt and does not claim it is invalid.

The queue smoke at `smoke.py:52–96` does check four selected intervals, serialization, intended failure followed by success, and attempt-count deduplication. Its assumptions should remain explicit: exclusive controlled CPU-smoke use of the canonical queue, compatible source in both worktrees, and normal Python execution with assertions enabled. Unlike `restart_smoke`, it has no initial idle-queue guard; `run-once` claims the next queued job rather than a named smoke job. Some subprocess waits are also unbounded and there is no comprehensive error-path cleanup. These limit unattended/reentrant use; no live queue was exercised in this recheck, and none of the existing 28 tests directly calls `orchestration.smoke`.

## Test execution

Requested suite command, bounded as instructed:

```sh
timeout 90s /home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m unittest discover -s tests_orca -v
```

- First sandboxed run: socket-dependent service cases reported errors, queue/record cases shown passed, and TestClient stalled at the FIFO test; the outer timeout ended the run with **exit 124**. This was not a passing run.
- Normal scoped automatic approval review allowed the same bounded command with local sockets. **28 tests passed in 5.896 seconds, exit 0**: 14 queue, 5 service, 2 record and 7 web cases. All four added regression tests passed. This duration is fixture-suite time, not inference or GPU throughput.
- The existing Starlette/httpx deprecation warning was emitted; no dependency was installed or modified.
- Additional bounded inline checks: public binding hashes (seven experiments), the two mocked adapter receipts, and the R4 false-positive reproduction. They created only disposable temporary fixtures, with no repository source/test edits.

The first `orca-ide skills get orchestration` call failed with `WSL ... UtilBindVsockAnyPort ... socket failed 1`; the scoped automatic approval retry succeeded using the same executable. No runtime reset, credential copying, protection disabling or alternate CLI was used.

## Limits and coordinator handoff

R1–R3 can be closed against this exact source tree. R4 should be corrected or the affected smoke result explicitly withheld from acceptance until independent evidence proves the intended overlap. The suite proves bounded fixture behavior; it does not establish actual service/media/browser operation, continuous projection health, preservation of original environments/outputs, effective role entitlement, or private-source provenance. Process-spawn/ownership persistence crash windows and broader malformed-schema resilience remain outside these regressions.

The coordinator owns the implementation response, any live acceptance and preservation checks, final setup decision and publication. Historical model adoption holds and experiment approval boundaries remain unchanged.
