import copy
import unittest

from scripts.export_reviewed_person_pilot import select_cases


class ReviewedPersonPilotTests(unittest.TestCase):
    def setUp(self):
        case = dict(number=2, window_id='w', split='train', source_sha256='source',
                    event_group='event', displayed_frame_origin=1,
                    frames=[dict(frame_index=40, boxes={'1': [dict(xyxy=[1, 2, 3, 4])]})])
        answer = dict(id='r', answer_version=1, source_binding_sha256='binding',
                      artifact_id='exp0066-label-02-video', status='acknowledged',
                      answer='보이는 사람은 모두 박스가 있음')
        decision = dict(case_number=2, window_id='w', request_id='r', answer_version=1,
                        source_binding_sha256='binding', original_split='train',
                        frame_indices=[40], disposition='export_reviewed_person_scope')
        self.args = [dict(cases=[case]), dict(requests=[answer]), dict(cases=[decision]),
                     dict(windows=[{k: case[k] for k in ('window_id', 'split', 'source_sha256', 'event_group')}])]

    def test_exact_review_scope_only(self):
        self.assertEqual(len(select_cases(*self.args)), 1)

    def test_changed_answer_version_rejected(self):
        self.args[1]['requests'][0]['answer_version'] = 2
        with self.assertRaisesRegex(ValueError, 'version'):
            select_cases(*self.args)

    def test_uncertain_answer_not_promoted(self):
        self.args[1]['requests'][0]['answer'] = '60초부터 박스가 없음'
        with self.assertRaisesRegex(ValueError, 'completeness'):
            select_cases(*self.args)

    def test_unreviewed_frame_rejected(self):
        self.args[2]['cases'][0]['frame_indices'].append(41)
        with self.assertRaisesRegex(ValueError, 'scope'):
            select_cases(*self.args)

    def test_empty_labels_not_background(self):
        self.args[0]['cases'][0]['frames'][0]['boxes']['1'] = []
        with self.assertRaisesRegex(ValueError, 'background'):
            select_cases(*self.args)

    def test_split_reassignment_rejected(self):
        self.args[3]['windows'][0]['split'] = 'validation'
        with self.assertRaisesRegex(ValueError, 'split'):
            select_cases(*self.args)

    def test_missing_case_disposition_rejected(self):
        self.args[2]['cases'] = []
        with self.assertRaisesRegex(ValueError, 'Missing'):
            select_cases(*self.args)

    def test_hold_preserves_exclusion(self):
        self.args[2]['cases'][0]['disposition'] = 'hold_incomplete_or_uncertain_person_scope'
        self.args[1]['requests'][0]['answer'] = '누락 있음'
        self.assertEqual(select_cases(*self.args), [])

    def test_shared_event_across_splits_rejected(self):
        second = copy.deepcopy(self.args)
        second[0]['cases'][0].update(number=6, window_id='w2', split='validation', source_sha256='source2')
        second[1]['requests'][0].update(id='r2', artifact_id='exp0066-label-06-video')
        second[2]['cases'][0].update(case_number=6, window_id='w2', request_id='r2', original_split='validation')
        second[3]['windows'][0].update(window_id='w2', split='validation', source_sha256='source2')
        for first, extra in zip(self.args, second):
            key = next(iter(first))
            first[key].extend(extra[key])
        with self.assertRaisesRegex(ValueError, 'leakage'):
            select_cases(*self.args)


if __name__ == '__main__':
    unittest.main()
