# EXP-0023 independent review

2026-10-29. Independent Astra high review of BATCH-0005's exact five new official pose predictions and one cached full-frame result. The reviewer owns this document and local review receipts only; no Git action, model construction, GPU execution, source-media decoding/viewing or upload was performed. The coordinator owns source commit/authorization, registration, local browser verification and remote publication.

## Pre-execution verdict

**Preflight PASS for the frozen five-condition comparison**, conditional on the coordinator's exact committed-source binding and authorization, the live canonical queue lease and unchanged free-VRAM gate. This is a CPU/source contract verdict, not evidence of successful GPU execution, correctly recovered people/joints or behavior performance.

| Frozen evidence | SHA256 |
| --- | --- |
| Readiness receipt | `49e779eae2a38fc96464681214674909381edaa7725bcff950818034123fabd3` |
| Source digest, 24 files | `c6de4151fe1c836a8c607db1979e058154368461dc823b3be8187d2cf82f8a16` |
| BATCH-0005 manifest | `a7c01d94d70aafeb6910ec0958fadc8ad5b461005224eaf68fe83c59d553f045` |
| Input contract | `5078fb94bf0646c082e4ed9ba5198d1230f20a0c86200a9457208302b799682b` |
| Historical EXP-0022 summary | `84905e3841a7394f0e3a0e214f7298746f33226fdaa3fafb703c3ded40cf5cde` |
| Sole checkpoint, unchanged | `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4` |

All 24 source hashes match current bytes. The readiness-bound owner's 23-test log passes nine new ROI/API/provenance/budget/migration contracts and fourteen existing queue regressions. The reviewer separately ran seven relevant synthetic CPU tests, all passing, including installed public API/config signatures; these overlap the owner's suite and do not represent additional predictions. The reviewer did not rerun the owner's source-RGB decoding/full-environment audit or broad queue suite. Historical manifest equality, exact native PTS 84/90/94 and the three stored RGB file hashes were independently checked without decoding; the owner preflight supplies raw RGB/crop byte verification. Six cached native-result/input/image/event artifact hashes match the historical summary. Source/video, environment and checkpoint provenance remain the owner's fixed input contract, not a newly fetched dataset or model.

The only new public calls are, in order, `030_090_C6`, `030_084_full`, `030_084_C6`, `030_094_full`, `030_094_C6`. The loop has no empty-person early exit: a normal empty first result proceeds to the remaining four conditions. `030_090_full` is absent from new calls and is read from the exact hash-bound EXP-0022 zero-row summary for the comparison. Partial-start markers and native Results prevent regeneration; the exact single initial queue attempt and one fixed key are required. Automatic retry is rejected; any separately reviewed correction remains outside this initial execution authorization.

The fixed original 1920×1080 RGB crop is `[216:864,537:1440]`, shape 648×903×3, using floor minima and ceil maxima from existing C6 `[.28,.20,.75,.80]`. The unchanged batch04 utility converts RGB to contiguous BGR once. Native ROI Results are interpreted in crop coordinates before adding (+537,+216) once to the separate original-coordinate representation; native Results and local rows are retained. Low-confidence, out-of-bounds and (0,0) unknown joints cannot become retained because of translation. Full-frame Results receive no translation or resizing. Boundary coordinates follow the existing inclusive Results-coordinate policy; they are not array indices.

The official `model.predict(source=bgr, **PREDICT_KWARGS)` uses the unchanged Ultralytics 8.4.192 environment/checkpoint and all 22 EXP-0022 public arguments:

```python
imgsz=640, rect=False, batch=1, conf=0.25, device='cuda:0',
quantize=None, nms=False, max_det=300, iou=0.7, agnostic_nms=False,
classes=[0], augment=False, compile=False, channels_last=False,
save=False, save_txt=False, save_crop=False, show=False, verbose=False,
stream=False, visualize=False, embed=None
```

