# EXP-0021 — independent BATCH-0003 review

2026-10-29. **Final verdict: PASS for faithful failure reporting and preservation; technical execution FAILED and the core pose-evaluation objective was not achieved.** The one logical retry is exhausted, with zero completed predictions. No third attempt or remaining-frame execution is authorized. Person/joint correctness and behavior were not measured; rule/tracker stages were not run. This review does not establish browser/GitHub delivery completion.

## Scope and provenance

The reviewer read the project charter, work plan, current instructions, complete BATCH-0003 plan, EXP-0019/0020 comparison constraints, relevant boundary/model ADRs and existing camera configuration. No media was viewed or decoded; no model was constructed; no GPU, installation, queue mutation, Git action or helper was used.

Saved native launch receipts identify Run `run_3d23462a014a`, reviewer Task `task_92d8e7d273a0` / Dispatch `ctx_197b8cccbac5`, requested/effective `gpt-6-astra` / `high`, ready/input-accepted with observed turn start. Execution launch receipt identifies Task `task_7c8a851c6d27` / Dispatch `ctx_b15556efe8cd`, requested/effective `gpt-6.1-sol` / `high`. The saved preflight native worker observations corroborate these exact active dispatches and provider models with fresh/live status. Effort is evidenced by the launch receipts; a stale first launch is not substituted for the active execution dispatch.

## Independent official-source checks

Direct official metadata retrieval confirmed the following (installed bytes remain a separate check):

| Item | Official identity |
| --- | --- |
| Ultralytics package | `8.4.192`, Python requirement `>=3.8` |
| Annotated tag | `v8.4.192`, tag object `8474632b76a0edda1855e9702215272c6a418cb7` |
| Tag target commit | `922563eab42b778445e55a2edbabb6974eed8e4b` |
| Wheel SHA256 | `ebca69963cdd07e5a197a25dd04f8db9a685f947143b8defefc75c868bdfdb4d` |
| Sole checkpoint | official assets release `v8.4.0`, `yolo26m-pose.pt`, 49,036,866 bytes |
| Official checkpoint SHA256 | `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4` |
| Tag LICENSE SHA256 | `0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0` |

