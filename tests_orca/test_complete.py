"""Registration tests use isolated TEST data only, never existing local outputs."""
from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orchestration import complete as module
from orchestration.catalog import export


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sceneguard-registration-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.runtime = self.base / 'runtime'
        self.media = self.base / 'media'
        for path in (self.repo, self.runtime, self.media):
            path.mkdir()
        self.config_path = self.runtime / 'config.json'
        self.config = {'repo_root': str(self.repo), 'runtime_dir': str(self.runtime),
                       'artifact_allow_root': str(self.media),
                       'artifacts': {'old': {'path': str(self.media / 'missing.mp4'), 'kind': 'video'}}}
        self.put(self.config_path, self.config)
        self.historical = {'experiment_id': 'EXP-0001', 'role': 'historical_import', 'evidence': []}
        self.put(self.repo / 'records/catalog.json', {'schema_version': 1, 'experiments': [self.historical]})
        self.put(self.repo / 'records/assignments.json', {'schema_version': 1, 'assignments': []})
        self.assignment = {
            'experiment_id': 'TEST-register', 'slot': 'slot1', 'title': 'Synthetic registration fixture',
            'run_id': 'run-fixture', 'task_id': 'task-fixture', 'dispatch_id': 'dispatch-fixture',
            'agent_model_requested': 'fixture-model', 'agent_model_effective': None,
            'reasoning_effective': None, 'assigned_at': '2026-10-28T00:00:00+00:00', 'synthetic': True}
        self.package = {
            'experiment_id': 'TEST-register', 'attempt_id': 'attempt-fixture', 'title': self.assignment['title'],
            'summary': 'Synthetic data only', 'evaluated_model': 'fixture, no model executed',
            'execution_status': 'inconclusive', 'review_status': 'inconclusive',
            'decision_status': 'adoption_on_hold', 'report_path': 'docs/experiments/TEST-register.md',
            'metrics_path': 'records/TEST-register/metrics.json', 'review_path': 'docs/reviews/TEST-register.md',
            'worker_opinion': 'Fixture only', 'next_step': 'No real experiment',
            'limitations': ['Synthetic fixture'], 'synthetic': True,
            'evidence': [{'artifact_id': 'fixture-video', 'label': 'Synthetic bytes, not a playable video', 'kind': 'video'}]}
        self.metrics = {'schema_version': 1, 'experiment_id': 'TEST-register', 'synthetic': True,
                        'metrics': [{'label': 'Unmeasured', 'value': None, 'unit': 'frame/s', 'sample_n': None,
                                     'scope': 'Synthetic fixture only', 'source': 'fixture/summary.json',
                                     'source_sha256': None, 'verification': 'unavailable'}]}
        self.put(self.repo / self.package['report_path'], 'Synthetic report. No experiment was executed.\n')
        self.put(self.repo / self.package['metrics_path'], self.metrics)
        self.refresh_review()
        video = self.media / 'synthetic.mp4'
        video.write_bytes(b'synthetic fixture; not actual media')
        self.manifest = {'artifacts': {'fixture-video': {'path': str(video), 'kind': 'video'}}}
        self.registry = module.Registry(self.config_path)
        self.registry.assign(self.assignment)

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding='utf-8')

    def refresh_review(self):
        for name in ('report', 'metrics'):
            self.package[f'reviewed_{name}_sha256'] = module.digest((self.repo / self.package[f'{name}_path']).read_bytes())
        self.put(self.repo / self.package['review_path'], 'Synthetic review, inconclusive.\n' + '\n'.join(
            self.package[f'reviewed_{name}_sha256'] for name in ('report', 'metrics')))

    def snapshot(self):
        return {str(path.relative_to(self.base)): path.read_bytes() for path in self.base.rglob('*')
                if path.is_file() and not path.is_symlink() and path.name != 'completion.lock'}

    def reject_preserved(self, package=None, manifest=None):
        before = self.snapshot()
        with self.assertRaises((ValueError, OSError, TypeError)):
            self.registry.complete(package or self.package, manifest or self.manifest)
        self.assertEqual(before, self.snapshot())

    def test_identical_assign_and_complete_are_byte_idempotent(self):
        self.assertEqual(self.registry.assign(self.assignment)['assignment'], 'already_registered')
        self.assertEqual(self.registry.complete(self.package, self.manifest)['registration'], 'registered')
        before = self.snapshot()
        self.assertEqual(self.registry.complete(self.package, self.manifest)['registration'], 'already_registered')
        self.assertEqual(before, self.snapshot())
        catalog = module.load(self.repo / 'records/catalog.json')
        self.assertEqual(catalog['experiments'][0], self.historical)
        self.assertTrue(catalog['experiments'][1]['synthetic'])
        self.assertIn('old', module.load(self.config_path)['artifacts'])

    def test_assignment_conflicts_and_duplicate_dispatch(self):
        for changes in ({'title': 'Different'}, {'experiment_id': 'TEST-other'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.registry.assign({**self.assignment, **changes})

    def test_shared_runtime_lock_serializes_identical_registrations(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(module.Registry(self.config_path).complete, self.package, self.manifest) for _ in range(2)]
            results = [future.result(timeout=5)['registration'] for future in futures]
        self.assertCountEqual(results, ['registered', 'already_registered'])
        self.assertEqual(len(module.load(self.repo / 'records/catalog.json')['experiments']), 2)

    def test_synthetic_requires_explicit_matching_labels(self):
        for changes in ({'synthetic': False}, {'experiment_id': 'EXP-0008'}, {'synthetic': None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                module.assignment({**self.assignment, **changes})
        package = dict(self.package); package.pop('synthetic')
        self.reject_preserved(package=package)

    def test_unknown_public_fields_and_secret_payload_rejected(self):
        for changes in ({'raw_response': 'private'}, {'summary': 'Bearer abcdefghijk'},
                        {'summary': 'log /home/user/private/results.json'},
                        {'summary': 'C:\\Users\\private'}, {'summary': 'sk-abcdefghijklmnop'}):
            with self.subTest(changes=changes):
                self.reject_preserved(package={**self.package, **changes})

    def test_unassigned_and_reserved_historical_ids_rejected(self):
        self.reject_preserved(package={**self.package, 'experiment_id': 'TEST-other'})
        with self.assertRaises(ValueError):
            module.assignment({**self.assignment, 'experiment_id': 'EXP-0001', 'synthetic': False})

    def test_stale_report_and_metrics_rejected_before_writes(self):
        for name in ('report', 'metrics'):
            path = self.repo / self.package[f'{name}_path']
            original = path.read_bytes()
            path.write_bytes(original + b'\n')
            self.reject_preserved()
            path.write_bytes(original)

    def test_review_must_contain_supplied_hashes(self):
        self.put(self.repo / self.package['review_path'], 'Old review without hashes')
        self.reject_preserved()

    def test_finite_numeric_or_null_metrics_and_provenance(self):
        for changes in ({'value': float('nan')}, {'value': float('inf')}, {'value': True},
                        {'value': '1'}, {'value': 1}, {'sample_n': -1},
                        {'source': '/private/file.json'}, {'source_sha256': 'bad'}, {'scope': ''}):
            with self.subTest(changes=changes):
                data = copy.deepcopy(self.metrics); data['metrics'][0].update(changes)
                self.put(self.repo / self.package['metrics_path'], data); self.refresh_review()
                self.reject_preserved()
        self.put(self.repo / self.package['metrics_path'], self.metrics); self.refresh_review()
        self.registry.complete(self.package, self.manifest)

    def test_measured_metric_retains_source_metadata(self):
        self.metrics['metrics'][0].update(value=2.5, sample_n=3, source_sha256='a' * 64, verification='fixture_checked')
        self.put(self.repo / self.package['metrics_path'], self.metrics); self.refresh_review()
        self.registry.complete(self.package, self.manifest)

    def test_missing_metric_metadata_rejected(self):
        del self.metrics['metrics'][0]['source']
        self.put(self.repo / self.package['metrics_path'], self.metrics); self.refresh_review()
        self.reject_preserved()

    def test_traversal_absolute_hidden_and_nonpublic_documents(self):
        for path in ('../report.md', '/tmp/report.md', 'docs/experiments/../report.md',
                     'docs/experiments/.env.md', 'outputs/report.md', 'docs//experiments/report.md'):
            with self.subTest(path=path):
                self.reject_preserved(package={**self.package, 'report_path': path})

    def test_document_symlink_and_parent_symlink_rejected(self):
        report = self.repo / self.package['report_path']
        target = self.base / 'outside.md'; target.write_bytes(report.read_bytes())
        report.unlink(); report.symlink_to(target)
        self.reject_preserved()
        report.unlink(); report.write_bytes(target.read_bytes())
        directory = report.parent
        moved = self.base / 'moved'; directory.rename(moved); directory.symlink_to(moved, target_is_directory=True)
        self.reject_preserved()

    def test_unsafe_artifact_paths_and_missing_files(self):
        for path in (str(self.base / 'outside.mp4'), str(self.media / '..' / 'outside.mp4'),
                     str(self.media / '.env'), str(self.media / 'missing.mp4'), 'relative.mp4'):
            with self.subTest(path=path):
                self.reject_preserved(manifest={'artifacts': {'fixture-video': {'path': path, 'kind': 'video'}}})

    def test_artifact_symlink_directory_fifo_and_type_rejected(self):
        paths = [self.media / 'link.mp4', self.media / 'directory.mp4', self.media / 'fifo.mp4', self.media / 'bad.txt']
        paths[0].symlink_to(self.media / 'synthetic.mp4'); paths[1].mkdir()
        os.mkfifo(paths[2]); paths[3].write_text('fixture')
        for path in paths:
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                self.registry.complete(self.package, {'artifacts': {'fixture-video': {'path': str(path), 'kind': 'video'}}})

    def test_artifact_manifest_ids_kinds_and_conflicts(self):
        for manifest in ({'artifacts': {}}, {'artifacts': {'other': self.manifest['artifacts']['fixture-video']}},
                         {'artifacts': {'fixture-video': {**self.manifest['artifacts']['fixture-video'], 'kind': 'image'}}}):
            with self.subTest(manifest=manifest):
                self.reject_preserved(manifest=manifest)
        self.config['artifacts']['fixture-video'] = {'path': str(self.media / 'different.mp4'), 'kind': 'video'}
        self.put(self.config_path, self.config); self.reject_preserved()

    def test_catalog_last_partial_failure_and_safe_retry(self):
        original_catalog = (self.repo / 'records/catalog.json').read_bytes()
        real = module.atomic
        def fail_catalog(path, value):
            if path == self.repo / 'records/catalog.json':
                raise OSError('injected interruption')
            real(path, value)
        with patch.object(module, 'atomic', side_effect=fail_catalog), self.assertRaises(OSError):
            self.registry.complete(self.package, self.manifest)
        self.assertEqual((self.repo / 'records/catalog.json').read_bytes(), original_catalog)
        self.assertFalse(self.registry.status('TEST-register')['registered'])
        # A changed attempt must not bypass the binding left by a partial write.
        self.reject_preserved(package={**self.package, 'attempt_id': 'changed-attempt', 'summary': 'Changed payload'})
        self.registry.complete(self.package, self.manifest)
        self.assertTrue(self.registry.status('TEST-register')['registered'])

    def test_partial_binding_then_config_failure_retry(self):
        real = module.atomic
        def fail_config(path, value):
            if path == self.config_path:
                raise OSError('injected config failure')
            real(path, value)
        with patch.object(module, 'atomic', side_effect=fail_config), self.assertRaises(OSError):
            self.registry.complete(self.package, self.manifest)
        self.assertFalse(self.registry.status('TEST-register')['registered'])
        self.reject_preserved(package={**self.package, 'attempt_id': 'changed-attempt'})
        self.registry.complete(self.package, self.manifest)

    def test_conflicting_completed_result_and_binding_immutable(self):
        self.registry.complete(self.package, self.manifest)
        self.reject_preserved(package={**self.package, 'summary': 'Different payload'})
        self.put(self.repo / self.package['review_path'], 'Changed review\n' + '\n'.join(
            self.package[f'reviewed_{name}_sha256'] for name in ('report', 'metrics')))
        self.reject_preserved()
        self.assertEqual(self.registry.status('TEST-register')['review_integrity'], 'stale')

    def test_status_never_certifies_native_web_or_github(self):
        self.registry.complete(self.package, self.manifest)
        result = self.registry.status('TEST-register')
        self.assertEqual(result['review_integrity'], 'current')
        self.assertEqual(result['source_integrity'], 'current')
        for key in ('github_publication', 'browser_verification', 'native_lifecycle', 'artifact_availability'):
            self.assertEqual(result[key], 'unverified')
        self.put(self.repo / self.package['report_path'], 'Changed report')
        result = self.registry.status('TEST-register')
        self.assertEqual(result['source_integrity'], 'stale'); self.assertEqual(result['review_integrity'], 'stale')

    def test_importer_guard_preserves_active_and_nonhistorical_repos(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            export(self.base / 'nonexistent-source', self.repo)
        self.assertEqual(before, self.snapshot())
        self.put(self.repo / 'records/assignments.json', {'schema_version': 1, 'assignments': []})
        self.put(self.repo / 'records/catalog.json', {'schema_version': 1, 'experiments': [{'experiment_id': 'TEST-existing'}]})
        before = self.snapshot()
        with self.assertRaises(ValueError):
            export(self.base / 'nonexistent-source', self.repo)
        self.assertEqual(before, self.snapshot())

    def test_importer_rejects_malformed_guard_and_symlink(self):
        path = self.repo / 'records/assignments.json'
        self.put(path, {'schema_version': 1})
        with self.assertRaises(ValueError):
            export(self.base / 'nonexistent-source', self.repo)
        path.unlink(); path.symlink_to(self.config_path)
        with self.assertRaises(OSError):
            export(self.base / 'nonexistent-source', self.repo)

    def test_cli_returns_safe_receipts_and_nonzero_errors(self):
        package = self.base / 'package.json'; artifacts = self.base / 'artifacts.json'
        self.put(package, self.package); self.put(artifacts, self.manifest)
        output = io.StringIO()
        with redirect_stdout(output):
            code = module.main(['--config', str(self.config_path), 'complete', '--package', str(package), '--artifacts', str(artifacts)])
        self.assertEqual(code, 0); self.assertEqual(json.loads(output.getvalue())['browser_verification'], 'unverified')
        self.put(package, {**self.package, 'summary': 'Bearer privatevalue'})
        output = io.StringIO()
        with redirect_stdout(output):
            code = module.main(['--config', str(self.config_path), 'complete', '--package', str(package), '--artifacts', str(artifacts)])
        self.assertEqual(code, 1); self.assertNotIn('privatevalue', output.getvalue()); self.assertNotIn(str(self.base), output.getvalue())

    def test_duplicate_json_key_and_nonfinite_json_rejected(self):
        for payload in ('{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                module.parse(payload)


if __name__ == '__main__':
    unittest.main()
