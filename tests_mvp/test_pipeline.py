import json
import importlib.util
from fractions import Fraction
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

import av
import numpy as np

from mvp.evidence import create_output, save_evidence
from mvp.pipeline import run_video
from tests_mvp.test_events import result
from tests_mvp.test_windows import write_video


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


class PipelineFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = write_video(self.root / "source.mp4")
        self.output = self.root / "outputs" / "attempt"
        self.settings = {"safe_output_roots": [str(self.root / "outputs")]}
        self.camera = {"camera_id": "test-camera", "roi": [.2, .1, .9, .8]}

    def tearDown(self):
        self.temp.cleanup()

    def run_pipeline(self, analyzer, video=None):
        return run_video(video or self.video, self.camera, analyzer, self.output,
                         {"test_only": True, "evaluation_observation": "NEVER SEND TO ANALYZER"}, self.settings)


class PipelineTests(PipelineFixture):

    def test_full_eof_raw_prompt_flush_merge_and_evidence(self):
        calls = []
        def analyze(rgb, source, window_id, roi):
            self.assertEqual(rgb.dtype, np.uint8)
            self.assertEqual(tuple(rgb.shape[1:]), (48, 64, 3))
            self.assertEqual(roi, self.camera["roi"])
            self.assertNotIn("NEVER SEND TO ANALYZER", json.dumps(source))
            self.assertNotIn("source.mp4", json.dumps(source))
            self.assertEqual(window_id, f"w{len(calls) + 1:06d}")
            self.assertTrue(all(t < source["window_end"] for t in source["pts_seconds"]))
            if calls:
                self.assertTrue((self.output / "windows" / calls[-1] / "result.json").is_file())
                self.assertTrue((self.output / "emissions.jsonl").read_text())
            calls.append(window_id)
            return result(["stepping_over_boundary"])
        summary = self.run_pipeline(analyze)
        self.assertTrue(summary["functional_success"], summary)
        self.assertEqual(summary["action_quality"], "not_evaluated")
        self.assertEqual(summary["windows_completed"], 4)
        self.assertEqual(len(calls), 3)
        self.assertEqual(summary["window_state_counts"]["insufficient_data"], 1)
        self.assertIsNone(summary["realtime_latency_seconds"])
        events = read_jsonl(self.output / "events.jsonl")
        candidate = next(e for e in events if e["state"] == "candidate")
        self.assertEqual(candidate["constituent_windows"], ["w000001", "w000002", "w000003"])
        self.assertEqual(candidate["first_available_at_source_time"], 5.0)
        self.assertEqual(candidate["first_last_input_pts"], 4.5)
        claim = candidate["constituents"][0]
        self.assertEqual(claim["model_claims"]["visible_evidence"], "synthetic evidence")
        self.assertEqual(claim["model_claims"]["uncertainties"], "")
        self.assertEqual(claim["model_claims"]["crossing_completion"], "not_confirmed")
        self.assertEqual(claim["result"], "windows/w000001/result.json")
        self.assertFalse(claim["claims_are_ground_truth"])
        self.assertLess(candidate["first_emission"]["monotonic_ns"], candidate["final_merge_at"]["monotonic_ns"])
        self.assertGreaterEqual(candidate["evidence"]["saved_at"]["monotonic_ns"], candidate["final_merge_at"]["monotonic_ns"])
        self.assertEqual(candidate["evidence"]["clipped_interval"], [0, 8])
        for name in calls:
            saved = json.loads((self.output / "windows" / name / "result.json").read_text())
            self.assertEqual(saved["raw_response"], "synthetic test only")
        self.assertEqual(json.loads((self.output / "summary.json").read_text()), summary)

    def test_unknown_never_normal_and_completion_only_does_not_create_candidate(self):
        replies = iter([result(["passage_or_waiting"], "observed"), {"parsed": None}, result(["indeterminate"])])
        summary = self.run_pipeline(lambda *args: next(replies))
        self.assertTrue(summary["functional_success"])
        self.assertNotIn("candidate", summary["event_state_counts"])
        self.assertEqual(summary["window_state_counts"]["observed_other"], 1)
        self.assertEqual(summary["event_state_counts"]["parse_failed"], 1)
        self.assertEqual(summary["event_state_counts"]["indeterminate"], 1)

    def test_single_frame_never_calls_model(self):
        video = write_video(self.root / "single.mp4", count=1)
        def forbidden(*args):
            raise AssertionError("must not analyze an insufficient tail")
        summary = self.run_pipeline(forbidden, video)
        self.assertTrue(summary["functional_success"], summary)
        self.assertEqual(summary["analyzer_calls"], 0)
        self.assertEqual(summary["window_state_counts"], {"insufficient_data": 1})

    def test_execution_failure_preserves_partial_result_and_stops_without_retry(self):
        calls = []
        def analyze(*args):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("intentional CPU test failure")
            return result(["contact"])
        summary = self.run_pipeline(analyze)
        self.assertEqual(summary["status"], "failed")
        self.assertFalse(summary["functional_success"])
        self.assertFalse(summary["eof_reached"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(summary["windows_completed"], 1)
        self.assertEqual(summary["failure"]["window_id"], "w000002")
        self.assertTrue((self.output / "windows/w000001/result.json").is_file())
        self.assertTrue((self.output / "windows/w000002/result.json").is_file())
        self.assertTrue((self.output / "failure.json").is_file())

    def test_failure_tokens_belong_only_to_current_call_through_wrapper(self):
        for stage in ("prepare", "decode"):
            self.output = self.root / "outputs" / stage
            class Analyzer:
                last_generated_token_ids = []
                last_expanded_prompt = None
                calls = 0
                def analyze(inner, *args):
                    inner.calls += 1
                    if inner.calls == 1:
                        inner.last_generated_token_ids = [[11, 12]]
                        inner.last_expanded_prompt = "first prompt"
                        return result(["passage_or_waiting"])
                    if stage == "decode":
                        inner.last_generated_token_ids = [[71, 72]]
                        inner.last_expanded_prompt = "current prompt"
                    raise ValueError(f"intentional {stage} failure")
            class Wrapper:
                def __init__(inner):
                    inner.analyzer = Analyzer()
                def analyze(inner, *args):
                    return inner.analyzer.analyze(*args)
            summary = self.run_pipeline(Wrapper())
            self.assertEqual(summary["status"], "failed")
            saved = json.loads((self.output / "windows/w000002/result.json").read_text())
            self.assertEqual(saved["generated_token_ids"], [[71, 72]] if stage == "decode" else [])
            self.assertEqual(saved["expanded_prompt"], "current prompt" if stage == "decode" else None)

    def test_evidence_is_clipped_and_original_context_with_no_overwrite(self):
        evidence = self.root / "clip.mp4"
        saved = save_evidence(self.video, evidence, interval=[.5, 1.5], source_bounds=[0, 8], context_seconds=2)
        self.assertEqual(saved["clipped_interval"], [0, 3.5])
        self.assertAlmostEqual(saved["encoded_duration_seconds"], 3.5, places=2)
        self.assertAlmostEqual(saved["last_source_pts"], 3.4, places=3)
        with av.open(str(evidence)) as decoded:
            frames = list(decoded.decode(video=0))
        self.assertEqual(len(frames), 35)
        self.assertEqual((frames[0].width, frames[0].height), (64, 48))
        original = evidence.read_bytes()
        with self.assertRaises(FileExistsError):
            save_evidence(self.video, evidence, interval=[0, 1], source_bounds=[0, 8])
        self.assertEqual(evidence.read_bytes(), original)

    def test_safe_roots_symlinks_and_existing_output(self):
        with self.assertRaises(ValueError):
            create_output(self.root / "outside", [self.root / "outputs"])
        with self.assertRaises(ValueError):
            create_output(Path("relative"), [self.root])
        (self.root / "outputs").mkdir()
        (self.root / "outputs/link").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            create_output(self.root / "outputs/link/escape", [self.root / "outputs"])
        create_output(self.output, [self.root / "outputs"])
        with self.assertRaises(FileExistsError):
            create_output(self.output, [self.root / "outputs"])

    def test_frozen_settings_reject_tuning_before_output_creation(self):
        self.settings["sampling_fps"] = 3
        with self.assertRaises(ValueError):
            self.run_pipeline(lambda *args: result(["contact"]))
        self.assertFalse(self.output.exists())

    def test_cli_enqueues_only_registered_canonical_queue(self):
        import sys
        from mvp.cli import main
        runtime = self.root / "canonical"
        registry = SimpleNamespace(RUNTIME=runtime, SETTINGS={"seed": 0},
                                   PHASES=('dev', 'full', 'prompt-regression', 'independent-original', 'independent-revised'),
                                   validate_run=MagicMock(),
                                   load_configs=lambda: ({}, {}, {"full_timeout_seconds": 1800}),
                                   input_contract=lambda phase: {"hash": phase},
                                   validate=MagicMock())
        queue = MagicMock()
        queue.enqueue.return_value = {"status": "queued"}
        with patch.dict(sys.modules, {"orchestration.mvp_command": registry}), (
                patch("orchestration.mvp_command", registry, create=True)), (
                patch("orchestration.queue.Queue", return_value=queue)), patch("builtins.print"):
            main(["--runtime", str(runtime), "enqueue", "--phase", "full", "--view", "full_frame",
                  "--job-key", "synthetic-cli", "--run-id", "test-run", "--task-id", "test-task",
                  "--dispatch-id", "test-dispatch", "--owner", "test-owner"])
        kwargs = queue.enqueue.call_args.kwargs
        self.assertEqual(kwargs["command"], "mvp-0001")
        self.assertEqual(kwargs["timeout"], 1800)
        self.assertEqual(kwargs["config"], {"phase": "full", "view": "full_frame", "settings": {"seed": 0}})
        queue.run_once.assert_not_called()
        with patch.dict(sys.modules, {"orchestration.mvp_command": registry}), (
                patch("orchestration.mvp_command", registry, create=True)), (
                patch("orchestration.queue.Queue", return_value=queue)), patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                main(["--runtime", str(self.root / "different"), "run-once"])
        queue.run_once.assert_not_called()


@unittest.skipUnless(importlib.util.find_spec("mvp.method"), "method worker must be integrated")
class MethodPipelineIntegrationTests(PipelineFixture):
    """Reuse and official prepare over actual pipeline-written inputs, CPU only."""

    def test_actual_pipeline_results_reuse_without_nested_analysis_key(self):
        from mvp.compare import ExactReuseAnalyzer, FingerprintedAnalyzer, read_baseline_results
        self.camera["roi"] = [0, 0, 1, 1]
        semantic = lambda rgb, source, window_id, *rest: window_id + ":" + source["rgb_sha256"]
        class TestAnalyzer:
            def analyze(inner, *args):
                return result(["passage_or_waiting"])
        with patch("mvp.compare.semantic_digest", side_effect=semantic):
            baseline = self.run_pipeline(FingerprintedAnalyzer(TestAnalyzer(), "model", "settings"))
            self.assertEqual(baseline["status"], "succeeded")
            records = read_baseline_results(self.output)
            self.assertIn("raw_response", records["w000001"])
            self.assertNotIn("analysis", records["w000001"])
            self.output = self.root / "outputs/reuse"
            class Delegate:
                calls = 0
                def analyze(inner, *args):
                    inner.calls += 1
                    raise AssertionError("reuse must not generate")
            delegate = Delegate()
            with patch("mvp.compare.successful_baseline", return_value={"status": "succeeded"}):
                reuse = ExactReuseAnalyzer(delegate, records, "synthetic-successful-attempt", "model", "settings")
            reused = self.run_pipeline(reuse)
            self.assertEqual(reused["status"], "succeeded", reused)
            self.assertEqual(delegate.calls, 0)
            self.assertEqual(reused["newly_generated_tokens"], 0)
            self.assertIsNone(reused["measured_stage_seconds"]["generation_seconds"])
            self.assertIsNone(reused["measured_stage_seconds"]["prepare_seconds"])
            for path in (self.output / "windows").glob("*/result.json"):
                value = json.loads(path.read_text())
                if value.get("skipped") != "insufficient_data":
                    self.assertTrue(value["reused"])
                    self.assertEqual(value["reuse_provenance"]["baseline_attempt"], "synthetic-successful-attempt")

    def test_pipeline_to_official_qwen_preparation_fractional_vfr_odd_and_single_eof(self):
        import torch
        from transformers import AutoProcessor
        from mvp.method import QwenAnalyzer
        from orchestration.mvp_command import MODEL_DIR
        processor = AutoProcessor.from_pretrained(MODEL_DIR, local_files_only=True)
        prepared = object.__new__(QwenAnalyzer)
        prepared.processor = processor
        self.camera["roi"] = [0, 0, 1, 1]
        cases = {"fractional": write_video(self.root / "frac.mp4", count=180, fps=Fraction(30000, 1001)),
                 "gap": write_video(self.root / "gap.mp4", [0, .1, .6, 1.6, 2.8, 3.2, 4.9, 5.4, 6.3]),
                 "odd": write_video(self.root / "odd.mp4", count=13),
                 "single": write_video(self.root / "single-eof.mp4", count=1)}
        infos = {}
        for case, video in cases.items():
            self.output = self.root / "outputs" / case
            infos[case] = []
            def analyze(rgb, source, window_id, roi):
                _, info, frames = prepared.prepare(rgb, source, window_id, roi)
                self.assertEqual(info["native_pts"], source["native_pts"])
                self.assertEqual(info["relative_indices"], source["relative_indices"])
                self.assertEqual(len(frames), len(rgb))
                self.assertEqual(info["source_pts"], source["pts_seconds"])
                self.assertLessEqual(info["last_observed_pts"], source["last_decoded_pts"])
                self.assertEqual(info["temporal_padding_frames"], len(rgb) % 2)
                self.assertFalse(info["temporal_padding_is_observation"])
                for coordinate, pts in zip(info["processor_timestamp_coordinates"], source["pts_seconds"]):
                    self.assertAlmostEqual(coordinate / source["fps"], pts - source["window_start"])
                infos[case].append(info)
                # This is synthetic test output, not a model prediction.
                return {**result(["passage_or_waiting"]), "input_metadata": info}
            summary = self.run_pipeline(analyze, video)
            self.assertTrue(summary["functional_success"], summary)
            self.assertTrue(summary["eof_reached"])
        self.assertEqual(len(infos["single"]), 0)
        self.assertEqual(infos["odd"][0]["temporal_padding_frames"], 1)
        self.assertAlmostEqual(infos["fractional"][0]["source_fps"], 30000/1001, places=5)
        gap = infos["gap"][0]
        self.assertNotAlmostEqual(gap["processor_timestamp_coordinates"][-1], gap["relative_indices"][-1])
        self.assertFalse(torch.cuda.is_initialized())


if __name__ == "__main__":
    unittest.main()