Sources: [tag object](https://api.github.com/repos/ultralytics/ultralytics/git/tags/8474632b76a0edda1855e9702215272c6a418cb7), [version-specific PyPI metadata](https://pypi.org/pypi/ultralytics/8.4.192/json), [official assets metadata](https://api.github.com/repos/ultralytics/assets/releases/tags/v8.4.0), [pinned license](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/LICENSE). The annotated tag is unsigned; an official-host SHA match is provenance/integrity evidence, not a cryptographic author-signature claim.

The official pose documentation describes COCO keypoints and a 640-input YOLO26m-pose benchmark; those dataset benchmarks do not establish performance on this CCTV. The exact implementation, including end-to-end output filtering, must be checked against the pinned package rather than assumed from a generic YOLO/NMS description. [Official pose task](https://docs.ultralytics.com/tasks/pose/).

The license is AGPL-3.0. Local evaluation does not erase copyleft obligations: any publication of a covered combined/derivative implementation needs compatible licensing and corresponding-source treatment; later network/product use requires a separate scope/license decision. The license's section 2 distinguishes running a program and its outputs from conveying a covered work; section 13 adds requirements for modified network-interactive software. Raw CCTV/coordinates are not automatically publishable because software is open source. Ultralytics also offers Enterprise licensing and states broad disclosure expectations for its AGPL option. This review authorizes no payment or commercial integration. [Pinned license](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/LICENSE), [publisher licensing guidance](https://www.ultralytics.com/license).

The referenced fence-rule repository's visible root listing offers no LICENSE entry. Its README is an idea reference only, not permission to copy its implementation; no third-party implementation was fetched or copied. [Reference repository](https://github.com/Khushnoor-gojwari/Fence_detection_wall_and_iron_fence).

## Rule-entry prerequisites recorded before pose outputs

The existing C3/C6 `legacy_boundary_config.line` and ROI are manually selected, fixed development crossing geometry. The camera-level `calibrated: true` marks that existing setup; it does **not** establish fence-top height, contact surface, ground plane, near/far side, or physical crossing completion. ADR-0005/0006 explicitly separate line-side candidates from physically climbing a fence. C1 has no calibrated boundary. In particular, `rope004` cannot inherit C3/C6 geometry or become a main fence-climb positive.

The following are conjunctive prerequisites, not findings that the new pose model has met them:

1. A local human must identify the relevant person and verify original-versus-overlay correspondence at the fixed diagnostic frames and in the continuous windows. Assess wrists, hips, knees and ankles separately, including left/right swaps, occlusion, partial bodies, duplicates and background false detections. Counts or confidence alone cannot certify this.
2. Any geometric predicate must have a human-confirmed meaning for its existing fixed boundary: which physical feature it represents, which side is which, and whether the claimed limb/contact relationship is visible. A crossing line cannot silently become fence-top or ground-height geometry. If those facts cannot be established from the authorized existing geometry, skip the rule stage; new calibrated geometry would require a separately recorded decision before application.
3. Temporal evidence must retain original native PTS and per-frame detection identity. Within-frame bbox/keypoint indexing is not a persistent person ID. Across-frame association must be independently justified; ambiguous overlap, ID discontinuity, missing required joints or implausible jumps yield **unknown**, never a bridge using another person's joints. No predicted/interpolated joints count as observations.
4. Fix the diagnostic confidence policy before results, retaining raw values and distinguishing confidence eligibility from actual visibility. Missing confidence, low confidence and sentinel `(0,0)` are unknown; a finite or high-confidence coordinate can still be wrong. A missing person/joint cannot be scored as a normal non-attempt.
5. Before any rule is evaluated, preregister one rule's required joint indices, geometry, relative-distance normalization, persistence duration/count, maximum admissible gap and unknown behavior, with one fixed association policy if needed. It must require temporally sustained same-person evidence beyond approach/contact. Two-dimensional hip movement is only a body-position proxy, not measured weight transfer. No output-dependent parameter sweep or post-hoc threshold adjustment is permitted.
6. Compare the fixed approach and attempt windows without treating their window-level references as person-level ground truth. Keep rope crossing separate, and do not infer attempt/completion/legal entry from skeletons. Accuracy/F1/FPR, per-person completion and generalization remain unavailable.

**Current rule-stage judgment: prerequisites unestablished; do not start it.** This can coexist with a future technical preflight PASS for the bounded pose-only stage. If physical correctness remains unconfirmed after execution, provide one compact local human-review bundle: the eleven original/overlay comparisons and the five fixed-window original/overlay sequences, with a short person/joint/geometry checklist. Reuse existing output; do not request another model run or repeat earlier window-label questions.

## Preflight evidence and acceptance history

Independent CPU checks now completed: **seven synthetic tests passed** against the frozen source with CUDA hidden and uninitialized, no model construction, no media, and no queue/Git actions. They test per-row correspondence/unknowns, malformed pose outputs, exact native-PTS spacing, the 6144 MiB gate/direct-lease rejection, official square LetterBox/color/coordinate mapping and strict end-to-end confidence filtering with overlap/index preservation. Five adversarial membership/parity mutations are rejected, and the two smoke frames plus 265 remaining frames form a disjoint complete set. Independently fetched pinned `nms`, `ops`, `augment`, `tasks`, `head` and engine `model` source bytes match the installed package; the local checkpoint's full size/hash matches the official digest above. The separate implementation test log reports 68 tests run, 67 passed and one skipped; its readiness prose saying 68 passed is imprecise.

The first available manifest contains **267 unique frames**: 260 window samples (60/50/50/50/50) plus the eleven diagnostics, with four overlapping diagnostics reused. All eleven native PTS/time-base/source/RGB bindings match EXP-0019 exactly; all five window memberships, sources, half-open bounds and 0.1-second minimum spacing pass independent metadata checks. This initial inspection does not replace the later frozen-manifest hash acceptance.

The reported interpreter blocker was fixed using a copied isolated executable, retaining path containment rather than relaxing it. The complete smoke input contract now verifies **302 pinned entries and the 18,783-file installed environment index**. Draft membership weaknesses were fixed with unique IDs, source identity, exact diagnostic parity, membership completeness and the initial frame-binding hash. Timing now starts before lease validation, records initial validation separately and names the measured interval `run_entry_wall_seconds`; Python startup and queue overhead remain outside it.

The preservation check matches all 3,000 recorded file sizes/mtimes and 2,819 recorded file hashes, plus the 75 initial public configuration/report/record hashes. All five old environments have matching normalized package-version inventories. Those inventories are evidence of their recorded scope, not a claim that every old environment byte was independently hashed. A read-only `pip freeze` attempt found no pip in the pre-existing VLM environment; standard-library distribution metadata provided the comparison without installation or environment changes.

Frozen preflight bindings:

| Evidence | SHA256 / identity |
| --- | --- |
| Readiness receipt | `96aa3833da911e5bd2e7dd33584cd0399bc5ad0fc562d1cb8bb8b32390fa6f6e` |
| Source digest, 13 files | `1096a4f9c6322a6e7da7f3f6fa204a54fc6b3f095ff618156453e431a8f339e0` |
| Final manifest | `6ea2fe8d692611f7808b1109a591fedff9cd8c901f13cc43474246324927883d` |
| Frame binding | `3a580c51544b4781b69523684b79ec5d9e2eab3317f5a2d91fd737dacb78edd5` |
| Requirements lock | `66882e94f9b144ea48c69ec477a216e88a2cbb87a2daff9459ae8f68e5f599a9` |
| Coordinator-reported source commit | `b52ac221a2e43924f86efd8fbd32a0df4973ceec` |

All source/environment/document hashes listed in the readiness receipt match local bytes. Git actions are outside this reviewer's task; commit-byte verification belongs to the coordinator and is not implied by the local source-digest check. **Preflight PASS is limited to this frozen pose-only contract**, conditional on that committed-source/authorization binding and the live resource/lease checks. It does not pass the human-pose/geometry gate or end this review task.

The coordinator was asked for the exact ready code/test, manifest/ADR, environment/package/weight inventory, preservation, lease/budget and role-provenance evidence paths, and to hold model construction/execution pending a specific preflight verdict. The implementation was not yet present at initial inspection; the later frozen evidence and bounded authorizations are recorded above and below.

The preflight checklist covered exact eleven-frame native PTS parity plus five fixed windows, at most 300 unique frames and at most 10fps; two specified smoke observations followed by their set complement without regeneration; full-frame 640/FP32/conf0.25, end-to-end/filter/padding/coordinate contract; canonical queue and live lease/parent/child lineage; free VRAM at least 6144 MiB before construction; one isolated environment/one checkpoint; bounded retries and immutable successful outputs; preservation of old environments/results; no label/prior leakage to inference. Model entry-point compatibility was inadequately covered, as the actual failures demonstrate.

Final failure acceptance additionally checked actual execution receipts, failure-artifact integrity, measured costs with scopes, CPU synthetic tests, explicit visual/rule limitations, preservation, private/public separation, final report/metrics hashes and the coordinator's conclusion. Registration, actual local browser playback/seek and GitHub remote byte verification belong to the coordinator and cannot be inferred from this review or from code alone.

## Actual smoke failure and correction review

Attempt `152d45f0113f4c94b44c69961a677023` passed the 6144 MiB resource gate with **7172 MiB free** and loaded the sole checkpoint in **0.347499 s**, then failed the architecture/end-to-end assertion. It has zero completed forwards, zero saved frame outputs and no inference-started marker. This is a real post-load adapter failure, not a pre-model failure and not an OOM. Initial preflight tests did not catch the checkpoint's legacy head-selection state; record that limitation rather than treating preflight PASS as an execution success.

The saved static ZIP/pickletools diagnosis reports legacy `end2end=True`, no `_end2end` field, existing one-to-one modules, COCO person names, 17×3 keypoint shape and strides 8/16/32. The original failed summary did not record each runtime architecture field, so its exact failing boolean was not directly observed. Independent pinned source inspection confirms the current getter defaults `_end2end` to false when both branches remain; the official predictor passes an explicit end-to-end override and `PyTorchBackend.load_model` applies `model.end2end = self.end2end_override` before optional fusion. That setter delegates to the head. This supports the proposed omission diagnosis without another checkpoint load by the reviewer. [Pinned PyTorch backend](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/ultralytics/nn/backends/pytorch.py), [pinned head](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/ultralytics/nn/modules/head.py).

The accepted minimal correction applies the **already registered** `end2end=True` through that official setter, sets the already registered `max_det=300`/`agnostic_nms=False`, retains unfused FP32 and unchanged input/model/settings hashes, and logs architecture before/after before any forward. The exact new job key is `batch0003-exp0021-pose-smoke-retry1`, with unchanged stage `smoke`: logical smoke attempt 2, new queue job attempt 1. Original and correction jobs reject ordinary retry; the correction guard binds the original failed summary, zero-forward state, code/source and queue lineage, allows at most two logical smoke attempts, and the remaining stage requires an exact successful smoke under the corrected source. Any started forward blocks regeneration.

**Correction preflight PASS:** readiness SHA256 `9cf61775c58c4b2819d403b6e69fe2d81570a264620a489f8eab0135b7a287ad`, source digest `7bd780ab2a7b59f011865042fd478a64e5a217a588c0b86bdb4d4597bc753c6a`, coordinator-reported commit `1b12d85c20ba922de5062148045281849055ef9e`. The original manifest remains `6ea2fe8d692611f7808b1109a591fedff9cd8c901f13cc43474246324927883d`, all 302 input pins/environment index verify again, and all 38 old jobs/38 old attempts exactly match the reviewer's pre-retry snapshot. The failed summary SHA256 is `593ebd605f6555dba9f426b81d6499878e03a8adfad0686ea5602bd3cb33eadb`.

Nine independent CPU tests pass, adding legacy-state head selection without a model and rejection of third attempts/changed original lineage. The implementation log reports 70 run/69 passed/one existing skip. One intermediate reviewer-test error used an obsolete transient draft key (`smoke-correction1`); the fixture was aligned with the final frozen `smoke-retry1` key and its failed log preserved. No production guard was weakened to pass it. At that checkpoint retry execution still required the coordinator's corrected commit-byte/authorization binding and unchanged live resource/lease gates; that preflight PASS did not establish corrected GPU success.

## Retry exhausted: actual failure outcome

The coordinator's corrected commit-byte receipt matches all 13 reviewed source files and commit `1b12d85c20ba922de5062148045281849055ef9e`; its saved authorization binds the same source and exact retry key. Retry attempt `070b7d4885154095bb84299b8f5916b8` passed the gate with **7169 MiB free**, loaded the model in **0.368981 s**, and recorded end-to-end state changing from false to true with the existing one-to-one branch present, COCO17×3 and stride 32. This corroborates the initial head-selection omission without rewriting the first attempt's missing runtime diagnostics.

The corrected attempt then failed at its first call with `TypeError: BaseModel.predict() got an unexpected keyword argument 'visualize'`. Pinned `BaseModel.forward` forwards keyword arguments into `predict(self, x, profile=False, augment=False, embed=None)`, which has no `visualize` argument; the direct runner supplied `visualize=False`. The traceback shows rejection at Python argument binding before `predict` enters the network. This is a second adapter-contract error. The forward-start marker exists, but the completed-forward count and saved prediction count are both zero. GPU checkpoint loading and input preprocessing did occur: do not describe the run as having no CUDA work. [Pinned inference entry point](https://github.com/ultralytics/ultralytics/blob/922563eab42b778445e55a2edbabb6974eed8e4b/ultralytics/nn/tasks.py).

The reviewer’s earlier source inspection and synthetic tests did not exercise the complete direct-call signature and missed this incompatibility before execution. Their PASS established only the checked conditions; it did not certify end-to-end compatibility. Preserve that review/test coverage gap together with both runtime failures. No source fix, checkpoint load or third attempt was made by the reviewer.

The canonical queue contains **39 jobs/39 attempts**, including exactly two failed EXP-0021 smoke jobs (one initial attempt, one logical retry). Each new job has native attempt number 1; that does not reset the logical retry budget. There is no remaining-stage job. All 38 previous jobs and 38 previous attempts match the independent pre-retry snapshot exactly. The failed summaries remain SHA256 `593ebd605f6555dba9f426b81d6499878e03a8adfad0686ea5602bd3cb33eadb` and `2acff1ceae9d44e1ad2cc7acfb90ee3ffea25375ec22926963d9a04ed682ccf8`. The corrected source digest remains unchanged.

| Measured scope | Initial smoke | Logical retry |
| --- | ---: | ---: |
| Initial validation, seconds | 3.801766 | 3.732527 |
| Model construction/load, seconds | 0.347499 | 0.368981 |
| Run-entry interval, seconds | 5.162014 | 5.193570 |
| Queue-attempt interval, seconds | 9.210638 | 9.182453 |
| Completed predictions | 0 | 0 |

Run-entry time begins before lease/input validation and excludes Python startup and supervisor overhead. Queue time includes that additional overhead; none of these intervals is measured successful inference latency or throughput. Load allocator peaks and device-wide samples are different scopes. With zero predictions there is **no inference FPS, person/joint coverage, visual-quality result or behavior comparison** to report. The prepared 267-frame manifest is an input inventory, not a completed evaluation denominator.

**Failure closure is the required outcome:** preserve both errors and measured costs, stop GPU work, keep adoption held and state that the experiment's core pose question was not answered. This is implementation failure, not demonstrated failure of YOLO26m-Pose's physical joint accuracy. Human pose review is unnecessary now because no pose overlay exists; any delivered videos must be explicitly original-input references. The earlier one-bundle proposal applies only if a separately authorized future run produces actual pose output. It is not a request to inspect nonexistent overlays or relabel the same windows now.

## Final publication acceptance and byte binding

The final [experiment report](../experiments/EXP-0021-yolo26m-pose.md), [coordinator conclusion](../experiments/BATCH-0003-summary.md), [comparison](../../records/EXP-0021/comparison.json), [costs](../../records/EXP-0021/costs.json) and [metrics](../../records/EXP-0021/metrics.json) faithfully state the two adapter failures and incomplete evaluation. A draft scope incorrectly called these failed model loads; this was corrected to failed smoke attempts with completed model loads before the hashes below were accepted. The final conclusion attributes the errors to implementation and preflight coverage, does not condemn the model's unmeasured quality, and keeps future work outside this exhausted batch.

All **16 measured metric pointers** resolve to matching hash-bound comparison values, independently checked against both raw failure summaries and canonical attempt timestamps. All **six unavailable metric entries** remain null with sample count zero; window bbox/joint counts, person quality and inference FPS are also unavailable. Model-load totals and queue totals reproduce the recorded measurements. A separate AST-only check confirms `visualize` is the sole unsupported keyword among the actual call's `augment`, `visualize`, `embed`; it constructs/imports no model. The two non-synthetic canonical receipts match saved registration and recorded supervisor/child identities, with exit code 1 for each attempt.

Final preservation checks again passed for the 3,000 recorded file metadata entries, 2,819 recorded hashes, 75 initial public hashes and all 38 pre-retry jobs/38 attempts. The corrected inference source remains frozen. Only safe code, architecture/configuration information, aggregate preparation/failure measurements and interpretation appear in the reviewed publication files; they contain no person coordinates, raw arrays, image/video payloads, weights or credentials. `.venv-pose-batch03`, model/media/output and runtime exclusions remain in force. This is a content-boundary review, not a claim about Git staging or remote publication performed by this reviewer.

The two local reference-media file hashes match their local index: a newly encoded original-only 030 window and the preserved original q04 reference. The index explicitly says no pose output. This reviewer did not decode/view those files; the producer's saved 60-frame PTS check and the coordinator's later actual browser playback/seek are separate evidence. No pose overlay or human pose-validation claim is accepted.

| Accepted artifact | SHA256 |
| --- | --- |
| EXP-0021 report | `a64b18fd230d318504d580c6fe4f4ff584edce151fb17c98efd0f931a917f482` |
| Metrics | `fff6e18af58434efb77fcf110cdb00b51b64d07b8e34c496b9b12cb6a2945e61` |
| Comparison | `01d836c21f3d1a99e47402bcc264e1ca08a822fabd6c7a0e054efb82b5377af5` |
| Costs | `b1c31f6ea37c285e29a159bdb069db3b76e089480cffe0b6e226f236edf611b4` |
| Coordinator conclusion | `1eeca829a461f2a4e50cfa852d118e2fbee97078fe4323a25bf2735ee9d28b4d` |
| ADR-0020 final state | `c9a4b367250a7c7d6f9b100f41615a5f7a395b65c167dbfe74f11df66a69f68b` |
| CPU failure builder | `85c6edede495971d7f0c0e64f926bf18ad0585ca2732a1d56162f28393afb57e` |
| Local final delivery index | `6c73b7b8ee1b36f7ae6a6cbd3aedab212c06c80eed4f5bbeb1cf677ac534918a` |

These exact bytes are accepted for **failure reporting**, with adoption held and no further GPU work. Changing a bound report/metric/conclusion requires a new binding review. The coordinator still owns result registration, actual local browser/media verification and GitHub remote-byte verification; technical failure remains failure even when those delivery tasks complete.
