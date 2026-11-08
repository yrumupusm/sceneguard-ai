"""CPU-only comparison guards and native timeline regression tests."""
import copy
import hashlib
import fcntl
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

from orchestration import model_comparison_command as command
from orchestration.queue import Queue,digest
from scripts.run_model_comparison import process_video,validate_window


class ComparisonTests(unittest.TestCase):
    def test_utf8_metadata_survives_native_dependency_locale_change(self):
        import locale
        from scripts.run_model_comparison import read as runner_read
        previous = locale.setlocale(locale.LC_CTYPE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'manifest.json'
                path.write_text('{"source": "월담행위"}', encoding='utf-8')
                locale.setlocale(locale.LC_CTYPE, 'C')
                self.assertEqual(command.read(path), {'source': '월담행위'})
                self.assertEqual(runner_read(path), {'source': '월담행위'})
        finally:
            locale.setlocale(locale.LC_CTYPE, previous)

    def test_comparison_timeout_has_explicit_four_hour_bound_without_relaxing_other_commands(self):
        context=dict(run_id='r',task_id='t',dispatch_id='d',owner='o')
        config=dict(stage='all45',model_id='r3d18_exp0064',execution_revision='timeout-v2',context=context,files={})
        with tempfile.TemporaryDirectory() as t,patch.object(command,'validate'),patch.object(command,'sources',return_value={}):
            q=Queue.initialize(Path(t)/'queue')
            q.enqueue(job_key=command.job_key(config),command='model-compare',input_value={},config=config,timeout=14400,**context)
            for limit in (14400.01,float('nan'),float('inf'),0,-1):
                with self.assertRaisesRegex(ValueError,'timeout'):
                    q.enqueue(job_key=command.job_key(config),command='model-compare',input_value={},config=config,timeout=limit,**context)
            with self.assertRaisesRegex(ValueError,'timeout'):
                q.enqueue(job_key='mock',timeout=3601,**context)

    def test_queue_migration_preserves_existing_rows_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(Path(t)/'queue')
            q.enqueue(job_key='old',run_id='r',task_id='t',dispatch_id='d',owner='o')
            q.migrate_commands()
            before=q.status()
            q.migrate_commands(include_model_compare=True)
            q.migrate_commands(include_model_compare=True)
            self.assertEqual(q.status(),before)
            with q.connection() as db:
                self.assertIn("'model-compare'",db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])

    def test_unheld_or_wrong_fd_rejects_before_model_access(self):
        with tempfile.TemporaryDirectory() as t,patch.object(command,'RUNTIME',Path(t)):
            for name,pattern in [('gpu.lock','not held'),('other.lock','Wrong')]:
                with (Path(t)/name).open('a+') as lock,patch.dict(os.environ,SCENEGUARD_GPU_LOCK_FD=str(lock.fileno())):
                    with self.assertRaisesRegex(ValueError,pattern):command.runner_guard(SimpleNamespace())

    def test_exact_source_input_review_and_assignment_required(self):
        context=dict(run_id='run_3d23462a014a',task_id='t',dispatch_id='d',owner='o')
        config=dict(stage='smoke',model_id='r3d18_exp0064',execution_revision='v1',context=context,files={})
        source={'code.py':hashlib.sha256(b'code').hexdigest()};inputs={'f':'h'}
        auth=dict(stage='smoke',model_id=config['model_id'],execution_revision='v1',context=context,
                  input_hash=digest(inputs),sources=source,code_sha='a'*40,
                  confirmed=True,comparison_authorized=True,independent_review_passed=True,root_go=True,explicit_gpu_go=True)
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'auth.json'
            def write(a):
                path.write_text(json.dumps(a));config['authorization']={'path':str(path),'sha256':command.file_hash(path)}
            with patch.object(command,'input_contract',return_value=inputs),patch.object(command,'sources',return_value=source),\
                 patch.object(command,'validate_assignment',return_value={}),\
                 patch.object(command.subprocess,'check_output',side_effect=lambda argv,**kw:'a'*40 if argv[1]=='rev-parse' else b'code'):
                write(auth);command.validate(config,inputs,command.RUNTIME)
                for key,value in [('root_go',False),('explicit_gpu_go',False),('sources',{}),('code_sha','b'*40),
                                  ('independent_review_passed',False),('input_hash','old'),('model_id','vjepa2_l')]:
                    write({**auth,key:value})
                    with self.assertRaises(ValueError,msg=key):command.validate(config,inputs,command.RUNTIME)
                write(auth)
                with self.assertRaises(ValueError):command.validate(config,{'changed':True},command.RUNTIME)
                with self.assertRaises(ValueError):command.validate(config,inputs,t)

    def test_success_exit_without_result_is_failed_with_actual_receipt(self):
        context=dict(run_id='r',task_id='t',dispatch_id='d',owner='o')
        config=dict(stage='smoke',model_id='r3d18_exp0064',execution_revision='v1',context=context,files={})
        with tempfile.TemporaryDirectory() as t,patch.object(command,'validate'),\
             patch.object(command,'sources',return_value={'fake':'bound'}),\
             patch.object(command,'OUTPUT',Path(t)/'results'):
            q=Queue.initialize(Path(t)/'queue')
            job=q.enqueue(job_key=command.job_key(config),command='model-compare',input_value={},config=config,**context)
            with patch.object(command,'command',return_value=['/bin/true']):result=q.supervise_once(job['job_id'])
            self.assertEqual(result['status'],'failed')
            receipt=json.loads((q.runtime/'attempts'/result['attempt_id']/'manifest.json').read_text())
            self.assertEqual(receipt['execution_status'],'failed');self.assertIsNone(receipt['result_sha256'])

    def test_native_pts_gap_and_boundary_duplicates_do_not_invent_observations(self):
        with tempfile.TemporaryDirectory() as t:
            clocks={'native_pts':[0,3003,9009],'time_base':'1/90000'}
            path=Path(t)/'clock.json';path.write_text(json.dumps({'clocks':clocks}))
            indices=[0]*7+[1]*2+[2]*7
            pts=[clocks['native_pts'][i]/90000 for i in indices]
            window=dict(window_id='boundary',sample_frame_indices=indices,sample_pts=pts,available_after_pts=pts[-1])
            video=dict(video_id='006',source_sha256='x',source_size=[4,2],native_pts_binding={'path':str(path)})
            frames=[(p/90000,np.full((2,4,3),i,dtype=np.uint8)) for i,p in enumerate(clocks['native_pts'])]
            rows=[]
            result=process_video(video,[window],frames,lambda pixels:{'pixel_values':pixels[:,0,0,0].tolist()},rows.append)
            self.assertEqual(result['decoded_native_frames'],3)
            self.assertEqual(rows[0]['observed_unique_frames'],3)
            self.assertEqual(rows[0]['output']['pixel_values'],indices)
            self.assertFalse(rows[0]['same_person_verified'])
            self.assertFalse(rows[0]['intrusion_completed'])
            single=[]
            process_video(video,[window],frames,lambda pixels:{'actual_input_frames':1,'input_frame_index':8},single.append)
            self.assertEqual(single[0]['box_frame_index'],1)
            self.assertEqual(single[0]['box_pts'],3003/90000)
            self.assertLess(single[0]['model_input_available_after_pts'],window['available_after_pts'])
            with self.assertRaisesRegex(ValueError,'Incomplete'):
                process_video(video,[window],frames[:-1],lambda x:{},lambda x:None)
            frames[1]=(1/30,frames[1][1])
            with self.assertRaisesRegex(ValueError,'PTS differ'):
                process_video(video,[window],frames,lambda x:{},lambda x:None)
            bad=copy.deepcopy(window);bad['available_after_pts']=0
            with self.assertRaisesRegex(ValueError,'last actual input'):validate_window(bad,clocks)

    def test_no_arbitrary_stage_path_or_retry(self):
        for stage,attempt in [('train','a'*32),('all45','../bad')]:
            with self.assertRaises(ValueError):command.output_path(stage,attempt)
        with self.assertRaises(ValueError):command.retry_guard(None,None)


if __name__=='__main__':unittest.main()
