# EXP-0022 — independent BATCH-0004 review

2026-10-29. **Final verdict: PASS for official-API technical smoke, faithful bounded reporting and preservation; useful pose evidence is insufficient in required 030_090, and 007_064 correspondence remains unreviewed.** This is a separate official-API recovery experiment, not a third BATCH-0003 attempt. A CPU preflight verdict will not establish successful GPU inference, actual person/joint correspondence, behavior discrimination or delivery completion. The remaining 265 inputs are held because the required key scene has no pose evidence; rule/tracker stages were not run. This review does not certify browser/GitHub delivery.

## Scope and provenance

The reviewer read AGENTS, the project README/charter/work plan, CODEX_NEXT_TASK, the complete BATCH-0004 plan, ADR-0020 and the prior EXP-0021 independent failure review. The historical two adapter failures and their inadequate call-contract preflight coverage remain unchanged. Reviewer ownership is this document and private review evidence under the new batch runtime directory. No helper, Git action, production edit, installation, model construction, GPU execution or media viewing/decoding is part of this review.

Saved native launch evidence identifies Run `run_3d23462a014a`, reviewer Task `task_656ab1d8e0c9` / Dispatch `ctx_633012716c3a`, requested/effective `gpt-6-astra` / `high`. The current implementation owner is Task `task_5df19346a61c` / Dispatch `ctx_9a8df3d90186`; native observations identify `gpt-6.1-sol`. These exact dispatches, rather than old worker rows, define this review's provenance.

## Pinned official API inspection

Thirteen independently fetched source/config files at commit `922563eab42b778445e55a2edbabb6974eed8e4b` match installed Ultralytics 8.4.192 bytes. Local evidence preserves each official URL and SHA256. No checkpoint was loaded to establish this source parity.

The public signature is `Model.predict(self, source=None, stream=False, predictor=None, **kwargs)`. Its kwargs are configuration, not arbitrary kwargs to the network. The official predictor's ordinary inference branch forwards `augment` and `embed`; it does not forward `visualize=False` into `BaseModel.predict`. The latter accepts `x, profile=False, augment=False, embed=None`, which explains the historical unsupported-argument failure. All actual new adapter kwargs still require independent validation once implementation freezes. [Pinned public API](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/ultralytics/engine/model.py), [predictor](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/ultralytics/engine/predictor.py), [network signature](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/ultralytics/nn/tasks.py).

Official setup deep-copies the loaded model, selects the backend with `fuse=True` and `end2end=(args.nms is False)`, and the PyTorch backend sets the end-to-end mode before fusion. FP32 is represented by unset/None `quantize`; the old `half=False` spelling is a deprecated mapping. First CUDA prediction performs one model warmup forward and a synthetic random-box NMS warmup before the sample's timed inference. Therefore NMS-free sample postprocessing does not imply no NMS function was called anywhere. Fuse and warmup distinguish this path from the failed unfused/no-warmup runner and must be measured/reported separately. [Pinned PyTorch backend](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/ultralytics/nn/backends/pytorch.py), [warmup](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/ultralytics/nn/autobackend.py).

Ndarray sources are BGR uint8 H×W×3; official preprocessing converts BGR to RGB and normalizes the resulting BCHW tensor. PosePredictor restores box/keypoint coordinates to original-image dimensions and produces `Results`; the adapter must not scale them again. Box/keypoint row association, exactly 17×3 per detection, empty results, invalid shapes/nonfinite values and low-confidence/sentinel unknowns require independent synthetic tests. Numeric eligibility is not human-visible joint correctness. [Pinned pose result construction](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/ultralytics/models/yolo/pose/predict.py).

## Acceptance criteria applied

Preflight must bind the exact new source/config/full kwargs, unchanged sole weight/environment and 267 source/PTS/RGB inputs, two smoke IDs and disjoint remaining complement, canonical lease/parent-child identity/free-VRAM gate, separate EXP-0022 accounting, at most one correction and preservation of any partial successes. Execution requires the coordinator's Git freeze and authorization after explicit preflight PASS.

