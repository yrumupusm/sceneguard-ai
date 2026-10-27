import unittest
from sceneguard.replay_thresholds import normalize,replay

CFG=dict(line=[[.5,0],[.5,1]],roi=[0,0,1,1],band=.005,dwell_seconds=.1,
         max_gap_seconds=.1,min_iou=.3,cooldown_seconds=1,score_threshold=.5)

class ReplayTests(unittest.TestCase):
    def test_threshold_boundary_order_clamp_and_empty(self):
        f=dict(source_size=[100,100],boxes=[[-1,0,20,20],[30,0,50,20],[0,0,0,0]],
               scores=[.5,.25,.9])
        self.assertEqual(normalize(f,.5),[dict(bbox=[0.,0.,.2,.2],score=.5)])
        self.assertEqual(len(normalize(f,.25)),2)
        self.assertEqual(normalize(dict(source_size=[100,100],boxes=[],scores=[]),.25),[])

    def test_fresh_state_and_missing_frame_preserved(self):
        cache=[dict(pts=i/30,native_pts=i,time_base='1/30',source_size=[100,100],
                    boxes=[[10,10,30,30]],scores=[s]) for i,s in enumerate([.6,.3,.6])]
        high,_,_=replay(cache,CFG,.5);low,_,_=replay(cache,CFG,.25)
        self.assertEqual([len(f['detections']) for f in high],[1,0,1])
        self.assertEqual([f['detections'][0]['track_id'] for f in low],[1,1,1])
        self.assertEqual(high[-1]['detections'][0]['track_id'],2)
        self.assertEqual(replay(cache,CFG,.5)[0],high)
        self.assertEqual(CFG['score_threshold'],.5)
        self.assertEqual([f['pts'] for f in high],[f['pts'] for f in low])
