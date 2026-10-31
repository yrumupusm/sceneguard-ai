import json
import math
import unittest
from copy import deepcopy

from sceneguard.directional_loss import (DirectionPolicy, gate_geometry, vectors_direction,
    SavedGateDirection, annotated_bundle, gate_distance, path_map)
from sceneguard.exp0044_application import evaluate


def scene():
    return dict(source_size=[1000,800],line=[[.5,.1],[.5,.9]],
        zones={'outside':[[.1,.1],[.45,.1],[.45,.9],[.1,.9]],
               'inside':[[.55,.1],[.9,.1],[.9,.9],[.55,.9]]})


def fixture(dx=20, end=False, cross=False, near=True):
    times=[0.,.25,.5,1.,1.5]; frames=[]; rows=[]
    initial=440 if near else 100
    # Coordinate space: original 1000 x 800 pixels, including a partial-body bbox.
    for i,t in enumerate(times):
        x=initial+dx*min(t/.5,1)
        pts=[[x,300],[x+2,310],[x+4,320],[x+6,330]]
        b=[(x-15)/1000,.35,(x+20)/1000,.55]
        boxes=[]; paths=[]
        if i<=2:
            boxes=[dict(cache_index=0,bbox=b,score=.8,track_ids=[7],assignment='confirmed_track')]
            rows.append(dict(pts=t,frame_index=i,cache_index=0,bbox=b))
        if i<=2 or end:
            if i>2 and cross:
                pts=[[550,300],[552,310],[554,320],[556,330]]
                b=[.53,.35,.58,.55]
            paths=[dict(window_id='w1',seed_pts=0.,seed_cache_index=0,seed_track_ids=[7],
                        point_ids=[0,1,2,3],points_original_pixels=pts)]
        if i>2 and end:
            boxes=[dict(cache_index=0,bbox=b,score=.8,track_ids=[19],assignment='confirmed_track')]
        frames.append(dict(pts=t,frame_index=i,camera_step_pixels=[0.,0.],
                           actual_boxes=boxes,point_paths=paths))
    segment=dict(id='s1',raw_id=7,rows=rows)
    event=dict(segment='s1',raw_id=7,decision_time_pts=1.5,last_observed_pts=.5,
               status='침입 의심',reason='recent_gate_presence_then_loss')
    return frames,segment,event


def normalized(eid, at, reason='recent_gate_presence_then_loss', raw=7):
    return dict(event_id=eid,decision_time_pts=at,track_ids=[raw],status='침입 의심',
        source_ref={'source_pointer':'/events/'+eid,'collection':'events'},
        source_event={'reason':reason})


def fake_group(events,review):
    """Contract double only; real repository UI/grouping is a local integration task."""
    timeline=[]; card=dict(incident_id='stable',event_ids=[],notification_eligible=False)
    for e in events:
        card['event_ids'].append(e['event_id'])
        card['notification_eligible'] |= e['event_id'] not in review
        timeline.append(dict(card=deepcopy(card),decision_time_pts=e['decision_time_pts']))
    return dict(events=deepcopy(events),cards=[deepcopy(card)],timeline=timeline,
                counts={'candidate_cards':1},review_only_events=[e for e in events if e['event_id'] in review])


