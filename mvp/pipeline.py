"""Model-independent original-video pipeline. Production callers use the queue."""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import resource
import subprocess
import time

import numpy as np

from mvp.evidence import append_json, create_output, save_evidence, timestamp, write_json
from mvp.events import EventMerger, classify
from mvp.windows import iter_windows


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _provenance():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                            capture_output=True, text=True, check=False)
    return {"git_head": result.stdout.strip() if result.returncode == 0 else None,
            "source_sha256": {str(p.relative_to(root)): _hash(p)
                              for p in sorted((root / "mvp").glob("*.py"))}}


def _validate(camera, settings):
    expected = {"window_seconds": 5.0, "stride_seconds": 2.5, "sampling_fps": 2.0,
                "minimum_real_frames": 2, "merge_gap_seconds": 0.0,
                "evidence_pre_seconds": 2.0, "evidence_post_seconds": 2.0}
    for key, value in expected.items():
        if settings.get(key, value) != value:
            raise ValueError(f"MVP-0001 frozen setting differs: {key}")
    roi = camera.get("roi", [0.0, 0.0, 1.0, 1.0])
    if (not isinstance(roi, (list, tuple)) or len(roi) != 4
            or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in roi)
            or not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1)):
        raise ValueError("camera ROI must be normalized original-image xyxy")
    if not isinstance(camera.get("camera_id"), str) or not camera["camera_id"]:
        raise ValueError("camera_id is required")
    return list(roi)


def _diagnostic_objects(analyzer):
    """Known thin wrappers expose their delegate as .analyzer; avoid cycles."""
    seen = set()
    while id(analyzer) not in seen:
        seen.add(id(analyzer))
        yield analyzer
        delegate = getattr(analyzer, "__dict__", {}).get("analyzer")
        if delegate is None:
            break
        analyzer = delegate


def _clear_diagnostics(analyzer):
    for item in _diagnostic_objects(analyzer):
        for name, empty in (("last_generated_token_ids", []), ("last_expanded_prompt", None),
                            ("last_processor_frames", None), ("last_input_metadata", None)):
            if hasattr(item, name):
                setattr(item, name, empty)


def _failure_diagnostics(analyzer):
    captured = {}
    for item in _diagnostic_objects(analyzer):
        for name, key in (("last_generated_token_ids", "generated_token_ids"),
                          ("last_expanded_prompt", "expanded_prompt"),
                          ("last_input_metadata", "input_metadata")):
            if hasattr(item, name):
                captured[key] = getattr(item, name)
    return captured


