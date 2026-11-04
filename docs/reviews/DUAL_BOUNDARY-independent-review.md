# Dual-boundary independent review

## Final actual-result verdict — valid comparison, candidate rejected

2026-11-04. Independently audited completed **run-002**, all 45 videos and all 52 resolved official events. The saved comparison is internally reproducible, but the candidate fails its behavioral objective: **confirmation TP 39→0, FN 13→52, gained 0, lost 39, retained 0**. Suspicion TP/FP/FN remain **51/10/1**, with all 51 earlier matches retained and no new or lost suspicion matches. The eight early confirmation notices disappear because **all 49 confirmation notices disappear**, not because they become later valid confirmations. Do not adopt this candidate as the default or describe it as an early-confirmation success.

| Saved-output measure | Before | After |
| --- | ---: | ---: |
| Confirmation TP / FP / FN | 39 / 1 / 13 | 0 / 0 / 52 |
| Suspicion TP / FP / FN | 51 / 10 / 1 | 51 / 10 / 1 |
| First suspicion notices | 112 | 118 |
| Early first suspicion notices for matched references | 29 | 31 |
| Unreviewed-time first suspicion notices | 83 | 86 |
| Unscored suspicion predictions | 58 | 57 |
| First confirmation notices | 49 | 0 |
| Early first confirmation notices for matched references | 8 | 0 |
| Verified-negative first suspicion / confirmation notices | 3 / 0 | 3 / 0 |

All eight earlier early-notice cases (010,011,016,029,030,032,038,041) lose their official confirmation match and have no later confirmation anywhere in that video. For 010, the old first confirmation at 59.933333s, first matching evidence at 62.133333s, official start 62.066667s and approximate user climbing onset 63s remain distinct. New confirmation is absent; its delay is undefined. The limited official-reference confirmation evaluator returns F1=0 and precision=null for the zero-prediction result; this is not an overall behavioral F1 or generalization claim. 006's unresolved reference and 008's semantic-review hold are retained.

Recomputed both before/after reports and aggregates with the frozen evaluation code, extracted predictions independently from all 45 saved card files, and recomputed the entire `comparison.json`: exact agreement. Compared all 39 lost event identifiers, all 52 remaining misses and every notice relation with the public result report. Verified all **31 public metric values and source SHA256s** at review time. The report's failure/nonadoption conclusion is supported. No rule analysis, video decode, tracking, flow, model inference or visual identity review was repeated.

### Final provenance and preservation

The executed root revision is `d40fe5011956acba47bd04b3a17dbf224b325f10`. All package and adapter bytes equal independently reviewed `2cdfc3e`; all **92 snapshot files** equal their committed bytes. `provenance.status=replay_complete`, completed videos=45, errors empty, wall=720.872907s, worker CPU sum=2557.409184s. Independently rehashed **221 protected paths** (204 original inputs plus 17 generated profiles/manifest), **47 generated execution inputs**, **19 archived geometry snapshots** and the 92 code snapshot files: all match. All 45 worker import paths stay within the snapshot, and their stored rule-stage/new detector/tracker/flow counters are zero. This is preservation of the enumerated saved inputs; it is not a new hash audit of raw media, DBs or receipts.

| run-002 artifact | SHA256 |
| --- | --- |
| `provenance.json` | `2ba5d2d7d9e8ea06666e09b5aa10c885350370b0c9a825fae2074c91c9df86e0` |
| `summary.json` | `e86c01dd4574950f837f2c873675be4b87d0cff2a2a797bc867d01df87f5ef23` |
| `comparison.json` | `dfe23f1362febb23edf5c405e37dc0092b9d764ed3118d85eaa150400c7763f7` |
| `after-manifest.json` | `fd35ca9968ddb45c6c3bef84d51e39b7f80babb8ae484f481cc4e89c4d1d00f8` |
| `after-report.json` | `ca1b874da30d77871e9b92aaf8007eed0ad9a328094967388c5276fb0447354e` |

### Nine outward-focus cases and saved refusal chronology

