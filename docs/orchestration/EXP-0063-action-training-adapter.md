# EXP-0063 action queue adapter implementation

2026-11-06. This is an implementation handoff, not a training result. No GPU execution, actual queue migration/enqueue, model download, production change, original report/catalog/binding edit, or truth change was performed by this worker. The coordinator owns final clip-plan-v2/release creation, independent review and actual execution.

## Implemented contract

`orchestration.action_training_command` adds `action-train` to the existing queue. `Queue.enqueue` validates before its additive migration; the existing backup, lock, row/attempt preservation and foreign-key checks remain in use. No import, input-contract calculation or status read migrates the queue. The adapter allows exactly `smoke` and `train`, with one job key per stage and manifest hash. Automatic retries are rejected; a failed execution requires a separately reviewed plan.

The interpreter is the existing `.venv-cv-batch02/bin/python`. Only the committed R3D-18 trainer/adapter/queue and focused tests are bound as source files. Configuration and all local input artifacts have complete SHA256 bindings. The pinned official pretrained SHA is `b3b3357ead25631ec9c57362ff2128a92d0427e01e2cd184951a44380c3f2e9d`.

Enqueue, supervisor and child validate the current native Orca Run/Task/Dispatch/owner; revoked/completed dispatches, non-live fleet liveness and an unproven exact worker are rejected. An authorization file must bind committed HEAD, exact source hashes, input digest, stage and context, with `confirmed`, `training_authorized`, `independent_review_passed`, and `explicit_gpu_go` all true. The supervisor saves `action-training-config.json` and `action-live-assignment.json` beneath its existing attempt directory. The child verifies the actual running attempt, supervisor process identity and registered config/input/source hashes.

The queue passes the inherited canonical `SCENEGUARD_GPU_LOCK_FD` and `CUDA_VISIBLE_DEVICES=0`. The child checks the canonical lock inode and proves an independent open cannot acquire it. The adapter queries GPU0 with `nvidia-smi`; the trainer checks CUDA free memory again. Both require at least6144MiB. A queue exit receipt does not establish model quality.

## Clip/review release interface

The label policy is `official_actor_action_intervals_sampled_alignment_review`; review status is `sampled_alignment_review_complete`. Row alignment is `annotation_interior_both_origins` and `official_annotations_sampled_alignment_review`. These declare official reference labels after sampled alignment review, not human certification of every clip. Existing frame/interval/ROI checks and all45 regression source hash/path exclusions remain enforced. Source/hash, annotation hash, group, split and location must match frozen combined split v3 SHA `bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499`.

The external trainer flags are `--review-release PATH --review-release-sha256 SHA`. They avoid circular release/manifest hashes. Release JSON must contain:

- `schema_version:1`, `experiment_id:"EXP-0063"`;
- `manifest_sha256`, `split_manifest_sha256`;
- `review_snapshot:{path,sha256}` and `interpretation_policy:{path,sha256}`;
- `reviews:[{request_id,version,answer_version}, ...]`, matching all8 exact saved snapshot requests.

The snapshot contains a `requests` array, including original answer, version, answer_version and source_binding_sha256. Release and manifest review provenance must match: manifest `review_evidence.review_snapshot` equals release `review_snapshot`; `review_evidence.review_policy` equals release `interpretation_policy`; and their `reviews` lists match. The snapshot and policy files are hashed again. This is a local content-bound snapshot, not a cryptographic human signature or permission to reinterpret ambiguous answers. The manifest also binds `config_sha256`, `baseline_lock_sha256` and `source_split_sha256`.

CPU `preflight` and `prepare` modes accept the common existing manifest/baseline/split/config/output flags plus the two release flags. `prepare` writes exact native-PTS decoded letterboxed `.npy` clips and a hash-bound `prepared.json`. Use a new immutable output revision; existing outputs are rejected. Those CPU modes do not execute the model or touch the actual queue.

## Queue config and execution interface

A new recovery queue config has exactly five keys; the historical four-key form remains readable only for prior receipts:

