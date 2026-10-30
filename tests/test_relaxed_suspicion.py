"""Synthetic review-rule tests; no model or original CCTV execution."""
from copy import deepcopy
import unittest
from sceneguard.relaxed_suspicion import RelaxedPolicy, add_relaxed_candidates, _box_overlaps


def fixture(boxes=None, last_index=2, final_index=40):
    stamps = [i/10 for i in range(final_index+1)]
    if boxes is None:
        boxes = [[.47,.3,.53,.5]]*(last_index+1)
    rows = [dict(pts=stamps[i], frame_index=i, cache_index=0, bbox=b)
            for i,b in enumerate(boxes)]
    scene = dict(source_size=[1000,500], line=[[.5,.2],[.5,.8]],
                 approach_polygon=[[.2,.1],[.8,.1],[.8,.9],[.2,.9]],
                 occlusions=[dict(id='occluded',from_side='outside',to_side='inside',
                                  polygon=[[.68,.3],[.78,.3],[.78,.5],[.68,.5]])])
    base = dict(experiment='EXP-0034', policy=dict(loss_wait=1., near_line_heights=.8),
                events=[], pairs=[], existing_alerts=[dict(emitted_at_pts=.1,track_id=7)],
                segments=[dict(id='s1',raw_id=7,rows=rows)],
                losses=[dict(segment='s1',raw_id=7,last_pts=rows[-1]['pts'],
                             status='판단 불가',reason='unresolved_loss',
                             origin_side=None, motion=dict(reliable=False),
                             ever_crossed=False, right_censored=False)])
    return base,scene,stamps


