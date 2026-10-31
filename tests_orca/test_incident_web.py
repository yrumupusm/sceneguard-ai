import hashlib
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sceneguard.exp0036_application import make_bundle
from sceneguard.incident_cards import group_events
from sceneguard.incident_notifications import group_notifications, notification_cards_at
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

    def test_registered_review_conflict_history_and_authorization(self):
        cid = self.bundle['timeline'][0]['incident_id']
        url = f'/api/incidents/007/reviews/{cid}'
        headers = {'Origin':'http://localhost'}
        draft = {'status':'침입 확인', 'reviewer':'검토자', 'note':'<b>plain</b>', 'expected_version':0, 'session_id':'fixture', 'bundle_sha256':self.sha()}
        query = {'session_id':'fixture', 'bundle_sha256':self.sha()}
        self.assertEqual(self.client.get(url, params=query).json(), {'review':None, 'history':[]})
        self.assertEqual(self.client.get(url, params={**query, 'bundle_sha256':'0'*64}).status_code, 409)
        self.assertEqual(self.client.post(url, json={**draft, 'bundle_sha256':'0'*64}, headers=headers).status_code, 409)
        self.assertEqual(self.client.post(url, json=draft).status_code, 403)
        self.assertEqual(self.client.post(url, json=draft, headers={'Origin':'http://evil'}).status_code, 403)
        self.assertEqual(self.client.post(url, json={**draft, 'path':'/tmp/x'}, headers=headers).status_code, 400)
        self.assertEqual(self.client.post('/api/incidents/007/reviews/incident-000000000000000000000000', json=draft, headers=headers).status_code, 404)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.client.post(url, json=draft, headers=headers), range(2)))
        self.assertEqual(sorted(r.status_code for r in responses), [200,409])
        conflict = next(r.json() for r in responses if r.status_code == 409)
        self.assertEqual(conflict['review']['version'], 1)
        updated = self.client.post(url, json={**draft, 'status':'판단 불가', 'expected_version':1}, headers=headers)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual([h['version'] for h in updated.json()['history']], [1,2])
        self.assertEqual(updated.json()['history'][0]['note'], '<b>plain</b>')
        self.assertEqual(self.client.get(url, params=query).json()['review']['version'], 2)
        self.assertTrue((self.root/'runtime/incident-reviews.sqlite3').exists())
        self.assertFalse((self.root/'runtime/exp0036-notification-receipts.sqlite3').exists())
        self.path.write_text('{}')
        self.assertEqual(self.client.get(url, params=query).status_code, 404)

    def test_generic_registration_and_session_binding(self):
        entry = dict(self.config['incident_bundles']['007'], experiment_id='EXP-0037', session_id='fixture',
                     source_label='007', view_label='baseline', provenance_label='저장 결과 재생')
        self.config['incident_bundles']['exp37-007-baseline'] = entry
        self.assignments.write_text(json.dumps({'assignments':[{'experiment_id':'EXP-0036'},{'experiment_id':'EXP-0037'}]}))
        self.write_config()
        self.assertEqual(self.client.get('/api/incidents/exp37-007-baseline').status_code, 200)
        self.assertEqual(self.client.get('/api/incident-registrations').json()[0]['id'], 'exp37-007-baseline')
        key = self.bundle['timeline'][0]['notification_key']
        url = '/api/incidents/exp37-007-baseline/claim'
        self.assertEqual(self.client.post(url, json={'notification_key':key}, headers={'Origin':'http://localhost'}).status_code, 404)
        entry['notification_enabled'] = True; self.write_config()
        self.assertTrue(self.client.post(url, json={'notification_key':key}, headers={'Origin':'http://localhost'}).json()['claimed'])
        (self.root/'outputs/original.mp4').write_bytes(b'original')
        self.config['artifacts']['original'] = {'path':str(self.root/'outputs/original.mp4'), 'kind':'video'}
        entry['media_artifact_id'] = 'original'; self.write_config()
        self.assertEqual(self.client.get('/artifacts/original').content, b'original')
        entry['session_id'] = 'wrong'; self.write_config()
        self.assertEqual(self.client.get('/api/incidents/exp37-007-baseline').status_code, 404)
        self.assertEqual(self.client.get('/api/incident-registrations').json(), [])
        self.assertEqual(self.client.get('/artifacts/original').status_code, 404)

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

    def test_exp0040_partition_and_existing_registration_isolation(self):
        original = deepcopy(self.bundle['events'])
        proposal = deepcopy(self.bundle)
        proposal.update(group_events(original[:1]))
        proposal.update(experiment='EXP-0040', full_original_alerts=original,
                        review_only_events=deepcopy(original[1:]))
        self.bundle = proposal; self.write_bundle()
        entry = dict(self.config['incident_bundles']['007'], experiment_id='EXP-0040',
                     session_id='fixture', source_label='007', view_label='제안', sha256=self.sha())
        self.config['incident_bundles']['exp40-007-proposed'] = entry
        self.assignments.write_text(json.dumps({'assignments':[{'experiment_id':'EXP-0036'}, {'experiment_id':'EXP-0040'}]}))
        self.write_config()
        url = '/api/incidents/exp40-007-proposed'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([e['event_id'] for e in data['events']], [original[0]['event_id']])
        self.assertEqual([e['event_id'] for e in data['review_only_alerts']], [original[1]['event_id']])
        self.assertNotIn('source_event', response.text)
        self.assertEqual(self.client.get('/api/incident-registrations').json(), [])
        self.assertEqual(self.client.get('/api/incident-registrations?experiment_id=EXP-0040').json()[0]['id'], 'exp40-007-proposed')
        self.assertEqual(self.client.post(url+'/claim', json={'notification_key':data['timeline'][0]['notification_key']}, headers={'Origin':'http://localhost'}).status_code, 404)
        entry['notification_enabled'] = True; self.write_config()
        self.assertEqual(self.client.get(url).status_code, 404)
        entry['notification_enabled'] = False; self.write_config()
        self.bundle['review_only_events'][0]['decision_time_pts'] = 19
        self.write_bundle(); entry['sha256'] = self.sha(); self.write_config()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_exp0041_causal_partition_and_baseline(self):
        original = deepcopy(self.bundle)
        entry = dict(self.config['incident_bundles']['007'], experiment_id='EXP-0041',
                     session_id='fixture', notification_enabled=False, source_label='007', view_label='baseline')
        self.config['incident_bundles']['exp41-007-baseline'] = entry
        self.assignments.write_text(json.dumps({'assignments':[{'experiment_id':'EXP-0041'}]}))
        self.write_config()
        url = '/api/incidents/exp41-007-baseline'
        baseline = self.client.get(url)
        self.assertEqual(baseline.status_code, 200)
        self.assertEqual(baseline.json()['contract'], 'group_all_then_notify_v1')
        self.assertEqual(baseline.json()['counts']['candidate_cards'], 1)
        events = original['events']
        proposal = group_notifications(events, [events[0]['event_id']])
        proposal.update(experiment='EXP-0041', source_window=[10, 20])
        self.bundle = proposal; self.write_bundle(); entry['sha256'] = self.sha(); self.write_config()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['events'], events)
        self.assertEqual(data['review_only_events'], events[:1])
        first, second = data['timeline']
        self.assertEqual((first['action'], first['notify'], first['card']['first_notification_pts']), ('created', False, None))
        self.assertEqual((second['action'], second['notify'], second['card']['first_notification_pts']), ('updated', True, 12))
        self.assertEqual(notification_cards_at(data['timeline'], 11), [])
        self.assertEqual(notification_cards_at(data['timeline'], 11, include_review_only=True)[0]['event_ids'], [events[0]['event_id']])
        self.assertEqual(len(notification_cards_at(data['timeline'], 12)), 1)
        self.assertEqual(self.client.post(url+'/claim', json={'notification_key':second['notification_key']}, headers={'Origin':'http://localhost'}).status_code, 404)
        self.assertFalse((self.root/'runtime/exp0036-notification-receipts.sqlite3').exists())
        self.bundle['timeline'][0]['card'] = deepcopy(second['card'])
        self.write_bundle(); entry['sha256'] = self.sha(); self.write_config()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.bundle = proposal; self.bundle['active_events'] = []
        self.write_bundle(); entry['sha256'] = self.sha(); self.write_config()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.bundle = proposal; self.write_bundle(); entry['sha256'] = self.sha(); entry['notification_enabled'] = True; self.write_config()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_exp0042_new_candidate_and_empty_diagnostic(self):
        original = deepcopy(self.bundle['events'])
        raw = dict(status='침입 의심', reason='gate_visual_transition', decision_time_pts=12.5,
                   evidence_until_pts=12.5, evidence=dict(seed_pts=10, reference_pts=12,
                       window_id='w1', seed_track_ids=[1]))
        eid = 'a'*64
        new = dict(session_id='fixture', camera_id='C3', gate_id='C3_fence', event_id=eid,
                   video_id='fixture', decision_time_pts=12.5, status='침입 의심', track_ids=[1],
                   source_ref=dict(collection='transition_events', source_pointer='/transition_events/'+eid,
                                   segment='w1', raw_id=None), source_event=raw)
        entry = dict(self.config['incident_bundles']['007'], experiment_id='EXP-0042',
                     session_id='fixture', notification_enabled=False, media_start_pts=10)
        self.config['incident_bundles']['exp42'] = entry
        self.assignments.write_text(json.dumps({'assignments':[{'experiment_id':'EXP-0042'}]}))
        def bundle(rows, mode):
            result = group_notifications(rows)
            result.update(experiment='EXP-0042', source_window=[10, 20], comparison_mode=mode,
                          live_notifications_enabled=False)
            return result
        for mode, rows in [('combined', [new]), ('transition-only', [])]:
            self.bundle = bundle(original + rows if mode == 'combined' else rows, mode)
            self.write_bundle(); entry['sha256'] = self.sha(); self.write_config()
            response = self.client.get('/api/incidents/exp42')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertFalse(data['notification_enabled'])
            if mode == 'combined':
                self.assertEqual(data['events'][:len(original)], original)
                self.assertEqual(data['events'][-1], new)
                self.assertEqual(data['timeline'][-1]['card']['first_notification_pts'], 11)
                self.assertEqual(data['timeline'][-1]['decision_time_pts'], 12.5)
            else:
                self.assertEqual(data['events'], [])
                self.assertEqual(data['timeline'], [])
        malformed = deepcopy(new); malformed['source_ref']['source_pointer'] = '/transition_events/' + '0'*64
        self.bundle = bundle(original + [malformed], 'combined')
        self.write_bundle(); entry['sha256'] = self.sha(); self.write_config()
        self.assertEqual(self.client.get('/api/incidents/exp42').status_code, 404)


if __name__ == '__main__': unittest.main()
