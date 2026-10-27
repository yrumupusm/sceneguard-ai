import unittest
from sceneguard.boundary import BoundaryTracker, finite_crossing, iou

CFG = dict(line=[[.5,.2],[.5,.8]], roi=[0,0,1,1], band=.01,
           dwell_seconds=.06, max_gap_seconds=.11, min_iou=.1, cooldown_seconds=.5)


def det(x, y=.5):
    return {'bbox':[x-.15,y-.25,x+.15,y], 'score':.9}


class BoundaryTests(unittest.TestCase):
    def run_sequence(self, points, times=None, config=None):
        tracker=BoundaryTracker(config or CFG); events=[]
        for i,p in enumerate(points):
            _, e=tracker.step(times[i] if times else i*.04, [] if p is None else [det(*p)])
            events.extend(e)
        return tracker,events

    def test_forward_dwell_interval_and_delay(self):
        _,e=self.run_sequence([(.4,.5)]*3+[(.6,.5)]*3)
        self.assertEqual(len(e),1)
        self.assertEqual(e[0]['direction'],'positive_to_negative')
        self.assertEqual(e[0]['candidate_interval'],[.08,.12])
        self.assertEqual(e[0]['emitted_at_pts'],.2)
        self.assertEqual(e[0]['physical_climb_completion'],'unknown')

    def test_reverse_and_duplicate_stability(self):
        _,e=self.run_sequence([(.4,.5)]*3+[(.6,.5)]*8+[(.4,.5)]*3)
        self.assertEqual([r['direction'] for r in e],['positive_to_negative','negative_to_positive'])

    def test_parallel_and_touch_without_crossing(self):
        for points in [[(.4,.4),(.4,.45),(.4,.5),(.4,.55)],
                       [(.4,.5)]*3+[(.5,.5)]*4+[(.4,.5)]*3]:
            self.assertEqual(self.run_sequence(points)[1],[])

    def test_first_appearance_on_one_side_not_event(self):
        self.assertEqual(self.run_sequence([(.6,.5)]*10)[1],[])

    def test_both_sides_must_dwell(self):
        self.assertEqual(self.run_sequence([(.4,.5)]+[(.6,.5)]*3)[1],[])
        self.assertEqual(self.run_sequence([(.4,.5)]*3+[(.6,.5)]*2)[1],[])

    def test_finite_line_and_roi(self):
        self.assertFalse(finite_crossing((.4,.9),(.6,.9),(.5,.2),(.5,.8)))
        self.assertEqual(self.run_sequence([(.4,.9)]*3+[(.6,.9)]*3)[1],[])
        cfg=CFG|{'roi':[.45,0,1,1]}
        self.assertEqual(self.run_sequence([(.4,.5)]*3+[(.6,.5)]*3,config=cfg)[1],[])

    def test_missing_detection_breaks_identity(self):
        t,e=self.run_sequence([(.4,.5)]*3+[None]+[(.6,.5)]*3)
        self.assertEqual(e,[]);self.assertEqual(t.stats['new_tracks'],2)

    def test_pts_gap_not_frame_count(self):
        _,e=self.run_sequence([(.4,.5)]*3+[(.6,.5)]*3,[0,.04,.08,.5,.54,.58])
        self.assertEqual(e,[])

    def test_ambiguous_matches_break_ids(self):
        t=BoundaryTracker(CFG)
        t.step(0,[det(.4),det(.41)])
        rows,e=t.step(.04,[det(.42)])
        self.assertEqual(rows[0]['track_id'],3);self.assertEqual(e,[])
        self.assertEqual(t.stats['ambiguous_detections'],1)

    def test_direction_filter(self):
        _,e=self.run_sequence([(.4,.5)]*3+[(.6,.5)]*3,config=CFG|{'directions':['negative_to_positive']})
        self.assertEqual(e,[])

    def test_reject_invalid_pts_and_geometry(self):
        t=BoundaryTracker(CFG);t.step(1,[])
        for pts in [1,.9,float('nan')]:
            with self.assertRaises(ValueError):t.step(pts,[])
        with self.assertRaises(ValueError):BoundaryTracker(CFG|{'line':[[0,0],[0,0]]})
        with self.assertRaises(ValueError):t.step(2,[{'bbox':[0,0,0,1]}])
        self.assertEqual(iou([0,0,1,1],[0,0,1,1]),1)


if __name__=='__main__': unittest.main()
