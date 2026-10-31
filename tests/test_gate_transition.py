import unittest
from dataclasses import replace
import cv2
import numpy as np
from sceneguard.gate_transition import (TransitionPolicy, GateTransition, EvidenceLatch,
    cue_metrics, tracked_points, geometry, inside_polygon)

SIZE = (200, 200)
LINE = [[.2, .5], [.8, .5]]
SCENE = dict(source_size=list(SIZE), line=LINE,
             approach_polygon=[[.05,.05],[.95,.05],[.95,.95],[.05,.95]],
             directions=['outside_to_inside','inside_to_outside'])

def cue(p,q, **kwargs):
    return cue_metrics(np.asarray(p,float),np.asarray(q,float),
                       line=LINE,size=SIZE,height=80.,**kwargs)

def cloud(y=112):
    return np.array([[x,y+dy] for x in (70,85,100,115,130) for dy in (0,2)],float)

def boxrow(tid=1, box=(.28,.30,.70,.80), score=.9, index=0):
    return dict(bbox=list(box), score=score, track_ids=[tid], cache_index=index)

class Cues(unittest.TestCase):
    def test_stationary(self):
        p=cloud(); self.assertEqual(cue(p,p)['score'],0)
    def test_parallel_walking(self):
        p=cloud(); self.assertEqual(cue(p,p+[8,0])['score'],0)
    def test_rigid_approach_is_not_sufficient(self):
        p=cloud(125); self.assertLess(cue(p,p+[0,-8])['score'],.55)
    def test_visible_crossing(self):
        p=cloud(107); self.assertGreater(cue(p,p+[0,-16])['score'],.55)
    def test_reverse_direction(self):
        p=cloud(91); self.assertGreater(cue(p,p+[0,16])['score'],.55)
    def test_no_infinite_line_crossing(self):
        p=cloud(107)+[150,0]; self.assertEqual(cue(p,p+[0,-16])['crossing_fraction'],0)
    def test_partial_points(self):
        p=cloud(107)[:3]; self.assertGreater(cue(p,p+[0,-16])['score'],.55)
    def test_local_change_while_still_visible(self):
        p=cloud(96); q=p.copy(); q[:4,1]-=18
        r=cue(p,q); self.assertEqual(r['crossing_fraction'],0); self.assertGreater(r['score'],.55)
    def test_small_jitter(self):
        p=cloud(100); q=p.copy(); q[::2,1]-=1
        self.assertLess(cue(p,q)['score'],.55)
    def test_far_from_gate_change(self):
        p=cloud(20); q=p.copy(); q[:4,1]-=18
        self.assertEqual(cue(p,q)['score'],0)
    def test_bad_correspondences(self):
        with self.assertRaises(ValueError): cue(cloud(),cloud()[:3])
    def test_not_enough_points(self):
        with self.assertRaises(ValueError): cue(cloud()[:2],cloud()[:2])
    def test_nan(self):
        p=cloud(); p[0,0]=np.nan
        with self.assertRaises(ValueError): cue(p,p)
    def test_degenerate_line(self):
        with self.assertRaises(ValueError): geometry([[.2,.2],[.2,.2]],SIZE)
    def test_polygon_edge(self):
        self.assertTrue(inside_polygon((.05,.2),SCENE['approach_polygon']))
    def test_policy(self):
        for k,v in [('score_threshold',2),('max_windows',2.5),('min_points',2),('window_seconds',.2)]:
            with self.subTest(k=k), self.assertRaises(ValueError): replace(TransitionPolicy(),**{k:v}).validate()

class Latch(unittest.TestCase):
    def test_three_samples_not_single_frame(self):
        s=EvidenceLatch(); self.assertFalse(s.push(0,.8)); self.assertFalse(s.push(.05,.8))
        self.assertTrue(s.push(.10,.8))
    def test_low_intermediate_frame_allowed(self):
        s=EvidenceLatch(); out=[s.push(t,x) for t,x in [(0,.8),(.05,.8),(.10,.1),(.15,.8)]]
        self.assertTrue(out[-1])
    def test_source_gap_not_counted(self):
        s=EvidenceLatch(); s.push(0,.8); s.push(.05,.8)
        self.assertFalse(s.push(1,.8))
    def test_cooldown(self):
        s=EvidenceLatch(); emitted=[s.push(i*.05,.8) for i in range(15)]
        self.assertEqual(sum(emitted),1)
    def test_waiting_does_not_disable_later_candidate(self):
        s=EvidenceLatch(); out=[s.push(i*.05, 0 if i<10 else .8) for i in range(18)]
        self.assertTrue(any(out[10:])); self.assertFalse(any(out[:10]))
    def test_no_future_snapshot(self):
        values=[(i*.05,0 if i<10 else .8) for i in range(20)]
        s=EvidenceLatch(); full=[s.push(t,x) for t,x in values]
        for n in range(1,len(values)+1):
            p=EvidenceLatch(); self.assertEqual(full[:n],[p.push(t,x) for t,x in values[:n]])
    def test_wrong_time(self):
        s=EvidenceLatch(); s.push(1,0)
        with self.assertRaises(ValueError): s.push(1,.8)