def run_video(video: Path, camera: dict, analyzer, output: Path,
              run_context: dict, settings: dict) -> dict:
    """Return a durable summary, including a partial summary on execution failure.

    analyzer.analyze (or an equivalent callable) sees only original uint8 RGB,
    anonymous window ID, measured timing metadata and fixed ROI. No config text,
    filename, observations, official labels or event times reach the analyzer.
    Failures stop this attempt; retries belong to explicit queue operations.
    """
    video = Path(video)
    if not video.is_file():
        raise ValueError("source is not a local regular file")
    roi = _validate(camera, settings)
    output = create_output(output, settings.get("safe_output_roots"))
    (output / "windows").mkdir()
    (output / "evidence").mkdir()
    started = time.monotonic_ns()
    summary = {"schema_version": 1, "status": "running", "eof_reached": False,
               "run_context": run_context, "camera": camera, "settings": settings,
               "source": {"path": str(video.resolve()), "sha256": _hash(video)},
               "code": _provenance(), "started_at": timestamp(started),
               "windows_completed": 0, "analyzer_calls": 0,
               "functional_success": False, "action_quality": "not_evaluated",
               "realtime_latency_seconds": None,
               "latency_note": "Offline file wallclock is not real-time detection latency"}
    write_json(output / "run.json", summary)
    write_json(output / "summary.json", summary)
    stats = {}
    states = Counter()
    merger = EventMerger(camera["camera_id"])
    timings = []
    output_tokens = []
    newly_generated_tokens = []
    stage_totals, stage_samples = Counter(), Counter()
    reused_windows = 0
    gpu_memory = []
    failure = None
    active_id = None
    # These files exist before decoding; readers can follow promptly flushed data.
    with (output / "windows.jsonl").open("x") as windows_log, (
            output / "emissions.jsonl").open("x") as emissions:
        try:
            for window in iter_windows(video, stats=stats):
                active_id = window.window_id
                source = window.source()
                folder = output / "windows" / active_id
                folder.mkdir()
                rgb = window.rgb
                source["rgb_sha256"] = hashlib.sha256(memoryview(rgb)).hexdigest()
                source["rgb_shape"] = list(rgb.shape)
                write_json(folder / "input.json", source)
                call_start = time.monotonic_ns()
                if len(window.samples) < 2:
                    result = {"raw_response": None, "parsed": None, "parse": None,
                              "timing": {}, "input_metadata": {}, "output_tokens": None,
                              "gpu_memory": None, "skipped": "insufficient_data"}
                    window_states = [("insufficient_data", None)]
                else:
                    summary["analyzer_calls"] += 1
                    analyze = getattr(analyzer, "analyze", analyzer)
                    _clear_diagnostics(analyzer)
                    try:
                        result = analyze(rgb, source, active_id, roi)
                    except Exception as exc:
                        result = {"raw_response": None, "parsed": None, "parse": None,
                                  "execution_error": {"type": type(exc).__name__, "message": str(exc)},
                                  **_failure_diagnostics(analyzer)}
                        write_json(folder / "result.json", result)
                        raise
                    if not isinstance(result, dict):
                        raise ValueError("analyzer must return the contracted dictionary")
                    # Persist raw output BEFORE interpreting action states.
                    write_json(folder / "result.json", result)
                    window_states = classify(result)
                if not (folder / "result.json").exists():
                    write_json(folder / "result.json", result)
                elapsed = (time.monotonic_ns() - call_start) / 1e9
                saved = timestamp(started)
                record = {"window_id": active_id, "source": source,
                          "result": f"windows/{active_id}/result.json",
                          "window_record": f"windows/{active_id}/window.json",
                          "model_claims": ({key: result["parsed"].get(key) for key in
                                            ("observed_actions", "visible_evidence", "uncertainties", "crossing_completion")}
                                           if isinstance(result.get("parsed"), dict) else None),
                          "states": window_states,
                          "estimated_interval": [window.start, window.end],
                          "last_input_pts": source["last_input_pts"],
                          "last_arrived_pts": window.last_decoded_pts,
                          "available_at_source_time": source["available_at_source_time"],
                          "emission": saved, "analysis_and_persist_seconds": elapsed,
                          "tail": window.end < window.nominal_end,
                          "real_observations": len(window.samples)}
                write_json(folder / "window.json", record)
                append_json(windows_log, record)
                for event in merger.add(record):
                    append_json(emissions, event)
                summary["windows_completed"] += 1
                for state, _ in window_states:
                    states[state] += 1
                timings.append(elapsed)
                if isinstance(result.get("output_tokens"), (int, float)):
                    output_tokens.append(result["output_tokens"])
                reused = bool(result.get("reused", False))
                reused_windows += int(reused)
                new_tokens = result.get("newly_generated_tokens", 0 if reused else result.get("output_tokens"))
                if isinstance(new_tokens, (int, float)):
                    newly_generated_tokens.append(new_tokens)
                for stage, duration in (result.get("timing") or {}).items():
                    if reused and stage in {"prepare_seconds", "generation_seconds"}:
                        continue
                    if type(duration) in (int, float) and math.isfinite(duration) and duration >= 0:
                        stage_totals[stage] += duration
                        stage_samples[stage] += 1
                if result.get("gpu_memory") is not None:
                    gpu_memory.append(result["gpu_memory"])
                # No RGB or raw model responses are retained across windows.
                del rgb, result
                summary.update(decode=dict(stats), window_state_counts=dict(states),
                               last_completed_window_id=active_id, updated_at=timestamp(started))
                write_json(output / "summary.json", summary, replace=True)
                active_id = None
        except Exception as exc:
            failure = {"stage": "decode_or_analyze", "window_id": active_id,
                       "last_completed_window_id": summary.get("last_completed_window_id"),
                       "type": type(exc).__name__, "message": str(exc),
                       "last_decoded_pts": stats.get("last_decoded_pts"),
                       "at": timestamp(started)}
            write_json(output / "failure.json", failure)
    evidence_errors = []
    with (output / "events.jsonl").open("x") as event_log:
        for event in merger.events:
            event["final_merge_at"] = timestamp(started)
            try:
                event["evidence"] = save_evidence(
                    video, output / "evidence" / f"{event['event_id']}.mp4",
                    interval=event["estimated_interval"],
                    source_bounds=[stats["first_decoded_pts"], stats["source_end_seconds"]],
                    context_seconds=2.0)
            except Exception as exc:
                event["evidence_error"] = {"type": type(exc).__name__, "message": str(exc)}
                evidence_errors.append({"event_id": event["event_id"], **event["evidence_error"]})
            append_json(event_log, event)
    finished = timestamp(started)
    summary.update(status="failed" if failure or evidence_errors else "succeeded",
                   eof_reached=bool(stats.get("eof_reached")),
                   functional_success=bool(stats.get("eof_reached")) and not failure and not evidence_errors,
                   decode=stats, failure=failure, evidence_errors=evidence_errors,
                   window_state_counts=dict(states), event_count=len(merger.events),
                   event_state_counts=dict(Counter(e["state"] for e in merger.events)),
                   finished_at=finished, file_wallclock_seconds=finished["elapsed_seconds"],
                   analysis_and_persist_seconds={"total": sum(timings),
                                                "p50": float(np.percentile(timings, 50)) if timings else None,
                                                "p95": float(np.percentile(timings, 95)) if timings else None},
                   output_tokens=sum(output_tokens) if output_tokens else None,
                   output_response_tokens=sum(output_tokens) if output_tokens else None,
                   newly_generated_tokens=sum(newly_generated_tokens) if newly_generated_tokens else 0,
                   reused_windows=reused_windows,
                   measured_stage_seconds={key: stage_totals.get(key) if stage_samples.get(key) else None
                                           for key in {"prepare_seconds", "generation_seconds", "reuse_validation_seconds", *stage_totals}},
                   measured_stage_samples=dict(stage_samples),
                   gpu_memory_by_window=gpu_memory,
                   process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   artifacts={"windows": "windows.jsonl", "first_emissions": "emissions.jsonl",
                              "events": "events.jsonl", "evidence": "evidence/"})
    write_json(output / "summary.json", summary, replace=True)
    return summary
