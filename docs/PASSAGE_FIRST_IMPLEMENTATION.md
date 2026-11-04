# EXP-0051 passage-first implementation

2026-11-04. Based on `aa2ac09e129f5cbd3a3713f79684f69ffe18b05c` and the EXP-0051 protocol. This implementation supersedes EXP-0050's blanket competition refusal and permanent ambiguous-run suppression. The task is measured gate-passage detection; person identity and a uniquely assignable raw-box graph are not prerequisites. This report describes software and synthetic contracts before the coordinator's frozen full45 replay. It does not establish behavioral improvement, adoption or physical-body truth.

## Mechanism fixed before actual outcomes

An adjacent actual bbox edge uses the unchanged existing continuity conditions: consecutive source frame indices, positive PTS step at most 0.25 seconds, at most 1.8 scale change, and center displacement at most half the larger measured bbox height. Branch/merge degrees in the complete adjacent raw-box graph remain diagnostics only. They neither erase origin nor suppress current/future confirmations. No persistent lineage ambiguity set remains in production replay.

The position proxy remains actual bbox horizontal center at 65% height, in original source pixels. The original outer line and finite inner polyline, opposite nonzero-side anchors, finite on-line runs, boundary order, 3-pixel motion convention, 0.2-second/3-observation stable origin/destination, 60-second corridor episode bound, and enabled directions remain unchanged. A stationary origin may later move and cross; edge standing, one-boundary approach, same-side return, endpoint detour, predicted boxes and a gap without measured support cannot supply full passage. The origin survives measured corridor continuity and local box ambiguity beyond the old three-second window. Stable renewed independent origin can start a new episode after an incomplete path, without rehabilitating old evidence.

An observation bookkeeping run can change while actual boxes remain adjacent and continuous. Such a handoff uses an actual bbox edge and retains finite bbox crossings; it is not a fabricated occlusion chord. A bookkeeping key that reappears after handoff starts usable actual context rather than remaining permanently hidden behind its old alias. Original birth/run construction is unchanged.

Across a real missing-box interval, the existing moving-point requirements remain: source-seeded actual observation references, source target-motion cohort, minimum three surviving points, at least 60% cohort coverage, persistent window and point IDs through every original frame, unchanged six-second/three-height pairing bounds, size bound, source-clock continuity and positive point/box displacement agreement. Each crossing is evaluated along every saved original point sample with the same finite-contour checker. Missing boxes are explicitly identified; the code never interpolates a measured bbox through them. Saved point measurements are not person identity.

Supported endpoints are ordered before any result inspection by this exact tuple:

1. Descending source-cohort coverage, `len(endpoint_ids) / len(source_moving_cohort)`.
2. Descending number of supported endpoint point IDs.
3. Ascending dimensionless motion residual, `distance(actual_box_center_delta, componentwise_median(camera_corrected_point_deltas)) / max(source_bbox_height_pixels, target_bbox_height_pixels)`.
4. Target frame index, target actual cache index, then saved window ID, in ascending order.

For adjacent geometry without sufficient saved points, coverage is zero, the point-ID list is empty, and residual is measured center displacement divided by the larger actual bbox height. This ranks supported edges; it adds no acceptance threshold. Among sources proposing the same endpoint, the same ordering applies, followed by latest actual source PTS and stable run-key ordering. Crossing success, direction, truth times, video IDs and old outcomes do not enter this ranking. All endpoint alternatives remain in association evidence with `identity_verified: false`.

The preferred source supplies one bookkeeping handoff. Existing destination paths and weaker actually supported source paths are retained as separate hypotheses rather than overwritten. These paths do not union their event ownership. A weaker path can still establish a real passage if the preferred association lacks a measured origin. An unchanged losing source endpoint cannot retry and claim proof accumulated independently by the selected destination; newly observed source endpoints remain eligible. A completed destination proof is retained. Hypotheses reaching a consumed gate passage are reset from its actually measured stable destination, allowing a separately observed return while preserving the original confirmed evidence.

