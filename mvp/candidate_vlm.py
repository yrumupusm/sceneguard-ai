"""EXP-0033: fixed CV-candidate -> original-video -> existing Qwen3-VL pilot.

CPU preparation stays independent of model code; GPU generation occurs ONLY
inside the existing mvp-0001 canonical queue and its verified inherited lease.
No model/labels/tracker/regions are trained or changed by this module.
"""
import hashlib
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs/exp0033_cv_vlm_manifest.json"
PROMPT = ROOT / "configs/exp0033_cv_vlm_prompt.txt"
REFERENCE = ROOT / "configs/exp0033_review_reference.json"
EXPECTED = [
    ("c030_cv", "w000001", "E01_030", "C6", 85.0, 95.0, "cv_candidate"),
    ("c007_cv", "w000002", "E01_007", "C3", 64.0, 74.0, "cv_candidate"),
    ("c007_control", "w000003", "E01_007", "C3", 52.5, 57.5,
     "independent_negative_control_no_cv_gate"),
]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for buf in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def frozen_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (manifest.get("schema_version"), manifest.get("experiment_id")) != (1, "EXP-0033"):
        raise ValueError("Wrong EXP-0033 manifest")
    items = manifest.get("cases")
    if not isinstance(items, list) or len(items) != len(EXPECTED):
        raise ValueError("Exactly three fixed windows are required")
    for item, expected in zip(items, EXPECTED):
        observed = tuple(item.get(k) for k in ("case_id", "window_id", "source_id",
                    "camera_id", "start", "end", "mode"))
        if observed != expected or item.get("samples") != 10:
            raise ValueError("Fixed EXP-0033 window definition changed")
        if item["mode"] == "cv_candidate":
            if (not isinstance(item.get("original_event_file"), str) or
                    type(item.get("original_event_raw_id")) is not int or
                    type(item.get("original_event_emission_pts")) not in (int, float)):
                raise ValueError("Candidate must bind to an actual saved CV event")
        elif any(key.startswith("original_event") for key in item):
            raise ValueError("Negative control must not be falsely called CV-detected")
    videos = manifest.get("videos", [])
    expected_sources = {"E01_030": "2a8006450e18c1d6fe8b5022302cc7d75066ebbe356c6aab453147c5c4f48f88",
                        "E01_007": "df88fcfe8293b5c624a617bb9d36e68fb366acbd0a35835805ee35e31c5b7c04"}
    if len(videos) != 2 or {x["source_id"] for x in videos} != set(expected_sources):
        raise ValueError("Only original 030 and 007 sources allowed")
    for video in videos:
        sid = video["source_id"]
        if (video.get("path") != f"data/TS_침입/{sid}.mp4" or
                video.get("source_sha256") != expected_sources[sid]):
            raise ValueError("Original source SHA/path contract changed")
    if any(key in json.dumps(items).lower() for key in ('"reference_label"', '"expected_behavior"', '"completion_label"')):
        raise ValueError("No evaluation labels in VLM input manifest")
    return manifest


def candidate_prompt(window_id):
    if window_id not in {row[1] for row in EXPECTED}:
        raise ValueError("Unknown anonymous model window")
    return f"Clip ID: {window_id}\n" + PROMPT.read_text(encoding="utf-8").strip()


def verify_candidate_events(manifest):
    """Preflight original saved CV emission: never create a candidate from user labels."""
    events = {}
    for item in manifest["cases"]:
        if item["mode"] != "cv_candidate":
            continue
        source = ROOT / item["original_event_file"]
        if not source.is_file():
            raise FileNotFoundError(f"Missing original gap events: {source}")
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        target = item["original_event_emission_pts"]
        found = [r for r in rows if r.get("video_id") == item["source_id"] and
                 r.get("condition") == "gap" and
                 r.get("track_id") == item["original_event_raw_id"] and
                 isinstance(r.get("emitted_at_pts"), (int, float)) and
                 abs(r["emitted_at_pts"] - target) < .001]
        if len(found) != 1 or not item["start"] < target < item["end"]:
            raise ValueError("CV event not uniquely verified within original window")
        events[item["case_id"]] = {"source_event":found[0], "file":item["original_event_file"],
                                   "sha256":sha256(source)}
    return events


