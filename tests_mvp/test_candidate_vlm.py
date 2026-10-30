"""EXP-0033 synthetic contracts. No GPU/model weights or actual CCTV required."""
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from mvp import candidate_vlm as cv


class ManifestAndPromptTests(unittest.TestCase):
    def test_exact_three_frozen_cases_and_separate_negative_control(self):
        m=cv.frozen_manifest()
        self.assertEqual(len(m["cases"]),3)
        self.assertEqual([x["mode"] for x in m["cases"]],
            ["cv_candidate","cv_candidate","independent_negative_control_no_cv_gate"])
        self.assertEqual({x["source_id"] for x in m["videos"]},{"E01_030","E01_007"})
        self.assertFalse(any("original_event" in k for k in m["cases"][2]))

    def test_all_cases_see_identical_action_instruction_without_reference(self):
        prompts=[cv.candidate_prompt(x[1]) for x in cv.EXPECTED]
        self.assertEqual([p.split("\n",1)[1] for p in prompts],
                         [prompts[0].split("\n",1)[1]]*3)
        self.assertTrue("climbing_attempt_or_in_progress" in prompts[0])
        self.assertFalse("Q03" in prompts[0] or "Q04" in prompts[0])
        with self.assertRaises(ValueError): cv.candidate_prompt("w999999")

    def test_claims_do_not_become_ground_truth(self):
        clean=dict(observed_actions=["passage_or_waiting"],crossing_completion="not_confirmed")
        self.assertEqual(cv.claim(clean),"model_did_not_claim_climbing_not_verified_negative")
        self.assertEqual(cv.claim(dict(clean,observed_actions=["climbing_attempt_or_in_progress"])),
                         "model_claims_climbing_needs_human_review")
        self.assertEqual(cv.claim(None),"unreadable_or_invalid_model_output")
        self.assertEqual(cv.claim(dict(clean,crossing_completion="observed")),
                         "inconsistent_completion_claim_needs_review")

    def test_posthoc_reference_cannot_make_accuracy_claim(self):
        with tempfile.TemporaryDirectory() as p:
            out=Path(p)/"output.json"
            out.write_text(json.dumps(dict(
              status="three_cases_analyzed_not_automatically_verified",
              results=[dict(case_id=x[0],model_claim="model_undetermined")
                       for x in cv.EXPECTED])))
            observed=cv.posthoc_reference_review(out)
            self.assertEqual(len(observed),3)
            self.assertTrue(all(not x["visual_agreement_verified"] for x in observed))
            self.assertTrue(any(x["human_observation_scope"]=="no_climbing_human_confirmed_in_window"
                                for x in observed))


class FakeFrame:
    def __init__(self,index):
        self.pts=index
        self.time_base=Fraction(1,30)
        self.duration=1
        self.width=self.height=32
    def to_ndarray(self,format):
        if format!="rgb24":raise ValueError
        return np.full((32,32,3),self.pts%255,dtype=np.uint8)


