#!/usr/bin/env python3
"""EXP-0014: deterministic, read-only EXP-0013 cache evaluation (stdlib only).

Only the frozen selection is supported. No decoder, model, queue, event merger,
network client, official annotation reader or media reader is used here.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mvp.events import classify
from vlm_batch.common import parse_pair

MANIFEST_SHA256 = "ec293844173fe8797b2e518ba1a01b98be2720f766fd4c27bf3d5f278a7186af"
ATTEMPTS = {"B": "49cad0749df04995bb55727d57946fec",
            "C": "a546b67626e54ef79cdf9bee1c70b3bf"}
INPUT_HASH = "c3bd766c6b4ff7707b9ac6eb75a0d76300df7984ff9b0ff86475ae9c3f98e8fe"
CODE_SHA = "65caebd473c43f4f554b0eb67d598b1f18a0e44f"
VIEWS = {"B": "full_frame", "C": "fixed_roi"}
ROIS = {"E01_007": [0.6, 0, 0.9, 0.6],
        "E01_030": [0.28, 0.2, 0.75, 0.8], "E01_013": [0, 0, 1, 1]}
CONFIG_HASHES = {"B": "0afc03175313624c63afe8b64057c9721086706d7f308f105746ce1e766c3a1c",
                 "C": "95f37a1350e974c89badf2954d7d78c57802132d81d2193e5a16f7f96d174236"}
GENERATION = {"attention": "sdpa", "batch_size": 1, "device": "cuda:0", "do_sample": False,
              "dtype": "bfloat16", "max_new_tokens": 384, "repetition_penalty": 1.0, "seed": 0}
POSITIVE_ACTIONS = {"stepping_over_boundary", "climbing_attempt_or_in_progress"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class CacheReader:
    """Track bytes actually consumed; verify their immutability before writing."""
    def __init__(self):
        self.consumed = {}

    def read(self, path):
        path = Path(path)
        raw = path.read_bytes()
        digest = sha(raw)
        if path in self.consumed and self.consumed[path] != digest:
            raise ValueError("source changed during evaluation")
        self.consumed[path] = digest
        return raw

    def json(self, path):
        raw = self.read(path)
        return json.loads(raw), sha(raw)

    def verify_unchanged(self):
        if any(sha(p.read_bytes()) != digest for p, digest in self.consumed.items()):
            raise ValueError("source changed during evaluation")


def load_manifest(path, reader):
    raw = reader.read(path)
    if sha(raw) != MANIFEST_SHA256:
        raise ValueError("frozen manifest SHA256 mismatch")
    manifest = json.loads(raw)
    cases = manifest["cases"]
    ids = [c["case_id"] for c in cases]
    pairs = [(c["source_id"], c["window_id"]) for c in cases]
    if len(cases) != 12 or len(set(ids)) != 12 or len(set(pairs)) != 12:
        raise ValueError("duplicate or changed selection")
    for case in cases:
        if case["source_id"] not in manifest["sources"]:
            raise ValueError("unknown source")
        if case["reference_label"] == "climbing_present" and case["case_id"] != "d030_90":
            raise ValueError("positive provenance differs from frozen policy")
        if case["case_id"] == "d030_eof" and case["reference_label"] != "uncertain":
            raise ValueError("031 noncompletion cannot label 030 EOF")
    return manifest


def label_scope(case):
    """Positive moment presence is useful; a negative moment labels no window."""
    if (case["case_id"] == "d030_90" and case["source_id"] == "E01_030"
            and case["reference_label"] == "climbing_present"
            and case["label_status"] == "human_observation_partial"):
        return "partial_positive_presence"
    return "unknown"


def inspect_result(result):
    """Output state, format, text consistency and completion are distinct axes.

    Lexical flags are deliberately narrow text diagnostics, never visual labels.
    Free-form model text and parser error strings never leave this function.
    """
    raw = result.get("raw_response")
    parsed_pair = parse_pair(raw) if isinstance(raw, str) else None
    parsed = parsed_pair["postprocessed_parsed"] if parsed_pair else None
    states = classify({"parsed": parsed}) if parsed else [("parse_failed", None)]
    if result.get("skipped") == "insufficient_data":
        states = [("insufficient_data", None)]
    if result.get("execution_error"):
        states = [("execution_error", None)]
    names = [s for s, _ in states]
    candidate = "candidate" in names
    unavailable = any(s in names for s in ("parse_failed", "insufficient_data", "execution_error"))
    if candidate:
        output = "candidate"
    elif unavailable or "indeterminate" in names:
        output = "unavailable"
    else:
        output = "candidate_absent"
    actions = parsed["observed_actions"] if parsed else []
    text = parsed["visible_evidence"].lower() if parsed else ""
    motion = bool(re.search(r"\b(climb\w*|stepping over|step over|crossing over)\b", text))
    denial = bool(re.search(r"\b(not moving|standing still|no movement)\b", text))
    consistency = ("explicit_motion_denial" if candidate and denial else
                   "no_climbing_motion_described" if candidate and not motion else
                   "climbing_motion_described_claim_only" if candidate else "not_applicable")
    completion = parsed["crossing_completion"] if parsed else "unavailable"
    return {
        "output_presence": output,
        "runtime_states": [[s, a] for s, a in states],
        "actions": list(dict.fromkeys(actions)),
        "raw_response_present": isinstance(raw, str) and bool(raw.strip()),
        "raw_response_sha256": sha(raw.encode()) if isinstance(raw, str) else None,
        "strict_form_compliant": bool(parsed_pair and parsed_pair["strict_parsed"]),
        "postprocessed_schema_valid": parsed is not None,
        "postprocessing": parsed_pair["postprocessing"] if parsed_pair else "unavailable",
        "stored_parser_matches_reparse": bool(parsed_pair and result.get("parse") == parsed_pair
                                               and result.get("parsed") == parsed),
        "action_evidence_text_consistency": consistency,
        "explanation_factuality": "unresolved_no_full_window_visual_review",
        "evidence_mentions_climbing_motion": motion,
        "evidence_explicit_motion_denial": denial,
        "candidate_with_indeterminate_action": candidate and "indeterminate" in actions,
        "candidate_with_uncertainty_text": candidate and bool(parsed and parsed["uncertainties"].strip()),
        "completion_claim": completion,
        "completion_support": "unverified" if completion == "observed" else "not_asserted",
        "completion_without_climbing_action": completion == "observed" and not POSITIVE_ACTIONS.intersection(actions),
        "text_completion_language_present": bool(re.search(r"\b(completed|successfully crossed|other side)\b", text)),
    }


def selected_log_records(path, selected_ids, reader):
    raw = reader.read(path)
    rows = {key: [] for key in selected_ids}
    for line in raw.splitlines():
        # JSONL has top-level and nested IDs. Select by the top-level record ID;
        # do not interpret unselected model claims, even for event rescue.
        if not any(re.search(rb'"window_id"\s*:\s*"' + key.encode() + rb'"', line)
                   for key in selected_ids):
            continue
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(row, dict) and row.get("window_id") in rows:
            rows[row["window_id"]].append((row, sha(line)))
    return rows, sha(raw)


def check_pair(case, method, metadata, source_meta, source, window, log_rows, result, manifest):
    """Return stable issue codes; invalid pairing never silently supplies a hit."""
    issues = []
    def require(condition, code):
        if not condition:
            issues.append(code)
    context = source_meta.get("run_context", {})
    camera = source_meta.get("camera", {})
    expected = case["paired_methods"][method]
    require(metadata.get("attempt_id") == ATTEMPTS[method], "attempt_mismatch")
    require(metadata.get("input_hash") == INPUT_HASH, "model_input_provenance_mismatch")
    require(metadata.get("code_sha") == CODE_SHA, "execution_code_mismatch")
    require(metadata.get("config", {}).get("view") == VIEWS[method], "method_view_mismatch")
    require(metadata.get("config", {}).get("phase") == "full", "phase_mismatch")
    require(metadata.get("config", {}).get("settings") == GENERATION, "generation_settings_mismatch")
    require(metadata.get("config_hash") == CONFIG_HASHES[method], "config_hash_mismatch")
    require(source_meta.get("settings", {}).get("generation") == GENERATION, "source_generation_mismatch")
    require(context.get("attempt_id") == ATTEMPTS[method], "source_attempt_mismatch")
    require(context.get("source_id") == case["source_id"] == camera.get("source_id"), "source_id_mismatch")
    require(camera.get("camera_id") == case["camera_group"], "camera_mismatch")
    require(source_meta.get("source", {}).get("sha256") == manifest["sources"][case["source_id"]]["source_sha256"], "source_hash_mismatch")
    require(context.get("view") == VIEWS[method], "source_view_mismatch")
    require(context.get("input_hash") == metadata.get("input_hash"), "source_input_binding_mismatch")
    require(context.get("code_sha") == metadata.get("code_sha"), "source_code_binding_mismatch")
    require(context.get("config_hash") == metadata.get("config_hash"), "source_config_binding_mismatch")
    roi = [0, 0, 1, 1] if method == "B" else ROIS[case["source_id"]]
    require(camera.get("roi") == roi, "source_roi_mismatch")
    require(window.get("window_id") == case["window_id"] == expected["window_id"], "window_id_mismatch")
    interval = [case["start_pts_seconds"], case["end_pts_seconds"]]
    require(window.get("estimated_interval") == interval == expected["scheduled_interval_seconds"], "interval_mismatch")
    require(source.get("window_start") == interval[0] and source.get("window_end") == interval[1], "input_interval_mismatch")
    pts = source.get("pts_seconds", [])
    if not isinstance(pts, list):
        issues.append("invalid_pts_array")
        pts = []
    require(pts == expected["actual_sampled_pts_seconds"], "pts_mismatch")
    require(len(pts) == expected["actual_sample_count"], "sample_count_mismatch")
    require(source.get("last_input_pts") == expected["last_input_pts"], "last_input_mismatch")
    require(source.get("last_decoded_pts") == expected["last_arrived_pts"], "last_arrived_mismatch")
    require(source.get("rgb_sha256") == expected["rgb_sha256"], "decoded_rgb_hash_mismatch")
    require(window.get("source") == source, "window_input_binding_mismatch")
    require(window.get("result") == f"windows/{case['window_id']}/result.json", "result_pointer_mismatch")
    require(len(log_rows) == 1, "missing_or_duplicate_log_record")
    require(len(log_rows) == 1 and log_rows[0][0] == window, "log_window_binding_mismatch")
    try:
        native, bases = source["native_pts"], source["time_base"]
        require(len(native) == len(bases) == len(pts) and all(
            abs(float(Fraction(b) * p) - s) < 1e-6 for p, b, s in zip(native, bases, pts)), "native_pts_mismatch")
        require(all(interval[0] <= p < interval[1] for p in pts)
                and all(a < b for a, b in zip(pts, pts[1:])), "unordered_or_outside_pts")
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        issues.append("invalid_native_pts")
    if not result.get("skipped") and not result.get("execution_error"):
        info = result.get("input_metadata") or {}
        if not isinstance(info, dict):
            info = {}
        require(info.get("source_pts") == pts and info.get("native_pts") == source.get("native_pts")
                and info.get("time_base") == source.get("time_base"), "result_pts_binding_mismatch")
        require(info.get("observed_frames") == len(pts), "result_sample_count_mismatch")
        require(info.get("window_start") == interval[0] and info.get("window_end") == interval[1], "result_interval_mismatch")
        require(info.get("roi") == roi, "result_roi_mismatch")
    return issues


def evaluate(root=ROOT):
    root = Path(root)
    reader = CacheReader()
    manifest = load_manifest(root / "configs/mvp_small_eval_manifest.json", reader)
    report_bytes = reader.read(root / "docs/experiments/EXP-0013-mvp-comparison.md")
    for attempt in ATTEMPTS.values():
        if attempt[:8].encode() not in report_bytes:
            raise ValueError("EXP-0013 report does not identify expected attempts")
    records, internal = [], {}
    base = root / "outputs/mvp0001/EXP-0012"
    for method, attempt in ATTEMPTS.items():
        folder = base / attempt
        try:
            meta, meta_hash = reader.json(folder / "loading.json")
            if not isinstance(meta, dict):
                raise ValueError("metadata object required")
        except (OSError, ValueError):
            meta, meta_hash = {}, None
        for source_id in manifest["sources"]:
            source_dir = folder / source_id
            cases = [c for c in manifest["cases"] if c["source_id"] == source_id]
            try:
                source_meta, source_meta_hash = reader.json(source_dir / "run.json")
                if not isinstance(source_meta, dict):
                    raise ValueError("metadata object required")
            except (OSError, ValueError):
                source_meta, source_meta_hash = {}, None
            try:
                log, log_hash = selected_log_records(source_dir / "windows.jsonl", [c["window_id"] for c in cases], reader)
            except (OSError, ValueError):
                log, log_hash = {}, None
            for case in cases:
                key = (method, case["case_id"])
                window_dir = source_dir / "windows" / case["window_id"]
                data, hashes, errors = {}, {}, []
                for name in ("input", "window", "result"):
                    try:
                        data[name], hashes[name + "_file_sha256"] = reader.json(window_dir / (name + ".json"))
                        if not isinstance(data[name], dict):
                            raise ValueError("object required")
                    except (OSError, ValueError):
                        data[name] = {}
                        errors.append("missing_or_invalid_" + name)
                log_rows = log.get(case["window_id"], [])
                errors += check_pair(case, method, meta, source_meta, data["input"], data["window"],
                                     log_rows, data["result"], manifest)
                result = inspect_result(data["result"])
                if result["stored_parser_matches_reparse"] is False and result["raw_response_present"]:
                    errors.append("stored_parser_mismatch")
                if result["runtime_states"] != data["window"].get("states"):
                    errors.append("runtime_state_mismatch")
                record = {"case_id": case["case_id"], "source_id": source_id, "method": method,
                          "window_id": case["window_id"], "evaluation_role": case["evaluation_role"],
                          "scheduled_interval_seconds": [case["start_pts_seconds"], case["end_pts_seconds"]],
                          "reference_label": case["reference_label"], "label_status": case["label_status"],
                          "label_scope": label_scope(case), "paired_trace_valid": not errors,
                          "pairing_issues": errors, "observed_output": result,
                          "counted_output_presence": result["output_presence"] if not errors else "unavailable",
                          "actual_sampled_pts_seconds": data["input"].get("pts_seconds"),
                          "actual_native_pts": data["input"].get("native_pts"),
                          "actual_time_base": data["input"].get("time_base"),
                          "last_input_pts": data["input"].get("last_input_pts"),
                          "last_arrived_pts": data["input"].get("last_decoded_pts"),
                          "decoded_source_rgb_sha256": data["input"].get("rgb_sha256"),
                          "source_sha256": source_meta.get("source", {}).get("sha256"),
                          "reused": data["result"].get("reused") is True,
                          "fallback_diagnostic": source_id == "E01_013",
                          "target_boundary_alignment": "not_roi_comparative" if source_id == "E01_013" else "unverified",
                          "presence_reference_consistency": "partial_positive_only" if label_scope(case) == "partial_positive_presence" and result["output_presence"] == "candidate" else "unresolved",
                          "completion_reference_provenance": "no_030_completion_label_from_031" if case["case_id"] == "d030_eof" else "no_completion_ground_truth",
                          "provenance": {**hashes, "loading_metadata_sha256": meta_hash,
                                         "source_run_metadata_sha256": source_meta_hash,
                                         "windows_log_file_sha256": log_hash,
                                         "selected_log_line_sha256": log_rows[0][1] if len(log_rows) == 1 else None,
                                         "semantic_input_sha256": data["result"].get("semantic_input_sha256"),
                                         "model_input_binding_sha256": meta.get("input_hash")}}
                records.append(record)
                internal[key] = data["result"]
    # Validate fallback against the selected B bytes, never load extra B windows.
    by_key = {(r["method"], r["case_id"]): r for r in records}
    for record in records:
        if record["method"] != "C" or not record["fallback_diagnostic"]:
            record["reuse_verified"] = None
            continue
        cid = record["case_id"]
        baseline = by_key[("B", cid)]
        b, c = internal[("B", cid)], internal[("C", cid)]
        provenance = c.get("reuse_provenance", {})
        record["reuse_verified"] = bool(record["reused"] and baseline["paired_trace_valid"]
            and provenance.get("baseline_attempt") == ATTEMPTS["B"]
            and provenance.get("baseline_window_id") == record["window_id"]
            and provenance.get("baseline_result_sha256") == baseline["provenance"].get("result_file_sha256")
            and provenance.get("baseline_raw_response_sha256") == baseline["observed_output"]["raw_response_sha256"]
            and provenance.get("semantic_input_sha256") == c.get("semantic_input_sha256") == b.get("semantic_input_sha256")
            and b.get("parsed") == c.get("parsed") and b.get("raw_response") == c.get("raw_response")
            and b.get("input_metadata") == c.get("input_metadata")
            and c.get("newly_generated_tokens") == 0 and c.get("timing", {}).get("generation_seconds") is None)
        record["provenance"]["reuse_baseline_result_sha256"] = provenance.get("baseline_result_sha256")
        if not record["reuse_verified"]:
            record["pairing_issues"].append("reuse_binding_mismatch")
            record["paired_trace_valid"] = False
            record["counted_output_presence"] = "unavailable"
    # Actual equality, rather than merely copying manifest assertions.
    for case in manifest["cases"]:
        b, c = [by_key[(m, case["case_id"])] for m in ("B", "C")]
        for record in (b, c):
            record["B_C_actual_pts_equal"] = b["actual_sampled_pts_seconds"] == c["actual_sampled_pts_seconds"] and b["actual_sampled_pts_seconds"] is not None
            record["B_C_source_rgb_hash_equal"] = b["decoded_source_rgb_sha256"] == c["decoded_source_rgb_sha256"] and b["decoded_source_rgb_sha256"] is not None
    reader.verify_unchanged()
    metrics = aggregate(records)
    metrics.update(schema_version=1, evaluation_id="EXP-0014", based_on_exp="EXP-0013",
                   frozen_manifest_sha256=MANIFEST_SHA256, selection_timing=manifest["selection_timing"],
                   source_report_sha256=sha(report_bytes),
                   implementation_sha256=sha(Path(__file__).read_bytes()),
                   source_files_verified_unchanged=len(reader.consumed),
                   execution_scope="CPU cached text/metadata only; no media decoding or inference",
                   model_pairing_scope="Same recorded execution input hash and generation metadata; model weights not reopened or rehashed",
                   labels_revision="frozen_manifest_with_EXP-0013_observation_errata",
                   item_results_sha256=sha(canonical(records)))
    metrics.update(experiment_id="EXP-0014")
    metrics["metrics"] = delivery_metric_rows(metrics, sha(json_bytes(records)))
    return metrics, records, reader


def aggregate(records):
    tables = []
    for method in ("B", "C"):
        for group in ("all_selected", "primary", "diagnostic", "fallback_diagnostic", "partial_positive_presence"):
            selected = [r for r in records if r["method"] == method and (
                group == "all_selected" or r["evaluation_role"] == group or
                group == "partial_positive_presence" and r["label_scope"] == group)]
            counts = Counter(r["counted_output_presence"] for r in selected)
            tables.append({"method": method, "group": group, "denominator": len(selected),
                           **{k: counts[k] for k in ("candidate", "candidate_absent", "unavailable")},
                           "unknown_label_count": sum(r["label_scope"] == "unknown" for r in selected),
                           "reused_count": sum(r["reused"] for r in selected)})
    return {"evaluation_extraction_complete": len(records) == 24 and all(r["paired_trace_valid"] for r in records),
            "behavioral_validation": "insufficient_evidence_human_review_pending",
            "selected_case_count": len({r["case_id"] for r in records}), "selected_pair_records": len(records),
            "traced_valid_records": sum(r["paired_trace_valid"] for r in records),
            "invalid_or_missing_records": sum(not r["paired_trace_valid"] for r in records),
            "primary_fully_confirmed_positive_denominator": 0,
            "primary_fully_confirmed_negative_denominator": 0,
            "unique_partial_positive_presence_cases": len({r["case_id"] for r in records if r["label_scope"] == "partial_positive_presence"}),
            "unique_unknown_label_cases": len({r["case_id"] for r in records if r["label_scope"] == "unknown"}),
            "confirmed_negative_cases": 0, "verified_negative_seconds": 0,
            "output_presence_tables": tables,
            "diagnostics_by_method": {m: {
                "strict_form_compliant": sum(r["observed_output"]["strict_form_compliant"] for r in records if r["method"] == m),
                "postprocessed_schema_valid": sum(r["observed_output"]["postprocessed_schema_valid"] for r in records if r["method"] == m),
                "completion_observed_claims": sum(r["observed_output"]["completion_claim"] == "observed" for r in records if r["method"] == m),
                "completion_without_climbing_action": sum(r["observed_output"]["completion_without_climbing_action"] for r in records if r["method"] == m),
                "text_consistency": dict(sorted(Counter(r["observed_output"]["action_evidence_text_consistency"] for r in records if r["method"] == m).items())),
                "denominator": sum(r["method"] == m for r in records)} for m in ("B", "C")},
            "performance_metrics": {k: None for k in ("accuracy", "precision", "recall", "f1", "fpr", "hourly_false_alarms")},
            "performance_null_reason": "No fully confirmed primary labels or negative windows; partial positive is diagnostic and target alignment/explanation factuality remain unreviewed",
            "counting_formula": "For each method/group, denominator = selected scheduled windows; candidate + candidate_absent + unavailable = denominator. Invalid pairing, missing, parse failure, insufficient input and indeterminate without candidate are unavailable. Candidate with indeterminate remains candidate. No merged event is read.",
            "exclusions": {"unknown_labels": "excluded from behavioral scores, retained in output counts",
                           "partial_positive": "d030_90 presence only, diagnostic; no person count, onset or completion score",
                           "fallback": "four C4 cases excluded from ROI comparative performance; four C records reuse B",
                           "target_boundary": "alignment unverified; off-ROI success/negative never inferred",
                           "diagnostic_anchors": "kept outside primary performance denominators",
                           "031_observation": "not transferred to 030 EOF",
                           "official_annotation": "manifest reference only; no official label file read",
                           "cost": "not measured by this evaluator; reused generation is not a speed improvement"}}


def delivery_metric_rows(summary, item_file_sha256):
    """Contract rows for the existing results viewer; counts are diagnostics, not scores."""
    rows = []
    by_method = summary["diagnostics_by_method"]
    all_counts = {x["method"]: x for x in summary["output_presence_tables"]
                  if x["group"] == "all_selected"}
    unknown = summary["unique_unknown_label_cases"]
    partial = summary["unique_partial_positive_presence_cases"]
    for method in ("B", "C"):
        details = by_method[method]
        candidates = all_counts[method]["candidate"]
        values = [
            (f"{method}: candidate output count (not a correctness score)", candidates,
             "candidate windows"),
            (f"{method}: original-form schema compliant", details["strict_form_compliant"],
             "form-only diagnostic"),
            (f"{method}: observed completion claims without climbing action", details["completion_without_climbing_action"],
             "text-only diagnostic"),
        ]
        for label, value, scope_suffix in values:
            rows.append({"label": label, "value": value, "unit": "window",
                         "sample_n": 12,
                         "scope": f"EXP-0014 fixed 12-window development sample; {unknown} unknown and {partial} partial-positive label(s); {scope_suffix}; not behavioral accuracy",
                         "source": "records/EXP-0014/window_reviews.json",
                         "source_sha256": item_file_sha256,
                         "verification": "source_json_sha256_checked"})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository with the fixed local cache")
    args = parser.parse_args()
    metrics, records, reader = evaluate(args.root)
    destination = args.root.resolve() / "records/EXP-0014"
    # Never follow output symlinks into a source directory.
    if destination.resolve() != destination or any((destination / n).is_symlink() for n in ("metrics.json", "window_reviews.json")):
        raise ValueError("evaluation output must not be a symlink")
    destination.mkdir(parents=True, exist_ok=True)
    reader.verify_unchanged()
    for name, value in (("metrics.json", metrics), ("window_reviews.json", records)):
        (destination / name).write_bytes(json_bytes(value))
    print(json.dumps({"evaluation": "EXP-0014", "records": len(records),
                      "valid": metrics["traced_valid_records"],
                      "behavioral_validation": metrics["behavioral_validation"]}, sort_keys=True))
    return 0 if metrics["evaluation_extraction_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
