# EXP-0074 B/C preparation — no training executed

2026-11-09. Prepared the auditable A/B/C plan, future canonical queue command and executable training loop, BN verification, and paired person comparison. This worker ran **zero optimizer steps, zero GPU work, and produced zero trained checkpoints**. The read-only WEB `pending --include-acknowledged` check returned `{"requests": []}`; no review/web state was changed and no media was uploaded. Historical `scripts/train_person_detector.py` was read and imported as a reference without modification.

The dispatched preparation scope was expanded by the coordinator to include the new `orchestration/person_bn_comparison_command.py` and minimal `orchestration/queue.py` wiring. No live queue migration, enqueue, retry, training authorization, Git commit, or push was performed. Only temporary synthetic queues were mutated by tests.

## Frozen comparison

| Variant | Initialization | Future training behavior |
|---|---|---|
| A | Exact official pretrained person slice in EXP68 epoch-0 `initial.pt`, without fitting | Baseline only; same person-head top300 semantics as B/C |
| B | Same EXP68 `initial.pt` as C, or the pinned official checkpoint with the exact six classifier row-0 slices | Full fine tuning; BN running statistics update |
| C | Identical initial trainable weights and buffers to B | Full fine tuning; only BN `running_mean`, `running_var`, and `num_batches_tracked` remain fixed |

The exact initialization SHA-256 is `436426a56cb2699c7be3391b3dc1e4c06b268b357b330e3b1cf13409ee01ef53`; official YOLO26m SHA-256 is `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`. No trained `last.pt` is accepted. The loader checks EXP68 epoch=0, optimizer_steps=0, empty optimizer state, and bitwise equality of every model/state_dict tensor against the official 80-to-person exact slice. The existing official hidden widths and all other weights remain intact.

All B/C parameters, including every BN affine weight and bias, are trainable. C calls `model.train()` and then sets only BN modules to evaluation mode; it reapplies this policy after each training-mode reset and checks all three BN buffers after each future update. This intentionally uses the fixed running statistics for C's forward normalization. It does not freeze entire blocks or disable BN affine gradients.

Both variants use seed 68, AdamW lr=0.0001, betas=(0.9,0.999), eps=1e-8, weight decay=0.0005, batch=2, image=640, epochs=5, FP32, no AMP, no EMA, no augmentation, no warmup, no gradient accumulation, zero loader workers, and gradient clipping at 10. The historical letterbox/target conversion and native dual-head loss are reused. `criterion.update()` occurs after epochs 1–4, yielding one-to-many gains 0.8, 0.625, 0.45, 0.275, 0.1. Model/criterion/optimizer are fresh for each variant. The plan records every epoch's exact `random.Random(68+epoch)` frame order and batches, with no historical 50-frame slice. Selection is always epoch 5.

## Dataset and evidence

The coordinator's canonical dataset is `outputs/model-comparison/exp0074/person-data-v1/manifest.json`, SHA-256 `01a08a3d42e610a3489b05859c9425ffe462b3709f46f967ea4537a48df2cf90`. This frozen version contains **197 frames: train 122 / 333 GT boxes; development 75 / 56 GT boxes**, including 25 explicitly reviewed empty development frames. It retains the original reviewed197; later corrected labels require a separately bound revision. Generic code derives counts and steps from the bound manifest, allowing an explicitly reviewed future revision without hardcoding197. This version plans 61 batches per epoch and **305 future optimizer updates per variant**.

The validator checks stable unique frame IDs, exact image bytes, finite source PTS, positive source dimensions, original-pixel GT geometry, unique per-frame GT IDs, confirmed-person/protected-data declarations, explicit per-frame `person_completeness_verified=true`, and valid source SHA-256 values. Source hashes, event/capture reservations and image pixels must be disjoint across splits. It accepts absolute images or paths relative to the manifest. The complete manifest bytes bind review provenance and original source metadata. Membership in protected school45/EXP64test relies on the coordinator's dataset provenance/audit; a declaration alone cannot prove exclusion. Physical capture independence remains uncertified, so this development split is diagnostic and is not an independent test.

Final local evidence is under `runtime/model-comparison/exp0074/bc-preparation-v1/`:

| Artifact | Meaning |
|---|---|
| `summary-v2.json` | Final bindings, verification counts, read-only queue state, and remaining gaps |
| `plan-v3.json` | Current dataset/image, pretrained weight, configuration, source, model-spec/environment hashes and exact five-epoch orders |
| `tests-v3.json` | **46 passed, 0 failures/errors/skips, 6.698 seconds**: 23 new preparation tests, 14 existing queue tests, 9 existing matcher tests |
| `yolo-cpu-verification-v3.json` | Actual YOLO26m architecture, synthetic batch2×3×640×640 inputs, CPU forward-only checks |
| `queue-B-unreleased-v2.json`, `queue-C-unreleased-v2.json` | Reviewable future command envelopes; authorization is null and no submission occurred |

