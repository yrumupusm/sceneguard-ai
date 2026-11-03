"""Synthetic failure/causality tests, not measured CCTV accuracy."""
from copy import deepcopy
import unittest

from sceneguard.approach_disappearance import Policy
from sceneguard.visible_crossing import visible_crossing_decision


def scene():
    return dict(source_size=[1000,1000],line=[[.5,.25],[.5,.75]],
        approach_polygon=[[.3,.1],[.7,.1],[.7,.9],[.3,.9]],
        zones={'outside':[[0,0],[.49,0],[.49,1],[0,1]],
               'inside':[[.51,0],[1,0],[1,1],[.51,1]]},
        directions=['outside_to_inside','inside_to_outside'])


def row(t,x,y=.5):
    return dict(pts=t,frame_index=round(t*30),cache_index=0,bbox=[x-.02,y-.05,x+.02,y+.05])


def inputs(direction='outside_to_inside'):
    rows=[row(i/10,x) for i,x in enumerate([.44,.45,.46,.48,.5,.52,.54,.55])]
    if direction == 'inside_to_outside':
        for r in rows:
            left, top, right, bottom = r['bbox']
            r['bbox'] = [1-right, top, 1-left, bottom]
    return (dict(segment='s1',raw_id=1,pts=.7,decision_time_pts=.7,
                 reason='observed_side_transition',direction=direction),
            dict(id='s1',raw_id=1,rows=rows),scene())


