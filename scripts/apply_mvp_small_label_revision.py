#!/usr/bin/env python3
"""EXP-0015: apply six frozen user window labels to sanitized EXP-0014 rows.

CPU/stdlib only. Reads the two fixed JSON inputs and this implementation for its
hash; never opens the manifest, media, raw answers, model cache or annotations.
Writes only records/EXP-0015/{metrics,window_reviews}.json; identical reruns are
no-ops and differing existing output is rejected.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PARENT_PATH = 'records/EXP-0014/window_reviews.json'
LABELS_PATH = 'configs/mvp_small_eval_labels_r1.json'
PARENT_SHA256 = '427d59cd0d8092a5fb69c936449be9301d1d302285e21381ec7e1d0ada672b1a'
MANIFEST_SHA256 = 'ec293844173fe8797b2e518ba1a01b98be2720f766fd4c27bf3d5f278a7186af'
LABELS_SHA256 = '9f2deedaebe137250f1926bc07d0ef4213a6590249718f4be785594be7640bcd'
REVISION = 'EXP-0015-LABEL-R1'
# Review ID, case, source, scheduled window, interval, label, completion, role.
MAPPINGS = (
    ('q01', 's007_early', 'E01_007', 'w000001', [0., 5.], 'no_climbing_observed', 'not_assessed', 'primary'),
    ('q02', 's007_preevent', 'E01_007', 'w000020', [47.5, 52.5], 'no_climbing_observed', 'not_assessed', 'primary'),
    ('q03', 'd007_boxchange', 'E01_007', 'w000022', [52.5, 57.5], 'no_climbing_observed', 'not_assessed', 'diagnostic'),
    ('q04', 'd007_official', 'E01_007', 'w000026', [62.5, 67.5], 'climbing_present', 'not_observed_clip_ends_before_complete', 'diagnostic'),
    ('q05', 's030_time', 'E01_030', 'w000021', [50., 55.], 'no_climbing_observed', 'not_assessed', 'primary'),
    ('q06', 'd030_eof', 'E01_030', 'w000063', [155., 160.], 'no_climbing_observed', 'not_assessed_no_visible_person', 'diagnostic'),
)
LABEL_FIELDS = ('reference_label', 'label_status', 'label_scope')
PRESENCES = ('candidate', 'candidate_absent', 'unavailable')
HASH = re.compile(r'[0-9a-f]{64}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad_constant(value):
        raise ValueError('nonfinite JSON number: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)


def validate_labels(labels):
    require(isinstance(labels, dict) and labels.get('schema_version') == 1, 'invalid labels schema')
    for key, expected in (('label_revision_id', REVISION), ('based_on_experiment', 'EXP-0013'),
                          ('parent_evaluation', 'EXP-0014'), ('parent_manifest_sha256', MANIFEST_SHA256),
                          ('parent_items_sha256', PARENT_SHA256)):
        require(labels.get(key) == expected, 'labels binding mismatch: ' + key)
    provenance = labels.get('provenance')
    require(isinstance(provenance, dict) and provenance.get('reviewer') == 'user', 'user provenance required')
    require(all(isinstance(provenance.get(k), str) and provenance[k].strip()
                for k in ('source', 'recorded_date', 'scope', 'completion_rule')), 'incomplete label provenance')
    entries = labels.get('labels')
    require(isinstance(entries, list) and len(entries) == 6, 'exactly six labels required')
    require(all(isinstance(x, dict) for x in entries), 'invalid label entry')
    by_id = {x.get('review_clip_id'): x for x in entries}
    require(len(by_id) == 6, 'duplicate review clip')
    for qid, cid, sid, wid, interval, reference, completion, _ in MAPPINGS:
        entry = by_id.get(qid, {})
        for key, expected in (('case_id', cid), ('source_id', sid), ('window_id', wid),
                              ('interval_seconds', interval), ('reference_label', reference),
                              ('completion_reference', completion), ('label_status', 'human_confirmed_for_window')):
            require(entry.get(key) == expected, 'six-label mapping mismatch: ' + qid + '/' + key)
        require(isinstance(entry.get('observed_behavior'), str) and entry['observed_behavior'].strip(),
                'observed behavior required')
    return {entry['case_id']: entry for entry in entries}


def validate_parent(parent, label_by_case):
    require(isinstance(parent, list) and len(parent) == 24, 'parent must contain 24 records')
    seen = set()
    cases = {}
    for row in parent:
        require(isinstance(row, dict), 'invalid parent row')
        required = set('case_id method source_id window_id scheduled_interval_seconds evaluation_role '
                       'reference_label label_status label_scope observed_output provenance counted_output_presence '
                       'paired_trace_valid pairing_issues completion_reference_provenance presence_reference_consistency '
                       'fallback_diagnostic reused source_sha256'.split())
        require(required <= row.keys() and 'user_label_revision' not in row, 'invalid parent row schema')
        cid, method = row['case_id'], row['method']
        require(isinstance(cid, str) and method in ('B', 'C'), 'invalid case/method')
        require((cid, method) not in seen, 'duplicate parent case/method')
        seen.add((cid, method))
        require(row['counted_output_presence'] in PRESENCES, 'invalid output presence')
        require(row['paired_trace_valid'] is True and row['pairing_issues'] == [], 'invalid parent trace')
        require(row['evaluation_role'] in ('primary', 'diagnostic', 'fallback_diagnostic'), 'invalid evaluation role')
        require(isinstance(row['observed_output'], dict) and isinstance(row['provenance'], dict)
                and row['provenance'] and all(isinstance(v, str) and HASH.fullmatch(v)
                                             for v in row['provenance'].values()), 'invalid prediction/provenance schema')
        require(row['observed_output'].get('output_presence') == row['counted_output_presence'], 'presence mismatch')
        binding = [row[k] for k in ('source_id', 'window_id', 'scheduled_interval_seconds', 'evaluation_role',
                                    'reference_label', 'label_status', 'label_scope')]
        require(cid not in cases or cases[cid] == binding, 'B/C case mapping mismatch')
        cases[cid] = binding
        if cid in label_by_case:
            entry = label_by_case[cid]
            role = next(m[-1] for m in MAPPINGS if m[1] == cid)
            require(binding[:4] == [entry['source_id'], entry['window_id'], entry['interval_seconds'], role],
                    'parent case/window mapping mismatch')
            require(row['reference_label'] == 'uncertain' and row['label_scope'] == 'unknown', 'reviewed parent label mismatch')
        elif cid == 'd030_90':
            require(binding[4:] == ['climbing_present', 'human_observation_partial', 'partial_positive_presence'],
                    'partial positive must stay partial')
        else:
            require(row['reference_label'] == 'uncertain' and row['label_scope'] == 'unknown', 'unknown label mismatch')
    require(len(cases) == 12 and set(label_by_case) <= cases.keys() and 'd030_90' in cases, 'parent selection mismatch')
    require(seen == {(cid, method) for cid in cases for method in ('B', 'C')}, 'missing B/C pair')
    require(len({(b[0], b[1]) for b in cases.values()}) == 12, 'duplicate source/window')
    require([sum(b[3] == role for b in cases.values()) for role in ('primary', 'diagnostic', 'fallback_diagnostic')]
            == [3, 5, 4], 'parent role denominators mismatch')


def revise(parent, labels, labels_sha256=LABELS_SHA256):
    """Pure revision; neither argument is mutated. File hash checks live in evaluate."""
    by_case = validate_labels(labels)
    validate_parent(parent, by_case)
    revised = copy.deepcopy(parent)
    for row in revised:
        entry = by_case.get(row['case_id'])
        if entry is None:
            continue
        prior = {key: row[key] for key in LABEL_FIELDS}
        positive = entry['reference_label'] == 'climbing_present'
        presence = row['counted_output_presence']
        consistency = ('unavailable' if presence == 'unavailable' else
                       'candidate_on_reviewed_attempt_positive' if positive and presence == 'candidate' else
                       'candidate_absent_on_reviewed_attempt_positive' if positive else
                       'candidate_on_reviewed_no_crossing' if presence == 'candidate' else
                       'candidate_absent_on_reviewed_no_crossing')
        row.update(reference_label=entry['reference_label'], label_status=entry['label_status'],
                   label_scope='full_window_positive_presence' if positive else 'full_window_no_climbing_observed')
        row['user_label_revision'] = {
            'label_revision_id': REVISION, 'labels_sha256': labels_sha256,
            'parent_evaluation': 'EXP-0014', 'parent_items_sha256': PARENT_SHA256,
            'parent_manifest_sha256': MANIFEST_SHA256, 'parent_label_fields': prior,
            'user_label': copy.deepcopy(entry), 'provenance': copy.deepcopy(labels['provenance']),
            'presence_reference_consistency': consistency,
            'historical_fields_rule': 'Parent prediction, provenance, consistency and completion fields remain unchanged; this block supplies the revised reference interpretation.',
        }
    return revised


def summarize(rows, labels, labels_sha256, implementation_sha256):
    unique = [r for r in rows if r['method'] == 'B']
    tables = []
    predicates = (
        ('all_selected', lambda r: True),
        ('primary_reviewed', lambda r: r['evaluation_role'] == 'primary' and 'user_label_revision' in r),
        ('diagnostic_reviewed', lambda r: r['evaluation_role'] == 'diagnostic' and 'user_label_revision' in r),
        ('all_reviewed', lambda r: 'user_label_revision' in r),
        ('reviewed_no_crossing', lambda r: 'user_label_revision' in r and r['reference_label'] == 'no_climbing_observed'),
        ('reviewed_attempt_positive', lambda r: 'user_label_revision' in r and r['reference_label'] == 'climbing_present'),
        ('partial_positive_presence', lambda r: r['label_scope'] == 'partial_positive_presence'),
        ('unknown', lambda r: r['label_scope'] == 'unknown'),
        ('fallback_diagnostic', lambda r: r['evaluation_role'] == 'fallback_diagnostic'),
    )
    for method in ('B', 'C'):
        for group, predicate in predicates:
            selected = [r for r in rows if r['method'] == method and predicate(r)]
            tables.append({'method': method, 'group': group, 'denominator': len(selected),
                           **{p: sum(r['counted_output_presence'] == p for r in selected) for p in PRESENCES},
                           'unknown_label_count': sum(r['label_scope'] == 'unknown' for r in selected),
                           'reused_count': sum(r['reused'] for r in selected)})
    item_sha = sha(json_bytes(rows))
    graph = []
    for method in ('B', 'C'):
        for group in ('primary_reviewed', 'diagnostic_reviewed', 'all_reviewed'):
            table = next(t for t in tables if t['method'] == method and t['group'] == group)
            graph.append({'label': method + ': ' + group + ' candidate outputs (descriptive count)',
                          'value': table['candidate'], 'unit': 'window', 'sample_n': table['denominator'],
                          'scope': 'EXP-0015 ' + group + '; outcome-aware development windows; candidate count only; no accuracy/F1/FPR/generalization inference',
                          'source': 'records/EXP-0015/window_reviews.json', 'source_sha256': item_sha,
                          'verification': 'source_json_sha256_checked'})
    return {
        'schema_version': 1, 'experiment_id': 'EXP-0015', 'evaluation_id': 'EXP-0015',
        'based_on_exp': 'EXP-0013', 'parent_evaluation': 'EXP-0014',
        'parent_items_sha256': PARENT_SHA256, 'frozen_manifest_sha256': MANIFEST_SHA256,
        'labels_revision': REVISION, 'labels_sha256': labels_sha256,
        'implementation_sha256': implementation_sha256, 'item_results_sha256': item_sha,
        'user_label_provenance': copy.deepcopy(labels['provenance']),
        'execution_scope': 'CPU-only label revision of two frozen JSON inputs; no media, raw answers, cache, weights, official annotations or GPU opened',
        'manifest_verification': 'Frozen manifest SHA is checked against the label binding and pinned constant; manifest file is not reopened',
        'source_files_verified_unchanged': 2, 'evaluation_extraction_complete': True,
        'selected_case_count': len(unique), 'selected_pair_records': len(rows),
        'traced_valid_records': sum(r['paired_trace_valid'] for r in rows), 'invalid_or_missing_records': 0,
        'user_reviewed_cases': 6, 'updated_label_records': 12, 'unchanged_records': 12,
        'confirmed_negative_cases': 5, 'full_window_confirmed_positive_cases': 1,
        'primary_fully_confirmed_negative_denominator': 3, 'primary_fully_confirmed_positive_denominator': 0,
        'diagnostic_reviewed_negative_denominator': 2, 'diagnostic_reviewed_positive_denominator': 1,
        'unique_partial_positive_presence_cases': sum(r['label_scope'] == 'partial_positive_presence' for r in unique),
        'unique_unknown_label_cases': sum(r['label_scope'] == 'unknown' for r in unique),
        'reviewed_no_crossing_scheduled_seconds': 25.0,
        'counting_formula': 'For each method/group, candidate + candidate_absent + unavailable = denominator (unique scheduled windows, not B/C records or independent videos). Partial d030_90 is excluded from all six reviewed counts.',
        'output_presence_tables': tables, 'metrics': graph,
        'performance_metrics': {key: None for key in ('accuracy', 'precision', 'recall', 'f1', 'fpr', 'hourly_false_alarms')},
        'behavioral_validation': 'descriptive_reviewed_window_comparison_only_adoption_hold',
        'performance_null_reason': 'Primary positives are zero; the sole full-window positive q04 is an outcome-aware diagnostic anchor. Six retrospective, dependent development windows do not support formal performance or generalization estimates.',
        'limits': [
            'User labels cover only scheduled 5-second windows and visible attempt/progress; access rights, intent, later events and whole-video normality are not labeled.',
            'q04 contains attempt/progress; completion was not observed before clip end. Other completion references are not assessed, not negative completion labels.',
            'B candidates on q02/q05 and C candidates on q03/q05 conflict with reviewed no-crossing labels; B is absent on q04. These failures remain visible.',
            'd030_90 remains a partial positive and five other cases remain unknown; 031 observations never transfer to 030.',
            'Four C fallback records reuse B and remain unknown; they are not independent ROI evidence.',
            'Parent completion/model text claims, form diagnostics, boundary alignment and explanation factuality are preserved historical evidence, not promoted to user-verified facts.',
            'No new inference, timing, cost, completion score, FPR or model adoption claim is made.',
        ],
    }


def evaluate(root=ROOT):
    root = Path(root).resolve()
    consumed = {}
    for relative, expected in ((LABELS_PATH, LABELS_SHA256), (PARENT_PATH, PARENT_SHA256)):
        path = root / relative
        require(path.resolve() == path and path.is_file(), 'input must be a regular non-symlink file')
        raw = path.read_bytes()
        require(sha(raw) == expected, 'frozen input SHA256 mismatch: ' + relative)
        consumed[path] = raw
    labels = decode(consumed[root / LABELS_PATH])
    parent = decode(consumed[root / PARENT_PATH])
    revised = revise(parent, labels)
    summary = summarize(revised, labels, LABELS_SHA256, sha(Path(__file__).read_bytes()))
    return summary, revised, consumed


def write_outputs(root, summary, rows, consumed):
    destination = Path(root).resolve() / 'records/EXP-0015'
    require(destination.resolve() == destination, 'output directory must not be a symlink')
    payloads = {destination / name: json_bytes(obj) for name, obj in
                (('metrics.json', summary), ('window_reviews.json', rows))}
    for path, raw in payloads.items():
        require(not path.is_symlink(), 'output must not be a symlink')
        if path.exists():
            require(path.is_file() and path.stat().st_nlink == 1 and path.read_bytes() == raw,
                    'refusing to overwrite differing or linked output: ' + path.name)
    require(all(path.read_bytes() == raw for path, raw in consumed.items()), 'source changed during revision')
    destination.mkdir(parents=True, exist_ok=True)
    for path, raw in payloads.items():
        if not path.exists():
            with path.open('xb') as stream:
                stream.write(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='repository root containing the two frozen JSON inputs')
    args = parser.parse_args(argv)
    summary, rows, consumed = evaluate(args.root)
    write_outputs(args.root, summary, rows, consumed)
    print(json.dumps({'evaluation': 'EXP-0015', 'updated_label_records': 12,
                      'item_results_sha256': summary['item_results_sha256'],
                      'behavioral_validation': summary['behavioral_validation']}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
