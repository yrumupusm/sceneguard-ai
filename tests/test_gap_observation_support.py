import copy
import unittest

from sceneguard.gap_observation_support import (FlowPolicy,ShortImageFlow,audit_loss,box,
    catalog_frame,flow_crop,select_seed)


def frame(pts=0.,boxes=None,scores=None):
    boxes=[[60.,50.,120.,130.]] if boxes is None else boxes
    scores=[.8]*len(boxes) if scores is None else scores
    c=dict(pts=pts,native_pts=round(pts*3000),time_base='1/3000',source_size=[300,200],boxes=boxes,scores=scores)
    t=dict(pts=pts,native_pts=c['native_pts'],time_base=c['time_base'],detections=[],states=[],unmatched=[])
    return c,t


def row(index=0,tid=1,observed=True,confirmed=True,bbox=None):
    return dict(cache_index=index,track_id=tid,observed=observed,confirmed=confirmed,
                bbox=bbox or [.2,.25,.4,.65],score=.8)


class CacheAuditTests(unittest.TestCase):
    def test_duplicate_state_and_observation_count_once(self):
        c,t=frame();t['detections']=[row()];t['states']=[row()]
        result=catalog_frame(c,t)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['track_ids'],[1])

    def test_prediction_does_not_become_measurement(self):
        c,t=frame(boxes=[]);t['states']=[dict(observed=False,bbox=None,prediction_bbox=[.2,.2,.4,.5])]
        self.assertEqual(catalog_frame(c,t),[])

    def test_unmatched_and_unconfirmed_are_kept(self):
        c,t=frame();t['unmatched']=[dict(cache_index=0,bbox=[.2,.25,.4,.65],score=.8)]
        self.assertEqual(catalog_frame(c,t)[0]['assignment'],'unmatched_detection')
        t['unmatched']=[];t['states']=[row(confirmed=False)]
        self.assertEqual(catalog_frame(c,t)[0]['assignment'],'unconfirmed_track')

    def test_weak_cache_box_not_silently_discarded(self):
        c,t=frame(scores=[.22])
        self.assertEqual(catalog_frame(c,t)[0]['assignment'],'cached_below_tracker_floor')

    def test_wrong_pts_rejected(self):
        c,t=frame();t['native_pts']=1
        with self.assertRaises(ValueError):catalog_frame(c,t)

    def test_wrong_measured_box_rejected(self):
        c,t=frame();t['detections']=[row(bbox=[.1,.2,.4,.6])]
        with self.assertRaises(ValueError):catalog_frame(c,t)

    def test_conflicting_assignment_rejected(self):
        c,t=frame();t['detections']=[row()];t['states']=[row(tid=2)]
        with self.assertRaises(ValueError):catalog_frame(c,t)

    def test_empty_box_rejected(self):
        with self.assertRaises(ValueError):box([0,0,0,1])

    def test_loss_audit_excludes_future_and_keeps_alarm(self):
        pairs=[frame(i/30) for i in range(4)]
        pairs[1][1]['states']=[row(tid=2)]
        pairs[2][1]['unmatched']=[dict(cache_index=0,bbox=[.2,.25,.4,.65],score=.8)]
        # Future invalid data must not enter the original decision's evidence.
        pairs[3][1]['detections']=[row(bbox=[.1,.1,.3,.3])]
        segment=dict(id='s1',raw_id=1,rows=[dict(pts=0.,bbox=[.2,.25,.4,.65],frame_index=0)])
        event=dict(segment='s1',raw_id=1,status='침입 의심',decision_time_pts=2/30,last_observed_pts=0.)
        saved=copy.deepcopy(pairs)
        result=audit_loss(event,segment,[p[0] for p in pairs],[p[1] for p in pairs])
        self.assertEqual(result['counts'],{'other_confirmed_detection_nearby':1,'unconfirmed_or_unmatched_detection_nearby':1})
        self.assertFalse(result['cancel_alarm']);self.assertEqual(pairs,saved)

    def test_outside_candidate_is_not_counted(self):
        pairs=[frame(0),frame(1/30,boxes=[[230,150,250,170]])]
        segment=dict(id='s1',raw_id=1,rows=[dict(pts=0.,bbox=[.2,.25,.4,.65],frame_index=0)])
        event=dict(segment='s1',raw_id=1,status='침입 의심',decision_time_pts=1/30,last_observed_pts=0.)
        r=audit_loss(event,segment,[p[0] for p in pairs],[p[1] for p in pairs])
        self.assertEqual(r['counts'],{'no_local_box_in_saved_cache':1})

    def test_missing_decision_frame_rejected(self):
        c,t=frame(0)
        s=dict(id='s',raw_id=1,rows=[dict(pts=0.,bbox=[.2,.25,.4,.65])])
        e=dict(segment='s',raw_id=1,status='침입 의심',last_observed_pts=0.,decision_time_pts=1.)
        with self.assertRaises(ValueError):audit_loss(e,s,[c],[t])

    def test_seed_and_crop_are_real_and_bounded(self):
        rows=[dict(pts=i/10,frame_index=i,bbox=[.2,.25,.4,.65],cache_index=0) for i in range(11)]
        self.assertAlmostEqual(select_seed({'rows':rows})['pts'],.6)
        self.assertIsNone(select_seed({'rows':[rows[-1]]}))
        self.assertEqual(flow_crop([0,0,.1,.1],[.9,.9,1,1],[300,200]),[0,0,300,200])

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):FlowPolicy(minimum_survival=2).validate()


