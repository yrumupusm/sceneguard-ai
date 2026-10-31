import unittest
from collections import defaultdict,deque
from sceneguard.exp0043_media import short_paths


class CausalTrailTests(unittest.TestCase):
    def row(self,t,ids=(0,),wid='w000001'):
        return dict(pts=t,point_paths=[dict(window_id=wid,point_ids=list(ids),
            points_original_pixels=[[t,pid] for pid in ids])])

    def test_trails_keep_only_point_correspondences_and_previous_point3_seconds(self):
        history=defaultdict(deque)
        for t in [0,.1,.2,.3,.4]:live=short_paths(history,self.row(t))
        vertices=live['w000001']['trails'][0]['vertices']
        self.assertEqual([p[0] for p in vertices],[.1,.2,.3,.4])
        self.assertEqual(vertices[-1],[.4,0])

    def test_dropped_points_are_not_current_or_retained_as_ghost_trails(self):
        history=defaultdict(deque);short_paths(history,self.row(0,(0,1)))
        live=short_paths(history,self.row(.1,(1,)))
        self.assertEqual([t['point_id'] for t in live['w000001']['trails']],[1])

    def test_retired_window_is_removed(self):
        history=defaultdict(deque);short_paths(history,self.row(0))
        self.assertEqual(short_paths(history,dict(pts=.1,point_paths=[])),{})
        self.assertEqual(dict(history),{})

    def test_windows_remain_individually_selectable(self):
        history=defaultdict(deque);row=self.row(0)
        row['point_paths']+=self.row(0,wid='w000002')['point_paths']
        self.assertEqual(set(short_paths(history,row)),{'w000001','w000002'})


if __name__=='__main__':unittest.main()
