"""Causal renderer timeline, exact source clock, and permanent point contracts."""
import unittest
from copy import deepcopy
from dataclasses import asdict
from sceneguard.exp0042_evidence import frame_clock, status_at, SavedPaths, intervals
from sceneguard.exp0042_application import normalize_transition
from sceneguard.incident_notifications import group_notifications

class RendererContract(unittest.TestCase):
    def row(self,n=1):
        return dict(native_pts=n,time_base='1/30',pts=n/30,
            point_paths=[dict(window_id='w000001',point_ids=[1,3],points_original_pixels=[[2.,3.],[4.,5.]])])
    def test_exact_native_clock(self):self.assertEqual(str(frame_clock(self.row())),'1/30')
    def test_wrong_seconds_rejected(self):
        row=self.row();row['pts']=1.
        with self.assertRaises(ValueError):frame_clock(row)
    def test_clock_increases(self):
        paths=SavedPaths();paths.push(self.row())
        with self.assertRaises(ValueError):paths.push(self.row())
    def test_point_ids_survive_without_reindexing(self):
        paths=SavedPaths();paths.push(self.row());row=self.row(2)
        row['point_paths'][0].update(point_ids=[3],points_original_pixels=[[6.,7.]])
        paths.push(row);self.assertEqual(paths.paths['w000001'],{3:[[4.,5.],[6.,7.]]})
        with self.assertRaises(ValueError):paths.push(self.row(3))
    def test_retired_window_cannot_reappear(self):
        paths=SavedPaths();paths.push(self.row());row=self.row(2);row['point_paths']=[];paths.push(row)
        with self.assertRaises(ValueError):paths.push(self.row(3))
    def test_status_prefix_does_not_leak_future_card_or_event(self):
        def event(t,w):
            raw=dict(status='침입 의심',reason='gate_visual_transition',decision_time_pts=t,evidence_until_pts=t,
                evidence=dict(seed_pts=0.,reference_pts=t-.1,window_id=w,seed_track_ids=[]))
            return normalize_transition(raw,scope=dict(session_id='s',camera_id='C3',gate_id='g'),video_id='v',source_sha256='x')
        bundle=group_notifications([event(1.,'w1'),event(2.,'w2'),event(8.,'w3')])
        self.assertEqual(status_at(bundle,.9)['cards'],0)
        self.assertEqual(status_at(bundle,1.)['candidate_rows'],1)
        self.assertEqual(status_at(bundle,1.5)['latest_candidate_pts'],1.)
        self.assertEqual(status_at(bundle,2.)['notification_intents'],1)
        self.assertEqual(status_at(bundle,8.)['notification_intents'],2)
    def test_all_candidates_have_clips_and_zero_still_has_core(self):
        rows=[dict(pts=48.),dict(pts=104.96666666666667)]
        events=[dict(event_id='a',decision_time_pts=65.),dict(event_id='b',decision_time_pts=66.),dict(event_id='c',decision_time_pts=90.)]
        targets=intervals(rows,events,'007')
        self.assertEqual({i for t in targets for i in t['event_ids']},{'a','b','c'})
        self.assertEqual(len([t for t in targets if t['event_ids']]),2)
        self.assertEqual(len(intervals(rows,[],'007')),3)

if __name__=='__main__':unittest.main()
