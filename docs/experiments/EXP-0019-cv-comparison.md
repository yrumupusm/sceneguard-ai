# EXP-0019 — BATCH-0002 native-frame CV comparison

2026-10-29 KST. **Eleven-frame native comparison executed successfully; exact visual quality review pending; adopt_on_hold.** This bounded diagnostic compares the preserved FCOS COCO_V1 outputs with one RF-DETR Medium checkpoint. It does not change the default detector, ByteTrack, ROI, event rules, or MVP.

The coordinator accepted the CPU native-source audit and the prior human observations of three approaching people at03084 and three climbing people at03090. Those observations establish neither precise person boxes nor completion. The separate sampled-input human bundle now reports q04 holding the gate and raising a foot (B/C adequacy not independently established), v01 crossing the rope and standing opposite, and v03 climbing a rock beside the gate (boundary crossing unestablished); this CV comparison does not certify VLM input sufficiency.

## Frozen comparison

The eleven frames are03084/90/94,00752/64/66,03132/40,006119/125/131. All have existing EXP-0004 prefinal person caches and review-manifest bindings, so FCOS inference is unnecessary. For006, nominal119/125/131 map to existing native PTS118.98553333333334/124.99153333333334/130.99753333333334; integer timestamps are labels for these selected frames, not fabricated native timestamps. v frames are omitted because exact-frame pose observability has not been reviewed. Every source, native PTS/time base, full RGB byte hash, historical cache and environment file is bound in the pre-execution manifest.

The sole new checkpoint is official RF-DETR Medium, rfdetr1.11.2/tag7433d5919d0f7e72cc6cb78663e0a731afd499e0, Apache-2.0. Downloaded size404,992,918 bytes and MD5`7223f764a87b863f02eb8d52bf0ce2ee` match the registry; actual SHA256`749ff6071828aaffac63e204c4f4135ed3d6cdae4d702e086c360edc3b5768c8`. Official source selection and checkpoint URL are in [ADR-0018](../decisions/ADR-0018-batch0002-cv-candidate.md).

RF-DETR uses full original RGB only, eager FP32, batch1, official576×576 resize/normalization, score strictly greater than0.5, default top300 over sparse COCO classes, person ID1, and no added NMS. Official predict maps boxes back to original coordinates once. FCOS uses its historical full-frame min800/max1333 path and final person score at least0.5; equal numeric score thresholds do not imply calibrated equivalence. Model family and preprocessing both differ.

The isolated environment installed torch2.5.1+cu124/torchvision0.20.1+cu124, rfdetr1.11.2, transformers5.1.0, supervision0.29.0. Its76-package inventory and23,147 installed code/native-library file hashes are frozen before enqueue. CPU import checks with CUDA hidden passed, cuda_initialized=false, and six reviewed installed RF-DETR files exactly match the cached official tag. Those checks constructed no model; subsequent construction and all predictions occurred only in the authorized canonical queue child. Existing environments are untouched. The execution child denies network connections, and offline environment flags prevent implicit backbone or extra checkpoint retrieval.

## Execution gate and cost

Only the existing canonical serial queue may execute the fixed `batch02-cv` command. Inherited lock inode/ownership, live parent and exact recorded child identity, coordinator-confirmed Task/Dispatch/commit, and source/input/config/environment hashes are checked before torch import. The free-VRAM minimum remains6144MiB. The queue migration backs up SQLite and checks preservation of every old job and attempt. Errors allow at most one explicit retry per job, and a retry is refused if any earlier attempt began predicting a frame; no automatic tuning or alternate queue exists.

Smoke consumes03084/90 once. Only technical success allows the other nine frames, without rerunning smoke. No diagnostic frame is used for warmup. First predict per separately loaded stage is labeled cold-first; later frames remain single-pass observations. The official release defers CUDA placement until first use; its official device-transfer helper is called inside the queue child and included in construction/load timing, without an inference. Model construction/load wall time, predict wall time including actual tensor capture/hash, allocator allocated/reserved peaks, and device-wide sampled memory are recorded separately. Device sampling may miss peaks and includes other processes. Historical FCOS latency is not a controlled benchmark and cannot establish a relative speedup. End-to-end video throughput, tracking/event quality, power, deployment performance, and generalization are unmeasured.

## Evidence and interpretation

Local ignored artifacts preserve original RGB, native PTS/time base, raw returned boxes/scores/class IDs, actual normalized model-input arrays/shapes/hashes, queue receipts, timings, device samples, and original/FCOS/RF-DETR panels for these eleven frames only. Public summaries contain nonidentifying frame aliases, output counts, costs and limitations. Overlap with the pre-existing Codex approximate03084/90 review regions is diagnostic only; overlapping regions can select the same detection and are not person IDs or GT.

More detections do not establish improved person recovery. Exact visual judgments of missing people, duplicates, partial bodies, suspicious background boxes and maintained climbing detections remain unknown pending review; no new visual claims are made here. Precision/recall/F1 are null because no precise person-box ground truth exists.006 late walking is outside the old ROI and must not count as correct event rejection. **Adoption stays on hold** until evidence and independent review justify a narrower conclusion; this task creates no integration PoC.

## Validation status

