"""Official processor regressions on synthetic CPU pixels; no weight loading."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
from unittest import mock

from mvp.method import QwenAnalyzer, crop_frames, validate_source


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'existing VLM environment required')
class ContractTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.rgb = np.zeros((3, 96, 160, 3), dtype=np.uint8)
        self.source = dict(fps=30.0, pts_seconds=[1.0, 1.5, 2.0], native_pts=[30, 45, 60],
                           time_base='1/30', relative_indices=[0, 15, 30], source_size=[160, 96],
                           window_start=1.0, window_end=6.0, last_decoded_pts=2.0)

    def test_outward_crop_preserves_frame_order_and_pixels(self):
        for i in range(3):
            self.rgb[i] = i + 1
        cropped, bounds = crop_frames(self.rgb, [0.101, 0.101, 0.899, 0.899])
        self.assertEqual(bounds, [16, 9, 144, 87])
        self.assertEqual(cropped[:, 0, 0, 0].tolist(), [1, 2, 3])
        self.assertEqual(cropped.shape, (3, 78, 128, 3))

    def test_reject_invalid_rectangles_shapes_and_pixels(self):
        for roi in ([0, 0, 2, 1], [0.5, 0, 0.5, 1], [0, 0, 0.01, 1], [0, 0, float('nan'), 1]):
            with self.assertRaises(ValueError):
                crop_frames(self.rgb, roi)
        with self.assertRaises(ValueError):
            crop_frames(self.rgb.astype('float32'), [0, 0, 1, 1])

    def test_reject_future_or_unordered_observations_and_nonanonymous_id(self):
        validate_source(self.rgb, self.source, 'w000001')
        for key, value in (('pts_seconds', [1, 1.5, 6]), ('last_decoded_pts', 1.9),
                           ('relative_indices', [0, 30, 15]), ('source_size', [1, 1])):
            with self.assertRaises(ValueError):
                validate_source(self.rgb, {**self.source, key: value}, 'w000001')
        with self.assertRaises(ValueError):
            validate_source(self.rgb, self.source, 'E01_007_climbing')

    def test_single_observation_returns_no_generated_answer(self):
        source = copy.deepcopy(self.source)
        for key in ('pts_seconds', 'native_pts', 'relative_indices'):
            source[key] = source[key][:1]
        analyzer = object.__new__(QwenAnalyzer)
        result = analyzer.analyze(self.rgb[:1], source, 'w000001', [0, 0, 1, 1])
        self.assertIsNone(result['parsed'])
        self.assertEqual(result['parse']['status'], 'insufficient_frames')
        self.assertEqual(result['output_tokens'], 0)
        json.dumps(result, allow_nan=False)

    def test_zero_observations_never_index_last_pts_or_generate(self):
        source = copy.deepcopy(self.source)
        for key in ('pts_seconds', 'native_pts', 'relative_indices'):
            source[key] = []
        analyzer = object.__new__(QwenAnalyzer)
        result = analyzer.analyze(self.rgb[:0], source, 'w000001', [0, 0, 1, 1])
        self.assertEqual(result['parse']['status'], 'insufficient_frames')
        self.assertIsNone(result['input_metadata']['last_observed_pts'])
        self.assertEqual(result['output_tokens'], 0)
        json.dumps(result, allow_nan=False)


@unittest.skipUnless(importlib.util.find_spec('transformers'), 'existing VLM environment required')
class OfficialProcessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from transformers import AutoProcessor
        cls.processor = AutoProcessor.from_pretrained(
            '/home/jhc7484/dev/sceneguard-ai/weights/Qwen3-VL-2B-Instruct', local_files_only=True)

    def setUp(self):
        self.analyzer = object.__new__(QwenAnalyzer)
        self.analyzer.processor = self.processor

    def source(self, n=10, height=1080, width=1920):
        return dict(fps=30.0, pts_seconds=[54+i/2 for i in range(n)],
                    native_pts=[829440+i*7680 for i in range(n)], time_base='1/15360',
                    relative_indices=[i*15 for i in range(n)], source_size=[width, height],
                    window_start=54.0, window_end=59.0, last_decoded_pts=58.5,
                    filename='DO_NOT_SEND_FILENAME', previous_answer='DO_NOT_SEND_ANSWER',
                    ground_truth='DO_NOT_SEND_GT')

    def test_ten_full_frames_match_original_baseline_every_tensor_exactly(self):
        import numpy as np
        import torch
        from transformers import AutoConfig
        from vlm_batch.qwen import Adapter
        rgb = np.zeros((10, 1080, 1920, 3), dtype=np.uint8)
        for i in range(10):
            rgb[i, :, :, 0] = i*20
        rgb[:, :100, :, 1] = 220
        rgb[:, :, -100:, 2] = 240
        source = self.source()
        baseline = object.__new__(Adapter)
        baseline.processor = self.processor
        baseline.model = SimpleNamespace(config=AutoConfig.from_pretrained(
            '/home/jhc7484/dev/sceneguard-ai/weights/Qwen3-VL-2B-Instruct', local_files_only=True))
        prompt = (Path(__file__).resolve().parents[1] / 'configs/vlm_batch01_prompt.txt').read_text().strip()
        original, before, old_frames = baseline.prepare(rgb, source, prompt, 'w000001')
        self.processor.video_processor.sample_frames = lambda *a, **k: self.fail('additional sampling')
        inputs, info, frames = self.analyzer.prepare(rgb, source, 'w000001', [0, 0, 1, 1])
        self.assertEqual(set(original), set(inputs))
        for key in inputs:
            self.assertTrue(torch.equal(original[key], inputs[key]), key)
        self.assertTrue(np.array_equal(old_frames, frames))
        self.assertEqual(info['resized_shape'], [10, 3, 448, 768])
        self.assertEqual(info['visual_tokens'], 1680)
        self.assertEqual(info['temporal_padding_frames'], 0)
        decoded = self.processor.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=False)
        for forbidden in ('DO_NOT_SEND_FILENAME', 'DO_NOT_SEND_ANSWER', 'DO_NOT_SEND_GT'):
            self.assertNotIn(forbidden, decoded)
        json.dumps(info, allow_nan=False)
        self.assertFalse(torch.cuda.is_initialized())

    def test_odd_eof_frames_preserve_pts_and_log_official_tail_padding(self):
        import numpy as np
        import torch
        rgb = np.zeros((3, 96, 160, 3), dtype=np.uint8)
        for i in range(3):
            rgb[i] = i*40
        source = self.source(3, 96, 160)
        before = copy.deepcopy(source)
        inputs, info, frames = self.analyzer.prepare(rgb, source, 'w000002', [0, 0, 1, 1])
        self.assertEqual(source, before)
        self.assertEqual(info['observed_frames'], 3)
        self.assertEqual(info['processor_frames'], 4)
        self.assertEqual(info['temporal_padding_frames'], 1)
        self.assertEqual(info['temporal_padding_source_pts'], 55.0)
        self.assertEqual(info['source_pts'], [54.0, 54.5, 55.0])
        self.assertEqual(frames[:, 0, 0, 0].tolist(), [0, 40, 80])
        self.assertEqual(info['video_grid_thw'][0][0], 2)
        self.assertFalse(torch.cuda.is_initialized())

    def test_clip03_fractional_fps_expanded_tokens_match_original_baseline(self):
        import numpy as np
        import torch
        from transformers import AutoConfig
        from vlm_batch.qwen import Adapter
        rgb = np.zeros((10, 1080, 1920, 3), dtype=np.uint8)
        first_native = 10801791
        native = [first_native+i*45045 for i in range(10)]
        pts = [p/90000 for p in native]
        source = dict(fps=30000/1001, pts_seconds=pts, native_pts=native,
                      time_base='1/90000', relative_indices=list(range(0, 150, 15)),
                      source_size=[1920, 1080], window_start=pts[0], window_end=pts[0]+5,
                      last_decoded_pts=pts[-1])
        old = object.__new__(Adapter)
        old.processor = self.processor
        old.model = SimpleNamespace(config=AutoConfig.from_pretrained(
            '/home/jhc7484/dev/sceneguard-ai/weights/Qwen3-VL-2B-Instruct', local_files_only=True))
        prompt = (Path(__file__).resolve().parents[1] / 'configs/vlm_batch01_prompt.txt').read_text().strip()
        before, _, _ = old.prepare(rgb, source, prompt, 'clip03')
        after, _, _ = self.analyzer.prepare(rgb, source, 'clip03', [0, 0, 1, 1])
        for key in before:
            self.assertTrue(torch.equal(before[key], after[key]), key)

    def test_fixed_roi_changes_pixels_with_same_question_and_frame_times(self):
        import numpy as np
        rgb = np.zeros((2, 96, 160, 3), dtype=np.uint8)
        rgb[:, :, 40:120] = 200
        source = self.source(2, 96, 160)
        _, info, frames = self.analyzer.prepare(rgb, source, 'w000003', [0.25, 0, 0.75, 1])
        self.assertEqual(info['crop_bounds_xyxy'], [40, 0, 120, 96])
        self.assertEqual(info['source_pts'], source['pts_seconds'])
        self.assertEqual(info['temporal_padding_frames'], 0)
        self.assertTrue((frames == 200).all())

    def test_fractional_fps_pts_gap_keeps_decoded_indices_separate_from_captions(self):
        import numpy as np
        rgb = np.zeros((3, 96, 160, 3), dtype=np.uint8)
        source = dict(fps=30000/1001, pts_seconds=[0.0, 0.5005, 1.5015],
                      native_pts=[0, 15015, 45045], time_base=['1/30000']*3,
                      relative_indices=[0, 15, 30], decoded_indices=[100, 115, 130],
                      source_size=[160, 96], window_start=0.0, window_end=2.0, last_decoded_pts=1.5015)
        _, info, _ = self.analyzer.prepare(rgb, source, 'w000004', [0, 0, 1, 1])
        self.assertEqual(info['relative_indices'], [0, 15, 30])
        self.assertAlmostEqual(info['processor_timestamp_coordinates'][-1], 45.0)
        self.assertEqual(info['native_pts'], [0, 15015, 45045])
        self.assertEqual(info['temporal_padding_source_pts'], 1.5015)

    def test_decode_failure_keeps_current_ids_and_next_prepare_failure_clears_them(self):
        import numpy as np
        import torch
        class Inputs(dict):
            def to(self, device):
                return self
        analyzer = object.__new__(QwenAnalyzer)
        analyzer.settings = {'device': 'cpu'}
        analyzer.processor = SimpleNamespace(tokenizer=SimpleNamespace(decode=lambda *a, **k: 'synthetic'),
            batch_decode=mock.Mock(side_effect=RuntimeError('intentional decode failure')))
        analyzer.model = SimpleNamespace(generate=lambda **kwargs: torch.tensor([[0, 0, 17, 18, 19]]))
        analyzer.prepare = mock.Mock(return_value=(Inputs(input_ids=torch.tensor([[0, 0]])), {}, None))
        rgb = np.zeros((2, 96, 160, 3), dtype=np.uint8)
        source = self.source(2, 96, 160)
        with tempfile.TemporaryDirectory() as folder, mock.patch.multiple(torch.cuda,
                reset_peak_memory_stats=mock.Mock(), synchronize=mock.Mock()):
            analyzer.artifact_root = Path(folder)
            with self.assertRaisesRegex(RuntimeError, 'decode failure'):
                analyzer.analyze(rgb, source, 'w000001', [0, 0, 1, 1])
            saved = np.load(Path(folder) / 'w000001/generated_token_ids.npy', allow_pickle=False)
            self.assertEqual(saved.tolist(), [[17, 18, 19]])
            analyzer.prepare.side_effect = RuntimeError('intentional prepare failure')
            with self.assertRaisesRegex(RuntimeError, 'prepare failure'):
                analyzer.analyze(rgb, source, 'w000002', [0, 0, 1, 1])
            self.assertEqual(analyzer.last_generated_token_ids, [])
            self.assertFalse((Path(folder) / 'w000002/generated_token_ids.npy').exists())


@unittest.skipUnless(importlib.util.find_spec('transformers') and importlib.util.find_spec('mvp.pipeline'),
                     'integrated pipeline and existing VLM environment required')
class PipelineContractTests(unittest.TestCase):
    def video(self, path):
        import av
        import numpy as np
        with av.open(str(path), 'w') as output:
            stream = output.add_stream('libx264', rate=10)
            stream.width, stream.height, stream.pix_fmt = 64, 48, 'yuv420p'
            for i in range(31):
                frame = av.VideoFrame.from_ndarray(np.full((48, 64, 3), i, dtype=np.uint8), format='rgb24')
                for packet in stream.encode(frame):
                    output.mux(packet)
            for packet in stream.encode():
                output.mux(packet)
        return path

    def test_successful_full_fallback_reuses_actual_pipeline_persisted_result_shape(self):
        from mvp.pipeline import run_video
        from mvp.compare import ExactReuseAnalyzer, FingerprintedAnalyzer, read_baseline_results
        calls = []
        class FakeAnalyzer:
            def analyze(self, rgb, source, window_id, roi):
                calls.append(window_id)
                parsed = dict(observed_actions=['passage_or_waiting'], visible_evidence='CPU fixture',
                              crossing_completion='not_confirmed', uncertainties='synthetic only')
                return dict(raw_response=json.dumps(parsed), parsed=parsed, parse={'strict_parsed': parsed},
                            timing={'generation_seconds': 9.0}, input_metadata={}, output_tokens=12,
                            gpu_memory={'peak_allocated_bytes': 1})
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            video = self.video(root / 'synthetic.mp4')
            camera = {'camera_id': 'C4', 'roi': [0, 0, 1, 1]}
            baseline = FingerprintedAnalyzer(FakeAnalyzer(), 'fixed-model', 'fixed-settings-source')
            settings = {'safe_output_roots': [str(root / 'outputs')]}
            summary = run_video(video, camera, baseline, root / 'outputs/baseline', {}, settings)
            self.assertEqual(summary['status'], 'succeeded')
            records = read_baseline_results(root / 'outputs/baseline')
            self.assertTrue(records)
            old_calls = len(calls)
            with mock.patch('mvp.compare.successful_baseline', return_value={'test_only': True}):
                reuse = ExactReuseAnalyzer(baseline, records, 'a'*32, 'fixed-model', 'fixed-settings-source')
                summary = run_video(video, camera, reuse, root / 'outputs/roi', {}, settings)
            self.assertEqual(summary['status'], 'succeeded', summary)
            self.assertEqual(len(calls), old_calls)
            reused = [json.loads(p.read_text()) for p in (root / 'outputs/roi/windows').glob('*/result.json')]
            self.assertTrue(any(r.get('reused') for r in reused))
            for record in reused:
                if record.get('reused'):
                    self.assertEqual(record['output_tokens'], 12)
                    self.assertEqual(record['newly_generated_tokens'], 0)
                    self.assertIsNone(record['timing']['generation_seconds'])
                    self.assertEqual(record['reuse_provenance']['baseline_attempt'], 'a'*32)
                    self.assertEqual(record['reuse_provenance']['baseline_result_sha256'],
                                     records[record['reuse_provenance']['baseline_window_id']]['_reuse_binding']['sha256'])
            # Alter a response while leaving its semantic input hash unchanged:
            # the pinned exact bytes must reject this arbitrary output change.
            binding = records['w000001']['_reuse_binding']
            path = Path(binding['path'])
            changed = json.loads(path.read_text())
            changed['raw_response'] = 'arbitrary changed answer'
            path.write_text(json.dumps(changed))
            with mock.patch('mvp.compare.successful_baseline', return_value={'test_only': True}):
                tampered = ExactReuseAnalyzer(baseline, records, 'a'*32, 'fixed-model', 'fixed-settings-source')
                summary = run_video(video, camera, tampered, root / 'outputs/tampered', {}, settings)
            self.assertEqual(summary['status'], 'failed')
            self.assertIn('pinned baseline result bytes changed', summary['failure']['message'])

    def test_window_native_gap_fractional_fps_and_eof_shapes_reach_official_method(self):
        import numpy as np
        from mvp.windows import Sample, Window
        from transformers import AutoProcessor
        analyzer = object.__new__(QwenAnalyzer)
        analyzer.processor = AutoProcessor.from_pretrained(
            '/home/jhc7484/dev/sceneguard-ai/weights/Qwen3-VL-2B-Instruct', local_files_only=True)
        frames = [Sample(np.zeros((48, 64, 3), dtype=np.uint8), p/30000, p, '1/30000', i, p/30000)
                  for p, i in ((0, 100), (15015, 115), (45045, 130))]
        for n in (0, 1, 3):
            window = Window('w000001', 0.0, 2.0, 5.0, tuple(frames[:n]), 30000/1001, (64, 48), 1.5015, True)
            if n < 2:
                result = analyzer.analyze(window.rgb, window.source(), window.window_id, [0, 0, 1, 1])
                self.assertEqual(result['parse']['status'], 'insufficient_frames')
            else:
                _, info, _ = analyzer.prepare(window.rgb, window.source(), window.window_id, [0, 0, 1, 1])
                self.assertEqual(info['relative_indices'], [0, 15, 30])
                self.assertEqual(info['source_pts'], [0.0, 0.5005, 1.5015])
                self.assertAlmostEqual(info['processor_timestamp_coordinates'][-1], 45.0)
                self.assertEqual(info['temporal_padding_frames'], 1)


if __name__ == '__main__':
    unittest.main()
