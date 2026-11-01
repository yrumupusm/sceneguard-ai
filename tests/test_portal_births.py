"""Synthetic geometry/temporal tests with the unchanged EXP45 observation engine."""
from copy import deepcopy
import unittest
from sceneguard.portal_births import (PortalGate, PortalBirths, make_region,
    compare_births, validate_polygon, clipped_area, area, digest)
from sceneguard.gate_episode_evidence import Gate, EpisodePolicy


def scene():
    return dict(source_size=[1000,1000],line=[[.4,.7],[.6,.7]],
        zones=dict(inside=[[.35,.55],[.65,.55],[.65,.65],[.35,.65]],
                   outside=[[.3,.75],[.7,.75],[.7,.9],[.3,.9]]))

POLY=[[.4,.2],[.6,.2],[.6,.7],[.4,.7]]
HEAD=[.47,.3,.51,.34]

def config(s=None, poly=None):
    return make_region(s or scene(),'TEST',poly or POLY,
        reference_pts=0,note='Synthetic static gate, not a CCTV calibration')


def box(bbox=HEAD, tid=1, score=.9, observed=True, cache=0):
    return dict(bbox=list(bbox),track_ids=[tid],cache_index=cache,
                score=score,observed=observed)


def frame(i, boxes=()):
    return dict(pts=round(i*.1,8),frame_index=i,actual_boxes=list(boxes))


def sequence(assign, count=25):
    return [frame(i,assign.get(i,())) for i in range(count)]


def collect(frames, s=None, c=None):
    s=s or scene();engine=PortalBirths(s,c or config(s),'TEST')
    events=[]
    for f in frames:events.extend(engine.step(f))
    return events,engine


class GeometryTests(unittest.TestCase):
    def setUp(self):self.s=scene();self.c=config();self.g=PortalGate(self.s,self.c,'TEST')
    def test_partial_head_without_ground_membership(self):
        site=self.g.locate(HEAD)
        self.assertTrue(site['inside_birth_site'])
        self.assertFalse(site['legacy_ground_test']['inside_birth_site'])
        self.assertFalse(site['physical_inside_verified'])
    def test_center_inside(self):self.assertTrue(self.g.locate([.46,.4,.52,.48])['inside_birth_site'])
    def test_small_box_does_not_shrink_region(self):
        for size in (.001,.01,.1):
            self.assertTrue(self.g.locate([.5-size/2,.4-size/2,.5+size/2,.4+size/2])['inside_birth_site'])
    def test_large_box_only_touches_gate(self):self.assertFalse(self.g.locate([.1,.21,.41,.4])['inside_birth_site'])
    def test_edge_only_contact(self):
        r=self.g.locate([.2,.3,.4,.5]);self.assertFalse(r['inside_birth_site']);self.assertEqual(r['portal_box_overlap'],0)
    def test_far_inside(self):self.assertFalse(self.g.locate([.48,.05,.52,.1])['inside_birth_site'])
    def test_side_corridor(self):self.assertFalse(self.g.locate([.7,.3,.74,.4])['inside_birth_site'])
    def test_outside_walkway(self):self.assertFalse(self.g.locate([.47,.76,.51,.84])['inside_birth_site'])
    def test_finite_polygon_not_infinite_line(self):self.assertFalse(self.g.locate([.9,.61,.94,.65])['inside_birth_site'])
    def test_box_overlap_accepts_center_outside_concavity(self):
        p=[[.3,.3],[.7,.3],[.7,.7],[.55,.7],[.55,.45],[.45,.45],[.45,.7],[.3,.7]]
        r=PortalGate(self.s,config(poly=p),'TEST').locate([.3,.3,.7,.7])
        self.assertFalse(r['portal_center_inside']);self.assertGreater(r['portal_box_overlap'],.5)
        self.assertTrue(r['inside_birth_site'])
    def test_exact_rectangle_area(self):self.assertAlmostEqual(clipped_area([tuple(p) for p in POLY],[.45,.3,.55,.5]),.02)
    def test_polygon_inside_box(self):self.assertAlmostEqual(clipped_area([tuple(p) for p in POLY],[0,0,1,1]),.1)
    def test_concave_area(self):
        p=validate_polygon([[.2,.2],[.8,.2],[.8,.4],[.4,.4],[.4,.8],[.2,.8]])
        self.assertAlmostEqual(area(p),.20)
        self.assertAlmostEqual(clipped_area(p,[0,0,1,1]),.20)
    def test_clockwise_works(self):self.assertEqual(PortalGate(self.s,config(poly=list(reversed(POLY))),'TEST').locate(HEAD)['portal_box_overlap'],1)
    def test_nonbirth_geometry_unchanged(self):self.assertEqual(self.g.locate(HEAD,birth=False),Gate(self.s).locate(HEAD,birth=False))
    def test_scene_not_mutated(self):
        s=deepcopy(self.s);c=deepcopy(self.c);self.g.locate(HEAD);self.assertEqual(s,self.s);self.assertEqual(c,self.c)
    def test_size_binding(self):
        c=deepcopy(self.c);c['source_size']=[1920,1080]
        with self.assertRaises(ValueError):PortalGate(self.s,c,'TEST')
    def test_camera_binding(self):
        with self.assertRaises(ValueError):PortalGate(self.s,self.c,'OTHER')
    def test_scene_binding(self):
        s=deepcopy(self.s);s['line'][0][0]=.3
        with self.assertRaises(ValueError):PortalGate(s,self.c,'TEST')
    def test_nonfinite_vertex(self):
        with self.assertRaises(ValueError):validate_polygon([[.1,.1],[.2,float('nan')],[.3,.4]])
    def test_self_crossing(self):
        with self.assertRaises(ValueError):validate_polygon([[.1,.1],[.9,.9],[.1,.9],[.9,.1]])
    def test_collinear(self):
        with self.assertRaises(ValueError):validate_polygon([[.1,.1],[.2,.2],[.3,.3]])
    def test_repeated_vertex(self):
        with self.assertRaises(ValueError):validate_polygon(POLY+[POLY[0]])
    def test_pixel_coordinates_rejected(self):
        with self.assertRaises(ValueError):validate_polygon([[10,10],[20,10],[20,20]])
    def test_missing_config(self):
        with self.assertRaises(ValueError):PortalGate(self.s,{},'TEST')
    def test_negative_reference(self):
        with self.assertRaises(ValueError):make_region(self.s,'TEST',POLY,reference_pts=-1,note='x')
    def test_invalid_box(self):
        with self.assertRaises(ValueError):self.g.locate([.5,.3,.4,.4])
    def test_scaling(self):
        s=scene();s['source_size']=[1920,1080]
        self.assertEqual(PortalGate(s,config(s),'TEST').locate(HEAD)['inside_birth_site'],self.g.locate(HEAD)['inside_birth_site'])
    def test_line_reversal_no_birth_change(self):
        s=scene();s['line'].reverse()
        self.assertEqual(PortalGate(s,config(s),'TEST').locate(HEAD)['inside_birth_site'],self.g.locate(HEAD)['inside_birth_site'])
    def test_static_polygon_does_not_read_detection_id(self):
        self.assertEqual(self.g.locate(HEAD),self.g.locate(list(HEAD)))


