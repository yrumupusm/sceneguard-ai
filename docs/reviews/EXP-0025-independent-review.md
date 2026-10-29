# EXP-0025 independent review

2026-10-29. Independent review of BATCH-0006's fixed C6 ROI comparison: three new official YOLO26m-Pose predictions at input size 960 against three cached EXP-0023 results at 640. The reviewer owns this document and local review receipts only; no Git action, model construction, GPU execution, media decoding/viewing or upload is performed. The coordinator owns committed-source authorization and final registration/browser/remote delivery.

## Review status

**Pre-execution CPU/source PASS for the exact freeze below**, conditional on the coordinator's committed-source binding and explicit execution authorization plus live canonical lease/resource gates. This is not evidence of successful GPU execution, new body/joint correspondence or behavior improvement.

The reviewer independently checked the immutable EXP-0023 summary SHA256 `1c08d87413a2bc399c2a426f63b865e7f3e2f817c8fc35801781ef206d67c46a` and all nine native Results/tensor/event artifact hashes for its three C6 records, without deserializing Results or decoding/viewing media. Their native PTS are 1290240/1382400/1443840 with time base 1/15360; cached output rows/retained joint estimates are 84 seconds 3/38, 90 seconds 1/12 and 94 seconds 0/0. These are preserved outputs, not new predictions or precise anatomical ground truth.

At the initial review checkpoint, all 41 historical canonical queue jobs and 41 attempts match the coordinator's preservation baseline. Of 399 baseline tracked file hashes, only the current assignments record differs; historical source, experiment records and labels remain unchanged. Final preservation must be checked again after execution.

| Frozen evidence | SHA256 |
| --- | --- |
| Readiness receipt | `8282d7bf6720e583591249a2a94bc3a8538fa56b31fcd5a2f44cb71dbd4087a9` |
| Source digest (33 files) | `fae3a85787a5df77003a8075e40ac89ae892309d8faeda838000dfc27fedc8dc` |
| Public manifest | `661b8afd12b17e66c84cdfdfa224158878e15d8093cc0c4eb1be9872a4b4a393` |
| Input contract | `3642344b244ed1d82c664b7c3812a3ee1b771b4e479e9de66fc79f77e90b90de` |
| Owner 11-test log | `fa9c724611e12c859948dfaa0e0859bbc41eb7670065ec8e1ddb108ec2f6b9c5` |
| Owner 14-test queue log | `19485fb2bef3c5b14fbff43ba5705a49be32669b9e91c909143073bf5916d6f1` |
| Reviewer six-test log | `a2f5db5ad7ad4d84b8ebeeb0e302356490b7145195810aeea1fe9eb2c6545bfb` |

All current source bytes match this freeze. An extra EOF blank line was removed from the new observer before this final binding; its class AST and all other source/input/test evidence remain unchanged.

The coordinator supplied Git-object/current-file proof for source commit `ecc8a55a68b806c7876b480b52a9b69b3e3aa85f`. Its 33-file map and digest match this independently reviewed freeze; the reviewer performed no Git action.

## CPU and source findings

The new kwargs dict is a deep copy of the historical 22-argument public contract, with only `imgsz` changed from 640 to 960. The nested class list is also independent. Model/checkpoint, Ultralytics 8.4.192, CUDA0, FP32 (`quantize=None`), rectFalse, batch1, conf0.25, classes[0], nmsFalse, max_det300 and all other public options remain the same. The installed official API/signature audit checks the downstream path and exercises official preprocessing on a synthetic CPU crop, yielding float32 1×3×960×960 without constructing a model or initializing CUDA.

The new observer class retains the historical official-body profiler exactly except for the 640→960 tensor-shape assertion and error text. It observes the unwrapped official methods and records sample network attempts/completions separately from warmup. It rejects a real preprocess tensor unless it is CUDA0 float32 1×3×960×960. Synthetic tests exercise both accepted 960 and rejected 640 shapes; actual GPU shape remains an execution-time requirement.

Fixed source RGB is cropped with unchanged batch05 geometry to 648×903×3, then converted to contiguous BGR by the unchanged batch04 utility. Native crop Results are parsed before exactly one (+537,+216) translation. Low-confidence, out-of-bounds and (0,0) unknowns preserve their status; empty Results remain normal, malformed/nonfinite Results are rejected, and all returned person rows are preserved. Cached 640 rows already in original coordinates are drawn directly, with no second offset. The triptych renderer iterates all rows, uses varied box/skeleton colors, and includes each row's score and retained estimate count in its header.

The sole new queue stage has exactly three ordered conditions: 90, 84 and 94 seconds at C6/960. No empty-result early exit, 640 call, alternative ROI, threshold sweep, rule, tracker or automatic retry is present. One model construction precedes the three public calls; official first warmup is separate. Partial-start markers and native Results prevent regeneration. The runner verifies canonical inherited lock/inode, exact live parent and child, Run/Task/Dispatch, committed source/input/config hashes, fixed interpreter, and free VRAM≥6144 MiB before model construction. Errors stop the run, with partial observations retained; network/DNS transport is denied.

