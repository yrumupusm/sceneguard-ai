# EXP-0015 — User-confirmed window label revision

- Date: 2026-10-28. Parent evaluation: EXP-0014; underlying saved B/C predictions: EXP-0013.
- Result: six user-confirmed 5-second labels applied to 12 matching B/C records. The other 12 records, including partial-positive `d030_90`, are unchanged. CPU revision and integrity checks passed; behavioral validation and model adoption remain on hold.
- Implementation baseline: `d9e47b0167e26a636b309ac3fc2c624fc12df2bb` plus the uncommitted implementation identified below. No commit or push is performed by this worker.

## Inputs, provenance and label scope

The only evaluation data inputs are [the frozen revision](../../configs/mvp_small_eval_labels_r1.json) and [sanitized parent records](../../records/EXP-0014/window_reviews.json). The user supplied these six labels after viewing original-only local review clips. This revision does not open media, raw model answers, model caches, weights, official annotation files or a GPU. It does not run inference or change the selection, predictions, sampling or model settings.

User confirmation covers the **scheduled 5-second window only**, and visible boundary-crossing **attempt or progress**. It does not establish access rights, intent, later events, or whether a whole video is normal. `q04` is attempt-positive: the clip ends before the person has fully crossed, so **completion was not observed before clip end**. This is not a completed crossing label or proof about later completion. Completion for the other windows is not assessed; `q06` additionally has no visible person. No observation from source 031 is transferred to source 030.

The CLI pins the exact parent item SHA, labels-file SHA and manifest SHA binding in the labels. The original manifest is not reopened: its identifier is checked against the frozen label binding and the implementation constant. JSON validation rejects duplicate keys/nonfinite numbers, incorrect parent/revision bindings, six-label mapping changes, duplicate/missing B/C pairs, inconsistent source/window/role bindings, invalid traces and changes to partial/unknown label scope. The parent file's exact SHA also binds every prediction and provenance field.

Each reviewed row updates only `reference_label`, `label_status` and `label_scope`, and adds `user_label_revision` containing the original label fields, full user label, provenance, hashes, completion reference and revised presence comparison. All other parent fields remain semantically identical, including model output, hashes, PTS, trace/reuse data and historical consistency/completion fields. Those historical fields retain the parent's interpretation; the distinct revision block supplies the new user reference interpretation. No model explanation, completion claim or boundary alignment is promoted to a user-confirmed fact.

## Primary reviewed windows

These are the three originally selected primary windows; all are now confirmed no-crossing within their scheduled window. There are **zero primary positive windows**.

| Review / case | Source / window | Scheduled seconds | User observation | B output | C output |
| --- | --- | --- | --- | --- | --- |
| q01 / s007_early | E01_007 / w000001 | 0–5 | Vehicle outside door; no crossing attempt/progress | absent | absent |
| q02 / s007_preevent | E01_007 / w000020 | 47.5–52.5 | People approach; no attempt/progress before clip end | **candidate** | absent |
| q05 / s030_time | E01_030 / w000021 | 50–55 | One of three people approaches; no attempt/progress | **candidate** | **candidate** |

B emits candidates in **2 of these 3 windows**; C in **1 of 3**. B's q02 candidate and both q05 candidates conflict with the user-confirmed no-crossing reference. These are observed local failures, retained in the records; the counts are not FPR or other population estimates.

## Diagnostic reviewed windows

These three windows retain their original diagnostic role and stay outside primary performance denominators. Historical case name `d007_official` identifies the frozen case; its new reference is the user's window observation, not an official annotation read.

| Review / case | Source / window | Scheduled seconds | User observation | B output | C output |
| --- | --- | --- | --- | --- | --- |
| q03 / d007_boxchange | E01_007 / w000022 | 52.5–57.5 | No visible crossing attempt/progress | absent | **candidate** |
| q04 / d007_official | E01_007 / w000026 | 62.5–67.5 | **Attempt/progress present; completion not observed before clip ends** | **absent** | candidate |
| q06 / d030_eof | E01_030 / w000063 | 155–160 | No person or event | absent | absent |

B emits **0 of 3** diagnostic reviewed candidates; C emits **2 of 3**. C's q03 candidate conflicts with the no-crossing reference. On the sole fully reviewed attempt-positive q04, B is absent and C emits a candidate; the C candidate does not establish that its model completion claim is correct.

## Counts and denominators

Each denominator counts unique scheduled windows **per method**, not B/C rows or independent videos. `candidate + candidate_absent + unavailable = denominator`; unavailable outputs remain in the denominator. All actual records here are trace-valid and available.

| Window group | Denominator per method | B candidate / absent / unavailable | C candidate / absent / unavailable |
| --- | ---: | ---: | ---: |
| Primary reviewed, all no-crossing | 3 | 2 / 1 / 0 | 1 / 2 / 0 |
| Diagnostic reviewed | 3 | 0 / 3 / 0 | 2 / 1 / 0 |
| All six reviewed | 6 | 2 / 4 / 0 | 3 / 3 / 0 |
| Reviewed no-crossing, across roles | 5 | 2 / 3 / 0 | 2 / 3 / 0 |
| Reviewed attempt-positive, diagnostic q04 only | 1 | 0 / 1 / 0 | 1 / 0 / 0 |
| Partial-positive d030_90, excluded from reviewed counts | 1 | 1 / 0 / 0 | 1 / 0 / 0 |
| Unknown cases | 5 | 1 / 4 / 0 | 1 / 4 / 0 |
| All selected windows | 12 | 4 / 8 / 0 | 5 / 7 / 0 |

