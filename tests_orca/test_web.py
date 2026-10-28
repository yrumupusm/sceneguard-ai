import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from webapp.app import app


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for directory in ['records/EXP-0007', 'docs/experiments', 'docs/reviews', 'runtime', 'outputs']:
            (self.root / directory).mkdir(parents=True)
        self.report = self.root / 'docs/experiments/report.md'
        self.report.write_text('<script>alert(1)</script>\n\n![remote](https://example.com/a.png)', encoding='utf-8')
        (self.root / 'docs/reviews/review.md').write_text('별도 검토', encoding='utf-8')
        self.metrics = {'metrics': [{'label': '정확도', 'value': None, 'unit': '%', 'sample_n': None, 'scope': '미측정'}]}
        (self.root / 'records/EXP-0007/metrics.json').write_text(json.dumps(self.metrics), encoding='utf-8')
        self.item = {'experiment_id': 'EXP-0007', 'slot': 'unassigned', 'report_path': 'docs/experiments/report.md', 'review_path': 'docs/reviews/review.md', 'metrics_path': 'records/EXP-0007/metrics.json', 'evidence': [{'artifact_id': 'clip', 'kind': 'video', 'label': 'clip'}, {'artifact_id': 'missing', 'kind': 'image'}]}
        self.catalog_path = self.root / 'records/catalog.json'
        self.write_catalog()
        (self.root / 'records/roles.json').write_text('{}', encoding='utf-8')
        (self.root / 'outputs/clip.mp4').write_bytes(b'0123456789')
        self.config = {'repo_root': str(self.root), 'runtime_dir': str(self.root / 'runtime'), 'artifact_allow_root': str(self.root / 'outputs'), 'artifacts': {'clip': {'path': str(self.root / 'outputs/clip.mp4'), 'kind': 'video'}, 'missing': {'path': str(self.root / 'outputs/missing.png'), 'kind': 'image'}}}
        self.config_path = self.root / 'config.json'
        self.write_config()
        self.env = patch.dict(os.environ, {'SCENEGUARD_LAB_CONFIG': str(self.config_path)})
        self.env.start()
        self.client = TestClient(app, base_url='http://localhost')

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def write_catalog(self):
        self.catalog_path.write_text(json.dumps({'experiments': [self.item]}), encoding='utf-8')

    def write_config(self):
        self.config_path.write_text(json.dumps(self.config), encoding='utf-8')

    def test_range_head_and_missing(self):
        r = self.client.get('/artifacts/clip', headers={'Range': 'bytes=2-5'})
        self.assertEqual((r.status_code, r.content, r.headers['content-range']), (206, b'2345', 'bytes 2-5/10'))
        self.assertEqual(self.client.get('/artifacts/clip', headers={'Range': 'bytes=-3'}).content, b'789')
        self.assertEqual(self.client.get('/artifacts/clip', headers={'Range': 'bytes=99-'}).status_code, 416)
        head = self.client.head('/artifacts/clip', headers={'Range': 'bytes=2-5'})
        self.assertEqual((head.status_code, head.content, head.headers['content-length']), (206, b'', '4'))
        self.assertEqual(self.client.get('/artifacts/missing').status_code, 404)
        self.assertFalse(self.client.get('/api/experiments/EXP-0007').json()['evidence'][1]['available'])

    def test_traversal_symlinks_and_unregistered(self):
        self.assertEqual(self.client.get('/artifacts/%2e%2e%2fclip').status_code, 404)
        self.config['artifacts']['clip']['path'] = str(self.root / 'outputs/../config.json')
        self.write_config()
        self.assertEqual(self.client.get('/artifacts/clip').status_code, 404)
        (self.root / 'outputs/link.mp4').symlink_to(self.root / 'outputs/clip.mp4')
        self.config['artifacts']['clip']['path'] = str(self.root / 'outputs/link.mp4')
        self.write_config()
        self.assertEqual(self.client.get('/artifacts/clip').status_code, 404)
        self.config['artifacts']['extra'] = {'path': str(self.root / 'outputs/clip.mp4'), 'kind': 'video'}
        self.write_config()
        self.assertEqual(self.client.get('/artifacts/extra').status_code, 404)
        self.item['report_path'] = 'docs/experiments/../../config.json'
        self.write_catalog()
        self.assertEqual(self.client.get('/api/experiments/EXP-0007').status_code, 503)

    def test_markup_null_status_and_methods(self):
        r = self.client.get('/api/experiments/EXP-0007')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsNone(body['metrics'][0]['value'])
        self.assertNotIn('<script>', body['report_html'])
        self.assertNotIn('<img', body['report_html'])
        self.assertIn('&lt;script&gt;', body['report_html'])
        self.assertIn('미측정', self.client.get('/assets/app.js').text)
        self.assertEqual(self.client.get('/api/status').json()['state'], 'unverified')
        self.assertEqual(self.client.post('/api/catalog').status_code, 405)
        self.assertEqual(self.client.get('/api/catalog', headers={'host':'example.com'}).status_code, 400)
        self.assertIn("default-src 'self'", r.headers['content-security-policy'])
        self.assertEqual(r.headers['cross-origin-resource-policy'], 'same-origin')


if __name__ == '__main__':
    unittest.main()