The owner recorded eleven CPU contract tests. The reviewer separately ran six selected synthetic tests, all passing, covering public signatures/960 preprocessing, the new observer assertion, offset/unknown handling, empty/malformed Results and all-row triptychs. These are overlapping contract checks, not new sample predictions. The reviewer independently matched stored RGB file hashes and the input-contract digest, but did not repeat source-image decoding, crop-byte calculation or the full installed-environment scan; those are covered by the owner's frozen CPU preflight. Historical native Results/tensors/images are verified as bytes, not opened or deserialized.

The queue extension registers the new command and preserves the existing lease/retry protocol. At this pre-execution checkpoint all 41 historical jobs and attempts still match the baseline; the only previously tracked changes are the additive queue source and the current assignments record. Old batch04/batch05 sources, outputs, reviews and labels remain unchanged. The public manifest contains aggregate limits and provenance hashes, while source paths, raw manifest, Results, tensors and images remain local.

## Quality boundary before the new user response

The prior EXP-0024 user review describes 84-second C6 boxes/joints as generally good, 90-second detection of only the rightmost of three climbing people with misaligned joints, and 94-second omission of both visible people. Those historical observations cannot validate new 960 output rows or joints. New bbox/body/wrist/hip/knee/ankle correspondence, occlusion, duplicates and ROI truncation require one bundled local user review of the three comparison images.

The three PTS belong to one development scene, not an independent camera or temporal-stability test. Output counts do not establish recovery, pose accuracy, behavior improvement or legal/completion judgments. Formal behavior metrics remain null; default adoption, tracking, rules, VLM combination, full-video processing and additional automatic experiments remain held.

## Actual execution audit before the new user response

**Technical execution PASS.** The sole new attempt `dbc34eb78e324d79a725925f48f4783c` used reviewed source commit `ecc8a55a68b806c7876b480b52a9b69b3e3aa85f` and the exact source/input/config and coordinator authorization. The saved summary SHA256 is `e1b2c56fa82aa77b3b7b27946a5434b865c7c3f8b882b07680f9f41787e5d994`. The authorization binds the independent local preflight receipt; the non-synthetic queue receipt records matching parent/child identities, success and exit code zero. The actual pre-load resource gate recorded 8172 MiB free, above the unchanged 6144 MiB requirement.

The run has one model construction, three public predictions and three completed sample forwards, plus one separately observed warmup forward. Error/retry counts are zero. There are exactly three start markers and three saved native Results in the approved order 90→84→94 seconds. The normal empty 90-second return did not prevent 84/94 processing. No new 640 inference exists. Canonical totals are now 42 jobs and 42 attempts; all 41 historical jobs and 41 attempts match the pre-run baseline.

| Native time | C6 640 cached rows / retained estimates | C6 960 new rows / retained estimates | Supported interpretation |
| --- | ---: | ---: | --- |
| 84 s | 3 / 38 | 3 / 37 | Same output-row count; new anatomical quality unreviewed |
| 90 s | 1 / 12 | 0 / 0 | Normal empty output where the user previously observed three people; no missed-person reduction |
| 94 s | 0 / 0 | 1 / 11 | New estimates exist; actual person and joint correspondence unconfirmed |

These are numeric outputs, not verified people or correct joints. The 90-second loss and 94-second new row do not support an overall improvement claim. At 84 seconds, three rows and a one-estimate difference do not establish preserved anatomical quality. At 94 seconds, neither identity among the two user-observed people nor correct wrist/hip/knee/ankle placement is known. The coordinator reports one bundled local image-review request; its unanswered status is not an approval or quality result.

All three observed input tensors are CUDA0 float32 1×3×960×960. Backend metadata records native PyTorch, end-to-end, fused, FP32, 17×3 keypoints and completed warmup. Saved observer event files agree with summary events and separate sample/warmup counts. Twelve new artifact hashes match: nine native Results/tensor/event files and three triptychs. The nine cached artifact hashes remain unchanged. No artifact was decoded or viewed by the reviewer. Saved local-to-original JSON arithmetic independently verifies one translation for all 68 joint entries and preservation of all 20 unknown statuses; this checks coordinate plumbing, not anatomy.

Constructor/checkpoint CPU loading took 0.243591 s; first official predictor setup 0.381986 s; official warmup 0.423834 s; run-entry interval 11.341878 s; canonical queue attempt 17.478248 s. Public call walls in execution order were 0.898043, 0.054531 and 0.038730 s. These scopes overlap and must not be added. First-call setup/fuse/warmup, profiler/synchronization and local tensor capture affect the measured intervals; three instrumented calls are not a deployment FPS benchmark. Cached 640 costs remain explicitly charged to historical EXP-0023, with zero new 640 inference cost; its five-call whole-run cost is not directly comparable to this three-call run.