After execution, inspect hash-bound saved Results summaries, technical failures versus normal zero persons, warmup/sample counts, costs and immutable previous records without exporting media or raw coordinates. Human correspondence evidence remains distinct from technical output and is required before remaining265. Final report, metrics and coordinator conclusion require explicit byte binding. Existing browser and GitHub remote verification belong to the coordinator; they cannot be inferred from this review.

## Independent CPU evidence and corrected draft findings

Fifteen synthetic CPU tests pass with CUDA hidden and uninitialized, no model construction or actual image input. Unlike the old metadata-only gap, these invoke the actual public `Model.predict` with a stub predictor, actual setup with a stub backend, and the actual `BasePredictor.inference → AutoBackend.forward → PyTorchBackend.forward` methods with a signature-checking stub network. Every supplied public kwarg passes the installed config validator. Additional cases exercise official square preprocessing/color conversion, native-coordinate Results construction including empty Nx17x3, adapter row correspondence/no second scaling, low-confidence/sentinel/out-of-bounds unknowns, malformed/NaN/class/confidence rejection, the exact 6144 MiB boundary and invalid direct lease rejection. One initial reviewer fixture assumed an unrounded LetterBox midpoint; its failed log is retained and its expected value was corrected for the official rounded resize/padding. No production guard was relaxed for that fixture.

The coordinator found the observer's decorated `setup_model.__code__` could identify a shared wrapper. The owner changed observation keys to `inspect.unwrap(...).__code__`; an independent test now invokes actual setup plus unrelated `Results.cpu` using the shared decorator and observes exactly one setup event with no leftover active frame. The reviewer also found that exception `return` events could inflate completed forwards; the owner now distinguishes attempted calls and non-None returned values. Owner-side synthetic exception regression checks one warmup success, one sample success and one failed sample independently of a model. These are instrumentation checks, not measured inference success.

Early draft smoke lookup lacked complete source/input/config and artifact bindings. The owner strengthened it, added execution-side fixed-key/attempt identity and per-input started/saved-output guards, and required hash-bound local human review provenance for remaining265. The current initial contract permits one attempt per stage and rejects automatic retries; any permitted one-time correction would need separately reviewed code/freeze and preservation rather than automatic budget reset. No correction is pre-authorized by this review.

Independent input validation matched all 302 file pins and 18,783 installed environment-file entries. The new manifest preserves the old 267 frames, exact native PTS/RGB/source identities, windows, sampling, sole checkpoint, environment and COCO17 ordering; smoke IDs are `030_090` and `007_064`, and their 265-frame complement is disjoint and complete. The initial canonical queue still has all 39 old jobs/39 attempts byte-for-field unchanged. The older 3,000-entry preservation snapshot matches apart from the catalog/assignment registries changed by subsequent authorized result registration; the new batch's 355-file root baseline separately captures the latest state. This is evidence for recorded scopes, not a claim that every repository/environment byte was independently archived.

CPU checkpoint construction time in the new runner is not directly comparable to the old runner's CPU-plus-CUDA loading interval: transfer and fusion now occur inside first public predictor setup. First-call setup, warmup, sample inference, tensor capture, observer synchronization overhead, Results.speed, allocator peaks and device-wide samples must retain separate scopes.

## Frozen smoke-only preflight acceptance

**Preflight PASS for the exact two-frame pose-only contract below**, conditional on the coordinator's committed-source/authorization binding and the unchanged live canonical lease and free-VRAM gate. This authorizes no remaining265, rule/tracker, retuning or autonomous retry, and is not a guarantee of GPU compatibility or useful person/joint estimates. This was the pre-execution verdict; final acceptance follows below.

| Frozen evidence | SHA256 |
| --- | --- |
| Readiness receipt | `9b89ca59022e5a9e86ae04ea81afc4174980709f9864acb383ab8f6afdd0b63a` |
| Source digest, 15 files | `1f33d6f8d9e4d1bf92645437b1d04d8abb99ccfeb6c265552c92328767f505a2` |
| New manifest | `dcd6501ef11cd8b7a06aeb2d0bf6c303acb6665ac65dc3a4f6e5d45bba8c4c98` |
| Smoke input contract | `e86d06ea40b0112723889b0e4ca2df891b7b5c4796e8ccfc886c029ab0db6ffb` |
| Historical manifest, unchanged | `6ea2fe8d692611f7808b1109a591fedff9cd8c901f13cc43474246324927883d` |
| Sole checkpoint, unchanged | `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4` |

