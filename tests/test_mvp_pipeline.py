"""RC integration contracts. Backend doubles are NOT CCTV/model validation."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from sceneguard.mvp_pipeline import (
    VERSION, RuleBackend, analyze_observations, collect_paths, digest,
    normalize_portal, validate_frames,
)

SCOPE = dict(session_id='recording-one', camera_id='C3', gate_id='entry')
SCENE = dict(source_size=[100, 100])
REGION = {'kind': 'test-region'}


def frames():
    return [dict(frame_index=i, pts=i / 30, native_pts=i, time_base='1/30',
        actual_boxes=[dict(cache_index=0, score=.9, bbox=[.1, .1, .3, .8])],
        point_paths=[], camera_step_pixels=[0., 0.]) for i in range(4)]


def event():
    return dict(**SCOPE, event_id='original', video_id='clip', status='침입 의심',
        decision_time_pts=0., track_ids=[], source_event={}, source_ref={})


def raw_birth():
    return dict(run_id='observation-1', birth_pts=0., decision_time_pts=.1,
        evidence_until_pts=.1, automatic_confirmation=False, status='침입 의심',
        birth_site={'inside_birth_site': True},
        observation_refs=[{'pts': 0., 'frame_index': 0, 'cache_index': 0},
                          {'pts': .1, 'frame_index': 3, 'cache_index': 0}])


def inputs(with_event=False):
    return (dict(video_id='clip', policy={'loss_wait': 1}, segments=[]),
            dict(video_id='clip', events=[event()] if with_event else [],
                 source_window=[0., .1], policy={'gap_seconds': 3, 'max_span_seconds': 10}))


class DoubleBackend:
    """Records wiring and implements a trivial response, NOT the real CV rules."""
    def __init__(self, births=(), drop_event=False, mutate_source=False):
        self.new = list(births); self.calls = []; self.drop = drop_event; self.mutate = mutate_source

    def prepare(self, *args):
        self.calls.append('prepare'); return 'direction', 'portal'

    def confirmations(self, baseline, bundle, scene, engine, run_id):
        self.calls.append('confirmations')
        if self.mutate: baseline['mutated'] = True
        return []

    def births(self, *args):
        self.calls.append('births')
        return dict(portal_events=copy.deepcopy(self.new), observation_runs={})

    def lifecycle(self, baseline, history, events, runs, fs, scene, region, engine, portal, scope):
        self.calls.append('lifecycle')
        return dict(events=copy.deepcopy(history['events'] + events), video_id='clip')

    def activity(self, prior, fs, portal, scope, run_id):
        self.calls.append('activity')
        return dict(events=[] if self.drop else prior['events'], cards=[], timeline=[],
                    counts={'incident_cards': 0}, contract='gate_activity_episodes_v1')


class FrameContracts(unittest.TestCase):
    def test_valid(self): validate_frames(frames(), source_size=[100, 100])
    def test_empty_window_is_not_negative(self):
        with self.assertRaises(ValueError): validate_frames([])
    def test_no_detections_is_valid(self):
        f = frames()
        for r in f: r['actual_boxes'] = []
        validate_frames(f)
    def test_duplicate_time(self):
        f = frames(); f[1]['pts'] = 0
        with self.assertRaises(ValueError): validate_frames(f)
    def test_index_skip(self):
        f = frames(); f[2]['frame_index'] = 4
        with self.assertRaises(ValueError): validate_frames(f)
    def test_native_clock_mismatch(self):
        f = frames(); f[1]['native_pts'] = 50
        with self.assertRaises(ValueError): validate_frames(f)
    def test_nan_time(self):
        f = frames(); f[1]['pts'] = math.nan
        with self.assertRaises(ValueError): validate_frames(f)
    def test_negative_timebase(self):
        f = frames(); f[0]['time_base'] = '-1/30'
        with self.assertRaises(ValueError): validate_frames(f)
    def test_duplicate_detection_ref(self):
        f = frames(); f[0]['actual_boxes'] *= 2
        with self.assertRaises(ValueError): validate_frames(f)
    def test_invalid_box(self):
        f = frames(); f[0]['actual_boxes'][0]['bbox'][2] = 3
        with self.assertRaises(ValueError): validate_frames(f)
    def test_nonfinite_score(self):
        f = frames(); f[0]['actual_boxes'][0]['score'] = math.inf
        with self.assertRaises(ValueError): validate_frames(f)
    def test_wrong_size(self):
        f = frames(); f[0]['source_size'] = [900, 200]
        with self.assertRaises(ValueError): validate_frames(f, source_size=[100, 100])


class PortalContracts(unittest.TestCase):
    def normalize(self, raw=None, run='one'):
        return normalize_portal(raw or raw_birth(), SCOPE, 'clip', run)
    def test_suspicion_not_confirmation(self):
        e = self.normalize()
        self.assertEqual(e['status'], '침입 의심')
        self.assertFalse(e['source_event']['automatic_confirmation'])
    def test_stable_event_id(self): self.assertEqual(self.normalize(), self.normalize())
    def test_recording_scoped_id(self):
        self.assertNotEqual(self.normalize(run='one')['event_id'], self.normalize(run='two')['event_id'])
    def test_future_reference(self):
        r = raw_birth(); r['observation_refs'][1]['pts'] = .2
        with self.assertRaises(ValueError): self.normalize(r)
    def test_empty_reference(self):
        r = raw_birth(); r['observation_refs'] = []
        with self.assertRaises(ValueError): self.normalize(r)
    def test_disallow_confirmation(self):
        r = raw_birth(); r['automatic_confirmation'] = True
        with self.assertRaises(ValueError): self.normalize(r)
    def test_bad_site(self):
        r = raw_birth(); r['birth_site']['inside_birth_site'] = False
        with self.assertRaises(ValueError): self.normalize(r)
    def test_no_source_mutation(self):
        r = raw_birth(); snapshot = copy.deepcopy(r); self.normalize(r)
        self.assertEqual(r, snapshot)


class CompositionContracts(unittest.TestCase):
    def run_analysis(self, backend, existing=False):
        b, c = inputs(existing)
        return analyze_observations(b, c, frames(), SCENE, REGION, SCOPE, 'run', backend=backend)
    def test_rule_order(self):
        b = DoubleBackend(); self.run_analysis(b, True)
        self.assertEqual(b.calls, ['prepare', 'confirmations', 'births', 'lifecycle', 'activity'])
    def test_no_candidates_needs_no_dummy(self):
        result = self.run_analysis(DoubleBackend())
        self.assertEqual(result['cards']['events'], [])
    def test_portal_only_input_supported(self):
        result = self.run_analysis(DoubleBackend([raw_birth()]))
        self.assertEqual(len(result['cards']['events']), 1)
        self.assertEqual(result['cards']['events'][0]['source_ref']['collection'], 'inside_birth_events')
    def test_base_and_portal_retained(self):
        result = self.run_analysis(DoubleBackend([raw_birth()]), True)
        self.assertEqual(len(result['cards']['events']), 2)
        self.assertIn(event(), result['cards']['events'])
    def test_dropped_candidate_fails(self):
        with self.assertRaises(ValueError): self.run_analysis(DoubleBackend(drop_event=True), True)
    def test_mutation_fails(self):
        with self.assertRaises(ValueError): self.run_analysis(DoubleBackend(mutate_source=True))
    def test_wrong_video_fails(self):
        b, c = inputs(); c['video_id'] = 'other'
        with self.assertRaises(ValueError):
            analyze_observations(b, c, frames(), SCENE, REGION, SCOPE, 'run', backend=DoubleBackend())
    def test_wrong_camera_fails(self):
        b, c = inputs(True); c['events'][0]['camera_id'] = 'C6'
        with self.assertRaises(ValueError):
            analyze_observations(b, c, frames(), SCENE, REGION, SCOPE, 'run', backend=DoubleBackend())
    def test_exp_results_not_required(self):
        f = self.run_analysis(DoubleBackend())['cards']
        self.assertFalse(f['historical_experiment_results_required'])
        self.assertEqual(f['execution_mode'], 'current_input_analysis')
    def test_no_action_candidates_no_live_delivery(self):
        f = self.run_analysis(DoubleBackend())['cards']
        self.assertFalse(f['rejected_transition_candidates_used'])
        self.assertFalse(f['live_notifications_enabled'])
        self.assertFalse(f['realtime'])
        self.assertIsNone(f['accuracy'])
    def test_semantic_validation_not_claimed(self):
        f = self.run_analysis(DoubleBackend())['cards']
        self.assertEqual(f['release_video_validation'], 'not_established')
        self.assertFalse(f['human_verified'])
    def test_final_version_distinct_from_experiment(self):
        f = self.run_analysis(DoubleBackend())['cards']
        self.assertEqual(f['experiment'], 'MVP-0002')
        self.assertEqual(f['pipeline_version'], VERSION)


class BackendEmptyContracts(unittest.TestCase):
    """Exercise the production backend's empty-path branches with tiny doubles."""
    def test_empty_lifecycle_export(self):
        class Empty:
            def __init__(self, **kw): pass
            def export(self): return {'events': [], 'cards': [], 'experiment': 'EXP-0048'}
        b = RuleBackend.__new__(RuleBackend); b.empty_lifecycle = Empty
        result = b.lifecycle({}, {'events': [], 'video_id': 'v', 'source_window': [0., .1]},
            [], {}, frames(), {}, {}, None, None, SCOPE)
        self.assertEqual(result['events'], [])
        self.assertEqual(result['available_after_pts'], .1)
    def test_all_empty_frames_processed(self):
        class Empty:
            def __init__(self, *a, **kw): self.seen = []
            def step(self, i, pts, **kw): self.seen.append(i)
            def export(self): return {'events': [], 'frames': self.seen}
        b = RuleBackend.__new__(RuleBackend); b.empty_activity = Empty
        b.activity_references = lambda frame, portal: []
        r = b.activity({'events': [], 'video_id': 'v', 'source_window': [0., .1]},
                       frames(), None, SCOPE, 'run')
        self.assertEqual(r['frames'], [0, 1, 2, 3])


