"""Synthetic EXP-0029 tests; not evidence of real CCTV identity accuracy."""
from dataclasses import replace
import unittest

import numpy as np

from sceneguard.tracklet_linking import (LinkSettings, build_tracklets, endpoint_rows,
    link_tracklets, observation_zone, region_events, unit_features, validate_zones)


def frame(pts, rows=()):
    return dict(pts=pts, detections=list(rows))


def det(tid=1, box=(.1,.1,.2,.5), score=.9, **kwargs):
    return dict(track_id=tid,bbox=list(box),score=score,observed=True,confirmed=True,
                cache_index=tid-1,**kwargs)


def segment(sid, start, end, box, raw_id=1):
    rows = [dict(pts=float(t),frame_index=i,raw_id=raw_id,bbox=list(box),score=.9,cache_index=raw_id-1)
            for i,t in enumerate(np.linspace(start,end,7))]
    return dict(id=sid,raw_id=raw_id,rows=rows,start=start,end=end,observations=7,eligible=True)


def feats(segments, vectors=None):
    vectors = vectors or [[1.,0.] for _ in segments]
    return {s['id']:dict(head=[v],tail=[v]) for s,v in zip(segments,vectors)}


ZONES = dict(outside=[[0,0],[.4,0],[.4,1],[0,1]],
             inside=[[.6,0],[1,0],[1,1],[.6,1]])


class TrackletTests(unittest.TestCase):
    def test_single_frame_gap_does_not_break_tracklet(self):
        rows=[frame(0,[det()]),frame(.1,[]),frame(.2,[det()]),frame(.3,[det()])]
        result=build_tracklets(rows)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['observations'],3)
        self.assertTrue(result[0]['eligible'])

    def test_long_gap_splits_even_with_same_raw_id(self):
        result=build_tracklets([frame(0,[det()]),frame(2,[det()])])
        self.assertEqual(len(result),2)
        self.assertEqual(result[1]['split_reason'],'observation_gap')

    def test_prediction_not_used(self):
        row=det();row['observed']=False
        self.assertEqual(build_tracklets([frame(0,[row])]),[])

    def test_short_segment_retained_but_ineligible(self):
        out=build_tracklets([frame(0,[det()])])
        self.assertEqual(len(out),1)
        self.assertFalse(out[0]['eligible'])

    def test_duplicate_id_rejected(self):
        with self.assertRaises(ValueError):build_tracklets([frame(0,[det(),det()])])

    def test_nonmonotonic_timestamps_rejected(self):
        with self.assertRaises(ValueError):build_tracklets([frame(1),frame(0)])

    def test_bad_measurement_rejected(self):
        with self.assertRaises(ValueError):build_tracklets([frame(0,[det(box=(.5,0,.2,.5))])])

    def test_no_artificial_observations(self):
        frames=[frame(0,[det()]),frame(.1),frame(.2,[det()])]
        self.assertEqual([r['pts'] for s in build_tracklets(frames) for r in s['rows']],[0,.2])

    def test_representatives_distributed_and_bounded(self):
        s=segment('a',0,4,(.1,.1,.2,.4))
        for end in ('head','tail'):
            reps=endpoint_rows(s,end)
            self.assertLessEqual(len(reps),3)
            self.assertEqual(len({r['frame_index'] for r in reps}),len(reps))
            self.assertTrue(all(r in s['rows'] for r in reps))

    def test_invalid_settings_rejected(self):
        for settings in [replace(LinkSettings(),max_gap_seconds=0),replace(LinkSettings(),min_similarity=float('nan')),
                         replace(LinkSettings(),representative_count=2.5)]:
            with self.assertRaises(ValueError):settings.validate()


