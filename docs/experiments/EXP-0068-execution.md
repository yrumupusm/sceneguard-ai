# EXP-0068 — actual YOLO26m person-only pilot execution

2026-11-08. **The authorized actual five-epoch run completed, but its fixed validation result worsened.** This is a bounded execution smoke/smallfit result, not school improvement. No subsequent model run, retry, threshold adjustment, validation-selected checkpoint or tuning followed it. Other models in the main six-model scope remain pending.

## Actual execution

Source HEAD `40c434a70fd50a03b4698a7d18780a3febc2f8c0`; canonical command `person-detector-train`, stage `train5`, job `1d01c841d451418cbb68f8fca4be2b16`, attempt `47adf16ca4fa4145b50e0ee150106c38`. Child exit0 and supervisor exit0 were positively observed; both process identities are `exited`. One new job/attempt succeeded; all144prior job rows and144prior attempt rows are exactly unchanged. Final queue145jobs/145attempts is idle. No retry occurred.

The frozen [protocol](EXP-0068-protocol.md) used all50train frames/151person box rows from two groups, and25validation frames/31box rows from one other group. Manifest SHA256 `1bda84cc3421bcfc1b528bfb4e4092c02e9ec22d4a09c41907ff46211381ad18`; all three EXP67 current answer_version1 and source bindings were rechecked read-only before enqueue, at runner start and after fitting. The explicit confirmed person/completeness labels are used; actions/identity remain unknown. School45/EXP64test are not inferred on or trained on, and EXP62 AFTER/EXP64 selected weights/0.5 and prior outputs are preserved.

All five epochs completed exactly25batches of two frames, accumulation1 and125actual optimizer updates, constant AdamW1e-4 FP32, fixed last epoch5. There was no automatic AMP, download, model warmup or augmentation. Epoch mean native training losses were2.107138,1.765629,1.565485,1.291848,1.076205. Those are optimization losses, not detection accuracy. All396named parameter tensors changed and remain finite, including actual first-backbone weights and both native box/classifier branches; optimizer states and gradients are finite. Explicit changed group tensor counts are backbone3, native one-to-many box24/classifier42 and one-to-one box24/classifier42. The backbone group checks the first block, while the full changed-name inventory covers the entire model.

The six official pretrained COCO class0 classifier rows were transplanted with no random classifier initialization. All other layers/hidden widths were kept. Across both raw heads and all25validation frames, regression and person logit maximum absolute difference before versus after adaptation was **0.0**. The paired baseline is this exact adapted, untrained one-class model; global80class versus1class top-k competition is not claimed to be equal.

## Fixed paired person result

Root evaluator `scripts/evaluate_person_detector_pair.py` uses the same25frames/31human-confirmed box rows with original pixel xyxy, retained confidence0.05, fixed evaluation confidence0.5 and deterministic maximum-cardinality one-to-one IoU0.5. It independently checks image SHA/frame/time and records each GT hit/recovery/loss.

| Condition | TP | FP | FN | Precision | Recall | F1 | Mean matched IoU |
|---|---:|---:|---:|---:|---:|---:|---:|
| Exact adapted untrained baseline |31|0|0|1.000000|1.000000|1.000000|0.976163|
| Fixed last epoch5 |6|0|25|1.000000|0.193548|0.324324|0.870231|

Paired GT rows: both detected6, newly missed25, recovered0, both missed0. Precision1.0 after fitting has only six matched output rows and does not establish low false-positive behavior in other scenes. These25frames share one event, and labels derive from explicitly human-reviewed YOLO26x proposals; correlated sampling and proposal-origin selection bias remain. These are box/frame counts, not people counts, action labels, independent generalization or school performance. Reduced training loss did not yield a better validation result. No hyperparameters were selected from these results and no additional fit is authorized by this report.

## Local durable evidence

Actual output directory: `outputs/model-comparison/exp0068/queued/train5/47adf16ca4fa4145b50e0ee150106c38/`. Source/input/model bindings are in the immutable queue config and input contract; result source hash `33f91324c466ff1d109771f427e64686a88ce1c9c327cc70a06804b5e99902b5`, input hash `ba83b2fc4e76df6ba5e3f72cc8c753ddcdb31cb81338b223452d83839a14bc26`.

