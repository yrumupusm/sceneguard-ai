import copy
import unittest

from sceneguard.mvp_review_quality import feature_consistency, overlap_geometry, quality_diagnostics, question_audit
from sceneguard.tracklet_linking import LinkSettings, build_tracklets, endpoint_rows


class QualityTests(unittest.TestCase):
    def test_outlier_retains_all_representatives_and_exposes_pair_scores(self):
        result = feature_consistency([[1, 0], [1, 0], [0, 1]])
        self.assertEqual(result['least_consistent_representative_index'], 2)
        self.assertTrue(result['possible_inconsistent_representative'])
        self.assertEqual(result['representatives_retained'], 3)
        self.assertEqual(result['pair_cosines'][0], [1., 1., 0.])

    def test_tied_least_index_does_not_imply_bad_person(self):
        result = feature_consistency([[1, 0]]*3)
        self.assertTrue(result['least_index_tied'])
        self.assertFalse(result['possible_inconsistent_representative'])

    def test_containment_and_nonoverlap(self):
        result = overlap_geometry([0, 0, 1, 1], [.2, .2, .3, .3])
        self.assertAlmostEqual(result['fraction_b_contained'], 1.)
        self.assertLess(result['iou'], .5)
        self.assertEqual(overlap_geometry([0, 0, .1, .1], [.2, .2, .3, .3])['iou'], 0.)

    def test_partial_extent_and_concurrency_keep_raw_rows(self):
        frames = []
        for i in range(5):
            frames.append(dict(pts=i/30, detections=[
                dict(track_id=1, bbox=[.1, .1, .2, .5 if i < 3 else .25], score=.9, cache_index=0, observed=True),
                dict(track_id=2, bbox=[.1, .1, .2, .5], score=.9, cache_index=1, observed=True),
                dict(track_id=99, bbox=[.1, .1, .2, .5], score=.9, cache_index=2, observed=False)]))
        settings = LinkSettings()
        segments = build_tracklets(frames, settings)
        representatives = {s['id']: {end: endpoint_rows(s, end, settings) for end in ('head', 'tail')}
                           for s in segments if s['eligible']}
        features = {'features': {sid: {end: [[1., 0.]]*len(rows) for end, rows in pair.items()}
                                 for sid, pair in representatives.items()}}
        before = copy.deepcopy((frames, segments, features, representatives))
        result = quality_diagnostics([dict(pts=f['pts']) for f in frames], frames, segments, features, representatives)
        self.assertEqual(result['counts']['concurrent_overlaps'], 5)
        self.assertEqual(result['counts']['extent_changes'], 1)
        self.assertEqual(result['extent_changes'][0]['raw_id'], 1)
        self.assertEqual((frames, segments, features, representatives), before)

    def test_q06_q07_stay_audit_only_outside_original_time_limit(self):
        segments = [dict(id=f't{i:04d}', raw_id=i, start=20., end=21.) for i in range(1, 14)]
        by_id = {s['id']: s for s in segments}
        by_id['t0006'].update(start=0., end=1.)
        by_id['t0011'].update(start=0., end=1.)
        by_id['t0012'].update(start=2., end=3.)
        by_id['t0013'].update(start=10., end=11.)
        by_id['t0007'].update(start=0., end=1.)
        by_id['t0008'].update(start=2., end=3.)
        links = [dict(before=a, after=b, status='rejected', reason='appearance_gate')
                 for a, b in [('t0006', 't0012'), ('t0011', 't0012'), ('t0007', 't0008')]]
        associations = dict(links=links, settings=dict(max_gap_seconds=5.))
        features = {'features': {s['id']: dict(head=[[1., 0.]], tail=[[1., 0.]]) for s in segments}}
        result = question_audit('007', segments, associations, features, dict(link_suggestions=[]))
        for row in result[2:4]:
            self.assertEqual(row['status'], 'outside_original_time_limit_audit_only')
            self.assertFalse(row['in_feed_suggestions'])
            self.assertIsNone(row['original_link'])
        self.assertEqual(result[-1]['question'], 'Q08')
        self.assertEqual(result[-1]['user_context'], [])
        self.assertEqual(result[-1]['review_context'][0]['source'], 'continuation_instruction_previous_review_draft')
        self.assertFalse(result[-1]['review_context'][0]['identity_verified'])


if __name__ == '__main__':
    unittest.main()