Earlier versioned evidence is retained. Final plan and test source bindings match. The actual-model verification predates the final dataset-validator guards and A/gap wording corrections; its BN/initialization verification code was unchanged by those fixes. The model-spec vendor files and environment snapshot are bound; future release validation also checks the installed interpreter environment.

Actual-model verification found **124 BN modules and 396 trainable parameter tensors**. Two forwards per variant, each preceded by an outer `train()` reset and policy reapplication, changed **372 B buffers and zero C buffers**. All trainable weights remained bitwise unchanged. Before/after BN state hashes, the exact official-slice initialization proof, Torch/Ultralytics versions and source hashes are recorded. These inputs were synthetic; this check did not compute dataset detection scores, loss, backward passes, or optimizer updates.

Synthetic module tests verify nonzero BN affine gradients, repeated training-mode resets, preserved C buffers, B running statistics/counters, identical initial B/C trainable parameter sets, the pinned loss-gain schedule, partial final batches, data/split/hash rejection, and stable A/B/C matching. A five-epoch checkpoint simulation saves and reloads **temporary synthetic modules with optimizer_steps=0 and empty optimizer state**, explicitly marked `synthetic_checkpoint_simulation`; it is not evidence of trained YOLO checkpoints. Interrupted writes leave no published partial file, existing artifacts cannot be overwritten, and synthetic receipts are rejected by the actual-result verifier.

Independent review exposed two initial validator counterexamples: an incomplete frame could pass, and the same source could cross splits under different event/reservation labels. Both were fixed before the final artifacts. New regressions reject missing/false completeness, missing/malformed source hashes, and cross-split sources regardless of those labels; the canonical197 manifest remains accepted unchanged.

## Future execution contract

`python scripts/prepare_person_bn_comparison.py prepare` creates a plan only. `python -m orchestration.person_bn_comparison_command --help` describes preparation of an enqueue envelope from an existing plan, real assignment context and optional existing authorization. It does not enqueue work. The recorded envelopes use this preparation dispatch for provenance only and must be regenerated with the actual future training dispatch and release.

The registered future queue command is `person-bn-comparison-train`, with stage/variant B or C. Canonical execution remains gated by matching committed source bytes, exact plan/config/input hashes, a new independent release, a bound coordinator grant and GPU GO message, live native assignment, the canonical queue snapshot/attempt, the inherited canonical reservation FD, supervisor process identity, and the selected output directory. Old EXP68 grants cannot authorize it. Automatic retry is refused.

After those checks, the future loop creates a fresh AdamW optimizer, executes the fixed five epochs, and saves each `epoch-01.pt` through `epoch-05.pt` with complete model/state_dict/optimizer and provenance. Each checkpoint contains per-tensor dtype/shape/content hashes plus the aggregate state hash, exact manifest/initialization/config/source bindings, epoch order hash and used loss gains. Publication uses same-filesystem atomic hard-link creation after fsync, refuses overwrite, and emits a file-SHA receipt. Queue success requires all five real checkpoint receipts/bytes, exact step totals and fixed epoch5 selection; an exit-zero child with missing output fails. Actual YOLO checkpoint serialization with a populated optimizer and GPU training remain unexecuted.

Temporary queue tests preserve existing rows and command names across the new migration, retain foreign keys and backup behavior, reject an unreleased enqueue before migration, exercise an inert exit-zero child through the new dispatch route, reject its missing result, and forbid retry. A final **read-only** canonical DB query found **145 jobs / 145 attempts / no active jobs / zero new-command jobs / no new-command schema migration**. The canonical database was never opened for writing by this worker.

## Paired comparison and limitations

The new comparison helper accepts complete A/B/C development predictions with exact frame-image/PTS bindings. It retains stable `(frame_id, gt_id)` keys, deterministic maximum-cardinality IoU0.5 matching at confidence0.5, per-GT retained/recovered/new_miss/persistent_miss states against A, and per-frame/event TP/FP/FN with unmatched FP indices. It does not invent persistent identity for unmatched predictions across models. Prediction production remains separate and must retain native end-to-end semantics, no extra NMS and the fixed thresholds; B/C predictions do not exist yet.

The coordinator's existing `outputs/model-comparison/exp0074/baseline-v1/A-evaluation.json` reports development **TP56/FP0/FN0 on 75 frames**, and train **TP288/FP9/FN45 on 122 frames**. This worker read that artifact and bound its hash; it did not rerun dataset inference. The current development recovery denominator is therefore **zero**. These197 frames can assess retention/new misses and FP changes, but cannot demonstrate development recovery. Training misses must not be reported as held-out recovery; later reviewed data needs its own frozen revision and provenance.

Preparation is executable and tested within this scope. Independent execution release, matching committed code and a future actual training assignment remain required; real B/C optimizer updates, native epoch checkpoints, predictions and performance comparison have not run. Existing weights, historical trainer, original reviewed197, school45 and EXP64test were not modified by this worker. No detector improvement, action accuracy, or independent generalization is claimed.
