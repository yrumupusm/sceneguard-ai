# Dual-boundary passage candidate implementation

2026-11-04. Implementation worktree starts at `40f22e79e2291dffde237e7e70b58a517b27ea35` and follows `DUAL_BOUNDARY_PASSAGE_PLAN.md`. The user's explicit authorization supersedes the earlier draft-review wait: both reviewed inner contours and early-confirmation suppression are implemented as an optional candidate mode. This report covers code and synthetic integration tests, not the separate frozen 45-video evaluation, independent review, deployment or behavioral acceptance.

## Input and production path

Add `inner_line: [[x,y], ...]` to a **new copied scene revision**, using normalized coordinates from the reviewed draft manifest. The existing `line` stays the outer segment; zones, portal configuration and old input/output files are retained. The mode is selected by the explicit presence of `inner_line`; an empty, degenerate, nonfinite or self-intersecting contour fails validation. No new CLI flag or truth-time input is required.

`RuleBackend.prepare()` creates `DualBoundaryDirection`. `RuleBackend.confirmations()` produces suspicion audits instead of old positive seed decisions. `replay_scoped()` selects the guarded causal dual-boundary lifecycle even if a caller passes its old direction engine or requests the old follow-up mode. The ordinary `analyze_observations()` → scoped cards → gate activity cards path remains integrated. Scene/registry revision validation accepts the additional validated field, including C6, while preserving its other calibration and policy fields. The absence of the field retains the legacy rule path.

No old existing-alert, visible-crossing, history-loss, outward-loss, ambiguous-loss, delayed-loss or follow-up confirmation can bypass the new path. Direct low-level confirmation helpers return a guarded suspicion for a dual-boundary scene; `DualBoundaryDirection` also disables the inherited old classifier/observed-crossing/retry entrypoints. Existing positive decisions passed to replay are retained as suppression audits, rather than seeded as facts. Candidate event payloads remain byte-for-byte equivalent as JSON values. Existing boundary alerts bind through a unique measured segment containing their two actual anchors and emission observation, then consume the same dual-boundary evidence as any other candidate; locating a track number is not passage proof.

## Geometry and measured evidence

`Corridor` pairs endpoints by the smaller total pixel distance and forms a finite polygon from the outer segment and reversed inner polyline. Boundary normals face the opposing contour. C8's reviewed inner endpoint sequence is reversed relative to the outer line; C1–C7 retain their order. C5 retains all five reviewed inner vertices. Classification respects finite endpoints, including internal polyline bends, rather than extending the gate into an infinite line. Crossing requires opposite nonzero-side anchors; touching alone is insufficient. Every measured on-line sample must remain on the finite contour, for both bbox proxies and saved point paths. An on-line path that walks beyond an endpoint cannot later claim a crossing, and simultaneous crossings retain their temporal order in both directions. Read-only validation of all eight canonical manifest contours succeeded; no manifest or source scene was changed.

The position proxy is the **actual bbox horizontal center at 65% height**, in source pixels. It is not reconstructed feet, a restored ground position, human identity or independently verified bodily passage. Stable origin and destination use the adopted 0.2-second/3-observation support and 3-pixel deadband. Adjacent actual boxes must retain the existing 0.25-second maximum step, 1.8 scale ratio and half-height position-continuity limits; a missing source frame cannot create a bbox chord.

A stable side of origin survives a long observed approach and region-unclassified corridor observations. Visible confirmation needs ordered entry through the finite source boundary, exit through the opposing boundary, and stable actual destination observations. It requires no loss wait. Mere persistence just beyond the outer edge or within the corridor remains suspicion. Reversal before passage clears the pending crossing, whereas an already confirmed inside-to-outside passage remains confirmed after a return. After a consumed visible passage, the measured destination can establish the next episode's origin.

The corridor origin has a common **60-second episode ceiling**, refreshed while still supported on the actual origin side before entry. This is an unvalidated common heuristic against indefinite inherited context, not a tuned duration or claim of optimality. Crossing a source gap resets origin state. Numeric IDs do not extend the episode.

## Occlusion, ambiguity and loss

Across an actual observation break, origin can transfer only through a unique saved moving-point cohort: at least the adopted minimum points, 60% of the source moving cohort, persistent point IDs through every original frame, actual source seed ownership, source continuity, bounded size/position, forward agreement with the new actual box and a current uniquely mapped run. The adopted **6-second pair horizon** and 3-height pair distance bound transfer; competing successors and competing source handoffs remain uncertain. The same rule applies to a gap even when the numeric raw ID remains unchanged. Source and destination boxes observed simultaneously cannot be silently merged.

Missing bbox intervals are explicitly marked as such. Any crossing supported during that gap is recorded separately as a saved point path with its window/point references; no interpolated bbox is fabricated. The before/after bbox references remain actual observations. An untrusted or ID-only break cannot inherit origin.

