import copy
import unittest

from scripts.export_confirmed_person_boxes import ANSWER, CASES, current_answers, select
from unittest.mock import patch


class ConfirmedPersonBoxesTests(unittest.TestCase):
    def setUp(self):
        self.package = {'frames': []}
        self.preview = dict(display_threshold=.5, fps=3, cases=[])
        self.responses = {'requests': []}
        for n, (split, start) in CASES.items():
            shown = []
            for index in range(start, start+25):
                fid = f'case-{n}-frame-{index}'
                box = dict(id=fid+':visible', xyxy=[10, 20, 30, 50], score=.7)
                self.package['frames'].append(dict(frame_id=fid, case_number=n, split=split,
                    frame_index=index, source_pts=index/3, image_sha256=fid, source_size=[100, 100],
                    source_sha256=f'source{n}', event_group=f'event{n}',
                    candidates=[dict(**box, kind='model'),
                                dict(id=fid+':hidden', kind='model', xyxy=[50, 50, 60, 70], score=.1),
                                dict(id='old', kind='original', xyxy=[0, 0, 5, 5], score=None)]))
                shown.append(dict(frame_id=fid, source_pts=index/3, image_sha256=fid,
                                  displayed_proposals=[copy.deepcopy(box)]))
            self.preview['cases'].append(dict(case_number=n, frame_count=25, frames=shown))
            self.responses['requests'].append(dict(id=f'r{n}', artifact_id=f'exp0067-repair-{n:02d}-video',
                experiment_id='EXP-0067', status='acknowledged', answer_version=1, answer=ANSWER,
                note='', source_binding_sha256=f'binding{n}'))

    def run_select(self):
        return select(self.package, self.preview, self.responses)

    def test_only_shown_boxes_not_hidden_or_original(self):
        rows = self.run_select()
        self.assertEqual(len(rows), 75)
        self.assertEqual(sum(len(b) for _, b, _ in rows), 75)
        self.assertTrue(all(b[0]['id'].endswith(':visible') for _, b, _ in rows))

    def test_uncertain_answer_or_qualifying_note_rejected(self):
        for field, value in [('answer', '판단 어려움'), ('note', '끝에는 한 명 빠짐')]:
            with self.subTest(field=field):
                old = self.responses['requests'][0][field]
                self.responses['requests'][0][field] = value
                with self.assertRaisesRegex(ValueError, 'unqualified'):
                    self.run_select()
                self.responses['requests'][0][field] = old

    def test_hidden_box_cannot_be_added_to_reviewed_set(self):
        self.preview['cases'][0]['frames'][0]['displayed_proposals'].append(
            dict(id='hidden', xyxy=[1, 2, 3, 4], score=.1))
        with self.assertRaisesRegex(ValueError, 'displayed'):
            self.run_select()

    def test_time_shift_rejected(self):
        self.preview['cases'][0]['frames'][0]['source_pts'] += 1/3
        with self.assertRaisesRegex(ValueError, 'time'):
            self.run_select()

    def test_extra_unseen_frame_rejected(self):
        self.package['frames'].append(copy.deepcopy(self.package['frames'][0]))
        with self.assertRaisesRegex(ValueError, '75'):
            self.run_select()

    def test_missing_displayed_frame_rejected(self):
        self.preview['cases'][0]['frames'].pop()
        with self.assertRaisesRegex(ValueError, '25'):
            self.run_select()

    def test_split_reassignment_rejected(self):
        self.package['frames'][0]['split'] = 'validation'
        with self.assertRaisesRegex(ValueError, 'split'):
            self.run_select()

    def test_same_event_across_splits_rejected(self):
        self.package['frames'][-1]['event_group'] = 'event1'
        with self.assertRaisesRegex(ValueError, 'leakage'):
            self.run_select()

    def test_updated_answer_snapshot_rejected(self):
        latest = copy.deepcopy(self.responses['requests'])
        latest[0]['answer_version'] = 2
        with patch('scripts.export_confirmed_person_boxes.configured_store') as store:
            store.return_value.list.return_value = latest
            with self.assertRaisesRegex(ValueError, 'Newer'):
                current_answers({}, self.responses)

    def test_same_answer_must_validate_media_binding(self):
        with patch('scripts.export_confirmed_person_boxes.configured_store') as store, \
                patch('scripts.export_confirmed_person_boxes.validate_binding', side_effect=ValueError('changed video')):
            store.return_value.list.return_value = self.responses['requests']
            with self.assertRaisesRegex(ValueError, 'changed video'):
                current_answers({}, self.responses)


if __name__ == '__main__':
    unittest.main()
