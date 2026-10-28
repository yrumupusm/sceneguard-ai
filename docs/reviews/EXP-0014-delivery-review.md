# EXP-0014 corrected delivery review

2026-10-28. **Registration readiness: ready for registration as a diagnostic evaluation delivery; the prior metrics-schema blocker and the test-total documentation finding are resolved.** No outstanding registration blocker was found in this review's scope. **Behavioral performance and B/C adoption remain unapproved** (`insufficient_evidence_human_review_pending`; 평가 준비 완료·사람 확인 대기). Registration readiness does not establish successful registration, publication, browser delivery, behavioral accuracy, or visual factuality.

This follow-up read `docs/reviews/EXP-0014-coordinator-review.md` first and preserves its historical verdict and bindings. Assignment: existing Run `run_3d23462a014a`, Task `task_054458e6e372`, Dispatch `ctx_b6f3685e735d`. The only retained file authored by this worker is this review. No source, experiment report, metrics, item data, manifest, or earlier review was edited; no commit or push was performed.

## Exact evidence binding

All three final artifact hashes supplied by the coordinator matched, including the replacement report supplied during this dispatch. This verdict applies to these bytes, not later revisions.

| Artifact | SHA256 |
|---|---|
| `docs/experiments/EXP-0014-mvp-small-evaluation.md` | `f6c591788b3cc740f4896ca0da5328b26e4817e958e9c0892dc57e70f39d1f75` |
| `records/EXP-0014/metrics.json` | `433b932add64fb4c92e75860d13586f1cee6aa0e25b5a6ed5178eff108de1685` |
| `records/EXP-0014/window_reviews.json` | `427d59cd0d8092a5fb69c936449be9301d1d302285e21381ec7e1d0ada672b1a` |
| `scripts/evaluate_mvp_small.py` | `3d53242c824cba4200d9ba7fe6765bb74608a72094ea41983183db6cf9fedfac` |
| `tests_mvp/test_small_evaluation.py` | `fec1c66bbaa8dd35d4f71cf0c8cb392f1171e6178aba188336774253329cf8d3` |
| `orchestration/complete.py` | `0b36f9dbcb92b69b22103e8204ec058d0450dbc97f81212875e241c86f37b956` |
| `configs/mvp_small_eval_manifest.json` | `ec293844173fe8797b2e518ba1a01b98be2720f766fd4c27bf3d5f278a7186af` |
| `docs/experiments/EXP-0013-mvp-comparison.md` | `c24f2499bb139e33b1e1285e0a67edff6493dd08ad6d41e0936c9cc0da092b1e` |
| `mvp/events.py` | `f6353d27fb2e963d21595cd733bb611db66e4f676fd6146e334dabafbcf94a14` |
| `vlm_batch/common.py` | `59ff4f586427373bdd4d9dd72fa1ef125ecc70924f81cc1254534741671a94cf` |
| `tests_mvp/test_events.py` | `67cf13fb6e0fb6781335ebc8d10a109c37758c3540584b63f79d09e8f1139450` |

The final metric implementation binding matches the evaluator above. The manifest, EXP-0013 source report, classifier, parser, and sanitized item-file hashes agree with the prior review; the EXP-0014 report, metrics and evaluator/test hashes intentionally differ. The canonical item-array hash remains `4178c85a188117329bc8099138be75c41837a87a84f5c34b7167ef670445d2c4`; it is distinct from the exact pretty-printed file hash used by every graph row.

## Contract and six displayed counts

A read-only invocation of the actual `orchestration.complete.metrics(document, "EXP-0014")` accepted the final JSON, loaded through that module's strict JSON parser. It now has `schema_version: 1`, matching `experiment_id`, and six complete metric rows. The registrar remains unchanged; its registration path calls this validator at `orchestration/complete.py:279`. No Registry instance, registration command, runtime configuration, database, or secret was opened.

Each row has a numeric count, `unit: window`, `sample_n: 12`, an explicit fixed development-sample scope, the text `not behavioral accuracy`, source `records/EXP-0014/window_reviews.json`, exact source SHA256 `427d59cd0d8092a5fb69c936449be9301d1d302285e21381ec7e1d0ada672b1a`, and `verification: source_json_sha256_checked`. Source hashing was independently checked; validator acceptance alone would not prove that a referenced source hash matches a file.

| Diagnostic | B | C | Denominator per method |
|---|---:|---:|---:|
| Scheduled candidate-output count, not correctness | 4 | 5 | 12 |
| Strict original-form schema compliance | 4 | 8 | 12 |
| Observed-completion claims without a climbing action | 4 | 3 | 12 |