Loss retains the adopted **1-second actual absence wait**. Positive loss requires stable origin, measured finite entry, a last actual proxy in the opposing half of the finite corridor, a continuous recent actual bbox path that made at least the existing minimum motion toward the opposing boundary, and fresh destination-directed saved target motion. Source gaps, expired context, ambiguous succession, missing direction, same-side return and lingering without recent progress cannot confirm. A video ending before the wait supplies no disappearance. No automatic negative/release is emitted by this candidate mode; comparison metadata reports that the release rule changed.

## Cards, audit and reproducibility

New positive resolutions use `kind=preserved_confirmation`, `confirmation_source=dual_boundary_passage_v1`, an explicit observation key, physical evidence reference and `source_decision`. `IncidentLifecycle` validates causal origin/path support, enabled direction, observation binding and absence evidence. `ScopedIncidentLifecycle` routes each physical outcome to one evidence anchor in the latest linked incident, preserving older pending evidence and sticky confirmation. The activity layer consumes the causal timeline, rather than the final state at earlier times.

Results retain the existing cards/events/timeline/notification structures. `scoped_lifecycle.dual_boundary_audit` records oriented geometry, proxy meaning, bounds and suppressed legacy positives. `followup_audit` records machine-readable reasons, source decisions and handoffs. Positive decisions include `direction`, origin references, finite `entry`/`exit`, association records and either `passage` or measured directed-loss evidence. `seed_decisions` are guarded suspicion audits; evaluators should read actual confirmation resolutions/cards rather than count seed positives. Final production card metadata includes `dual_boundary_rules_enabled`, `release_rule_changed`, and the new algorithm identifier.

At task start the required read-only web `pending --include-acknowledged` command returned `requests: []`. No web DB mutations, source media upload, GPU/detector/tracker/flow generation, frozen-output edits, evaluator edits, root HANDOFF edits or push occurred. The canonical manifest and its 17 protected calibration file hashes were checked read-only; source revision selection is left to the evaluation worker.

## Validation

The final self-contained suite below passes **528 tests, zero failures/errors/skips**, including **33 new dual-boundary tests**. It exercises the production backend, symmetric visible/loss confirmation, early-edge lingering/jitter/object-proxy suppression, long origin retention, finite endpoints/C5-style bend/C8-style reversal, source/data gaps and recording end, predicted boxes, size/position jumps, unique/competing saved-point transfer, genuine occlusion without bbox reconstruction, same-ID gaps, original-alert anchor binding, source immutability, prefix equivalence, sticky proven exit and scoped incident ownership.

```bash
PYTHONPATH=.:tests /home/jhc7484/dev/sceneguard-ai/.venv-cv-batch02/bin/python -m unittest \
  test_dual_boundary test_mvp_pipeline test_visible_crossing test_existing_alert_crossing \
  test_outward_crossing test_gate_observation test_gate_observation_integration \
  test_lifecycle_followup test_incident_lifecycle test_incident_outcome_scope \
  test_gate_activity_episodes test_gate_episode_evidence test_directional_loss \
  test_portal_births test_incident_cards test_video_cards test_target_binding_contract \
  test_handoff_binding_contract test_stationary_origin_crossing_contract \
  test_delayed_raw_loss test_delayed_loss_binding_contract test_delayed_loss_ownership_contract -q
```

The six independent `test_dual_boundary_review` contracts from reviewer commit `3cbf50cbb02289b5666f3fbc450e3f99fa7aba3a` also pass, including the symmetric endpoint-touch/run-past counterexample. They were run from `/tmp` with this implementation checkout first on `PYTHONPATH` and the review checkout's `tests` second. The owned tests additionally exercise the shared saved-point finite-path checker and a two-boundaries-in-one-step ordering counterexample.

`python -m compileall -q sceneguard` and `git diff --check` also pass. A broader camera-profile fixture attempt had one FileNotFoundError because this isolated worktree lacks `runtime/EXP-0034/scene007.json`, plus one existing local-data skip; it is not counted as a passing camera-profile suite. An earlier command accidentally named a nonexistent test module; the corrected explicit suite above is the reported result. Existing canonical runtime/outputs were not copied, linked for mutation or rewritten to hide these environment limits.

The 45-video frozen replay, official 52-event matching, lost/new matches, first-confirmation timing and independent review remain separate coordinator-owned acceptance work. These tests establish software contracts, not that a 65% bbox proxy can reliably distinguish a person climbing from putting an object through a gate. Sparse observations, partial boxes, true overlapping people, unobserved boundary passage and the common episode/association bounds can retain suspicion or lose an earlier match; actual regression and early-confirmation results must be reported without tuning to truth times.