class TemporalTests(unittest.TestCase):
    def test_real_birth_is_only_suspicion(self):
        events,_=collect(sequence({11:[box()],12:[box()],13:[box()]}))
        self.assertEqual(len(events),1);self.assertEqual(events[0]['status'],'침입 의심')
        self.assertFalse(events[0]['automatic_confirmation']);self.assertEqual(events[0]['birth_pts'],1.1)
        self.assertEqual(events[0]['decision_time_pts'],1.2)
    def test_frame_zero_is_not_a_birth(self):
        events,_=collect(sequence({i:[box()] for i in range(25)}));self.assertEqual(events,[])
    def test_one_frame_glint_not_supported(self):
        events,_=collect(sequence({11:[box()]}));self.assertEqual(events,[])
    def test_predicted_boxes_are_not_observations(self):
        events,_=collect(sequence({i:[box(observed=False)] for i in range(11,20)}));self.assertEqual(events,[])
    def test_low_score_unchanged(self):
        events,_=collect(sequence({i:[box(score=.2)] for i in range(11,20)}));self.assertEqual(events,[])
    def test_new_id_not_new_birth(self):
        events,_=collect(sequence({i:[box(tid=i)] for i in range(11,25)}));self.assertEqual(len(events),1)
    def test_short_detection_gap(self):
        events,_=collect(sequence({11:[box()],12:[box()],16:[box(tid=5)],17:[box(tid=5)]}))
        self.assertEqual(len(events),1)
    def test_source_gap_warms_up_again(self):
        data=sequence({},count=11)+[frame(i,[box()]) for i in range(15,25)]
        events,_=collect(data);self.assertEqual(events,[])
    def test_duplicate_box_not_two_births(self):
        events,_=collect(sequence({i:[box(),box(tid=9,cache=1)] for i in range(11,15)}))
        self.assertEqual(len(events),1)
    def test_prior_outside_approach_not_new_birth(self):
        a={}
        for i in range(5,25):
            x=min(.5,.31+(i-5)*.012)
            a[i]=[box([x-.035,.3,x+.035,.37],tid=i)]
        events,eng=collect(sequence(a));self.assertEqual(events,[]);self.assertEqual(len(eng.audit),1)
    def test_birth_moving_away_retains_first_site(self):
        events,_=collect(sequence({11:[box([.55,.3,.59,.34])],12:[box([.57,.3,.61,.34])],
                                   13:[box([.59,.3,.63,.34])]}))
        self.assertEqual(len(events),1);self.assertEqual(events[0]['first_actual_bbox'],[.55,.3,.59,.34])
    def test_bookkeeping_is_identical_across_geometry(self):
        frames=sequence({i:[box()] for i in range(11,25)})
        old=deepcopy(frames);r=compare_births(frames,scene(),config(),'TEST')
        self.assertEqual(frames,old);self.assertEqual(r['legacy_events'],[]);self.assertEqual(len(r['portal_events']),1)
    def test_inputs_and_config_not_mutated(self):
        frames=sequence({11:[box()],12:[box()]});s=scene();c=config();old=deepcopy((frames,s,c))
        compare_births(frames,s,c,'TEST');self.assertEqual(old,(frames,s,c))
    def test_two_spatially_distinct_births(self):
        b1=box([.42,.3,.45,.34]);b2=box([.55,.5,.58,.54],tid=2,cache=2)
        events,_=collect(sequence({11:[b1,b2],12:[b1,b2],13:[b1,b2]}));self.assertEqual(len(events),2)
    def test_future_changes_do_not_change_prefix(self):
        f=sequence({i:[box()] for i in range(11,25)})
        a,_=collect(f[:14]);b,_=collect(f);self.assertEqual(a,b)
    def test_outside_projection_cannot_be_safely_disambiguated(self):
        # An outside person whose footprint projects inside the polygon CAN trigger.
        # Keep this counterexample explicit, rather than claiming perfect rejection.
        events,_=collect(sequence({11:[box()],12:[box()]}))
        self.assertEqual(len(events),1);self.assertFalse(events[0]['birth_site']['physical_inside_verified'])
    def test_distinct_timestamps_required(self):
        eng=PortalBirths(scene(),config(),'TEST');eng.step(frame(0))
        with self.assertRaises(ValueError):eng.step(frame(0))
    def test_region_must_be_explicit_not_full_inside_fallback(self):
        c=config();del c['polygon']
        with self.assertRaises((ValueError,KeyError)):PortalBirths(scene(),c,'TEST')


