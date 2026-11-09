import unittest
from pathlib import Path
import tempfile
from scripts.evaluate_exp0074_baseline import summarize
from scripts.evaluate_exp0074_checkpoint import development_subset, verify_receipt, summarize_epoch
from scripts.evaluate_person_detector_pair import sha


class BaselineTests(unittest.TestCase):
    def frame(self, fid, boxes):
        return dict(frame_id=fid,split='development',event_group='capture-01',capture_reservation='capture-01',
                    source_pts=1.,source_size=[1920,1080],image_sha256='a'*64,
                    confirmed_person_boxes=[dict(id=fid+':'+str(i),xyxy=b) for i,b in enumerate(boxes)])

    def pred(self, fid, boxes, scores):
        return dict(frame_id=fid,image_sha256='a'*64,source_pts=1.,boxes=boxes,person_scores=scores)

    def test_empty_frame_false_positive_not_true_negative_person(self):
        result=summarize([self.frame('empty',[])],[self.pred('empty',[[1,2,10,20]],[.8])])
        self.assertEqual(result['groups']['development']['fp'],1)
        self.assertIsNone(result['groups']['development']['recall'])
        self.assertEqual(result['conditions']['development']['explicit_empty']['false_positive_frames'],1)

    def test_duplicates_do_not_recover_other_person(self):
        boxes=[[1,2,70,90],[500,500,600,650]]
        result=summarize([self.frame('f',boxes)],[self.pred('f',[boxes[0],boxes[0]],[.9,.8])])
        self.assertEqual([result['groups']['development'][k] for k in ('tp','fp','fn')],[1,1,1])
        self.assertEqual(result['recovery_denominator'],1)
        self.assertEqual([p['baseline_detected'] for p in result['people']],[True,False])
        self.assertIsNone(result['future_recovered'])

    def test_missing_or_changed_frame_fails_closed(self):
        frame=self.frame('f',[])
        with self.assertRaises(ValueError):summarize([frame],[])
        pred=self.pred('f',[],[]);pred['source_pts']=2.
        with self.assertRaises(ValueError):summarize([frame],[pred])

    def test_development_export_keeps_exact_identity(self):
        dev=self.frame('dev',[]);train=self.frame('train',[]);train['split']='train'
        rows=[self.pred('dev',[],[]),self.pred('train',[],[])]
        self.assertEqual(development_subset({'frames':[train,dev]},rows),[rows[0]])
        with self.assertRaises(ValueError):development_subset({'frames':[dev]},[rows[0],rows[0]])

    def test_future_miss_is_not_baseline_recovery_denominator(self):
        box=[10,10,100,200];frame=self.frame('f',[box])
        a=summarize([frame],[self.pred('f',[box],[.8])])
        b=summarize_epoch([frame],[self.pred('f',[],[])])
        self.assertEqual(a['recovery_denominator'],0)
        self.assertEqual(b['condition_missed_gt_rows'],1)
        self.assertNotIn('recovery_denominator',b)
        self.assertNotIn('baseline_detected',b['people'][0])
        self.assertFalse(b['people'][0]['detected'])

    def test_future_checkpoint_requires_real_exact_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            cp=Path(td)/'epoch.pt';cp.write_bytes(b'fixture-not-a-model')
            manifest=Path(td)/'manifest.json';manifest.write_text('{}')
            receipt=dict(evidence_kind='actual_training_checkpoint',checkpoint={'path':str(cp.resolve()),'sha256':sha(cp)},
                provenance={'manifest':{'path':str(manifest.resolve()),'sha256':sha(manifest)},'variant':'C'},epoch=1)
            verify_receipt(receipt,cp,manifest)
            receipt['evidence_kind']='synthetic_checkpoint_simulation'
            with self.assertRaises(ValueError):verify_receipt(receipt,cp,manifest)
            receipt['evidence_kind']='actual_training_checkpoint';cp.write_bytes(b'changed')
            with self.assertRaises(ValueError):verify_receipt(receipt,cp,manifest)


if __name__=='__main__': unittest.main()
