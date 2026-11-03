"""Causal boundary-alert validation, without CCTV accuracy assertions."""
from copy import deepcopy
import unittest

from sceneguard.existing_alert_crossing import existing_alert_crossing_decision


def row(t, x, bottom=.6):
    return dict(pts=t,frame_index=round(t*30),cache_index=0,
                bbox=[x-.02,bottom-.1,x+.02,bottom],observed=True)


def inputs(outward=False):
    source=dict(track_id=3,observed_pts_before=.3,observed_pts_after=.5,
        candidate_interval=[.3,.5],candidate_pts=.4,emitted_at_pts=.7,
        direction='negative_to_positive' if outward else 'positive_to_negative',condition='gap')
    xs=[.44,.45,.46,.48,.5,.52,.54,.55]
    if outward:xs=[1-x for x in xs]
    segments=[dict(id='s1',raw_id=3,rows=[row(i/10,x) for i,x in enumerate(xs)])]
    scene=dict(source_size=[1000,1000],line=[[.5,.25],[.5,.75]],
        approach_polygon=[[.3,.1],[.7,.1],[.7,.9],[.3,.9]],
        zones={'outside':[[0,0],[.49,0],[.49,1],[0,1]],
               'inside':[[.51,0],[1,0],[1,1],[.51,1]]},
        directions=['outside_to_inside','inside_to_outside'])
    return source,segments,scene