The existing official observer/resource helpers are imported read-only; the old runner is not executed. One model construction, official first warmup and five sample calls are intended and must be audited separately after execution. Native Results, captured tensors and event logs remain local. The runner requires the inherited canonical lock inode, live exact parent/child identities, native Run/Task/Dispatch, source/input/config hashes, coordinator commit and at least 6144 MiB free before model construction. Network transport/DNS is denied and no replacement model is used.

All forty historical queue jobs and forty attempts match the coordinator's preservation baseline. The owner's queue snapshot has the same rows in a different ordering. Of 374 previously tracked file hashes, the only changes at this checkpoint are the reviewed additive queue registration and current assignment record; historical batch04 sources and experiment/report/review files are unchanged. The registration adds batch05 without altering historical row content. No real queue mutation was performed by this reviewer.

The coordinator supplied source-commit proof for `62fe072bdd70f4e3eeb8c51a4984b96f221fea41`; its 24 Git-object/current-file hashes match this reviewed source freeze. This is coordinator-supplied Git provenance, independently matched to the reviewed receipt without a reviewer Git action.

## Required post-execution interpretation

The three original/full/C6 comparison artifacts must be checked by hash; their existence is not human confirmation of bbox/joint correspondence. Output rows and retained numeric joint estimates must never be described as correct people/joints without local human review. Full-frame and ROI have different observation ranges and scale/letterbox effects despite equal 640 model input. C6 calibrated is not physical fence-top/far-side calibration. Person tracking, rules, CV+VLM combination, full267, completion/legal judgments and accuracy/precision/recall/F1/FPR are outside scope. Final actual-run accounting, costs, historical preservation and report/metrics/coordinator-conclusion bindings remain pending.

## Actual execution audit

**Actual technical execution PASS.** The sole new attempt `90784d50902748b9956101771e27662b` ran under committed source `62fe072bdd70f4e3eeb8c51a4984b96f221fea41` and the same reviewed source/input/config contract. Its saved summary SHA256 is `1c08d87413a2bc399c2a426f63b865e7f3e2f817c8fc35801781ef206d67c46a`. Coordinator authorization matches the exact five ordered conditions. The non-synthetic queue receipt records exit code zero and the exact registered parent/child identities. An earlier coordinator-observed resource shortage caused a temporary hold, not a failed attempt; the actual pre-construction gate recorded 8262 MiB free.

The new run has one model construction, five public calls, five completed sample forwards and one separate completed warmup forward, with no error or retry. The five native Results and five started markers match the ordered approved conditions; no new 90-second full-frame call exists. Current canonical totals are 41 jobs and 41 attempts, with all forty prior jobs and forty prior attempts exactly preserved. All 24 frozen execution-source hashes still match.

| Native time | Full rows / retained estimates | C6 rows / retained estimates |
| --- | ---: | ---: |
| 84 s | 2 / 24, new | 3 / 38, new |
| 90 s | 0 / 0, cached EXP-0022 | 1 / 12, new |
| 94 s | 0 / 0, new | 0 / 0, new |

These are output rows and retained numeric joint estimates, not verified people or correct joints. The 90-second ROI result supplies new estimates where full-frame had none, but actual body correspondence remains unreviewed. The 94-second pair returns normal empty Results, not technical exceptions or proof that no person is present. The batch finishes here without tracking, rules or further GPU work.

The reviewer checked 27 new artifact hashes (15 Results/tensor/event files and 12 images comprising three triptychs and nine panels) plus the six cached artifact hashes. Native Results/tensors/images were hashed as bytes without deserializing or viewing them. Saved local-to-original JSON arithmetic independently matches exactly one ROI translation for 68 joint entries; all eighteen unknown statuses remain unknown after translation. Full-frame row records are unchanged. Native PTS and stored RGB metadata match the frozen three input records. This validates data plumbing and provenance, not anatomical correctness; a local human comparison of the three images remains necessary.

All five observed input tensor metadata records are CUDA0 float32 1×3×640×640. The backend records native PyTorch, fused, end-to-end, FP32, 17×3 keypoints and completed warmup. Observer event files agree with summary events, tensor metadata and separate forward counts.

