import importlib.util
from pathlib import Path
import sys
import unittest
import json
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import render_action_followup as media


class FollowupMediaTests(unittest.TestCase):
    def test_selection_preserves_all_misses_and_camera_diagnostics(self):
        events=[]
        for i,(camera,kind,matched) in enumerate([('C1','low',True),('C1','low',False),('C1','low',False),('C2','low',True),('C2','candidate',True),('C2','candidate',True)]):
            events.append(dict(video_id=str(i),start=i,reference_id=str(i),diagnostic=kind,baseline_confirmation_matched=matched))
        cameras={str(i):c for i,c in enumerate(['C1','C1','C1','C2','C2','C2'])}
        selected,decisions=media.select_events([{'events':events}],cameras)
        self.assertEqual({e['reference_id'] for e in selected},{'1','2','3','4'})
        self.assertEqual(len(decisions),6)

    def test_partial_requires_actual_observation_in_reference(self):
        plan={'samples':[{'pts':i,'observed':{'x':[0,0,1,1]} if i==0 else {}} for i in range(8)],
              'missing_windows':[{'start_target_index':0,'track_id':'x','missing_target_indices':list(range(1,8))}]}
        window,partial=media.choose_window({'start':4,'end':5},plan,[])
        self.assertIsNone(window);self.assertIsNone(partial)
        window,partial=media.choose_window({'start':0,'end':1},plan,[])
        self.assertIsNone(window);self.assertEqual(partial['track_id'],'x')

    def test_scored_window_uses_sample_overlap_half_open(self):
        scores=[dict(score=.9,start_target_index=0,sample_pts=[0,1,2]),dict(score=.1,start_target_index=3,sample_pts=[3,4,5])]
        window,_=media.choose_window({'start':3,'end':4},{'missing_windows':[]},scores)
        self.assertEqual(window['score'],.1)

    def test_annotation_origin_and_other_actor_roi_are_separate(self):
        label={'annotations':[dict(actor_id=0,class_name='stand',cur_frame=2,bbox=[[1,1],[3,3]]),dict(actor_id=1,class_name='wall_over',cur_frame=2,bbox=[[2,2],[5,5]])]}
        row={'actor_id':0,'sample_frame_indices':[1],'roi_xyxy':[0,0,4,4]}
        audit=media.annotation_roi_audit(row,label)
        self.assertFalse(audit['origins']['0'][0]['target_annotated'])
        self.assertTrue(audit['origins']['1'][0]['target_annotated'])
        self.assertEqual(audit['origins']['1'][0]['other_annotated_actors_in_roi'][0]['id'],'1')
        self.assertIsNone(audit['unannotated_other_climber_in_roi'])

    def test_no_input_has_no_manufactured_roi_or_score(self):
        plan=dict(last_pts=8,source_path='x',source_sha256='a',width=10,height=10,
                  samples=[dict(pts=i,frame_index=i,observed={}) for i in range(9)],missing_windows=[])
        event=dict(start=2,end=4,video_id='v',camera_id='C1',reference_id='e',diagnostic='no_observed_window_in_reference',baseline_confirmation_matched=False)
        item=media.school_item(event,plan,[])
        self.assertIsNone(item['window']);self.assertIsNone(item['target_id'])
        self.assertTrue(all(s['boxes']==[] for s in item['samples']))

    def test_reviewed_coverage_rejects_changed_event_caption(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            rows=[{'video_id':str(i),'events':[{'video_id':str(i),'reference_id':str(j),'diagnostic':'low','start':1} for j in range(2 if i<7 else 1)]} for i in range(45)]
            (root/'per-video.json').write_text(json.dumps(rows))
            (root/'summary.json').write_text(json.dumps({'event_diagnostic_counts':{'low':52}}))
            summary_sha=media.sha(root/'summary.json');rows_sha=media.sha(root/'per-video.json')
            self.assertEqual(len(media.reviewed_coverage(root,summary_sha,rows_sha)[1]),45)
            rows[0]['events'][0]['start']=999
            (root/'per-video.json').write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError,'reviewed bytes'):
                media.reviewed_coverage(root,summary_sha,rows_sha)

    def test_partial_context_contains_all_eight_planned_positions(self):
        samples=[dict(pts=i,frame_index=i,observed={'x':[0,0,1,1]} if i%2 else {}) for i in range(30)]
        plan=dict(last_pts=29,source_path='x',source_sha256='a',width=10,height=10,samples=samples,
                  missing_windows=[dict(start_target_index=15,track_id='x',missing_target_indices=[16,18,20,22])])
        event=dict(start=1,end=29,video_id='v',camera_id='C1',reference_id='e',diagnostic='partial_observations_only',baseline_confirmation_matched=False)
        item=media.school_item(event,plan,[])
        self.assertEqual([s['pts'] for s in item['partial_sample_plan']],list(range(15,23)))
        self.assertTrue(set(range(15,23))<={s['pts'] for s in item['samples']})
        self.assertIsNone(item['window'])


if __name__=='__main__': unittest.main()
