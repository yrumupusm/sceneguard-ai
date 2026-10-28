# EXP-0015-LABEL-R1 independent review

Date: 2026-10-28. Reviewed repository baseline: `d9e47b0167e26a636b309ac3fc2c624fc12df2bb` with the uncommitted artifacts bound below. Task: `task_ff0208b63e32`; dispatch: `ctx_155bbf7a2164`.

**Verdict: PASS for evaluation registration readiness of these exact report and metrics bytes. Behavioral performance remains unvalidated; adoption remains on hold.** No blocking or nonblocking correctness/privacy defect was found in the reviewed revision. This review does not certify completion registration, GitHub publication, browser delivery, or operational suitability; those remain coordinator-owned steps.

The review inspected the frozen label configuration, parent and revised sanitized records, implementation, tests, experiment report, manifest hash, and the pure `orchestration.complete.metrics` validator. Only this review document was added. No implementation, report, config, result, web code, or runtime state was edited; no commit or push was performed. Synthetic tests used temporary fixtures. No source media, raw model answers, model cache, weights, official annotations, GPU, inference, or runtime secrets were accessed.

## Exact artifact binding

All six SHA-256 values supplied in the dispatch matched the current files. The final registration verdict binds both the experiment report and metrics listed here; an edit to either requires renewed binding/review.

| Artifact | SHA-256 |
| --- | --- |
| `docs/experiments/EXP-0015-user-label-revision.md` | `f203c8948aff7c882a2428c52b5d7c4e79c9eef92e37d2141672da370a77c3ee` |
| `records/EXP-0015/metrics.json` | `e950fb042ad919f64346908e8b7bcfc64953c17e39c81c3c3ae0576dba1e7a14` |
| `records/EXP-0015/window_reviews.json` | `b82267a2c8a457a2dd505183c61fb0cffde886776970322e66176e69493de0d0` |
| `configs/mvp_small_eval_labels_r1.json` | `9f2deedaebe137250f1926bc07d0ef4213a6590249718f4be785594be7640bcd` |
| `records/EXP-0014/window_reviews.json` | `427d59cd0d8092a5fb69c936449be9301d1d302285e21381ec7e1d0ada672b1a` |
| `records/EXP-0014/metrics.json` | `433b932add64fb4c92e75860d13586f1cee6aa0e25b5a6ed5178eff108de1685` |
| `configs/mvp_small_eval_manifest.json` | `ec293844173fe8797b2e518ba1a01b98be2720f766fd4c27bf3d5f278a7186af` |
| `scripts/apply_mvp_small_label_revision.py` | `cd502405a6911356aea0143665e27fe34a78bc47c1019285043de378fe65fb39` |
| `tests_mvp/test_label_revision.py` | `6d35bc63bb2222d4ca2de4ef3d92f3e9b1326dcee67e540eaeb04e0536b72819` |
| `orchestration/complete.py` | `0b36f9dbcb92b69b22103e8204ec058d0450dbc97f81212875e241c86f37b956` |

The independent review additionally hashed the actual manifest file. The revision evaluator itself reads only the two fixed sanitized JSON inputs and its own implementation for hashing; its manifest check is a pinned binding, as the report accurately states. Media/result/cache hashes carried by the parent are preserved provenance, not a claim that this review reopened or rehashed those prohibited original artifacts.

## Labels, scope and observed failures

The configuration and both revised method rows match every specified review/case/source/window/interval binding:

| Review | Case | Source / window | Seconds | Role | User reference | B / C presence |
| --- | --- | --- | --- | --- | --- | --- |
| q01 | s007_early | E01_007 / w000001 | 0–5 | primary | no attempt/progress | absent / absent |
| q02 | s007_preevent | E01_007 / w000020 | 47.5–52.5 | primary | no attempt/progress | candidate / absent |
| q03 | d007_boxchange | E01_007 / w000022 | 52.5–57.5 | diagnostic | no attempt/progress | absent / candidate |
| q04 | d007_official | E01_007 / w000026 | 62.5–67.5 | diagnostic | attempt/progress present | absent / candidate |
| q05 | s030_time | E01_030 / w000021 | 50–55 | primary | no attempt/progress | candidate / candidate |
| q06 | d030_eof | E01_030 / w000063 | 155–160 | diagnostic | no person/event | absent / absent |

Each user observation covers exactly five scheduled seconds. The provenance records user review of original-only clips, not model-derived ground truth. Verification here checks faithful application of the dispatched user-label contract and frozen configuration; it is not a fresh visual adjudication or independent authentication of the original conversation.

q04 is positive for visible attempt/progress only. Its completion reference is `not_observed_clip_ends_before_complete`; it does not establish a completed crossing or subsequent outcome. Other completion references remain unassessed, with q06 additionally identifying no visible person. The historical `d007_official` case name does not make this an official-annotation label. Access rights, intent and whole-video normality are outside the labels.

The negative-window failures are retained explicitly: B candidates on q02/q05 and C candidates on q03/q05 conflict with reviewed no-crossing references. B misses the reviewed attempt on q04; C emits a candidate. C's actual q04 historical completion fields are `indeterminate` / `not_asserted`, and neither its candidate nor its explanation is promoted to user-confirmed completion or factuality.

`d030_90` remains a separate partial positive. The five unknown cases remain `d030_84`, `s013_early`, `s013_mid`, `d013_official`, and `s013_late`. None becomes negative or enters the six reviewed counts. Both d030_eof rows preserve `no_030_completion_label_from_031`; no source-031 observation transfers to source 030.