class GeometryTests(unittest.TestCase):
    def test_inward_orientation_not_endpoint_order(self):
        s=scene(); g=gate_geometry(s); s['line'].reverse()
        self.assertEqual(g['inward_normal'],gate_geometry(s)['inward_normal'])

    def test_inward(self):
        self.assertEqual(vectors_direction([(10,0)]*4,gate_geometry(scene()))['direction'],'inward')

    def test_outward(self):
        self.assertEqual(vectors_direction([(-10,0)]*4,gate_geometry(scene()))['direction'],'outward')

    def test_parallel(self):
        self.assertEqual(vectors_direction([(0,10)]*4,gate_geometry(scene()))['direction'],'parallel')

    def test_static(self):
        self.assertEqual(vectors_direction([(0,0)]*10,gate_geometry(scene()))['direction'],'unknown')

    def test_stationary_gate_residue_not_motion_vote(self):
        r=vectors_direction([(0,0)]*40+[(10,0)]*4,gate_geometry(scene()))
        self.assertEqual(r['direction'],'inward'); self.assertEqual(r['moving_points'],4)

    def test_opposing_people_not_confirmed_by_net_zero(self):
        r=vectors_direction([(10,0)]*4+[(-10,0)]*4,gate_geometry(scene()))
        self.assertEqual(r['direction'],'unknown')

    def test_outlier_trim(self):
        r=vectors_direction([(10,0)]*19+[(-9000,0)],gate_geometry(scene()))
        self.assertEqual(r['direction'],'inward')

    def test_too_few_points_keeps_unknown(self):
        self.assertEqual(vectors_direction([(10,0)]*2,gate_geometry(scene()))['direction'],'unknown')

    def test_missing_side_is_not_guessed(self):
        s=scene(); s['zones']={}
        self.assertEqual(vectors_direction([(10,0)]*4,gate_geometry(s))['direction'],'unknown')

    def test_swapping_inside_outside_reverses_direction(self):
        s=scene(); s['zones']['inside'],s['zones']['outside']=s['zones']['outside'],s['zones']['inside']
        self.assertEqual(vectors_direction([(10,0)]*4,gate_geometry(s))['direction'],'outward')

    def test_diagonal_inward(self):
        s=scene(); s['line']=[[.2,.2],[.8,.8]]
        g=gate_geometry(s); n=g['inward_normal']
        r=vectors_direction([(n[0]*10,n[1]*10)]*4,g)
        self.assertEqual(r['direction'],'inward')

    def test_finite_segment_not_infinite_line(self):
        self.assertGreater(gate_distance((500,790),gate_geometry(scene())),60)

    def test_bad_line_rejected(self):
        s=scene(); s['line']=[[.5,.5],[.5,.5]]
        with self.assertRaises(ValueError): gate_geometry(s)

    def test_duplicate_point_id_rejected(self):
        with self.assertRaises(ValueError):
            path_map(dict(point_ids=[1,1],points_original_pixels=[[0,0],[1,1]]))

    def test_invalid_policy(self):
        with self.assertRaises(ValueError): DirectionPolicy(normal_pixels=0).validate()