Consumed/handoff source states and source-gap alternatives are discarded. Alternative states beyond the existing association horizon are unused and discarded; when resets produce equivalent fresh hypotheses, canonical full-state deduplication retains one. Distinct supported active paths are never capped or vetoed. `max_active_path_hypotheses` records the maximum live path hypotheses within the association horizon for lifecycle-cost review.

## Exact evidence ownership

Each path retains its actual `(frame_index, cache_index)` references for the current episode, separate from the shorter motion history. Candidate eligibility requires membership of its bound actual source anchor in that path. A notification clock alone cannot connect an old candidate to a later episode, and a same raw ID does not bridge a break. Existing unique same-frame containment bookkeeping normalizes the selected actual run reference while preserving the original candidate payload.

Candidates at a stationary preexisting destination cannot take ownership of an incoming crossing merely because their clock is newer or their eventual observation key matches. For dual-boundary confirmations only, `ScopedIncidentLifecycle` selects the latest *eligible* evidence anchor. Its physical-proof claim still prevents reuse by older evidence. When a measured handoff and proof finish on the same frame, that dual confirmation validates after the handoff in the single immutable source-clock batch. All legacy ordering and ownership behavior remains unchanged without this rule.

An unsupported break, expired context or consumed passage starts a separate episode. New evidence can confirm a current compatible candidate while old unrelated evidence stays suspected. No broad release or negative verdict is emitted. Already confirmed outward passage remains sticky after return; a later independently measured reverse passage can add its own event.

## Current passage route when no seed is eligible

The coordinator explicitly approved this narrow route before actual replay. When a complete, enabled, causally observed two-boundary passage has no eligible pending seed, replay creates one candidate in the separate `measured_passage_events` source collection at causal proof completion. Its payload contains the actual passage and destination observation references, the current run, no asserted person/track identity, and reason `current_measured_passage_without_eligible_seed`. The event ID is the digest of rule, recording/camera/gate scope, and the actual entry/exit physical evidence. It confirms through the same validated lifecycle and consumes that passage. Dwell or retry does not reemit it.

Empty original candidate streams now reach the dual lifecycle using the explicit recording scope. A full measured passage is therefore detectable without inventing a legacy seed. Missing/incomplete paths and directed loss without a source candidate do not generate this new candidate. Original invalid existing-alert anchors still leave that original evidence suspected; an independently complete measured passage can produce a separate event. This changes candidate generation and can increase independent notifications, including a complete measured reverse passage. It must be measured separately in the coordinator's results.

All original and portal candidates are preserved as unchanged JSON values. Production integration verifies that added candidates come from `measured_passage_events`, and verifies exact preservation from scoped lifecycle through activity cards. Audit metadata reports original and derived candidate counts, association policy and diagnostic-only raw competition. The existing no-`inner_line` route is unchanged.

## Owned files and validation

Production changes are limited to `dual_boundary.py`, dual routing in `exp0048_application.py` and `mvp_pipeline.py`, and dual-only ordering/eligible-owner hooks in `incident_lifecycle.py` and `incident_outcome_scope.py`. Owned tests are `tests/test_dual_boundary.py` and new `tests/test_passage_first.py`. No prior independent-review tests/docs, evaluator, web, records or root HANDOFF were edited.

The explicit suite below passed **552 tests, no failures/errors/skips**: 39 revised dual-boundary tests, 18 new passage-first tests and 495 existing regression tests. Four owned method families intentionally supersede the previous universal branch/merge/gap-competition refusal and permanent later-candidate refusal expectations. Real gaps without point support remain negative. Invalid original alert anchors are tested separately from a newly derived valid passage.

