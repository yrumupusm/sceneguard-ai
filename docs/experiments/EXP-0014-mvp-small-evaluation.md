# EXP-0014 — frozen small evaluation of EXP-0013 cached outputs

2026-10-28. **CPU extraction/evaluation completed for all 24 selected B/C records; behavioral validation and adoption remain pending.** This evaluates existing EXP-0013 outputs without inference, media decoding, model loading, settings changes or source-output edits. It does not repeat EXP-0013 or overwrite its report, metrics or review binding. Independent review, registration and delivery belong to the coordinator.

The [frozen manifest](../../configs/mvp_small_eval_manifest.json) has SHA256 `ec293844173fe8797b2e518ba1a01b98be2720f766fd4c27bf3d5f278a7186af`: 12 fixed, non-overlapping scheduled 5-second windows, four per source. Selection was retrospective after inference and public aggregate reporting, before the selected itemized B/C responses were read. These are outcome-aware development/diagnostic materials, with unresolved site independence. The [evaluation plan](../data/MVP_SMALL_EVALUATION_PLAN.md) and [observation errata](../data/EXP-0013-observation-errata.md) govern interpretation.

## Reproduction and trace scope

From this repository root, using Python 3 and the existing local cache:

```bash
python3 scripts/evaluate_mvp_small.py
python3 -m unittest tests_mvp.test_small_evaluation -v
# Focused evaluator plus unchanged runtime-state regression:
python3 -m unittest tests_mvp.test_events tests_mvp.test_small_evaluation -v
```

The evaluator uses only Python's standard library and the existing pure-Python parser/classifier. It reads the immutable selection, EXP-0013 report, two attempt loading-metadata files, six source `run.json` metadata files, six `windows.jsonl` files, and exactly the selected 24 sets of `input.json`, `window.json`, and `result.json`. It interprets selected JSONL rows only. It opens no merged events, unselected result files, CV cache, official-label files, video, processor arrays, model weights, queue or external service. No review clips were created.

B is attempt `49cad0749df04995bb55727d57946fec`, full-frame; C is `a546b67626e54ef79cdf9bee1c70b3bf`, fixed ROI, both recorded in [EXP-0013](EXP-0013-mvp-comparison.md). The actual attempt folders retain the historical EXP-0012 namespace; this does not change the source experiment attribution. Both cache metadata records bind the same recorded execution input hash `c3bd766c6b4ff7707b9ac6eb75a0d76300df7984ff9b0ff86475ae9c3f98e8fe`, code revision, and frozen generation settings. Method-specific config hashes/views, camera/source IDs, saved source-file hashes, source ROI and result ROI are checked. Qwen model identity is inherited from the EXP-0013 report and recorded input provenance; this evaluation does not independently reopen/re-hash weights or reconstruct processor tensors.

All **24/24** selected records have matching scheduled source/window intervals, actual sampled/native PTS and rational time bases, saved decoded-source RGB hashes, source metadata, JSONL row, window record, result pointer and reparsed output. All 12 paired PTS arrays and saved source RGB hashes agree across B/C. Each window has ten saved observations from its start through end minus 0.5s. This verifies cached numeric/hash provenance, without re-decoding pixels. Each result and input/window/log/source metadata file has its own SHA256 in the [sanitized item data](../../records/EXP-0014/window_reviews.json); missing/invalid pairing is represented explicitly and counted unavailable. All 88 consumed input files were rehashed unchanged before output writing. Source report SHA256 is `c24f2499bb139e33b1e1285e0a67edff6493dd08ad6d41e0936c9cc0da092b1e`.

The four C4/C results are exact fallback reuse of the selected B results, verified against B result-byte/raw-response hashes, window/attempt IDs, semantic input fingerprints, parsed answers and processor metadata. They have zero newly generated tokens and null generation time. They are four diagnostic records, not four independent ROI successes or evidence of an inference-speed improvement. Cost was not measured in this evaluation.

## Output presence counts and denominators