Each of the nine previously missed target references remains missed; none has a new confirmation anywhere in its video. The table shows the first **candidate emitted inside the target official interval**, its bound observation run, and that run's first recorded adjacent-box competition. This is saved bookkeeping evidence, not the action onset, a person count or identity truth.

| Video / target official row | In-window candidates / bound | First in-window candidate (s) | Bound run | First competition on that run (s) | In-window recorded decision reasons |
| --- | ---: | ---: | --- | ---: | --- |
| 013 / 000 | 3 / 3 | 62.600 | 00551 | 62.500 | ambiguity 3 |
| 015 / 000 | 5 / 5 | 60.400 | 00514 | 59.367 | ambiguity 6; expired association 1 |
| 021 / 000 | 18 / 18 | 69.433 | 00271 | 69.467 | ambiguity 21; expired association 2; disconnected path 1 |
| 028 / 000 | 10 / 10 | 60.667 | 00083 | 60.567 | ambiguity 10; expired association 1 |
| 034 / 000 | 13 / 13 | 26.967 | 00044 | 27.100 | expired association 11; ambiguity 9; unstable origin, disconnected path and wait 1 each |
| 036 / 001 | 7 / 7 | 27.000 | 00228 | 26.967 | ambiguity 7 |
| 043 / 000 | 7 / 7 | 68.467 | 00341 | 68.467 | ambiguity 9; wait 2; unstable origin and disconnected path 1 each |
| 044 / 000 | 2 / 2 | 74.300 | 00052 | 74.233 | ambiguity 2; unstable origin, wait and disconnected path 1 each |
| 045 / 001 | 1 / 1 | 14.300 | 00122 | 11.967 | ambiguity 4, including earlier pending runs |

The full run IDs are prefixed `observation-`. 021 first records a disconnected path at 69.433s before the competition veto at 69.467s. 034 first records unstable origin at 26.967s before competition at 27.100s. 044's second candidate at 77.967s records unstable origin, then waiting/disconnection and competition at 78.900s. Thus absence of a confirmation cannot be attributed exclusively to a single guard. All nine target intervals contain bound candidates, so these misses are not simply a missing-candidate or entirely unbound-input outcome. Their saved in-window snapshots contain no opposing exit; some contain an origin but no entry. These are sparse audit snapshots, not proof that all underlying measured paths lack an origin or crossing.

028's previous 69.300s confirmation is after its official end 69.233333s and disappears without becoming an in-window match. In 036 the early row001 stays missed and the distinct later row000 match is lost. In 045 the early row001 stays missed and the later row000 match (old notice 83.600s) is lost; this does not establish person-specific bidirectional truth. For 010, the 62.133333s candidate binds by same-frame containment to run00504, already marked competing at 61.200s; the 63.433333s portal candidate binds run00520, marked competing at 63.100s. Neither yields a confirmation.

Across all videos, 986 source candidates are preserved and 963 bind to observation runs. Audit totals are 128,604 adjacent-frame competition records, 1,216 ambiguity decision changes, 804 association-horizon expiry changes, 79 disconnected-path changes, 33 unstable-origin changes, 71 wait changes, 35 missing-origin/entry loss changes, six missing ordered finite-passage changes and 58 handoffs. These counts have different units and are not independent failures, people or physical events. The graph considers all eligible raw boxes, including competing footprints discarded by birth deduplication, and its veto persists through the run lineage; it can suppress later evidence after competition has gone away. This mechanism is verified in code and synthetic tests and is present in saved refusal chronology, but no ablation was run to assign each actual miss solely to it. Vehicle/occlusion/identity causes and a claimed benefit from relaxing the guard remain unverified.

### Recorded diagnostics inside each of the 52 missed reference intervals

This table is an audit index, not new ground truth. Candidates are source events emitted in the half-open official interval; bound is their initial binding count. Reasons count only saved `followup_audit` rows with a `source_decision` timestamp inside that interval, including earlier still-pending runs. The implementation suppresses duplicate negative-reason logging, so an empty interval is **not** absence of an active veto. Origin/entry/exit columns count their presence in those saved snapshots, not distinct physical passages. In particular 004 has two unbound candidates, while 042 has no new in-window candidate; other pending evidence may still exist.