class CandidateExecutionTests(unittest.TestCase):
    def exercise(self, root, fail=False):
        from mvp.method import analyzer_prompt
        manifest=cv.frozen_manifest()
        seen=[]
        class Analyzer:
            last_expanded_prompt=None
            last_processor_frames=None
            last_generated_token_ids=[]
            last_input_metadata=None
            def analyze(self,rgb,source,wid,roi):
                seen.append((wid,source,roi))
                self.last_expanded_prompt=analyzer_prompt(wid,'candidate-vlm')
                self.last_processor_frames=rgb
                self.last_generated_token_ids=[[1,2]]
                self.last_input_metadata={'observed_frames':len(rgb)}
                if fail: raise RuntimeError('synthetic generation failure')
                return dict(raw_response='fixture',parsed=None,parse={'status':'invalid'},
                            timing={'prepare_seconds':.1,'generation_seconds':.2},output_tokens=2)
        def sampled(video,start,end,count):
            return np.zeros((count,32,32,3),dtype=np.uint8),{'pts_seconds':[start+i*(end-start)/count for i in range(count)]}
        with patch.object(cv,'verify_candidate_events',return_value={'c030_cv':{},'c007_cv':{}}), \
             patch.object(cv,'sha256',side_effect=lambda p:next(x['source_sha256'] for x in manifest['videos'] if p.name==x['source_id']+'.mp4')), \
             patch.object(cv,'sample_original',side_effect=sampled), \
             patch('mvp.evidence.save_evidence',return_value={'frames':300}):
            result=cv.run_candidate_review(Analyzer(),root,{'dispatch_id':'synthetic'},
                {'cameras':{'C3':{'roi':[.6,0,.9,.6]},'C6':{'roi':[.28,.2,.75,.8]}}},
                {'videos':{x['source_id']:x['source_sha256'] for x in manifest['videos']}})
        return result,seen

    def test_three_calls_preserve_auditable_inputs_and_separate_costs(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)
            result,seen=self.exercise(root)
            self.assertEqual(len(seen),3)
            self.assertEqual([x[0] for x in seen],[x[1] for x in cv.EXPECTED])
            for row in result:
                target=root/'windows'/row['window_id']
                self.assertEqual(np.load(target/'processor_rgb.npy').shape[0],10)
                self.assertEqual(np.load(target/'generated_token_ids.npy').tolist(),[[1,2]])
                self.assertTrue((target/'expanded_prompt.txt').read_text().startswith('Clip ID: w'))
                self.assertEqual(row['cost_seconds']['generation'],.2)
                self.assertEqual(json.loads((target/'input_provenance.json').read_text())['run_context'],{'dispatch_id':'synthetic'})

    def test_failure_keeps_diagnostics_and_never_runs_next_case(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)
            with self.assertRaisesRegex(RuntimeError,'synthetic generation failure'):
                self.exercise(root,fail=True)
            target=root/'windows'/'w000001'
            self.assertEqual(json.loads((target/'failure.json').read_text())['generated_token_ids'],[[1,2]])
            self.assertTrue((target/'processor_rgb.npy').is_file())
            self.assertFalse((root/'windows'/'w000002').exists())
            self.assertFalse((root/'candidate_vlm_results.json').exists())


class FakeAV:
    def __init__(self,indices):
        stream=SimpleNamespace(average_rate=Fraction(30,1),guessed_rate=None,
                               width=32,height=32)
        self.streams=SimpleNamespace(video=[stream])
        self.indices=indices
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def decode(self,stream):
        return iter([FakeFrame(i) for i in self.indices])


class NativePTSTests(unittest.TestCase):
    def test_five_second_clip_has_ten_real_ordered_frame_samples(self):
        fake=SimpleNamespace(open=lambda *_:FakeAV(range(0,240)))
        with patch.dict(sys.modules,{"av":fake}):
            rgb,s=cv.sample_original("ignored",2,7)
        self.assertEqual(len(rgb),10)
        self.assertEqual(s["native_pts"],[60+15*i for i in range(10)])
        self.assertEqual(s["window_start"],2)
        self.assertEqual(s["window_end"],7)
        self.assertEqual(s["source_size"],[32,32])
        self.assertEqual(len(set(s["decoded_indices"])),10)

    def test_ten_second_clip_uses_ten_actual_frames_not_fictitious_midpoints(self):
        fake=SimpleNamespace(open=lambda *_:FakeAV(range(0,450)))
        with patch.dict(sys.modules,{"av":fake}):
            _,s=cv.sample_original("ignored",2,12)
        self.assertEqual(s["native_pts"],[60+30*i for i in range(10)])
        self.assertTrue(all(float(Fraction(p,30))==t for p,t in zip(s["native_pts"],s["pts_seconds"])))

    def test_native_missing_sample_does_not_repeat_frame(self):
        fake=SimpleNamespace(open=lambda *_:FakeAV([i for i in range(0,240) if i%15>2]))
        with patch.dict(sys.modules,{"av":fake}):
            _,s=cv.sample_original("ignored",2,7)
        self.assertEqual(len(s["native_pts"]),10)
        self.assertEqual(len(s["native_pts"]),len(set(s["native_pts"])))

    def test_truncated_input_rejected(self):
        fake=SimpleNamespace(open=lambda *_:FakeAV(range(0,100)))
        with patch.dict(sys.modules,{"av":fake}):
            with self.assertRaisesRegex(ValueError,"end was not observed"):
                cv.sample_original("ignored",2,7)

    def test_non_monotonic_native_pts_rejected(self):
        fake=SimpleNamespace(open=lambda *_:FakeAV([0,1,2,1,3,4,5,6,7,8,9,10,11,12]))
        with patch.dict(sys.modules,{"av":fake}):
            with self.assertRaisesRegex(ValueError,"Nonmonotonic"):
                cv.sample_original("ignored",0,1)


if __name__=="__main__":
    unittest.main()