class RealOpticalFlowTests(unittest.TestCase):
    def setUp(self):
        import cv2
        import numpy as np
        self.np=np;self.cv=cv2
        rng=np.random.default_rng(3)
        self.background=rng.integers(0,100,(200,300),dtype=np.uint8)
        self.texture=rng.integers(100,255,(80,60),dtype=np.uint8)
        self.seed=dict(pts=0.,frame_index=0,bbox=[.2,.25,.4,.65],cache_index=0)
        self.candidates=[dict(cache_index=0,score=.8,bbox=self.seed['bbox'],track_ids=[1],assignment='confirmed_track')]

    def image(self,shift=0):
        image=self.background.copy();image[50:130,60+shift:120+shift]=self.texture
        return image

    def moving(self):
        flow=ShortImageFlow(self.image(),self.seed,[300,200],(0,0),self.candidates)
        for i in range(1,9):flow.update(self.image(i*2),i/30,i)
        end=[dict(self.candidates[0],bbox=[76/300,.25,136/300,.65],track_ids=[2])]
        return flow,end

    def test_actual_pixel_translation_tracks_and_remains_support_only(self):
        flow,end=self.moving();result=flow.summary(4/30,end)
        self.assertEqual(result['outcome'],'image_continuation_supported_review_only')
        self.assertFalse(result['cancel_alarm'])
        self.assertFalse(result['identity_verified'])
        self.assertGreater(result['endpoint_points'],5)
        self.assertAlmostEqual(flow.records[-1]['relative_displacement'][0],16,delta=1)

    def test_static_gate_features_not_accepted_as_motion(self):
        flow=ShortImageFlow(self.image(),self.seed,[300,200],(0,0),self.candidates)
        for i in range(1,9):flow.update(self.image(),i/30,i)
        self.assertEqual(flow.summary(4/30,self.candidates)['outcome'],'static_or_background_ambiguous')

    def test_global_camera_shift_not_target_motion(self):
        image=self.image()
        flow=ShortImageFlow(image,self.seed,[300,200],(0,0),self.candidates)
        for i in range(1,5):
            shifted=self.cv.warpAffine(image,self.np.float32([[1,0,i],[0,1,0]]),(300,200))
            flow.update(shifted,i/30,i)
        self.assertEqual(flow.summary(3/30,self.candidates)['outcome'],'static_or_background_ambiguous')

    def test_missing_features_not_intrusion_or_negative(self):
        blank=self.np.zeros((200,300),dtype=self.np.uint8)
        flow=ShortImageFlow(blank,self.seed,[300,200],(0,0),self.candidates)
        flow.update(blank,1/30,1)
        r=flow.summary(0,[])
        self.assertEqual(r['outcome'],'insufficient_seed_features');self.assertFalse(r['cancel_alarm'])

    def test_temporal_gap_stops_points_and_does_not_reseed(self):
        flow,end=self.moving();flow.update(self.image(16),1.,30)
        flow.update(self.image(16),1+1/30,31)
        self.assertEqual(flow.summary(4/30,end)['outcome'],'source_gap_flow_not_used')
        self.assertEqual(len(flow.p),0)

    def test_multiple_endpoint_targets_remain_ambiguous(self):
        flow,end=self.moving();end.append(dict(end[0],cache_index=1,track_ids=[3]))
        self.assertEqual(flow.summary(4/30,end)['outcome'],'overlap_or_multiple_targets_ambiguous')

    def test_no_detector_confirmation_does_not_mean_target_absent(self):
        flow,_=self.moving()
        self.assertEqual(flow.summary(4/30,[])['outcome'],'feature_path_without_detector_confirmation')

    def test_shape_change_rejected(self):
        flow,_=self.moving()
        with self.assertRaises(ValueError):flow.update(self.image()[:100],.3,9)

    def test_nonmonotonic_time_rejected(self):
        flow,_=self.moving()
        with self.assertRaises(ValueError):flow.update(self.image(),0.,0)


if __name__=='__main__':unittest.main()
