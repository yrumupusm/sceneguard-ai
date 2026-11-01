import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('accuracy_evaluation', ROOT/'sceneguard/accuracy_evaluation.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def event(eid='g1', start=10., end=20., gate='gate', precise=True):
    return dict(id=eid, start=start, end=end, gate_id=gate,
                provenance='synthetic_fixture_not_CCTV_truth', onset_precise=precise)


def pred(pid='p1', times=None, confirmed=None, gate='gate', notices=None):
    return dict(id=pid, gate_id=gate,
        suspicion_evidence_pts=[12.] if times is None else times,
        confirmation_evidence_pts=[] if confirmed is None else confirmed,
        notifications=[] if notices is None else notices)


def negative(a=0., b=10.):
    return dict(start=a,end=b,gate_id='gate',provenance='synthetic_review')


def video(events=None, predictions=None, negatives=None, **kwargs):
    value = dict(video_id='v1',split='development',duration_seconds=30.,processed_seconds=30.,
        execution_status='complete',truth_basis='reviewed',
        events=[event()] if events is None else events,
        predictions=[pred()] if predictions is None else predictions,
        verified_non_event_intervals=[] if negatives is None else negatives)
    value.update(kwargs)
    return value


class AccuracyTests(unittest.TestCase):
    def test_hit(self):
        r = audit.score_video(video(), 'suspicion')
        self.assertEqual(r['counts']['tp'],1)
        self.assertEqual(r['metrics']['precision'],1)
        self.assertEqual(r['matches'][0]['source_detection_delay_seconds'],2)

    def test_confirmation_separate(self):
        r = audit.score_video(video(), 'confirmation')
        self.assertEqual((r['counts']['tp'],r['counts']['fn']),(0,1))
        self.assertIsNone(r['metrics']['precision'])

    def test_one_card_cannot_cover_two_events(self):
        v = video(events=[event(),event('g2',21,25)], predictions=[pred(times=[12,22])])
        r = audit.score_video(v,'suspicion')
        self.assertEqual((r['counts']['tp'],r['counts']['fn']),(1,1))

    def test_maximum_matching_not_greedy(self):
        edges={'p1':['g1','g2'],'p2':['g1']}
        self.assertEqual(audit.maximum_matching(edges),{'p1':'g2','p2':'g1'})

    def test_duplicate_alarm_counts_fp(self):
        r = audit.score_video(video(predictions=[pred('p1'),pred('p2')]),'suspicion')
        self.assertEqual((r['counts']['tp'],r['counts']['duplicate_fp']),(1,1))
        self.assertEqual(r['metrics']['precision'],.5)

    def test_occupancy_not_matched(self):
        # No fabricated time at 15 just because a card was open from 5 to 25.
        r=audit.score_video(video(predictions=[pred(times=[5,25])]),'suspicion')
        self.assertEqual(r['counts']['tp'],0)
        self.assertEqual(r['counts']['fn'],1)

    def test_verified_negative_fp(self):
        v=video(events=[],predictions=[pred(times=[4])],negatives=[negative(0,30)])
        r=audit.score_video(v,'suspicion')
        self.assertEqual(r['counts']['fp'],1)
        self.assertEqual(r['metrics']['precision'],0)
        self.assertIsNone(r['metrics']['recall_on_resolved_references'])

    def test_unreviewed_not_negative(self):
        r=audit.score_video(video(predictions=[pred(times=[22])]),'suspicion')
        self.assertEqual((r['counts']['fp'],r['counts']['unscored_predictions']),(0,1))
        self.assertIsNone(r['metrics']['precision'])

    def test_mixed_reviewed_unknown_not_silently_fp(self):
        v=video(predictions=[pred(times=[5,25])],negatives=[negative()])
        r=audit.score_video(v,'suspicion')
        self.assertEqual(r['counts']['unscored_predictions'],1)

    def test_early_alarm_is_visible_even_when_event_later_hit(self):
        v=video(predictions=[pred(times=[5,12],notices=[dict(kind='suspicion',pts=5)])],
                negatives=[negative()])
        r=audit.score_video(v,'suspicion')
        self.assertEqual(r['counts']['tp'],1)
        self.assertEqual(r['counts']['false_notices_in_verified_negative'],1)
        self.assertEqual(r['counts']['early_first_notices_for_matched_events'],1)
        self.assertEqual(r['metrics']['false_notices_per_verified_negative_gate_hour'],360)

    def test_confirming_early_is_not_hidden(self):
        v=video(predictions=[pred(times=[5,12],confirmed=[6,13],
                notices=[dict(kind='confirmation',pts=6)])],negatives=[negative()])
        r=audit.score_video(v,'confirmation')
        self.assertEqual(r['counts']['tp'],1)
        self.assertEqual(r['counts']['false_notices_in_verified_negative'],1)

    def test_union_negative_exposure(self):
        self.assertEqual(audit.union_seconds([negative(0,5),negative(3,8)]),8)

    def test_unknown_onset_no_precise_delay(self):
        r=audit.score_video(video(events=[event(precise=False)]),'suspicion')
        self.assertIsNone(r['matches'][0]['source_detection_delay_seconds'])
        self.assertEqual(r['matches'][0]['offset_from_reference_start_seconds'],2)

    def test_failed_keeps_inventory_denominator(self):
        v=video(predictions=[],execution_status='failed',processed_seconds=2.,reason='decode error')
        r=audit.score_video(v,'suspicion')
        self.assertFalse(r['eligible_for_reference_scoring'])
        self.assertEqual(r['counts']['fn'],0) # not a detector-only failure
        self.assertEqual(r['counts']['inventory_resolved_events'],1)
        self.assertEqual(r['metrics']['reference_coverage_across_inventory'],0)

    def test_partial_not_claimed_complete(self):
        with self.assertRaises(ValueError): audit.validate_video(video(processed_seconds=20))

    def test_duplicate_video_rejected(self):
        m=dict(schema_version=1,analysis_revision='abc',protocol_id='test',videos=[video(),video()])
        with self.assertRaises(ValueError):audit.evaluate(m)

    def test_duplicate_pred_rejected(self):
        with self.assertRaises(ValueError):audit.validate_video(video(predictions=[pred(),pred()]))

    def test_positive_negative_conflict(self):
        with self.assertRaises(ValueError):audit.validate_video(video(negatives=[negative(0,30)]))

    def test_wrong_gate_does_not_match(self):
        r=audit.score_video(video(predictions=[pred(gate='other')]),'suspicion')
        self.assertEqual(r['counts']['tp'],0)

    def test_end_is_exclusive(self):
        r=audit.score_video(video(predictions=[pred(times=[20])]),'suspicion')
        self.assertEqual(r['counts']['tp'],0)

    def test_empty_negative_video_is_valid(self):
        v=video(events=[],predictions=[],negatives=[negative(0,30)])
        r=audit.score_video(v,'confirmation')
        self.assertEqual(r['counts']['fp'],0)
        self.assertIsNone(r['metrics']['precision'])
        self.assertEqual(r['metrics']['false_notices_per_verified_negative_gate_hour'],0)

    def test_unresolved_labels_not_fake_negative(self):
        v=video(events=[],truth_basis='unresolved',unresolved_reference_events=2)
        r=audit.score_video(v,'suspicion')
        self.assertFalse(r['eligible_for_reference_scoring'])
        self.assertEqual(r['counts']['unscored_predictions'],1)
        self.assertEqual(r['counts']['unresolved_reference_events'],2)

    def test_separate_splits_and_truth_sources(self):
        videos=[video(),video(video_id='v2',split='additional_seen',truth_basis='official_reference')]
        m=dict(schema_version=1,analysis_revision='abc',protocol_id='test',videos=videos)
        r=audit.evaluate(m)
        self.assertEqual(len(r['modes']['suspicion']['by_split_and_truth']),2)
        self.assertEqual(r['inventory']['videos'],2)
        self.assertEqual(r['inventory']['source_seconds'],60)

    def test_evaluator_does_not_mutate(self):
        import copy
        v=video();before=copy.deepcopy(v)
        audit.score_video(v,'suspicion')
        self.assertEqual(v,before)

    def test_notification_before_evidence_rejected(self):
        with self.assertRaises(ValueError):
            audit.validate_video(video(predictions=[pred(notices=[dict(kind='suspicion',pts=5)])]))

    def test_overlapping_same_gate_gold_rejected(self):
        with self.assertRaises(ValueError):
            audit.validate_video(video(events=[event(),event('g2',15,25)]))


if __name__=='__main__':unittest.main()
