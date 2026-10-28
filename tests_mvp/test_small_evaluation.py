"""Portable CPU fixtures: no local media, inference, or actual cached answers."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import evaluate_mvp_small as ev
from orchestration.complete import metrics as validate_delivery_metrics


def answer(actions=None, evidence="People stand near a gate.", completion="not_confirmed", fenced=False):
    parsed = {"observed_actions": actions or ["passage_or_waiting"], "visible_evidence": evidence,
              "crossing_completion": completion, "uncertainties": ""}
    raw = json.dumps(parsed)
    if fenced:
        raw = "```json\n" + raw + "\n```"
    return {"raw_response": raw, "parsed": parsed, "parse": ev.parse_pair(raw), "reused": False,
            "semantic_input_sha256": "a" * 64, "newly_generated_tokens": 20,
            "timing": {"generation_seconds": 1.0}}


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True) + "\n")


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        manifest_raw = (ev.ROOT / "configs/mvp_small_eval_manifest.json").read_bytes()
        p = self.root / "configs/mvp_small_eval_manifest.json"
        p.parent.mkdir()
        p.write_bytes(manifest_raw)
        self.manifest = json.loads(manifest_raw)
        report = self.root / "docs/experiments/EXP-0013-mvp-comparison.md"
        report.parent.mkdir(parents=True)
        report.write_text("EXP-0013 " + " ".join(a[:8] for a in ev.ATTEMPTS.values()))
        for method, attempt in ev.ATTEMPTS.items():
            folder = self.root / "outputs/mvp0001/EXP-0012" / attempt
            meta = {"attempt_id": attempt, "input_hash": ev.INPUT_HASH, "code_sha": ev.CODE_SHA,
                    "config_hash": ev.CONFIG_HASHES[method],
                    "config": {"phase": "full", "view": ev.VIEWS[method], "settings": ev.GENERATION}}
            write(folder / "loading.json", meta)
            for sid, source in self.manifest["sources"].items():
                roi = [0, 0, 1, 1] if method == "B" else ev.ROIS[sid]
                source_meta = {"source": {"sha256": source["source_sha256"], "path": "/private/source.mp4"},
                               "camera": {"source_id": sid, "camera_id": source["camera_group"], "roi": roi},
                               "settings": {"generation": ev.GENERATION},
                               "run_context": {"attempt_id": attempt, "source_id": sid, "view": ev.VIEWS[method],
                                               "input_hash": ev.INPUT_HASH, "code_sha": ev.CODE_SHA,
                                               "config_hash": ev.CONFIG_HASHES[method]}}
                write(folder / sid / "run.json", source_meta)
                rows = []
                for case in self.manifest["cases"]:
                    if case["source_id"] != sid:
                        continue
                    expected = case["paired_methods"][method]
                    pts = expected["actual_sampled_pts_seconds"]
                    inp = {"window_start": case["start_pts_seconds"], "window_end": case["end_pts_seconds"],
                           "pts_seconds": pts, "native_pts": [int(p * 2) for p in pts],
                           "time_base": ["1/2"] * len(pts), "rgb_sha256": expected["rgb_sha256"],
                           "last_input_pts": expected["last_input_pts"], "last_decoded_pts": expected["last_arrived_pts"]}
                    result = answer(fenced=sid == "E01_013")
                    result["input_metadata"] = {"source_pts": pts, "native_pts": inp["native_pts"],
                                                "time_base": inp["time_base"], "observed_frames": len(pts),
                                                "window_start": inp["window_start"], "window_end": inp["window_end"], "roi": roi}
                    if method == "C" and sid == "E01_013":
                        baseline = self.path("B", case["case_id"], "result")
                        b = json.loads(baseline.read_text())
                        result = copy.deepcopy(b)
                        result.update(reused=True, newly_generated_tokens=0, timing={"generation_seconds": None})
                        result["reuse_provenance"] = {"baseline_attempt": ev.ATTEMPTS["B"],
                            "baseline_window_id": case["window_id"], "baseline_result_sha256": ev.sha(baseline.read_bytes()),
                            "baseline_raw_response_sha256": ev.sha(b["raw_response"].encode()),
                            "semantic_input_sha256": b["semantic_input_sha256"]}
                    window = {"window_id": case["window_id"], "source": inp,
                              "result": f"windows/{case['window_id']}/result.json",
                              "estimated_interval": expected["scheduled_interval_seconds"],
                              "states": [list(x) for x in ev.classify(result)]}
                    for name, obj in (("input", inp), ("window", window), ("result", result)):
                        write(self.path(method, case["case_id"], name), obj)
                    rows.append(json.dumps(window, sort_keys=True))
                (folder / sid / "windows.jsonl").write_text("\n".join(rows) + "\n")
                # A long merged event must never rescue a selected absent result.
                write(folder / sid / "events.jsonl", {"state": "candidate", "estimated_interval": [0, 999]})

    def path(self, method, cid, name):
        case = next(c for c in self.manifest["cases"] if c["case_id"] == cid)
        return (self.root / "outputs/mvp0001/EXP-0012" / ev.ATTEMPTS[method] /
                case["source_id"] / "windows" / case["window_id"] / (name + ".json"))

    def run_eval(self):
        return ev.evaluate(self.root)

    def row(self, records, method="B", cid="d030_90"):
        return next(r for r in records if r["case_id"] == cid and r["method"] == method)

    def test_all_24_pair_records_and_pts_are_traced(self):
        metrics, rows, _ = self.run_eval()
        self.assertTrue(metrics["evaluation_extraction_complete"])
        self.assertEqual(metrics["traced_valid_records"], 24)
        self.assertTrue(all(r["B_C_actual_pts_equal"] and r["B_C_source_rgb_hash_equal"] for r in rows))
        self.assertTrue(all(len(r["provenance"]["result_file_sha256"]) == 64 for r in rows))

    def test_source_window_pts_and_hash_mismatches_are_unavailable(self):
        mutations = [("input", "rgb_sha256", "0" * 64, "decoded_rgb_hash_mismatch"),
                     ("input", "pts_seconds", [0], "pts_mismatch"),
                     ("window", "window_id", "w999999", "window_id_mismatch")]
        for name, key, value, issue in mutations:
            with self.subTest(issue=issue):
                p = self.path("B", "d030_90", name)
                old = p.read_bytes()
                d = json.loads(old); d[key] = value; write(p, d)
                _, rows, _ = self.run_eval()
                row = self.row(rows)
                self.assertIn(issue, row["pairing_issues"])
                self.assertEqual(row["counted_output_presence"], "unavailable")
                p.write_bytes(old)
        p = self.path("B", "d030_90", "input").parents[2] / "run.json"
        d = json.loads(p.read_text()); d["camera"]["source_id"] = "E01_031"; write(p, d)
        self.assertIn("source_id_mismatch", self.row(self.run_eval()[1])["pairing_issues"])

    def test_no_merged_event_rescue_or_unselected_output_reads(self):
        original = ev.CacheReader.read
        seen = []
        def guarded(reader, p):
            seen.append(Path(p))
            self.assertNotIn(Path(p).name, ("events.jsonl", "emissions.jsonl"))
            return original(reader, p)
        with patch.object(ev.CacheReader, "read", guarded):
            _, rows, _ = self.run_eval()
        self.assertEqual(self.row(rows)["counted_output_presence"], "candidate_absent")
        self.assertEqual(sum(p.name == "result.json" for p in seen), 24)
        selected = {self.path(m, c["case_id"], "result") for m in ("B", "C") for c in self.manifest["cases"]}
        self.assertEqual({p for p in seen if p.name == "result.json"}, selected)

    def test_unknown_and_partial_moment_are_not_negative(self):
        metrics, rows, _ = self.run_eval()
        self.assertEqual(metrics["confirmed_negative_cases"], 0)
        self.assertEqual(metrics["verified_negative_seconds"], 0)
        self.assertEqual(self.row(rows, cid="d030_84")["label_scope"], "unknown")
        self.assertEqual(metrics["unique_unknown_label_cases"], 11)
        self.assertTrue(all(v is None for v in metrics["performance_metrics"].values()))

    def test_partial_positive_unavailable_stays_in_denominator(self):
        self.path("B", "d030_90", "result").unlink()
        metrics, rows, _ = self.run_eval()
        table = next(t for t in metrics["output_presence_tables"] if t["method"] == "B" and t["group"] == "partial_positive_presence")
        self.assertEqual((table["denominator"], table["unavailable"]), (1, 1))
        self.assertEqual(metrics["unique_partial_positive_presence_cases"], 1)
        self.assertIn("missing_or_invalid_result", self.row(rows)["pairing_issues"])

    def test_fallback_is_verified_reuse_not_independent_roi_sample(self):
        _, rows, _ = self.run_eval()
        fallback = [r for r in rows if r["method"] == "C" and r["fallback_diagnostic"]]
        self.assertEqual(len(fallback), 4)
        self.assertTrue(all(r["reuse_verified"] for r in fallback))
        self.assertTrue(all(r["target_boundary_alignment"] == "not_roi_comparative" for r in fallback))
        p = self.path("C", "s013_mid", "result")
        d = json.loads(p.read_text()); d["reuse_provenance"]["baseline_result_sha256"] = "0" * 64; write(p, d)
        row = self.row(self.run_eval()[1], "C", "s013_mid")
        self.assertFalse(row["reuse_verified"])
        self.assertEqual(row["counted_output_presence"], "unavailable")

    def test_duplicate_log_is_explicit_invalid_pair(self):
        p = self.path("B", "d030_90", "input").parents[2] / "windows.jsonl"
        lines = p.read_text().splitlines()
        target = next(line for line in lines if json.loads(line)["window_id"] == "w000036")
        p.write_text("\n".join(lines + [target]) + "\n")
        row = self.row(self.run_eval()[1])
        self.assertIn("missing_or_duplicate_log_record", row["pairing_issues"])
        self.assertFalse(row["paired_trace_valid"])

    def test_031_noncompletion_does_not_transfer_to_030(self):
        _, rows, _ = self.run_eval()
        row = self.row(rows, cid="d030_eof")
        self.assertEqual(row["reference_label"], "uncertain")
        self.assertEqual(row["completion_reference_provenance"], "no_030_completion_label_from_031")
        case = next(c for c in self.manifest["cases"] if c["case_id"] == "d030_eof")
        altered = {**case, "reference_label": "no_climbing_observed", "label_status": "human_confirmed_for_scope"}
        self.assertEqual(ev.label_scope(altered), "unknown")

    def test_form_behavior_and_completion_are_separate(self):
        result = ev.inspect_result(answer(["stepping_over_boundary"], "People stand and are not moving.", "observed", True))
        self.assertFalse(result["strict_form_compliant"])
        self.assertTrue(result["postprocessed_schema_valid"])
        self.assertEqual(result["output_presence"], "candidate")
        self.assertEqual(result["action_evidence_text_consistency"], "explicit_motion_denial")
        self.assertEqual(result["completion_support"], "unverified")
        self.assertEqual(result["explanation_factuality"], "unresolved_no_full_window_visual_review")
        result = ev.inspect_result(answer(completion="observed"))
        self.assertEqual(result["output_presence"], "candidate_absent")
        self.assertTrue(result["completion_without_climbing_action"])

    def test_candidate_and_indeterminate_preserves_candidate(self):
        result = ev.inspect_result(answer(["indeterminate", "stepping_over_boundary", "stepping_over_boundary"]))
        self.assertEqual(result["output_presence"], "candidate")
        self.assertTrue(result["candidate_with_indeterminate_action"])
        self.assertEqual(len(result["runtime_states"]), 2)

    def test_unknown_parse_failed_insufficient_and_contact_are_distinct(self):
        for obj in (answer(["indeterminate"]), {"raw_response": "bad", "parsed": None},
                    {"skipped": "insufficient_data"}, {"execution_error": {"type": "failure"}}):
            self.assertEqual(ev.inspect_result(obj)["output_presence"], "unavailable")
        contact = ev.inspect_result(answer(["contact"]))
        self.assertEqual(contact["runtime_states"], [["contact_review", "contact"]])
        self.assertEqual(contact["output_presence"], "candidate_absent")

    def test_stored_parser_cannot_override_raw_answer(self):
        p = self.path("B", "d030_90", "result")
        d = json.loads(p.read_text()); d["parsed"]["observed_actions"] = ["stepping_over_boundary"]; write(p, d)
        row = self.row(self.run_eval()[1])
        self.assertIn("stored_parser_mismatch", row["pairing_issues"])
        self.assertEqual(row["observed_output"]["output_presence"], "candidate_absent")

    def test_invalid_json_result_is_unavailable(self):
        self.path("B", "d030_90", "result").write_text("{")
        metrics, rows, _ = self.run_eval()
        self.assertFalse(metrics["evaluation_extraction_complete"])
        self.assertEqual(self.row(rows)["counted_output_presence"], "unavailable")

    def test_manifest_edit_is_rejected_before_results_read(self):
        p = self.root / "configs/mvp_small_eval_manifest.json"
        p.write_bytes(p.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "frozen manifest"):
            self.run_eval()

    def test_read_only_deterministic_and_sanitized(self):
        files = list((self.root / "outputs").rglob("*"))
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files if p.is_file()}
        first = self.run_eval()[:2]
        second = self.run_eval()[:2]
        self.assertEqual(first, second)
        for p, (raw, mtime) in before.items():
            self.assertEqual((p.read_bytes(), p.stat().st_mtime_ns), (raw, mtime))
        public = json.dumps(first)
        for private in ("/private/", str(self.root), "People stand near a gate.", "raw_response\":"):
            self.assertNotIn(private, public)
        self.assertTrue(all(t["candidate"] + t["candidate_absent"] + t["unavailable"] == t["denominator"]
                            for t in first[0]["output_presence_tables"]))

    def test_metrics_document_meets_viewer_contract_with_diagnostic_counts(self):
        metrics, rows, _ = self.run_eval()
        self.assertEqual(metrics["experiment_id"], "EXP-0014")
        validate_delivery_metrics(metrics, "EXP-0014")
        encoded_rows = (json.dumps(rows, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
        expected_sha = hashlib.sha256(encoded_rows).hexdigest()
        self.assertEqual(len(metrics["metrics"]), 6)
        self.assertTrue(all(m["source_sha256"] == expected_sha for m in metrics["metrics"]))
        self.assertEqual([m["value"] for m in metrics["metrics"][:3]], [0, 8, 0])
        self.assertTrue(all(m["sample_n"] == 12 for m in metrics["metrics"]))
        self.assertIsNone(metrics["performance_metrics"]["accuracy"])

    def test_consumed_source_change_is_detected(self):
        p = self.path("B", "d030_90", "result")
        reader = ev.CacheReader(); reader.read(p)
        p.write_text("{}")
        with self.assertRaisesRegex(ValueError, "source changed"):
            reader.verify_unchanged()


if __name__ == "__main__":
    unittest.main()