class FeatureCollectorContracts(unittest.TestCase):
    def test_rejected_event_and_scores_not_reused(self):
        import numpy as np
        mod_engine = types.ModuleType('sceneguard.gate_transition')
        class Engine:
            def __init__(self, scene): pass
            def step(self, gray, pts, boxes, index):
                return dict(frame_index=index, pts=pts, point_paths=[], camera_step_pixels=[0, 0],
                            event={'bad': 'rejected action proposal'}, signals=[.99])
        mod_engine.GateTransition = Engine
        mod_catalog = types.ModuleType('sceneguard.gap_observation_support')
        mod_catalog.catalog_frame = lambda c, t: c['actual_boxes']
        mod_decode = types.ModuleType('sceneguard.run_tracklet_linking')
        mod_decode.decode_native = lambda v, fs: ((i, np.zeros((3, 3, 3), dtype=np.uint8))
                                                  for i in range(len(fs)))
        with tempfile.TemporaryDirectory() as d, patch.dict(sys.modules, {
                'sceneguard.gate_transition': mod_engine,
                'sceneguard.gap_observation_support': mod_catalog,
                'sceneguard.run_tracklet_linking': mod_decode}):
            collect_paths('not-a-real-video', frames(), frames(), {}, Path(d))
            rows = [json.loads(s) for s in (Path(d) / 'frame-evidence.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 4)
        self.assertTrue(all('event' not in r and 'signals' not in r for r in rows))
        self.assertEqual(rows[-1]['native_pts'], 3)




class EntryPointContracts(unittest.TestCase):
    """Exercise files/resume/status with a simulated front-end, not CCTV inference."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root/'outputs').mkdir(); (self.root/'sceneguard').mkdir()
        (self.root/'sceneguard/code.py').write_text('# integration fixture\n')
        self.video = self.root/'clip.mp4'; self.video.write_bytes(b'not-real-media')
        self.scene = self.root/'scene.json'; self.scene.write_text(json.dumps(SCENE))
        self.portal = self.root/'portal.json'; self.portal.write_text(json.dumps(REGION))
        self.camera = self.root/'cameras.json'
        self.camera.write_text(json.dumps({'cameras': {'C3': {'legacy_boundary_config': {'boundary_id': 'entry'}}}}))
        self.out = self.root/'outputs/run'
        self.front_calls = 0; self.path_calls = 0; self.decide_calls = 0
        self.vc = types.ModuleType('sceneguard.video_cards')
        self.vc.ROOT = self.root; self.vc.SCENES = {'C3': self.scene}; self.vc.CAMERAS = self.camera
        self.vc.read = lambda path: json.loads(Path(path).read_text())
        self.vc.sha256 = lambda path: __import__('hashlib').sha256(Path(path).read_bytes()).hexdigest()
        def save(path, value):
            with Path(path).open('x') as f: json.dump(value, f, allow_nan=False)
        self.vc.save = save
        self.vc.status = lambda path, **kw: Path(path).write_text(json.dumps(kw))
        self.vc.probe = lambda video: {'duration': .2, 'size': [100, 100]}
        self.vc.validate_cached = lambda *args: ({}, frames(), 1/30, {'cache': 'stable'})
        def front(video, camera, output, **kw):
            self.front_calls += 1
            if not (output/'analysis').exists():
                (output/'analysis').mkdir(parents=True); (output/'tracking').mkdir()
                b, c = inputs()
                b['source_paths'] = {'cache': 'fixture-cache'}
                save(output/'analysis/analysis.json', b); save(output/'analysis/cards.json', c)
                (output/'tracking/frames.jsonl').write_text('\n'.join(json.dumps(r) for r in frames()))
            return {'state': 'complete', 'mode': 'saved_cache', 'detector_frames_this_execution': 0}
        self.vc.execute = front
        def stage(output, name, binding, action):
            target = output/name
            if target.exists():
                if self.vc.read(target/'stage.json')['binding'] != binding:
                    raise ValueError('Stage binding changed')
                return target, True
            target.mkdir(); action(target)
            save(target/'stage.json', {'binding': binding})
            return target, False
        self.vc.stage = stage
        def media(video, fs, cards, directory, interval):
            (directory/'original.mp4').write_bytes(b'fixture-encoded-video')
            save(directory/'media.json', [{'file': 'original.mp4', 'key': 'original'}])
            save(directory/'source-frames.json', [{'pts': f['pts']} for f in fs])
        self.vc.evidence = media
        geometry = types.ModuleType('sceneguard.gate_episode_evidence')
        geometry.revised_scene = lambda before, after: after
        portal = types.ModuleType('sceneguard.portal_births'); portal.PortalGate = lambda *a: None
        normalization = types.ModuleType('sceneguard.exp0036_application')
        normalization.make_bundle = lambda b, camera, gate, session: inputs()[1]
        def collect(video, fs, tracks, scene, output):
            self.path_calls += 1
            (output/'frame-evidence.jsonl').write_text('\n'.join(json.dumps(r) for r in frames()))
        def analyze(*a):
            self.decide_calls += 1
            return {'cards': {'cards': [], 'events': [], 'counts': {'incident_cards': 0},
                              'source_window': [0., .1]}}
        self.patch_modules = patch.dict(sys.modules, {
            'sceneguard.video_cards': self.vc, 'sceneguard.gate_episode_evidence': geometry,
            'sceneguard.portal_births': portal, 'sceneguard.exp0036_application': normalization})
        self.patch_collect = patch('sceneguard.mvp_pipeline.collect_paths', collect)
        self.patch_analyze = patch('sceneguard.mvp_pipeline.analyze_observations', analyze)
        self.patch_modules.start(); self.patch_collect.start(); self.patch_analyze.start()

    def tearDown(self):
        self.patch_analyze.stop(); self.patch_collect.stop(); self.patch_modules.stop(); self.temp.cleanup()

    def invoke(self):
        from sceneguard.mvp_pipeline import execute
        return execute(self.video, 'C3', self.out, scene_path=self.scene, portal_path=self.portal,
                       start=0., end=.1, cache=self.root/'cache')

    def test_analysis_not_release_complete(self):
        r = self.invoke()
        self.assertEqual(r['state'], 'analysis_complete')
        self.assertFalse(r['overall_release_complete'])
        self.assertFalse(r['service_registered'])
        self.assertFalse(r['browser_verified'])

    def test_resume_does_not_recompute_paths_or_decisions(self):
        first = self.invoke(); before = (self.out/'viewer-manifest.json').read_bytes()
        second = self.invoke()
        self.assertEqual(before, (self.out/'viewer-manifest.json').read_bytes())
        self.assertEqual(self.path_calls, 1); self.assertEqual(self.decide_calls, 1)
        self.assertTrue(all(second['reused'].values()))
        self.assertFalse(first['reused']['paths'])

    def test_changed_source_refuses_resume(self):
        self.invoke(); self.video.write_bytes(b'changed-source')
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.path_calls, 1)

    def test_blocked_frontend_not_success(self):
        self.vc.execute = lambda *a, **k: {'state': 'blocked', 'reason': 'cache missing'}
        r = self.invoke()
        self.assertEqual(r['state'], 'blocked')
        self.assertFalse((self.out/'viewer-manifest.json').exists())
        self.assertEqual(self.decide_calls, 0)

    def test_exception_creates_failure_status(self):
        self.vc.execute = lambda *a, **k: (_ for _ in ()).throw(ValueError('frontend error'))
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(json.loads((self.out/'status.json').read_text())['state'], 'failed')
        self.assertFalse((self.out/'viewer-manifest.json').exists())

    def test_manifest_binds_output_and_disables_delivery(self):
        self.invoke(); manifest = json.loads((self.out/'viewer-manifest.json').read_text())
        self.assertEqual(manifest['source_sha256'], self.vc.sha256(self.video))
        self.assertEqual(manifest['cards_sha256'], self.vc.sha256(Path(manifest['cards_path'])))
        self.assertFalse(manifest['live_notifications_enabled'])
        self.assertEqual(manifest['registration_status'], 'adapter_required')


if __name__ == '__main__': unittest.main()