Codes: **A** competing/untrusted successor; **H** association horizon expired; **D** disconnected actual box path; **O** origin unstable; **W** waiting since actual observation; **M** loss missing origin or measured entry. Official row `000` means `official-row-000`, etc. Every row below has confirmation FN=1 after replay.

| Video | Official row | In-window candidates | Bound | Recorded reason changes | Origin / entry / exit snapshots |
| --- | --- | ---: | ---: | --- | --- |
| 001 | 000 | 21 | 20 | H:20,A:17,D:2,O:1,W:1,M:1 | 0/0/0 |
| 002 | 000 | 5 | 4 | A:5,D:1,W:1,H:1 | 1/0/0 |
| 003 | 000 | 24 | 24 | A:26,H:12,D:1,W:1 | 1/0/0 |
| 004 | 000 | 2 | 0 | none | 0/0/0 |
| 005 | 000 | 8 | 6 | A:7,D:1,W:1,H:1 | 0/0/0 |
| 007 | 000 | 8 | 8 | A:4,H:3 | 0/0/0 |
| 008 | 000 | 7 | 7 | A:7 | 0/0/0 |
| 009 | 000 | 7 | 7 | A:9,H:3 | 0/0/0 |
| 010 | 000 | 3 | 3 | A:2,H:1 | 1/0/0 |
| 011 | 000 | 7 | 7 | A:5,H:3,D:1,W:1 | 0/0/0 |
| 012 | 000 | 4 | 4 | A:5,D:1 | 0/0/0 |
| 013 | 000 | 3 | 3 | A:3 | 0/0/0 |
| 014 | 000 | 21 | 21 | H:20,A:19,D:1 | 0/0/0 |
| 015 | 000 | 5 | 5 | A:6,H:1 | 3/0/0 |
| 016 | 000 | 7 | 7 | H:6,A:5 | 0/0/0 |
| 017 | 000 | 5 | 5 | A:6,H:3 | 0/0/0 |
| 018 | 000 | 11 | 11 | A:8,D:2,H:1,W:1,M:1 | 0/0/0 |
| 019 | 000 | 8 | 8 | A:7,H:6 | 0/0/0 |
| 020 | 000 | 11 | 11 | A:18,H:7 | 3/1/0 |
| 020 | 001 | 4 | 4 | A:4,H:2 | 1/0/0 |
| 021 | 000 | 18 | 18 | A:21,H:2,D:1 | 0/0/0 |
| 022 | 000 | 13 | 12 | A:12,H:2,D:1 | 0/0/0 |
| 023 | 000 | 4 | 4 | A:5,H:2,O:1,W:1,D:1 | 0/0/0 |
| 024 | 000 | 2 | 2 | H:4,A:1 | 2/0/0 |
| 025 | 000 | 12 | 12 | H:11,A:9 | 0/0/0 |
| 026 | 000 | 3 | 3 | H:6,A:2 | 0/0/0 |
| 027 | 000 | 3 | 3 | A:3,H:3,M:2,D:1,W:1 | 0/0/0 |
| 028 | 000 | 10 | 10 | A:10,H:1 | 0/0/0 |
| 029 | 000 | 9 | 8 | A:11,H:7,D:1,W:1 | 1/0/0 |
| 029 | 001 | 5 | 4 | A:4,H:1,D:1,W:1,M:1 | 0/0/0 |
| 030 | 000 | 13 | 13 | H:10,A:8 | 0/0/0 |
| 031 | 000 | 53 | 53 | A:54,H:51,W:8,D:7,M:5,O:2 | 5/0/0 |
| 032 | 000 | 4 | 4 | A:4,H:3 | 0/0/0 |
| 033 | 000 | 6 | 6 | A:11,H:4,D:1 | 0/0/0 |
| 034 | 000 | 13 | 13 | H:11,A:9,O:1,D:1,W:1 | 1/0/0 |
| 035 | 000 | 1 | 1 | A:1 | 0/0/0 |
| 035 | 001 | 2 | 2 | A:2 | 0/0/0 |
| 035 | 002 | 6 | 5 | A:6 | 0/0/0 |
| 036 | 001 | 7 | 7 | A:7 | 0/0/0 |
| 036 | 000 | 15 | 15 | A:11,H:8 | 1/0/0 |
| 037 | 000 | 5 | 5 | A:2 | 0/0/0 |
| 038 | 000 | 47 | 47 | A:52,H:44,D:8,W:8,O:2,M:1 | 3/0/0 |
| 039 | 000 | 9 | 9 | A:14,H:3,D:1,W:1 | 0/0/0 |
| 039 | 002 | 14 | 14 | A:31,H:6 | 1/0/0 |
| 039 | 001 | 54 | 50 | A:55,H:36,D:1 | 6/0/0 |
| 040 | 000 | 4 | 4 | H:4,D:3,A:3,W:2,M:1 | 0/0/0 |
| 041 | 000 | 4 | 4 | H:13,A:1 | 0/0/0 |
| 042 | 000 | 0 | 0 | H:2 | 0/0/0 |
| 043 | 000 | 7 | 7 | A:9,W:2,O:1,D:1 | 0/0/0 |
| 044 | 000 | 2 | 2 | A:2,O:1,W:1,D:1 | 0/0/0 |
| 045 | 001 | 1 | 1 | A:4 | 0/0/0 |
| 045 | 000 | 41 | 41 | A:42,H:23,O:1,W:1 | 4/0/0 |

