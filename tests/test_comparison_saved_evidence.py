import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.comparison_saved_evidence import ROOT, checked_rows, checked_head_scores, sha


class SavedOutputTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(video_id='E01_001', source_sha256='fixed', window={'window_id':'a'}, output={})
        self.expected = {'a':dict(video_id='E01_001',source_sha256='fixed',window={'window_id':'a'})}
        self.result = dict(model_id='r3d18_exp0064',status='smoke_passed',scored_windows=1)

    def consume(self, rows, result=None, expected=None):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'windows.jsonl'
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
            return list(checked_rows(path,result or self.result,expected or self.expected))

    def test_changed_actor_video_or_original_bytes_cannot_be_rendered_as_same_input(self):
        for field,value in [('video_id','E01_002'),('source_sha256','changed')]:
            row=copy.deepcopy(self.row);row[field]=value
            with self.assertRaisesRegex(ValueError,'correspondence'):self.consume([row])

    def test_duplicate_rows_cannot_inflate_coverage(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):self.consume([self.row,self.row])

    def test_missing_fullpass_window_cannot_be_complete(self):
        expected={**self.expected,'b':dict(video_id='E01_001',source_sha256='fixed',window={'window_id':'b'})}
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            self.consume([self.row],dict(self.result,status='inference_complete'),expected)

    def test_old_evad_double_scaled_output_is_not_accepted_for_review(self):
        with self.assertRaisesRegex(ValueError,'predates'):
            self.consume([self.row],dict(self.result,model_id='evad_vitl'))

    def test_read_only_matching_smoke_keeps_exact_source_row(self):
        self.assertEqual(self.consume([self.row]),[self.row])


class SavedHeadScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.head_path=self.root/'head-result.json';self.head_path.write_text('{}')
        self.receipt=self.root/'receipt.json';self.receipt.write_text('{}')
        (self.root/'head.pt').write_bytes(b'synthetic')
        self.raw_path=self.root/'raw.json';self.raw_path.write_text('{}')
        (self.root/'windows.jsonl').write_text('{}')
        self.head=dict(head_sha256='fixed-head',selection={'threshold':.5})
        self.raw=dict(model_id='vjepa2_l');self.proof={'result_sha256':'raw-fixed','result_path':str(self.raw_path)}
        self.expected={'a':dict(window={'window_id':'a'},video_id='E01_001',source_sha256='original',role='diagnostic')}
        self.row=dict(window={'window_id':'a'},video_id='E01_001',source_sha256='original',head_threshold=.5,person_threshold=None,
                      model_id='vjepa2_l',person_scores=[],intrusion_completed=None,intrusion_state_changed=False,same_person_verified=False,boxes=[],scores=[dict(
                          climbing_action_score=.6,query_index=None,climbing_action_candidate=True,intrusion_completed=None,
                          intrusion_state_changed=False,threshold_status='provisional_official_reference_not_human_calibrated',
                          matched_false_positive_operating_point_verified=False,person_and_action_candidate=None)])
        self.native=dict(window={'window_id':'a'},output={'boxes':[],'person_scores':[]})
        self.report=dict(status='frozen_head_scored_saved_school_outputs',model_id='vjepa2_l',raw_provenance=self.proof,
                         windows=1,new_encoder_or_detector_forwards=0,school_data_used_for_training_or_threshold_selection=False,
                         semantic_evaluation_complete=False,head_result_path=str(self.head_path),
                         head_result_sha256=sha(self.head_path),head_receipt_sha256=sha(self.receipt),head_sha256='fixed-head',
                         head_selection=self.head['selection'],bindings={str(p):sha(p) for p in (
                             self.raw_path,self.root/'windows.jsonl',self.head_path,self.root/'head.pt',
                             ROOT/'scripts/score_model_comparison_heads.py',ROOT/'scripts/train_comparison_heads.py',
                             ROOT/'scripts/comparison_saved_evidence.py')})

    def consume(self,rows=None,report=None):
        scores=self.root/'scores.jsonl';scores.write_text(''.join(json.dumps(r)+'\n' for r in (rows if rows is not None else [self.row])))
        path=self.root/'result.json';path.write_text(json.dumps({**(report or self.report),'scores_sha256':sha(scores)}))
        with patch('scripts.score_model_comparison_heads.checked_head',return_value=(self.head,self.receipt,{})),\
             patch('scripts.comparison_saved_evidence.checked_rows',return_value=iter([self.native])):
            return checked_head_scores(path,self.raw,self.proof,self.expected)

    def test_exact_frozen_scene_score_is_not_actor_or_intrusion_success(self):
        report,rows,proof=self.consume()
        self.assertIsNone(rows['a']['scores'][0]['query_index'])
        self.assertIsNone(rows['a']['intrusion_completed'])
        self.assertFalse(report['semantic_evaluation_complete'])

    def test_foreign_raw_result_or_school_threshold_selection_is_rejected(self):
        for k,v in [('raw_provenance',{'result_sha256':'foreign'}),('school_data_used_for_training_or_threshold_selection',True),
                    ('semantic_evaluation_complete',True)]:
            with self.assertRaises(ValueError):self.consume(report={**self.report,k:v})

    def test_missing_duplicate_or_retimed_score_is_rejected(self):
        for rows in ([],[self.row,self.row],[{**self.row,'video_id':'different'}]):
            with self.assertRaises(ValueError):self.consume(rows=rows)

    def test_score_cannot_promote_intrusion_or_change_threshold(self):
        for k,v in [('intrusion_completed',True),('head_threshold',.1),('same_person_verified',True)]:
            with self.assertRaises(ValueError):self.consume(rows=[{**self.row,k:v}])
        bad=copy.deepcopy(self.row);bad['scores'][0]['climbing_action_candidate']=False
        with self.assertRaises(ValueError):self.consume(rows=[bad])

    def test_scored_geometry_model_and_source_binding_cannot_be_swapped(self):
        for k,v in [('boxes',[[1,2,3,4]]),('person_scores',[.9]),('model_id','evad_vitl')]:
            with self.assertRaises(ValueError):self.consume(rows=[{**self.row,k:v}])
        with self.assertRaises(ValueError):self.consume(report={**self.report,'bindings':{}})
        bad=copy.deepcopy(self.row);bad['scores'][0]['person_and_action_candidate']=True
        with self.assertRaises(ValueError):self.consume(rows=[bad])


if __name__=='__main__':unittest.main()
