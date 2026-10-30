"""EXP-0032 incident-window evaluation of *existing* gap-line event emissions.

Strict scope: a candidate is not a verified physical crossing; window-presence
coverage is not complete-event recall; unreviewed time is NOT negative time.
No detector, tracker, labels inferred from official metadata, or video decoding.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

ALLOWED = {
    "confirmed_positive_window", "confirmed_negative_window",
    "provisional_positive_window", "provisional_negative_window",
    "unreviewed_window",
}
VERIFIED = {"confirmed_positive_window", "confirmed_negative_window"}
MIN_FALSE_ALARM_HOURS = 5 / 60  # Do not report a volatile per-hour rate below 5 min.


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}: finite number required")
    return float(value)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_manifest(manifest):
    if manifest.get("schema_version") != 1 or manifest.get("experiment_id") != "EXP-0032":
        raise ValueError("Not the EXP-0032 evaluation manifest")
    videos = manifest.get("videos")
    if not isinstance(videos, list) or not videos:
        raise ValueError("Nonempty videos required")
    seen_vids, seen_labels = set(), set()
    for video in videos:
        vid = video.get("video_id")
        if not isinstance(vid, str) or not vid.startswith("E01_") or vid in seen_vids:
            raise ValueError("Unique video_id required")
        seen_vids.add(vid)
        if video.get("role") != "development_only":
            raise ValueError("Only development data may be called development_only")
        source = video.get("source_sha256")
        if not isinstance(source, str) or len(source) != 64 or any(c not in "0123456789abcdef" for c in source):
            raise ValueError("Exact source SHA256 required")
        if not isinstance(video.get("camera_group"), str) or not video["camera_group"]:
            raise ValueError("Missing camera-group leakage marker")
        lo, hi = video["evaluated_window"]
        lo, hi = number(lo, "evaluated start"), number(hi, "evaluated end")
        if not 0 <= lo < hi:
            raise ValueError("Invalid evaluated time window")
        for w in video["reference_windows"]:
            key = w.get("window_id")
            if not isinstance(key, str) or not key or key in seen_labels:
                raise ValueError("Duplicate or empty review window ID")
            seen_labels.add(key)
            if w.get("status") not in ALLOWED:
                raise ValueError("Unknown reference status")
            a, b = w["interval"]
            a, b = number(a, "review start"), number(b, "review end")
            if not lo <= a < b <= hi + 1e-6:
                raise ValueError("Review interval outside actual evaluated clip")
            if not isinstance(w.get("evidence"), str) or not w["evidence"]:
                raise ValueError("Every reference needs a provenance pointer")
            if w["status"] in VERIFIED and w.get("review_basis") != "human_confirmed_for_window":
                raise ValueError("Confirmed window requires human-confirmed provenance")
            if w["status"] not in VERIFIED and w.get("review_basis") == "human_confirmed_for_window":
                raise ValueError("Do not silently demote human-confirmed reference")
        known = [w for w in video["reference_windows"] if w["status"] in VERIFIED]
        ordered = sorted(known, key=lambda w: (w["interval"][0], w["interval"][1]))
        for x, y in zip(ordered, ordered[1:]):
            if x["interval"][1] > y["interval"][0] + 1e-9:
                raise ValueError("Overlapping confirmed windows are not independent")
        if not (isinstance(video.get("cache_metadata"), str) and
                isinstance(video.get("prediction_file"), str) and
                isinstance(video.get("replay_summary"), str)):
            raise ValueError("Cache, replay summary, and event paths required")
    return manifest


def load_jsonl(path):
    records = []
    for no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed prediction row {no}") from e
    return records


def read_saved_events(video):
    """Validate existing cache/replay provenance even when events.jsonl is empty."""
    meta_path = Path(video["cache_metadata"])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    vid = video["video_id"]
    if (meta.get("status") != "complete" or meta.get("video_id") != vid or
            meta.get("source_sha256") != video["source_sha256"]):
        raise ValueError(f"{vid}: incomplete or wrong video/cache SHA")
    if meta.get("person_cache", {}).get("stage") != "model_return_after_internal_filters_nms_global_cap_before_project_score":
        raise ValueError(f"{vid}: not the unchanged pretrained FCOS cache stage")
    cache_path = meta_path.parent / "person_cache.jsonl"
    cache_hash = digest(cache_path)
    if meta["person_cache"].get("sha256") != cache_hash:
        raise ValueError(f"{vid}: person cache was altered")
    requested = meta.get("requested_window")
    want = video["evaluated_window"]
    if not isinstance(requested, list) or len(requested) != 2:
        raise ValueError(f"{vid}: missing actual requested window")
    if abs(number(requested[0], "clip start")-number(want[0], "clip start")) > .05:
        raise ValueError(f"{vid}: prediction source has wrong clip start")
    # The source may end a fraction of a frame early, but never rely on missing footage.
    if abs(number(requested[1], "clip end")-number(want[1], "clip end")) > .05:
        raise ValueError(f"{vid}: prediction source has wrong clip end")
    if not meta.get("frames") or not (want[0]-.05 <= meta["first_pts"] < want[0]+.05):
        raise ValueError(f"{vid}: wrong source coverage beginning")
    if not want[1]-.06 <= meta["last_pts"] < want[1]+1e-6:
        raise ValueError(f"{vid}: source did not cover the requested review end")
    summary_path = Path(video["replay_summary"])
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "complete":
        raise ValueError(f"{vid}: replay incomplete")
    matches = [c for c in summary.get("comparisons", []) if c.get("condition") == "gap"]
    if len(matches) != 1:
        raise ValueError(f"{vid}: expected exactly one gap-line replay")
    gap = matches[0]
    if gap.get("input_sha256") != {"cache": cache_hash, "metadata": digest(meta_path)}:
        raise ValueError(f"{vid}: replay inputs are not this FCOS cache")
    records = load_jsonl(video["prediction_file"])
    if gap.get("candidates") != len(records):
        raise ValueError(f"{vid}: saved event count mismatch")
    output = []
    for i, r in enumerate(records):
        if r.get("video_id") != vid or r.get("condition") != "gap":
            raise ValueError("Mixed video or strict/other candidate in gap evaluation")
        at = number(r["emitted_at_pts"], "event emission")
        estimated = number(r["candidate_pts"], "candidate time")
        a,b = r["candidate_interval"]
        if (not want[0] <= estimated <= at < want[1] or
                abs((number(a,"candidate start")+number(b,"candidate end"))/2-estimated)>1e-5 or
                not a <= b <= at):
            raise ValueError("Invalid original/native event timestamps")
        output.append(dict(original_row=i+1, emitted_at_pts=at,
                           estimated_at_pts=estimated, raw_track_id=r.get("track_id"),
                           direction=r.get("direction")))
    return output, dict(cache_sha256=cache_hash, metadata_sha256=digest(meta_path),
                        event_sha256=digest(video["prediction_file"]),
                        replay_sha256=digest(summary_path),
                        original_events=len(records), input_frames=meta["frames"])


def dedup_incidents(events, merge_seconds=2.0):
    """Prespecified episode unit: alerts within 2 s in one camera => one candidate.

    Keeps member IDs, does NOT assert that separate people are the same.
    """
    merge_seconds = number(merge_seconds, "merge_seconds")
    if merge_seconds <= 0:
        raise ValueError("Positive dedup seconds required")
    groups = []
    for e in sorted(events, key=lambda x:(x["emitted_at_pts"],x["original_row"])):
        t = number(e["emitted_at_pts"],"emission")
        if not groups or t-groups[-1]["last_emitted_at_pts"]>merge_seconds+1e-9:
            groups.append(dict(incident_id=f"candidate-{len(groups)+1:04d}",
                               first_emitted_at_pts=t,last_emitted_at_pts=t,
                               observed_raw_track_ids=[], original_event_rows=[],
                               member_emission_pts=[]))
        g = groups[-1]
        g["last_emitted_at_pts"]=t
        g["original_event_rows"].append(e["original_row"])
        g["member_emission_pts"].append(t)
        if e["raw_track_id"] not in g["observed_raw_track_ids"]:
            g["observed_raw_track_ids"].append(e["raw_track_id"])
    return groups


def _window_hit(group, interval):
    # Assign an episode to exactly one review window by its FIRST emission.
    # Do not double count a continuous alert burst spanning adjacent windows.
    # This is an episode output clock, not the hindsight-estimated crossing time.
    t = group["first_emitted_at_pts"]
    return interval[0] <= t < interval[1]


def evaluate_window_presence(manifest, predictions):
    """Counts only verified *windows*, not complete events or all unreviewed time."""
    validate_manifest(manifest)
    per_video = []
    totals = dict(confirmed_positive_windows=0, positive_windows_with_candidate=0,
                  confirmed_negative_windows=0, negative_windows_with_candidate=0,
                  false_alarm_candidate_episodes_in_confirmed_negative=0,
                  verified_negative_seconds=0., provisional_windows=0,
                  unreviewed_incidents=0, raw_candidates=0, candidate_episodes=0)
    for video in manifest["videos"]:
        vid = video["video_id"]
        if vid not in predictions:
            raise ValueError(f"Missing complete prediction input for {vid}")
        events = predictions[vid]
        groups = dedup_incidents(events)
        totals["raw_candidates"] += len(events)
        totals["candidate_episodes"] += len(groups)
        rows = []
        covered = set()
        for w in video["reference_windows"]:
            hits = [g for g in groups if _window_hit(g, w["interval"])]
            status = w["status"]
            if status == "confirmed_positive_window":
                totals["confirmed_positive_windows"] += 1
                totals["positive_windows_with_candidate"] += bool(hits)
                covered.update(g["incident_id"] for g in hits)
                verdict = "candidate_present_in_reviewed_window" if hits else "missed_in_reviewed_window"
            elif status == "confirmed_negative_window":
                totals["confirmed_negative_windows"] += 1
                totals["verified_negative_seconds"] += w["interval"][1]-w["interval"][0]
                totals["negative_windows_with_candidate"] += bool(hits)
                totals["false_alarm_candidate_episodes_in_confirmed_negative"] += len(hits)
                covered.update(g["incident_id"] for g in hits)
                verdict = "false_alarm_in_reviewed_window" if hits else "no_alarm_in_reviewed_window"
            else:
                totals["provisional_windows"] += 1
                verdict = "not_scored_unverified_reference"
            rows.append(dict(window_id=w["window_id"],status=status,
                             interval=w["interval"],evidence=w["evidence"],
                             candidate_episode_ids=[g["incident_id"] for g in hits],
                             interpretation=verdict))
        unknown = [g["incident_id"] for g in groups if g["incident_id"] not in covered]
        totals["unreviewed_incidents"] += len(unknown)
        per_video.append(dict(video_id=vid, role=video["role"],
                              camera_group=video["camera_group"],
                              raw_candidates=len(events), candidate_episodes=groups,
                              reference_windows=rows,
                              not_scored_candidate_ids=unknown))
    # No full-event labels have been validated; this is explicitly window PRESENCE.
    pos = totals["confirmed_positive_windows"]
    neg = totals["confirmed_negative_windows"]
    totals["positive_window_coverage"] = totals["positive_windows_with_candidate"]/pos if pos else None
    totals["negative_window_no_alarm_fraction"] = (neg-totals["negative_windows_with_candidate"])/neg if neg else None
    hrs = totals["verified_negative_seconds"]/3600
    totals["false_alarms_per_hour"] = (totals["false_alarm_candidate_episodes_in_confirmed_negative"]/hrs
           if hrs >= MIN_FALSE_ALARM_HOURS else None)
    totals["confirmed_complete_incident_recall"] = None
    totals["event_precision"] = None
    totals["event_f1"] = None
    return dict(experiment_id="EXP-0032",scope="development_only_partial_window_review",
                candidate_type="ByteTrack_gap_line_output_not_physical_completion",
                clock="original_event_emission_pts_not_hindsight_timestamp",
                merge_seconds=2., metrics=totals, per_video=per_video,
                limitations=["Provisional and unreviewed time is never scored negative",
                             "Confirmed positive-window coverage is NOT full-incident recall",
                             "No completed-crossing or per-person identity ground truth",
                             "Camera groups may share sites; no independent/blind test",
                             "Negative exposure below 5 min has no hourly alarm rate"])


def run_cli(manifest_path, output):
    p = Path(output)
    if (not p.resolve().is_relative_to(Path("outputs").resolve()) or
            p.exists() or p.is_symlink() or any(x.is_symlink() for x in p.parents)):
        raise FileExistsError("Use a new, non-symlink local outputs path")
    manifest_bytes = Path(manifest_path).read_bytes()
    m = validate_manifest(json.loads(manifest_bytes))
    feeds, prov = {}, {}
    for video in m["videos"]:
        feeds[video["video_id"]], prov[video["video_id"]] = read_saved_events(video)
    result = evaluate_window_presence(m, feeds)
    result["input_provenance"] = prov
    result["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return result


def main():
    import argparse
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--manifest",type=Path,default=Path("configs/exp0032_incident_windows.json"))
    cli.add_argument("--output",type=Path,required=True)
    args=cli.parse_args()
    result=run_cli(args.manifest,args.output)
    print(json.dumps(result["metrics"],ensure_ascii=False,indent=2,allow_nan=False))


if __name__ == "__main__":
    main()
