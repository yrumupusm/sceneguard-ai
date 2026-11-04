# Dual-boundary independent review

## Frozen code verdict — ready for the comparison, behavior pending

2026-11-04. **Accepted for the authorized saved-measurement comparison:** `2cdfc3eb9966e69a4211035df6eea8fa21c41fcc`. The implementation checkout was clean before and after the final independent run. `sceneguard/dual_boundary.py` SHA256 was `267fce3936cdcd6b45f05a35eba36f2880b9e1ad503c4083e6aecc659648d3d1`. Reviewed the committed delta, then ran **559 tests with zero failures/errors/skips**: 25 independent review tests (19 using production `analyze_observations`), 39 implementation tests and 495 legacy regressions. The endpoint touch, contiguous competing-box inheritance and collinear self-overlap findings are fixed at this revision. No remaining reproduced false-positive correctness blocker was found within this review scope; the conservative run-lifetime limitation below is explicit and is not certified as successful behavior.

Final command, from the implementation checkout:

```bash
PYTHONPATH=.:tests:/home/jhc7484/dev/sceneguard-ai/sg-dual-boundary-review/tests \
  /home/jhc7484/dev/sceneguard-ai/.venv-cv-batch02/bin/python -m unittest \
  test_dual_boundary_review test_dual_boundary test_mvp_pipeline \
  test_visible_crossing test_existing_alert_crossing test_outward_crossing \
  test_gate_observation test_gate_observation_integration test_lifecycle_followup \
  test_incident_lifecycle test_incident_outcome_scope test_gate_activity_episodes \
  test_gate_episode_evidence test_directional_loss test_portal_births \
  test_incident_cards test_video_cards test_target_binding_contract \
  test_handoff_binding_contract test_stationary_origin_crossing_contract \
  test_delayed_raw_loss test_delayed_loss_binding_contract \
  test_delayed_loss_ownership_contract -q
```

The independent fixtures preserve input values, compare every causal prefix of both scoped and final activity timelines, and run the production backend/run builder without injected rule stubs. They cover exact candidate anchors and clocks, one physical outcome/one current evidence owner, no reuse by later candidates, finite polyline passage, actual absence versus EOF/source gaps, fresh versus stale direction, saved-point continuity/competition, old origins and sticky positives. The known-limit test intentionally measures suppression of a later fresh passage; it is not counted as successful recovery. `git diff --check` passed for the two owned review files. **Actual full45 comparison and behavioral adoption remain separate, pending the coordinator's frozen result artifacts.**

## Current review scope and conservative ambiguity limitation

The corrected candidate is reviewed for **saved-measurement comparison readiness only**. Code acceptance does not establish behavioral improvement, default adoption, person identity, physical crossing or release accuracy. Final frozen revision and test results are recorded separately from the historical failed checkpoint below.

The optional mode is selected in production by `scene.inner_line`. `RuleBackend.prepare` selects `DualBoundaryDirection`; `RuleBackend.confirmations` guards every seed instead of executing old positive classifiers; and `replay_scoped` selects the dual lifecycle before any legacy replay branch. Direct old existing-alert/visible/history/outward helpers also guard the field. In the dual lifecycle, only its causal measured-passage or directed-corridor-loss resolutions can confirm; no legacy inward/outward/delayed/ambiguous-loss/observed-continuation/preserved-seed path runs, and no automatic release is emitted. The unchanged no-inner-line branches are covered by the independently rerun legacy regressions.

The correction checks the complete adjacent actual-box association graph before advancing a run. Both predecessor and successor competition block lineage; birth deduplication and greedy tie-breaking cannot establish uniqueness. Across gaps, saved-point endpoints are counted by actual cache index before unique run mapping. The final selected design deliberately keeps an affected run ambiguous until a source-clock reset and propagates ambiguity through handoff. **A later complete, independently supported passage on that same run may therefore remain unconfirmed, even after the 60-second origin episode expires.** This is an explicit conservative recall limitation, not successful identity disambiguation or episode recovery.