Only one in-window audit snapshot in this table records an entry: 020/row000 at 7.400s, outside origin, still ambiguous and with no exit. No snapshot in the table records an exit. This is an index of what was actually serialized; early returns and deduplicated logging prevent using it as a complete per-frame geometric diagnosis. No automatic parameter change, repeated rules replay or new human label was made from these findings.

## Frozen code verdict — accepted for comparison, distinct from failed behavior

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

The independent fixtures preserve input values, compare every causal prefix of both scoped and final activity timelines, and run the production backend/run builder without injected rule stubs. They cover exact candidate anchors and clocks, one physical outcome/one current evidence owner, no reuse by later candidates, finite polyline passage, actual absence versus EOF/source gaps, fresh versus stale direction, saved-point continuity/competition, old origins and sticky positives. The known-limit test intentionally measures suppression of a later fresh passage; it is not counted as successful recovery. `git diff --check` passed for the two owned review files. **The completed full45 comparison above rejects behavioral adoption despite these software-contract tests passing.**

## Actual execution audit — failed run-001 retained

The coordinator's first full45 attempt used root integration `de72c5ff538cf5351384d1afd9dd563aebb1cded`. Independently confirmed that all `sceneguard` files and `scripts/mvp_full_evaluation_adapter.py` are byte-identical to reviewed `2cdfc3e`. Runner SHA256 was `c2d86d3ca9fedc50b8452b1b70225326bb605e443b88a2408b4eb6b3665af9fc`, the prepared evaluator from `f429bfed7da07960724150aa3f03747bb31965fa`.

Canonical `outputs/validation/dual-boundary-passage-v1/run-001/provenance.json` reports **failed**, 0 completed videos, 45 worker errors plus one runner summary error, 33.043104s wall, and both protected-input/source-snapshot preservation flags true. Its SHA256 is `367d13e2a7507fef0e24a0902f8a124e9d832d11962855e7308fc12b40fe2bc8`. `candidate_replay_executed=true` records invocation, not completed decisions or performance.

Independently traced the worker failure to evaluator profile construction: it adds `inner_line` to a copied scene but byte-copies the portal with its old `scene_digest`. Production `PortalGate` correctly rejects that mismatch before lifecycle decisions. For C1 the new scene digest is `eeeb70e11ddded26d11cb990969719b0d07970b778b3cc31146961b27f556cfd`, while the copied portal references `38be973f80c83fadc5106df3f0a78ab1f7b20eb61eb35d5cbba24615cccb3e90`. The reviewer reported the mismatch promptly; the coordinator owns a narrow evaluator fix to rebind only the newly generated portal fingerprint, preserving original geometry/provenance and the failed run. **No candidate behavior metric can be inferred from run-001.** The subsequent fresh execution and its outcome audit are separate from this failure record.

