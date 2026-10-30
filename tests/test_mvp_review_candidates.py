import unittest
import numpy as np
from mvp_review_candidates import appearance_diagnostics,propose_links,review_events,make_feed


class MVPReviewTests(unittest.TestCase):
    def test_line_event_is_not_crossing_success(self):
        e=review_events([dict(track_id=8,emitted_at_pts=70.133333,video_id='E01_007')],[],
                         start=48,end=105,video_id='E01_007')
        self.assertEqual(e[0]['category'],'boundary_motion_requires_review')
        self.assertEqual(e[0]['physical_climb_completion'],'unknown')
        self.assertFalse(e[0]['identity_verified'])
        self.assertEqual(e[0]['evidence_window'],[66.133333,78.133333])

    def test_simultaneous_people_do_not_merge(self):
        rows=review_events([dict(track_id=x,emitted_at_pts=90.3,video_id='E01_030') for x in (3,4)],[],
                           start=84,end=100,video_id='E01_030')
        self.assertEqual(len(rows),2)
        self.assertEqual({r['raw_track_id'] for r in rows},{3,4})

    def test_optional_new_region_data_not_fabricated(self):
        e=review_events([], [dict(chain_id='p1',confirmed_at=93.2,direction='outside_to_inside')],
                        start=84,end=100,video_id='E01_030')
        self.assertEqual(e[0]['category'],'two_side_transition_requires_review')
        self.assertFalse(e[0]['identity_verified'])

    def test_rejected_similarity_never_accepted(self):
        links=[dict(before='t1',after='t2',status='rejected',reason='appearance_gate',
                    similarity=.37,gap_seconds=3.3)]
        segments=[dict(id='t1',raw_id=1),dict(id='t2',raw_id=9)]
        e=propose_links(dict(links=links),segments)
        self.assertEqual(len(e),1)
        self.assertEqual(e[0]['status'],'possible_match_needs_review')
        self.assertFalse(e[0]['identity_verified'])

    def test_accepted_is_still_unverified(self):
        links=[dict(before='t1',after='t2',status='accepted',reason='appearance_time_space',
                    similarity=.71,gap_seconds=1.2)]
        segments=[dict(id='t1',raw_id=9),dict(id='t2',raw_id=9)]
        e=propose_links(dict(links=links),segments)
        self.assertEqual(e[0]['status'],'auto_associated_unverified')

    def test_review_candidates_top_two_not_threshold_sweep(self):
        vals=[.21,.42,.36]
        links=[dict(before='a',after=f'b{i}',status='rejected',reason='appearance_gate',
                    similarity=v,gap_seconds=3) for i,v in enumerate(vals)]
        segments=[dict(id='a',raw_id=1)]+[dict(id=f'b{i}',raw_id=i+2) for i in range(3)]
        e=propose_links(dict(links=links),segments)
        self.assertEqual([r['similarity'] for r in e],[.42,.36])

    def test_endpoint_diagnostic_does_not_classify_people(self):
        vals=dict(features={'a':dict(head=[[1,0],[1,0],[-1,0]],tail=[[1,0],[1,0]])})
        stats=appearance_diagnostics(vals)['a']
        self.assertEqual(stats['head']['min_similarity'],-1)
        self.assertNotIn('identity_verified',stats)

    def test_feed_without_region_data_does_not_claim_current_polygons(self):
        feed=make_feed(video_id='E01_030',start=84,end=100,
              gap_events=[],associations=dict(links=[]),tracklets=[],saved_features=dict(features={}))
        self.assertEqual(feed['region_status'],'no_current_region_results_supplied')
        self.assertEqual(feed['counts']['two_side_candidates'],0)

    def test_cross_video_events_rejected(self):
        with self.assertRaises(ValueError):
            review_events([dict(video_id='E01_007',emitted_at_pts=90)],[],
                          start=84,end=100,video_id='E01_030')

    def test_bad_feature_zero_norm_rejected(self):
        with self.assertRaises(ValueError):
            appearance_diagnostics(dict(features={'a':dict(head=[[0,0]],tail=[[1,1]])}))


if __name__=='__main__':
    unittest.main()
