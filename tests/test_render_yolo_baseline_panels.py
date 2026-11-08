import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.render_yolo_baseline_panels import checked_case_output, load_completed, check_receipt


class DetectorPanelEvidenceTests(unittest.TestCase):
    def setUp(self):
        window = dict(sample_frame_indices=list(range(16)), sample_pts=[x/3 for x in range(16)])
        self.case = dict(window=window, video_id='source', media=dict(keyframe_pts=8/3))
        self.row = dict(window=copy.deepcopy(window), video_id='source', box_frame_index=8,
                        box_pts=8/3, model_input_available_after_pts=8/3,
                        output=dict(actual_input_frames=1, input_frame_index=8, person_threshold=.5,
                                    action_scores=None, climbing_score=None))

    def test_preserves_exact_saved_output(self):
        self.assertIs(checked_case_output(self.case, self.row), self.row['output'])

    def test_rejects_other_frame_even_when_video_matches(self):
        self.row['box_frame_index'] = 7
        with self.assertRaises(ValueError): checked_case_output(self.case, self.row)

    def test_rejects_box_on_wrong_display_time(self):
        self.case['media']['keyframe_pts'] = 7/3
        with self.assertRaises(ValueError): checked_case_output(self.case, self.row)

    def test_rejects_person_score_presented_as_climb(self):
        self.row['output']['climbing_score'] = .9
        with self.assertRaises(ValueError): checked_case_output(self.case, self.row)

    def test_smoke_success_cannot_be_full_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'completion.json'
            path.write_text(json.dumps(dict(status='succeeded', stage='smoke')))
            with self.assertRaises(ValueError): load_completed(path, 'cohort')

    def test_rejects_failed_or_misbound_receipt(self):
        result = dict(source_hash='source', input_hash='input', code_sha='code')
        completion = dict(**result, attempt_id='attempt', job_id='job', result=dict(sha256='result'))
        receipt = dict(execution_status='succeeded', synthetic=False, attempt_id='attempt',
                       result_sha256='result', result_path='/saved/output',
                       registration=dict(**result, command='model-compare', job_id='job'))
        path=Path('/saved/output/result.json')
        check_receipt(receipt, result, path, completion)
        for field,value in [('execution_status','failed'),('synthetic',True),('result_path','/another/output')]:
            with self.subTest(field=field):
                bad=copy.deepcopy(receipt);bad[field]=value
                with self.assertRaises(ValueError):check_receipt(bad,result,path,completion)
        for field in ('source_hash','input_hash','code_sha','job_id','command'):
            with self.subTest(field=field):
                bad=copy.deepcopy(receipt);bad['registration'][field]='different'
                with self.assertRaises(ValueError):check_receipt(bad,result,path,completion)


if __name__ == '__main__':
    unittest.main()
