import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from orchestration.smoke import restart_smoke


class RestartEvidence(unittest.TestCase):
    def check_case(self, *, completed_first=False, child_finish=102, connected=True, services_live=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.json'
            config.write_text(json.dumps({'repo_root': directory, 'runtime_dir': directory, 'orca_run_id': 'fixture'}))
            running = {'job_id': 'job', 'attempt_id': 'attempt', 'child_pid': 123,
                       'child_identity': 'fixture', 'status': 'running', 'finished_at': None}
            completed = {**running, 'status': 'succeeded', 'finished_at': 103}
            phase = {'complete': completed_first, 'initial': True}
            queue = MagicMock(); queue.runtime = root
            def status():
                if phase['initial']:
                    phase['initial'] = False
                    return {'jobs': [], 'attempts': []}
                return {'jobs': [], 'attempts': [completed if phase['complete'] else running]}
            queue.status.side_effect = status
            queue.enqueue.return_value = {'job_id': 'job'}
            child_path = root / 'attempts/attempt/mock-result.json'
            child_path.parent.mkdir(parents=True)
            child_path.write_text(json.dumps({'pid': 123, 'started_at': 99, 'finished_at': child_finish}))
            process = MagicMock()
            process.communicate.side_effect = lambda **_: phase.update(complete=True)
            service_calls = []
            def service(_, action):
                service_calls.append(action)
                if action == 'status':
                    return {'services': {n: {'identity_matches': services_live} for n in ('web', 'projection')}}
                if action == 'stop':
                    return {'stopped': True}
                return {'url': 'http://fixture', 'state': 'started' if connected else 'degraded',
                        'projection_state': 'connected' if connected else 'disconnected'}
            with patch('orchestration.smoke.Queue', return_value=queue), \
                 patch('orchestration.smoke.subprocess.Popen', return_value=process), \
                 patch('orchestration.smoke.service', side_effect=service), \
                 patch('orchestration.smoke.process_state', return_value='live'), \
                 patch('orchestration.smoke.time.time', side_effect=[100, 101]), \
                 patch('orchestration.smoke.urllib.request.urlopen') as http:
                http.return_value.__enter__.return_value.status = 200
                if completed_first or child_finish < 101 or not connected or not services_live:
                    with self.assertRaises(RuntimeError):
                        restart_smoke(config, 'fixture', 'task')
                else:
                    self.assertTrue(restart_smoke(config, 'fixture', 'task')['passed'])
                if not services_live:
                    queue.enqueue.assert_not_called()
            result = json.loads((root / 'fixture-service-smoke.json').read_text())
            return result, service_calls

    def test_already_finished_attempt_cannot_prove_overlap(self):
        result, calls = self.check_case(completed_first=True)
        self.assertFalse(result['passed'])
        self.assertEqual(result['state'], 'inconclusive')
        self.assertNotIn('stop', calls)

    def test_early_child_completion_and_degraded_restart_are_not_success(self):
        for options in ({'child_finish': 99}, {'connected': False}):
            with self.subTest(options=options):
                result, _ = self.check_case(**options)
                self.assertFalse(result['passed'])
                self.assertIn('error', result)

    def test_live_attempt_crossing_entire_stop_is_required(self):
        result, _ = self.check_case()
        self.assertTrue(result['passed'])
        self.assertLess(result['web_stopped_at'], result['child_finished_at'])
        self.assertEqual(result['attempt_at_stop']['attempt_id'], result['attempt_after_stop']['attempt_id'])

    def test_missing_owned_services_refuses_mock_submission(self):
        result, calls = self.check_case(services_live=False)
        self.assertFalse(result['passed'])
        self.assertEqual(calls, ['status'])


if __name__ == '__main__':
    unittest.main()