class LossTests(unittest.TestCase):
    def classify(self,dx=20,end=False,cross=False,near=True):
        frames,seg,event=fixture(dx,end,cross,near)
        return SavedGateDirection(frames,scene()).classify(event,seg)

    def test_inward_gate_loss_auto_confirmation(self):
        r=self.classify(); self.assertEqual(r['status'],'침입 확인')
        self.assertTrue(r['automatic_confirmation']); self.assertTrue(r['notify'])
        self.assertFalse(r['human_verified'])

    def test_outward_loss_still_suspicion(self):
        r=self.classify(-20); self.assertEqual(r['status'],'침입 의심'); self.assertTrue(r['notify'])

    def test_ambiguous_direction_still_suspicion(self):
        r=self.classify(0); self.assertEqual(r['status'],'침입 의심'); self.assertTrue(r['notify'])

    def test_actual_id_replacement_is_not_disappearance(self):
        r=self.classify(end=True)
        self.assertFalse(r['notify']); self.assertFalse(r['automatic_confirmation'])
        self.assertEqual(r['reason'],'id_ended_but_observation_continues')

    def test_visible_crossing_is_not_cancelled(self):
        r=self.classify(end=True,cross=True)
        self.assertTrue(r['notify']); self.assertEqual(r['continuation'],'cross_side_observation')

    def test_far_away_not_auto_confirmed(self):
        r=self.classify(near=False); self.assertEqual(r['status'],'침입 의심')

    def test_end_of_clip_not_disappearance(self):
        f,s,e=fixture(); r=SavedGateDirection(f[:-1],scene()).classify(e,s)
        self.assertFalse(r['notify']); self.assertEqual(r['reason'],'loss_wait_not_observed')

    def test_wait_must_really_elapse(self):
        f,s,e=fixture(); e['decision_time_pts']=1.
        self.assertFalse(SavedGateDirection(f,scene()).classify(e,s)['notify'])

    def test_no_saved_paths_keeps_candidate(self):
        f,s,e=fixture()
        for r in f:r['point_paths']=[]
        out=SavedGateDirection(f,scene()).classify(e,s)
        self.assertTrue(out['notify']); self.assertEqual(out['status'],'침입 의심')

    def test_window_expiry_does_not_create_candidate(self):
        f,s,e=fixture(); engine=SavedGateDirection(f,scene())
        self.assertFalse(hasattr(engine,'events'))  # existing real loss candidate required

    def test_background_points_without_endpoint_person_do_not_cancel(self):
        f,s,e=fixture(end=True)
        f[-1]['actual_boxes']=[]
        self.assertTrue(SavedGateDirection(f,scene()).classify(e,s)['notify'])

    def test_other_person_nearby_is_not_visibility_proof(self):
        f,s,e=fixture(end=True)
        f[-1]['actual_boxes']=[dict(cache_index=1,bbox=[.6,.3,.7,.6],score=.9,track_ids=[20])]
        self.assertTrue(SavedGateDirection(f,scene()).classify(e,s)['notify'])

    def test_prediction_box_cannot_cancel(self):
        f,s,e=fixture(end=True); f[-1]['actual_boxes'][0]['observed']=False
        self.assertTrue(SavedGateDirection(f,scene()).classify(e,s)['notify'])

    def test_same_ids_only_no_real_points_still_suspicion(self):
        f,s,e=fixture(); f[-1]['actual_boxes']=deepcopy(f[2]['actual_boxes'])
        # A new box alone is not a correspondence with the lost target.
        self.assertTrue(SavedGateDirection(f,scene()).classify(e,s)['notify'])

    def test_shrinking_point_set_no_centroid_motion(self):
        f,s,e=fixture(dx=0)
        f[2]['point_paths'][0]['point_ids']=[1,2,3]
        f[2]['point_paths'][0]['points_original_pixels']=f[2]['point_paths'][0]['points_original_pixels'][1:]
        self.assertEqual(SavedGateDirection(f,scene()).classify(e,s)['direction']['direction'],'unknown')

    def test_camera_motion_subtracted(self):
        f,s,e=fixture(dx=20)
        f[1]['camera_step_pixels']=[10,0]; f[2]['camera_step_pixels']=[10,0]
        self.assertEqual(SavedGateDirection(f,scene()).classify(e,s)['direction']['direction'],'unknown')

    def test_late_reappearance_not_used(self):
        f,s,e=fixture(); before=SavedGateDirection(f,scene()).classify(e,s)
        extra=deepcopy(f[-1]); extra.update(pts=2.,frame_index=5)
        extra['actual_boxes']=deepcopy(f[2]['actual_boxes']); f.append(extra)
        self.assertEqual(before,SavedGateDirection(f,scene()).classify(e,s))

    def test_remaining_half_of_mixed_box_does_not_cancel_loss(self):
        f,s,e=fixture(end=True)
        for row in f:
            if row['point_paths']:
                path=row['point_paths'][0]
                path['point_ids'] += [4,5,6,7]
                path['points_original_pixels'] += [[p[0],p[1]+5] for p in path['points_original_pixels'][:4]]
        # Half the anchor points vanish; remaining nearby points cannot prove
        # that everybody represented by a merged box stayed visible.
        f[-1]['point_paths'][0]['point_ids']=f[-1]['point_paths'][0]['point_ids'][:4]
        f[-1]['point_paths'][0]['points_original_pixels']=f[-1]['point_paths'][0]['points_original_pixels'][:4]
        self.assertTrue(SavedGateDirection(f,scene()).classify(e,s)['notify'])

    def test_direction_never_averages_unrelated_window(self):
        f,s,e=fixture()
        for i in range(3):
            row=f[i]
            row['actual_boxes'].append(dict(cache_index=1,bbox=[.7,.2,.8,.6],score=.9,track_ids=[90]))
            row['point_paths'].append(dict(window_id='other',seed_pts=0.,seed_cache_index=1,
                point_ids=[0,1,2,3],points_original_pixels=[[750-i*10,300+j*10] for j in range(4)]))
        self.assertEqual(SavedGateDirection(f,scene()).classify(e,s)['direction']['direction'],'inward')

    def test_no_manual_status_change(self):
        f,s,e=fixture(); original=deepcopy((f,s,e))
        json.dumps(SavedGateDirection(f,scene()).classify(e,s),allow_nan=False)
        self.assertEqual((f,s,e),original)