def sample_original(video_path, start, end, count=10):
    """Decode native PTS; select first actual frame at/after each target, no repeats."""
    import av
    import numpy as np
    if not (0 <= start < end and count == 10 and end-start <= 10.01):
        raise ValueError("Only fixed bounded 10-frame source windows")
    targets = [start + i*(end-start)/count for i in range(count)]
    selected = []
    chosen_keys = set()
    arrived_end, last_pts, previous_pts = False, None, None
    width, height, fps = None, None, None
    with av.open(str(video_path)) as container:
        if not container.streams.video:
            raise ValueError("Original CCTV has no video stream")
        stream = container.streams.video[0]
        rate = stream.average_rate or stream.guessed_rate
        if rate is None:
            raise ValueError("Original display FPS unavailable")
        fps = float(rate)
        if fps <= 0 or not math.isfinite(fps):
            raise ValueError("Invalid original source FPS")
        width, height = stream.width, stream.height
        next_target = 0
        for index, frame in enumerate(container.decode(stream)):
            if frame.pts is None or frame.time_base is None:
                raise ValueError("Missing original native PTS/timebase")
            pts = float(frame.pts*frame.time_base)
            if not math.isfinite(pts) or (previous_pts is not None and pts <= previous_pts):
                raise ValueError("Nonmonotonic native presentation time")
            previous_pts, last_pts = pts, pts
            if pts >= end:
                arrived_end = True
                break
            if pts < start or next_target >= count:
                continue
            if pts + 1e-9 < targets[next_target]:
                continue
            # A genuine decoder gap skips sampling targets; never repeat the frame.
            while next_target < count and targets[next_target] <= pts+1e-9:
                next_target += 1
            key = index, int(frame.pts), str(frame.time_base)
            if key in chosen_keys:
                raise ValueError("Duplicate decoded frame")
            chosen_keys.add(key)
            rgb = frame.to_ndarray(format="rgb24")
            if rgb.shape != (height, width, 3):
                raise ValueError("Native frame dimensions changed")
            selected.append(dict(rgb=rgb, pts=pts, native_pts=int(frame.pts),
                                 time_base=str(frame.time_base), decoded_index=index,
                                 rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest()))
    if not arrived_end:
        raise ValueError("Window end was not observed in original source")
    if not 2 <= len(selected) <= count:
        raise ValueError("Insufficient genuine frames in selected original window")
    indices=[x["decoded_index"] for x in selected]
    source=dict(fps=fps, pts_seconds=[x["pts"] for x in selected],
                native_pts=[x["native_pts"] for x in selected],
                time_base=[x["time_base"] for x in selected],
                relative_indices=[k-indices[0] for k in indices],
                decoded_indices=indices,
                source_size=[width,height], window_start=start, window_end=end,
                last_decoded_pts=last_pts,
                source_sampling="uniform_target_first_decoded_frame_at_or_after;no_duplicates",
                sampled_original_frame_sha256=[x["rgb_sha256"] for x in selected])
    return np.stack([x["rgb"] for x in selected]), source


def claim(parsed):
    """Parsed VLM *claim*, not ground truth or an automatically confirmed incident."""
    if parsed is None:
        return "unreadable_or_invalid_model_output"
    actions = set(parsed["observed_actions"])
    if "climbing_attempt_or_in_progress" in actions or "stepping_over_boundary" in actions:
        return "model_claims_climbing_needs_human_review"
    if "indeterminate" in actions or parsed["crossing_completion"] == "indeterminate":
        return "model_undetermined"
    if parsed["crossing_completion"] == "observed":
        return "inconsistent_completion_claim_needs_review"
    return "model_did_not_claim_climbing_not_verified_negative"