class AssociationTests(unittest.TestCase):
    def setUp(self):
        self.a=segment('a',0,.6,(.2,.1,.3,.5))
        self.b=segment('b',3.9,4.5,(.45,.1,.55,.5),raw_id=9)

    def test_no_overlap_boxes_can_reconnect_after_3p3_seconds(self):
        ss=[self.a,self.b]
        result=link_tracklets(ss,feats(ss))
        self.assertEqual(result['mapping']['a'],result['mapping']['b'])
        self.assertEqual(result['links'][0]['status'],'accepted')
        self.assertAlmostEqual(result['links'][0]['gap_seconds'],3.3)

    def test_wrong_appearance_not_connected(self):
        ss=[self.a,self.b]
        result=link_tracklets(ss,feats(ss,[[1,0],[0,1]]))
        self.assertNotEqual(result['mapping']['a'],result['mapping']['b'])

    def test_same_raw_id_does_not_force_link(self):
        self.b['raw_id']=1
        ss=[self.a,self.b]
        result=link_tracklets(ss,feats(ss,[[1,0],[0,1]]))
        self.assertEqual(result['links'][0]['reason'],'appearance_gate')

    def test_long_gap_not_connected(self):
        b=segment('b',6,6.6,(.3,.1,.4,.5))
        result=link_tracklets([self.a,b],feats([self.a,b]))
        self.assertEqual(result['links'],[])

    def test_simultaneous_tracks_not_merged(self):
        b=segment('b',.3,1,(.3,.1,.4,.5))
        result=link_tracklets([self.a,b],feats([self.a,b]))
        self.assertEqual(len(result['chains']),2)

    def test_identical_competitors_are_deferred(self):
        c=segment('c',3.9,4.5,(.46,.1,.56,.5),raw_id=10)
        ss=[self.a,self.b,c]
        result=link_tracklets(ss,feats(ss))
        self.assertEqual(sum(r['status']=='accepted' for r in result['links']),0)
        self.assertTrue(all(r['reason']=='ambiguous_appearance' for r in result['links']))

    def test_two_people_one_to_one_no_branch(self):
        a2=segment('a2',0,.6,(.21,.1,.31,.5),raw_id=2)
        b2=segment('b2',3.9,4.5,(.46,.1,.56,.5),raw_id=10)
        ss=[self.a,a2,self.b,b2]
        result=link_tracklets(ss,feats(ss,[[1,0],[0,1],[1,0],[0,1]]))
        self.assertEqual(result['mapping']['a'],result['mapping']['b'])
        self.assertEqual(result['mapping']['a2'],result['mapping']['b2'])
        self.assertNotEqual(result['mapping']['a'],result['mapping']['a2'])

    def test_chain_of_three_has_one_global_id(self):
        c=segment('c',7.8,8.4,(.65,.1,.75,.5),raw_id=11)
        ss=[self.a,self.b,c]
        result=link_tracklets(ss,feats(ss))
        self.assertEqual(len(result['chains']),1)
        self.assertEqual(result['chains'][0]['segments'],['a','b','c'])

    def test_missing_features_not_geometry_fallback(self):
        result=link_tracklets([self.a,self.b],{})
        self.assertEqual(result['links'][0]['reason'],'missing_appearance')

    def test_zero_feature_rejected(self):
        with self.assertRaises(ValueError):unit_features([[0,0]])

    def test_empty_input(self):
        self.assertEqual(link_tracklets([],{} )['chains'],[])


class RegionTests(unittest.TestCase):
    def test_zone_membership_and_transition_band(self):
        self.assertEqual(observation_zone((.1,.1,.2,.5),ZONES),'outside')
        self.assertEqual(observation_zone((.7,.1,.8,.5),ZONES),'inside')
        self.assertIsNone(observation_zone((.45,.1,.55,.5),ZONES))

    def test_overlap_is_unknown(self):
        overlapping=dict(outside=ZONES['outside'],inside=ZONES['outside'])
        self.assertIsNone(observation_zone((.1,.1,.2,.5),overlapping))

    def test_missing_polygons_not_guessed(self):
        with self.assertRaises(ValueError):validate_zones(dict(outside=[],inside=[]))

    def test_linked_sides_produce_candidate_not_climb_proof(self):
        a=segment('a',0,.6,(.25,.1,.35,.5))
        b=segment('b',3.9,4.5,(.65,.1,.75,.5),raw_id=9)
        ss=[a,b];assoc=link_tracklets(ss,feats(ss))
        events=region_events(ss,assoc,ZONES,.1,available_after_pts=5.)
        self.assertEqual(len(events),1)
        self.assertTrue(events[0]['linked_tracklets'])
        self.assertEqual(events[0]['direction'],'outside_to_inside')
        self.assertEqual(events[0]['physical_climb_completion'],'unknown')
        self.assertEqual(events[0]['available_after_pts'],5.)

    def test_approach_only_no_candidate(self):
        a=segment('a',0,.6,(.1,.1,.2,.5))
        b=segment('b',3,3.6,(.25,.1,.35,.5),raw_id=9)
        ss=[a,b]
        self.assertEqual(region_events(ss,link_tracklets(ss,feats(ss)),ZONES,.1),[])

    def test_gap_not_counted_as_dwell(self):
        a=segment('a',0,.6,(.25,.1,.35,.5))
        b=segment('b',3.9,4.5,(.65,.1,.75,.5),raw_id=9)
        b['rows']=[b['rows'][0],b['rows'][-1]]
        ss=[a,b]
        self.assertEqual(region_events(ss,link_tracklets(ss,feats(ss)),ZONES,.1),[])

    def test_same_track_region_crossing_control(self):
        a=segment('a',0,.6,(.25,.1,.35,.5))
        tail=segment('b',.7,1.3,(.65,.1,.75,.5))
        a['rows']+=tail['rows'];a['end']=1.3
        events=region_events([a],dict(chains=[dict(id='a',segments=['a'])]),ZONES,.1)
        self.assertEqual(len(events),1)
        self.assertFalse(events[0]['linked_tracklets'])

    def test_new_person_inside_no_outside_history(self):
        a=segment('a',0,.6,(.65,.1,.75,.5))
        self.assertEqual(region_events([a],dict(chains=[dict(id='a',segments=['a'])]),ZONES,.1),[])

    def test_overlapping_chain_refused(self):
        a=segment('a',0,.6,(.25,.1,.35,.5))
        b=segment('b',0,.6,(.65,.1,.75,.5))
        with self.assertRaises(ValueError):
            region_events([a,b],dict(chains=[dict(id='p',segments=['a','b'])]),ZONES,.1)


if __name__=='__main__':unittest.main()