| Key | Value |
| --- | --- |
| `stage` | `smoke` or `train` |
| `execution_revision` | Exactly `amp-overflow-v2` for the reviewed recovery |
| `context` | Exact current `{run_id,task_id,dispatch_id,owner}` |
| `files` | Smoke: `{manifest,baseline_lock,split_manifest,config,prepared,review_release,weights}`. Train adds exactly `preparation_evidence`; each value is `{path,sha256}` |
| `authorization` | `{path,sha256}` of the coordinator authorization JSON |

All file paths are absolute local paths. `files.prepared.path` points to `prepared.json`, not its directory. Authorization includes `context`, `stage`, `execution_revision`, `recovery_from_attempt`, `input_hash`, `sources`, `code_sha` and the four true flags above; train additionally includes `smoke_result:{path,sha256}`.

To calculate the read-only input contract from an assembled queue config:

```bash
.venv-cv-batch02/bin/python -m orchestration.action_training_command --queue-config /absolute/path/to/assembled-queue-config.json
```

The authorization hash is not part of its own `input_hash`; obtain that hash with `digest(input_contract(config))`. Source bindings come from `sources()` and include the frozen CPU preparation producer and the focused preparation-provenance counterexamples. The config can be assembled in two phases: calculate the input/source contracts, create authorization, then bind its hash into config. Creating these files does not enqueue work.

After review and explicit coordinator execution GO, use the existing queue API to register and execute only the returned job ID:

```python
from orchestration.action_training_command import RUNTIME, read, input_contract, job_key
from orchestration.queue import Queue

def execute_reviewed_config(config_path, timeout_seconds):
    config = read(config_path)
    inputs = input_contract(config)
    queue = Queue(RUNTIME)  # Existing queue, never Queue.initialize here.
    registered = queue.enqueue(
        job_key=job_key(config), command='action-train', config=config,
        input_value=inputs, timeout=timeout_seconds, **config['context'])
    return registered, queue.run_once(job_id=registered['job_id'])
```

Use a deliberate timeout large enough for the stage; the adapter permits at most172800seconds. `run_once(job_id=...)` uses the existing detached supervisor and avoids draining unrelated jobs. This snippet was not executed against the actual queue.

Outputs are new directories under `outputs/action-recognition/exp0063/queued-training/{smoke|train}/{attempt_id}`. Smoke deterministically selects the first16 official negative and16 positive training clips, plus2 negative and2 positive validation clips in manifest order. It rejects insufficient real examples, reads/hashes/loads no test source or prepared pixel files, and runs one epoch with8 full batch4 microbatches and2 AdamW steps, including persistent optimizer state. It records actual microbatch sizes, accumulation, optimizer steps, memory/history and `test_accessed:false`. Train authorization must bind a successful same-manifest/config smoke result with32train/4val, the requested full microbatches, accumulation4, exactly2optimizer steps and the canonical proof described below. Smoke checkpoints are separate and are not resumed into the full training.

Full train retains10epochs, seed6301, AMP, AdamW and validation-CE checkpoint selection. Only after selecting the best checkpoint does it evaluate the test once. Scores retain source/event/actor/action/PTS/evidence, and errors are exported with annotation-reference FP/FN types. Results separate `same_place` and `heldout_place`, source/event/clip denominators and per-action negative FP/TN/FPR or positive recall. Human precision/recall/F1 and intrusion completion accuracy remain null. Official reference action performance is not intrusion completion or production performance. The final config records the four explicitly supported normal classes and `validation_negative_coverage:"sitting_only"`; it does not claim walking/waiting validation coverage.

## Verification and remaining work

Focused CPU checks passed in the existing environment:24trainer tests,9adapter tests, and14existing queue regression tests (47total). They cover exact release/version/hash tampering, frozen splits/leakage/regression exclusions, real native video decode, missing test-pixel files during smoke, insufficient smoke rows, full-batch train gate, null human metrics/cohort separation, live assignment/GO/committed source checks,6144MiB boundary, wrong/unheld FD rejection, CPU child FD/device environment inheritance, and migration of a read-only copy of the actual queue with every existing job/attempt unchanged. The migration test modifies only its temporary copy.

