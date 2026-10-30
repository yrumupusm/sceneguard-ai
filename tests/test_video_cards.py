"""Pipeline provenance/resume contracts; synthetic media, no model execution."""
from contextlib import ExitStack
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sceneguard import video_cards as vc
from sceneguard.replay_gap_tracking import FCOS_SHA, POSTPROCESS, STAGE


class PipelineTests(unittest.TestCase):
    def setUp(self):
        import av
        import numpy as np
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'outputs').mkdir()
        self.video = self.root/'selected.mp4'
        with av.open(str(self.video),'w') as target:
            stream = target.add_stream('libx264',rate=30)
            stream.width,stream.height = 64,48
            stream.pix_fmt='yuv420p'
            for i in range(60):
                frame=av.VideoFrame.from_ndarray(np.zeros((48,64,3),dtype=np.uint8),format='rgb24')
                frame.pts,frame.time_base=i,Fraction(1,30)
                for packet in stream.encode(frame):target.mux(packet)
            for packet in stream.encode():target.mux(packet)
        with av.open(str(self.video)) as source:
            self.frames=[dict(pts=float(f.pts*f.time_base),native_pts=f.pts,time_base=str(f.time_base),
                             source_size=[64,48],boxes=[],scores=[]) for f in source.decode(video=0)]
        self.config=dict(line=[[.5,0],[.5,1]],roi=[0,0,1,1],band=.005,dwell_seconds=.1,
            max_gap_seconds=.1,min_iou=.3,cooldown_seconds=1.,score_threshold=.5,
            directions=['negative_to_positive','positive_to_negative'],boundary_id='C3_fence',camera_group='C3')
        self.camera=dict(camera_id='C3',legacy_boundary_config=self.config)
        self.cameras=self.root/'cameras.json'
        vc.save(self.cameras,dict(cameras={'C3':self.camera}))
        zones=dict(outside=[[0,0],[.4,0],[.4,1],[0,1]],inside=[[.6,0],[1,0],[1,1],[.6,1]])
        self.regions=self.root/'regions.json';vc.save(self.regions,zones)
        self.scene=self.root/'scene.json'
        vc.save(self.scene,dict(source_size=[64,48],line=self.config['line'],
            approach_polygon=[[0,0],[1,0],[1,1],[0,1]],zones=zones,
            directions=['outside_to_inside','inside_to_outside'],
            annotation_provenance=dict(current_regions_path=str(self.regions),current_regions_sha256=vc.sha256(self.regions))))
        self.cache=self.root/'cache';self.cache.mkdir()
        (self.cache/'person_cache.jsonl').write_text(''.join(json.dumps(f)+'\n' for f in self.frames))
        self.meta=dict(status='complete',source_sha256=vc.sha256(self.video),source_size=[64,48],
            model_sha256=FCOS_SHA,model='fcos_resnet50_fpn.COCO_V1',model_postprocess=POSTPROCESS,
            model_input=dict(min_size=800,max_size=1333),sampling='none',precision='float32',batch_size=1,seed=0,
            config=self.config,frames=60,video_id='explicit-source',first_pts=0.,last_pts=self.frames[-1]['pts'],
            person_cache=dict(schema=1,stage=STAGE,sha256=vc.sha256(self.cache/'person_cache.jsonl')))
        vc.save(self.cache/'run.json',self.meta)
        self.info=vc.probe(self.video)

    def local(self):
        stack=ExitStack()
        stack.enter_context(patch.object(vc,'ROOT',self.root))
        stack.enter_context(patch.object(vc,'CAMERAS',self.cameras))
        stack.enter_context(patch.object(vc,'SCENES',{'C3':self.scene}))
        stack.enter_context(patch.object(vc,'code_binding',return_value={'test':'fixed'}))
        return stack

    def validate(self):
        return vc.validate_cached(self.video,self.camera,self.cache,0.,2.,self.info)

    def rewrite_meta(self, **changes):
        self.meta.update(changes)
        (self.cache/'run.json').write_text(json.dumps(self.meta))

    def test_end_to_end_original_video_and_resume_without_detector(self):
        output=self.root/'outputs/demo'
        with self.local(), patch('sceneguard.run_cv.run',side_effect=AssertionError('No model calls')):
            first=vc.execute(self.video,'C3',output,cache=self.cache,whole=True)
            self.assertEqual(first['state'],'complete')
            before={str(p):p.read_bytes() for p in output.rglob('*') if p.is_file() and p.name not in ('status.json','.pipeline.lock')}
            second=vc.execute(self.video,'C3',output,cache=self.cache,whole=True)
            self.assertTrue(all(second['reused_stages'].values()))
            self.assertEqual(before,{p:Path(p).read_bytes() for p in before})
            self.assertEqual(second['detector_frames_this_execution'],0)
            reg=vc.read(output/'registration.json')
            self.assertTrue(Path(reg['media'][0]['path']).is_file())
            self.assertEqual(reg['media'][0]['decoded_frames'],60)
            self.assertEqual(reg['source_pts_origin'],0.)

    def test_source_sha_rejects_renamed_wrong_video(self):
        self.rewrite_meta(source_sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'binding'):self.validate()

    def test_explicit_camera_mismatch_is_rejected(self):
        wrong=deepcopy(self.camera);wrong['legacy_boundary_config']['camera_group']='C6'
        with self.assertRaisesRegex(ValueError,'binding'):
            vc.validate_cached(self.video,wrong,self.cache,0.,2.,self.info)

    def test_model_and_settings_mismatch_is_rejected(self):
        self.rewrite_meta(precision='float16')
        with self.assertRaisesRegex(ValueError,'binding'):self.validate()

    def test_native_pts_float_binding_is_rejected(self):
        self.frames[3]['native_pts']+=1
        path=self.cache/'person_cache.jsonl'
        path.write_text(''.join(json.dumps(f)+'\n' for f in self.frames))
        self.meta['person_cache']['sha256']=vc.sha256(path);self.rewrite_meta()
        with self.assertRaisesRegex(ValueError,'native source PTS'):self.validate()

    def test_cache_tamper_is_rejected(self):
        with (self.cache/'person_cache.jsonl').open('a') as stream:stream.write('\n')
        with self.assertRaises(ValueError):self.validate()

    def test_window_not_covered_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'entire selected'):
            vc.validate_cached(self.video,self.camera,self.cache,0.,3.,self.info)

    def test_completed_stage_tamper_refused(self):
        out=self.root/'outputs/stages';out.mkdir()
        folder,_=vc.stage(out,'analysis',{'source':'a'},lambda p:vc.save(p/'data.json',{'value':1}))
        (folder/'data.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'bytes/binding'):
            vc.stage(out,'analysis',{'source':'a'},lambda p:self.fail('must not rerun'))

    def test_failed_stage_is_resumable_without_overwriting_old_partial(self):
        out=self.root/'outputs/stages';out.mkdir()
        def fail(p):
            vc.save(p/'partial.json',{})
            raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError):vc.stage(out,'analysis',{},fail)
        old=list(out.iterdir())
        target,reused=vc.stage(out,'analysis',{},lambda p:vc.save(p/'done.json',{}))
        self.assertFalse(reused)
        self.assertTrue(all(p.exists() for p in old))
        self.assertTrue((target/'done.json').exists())

    def test_symlink_stage_and_receipt_are_rejected_before_read(self):
        out=self.root/'outputs/stages';out.mkdir()
        external=self.root/'external';external.mkdir()
        (out/'analysis').symlink_to(external,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):
            vc.stage(out,'analysis',{},lambda p:self.fail('must not follow symlink'))
        (out/'analysis').unlink();(out/'analysis').mkdir()
        secret=self.root/'secret.json';vc.save(secret,{})
        (out/'analysis/stage.json').symlink_to(secret)
        with self.assertRaisesRegex(ValueError,'symlink'):
            vc.stage(out,'analysis',{},lambda p:self.fail('must not read symlink'))

    def test_service_registration_adds_only_new_ids_and_rejects_conflict(self):
        from sceneguard import video_cards_registration as registrar
        output=self.root/'outputs/demo'
        (self.root/'records').mkdir()
        vc.save(self.root/'records/assignments.json',dict(assignments=[dict(experiment_id='EXP-0037')]))
        runtime=self.root/'runtime';runtime.mkdir()
        config_path=runtime/'local_config.json'
        initial=dict(runtime_dir=str(runtime),repo_root=str(self.root),artifact_allow_root=str(self.root/'outputs'),
                     incident_bundles={'old':{'retained':True}},artifacts={'old':{'retained':True}})
        vc.save(config_path,initial)
        with self.local(),patch.object(registrar,'ROOT',self.root):
            vc.execute(self.video,'C3',output,cache=self.cache,whole=True)
            result=registrar.register(config_path,output/'registration.json','test-new')
            current=vc.read(config_path)
            self.assertEqual(current['incident_bundles']['old'],initial['incident_bundles']['old'])
            self.assertEqual(current['artifacts']['old'],initial['artifacts']['old'])
            self.assertTrue(result['registered'])
            self.assertTrue(current['incident_bundles']['test-new']['notification_enabled'])
            registrar.register(config_path,output/'registration.json','test-new')
            current['incident_bundles']['test-new']['sha256']='0'*64
            config_path.write_text(json.dumps(current))
            before=config_path.read_bytes()
            with self.assertRaisesRegex(ValueError,'Conflicting'):
                registrar.register(config_path,output/'registration.json','test-new')
            self.assertEqual(config_path.read_bytes(),before)

    def test_unsupported_camera_does_not_create_output(self):
        out=self.root/'outputs/bad'
        with self.assertRaises(ValueError):vc.execute(self.video,'C7',out,cache=self.cache,whole=True)
        self.assertFalse(out.exists())

    def test_missing_queue_context_blocks_uncached_video_without_inference(self):
        with self.local(),patch.object(vc,'find_cache',return_value=None):
            state=vc.execute(self.video,'C3',self.root/'outputs/blocked',whole=True)
        self.assertEqual(state['state'],'blocked')
        self.assertEqual(state['detector_calls'],0)

    def test_cache_discovery_uses_source_bytes_not_filename(self):
        self.cache.rename(self.root/'outputs/renamed-cache')
        with self.local():
            found=vc.find_cache(self.video,self.camera,0.,2.,self.info)
        self.assertEqual(found,self.root/'outputs/renamed-cache')

    def test_probe_refuses_unsupported_fps(self):
        class Stream:
            average_rate=Fraction(25)
        class Container:
            streams=type('Streams',(),dict(video=[Stream()]))()
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with patch('av.open',return_value=Container()):
            with self.assertRaisesRegex(ValueError,'30fps'):vc.probe(self.video)


