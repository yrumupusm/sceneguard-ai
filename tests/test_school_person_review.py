import copy
import unittest
from scripts.prepare_school_person_review import select_output, proposals


def row(role='fullvideo_regular',t=90.):
    return dict(video_id='E01_030',box_pts=t,box_frame_index=2700,
        window=dict(role=role,window_id=role,sample_pts=[t]*16,sample_frame_indices=[2700]*16),
        output=dict(actual_input_frames=1,boxes=[[1,2,10,20]],person_scores=[.7],valid_boxes=[True]))


class SchoolReviewTests(unittest.TestCase):
    def test_native_time_must_match_not_round_to_nearby(self):
        with self.assertRaises(ValueError):select_output({'a':row(t=90.0333)},'E01_030',90.)

    def test_duplicate_clock_uses_regular_and_rejects_conflicts(self):
        a=row();b=row('diagnostic')
        self.assertEqual(select_output({'a':a,'b':b},'E01_030',90.),a)
        b['output']['person_scores']=[.6]
        with self.assertRaises(ValueError):select_output({'a':a,'b':b},'E01_030',90.)

    def test_wrong_output_frame_is_rejected(self):
        a=row();a['box_frame_index']=2699
        with self.assertRaises(ValueError):select_output({'a':a},'E01_030',90.)

    def test_cross_model_overlap_dedup_is_only_reference(self):
        outputs={m:row() for m in ['yolo26m','yolo26l','yolo26x']}
        before=copy.deepcopy(outputs);result=proposals(outputs,'test')
        self.assertEqual(len(result),1);self.assertEqual(result[0]['kind'],'model')
        self.assertEqual(outputs,before)
        self.assertNotIn('confirmed',result[0])

    def test_no_proposals_is_not_empty_ground_truth(self):
        outputs={m:row() for m in ['yolo26m','yolo26l','yolo26x']}
        for r in outputs.values():r['output'].update(boxes=[],person_scores=[],valid_boxes=[])
        self.assertEqual(proposals(outputs,'test'),[])


if __name__=='__main__':unittest.main()