```bash
.venv-cv-batch02/bin/python -m unittest discover -s tests -p test_action_recognizer.py -v
.venv-cv-batch02/bin/python -m unittest discover -s tests_orca -p test_action_training.py -v
.venv-cv-batch02/bin/python -m unittest discover -s tests_orca -p test_queue.py -v
```

No actual memory measurement or training success is claimed. Remaining: coordinator final clip/release/CPU preparation, independent review of committed files and final actual inputs, live execution assignment/GO, actual smoke, then the first full training/evaluation. Existing reports/catalog/bindings, production modules, all45 original regression videos and results, review DBs and actual queue rows are preserved by this worker.

## 2026-11-06 train-only completed-preparation revision

Root explicitly opened an adapter-only revision window in Orca message `msg_02a17481de9d` while no GPU authorization or attempt existed and GPU resources were externally occupied. This superseded the earlier after-smoke timing restriction; it did not permit changing the trainer, queue, CPU decoder, model/config, manifest, release, baseline, or inference code. Those files remain byte-identical to the reviewed source freeze. This section records implementation and CPU checks, not actual training or inference. No actual queue mutation, model load, GPU job, or raw-media rescan was performed for the revision. The initial implementation was committed previously; this revision awaits Astra diff review and root commit GO.

The previous train path hashed the full original corpus once at input build, once at enqueue, once in the supervisor command, and once in the child guard. The full5741 manifest contains1081 unique videos with29,697,473,482bytes (27.6579274628GiB), so those four calls hash110.6317098513GiB of logical video bytes. Optional independent pre-validation adds another pass. These are metadata-derived logical-byte counts, not measured physical-disk reads or elapsed-time benchmarks. Smoke36 uses19 videos/573,676,957bytes (0.5342783006GiB) per pass.

Smoke retains its exact seven-file schema and existing selected-original hashing, no-test-pixel behavior, model, sampling and actual computation. Train requires exactly those seven files plus `files.preparation_evidence`, an absolute `{path,sha256}` binding. Its JSON has the following exact shape; `binding` means exactly an absolute local path and a lowercase64hex SHA256, not a mutable filename-only reference.

```text
{
  schema_version: 1,
  kind: "completed_action_preparation_v1",
  scope: "full_corpus",
  prepared: binding,
  producer_contract: binding,
  successful_result: binding,
  source_gate_receipt: binding,
  equivalence: {report: binding, sequential_snapshot: binding}
}
```

The evidence's prepared binding must equal `files.prepared`. The producer files are the same directory's exact `contract.json`, `result.json`, `verified-source-hashes.json` and `sequential-equivalence.json`; a `failure.json` marker rejects the publication. The producer contract must equal `prepared.preparation.contract`, have prepare mode/workers4/expected full clip count/counts, match current reviewed trainer and CPU driver bytes, and bind the same manifest/config/split/baseline/release/review snapshot/policy. Prepared clip IDs must equal all frozen manifest clip IDs with unique producer-local absolute NPY paths; the current full manifest has5741. The completed result must have status prepared, workers4, the same full clip count and the exact prepared.json SHA. Smoke-only, benchmark, partial, failed and missing results cannot authorize train.

The source-gate receipt must have passed and contain each original video/official annotation path and its frozen manifest hash exactly once, with no missing, extra, duplicate or conflicting entries. This is HISTORICAL successful-preparation provenance. Training does not reopen or claim to freshly verify current unused raw video bytes. Current official annotation bytes are still hashed (34,465,431bytes/1081files in this corpus), and every actual selected NPY byte is freshly hashed at every training guard. No stat/mtime cache or unchecked pixel cache substitutes for those consumed-input checks.

