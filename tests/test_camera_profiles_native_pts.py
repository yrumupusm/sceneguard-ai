"""Frozen camera mappings and actual gapped native clocks; CPU/synthetic media only."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_video_cards as legacy
from sceneguard import video_cards as vc
from sceneguard.byte_adapter import ByteAdapter
from sceneguard.portal_births import make_region


DT = Fraction(1001, 30000)
TB = Fraction(1, 90000)


class NativeProfileContracts(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy.PipelineTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.video, self.cache = self.fixture.video, self.fixture.cache
        self.registry = self.root/'registry.json'
        self.profile = deepcopy(self.fixture.camera)
        self.profile.update(camera_id='C8', calibrated=True, roi=[0,0,1,1])
        self.profile['legacy_boundary_config'].update(camera_group='C8', boundary_id='C8_fence')
        self.scene = self.fixture.scene
        self.portal = self.root/'portal.json'
        vc.save(self.portal, make_region(vc.read(self.scene), 'C8',
            [[.45,.1],[.55,.1],[.55,.9],[.45,.9]], reference_pts=0, note='Synthetic static geometry'))
        self.profile.update(scene_path=self.scene.name, scene_sha256=vc.sha256(self.scene),
                            portal_path=self.portal.name, portal_sha256=vc.sha256(self.portal))
        self.document = dict(schema_version=1, cameras={'C8':self.profile},
            sources={str(self.video):dict(camera_id='C8',sha256=vc.sha256(self.video))})
        self.write_registry()

    def write_registry(self):
        self.registry.write_text(json.dumps(self.document))

    def write_native(self):
        import numpy as np
        from sceneguard.mvp_review_evidence import _VideoWriter
        self.video.unlink()
        writer = _VideoWriter(self.video, [64,48], DT, time_base=TB)
        self.stamps = [i*3003+(3003 if i >= 30 else 0) for i in range(240)]
        for t in self.stamps:
            writer.write(np.zeros((48,64,3),dtype=np.uint8), pts=t)
        writer.close()
        self.frames = [dict(pts=float(t*TB),native_pts=t,time_base=str(TB),
                           source_size=[64,48],boxes=[],scores=[]) for t in self.stamps]
        self.write_cache(self.frames)
        self.document['sources'][str(self.video)]['sha256'] = vc.sha256(self.video)
        self.write_registry()
        return vc.probe(self.video)

    def write_cache(self, frames):
        path = self.cache/'person_cache.jsonl'
        path.write_text(''.join(json.dumps(f)+'\n' for f in frames))
        meta = deepcopy(self.fixture.meta)
        meta.update(config=self.profile['legacy_boundary_config'],source_sha256=vc.sha256(self.video),
                    frames=len(frames),first_pts=frames[0]['pts'],last_pts=frames[-1]['pts'])
        meta['person_cache']['sha256'] = vc.sha256(path)
        (self.cache/'run.json').write_text(json.dumps(meta))

    def test_c8_requires_explicit_frozen_mapping_and_binds_source_bytes(self):
        with self.fixture.local():
            selected = vc.camera_profile('C8',self.video,self.registry)
            self.assertEqual(selected[0],self.profile)
            self.assertEqual(selected[1],self.scene)
            with self.assertRaises(ValueError): vc.camera_profile('C8',self.video)
            with self.assertRaisesRegex(ValueError,'mapping'):
                vc.camera_profile('C7',self.video,self.registry_for_other_group())
            self.video.write_bytes(b'changed-source')
            with self.assertRaisesRegex(ValueError,'mapping'):
                vc.camera_profile('C8',self.video,self.registry)

    def registry_for_other_group(self):
        self.document['cameras']['C7'] = self.profile
        self.write_registry()
        return self.registry

    def test_profile_tamper_and_policy_tuning_are_rejected(self):
        with self.fixture.local():
            self.profile['legacy_boundary_config']['score_threshold'] = .4
            self.write_registry()
            with self.assertRaisesRegex(ValueError,'boundary policy'):
                vc.camera_profile('C8',self.video,self.registry)
            self.profile['legacy_boundary_config']['score_threshold'] = .5
            self.write_registry()
            self.portal.write_text('{}')
            with self.assertRaisesRegex(ValueError,'profile hash'):
                vc.camera_profile('C8',self.video,self.registry)

    def test_c3_c6_camera_policy_and_original_cpu_seed_are_preserved(self):
        # Real repository calibration bytes, without media/model execution.
        cameras = vc.read(vc.CAMERAS)['cameras']
        for camera in ('C3','C6'):
            profile = deepcopy(cameras[camera])
            scene = vc.SCENES[camera]
            portal = vc.ROOT/f'runtime/portal-regions/exp0046/{camera}.json'
            profile.update(scene_path=str(scene),scene_sha256=vc.sha256(scene),
                           portal_path=str(portal),portal_sha256=vc.sha256(portal))
            self.document['cameras'][camera] = profile
            self.document['sources'][str(self.video)]['camera_id'] = camera
            self.write_registry()
            self.assertEqual(vc.camera_profile(camera,self.video,self.registry)[0],profile)
            self.assertEqual(vc.source_scene(camera,self.scene,self.registry),scene)
            profile['legacy_boundary_config']['max_gap_seconds'] = .2
            self.write_registry()
            with self.assertRaisesRegex(ValueError,'C3/C6'):
                vc.camera_profile(camera,self.video,self.registry)

    def test_native_gap_all_frames_and_clipped_evidence_keep_actual_pts(self):
        info = self.write_native()
        self.assertEqual(info['fps'],'30000/1001')
        self.assertEqual(info['native_pts'],self.stamps)
        self.assertEqual(info['source_end_exclusive'],float(self.stamps[-1]*TB+DT))
        with self.fixture.local():
            _, fs, interval, _ = vc.validate_cached(self.video,self.profile,self.cache,
                0.,info['source_end_exclusive'],info)
            out = self.root/'native-evidence';out.mkdir()
            card = dict(incident_id='clip', first_alert_pts=fs[89]['pts'],last_alert_pts=fs[90]['pts'])
            vc.evidence(self.video,fs,[card],out,interval)
        import av
        for name in ('original','clip'):
            with av.open(str(out/f'{name}.mp4')) as source:
                actual = [f.pts*f.time_base for f in source.decode(video=0)]
            expected = self.stamps if name == 'original' else [
                t for t in self.stamps if fs[89]['pts']-3 <= float(t*TB) <= fs[90]['pts']+3]
            self.assertEqual(actual,[(t-expected[0])*TB for t in expected])
            if name == 'clip':
                self.assertGreater(expected[0],0)
                self.assertIn(2*DT,[b-a for a,b in zip(actual,actual[1:])])
        mapping = vc.read(out/'source-frames.json')
        self.assertEqual([r['native_pts'] for r in mapping],self.stamps)
        self.assertAlmostEqual(mapping[30]['playback_seconds']-mapping[29]['playback_seconds'],float(2*DT))

    def test_same_count_altered_cache_pts_cannot_impersonate_source(self):
        info = self.write_native()
        # Move the real gap one frame earlier: count, rate, monotonicity and
        # every pts/native_pts pair remain internally valid, but source differs.
        self.frames[29]['native_pts'] += 3003
        self.frames[29]['pts'] = float(self.frames[29]['native_pts']*TB)
        self.write_cache(self.frames)
        with self.assertRaisesRegex(ValueError,'every actual native source PTS'):
            vc.validate_cached(self.video,self.profile,self.cache,0.,info['source_end_exclusive'],info)

    def test_discovery_reuses_native_cache_when_window_starts_in_source_gap(self):
        info = self.write_native()
        self.write_cache(self.frames[30:])
        moved = self.root/'outputs/native-cache'
        self.cache.rename(moved)
        begin = float(self.stamps[29]*TB+DT/4)
        with self.fixture.local():
            self.assertEqual(vc.find_cache(self.video,self.profile,begin,
                                          info['source_end_exclusive'],info),moved)

    def test_relabelled_30fps_and_reordered_pts_are_rejected(self):
        info = self.write_native()
        for mode in ('relabel','reorder'):
            rows = deepcopy(self.frames)
            if mode == 'relabel':
                for i,r in enumerate(rows):
                    r.update(native_pts=i,time_base='1/30',pts=i/30)
            else:
                rows[20], rows[21] = rows[21], rows[20]
            self.write_cache(rows)
            with self.assertRaises(ValueError):
                vc.validate_cached(self.video,self.profile,self.cache,0.,info['source_end_exclusive'],info)

    def test_whole_native_mvp_uses_same_registry_through_all_cpu_stages(self):
        from sceneguard.mvp_pipeline import execute
        info = self.write_native()
        out = self.root/'outputs/native-mvp'
        with self.fixture.local():
            result = execute(self.video,'C8',out,scene_path=self.scene,portal_path=self.portal,
                             cache=self.cache,whole=True,camera_registry=self.registry)
        self.assertEqual(result['state'],'analysis_complete')
        self.assertEqual(result['frames'],len(self.stamps))
        self.assertEqual(vc.read(out/'source/request.json')['camera_registry'],str(self.registry))
        for path in ('source/tracking/frames.jsonl','image-paths/frame-evidence.jsonl'):
            rows = [json.loads(s) for s in (out/path).read_text().splitlines()]
            self.assertEqual([r['native_pts'] for r in rows],self.stamps)
        manifest = vc.read(out/'viewer-manifest.json')
        self.assertEqual(manifest['requested_window'],[0.,info['source_end_exclusive']])
        self.assertEqual(vc.read(Path(manifest['source_frames_path']))[-1]['native_pts'],self.stamps[-1])

    def test_whole_endpoint_includes_last_frame_when_container_duration_equals_it(self):
        info = self.write_native()
        native_probe = dict(info,duration=self.frames[-1]['pts'])
        out = self.root/'outputs/native-eof'
        with self.fixture.local(), patch.object(vc,'probe',return_value=native_probe):
            result = vc.execute(self.video,'C8',out,cache=self.cache,whole=True,camera_registry=self.registry)
        self.assertEqual(result['frames'],len(self.stamps))
        self.assertEqual(vc.read(out/'request.json')['requested_window'][1],info['source_end_exclusive'])

    def test_canonical_queue_preflight_binds_registry_source_and_profile_bytes(self):
        from orchestration import video_cards_command as adapter
        from orchestration.queue import digest
        self.write_cache(self.fixture.frames)
        out = self.root/'outputs/queue-preflight'
        context = dict(run_id='existing',task_id='task',dispatch_id='dispatch',owner='worker')
        with self.fixture.local(), patch.object(vc,'find_cache',return_value=None):
            result = vc.execute(self.video,'C8',out,whole=True,camera_registry=self.registry)
            self.assertEqual(result['state'],'blocked')
            request = vc.read(out/'request.json');request['queue_context'] = context
            (out/'request.json').write_text(json.dumps(request))
            weight = self.root/'existing-test-weight';weight.write_bytes(b'no model loaded')
            config = dict(stage='fcos-cache',request_path=str(out/'request.json'),
                          request_sha256=vc.sha256(out/'request.json'),settings=adapter.SETTINGS,context=context)
            inputs = dict(request_sha256=config['request_sha256'],source_sha256=vc.sha256(self.video),
                          model_sha256=vc.sha256(weight),settings_sha256=digest(adapter.SETTINGS))
            with patch.object(adapter,'ROOT',self.root), patch.object(adapter,'WEIGHT',weight), \
                    patch.object(adapter,'FCOS_SHA',vc.sha256(weight)), \
                    patch.object(adapter,'validate_assignment',return_value={}) as assignment:
                self.assertEqual(adapter.validate(config,inputs,adapter.RUNTIME),request)
                self.assertEqual(assignment.call_count,1)
                self.document['scope'] = 'changed after freeze'
                self.write_registry()
                with self.assertRaisesRegex(ValueError,'input bytes differ'):
                    adapter.validate(config,inputs,adapter.RUNTIME)
                self.assertEqual(assignment.call_count,1)


class LegacyCacheRegression(unittest.TestCase):
    def test_007_030_tracking_and_candidates_equal_preserved_complete_runs(self):
        """Optional local real-cache regression: no decoder, detector or models."""
        import tempfile
        historical = vc.ROOT/'outputs/validation/mvp-all-v2/runs'
        if not all((historical/f'E01_{key}/source/tracking/frames.jsonl').is_file() for key in ('007','030')):
            self.skipTest('Preserved local 007/030 detector caches are not distributed')
        cameras = vc.read(vc.CAMERAS)['cameras']
        from sceneguard.replay_gap_tracking import load_cache
        for key,camera in (('007','C3'),('030','C6')):
            source = historical/f'E01_{key}/source'
            analysis = vc.read(source/'analysis/analysis.json')
            meta,frames,interval,_ = load_cache(analysis['source_paths']['cache'])
            with tempfile.TemporaryDirectory() as d:
                output = Path(d)
                vc.track(frames,cameras[camera],output,interval,meta['video_id'])
                self.assertEqual((output/'frames.jsonl').read_bytes(),(source/'tracking/frames.jsonl').read_bytes())
                self.assertEqual(vc.read(output/'events.json'),vc.read(source/'tracking/events.json'))


class NativeTrackerContracts(unittest.TestCase):
    def frame(self, tick, score=.9):
        return dict(pts=float(tick*DT),native_pts=tick*3003,time_base=str(TB),source_size=[100,100],
                    boxes=[] if score is None else [[40,10,60,70]],scores=[] if score is None else [score])

    def test_internal_gap_aging_produces_only_current_actual_measurements(self):
        adapter = ByteAdapter(True,native_interval=DT,retain_seconds=3.)
        first = adapter.step(self.frame(0))[0][0]['track_id']
        obs,states,_ = adapter.step(self.frame(2))
        self.assertEqual(adapter.gap_prediction_steps,1)
        self.assertEqual(adapter.tracker.frame_id,3)
        self.assertEqual(obs[0]['track_id'],first)
        self.assertEqual(obs[0]['last_observed_pts'],float(2*DT))
        self.assertTrue(all(r['observed'] for r in obs))
        self.assertEqual(len(states),1)

    def test_native_elapsed_seconds_expire_track_before_reassociation(self):
        from sceneguard.replay_gap_tracking import make_adapter
        adapter = make_adapter(3.,float(DT),native_timing=True)
        old = adapter.step(self.frame(0))[0][0]['track_id']
        obs,states,_ = adapter.step(self.frame(91))
        self.assertEqual(obs,[])
        self.assertNotIn(old,[s['track_id'] for s in states])
        self.assertNotEqual(adapter.step(self.frame(92))[0][0]['track_id'],old)

    def test_nonlattice_native_pts_are_rejected(self):
        adapter = ByteAdapter(True,native_interval=DT,retain_seconds=3.)
        adapter.step(self.frame(0))
        frame = self.frame(1);frame['native_pts'] += 1;frame['pts'] = float(frame['native_pts']*TB)
        with self.assertRaisesRegex(ValueError,'integral PTS gaps'):adapter.step(frame)

    def test_cpu_image_windows_reset_after_source_gap_without_inventing_samples(self):
        import numpy as np
        from sceneguard.gate_transition import GateTransition
        scene = dict(source_size=[100,100],line=[[.5,0],[.5,1]],
            approach_polygon=[[0,0],[1,0],[1,1],[0,1]],
            directions=['outside_to_inside','inside_to_outside'])
        engine = GateTransition(scene)
        image = np.random.default_rng(42).integers(0,256,(100,100),dtype=np.uint8)
        boxes = [dict(bbox=[.3,.1,.7,.9],score=.9,cache_index=0,track_ids=[1])]
        born = engine.step(image,0.,boxes,0)
        self.assertTrue(born['point_paths'])
        step = engine.step(image,float(2*DT),boxes,1)
        self.assertFalse(step['source_gap'])
        self.assertEqual(step['point_paths'][0]['window_id'],born['point_paths'][0]['window_id'])
        gap = engine.step(image,float(10*DT),boxes,2)
        self.assertTrue(gap['source_gap'])
        self.assertEqual(gap['point_paths'],[])
        self.assertEqual(gap['frame_index'],2)


if __name__ == '__main__': unittest.main()