## Independent arithmetic and metric validation

The following counts were recomputed directly from current records with independently specified case sets, rather than accepted from the implementation's summary. Each cell is candidate / absent / unavailable; denominators count windows per method.

| Group | Denominator | B | C |
| --- | ---: | --- | --- |
| All selected | 12 | 4 / 8 / 0 | 5 / 7 / 0 |
| Primary reviewed | 3 | 2 / 1 / 0 | 1 / 2 / 0 |
| Diagnostic reviewed | 3 | 0 / 3 / 0 | 2 / 1 / 0 |
| All reviewed | 6 | 2 / 4 / 0 | 3 / 3 / 0 |
| Reviewed no-crossing | 5 | 2 / 3 / 0 | 2 / 3 / 0 |
| Reviewed attempt-positive | 1 | 0 / 1 / 0 | 1 / 0 / 0 |
| Partial positive | 1 | 1 / 0 / 0 | 1 / 0 / 0 |
| Unknown | 5 | 1 / 4 / 0 | 1 / 4 / 0 |
| Fallback diagnostic | 4 | 0 / 4 / 0 | 0 / 4 / 0 |

All 18 table rows satisfy candidate + absent + unavailable = denominator, including all unknown-label and reused-output counts. Each method has five unknowns overall, four of them fallback cases. C has four reused outputs in all-selected, unknown and fallback groups, and zero elsewhere; B has zero reused outputs. Those four C outputs are not independent ROI comparisons.

All numeric/boolean top-level metrics were checked: schema 1; extraction complete; 12 cases / 24 paired records; 24 valid traces / 0 invalid-or-missing records; 6 reviewed cases; 12 revised / 12 unchanged records; 5 confirmed negatives / 1 full-window attempt-positive; primary denominators 3 negative / 0 positive; diagnostic reviewed denominators 2 negative / 1 positive; 1 partial positive / 5 unknown cases; 25 scheduled no-crossing seconds; 2 frozen data inputs verified unchanged. “Full-window positive” concerns the reviewed window's attempt presence, not completed crossing.

The six graph rows have values `[2, 0, 2, 1, 2, 3]` and sample sizes `[3, 3, 6, 3, 3, 6]` in B-primary/B-diagnostic/B-all/C-primary/C-diagnostic/C-all order. Every graph source points to the actual revised records and its SHA-256 matches their current bytes. Parent, labels, manifest, implementation and item-result hash bindings also match actual permitted files. Accuracy, precision, recall, F1, FPR and hourly false alarms are all JSON null.

The report and metrics consistently limit these to descriptive results. Zero primary positives, the outcome-aware diagnostic positive, retrospective selection, shared sources/nearby windows, tiny denominators and reused fallback outputs prevent formal accuracy/F1/FPR, generalization, operational suitability or adoption claims. Test success and evaluation registration readiness do not resolve those limitations.

## Preservation, privacy and reproducibility evidence

Every parent row was paired by `(case_id, method)`. Exactly the three allowed label fields change on the 12 reviewed rows, with only `user_label_revision` added. Its parent-label snapshot, complete user label and provenance match their sources. Every other parent field is semantically identical, including predictions, action/form diagnostics, actual PTS, source/RGB hashes, trace comparisons, reuse evidence, completion, historical reference consistency and all provenance hashes. The 12 unrevised rows are identical under canonical byte serialization. Historical consistency fields remain explicitly historical; revised interpretation lives in the revision block.

Both files under `records/EXP-0014` match `git show HEAD:<path>` byte-for-byte. All inspected input/output files retained their bytes and modification times through the independent actual-data checks. The report's expected and actual artifact hashes match. No parent evaluation was overwritten.

The report/config/metrics and sanitized records contain no discovered identifying personal details, source-media payloads, absolute local artifact paths, credential values or raw model-answer text. Inherited `raw_response_present` and `raw_response_sha256` fields are booleans and hashes only. The metrics pass the existing conservative publication filter; record strings were separately scanned for absolute paths/token patterns and their inherited raw-response metadata inspected by type. This is evidence about these exact outputs, not a universal privacy guarantee.

Executed successfully:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests_mvp.test_label_revision -v
```

Result: **16 tests passed**. Coverage includes mapping/binding rejection, partial/unknown preservation, q04 attempt/completion separation, negative-window failures, unavailable-denominator handling, immutable arguments/predictions, graph hashes, fixed input access, duplicate/nonfinite JSON rejection, source-change detection, output redirection/overwrite refusal, and deterministic two-output CLI behavior on temporary synthetic fixtures.

The pure validator was also run directly on the actual stored metrics:

```bash
python3 -B - <<'PY'
import json
from pathlib import Path
from orchestration.complete import metrics
metrics(json.loads(Path('records/EXP-0015/metrics.json').read_bytes()), 'EXP-0015')
print('PASS')
PY
```

Additional read-only inline assertions independently recomputed every table and numeric metric, checked labels and all preserved fields, hashed each graph source, compared parent records with Git HEAD, and scanned sanitized output strings. Two calls to `revision.evaluate(root)` regenerated metrics and records in memory; both serializations matched both current output files byte-for-byte. Production outputs were not rewritten. Actual-data in-memory determinism and temporary-fixture CLI no-op/mtime preservation both passed.

No remediation is required for registration of the bound artifacts. Preserve the behavior-performance/adoption hold and exact hash bindings during coordinator integration; publication and browser verification remain separate delivery evidence.
