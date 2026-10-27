import unittest
from copy import deepcopy
from sceneguard.candidate_review import CandidateReview, change


def event(t=.2):
    return dict(emitted_at_pts=t,track_id=1,direction='positive_to_negative',candidate_pts=t-.05)


def obs(box=(.1,.1,.2,.3),observed=True):
    return [dict(track_id=1,bbox=list(box),observed=observed,confirmed=True)]


class ReviewTests(unittest.TestCase):
    def execute(self, boxes, missing=(), end=12):
        r=CandidateReview();updates=[]
        for i in range(end+1):
            updates+=r.step(i/30,[] if i in missing else obs(boxes(i)),[event()] if i==6 else [])
        updates+=r.finish()
        return updates

    def test_box_jump(self):
        v=self.execute(lambda i:(.1,.1,.2,.3 if i<8 else .6))[-1]
        self.assertEqual(v['status'],'deferred');self.assertTrue(v['anomaly_detected'])
        self.assertAlmostEqual(v['decision_pts'],.4)

    def test_stable_translation(self):
        v=self.execute(lambda i:(.1,.1+i*.005,.2,.3+i*.005))[-1]
        self.assertEqual(v['status'],'passed')

    def test_mixed_motion_and_scope(self):
        v=self.execute(lambda i:(.1,.1+i*.005,.2,(.3 if i<8 else .6)+i*.005))[-1]
        self.assertEqual(v['status'],'deferred')

    def test_gap_takes_priority_over_anomaly(self):
        v=self.execute(lambda i:(.1,.1,.2,.3 if i<8 else .6),missing=(11,))[-1]
        self.assertEqual(v['status'],'insufficient');self.assertTrue(v['anomaly_detected'])

    def test_eof(self):
        v=self.execute(lambda i:(.1,.1,.2,.3),end=9)[-1]
        self.assertIn('end_before_deadline',v['reasons']);self.assertEqual(v['decision_pts'],.3)

    def test_no_future_or_early_decision(self):
        r=CandidateReview()
        for i in range(12):
            v=r.step(i/30,obs(),[event()] if i==6 else [])
            self.assertTrue(all(x['status']=='pending' for x in v))
        final=r.step(.4,obs(),[])[0];saved=deepcopy(final)
        r.step(13/30,obs((.1,.1,.8,.9)),[])
        self.assertEqual(final,saved);self.assertEqual(final['status'],'passed')
        self.assertLessEqual(final['last_observation_pts'],final['decision_pts'])
        with self.assertRaises(ValueError):CandidateReview().step(0,obs(),[event()])

    def test_predictions_not_observations(self):
        r=CandidateReview();out=[]
        for i in range(13):out+=r.step(i/30,obs(observed=i!=8),[event()] if i==6 else [])
        self.assertEqual(out[-1]['status'],'insufficient')

    def test_disabled_identity_and_no_mutation(self):
        r=CandidateReview(False);e=[event(0)];o=obs();before=deepcopy((e,o))
        self.assertEqual(r.step(0,o,e),e);self.assertEqual((e,o),before)

    def test_stable_partial_box_passes(self):
        self.assertEqual(self.execute(lambda i:(.1,.1,.2,.15))[-1]['status'],'passed')

    def test_width_and_threshold(self):
        self.assertEqual(self.execute(lambda i:(0,0,.2 if i<8 else .4,.2))[-1]['status'],'deferred')
        self.assertEqual(change([0,0,1,2],[0,0,1,3])['height_ratio'],1.5)

    def test_pts_gap_and_missing_past(self):
        r=CandidateReview();r.step(0,obs(),[]);r.step(.2,obs(),[event()])
        v=r.step(.4,obs(),[])[0];self.assertIn('pts_gap',v['reasons'])
        r=CandidateReview();r.step(.2,obs(),[event()]);v=r.finish()[0]
        self.assertIn('missing_lookback',v['reasons'])


if __name__=='__main__':unittest.main()