class CandidateContractTests(unittest.TestCase):
    def setUp(self):
        from sceneguard.exp0046_application import normalize_portal
        self.normalize=normalize_portal
        self.raw=collect(sequence({11:[box()],12:[box()]}))[0][0]
        self.history=dict(video_id='SYNTHETIC',events=[dict(session_id='test-recording',camera_id='TEST',gate_id='door')])
    def test_normalization_preserves_evidence(self):
        before=deepcopy(self.raw);event=self.normalize(self.raw,self.history,config())
        self.assertEqual(self.raw,before);self.assertEqual(event['source_event'],before)
        self.assertEqual(event['track_ids'],[])
    def test_repeat_is_idempotent(self):
        self.assertEqual(self.normalize(self.raw,self.history,config()),self.normalize(self.raw,self.history,config()))
    def test_different_region_has_different_event_identity(self):
        c=config();d=deepcopy(c);d['provenance']['note']='Another calibration'
        self.assertNotEqual(self.normalize(self.raw,self.history,c)['event_id'],self.normalize(self.raw,self.history,d)['event_id'])
    def test_cannot_automatically_confirm_birth(self):
        self.raw['automatic_confirmation']=True
        with self.assertRaises(ValueError):self.normalize(self.raw,self.history,config())
    def test_future_ref_is_rejected(self):
        self.raw['observation_refs'][-1]['pts']=99
        with self.assertRaises(ValueError):self.normalize(self.raw,self.history,config())
    def test_mixed_cameras_rejected(self):
        self.history['events'].append(dict(session_id='test-recording',camera_id='OTHER',gate_id='door'))
        with self.assertRaises(ValueError):self.normalize(self.raw,self.history,config())
    def test_first_time_not_backdated(self):
        event=self.normalize(self.raw,self.history,config())
        self.assertEqual(event['decision_time_pts'],1.2)
        self.assertEqual(event['source_event']['birth_pts'],1.1)


if __name__=='__main__':unittest.main()
