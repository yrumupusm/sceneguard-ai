# Shared CPU mock queue

This setup implements a local Linux/WSL queue reservation using Python 3 standard
library only. The registered workload is **CPU sleep**, not GPU inference. Its
timestamps test serialization and recovery; they say nothing about CV/VLM speed,
GPU memory, accuracy, or real model throughput. Orca remains the source of truth
for Run/Task/Dispatch lifecycle; this database records local job execution only.

## Decision and boundaries

The implementation follows [SETUP_ORCA section 5](SETUP_ORCA.md) and the
[infra_builder role](AGENT_ROLES.md). SQLite `BEGIN IMMEDIATE` provides atomic
claims and the database enforces a unique job key and `(job_id, attempt_no)`.
A canonical OS `flock` covers claim, subprocess execution, result recording and
recovery. SQLite alone would leave a process running after its scheduler dies;
a lock held only by the CLI caller would have the same problem. A detached
supervisor holds the reservation and passes the same open file description to
the registered child. No additional scheduler service or dependency is needed.

The only command registration is `cpu-mock`: the current Python executable,
isolated mode (`-I`), this package's `mock_job.py`, generated numeric arguments and
generated result/lock arguments. The working directory is the executing checkout
root. User input cannot supply an executable, shell, cwd, output path or extra
argv. No subprocess uses `shell=True`. Synthetic JSON input is hashed metadata;
it is never interpreted as a filename or command. The only allowed config keys
are `seconds` (finite 0..3600) and `exit_code` (integer 0..125).

This is one cooperative local-host queue, not a machine-wide GPU access control
system. Every participating worktree **must use the same explicit absolute
runtime path**. The implementation cannot discover a second independently
initialized runtime or stop processes outside this queue. Keep this design for
the authorized mock setup; reassess it before registering actual model jobs,
descendants, multi-host storage or external submission.

## CLI

Run from the checkout root with system Python 3; existing `.venv` and `.venv-vlm`
are not used or changed. Linux `/proc`, `flock`, `os.pidfd_open` and
`signal.pidfd_send_signal` are required. The tested system provides these.

Choose the host's shared runtime once. `/absolute/shared/sceneguard-runtime` below
is an example to replace with that path; do not choose a different path per
worktree. No command infers a runtime from cwd or an environment variable.

```bash
python3 -m orchestration.queue --help
python3 -m orchestration.queue --runtime /absolute/shared/sceneguard-runtime init
python3 -m orchestration.queue --runtime /absolute/shared/sceneguard-runtime enqueue \
  --job-key setup-mock-a --run-id setup-run --task-id setup-task \
  --dispatch-id setup-dispatch --owner infra_builder \
  --config-json '{"seconds": 0.5, "exit_code": 0}' --timeout 5
python3 -m orchestration.queue --runtime /absolute/shared/sceneguard-runtime run-once
python3 -m orchestration.queue --runtime /absolute/shared/sceneguard-runtime status
python3 -m orchestration.queue --runtime /absolute/shared/sceneguard-runtime recover
```

All successful commands print JSON. `enqueue` also supports `--command cpu-mock`,
`--input-json`, `--expected-input-hash` and `--expected-config-hash`. Hashes are
SHA-256 of JSON serialized with sorted keys, compact separators and `allow_nan=False`.
The stored config/input is verified again before launch. Source hashes cover
both Python implementation files; code changes between enqueue and execution
fail the attempt instead of silently running changed code. `code_sha` records
the checkout HEAD, while source hashes also cover uncommitted implementation.

The same key and identical contract returns the existing job without running it
again. A reused key with changed metadata/config/code/timeout is rejected.
`run-once` blocks for the shared reservation, then processes at most one queued
job. Two separate terminals may each call it; the CPU mock intervals serialize.
It does not run a permanent daemon or automatically drain the queue. The
`_supervise` subcommand is internal and does not expand the command registry.

`run-once` reports its supervisor PID and supervisor exit code. A recorded mock
failure is handled successfully by the supervisor, so its exit code can be zero;
read job/attempt status for the workload outcome. A supervisor crash produces a
nonzero `supervisor_exit_code`. Invalid arguments/contracts exit 2. Status reads
are read-only and never start work or run recovery.

An explicit request is needed for cancellation or retry (replace `JOB_ID` with
the `job_id` returned by enqueue):

```bash
python3 -m orchestration.queue --runtime /absolute/shared/sceneguard-runtime cancel JOB_ID
python3 -m orchestration.queue --runtime /absolute/shared/sceneguard-runtime retry JOB_ID
```

Cancel marks an unstarted job `cancelled`, or asks its live supervisor to kill
the exact registered child using its pidfd. Timeout also uses that exact pidfd;
the child is reaped before releasing the reservation. Polling is approximately
50 ms, not a guaranteed latency. Timeout is `failed` with reason `timeout` and
observed exit code (normally `-9`); cancellation is a distinct state/reason.
Cancellation of an unstarted job creates no pretend execution attempt.

There is **at most one explicit retry**, meaning at most two execution attempts
per job. Only a job with one known `failed`, `cancelled` or `interrupted` attempt
can be retried. Completed, queued, live and unknown jobs cannot be retried.
Retry preserves prior attempt rows/artifacts. Neither restart nor recover
automatically retries a job; resubmitting its key does not retry it either.

## Runtime records and recovery