```bash
PYTHONPATH=.:tests /home/jhc7484/dev/sceneguard-ai/.venv-cv-batch02/bin/python -m unittest \
  test_dual_boundary test_passage_first test_mvp_pipeline test_visible_crossing \
  test_existing_alert_crossing test_outward_crossing test_gate_observation \
  test_gate_observation_integration test_lifecycle_followup test_incident_lifecycle \
  test_incident_outcome_scope test_gate_activity_episodes test_gate_episode_evidence \
  test_directional_loss test_portal_births test_incident_cards test_video_cards \
  test_target_binding_contract test_handoff_binding_contract \
  test_stationary_origin_crossing_contract test_delayed_raw_loss \
  test_delayed_loss_binding_contract test_delayed_loss_ownership_contract -q
```

The independent reviewer's separately owned new policy suite also passed **31 tests** from this checkout:

```bash
PYTHONPATH=.:tests:../sg-passage-first-review/tests \
  /home/jhc7484/dev/sceneguard-ai/.venv-cv-batch02/bin/python \
  -m unittest test_passage_first_review -q
```

It independently covers duplicate/nearby ambiguity in both directions, many-source convergence, retained long origin, supported duplicate endpoints after occlusion, actual missing-path negatives, interrupted saved points, target replacement, old-anchor exclusion, stationary destination coexistence, causal prefixes, disabled directions, exact source alerts, loss wait/direction/EOF, finite contours and sticky prior positives. These suites overlap in contracts and are not claimed as 583 independent behavior scenarios. The old independent suite's blanket-veto expectations remain historical and untouched; the new independent suite explicitly records policy replacements.

Canonical-environment `compileall` and `git diff --check` passed. An initial bare `python` verification command was unavailable in this shell; the canonical existing CV interpreter completed it without installation. Startup web `pending --include-acknowledged` succeeded with `requests: []`. The existing saved manifest and execution-binding schema were inspected read-only, together with saved frame/point readers; no actual candidate replay, outcome fitting, source-media upload, GPU, new detection/tracking/flow/VLM, protected input edits or push occurred.

## Remaining limits and delivery

The proxy and saved points remain fallible image observations. Smooth neighboring-person/object substitutions can look like a coherent image path; relaxed identity uniqueness does not solve identity. Missing actual boundaries, motionless loss tails, point dropout, pair/episode limits and malformed geometry can still prevent confirmation. Finite interpolation between adjacent actual samples does not reconstruct hidden feet. Multiple distinct nearby actual paths may still produce multiple gate events; this is not a person counter. Directed corridor loss remains a separately labeled weaker hypothesis with the existing actual-absence wait; this candidate mode does not automatically release suspicion.

The coordinator owns frozen full45 replay, original52-event matching, gained/lost confirmations, first clocks, original/derived and unreviewed notifications, priority outward videos, 010 timing, 006 uncertainty, 008 semantic deferral, registration and adoption. Passing synthetic contracts and eliminating the known blanket veto do not certify recall, F1, physical passage accuracy or operational adoption.

## Correction after the first frozen replay — active measured branches

2026-11-04. Correction dispatch `ctx_61a0e743b997`, effective `gpt-6.1-sol` / `high` as reported by Orca's exact worker launch and live terminal observation. The independent reviewer discovered an additional synthetic miss after the initial 31-test review and the coordinator's first replay: the original bookkeeping source stays on a stationary duplicate while another actual branch traverses the gate. The old proposal loop inspected only missing sources, so the moving branch lost its stable origin. The first replay at `8ed1766` is preserved by the coordinator; this worker neither replayed actual videos nor inspected their outcomes. Startup web pending lookup succeeded with `requests: []`.

Proposals now inspect the preceding actual endpoint before advancing current rows, including active sources. The unchanged measured endpoint ranking selects a supported outgoing branch. Equally ranked hypotheses prefer an existing stable origin and then exact pending-anchor support; neither changes endpoint acceptance or introduces a crossing-success score. Existing destination and weaker supported source hypotheses remain available. Only the selected eligible source witness is copied, after filtering expired contexts by the existing six-second horizon; the algorithm does not expand the Cartesian product of all path histories. A recurring alias key is detached without deleting valid path state, and can receive measured continuity on that same frame.

