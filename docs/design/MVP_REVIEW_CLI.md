# Saved-observation MVP review CLI

This local, offline review flow reuses the already measured EXP-0029 observations, native PTS, tracklets, representative features and accepted associations. It combines existing boundary-motion candidates, current-polygon two-side candidates, possible identity links and original evidence. It does not classify legal access or establish physical crossing completion. The actual run and visual findings are recorded in [EXP-0030](../experiments/EXP-0030-mvp-review-integration.md).

## Inputs and preservation

Run from the repository root with the existing `.venv`. The supported development windows are E01_030 84–100s (480 frames) and E01_007 48–105s (1,710 frames). Source paths are declared in `sceneguard/run_mvp_review.py`; the original videos and EXP-0029 artifacts must already exist locally. This is a reproducible fixed development run, not a general arbitrary-video detector.

`runtime/EXP-0030/current-regions.json` binds the actual user-modified030 config and unchanged007 config to their file/source SHA256. Coordinates remain local. Do not substitute the historical030 runtime config or historical region-event files. There is no old/new polygon comparison in this flow. `protected-files.json` provides the previous-output preservation inventory.

The freeze step validates the original video/cache/tracking/settings binding, exact observed-row partition, representative selection, stored 512-dimensional features, accepted-chain mapping and current region source/dimensions/hash. It records the implementation and input hashes. Synthetic tests and independent review precede execution.

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*mvp_review*.py' -v
.venv/bin/python -m sceneguard.run_mvp_review freeze
# Execute only after independent preflight of the frozen source/input manifest.
CUDA_VISIBLE_DEVICES='' .venv/bin/python -m sceneguard.run_mvp_review execute
```

`outputs/exp0030/current-v1` must not already exist. The runner refuses overwrite and does not automatically retry. Keep completed/failed outputs and their source freeze; a new authorized attempt requires a separately named output and new review. Do not delete an old run just to repeat these commands. No detector, tracker or encoder forward call is part of this flow; the common GPU queue is left unchanged.

## Meaning of outputs

- Existing accepted associations remain `auto_associated_unverified`; review suggestions never modify raw IDs or chains. Similarity is not an identity probability.
- The upstream feed keeps at most two rejected/deferred similarity proposals per earlier tracklet as `possible_match_needs_review`. Pairs outside the original 5 s association horizon are audit-only, never recovered automatic links.
- `boundary_motion_requires_review` preserves original gap-rule candidates. `two_side_transition_requires_review` uses only current-region actual observations and original chain membership. Both retain completion/identity uncertainty.
- Diagnostic overlap, box-extent and representative-consistency flags annotate suspect inputs; they neither select a person nor silently drop representatives. Stable partial/mixed crops can escape these checks.
- Original candidate/estimated interval, original emission/region confirmation PTS, full-window offline availability, feed preparation UTC and completed media UTC are distinct clocks. This is not live alert latency.
- The007 56.7 s approach observation is a user-confirmed context reference, not a synthetic detector event or a new algorithm truth label.

Per-video `feed.json`, `region-events.json`, `quality-diagnostics.json`, `question-audit.json`, `summary.json` and `render-receipt.json` are local. Evidence bundles provide the original/raw/association/review comparison, short source clips and a local index. Candidate and link references preserve uncertainty and original PTS. Whole-run `execution-receipt.json` records timings and preservation; failure receipts remain separate if execution fails.

## Review and delivery

Read raw original panels alongside boxes. Verify same-person correspondence independently of model IDs; distinguish body movement from changing box extent and multi-person crops. The examples are development material, not an independent evaluation set. No IDF1/HOTA, intrusion accuracy or final F1 is inferred from output counts.

The existing `orchestration.complete` flow registers report, aggregate metrics, independent SHA-bound review and allowlisted evidence. Local registration, actual browser playback and GitHub publication are separate checks; see [delivery contract](../orchestration/EXPERIMENT_DELIVERY.md). No viewer feature is added. Videos, crops, raw coordinates/features, local configs and runtime receipts stay excluded from Git.
