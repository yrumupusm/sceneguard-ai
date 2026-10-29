"""Display receipts must bind actual cached observations and emission times."""
from fractions import Fraction
import tempfile
from pathlib import Path
import unittest

from scripts.render_exp0028_tracking import event_labels, timing_key, validate_record, strict_reproduction


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.cached = dict(pts=2., native_pts=30720, time_base='1/15360', source_size=[1920, 1080],
                           boxes=[[192, 108, 384, 540]], scores=[.7])
        self.record = dict(pts=2., native_pts=60, time_base='1/30', states=[
            dict(observed=True, cache_index=0, bbox=[.1, .1, .2, .5], score=.7),
            dict(observed=False, prediction_bbox=[.2, .2, .3, .6])])

    def test_native_rational_time_equivalence(self):
        self.assertEqual(timing_key(self.record), Fraction(2))
        validate_record(self.record, self.cached)

    def test_shifted_overlay_rejected(self):
        self.record['native_pts'] += 1
        with self.assertRaisesRegex(ValueError, 'timing'):
            validate_record(self.record, self.cached)

    def test_wrong_cache_box_or_score_rejected(self):
        self.record['states'][0]['bbox'][3] = .6
        with self.assertRaisesRegex(ValueError, 'cache'):
            validate_record(self.record, self.cached)

    def test_alert_uses_emission_not_inferred_candidate_time(self):
        event = dict(track_id=1, candidate_pts=1., emitted_at_pts=2.)
        self.assertEqual(event_labels([event], 1.), [])
        self.assertEqual(len(event_labels([event], 2.)), 1)
        self.assertEqual(event_labels([event], 3.), [])

    def test_strict_reproduction_does_not_ignore_other_event_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp)/'old', Path(tmp)/'new'
            for path in (old, new):
                path.mkdir()
                (path/'frames.jsonl').write_text('{}\n')
                (path/'reobservations.jsonl').write_text('')
            (old/'events.jsonl').write_text('{"condition":"C","track_id":1}\n')
            (new/'events.jsonl').write_text('{"condition":"strict","track_id":1}\n')
            self.assertTrue(strict_reproduction(old, new)['frames_byte_exact'])
            (new/'events.jsonl').write_text('{"condition":"strict","track_id":2}\n')
            with self.assertRaisesRegex(ValueError, 'reproduction'):
                strict_reproduction(old, new)


if __name__ == '__main__':
    unittest.main()