These six values were independently summed from sanitized item fields, then compared with the graph rows and detailed summaries. All ten output-presence tables were independently recomputed, including unavailable, unknown-label and reuse counts. All selected counts remain B 4/8/0 and C 5/7/0 candidate/absent/unavailable; primary counts remain 2/1/0 and 1/2/0; non-fallback diagnostic counts remain 2/3/0 and 4/1/0; fallback counts remain 0/4/0 for both. The partial-positive subset is 1/0/0 for both and overlaps the diagnostic group.

The detailed report's numerical diagnostics remain consistent: postprocessed schema validity 12/12 each, removed fences 8/4, observed-completion claims 8/7, and candidate-text categories 2/1/1 for B and 4/0/1 for C (motion-described / explicit denial / no motion described). There are 12 unique windows and 24 method-window records, 11 unknown cases, one partial-positive case, and four reused C4/C records. These are not 24 independent events or evidence of independent ROI success.

All six behavioral metrics—accuracy, precision, recall, F1, FPR and hourly false alarms—remain null. Confirmed primary positive/negative denominators and verified negative duration remain zero. Every explanation-factuality field remains unresolved. No completion or person-level ground truth was introduced by the schema correction.

## Reproducibility and regression checks

The new `json_bytes()` serializer at `scripts/evaluate_mvp_small.py:40` supplies both the bytes hashed for graph provenance and the bytes written by the CLI at line 445. Reserializing the existing sanitized records in memory reproduced their exact file bytes, including the trailing newline. The canonical hash also reproduced independently. Regenerating all six delivery rows from the saved sanitized records reproduced the final rows exactly; every field returned by `aggregate()` matched the saved metrics. These checks used no real cached-answer evaluation.

`delivery_metric_rows()` at line 404 derives values from the existing aggregate summary and adds no behavioral scoring, parsing, inference, or source-cache reads. Its denominator is fixed at 12, consistent with the evaluator's hash-frozen manifest and mandatory 12-case selection. It is suitable for this fixed experiment, not a generalized variable-sized evaluator. The detailed result structure, null-score policy, source-mutation checks, and fallback treatment remain intact. No meaningful runtime regression from adding schema rows was found.

Executed once:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests_mvp.test_events tests_mvp.test_small_evaluation -v
```

**21 tests passed in 0.496s: 17 evaluator fixtures and four existing runtime-state regressions.** The new contract fixture at `tests_mvp/test_small_evaluation.py:247` checks validator acceptance, six rows, exact serialized-source hashes, denominators, synthetic B counts and null accuracy. This review independently checked both B and C final-artifact counts and every behavioral null, beyond that fixture's B-specific assertion. Existing tests passed for unavailable denominators, unknown-not-negative, fallback corruption, duplicate actions/logs, source/PTS/hash mismatches, form/completion separation, 031/030 provenance, deterministic sanitized output and source mutation detection. Fixtures create and clean temporary synthetic files; bytecode writes were disabled, and no real cached responses or media are used.

## Resolved finding and remaining limits

**Resolved low-severity finding — stale test totals.** The initially assigned report, SHA256 `1b196229ed54f084bd1b5ddfb9f27ef850c7a8e680394c059ac5103c03271e9e`, reported the pre-fix 16 evaluator and 20 combined tests. The coordinator corrected the report during this dispatch and supplied the replacement hash bound above. The final report at `docs/experiments/EXP-0014-mvp-small-evaluation.md:92` now distinguishes those initial runs from the current 17 evaluator and 21 combined passing tests, consistent with this review's run. Its added graph explanation accurately describes the six output/form/text counts without claiming behavioral correctness.

The final report was reread in full. The actual metrics validator, six-row regeneration/source bindings, behavioral nulls and all five report/metrics/items/evaluator/test hashes were checked again after the coordinator's correction. Metrics, item data, evaluator and tests were unchanged, so another test run was unnecessary. This worker did not edit the experiment report. The final report additionally attributes preparation of six local review clips to the coordinator; that operational statement was not independently verified here because opening media was outside this assignment.

The registration validator's public-data check accepted the metrics and report. A recursive inspection of the sanitized records found no raw answer, parsed/freeform answer object, explanation text, credential, or private absolute path; response-presence booleans and response SHA256 values are metadata only. The new graph rows contain only scoped numeric diagnostics and a public repository-relative source path.

No CCTV pixels, actual raw/freeform answers, media, weights, external services, network requests, GPU operations or runtime secrets were accessed. This follow-up did not repeat the earlier review's opaque source-cache hashing or independently reparse actual answers; its source-provenance conclusions rely on the unchanged item-file binding and the earlier review, plus the current pure-code and synthetic checks. Full real-cache CLI reproduction would read actual answers and write outputs, so it was deliberately outside the assigned review boundary. Registration, publication and browser verification remain coordinator work. Behavioral scoring, visual factuality, common-boundary alignment and B/C adoption still require appropriate human evidence and remain unapproved.