class RelaxedCandidateTests(unittest.TestCase):
    def apply(self, case):
        return add_relaxed_candidates(*case)

    def test_unknown_origin_and_direction_no_longer_block(self):
        result=self.apply(fixture())
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],1)
        self.assertEqual(result['events'][0]['status'],'침입 의심')
        self.assertFalse(result['events'][0]['supporting_evidence']['motion_reliable'])

    def test_all_old_optional_gates_false_still_candidate(self):
        b,s,t=fixture();b['losses'][0].update(toward_boundary=False,near_finite_line=False,
                                            occlusions=[],possible_new_ids=[])
        self.assertEqual(self.apply((b,s,t))['relaxation_summary']['added_loss_candidates'],1)

    def test_stationary_gate_loss_can_be_a_review_candidate(self):
        result=self.apply(fixture())
        self.assertEqual(result['events'][0]['pts'],1.2)
        self.assertFalse(result['events'][0]['confirmed_intrusion'])

    def test_gate_line_is_enough_without_occlusion_polygon(self):
        b,s,t=fixture();s['occlusions']=[]
        self.assertEqual(self.apply((b,s,t))['relaxation_summary']['added_loss_candidates'],1)

    def test_occlusion_overlap_is_enough_away_from_line(self):
        b,s,t=fixture(boxes=[[.7,.35,.73,.37]]*3)
        result=self.apply((b,s,t))
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],1)
        self.assertFalse(result['relaxation_audit'][0]['support'][0]['near_finite_line'])

    def test_recent_history_survives_final_tiny_shifted_box(self):
        b,s,t=fixture(boxes=[[.47,.3,.53,.5]]*3+[[.63,.15,.64,.17]])
        result=self.apply((b,s,t))
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],1)
        self.assertEqual(result['relaxation_audit'][0]['support_count'],3)

    def test_analysis_end_is_not_disappearance(self):
        b,s,t=fixture(final_index=10)
        result=self.apply((b,s,t))
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],0)
        self.assertEqual(result['relaxation_audit'][0]['reason'],'analysis_window_ended_before_loss_wait')

    def test_far_loss_stays_unknown(self):
        result=self.apply(fixture(boxes=[[.1,.1,.13,.13]]*3))
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],0)
        self.assertEqual(result['losses'][0]['status'],'판단 불가')

    def test_infinite_line_extension_is_not_gate(self):
        result=self.apply(fixture(boxes=[[.49,.94,.51,.96]]*3))
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],0)

    def test_one_isolated_measurement_not_enough(self):
        result=self.apply(fixture(last_index=0))
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],0)

    def test_older_than_three_seconds_not_reused(self):
        boxes=[[.47,.3,.53,.5]]*3+[[.1,.1,.13,.13]]*33
        result=self.apply(fixture(boxes=boxes,final_index=50))
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],0)

    def test_confirmed_normal_exit_after_gate_observations_suppresses_new_candidate(self):
        b,s,t=fixture(boxes=[[.47,.3,.53,.5]]*3+[[.1,.1,.13,.13]]*3)
        b['events']=[dict(segment='s1',raw_id=7,pts=.4,status='침입 아님',reason='observed_same_side_exit')]
        result=self.apply((b,s,t))
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],0)
        self.assertEqual(result['relaxation_audit'][0]['reason'],'observed_normal_exit_after_gate_evidence')

    def test_unknown_roi_exit_is_not_proof_of_normal_exit(self):
        b,s,t=fixture();b['losses'][0]['reason']='observed_exit_not_disappearance'
        self.assertEqual(self.apply((b,s,t))['relaxation_summary']['added_loss_candidates'],1)

    def test_return_after_earlier_exit_can_create_new_loss_candidate(self):
        b,s,t=fixture()
        b['events']=[dict(segment='s1',raw_id=7,pts=.05,status='침입 아님',reason='observed_same_side_exit')]
        self.assertEqual(self.apply((b,s,t))['relaxation_summary']['added_loss_candidates'],1)

    def test_existing_suspicion_not_duplicated(self):
        b,s,t=fixture();b['losses'][0]['status']='침입 의심'
        b['events']=[dict(segment='s1',raw_id=7,pts=1.2,status='침입 의심',reason='approach_to_known_occlusion_loss')]
        result=self.apply((b,s,t))
        self.assertEqual(result['relaxation_summary']['added_loss_candidates'],0)
        self.assertEqual(result['events'],b['events'])

    def test_previous_alerts_and_raw_ids_not_changed(self):
        b,s,t=fixture();before=deepcopy(b)
        result=self.apply((b,s,t))
        self.assertEqual(b,before)
        self.assertEqual(result['existing_alerts'],before['existing_alerts'])
        self.assertEqual(result['segments'],before['segments'])
        self.assertEqual(result['pairs'],before['pairs'])

    def test_suspected_transition_not_erased_by_later_exit(self):
        b,s,t=fixture()
        b['events']=[dict(segment='s1',raw_id=7,pts=.1,status='침입 의심',reason='observed_side_transition')]
        result=self.apply((b,s,t))
        self.assertIn(b['events'][0],result['events'])

    def test_no_automatic_confirmation_or_vlm_requirement(self):
        result=self.apply(fixture())
        self.assertFalse(any(e['status']=='침입 확인' for e in result['events']))
        self.assertFalse(result['events'][0]['supporting_evidence']['vlm_required'])
        self.assertFalse(result['events'][0]['reappearance_required'])

    def test_wrong_pts_or_measurement_binding_rejected(self):
        b,s,t=fixture();b['segments'][0]['rows'][0]['pts']=.01
        with self.assertRaises(ValueError): self.apply((b,s,t))

    def test_nonfinite_or_invalid_policy_rejected(self):
        for p in (RelaxedPolicy(history_seconds=float('nan')),RelaxedPolicy(min_near_observations=0)):
            with self.assertRaises(ValueError): p.validate()

    def test_earlier_output_does_not_use_new_later_frames_for_evidence(self):
        b,s,t=fixture()
        first=self.apply((b,s,t))
        later=self.apply((b,s,t+[4.1,4.2,4.3]))
        e1,e2=first['events'][0],later['events'][0]
        for k in ('pts','near_evidence_frame_indices','supporting_evidence'):
            self.assertEqual(e1[k],e2[k])

    def test_actual_frame_at_wait_boundary_used(self):
        b,s,t=fixture();t=t[:3]+[1.25,1.35,2.0]
        result=self.apply((b,s,t))
        self.assertEqual(result['events'][0]['pts'],1.25)

    def test_box_polygon_edge_intersection_detected(self):
        poly=[[.45,.1],[.55,.1],[.55,.9],[.45,.9]]
        self.assertTrue(_box_overlaps([.1,.45,.9,.55],poly))
        self.assertFalse(_box_overlaps([.1,.1,.2,.2],poly))

    def test_loss_raw_id_mismatch_rejected(self):
        b,s,t=fixture();b['losses'][0]['raw_id']=99
        with self.assertRaises(ValueError): self.apply((b,s,t))


if __name__=='__main__': unittest.main()