class ExistingAlertCrossingTests(unittest.TestCase):
    def test_both_measured_directions_confirm_at_emission_clock(self):
        for outward in (False,True):
            with self.subTest(outward=outward):
                result=existing_alert_crossing_decision(*inputs(outward))
                self.assertTrue(result['automatic_confirmation'])
                self.assertEqual(result['direction'],'inside_to_outside' if outward else 'outside_to_inside')
                self.assertEqual(result['decision_time_pts'],.7)
                self.assertEqual(result['last_observed_pts'],.7)
                self.assertEqual(result['rule_id'],'existing_alert_gate_crossing_v1')
                self.assertFalse(result['human_verified'])
                self.assertFalse(result['loss_wait_required'])
                self.assertTrue(result['finite_gate_crossings'])
                self.assertTrue(all(r['pts']<=.7 for r in result['observation_refs']))

    def test_future_rows_cannot_complete_destination_dwell(self):
        source,segments,scene=inputs();source['emitted_at_pts']=.6
        self.assertFalse(existing_alert_crossing_decision(source,segments,scene)['automatic_confirmation'])

    def test_future_rows_do_not_change_completed_decision(self):
        args=inputs();before=existing_alert_crossing_decision(*args)
        args[1][0]['rows'] += [row(.8,.4),row(.9,.3)]
        self.assertEqual(before,existing_alert_crossing_decision(*args))

    def test_wrong_source_direction_does_not_establish_crossing(self):
        source,segments,scene=inputs();source['direction']='negative_to_positive'
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'existing_alert_signed_direction_not_measured')

    def test_approach_without_crossing_rejected(self):
        source,segments,scene=inputs()
        for r in segments[0]['rows']:r['bbox']=row(r['pts'],.48)['bbox']
        self.assertFalse(existing_alert_crossing_decision(source,segments,scene)['automatic_confirmation'])

    def test_line_extension_rejected_in_both_directions(self):
        for outward in (False,True):
            source,segments,scene=inputs(outward)
            for r in segments[0]['rows']:r['bbox']=row(r['pts'],sum(r['bbox'][::2])/2,.8)['bbox']
            result=existing_alert_crossing_decision(source,segments,scene)
            self.assertFalse(result['automatic_confirmation'])
            self.assertEqual(result['reason'],'existing_alert_no_measured_finite_gate_crossing')

    def test_gap_or_box_jump_cannot_bridge_crossing(self):
        for failure in ('gap','position','width','height'):
            source,segments,scene=inputs();rows=segments[0]['rows']
            if failure=='gap':segments[0]['rows']=[r for r in rows if r['pts'] not in (.4,.5)]
            elif failure=='position':rows[4]['bbox']=row(.4,.7)['bbox']
            elif failure=='width':rows[4]['bbox']=[.499,.5,.501,.6]
            else:rows[4]['bbox']=[.48,.59,.52,.6]
            with self.subTest(failure=failure):
                self.assertFalse(existing_alert_crossing_decision(source,segments,scene)['automatic_confirmation'])

    def test_fragment_must_contain_both_anchors(self):
        source,segments,scene=inputs();rows=segments[0]['rows']
        segments[0]['rows']=rows[4:]
        segments.append(dict(id='other',raw_id=3,rows=rows[:4]))
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'existing_alert_anchor_not_in_emission_fragment')

    def test_long_gap_with_both_anchors_still_present_rejected(self):
        source,segments,scene=inputs()
        segments[0]['rows']=[row(t,x) for t,x in [(0.,.44),(.1,.45),(.2,.46),(.3,.48),
                                                 (.7,.52),(.8,.54),(.9,.55)]]
        source.update(observed_pts_after=.7,candidate_interval=[.3,.7],emitted_at_pts=.9)
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'existing_alert_discontinuous_anchor_path')

    def test_ambiguous_reused_id_at_emission_rejected(self):
        source,segments,scene=inputs();segments.append(deepcopy(segments[0]));segments[1]['id']='other'
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'existing_alert_measured_fragment_not_unique')

    def test_no_observation_at_emission_rejected(self):
        source,segments,scene=inputs();source['emitted_at_pts']=.75
        self.assertFalse(existing_alert_crossing_decision(source,segments,scene)['automatic_confirmation'])

    def test_unstable_origin_rejected(self):
        source,segments,scene=inputs();segments[0]['rows']=segments[0]['rows'][2:]
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'existing_alert_origin_dwell_not_measured')

    def test_jitter_in_destination_dwell_rejected(self):
        source,segments,scene=inputs();segments[0]['rows'][-2]['bbox']=row(.6,.5005)['bbox']
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'existing_alert_destination_dwell_not_measured')

    def test_disabled_direction_rejected(self):
        for outward in (False,True):
            source,segments,scene=inputs(outward)
            scene['directions']=['outside_to_inside' if outward else 'inside_to_outside']
            self.assertFalse(existing_alert_crossing_decision(source,segments,scene)['automatic_confirmation'])

    def test_zone_centers_on_same_side_are_ambiguous(self):
        source,segments,scene=inputs();scene['zones']['inside']=[[.1,0],[.3,0],[.3,1],[.1,1]]
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertEqual(result['reason'],'ambiguous_configured_boundary_orientation')

    def test_candidate_summary_cannot_replace_measured_support(self):
        source,segments,scene=inputs();source.update(confirmation_observations=999,confirmation_visible_seconds=999)
        segments[0]['rows']=segments[0]['rows'][2:]
        self.assertFalse(existing_alert_crossing_decision(source,segments,scene)['automatic_confirmation'])

    def test_predicted_box_rejected(self):
        source,segments,scene=inputs();segments[0]['rows'][3]['observed']=False
        with self.assertRaises(ValueError):existing_alert_crossing_decision(source,segments,scene)

    def test_duplicate_observation_clock_rejected(self):
        source,segments,scene=inputs();segments[0]['rows'][2]['pts']=.1
        with self.assertRaises(ValueError):existing_alert_crossing_decision(source,segments,scene)

    def test_clock_and_interval_mismatches_rejected(self):
        for update in ({'decision_time_pts':.6},{'candidate_interval':[.2,.5]},
                       {'observed_pts_after':.8},{'track_id':True}):
            source,segments,scene=inputs();source.update(update)
            with self.subTest(update=update),self.assertRaises(ValueError):
                existing_alert_crossing_decision(source,segments,scene)

    def test_endpoints_and_source_direction_reverse_together(self):
        source,segments,scene=inputs();scene['line'].reverse();source['direction']='negative_to_positive'
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertTrue(result['automatic_confirmation'])
        self.assertEqual(result['direction'],'outside_to_inside')

    def test_crossing_outside_approach_polygon_rejected(self):
        source,segments,scene=inputs();scene['approach_polygon']=[[.3,.1],[.7,.1],[.7,.4],[.3,.4]]
        self.assertFalse(existing_alert_crossing_decision(source,segments,scene)['automatic_confirmation'])

    def test_opposite_finite_crossing_cannot_prove_extension_crossings(self):
        positions=[(.46,.8),(.47,.8),(.48,.8),(.505,.8),(.505,.76),
                   (.505,.72),(.505,.69),(.495,.69),(.495,.73),
                   (.495,.77),(.495,.8),(.52,.8),(.53,.8),(.54,.8)]
        for outward in (False,True):
            source,segments,scene=inputs(outward)
            source.update(observed_pts_before=.2,observed_pts_after=1.1,
                          candidate_interval=[.2,1.1],emitted_at_pts=1.3)
            segments[0]['rows']=[row(i/10,1-x if outward else x,y) for i,(x,y) in enumerate(positions)]
            result=existing_alert_crossing_decision(source,segments,scene)
            self.assertFalse(result['automatic_confirmation'])
            self.assertEqual(result['reason'],'existing_alert_no_measured_finite_gate_crossing')

    def test_touching_gate_then_walking_beyond_endpoint_rejected(self):
        source,segments,scene=inputs()
        positions=[(.44,.7),(.45,.7),(.46,.7),(.48,.7),(.5,.7),
                   (.5,.73),(.5,.76),(.5,.8),(.52,.8),(.54,.8),(.55,.8)]
        segments[0]['rows']=[row(i/10,x,y) for i,(x,y) in enumerate(positions)]
        source.update(observed_pts_after=.8,candidate_interval=[.3,.8],emitted_at_pts=1.)
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'existing_alert_no_measured_finite_gate_crossing')

    def test_gate_endpoint_is_supported(self):
        source,segments,scene=inputs()
        for r in segments[0]['rows']:r['bbox']=row(r['pts'],sum(r['bbox'][::2])/2,.75)['bbox']
        self.assertTrue(existing_alert_crossing_decision(source,segments,scene)['automatic_confirmation'])

    def test_slow_continuous_boundary_band_travel_preserves_causal_anchors(self):
        source,segments,scene=inputs()
        xs=[.44,.45,.46,.48]+[.5]*31+[.52,.54,.55]
        segments[0]['rows']=[row(i/10,x) for i,x in enumerate(xs)]
        source.update(observed_pts_after=3.5,candidate_interval=[.3,3.5],emitted_at_pts=3.7)
        result=existing_alert_crossing_decision(source,segments,scene)
        self.assertTrue(result['automatic_confirmation'])
        self.assertEqual(result['decision_time_pts'],3.7)

    def test_inputs_immutable(self):
        args=inputs();snapshot=deepcopy(args);existing_alert_crossing_decision(*args)
        self.assertEqual(args,snapshot)


if __name__=='__main__':unittest.main()