| Artifact | SHA256 |
|---|---|
| result.json |cca006fd4d57ee83dba32e614ef4528f336670b3697038e6c0dfa4f3789b7aff|
| Canonical attempt receipt manifest.json |c76fd3f300488760f7b8de9605c6a3ead41251f8ecbd5f54cf9d748b7c44a15c|
| initial.pt, full model/state plus empty initial optimizer |436426a56cb2699c7be3391b3dc1e4c06b268b357b330e3b1cf13409ee01ef53|
| last.pt, full model/state plus actual optimizer125 |42c348982b4788c23fe731ede7117a40098b2fb3c995d6f4faee3687fc5544b9|
| before-predictions.jsonl |09ad9a110af6b11f95dae42ceb3f884053e5bdd92f065d941a6daeddf4634d5a|
| after-predictions.jsonl |f2d70e2b7719cf7b226fef2fdd8017aae545579d21dc142b4be323d66f7106ff|
| before-all-anchors.npz |02f970f19356c55d85da5674917b791fd8fa8fce7be579a102cbfc51dc9e41c4|
| after-all-anchors.npz |88d0b470cfa3f37d874c69a34ccc22fa17f2769511549ac8905bb157ef888fc6|
| optimizer-steps.jsonl |ffa0e27274d9ef723c485fd6e5078fbdd242f487b082e32c091bf2fd38c60c64|
| person-adaptation.json |73853ecaa240d7155a1d3a623eb454e8ca592e0883d7abafd3b85aa2be08ec56|
| executor/execution/paired-evaluation.json |5065df51571eba5256b092ddcaa2413b1d632a632620d979c3e0ae6249977d2a|

The two NPZ files retain all8400decoded native one-to-one anchors per frame without confidence filtering or top-k; the before/after JSONL uses native single-class top300 and original-pixel finite positive-area boxes. Full epoch frame inventories and125step logs are saved. No media, labels or checkpoints are sent to cloud image tools.

The child monotonic measured interval is52.642615seconds including adaptation/parity, fitting, checkpoints, validation and selected integrity checks; peak PyTorch allocated/reserved GPU memory is2,502,774,784/2,648,702,976bytes. Canonical wall-clock timestamp difference49.723710seconds is recorded separately and differs from the monotonic timer; the cause is unverified and no throughput inference is made. Neither interval measures source-video realtime FPS.

## Release history and limits

The first candidate `063cdad81f66a033` was superseded before any enqueue: read-only native loss inspection found that Ultralytics8.4.192 returns named loss items as a dictionary. The logging serializer and native dual-head loss/backward/schedule regression were corrected in40c434a. All19trainer/evaluator CPU tests pass; earlier14queue regression tests passed, and root separately verified old repair/export regressions. The initial test oracle also confused a scale index with a classifier layer; that test was corrected before freeze. These preparation corrections did not produce failed GPU attempts.

Actual candidate `candidate-a31fa76996a526a3.json` SHA `71e1e1433414147deaeb97d7ac3befa9a34800e9a0dfd2c868a15f7dd6bf76df` was independently accepted by `reviewer/execution-release-v2.json` SHA `7b45f43877dfa10cc4f80caa30d13ca55ce1f3014870c44fc6c537f50bef5adc`. Concrete coordinator GO `msg_22d11e9c9459` binds `root-grant-v1.json` SHA `72439e195fb1b28cd7f3f60bf6b0f392e6b737058ef7a519fa0a1eb57702eb84`.

A pre-enqueue resource guard first observed less than6144MiB free and wrote `executor/resource-waits/wait-060eecbde64240435497c6ac0d541d11c254d3d87a1dac29b24def5653e701dc.json`, SHA `066980d42e7520edc68a8449ceb368cb7ed2ef485da9be1533160820f12d9aec`, with zero new jobs/attempts. After capacity recovered to6978MiB, the same exact approved executor performed the sole run. Other processes were not stopped and the guard was not lowered.

Independent CPU actual-output audit passed in `reviewer/actual-output-audit.json`, SHA `b356a2019581cb5dda5c6e550d9f669c21a04a8ece4ae2626f00f05ad2e94a02`: full finite checkpoints/396optimizer states/125positive-gradient steps, exact initial official-person adaptation, raw25×8400×5 arrays and independent matching all agree. Independent `reviewer/queue-result-audit.json`, SHA `752e15daef2fa5f3cb5337422fc1d9a74373ee676fb02a2bf8583ff6596026d3`, confirms the exact145/145queue, all144historical rows preserved, zero retries, idle queue and both process exits. Root-owned visual/web/public delivery remains tracked separately and is not implied by successful fitting or these audits. The pretrained default, protected school/test outputs and all other model candidates remain preserved; do not promote the degraded pilot as a new default or automatically start another fit.