The runtime contains `queue-runtime.json`, `queue.sqlite3`, `init.lock`,
`gpu.lock`, `supervisor.log` and `attempts/<attempt_id>/`. Keep **all of it local
and out of Git**. Tests put it under disposable `/tmp` directories; no persistent
runtime directory was created in this checkout. The coordinator should select
an ignored canonical runtime location before shared deployment.

Initialization records the resolved absolute path. Symlink aliases resolve to
the same lock/database; a moved/copied runtime with a different canonical path
is rejected. Never delete, replace, unlink or forcibly unlock `gpu.lock` while
any queue process might exist. Its open file description is inherited by the
child, and closing the supervisor copy does not release the child's reservation.

Jobs store run/task/dispatch/owner, registered command, expected input/config
hashes, source hashes, code SHA, timeout, queue creation and execution state.
Attempts store a UUID, attempt number, owner, supervisor/child PIDs and start
identities, start/finish times, observed exit, heartbeat, timeout, reason and
result manifest path. Identity combines Linux boot ID with `/proc` start ticks.
`manifest.json` contains the job and attempt receipt; `mock-start.json` and
`mock-result.json` contain synthetic child observations, with GPU measurements
explicitly null. Logs and absolute paths remain local.

The execution states are:

| State | Meaning |
| --- | --- |
| `queued` | No execution claim yet, or one explicitly authorized retry queued |
| `running` | Claimed; a supervisor/child may still be active |
| `succeeded` | Supervisor observed child exit 0 |
| `failed` | Observed nonzero exit, timeout or setup/contract error |
| `cancelled` | Explicit cancellation, before claim or handled by supervisor |
| `interrupted` | Recovery proved recorded processes exited without a final receipt |
| `unknown` | PID identity mismatched, missing or unreadable; human investigation needed |

`recover` first tries the reservation without blocking. If busy, it reports busy
and sends no signal or state mutation. Once the reservation is free, it compares
actual identities with recorded ones. An exact live process stays running; a
missing/zombie process is exited; a reused PID, unreadable `/proc` or missing
identity is unknown. Any unresolved running/unknown job blocks new claims across
the queue. Recovery never kills a process or clears the lock.

If the CLI worker dies, its detached supervisor still enforces heartbeat,
timeout and completion. If the supervisor itself dies, the child retains the
lock until exit. Its previous job is then interrupted, with exit code null;
the child's self-written result alone is not proof that its parent observed
successful exit. The next worker may process the next queued job, but never
silently repeats the interrupted one. Timeout/cancel/heartbeat cannot be
enforced while the supervisor is dead; this registered mock is bounded by its
configured sleep. Recover after it exits. There is no automatic orphan adoption.

Power loss, file-system durability, network filesystems, malicious local DB
editing and arbitrary descendant process trees are outside this smoke setup's
verification. Do not resolve unknown state by editing the DB or killing a PID
based only on its number. Preserve the receipt and ask the coordinator to
investigate the actual process identity and runtime selection.

## Local verification and dispatch evidence

Command: `python3 -m unittest discover -s tests_orca -p test_queue.py -v`.
The initial run passed all **14 tests** in **5.508 seconds** on 2026-10-28;
a subsequent run passed the same suite in **5.632 seconds**.
This is suite wall time for CPU mocks, not a GPU benchmark. Tests cover concurrent
enqueue uniqueness, two-worker serialization, failure release, completed-job
restart deduplication, CLI-worker death, supervisor death with a live child,
timeout cleanup, running/queued cancellation, one explicit retry, PID reuse and
unreadable identities, canonical path/runtime requirements, command/config/hash
validation and stored hash tampering. Later changes must rerun the same suite.

Worker provenance for this change:

- Worktree branch `setup/orca-infra`, base
  `83ce1b56ba4d9e73bae5f1c48856d73a4c371d83`.
- Orca Run `run_3d23462a014a`, Task `task_0260be022067`, Dispatch
  `ctx_999991dd888d`, role `infra_builder`.
- `orca-ide orchestration worker-show --dispatch ctx_999991dd888d --json`
  returned exact worker/task binding and `projection.provider.model` =
  `gpt-6.1-sol`. Its terminal runtime preview displayed `GPT-6.1-Sol high`.
  `startOptions.launch.requested/effective` model/effort fields were null;
  they are not evidence of verified launch options.
- The coordinator independently confirmed Codex thread metadata model
  `gpt-6.1-sol`, `reasoningEffort high`, CLI `0.165.0` in durable Orca message
  `msg_ee01c5a1332f`. This is separate runtime evidence, not this worker naming
  its own model. The coordinator owns retaining the source metadata receipt.

Only the five files assigned by the dispatch are edited. Integration/push,
`HANDOFF.md`, `LOCAL_SETUP_REPORT.md`, canonical runtime selection and independent
review belong to the coordinator; this worker does not change those documents
or claim the complete Orca setup is finished. No new agent, real GPU job,
CV/VLM/data/weight access or environment installation is part of this work.

## 통합 후 로컬 상태

위 worker 검증 당시에는 persistent runtime을 만들지 않았다. 이후 총괄이 선택한 공통 runtime, 실제 worktree 간 smoke/서비스 재시작 검증, 독립 검토 및 게시 상태는 [LOCAL_SETUP_REPORT](LOCAL_SETUP_REPORT.md)를 따른다. 그 보고서의 현재 공통 절대 경로를 사용하며 worktree별 큐를 새로 만들지 않는다.