Independent `test_known_limit_ambiguous_run_veto_suppresses_even_fresh_episode` demonstrates the limitation: competing boxes only at 0/.1s, a many-predecessor edge at .2s, unique stationary outside observations afterward, a new candidate at .6s and then a complete two-boundary passage. Both old and new candidates remain suspected. The test asserts the **present suppression**, not a successful fresh episode. A safe future recovery must both discard ambiguous origin/proof and prevent old pending evidence from consuming a fresh episode. The coordinator explicitly deferred that change before any actual comparison result was seen; it is not tuned from replay outcomes. Already confirmed passage remains sticky when later competition appears.

The draft correction tested from a single in-memory source load had `dual_boundary.py` SHA256 `b3d61cbe499f4dcaafd2ee8a79e5f65987fbe69adc4152037833db19c0e6d4f6`; the then-current 24 independent tests all passed. Exact frozen acceptance still requires the commit-specific rerun below. Read-only actual geometry validation retained all eight contours, C5's five vertices and C8 endpoint reversal. The canonical draft-manifest SHA256 is `d9364ed671e0f4cb545af2bcdde9a321d423826737a07f92cd9b567892d7d56f`; all 17 protected registry/scene/portal hashes matched. Old manifest approval flags remain untouched; current authorization is the later explicit plan.

## Historical follow-up checkpoint — 278c463 required corrections

2026-11-04. Reviewed frozen implementation `278c4637e2aea484e64604de66f79070a9ed9aed` in the implementation checkout (clean status). **Acceptance of that revision was withheld for the two reproducible correctness findings below.** The coordinator was notified immediately; the attempt to notify the original implementer directly returned `dispatch_inactive`, and the exact reproduction was relayed to the coordinator for a follow-up dispatch. No production files were edited by this reviewer.

The initial endpoint-touch counterexample is fixed: opposite nonzero anchors and every finite on-line observation now protect the bbox and saved-point paths. The original six independent tests pass. The preflight section below is retained as the earlier findings and evidence, not the current endpoint-fix status.

### Must-fix: contiguous geometric matching bypasses competition checks

Production `analyze_observations` calls the unchanged `InsideBirths` greedy run builder. In the new replay, a `connected()` same-run row goes straight to `PassageState.step`; competitor checks are only applied by `successor()` across a break. Thus a greedy alternating choice among plausible boxes can inherit a stable origin and confirm, with an empty `associations` list. One-to-many and many-to-one contiguous association must not supply unambiguous lineage merely because the run builder chose a winner. Preserve the legacy birth bookkeeping and apply this protection in the optional dual-boundary evidence layer.

Independent production reproduction uses outer x=.4, inner x=.6, y=.2..8, 0.2-height actual boxes and x proxies `.35,.36,.37,.41,.45,.50,.55,.60,.65,.66,.67` at 0.1-second steps. Add a second actual box shifted x=-.04 from frame 3 onward, with a distinct cache index and no saved points. Frozen code confirms at 1.0s; its origin, entry and exit actually alternate cache indices. Mirroring all x coordinates fails identically. The inverse fixture supplies two plausible source boxes (second shifted -.04) for the first three frames and one afterward; that also wrongly confirms. The tests use the actual production backend and its run construction, not caller-supplied runs.

### Must-fix: collinear self-overlap passes geometry validation

For outer `[[.4,.2],[.4,.8]]`, inner `[[.6,.2],[.6,.7],[.6,.4],[.6,.8]]` backtracks and overlaps itself, but `Corridor` accepts it. `intersection()` returns no hit for collinear segments, while adjacent edges are skipped entirely. The documented simple finite-contour contract requires rejecting adjacent backtracking and nonadjacent overlap. Ordinary collinear forward vertices may remain valid; this is input validation, not a request to change reviewed camera geometry.

### Follow-up tests and scope

