import copy
import math
import unittest
from sceneguard.approach_disappearance import analyze, Policy, angle_degrees, angle_audit, motion
from sceneguard.appearance_support import parse_comparison, link_proposals


def scene():
    return {'source_size':[1000,500],'line':[[.5,.1],[.5,.9]],
        'approach_polygon':[[.2,.1],[.8,.1],[.8,.9],[.2,.9]],
        'zones':{'outside':[[0,0],[.48,0],[.48,1],[0,1]],
                 'inside':[[.52,0],[1,0],[1,1],[.52,1]]},
        'directions':['outside_to_inside','inside_to_outside'],
        'occlusions':[{'id':'gate','from_side':'outside','to_side':'inside',
                      'polygon':[[.4,.2],[.51,.2],[.51,.8],[.4,.8]]}]}


def d(x, tid=1, observed=True, y=.5):
    return {'track_id':tid,'observed':observed,'confirmed':True,
            'bbox':[x-.02,y-.1,x+.02,y+.1],'score':.9,'cache_index':0}


def frames(xs, empty=15, tid=1):
    return [{'pts':i*.1,'detections':[d(x,tid)]} for i,x in enumerate(xs)]+[
            {'pts':(len(xs)+i)*.1,'detections':[]} for i in range(empty)]


class RulesTests(unittest.TestCase):
    def test_directed_occlusion_loss_is_suspicion_without_reappearance(self):
        r=analyze(frames([.30,.31,.33,.35,.37,.39,.41,.43,.45,.47]),scene())
        self.assertEqual(r['losses'][0]['status'],'침입 의심')
        self.assertFalse(r['events'][0]['reappearance_required'])

    def test_unknown_occlusion_does_not_fabricate_intrusion(self):
        s=scene();s['occlusions']=[]
        r=analyze(frames([.30,.32,.34,.36,.38,.40,.42,.44,.46,.47]),s)
        self.assertEqual(r['losses'][0]['status'],'판단 불가')

    def test_stationary_disappearance_not_intrusion(self):
        r=analyze(frames([.46]*12),scene())
        self.assertFalse(r['events'])
        self.assertFalse(r['losses'][0]['motion']['reliable'])

    def test_motion_away_from_gate_does_not_trigger(self):
        r=analyze(frames([.47,.465,.46,.455,.45,.445,.44]),scene())
        self.assertFalse(r['events'])

    def test_same_side_exit_is_normal_only_when_observed(self):
        r=analyze(frames([.10,.12,.15,.25,.30,.35,.30,.25,.15,.10]),scene())
        self.assertTrue(any(e['status']=='침입 아님' for e in r['events']))
        self.assertEqual(r['losses'][0]['reason'],'observed_exit_not_disappearance')

    def test_cross_then_return_does_not_erase_prior_alarm(self):
        xs=[.30]*4+[.40,.46,.54]+[.60]*4+[.46]+[.35]*4+[.10]
        r=analyze(frames(xs),scene())
        self.assertTrue(any(e['status']=='침입 의심' for e in r['events']))
        self.assertFalse(any(e['status']=='침입 아님' for e in r['events']))

    def test_end_of_recording_is_not_disappearance(self):
        r=analyze(frames([.30,.34,.38,.42,.46],empty=1),scene())
        self.assertTrue(r['losses'][0]['right_censored'])
        self.assertFalse(r['events'])

    def test_prediction_only_boxes_are_ignored(self):
        fs=frames([.30]*5)
        for f in fs[5:]:
            f['detections']=[d(.46,observed=False)]
            f['states']=[{'state':'lost_prediction','prediction_bbox':[.5,.5,.7,.7]}]
        r=analyze(fs,scene())
        self.assertEqual(len(r['segments'][0]['rows']),5)
        self.assertFalse(r['events'])

    def test_single_missing_frame_does_not_split(self):
        fs=frames([.3,.32,.34,.36,.38,.4],empty=0)
        fs[3]['detections']=[]
        r=analyze(fs,scene())
        self.assertEqual(len(r['segments']),1)

    def test_new_id_is_pair_not_auto_identity(self):
        fs=frames([.3,.32,.34,.36,.38,.4,.42,.44,.46],empty=2)
        start=len(fs)
        fs += [{'pts':(start+i)*.1,'detections':[d(.6,tid=9)]} for i in range(5)]
        r=analyze(fs,scene())
        self.assertTrue(r['pairs'])
        self.assertFalse(r['pairs'][0]['identity_verified'])
        self.assertTrue(r['losses'][0]['id_fragmentation_possible'])

    def test_backward_pair_retained_despite_angle(self):
        fs=frames([.30,.32,.34,.36,.38,.4,.42,.44,.46],empty=2)
        start=len(fs)
        fs += [{'pts':(start+i)*.1,'detections':[d(.38,tid=9)]} for i in range(5)]
        r=analyze(fs,scene())
        self.assertTrue(r['pairs'])
        self.assertFalse(r['pairs'][0]['in_forward_90'])

    def test_finite_line_extension_does_not_trigger(self):
        s=scene();s['line']=[[.5,.01],[.5,.05]]
        r=analyze(frames([.3,.32,.34,.36,.38,.4,.42,.44,.46]),s)
        self.assertFalse(r['events'])

    def test_large_bbox_change_is_not_direction_evidence(self):
        rows=[{'pts':i*.1,'bbox':[.4,.3,.5,.4 if i%2 else .8]} for i in range(8)]
        m=motion(rows,[1000,500],Policy())
        self.assertFalse(m['reliable'])
        self.assertGreater(m['rejected_steps'],0)

    def test_nonmonotonic_time_rejected(self):
        fs=frames([.3]*5);fs[2]['pts']=0
        with self.assertRaises(ValueError):analyze(fs,scene())

    def test_invalid_scene_rejected(self):
        s=scene();s['line']=[[.5,.5],[.5,.5]]
        with self.assertRaises(ValueError):analyze(frames([.3]*5),s)

    def test_short_direction_is_unknown_not_zero_angle(self):
        self.assertIsNone(angle_degrees([0,0],[3,4]))
        self.assertAlmostEqual(angle_degrees([1,0],[0,1]),90)

    def test_only_human_verified_same_matches_enter_angle_audit(self):
        pairs=[{'pair_id':'p1','angle_degrees':30,'in_forward_90':True},
               {'pair_id':'p2','angle_degrees':170,'in_forward_90':False}]
        a=angle_audit(pairs,{'p1':'same','p2':'unknown'})
        self.assertEqual(a['direction_available'],1)
        self.assertEqual(a['within_90_fraction'],1)
        self.assertIsNone(angle_audit(pairs,{})['within_90_fraction'])


