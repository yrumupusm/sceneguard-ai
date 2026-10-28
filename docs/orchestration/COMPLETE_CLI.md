# Coordinator result registration

`orchestration.complete` implements the fixed [delivery contract](EXPERIMENT_DELIVERY.md). Only the trusted coordinator invokes registration after receiving an actual native Orca assignment and a separately authored review. The CLI does not authenticate a role, launch agents/models/jobs, change native lifecycle state, or create experiment/report/review content. Registration, experiment execution, GitHub publication, and actual browser verification remain separate facts.

Use the existing environment; installation is unnecessary:

```sh
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.complete --help
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.complete --config LOCAL_CONFIG assign --assignment ASSIGNMENT_JSON
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.complete --config LOCAL_CONFIG complete --package PACKAGE_JSON --artifacts LOCAL_ARTIFACTS_JSON
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.complete --config LOCAL_CONFIG status --experiment EXPERIMENT_ID
```

Replace uppercase arguments with existing local file paths or an experiment identifier. Config must already contain absolute `repo_root`, existing canonical `runtime_dir`, `artifact_allow_root`, and the existing `artifacts` mapping (which may be empty). Use the same runtime across worktrees; `completion.lock` serializes assignment, completion, and status operations. This lock is separate from the GPU execution lock. Config is local-only and must not be committed. The command never reads existing media bytes or copies media.

Assignment JSON has exactly the fields listed in the shared contract: `experiment_id`, `slot`, `title`, `run_id`, `task_id`, `dispatch_id`, `agent_model_requested`, `agent_model_effective`, `reasoning_effective`, `assigned_at`, and `synthetic`. Slots are `slot1`/`slot2`/`slot3`; an unknown effective model or effort remains null. Time must include a timezone. IDs use ASCII letters, numbers, underscores, and hyphens, up to 128 characters. A dispatch cannot be assigned to two experiments. Existing identical assignments are unchanged; conflicting assignments are rejected. Assignment does not check native state or prove that a requested model was invoked; retain the real Orca receipt separately.

Completion package JSON has exactly the required fields in the shared contract, with an optional `synthetic` boolean. It references existing UTF-8 Markdown under `docs/experiments/` and `docs/reviews/`, plus JSON under `records/EXPERIMENT_ID/`. Report, review, and metrics must be separate files. Package title must match its assignment. Execution status is `succeeded`, `failed`, or `inconclusive`; review status is `accepted_for_comparison`, `needs_revision`, `blocked`, or `inconclusive`; decision status remains `adoption_on_hold` or `rejected`.

Metrics JSON requires `schema_version: 1`, matching `experiment_id`, and a `metrics` array. Each metric requires `label`, `value`, `unit`, `sample_n`, `scope`, `source`, `source_sha256`, and `verification`. Values are finite numbers or null, never booleans or numeric strings. Measured values need a positive integer sample size, a lowercase SHA256, and verification other than `unavailable`; null measurements may use null sample size/hash. Source is a safe relative provenance reference, not an instruction to open a raw output. The registrar does not recompute measurements or inspect their raw sources. Extra public metadata in metrics is retained in its original file; duplicate JSON keys, NaN, and Infinity are rejected.

The reviewer must write both exact lowercase SHA256 strings into the separate review Markdown, then supply those hashes as `reviewed_report_sha256` and `reviewed_metrics_sha256` in the package. The registrar compares those supplied values with the actual report and metrics bytes. It never silently refreshes an old review to new source hashes. A review containing matching hashes establishes a version link; it does not prove independent review quality or human approval.

Local artifact JSON has only an `artifacts` object mapping evidence IDs to `{path: ABSOLUTE_LOCAL_PATH, kind: video_or_image}`. IDs must match package evidence exactly; entries require both `path` and `kind`. Supported media matches the existing viewer: video `.mp4`, image `.jpg`/`.png`. Each path must point to an existing regular file under the configured allow root, without symlinks, hidden components, traversal, or special files. Kind must match evidence. Existing allowlist entries are preserved, conflicting mappings rejected, and IDs belonging to another result cannot be reused. Empty evidence requires an empty artifact mapping; it does not certify video verification.

Public records, package, metrics, report, and review undergo conservative checks for credential-shaped strings and absolute local paths; known private/raw-payload field names are prohibited in structured public inputs. Public paths reject hidden components, traversal, backslashes, and absolute locations. All directory walks and file opens reject symlinks, including configured roots. Public JSON/document reads are bounded to 4 MiB. These checks are not a comprehensive secret scanner or a substitute for coordinator publication review. CLI errors deliberately omit input values and local paths.

After all validation, completion creates an immutable `docs/reviews/EXPERIMENT_ID.binding.json`, merges the local config allowlist, then atomically replaces the public catalog last. Binding uses the existing viewer's `reviewed_sources` schema, includes the review hash, and retains the synthetic label and registration digest. Existing catalog rows and the three input documents are preserved. Each replacement flushes its file and parent directory. A crash can leave an unindexed binding or merged allowlist; rerun the identical command to finish. A changed payload, assignment, review, artifact mapping, or completed ID is rejected, including after partial failure. Registration does not revise an already completed ID; coordinate a new approved experiment rather than overwriting one.

`status` reports whether assignment/catalog registration exists and whether current report/metrics/review hashes match the binding. Missing or changed documents are unavailable/stale. It always leaves `github_publication`, `browser_verification`, `native_lifecycle`, and `artifact_availability` as `unverified`: a successful registration does not demonstrate any of them. The coordinator owns publication and browser receipts. Content can change outside the cooperative runtime lock; status checks current bytes, and a changed report/metrics/review requires new review and delivery verification.

Historical EXP-0001–0007 IDs are reserved and their existing rows are untouched. The historical importer rejects any nonempty assignments list or nonhistorical catalog rows before reading local sources or writing files; malformed/symlink guard files also fail closed. Historical import is an offline setup operation and must not run concurrently with initial assignment creation.

Synthetic fixture IDs must start `TEST-` and explicitly set `synthetic: true` in both assignment and package. Real IDs use `EXP-` plus at least four digits and `synthetic: false` in assignment. Tests generate all fixture reports/metrics/reviews/media metadata inside temporary directories; there are no public fixture results. No real experiment is run by this implementation or its tests.

Local verification on 2026-10-28 uses:

```sh
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m unittest tests_orca.test_complete -v
```

The bounded fixture suite covers byte-identical retries, shared runtime locking, conflicting IDs, stale review sources, numeric/source metadata, unsafe paths/artifacts, partial-write retry, preservation, importer guards, and receipts that do not imply GitHub/browser verification. Worker role is `infra_builder`; the coordinator reported actual thread metadata `gpt-6.1-sol/high`, Codex CLI 0.165. Actual experiment execution, GitHub publication, service restart, API integration, and browser playback are not performed by this worker.

Final local result: **24 tests passed in 0.573 seconds**, with `git diff --check` clean. An intermediate extended-suite run had one fixture setup error: a nonhistorical-import case was accidentally placed after a symlink case and wrote through the fixture symlink; the cases were separated and the full suite passed. All generated artifacts remained in the temporary fixture repository and were removed by test cleanup. Repository `records/assignments.json` remains empty; no TEST results are registered in the real catalog.
