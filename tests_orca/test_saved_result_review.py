"""Saved-only evidence, permission, source binding and independent review history."""
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
from sceneguard.gate_activity_episodes import GateActivityEpisodes, SUSPECTED, CONFIRMED
from sceneguard.review_store import ReviewStore
from webapp.app import app
from webapp.assessment_store import AssessmentStore


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SavedResultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        scope = dict(session_id='recording', camera_id='camera', gate_id='door')
        event = dict(scope, event_id='a' * 64, decision_time_pts=.2, status=SUSPECTED,
                     track_ids=[], source_event={'observation_refs': [dict(pts=.2, frame_index=1, cache_index=0)]})
        state = dict(event_id=event['event_id'], incident_id='old-card', automatic_status=SUSPECTED,
                     opened_pts=.2, last_state_change_pts=.2, first_confirmation_pts=None,
                     released_pts=None, observation_key='run-a', binding={'source_observation_key': 'original'},
                     release_protected=False, human_verified=False, identity_verified=False)
        engine = GateActivityEpisodes(scope)
        engine.step(0, 0.)
        engine.step(1, .2, portal_refs=[dict(pts=.2, frame_index=1, cache_index=0)], candidates=[event], evidence_updates=[state])
        confirmed = dict(state, automatic_status=CONFIRMED, last_state_change_pts=.8, first_confirmation_pts=.8)
        engine.step(2, .8, evidence_updates=[confirmed])
        engine.step(3, 1.)
        cards = engine.export()
        cards.update(experiment='MVP-0002', analysis_run_id='recording', source_evidence_mode='computed_in_current_run',
                     source_window=[0, 1], source_resolution_log=[])
        self.cid = cards['cards'][0]['incident_id']
        self.digest = write(self.root / 'run/decision/cards.json', cards)
        frames = [dict(frame_index=i, pts=t, native_pts=round(t * 100), time_base='1/100', playback_seconds=t)
                  for i, t in enumerate((0., .2, .8, 1.))]
        self.frames = frames
        frame_hash = write(self.root / 'run/evidence/source-frames.json', frames)
        video = self.root / 'run/evidence/original.mp4'
        video.write_bytes(b'local video')
        self.video_hash = hashlib.sha256(video.read_bytes()).hexdigest()
        manifest = dict(kind='sceneguard_mvp_viewer_v1', experiment='MVP-0002', run_id='recording',
                        cards_path=str(self.root / 'run/decision/cards.json'), cards_sha256=self.digest,
                        source_frames_path=str(self.root / 'run/evidence/source-frames.json'), source_frames_sha256=frame_hash,
                        media=[dict(key='original', path=str(video), sha256=self.video_hash)])
        manifest_hash = write(self.root / 'run/viewer-manifest.json', manifest)
        boxes = [dict(cache_index=0, bbox=[.1, .1, .3, .6], track_ids=[]),
                 dict(cache_index=1, bbox=[.7, .1, .9, .6], track_ids=[99]),
                 dict(cache_index=2, bbox=[.2, .2, .4, .6], track_ids=[], predicted=True)]
        observations = [dict(f, actual_boxes=deepcopy(boxes) if f['pts'] == .2 else [],
                             predicted_boxes=[dict(bbox=[0, 0, 1, 1], track_ids=[1])]) for f in frames]
        path = self.root / 'run/image-paths/frame-evidence.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text('\n'.join(json.dumps(r) for r in observations))
        paths_hash = write(self.root / 'run/image-paths/stage.json', dict(status='complete',
                           artifacts={'frame-evidence.jsonl': hashlib.sha256(path.read_bytes()).hexdigest()}))
        write(self.root / 'run/decision/stage.json', dict(status='complete', artifacts={'cards.json': self.digest}, binding={'paths': paths_hash}))
        write(self.root / 'repo/records/catalog.json', dict(experiments=[]))
        self.c = dict(repo_root=str(self.root / 'repo'), artifact_allow_root=str(self.root), runtime_dir=str(self.root / 'runtime'),
                      artifacts={'video': dict(kind='video', path=str(video))}, incident_bundles={'bundle': dict(
                          experiment_id='MVP-0002', media_artifact_id='video', notification_enabled=False,
                          path='run/decision/cards.json', sha256=self.digest, session_id='recording', source_label='test',
                          manifest_path='run/viewer-manifest.json', manifest_sha256=manifest_hash)})
        self.config_path = self.root / 'config.json'
        write(self.config_path, self.c)
        env = patch.dict(os.environ, {'SCENEGUARD_LAB_CONFIG': str(self.config_path)})
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(app, base_url='http://localhost')
        self.query = dict(session_id='recording', bundle_sha256=self.digest)
        self.headers = {'origin': 'http://localhost'}
        self.assessment = dict(self.query, event_assessment='correct_event', bbox_quality='poor',
                               expected_version=0, reviewer='human', note='separate judgments')
        self.url = f'/api/incidents/bundle/assessments/{self.cid}'
        self.evidence_url = f'/api/incidents/bundle/evidence/{self.cid}'

    def test_exact_saved_boxes_no_predictions_unrelated_or_stale_box(self):
        r = self.client.get(self.evidence_url, params=self.query)
        self.assertEqual(r.status_code, 200)
        suspicion, confirmation = r.json()['items']
        self.assertTrue(suspicion['available'])
        self.assertEqual(suspicion['frame'], self.frames[1])
        self.assertEqual([b['cache_index'] for b in suspicion['boxes']], [0])
        self.assertTrue(confirmation['available'])
        self.assertEqual(confirmation['boxes'], [])
        self.assertEqual(confirmation['reason'], 'no_incident_observation_at_decision')
        self.assertEqual(confirmation['frame']['native_pts'], 80)
        prior = confirmation['last_observation']
        self.assertTrue(prior['available'])
        self.assertEqual(prior['frame']['pts'], .2)
        self.assertEqual(prior['frame']['native_pts'], 20)
        self.assertAlmostEqual(prior['seconds_before_decision'], .6)
        self.assertEqual(prior['decision_time_pts'], .8)
        self.assertEqual([b['cache_index'] for b in prior['boxes']], [0])
        self.assertIn('confirmation-last-observation.jpg', prior['image_url'])
        self.assertEqual(r.json()['original_media_url'], '/artifacts/video')

    def test_assessment_history_versions_independent_fields_and_legacy_preservation(self):
        legacy_path = self.root / 'runtime/incident-reviews.sqlite3'
        legacy = ReviewStore(legacy_path)
        legacy.save('recording', self.cid, self.digest, status='침입 확인', reviewer='old', expected_version=0)
        before = legacy_path.read_bytes()
        self.assertEqual(self.client.get(self.url, params=self.query).json(), dict(review=None, history=[]))
        response = self.client.post(self.url, json=self.assessment, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['review']['bbox_quality'], 'poor')
        self.assertEqual(response.json()['review']['event_assessment'], 'correct_event')
        self.assertEqual(self.client.post(self.url, json=self.assessment, headers=self.headers).status_code, 409)
        changed = dict(self.assessment, expected_version=1, event_assessment='uncertain', bbox_quality='good')
        self.assertEqual(self.client.post(self.url, json=changed, headers=self.headers).status_code, 200)
        persisted = AssessmentStore(self.root / 'runtime/saved-result-assessments.sqlite3')
        history = persisted.history('recording', self.cid, self.digest)
        self.assertEqual([h['version'] for h in history], [1, 2])
        self.assertEqual(history[0]['bbox_quality'], 'poor')
        self.assertEqual(legacy_path.read_bytes(), before)
        self.assertEqual(legacy.get('recording', self.cid, self.digest)['status'], '침입 확인')

    def test_omission_for_empty_or_nonempty_video_and_time_validation(self):
        url = '/api/incidents/bundle/omission-review'
        draft = dict(self.query, status='missed', time_pts=.4, reviewer='human', note='another event', expected_version=0)
        self.assertEqual(self.client.post(url, json=draft, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(url, params=self.query).json()['review']['time_pts'], .4)
        self.assertIsNone(self.client.get(self.url, params=self.query).json()['review'])
        self.assertEqual(self.client.post(url, json=draft, headers=self.headers).status_code, 409)
        for at in (-1, 2, True, '0.4'):
            self.assertEqual(self.client.post(url, json=dict(draft, time_pts=at, expected_version=1), headers=self.headers).status_code, 400)
        draft.update(status='none', time_pts=None, expected_version=1)
        self.assertEqual(self.client.post(url, json=draft, headers=self.headers).json()['review']['version'], 2)

    def test_origin_membership_and_binding_permissions(self):
        for headers in ({}, {'origin': 'https://elsewhere'}, {'origin': 'http://localhost', 'sec-fetch-site': 'cross-site'}):
            self.assertEqual(self.client.post(self.url, json=self.assessment, headers=headers).status_code, 403)
        for url in (self.url, self.evidence_url, '/api/incidents/bundle/omission-review'):
            self.assertEqual(self.client.get(url, params=dict(self.query, bundle_sha256='b' * 64)).status_code, 409)
            self.assertEqual(self.client.get(url, params=dict(self.query, session_id='other')).status_code, 409)
        self.assertEqual(self.client.get('/api/incidents/bundle/assessments/video-omission', params=self.query).status_code, 404)
        self.assertEqual(self.client.post('/api/incidents/bundle/assessments/video-omission', json=self.assessment, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get('/api/incidents/unknown/omission-review', params=self.query).status_code, 404)
        self.assertEqual(self.client.get(self.evidence_url + '/unknown.jpg', params=self.query).status_code, 404)
        self.assertEqual(self.client.post(self.url, json=dict(self.assessment, bundle_sha256='b' * 64), headers=self.headers).status_code, 409)
        self.assertFalse((self.root / 'runtime').exists())

    def test_input_validation_does_not_write(self):
        for changes in ({'event_assessment': '침입 확인'}, {'bbox_quality': 'great'}, {'expected_version': True},
                        {'expected_version': -1}, {'reviewer': ''}, {'note': 'a' * 2001}, {'extra': 1}):
            r = self.client.post(self.url, json=dict(self.assessment, **changes), headers=self.headers)
            self.assertEqual(r.status_code, 400, changes)
        self.assertEqual(self.client.get(self.url, params=self.query).json()['history'], [])

    def test_missing_and_tampered_evidence_fail_closed(self):
        path = self.root / 'run/image-paths/frame-evidence.jsonl'
        original = path.read_bytes()
        path.write_bytes(original + b' ')
        response = self.client.get(self.evidence_url, params=self.query).json()
        self.assertTrue(all(not item['available'] for item in response['items']))
        self.assertEqual(self.client.get(self.evidence_url + '/suspicion.jpg', params=self.query).status_code, 404)
        path.unlink()
        path.symlink_to(self.root / 'run/decision/cards.json')
        self.assertFalse(self.client.get(self.evidence_url, params=self.query).json()['items'][0]['available'])
        path.unlink()
        path.write_bytes(original)
        (self.root / 'run/evidence/original.mp4').write_bytes(b'tampered')
        self.assertEqual(self.client.get(self.evidence_url + '/suspicion.jpg', params=self.query).status_code, 503)

    def test_sidecar_symlink_rejected(self):
        target = self.root / 'untouched'
        target.write_text('keep')
        (self.root / 'runtime').mkdir()
        (self.root / 'runtime/saved-result-assessments.sqlite3').symlink_to(target)
        self.assertEqual(self.client.post(self.url, json=self.assessment, headers=self.headers).status_code, 503)
        self.assertEqual(target.read_text(), 'keep')

    def test_absent_confirmation_and_native_clock_mismatch_are_explicit(self):
        from webapp.saved_review import evidence_data
        from webapp.incident import load_bundle
        bundle = load_bundle(self.c, 'bundle')
        for row in bundle['timeline']:
            row['card']['first_confirmation_pts'] = None
        absent = evidence_data(self.c, 'bundle', self.cid, bundle)[0]['items'][1]
        self.assertFalse(absent['available'])
        self.assertEqual(absent['reason'], 'no_automatic_confirmation')
        from webapp.saved_review import saved_inputs
        inputs = saved_inputs(self.c, 'bundle', bundle)
        inputs[2][1]['native_pts'] += 1
        with patch('webapp.saved_review.saved_inputs', return_value=inputs):
            item = evidence_data(self.c, 'bundle', self.cid, bundle)[0]['items'][0]
        self.assertFalse(item['available'])
        self.assertEqual(item['reason'], 'exact_saved_frame_unavailable')

    def test_prior_observation_uses_only_causal_saved_refs_and_its_actual_frame(self):
        from webapp.saved_review import last_observation
        frame = self.frames[1]
        row = dict(frame, actual_boxes=[dict(cache_index=0, bbox=[.1,.1,.3,.6], track_ids=[]),
                                       dict(cache_index=1, bbox=[.5,.1,.7,.6], track_ids=[99])])
        snapshot = dict(card=dict(event_ids=[], track_ids=[99], last_gate_observation_refs=[
            dict(pts=.2, frame_index=1, cache_index=0),
            dict(pts=.9, frame_index=2, cache_index=1)]))
        prior = last_observation(snapshot, [], self.frames, {1:row}, .8)
        self.assertEqual(prior['frame']['pts'], .2)
        self.assertEqual([box['cache_index'] for box in prior['boxes']], [0])
        self.assertFalse(last_observation(snapshot, [], self.frames, {1:row}, .2)['available'])
        self.assertFalse(last_observation(dict(card=dict(event_ids=[], track_ids=[99])), [], self.frames, {1:row}, .8)['available'])

    def test_omission_does_not_require_an_incident_card(self):
        from webapp.incident import load_bundle
        bundle = load_bundle(self.c, 'bundle')
        bundle['timeline'] = []
        draft = dict(self.query, status='uncertain', time_pts=None, reviewer='human', note='', expected_version=0)
        with patch('webapp.incident.registered', return_value=bundle):
            response = self.client.post('/api/incidents/bundle/omission-review', json=draft, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['review']['status'], 'uncertain')


class RendererTests(unittest.TestCase):
    def test_direct_module_import_orders(self):
        for module in ('webapp.incident', 'webapp.app', 'webapp.saved_review', 'webapp.mvp_registration'):
            result = subprocess.run([sys.executable, '-c', 'import ' + module], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_cpu_helper_decodes_exact_frame_and_refuses_missing_frame(self):
        repo = Path(__file__).resolve().parents[1]
        interpreter = repo / '.venv-cv-batch02/bin/python'
        if not interpreter.exists():
            self.skipTest('Existing local CPU media environment not installed')
        script = '''
import av, cv2, numpy as np, tempfile, os
from fractions import Fraction
from webapp.evidence_image import render
with tempfile.TemporaryDirectory() as folder:
    path=folder+'/test.mp4'
    with av.open(path,'w') as out:
        stream=out.add_stream('libx264',rate=30);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
        for index in range(3):
            pixels=np.zeros((64,64,3),dtype=np.uint8);pixels[:]=[index*80,0,0]
            frame=av.VideoFrame.from_ndarray(pixels,format='bgr24');frame.pts=index;frame.time_base=Fraction(1,30)
            for packet in stream.encode(frame):out.mux(packet)
        for packet in stream.encode():out.mux(packet)
    item={'frame':{'playback_seconds':1/30},'boxes':[{'bbox':[.25,.25,.75,.75]}]}
    jpeg=render(os.open(path,os.O_RDONLY),item)
    decoded=cv2.imdecode(np.frombuffer(jpeg,dtype=np.uint8),cv2.IMREAD_COLOR)
    assert 65 < int(decoded[2,2,0]) < 95, decoded[2,2]
    assert int(decoded[16,16,1]) > 150, decoded[16,16]
    try:render(os.open(path,os.O_RDONLY),{'frame':{'playback_seconds':.05},'boxes':[]})
    except ValueError:pass
    else:raise AssertionError('Inexact source frame was accepted')
print('exact-frame decode, saved box rendering and missing-frame refusal passed')
'''
        done = subprocess.run([str(interpreter), '-c', script], cwd=repo, capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == '__main__':
    unittest.main()