The exact2033 sequential prefix snapshot is additionally pinned to SHA `080bf01a7cd5c686e73cdd744b2087f46c3631ae73df9371e67b501f2c07633c`; it cannot be replaced by a shorter re-bound self-declared subset. Its manifest hash must match; every snapshot clip must exist in full prepared with identical recorded NPY SHA. The equivalence report must cover the whole snapshot, with byte/array/dtype/shape flags all true. Actual full prepared NPY bytes are verified; historical snapshot pixels are not training inputs and are not reread merely to repeat the completed producer's comparison. All split, content/path regression45 exclusion, alignment, review release and source/HEAD/live queue/FD/device/resource/no-retry guards remain in force. Actual all45 inference consumes originals, so its existing current-original hash verification remains unchanged.

Train additionally requires a canonical successful smoke, beyond a self-declared result JSON. Read-only canonical SQLite lookup must find the same succeeded action-train smoke job/attempt and exact result-manifest path. Its receipt must be nonsynthetic, succeeded, and match all registered command/job/assignment/source/input/config/commit fields; attempt snapshot and stored config/input digests must agree. The recorded historical reviewed authorization and each source's committed bytes are verified, and the historical trainer core SHA must equal the current frozen trainer SHA even though adapter/queue revisions may differ. Manifest/config/official weights/baseline/split/release must match the requested training.

The deterministic36 smoke IDs must be exactly32training/4validation/test0, have the exact source provenance and all36 pixel hashes equal the corresponding current full-prepared hashes; smoke result requires eight batch4 microbatches, accumulation4, exactly2optimizer steps, smoke-only completion and test_accessed=false. Historical smoke prepared metadata must match its queued pixel map. No old smoke NPY or raw video is reopened: current full-prepared NPY bytes were freshly verified. The returned proof is saved in action-live-assignment provenance. An invalid proof fails before live assignment/model/resource execution; it cannot be bypassed by binding only a result file. Smoke checkpoints remain unused as training initialization.

CPU command:

```bash
.venv-cv-batch02/bin/python -m unittest tests_orca.test_action_training_provenance tests_orca.test_action_training tests_orca.test_action_inference tests.test_action_regression tests_orca.test_queue tests.test_action_recognizer -v
```

85tests passed in15.900seconds, including17 focused provenance/smoke-proof tests with multiple counterexamples. Training succeeds in the fixture with every original MP4 absent and raw opens trapped, while all38 consumed synthetic NPY files are freshly rehashed across each of four repeated contract calls. Tests reject missing/modified NPY and annotation bytes, failed/partial/smoke/benchmark publications, metadata/review/driver/trainer binding changes, source receipt duplicates/missing/extra/wrong hashes, regression45 path/content leakage, equivalence corruption and substituted canonical smoke receipt/config/input/pixel/core evidence. Existing smoke raw-source access and test-pixel exclusion, source/liveness/FD/resource/queue and action inference tests still pass. Synthetic queue proof uses only a temporary SQLite file; the actual canonical DB is read-only and unchanged.

Next steps require independent review and root commit/source-freeze revision before any execution authorization. Full preparation must actually publish its successful complete receipts; a canonical actual smoke must succeed; then a new exact-source/input/HEAD train GO may authorize the unchanged model's first full run. No performance gain, action quality, actual GPU memory, training success or all45 inference is claimed by these CPU tests.

## Bounded AMP overflow recovery — reviewed source window

The original full train attempt `058639f80f394a71b345eb4eae5ceacb` failed with exit1 on the nonfinite-gradient check before the first epoch history. Root proved both child and detached supervisor exited and then explicitly opened the bounded source revision in `msg_63d36578509e`. The failed job/attempt/output, original successful smoke and all97 pre-recovery canonical rows remain history. This is a numerical implementation correction, not a new model/config/data/threshold search, and no all45 empirical result exists. The execution worker owns the trainer's optimizer-only correction; this adapter revision does not edit queue.py, CPU driver, config, manifest/release, prepared pixels, baseline, or inference source.

Future runnable configs require top-level `execution_revision:"amp-overflow-v2"`. Authorization must bind the same value and `recovery_from_attempt:"058639f80f394a71b345eb4eae5ceacb"` along with existing exact committed source/input/HEAD/current assignment/GPU GO flags. New deterministic keys append this fixed revision to the stage+manifest key; unknown revision strings are rejected. Missing-field old keys exist only for historical receipt comparison and cannot pass new execution validation. Queue.retry remains forbidden; new revision jobs get distinct IDs/output paths and one initial attempt each. No old failed job is reset.

