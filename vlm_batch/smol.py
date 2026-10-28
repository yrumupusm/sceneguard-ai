"""Pinned SmolVLM2 video baseline; model construction belongs to the GPU queue.

``prepare`` can also be exercised with a processor alone for CPU validation.
No media paths, manifest labels, prior answers, or source filenames enter text.
"""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoProcessor
from transformers.video_utils import VideoMetadata

MODEL_ID = "HuggingFaceTB/SmolVLM2-2.2B-Instruct"
REVISION = "482adb537c021c86670beed01cd58990d01e72e4"
BASELINE_SETTINGS = {
    "seed": 0, "do_sample": False, "max_new_tokens": 384, "repetition_penalty": 1.0,
    "dtype": "bfloat16", "attention": "sdpa", "device": "cuda:0", "batch_size": 1,
}
PREPROCESSING = {
    "do_sample_frames": False,
    "do_resize": True,
    "size": {"longest_edge": 384},
    "do_pad": True,
}


def load_processor(model_dir):
    """CPU-only loading of official local processor/tokenizer, never weights."""
    processor = AutoProcessor.from_pretrained(
        model_dir, local_files_only=True, trust_remote_code=False)
    vp = processor.video_processor
    if (vp.max_image_size != {"longest_edge": 384} or processor.image_seq_len != 81
            or list(vp.image_mean) != [0.5, 0.5, 0.5]
            or list(vp.image_std) != [0.5, 0.5, 0.5]
            or not vp.do_rescale or not vp.do_normalize or not vp.do_convert_rgb
            or int(vp.resample) != 1
            or not np.isclose(vp.rescale_factor, 1 / 255)):
        raise ValueError("official processor differs from frozen Smol baseline")
    return processor


