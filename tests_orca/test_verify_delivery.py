import hashlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from orchestration.verify_delivery import snapshot, verify_browser, verify_github


class SeparateAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {'repo_root': str(self.root)}
        self.item = {'experiment_id': 'TEST-VERIFY', 'slot': 'unassigned', 'execution_status': 'succeeded',
                     'report_path': 'docs/experiments/TEST-VERIFY.md',
                     'metrics_path': 'records/TEST-VERIFY/metrics.json',
                     'review_path': 'docs/reviews/TEST-VERIFY.md',
                     'review_binding_path': 'docs/reviews/TEST-VERIFY.binding.json',
                     'evidence': [{'artifact_id': 'fixture-video', 'kind': 'video'}]}
        def write(path, value):
            path = self.root / path; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
            return hashlib.sha256(path.read_bytes()).hexdigest()
        self.item['report_sha256'] = write(self.item['report_path'], 'Synthetic fixture report')
        self.item['metrics_sha256'] = write(self.item['metrics_path'], json.dumps({'metrics': [
            {'label':'fixture','value':1,'unit':'fixture','scope':'synthetic'}]}))
        review_hash = write(self.item['review_path'], 'Synthetic review')
        write(self.item['review_binding_path'], json.dumps({
            'review_path':self.item['review_path'],'review_sha256':review_hash,
            'reviewed_sources':{'TEST-VERIFY':{k:self.item[k] for k in ('report_sha256','metrics_sha256')}}}))
        write('records/catalog.json', json.dumps({'experiments':[self.item]}))
        self.sha = 'a' * 40

    def tearDown(self):
        self.temp.cleanup()

    def git(self, root, *args):
        if args[:2] == ('remote','get-url'):
            return b'https://github.com/example/fixture.git\n'
        if args[0] == 'ls-remote':
            return (self.sha+'\trefs/heads/main\n').encode()
        if args[0] == 'show':
            return (self.root / args[1].split(':',1)[1]).read_bytes()
        raise AssertionError(args)

    def test_publication_is_verified_without_claiming_browser(self):
        with patch('orchestration.verify_delivery.command', side_effect=self.git):
            result = verify_github(self.config, 'TEST-VERIFY', self.sha)
        self.assertTrue(result['passed'])
        self.assertFalse(result['browser_verified'])
        self.assertEqual(len(result['source_sha256']),4)

    def test_remote_mismatch_and_local_changed_source_do_not_pass(self):
        with patch('orchestration.verify_delivery.command', side_effect=self.git):
            with self.assertRaisesRegex(ValueError,'Remote branch'):
                verify_github(self.config, 'TEST-VERIFY', 'b'*40)
        (self.root / self.item['report_path']).write_text('changed after review')
        with self.assertRaisesRegex(ValueError,'changed'):
            snapshot(self.config, 'TEST-VERIFY')

    def test_http_success_is_not_browser_acceptance(self):
        api = {**self.item, 'review_integrity':'current',
               'current_source_sha256': snapshot(self.config, 'TEST-VERIFY')[3],
               'source_integrity':{'report_match':True,'metrics_match':True}}
        js = (Path(__file__).resolve().parents[1] / 'webapp/app.js').read_bytes()
        def response(url, **kwargs):
            return io.BytesIO(js if url.endswith('.js') else json.dumps(api).encode())
        with patch('orchestration.verify_delivery.urllib.request.urlopen', side_effect=response), \
             patch('orchestration.verify_delivery.subprocess.check_output', return_value=b'{"ok":false}'):
            with self.assertRaisesRegex(ValueError,'Browser operation failed'):
                verify_browser(self.config,'TEST-VERIFY','fixture-page','http://127.0.0.1:8766','orca-ide',0)

    def test_browser_never_visits_nonlocal_endpoint(self):
        with patch('orchestration.verify_delivery.urllib.request.urlopen') as request:
            with self.assertRaisesRegex(ValueError,'loopback'):
                verify_browser(self.config,'TEST-VERIFY','page','https://example.com','orca-ide')
            request.assert_not_called()

    def test_browser_cli_failure_keeps_its_reason(self):
        api = {**self.item, 'review_integrity':'current',
               'current_source_sha256': snapshot(self.config, 'TEST-VERIFY')[3],
               'source_integrity':{'report_match':True,'metrics_match':True}}
        js = (Path(__file__).resolve().parents[1] / 'webapp/app.js').read_bytes()
        def response(url, **kwargs):
            return io.BytesIO(js if url.endswith('.js') else json.dumps(api).encode())
        failure = subprocess.CalledProcessError(1, ['orca-ide'],
            output=b'{"ok":false,"error":{"code":"browser_tab_not_found","message":"Page absent"}}')
        with patch('orchestration.verify_delivery.urllib.request.urlopen', side_effect=response), \
             patch('orchestration.verify_delivery.subprocess.check_output', side_effect=failure):
            with self.assertRaisesRegex(ValueError,'browser_tab_not_found: Page absent'):
                verify_browser(self.config,'TEST-VERIFY','fixture-page','http://127.0.0.1:8766','orca-ide',0)

    def test_other_server_review_is_not_local_review_acceptance(self):
        hashes = snapshot(self.config, 'TEST-VERIFY')[3]
        hashes[self.item['review_path']] = 'b' * 64
        api = {**self.item, 'review_integrity':'current', 'current_source_sha256':hashes,
               'source_integrity':{'report_match':True,'metrics_match':True}}
        with patch('orchestration.verify_delivery.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(api).encode())), \
             patch('orchestration.verify_delivery.subprocess.check_output') as browser:
            with self.assertRaisesRegex(ValueError,'source or review version'):
                verify_browser(self.config,'TEST-VERIFY','fixture-page','http://127.0.0.1:8766','orca-ide',0)
            browser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
