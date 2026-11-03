"""Saved-point continuation safety tests; no image inference or accuracy claims."""
from copy import deepcopy
import unittest

from sceneguard.approach_disappearance import zone
from sceneguard.gate_observation import GateObservationDirection


def scene():
    return dict(source_size=[1000,1000],line=[[.5,.15],[.5,.75]],
        approach_polygon=[[.3,.1],[.7,.1],[.7,.9],[.3,.9]],
        zones={'outside':[[0,0],[.45,0],[.45,1],[0,1]],
               'inside':[[.55,0],[1,0],[1,1],[.55,1]]},
        directions=['outside_to_inside','inside_to_outside'])


def fixture(xs=None, point_xs=None, bottom=.55):
    xs=xs or [440,450,460,480,500,520,540,550,560,560,560,560,560]
    point_xs=point_xs or xs
    frames=[];rows=[]
    for i,(x,px) in enumerate(zip(xs,point_xs)):
        t=i/10;box=[(x-35)/1000,bottom-.2,(x+35)/1000,bottom]
        detection=dict(cache_index=0,bbox=box,score=.8,observed=True,
                       track_ids=[7 if i<=2 else 19],assignment='confirmed_track')
        path=dict(window_id='w1',seed_pts=0.,seed_cache_index=0,seed_track_ids=[7],
                  point_ids=[0,1,2,3],
                  points_original_pixels=[[px,bottom*1000-40+j*5] for j in range(4)])
        frames.append(dict(pts=t,frame_index=i,camera_step_pixels=[0.,0.],
                           actual_boxes=[detection],point_paths=[path]))
        if i<=2:rows.append(dict(pts=t,frame_index=i,cache_index=0,bbox=deepcopy(box)))
    segment=dict(id='s1',raw_id=7,rows=rows)
    event=dict(segment='s1',raw_id=7,decision_time_pts=frames[-1]['pts'],last_observed_pts=.2,
               status='침입 의심',reason='recent_gate_presence_then_loss')
    return frames,segment,event


