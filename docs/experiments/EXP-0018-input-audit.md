# EXP-0018 — BATCH-0002 CPU input-sufficiency audit

2026-10-29 KST. **Saved-input provenance and geometry audit completed; actual sampled-input action sufficiency remains unknown pending one small human check.** No new model inference or behavior-performance estimate was made. The coordinator owns the final stage gate, independent review, delivery, and latest project documents.

The audit uses the [BATCH-0002 plan](BATCH-0002-model-upgrade-plan.md), [EXP-0015 original-clip user references](EXP-0015-user-label-revision.md), [EXP-0017 saved inputs](EXP-0017-execution.md), and [EXP-0002](EXP-0002-fcos-detector-comparison.md)/[EXP-0003](EXP-0003-fcos-candidate-diagnostics.md) diagnostic records. Implementation/config/tests were committed by the coordinator as `3e9a6bb415e175106b9deac55a58cfc465e26eae` before any actual source decoding or audit artifact generation. Native Task `task_806f089dde4f`, Dispatch `ctx_f0c0eef8ed14`; the worker did not commit or push.

## Subsequent user input review and coordinator gate

After the CPU audit snapshot, the user reviewed the three generated local clips and reported: q04 shows holding the gate and raising a foot; v01 shows crossing the rope/line and standing on the opposite side; v03 ends while stepping/climbing onto a rock beside the gate. The exact text is preserved separately in [the new input-review record](../../configs/batch0002_user_input_review.json). This is user-provided visual evidence, not an agent viewing media or a model-generated label. The immutable CPU JSON below remains the pre-answer metadata snapshot.

These observations support a **conditional go for the frozen new VLM comparison**, because q04/v01 retain relevant movement cues. They do not prove every view adequate: the user did not distinguish q04 B versus C, give exact-frame/person annotations, or confirm boundary crossing in v03. The v01 opposite-side observation supplies a new limited completion reference for this reviewed input; prior EXP-0016/17 completion-unassessed records remain untouched. The older v03 attempt reference and this narrower rock-ascent observation are reported separately; rock ascent alone cannot establish boundary crossing. No source frames/ROI/prompt or candidate outputs were tuned using this reply. Native CV diagnostics can proceed on their own prior evidence as described below. No integration/adoption decision follows from the input gate.

## Purpose and evidence boundary

The question is whether the **exact actual sampled and resized inputs** contain enough visible body/boundary motion to distinguish attempt/progress from approach. Matching labels, pixels, PTS, resolution, candidate counts, or a working decoder alone cannot answer that semantic question. This audit measures input provenance, temporal coverage, crop/resize geometry, token metadata, and limited prior-location projections. It does not view media through image tools, ask a VLM, identify people, infer actions, or turn model boxes into ground truth.

Prior user labels describe original 5-second review clips. They remain valid at their original scope and do not establish that all essential cues survive 2fps and resizing. q04 remains attempt/progress with completion not observed before clip end; v01/v03 remain attempt/progress with completion not assessed. v03 is the gap beside the gate, with ambiguous boundary association. q06's no-person/no-event label applies only to 030:155–160, and no 031 observation is transferred to 030.

## Measured input coverage

The [public audit JSON](../../records/EXP-0018/input_audit.json) records all source/input/cached-RGB hashes and an explicit selected-source-frame inventory, using public-safe aliases and numerical metadata. Absolute paths, raw media, and local receipts remain ignored.

| Audit item | Measured result | Boundary |
| --- | --- | --- |
| Scheduled windows | All ten q01–q06/v01–v04 | Selected development/diagnostic material across four sources, not an independent test |
| Actual saved processor variants | 20: q B/C ×6, v original/revised ×4 | 200 frame observations; paired observations are not independent source frames |
| Selected native source RGB frames | 103 unique: 100 q/v samples plus 030:84/90/94 | 007:64/66 reuse q04 samples; inventory deduplicates source/native PTS/time base |
| Source and crop checks | All 20 variants match recorded source RGB and crop hashes after exact-PTS decode | Source files also match frozen SHA; no processor transforms or hidden tensors recomputed |
| Pair checks | q B/C source samples equal; v original/revised source and saved processor NPY bytes equal | q B/C are intentionally different spatial views |
| Historical q processor pixels | Unavailable for all 12 earlier B/C records | Historical source/native PTS/RGB and recorded visual metadata match; actual historical processor-pixel equality is unestablished |
| Diagnostics | Exact original 030:84/90/94 and 007:64/66 | Historical 030 processor RGB absent; no reconstructed pixels presented as actual |
| Later CV comparison frames executed | 0 | The later 240-frame CV comparison cap is a separate stage |