An active source retains its own branch and pending event ownership. A complete inherited passage can transfer only pending candidates whose exact actual anchors occur in its episode, immediately before confirmation in the same immutable clock batch. Missing-source handoffs also filter anchors. No union of different paths' reference sets occurs. Alternative witnesses of one consumed measured origin episode restart from their own actual endpoint; the selected completed passage retains its stable measured destination. This avoids emitting that same branched episode repeatedly and permits subsequent independently observed origins and return passages. Prior confirmation remains sticky.

For geometric-only active departure, an already observed destination must actually move; exact stationary native boxes cannot form a moving chain. Nonzero native source/destination displacement must agree with the proposed edge. A stationary source is neutral, a newly observed destination can retain its first actual edge, and there is **no per-frame minimum-speed threshold**. Saved source-point support can keep an alternative eligible despite conflicting native bookkeeping motion. This is local measured-path consistency, not an identity or uniqueness requirement.

Such a point-supported active branch is disproved only when its persistent original source cohort supplies actual opposing motion: at least three surviving original IDs and 60% cohort coverage through every saved frame, with camera-corrected point displacement opposing the inherited actual box displacement over the existing 0.5-second reference / one-second history. Both displacements must satisfy the existing three-pixel motion convention. Only that branch resets. Missing/interrupted/insufficient points, stationary points, and points merely outside a partial box remain unknown and do not reset it. In the independent opposing-return fixture the inherited branch is contradicted at frame 6, before any confirmation. A monitor whose persistent support is interrupted becomes inactive without invalidating its measured bbox path.

Adjacent point-supported edges now identify actual adjacent bbox continuity and set `missing_box_interval_is_not_measured_box_path: false`; their finite crossings remain actual bbox crossings. Real missing-box intervals retain saved-point crossings and the true missing-box flag. A second concrete regression from the review exposed slow crossings through the existing three-pixel boundary deadband: samples just beyond the finite corridor polygon previously cleared entry before stable destination classification. Finite samples inside that unchanged band now retain corridor uncertainty; they establish neither stable origin nor destination. Finite endpoint escapes remain excluded.

Deduplication compares future-relevant state while retaining one complete untouched actual witness: finite-boundary/origin/proof state, the full recent motion rows and loss tail, saved point seed rows, active cohort monitors, and membership of every possible original candidate anchor. Immutable original source pointers supply anchor retention tags, including containment normalization; they never score an association or provide future crossing coordinates. Older non-seed rows, non-anchor reference membership and audit-only handoff annotations cannot change a future decision and are omitted from the equivalence key. Distinct useful states are never numerically capped.

Final validation passed **590 tests** without failures/errors/skips: the original required suite plus three owned correction tests gives 555, and the independently owned review suite gives 35. Owned additions cover active stationary-source departure in both directions with/without saved points, a late exact candidate after history compaction, and sustained duplicate histories. Independent additions cover active departure, repeated corridor branches, stationary box chains and persistent one-pixel-per-frame point-supported movement. Its gap metadata assertion now checks real gaps and adjacent actual edges separately; the reviewer owns that change.

Using the command above with `test_passage_first_review` added and `../sg-passage-first-review/tests` appended to `PYTHONPATH`, all 590 tests completed in 8.345 seconds. Synthetic shifted-duplicate corridor workloads of 45/85/165 frames had maximum live hypotheses 4/4/4 without points and 5/5/5 with points, with no confirmations before actual exit. Measured wrapper times were 0.042112/0.075801/0.163165 seconds and 0.059318/0.118437/0.280721 seconds respectively. These are local synthetic cost checks, not video throughput guarantees. Early uncommitted drafts exposed excessive duplicate-history cost and the new per-frame speed floor; neither is retained in this correction.

Only `sceneguard/dual_boundary.py`, `tests/test_passage_first.py` and this correction section changed. The other four owned production files, numeric policies, source candidates, evaluator, protected records, web, root handoff and first replay remain untouched. No GPU, new inference, actual replay, threshold search, nested worker, push or operational adoption was performed by this correction dispatch. The coordinator owns the next frozen replay and delivery; synthetic passes do not establish behavioral improvement.
