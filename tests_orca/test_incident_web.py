import hashlib
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sceneguard.exp0036_application import make_bundle
from webapp.app import app


class IncidentWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for p in ('records', 'outputs', 'runtime'):
            (self.root / p).mkdir()
        result = {'experiment':'EXP-0035', 'video_id':'fixture', 'source_window':[10, 20],
                  'events':[{'status':'침입 의심','decision_time_pts':11, 'raw_id':1, 'segment':'s', 'secret':'not exposed'},
                            {'status':'침입 의심','decision_time_pts':12, 'raw_id':2}], 'existing_alerts':[]}
        self.bundle = make_bundle(result, 'C3', 'C3_fence', 'fixture')
        self.path = self.root / 'outputs/cards.json'
        self.write_bundle()
        self.catalog = {'experiments':[{'experiment_id':'EXP-0035','evidence':[{'artifact_id':'clip','kind':'video'}]}]}
        (self.root / 'records/catalog.json').write_text(json.dumps(self.catalog))
        self.assignments = self.root / 'records/assignments.json'
        self.assignments.write_text(json.dumps({'assignments':[{'experiment_id':'EXP-0036'}]}))
        (self.root / 'outputs/clip.mp4').write_bytes(b'video')
        self.config = {'repo_root':str(self.root), 'artifact_allow_root':str(self.root/'outputs'), 'runtime_dir':str(self.root/'runtime'),
                       'artifacts':{'clip':{'path':str(self.root/'outputs/clip.mp4'),'kind':'video'}},
                       'incident_bundles':{'007':{'path':'cards.json','sha256':self.sha(), 'media_artifact_id':'clip', 'experiment_id':'EXP-0036'}}}
        self.cfg = self.root / 'config.json'; self.write_config()
        self.env = patch.dict(os.environ, {'SCENEGUARD_LAB_CONFIG':str(self.cfg)}); self.env.start()
        self.client = TestClient(app, base_url='http://localhost')

    def tearDown(self):
        self.client.close(); self.env.stop(); self.tmp.cleanup()

    def write_bundle(self): self.path.write_text(json.dumps(self.bundle, ensure_ascii=False))
    def sha(self): return hashlib.sha256(self.path.read_bytes()).hexdigest()
    def write_config(self): self.cfg.write_text(json.dumps(self.config))
    def claim(self, key, headers=None):
        return self.client.post('/api/incidents/007/claim', json={'notification_key':key}, headers=headers or {'Origin':'http://localhost'})

    def test_sanitized_and_registered(self):
        r = self.client.get('/api/incidents/007'); self.assertEqual(r.status_code, 200)
        self.assertNotIn('source_event', r.text); self.assertNotIn('secret', r.text)
        self.assertNotIn('provenance', r.text)
        self.assertEqual(len(r.json()['timeline']), 2)
        self.assertEqual(self.client.get('/api/incidents/030').status_code, 404)
        self.assignments.write_text('{"assignments":[]}')
        self.assertEqual(self.client.get('/api/incidents/007').status_code, 404)

    def test_tamper_partial_path_and_unregistered_media(self):
        self.path.write_text('{}'); self.assertEqual(self.client.get('/api/incidents/007').status_code, 404)
        self.write_bundle(); self.bundle['timeline'].pop(); self.write_bundle()
        self.config['incident_bundles']['007']['sha256'] = self.sha(); self.write_config()
        self.assertEqual(self.client.get('/api/incidents/007').status_code, 404)
        self.config['incident_bundles']['007']['path'] = '../config.json'; self.write_config()
        self.assertEqual(self.client.get('/api/incidents/007').status_code, 404)
        self.config['incident_bundles']['007']['path'] = 'link.json'
        (self.root/'outputs/link.json').symlink_to(self.path); self.write_config()
        self.assertEqual(self.client.get('/api/incidents/007').status_code, 404)
        self.config['incident_bundles']['007']['path'] = 'cards.json'
        self.config['incident_bundles']['007']['media_artifact_id'] = 'other'; self.write_config()
        self.assertEqual(self.client.get('/api/incidents/007').status_code, 404)

    def test_future_and_duplicate_snapshot_membership_rejected(self):
        first = self.bundle['timeline'][0]['card']
        first['event_ids'].append(self.bundle['timeline'][1]['event_id'])
        first['alert_count'] = 2
        first['track_ids'] = [1, 2]
        self.write_bundle(); self.config['incident_bundles']['007']['sha256'] = self.sha(); self.write_config()
        self.assertEqual(self.client.get('/api/incidents/007').status_code, 404)
        first['event_ids'] = [self.bundle['timeline'][0]['event_id']]
        first['alert_count'] = 1; first['track_ids'] = [1]
        second = self.bundle['timeline'][1]['card']
        second['event_ids'] = [second['event_ids'][0], second['event_ids'][0]]
        self.write_bundle(); self.config['incident_bundles']['007']['sha256'] = self.sha(); self.write_config()
        self.assertEqual(self.client.get('/api/incidents/007').status_code, 404)

    def test_claim_guard_idempotent_and_concurrent(self):
        key = self.bundle['timeline'][0]['notification_key']
        self.assertEqual(self.claim(key, {'Origin':'http://evil.example'}).status_code, 403)
        self.assertEqual(self.claim(key, {'Origin':'http://localhost','Sec-Fetch-Site':'cross-site'}).status_code, 403)
        self.assertEqual(self.claim('notify:incident-000000000000000000000000').status_code, 404)
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda _: self.claim(key), range(8)))
        self.assertTrue(all(r.status_code == 200 for r in responses))
        self.assertEqual(sum(r.json()['claimed'] for r in responses), 1)
        self.assertFalse(self.claim(key).json()['claimed'])
        self.assertEqual(self.claim(key).json()['delivery'], 'not_verified')


if __name__ == '__main__': unittest.main()