class AppearanceTests(unittest.TestCase):
    good='{"upper":"match","lower":"unavailable","bag":"match","decision":"compatible"}'
    def test_hidden_lower_is_excluded_not_different(self):
        self.assertTrue(parse_comparison(self.good)['valid'])
        self.assertFalse(parse_comparison(self.good)['identity_verified'])

    def test_all_hidden_cannot_be_compatible(self):
        s='{"upper":"unavailable","lower":"unavailable","bag":"unavailable","decision":"compatible"}'
        self.assertFalse(parse_comparison(s)['valid'])

    def test_hidden_parts_cannot_support_difference(self):
        s='{"upper":"unavailable","lower":"unavailable","bag":"unavailable","decision":"different"}'
        self.assertFalse(parse_comparison(s)['valid'])

    def test_conflicting_part_and_decision_rejected(self):
        self.assertFalse(parse_comparison(self.good.replace('"lower":"unavailable"','"lower":"different"'))['valid'])

    def test_fence_removed_without_semantic_repair(self):
        self.assertTrue(parse_comparison('```json\n'+self.good+'\n```')['valid'])

    def test_duplicate_keys_and_wrong_output_rejected(self):
        self.assertFalse(parse_comparison('{"upper":"match","upper":"different"}')['valid'])
        self.assertFalse(parse_comparison('yes same person')['valid'])

    def test_mutual_unique_one_to_one_proposal_only(self):
        ps=[{'pair_id':'ab','before':'a','after':'b','in_forward_90':False}]
        result=link_proposals(ps,{'ab':self.good})
        self.assertEqual(result[0]['link_status'],'review_link_proposed')
        self.assertFalse(result[0]['identity_verified'])

    def test_two_targets_not_forcibly_joined(self):
        ps=[{'pair_id':'ab','before':'a','after':'b'}, {'pair_id':'ac','before':'a','after':'c'}]
        result=link_proposals(ps,{'ab':self.good,'ac':self.good})
        self.assertTrue(all(r['link_status']=='ambiguous_not_linked' for r in result))

    def test_two_sources_not_forcibly_joined(self):
        ps=[{'pair_id':'ab','before':'a','after':'b'}, {'pair_id':'cb','before':'c','after':'b'}]
        result=link_proposals(ps,{'ab':self.good,'cb':self.good})
        self.assertTrue(all(r['link_status']=='ambiguous_not_linked' for r in result))

    def test_invalid_response_stays_unknown(self):
        ps=[{'pair_id':'ab','before':'a','after':'b'}]
        self.assertEqual(link_proposals(ps,{'ab':'bad'})[0]['link_status'],'unresolved')


class AdditionalRulesTests(unittest.TestCase):
    def test_pixel_aspect_ratio_used_for_angle(self):
        fs=frames([.30,.31,.32,.33,.34,.35,.36,.37],empty=0)
        for i,f in enumerate(fs):
            f['detections'][0]=d(.3+i*.01,y=.3+i*.01)
        r=analyze(fs,scene())
        vx,vy=r['losses'][0]['motion']['velocity_pixels_per_second']
        self.assertAlmostEqual(vx/vy,2.)

    def test_cross_in_nonalarm_direction_then_return_not_normalized_away(self):
        s=scene();s['directions']=['outside_to_inside']
        xs=[.65]*4+[.54,.46]+[.4]*4+[.55]+[.65]*4+[.9]
        r=analyze(frames(xs),s)
        self.assertFalse(any(e['status']=='침입 아님' for e in r['events']))

    def test_gap_before_return_cannot_be_verified_normal(self):
        fs=frames([.1,.15,.25,.3,.35,.3,.25,.15],empty=0)
        for i in (4,5):fs[i]['detections']=[]
        r=analyze(fs,scene())
        self.assertFalse(any(e['status']=='침입 아님' for e in r['events']))

    def test_unknown_audit_pair_rejected(self):
        with self.assertRaises(ValueError):angle_audit([],{'madeup':'same'})

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):analyze(frames([.3]*3),scene(),Policy(loss_wait=-1))

if __name__=='__main__':unittest.main()
