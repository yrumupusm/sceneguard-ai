import unittest
from scripts.evaluate_person_detector_pair import evaluate, match, validate_predictions


class PersonDetectorPairTests(unittest.TestCase):
    def test_duplicate_prediction_is_false_positive(self):
        b = [0, 0, 10, 10]
        r = match([b], [b, b], [.9, .8])
        self.assertEqual((r['tp'], r['fp'], r['fn']), (1, 1, 0))

    def test_another_person_cannot_rescue_missed_target(self):
        r = match([[0, 0, 10, 10]], [[20, 20, 30, 30]], [.99])
        self.assertEqual((r['tp'], r['fp'], r['fn']), (0, 1, 1))

    def test_low_score_is_not_a_detection(self):
        r = match([[0, 0, 10, 10]], [[0, 0, 10, 10]], [.4999])
        self.assertEqual((r['tp'], r['fp'], r['fn']), (0, 0, 1))

    def test_exact_threshold_is_included(self):
        r = match([[0, 0, 10, 10]], [[0, 0, 10, 10]], [.5])
        self.assertEqual(r['tp'], 1)

    def test_reassignment_finds_two_people(self):
        gt = [[0, 0, 10, 10], [4, 0, 14, 10]]
        predictions = [[2, 0, 12, 10], [0, 0, 10, 10]]
        r = match(gt, predictions, [.95, .8])
        self.assertEqual((r['tp'], r['fp'], r['fn']), (2, 0, 0))
        self.assertEqual(len({m['prediction_index'] for m in r['matches']}), 2)

    def test_missing_frame_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Exact validation'):
            validate_predictions([], [dict(frame_id='a')])

    def test_changed_pixels_or_time_is_rejected(self):
        frame = dict(frame_id='a', image_sha256='sha', source_pts=1, source_size=[100, 100])
        for key, value in [('image_sha256', 'changed'), ('source_pts', 2)]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'pixels/time'):
                validate_predictions([dict(frame, boxes=[], person_scores=[], **{key:value})], [frame])

    def test_nonfinite_or_reversed_boxes_are_rejected(self):
        frame = dict(frame_id='a', image_sha256='sha', source_pts=1, source_size=[100, 100])
        for box in ([0, 0, float('nan'), 10], [10, 0, 0, 10]):
            with self.subTest(box=box), self.assertRaisesRegex(ValueError, 'Invalid'):
                validate_predictions([dict(frame, boxes=[box], person_scores=[.9])], [frame])

    def test_paired_people_counts_keep_recovery_and_new_miss_separate(self):
        frames, before, after = [], [], []
        for i in range(25):
            boxes = [[0, 0, 10, 10]] + ([[20, 0, 30, 10]] if i < 6 else [])
            frame = dict(frame_id=str(i), image_sha256=str(i), source_pts=float(i),
                source_size=[100, 100], split='validation', event_group='single-event',
                person_completeness_verified=True,
                confirmed_person_boxes=[dict(id=f'{i}:{j}', xyxy=b) for j, b in enumerate(boxes)])
            frames.append(frame)
            a = boxes[1:] if i == 0 else boxes
            b = boxes[1:] if i == 1 else boxes
            before.append(dict(frame, boxes=a, person_scores=[.8]*len(a)))
            after.append(dict(frame, boxes=b, person_scores=[.8]*len(b)))
        result = evaluate(dict(frames=frames), before, after)
        self.assertEqual(result['paired_gt_counts'], dict(both_detected=29, recovered=1, new_miss=1, both_missed=0))
        self.assertEqual(result['metrics']['before']['tp'], 30)
        self.assertEqual(result['metrics']['after']['tp'], 30)
        self.assertFalse(result['independent_generalization'])


if __name__ == '__main__':
    unittest.main()