class ImagePath(unittest.TestCase):
    def setUp(self):
        self.image=np.zeros((200,200),np.uint8)
        rng=np.random.default_rng(10)
        self.image[55:145,55:145]=rng.integers(0,255,(90,90),np.uint8)
    def test_actual_lk_translation(self):
        pts=cv2.goodFeaturesToTrack(self.image,48,.02,3).reshape(-1,2)
        moved=cv2.warpAffine(self.image,np.float32([[1,0,2],[0,1,-3]]),(200,200))
        q,good=tracked_points(self.image,moved,pts,TransitionPolicy())
        self.assertGreater(int(good.sum()),10)
        np.testing.assert_allclose(np.median(q[good]-pts[good],axis=0),[2,-3],atol=.2)
    def test_visible_moving_target_emits_before_any_loss(self):
        rng=np.random.default_rng(9)
        bg=rng.integers(0,45,(200,200),np.uint8)
        patch=rng.integers(70,255,(42,54),np.uint8)
        engine=GateTransition(SCENE); out=[]
        for i in range(32):
            y=110-i; frame=bg.copy(); frame[y:y+42,70:124]=patch
            d=boxrow(box=(.35,y/200,.62,(y+42)/200))
            r=engine.step(frame,i/30,[d],i)
            if r['event']: out.append(r['event'])
        self.assertGreater(len(out),0)
        self.assertTrue(all(e['decision_time_pts']<31/30 for e in out))
    def test_target_continues_after_id_is_absent(self):
        rng=np.random.default_rng(9)
        bg=rng.integers(0,45,(200,200),np.uint8)
        patch=rng.integers(70,255,(42,54),np.uint8)
        engine=GateTransition(SCENE); events=[]
        for i in range(32):
            y=110-i; frame=bg.copy(); frame[y:y+42,70:124]=patch
            d=boxrow(box=(.35,y/200,.62,(y+42)/200))
            r=engine.step(frame,i/30,[d] if i<8 else [],i)
            if r['event']: events.append(r['event'])
        self.assertGreater(len(events),0)
    def test_camera_translation_not_target_transition(self):
        rng=np.random.default_rng(7); original=rng.integers(0,255,(200,200),np.uint8)
        engine=GateTransition(SCENE)
        for i in range(20):
            frame=cv2.warpAffine(original,np.float32([[1,0,0],[0,1,-i]]),(200,200))
            r=engine.step(frame,i/30,[boxrow(box=(.3,.5-i/200,.6,.75-i/200))],i)
            self.assertIsNone(r['event'])
    def test_empty_flow(self):
        q,g=tracked_points(self.image,self.image,np.empty((0,2)),TransitionPolicy())
        self.assertEqual(len(q),0); self.assertEqual(len(g),0)
    def test_static_images_no_candidates_even_with_id_switch(self):
        engine=GateTransition(SCENE); events=[]
        for i in range(30):
            result=engine.step(self.image,i/30,[boxrow(1 if i<10 else 9)],i)
            if result['event']: events.append(result['event'])
        self.assertEqual(events,[]); self.assertGreater(engine.serial,0)
    def test_overlaps_do_not_erase_seed(self):
        engine=GateTransition(SCENE)
        r=engine.step(self.image,0,[boxrow(),boxrow(8,index=1)],0)
        self.assertEqual(r['seeded'],2)
    def test_prediction_not_seeded(self):
        engine=GateTransition(SCENE)
        r=engine.step(self.image,0,[dict(bbox=None,observed=False,state='lost_prediction')],0)
        self.assertEqual(r['windows'],0)
    def test_box_resize_without_image_change_does_not_trigger(self):
        engine=GateTransition(SCENE)
        for i in range(24):
            b=(.28,.30,.70,.80) if i<10 else (.35,.38,.55,.58)
            self.assertIsNone(engine.step(self.image,i/30,[boxrow(box=b)],i)['event'])
    def test_no_detection_does_not_emit_loss(self):
        engine=GateTransition(SCENE)
        for i in range(25):
            r=engine.step(self.image,i/30,[boxrow()] if i<5 else [],i)
            self.assertIsNone(r['event'])
    def test_cap_and_non_increasing_index(self):
        engine=GateTransition(SCENE,replace(TransitionPolicy(),max_windows=1))
        self.assertEqual(engine.step(self.image,0,[boxrow(),boxrow(8,index=1)],0)['windows'],1)
        with self.assertRaises(ValueError): engine.step(self.image,.03,[],0)
    def test_gap_resets_and_does_not_generate(self):
        engine=GateTransition(SCENE); engine.step(self.image,0,[boxrow()],0)
        r=engine.step(self.image,1,[],30)
        self.assertTrue(r['source_gap']); self.assertEqual(r['windows'],0); self.assertIsNone(r['event'])
    def test_input_shape(self):
        with self.assertRaises(ValueError): GateTransition(SCENE).step(self.image[:10],0,[],0)
    def test_input_nan_score(self):
        with self.assertRaises(ValueError): GateTransition(SCENE).step(self.image,0,[boxrow(score=float('nan'))],0)
    def test_unidirectional_not_silently_ignored(self):
        with self.assertRaises(ValueError): GateTransition(dict(SCENE,directions=['outside_to_inside']))

if __name__=='__main__': unittest.main()
