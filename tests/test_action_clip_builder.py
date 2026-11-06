"""Counterexamples for actor/action labels, index uncertainty and frozen splits."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('clip_builder', Path(__file__).resolve().parents[1]/'scripts/build_action_training_clips.py')
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


def fixture(name='wall_over'):
    event = dict(event_index=0, actor_id=7, object_id=4, class_name=name,
                 annotation_classes=[name], start_frame_declared=10, end_frame_declared=30)
    source = dict(source_id='source-a', source_path='/data/a.mp4', source_sha256='a'*64,
                  label_path='/data/a.json', label_sha256='b'*64, scenario=1, excluded=False, errors=[],
                  label={'events': [event], 'info': {'location':'park', 'fps':3}},
                  video={'width':1000,'height':800,'average_rate':'3','time_base':'1/3'})
    a = dict(source_id='source-a',source_sha256='a'*64,label_sha256='b'*64,group_id='event-a',
             location='park',split='train',excluded=False,evaluation_cohort='same_place_separate_capture')
    annotations=[dict(actor_id=7,object_id=4,class_name=name,cur_frame=i,bbox=[[100,100],[200,300]]) for i in range(10,31)]
    packet={'pts':list(range(100)), 'time_base':'1/3'}
    return source,a,event,annotations,packet


class ClipBuilderTest(unittest.TestCase):
    def test_origin_intersection_and_center_tie(self):
        self.assertEqual(b.center_indices(10,18), list(range(10,18)))
        self.assertEqual(b.center_indices(10,19), list(range(10,18)))
        self.assertEqual(b.center_indices(10,20), list(range(11,19)))
        with self.assertRaisesRegex(ValueError,'short_both_origin'):
            b.center_indices(10,17)

    def test_roi_covers_both_origins_and_stays_fullframe(self):
        s,a,e,ann,p=fixture()
        ann[14]['bbox']=[[250,200],[350,400]]  # d+1 only at last selected sample
        row=b.plan_event(s,a,e,ann,p)
        self.assertEqual(row['sample_frame_indices'],list(range(16,24)))
        self.assertEqual(row['actor_union_xyxy'],[100,100,350,400])
        self.assertEqual(row['roi_xyxy'],[0,0,600,550])
        self.assertFalse(row['roi_human_inspected'])
        self.assertEqual(len(row['label_evidence']['selected_annotation_indices']),9)
        self.assertTrue(row['verified_action_interval'][0]<=row['sample_pts'][0])
        self.assertTrue(row['verified_action_interval'][1]>=row['sample_pts'][-1])

    def test_missing_frame_never_padded(self):
        s,a,e,ann,p=fixture()
        ann=[x for x in ann if x['cur_frame']!=24]
        with self.assertRaisesRegex(ValueError,'missing_box_frames'):
            b.plan_event(s,a,e,ann,p)

    def test_duplicate_and_contradictory_boxes_quarantined(self):
        s,a,e,ann,p=fixture()
        ann.append(copy.deepcopy(ann[8]))
        with self.assertRaisesRegex(ValueError,'duplicate_or_contradictory'):
            b.plan_event(s,a,e,ann,p)
        ann.pop();ann[8]['class_name']='moving'
        with self.assertRaisesRegex(ValueError,'multi_action_ambiguity'):
            b.plan_event(s,a,e,ann,p)

    def test_invalid_or_nonfinite_box_quarantined(self):
        for bbox in ([[0,0],[1001,20]], [[0,0],[0,20]], [[0,float('nan')],[10,20]]):
            with self.subTest(bbox=bbox):
                s,a,e,ann,p=fixture();ann[8]['bbox']=bbox
                with self.assertRaisesRegex(ValueError,'invalid_box'):
                    b.plan_event(s,a,e,ann,p)

    def test_negative_is_actor_annotation_not_absence(self):
        s,a,e,ann,p=fixture('moving')
        row=b.plan_event(s,a,e,ann,p)
        self.assertEqual(row['label'],0)
        self.assertEqual(row['negative_basis'],'explicit_action_annotation')
        e['class_name']='sit_down_bench'
        with self.assertRaisesRegex(ValueError,'unsupported_or_ambiguous'):
            b.plan_event(s,a,e,ann,p)

    def test_sitting_requires_explicit_v2_policy_and_actor_annotation(self):
        for name in ('sit_down_bench','sit_down_floor'):
            s,a,e,ann,p=fixture(name)
            with self.assertRaisesRegex(ValueError,'unsupported_or_ambiguous'):
                b.plan_event(s,a,e,ann,p)
            row=b.plan_event(s,a,e,ann,p,negative_policy='explicit_normal_actions_v2')
            self.assertEqual((row['label'],row['action_class'],row['negative_basis']),
                             (0,name,'explicit_action_annotation'))
            ann.append(dict(actor_id=99,object_id=4,class_name='wall_over',cur_frame=20,bbox=[[800,0],[900,100]]))
            with self.assertRaisesRegex(ValueError,'concurrent_wall_over'):
                b.plan_event(s,a,e,ann,p,negative_policy='explicit_normal_actions_v2')

    def test_any_concurrent_wall_actor_rejects_negative(self):
        s,a,e,ann,p=fixture('stand')
        ann.append(dict(actor_id=99,object_id=4,class_name='wall_over',cur_frame=24,bbox=[[800,0],[900,100]]))
        with self.assertRaisesRegex(ValueError,'concurrent_wall_over_annotation'):
            b.plan_event(s,a,e,ann,p)

    def test_wall_event_rejects_negative_even_if_wall_box_missing(self):
        s,a,e,ann,p=fixture('stand')
        other=dict(e,event_index=1,actor_id=99,class_name='wall_over',annotation_classes=['wall_over'])
        s['label']['events'].append(other)
        with self.assertRaisesRegex(ValueError,'concurrent_wall_over_event'):
            b.plan_event(s,a,e,ann,p)

    def test_other_actor_stand_does_not_invalidate_positive(self):
        s,a,e,ann,p=fixture()
        ann.append(dict(actor_id=99,object_id=4,class_name='stand',cur_frame=24,bbox=[[800,0],[900,100]]))
        self.assertEqual(b.plan_event(s,a,e,ann,p)['label'],1)

    def test_same_actor_overlapping_events_quarantined(self):
        s,a,e,ann,p=fixture()
        s['label']['events'].append(dict(e,event_index=1))
        with self.assertRaisesRegex(ValueError,'overlapping_actor_events'):
            b.plan_event(s,a,e,ann,p)

    def test_same_actor_conflicting_objects_do_not_escape_ambiguity_guard(self):
        s,a,e,ann,p=fixture()
        ann.append(dict(actor_id=7,object_id=99,class_name='stand',cur_frame=20,bbox=[[100,100],[200,300]]))
        with self.assertRaisesRegex(ValueError,'multi_action_ambiguity'):
            b.plan_event(s,a,e,ann,p)
        ann.pop();s['label']['events'].append(dict(e,event_index=1,object_id=99))
        with self.assertRaisesRegex(ValueError,'overlapping_actor_events'):
            b.plan_event(s,a,e,ann,p)

    def test_missing_or_duplicate_native_pts_quarantined(self):
        for change in ('gap','duplicate','missing'):
            with self.subTest(change=change):
                s,a,e,ann,p=fixture()
                if change=='gap':p['pts'].remove(20)
                elif change=='duplicate':p['pts'].append(20)
                else:p['pts'][20]=None
                with self.assertRaisesRegex(ValueError,'native_frames|packet_pts'):
                    b.plan_event(s,a,e,ann,p)

    def test_build_accounting_excludes_sources_and_freezes_membership(self):
        s,a,e,ann,p=fixture()
        split={'assignments':[a],'held_out_test_locations':['heldout']}
        baseline={'status':'verified','baseline_experiment':'EXP-0062','regression_only_videos':[]}
        build=lambda:b.build_plan([s],split,baseline,{'source-a':p},lambda _: {'events':[e],'annotations':ann})
        clips, exclusions, sources=build()
        self.assertEqual((len(clips),len(exclusions),len(sources)),(1,0,1))
        a['source_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'hash differs'):build()
        a['source_sha256']=s['source_sha256'];a['location']='heldout';s['label']['info']['location']='heldout'
        with self.assertRaisesRegex(ValueError,'Held-out'):build()
        a['split']='excluded';a['excluded']=True
        clips, exclusions, _=build()
        self.assertEqual((len(clips),exclusions[0]['reason']),(0,'user_excluded_source'))

    def test_regression_forbidden_by_path_and_hash(self):
        for field in ('path','sha256'):
            s,a,e,ann,p=fixture()
            item={'path':'/other','sha256':'c'*64};item[field]=s['source_path' if field=='path' else 'source_sha256']
            with self.assertRaisesRegex(ValueError,'Forbidden regression'):
                b.build_plan([s],{'assignments':[a],'held_out_test_locations':[]},
                             {'status':'verified','baseline_experiment':'EXP-0062','regression_only_videos':[item]},
                             {'source-a':p},lambda _: {'events':[e],'annotations':ann})

    def test_event_group_or_source_copies_cannot_cross_splits(self):
        for same_hash in (True, False):
            s,a,e,ann,p=fixture();s2=copy.deepcopy(s);a2=copy.deepcopy(a)
            s2.update(source_id='source-b',source_path='/data/b.mp4')
            a2.update(source_id='source-b',split='test')
            if same_hash:a2['group_id']='event-b'
            else:s2['source_sha256']=a2['source_sha256']='c'*64
            with self.assertRaisesRegex(ValueError,'leakage'):
                b.build_plan([s,s2],{'assignments':[a,a2],'held_out_test_locations':[]},
                             {'status':'verified','baseline_experiment':'EXP-0062','regression_only_videos':[]},
                             {'source-a':p,'source-b':p},lambda _: {'events':[e],'annotations':ann})

    def test_review_versions_and_hashes_are_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);snapshot=root/'snapshot.json';policy=root/'policy.md';evidence=root/'evidence.json'
            reviews=[dict(id=f'request-{i}',version=4,answer_version=1,status='applied',answer='sample observation') for i in range(8)]
            snapshot.write_text(json.dumps({'requests':reviews}));policy.write_text('Sampled alignment only.')
            data=dict(experiment_id='EXP-0063',label_policy=b.LABEL_POLICY,review_status=b.REVIEW_STATUS,
                      full_human_semantic_validation=False,
                      review_snapshot={'path':str(snapshot),'sha256':b.sha(snapshot)},
                      interpretation_policy={'path':str(policy),'sha256':b.sha(policy)},
                      reviews=[{'request_id':r['id'],'version':4,'answer_version':1} for r in reviews])
            evidence.write_text(json.dumps(data));self.assertEqual(b.validate_review_evidence(evidence),data)
            data['reviews'][0]['answer_version']=2;evidence.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'exact eight'):b.validate_review_evidence(evidence)
            data['reviews'][0]['answer_version']=1;evidence.write_text(json.dumps(data));policy.write_text('Changed')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):b.validate_review_evidence(evidence)


if __name__=='__main__':unittest.main()