The independent suite now runs **23 tests**, including **17 through production `analyze_observations`** using separately constructed fixtures. At `278c463`, three tests fail with four failing subcases: contiguous competition in both directions, many-source inheritance and the collinear malformed contour. The other tests pass, covering finite touch/endpoints, a five-vertex joint versus its chord, actual symmetric passage, all timeline prefixes including the activity layer, exact existing-alert anchors, latest-evidence ownership, no passage reuse by a later event, >3-second origins and 60-second expiry, sticky return, same-side return without release, unique saved-point occlusion with missing-box provenance, competing/absent/interrupted point support, actual absence wait, stationary and stale direction, EOF/source gaps, disabled direction, predicted input rejection and empty candidate streams. Synthetic bbox/point movements are not physical-body or CCTV truth.

Independently reran the implementation report's explicit suite of **528 tests: all passed** at the same clean frozen commit. This includes 495 legacy tests and 33 implementation tests; passing those tests did not expose the production competition issue. Required web review lookup again succeeded with `requests: []`, with no DB changes. No inference, tracking, flow, full45 replay or media upload occurred in this review. Canonical `outputs/validation/dual-boundary-passage-v1/run-001` had no ready result files at this checkpoint; actual behavior acceptance is separate and pending.

## Earlier preflight record

2026-11-04. **Preflight complete; frozen-code acceptance and actual replay review remain outstanding.** The implementation is authorized by `docs/DUAL_BOUNDARY_PASSAGE_PLAN.md`; the older draft's approval wait does not block that work. This review does not approve default adoption or claim behavioral improvement.

## Revision and scope

- Baseline reviewed: `40f22e79e2291dffde237e7e70b58a517b27ea35`.
- Read `AGENTS.md`, `docs/WEB_REVIEW_WORKFLOW.md`, the dual-boundary plan and inner-boundary draft description, plus `mvp_pipeline`, `visible_crossing`, `existing_alert_crossing`, `outward_crossing`, `gate_observation`, `exp0048_application`, `lifecycle_followup` and supporting lifecycle/geometry code and tests.
- Canonical read-only `pending --include-acknowledged` succeeded with `{"requests": []}`. No review answers were consumed or changed.
- Implementation checkout inspected read-only while it was being edited, still based on the same HEAD. The exact in-memory `dual_boundary.py` source used for the independent test run had SHA256 `1a98b827f296a49b6cee1d1c46d2d97b358ef994f0e2de2d32d7b0ddaf677609`. This is a draft-file result, not a frozen-commit verdict.
- Owned changes only: this report and `tests/test_dual_boundary_review.py`. No production edits, raw media access/upload, replay output mutation, truth changes, inference, tracking, flow computation, package installation or push.

## Reproduced must-fix: boundary touching is accepted as passage

In the inspected draft, `Corridor.intersections` records a hit when a measured proxy merely reaches a boundary. `PassageState.step` immediately stores that as entry/exit. It does not require opposite nonzero sides around an exact-on-line run, so a subsequent walk along the boundary and around its endpoint can complete a false finite passage.

Independent fixture: outer line `x=.4`, inner line `x=.6`, both spanning `y=.2..8`; stable outside proxy `(.35,.5)` approaches through the outer line, touches inner `(.6,.5)`, follows that line to `(.6,.85)`, goes around the endpoint to `(.65,.85)`, then returns parallel to `(.65,.5)` and dwells. All box steps meet continuity limits. The draft confirms, with stored exit at `.7s`, although the actual side change happened beyond the finite endpoint. The mirrored inside→outside path fails identically.

**Required correction:** finite passage needs opposite nonzero-side anchors, including the whole intervening on-line run, with finite membership throughout that run. A touch alone is insufficient. Retain valid exact-on-line crossing support and test C5 joints as well as straight endpoints. Existing `visible_crossing._finite_crossings` demonstrates the old single-segment on-line-run contract; adapting that principle must preserve the new polyline geometry. This is a reproducible correctness error, not a threshold preference.