All fifteen frozen source hashes and the readiness-bound API audit/test log match current local bytes. The owner's log reports 30 tests passed (16 new contract tests and 14 queue tests), with no skip. The reviewer separately ran fifteen independent synthetic cases and three owner critical regressions, all passing; these overlapping suites are not 48 independent requirements or predictions. No successful inference is inferred from them.

The full call is `model.predict(source=bgr, **PREDICT_KWARGS)` with no custom predictor override, using all 22 pinned public arguments:

```python
imgsz=640, rect=False, batch=1, conf=0.25, device='cuda:0',
quantize=None, nms=False, max_det=300, iou=0.7, agnostic_nms=False,
classes=[0], augment=False, compile=False, channels_last=False,
save=False, save_txt=False, save_crop=False, show=False, verbose=False,
stream=False, visualize=False, embed=None
```

`visualize=False` is valid public configuration and is consumed by the official predictor; it is not forwarded as a private network kwarg. Official end-to-end postprocessing applies strict confidence `>0.25` and person class filtering while preserving selected row correspondence; it does not suppress overlapping sample rows by IoU. Native Results coordinates are consumed without manual resize/NMS/head mutation. The reviewed observer uses unwrapped function codes and separates warmup/sample attempts from completed returns. Constructor/setup/warmup/runtime scopes and zero-person-versus-exception interpretation remain mandatory reporting constraints.

The coordinator reports commit `7c281e34bc12bd9b53f7cebe73f313f801f870e2` and supplies a Git-object/current-file comparison receipt for all fifteen frozen source files. This receipt matches the reviewed hashes; the reviewer performed no Git action. Actual execution still requires the coordinator's explicit smoke-only authorization and live gates.


## Actual smoke execution audit

**Technical smoke PASS; person/joint usefulness is not established.** Initial attempt `6509c805b40e4d7a8137f770cfa04a05` returned two official Results under the reviewed source/commit. The coordinator's authorization allows only smoke and binds the same fifteen source hashes. The saved summary SHA256 is `84905e3841a7394f0e3a0e214f7298746f33226fdaa3fafb703c3ded40cf5cde`; independent checks match its queue registration, exact native PTS/RGB metadata, architecture and twelve artifact hashes. Native Results/tensor/image files were checked as bytes without deserializing/viewing their media. The reviewer inspected only saved JSON contracts and aggregate observations.

| Observation | 030_090 | 007_064 |
| --- | ---: | ---: |
| Actual public Results returned | 1 | 1 |
| Person output rows | 0 | 2 |
| Retained joint estimates under fixed numeric policy | 0 | 23 |
| Public predict wall, seconds | 0.909371 | 0.027484 |
| Results inference interval, milliseconds | 12.631883 | 13.310806 |

The zero-person result is a normal empty Nx17x3 API output, not an exception or grounds for a technical retry. Two rows and 23 retained estimates in 007 are not confirmed people or correctly located joints. Both original/overlay comparison files exist and match recorded hashes, but image existence does not establish physical correspondence. No model-quality conclusion is inferred from this reviewer's unviewed pixels.

The run completed one warmup model forward and two sample model forwards, with two public calls and two saved native Results; the warmup is not a third evaluation input. Recorded architecture is native PyTorch, end-to-end, fused, FP32, COCO17×3, with first warmup completed. Observed input tensors are CUDA0 float32 1×3×640×640. No retry or remaining-stage job exists. All 39 previous jobs/39 attempts exactly match the root baseline; the queue now has 40 of each.

