# EXP-0066 person-label repair execution

Current status: independently reviewed, explicitly released canonical one-job inference completed on all75frames, saving217unreviewed proposals; queue144/144 is idle, both processes exited and143prior rows/raw annotations are preserved. Underlying artifacts retain the EXP0066 namespace; root's new human review/editor workflow uses EXP0067 so the answered original EXP0066 report/media remain immutable.

The active assignment is Run `run_3d23462a014a`, Task `task_2cc40cbc8e6e`, Dispatch `ctx_6fdc2f3a6d68`, owner `term_12928c5f-4b0d-4d2d-934f-d104b905e0dc`. This separate task supersedes the completed-baseline GPU stopping boundary only for the explicitly authorized bounded missing-person draft work. Detector training and GT promotion are not authorized by preparation or a proposal pass.

## Exact prepared scope

Cases1/3/5 only: native indices99–123 at33–41seconds (train),159–183 at53–61seconds (train), and40–64 at13.333333–21.333333seconds (validation). Each case has25actual consecutive3FPS source frames. Original train50/validation25 allocation, source/event groups and exact review answer versions1/2/1 are preserved. The prior applied answers concern missing-person completeness; they do not certify precise boxes, frame-origin interpretation, identity or behavior. Case3 boundaries/duplicate actor0 are not filled/merged, and case5's later climbing behavior remains unknown.

CPU preparation is `outputs/model-comparison/exp0066/label-repair-v1/prepared-v1/manifest.json`, SHA256 `758660c56333e6712c980c6f0f8eddaff93fcc9d7594fcc8dadf5c8191324aa8`. All75PNG files are original1920×1080 RGB, verified against the immutable display review's native frame index, PTS tick/timebase, source RGB SHA and source video SHA. Original label files have separate verbatim byte-identical copies; both origin0/origin1 box layers and all79origin1 annotation rows remain raw and separate. Empty annotations stay unknown, never background GT. No YOLO training text labels or accepted corrected boxes are generated.

The fixed review/answers/decisions/head-plan/pilot/baseline metadata hashes are hard-bound in the preparer. The pilot2/4/6 manifest remains SHA256 `1df00c365ed086e3d6a2fa801a65fdf78bda5f41361c600c3ce3c237385ff814`; no pilot frame is re-inferred or copied into this repair. Three selected source hashes are disjoint from protected school45, and original plan/pilot source/group splits are retained without train/validation leakage. No protected school45 or EXP0064 test media is decoded or used to train/select thresholds.

```bash
CUDA_VISIBLE_DEVICES='' .venv-exp0066-encoders/bin/python scripts/prepare_person_label_repair.py \
  --output outputs/model-comparison/exp0066/label-repair-v1/prepared-v1
CUDA_VISIBLE_DEVICES='' .venv-exp0066-encoders/bin/python -m unittest tests.test_person_label_repair
```

The prepared output already exists and is immutable; reproduction requires a separately named fresh owned output. The command/runner release binds the exact prepared manifest above.

## Queue-only draft pass and editor schema

Root owns the shared queue registry edit. New canonical command `person-label-repair`, stage `draft75`, model `yolo26x`, one job/1800seconds, uses the existing shared lease with inherited reservation FD, live current Run/Task/Dispatch/owner, exact committed code/source/input/spec/environment bindings and unchanged6144MiB resource guard. No standalone inference path exists. The runner imports Torch/model code only after the actual running-job/FD/source authorization guard.

The existing official pretrained YOLO26x checkpoint SHA256 `9fdd44a31c504547ffb81d2c6d9e6dac3493c8eaa8b0398d3f43bae6c7003e92` and existing frozen spec SHA256 `e314c38d874e3a73903fb387e7f611a07c067a16d017e3a3367d04012c45136f` are reused. Official whole-frame640, FP32, batch1, RGB-to-contiguous-BGR, native end-to-end person-class0 output at0.05/max300 and default review display0.5 remain unchanged. No added NMS, tracking, proposals-as-input, crop, tuning or new model is used. The adapter's16-slot interface receives a non-copying repeated view of one native RGB; it consumes only slot8, so there is exactly one actual input image per scored frame and no temporal evidence/interpolation/future-frame use.

