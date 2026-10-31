"""Counterexamples for the one frozen seed-geometry/recent-dynamics hypothesis.

Synthetic image motion is not semantic action ground truth. Tests intentionally
expose retained post-stop and reversal evidence, rather than hiding this risk.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

from sceneguard.exp0043_comparison import (
    SeedGeometryReplay, seed_geometry_metric, normalize_candidate,
)
from sceneguard.gate_transition import cue_metrics, TransitionPolicy

SCENE = dict(line=[[.1,.5],[.9,.5]], source_size=[200,200])
P = np.array([[70,106],[75,107],[80,108],[85,109],
              [90,110],[95,111],[100,112],[105,113.]], dtype=float)


def metric(p, q, height=50, change=.1):
    saved = cue_metrics(p, q, line=SCENE['line'], size=SCENE['source_size'],
                        height=height, dt=.5, prior_speed=.2)
    saved['motion_change'] = change
    return seed_geometry_metric(p, q, scene=SCENE, height=height, saved=saved)


class CounterexampleTests(unittest.TestCase):
    def test_approach_without_crossing_is_not_sufficient(self):
        # Rigid approach from below the gate, no deformation or boundary passage.
        result = metric(P+[0,20], P+[0,5])
        self.assertLess(result['score'], .55)
        self.assertEqual(result['crossing_fraction'], 0)
        self.assertAlmostEqual(result['local_deformation'], 0)

    def test_parallel_walking_does_not_create_upward_or_progress(self):
        result = metric(P, P+[30,0])
        self.assertEqual(result['score'], 0)
        self.assertEqual(result['upward_image_motion'], 0)
        self.assertEqual(result['normal_progress'], 0)

    def test_waiting_has_no_transition(self):
        result = metric(P, P)
        self.assertEqual(result['score'], 0)
        self.assertEqual(result['local_deformation'], 0)

    def test_partial_body_retains_seed_scale_and_quality_penalty(self):
        q = P+np.array([[0,-3],[0,-3],[0,-3],[0,-3],
                       [0,-14],[0,-15],[0,-16],[0,-17]])
        partial = metric(P[:3], q[:3])
        self.assertEqual(partial['point_count'], 3)
        self.assertFalse(partial['identity_verified'])
        self.assertIsNone(partial['probability'])
        # A tiny visible fragment is not silently rescaled into a whole body.
        large_scale = metric(P[:3], q[:3], height=100)
        self.assertLess(large_scale['upward_image_motion'], partial['upward_image_motion'])
        self.assertLess(partial['score'], .55)

    def test_gradual_intrusion_like_change_keeps_cumulative_geometry(self):
        delta=np.array([[0,-3],[0,-3],[0,-3],[0,-3],
                        [0,-14],[0,-15],[0,-16],[0,-17]])
        q=P+delta
        seed=metric(P,q)
        rolling=metric(P+delta*.8,q)
        self.assertGreater(seed['upward_image_motion'], rolling['upward_image_motion'])
        self.assertGreater(seed['local_deformation'], rolling['local_deformation'])
        self.assertGreater(seed['score'], rolling['score'])
        self.assertFalse(seed['identity_verified'])

    def test_reversal_can_leave_seed_evidence_until_return_risk_is_explicit(self):
        # Out-and-partway-back remains displaced from birth; no hidden direction veto.
        halfway=metric(P,P+[0,-12])
        returned=metric(P,P)
        self.assertGreater(halfway['score'], returned['score'])
        self.assertEqual(returned['score'], 0)

    def test_stopped_motion_can_retain_seed_evidence_risk_is_explicit(self):
        q=P+np.array([[0,-3],[0,-3],[0,-3],[0,-3],
                      [0,-14],[0,-15],[0,-16],[0,-17]])
        saved=cue_metrics(q,q,line=SCENE['line'],size=SCENE['source_size'],height=50)
        retained=seed_geometry_metric(P,q,scene=SCENE,height=50,saved=saved)
        self.assertEqual(saved['score'], 0)
        self.assertEqual(retained['motion_change'], 0)
        self.assertGreater(retained['score'], saved['score'])

    def test_recent_dynamics_and_current_proximity_are_preserved(self):
        q=P+[0,-12]
        saved=cue_metrics(P+[0,-10],q,line=SCENE['line'],size=SCENE['source_size'],
                          height=50,dt=.5,prior_speed=.4)
        saved['motion_change']=.123456
        saved['speed_heights_per_second']=.789
        result=seed_geometry_metric(P,q,scene=SCENE,height=50,saved=saved)
        for key in ('motion_change','speed_heights_per_second','proximity','point_count'):
            self.assertEqual(result[key],saved[key])

    def test_nonrigid_approach_can_still_be_false_positive(self):
        p=P+np.array([[0,10]]*4+[[0,25]]*4)
        result=metric(p,P)
        self.assertEqual(result['crossing_fraction'],0)
        self.assertGreaterEqual(result['score'],.55)

    def test_seed_score_replaces_recent_score_even_when_lower(self):
        saved=cue_metrics(P+[0,12],P,line=SCENE['line'],size=SCENE['source_size'],
                          height=50,dt=.5)
        result=seed_geometry_metric(P,P,scene=SCENE,height=50,saved=saved,dt=1)
        self.assertGreater(saved['score'],0)
        self.assertEqual(result['score'],0)
        self.assertLess(result['score'],saved['score'])


class ReplayContractTests(unittest.TestCase):
    def row(self,at,points,ids=None,step=(0,0),signal=True):
        ids=list(range(len(points))) if ids is None else ids
        s=cue_metrics(P[np.array(ids)],np.asarray(points),line=SCENE['line'],
                      size=SCENE['source_size'],height=50,dt=max(.1,at))
        s.update(window_id='w1',reference_pts=max(0,at-.5),seed_pts=0,
                 seed_track_ids=[7],seed_cache_index=0,point_ids=ids,
                 points_original_pixels=np.asarray(points).tolist(),
                 camera_support=True,evidence_until_pts=at)
        return dict(pts=at,frame_index=round(at*30),native_pts=round(at*300),
            time_base='1/300',source_gap=False,camera_support=True,camera_step_pixels=list(step),
            signals=[s] if signal else [],
            point_paths=[dict(window_id='w1',seed_pts=0,point_ids=ids,
                seed_track_ids=[7],seed_cache_index=0,
                points_original_pixels=np.asarray(points).tolist())],
            actual_boxes=[dict(cache_index=0,bbox=[.3,.4,.7,.65])])

    def test_point_pairing_uses_permanent_ids_after_loss_and_reorder(self):
        e=SeedGeometryReplay(SCENE,TransitionPolicy())
        e.step(self.row(0,P,signal=False))
        ids=[7,2,4,0]; q=P[ids]+[0,-12]
        r=e.step(self.row(.5,q,ids))
        expected=metric(P[ids],q)
        self.assertEqual(r['signals'][0]['point_ids'],ids)
        self.assertAlmostEqual(r['signals'][0]['normal_progress'],expected['normal_progress'])
        self.assertEqual(r['signals'][0]['reference_pts'],0)
        self.assertEqual(r['signals'][0]['recent_reference_pts'],0)
        self.assertEqual(r['signals'][0]['geometry_dt'],.5)

    def test_camera_correction_uses_same_original_pixel_frame(self):
        e=SeedGeometryReplay(SCENE,TransitionPolicy())
        e.step(self.row(0,P,signal=False))
        r=e.step(self.row(.5,P+[6,4],step=(6,4)))
        self.assertEqual(r['signals'][0]['upward_image_motion'],0)
        self.assertEqual(r['signals'][0]['local_deformation'],0)
        self.assertEqual(r['score'],0)

    def test_prefix_is_causal_and_input_rows_are_immutable(self):
        rows=[self.row(0,P,signal=False),self.row(.1,P+[0,-1]),
              self.row(.2,P+[0,-2]),self.row(.3,P+[0,-3])]
        original=copy.deepcopy(rows)
        e=SeedGeometryReplay(SCENE,TransitionPolicy()); first=[e.step(r) for r in rows[:3]]
        e.step(rows[3])
        f=SeedGeometryReplay(SCENE,TransitionPolicy()); second=[f.step(r) for r in rows[:3]]
        self.assertEqual(first,second)
        self.assertEqual(rows,original)
        self.assertEqual(first[-1]['signals'][0]['evidence_until_pts'],.2)
        with self.assertRaises(ValueError): e.step(rows[0])

    def test_missing_seed_and_future_reference_are_rejected(self):
        with self.assertRaises(ValueError):
            SeedGeometryReplay(SCENE,TransitionPolicy()).step(self.row(.5,P))
        e=SeedGeometryReplay(SCENE,TransitionPolicy()); e.step(self.row(0,P,signal=False))
        row=self.row(.1,P); row['signals'][0]['reference_pts']=.2
        with self.assertRaises(ValueError): e.step(row)

    def test_source_gap_cannot_bridge_prior_seed(self):
        e=SeedGeometryReplay(SCENE,TransitionPolicy()); e.step(self.row(0,P,signal=False))
        row=self.row(.5,P); row['source_gap']=True
        with self.assertRaises(ValueError): e.step(row)

    def test_retired_window_cannot_reappear_with_old_seed(self):
        e=SeedGeometryReplay(SCENE,TransitionPolicy()); e.step(self.row(0,P,signal=False))
        empty=self.row(.1,P,signal=False); empty['point_paths']=[]
        e.step(empty)
        with self.assertRaises(ValueError): e.step(self.row(.2,P))

    def test_seed_expiry_is_not_extended(self):
        e=SeedGeometryReplay(SCENE,TransitionPolicy()); e.step(self.row(0,P,signal=False))
        with self.assertRaises(ValueError): e.step(self.row(2.6,P))

    def test_two_reference_clocks_and_real_seed_age_are_explicit(self):
        e=SeedGeometryReplay(SCENE,TransitionPolicy()); e.step(self.row(0,P,signal=False))
        row=self.row(.6,P+[0,-5]); result=e.step(row)['signals'][0]
        self.assertEqual(result['geometry_reference_pts'],0)
        self.assertEqual(result['geometry_dt'],.6)
        self.assertAlmostEqual(result['recent_reference_pts'],.1)
        self.assertAlmostEqual(result['recent_dt'],.5)
        self.assertEqual(result['motion_change'],row['signals'][0]['motion_change'])
        self.assertEqual(result['speed_heights_per_second'],row['signals'][0]['speed_heights_per_second'])

    def test_candidate_namespace_is_distinct_from_exp42_and_metadata_causal(self):
        e=SeedGeometryReplay(SCENE,TransitionPolicy()); e.step(self.row(0,P,signal=False))
        q=P+[0,-12]; r=e.step(self.row(.1,q))
        raw=dict(status='침입 의심',reason='gate_visual_transition',
            decision_time_pts=.1,frame_index=3,evidence=r['signals'][0],
            evidence_until_pts=.1,identity_verified=False,automatic_confirmation=False)
        event=normalize_candidate(raw,scope=dict(session_id='test',camera_id='C3',gate_id='g'),
                                  video_id='test',source_sha256='abc')
        self.assertEqual(event['algorithm'],'seed_geometry_recent_dynamics_v1')
        self.assertEqual(event['source_event']['evidence']['reference_pts'],0)


if __name__=='__main__': unittest.main()
