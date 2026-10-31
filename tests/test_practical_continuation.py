"""Synthetic behavior checks; not CCTV accuracy or end-to-end integration."""
from copy import deepcopy
import unittest
import cv2
import numpy as np
from sceneguard.practical_continuation import (
    PracticalPolicy, pixels, seed_pool, corners, choose_seeds, trace, assess,
    evidence_score, notification_partition)

SIZE=(200,160)
BOX=[.2,.2,.6,.8]


def candidate(box=BOX, index=2, tid=20, score=.8):
    return dict(bbox=list(box),cache_index=index,track_ids=[tid],score=score)


def seed(i=0, box=BOX):
    return dict(frame_index=i,pts=i/30,bbox=list(box),cache_index=0)


def image():
    rng=np.random.default_rng(40)
    return cv2.GaussianBlur(rng.integers(0,256,(160,200),dtype=np.uint8),(3,3),0)


def path(points, anchors=None, quality=None, initial=60):
    p=np.asarray(points,dtype=np.float32).reshape(-1,2); ids=np.arange(len(p))
    return dict(points=p,anchors=p.copy() if anchors is None else np.asarray(anchors,dtype=float),
        ids=ids,patch_quality=np.ones(len(p)) if quality is None else np.asarray(quality),
        source_membership=np.ones(len(p)), initial_points=initial,
        records=[dict(frame_index=i,pts=.9+i/30,ids=ids.tolist(),points=p.tolist()) for i in range(4)])


def event(i,raw=1, reason='recent_gate_presence_then_loss',at=2.,collection='events'):
    return dict(event_id=f'e{i}',decision_time_pts=at,status='침입 의심',track_ids=[raw],
        source_ref=dict(collection=collection,source_pointer=f'/{collection}/{i}',raw_id=raw),
        source_event=dict(reason=reason))


def audit(i=0, raw=1, at=2.):
    return dict(source_pointer=f'/events/{i}',raw_id=raw,evidence_until_pts=at,recommendation='review_only')


class GeometryTests(unittest.TestCase):
    def test_policy_defaults(self):
        self.assertEqual(PracticalPolicy().validate().min_points,3)
    def test_bad_threshold(self):
        with self.assertRaises(ValueError): PracticalPolicy(score_threshold=2).validate()
    def test_bad_count(self):
        with self.assertRaises(ValueError): PracticalPolicy(min_points=1.5).validate()
    def test_bad_bbox(self):
        with self.assertRaises(ValueError): pixels([.7,.2,.2,.5],SIZE)
    def test_pixel_coordinates(self):
        np.testing.assert_allclose(pixels(BOX,SIZE),[40,32,120,128])
    def test_seed_pool_looks_back_three_seconds(self):
        rows=[seed(i) for i in range(121)]
        pool=seed_pool(rows,PracticalPolicy())
        self.assertGreaterEqual(pool[0]['pts'],1.)
        self.assertLess(pool[0]['pts'],1.5)
        self.assertTrue(all(.1<=4-r['pts']<=3+1e-9 for r in pool))
    def test_fully_overlapped_box_still_has_points(self):
        pts=corners(image(),seed(),[candidate(index=0),candidate(index=1)],SIZE,PracticalPolicy())
        self.assertGreater(len(pts),10)
    def test_featureless_image(self):
        pts=corners(np.zeros((160,200),np.uint8),seed(),[],SIZE,PracticalPolicy())
        self.assertEqual(len(pts),0)
    def test_visual_seed_selection_finds_earlier_texture(self):
        rows=[seed(i) for i in range(91)]
        pool=seed_pool(rows,PracticalPolicy())
        g={r['frame_index']:image() if r['pts']<1.5 else np.zeros((160,200),np.uint8) for r in pool}
        c={k:[candidate(index=0),candidate(index=1)] for k in g}
        selected=choose_seeds(rows,g,c,SIZE,PracticalPolicy())
        self.assertLess(selected[0][1]['pts'],1.5)
        self.assertGreater(len(selected[0][2]),3)


class ImageFlowTests(unittest.TestCase):
    def run_flow(self,dx=0):
        im=image(); grays={i:cv2.warpAffine(im,np.float32([[1,0,dx*i],[0,1,0]]),SIZE)
                          for i in range(16)}
        rows=[seed(i, [.2+dx*i/200,.2,.6+dx*i/200,.8]) for i in range(6)]
        points=corners(im,rows[0],[],SIZE,PracticalPolicy())
        return trace(grays,{i:i/30 for i in grays},rows[0],points,rows,SIZE,PracticalPolicy()),grays
    def test_static_target_keeps_points(self):
        p,_=self.run_flow()
        self.assertGreaterEqual(len(p['points']),20)
        self.assertGreater(float(np.median(p['patch_quality'])),.99)
    def test_translation_follows_actual_pixels(self):
        p,_=self.run_flow(1)
        self.assertGreater(len(p['points']),10)
        np.testing.assert_allclose(np.median(p['points']-p['anchors'],axis=0),[10,0],atol=.2)
    def test_gap_does_not_extrapolate(self):
        im=image(); pts=corners(im,seed(),[],SIZE,PracticalPolicy())
        p=trace({0:im,1:im},{0:0.,1:.2},seed(),pts,[seed()],SIZE,PracticalPolicy())
        self.assertEqual(len(p['points']),0)
    def test_invalid_frame_order(self):
        im=image(); pts=corners(im,seed(),[],SIZE,PracticalPolicy())
        with self.assertRaises(ValueError):
            trace({0:im,1:im},{0:0.,1:0.},seed(),pts,[seed()],SIZE,PracticalPolicy())
    def test_point_ids_are_not_reused(self):
        p,_=self.run_flow(3)
        records=p['records']
        self.assertTrue(all(set(b['ids'])<=set(a['ids']) for a,b in zip(records,records[1:])))