The fixed failed parent is observed through read-only canonical SQLite and its nonsynthetic failed receipt: exact99d18b3 historical code, train stage, failed job/attempt, exit1, one attempt and registered config/input digests must agree. A new smoke shares the same six manifest/baseline/split/config/release/weight bindings but can retain its distinct36-clip prepared.json and seven-file schema. Full train additionally requires the original full prepared/evidence bindings (eight-file schema). Unknown/running/succeeded or substituted parent records cannot authorize this recovery. Root's positive-exit proof is required before the source window; this metadata check neither guesses process death nor changes queue state.

Old full prepared pixels are NOT relabeled as produced by revised code. Their producer trainer stays SHA `2a0d01de3ec9b872c99761472b0626ba1e5f41a5b9f2c9be4eef4fe5626ff350`, anchored to Git `99d18b3e1e899ef17380ca3f7e87de290f1e3859`. The adapter reads those old committed bytes without executing historical code and verifies the whole-file hash. It compares every existing non-main helper definition byte-for-byte and by AST, all module import/global dependencies, full main definition metadata with body omitted, and main's AST body through `optimizer=AdamW` inclusive. This protects CLI/data/CPU prepare branches, decoder/ROI/letterbox/native samples, manifest/config/release/partition/prepared validation, seed/model/weights/normalization and nested batch/evaluation code.

Only the specifically reviewed new undecorated optimizer helpers `install_actual_step_counter`, `amp_optimizer_update`, and `ensure_finite_training_state` may be added. Duplicate/shadowed functions, added global writes/imports, executing defaults/annotations, main decorator/signature/return-annotation changes and preprocessing/model drift fail. Post-optimizer accumulation/scaler handling, actual/attempted/skipped accounting and finite-state telemetry are the separately reviewed numerical change. The compatibility proof records historical producer commit/SHA, current execution trainer SHA, all helper digests, imports/global AST digest and protected main-prefix digest in the input contract. Existing5741 prepared/source/equivalence bytes, exact2033 prefix anchor, current consumed NPY and annotation verification,45 exclusion, review/split/live queue/FD/resource guards remain intact; no raw-video rescan or43-minute CPU re-decode is needed for unchanged pixels.

The old successful smoke cannot authorize a changed trainer core. Revised train requires a canonical succeeded smoke with the same `amp-overflow-v2` revision and the CURRENT trainer core, together with identical manifest/config/official weights/release and all36 current full-prepared pixel hashes. Its SHA-bound result must record actual updates2, attempted updates2, skipped updates0, positive finite AMP scale, finite model/optimizer state and the hash of its two actual `amp-updates.jsonl` events. Event counters, applied/skipped flags, accumulation boundaries, sample counts, before/after scales and one-epoch history must agree. A step count based only on attempted calls is rejected. Source/live-assignment provenance records both this numerical proof and the preserved failed parent.

Candidate CPU verification: the combined provenance/adapter/inference/regression/queue/trainer suite passed100tests in15.791seconds, including optimization-only compatibility, shadowing/default/decorator/return annotation/global/import/prelude attacks, old-Git/producer replacement, separate smoke/full-parent data rules, same-core/revision proof and malformed AMP finite/counter/update evidence. Only synthetic temporary DBs are mutated by these tests; the actual97 canonical rows are preserved. The trainer's numerical tests are owned by the execution worker. Final candidate hashes, independent review, root commit/source freeze, a new actual revised smoke and a new full train GO are still required; no recovery GPU execution is implied by these tests.

The earlier all45 runtime handoff pinned to HEAD99d18b3 must not execute after recovery source commits. Preserve those artifacts and issue a newly reviewed runtime revision against the new root source freeze before actual action inference. The unchanged all45 v2 coverage/ROI/advisory contract remains fixed.