The five reviewed no-crossing windows total 25 scheduled seconds, a small selected development sample. The six confirmed cases comprise five no-crossing and one diagnostic attempt-positive. There are still five unknown cases (`d030_84` and four E01_013 fallback cases), plus one separate partial positive (`d030_90`); neither class is converted to negative. Four C fallback records reuse B outputs and supply no independent ROI comparison.

[Metrics](../../records/EXP-0015/metrics.json) contain six graph rows: primary reviewed, diagnostic reviewed and all reviewed candidate counts for each method, with sample sizes 3, 3 and 6. Their source hashes bind the exact new [window records](../../records/EXP-0015/window_reviews.json) bytes. **Accuracy, precision, recall, F1, FPR and hourly false alarms remain null.** The only fully reviewed positive is an outcome-aware diagnostic anchor; primary positives are zero. Retrospective selection after aggregate outcomes, shared sources/nearby windows, tiny denominators and reused fallback outputs preclude performance/generalization claims. Candidate totals, test success and schema compliance do not establish behavior accuracy, operational suitability or model adoption. Explanation factuality, ROI boundary alignment, onset/timing, completion accuracy and execution cost are not evaluated by this label revision.

## Reproduction and verification

From the repository root:

```bash
python3 scripts/apply_mvp_small_label_revision.py --help
python3 scripts/apply_mvp_small_label_revision.py
python3 scripts/apply_mvp_small_label_revision.py
python3 -m unittest tests_mvp.test_label_revision -v
```

The CLI accepts only `--root` for the two fixed relative inputs and writes only `records/EXP-0015/metrics.json` and `records/EXP-0015/window_reviews.json`. An identical rerun leaves their bytes and modification times unchanged. Differing existing files, symlinks and hardlinked output files are rejected; the original parent/config files are never written. Input bytes are rechecked immediately before output writes.

Focused test result: **16 tests passed**. Synthetic fixtures cover every review/case/source/window/interval/label/completion mapping, schema/hash rejection, primary/diagnostic/reviewed denominators including unavailable predictions, q02/q03/q05 failures, q04 attempt/completion distinction, no argument mutation, unchanged predictions/provenance, all unknown/partial labels, two-file-only input access, parent/config bytes and mtimes, repeat determinism, unsafe destinations, source changes and output overwrite refusal. These are CPU integrity/regression checks, not behavior performance validation.

The exact additional real-output validation command was:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from orchestration.complete import metrics
from scripts import apply_mvp_small_label_revision as revision
root = Path('.')
summary, rows, consumed = revision.evaluate(root)
metrics(summary, 'EXP-0015')
assert len(summary['metrics']) == 6
assert (root / 'records/EXP-0015/metrics.json').read_bytes() == revision.json_bytes(summary)
assert (root / 'records/EXP-0015/window_reviews.json').read_bytes() == revision.json_bytes(rows)
parent = json.loads((root / revision.PARENT_PATH).read_bytes())
for old, new in zip(parent, rows):
    if 'user_label_revision' not in new:
        assert revision.json_bytes(old) == revision.json_bytes(new)
    for key, value in old.items():
        if key not in revision.LABEL_FIELDS:
            assert revision.json_bytes(value) == revision.json_bytes(new[key]), key
assert all(path.read_bytes() == raw for path, raw in consumed.items())
print('PASS: metrics validator, six graph rows, output bytes, all preserved fields and two frozen inputs')
PY
```

That command passed on the actual sanitized records. Repeated CLI execution produced identical output and passed the existing `orchestration.complete.metrics` validator without changing the validator or completion runtime.

## SHA-256 evidence

| Artifact | SHA-256 |
| --- | --- |
| Frozen labels config, unchanged | `9f2deedaebe137250f1926bc07d0ef4213a6590249718f4be785594be7640bcd` |
| EXP-0014 window records, unchanged | `427d59cd0d8092a5fb69c936449be9301d1d302285e21381ec7e1d0ada672b1a` |
| Frozen parent manifest binding, file not reopened | `ec293844173fe8797b2e518ba1a01b98be2720f766fd4c27bf3d5f278a7186af` |
| Revision implementation | `cd502405a6911356aea0143665e27fe34a78bc47c1019285043de378fe65fb39` |
| EXP-0015 metrics | `e950fb042ad919f64346908e8b7bcfc64953c17e39c81c3c3ae0576dba1e7a14` |
| EXP-0015 window records | `b82267a2c8a457a2dd505183c61fb0cffde886776970322e66176e69493de0d0` |

Independent review, completion registration, catalog/assignment integration, publication and browser delivery checks remain coordinator-owned work. This worker changes only its five assigned files and makes no adoption decision.
