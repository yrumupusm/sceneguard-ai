"""Freeze seven CPU-only detection evaluation inputs; never load a model.

Paths and images in the resulting manifest are local only. Existing preparation
approval flags are historical evidence and are never modified by this script.
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA256 = "92ee33df46b231e70a26d9901f361a67845c882ce0afd2f0c97e55dca7622549"
FIXED_SAMPLES = (
    ("030_084", "E01_030", 84), ("030_090", "E01_030", 90),
    ("030_094", "E01_030", 94), ("030_050", "E01_030", 50),
    ("030_055", "E01_030", 55), ("007_047p5", "E01_007", 47.5),
    ("007_052p5", "E01_007", 52.5),
)
RATIONALE = (
    "Three climbing development frames previously reviewed by the user, plus four "
    "fixed normal-approach checks. These checks are not formal negative events or "
    "precise box GT; there is no independent GT. Selection is fixed before inference, "
    "without model-based selection. Evaluate person detection, not behavior."
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def relative(root, path):
    return Path(path).resolve().relative_to(root.resolve()).as_posix()


def roi_pixels(roi, width, height):
    require(len(roi) == 4 and all(math.isfinite(v) for v in roi), "Invalid ROI")
    x1, y1, x2, y2 = roi
    require(0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1, "Invalid ROI bounds")
    return [math.floor(x1 * width), math.floor(y1 * height),
            math.ceil(x2 * width), math.ceil(y2 * height)]


def exact_native_pts(seconds, time_base):
    native = Fraction(str(seconds)) / Fraction(time_base)
    require(native.denominator == 1, "Requested time is not an exact native PTS")
    return native.numerator


def decode_exact(path, seconds):
    """CPU seek/decode; never select the closest frame or resample timestamps."""
    import av
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "NONE"
        base = str(stream.time_base)
        target = exact_native_pts(seconds, base)
        container.seek(target, stream=stream, backward=True, any_frame=False)
        traversed = 0
        for frame in container.decode(stream):
            traversed += 1
            if frame.pts is None or frame.pts < target:
                continue
            require(frame.pts == target and Fraction(frame.time_base) == Fraction(base),
                    "Exact requested native PTS absent or time base changed")
            return frame.to_ndarray(format="rgb24"), target, base, traversed
        raise ValueError("Decoder EOF before exact requested PTS")


def cached_rgb(root, row, source, seconds):
    require(row["source_id"] == source["source_id"] and
            row["source_sha256"] == source["sha256"], "Cached source mismatch")
    require(row["source_path"] == source["relative_video_path"], "Cached source path mismatch")
    require(Fraction(row["native_pts"]) * Fraction(row["time_base"]) == Fraction(str(seconds))
            and Fraction(str(row["pts_seconds"])) == Fraction(str(seconds)), "Cached exact PTS mismatch")
    path = root / row["rgb_path"]
    require(sha_file(path) == row["rgb_sha256"], "Cached npy file hash mismatch")
    rgb = np.load(path, allow_pickle=False)
    require(rgb.dtype == np.uint8 and rgb.ndim == 3 and rgb.shape[2] == 3,
            "Cached RGB dtype/shape invalid")
    require(list(rgb.shape) == row["rgb_shape"] and
            sha_bytes(rgb.tobytes()) == row["rgb_bytes_sha256"], "Cached RGB hash/shape mismatch")
    return rgb


def audit_dataset(dataset):
    """Bind every split image to the unchanged Roboflow source export."""
    import yaml
    manifest_path = dataset / "manifest.json"
    summary_path = dataset / "summary.json"
    manifest, summary = read_json(manifest_path), read_json(summary_path)
    require(summary["archive_sha256"] == ARCHIVE_SHA256, "Wrong training source archive")
    config = yaml.safe_load((dataset / "data.yaml").read_text())
    require(config["nc"] == 1 and config["names"] == ["person"] and
            Path(config["path"]).resolve() == dataset.resolve(), "Training YAML mapping mismatch")
    for split, key in (("train", "train"), ("valid", "val"), ("test", "test")):
        require(config[key] == f"{split}/images", "Training split path mismatch")
    members = {r["name"]: r["sha256"] for r in manifest["source_members"]}
    for name, digest in members.items():
        require(sha_file(dataset / "source" / name) == digest, "Original dataset source hash mismatch")
    counts, rows, image_hashes, split_hashes = Counter(), Counter(), [], {}
    for sample in manifest["samples"]:
        name = sample["image"]
        split = Path(name).parts[0]
        require(split in ("train", "valid", "test") and Path(name).parts[1] == "images",
                "Unexpected dataset image path")
        require(members[name] == sample["image_sha256"] == sha_file(dataset / name),
                "Training image not identical to Roboflow archive source")
        label = sample["source_label"]
        require(members[label] == sample["source_label_sha256"], "Raw label binding mismatch")
        require(sha_file(dataset / label) == sample["output_label_sha256"], "Prepared label hash mismatch")
        require(not any(token in name.lower() for token in ("e01_", "sceneguard")),
                "SceneGuard source name in training dataset")
        counts[split] += 1
        rows[split] += sample["person_rows"]
        image_hashes.append(sample["image_sha256"])
    require(dict(counts) == {"train": 210, "valid": 20, "test": 17}, "Dataset split counts changed")
    require(dict(rows) == {"train": 279, "valid": 24, "test": 51}, "Dataset row counts changed")
    for split in counts:
        expected_images = {s["image"] for s in manifest["samples"] if s["image"].startswith(split + "/")}
        expected_labels = {s["source_label"] for s in manifest["samples"] if s["image"].startswith(split + "/")}
        require({p.relative_to(dataset).as_posix() for p in (dataset / split / "images").iterdir()} == expected_images,
                "Extra/missing dataset images")
        require({p.relative_to(dataset).as_posix() for p in (dataset / split / "labels").iterdir()} == expected_labels,
                "Extra/missing dataset labels")
        records = [s for s in manifest["samples"] if s["image"] in expected_images]
        split_hashes[split] = sha_bytes(json.dumps(records, sort_keys=True, separators=(",", ":")).encode())
    return dict(dataset_path=str(dataset), archive_sha256=ARCHIVE_SHA256,
                manifest_sha256=sha_file(manifest_path), summary_sha256=sha_file(summary_path),
                data_yaml_sha256=sha_file(dataset / "data.yaml"), split_images=dict(counts),
                split_person_rows=dict(rows), split_records_sha256=split_hashes,
                all_images_identical_to_preserved_roboflow_source=True,
                provided_sceneguard_inputs_in_training=False,
                exclusion_evidence="All 247 images exactly match preserved archive-source hashes; no extra files or SceneGuard source names.",
                independent_source_overlap_ruled_out=False,
                human_box_review_complete=False, independent_gt=False,
                historical_preparation_flags_unchanged=True,
                image_file_hashes=image_hashes)


def prepare(root, destination, dataset, manifest_path=None):
    root, destination, dataset = root.resolve(), destination.resolve(), dataset.resolve()
    manifest_path = (manifest_path or destination / "evaluation-manifest.local.json").resolve()
    require(destination.is_relative_to(root), "Output must be inside repository")
    require(manifest_path.is_relative_to(root), "Manifest must be inside repository")
    if destination.exists() or manifest_path.exists():
        raise FileExistsError("Evaluation output exists; never overwrite")
    sources_path = root / "configs/mvp0001_sources.json"
    cameras_path = root / "configs/mvp0001_cameras.json"
    prior_path = root / "configs/batch0005_pose_manifest.json"
    cached_path = root / "runtime/BATCH-0003/frame-binding.json"
    sources = {s["source_id"]: s for s in read_json(sources_path)["continuous_sources"]}
    cameras = read_json(cameras_path)["cameras"]
    prior = read_json(prior_path)
    bindings = [*prior["frames"], *read_json(cached_path)["frames"]]
    audit = audit_dataset(dataset)
    audit["dataset_path"] = relative(root, dataset)
    for sid, cid in (("E01_030", "C6"), ("E01_007", "C3")):
        require(sources[sid]["camera_id"] == cid, "Camera mapping changed")
        require(sha_file(root / sources[sid]["relative_video_path"]) == sources[sid]["sha256"],
                "Original video source hash mismatch")
    frames, staged = [], []
    for frame_id, sid, seconds in FIXED_SAMPLES:
        source = sources[sid]
        matches = [b for b in bindings if b["source_id"] == sid and
                   Fraction(str(b["pts_seconds"])) == Fraction(str(seconds))]
        if matches:
            old = matches[0]
            rgb = cached_rgb(root, old, source, seconds)
            native, base = old["native_pts"], old["time_base"]
            provenance = dict(method="exact_native_pts_cached_rgb", cached_rgb_path=old["rgb_path"],
                              binding_path=relative(root, prior_path if old in prior["frames"] else cached_path),
                              binding_sha256=sha_file(prior_path if old in prior["frames"] else cached_path))
        else:
            rgb, native, base, traversed = decode_exact(root / source["relative_video_path"], seconds)
            provenance = dict(method="pyav_cpu_exact_native_pts", decoded_frames_including_seek_preroll=traversed)
        require(rgb.dtype == np.uint8 and rgb.ndim == 3 and rgb.shape[2] == 3, "RGB dtype/shape invalid")
        require(native == exact_native_pts(seconds, base), "Native timestamp mismatch")
        camera = cameras[source["camera_id"]]
        pixels = roi_pixels(camera["roi"], rgb.shape[1], rgb.shape[0])
        if sid == "E01_030":
            require(pixels == [537, 216, 1440, 864] and camera["roi"] == prior["camera"]["roi"],
                    "C6 crop changed")
        x1, y1, x2, y2 = pixels
        crop = np.ascontiguousarray(rgb[y1:y2, x1:x2])
        require(crop.size > 0, "Empty crop")
        if frame_id in prior.get("crop_bytes_sha256", {}):
            require(sha_bytes(crop.tobytes()) == prior["crop_bytes_sha256"][frame_id], "Historical C6 crop changed")
        row = dict(frame_id=frame_id, source_id=sid, source_path=source["relative_video_path"],
                   source_sha256=source["sha256"], camera_id=source["camera_id"],
                   requested_seconds=seconds, native_pts=native, time_base=base,
                   pts_seconds=float(Fraction(native) * Fraction(base)), color_space="RGB", dtype="uint8",
                   source_size=[rgb.shape[1], rgb.shape[0]], roi=camera["roi"], crop_xyxy=pixels,
                   roi_provenance=dict(selection=camera["selection"], selection_source=camera["selection_source"]),
                   provenance=provenance)
        for prefix, array in (("rgb", rgb), ("crop", crop)):
            path = destination / "evaluation-inputs" / f"{frame_id}-{prefix}.npy"
            row[prefix + "_path"] = relative(root, path)
            row[prefix + "_shape"] = list(array.shape)
            row[prefix + "_bytes_sha256"] = sha_bytes(array.tobytes())
            staged.append((path, np.ascontiguousarray(array), row, prefix))
        frames.append(row)
    # All source/cache/PTS/dataset checks precede creating output files.
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "evaluation-inputs").mkdir()
    for path, array, row, prefix in staged:
        with path.open("xb") as handle:
            np.save(handle, array, allow_pickle=False)
        row[prefix + "_sha256"] = sha_file(path)
    audit["evaluation_npy_file_hash_overlap_with_dataset"] = sorted(
        set(audit.pop("image_file_hashes")) & {r[k] for r in frames for k in ("rgb_sha256", "crop_sha256")})
    result = dict(schema_version=1, batch="BATCH-0007", experiment_id="EXP-0026",
                  scope="fixed person detection development inputs; no behavior or independent GT",
                  sample_rationale=RATIONALE, exact_pts_required=True, nearest_frame_selection=False,
                  model_based_selection=False, event_labels_in_model_input=False,
                  independent_gt=False, human_visual_review="deferred", local_only=True,
                  camera_config_sha256=sha_file(cameras_path),
                  historical_environment_pins=prior.get("environment", {}),
                  source_pins={relative(root, p): sha_file(p) for p in (sources_path, cameras_path, prior_path, cached_path)},
                  preparation_script_sha256=sha_file(Path(__file__)), dataset_audit=audit, frames=frames)
    for path, value in ((manifest_path, result), (destination / "evaluation-frames.local.json", frames)):
        with path.open("x") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("runtime/BATCH-0007/training/evaluation-preparation"))
    parser.add_argument("--dataset", type=Path, default=Path("data/climbing_fence/person_bbox_draft_v1"))
    parser.add_argument("--manifest", type=Path, default=Path("runtime/BATCH-0007/training/evaluation-manifest.local.json"))
    args = parser.parse_args()
    result = prepare(ROOT, ROOT / args.output, ROOT / args.dataset, ROOT / args.manifest)
    print(json.dumps(dict(frames=len(result["frames"]), dataset_audit=result["dataset_audit"], output=str(args.output)), indent=2))


if __name__ == "__main__":
    main()