### Narrow evaluator correction before run-002

Reviewed the binding-only runner correction committed by the coordinator as `d40fe50`; runner SHA256 `822c9783522356f520b2db6a7963fb49f4a551986ea7dd88391af174dc3bb469`. The original portal is validated against its original scene before copying; only the new copy's `scene_digest` is rebound, and that copy is then validated against the exact new scene. Existing profiles are compared by full values, and old/new digests are retained in the profile manifest. No rule, proxy, boundary, wait, direction threshold or truth was changed.

Independently ran all **17 evaluator tests**, then built the actual 45 mappings into a disposable temporary directory without calling analysis. All eight real `PortalGate` bindings validated; every new scene differed only by its exact `inner_line`; every new portal differed only in `scene_digest`; C5 retained five vertices; and all 17 original protected hashes matched before/after. This verifies profile integration rather than candidate behavior. The failed canonical run-001 remains untouched; the fresh run-002 must carry its own final provenance.

## Current review scope and conservative ambiguity limitation

The corrected candidate is reviewed for **saved-measurement comparison readiness only**. Code acceptance does not establish behavioral improvement, default adoption, person identity, physical crossing or release accuracy. Final frozen revision and test results are recorded separately from the historical failed checkpoint below.

The optional mode is selected in production by `scene.inner_line`. `RuleBackend.prepare` selects `DualBoundaryDirection`; `RuleBackend.confirmations` guards every seed instead of executing old positive classifiers; and `replay_scoped` selects the dual lifecycle before any legacy replay branch. Direct old existing-alert/visible/history/outward helpers also guard the field. In the dual lifecycle, only its causal measured-passage or directed-corridor-loss resolutions can confirm; no legacy inward/outward/delayed/ambiguous-loss/observed-continuation/preserved-seed path runs, and no automatic release is emitted. The unchanged no-inner-line branches are covered by the independently rerun legacy regressions.

The correction checks the complete adjacent actual-box association graph before advancing a run. Both predecessor and successor competition block lineage; birth deduplication and greedy tie-breaking cannot establish uniqueness. Across gaps, saved-point endpoints are counted by actual cache index before unique run mapping. The final selected design deliberately keeps an affected run ambiguous until a source-clock reset and propagates ambiguity through handoff. **A later complete, independently supported passage on that same run may therefore remain unconfirmed, even after the 60-second origin episode expires.** This is an explicit conservative recall limitation, not successful identity disambiguation or episode recovery.

Independent `test_known_limit_ambiguous_run_veto_suppresses_even_fresh_episode` demonstrates the limitation: competing boxes only at 0/.1s, a many-predecessor edge at .2s, unique stationary outside observations afterward, a new candidate at .6s and then a complete two-boundary passage. Both old and new candidates remain suspected. The test asserts the **present suppression**, not a successful fresh episode. A safe future recovery must both discard ambiguous origin/proof and prevent old pending evidence from consuming a fresh episode. The coordinator explicitly deferred that change before any actual comparison result was seen; it is not tuned from replay outcomes. Already confirmed passage remains sticky when later competition appears.

The draft correction tested from a single in-memory source load had `dual_boundary.py` SHA256 `b3d61cbe499f4dcaafd2ee8a79e5f65987fbe69adc4152037833db19c0e6d4f6`; the then-current 24 independent tests all passed. Commit-specific frozen acceptance is recorded above. Read-only actual geometry validation retained all eight contours, C5's five vertices and C8 endpoint reversal. The canonical draft-manifest SHA256 is `d9364ed671e0f4cb545af2bcdde9a321d423826737a07f92cd9b567892d7d56f`; all 17 protected registry/scene/portal hashes matched. Old manifest approval flags remain untouched; current authorization is the later explicit plan.

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
