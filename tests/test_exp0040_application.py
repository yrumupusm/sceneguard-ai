"""Contract tests for saved-score partitioning and display-only evidence."""
from copy import deepcopy
import unittest

from sceneguard.exp0040_application import proposal_bundle, timeline_comparison
from sceneguard.exp0036_application import make_bundle
from sceneguard.practical_continuation import seed_decision
from sceneguard.exp0040_evidence import extend_paths


def original():
    rows=[dict(status='침입 의심',segment=f's{i}',raw_id=i,
               reason='recent_gate_presence_then_loss',decision_time_pts=t)
          for i,t in enumerate((10.,12.,14.))]
    return make_bundle(dict(experiment='EXP-0035',video_id='E01_007',source_window=[0,20],
                            events=rows,existing_alerts=[]),'C3','C3_fence','E01_007-original')


def decision(i,score=.8,box=(.1,.1,.3,.5)):
    return dict(source_pointer=f'/events/{i}',raw_id=i,evidence_until_pts=10.+2*i,
                alternatives=[dict(score=score,endpoint_bbox=box)])


class SavedScoreTests(unittest.TestCase):
    def test_default_refactor_equivalent_to_original_qualified_seed_gate(self):
        # A weak conflicting seed does not create a new default-policy veto.
        alts=[dict(score=.8,endpoint_bbox=[.1,.1,.3,.5]),
              dict(score=.65,endpoint_bbox=[.6,.1,.8,.5])]
        self.assertEqual(seed_decision(alts,.70)['recommendation'],'review_only')
        self.assertEqual(seed_decision(alts,.55)['reason'],'different_seed_paths_disagree')
        self.assertEqual(seed_decision(alts,.85)['recommendation'],'keep')

    def test_same_features_duplicate_boxes_not_conflicting(self):
        self.assertEqual(seed_decision([dict(score=.8,endpoint_bbox=[.1,.1,.3,.5]),
            dict(score=.8,endpoint_bbox=[.12,.1,.32,.5])],.7)['recommendation'],'review_only')

    def test_exact_original_events_partition_with_unmodified_ids_and_times(self):
        baseline=original();frozen=deepcopy(baseline)
        proposal=proposal_bundle(baseline,[decision(1)],.7)
        combined=proposal['events']+proposal['review_only_events']
        self.assertEqual({e['event_id']:e for e in combined},
                         {e['event_id']:e for e in baseline['events']})
        self.assertEqual(baseline,frozen)
        self.assertEqual(len(proposal['review_only_events']),1)

    def test_baseline_card_source_interval_survives_changed_card_identity(self):
        baseline=original();proposal=proposal_bundle(baseline,[decision(0)],.7)
        row=timeline_comparison(baseline,proposal)[0]
        self.assertEqual(row['source_interval'],[10.,14.])
        self.assertEqual(row['original_first_notification_pts'],10.)
        self.assertEqual(row['retained_first_event_pts'],12.)
        self.assertEqual(row['proposed_cards'][0]['first_notification_pts'],12.)

    def test_saved_sensitivity_rechecks_boundary_gate(self):
        baseline=original()
        boundary=deepcopy(baseline['events'][0]);boundary.update(event_id='boundary',decision_time_pts=9.)
        boundary['source_ref'].update(collection='existing_alerts',source_pointer='/existing_alerts/0')
        boundary['source_event']['reason']='crossing'
        baseline['events'].append(boundary)
        for threshold in (.55,.65,.70,.75,.85):
            proposal=proposal_bundle(baseline,[decision(0,score=.95)],threshold)
            self.assertEqual(len(proposal['review_only_events']),0)

    def test_other_people_events_stay_active(self):
        proposal=proposal_bundle(original(),[decision(0)],.7)
        self.assertEqual([e['track_ids'] for e in proposal['events']],[[1],[2]])

    def test_duplicate_audit_pointer_refused(self):
        with self.assertRaises(ValueError):proposal_bundle(original(),[decision(0),decision(0)],.7)


class EvidenceAdapterTests(unittest.TestCase):
    def test_saved_permanent_ids_and_positions(self):
        paths=extend_paths({},dict(ids=[2,9],points=[[1,2],[3,4]]),True)
        paths=extend_paths(paths,dict(ids=[9],points=[[4,5]]))
        self.assertEqual(paths,{9:[[3,4],[4,5]]})

    def test_saved_point_cannot_reappear(self):
        paths=extend_paths({},dict(ids=[2],points=[[1,2]]),True)
        paths=extend_paths(paths,dict(ids=[],points=[]))
        with self.assertRaises(ValueError):extend_paths(paths,dict(ids=[2],points=[[2,3]]))

    def test_duplicate_permanent_point_id_refused(self):
        with self.assertRaises(ValueError):extend_paths({},dict(ids=[2,2],points=[[1,2],[3,4]]),True)


if __name__=='__main__':unittest.main()
