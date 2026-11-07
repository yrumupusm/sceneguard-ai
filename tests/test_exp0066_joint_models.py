import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('exp0066_joint', ROOT / 'scripts/exp0066_joint_models.py')
j = importlib.util.module_from_spec(spec); sys.modules[spec.name] = j; spec.loader.exec_module(j)


class GeometryTests(unittest.TestCase):
    def test_landscape_full_field_without_center_crop(self):
        g = j.resize_geometry(1080, 1920, 'evad_vitb_vmaev2')
        self.assertEqual((g['resized_height'], g['resized_width']), (288, 512))
        b, valid = j.boxes_to_original([[0, 0, 512, 288]], g)
        np.testing.assert_allclose(b, [[0, 0, 1920, 1080]])
        self.assertEqual(valid, [True]); self.assertFalse(g['crop'])

    def test_rounding_and_padding_do_not_change_box_domain(self):
        g = j.resize_geometry(1080, 1920, 'stmixer_vitb_vmaev2')
        self.assertEqual((g['resized_height'], g['resized_width'], g['padded_width']), (256, 455, 480))
        b, _ = j.boxes_to_original([[0, 0, 1, 1]], g, normalized=True)
        np.testing.assert_allclose(b, [[0, 0, 1920, 1080]])

    def test_portrait_inverse_has_separate_axis_rounding(self):
        g = j.resize_geometry(1001, 333, 'evad_vitl')
        source = np.array([[25, 100, 301, 900]], float)
        scaled = source * ([g['scale_x'], g['scale_y']] * 2)
        b, _ = j.boxes_to_original(scaled, g)
        np.testing.assert_allclose(b, source)

    def test_extreme_stm_aspect_ratio_is_explicit_failure(self):
        with self.assertRaises(ValueError): j.resize_geometry(100, 10000, 'stmixer_vitb_vmaev2')
        self.assertLessEqual(j.resize_geometry(100, 10000, 'evad_vitl')['resized_width'], 1333)

    def test_outside_and_degenerate_queries_retained_with_flags(self):
        g = j.resize_geometry(1080, 1920, 'evad_vitb_vmaev2')
        b, valid = j.boxes_to_original([[-100, -100, 700, 500], [10, 20, 10, 40]], g)
        self.assertEqual(len(b), 2); self.assertEqual(valid, [True, False])
        np.testing.assert_allclose(b[0], [0, 0, 1920, 1080])

    def test_nonfinite_boxes_fail_closed(self):
        with self.assertRaises(ValueError): j.boxes_to_original([[0, 0, np.nan, 1]], {})


