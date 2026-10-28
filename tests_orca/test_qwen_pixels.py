"""Focused official CPU processor checks; synthetic pixels, no weights/CUDA."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

from vlm_batch.qwen import Adapter as Baseline
from vlm_batch.qwen_high_pixels import Adapter as HighPixels


class PresetTests(unittest.TestCase):
    def test_only_frozen_pixel_budget_differs(self):
        self.assertIs(HighPixels.__init__, Baseline.__init__)
        self.assertIs(HighPixels.prepare, Baseline.prepare)
        self.assertEqual(Baseline.PROCESSOR_SIZE,
                         {'shortest_edge': 16384, 'longest_edge': 3584000})
        self.assertEqual(HighPixels.PROCESSOR_SIZE,
                         {'shortest_edge': 16384, 'longest_edge': 7168000})


@unittest.skipUnless(importlib.util.find_spec('transformers'), 'existing VLM environment required')
class OfficialProcessorTests(unittest.TestCase):
    def test_geometry_full_screen_frame_order_and_no_sampling(self):
        import numpy as np
        import torch
        from transformers import AutoConfig, AutoProcessor
        model_dir = Path('/home/jhc7484/dev/sceneguard-ai/weights/Qwen3-VL-2B-Instruct')
        processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
        processor.video_processor.sample_frames = lambda *a, **k: self.fail('extra sampling')
        config = AutoConfig.from_pretrained(model_dir, local_files_only=True)
        rgb = np.zeros((10, 1080, 1920, 3), dtype=np.uint8)
        for index in range(10):
            rgb[index, :, :, 0] = index * 20
        rgb[:, :100, :, 1] = 220
        rgb[:, -100:, :, 1] = 180
        rgb[:, :, :100, 2] = 40
        rgb[:, :, -100:, 2] = 240
        source = {'fps': 30000 / 1001, 'relative_indices': list(range(0, 150, 15)),
                  'evaluation_note': 'DO_NOT_SEND_LABELS'}
        prompt = (Path(__file__).resolve().parents[1] / 'configs/vlm_batch01_prompt.txt').read_text().strip()
        results = []
        for cls in (Baseline, HighPixels):
            adapter = object.__new__(cls)
            adapter.processor = processor
            adapter.model = SimpleNamespace(config=config)
            inputs, info, frames = adapter.prepare(rgb, source, prompt, 'clip03')
            h, w = frames.shape[1:3]
            self.assertEqual(frames[:, h // 2, w // 2, 0].tolist(), list(range(0, 200, 20)))
            for positions, expected in (((0, w // 2, 1), 220), ((h - 1, w // 2, 1), 180),
                                        ((h // 2, 0, 2), 40), ((h // 2, w - 1, 2), 240)):
                self.assertEqual(frames[:, positions[0], positions[1], positions[2]].tolist(), [expected] * 10)
            decoded = processor.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=False)
            self.assertIn(prompt, decoded)
            self.assertNotIn('DO_NOT_SEND_LABELS', decoded)
            self.assertFalse(info['extra_sampling'])
            self.assertEqual(info['temporal_padding_frames'], 0)
            self.assertEqual(info['resize_calls'], 1)
            grid = info['video_grid_thw'][0]
            self.assertEqual(grid, [5, h // 16, w // 16])
            self.assertEqual(info['visual_tokens'], 5 * (h // 16) * (w // 16) // 4)
            results.append(info)
        self.assertEqual(results[0]['resized_shape'], [10, 3, 448, 768])
        self.assertEqual(results[0]['visual_tokens'], 1680)
        self.assertEqual(results[1]['resized_shape'], [10, 3, 608, 1120])
        self.assertEqual(results[1]['video_grid_thw'], [[5, 38, 70]])
        self.assertEqual(results[1]['visual_tokens'], 3325)
        self.assertEqual(results[1]['input_tokens'], 3588)
        self.assertFalse(torch.cuda.is_initialized())
        print('Official CPU geometry:', results, flush=True)


if __name__ == '__main__':
    unittest.main()
