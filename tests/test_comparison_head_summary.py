import unittest
from unittest.mock import patch
from scripts.summarize_model_comparison_heads import verified_raw_models, MODELS


class FixedDenominatorTests(unittest.TestCase):
    def test_completion_boolean_cannot_drop_any_of_eight_models(self):
        for missing in MODELS:
            with self.assertRaisesRegex(ValueError,'Exact eight'):
                verified_raw_models(dict(cohort_sha256='h',all_eight_full_passes_complete=True,
                                         models={m:{} for m in MODELS if m!=missing}),'h')

    def test_r3d_also_requires_actual_complete_full_pass(self):
        def provenance(path,cohort):
            return dict(model_id=path,status='smoke_passed' if path=='r3d18_exp0064' else 'inference_complete',
                        scored_windows=6219,decoded_native_frames=184300,videos=list(range(45))),{'result_path':path}
        summary=dict(cohort_sha256='h',all_eight_full_passes_complete=True,models={m:dict(
            status='inference_complete',windows=6219,decoded_native_frames=184300,provenance={'result_path':m}) for m in MODELS})
        with patch('scripts.summarize_model_comparison_heads.result_provenance',side_effect=provenance):
            with self.assertRaisesRegex(ValueError,'Actual completed'):verified_raw_models(summary,'h')


if __name__=='__main__':unittest.main()