`Candidate absent` means an available scheduled output produced no climbing candidate. It is not a negative reference label or true negative. `Unavailable` includes missing/invalid pairing, parse failure, insufficient input, execution failure, and indeterminate-only output; a candidate together with indeterminate remains a candidate. Contact remains a separate runtime state and is not silently promoted to climbing. Each window counts once regardless of duplicate action words, number of people or merged-event coverage.

| Selection group | B candidate / absent / unavailable | C candidate / absent / unavailable | Windows per method | Reference scope |
|---|---:|---:|---:|---|
| All selected | 4 / 8 / 0 | 5 / 7 / 0 | 12 | 11 unknown, one partial positive presence |
| Primary | 2 / 1 / 0 | 1 / 2 / 0 | 3 | All unknown |
| Non-fallback diagnostic | 2 / 3 / 0 | 4 / 1 / 0 | 5 | Four unknown, one partial positive presence |
| C4 fallback diagnostic | 0 / 4 / 0 | 0 / 4 / 0 | 4 | All unknown; C reuses B |
| Partial positive subset (`d030_90`) | 1 / 0 / 0 | 1 / 0 / 0 | 1 | Presence only; already included above |

Calculation: within each method/group, `candidate + candidate_absent + unavailable = selected-window denominator`. Unavailable positive-presence cases stay in that subset's denominator. The partial-positive subset is not added to the group totals again. Full-window confirmed primary positive denominator = **0**, confirmed negative denominator = **0**, verified negative duration = **0 seconds**. There is one unique partial-positive diagnostic case, not two independent B/C events or three person-level events.

Accuracy, precision, recall, F1, FPR and hourly false alarms are **null** in [metrics.json](../../records/EXP-0014/metrics.json). Unknown labels, diagnostic selection, unverified common-boundary alignment and absent full-window negatives do not support those scores. Unknown predictions remain visible in the output counts. No independent-site/generalization or continuous-event recall claim is made.

For the existing results page, the `metrics[]` delivery contract contains six graph rows: B/C candidate-output counts, original-form schema counts, and completion claims lacking a climbing action. These are output/form/text diagnostics only. They are not accuracy or human-verified false positives. Behavioral score fields remain null. Each graph row points to the exact sanitized `window_reviews.json` SHA256.

## Item-level comparison

`Other` below means candidate absent. Every label stays exactly as frozen; all rows except `d030_90` have uncertain action truth. Full-window visual factuality, common monitored-boundary correspondence and person-level completion remain unresolved.

| Case / source | Scheduled seconds / window | Role / label provenance | B output | C output |
|---|---|---|---|---|
| `s007_early` / 007 | 0–5 / w000001 | Primary / unreviewed | Other | Other |
| `s007_preevent` / 007 | 47.5–52.5 / w000020 | Primary / unreviewed | Candidate | Other |
| `d007_boxchange` / 007 | 52.5–57.5 / w000022 | Diagnostic / partial AI visual review | Other | Candidate |
| `d007_official` / 007 | 62.5–67.5 / w000026 | Diagnostic / official reference only | Other | Candidate |
| `s030_time` / 030 | 50–55 / w000021 | Primary / unreviewed | Candidate | Candidate |
| `d030_84` / 030 | 82.5–87.5 / w000034 | Diagnostic / partial user moment | Candidate | Candidate |
| `d030_90` / 030 | 87.5–92.5 / w000036 | Diagnostic / partial user positive presence | Candidate | Candidate |
| `d030_eof` / 030 | 155–160 / w000063 | Diagnostic / unreviewed | Other | Other |
| `s013_early` / 013 | 0–5 / w000001 | Fallback / unreviewed | Other | Other, reused |
| `s013_mid` / 013 | 40–45 / w000017 | Fallback / unreviewed | Other | Other, reused |
| `d013_official` / 013 | 60–65 / w000025 | Fallback / official reference only | Other | Other, reused |
| `s013_late` / 013 | 120–125 / w000049 | Fallback / unreviewed | Other | Other, reused |

The only supported positive-presence comparison is the **scheduled** `d030_90` response: B and C each emit `stepping_over_boundary`. This agrees partially with the user's approximate climbing-presence observation; it does not establish explanation factuality, exact onset, identities, all three persons' coverage or crossing completion. No hit was obtained from the historical long merged events.