Regression: `IndependentDualBoundaryReview.test_touch_then_walk_past_endpoint_is_not_finite_passage`. The fixture uses actual-box-style synthetic rows and explicitly documented 65%-height proxies; it is not a video/feet truth claim.

## Integration requirements supported by current code

| Concern | Baseline evidence | Required acceptance evidence |
|---|---|---|
| Old positive paths bypass a new helper | `RuleBackend.confirmations` independently calls preserved-alert validation, visible crossing, and classify/history/outward loss. `replay_scoped` can later produce inward loss, outward-crossing loss, observed crossing and delayed raw loss. | With an active inner boundary, exercise all reachable positive entry points through the actual selected backend; central gating or equivalent complete coverage must prevent legacy confirmation bypass. Without an inner boundary, preserve legacy behavior. |
| Active backend differs from an isolated helper | Baseline `RuleBackend.prepare` instantiates `SavedGateDirection`; its lifecycle call sets `observe_gate_crossings=False`. Observation-continuation tests explicitly construct another engine and enable the flag. | Verify the implementation and evaluation entry points actually select the dual-boundary backend. Passing new helper tests alone is insufficient. |
| Origin disappears from a rolling window | `visible_crossing_decision`, `outward_loss_decision`, `GateObservationDirection._origin_support` use 3-second history; `replay_scoped` also expires `crossing_sources` after that horizon. | Retain a stable measured origin through continuously associated corridor/unclassified observations beyond 3 seconds, bounded by explicit episode/association validity. Test source gaps, stale same raw ID, box/scale jumps and later unrelated people. Do not solve by only enlarging the rolling window. |
| Competition can differ between positive proof and handoff | `_stable_passages` chooses one same-frame candidate by coverage/cache index. `followup_run` and the replay's destination counter separately check successor/source competition later. | Positive passage must itself reject competing plausible boxes and many-to-one inheritance. Tiebreaks may organize evidence but cannot establish identity. Repeated windows/duplicate detections cannot create extra independent support. |
| Loss alone can confirm legacy inputs | Existing outward test has origin x=.57→.54 with common boundary x=.5: the legacy outward-loss helper confirms without a measured crossing of that line. History/inward loss similarly relies on encounter and direction. | An active boundary must not silently inherit that legacy positive. If directed corridor disappearance remains an explicitly supported hypothesis, label its missing opposite-side observation and basis separately from measured two-boundary passage; test stationary terminal context and same-side return. |
| Outcome ownership and sticky positives | `ScopedIncidentLifecycle` routes observed/loss outcomes to one owner/anchor, but non-delayed `preserved_confirmation` bypasses that routing. The base lifecycle preserves already-confirmed status. | New positives need one stable physical-evidence identity and appropriate ownership, including retries/handoffs/newer candidates. Do not reuse one passage to confirm older unrelated evidence; do not erase a genuinely completed inside→outside passage after return. |
| Future rows and EOF | Visible/existing-alert paths explicitly use a prefix. `ObservationHistory.advance` requires ordered frames; the pipeline deliberately does not flush a final loss at EOF. | Compare each decision on the prefix with that decision when future rows are present; check new caches/retained origins, event binding, associations and proof timestamps. EOF/data gaps cannot fabricate absence or destination dwell. |

These are acceptance constraints, not a demand for a specific class hierarchy or unrelated redesign. The coordinator received actionable findings before this report was finalized.

## Geometry, provenance and limits

The two contours are image-space annotations. Neither a box bottom nor its 65%-height point reconstructs hidden feet or calibrated ground-plane crossing. The baseline already uses differing proxies: visible crossing uses 65% height; existing-alert and continuation crossing use bottom centers; gate proximity uses box centers. The new evidence must identify its proxy and use compatible geometric evidence for a claimed passage, without quietly combining unrelated points into a synthetic crossing.