class Adapter:
    def __init__(self, model_dir, settings):
        if settings != BASELINE_SETTINGS:
            raise ValueError("Smol baseline settings must match the frozen contract")
        self.settings = json.loads(json.dumps(settings))
        self.processor = load_processor(model_dir)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_dir, local_files_only=True, trust_remote_code=False,
            torch_dtype=torch.bfloat16, attn_implementation="sdpa",
            device_map={"": "cuda:0"},
        ).eval()
        self.model_metadata = {
            "model_parameter_dtypes": sorted({str(p.dtype) for p in self.model.parameters()}),
            "attention_model": self.model.config._attn_implementation,
            "attention_text": self.model.config.text_config._attn_implementation,
            "attention_vision": self.model.config.vision_config._attn_implementation,
            "model_config_use_cache": self.model.config.use_cache,
            "generation_config_use_cache": self.model.generation_config.use_cache,
        }

    def prepare(self, rgb, source, prompt, clip_id):
        if self.settings != BASELINE_SETTINGS:
            raise ValueError("Smol settings changed after initialization")
        if (not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8
                or rgb.shape != (10, 1080, 1920, 3)):
            raise ValueError("expected ten original full-screen RGB frames")
        if source["clip_id"] != clip_id or len(source["frames"]) != 10:
            raise ValueError("clip identity/frame count mismatch")
        if list(rgb.shape) != source["source_shape"]:
            raise ValueError("source RGB shape mismatch")
        indices = source["relative_indices"]
        fps = float(source["fps"])
        pts = [float(frame["pts"]) for frame in source["frames"]]
        targets = [float(frame["target"]) for frame in source["frames"]]
        relative_pts = [value - pts[0] for value in pts]
        timestamps = [index / fps for index in indices]
        native_seconds = [frame["native_pts"] * float(Fraction(frame["time_base"]))
                          for frame in source["frames"]]
        if (len(indices) != 10 or any(b <= a for a, b in zip(indices, indices[1:]))
                or not np.allclose(native_seconds, pts, rtol=0, atol=1e-6)
                or not np.allclose(timestamps, relative_pts, rtol=0, atol=1e-6)
                or not np.allclose(np.array(targets) - targets[0], np.arange(10) / 2,
                                   rtol=0, atol=1e-6)
                or any(p < t - 1e-6 or p - t > 1 / fps + 1e-6 for p, t in zip(pts, targets))):
            raise ValueError("native frame order/timestamps differ from fixed 2fps input")
        video_metadata = VideoMetadata(
            total_num_frames=int(round(fps * 5)), fps=fps, duration=5.0,
            width=rgb.shape[2], height=rgb.shape[1], frames_indices=list(indices),
            video_backend="preselected_native_pts_rgb_cache",
        )
        messages = [{"role": "user", "content": [
            {"type": "video"}, {"type": "text", "text": f"Clip ID: {clip_id}\n" + prompt}]}]
        text = self.processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False)
        # This is one VIDEO, not ten independently templated images. Do not
        # tokenize through the template: direct video arrays retain supplied PTS.
        inputs = self.processor(
            text=text, videos=[[rgb]], video_metadata=[video_metadata],
            return_tensors="pt", **PREPROCESSING,
        )
        values = inputs["pixel_values"]
        mask = inputs["pixel_attention_mask"]
        image_tokens = int((inputs["input_ids"] == self.processor.image_token_id).sum())
        if tuple(values.shape) != (1, 10, 3, 384, 384) or image_tokens != 810:
            raise ValueError("unexpected native video frame/token geometry")
        if tuple(mask.shape) != (1, 10, 384, 384) or not bool(mask.all()):
            raise ValueError("unexpected native video padding")
        # Official uint8 resize precedes normalization; inversion restores the
        # actual full-screen resized RGB that the model receives, for local review.
        actual = ((values[0].float().cpu() * 0.5 + 0.5) * 255).round().clamp(0, 255)
        actual_rgb_frames = actual.to(torch.uint8).permute(0, 2, 3, 1).contiguous().numpy()
        vp = self.processor.video_processor
        metadata = {
            "model": MODEL_ID, "revision": REVISION,
            "modality": "one_native_video", "source_shape": list(rgb.shape),
            "frames_before_processor": 10, "frames_after_processor": 10,
            "sampling": "disabled; source order retained", "source_pts": pts,
            "native_pts": [frame["native_pts"] for frame in source["frames"]],
            "sampling_target_seconds": targets,
            "time_bases": [frame["time_base"] for frame in source["frames"]],
            "relative_indices": list(indices), "source_fps": fps,
            "model_relative_timestamps_seconds": timestamps,
            "timestamp_text": [f"{int(t // 60):02d}:{int(t % 60):02d}" for t in timestamps],
            "timestamp_limitation": "official video prompt truncates subsecond timestamps; frames are not duplicated",
            "video_duration_seconds": 5.0, "last_sample_seconds": relative_pts[-1],
            "resize_stages_hw": [[216, 384], [384, 384]],
            "full_screen": True, "crop": False, "image_splitting": False,
            "aspect_ratio_preserved": False,
            "resample_requested": "LANCZOS", "resample_actual": "BICUBIC (official torch fallback)",
            "antialias": True, "pixel_values_shape": list(values.shape),
            "pixel_attention_mask_shape": list(mask.shape), "padding_pixels": 0,
            "normalization": {"rescale_factor": vp.rescale_factor,
                              "mean": list(vp.image_mean), "std": list(vp.image_std)},
            "vision_patch_size": 14, "vision_patch_grid": [27, 27],
            "pixel_shuffle_scale": 3, "visual_tokens_per_frame": 81,
            "visual_tokens": image_tokens, "input_tokens": int(inputs["input_ids"].shape[-1]),
            "actual_rgb_shape": list(actual_rgb_frames.shape),
            "actual_rgb_sha256": hashlib.sha256(actual_rgb_frames.tobytes()).hexdigest(),
            "text_before_video_expansion_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "processor_settings": json.loads(json.dumps(PREPROCESSING)),
            "runtime_settings": json.loads(json.dumps(self.settings)),
        }
        inputs["pixel_values"] = values.to(torch.bfloat16)
        metadata["pixel_values_runtime_dtype"] = str(inputs["pixel_values"].dtype)
        metadata.update(getattr(self, "model_metadata", {}))
        return inputs, metadata, actual_rgb_frames


