"""CPU-only synthetic label revision fixtures; no media, cache or inference."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orchestration.complete import metrics as validate_delivery_metrics
from scripts import apply_mvp_small_label_revision as revision


def fixtures():
    labels = {
        'schema_version': 1, 'label_revision_id': revision.REVISION,
        'based_on_experiment': 'EXP-0013', 'parent_evaluation': 'EXP-0014',
        'parent_manifest_sha256': revision.MANIFEST_SHA256,
        'parent_items_sha256': revision.PARENT_SHA256,
        'provenance': {'reviewer': 'user', 'source': 'synthetic user review', 'recorded_date': '2026-10-28',
                       'scope': 'Scheduled 5-second window; attempt/progress only.',
                       'completion_rule': 'Attempt/progress differs from completion.'}, 'labels': [],
    }
    cases = []
    for qid, cid, sid, wid, interval, label, completion, role in revision.MAPPINGS:
        labels['labels'].append({'review_clip_id': qid, 'case_id': cid, 'source_id': sid, 'window_id': wid,
                                 'interval_seconds': interval[:], 'reference_label': label,
                                 'label_status': 'human_confirmed_for_window',
                                 'observed_behavior': 'Synthetic window behavior.', 'completion_reference': completion})
        cases.append((cid, sid, wid, interval[:], role))
    cases.extend([
        ('d030_84', 'E01_030', 'w000034', [82.5, 87.5], 'diagnostic'),
        ('d030_90', 'E01_030', 'w000036', [87.5, 92.5], 'diagnostic'),
        *[(cid, 'E01_013', wid, [start, start + 5.], 'fallback_diagnostic') for cid, wid, start in (
            ('s013_early', 'w000001', 0.), ('s013_mid', 'w000017', 40.),
            ('d013_official', 'w000025', 60.), ('s013_late', 'w000049', 120.))],
    ])
    rows = []
    candidates = {'B': {'s007_preevent', 's030_time', 'd030_84', 'd030_90'},
                  'C': {'d007_boxchange', 'd007_official', 's030_time', 'd030_84', 'd030_90'}}
    for method in ('B', 'C'):
        for cid, sid, wid, interval, role in cases:
            partial = cid == 'd030_90'
            presence = 'candidate' if cid in candidates[method] else 'candidate_absent'
            rows.append({
                'case_id': cid, 'method': method, 'source_id': sid, 'window_id': wid,
                'scheduled_interval_seconds': interval[:], 'evaluation_role': role,
                'reference_label': 'climbing_present' if partial else 'uncertain',
                'label_status': 'human_observation_partial' if partial else 'needs_human_review',
                'label_scope': 'partial_positive_presence' if partial else 'unknown',
                'counted_output_presence': presence, 'paired_trace_valid': True, 'pairing_issues': [],
                'observed_output': {'output_presence': presence, 'completion_claim': 'observed',
                                    'completion_support': 'unverified', 'actions': ['synthetic_action']},
                'provenance': {'result_file_sha256': 'a' * 64}, 'source_sha256': 'b' * 64,
                'completion_reference_provenance': 'no_030_completion_label_from_031' if cid == 'd030_eof' else 'no_completion_ground_truth',
                'presence_reference_consistency': 'unresolved', 'fallback_diagnostic': role == 'fallback_diagnostic',
                'reused': method == 'C' and role == 'fallback_diagnostic',
                'arbitrary_prediction_field': {'keep_exact': [1, 2.0, False, None, 'opaque']},
            })
    return rows, labels


class LabelRevisionTests(unittest.TestCase):
    def setUp(self):
        self.parent, self.labels = fixtures()

    def revised(self):
        return revision.revise(self.parent, self.labels)

    def summary(self, rows=None):
        return revision.summarize(rows if rows is not None else self.revised(), self.labels,
                                  revision.LABELS_SHA256, 'f' * 64)

    def row(self, rows, cid, method='B'):
        return next(r for r in rows if r['case_id'] == cid and r['method'] == method)

    def test_six_mappings_applied_to_both_methods_only(self):
        rows = self.revised()
        for qid, cid, sid, wid, interval, label, completion, role in revision.MAPPINGS:
            for method in ('B', 'C'):
                row = self.row(rows, cid, method)
                self.assertEqual((row['source_id'], row['window_id'], row['scheduled_interval_seconds']), (sid, wid, interval))
                self.assertEqual(row['reference_label'], label)
                self.assertEqual(row['label_status'], 'human_confirmed_for_window')
                block = row['user_label_revision']
                self.assertEqual(block['user_label']['review_clip_id'], qid)
                self.assertEqual(block['user_label']['completion_reference'], completion)
                self.assertEqual(block['parent_items_sha256'], revision.PARENT_SHA256)
                self.assertEqual(block['parent_label_fields']['label_scope'], 'unknown')
        self.assertEqual(sum('user_label_revision' in r for r in rows), 12)

    def test_inputs_predictions_provenance_and_nonlabel_fields_never_mutated(self):
        before = copy.deepcopy((self.parent, self.labels))
        rows = self.revised()
        self.assertEqual((self.parent, self.labels), before)
        for parent, row in zip(self.parent, rows):
            for key in parent:
                if key not in revision.LABEL_FIELDS:
                    self.assertEqual(row[key], parent[key], key)
        rows[0]['observed_output']['actions'].append('changed')
        rows[0]['user_label_revision']['provenance']['scope'] = 'changed'
        self.assertEqual((self.parent, self.labels), before)

    def test_partial_and_all_five_unknown_cases_remain_byte_semantically_identical(self):
        rows = self.revised()
        reviewed = {m[1] for m in revision.MAPPINGS}
        for old, new in zip(self.parent, rows):
            if old['case_id'] not in reviewed:
                self.assertEqual(revision.json_bytes(old), revision.json_bytes(new))
        partial = self.row(rows, 'd030_90')
        self.assertEqual(partial['label_scope'], 'partial_positive_presence')
        self.assertNotIn('user_label_revision', partial)
        self.assertEqual(self.summary()['unique_unknown_label_cases'], 5)
        self.assertEqual(self.summary()['unique_partial_positive_presence_cases'], 1)

    def test_attempt_positive_is_not_completed_crossing(self):
        for method, consistency in [('B', 'candidate_absent_on_reviewed_attempt_positive'),
                                    ('C', 'candidate_on_reviewed_attempt_positive')]:
            row = self.row(self.revised(), 'd007_official', method)
            self.assertEqual(row['reference_label'], 'climbing_present')
            block = row['user_label_revision']
            self.assertEqual(block['user_label']['completion_reference'], 'not_observed_clip_ends_before_complete')
            self.assertEqual(block['presence_reference_consistency'], consistency)
            self.assertEqual(row['observed_output']['completion_claim'], 'observed')
            self.assertEqual(row['observed_output']['completion_support'], 'unverified')
        eof = self.row(self.revised(), 'd030_eof')
        self.assertEqual(eof['completion_reference_provenance'], 'no_030_completion_label_from_031')
        self.assertEqual(eof['user_label_revision']['user_label']['completion_reference'], 'not_assessed_no_visible_person')

    def test_denominators_and_expected_descriptive_comparison(self):
        summary = self.summary()
        expected = {'all_selected': (12, 4, 5), 'primary_reviewed': (3, 2, 1),
                    'diagnostic_reviewed': (3, 0, 2), 'all_reviewed': (6, 2, 3),
                    'reviewed_no_crossing': (5, 2, 2), 'reviewed_attempt_positive': (1, 0, 1),
                    'partial_positive_presence': (1, 1, 1), 'unknown': (5, 1, 1),
                    'fallback_diagnostic': (4, 0, 0)}
        for table in summary['output_presence_tables']:
            n, b, c = expected[table['group']]
            self.assertEqual(table['denominator'], n)
            self.assertEqual(table['candidate'], b if table['method'] == 'B' else c)
            self.assertEqual(sum(table[p] for p in revision.PRESENCES), n)
        self.assertEqual(summary['primary_fully_confirmed_positive_denominator'], 0)
        self.assertEqual(summary['primary_fully_confirmed_negative_denominator'], 3)
        self.assertEqual(summary['confirmed_negative_cases'], 5)
        self.assertEqual(summary['full_window_confirmed_positive_cases'], 1)
        self.assertEqual(summary['reviewed_no_crossing_scheduled_seconds'], 25.)
        self.assertTrue(all(v is None for v in summary['performance_metrics'].values()))

    def test_graph_six_rows_validate_and_bind_exact_output_bytes(self):
        rows = self.revised()
        summary = self.summary(rows)
        validate_delivery_metrics(summary, 'EXP-0015')
        self.assertEqual([m['value'] for m in summary['metrics']], [2, 0, 2, 1, 2, 3])
        self.assertEqual([m['sample_n'] for m in summary['metrics']], [3, 3, 6, 3, 3, 6])
        self.assertTrue(all(m['source_sha256'] == revision.sha(revision.json_bytes(rows)) for m in summary['metrics']))

    def test_unavailable_prediction_remains_in_reviewed_denominator(self):
        parent = self.row(self.parent, 's007_preevent')
        parent['counted_output_presence'] = 'unavailable'
        parent['observed_output']['output_presence'] = 'unavailable'
        rows = self.revised()
        table = next(t for t in self.summary(rows)['output_presence_tables']
                     if t['method'] == 'B' and t['group'] == 'primary_reviewed')
        self.assertEqual((table['denominator'], table['candidate'], table['unavailable']), (3, 1, 1))
        self.assertEqual(self.row(rows, 's007_preevent')['user_label_revision']['presence_reference_consistency'],
                         'unavailable')

    def test_errors_are_explicit_for_q02_q03_q05_and_q04(self):
        rows = self.revised()
        for method, cid in [('B', 's007_preevent'), ('B', 's030_time'),
                            ('C', 'd007_boxchange'), ('C', 's030_time')]:
            self.assertEqual(self.row(rows, cid, method)['user_label_revision']['presence_reference_consistency'],
                             'candidate_on_reviewed_no_crossing')
        self.assertIn('q02/q05', ' '.join(self.summary()['limits']))
        self.assertIn('q03/q05', ' '.join(self.summary()['limits']))

    def test_all_mapping_fields_and_label_bindings_are_validated(self):
        for field, value in [('case_id', 's007_early'), ('source_id', 'E01_030'), ('window_id', 'w999999'),
                             ('interval_seconds', [0, 4]), ('reference_label', 'climbing_present'),
                             ('completion_reference', 'observed'), ('label_status', 'unreviewed')]:
            labels = copy.deepcopy(self.labels)
            labels['labels'][1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                revision.revise(self.parent, labels)
        for field in ('parent_items_sha256', 'parent_manifest_sha256', 'parent_evaluation', 'label_revision_id'):
            labels = copy.deepcopy(self.labels); labels[field] = 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError):
                revision.revise(self.parent, labels)
        for size in (5, 7):
            labels = copy.deepcopy(self.labels)
            labels['labels'] = (labels['labels'] * 2)[:size]
            with self.assertRaises(ValueError):
                revision.revise(self.parent, labels)

    def test_parent_schema_pairs_window_role_and_partial_validation(self):
        mutations = [('source_id', 'E01_030'), ('window_id', 'w999999'), ('scheduled_interval_seconds', [0., 4.]),
                     ('evaluation_role', 'diagnostic'), ('method', 'D'), ('counted_output_presence', 'normal'),
                     ('paired_trace_valid', False), ('provenance', {}), ('observed_output', None)]
        for key, value in mutations:
            rows = copy.deepcopy(self.parent); rows[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                revision.revise(rows, self.labels)
        rows = copy.deepcopy(self.parent); rows[-1] = copy.deepcopy(rows[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            revision.revise(rows, self.labels)
        rows = copy.deepcopy(self.parent); self.row(rows, 'd030_90')['label_scope'] = 'full_window_positive_presence'
        with self.assertRaises(ValueError):
            revision.revise(rows, self.labels)
        with self.assertRaises(ValueError):
            revision.revise(self.parent[:-1], self.labels)

    def fixture_root(self, root):
        parent_raw = revision.json_bytes(self.parent)
        labels = copy.deepcopy(self.labels)
        labels['parent_items_sha256'] = revision.sha(parent_raw)
        labels_raw = revision.json_bytes(labels)
        for name, raw in [(revision.PARENT_PATH, parent_raw), (revision.LABELS_PATH, labels_raw)]:
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        return patch.multiple(revision, PARENT_SHA256=revision.sha(parent_raw), LABELS_SHA256=revision.sha(labels_raw))

    def test_cli_is_deterministic_read_only_and_writes_only_two_new_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.fixture_root(root):
                source = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*.json')}
                with patch('builtins.print'):
                    self.assertEqual(revision.main(['--root', str(root)]), 0)
                produced = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*.json')}
                self.assertEqual(set(produced) - set(source), {root / 'records/EXP-0015/metrics.json', root / 'records/EXP-0015/window_reviews.json'})
                self.assertEqual({p: produced[p] for p in source}, source)
                with patch('builtins.print'):
                    revision.main(['--root', str(root)])
                self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in produced}, produced)

    def test_only_fixed_sanitized_inputs_and_implementation_are_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.fixture_root(root):
                original = Path.read_bytes
                seen = []
                def guarded(path):
                    seen.append(path)
                    self.assertIn(path, {root / revision.LABELS_PATH, root / revision.PARENT_PATH, Path(revision.__file__)})
                    return original(path)
                with patch.object(Path, 'read_bytes', guarded):
                    revision.evaluate(root)
                self.assertEqual(len(seen), 3)

    def test_hash_mismatch_rejected_before_outputs_are_created(self):
        for relative in (revision.PARENT_PATH, revision.LABELS_PATH):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.fixture_root(root):
                    path = root / relative; path.write_bytes(path.read_bytes() + b'\n')
                    with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                        revision.main(['--root', str(root)])
                    self.assertFalse((root / 'records/EXP-0015').exists())

    def test_source_change_and_output_redirect_or_overwrite_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.fixture_root(root):
                summary, rows, consumed = revision.evaluate(root)
                source = root / revision.PARENT_PATH
                original = source.read_bytes(); source.write_bytes(original + b'\n')
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    revision.write_outputs(root, summary, rows, consumed)
                source.write_bytes(original)
                outdir = root / 'records/EXP-0015'; outdir.symlink_to(source.parent, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    revision.write_outputs(root, summary, rows, consumed)
                outdir.unlink(); outdir.mkdir()
                target = outdir / 'metrics.json'; target.symlink_to(source)
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    revision.write_outputs(root, summary, rows, consumed)
                target.unlink(); target.write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError, 'overwrite'):
                    revision.write_outputs(root, summary, rows, consumed)
                self.assertEqual(source.read_bytes(), original)
                self.assertFalse((outdir / 'window_reviews.json').exists())

    def test_json_rejects_duplicate_keys_and_nonfinite_numbers(self):
        for raw in (b'{"labels":[],"labels":[]}', b'{"value":NaN}'):
            with self.assertRaises(ValueError):
                revision.decode(raw)

    def test_help_requires_no_inputs(self):
        with patch('builtins.print'), self.assertRaises(SystemExit) as result:
            revision.main(['--help'])
        self.assertEqual(result.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