class BundleContractTests(unittest.TestCase):
    def test_original_payloads_and_events_kept(self):
        b={'events':[normalized('a',1)]}; old=deepcopy(b)
        d=[dict(event_id='a',notify=True,automatic_confirmation=True,decision_time_pts=1)]
        p=annotated_bundle(b,d,fake_group)
        self.assertEqual(b,old); self.assertEqual(p['events'],b['events'])
        self.assertEqual(p['cards'][0]['automatic_status'],'침입 확인')

    def test_no_future_confirmation_in_snapshot(self):
        b={'events':[normalized('a',1),normalized('b',2)]}
        d=[dict(event_id='b',notify=True,automatic_confirmation=True,decision_time_pts=2)]
        p=annotated_bundle(b,d,fake_group)
        self.assertFalse(p['timeline'][0]['card']['automatic_confirmation'])
        self.assertTrue(p['timeline'][1]['card']['automatic_confirmation'])

    def test_other_person_alert_is_kept(self):
        b={'events':[normalized('a',1),normalized('b',1.1,raw=9)]}
        d=[dict(event_id='a',notify=False,automatic_confirmation=False,decision_time_pts=1)]
        p=annotated_bundle(b,d,fake_group)
        self.assertEqual([e['event_id'] for e in p['review_only_events']],['a'])
        self.assertTrue(p['cards'][0]['notification_eligible'])

    def test_independent_crossing_prevents_cancel(self):
        b={'events':[normalized('x',.5,'boundary_crossing'),normalized('a',1)]}
        d=[dict(event_id='a',notify=False,automatic_confirmation=False,decision_time_pts=1)]
        self.assertEqual(annotated_bundle(b,d,fake_group)['review_only_events'],[])

    def test_future_crossing_not_a_past_protection(self):
        b={'events':[normalized('a',1),normalized('x',2,'boundary_crossing')]}
        d=[dict(event_id='a',notify=False,automatic_confirmation=False,decision_time_pts=1)]
        p=annotated_bundle(b,d,fake_group)
        self.assertEqual([e['event_id'] for e in p['review_only_events']],['a'])

    def test_unknown_reference_rejected(self):
        with self.assertRaises(ValueError):
            annotated_bundle({'events':[]},[dict(event_id='x')],fake_group)

    def test_pure_application_uses_real_candidate_only(self):
        f,s,e=fixture(); ev=normalized('a',1.5); ev['source_event']=e
        baseline=dict(segments=[s],policy={'loss_wait':1.})
        bundle=dict(events=[ev],video_id='synthetic',source_window=[0,1.5])
        p=evaluate(baseline,bundle,f,scene(),fake_group)
        self.assertEqual(len(p['decisions']),1)
        self.assertEqual(p['decisions'][0]['status'],'침입 확인')
        self.assertFalse(p['live_notifications_enabled'])


if __name__=='__main__':unittest.main()
