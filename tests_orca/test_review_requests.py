"""Temporary-only request persistence, causal revisions, scoped sources and API."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from webapp.app import app
from webapp import review_requests  # noqa: F401; registration is owned by app integration
from webapp.review_request_store import RequestConflict, ReviewRequestStore, StaleBinding, configured_store


ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReviewRequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.exp = 'EXP-TEST'
        self.report = self.repo / 'docs/experiments/EXP-TEST-results.md'
        self.report.parent.mkdir(parents=True)
        self.report.write_text('Saved experiment, no human truth.\n')
        write(self.repo / 'records/EXP-TEST/metrics.json', {'metrics': []})
        self.catalog = {'experiments': [dict(experiment_id=self.exp,
            report_path='docs/experiments/EXP-TEST-results.md', metrics_path='records/EXP-TEST/metrics.json',
            evidence=[dict(artifact_id='video', kind='video')]),
            dict(experiment_id='OTHER', evidence=[dict(artifact_id='other', kind='image')])]}
        write(self.repo / 'records/catalog.json', self.catalog)
        self.video = self.root / 'media/video.mp4'
        self.video.parent.mkdir()
        self.video.write_bytes(b'not decoded; registered saved video')
        self.other = self.root / 'media/other.png'
        self.other.write_bytes(b'other experiment')
        self.bundle = self.root / 'media/bundle.json'
        self.bundle_digest = write(self.bundle, {'source_window': [48., 105.], 'events': []})
        self.c = dict(repo_root=str(self.repo), artifact_allow_root=str(self.root / 'media'),
            runtime_dir=str(self.root / 'runtime'),
            artifacts={'video': dict(kind='video', path=str(self.video)),
                       'other': dict(kind='image', path=str(self.other))},
            incident_bundles={'bundle': dict(experiment_id=self.exp, path='bundle.json', sha256=self.bundle_digest,
                                            media_artifact_id='video', session_id='saved-run')})
        self.config_path = self.root / 'config.json'
        write(self.config_path, self.c)
        env = patch.dict(os.environ, {'SCENEGUARD_LAB_CONFIG': str(self.config_path)})
        env.start()
        self.addCleanup(env.stop)
        self.db = configured_store(self.c)
        self.spec = dict(id='question-1', experiment_id=self.exp, title='관찰 확인', question='이 구간에서 무엇을 보았나요?',
                         options=['접근', '통과', '불확실'], bundle_id='bundle', artifact_id='video',
                         source_time=64., end_time=74., source_label='E01_007')
        self.client = TestClient(app, base_url='http://localhost')
        self.addCleanup(self.client.close)
        self.url = '/api/review-requests/question-1/answer'
        self.headers = {'origin': 'http://localhost'}
        self.answer = dict(expected_version=1, reviewer='human', answer='사람을 따라갑니다', note='한 문맥의 관찰')

    def create(self, **overrides):
        return self.db.create(self.c, dict(self.spec, **overrides))

    def answer_api(self, **overrides):
        return self.client.post(self.url, headers=self.headers, json=dict(self.answer, **overrides))

    def cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/review_requests.py'), *args],
                              cwd=ROOT, env=env, text=True, capture_output=True)

    def test_empty_reads_do_not_create_store_or_claim_completion(self):
        self.assertEqual(self.db.list(), [])
        self.assertEqual(self.db.summary(), {})
        self.assertEqual(self.client.get('/api/review-requests', params={'experiment_id': self.exp}).json(), {'requests': []})
        self.assertEqual(self.client.get('/api/review-requests/summary').json(), {'experiments': {}})
        self.assertEqual(json.loads(self.cli('pending').stdout), {'requests': []})
        self.assertFalse(self.db.path.exists())
        self.assertFalse(self.db.path.parent.exists())

    def test_persistence_history_and_summary_across_reopened_store(self):
        row = self.create()
        self.assertEqual((row['status'], row['version'], row['answer_version']), ('pending', 1, 0))
        self.assertEqual(row['history'][0]['action'], 'created')
        self.assertIsNone(row['answer'])
        self.assertEqual(self.answer_api().status_code, 200)
        reopened = ReviewRequestStore(self.db.path)
        row = reopened.get(row['id'])
        self.assertEqual((row['status'], row['version'], row['answer_version']), ('answered', 2, 1))
        self.assertEqual([r['action'] for r in row['history']], ['created', 'answered'])
        self.assertIsNone(row['history'][0]['answer'])
        self.assertEqual(row['history'][1]['answer'], self.answer['answer'])
        expected = dict(total=1, pending=0, answered=1, acknowledged=0, applied=0, deferred=0)
        self.assertEqual(self.client.get('/api/review-requests/summary').json()['experiments'][self.exp], expected)
        self.assertEqual(self.client.get('/api/review-requests', params={'experiment_id': 'OTHER'}).json(), {'requests': []})

    def test_exact_version_conflict_preserves_original_answer(self):
        self.create()
        self.answer_api()
        before = self.db.path.read_bytes()
        conflict = self.answer_api(answer='stale tab')
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()['request']['version'], 2)
        self.assertEqual(self.db.path.read_bytes(), before)
        self.assertEqual(len(self.db.get('question-1')['history']), 2)

    def test_two_writers_cannot_both_answer_the_same_revision(self):
        self.create()
        def answer(value):
            try:
                return configured_store(self.c).answer(self.c, 'question-1', **dict(self.answer, answer=value))['version']
            except RequestConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(answer, ['one', 'two']))
        self.assertCountEqual(results, [2, 'conflict'])
        self.assertEqual(len(self.db.get('question-1')['history']), 2)

    def test_lifecycle_guards_and_edit_resets_obsolete_processing(self):
        self.create()
        with self.assertRaises(RequestConflict):
            self.db.acknowledge(self.c, 'question-1', expected_version=1, answer_version=1)
        self.answer_api()
        with self.assertRaises(RequestConflict):
            self.db.resolve(self.c, 'question-1', expected_version=2, answer_version=1, outcome='applied', note='premature')
        with self.assertRaises(RequestConflict):
            self.db.acknowledge(self.c, 'question-1', expected_version=2, answer_version=2)
        row = self.db.acknowledge(self.c, 'question-1', expected_version=2, answer_version=1, note='read exact answer')
        self.assertEqual(row['status'], 'acknowledged')
        row = self.db.resolve(self.c, 'question-1', expected_version=3, answer_version=1, outcome='applied', note='recorded in report')
        self.assertEqual(row['status'], 'applied')
        result = self.answer_api(expected_version=4, answer='수정한 관찰')
        self.assertEqual(result.status_code, 200)
        row = result.json()['request']
        self.assertEqual((row['status'], row['version'], row['answer_version'], row['processing_note']), ('answered', 5, 2, ''))
        self.assertEqual(row['history'][3]['processing_note'], 'recorded in report')
        self.assertEqual(row['history'][3]['answer'], self.answer['answer'])
        with self.assertRaises(RequestConflict):
            self.db.resolve(self.c, 'question-1', expected_version=5, answer_version=1, outcome='deferred', note='old answer')
        self.db.acknowledge(self.c, 'question-1', expected_version=5, answer_version=2)
        row = self.db.resolve(self.c, 'question-1', expected_version=6, answer_version=2, outcome='deferred', note='needs separate scope')
        self.assertEqual(row['status'], 'deferred')
        self.assertEqual(row['source_binding_sha256'], row['history'][0]['source_binding_sha256'])

    def test_answer_requires_same_origin_json(self):
        self.create()
        for headers in ({}, {'origin': 'https://elsewhere.example'},
                        dict(self.headers, **{'sec-fetch-site': 'cross-site'}),
                        dict(self.headers, **{'content-type': 'text/plain'})):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.post(self.url, headers=headers, json=self.answer).status_code, 403)
        self.assertEqual(self.db.get('question-1')['version'], 1)

    def test_answer_schema_nonempty_and_strict_integer_version(self):
        self.create()
        for override in ({'answer': ''}, {'answer': '  \n'}, {'answer': ['yes']}, {'reviewer': ''},
                         {'reviewer': 3}, {'note': None}, {'expected_version': True}, {'expected_version': 1.0},
                         {'expected_version': 0}, {'experiment_id': 'OTHER'}, {'status': 'applied'}):
            with self.subTest(override=override):
                self.assertEqual(self.answer_api(**override).status_code, 400)
        for body in ([], None, {'answer': 'only field'}):
            headers = dict(self.headers, **{'content-type': 'application/json'})
            self.assertEqual(self.client.post(self.url, headers=headers, content=json.dumps(body)).status_code, 400)
        self.assertEqual(self.client.post(self.url, headers=dict(self.headers, **{'content-type': 'application/json'}), content='{').status_code, 400)
        self.assertEqual(self.db.get('question-1')['version'], 1)

    def test_only_answer_is_exposed_for_web_mutation(self):
        self.create()
        for path in ('/api/review-requests', '/api/review-requests/question-1/acknowledge',
                     '/api/review-requests/question-1/resolve'):
            self.assertIn(self.client.post(path, headers=self.headers, json=self.spec).status_code, (404, 405))
        self.assertEqual(self.client.post('/api/review-requests/unknown/answer', headers=self.headers, json=self.answer).status_code, 404)

    def test_creation_rejects_cross_experiment_or_arbitrary_source(self):
        variants = [dict(experiment_id='UNKNOWN'), dict(experiment_id='OTHER'), dict(bundle_id='../bundle'),
                    dict(bundle_id='https://example.com'), dict(artifact_id='other'), dict(artifact_id=str(self.video)),
                    dict(url='https://example.com'), dict(path=str(self.video)), dict(options='not array'),
                    dict(options=['same', 'same']), dict(question=''), dict(id='../bad')]
        for override in variants:
            with self.subTest(override=override), self.assertRaises((ValueError, KeyError)):
                self.create(**override)
        self.assertFalse(self.db.path.exists())

    def test_timestamp_scope_and_finite_values(self):
        for override in (dict(source_time=47.99), dict(source_time=105.01), dict(end_time=106),
                         dict(end_time=63), dict(source_time=None), dict(source_time=True),
                         dict(source_time=float('nan')), dict(end_time=float('inf')),
                         dict(bundle_id=None)):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.create(**override)
        row = self.create(source_time=48, end_time=105)
        self.assertEqual(row['source_time'], 48)

    def test_unscoped_question_and_registered_artifact_without_time(self):
        row = self.create(bundle_id=None, artifact_id=None, source_time=None, end_time=None)
        self.assertIsNone(row['artifact_id'])
        row = self.create(id='artifact-only', bundle_id=None, source_time=None, end_time=None)
        self.assertEqual(row['artifact_id'], 'video')

    def test_timed_artifact_requires_bundle_playback_clock(self):
        self.c['artifacts']['video']['source_window'] = [0, 10]
        with self.assertRaises(ValueError):
            self.db.create(self.c, dict(self.spec, bundle_id=None, source_time=1, end_time=9))

    def test_cli_can_resume_acknowledged_but_unresolved_answers(self):
        self.create()
        self.answer_api()
        row = self.db.acknowledge(self.c, 'question-1', expected_version=2, answer_version=1)
        self.assertEqual(json.loads(self.cli('pending').stdout)['requests'], [])
        resumed = json.loads(self.cli('pending', '--include-acknowledged').stdout)['requests']
        self.assertEqual([(r['id'], r['status'], r['version']) for r in resumed], [('question-1', 'acknowledged', row['version'])])

    def test_duplicate_id_does_not_replace_question_or_history(self):
        self.create()
        before = self.db.get('question-1')
        with self.assertRaises(RequestConflict):
            self.create(question='overwrite')
        self.assertEqual(self.db.get('question-1'), before)

    def test_stale_report_binding_rejects_answer_and_cli_processing(self):
        self.create()
        self.answer_api()
        before = self.db.path.read_bytes()
        self.report.write_text('Changed saved report')
        response = self.answer_api(expected_version=2)
        self.assertEqual(response.status_code, 409)
        self.assertIn('binding', response.json()['detail'])
        with self.assertRaises(StaleBinding):
            self.db.acknowledge(self.c, 'question-1', expected_version=2, answer_version=1)
        result = self.cli('acknowledge', 'question-1', '--expected-version', '2', '--answer-version', '1')
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(self.db.path.read_bytes(), before)

    def test_changed_bundle_registration_or_media_bytes_reject_writes(self):
        self.create()
        self.video.write_bytes(b'changed media under same allowlisted path')
        self.assertEqual(self.answer_api().status_code, 409)
        self.video.write_bytes(b'not decoded; registered saved video')
        config = deepcopy(self.c)
        config['incident_bundles']['bundle']['session_id'] = 'different-session'
        with self.assertRaises(StaleBinding):
            self.db.answer(config, 'question-1', **self.answer)
        self.bundle.write_text('{}')
        self.assertEqual(self.answer_api().status_code, 409)

    def test_registration_changes_and_missing_catalog_do_not_transfer_answer(self):
        self.create()
        changed = deepcopy(self.catalog)
        changed['experiments'][0]['evidence'][0]['label'] = 'different registered source label'
        write(self.repo / 'records/catalog.json', changed)
        self.assertEqual(self.answer_api().status_code, 409)
        write(self.repo / 'records/catalog.json', {'experiments': []})
        self.assertEqual(self.answer_api().status_code, 409)

    def test_symlink_evidence_and_symlink_database_are_rejected(self):
        self.video.unlink()
        self.video.symlink_to(self.other)
        with self.assertRaises((OSError, ValueError)):
            self.create()
        self.db.path.parent.mkdir()
        self.db.path.symlink_to(self.other)
        with self.assertRaises(ValueError):
            configured_store(self.c)

    def test_cli_create_pending_acknowledge_resolve_with_exact_guards(self):
        spec_path = self.root / 'request.json'
        write(spec_path, self.spec)
        result = self.cli('--config', str(self.config_path), 'create', '--spec-file', str(spec_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['request']['status'], 'pending')
        self.assertEqual(json.loads(self.cli('pending').stdout)['requests'], [])
        self.answer_api()
        before = self.db.path.read_bytes()
        result = self.cli('pending', '--experiment-id', self.exp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['requests']), 1)
        self.assertEqual(self.db.path.read_bytes(), before)
        result = self.cli('acknowledge', 'question-1', '--expected-version', '2', '--answer-version', '99')
        self.assertEqual(result.returncode, 3)
        result = self.cli('acknowledge', 'question-1', '--expected-version', '2', '--answer-version', '1', '--note', 'read')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.cli('pending').stdout)['requests'], [])
        result = self.cli('resolve', 'question-1', '--expected-version', '3', '--answer-version', '1', '--outcome', 'deferred', '--note', 'needs separate work')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['request']['status'], 'deferred')
        self.assertEqual(self.db.get('question-1')['version'], 4)

    def test_cli_rejects_missing_versions_or_empty_resolution_note(self):
        self.create()
        result = self.cli('acknowledge', 'question-1')
        self.assertEqual(result.returncode, 2)
        result = self.cli('resolve', 'question-1', '--expected-version', '1', '--answer-version', '1', '--outcome', 'applied', '--note', '')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.db.get('question-1')['version'], 1)


if __name__ == '__main__':
    unittest.main()
