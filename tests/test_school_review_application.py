import unittest
import json
import tempfile
from pathlib import Path
from scripts.apply_school_person_review import classify, QUALIFIED_NOTES
from scripts.evaluate_exp0074_baseline import summarize
from scripts.evaluate_exp0074_checkpoint import evaluation_frames, summarize_epoch


class SchoolApplicationTests(unittest.TestCase):
    def setUp(self):
        self.frame=dict(frame_id='f',image_sha256='image')
        self.rev=dict(frame_id='f',image_sha256='image',package_sha256='package',version=1,
            status='draft',confirmed=True,empty_confirmed=False,boxes=[{'id':'human'}],note='')
        self.chat=dict(source='current_user_chat',verbatim='검수 완료',training_authorized=False,
            versions={'f':1},package_sha256='package')

    def test_saved_draft_plus_explicit_current_completion(self):
        self.assertEqual(classify(self.frame,self.rev,self.chat),'accepted_person_boxes')
        self.assertEqual(self.rev['status'],'draft')

    def test_explicit_empty_is_not_absence_of_model_boxes(self):
        self.rev.update(boxes=[],confirmed=False)
        self.assertEqual(classify(self.frame,self.rev,self.chat),'held_unconfirmed_empty')
        self.rev['empty_confirmed']=True
        self.assertEqual(classify(self.frame,self.rev,self.chat),'accepted_explicit_empty')

    def test_qualified_note_overrides_checked_completeness(self):
        fid=next(iter(QUALIFIED_NOTES));self.frame['frame_id']=fid;self.rev.update(frame_id=fid,note=QUALIFIED_NOTES[fid])
        self.chat['versions']={fid:1}
        self.assertEqual(classify(self.frame,self.rev,self.chat),'held_incomplete_person_visibility')

    def test_unread_new_note_and_changed_revision_rejected(self):
        self.rev['note']='새로운 애매한 대상'
        with self.assertRaises(ValueError):classify(self.frame,self.rev,self.chat)
        self.rev.update(note='',version=2)
        with self.assertRaises(ValueError):classify(self.frame,self.rev,self.chat)

    def test_school_fn_denominator_not_development(self):
        f=dict(frame_id='f',split='school_regression',event_group='video',capture_reservation='camera',
            source_pts=1.,source_size=[100,100],image_sha256='a'*64,
            confirmed_person_boxes=[dict(id='person1',xyxy=[10,10,20,40])])
        p=dict(frame_id='f',source_pts=1.,image_sha256='a'*64,boxes=[],person_scores=[])
        result=summarize([f],[p],evaluation_split='school_regression')
        self.assertEqual(result['recovery_denominator'],1)
        self.assertNotIn('development',result['groups'])
        epoch=summarize_epoch([f],[p],evaluation_split='school_regression')
        self.assertEqual(epoch['condition_missed_gt_rows'],1)
        self.assertNotIn('recovery_denominator',epoch)

    def test_school_evaluation_does_not_change_training_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'train.json';b=Path(td)/'school.json'
            a.write_text(json.dumps({'frames':[{'split':'train','source_sha256':'train','image_sha256':'train-image'}]}))
            s=dict(purpose='protected_school_regression_only',training_eligible=False,threshold_selection_eligible=False,
                frames=[dict(split='school_regression',source_sha256='school',image_sha256='school-image',training_eligible=False)])
            b.write_text(json.dumps(s));original=a.read_bytes()
            self.assertEqual(evaluation_frames(a,b),(b,s['frames'],'school_regression'))
            self.assertEqual(a.read_bytes(),original)
            s['frames'][0]['source_sha256']='train';b.write_text(json.dumps(s))
            with self.assertRaises(ValueError):evaluation_frames(a,b)


if __name__=='__main__':unittest.main()
