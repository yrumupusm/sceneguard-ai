import unittest
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from scripts import export_model_comparison_metrics as exporter
from scripts.export_model_comparison_metrics import event_counts


class EventMetricExportTests(unittest.TestCase):
    def rows(self):
        return [dict(video_id='video', reference_id=str(i), baseline_confirmation_matched=i<37,
                     diagnostic='temporal_candidate_identity_unverified' if i%2==0 else 'input_present_below_action_threshold',
                     same_person_and_gate_verified=False, action_true_positive=None, person_recovery=None,
                     intrusion_completed=None, online_detection_delay_seconds=None) for i in range(52)]

    def test_all_and_previously_missed_denominators_stay_separate(self):
        values=event_counts(self.rows())
        self.assertEqual(sum(values['all52'].values()),52)
        self.assertEqual(sum(values['baseline_missed15'].values()),15)
        self.assertEqual(values['all52']['temporal_candidate_identity_unverified'],26)
        self.assertEqual(values['baseline_missed15']['temporal_candidate_identity_unverified'],7)

    def test_partial_duplicate_or_promoted_success_is_rejected(self):
        cases=[self.rows()[:-1],self.rows(),self.rows(),self.rows()]
        cases[1][-1]['reference_id']=cases[1][-2]['reference_id']
        cases[2][0]['action_true_positive']=True
        cases[3][0]['baseline_confirmation_matched']=1
        for rows in cases:
            with self.assertRaises(ValueError):event_counts(rows)

    def test_export_rejects_mixed_runs_and_changed_frozen_references(self):
        # Synthetic files stay in a disposable directory; no real result registration.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);raw_path=root/'raw.json';heads_path=root/'heads.json';events_path=root/'events.json';ref=root/'reference.json'
            references=[dict(video_id='video',reference_id=str(i),gate_id='gate',start=float(i),end=i+.5,
                             baseline_confirmation_matched=i<37) for i in range(52)]
            ref.write_text(json.dumps([dict(events=references)]))
            rows=[]
            for r,context in zip(self.rows(),references):
                rows.append(dict(r,**{k:v for k,v in context.items() if k not in r},regular_anchor_windows=1,
                                 action_candidate_windows=1,person_and_action_candidate_windows=None,
                                 first_candidate_input_available_pts=None))
            raw=dict(all_eight_full_passes_complete=True,semantic_evaluation_complete=False,models={})
            for model in exporter.MODELS:
                raw['models'][model]=dict(status='inference_complete',windows=6219,decoded_native_frames=184300,
                    elapsed_seconds=1,load_seconds=1,peak_gpu_allocated_bytes=1,peak_gpu_reserved_bytes=1,
                    model_spec_sha256='a'*64,source_hash='b'*64,provenance=dict(result_sha256='c'*64))
            raw_path.write_text(json.dumps(raw));binding=dict(path=str(raw_path),sha256=exporter.sha(raw_path))
            heads=dict(all_seven_heads_scored=True,r3d_threshold=.5,semantic_evaluation_complete=False,raw_summary=binding,models={})
            events=dict(official_events=52,baseline_confirmed=37,baseline_missed=15,unresolved_reference_events=1,
                        semantic_evaluation_complete=False,raw_summary=binding,reference=dict(path=str(ref),sha256=exporter.sha(ref)),models={})
            for model in exporter.MODELS:
                score=None if model=='r3d18_exp0064' else dict(path=str(root/(model+'.json')),sha256='d'*64)
                events['models'][model]=dict(raw_provenance=copy.deepcopy(raw['models'][model]['provenance']),
                                            score_provenance=score,events=copy.deepcopy(rows))
                if score is not None:
                    heads['models'][model]=dict(status='frozen_head_scoring_complete',official_reference_only=True,
                        human_calibration_complete=False,person_recall=None,climbing_precision=None,climbing_recall=None,intrusion_improvement=None,
                        score_provenance=score,head_sha256='e'*64,selected_epoch=1,sample_count=2,feature_dimension=1,
                        coverage_by_split={},validation_metric_scope='weak_full_scene_not_actor_specific',validation_normal_subtypes='sitting_only',
                        groups=[],cpu_head_scoring_seconds=0,scoring_elapsed_seconds=0,timing_scope='synthetic',
                        selection=dict(tp=1,fp=0,tn=1,fn=0,negative_count=1,reference_precision=1,reference_recall=1,reference_fpr=0))
            heads_path.write_text(json.dumps(heads));events_path.write_text(json.dumps(events))
            with patch.object(exporter,'ROOT',root),patch.object(exporter,'REFERENCE',ref),patch.object(exporter,'REFERENCE_SHA',exporter.sha(ref)):
                exporter.export(raw_path,heads_path,events_path,root/'valid')
                measured=json.loads((root/'valid/metrics.json').read_text())['metrics']
                self.assertTrue(all(r['value'] is None for r in measured if r['verification']=='unavailable'))
                for field in ('raw_provenance','score_provenance'):
                    bad=copy.deepcopy(events);bad['models'][exporter.MODELS[0]][field]={'different_run':True}
                    events_path.write_text(json.dumps(bad));output=root/field
                    with self.assertRaisesRegex(ValueError,'Cross-summary'):exporter.export(raw_path,heads_path,events_path,output)
                    self.assertFalse(output.exists())
                for field,value in [('reference_id','different'),('gate_id','other'),('start',-.5),('end',9.)]:
                    bad=copy.deepcopy(events);bad['models'][exporter.MODELS[0]]['events'][0][field]=value
                    events_path.write_text(json.dumps(bad))
                    with self.assertRaisesRegex(ValueError,'frozen references'):
                        exporter.export(raw_path,heads_path,events_path,root/field)
                bad=copy.deepcopy(events);changed=bad['models'][exporter.MODELS[0]]['events']
                changed[0]['baseline_confirmation_matched']=False;changed[37]['baseline_confirmation_matched']=True
                events_path.write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError,'frozen references'):
                    exporter.export(raw_path,heads_path,events_path,root/'baseline')


if __name__=='__main__':unittest.main()
