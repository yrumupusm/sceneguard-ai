# WEB-0002 independent review

2026-11-02. Independent review of the split experiment/video-review UI, saved-box evidence, and persistent user assessments. This reviewer owns only this document. No inference, new model, commit, live DB edit, browser operation, deployment, or service restart was performed by this reviewer.

## Review status

**Pass for the reviewed implementation, with the coverage/provenance limits below.** The assessment overwrite race, circular import, and evidence-display findings were fixed and independently rechecked. The final combined **59-test Python suite and ten Node fixture suites pass**. No unresolved blocking implementation finding remains at the 06:50 UTC checkpoint. Browser/deployment verification and live DB preservation evidence belong to the coordinator; this report does not certify those activities.

## Findings communicated to owners

| Finding | Consequence | Status |
|---|---|---|
| Fixed-height experiment flex list permits rows to shrink | With many entries, content can overflow compressed rows instead of retaining readable natural heights. | Fixed in source: nonshrinking rows and single-line titles. Actual layout remains coordinator browser scope. |
| Friendly-label rewrite removes observation/routing/closure semantics | Removing raw IDs should preserve useful status and reason information. | Addressed with readable reason labels and applied/excluded counts; EXP48 fixture passes. Unknown reasons are labeled unconfirmed rather than invented. |
| Evidence images initially labeled only with decision PTS | An earlier observed box/frame could be mistaken for the decision frame. | Fixed: separate decision and evidence-frame PTS. The later addition keeps any preceding actual observation in a separate image with its own PTS. |
| New assessment history omits version, save time, and omission PTS | A superseded missed-event timestamp cannot be recovered from the visible history. | Fixed: all three are present in visible history. |
| Legacy review input still initially selects intrusion suspicion | The old manual-review selector appears alongside new unreviewed defaults. | Legacy panel is now labeled as existing manual review; new event, bbox, and omission assessments default to unreviewed and remain separate. |
| Null confirmation timestamp crashes evidence panel | Backend returns an explicit absent confirmation; unconditional `toFixed` replaced the entire evidence panel with an error. | Fixed; null-confirmation Node fixture passes. |
| Empty box list rendered without absence disclosure | An original frame could be mistaken for successfully boxed evidence. | Fixed: explicit no-saved-incident-box label, plain-frame alternative text, and visible image-error handling. |
| Editing one field before initial assessment GET suppresses every saved field | With stored `correct_event`/`good`, typing a note before GET resolves then saving posts `unreviewed`/`unreviewed` at the latest version, overwriting untouched judgments. | Fixed by coordinator with per-field dirty tracking; deferred-GET regression now preserves the draft note, stored event/bbox/reviewer, and version. |
| Direct incident-module import newly fails | `from webapp.incident import load_bundle` triggers app → saved_review → partially initialized incident. App-first startup and tests pass, masking the regression. | Fixed with lazy incident imports; direct import independently passes and four module-entry orders are covered by regression. |

## Acceptance checks

- Separate sticky navigation; one experiment per scrollable row; friendly visible identifiers.
- Retained playback position, selected source/result, and review draft state across route switching; hidden-video notification suppression.
- Only saved actual boxes; explicit frame/native PTS association; absent-box labels; safe registered media allowlist and immutable source binding.
- Separate user event, bbox, and omission assessments with unreviewed defaults, version conflicts, durable history, and preservation of legacy review data.
- Isolated regression tests after implementation readiness; no fixture or source inspection represented as actual browser validation.

## Evidence examined

The new backend reads the registered MVP manifest, source-frame hash, decision-stage consistency fields, image-path-stage hash, and saved frame evidence. It uses only `actual_boxes` associated with references or track IDs in the snapshot at the decision time, filters explicit prediction/unobserved markers, validates normalized coordinates and native PTS/time base, and never borrows a preceding box to draw on the decision frame. The renderer decodes the exact mapped playback frame and draws saved coordinates; it does not load a model or perform detection/tracking/flow. Still endpoints authorize registration/card/source binding, use the existing path allowlist and symlink-rejecting file opener, verify the original video's hash, and pass an already authorized file descriptor to a fixed helper.

A read-only invocation against the real saved `007-acceptance-v2` manifest returned first suspicion at 55.633333 seconds (native PTS 854528, time base 1/15360, two associated saved actual boxes) and confirmation at 72.133333 seconds (native PTS 1107968, same time base, no associated box). The separately timed preceding images use 55.466667 seconds/native PTS 851968 and 71.566667 seconds/native PTS 1099264 respectively, each with one saved referenced box; they do not alter the decision frame's box list. These were endpoint-data/source checks, not visual semantic validation or browser playback.