Constructor/checkpoint CPU loading took 0.205794 s; first predictor setup 0.360853 s; official warmup 0.443770 s; run-entry interval 6.352339 s; canonical queue attempt 9.631618 s. Public call walls in execution order were 0.903369, 0.034790, 0.024386, 0.033997 and 0.028063 s. First-call setup/warmup and nested network intervals overlap; adding them as disjoint costs would double count. Results.speed excludes warmup but includes observer/synchronization and tensor capture overhead within its scopes. Allocator peaks after reset were 204,847,616 allocated and 228,589,568 reserved bytes, distinct from device-wide samples and whole-process VRAM. Cached full90 has no new prediction cost; its historical timing remains attributed to EXP-0022. Five profiled calls do not establish deployment FPS or reliable comparative speed.

All 52 public metric entries resolve to their hash-bound sources. Forty-seven measured/diagnostic entries agree with saved aggregate counts, costs and event/queue evidence; five formal behavior metrics remain null with zero evaluated samples. The public extraction builder was source-reviewed rather than executed by this reviewer because it repeats full-input decoding and writes outside reviewer ownership. Final publication-byte binding follows once the report and coordinator conclusion are complete.

## Final report acceptance and byte binding

**Final acceptance PASS for completed technical execution, faithful bounded reporting and preservation.** The report, metrics and coordinator conclusion distinguish five new predictions from the cached full90 result and official warmup, and keep actual person/joint correspondence unresolved. The conclusion correctly preserves the prior user observations as prior observations: around 84 seconds three people stand/approach and around 90 seconds three climb the gate, as recorded in the existing MVP evaluation notes. Those observations do not validate any new overlay row or joint and do not provide per-person completion GT.

All 108 protected historical experiment/report/review/record and batch03/batch04 source files checked after execution match the coordinator's baseline. The exact current frozen source, forty historical queue jobs/attempts, original cached artifacts and null behavior metrics are preserved. The nineteen device samples and their aggregate extrema agree with costs. No model source changed during this final report review.

The accepted public files contain code, aggregate diagnostics, provenance hashes and limitations; no original image/tensor/native Results payload, raw person-coordinate arrays, actual local absolute paths, checkpoint or credentials were found. This content review is separate from the coordinator's Git staging/publication checks. The three triptychs and nine individual panels remain local. Their byte hashes were verified; owner-reported decode/shape checks and coordinator browser rendering are separate evidence, and neither certifies real body correspondence.

| Accepted artifact | SHA256 |
| --- | --- |
| EXP-0023 report | `0978d472573ac037a268483b8b358b8d8b5b359f7557c372fc621f9a1dab1e36` |
| Metrics | `1143c6d5e7f6587a63047edcf7a711564f7eed5ddb42118c489b4de89ce18070` |
| Comparison | `1797f459950f62bcb50cce9fb85d13d3d5fc1ecb58de3035ef3127b81b039ec7` |
| Costs | `a5043cc503dd092d4857ce271c8fcfdece529002ebc51c4140b08fb0fc967a5e` |
| Coordinator conclusion | `a197b5247ae9202f65234996304e5ca1c6a18d283a36581d7cbc4808ecf4d910` |
| ADR-0022 final state | `1e065da0a366bcf0a3aa6fe33025311d9e3a453842f0bed40578b9da6c409874` |
| Public CPU extraction builder | `357ce2189bb054813d8936ebd46e50e1f61aa2debe6a2ece981459154add38b1` |

Any change to these accepted bytes requires renewed binding review. The one bundled local human review request remains unanswered at this binding: actual bbox, wrist/hip/knee/ankle correspondence, occlusion, duplicates, non-person suspicion and ROI truncation remain unknown. The recommendation to review the existing three images before any new experimental scope is supported; default adoption, tracking, rules, CV+VLM and formal behavior evaluation remain held. No further GPU execution is authorized or queued by this review.

The coordinator owns final registration, actual existing-web image rendering and GitHub remote-byte evidence. Still-image evidence has no video playback/seek claim. This review establishes its named technical and reporting scope, not operational accuracy or delivery completion.