def run_candidate_review(analyzer, folder, context, cameras, registered_inputs):
    """Run inside existing canonical mvp-0001 queue after model+lease preflight."""
    from orchestration.mock_job import atomic_json
    from mvp.evidence import save_evidence

    manifest = frozen_manifest()
    events = verify_candidate_events(manifest)
    source_rows = {x["source_id"]:x for x in manifest["videos"]}
    for sid, item in source_rows.items():
        path = ROOT / item["path"]
        if sha256(path) != item["source_sha256"] or registered_inputs["videos"][sid] != item["source_sha256"]:
            raise ValueError("Source video differs from queue-registered bytes")
    outcomes=[]
    for case in manifest["cases"]:
        wid=case["window_id"]
        target=folder/"windows"/wid
        target.mkdir(parents=True,exist_ok=False)
        video=ROOT/source_rows[case["source_id"]]["path"]
        rgb, source=sample_original(video,case["start"],case["end"],case["samples"])
        metadata={**{k:case[k] for k in ("case_id","window_id","source_id","camera_id","start","end","mode")},
                  "source_sha256":source_rows[case["source_id"]]["source_sha256"],
                  "original_cv_event":events.get(case["case_id"]),
                  "roi":cameras["cameras"][case["camera_id"]]["roi"],
                  "source_timing":source}
        atomic_json(target/"input_provenance.json",metadata)
        # Model sees ONLY original RGB, timing metadata, anonymized ID and same static prompt.
        analyzer.artifact_root=folder/"windows"
        result=analyzer.analyze(rgb,source,wid,list(metadata["roi"]))
        atomic_json(target/"result.json",result)
        (target/"raw_response.txt").write_text(result.get("raw_response",""),encoding="utf-8")
        parsed=result.get("parsed")
        outcome=dict(case_id=case["case_id"],window_id=wid, source_id=case["source_id"],
                     mode=case["mode"],original_cv_verified=case["case_id"] in events,
                     sampled_frames=len(rgb),
                     sample_pts=source["pts_seconds"], model_claim=claim(parsed),
                     observed_actions=parsed["observed_actions"] if parsed else [],
                     visible_evidence=parsed["visible_evidence"] if parsed else None,
                     crossing_completion_claim=parsed["crossing_completion"] if parsed else "unknown",
                     uncertainties=parsed["uncertainties"] if parsed else None,
                     parse_status=result["parse"],
                     generation_seconds=result.get("timing",{}).get("generation_seconds"),
                     model_output_tokens=result.get("output_tokens"),
                     identity_verified=False,physical_completion_verified=False)
        # Always preserve the same uncropped source for a reviewer, including control.
        clip=save_evidence(video,target/"original_clip.mp4",
                           interval=[case["start"],case["end"]],
                           source_bounds=[0,case["end"]],context_seconds=0)
        outcome["evidence_file"]=str(Path("windows")/wid/"original_clip.mp4")
        outcome["source_original_frames"]=clip["frames"]
        atomic_json(target/"review_record.json",outcome)
        outcomes.append(outcome)
    if len(outcomes)!=3:
        raise ValueError("Not all fixed Qwen cases completed")
    atomic_json(folder/"candidate_vlm_results.json",{
        "experiment_id":"EXP-0033","status":"three_cases_analyzed_not_automatically_verified",
        "new_model_or_training":False, "existing_cv_events_not_modified":True,
        "model_phase":"candidate-vlm","results":outcomes,
        "note":"No labels were supplied to the model. Evaluate against references only AFTER model completion."})
    parts=["<!doctype html><html lang='ko'><meta charset='utf-8'><title>SceneGuard CV→VLM</title>",
           "<style>body{font-family:system-ui;max-width:880px;margin:3rem auto;padding:0 1rem}article{margin:2rem 0;padding:1rem;border:1px solid #aaa;border-radius:.6rem}video{width:100%}pre{white-space:pre-wrap}</style>",
           "<h1>CV → Qwen3-VL: 3개 개발 장면</h1><p>AI 판단은 검토 의견이며 침입 완료 판정이 아닙니다.</p>"]
    for x in outcomes:
        parts.append("<article><h2>"+html.escape(x["case_id"])+"</h2>"
                     "<p>"+html.escape(x["model_claim"])+"</p>"
                     "<video controls preload='metadata' src='"+html.escape(x["evidence_file"],quote=True)+"'></video>"
                     "<pre>"+html.escape(x["visible_evidence"] or "근거 없음")+"</pre></article>")
    parts.append("</html>")
    (folder/"index.html").write_text("".join(parts),encoding="utf-8")
    return outcomes