class DecisionTests(unittest.TestCase):
    def decision(self,p,cs=None,line=None):
        c=cs if cs is not None else [candidate()]
        return assess(p,{i:c for i in range(4)},SIZE,line,.8,1.,PracticalPolicy())
    def test_partial_survival_can_change_notification(self):
        p=path([[60,50],[65,60],[75,70],[80,80]],initial=60)
        self.assertEqual(self.decision(p)['recommendation'],'review_only')
    def test_static_overlap_no_blanket_veto(self):
        p=path([[60,50],[65,60],[75,70],[80,80]])
        self.assertGreater(self.decision(p)['score'],.70)
    def test_duplicate_boxes_not_distinct_people(self):
        p=path([[60,50],[65,60],[75,70],[80,80]])
        self.assertEqual(self.decision(p,[candidate(),candidate(index=3)])['recommendation'],'review_only')
    def test_background_points_without_person_box_keep_alarm(self):
        p=path([[10,10],[12,14],[15,10],[18,12]])
        self.assertEqual(self.decision(p)['recommendation'],'keep')
    def test_patch_mismatch_keeps_alarm(self):
        p=path([[60,50],[65,60],[75,70],[80,80]],quality=[0,0,0,0])
        self.assertEqual(self.decision(p)['recommendation'],'keep')
    def test_visibly_crossed_line_is_not_same_side_continuation(self):
        p=path([[110,50],[112,60],[115,70],[118,80]],anchors=[[80,50],[82,60],[85,70],[88,80]])
        self.assertEqual(self.decision(p,line=[[.5,0],[.5,1]])['recommendation'],'keep')
    def test_two_separate_people_not_resolved_by_nearby_boxes(self):
        p=path([[50,50],[55,60],[60,70],[65,80],[140,50],[145,60],[150,70],[155,80]])
        cs=[candidate([.20,.2,.4,.8]),candidate([.65,.2,.85,.8],index=3,tid=30)]
        self.assertEqual(self.decision(p,cs)['recommendation'],'keep')
    def test_too_few_points_keep(self):
        self.assertEqual(self.decision(path([[60,50],[65,60]]))['recommendation'],'keep')
    def test_support_score_is_not_a_probability(self):
        self.assertIsNone(self.decision(path([[60,50],[65,60],[75,70]]))['probability'])


class NotificationTests(unittest.TestCase):
    def test_changes_only_eligible_loss(self):
        ev=[event(0),event(1,raw=2)]
        active,review=notification_partition(ev,[audit()])
        self.assertEqual([x['event_id'] for x in active],['e1'])
        self.assertEqual([x['event_id'] for x in review],['e0'])
    def test_original_bytes_unchanged(self):
        ev=[event(0),event(1)]; old=deepcopy(ev)
        active,review=notification_partition(ev,[audit()])
        active[0]['track_ids'].append(99);review[0]['source_event']['reason']='changed'
        self.assertEqual(ev,old)
    def test_independent_boundary_evidence_preserved(self):
        ev=[event(0),event(1,reason='crossing',at=1.5,collection='existing_alerts')]
        active,review=notification_partition(ev,[audit()])
        self.assertEqual(len(active),2);self.assertEqual(review,[])
    def test_other_person_alarm_not_canceled(self):
        ev=[event(0),event(1,raw=2,reason='crossing',collection='existing_alerts')]
        active,review=notification_partition(ev,[audit()])
        self.assertEqual(len(active),1);self.assertEqual(active[0]['track_ids'],[2])
    def test_future_independent_alarm_cannot_rewrite_past(self):
        ev=[event(0),event(1,reason='crossing',at=3,collection='existing_alerts')]
        self.assertEqual(len(notification_partition(ev,[audit()])[1]),1)
    def test_future_image_evidence_refused(self):
        with self.assertRaises(ValueError):notification_partition([event(0)],[audit(at=2.1)])
    def test_wrong_target_refused(self):
        with self.assertRaises(ValueError):notification_partition([event(0)],[audit(raw=9)])
    def test_unresolved_support_does_not_block_original_suspicion(self):
        a=audit();a['recommendation']='keep'
        self.assertEqual(len(notification_partition([event(0)],[a])[0]),1)


if __name__=='__main__':unittest.main()