def validate_cpu(model_dir, prompt):
    """Synthetic video only: prove modality/order/full-screen framing without a model."""
    adapter = object.__new__(Adapter)
    adapter.settings = json.loads(json.dumps(BASELINE_SETTINGS))
    adapter.processor = load_processor(model_dir)

    def no_sampling(*args, **kwargs):
        raise AssertionError("preselected video must never be sampled again")

    adapter.processor.video_processor.sample_frames = no_sampling
    rgb = np.empty((10, 1080, 1920, 3), dtype=np.uint8)
    for index in range(10):
        rgb[index] = [index * 20, 50, 150]
    # Distinct wide borders catch cropping and preserve temporal markers centrally.
    rgb[:, :100, :, 1] = 220
    rgb[:, -100:, :, 1] = 180
    rgb[:, :, :100, 2] = 40
    rgb[:, :, -100:, 2] = 240
    source = {
        "clip_id": "synthetic", "source_shape": list(rgb.shape), "fps": 30.0,
        "relative_indices": list(range(0, 150, 15)),
        "frames": [{"pts": index / 2, "target": index / 2, "native_pts": index * 7680,
                    "time_base": "1/15360"} for index in range(10)],
        "evaluation_note": "NEVER_SEND_EVALUATION_TO_MODEL",
    }
    inputs, metadata, actual = adapter.prepare(rgb, source, prompt, "synthetic")
    assert actual[:, 192, 192, 0].tolist() == list(range(0, 200, 20)), "frame order changed"
    assert actual[:, 0, 192, 1].tolist() == [220] * 10, "top border lost"
    assert actual[:, -1, 192, 1].tolist() == [180] * 10, "bottom border lost"
    assert actual[:, 192, 0, 2].tolist() == [40] * 10, "left border lost"
    assert actual[:, 192, -1, 2].tolist() == [240] * 10, "right border lost"
    decoded = adapter.processor.tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=False)
    assert "NEVER_SEND_EVALUATION_TO_MODEL" not in decoded
    assert decoded.count("Frame from ") == 10
    assert "series of ten frames from a 0:00:05" in decoded
    assert decoded.count("Frame from 00:00:") == 2
    assert prompt in decoded
    assert metadata["visual_tokens"] == 810
    assert len({hashlib.sha256(frame.tobytes()).hexdigest() for frame in actual}) == 10
    corrupted = json.loads(json.dumps(source))
    corrupted["relative_indices"][1] = 0
    try:
        adapter.prepare(rgb, corrupted, prompt, "synthetic")
    except ValueError:
        pass
    else:
        raise AssertionError("duplicated source index accepted")
    fractional = json.loads(json.dumps(source))
    fractional["fps"] = 30000 / 1001
    fractional["frames"] = [
        {"pts": 120.0199 + index * 0.5005, "target": 120 + index / 2,
         "native_pts": 359700 + index * 1500, "time_base": "1001/3000000"}
        for index in range(10)]
    _, fractional_info, fractional_actual = adapter.prepare(rgb, fractional, prompt, "synthetic")
    assert np.array_equal(fractional_actual, actual)
    assert np.isclose(fractional_info["model_relative_timestamps_seconds"][-1], 4.5045)
    assert not torch.cuda.is_initialized(), "CPU validation initialized CUDA"
    return {
        "validation": "passed", "synthetic_only": True, "model_loaded": False,
        "cuda_initialized": False,
        "checks": ["one_native_video", "ten_unique_ordered_frames", "sampling_not_called",
                   "four_full_screen_borders", "source_metadata_excluded_from_text",
                   "ten_official_timestamp_captions", "common_prompt_unchanged",
                   "810_visual_tokens", "duplicate_source_index_rejected",
                   "2997fps_native_pts_preserved", "cuda_not_initialized"],
        "metadata": metadata,
        "fractional_fps_metadata": fractional_info,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CPU-only synthetic Smol processor validation")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_cpu(args.model_dir, args.prompt.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in result if not key.endswith("metadata")}))