Canonical outputs are `outputs/model-comparison/exp0066/label-repair-v1/queued/draft75/ATTEMPT/proposals.jsonl` and `result.json`. Each row preserves the prepared frame's source/image/review/annotation fields, both original box layers, exact native PTS/index and separate `proposals` array. Stable proposal IDs are `FRAME_ID:yolo26x:INDEX`; each proposal has original-pixel `xyxy`, person score, native class0, valid-area flag, model/spec provenance and `review_state=unreviewed_model_proposal`, `human_verified=false`, `training_eligible=false`. Retained native detector output and fixed call metadata remain in `detector_output`. Original annotations and model proposals are not matched, deduplicated, unioned or promoted to GT. No-detection rows are preserved and do not certify no visible people.

Root's editor can consume the prepared manifest now and attach the separately bound proposal stream only after canonical success. Human choices/corrections belong to a new versioned review history; the preparer, raw labels and model drafts remain immutable. Saved human edits do not auto-start training. Official model warmup is unscored additional work:75scored outputs do not mean75total forwards; native prediction speed excludes warmup while enclosing elapsed includes it. Total forward count and separate warmup time are not invented.

## Freeze and execution gates

Root committed queue/prepare/infer/command/tests and the EXP0067 protocol; the runtime executor is independently hash-bound. `executor/run.py candidate` performs CPU-only actual input/RGB/source/label/vendor/environment checks, committed source-map verification, live assignment check and read-only snapshot of all143historical jobs/attempts. Every candidate approval flag remains false. Candidate, executor SHA, actual input binding/hash, files, source maps, HEAD and initial queue snapshot must match a separate independent acceptance with status `accepted_person_label_repair_execution_release`, then a new root grant with status `root_authorized_person_label_repair` and actual native GO message.

Only `run` with exact bound root grant/SHA/message can create execution authorization. Resource preflights occur before execution-directory creation/enqueue; insufficient/unverifiable capacity records a wait75 with zero queue mutation. The canonical command/runner recheck the gate under the real reservation. Existing execution/STOP/job-key state refuses retries. The canonical `Queue.run_once` implementation already creates and waits for a detached supervisor; positive child/supervisor exit checks therefore remain valid without another wrapper. Any failed or unverifiable real attempt is preserved and stops further work.

After release, acceptance requires exactly one successful canonical job/attempt, actual result/receipt/source/input/context hashes, all75frame/proposal rows and unchanged raw annotations, all143prior rows preserved, idle queue and positively exited processes. Human precision/recall and completeness remain unknown. No commits/push, cloud media upload, shared source/registry edit by this worker, or training has occurred.

## CPU validation so far

Ten tests pass in the existing encoder environment. They cover exact75/native3FPS/split/answer versions, review/scope/clock changes, protected school/source/group leakage, actual75RGB/79annotation verification, immutable annotation/image/coverage flags, repeated single-image adapter view, proposal geometry/score/action/native-mode rejection, missing GO and wrong held FD, retry refusal, and preserving temporary queue CHECK migration with zero attempts. The first migration fixture used an uninitialized temporary Queue; changing the fixture to the actual `Queue.initialize` API fixed it before source freeze. No real queue or model was run by these tests. The executor has additional CPU-only release/wait/retry counterexamples; actual candidate/review/release and execution evidence follow separately.

## Final CPU candidate ready for independent execution review

Exact committed source HEAD `a8dfd8fdd63d22902de807a591fca2e6d5dd6b44`; ten-file map is bound in `runtime/model-comparison/exp0066/label-repair-v1/executor/candidate-9c73cea12004295a.json`, SHA256 `7e2b5acbb27880dbef10e1f7987d81cffd603e9dd190f76f5e404e33c7760b61`. Runtime executor SHA256 `49e47666418e4d735c359b37787676742cfc7d7b54e9c628d7ba4b8adac314dd` is independently hash-bound. Ten preparation/registry tests and three executor release/wait/no-retry tests passed. The real canonical143jobs/attempts remain unchanged; only synthetic temporary queues were mutated by tests. Root and reviewer confirmed that canonical `run_once` itself detaches and waits for the supervisor, so the existing method is retained. Every candidate permission flag remains false, and actual model inference/queue registration is zero. Independent execution acceptance and a new exact root grant/path/SHA/native message remain required.

## Actual reviewed release and one-job completion

