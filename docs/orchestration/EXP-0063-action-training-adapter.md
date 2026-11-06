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

A local queue config has exactly four keys:

| Key | Value |
| --- | --- |
| `stage` | `smoke` or `train` |
| `context` | Exact current `{run_id,task_id,dispatch_id,owner}` |
| `files` | `{manifest,baseline_lock,split_manifest,config,prepared,review_release,weights}`; each value is `{path,sha256}` |
| `authorization` | `{path,sha256}` of the coordinator authorization JSON |

All file paths are absolute local paths. `files.prepared.path` points to `prepared.json`, not its directory. Authorization includes `context`, `stage`, `input_hash`, `sources`, `code_sha` and the four true flags above; train additionally includes `smoke_result:{path,sha256}`.

To calculate the read-only input contract from an assembled queue config:

```bash
.venv-cv-batch02/bin/python -m orchestration.action_training_command --queue-config /absolute/path/to/assembled-queue-config.json
```

The authorization hash is not part of its own `input_hash`; obtain that hash with `digest(input_contract(config))`. Source bindings come from `sources()`. The config can be assembled in two phases: calculate the input/source contracts, create authorization, then bind its hash into config. Creating these files does not enqueue work.

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

Outputs are new directories under `outputs/action-recognition/exp0063/queued-training/{smoke|train}/{attempt_id}`. Smoke deterministically selects the first16 official negative and16 positive training clips, plus2 negative and2 positive validation clips in manifest order. It rejects insufficient real examples, reads/hashes/loads no test source or prepared pixel files, and runs one epoch with8 full batch4 microbatches and2 AdamW steps, including persistent optimizer state. It records actual microbatch sizes, accumulation, optimizer steps, memory/history and `test_accessed:false`. Train authorization must bind a successful same-manifest/config smoke result with32train/4val, the requested full microbatches, accumulation4 and at least2optimizer steps. Smoke checkpoints are separate and are not resumed into the full training.

Full train retains10epochs, seed6301, AMP, AdamW and validation-CE checkpoint selection. Only after selecting the best checkpoint does it evaluate the test once. Scores retain source/event/actor/action/PTS/evidence, and errors are exported with annotation-reference FP/FN types. Results separate `same_place` and `heldout_place`, source/event/clip denominators and per-action negative FP/TN/FPR or positive recall. Human precision/recall/F1 and intrusion completion accuracy remain null. Official reference action performance is not intrusion completion or production performance. The final config records the four explicitly supported normal classes and `validation_negative_coverage:"sitting_only"`; it does not claim walking/waiting validation coverage.

## Verification and remaining work

Focused CPU checks passed in the existing environment:24trainer tests,9adapter tests, and14existing queue regression tests (47total). They cover exact release/version/hash tampering, frozen splits/leakage/regression exclusions, real native video decode, missing test-pixel files during smoke, insufficient smoke rows, full-batch train gate, null human metrics/cohort separation, live assignment/GO/committed source checks,6144MiB boundary, wrong/unheld FD rejection, CPU child FD/device environment inheritance, and migration of a read-only copy of the actual queue with every existing job/attempt unchanged. The migration test modifies only its temporary copy.

```bash
.venv-cv-batch02/bin/python -m unittest discover -s tests -p test_action_recognizer.py -v
.venv-cv-batch02/bin/python -m unittest discover -s tests_orca -p test_action_training.py -v
.venv-cv-batch02/bin/python -m unittest discover -s tests_orca -p test_queue.py -v
```

No actual memory measurement or training success is claimed. Remaining: coordinator final clip/release/CPU preparation, independent review of committed files and final actual inputs, live execution assignment/GO, actual smoke, then the first full training/evaluation. Existing reports/catalog/bindings, production modules, all45 original regression videos and results, review DBs and actual queue rows are preserved by this worker.