The preceding-image helper considers only explicit saved references strictly earlier than the decision, resolves their own source-frame/native-PTS mapping, excludes unrelated track fallback, and returns unavailable if no qualifying box exists. The frontend states that this is an earlier actual observation, not a decision-time box or same-person confirmation. An independent transient DOM fixture verified the two timestamps, distinct image URLs, and current-frame absence label.

User event assessment and bbox quality are independent fields in a versioned incident assessment. Video omission has its own subject, optional source timestamp, note and history. The new `saved-result-assessments.sqlite3` sidecar is separate from legacy `incident-reviews.sqlite3`; automatic cards are not updated. Same-origin JSON, source binding, card membership, allowed values, bounded notes, integer versions and omission source-window bounds are checked. Atomic transactions reject stale versions and retain prior history. Fixture tests reopen persisted storage and compare the legacy DB bytes before/after; this does not establish live runtime DB preservation.

The route switch hides/shows existing page containers and pauses hidden media without replacing the media/review DOM. Source/result selection, playback position, route scroll, and unsaved drafts therefore survive route switching; catalog polling retains existing media. The route's hidden state is set before pausing, and pause-triggered refresh checks hidden ancestry. Friendly incident numbers replace opaque card IDs, while meaningful source filenames remain visible. These findings are source/fixture evidence; physical sticky positioning, playback, and visual layout require the coordinator's browser checks. Changing source/result selections is distinct from changing routes and can rebuild that source's panel.

## Coverage and provenance limits

- The coordinator/backend owner report **13 registered MVP results and 63 older EXP registrations** in the current service configuration. The 45 analyzed outputs are not all individually registered for the new incident-review flow. This report does not certify all 45 videos as delivered or visually reviewed.
- The new boxed-still adapter supports registered MVP manifests with saved frame mappings. Older EXP media remain available through their existing views; absent/incompatible mappings are not reconstructed through inference.
- Existing manifests hash-anchor cards and source-frame maps. The old decision-stage file is checked for consistency against the cards digest, but its own hash is not anchored in the old manifest. That stage supplies the paths-stage hash, which in turn validates the actual-box JSONL. This is useful local consistency checking, not a fully cryptographically anchored observation chain.
- Exact-frame availability, a saved box, and an automatic confirmation do not establish correct object localization, person identity, or event truth. The separate user assessments remain the source of those human judgments; no accuracy claim follows from these tests.

## Executed checks

Canonical interpreter: `/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python`, with `PYTHONPATH=.:tests`:

```text
python -m unittest tests_orca.test_web tests_orca.test_incident_web \
  tests_orca.test_presentation tests_orca.test_editorial \
  tests_orca.test_saved_result_review test_exp0046_web test_exp0047_web \
  test_exp0048_web test_exp0049_web test_mvp_registration
```

**Initially 55 tests passed; after the import/prior-observation edge cases, the same command passed 59 tests.** The new renderer test uses an isolated synthetic video in the existing CPU environment and checks decoded-frame color, drawn-box pixels, and refusal of an inexact frame. Additional cases cover absent confirmation, mismatched native clocks, empty-video omission, direct import order, and preceding observations without future/unrelated references. Tests use temporary fixture storage, not live DB writes.

Ten Node suites passed again after the final frontend changes: `test_experiment_library`, `test_cards`, `test_mvp_web`, `test_incident_web`, `test_incident_review`, `test_exp0047_web`, `test_exp0048_web`, `test_exp0049_web`, `test_routes`, and `test_assessments`, all under `tests_orca/`. These exercise DOM/logic fixtures, including route switching and hidden-media pause, causal state/rewind, existing review conflicts/drafts, new unreviewed defaults, explicit evidence PTS, absent confirmation, absent boxes, and the fixed delayed-GET race. They do not constitute real-browser validation. `git diff --check` passed.

## Reviewed implementation identity

SHA256 at the final 06:50 UTC checkpoint:

```text
webapp/app.js              4216caf26cb0b80ef67870c2a563ba64a29c45b000e976622d2768dbe777e836
webapp/app.py              3a7d68e3ea4a04a291c8b773189dc3ccf456a4c8651b3cf699c8a1aa233f6524
webapp/index.html          a2bcf7e28436888b5e20d4f4fb729cff37a8033d3d040fcc814a6c06f2c6b9ca
webapp/style.css           df2e3b9258113020e4d91ef299ddd287b7fe2cf137dedabf43ac81f542612546
webapp/assessment_store.py 1cb488cfd9817e387cd2d7149cd1523012780ed0c8052255e5e6f029ae1ff961
webapp/evidence_image.py   d5b0ec6977b153aad984f74ac40438d1612b2209a1fa22684e8ae58fd4a9de2c
webapp/saved_review.py     ab2d94e798d6f91b13420bbad29827deee441547e3d10da8380c82c18acbfd17
```