class GateObservationTests(unittest.TestCase):
    def test_coherent_boxes_cross_finite_gate_and_stabilize(self):
        frames,segment,_=fixture();engine=GateObservationDirection(frames,scene())
        result=engine.observed_crossing(segment,7)
        self.assertIsNotNone(result)
        self.assertTrue(result['automatic_confirmation'])
        self.assertEqual(result['rule_id'],'observed_gate_continuation_v1')
        self.assertEqual(result['direction'],'outside_to_inside')
        self.assertEqual(result['decision_time_pts'],.7)
        self.assertLessEqual(result['last_observed_pts'],.7)
        self.assertFalse(result['human_verified'])

    def test_mirrored_coherent_crossing_supports_enabled_outward_direction(self):
        frames,segment,_=fixture([560,550,540,520,500,480,460,450,440,440,440,440,440])
        result=GateObservationDirection(frames,scene()).observed_crossing(segment,7)
        self.assertIsNotNone(result)
        self.assertEqual(result['direction'],'inside_to_outside')

    def test_static_box_point_jitter_cannot_confirm(self):
        frames,segment,_=fixture([500]*13,[497,497,497,503,497,497,497,497,497,497,497,497,497])
        engine=GateObservationDirection(frames,scene())
        for index in (3,4,7,12):
            with self.subTest(index=index):self.assertIsNone(engine.observed_crossing(segment,index))

    def test_point_crossing_inside_static_box_cannot_confirm_even_with_dwell(self):
        frames,segment,_=fixture([500]*13,[490,490,490,510,510,510,510,510,510,510,510,510,510])
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,12))

    def test_future_boxes_cannot_complete_destination_dwell(self):
        frames,segment,_=fixture()
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,6))

    def test_destination_dwell_cannot_pool_alternating_point_cohorts(self):
        frames,segment,_=fixture()
        for i,frame in enumerate(frames[3:],3):
            frame['point_paths'][0]['points_original_pixels'][i%4][0]=900
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,12))

    def test_future_append_cannot_change_current_decision(self):
        frames,segment,_=fixture();before=GateObservationDirection(frames[:8],scene()).continuation_details(segment,7)
        after=GateObservationDirection(frames,scene()).continuation_details(segment,7)
        self.assertEqual(before,after)

    def test_expired_path_cache_and_rewind_match_fresh_calculation(self):
        frames,segment,_=fixture()
        for frame in frames[8:]:frame['point_paths']=[];frame['actual_boxes']=[]
        engine=GateObservationDirection(frames,scene());engine.continuation_details(segment,7)
        self.assertEqual(engine.continuation_details(segment,12),
            GateObservationDirection(frames,scene()).continuation_details(segment,12))
        self.assertEqual(engine.continuation_details(segment,6),
            GateObservationDirection(frames[:7],scene()).continuation_details(segment,6))

    def test_measured_boxes_crossing_line_extension_rejected(self):
        frames,segment,_=fixture(bottom=.9)
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,12))

    def test_finite_point_crossing_cannot_replace_box_path_across_extension(self):
        frames,segment,_=fixture(bottom=.78)
        for frame in frames:
            for j,p in enumerate(frame['point_paths'][0]['points_original_pixels']):p[1]=700+j*5
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,12))

    def test_one_crossing_point_outlier_does_not_confirm(self):
        frames,segment,_=fixture([500]*13,[497]*13)
        for frame in frames[3:]:frame['point_paths'][0]['points_original_pixels'][0][0]=520
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,12))

    def test_camera_pan_cannot_supply_corrected_crossing_motion(self):
        frames,segment,_=fixture()
        for a,b in zip(frames,frames[1:]):
            ax=a['point_paths'][0]['points_original_pixels'][0][0]
            bx=b['point_paths'][0]['points_original_pixels'][0][0]
            b['camera_step_pixels']=[bx-ax,0.]
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,12))

    def test_missing_source_frame_breaks_crossing_proof(self):
        frames,segment,_=fixture();frames=[f for f in frames if f['frame_index']!=4]
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,12))

    def test_missing_point_path_cannot_be_interpolated_across_gate(self):
        frames,segment,_=fixture();frames[4]['point_paths']=[]
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,12))

    def test_unmeasured_destination_boxes_cannot_complete_dwell(self):
        frames,segment,_=fixture()
        for f in frames[5:]:f['actual_boxes'][0]['observed']=False
        self.assertIsNone(GateObservationDirection(frames,scene()).observed_crossing(segment,12))

    def test_same_side_endpoint_is_retained_without_polygon_membership(self):
        frames,segment,event=fixture([440,450,460]+[470]*10)
        self.assertIsNone(zone(dict(bbox=frames[-1]['actual_boxes'][0]['bbox']),scene()))
        engine=GateObservationDirection(frames,scene());details=engine.continuation_details(segment,12)
        self.assertEqual(details['status'],'same_side_continuation')
        self.assertTrue(details['current_endpoint_observed'])
        result=engine.classify(event,segment)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'id_ended_but_observation_continues')

    def test_normal_outside_approach_then_turnback_is_not_confirmation(self):
        frames,segment,event=fixture([440,450,460,480,490,480,470,460,450,440,440,440,440])
        engine=GateObservationDirection(frames,scene())
        self.assertIsNone(engine.observed_crossing(segment,12))
        self.assertFalse(engine.classify(event,segment)['automatic_confirmation'])

    def test_strong_endpoint_with_unclear_side_is_not_disappearance(self):
        frames,segment,event=fixture([440,450,460]+[500]*10,[440,450,460]+[500]*10)
        engine=GateObservationDirection(frames,scene());details=engine.continuation_details(segment,12)
        self.assertEqual(details['status'],'boundary_unclear_continuation')
        self.assertEqual(engine.continuation(segment,12),'boundary_unclear_continuation')
        result=engine.classify(event,segment)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['continuation_assessment']['status'],'boundary_unclear_continuation')

    def test_recent_bound_box_cannot_count_as_full_absence_since_id_ended(self):
        frames,segment,event=fixture([440,450,460]+[500]*10,[440,450,460]+[500]*10)
        frames[-1]['actual_boxes']=[]
        engine=GateObservationDirection(frames,scene())
        self.assertEqual(engine.continuation_details(segment,12)['status'],'recent_bound_continuation')
        self.assertFalse(engine.classify(event,segment)['automatic_confirmation'])

    def test_unrelated_inside_person_does_not_block_source_loss(self):
        frames,segment,event=fixture()
        for f in frames[3:]:
            f['actual_boxes']=[dict(cache_index=1,bbox=[.7,.35,.8,.55],score=.9,observed=True,track_ids=[99])]
            f['point_paths']=[]
        result=GateObservationDirection(frames,scene()).classify(event,segment)
        self.assertTrue(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'inward_motion_then_gate_loss')
        self.assertEqual(result['continuation_assessment']['status'],'unresolved')

    def test_disabled_outward_direction_cannot_confirm(self):
        frames,segment,_=fixture([560,550,540,520,500,480,460,450,440,440,440,440,440])
        config=scene();config['directions']=['outside_to_inside']
        self.assertIsNone(GateObservationDirection(frames,config).observed_crossing(segment,12))

    def test_source_inputs_and_cached_details_are_immutable(self):
        frames,segment,event=fixture();config=scene();snapshot=deepcopy((frames,segment,event,config))
        engine=GateObservationDirection(frames,config)
        details=engine.continuation_details(segment,7);details['status']='tampered'
        self.assertNotEqual(engine.continuation_details(segment,7)['status'],'tampered')
        engine.observed_crossing(segment,7);engine.classify(event,segment)
        self.assertEqual((frames,segment,event,config),snapshot)


if __name__=='__main__':unittest.main()