C5 has five inner vertices, not a single straight chord. Finite intersections, segment order, orientation, bends, shared vertices, exact touches and endpoint extension need explicit tests. Segment-normal changes near a bend must not manufacture progress; interpolation between adjacent observed samples must be labeled interpolation. Missing-box intervals bridged by saved points must retain the source box/point references and ambiguity, and must never be described as continuously measured boxes. Reject malformed/nonfinite/self-intersecting geometry; preserve the approved outer line and original input revisions.

Early-confirmation correction must distinguish a stationary or jittering box at the edge from actual movement through both sides. Stable observation count alone cannot do that. A person initially stationary may later genuinely cross, so the stationary-origin case must remain eligible once movement is measured. Object insertion or posture shifts may move the box proxy without actual body passage: this remains unvalidated behavior unless independent visual evidence establishes it. Do not tune proxy fractions, waits or motion cutoffs to the eight known early examples.

An explicit episode bound is compatible with preventing unlimited origin transfer; no numerical bound is certified optimal by this review. Loss after entry/progress is weaker evidence than observed opposing-side arrival and must be reported as such. This preflight does not settle camera-specific contour adequacy, physical passage accuracy, identity accuracy or the practical early/late tradeoff.

## Tests actually run

Baseline command, from this review worktree:

```bash
PYTHONPATH=.:tests /home/jhc7484/dev/sceneguard-ai/.venv-cv-batch02/bin/python -m unittest \
  test_visible_crossing test_existing_alert_crossing test_outward_crossing \
  test_gate_observation test_gate_observation_integration test_lifecycle_followup \
  test_target_binding_contract test_handoff_binding_contract test_delayed_raw_loss \
  test_delayed_loss_ownership_contract test_stationary_origin_crossing_contract test_mvp_pipeline
```

Result: **195 tests passed**. Initial runs in `.venv-orca-lab` and `.venv` each reached 194 passes and one import error (NumPy and OpenCV respectively); using the existing CV environment resolved the environment issue without installation.

Independent candidate command, from `/tmp` to avoid importing the review checkout's baseline package:

```bash
PYTHONPATH=/home/jhc7484/dev/sceneguard-ai/sg-dual-boundary-impl:/home/jhc7484/dev/sceneguard-ai/sg-dual-boundary-review/tests \
  /home/jhc7484/dev/sceneguard-ai/.venv-cv-batch02/bin/python -m unittest -v test_dual_boundary_review
```

Result against the draft hash above: **6 tests run, 5 passed; the finite-endpoint touch test failed in both directional subcases**. Passing cases cover symmetric actual two-boundary passage, >3-second corridor origin retention, stationary-only rejection, missing destination dwell in a prefix, and sticky positive after continuous return. The exact-hash rerun loaded the source bytes once into memory before executing the suite to avoid attributing another worker's simultaneous edits to the tested bytes.

The independent suite deliberately skips when `sceneguard.dual_boundary` is absent at the baseline revision. That skip is not candidate acceptance. Final review must verify all six execute on the frozen implementation and extend integration/association/C5 coverage as required. These synthetic results do not measure CCTV behavior.

## Outstanding frozen-code and replay review

The coordinator will provide the frozen implementation revision and result artifacts in a subsequent dispatch. Recheck the reproduced endpoint error, all active confirmation paths, source binding/competition, physical outcome ownership, geometry validation, no-future leakage and legacy-input parity against that exact revision. Inspect configuration and input/code/boundary hashes before accepting the stored-measurement comparison.

Maintain all 45 videos and official 52 events: baseline confirmed 39/52, suspected 51/52, and eight early first confirmations are comparison facts supplied by the approved plan, not independently recomputed in this preflight. Report lost matches, new matches, remaining misses, first-confirmation clocks and suspicious/duplicate/unreviewed evidence separately. Official-window earliness and user-reviewed 010 climbing at approximately 63s versus its prior 59.933s confirmation are distinct references. Preserve 006 time uncertainty and 008 semantic-review deferral. Do not convert tests, raw candidate counts or retained origins into accuracy or a generalization claim.

No actual 45-video replay, official matching recomputation, final implementation acceptance or default adoption was performed by this preflight dispatch.