The pre-construction resource gate observed 7,864 MiB free against the unchanged 6,144 MiB requirement. Initial validation took 3.750996 s, CPU constructor/checkpoint loading 0.221487 s, first predictor setup 0.408727 s, official warmup 0.425134 s, run-entry interval 6.463836 s, and queue-attempt interval 11.141388 s. Setup/warmup are included in first public-predict wall; nested network and parent observer intervals overlap and must not be summed as disjoint durations. Results.speed excludes warmup and includes observer overhead within its profiled scopes. Allocator peaks were 204,846,592 allocated bytes and 228,589,568 reserved bytes after the runner's reset; these are not device-wide or whole-process memory peaks. No deployment FPS is established by two profiled samples.

**Remaining265 remains held:** the required actual person/joint correspondence gate has not passed, and the key 030 diagnostic has no returned pose despite the preserved user observation of people climbing at that moment. The coordinator recorded this explicit insufficiency decision after smoke; it is not merely a pending-approval delay or an execution error. Rule/tracker/behavior comparison remains unrun; there is no per-person GT, accuracy/F1/FPR, completion or legal-entry result. Preserve the two outputs and present the compact local human-review bundle without regenerating them. Browser/media display and remote publication remain separate coordinator evidence.


## Final report acceptance and byte binding

**Final acceptance PASS for the completed two-input technical smoke and its limited conclusions.** The report and coordinator conclusion correctly distinguish API recovery from unestablished useful joints/behavior. The required 030 scene returned no pose despite the preserved user observation; the coordinator therefore held remaining265. A favorable later 007 review would not erase that missing key-case evidence. The one local human question remains pending, and 007 correspondence is explicitly unknown. No extra GPU job, retry, rule, tracker or adoption is authorized by this review.

All 27 metric pointers resolve to their hash-bound source values: 22 measured entries agree with the actual summary, observer events, resource samples and queue timestamps; five formal behavior metrics remain null with zero evaluated samples. Warmup's observed sample count was corrected from the draft generic value two to one. The report's misleading draft phrase saying no GPU execution occurred after loading was corrected to no additional GPU execution after smoke. These reporting corrections did not change inference source or regenerate any output.

The actual receipt is non-synthetic, records exit code zero, and matches canonical attempt/job source/input/config/commit and saved supervisor/child identities. All 39 historical jobs/attempts and 104 protected historical source/config/report/review files match the root baseline. The fifteen execution source hashes remain frozen. The public CPU extraction builder is outside that allowlist; its hash agrees with metrics provenance. It was source-reviewed, not executed by this reviewer, because its reproduction includes Git reads and writes outside reviewer ownership. The producer's saved run and independent read-only numeric audit provide separate evidence.

The reviewed publication files contain code, aggregate counts/timings, provenance hashes and limits; no raw person-coordinate arrays, actual local absolute paths, media/tensor payloads, weights or credentials were found. This is a content review, not Git staging/publication verification. Original/overlay/native Results remain local.

| Accepted artifact | SHA256 |
| --- | --- |
| EXP-0022 report | `d7a988aafae7b14a184b128ef1f240d85944a4f48ec31d0ecb04257b4347ae3f` |
| Metrics | `c75ef5f7ebca3698e1ec37601492a808daffe4956dc08ad447733b2e91f29e71` |
| Comparison | `7c3f9f6c69ce2d83f395aee80956c318d61265a9fe73651a856a67ccf926ef37` |
| Costs | `1c1af575ed64fc8570cf2ecc732345e6fbae0b48e8903e14e70c914599bccaef` |
| Coordinator conclusion | `d6d2fe9983a98d10f3b018d897ea8ca378c9b72afc13daa470cf64f777919b20` |
| ADR-0021 final state | `6066f4fea90783e9af3d86e7bf0d7336be1a7883a44a27edb9efcb75c9b5d621` |
| Public CPU extraction builder | `c4d70ddcf2ec4af53cc04a88eaf8a5cfb11d093a5b8ed187125aad7e2452e81f` |

Changing these report/metric/conclusion bytes requires renewed binding review. The coordinator owns existing-web registration, actual local display of the two real comparison images and GitHub remote-byte checks. This smoke produced still-image evidence, not a pose video, so a fabricated video or a claim of playback/seek verification is inappropriate. Delivery completion remains separate from technical success, unreviewed 007 joints and the held behavior/adoption decision.