Independent acceptance `runtime/model-comparison/exp0066/label-repair-v1/reviewer/execution-release-v1.json` SHA256 `896eda0c60ad9e603f516494b5bb56b639e8214767438a8f7b1cedf22b981459` accepted candidate7e2b5acb/executor49e47666/committedHEADa8dfd8f/actual input6d19a930. Native root GO `msg_1ed0343480bd` and exact grant delivery `msg_80f055781777` bound `root-grant-v1.json` SHA256 `167cc09435396ccc0ebbe7a6c805c5243c44d4a69a5ceba71a919d20d64bb535`. The reviewed executor check passed before run; resource gates and actual held-FD/live-context/source guards passed at execution.

Canonical job `3b29e75eea2b47afb706520b5f6de728` / attempt `7aa4c4bb65ec46ac9d4cd4f4dcb00775` succeeded with75native scored images/train50/validation25. Both actual process identities exited and the144jobs/144attempts queue is idle, with all143prior rows unchanged and exactly one new job/attempt. No retry or fallback occurred. Original75images, three raw label files and all79origin1rows/both origins remain unchanged;217unique model proposal IDs remain separate and unreviewed,182valid rows meeting the unchanged0.5default display condition.

| Case | Split | Native frames | Raw origin1 annotations | Returned drafts at0.05 | Valid drafts at0.5 |
|---|---|---:|---:|---:|---:|
| 1 | train | 25 | 12 | 98 | 77 |
| 3 | train | 25 | 49 | 84 | 74 |
| 5 | validation | 25 | 18 | 35 | 31 |

These are unreviewed detector rows; no difference/subtraction from original annotations is counted as recovered people, and human review still determines correct coordinates/completeness. Root's EXP0067 workflow must bind exactly the shown proposal IDs/coordinates/frame/image hashes and answer version; hidden lower-score drafts and a union with old labels are not automatically approved. No training, action-label/identity inference or ground-truth promotion occurred.

Proposals `/home/jhc7484/dev/sceneguard-ai/outputs/model-comparison/exp0066/label-repair-v1/queued/draft75/7aa4c4bb65ec46ac9d4cd4f4dcb00775/proposals.jsonl`, SHA256 `bab8bf53add31dca3715f413d09b1cc1e280eecf08cfd81c5355cc004371fb60`. Result SHA256 `f1b71dc1756c5d1a32c38a13dd96e6197680c3bca7d670ed1ab86ba2e05dec63`; canonical receipt SHA256 `7ae47e95258e59f13745ffbe687bce1abf43e96fc2e55d1d8f956811881793e3`. Complete paths, current process exits, per-case counts and provenance audit are bound in `runtime/model-comparison/exp0066/label-repair-v1/executor/actual-output-proof-v1.json`, SHA256 `28e3517642bbe3689a7259847f48676a77b1bbd0d503c0a494d9416f2a997aaf`. Native GPU peak allocated/reserved bytes are 439,168,512/635,437,056; canonical enclosing elapsed 10.984835s and load 0.536142s.75scored outputs exclude unscored official warmup; total forwards/separate warmup time are unknown.

Root and independent reviewer received actual result/proposal/receipt paths immediately. Actual artifact/editor/75preview-frame reviews passed independently; label acceptance and a frozen detector-training protocol remain later stages. No further GPU/model work is authorized by this success.

## Independent closing acceptance and handoff

Independent actual-output acceptance `runtime/model-comparison/exp0066/label-repair-v1/reviewer/actual-proposals-review-v1.json`, SHA256 `3a87b48d81321707fa9ba4578c093a12e1f92047880347945faa7ecea0384faa`, matches the canonical result/receipt/proposal bindings and accepts75frames, both exited processes, idle144rows and preserved143history with human/training flagsfalse. Editor/package/all75preview-frame acceptance SHA256 `b00e2b1c6fb1538b32fed7394373ddd3b31e684dda73183e26a31536f738fd31` preserves both origins and all217model candidates/79original rows while displaying182valid model rows at0.5. Actual browser acceptance SHA256 `f66219b5a606f21302e5cc9c413d79fa4dc0ab9178f2a5cf19ba6c293c76688a` checked all75frames and playback/previous/seek with zero POSTs and all75real frame reviews still pending. This verifies artifact/frame/coordinate/provenance and UI behavior; it does not certify the proposals as human ground truth.

Root accepted the complete worker scope and requested settlement in native message `msg_656fedc7f03d`. Root owns EXP0067 registration/delivery and subsequent human approval/dataset/protocol work. This task performed one released canonical model job and no further GPU work, training, truth promotion, shared queue edit, commit/push or cloud media transfer.