The decoder traversed **11,143 frames including repeated seek preroll** to reach the selected native PTS. Those intermediate frames were not RGB-converted, selected, or exported. This number is not a unique comparison-frame inventory or a throughput measurement.

Every q/v input has ten actual observations spaced by 0.5s, with a first-to-last span of 4.5s and a 0.5s interval from last sample to the scheduled end. No extra sampling or temporal padding is recorded. Native integer PTS and rational time bases agree with seconds. The recorded processor uses two-frame temporal patches (five temporal groups) and timestamp captions from pair averaging and 0.1s rounding. This establishes temporal representation metadata; it does not prove that an essential motion fell between samples or survived them.

| Window | Original scheduled seconds | Actual sampled PTS range | Existing original-clip user reference |
| --- | --- | --- | --- |
| q01, 007 | 0–5 | 0–4.5 | No attempt/progress |
| q02, 007 | 47.5–52.5 | 47.5–52 | Approach only |
| q03, 007 | 52.5–57.5 | 52.5–57 | No attempt/progress |
| q04, 007 | 62.5–67.5 | 62.5–67 | Attempt/progress, completion not observed |
| q05, 030 | 50–55 | 50–54.5 | Approach only |
| q06, 030 | 155–160 | 155–159.5 | No person/event in this window |
| v01, 004 | 60–65 | 60–64.5 | Attempt/progress, completion not assessed |
| v02, 004 | 0–5 | 0–4.5 | Non-event |
| v03, 021 | 65–70 | 65–69.5 | Attempt/progress beside gate, boundary ambiguous |
| v04, 021 | 0–5 | 0–4.5 | Non-event |

## Spatial scale and ROI

Dimensions below are width × height. Crop bounds are checked against the recorded normalized ROI with outward floor/ceil rounding; saved NPY shape is checked against resize metadata and visual-token grid. Source/crop hashes are independently verified from selected original frames.

| Saved view | Source W×H | Crop W×H | Actual saved processor W×H | Original area retained | Visual tokens/window | Input tokens/window |
| --- | --- | --- | --- | ---: | ---: | ---: |
| q B, all six | 1920×1080 | 1920×1080 | 768×448 | 100% | 1680 | 2073 |
| q C, 007 q01–q04 | 1920×1080 | 576×648 | 544×608 | 18% | 1615 | 2008 |
| q C, 030 q05–q06 | 1920×1080 | 903×648 | 704×480 | 28.21875% | 1650 | 2043 |
| v01/v02, full-frame | 1280×720 | 1280×720 | 768×448 | 100% | 1680 | 1947 original / 2073 revised |
| v03/v04, full-frame | 1920×1080 | 1920×1080 | 768×448 | 100% | 1680 | 1947 original / 2073 revised |

These are measured dimensions and recorded token counts, not evidence that ROI preserves an action. The ROI views retain more processor pixels per original spatial unit inside their crops, while excluding other source areas; no q/v exact-sample human boxes exist to establish person coverage or exact person size. Those fields remain null for every q/v row. The original/revised v conditions have identical saved RGB despite different prompt/input-token counts; the failed revised prompt is not endorsed by this audit.

## Prior location ranges and native CV feasibility

The only coordinate locations used are EXP-0003's saved manual approximation at **030:84/90**: its author is explicitly “Codex visual approximation before candidate inspection, not user-provided boxes or ground truth,” in a 960×540 original-preview coordinate space. These approximate review rectangles are diagnostic spatial ranges. They are neither person GT boxes nor input crops, and no detector output coordinates supply the ranges.

Projected heights below use the exact historical 030 crop/resize metadata for windows containing the listed native instant. Historical processor RGB for those windows is absent, so these are **geometric projections of prior rectangles**, not measurements of an actual saved 030 processor image or visible body extent.

| Prior native instant / location | Source rectangle height | Full-frame B projected height | Fixed-ROI C projected height |
| --- | ---: | ---: | ---: |
| 030:84 left / rear-right / front | 170 / 180 / 220 px | 70.5 / 74.7 / 91.3 px | 125.9 / 133.3 / 163.0 px |
| 030:90 left / rear-middle / front-right | 190 / 160 / 180 px | 78.8 / 66.4 / 74.7 px | 140.7 / 118.5 / 133.3 px |

All six prior rectangles fall wholly inside the historical C6 crop. That proves retention of these approximate coordinate ranges only. It does not prove a person is fully visible or that climbing can be distinguished after resizing. There are no documented coordinate boxes at 030:94 or 007:64/66; size is unavailable there.