Allocator peaks after reset were 308,564,992 allocated and 387,973,120 reserved bytes. Fourteen device-wide samples agree with their aggregate maximum 2538 MiB used and minimum 7516 MiB free; there were no sampler errors. Device samples include other processes and are distinct from PyTorch allocator peaks and the pre-load gate.

All 47 public metric entries resolve to their hash-bound sources and agree with saved counts/costs; five formal behavior metrics remain null with zero evaluated samples. The public extraction builder was source-reviewed without executing its real-input decoding or writes. All 129 protected historical source/experiment/report/review/record files checked after execution match the coordinator baseline. The 33 frozen execution files remain identical. Final report, coordinator conclusion and publication-byte binding remain pending.


## Subsequent user qualitative review

After the initial technical audit, the coordinator relayed the user's review of the new right-hand 960 panels: **84 seconds looks good; 90 seconds is at the previous experiment's level; at 94 seconds the person on the gate is detected and looks surprisingly good, while the already-across person remains missed.** This is user-provided qualitative correspondence evidence, not an agent pixel review or a precise per-joint ground-truth annotation. The prior unanswered/unknown statements above describe the earlier audit checkpoint; this subsequent evidence updates that quality status without changing model outputs or historical reports.

The 94-second new row may now be attributed qualitatively to the person on the gate, with a positive user judgment of the visible pose. The other visible person remains missed. The 84-second user judgment is positive but does not establish exact wrist/hip/knee/ankle errors or temporal stability. The user's 90-second “same level” assessment describes continued inadequate useful pose evidence: saved 640 output remains 1 row/12 estimates and new 960 remains 0/0. It is not identical numeric output and cannot create a new detection or joint estimate.

This supports a limited qualitative gain for the on-gate person at 94 seconds, alongside continued omissions and the loss of the previous 90-second output. It does not establish overall improvement, precise pose accuracy, behavior performance, generalization or default adoption. No further inference accompanies this user review. Final owner-report/metrics and coordinator-summary bindings must include these new observations before final acceptance.


## Final acceptance and exact byte binding

**Final acceptance PASS for completed technical execution, faithful user-informed reporting and preservation.** The final owner report, metrics/comparison, ADR and coordinator conclusion correctly incorporate the user's qualitative 84/94 judgments and the continued 90/94 omissions. They preserve all raw output counts, distinguish qualitative correspondence from individual-joint accuracy, and keep behavior performance and default adoption on hold. The earlier pending/unknown statements above are historical checkpoints, superseded only to the limited extent of the subsequent user review.

The final 47 metric entries were rechecked against their current source hashes and pointers. Five formal behavior metrics remain null. The zero-new-640 metric has value 0 over three cached conditions; its sample count was corrected to 3 for the existing measured-value schema, without changing predictions or costs. The user-review summary is separately hash-bound, and the changed public builder remains outside the frozen inference source. No new model call or GPU job was introduced by reporting or user-review updates.

All 33 frozen execution source files, the 41 prior jobs/attempts and 129 protected historical files remain unchanged at final acceptance. Queue totals remain 42/42. Accepted public artifacts contain code, non-identifying diagnostics, provenance hashes and limitations; no raw person-coordinate arrays, media/tensor payload, checkpoint, actual local absolute path or credential content was found. The builder's coordinate field names are source code, not coordinate data. The reviewer did not view the local images. This is separate from the coordinator's staging, actual browser rendering and remote-byte checks.

| Accepted artifact | SHA256 |
| --- | --- |
| EXP-0025 report | `80ee4f04a8569f6121864496b1d683c7dcef650fb929943d3fce506f2f6ed0ab` |
| Metrics | `7eaa71f84d54d6b4bcd5f06bd997a465f9e74756d9df3754359a8dc3326db7f5` |
| Comparison | `c3a08068419846ca3fca6f608697abe1dce1a73b5dd62e837bb3dee6061dc5e7` |
| Costs | `6f257b5948436e5accdff3eda310ac6f09d735e29c63d60bcfaeec7e0639b1ef` |
| Coordinator conclusion | `36466ce9d9abde75cbb6d9126b208738248b866ad7b52fd24efd28c4555e38cd` |
| ADR-0023 | `f4e30eb077d92edc7dcb4c0743751a9e881c0c4eaf63335d479851b207c90bd0` |
| Public CPU extraction builder | `6c603b7f9aa157439205cf3044cfc5d3545d4cfc7f92384859e131e2fd469989` |
| Local user-review summary (content stays local) | `3f8961fe8da2b4d8568550195472a90b50088f10059655118bb11d837353b1a1` |

Any change to accepted public bytes requires renewed binding review. The next decision is whether evidence is sufficient to expand pose-based behavior judgment; the present evidence supports keeping that expansion and default adoption on hold. The already received three-image user review need not be requested again. No new resolution/model/threshold/ROI/tracking/rule experiment or GPU work is authorized by this review.

The coordinator owns completion registration, actual rendering of the three still images and final GitHub remote-byte verification. Still-image evidence has no video playback/seek claim. This review does not substitute for those delivery checks or claim operational accuracy.
