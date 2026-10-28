# EXP-0019 — BATCH-0002 native-frame CV comparison

2026-10-29 KST. **CPU preparation complete; model execution awaits coordinator freeze/assignment; adopt_on_hold.** This bounded diagnostic compares the preserved FCOS COCO_V1 outputs with one RF-DETR Medium checkpoint. It does not change the default detector, ByteTrack, ROI, event rules, or MVP.

The coordinator accepted the CPU native-source audit and the prior human observations of three approaching people at03084 and three climbing people at03090. Those observations establish neither precise person boxes nor completion. The separate sampled-input human bundle now reports q04 holding the gate and raising a foot (B/C adequacy not independently established), v01 crossing the rope and standing opposite, and v03 climbing a rock beside the gate (boundary crossing unestablished); this CV comparison does not certify VLM input sufficiency.

## Frozen comparison

The eleven frames are03084/90/94,00752/64/66,03132/40,006119/125/131. All have existing EXP-0004 prefinal person caches and review-manifest bindings, so FCOS inference is unnecessary. For006, nominal119/125/131 map to existing native PTS118.98553333333334/124.99153333333334/130.99753333333334; integer timestamps are labels for these selected frames, not fabricated native timestamps. v frames are omitted because exact-frame pose observability has not been reviewed. Every source, native PTS/time base, full RGB byte hash, historical cache and environment file is bound in the pre-execution manifest.

The sole new checkpoint is official RF-DETR Medium, rfdetr1.11.2/tag7433d5919d0f7e72cc6cb78663e0a731afd499e0, Apache-2.0. Downloaded size404,992,918 bytes and MD5`7223f764a87b863f02eb8d52bf0ce2ee` match the registry; actual SHA256`749ff6071828aaffac63e204c4f4135ed3d6cdae4d702e086c360edc3b5768c8`. Official source selection and checkpoint URL are in [ADR-0018](../decisions/ADR-0018-batch0002-cv-candidate.md).

RF-DETR uses full original RGB only, eager FP32, batch1, official576×576 resize/normalization, score strictly greater than0.5, default top300 over sparse COCO classes, person ID1, and no added NMS. Official predict maps boxes back to original coordinates once. FCOS uses its historical full-frame min800/max1333 path and final person score at least0.5; equal numeric score thresholds do not imply calibrated equivalence. Model family and preprocessing both differ.

The isolated environment installed torch2.5.1+cu124/torchvision0.20.1+cu124, rfdetr1.11.2, transformers5.1.0, supervision0.29.0. Its76-package inventory and23,147 installed code/native-library file hashes are frozen before enqueue. CPU import checks with CUDA hidden passed, cuda_initialized=false, and six reviewed installed RF-DETR files exactly match the cached official tag. No model has been constructed in those checks. Existing environments are untouched. The execution child denies network connections, and offline environment flags prevent implicit backbone or extra checkpoint retrieval.

## Execution gate and cost

Only the existing canonical serial queue may execute the fixed `batch02-cv` command. Inherited lock inode/ownership, live parent and exact recorded child identity, coordinator-confirmed Task/Dispatch/commit, and source/input/config/environment hashes are checked before torch import. The free-VRAM minimum remains6144MiB. The queue migration backs up SQLite and checks preservation of every old job and attempt. Errors allow at most one explicit retry per job, and a retry is refused if any earlier attempt began predicting a frame; no automatic tuning or alternate queue exists.

Smoke consumes03084/90 once. Only technical success allows the other nine frames, without rerunning smoke. No diagnostic frame is used for warmup. First predict per separately loaded stage is labeled cold-first; later frames remain single-pass observations. The official release defers CUDA placement until first use; its official device-transfer helper is called inside the queue child and included in construction/load timing, without an inference. Model construction/load wall time, predict wall time including actual tensor capture/hash, allocator allocated/reserved peaks, and device-wide sampled memory are recorded separately. Device sampling may miss peaks and includes other processes. Historical FCOS latency is not a controlled benchmark and cannot establish a relative speedup. End-to-end video throughput, tracking/event quality, power, deployment performance, and generalization are unmeasured.

## Evidence and interpretation

Local ignored artifacts preserve original RGB, native PTS/time base, raw returned boxes/scores/class IDs, actual normalized model-input arrays/shapes/hashes, queue receipts, timings, device samples, and original/FCOS/RF-DETR panels for these eleven frames only. Public summaries contain nonidentifying frame aliases, output counts, costs and limitations. Overlap with the pre-existing Codex approximate03084/90 review regions is diagnostic only; overlapping regions can select the same detection and are not person IDs or GT.

More detections do not establish improved person recovery. Exact visual judgments of missing people, duplicates, partial bodies, suspicious background boxes and maintained climbing detections remain unknown pending review; no new visual claims are made here. Precision/recall/F1 are null because no precise person-box ground truth exists.006 late walking is outside the old ROI and must not count as correct event rejection. **Adoption stays on hold** until evidence and independent review justify a narrower conclusion; this task creates no integration PoC.

## Validation status

Twelve new CPU contract tests pass, including direct-child rejection, lease identity, strict score/sparse class mapping, resource gate and preservation migration. System-Python full Orca discovery encountered two unrelated missing-fastapi import errors; the existing project interpreter passed all48 targeted queue, existing VLM/MVP registration and new CV checks. Installation, pip dependency check and CPU imports pass; actual smoke/full compatibility, detections and costs remain unmeasured.