The prior user explicitly reviewed three approaching people at native 030:84 and three climbing people at native 030:90, as retained by the existing diagnostics and coordinator clarification. This run binds the exact source SHA/native PTS and provides RGB hashes for those instants. That existing native-frame evidence supports preparing a **tiny detector comparison at those exact native frames independently of the unresolved VLM input gate**. No new body-action observation, precise person boxes, completion label, detector success, or CV model adoption is claimed here.

## One small local human-check bundle

The generated local bundle contains exactly three five-second clips:

- `outputs/batch0002/input-audit/q04-source-versus-actual.mp4`: original sampled source, saved B, saved C.
- `outputs/batch0002/input-audit/v01-source-versus-actual.mp4`: original sampled source and saved full-frame original-prompt input.
- `outputs/batch0002/input-audit/v03-source-versus-actual.mp4`: original sampled source and saved full-frame original-prompt input.

Every panel uses the **same ten original native PTS at 2fps**. The source panel is sampled native RGB, not full-rate original-clip playback. The display is resized and encoded for local viewing only; it is not a new inference input or pixel-exact replacement for the separately hash-bound NPY arrays. Each frame displays original PTS, native PTS/time base, dimensions, and known sampling. All three exported clips were decoded for metadata verification: ten frames, timestamps 0–4.5 in 0.5s steps, duration 5s.

The single bundled question is: **For q04 B/C and v01/v03, do the actual samples show body lift/leg-over or boundary-relative progress distinct from approach, or are they insufficient/uncertain? If clear, list the visible original PTS.** This asks about sampled-input adequacy, retaining original-clip labels and completion limits. It does not request another ten-window review.

No human answer had been received by this worker when the audit was generated. Do not mark action “seen,” input “adequate,” or input “inadequate” from metadata alone. A clearly visible positive would support the corresponding controlled VLM comparison; an uncertain or insufficient case needs an explicit gate decision. The coordinator can advance only grounded prerequisites and owns that decision.

## Reproduction, verification, and limits

```bash
.venv-vlm/bin/python -B -m unittest tests_mvp.test_batch0002_input_audit -v
.venv-vlm/bin/python -B scripts/audit_batch0002_inputs.py --source-commit 3e9a6bb415e175106b9deac55a58cfc465e26eae
```

The CLI verifies the three committed source/config/test files byte for byte, pins metadata inputs, uses EXP-0017's existing local file index, and refuses pre-existing audit output namespaces/results. Reproduction requires the unchanged local inputs and a fresh output namespace; do not delete historical results to rerun it. Source files and every consumed metadata/cache file are rehashed before and after artifact generation.

**14 synthetic CPU integrity tests passed before execution.** They cover timing/native PTS, crop/shape/token bindings, non-GT location projections, source/crop pixel hashes, all 20 variant collection, historical-pixel unavailability, cached-byte and historical-metadata tampering, input changes, output preservation, strict JSON, committed-source freeze, and synthetic local clip/decoder behavior. The actual audit completed on its first attempt with zero audit failures/retries. One later verification command mistakenly used system `python3`, failed on missing `av` before media access, and was corrected once to the unchanged existing `.venv-vlm`; the audit was not rerun.

Post-run checks revalidated **111 consumed files** and **29 display artifacts** (20 sheets, five original diagnostic images, three review clips, one bundle manifest), confirmed the 103-entry unique inventory and public-summary privacy fields, and verified all three clip timelines. Local receipts are `runtime/BATCH-0002/input-audit/consumed-files.local.json` and `verification.local.json`; display media stay under `outputs/batch0002/input-audit/`. Nothing was sent through image/browser/cloud tools. No GPU, weights, downloads, model/processor construction, model outputs, queue mutation, environment changes, source-result edits, web changes, or worker commit/push occurred.

Environment: existing Python 3.10.12, PyAV 16.0.1, NumPy 2.2.6, Pillow 12.3.0. Native FFmpeg library versions are in the JSON. No inference latency/FPS/VRAM or CPU resource profile was measured. Accuracy, precision/recall/F1, FPR, semantic success, and operational/generalization claims are unavailable. Sampling/scale as a cause of previous failures remains unestablished.

| Artifact | SHA-256 |
| --- | --- |
| Public input audit | `3a7daf37e36cc2c01694a2d859e5246a0dd31ba7973f53ef4aea6db8694ab5e1` |
| configs/batch0002_input_audit.json | `9509b8ffc309b416c9a9f7c9b72e0db5ccd71a3e4b7b4057198491311324ab37` |
| scripts/audit_batch0002_inputs.py | `56d97861c4905ee573512db9ed9c74d9fc80920acfc6dae4a455b0c96d0d7fbb` |
| tests_mvp/test_batch0002_input_audit.py | `7cfd88f69000e13a316d5f41c7bef7129cb453e715f2767e6d26bcce53022d51` |