class PreprocessingTests(unittest.TestCase):
    def test_rgb_channels_mean_std_and_no_temporal_resampling(self):
        import torch
        frames = np.zeros((16, 36, 64, 3), np.uint8)
        frames[..., 0] = 255
        frames[:, :, :, 1] = np.arange(16)[:, None, None]
        tensor, geometry = j.preprocess_clip(frames, {'model_id':'evad_vitb_vmaev2'})
        self.assertEqual(tuple(tensor.shape), (3, 16, 288, 512))
        self.assertAlmostEqual(tensor[0, 0, 0, 0].item(), (1-.45)/.225, places=6)
        np.testing.assert_allclose(tensor[1, :, 0, 0].numpy(), (np.arange(16)/255-.45)/.225, atol=1e-6)
        self.assertEqual(geometry['field_of_view'], 'entire_input_frame')
        self.assertFalse(torch.cuda.is_initialized())

    def test_bad_input_shape_dtype_is_not_silently_filled(self):
        for frames in (np.zeros((15, 8, 8, 3), np.uint8), np.zeros((16, 8, 8, 3), float)):
            with self.assertRaises(ValueError): j.preprocess_clip(frames, {'model_id':'evad_vitl'})

    def test_spatial_control_requires_label(self):
        frames = np.zeros((16, 36, 64, 3), np.uint8)
        with self.assertRaises(ValueError): j.preprocess_clip(frames, {'model_id':'evad_vitl','spatial_control_short_side':224})

    def test_matches_official_evad_image_mapper_without_model_forward(self):
        import torch
        sys.path.insert(0, str(ROOT / 'runtime/vendor/EVAD-exp0066'))
        from projects.evad.models import add_evad_config
        from slowfast.config.defaults import get_cfg
        from slowfast.datasets.dataset_mapper import SparseDatasetMapper
        cfg = get_cfg(); add_evad_config(cfg)
        cfg.merge_from_file(str(ROOT / 'runtime/vendor/EVAD-exp0066/projects/evad/configs/ViT_B_16x4_KTP.yaml'))
        frames = np.random.default_rng(66).integers(0, 256, (16, 45, 83, 3), dtype=np.uint8)
        expected, _ = SparseDatasetMapper(cfg, is_train=False)([f[..., ::-1].copy() for f in frames], np.zeros((0, 4), np.float32))
        actual, _ = j.preprocess_clip(frames, {'model_id':'evad_vitb_vmaev2'})
        torch.testing.assert_close(actual, expected, rtol=0, atol=1e-6)

    def test_matches_official_stm_image_transform_without_model_forward(self):
        import torch
        sys.path.insert(0, str(ROOT / 'runtime/vendor/STMixer-exp0066'))
        from alphaction.dataset.datasets.ava_dataset import Ava
        mapper = object.__new__(Ava)
        mapper._split = 'test'; mapper._jitter_min_scale = [256]; mapper._jitter_max_scale = 1333
        mapper._test_force_flip = False; mapper._data_mean = [.45]*3; mapper._data_std = [.225]*3
        mapper._use_bgr = False
        frames = np.random.default_rng(67).integers(0, 256, (16, 45, 83, 3), dtype=np.uint8)
        expected, _ = mapper._images_and_boxes_preprocessing_cv2([f[..., ::-1].copy() for f in frames], np.zeros((0, 4), np.float32))
        actual, _ = j.preprocess_clip(frames, {'model_id':'stmixer_vitb_vmaev2'})
        torch.testing.assert_close(actual, expected, rtol=0, atol=1e-6)


class ContractTests(unittest.TestCase):
    def test_exact_three_joint_candidates_remain_separate(self):
        self.assertEqual(set(j.MODELS), {'evad_vitb_vmaev2','evad_vitl','stmixer_vitb_vmaev2'})

    def test_ava_label20_is_not_renamed_cctv_climbing_probability(self):
        labels = j.read(j.LABELS)['labels']
        self.assertEqual(len(labels), 80)
        self.assertEqual(labels['20'], 'climb (e.g., a mountain)')
        self.assertIn('not_CCTV', j.SEMANTICS)

    def test_wrong_checkpoint_or_vendor_binding_rejected_before_model_import(self):
        with self.assertRaises(ValueError):
            j.validate_spec(dict(model_id='evad_vitl', vendor_path='/wrong', vendor_commit='bad'))

    def test_physical_clip_clock_is_two_seconds_not_twenty_native3fps_seconds(self):
        offsets = [(i-8)*4/30 for i in range(16)]
        self.assertAlmostEqual(offsets[-1]-offsets[0], 2.)
        self.assertGreater(max(offsets), 0)

    def test_probability_contract_refuses_logits_and_partial_class_scores(self):
        j.validate_scores(np.ones(100)*.5, np.zeros((100, 80)))
        with self.assertRaises(ValueError): j.validate_scores(np.ones(100)*1.2, np.zeros((100, 80)))
        with self.assertRaises(ValueError): j.validate_scores(np.ones(100)*.5, np.zeros((100, 60)))
        with self.assertRaises(ValueError): j.validate_scores(np.ones(99)*.5, np.zeros((99, 80)))

    def test_cpu_forward_refused_before_any_native_call(self):
        import torch
        class Native:
            def parameters(self): return iter([torch.zeros(1)])
            def __call__(self, *args): raise AssertionError('No native forward may execute')
        spec = dict(model_id='evad_vitl', checkpoint_sha256='test')
        model = j.JointModel(Native(), spec, {}, {})
        with self.assertRaisesRegex(ValueError, 'No CPU forward'):
            j.infer_clip(model, np.zeros((16, 36, 64, 3), np.uint8), spec)


if __name__ == '__main__': unittest.main()
