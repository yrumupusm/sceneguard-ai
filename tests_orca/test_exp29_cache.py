"""CPU contracts for EXP29: authority, preservation, native join and replay."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from orchestration import exp29_cache_command as command
from orchestration.queue import Queue, digest, source_hash
from exp29_cache.merge import merge_and_replay
from exp29_cache import runner
from sceneguard.replay_gap_tracking import sha256, load_cache


def rows(first, count):
    return [dict(pts=float(Fraction(first+i*512,15360)), native_pts=first+i*512,
                 time_base='1/15360', source_size=[1920,1080], boxes=[], scores=[])
            for i in range(count)]


def write_segment(folder, frames, meta):
    folder.mkdir()
    # Deliberately noncanonical whitespace exercises byte-preserving concatenation.
    (folder/'person_cache.jsonl').write_text(''.join(json.dumps(r, separators=(', ', ': '))+'\n' for r in frames))
    meta = copy.deepcopy(meta)
    meta.update(frames=len(frames), first_pts=frames[0]['pts'], last_pts=frames[-1]['pts'])
    meta['person_cache']['sha256'] = sha256(folder/'person_cache.jsonl')
    (folder/'run.json').write_text(json.dumps(meta))


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.meta = json.loads((command.CACHE/'run.json').read_text())
        self.old, self.new = rows(737280,600), rows(1044480,1110)
        self.schedule = {label:[{k:r[k] for k in ('pts','native_pts','time_base','source_size')} for r in rr]
                         for label,rr in [('original',self.old),('extension',self.new)]}

    def test_native_join_exact_and_reject_duplicate_missing_fabricated_time(self):
        command.timing_rows(self.old+self.new,737280,1710)
        for mutation in ('duplicate','missing','clock','size'):
            bad = copy.deepcopy(self.new)
            if mutation == 'duplicate': bad[0] = copy.deepcopy(self.old[-1])
            elif mutation == 'missing': bad.pop(1)
            elif mutation == 'clock': bad[4]['pts'] += .00001
            else: bad[0]['source_size'] = [960,540]
            with self.assertRaises(ValueError,msg=mutation):
                command.timing_rows(bad,1044480,1110)

    def test_real_cpu_merge_keeps_old_bytes_and_continuous_replay(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);old=root/'old';new=root/'new';out=root/'merged';replay=root/'replay'
            write_segment(old,self.old,self.meta);write_segment(new,self.new,self.meta)
            before={str(p):p.read_bytes() for f in (old,new) for p in f.iterdir()}
            result=merge_and_replay(old,new,out,replay,self.schedule)
            self.assertTrue(result['exact_native_continuity'])
            self.assertEqual((out/'person_cache.jsonl').read_bytes(),before[str(old/'person_cache.jsonl')]+before[str(new/'person_cache.jsonl')])
            self.assertEqual(result['join_native_pts'],[1043968,1044480])
            self.assertEqual(len(load_cache(out)[1]),1710)
            for condition in ('strict','gap'):
                tracked=[json.loads(l) for l in (replay/condition/'frames.jsonl').read_text().splitlines()]
                self.assertEqual(len(tracked),1710)
                self.assertEqual(tracked[600]['native_pts'],1044480)
                self.assertFalse(any(r['detections'] for r in tracked))
            self.assertEqual(before,{str(p):p.read_bytes() for f in (old,new) for p in f.iterdir()})
            with self.assertRaises(FileExistsError): merge_and_replay(old,new,out,replay,self.schedule)

    def test_merge_rejects_input_change_and_wrong_decode_schedule_before_outputs(self):
        for kind in ('schedule','model'):
            with tempfile.TemporaryDirectory() as t:
                r=Path(t);write_segment(r/'old',self.old,self.meta)
                meta=copy.deepcopy(self.meta)
                schedule=copy.deepcopy(self.schedule)
                if kind == 'model':meta['model_input']['min_size']=640
                else:schedule['extension'][0]['native_pts'] += 1
                write_segment(r/'new',self.new,meta)
                with self.assertRaises(ValueError):merge_and_replay(r/'old',r/'new',r/'out',r/'replay',schedule)
                self.assertFalse((r/'out').exists())

    def test_direct_launch_rejected_before_torch_import(self):
        p=subprocess.run([sys.executable,'-I',str(command.ROOT/'exp29_cache/runner.py'),
                          '--stage','extend007','--attempt','a'*32,'--lock-fd','999999'],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('Bad file descriptor',p.stderr)
        self.assertNotIn('import torch',p.stderr)

    def test_resource_gate_unchanged(self):
        with patch('batch04_pose.runner.subprocess.check_output',return_value='4000,6143'):
            with self.assertRaisesRegex(ValueError,'6144'):runner.resources()
        with patch('batch04_pose.runner.subprocess.check_output',return_value='4000,6144'):
            self.assertEqual(runner.resources()['free_mib'],6144)

    def test_exact_reviewed_authority_and_input_source_commit_binding(self):
        a=dict(zip(('run_id','task_id','dispatch_id'),command.IDENTITY))
        a.update(confirmed=True,inference_authorized=True,independent_review_passed=True,
                 maximum_new_frames=1110,allowed_stages=['extend007'],sources={'a':'b'},
                 input_contract_sha256=digest({'i':1}),code_sha='a'*40)
        with tempfile.TemporaryDirectory() as t,patch.object(command,'LOCAL',Path(t)),\
             patch.object(command,'sources',return_value={'a':'b'}),patch.object(command,'input_contract',return_value={'i':1}),\
             patch.object(command.subprocess,'check_output',return_value='a'*40+'\n'):
            p=Path(t)/'cache007-execution-authorization.json';p.write_text(json.dumps(a))
            command.validate_assignment(*command.IDENTITY)
            for key,value in [('sources',{}),('input_contract_sha256','0'*64),('code_sha','0'*40),
                              ('inference_authorized',False),('independent_review_passed',False),
                              ('maximum_new_frames',1111),('allowed_stages',['other'])]:
                p.write_text(json.dumps({**a,key:value}))
                with self.assertRaises(ValueError,msg=key):command.validate_assignment(*command.IDENTITY)
            p.write_text(json.dumps(a))
            with self.assertRaises(ValueError):command.validate_assignment(command.IDENTITY[0],'other',command.IDENTITY[2])

    def test_fixed_command_paths_and_settings(self):
        config=dict(stage='extend007',settings=copy.deepcopy(command.SETTINGS))
        with patch.object(command,'input_contract',return_value={'i':1}),patch.object(command,'validate_assignment'):
            argv=command.command(config,{'i':1},command.RUNTIME,'a'*32,123)
            self.assertEqual(argv[0],str(command.ROOT/'.venv/bin/python'))
            self.assertIn('exp29_cache/runner.py',' '.join(argv))
            with self.assertRaises(ValueError):command.validate(config,{'i':1},Path('/tmp/other'))
            config['settings']['start']=67.0
            with self.assertRaises(ValueError):command.validate(config,{'i':1},command.RUNTIME)
        with self.assertRaises(ValueError):command.output_path('extend007','../bad')
        with self.assertRaises(ValueError):command.job_key('extend030')
        self.assertEqual(source_hash('exp29-cache007'),digest(command.sources()))

    def test_history_copy_migration_preserves_44_jobs_and_attempts(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t)
            with sqlite3.connect('file:'+str(command.RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as src,sqlite3.connect(q.db) as dest:
                src.backup(dest)
            before=q.status()
            history={j['job_id'] for j in before['jobs'] if j['command']!='exp29-cache007'}
            self.assertEqual(len(history),44)
            self.assertEqual(sum(a['job_id'] in history for a in before['attempts']),44)
            q.migrate_commands(include_exp29_cache=True);q.migrate_commands(include_exp29_cache=True)
            self.assertEqual(q.status(),before)
            self.assertLessEqual(len(list(Path(t).glob('queue-before-exp29-cache007-*.sqlite3'))),1)
            with q.connection() as db:self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())

    def test_retry_requires_explicit_review_of_first_execution_error(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t)
            j=q.enqueue(job_key='synthetic',run_id='r',task_id='t',dispatch_id='d',owner='cpu')
            q.supervise_once()
            with q.connection() as db:
                attempt=db.execute('SELECT attempt_id FROM attempts').fetchone()[0]
                row=db.execute('SELECT * FROM jobs').fetchone()
                with patch.object(command,'validate_assignment',return_value={}):
                    with self.assertRaises(ValueError):command.retry_guard(db,row)
                db.execute("UPDATE attempts SET status='failed'")
                with patch.object(command,'validate_assignment',return_value={'execution_error_retry_authorized_for':attempt}):
                    command.retry_guard(db,row)

    def test_execution_guard_rejects_other_identity_and_third_attempt(self):
        class DB:
            def __init__(self,rows):self.rows=rows
            def execute(self,*a):return type('R',(),{'fetchall':lambda _:self.rows})()
        row=(command.job_key(),*command.IDENTITY,'a'*32,1)
        command.execution_guard(DB([row]),{'job_key':command.job_key()},'a'*32)
        for values in ([row]*3,[(row[0],'other',*row[2:])],[]):
            with self.assertRaises(ValueError):command.execution_guard(DB(values),{'job_key':command.job_key()},'a'*32)


if __name__ == '__main__':unittest.main()