Twelve new CPU contract tests pass, including direct-child rejection, lease identity, strict score/sparse class mapping, resource gate and preservation migration. System-Python full Orca discovery encountered two unrelated missing-fastapi import errors; the existing project interpreter passed all48 targeted queue, existing VLM/MVP registration and new CV checks. Installation, pip dependency check, CPU imports and both actual CUDA stages pass. The coordinator ran the full Orca suite in the existing lab environment:101 tests ran successfully with1 skipped (100 passed); its local log is separate from the earlier missing-fastapi discovery attempts. Independent quality review is pending.


## Actual execution and original-frame comparison

The coordinator reviewed and committed the frozen execution bytes as `e0dc11a505002304eb0daf03d723d735849dcce8`, then confirmed the registered EXP-0019 Task/Dispatch. Execution source digest was `5e6f7f75aeaeac197e3912fe89471f5608295d068dd1475b9d275515de0aae30`. Both queue jobs and both first attempts succeeded: **11 unique frame predictions,0 warmup,0 retries,0 errors/OOM**. No FCOS prediction or additional checkpoint/backbone download occurred. Source bytes and all pinned input/environment/weight/cache files were verified again after execution. All18 pre-existing jobs and18 attempts remained byte-for-byte equal as records; the additive migration backup is retained locally.

These are **final person-box output counts**, not numbers of recovered people or quality scores. The two cold-first rows belong to separate model loads and were never repeated.

| Frame alias | Native PTS | Time base | Actual source PTS(s) | FCOS≥0.5 | RF-DETR>0.5 | Predict(ms) |
| --- | --- | --- | --- | --- | --- | --- |
|030_084|1290240|1/15360|84.000000000|3|3|1103.287 (cold-first)|
|030_090|1382400|1/15360|90.000000000|0|1|37.649|
|030_094|1443840|1/15360|94.000000000|0|0|963.480 (cold-first)|
|007_052|798720|1/15360|52.000000000|2|2|85.669|
|007_064|983040|1/15360|64.000000000|3|2|31.447|
|007_066|1013760|1/15360|66.000000000|1|2|36.053|
|031_032|491520|1/15360|32.000000000|2|0|31.157|
|031_040|614400|1/15360|40.000000000|0|0|33.207|
|006_119|10708698|1/90000|118.985533333|2|2|53.151|
|006_125|11249238|1/90000|124.991533333|0|2|30.376|
|006_131|11789778|1/90000|130.997533333|2|0|35.719|

At the prior human-confirmed03090 climbing instant, RF-DETR returns one person box versus FCOS zero. That box has not been visually adjudicated for person identity, whole/partial body, overlap or background. The output does not establish stable recovery of the three previously observed people. Counts increase at some other frames and decrease at others, so they support no blanket improvement claim.03094 and03140 remain zero-output diagnostic frames; exact person-level judgments remain unknown. No new visual observations were made by an image model or cloud media tool.

## Measured costs and evidence

| Measurement | Smoke2 frames | Remaining9 frames |
| --- | --- | --- |
| Child free-VRAM gate(MiB) |7495|7698|
| Model construction/load plus official CUDA transfer(s)|2.8745|2.9235|
| Load allocator peak allocated/reserved(MiB)|129.21 /156|129.21 /156|
| Predict allocator peak allocated/reserved(MiB)|214.22 /244|214.22 /244|
| Device-wide sampled used-memory range(MiB)|2558–3068|2361–2866|
| Device samples / sampling errors|28 /0|64 /0|
| Queue attempt duration(s), including hash/import/receipt overhead|13.251|24.907|

Total instrumented predict time was2.4412s across11 calls. Nine subsequent-frame measurements range30.376–85.669ms; the two cold-first values are reported separately above. These small single-pass measurements include the actual tensor CPU-copy/hash capture hook and cannot establish a controlled throughput or latency advantage over historical FCOS. Device-wide samples include other GPU use and can miss peaks; they are not interchangeable with allocator peaks. Actual inputs were captured as FP32 `1×3×576×576` for all11 predictions, with original1920×1080 RGB and original-coordinate returned boxes retained. No second coordinate scaling was applied.

The ignored local comparison directory contains11 original/FCOS/RF-DETR panels and the privacy-safe counts/timing summary. Actual source PTS, native PTS and time base were added to panel display text only after both inference stages settled. Raw returned boxes/scores/classes, actual preprocessed arrays/hashes, original RGB, tentative overlap diagnostics, device samples, environment inventory, migration backup and both queue receipts remain local; they are not published media or bbox ground truth. The local execution-results and integrity receipts bind job/attempt IDs and evidence hashes for independent review.

**Decision: adopt_on_hold.** Technical compatibility is established for these eleven frames. Stable human recovery, duplicate/background/partial-box quality, event sensitivity, precision/recall/F1, new-camera generalization and operational cost remain unestablished. These outputs alone do not justify replacing FCOS, changing tracking/ROI/events, or starting a combined PoC. The next needed evidence is exact local panel adjudication under the preserved human observations and independent review, without another inference or settings search.


Public source-bound numeric records: [metrics](../../records/EXP-0019/metrics.json) and [native-frame comparison summary](../../records/EXP-0019/comparison.json). Every measured metric cites the relative local summary source, its actual SHA256 and exact field pointer; original-source, manifest, environment inventory, checkpoint and execution-source hashes are frozen in those records. Raw summaries stay local and are not included as public bbox payloads.