class VisibleCrossingTests(unittest.TestCase):
    def test_continuous_passage_confirms_without_waiting_for_loss(self):
        source,seg,sc=inputs(); result=visible_crossing_decision(source,seg,sc)
        self.assertTrue(result['automatic_confirmation'])
        self.assertEqual(result['decision_time_pts'],.7)
        self.assertEqual(result['last_observed_pts'],.7)
        self.assertFalse(result['loss_wait_required'])
        self.assertFalse(result['human_verified'])
    def test_direction_metadata_cannot_override_measured_path(self):
        source,seg,sc=inputs();source['direction']='inside_to_outside'
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_inside_only_does_not_establish_crossing(self):
        source,seg,sc=inputs()
        for r in seg['rows']:r['bbox']=row(r['pts'],.55)['bbox']
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_short_inside_streak_rejected(self):
        source,seg,sc=inputs();seg['rows'][-3]['bbox']=row(.5,.50)['bbox']
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_gap_cannot_bridge_the_sides(self):
        source,seg,sc=inputs();seg['rows']=[r for r in seg['rows'] if r['pts'] not in [.3,.4]]
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_future_observations_cannot_finish_inside_stability(self):
        source,seg,sc=inputs();source.update(pts=.6,decision_time_pts=.6)
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_future_append_does_not_change_decision(self):
        source,seg,sc=inputs();before=visible_crossing_decision(source,seg,sc)
        seg['rows'] += [row(.8,.56),row(.9,.57)]
        self.assertEqual(before,visible_crossing_decision(source,seg,sc))
    def test_metadata_mismatch_fails(self):
        source,seg,sc=inputs();source['raw_id']=2
        with self.assertRaises(ValueError):visible_crossing_decision(source,seg,sc)
    def test_clock_mismatch_fails(self):
        source,seg,sc=inputs();source['decision_time_pts']=.8
        with self.assertRaises(ValueError):visible_crossing_decision(source,seg,sc)
    def test_ambiguous_overlapping_regions_cannot_confirm(self):
        source,seg,sc=inputs();sc['zones']['outside']=[[0,0],[.6,0],[.6,1],[0,1]]
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_far_from_finite_gate_rejected(self):
        source,seg,sc=inputs();sc['approach_polygon']=[[0,0],[1,0],[1,1],[0,1]]
        for r in seg['rows']:r['bbox']=row(r['pts'],sum(r['bbox'][::2])/2,.95)['bbox']
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_crossing_near_line_extension_is_not_gate_crossing(self):
        source,seg,sc=inputs()
        for r in seg['rows']:
            r['bbox']=row(r['pts'],sum(r['bbox'][::2])/2,.8)['bbox']
        result=visible_crossing_decision(source,seg,sc)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'no_observed_finite_gate_crossing')
    def test_exact_on_line_sample_between_sides_is_supported(self):
        result=visible_crossing_decision(*inputs())
        self.assertTrue(result['automatic_confirmation'])
        self.assertTrue(result['finite_gate_crossings'])
        self.assertTrue(all(0 <= u <= 1 for c in result['finite_gate_crossings'] for u in c['gate_along']))
    def test_touching_gate_then_crossing_beyond_endpoint_rejected(self):
        source,seg,sc=inputs()
        positions=[(.44,.7),(.45,.7),(.46,.7),(.48,.7),(.5,.7),
                   (.5,.73),(.5,.76),(.5,.8),(.52,.8),(.54,.8),(.55,.8)]
        seg['rows']=[row(i/10,x,y) for i,(x,y) in enumerate(positions)]
        source.update(pts=1.,decision_time_pts=1.)
        result=visible_crossing_decision(source,seg,sc)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'no_observed_finite_gate_crossing')
    def test_outward_finite_crossing_cannot_support_inward_extension_crossings(self):
        source,seg,sc=inputs()
        positions=[(.46,.8),(.47,.8),(.48,.8),(.505,.8),(.505,.76),
                   (.505,.72),(.505,.69),(.495,.69),(.495,.73),
                   (.495,.77),(.495,.8),(.52,.8),(.53,.8),(.54,.8)]
        seg['rows']=[row(i/10,x,y) for i,(x,y) in enumerate(positions)]
        source.update(pts=1.3,decision_time_pts=1.3)
        result=visible_crossing_decision(source,seg,sc)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'no_observed_finite_gate_crossing')
    def test_gate_endpoint_is_valid_but_extension_is_not(self):
        source,seg,sc=inputs()
        for r in seg['rows']:
            r['bbox']=row(r['pts'],sum(r['bbox'][::2])/2,.735)['bbox']
        self.assertTrue(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_disconnected_box_jump_rejected(self):
        source,seg,sc=inputs()
        for r in seg['rows'][-3:]:r['bbox']=row(r['pts'],.7)['bbox']
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_scale_jump_rejected(self):
        source,seg,sc=inputs();seg['rows'][4]['bbox']=[.49,.495,.51,.505]
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_predicted_box_rejected(self):
        source,seg,sc=inputs();seg['rows'][3]['observed']=False
        with self.assertRaises(ValueError):visible_crossing_decision(source,seg,sc)
    def test_wrong_event_type_rejected(self):
        source,seg,sc=inputs();source['reason']='recent_gate_presence_then_loss'
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_reversing_line_does_not_change_inward_meaning(self):
        source,seg,sc=inputs();sc['line'].reverse()
        self.assertTrue(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_polygon_transition_on_same_boundary_side_rejected(self):
        source,seg,sc=inputs();sc['line']=[[.8,.25],[.8,.75]]
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])
    def test_duplicate_observation_clock_rejected(self):
        source,seg,sc=inputs();seg['rows'][2]['pts']=seg['rows'][1]['pts']
        with self.assertRaises(ValueError):visible_crossing_decision(source,seg,sc)
    def test_inputs_immutable(self):
        args=inputs();snapshot=deepcopy(args);visible_crossing_decision(*args)
        self.assertEqual(args,snapshot)
    def test_direction_disabled(self):
        source,seg,sc=inputs();sc['directions']=['inside_to_outside']
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])

    def test_outward_continuous_passage_confirms_with_physical_side_evidence(self):
        result=visible_crossing_decision(*inputs('inside_to_outside'))
        self.assertTrue(result['automatic_confirmation'])
        self.assertEqual(result['status'],'침입 확인')
        self.assertEqual(result['direction'],'inside_to_outside')
        self.assertEqual(result['reason'],'continuous_observed_inside_to_outside')
        self.assertEqual(result['decision_time_pts'],.7)
        self.assertEqual(result['last_observed_pts'],.7)
        self.assertFalse(result['loss_wait_required'])
        self.assertFalse(result['human_verified'])
        self.assertLess(result['inside_support'][-1]['pts'],result['outside_support'][0]['pts'])
        self.assertTrue(result['finite_gate_crossings'])

    def test_outward_direction_must_be_enabled(self):
        source,seg,sc=inputs('inside_to_outside');sc['directions']=['outside_to_inside']
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])

    def test_outward_metadata_cannot_claim_inward_path(self):
        source,seg,sc=inputs('inside_to_outside');source['direction']='outside_to_inside'
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])

    def test_outward_requires_stable_actual_sides_and_continuity(self):
        for failure in ('no_inside','short_outside','gap','jump','scale','overlap'):
            with self.subTest(failure=failure):
                source,seg,sc=inputs('inside_to_outside')
                if failure=='no_inside':
                    for r in seg['rows']:r['bbox']=row(r['pts'],.45)['bbox']
                elif failure=='short_outside':seg['rows'][-3]['bbox']=row(.5,.5)['bbox']
                elif failure=='gap':seg['rows']=[r for r in seg['rows'] if r['pts'] not in [.3,.4]]
                elif failure=='jump':
                    for r in seg['rows'][-3:]:r['bbox']=row(r['pts'],.3)['bbox']
                elif failure=='scale':seg['rows'][4]['bbox']=[.49,.495,.51,.505]
                else:sc['zones']['inside']=[[.4,0],[1,0],[1,1],[.4,1]]
                self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])

    def test_outward_future_rows_cannot_complete_stability(self):
        source,seg,sc=inputs('inside_to_outside');source.update(pts=.6,decision_time_pts=.6)
        self.assertFalse(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])

    def test_outward_future_append_does_not_change_decision(self):
        source,seg,sc=inputs('inside_to_outside');before=visible_crossing_decision(source,seg,sc)
        seg['rows'] += [row(.8,.44),row(.9,.43)]
        self.assertEqual(before,visible_crossing_decision(source,seg,sc))

    def test_outward_line_extension_crossing_rejected(self):
        source,seg,sc=inputs('inside_to_outside')
        for r in seg['rows']:r['bbox']=row(r['pts'],sum(r['bbox'][::2])/2,.8)['bbox']
        result=visible_crossing_decision(source,seg,sc)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'no_observed_finite_gate_crossing')

    def test_inward_finite_crossing_cannot_support_outward_extension_crossings(self):
        source,seg,sc=inputs('inside_to_outside')
        positions=[(.46,.8),(.47,.8),(.48,.8),(.505,.8),(.505,.76),
                   (.505,.72),(.505,.69),(.495,.69),(.495,.73),
                   (.495,.77),(.495,.8),(.52,.8),(.53,.8),(.54,.8)]
        seg['rows']=[row(i/10,1-x,y) for i,(x,y) in enumerate(positions)]
        source.update(pts=1.3,decision_time_pts=1.3)
        result=visible_crossing_decision(source,seg,sc)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'no_observed_finite_gate_crossing')

    def test_reversing_line_does_not_change_outward_meaning(self):
        source,seg,sc=inputs('inside_to_outside');sc['line'].reverse()
        self.assertTrue(visible_crossing_decision(source,seg,sc)['automatic_confirmation'])


if __name__=='__main__':unittest.main()