def posthoc_reference_review(model_output, reference=REFERENCE):
    """CPU only: attach *separately held* human/coarse references after inference."""
    record=json.loads(Path(model_output).read_text(encoding="utf-8"))
    labels=json.loads(Path(reference).read_text(encoding="utf-8"))
    if record.get("status")!="three_cases_analyzed_not_automatically_verified":
        raise ValueError("Not a complete fixed VLM pilot result")
    if labels.get("experiment_id")!="EXP-0033":
        raise ValueError("Wrong reference version")
    reviews={x["case_id"]:x for x in labels["references"]}
    if set(reviews)!={x["case_id"] for x in record["results"]}:
        raise ValueError("Reference/case mismatch")
    def preliminary(model, status):
        # A reference/claim contrast, NOT an independently checked video verdict.
        positive = model == "model_claims_climbing_needs_human_review"
        negative = model == "model_did_not_claim_climbing_not_verified_negative"
        if status == "no_climbing_human_confirmed_in_window":
            return ("contradicts_confirmed_no_attempt_window" if positive else
                    "no_climbing_claim_consistent_with_reference" if negative else "indeterminate")
        if status == "climbing_attempt_seen_user_coarse":
            return ("claim_temporally_consistent_requires_evidence_review" if positive else
                    "model_did_not_claim_observed_attempt" if negative else "indeterminate")
        return "no_supported_reference_for_comparison"
    return [{"case_id":x["case_id"],"model_claim":x["model_claim"],
             "human_observation_scope":reviews[x["case_id"]]["reference_status"],
             "completion_reference":reviews[x["case_id"]]["completion"],
             "review_source":reviews[x["case_id"]]["evidence"],
             "preliminary_alignment":preliminary(x["model_claim"],reviews[x["case_id"]]["reference_status"]),
             "visual_agreement_verified":False,
             "requires_original_video_review":True}
            for x in record["results"]]


def main():
    import argparse
    p=argparse.ArgumentParser(description="EXP-0033 fixed CPU preflight or post-model review")
    sub=p.add_subparsers(dest="action",required=True)
    sub.add_parser("preflight")
    review=sub.add_parser("review")
    review.add_argument("--results",type=Path,required=True)
    review.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.action=="preflight":
        m=frozen_manifest()
        matched=verify_candidate_events(m)
        for video in m["videos"]:
            path=ROOT/video["path"]
            if sha256(path)!=video["source_sha256"]:
                raise ValueError("Original source video hash differs")
        print(json.dumps({"cases":len(m["cases"]),"sources":len(m["videos"]),
                          "verified_cv_trigger_cases":len(matched),
                          "negative_controls_without_cv_gate":1,
                          "gpu_or_model_used":False},ensure_ascii=False))
    else:
        out=args.output
        if (not out.resolve().is_relative_to((ROOT/"outputs").resolve()) or
                out.exists() or out.is_symlink() or any(x.is_symlink() for x in out.parents)):
            raise FileExistsError("Only new local ignored outputs/ JSON file is permitted")
        review=posthoc_reference_review(args.results)
        out.parent.mkdir(parents=True,exist_ok=True)
        with out.open("x",encoding="utf-8") as stream:
            json.dump({"experiment_id":"EXP-0033","status":"reference_contrast_not_independent_truth",
                       "reviews":review},stream,indent=2,ensure_ascii=False,allow_nan=False)
            stream.write("\n")
        print(json.dumps({"reviews":len(review),"visual_agreement_verified":False},ensure_ascii=False))


if __name__=="__main__":
    main()
