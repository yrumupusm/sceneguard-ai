"""Bounded label-repair CPU counterexamples; no real queue or detector forward."""
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import prepare_person_label_repair as prep
from scripts import infer_person_label_repair as infer
from orchestration import person_label_repair_command as command


class RepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data=prep.fixed_inputs();wanted={c['window_id'] for c in data['review']['cases'] if c['number'] in prep.CASES}
        data['plan']={'windows':[w for w in data['plan']['windows'] if w['window_id'] in wanted]}
        data['responses']={'requests':[{k:v for k,v in a.items() if k!='history'} for a in data['responses']['requests']]}
        cls.data=data

    def temporary(self):return tempfile.TemporaryDirectory(dir=prep.ROOT/'runtime/model-comparison/exp0066/label-repair-v1/executor')

    def test_exact_native75_cases_versions_splits_and_original_boxes(self):
        rows=prep.selected(self.data)
        self.assertEqual([c['number'] for c,_,_,_ in rows],[1,3,5])
        self.assertEqual(sum(len(c['frames']) for c,_,_,_ in rows),75)
        self.assertEqual([a['answer_version'] for _,_,_,a in rows],[1,2,1])
        self.assertEqual([c['split'] for c,_,_,_ in rows],['train','train','validation'])
        c,w,d,a=rows[0];frame=prep.frame_identity(c,w,d,a,c['frames'][0])
        self.assertEqual(frame['original_boxes_by_origin'],{'0':[],'1':[]})
        self.assertFalse(frame['human_verified']);self.assertFalse(frame['training_eligible'])
        self.assertFalse(frame['frame_origin_certified'])

    def test_review_version_binding_split_native_clock_and_scope_drift_rejected(self):
        def answer(data):data['responses']['requests'][0]['answer_version']=99
        def split(data):data['review']['cases'][0]['split']='validation'
        def clock(data):data['review']['cases'][0]['frames'][0]['source_pts']+=1/30
        def index(data):data['review']['cases'][0]['frames'][0]['frame_index']+=1
        def missing(data):data['review']['cases'][0]['frames'].pop()
        def wrong_disposition(data):data['decisions']['cases'][0]['disposition']='export_reviewed_person_scope'
        for mutate in (answer,split,clock,index,missing,wrong_disposition):
            data=copy.deepcopy(self.data);mutate(data)
            # The first response may concern another case; change a selected answer explicitly.
            if mutate is answer:
                aid=data['decisions']['cases'][0]['request_id']
                next(a for a in data['responses']['requests'] if a['id']==aid)['answer_version']=99
            with self.assertRaises(ValueError):prep.selected(data)

    def test_protected_school_source_and_cross_split_group_rejected(self):
        data=copy.deepcopy(self.data);data['baseline']['regression_only_videos'].append({'sha256':data['review']['cases'][0]['source_sha256']})
        with self.assertRaisesRegex(ValueError,'source'):prep.selected(data)
        data=copy.deepcopy(self.data);data['pilot']['frames'][0]['split']='validation'
        data['pilot']['frames'][0]['event_group']=data['review']['cases'][0]['event_group']
        with self.assertRaisesRegex(ValueError,'leakage'):prep.selected(data)

    def test_actual_prepared_native_rgb_and_immutable_annotations_validate(self):
        value=prep.validate_preparation(command.PREPARATION)
        self.assertEqual(len(value['images']),75);self.assertEqual(len(value['source_files']),3)
        manifest=prep.read(command.PREPARATION)
        self.assertEqual(sum(len(r['original_annotations']) for r in manifest['frames']),79)
        self.assertEqual(manifest['frame_counts'],{'train':50,'validation':25})
        self.assertFalse(manifest['training_release'])

    def fixture(self,root):
        import hashlib
        import numpy as np
        from PIL import Image
        data=copy.deepcopy(self.data);rgb=np.zeros((2,2,3),dtype=np.uint8);h=hashlib.sha256(rgb.tobytes()).hexdigest()
        refs={w['window_id']:w for w in data['plan']['windows']};prepared=root/'prepared';prepared.mkdir();rows=[]
        for c in data['review']['cases']:
            if c['number'] not in prep.CASES:continue
            c['source_size']=[2,2];c['label_bindings']={};w=refs[c['window_id']];w['source_size']=[2,2]
            source=root/f"source{c['number']}";source.write_bytes(str(c['number']).encode());w['source_path']=str(source)
            c['source_sha256']=w['source_sha256']=prep.sha(source)
            for ref in c['frames']:
                ref['source_rgb_sha256']=h;ref['boxes']={'0':[],'1':[]}
        fixed={k:(root/(k+'.json'),'unused') for k in prep.FIXED}
        with patch.object(prep,'fixed_inputs',return_value=data):selected=prep.selected(data)
        for c,w,d,a in selected:
            for ref in c['frames']:
                row=prep.frame_identity(c,w,d,a,ref);folder=prepared/'images'/row['split'];folder.mkdir(parents=True,exist_ok=True)
                image=folder/(row['frame_id']+'.png');Image.fromarray(rgb).save(image)
                row.update(image=prep.binding(image),original_label_copies=[]);rows.append(row)
        m=dict(purpose='person_label_repair_drafts_only',case_numbers=[1,3,5],training_release=False,human_verified=False,
               detector_proposals_are_ground_truth=False,model_inference_count=0,preparer_sha256=prep.sha(prep.__file__),
               original_annotations_modified=False,protected_school_or_test_used=False,frames=rows,
               frame_counts={'train':50,'validation':25},preparation_inputs={k:dict(path=str(p),sha256=h) for k,(p,h) in fixed.items()})
        path=prepared/'manifest.json';path.write_text(json.dumps(m))
        return data,fixed,path,m

    def test_prepared_annotation_image_or_rgb_tampering_and_duplicates_rejected(self):
        with self.temporary() as t:
            data,fixed,path,m=self.fixture(Path(t))
            with patch.object(prep,'fixed_inputs',return_value=data),patch.object(prep,'FIXED',fixed):
                prep.validate_preparation(path)
                mutations=[lambda x:x['frames'][0].update(original_annotations=[dict(actor=99,xyxy=[0,0,1,1])]),
                           lambda x:x['frames'].pop(),lambda x:x['frames'].append(x['frames'][0]),
                           lambda x:x['frames'][0]['image'].update(sha256='0'*64),
                           lambda x:x.update(training_release=True)]
                for mutate in mutations:
                    changed=copy.deepcopy(m);mutate(changed);path.write_text(json.dumps(changed))
                    with self.assertRaises(ValueError):prep.validate_preparation(path)

    def native(self):
        return dict(boxes=[[1,2,5,8]],person_scores=[.6],native_class_ids=[0],valid_boxes=[True],
            input_frame_index=8,actual_input_frames=1,input_color='BGR',input_resolution=[640,640],full_frame=True,
            person_threshold=.5,retained_person_threshold=.05,box_format='xyxy_original_input_pixels',native_end2end=True,
            additional_nms=False,external_person_proposals=False,fcos_gating=False,climbing_score=None,action_scores=None)

    def test_single_rgb_view_and_proposals_never_merge_or_become_truth(self):
        import numpy as np
        rgb=np.zeros((12,20,3),dtype=np.uint8);native=self.native()
        def stub(model,frames,spec):
            self.assertEqual(frames.shape,(16,12,20,3));self.assertEqual(frames.strides[0],0)
            self.assertTrue(np.array_equal(frames[8],rgb));return native
        self.assertIs(infer.infer_one(None,rgb,{},stub),native)
        original=[dict(actor=0,action='wall_over',xyxy=[1,2,5,8])]
        frame=dict(frame_id='case-01-frame-000099',source_size=[20,12],original_annotations=copy.deepcopy(original))
        rows=infer.proposal_rows(frame,native,'specsha')
        self.assertEqual(frame['original_annotations'],original);self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]['human_verified']);self.assertFalse(rows[0]['training_eligible'])
        self.assertEqual(rows[0]['review_state'],'unreviewed_model_proposal')

    def test_invalid_proposal_geometry_score_action_or_native_settings_rejected(self):
        mutations=[lambda x:x.update(boxes=[[1,2,100,8]]),lambda x:x.update(person_scores=[float('nan')]),
                   lambda x:x.update(person_scores=[.01]),lambda x:x.update(climbing_score=.6),
                   lambda x:x.update(additional_nms=True),lambda x:x.update(valid_boxes=[False])]
        for mutate in mutations:
            value=self.native();mutate(value)
            with self.assertRaises(ValueError):infer.proposal_rows(dict(frame_id='f',source_size=[20,12]),value,'sha')

    def test_pending_root_go_cannot_reach_source_assignment_or_model(self):
        with self.temporary() as t:
            p=Path(t)/'auth.json';p.write_text(json.dumps(dict(root_go=False)))
            config=dict(context=command.CONTEXT,stage='draft75',model_id='yolo26x',execution_revision='label-repair-v1',
                        files={},authorization=prep.binding(p))
            with patch.object(command,'input_contract',return_value={}),patch.object(command,'sources',return_value={}),\
                 patch.object(command,'validate_assignment',side_effect=AssertionError('must reject first')):
                with self.assertRaisesRegex(ValueError,'authorization'):command.validate(config,{},command.RUNTIME)

    def test_wrong_held_fd_and_direct_execution_rejected_before_inference(self):
        with self.temporary() as t:
            root=Path(t);(root/'gpu.lock').touch();wrong=root/'other';wrong.touch()
            with wrong.open('r') as f,patch.object(command,'RUNTIME',root),patch.dict(os.environ,{'SCENEGUARD_GPU_LOCK_FD':str(f.fileno())}):
                with self.assertRaisesRegex(ValueError,'reservation FD'):command.runner_guard(SimpleNamespace())
        with self.assertRaisesRegex(ValueError,'separately reviewed'):command.retry_guard(None,None)

    def test_root_queue_registry_migration_preserves_temporary_old_rows(self):
        from orchestration.queue import Queue,digest
        with self.temporary() as t:
            q=Queue.initialize(str(Path(t)/'queue'))
            first=q.enqueue(job_key='old',run_id='synthetic',task_id='synthetic',dispatch_id='synthetic',owner='synthetic')
            with q.connection() as db:old=dict(db.execute('select * from jobs where job_id=?',(first['job_id'],)).fetchone())
            config=dict(context=command.CONTEXT,stage='draft75',model_id='yolo26x',execution_revision='label-repair-v1',files={},authorization=None)
            with patch.object(command,'validate',return_value={}):
                value=q.enqueue(job_key=command.job_key(config),command='person-label-repair',config=config,input_value={},
                                timeout=1800,expected_input_hash=digest({}),expected_config_hash=digest(config),**command.CONTEXT)
            with q.connection() as db:
                self.assertEqual(dict(db.execute('select * from jobs where job_id=?',(first['job_id'],)).fetchone()),old)
                self.assertEqual(db.execute('select count(*) from attempts').fetchone()[0],0)
                self.assertEqual(db.execute('select count(*) from jobs').fetchone()[0],2)
            self.assertEqual(value['command'],'person-label-repair')


if __name__=='__main__':unittest.main(verbosity=2)
