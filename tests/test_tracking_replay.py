import unittest
import numpy as np
from sceneguard.byte_adapter import ByteAdapter
from sceneguard.boundary import ObservedBoundary, BoundaryTracker
from sceneguard.vendor.bytetrack import matching

CFG=dict(line=[[.5,0],[.5,1]],roi=[0,0,1,1],band=.005,dwell_seconds=.1,
         max_gap_seconds=.1,min_iou=.3,cooldown_seconds=1,score_threshold=.5)


def frame(i, score=None, box=None):
    return dict(pts=i/30, native_pts=i,time_base='1/30',source_size=[1920,1080],
                boxes=[] if score is None else [box or [400.,100.,600.,500.]],
                scores=[] if score is None else [score])


class ByteTests(unittest.TestCase):
    def test_low_cannot_start_and_new_threshold(self):
        t=ByteAdapter(True)
        self.assertEqual(t.step(frame(0,.49))[1],[])
        self.assertEqual(t.step(frame(1,.59))[1],[])
        obs,states,_=t.step(frame(2,.6))
        self.assertEqual(obs,[])
        self.assertFalse(states[0]['confirmed'])
        self.assertEqual(t.step(frame(3,.5))[0][0]['track_id'],states[0]['track_id'])

    def test_low_second_inclusive_boundaries_and_high_only_control(self):
        for use_low, count in [(False,0),(True,1)]:
            t=ByteAdapter(use_low)
            self.assertEqual(t.step(frame(0,.9))[0][0]['track_id'],1)
            obs,states,_=t.step(frame(1,.25))
            self.assertEqual(len(obs),count)
            if use_low:
                self.assertEqual(obs[0]['association'],'low_second')
                self.assertEqual(t.step(frame(2,.5))[0][0]['association'],'high')
                self.assertEqual(t.step(frame(3,.249999))[0],[])
            else:self.assertFalse(states[0]['observed'])

    def test_coordinates_measurements_not_kalman_and_empty_lifecycle(self):
        t=ByteAdapter(True)
        t.step(frame(0,.9))
        raw=[405.,100.,605.,500.]
        obs,_,_=t.step(frame(1,.9,raw))
        self.assertEqual(obs[0]['bbox'],[v/d for v,d in zip(raw,[1920,1080,1920,1080])])
        self.assertNotEqual(obs[0]['bbox'],obs[0]['filter_bbox'])
        obs,states,_=t.step(frame(2))
        self.assertFalse(obs);self.assertFalse(states[0]['observed']);self.assertIsNone(states[0]['bbox'])
        for i in range(3,33):obs,states,_=t.step(frame(i))
        self.assertEqual(states,[])

    def test_low_cannot_reactivate_lost_and_b_c_high_identical(self):
        runs=[]
        for low in [False,True]:
            t=ByteAdapter(low)
            runs.append([t.step(frame(i,s)) for i,s in enumerate([.9,.8,None,.7])])
        self.assertEqual(runs[0],runs[1])
        t=ByteAdapter(True);t.step(frame(0,.9));t.step(frame(1))
        self.assertEqual(t.step(frame(2,.3))[0],[])

    def test_lap_cost_limit_inclusive(self):
        for cost,count in [(.5,1),(.500001,0)]:
            matches,_,_=matching.linear_assignment(np.array([[cost]]),.5)
            self.assertEqual(len(matches),count)


class ExternalBoundaryTests(unittest.TestCase):
    def row(self,x,observed=True):
        return dict(track_id=87,bbox=[x-.1,.2,x+.1,.5],observed=observed,confirmed=True)

    def test_external_id_crossing_and_prediction_cannot_emit(self):
        rule=ObservedBoundary(CFG);events=[]
        for i,x in enumerate([.4]*5+[.6]*5):
            events.extend(rule.step(i/30,[self.row(x)]))
        self.assertEqual(len(events),1);self.assertEqual(events[0]['track_id'],87)
        rule=ObservedBoundary(CFG);events=[]
        for i,x in enumerate([.4]*5+[.6]*5):
            events.extend(rule.step(i/30,[self.row(x, i<5)]))
        self.assertEqual(events,[])

    def test_missing_frame_and_long_pts_gap_reset(self):
        for missing in [True,False]:
            rule=ObservedBoundary(CFG)
            for i in range(5):rule.step(i/30,[self.row(.4)])
            if missing:rule.step(5/30,[])
            times=[i/30 for i in range(6,11)] if missing else [1+i/30 for i in range(5)]
            self.assertFalse([e for t in times for e in rule.step(t,[self.row(.6)])])

    def test_original_and_external_rule_equivalence_with_observed_ids(self):
        original=BoundaryTracker(CFG);external=ObservedBoundary(CFG)
        for i,x in enumerate([.4]*5+[.6]*5):
            rows,events=original.step(i/30,[dict(bbox=[x-.2,.2,x+.2,.5],score=.9)])
            self.assertEqual(events,external.step(i/30,rows))