class QueueContracts(unittest.TestCase):
    def test_exact_job_supervisor_cannot_claim_older_unrelated_work(self):
        from orchestration.queue import Queue
        with tempfile.TemporaryDirectory() as temp:
            queue=Queue.initialize(Path(temp).absolute())
            def enqueue(key):
                return queue.enqueue(job_key=key,run_id='r',task_id='t',dispatch_id='d',owner='o')
            old=enqueue('unrelated-oldest'); selected=enqueue('explicit-selected')
            queue.run_once(job_id=selected['job_id'])
            statuses={j['job_id']:j['status'] for j in queue.status()['jobs']}
            self.assertEqual(statuses[old['job_id']],'queued')
            self.assertEqual(statuses[selected['job_id']],'succeeded')
            queue.run_once(job_id='missing')
            self.assertEqual(queue.status()['jobs'][0]['status'],'queued')
            queue.run_once()
            self.assertTrue(all(j['status']=='succeeded' for j in queue.status()['jobs']))

    def test_additive_migration_preserves_every_old_row_and_attempt(self):
        from orchestration.queue import Queue
        with tempfile.TemporaryDirectory() as temp:
            queue=Queue.initialize(Path(temp).absolute())
            queue.enqueue(job_key='existing',run_id='r',task_id='t',dispatch_id='d',owner='o')
            queue.run_once()
            with queue.connection() as db:
                jobs=[tuple(r) for r in db.execute('SELECT * FROM jobs')]
                attempts=[tuple(r) for r in db.execute('SELECT * FROM attempts')]
            queue.migrate_commands(include_video_cards=True)
            with queue.connection() as db:
                self.assertEqual(jobs,[tuple(r) for r in db.execute('SELECT * FROM jobs')])
                self.assertEqual(attempts,[tuple(r) for r in db.execute('SELECT * FROM attempts')])
                self.assertIn("'video-cards'",db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])

    def test_canonical_assignment_cannot_be_replaced_with_foreign_run(self):
        from orchestration.video_cards_command import validate_assignment
        with self.assertRaises(ValueError):validate_assignment(dict(run_id='other'))

    def test_fresh_cache_retry_is_never_automatic(self):
        from orchestration.video_cards_command import retry_guard
        with self.assertRaisesRegex(ValueError,'retry'):retry_guard(None,{})


if __name__=='__main__':unittest.main()