At `d030_84`, the user's standing/approach observation is moment-only. Neither its candidate nor its textual tension proves a false positive over the full 5 seconds. The 007 box-change observation came from ChatGPT's local visual review, not a user-confirmed negative action label. Official JSON intervals are only the manifest's prior selection references, not newly confirmed scene labels.

The EOF anchor is specifically **w000063, 155–160s, ten observations**, with candidate absence from both methods. The historical insufficient-data EOF tail and later overlapping candidates are outside the frozen selection and cannot replace this result. The all-person noncompletion observation belongs to **031**, not 030; no 030 completion/noncompletion label is inferred from it or from EOF processing.

## Parsing, evidence and completion are separate findings

| Dimension, denominator 12 per method | B | C |
|---|---:|---:|
| Strict original-form schema compliant | 4 | 8 |
| Schema valid after permitted whole-response processing | 12 | 12 |
| Outer JSON fence removed | 8 | 4 |
| `crossing_completion=observed` claims | 8 | 7 |
| Such claims without a climbing action | 4 | 3 |
| Candidate explanation describes climbing motion, claim only | 2 | 4 |
| Candidate explanation has explicit motion denial | 1 | 0 |
| Candidate explanation does not describe climbing motion | 1 | 1 |

The evaluator reparses raw responses with the unchanged parser and checks stored parser/classifier agreement. Original strict form and fence-recovered schema validity remain separate. All selected outputs are parseable after processing; this does not certify behavior or factual explanations.

Text diagnostics use documented narrow lexical checks for climbing/stepping motion and explicit lack of motion. They assess relationships **inside the answer**, not pixels. In B `s007_preevent`, the candidate explanation describes passage near an open gate without climbing motion. In B `d030_84`, the candidate explanation explicitly describes no movement; C's same-window candidate describes standing/approach without climbing motion. These tensions are preserved even though the runtime issued candidates. The priority failure type for further human review is **climbing/completion escalation unsupported by the answer's own action evidence**; it is not a measured false-positive rate.

All `observed` completion claims are unverified, including the partial-positive case. B `s007_early`, `d007_boxchange`, `s013_early`, `s013_mid`, and C `s007_preevent`, `s013_early`, `s013_mid` assert observed completion while listing only passage/waiting. These are separate completion-support diagnostics, not additional climbing candidates. C `d007_official` remains a candidate while its completion is indeterminate and its explanation includes uncertainty; that uncertainty does not erase the candidate.

The sanitized item file contains categorical statuses and numeric/hash provenance only: no model raw response, free-form explanation, media, private path, credentials or identities. `explanation_factuality` remains unresolved for every item. The coarse text checks are deliberately incomplete and cannot prove a factual hallucination or a correct action.

## Verification and remaining work

Initial evaluator-only run: **16 tests passed**; initial evaluator plus unchanged runtime-state regression: **20 passed**. After the delivery-schema correction, the current suite is **17 evaluator tests and 21 combined tests passed**; the new case calls the existing `orchestration.complete.metrics` validator and checks each diagnostic row's source-file hash. Reproduction commands above run this current suite. Portable synthetic fixtures cover source/window/PTS/hash matching; no merged-event rescue or unselected-result reads; unknown-not-negative; partial positive unavailable accounting; duplicate logs/actions; exact fallback reuse and corruption; 031-to-030 guard; raw-vs-stored parser, strict/fence form, behavioral state and completion separation; missing/invalid output; immutable-manifest rejection; deterministic sanitized results and unchanged source bytes/mtimes. These are implementation tests, not behavioral labels.

The evaluation is reproducible and ready for independent review. Behavioral evidence remains insufficient: three primary cases and the other diagnostic/fallback cases need scoped human scene review before scoring, and no full-window confirmed negative exists. The coordinator prepared six original-only 5-second clips for one consolidated local review; they are ignored from Git and contain no overlays. Their local paths are provided separately to the user. Both B and C remain on hold for behavioral adoption; no new model experiment or automatic follow-up is started.
