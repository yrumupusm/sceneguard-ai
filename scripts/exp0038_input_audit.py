"""CPU-only EXP38 frozen-input audit and local review inventory.

Never loads a model, downloads files, or parses historical model responses.
Protected response files are hashed as opaque bytes only. Run with the existing
CV environment from the repository root; all generated artifacts stay local.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
AUDIT = ROOT / "runtime/EXP-0038/input-audit"
REVIEW = ROOT / "outputs/exp0038/input-review"
BASELINE = ROOT / "outputs/mvp0001/EXP-0034/565b65a15fee492a8aea0e29bde1cb4e"
MANIFEST = ROOT / "runtime/EXP-0034/appearance_manifest.json"
EXPECTED_SHA = "996ecdb638b624d69c54a70ff0e44027c95a3d2dd04a78efa00a69856af3ec90"
QUEUE = Path("/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue/queue.sqlite3")
EXPECTED_COUNTS = [5, 5, 5, 4, 4, 4]


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    # Guard semantic reads; sha() deliberately has separate byte-only access.
    if path.name in {"appearance_results.json", "result.json", "summary.json",
                     "raw_response.txt", "visual-audit.local.json"}:
        raise ValueError("Historical answer content is isolated")
    return json.loads(path.read_text())


def write_fresh(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def queue_snapshot():
    # Direct read-only connection: never instantiate Queue or migrate schema.
    with sqlite3.connect(f"file:{QUEUE}?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        rows = {table: [list(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY 1")]
                for table in ("jobs", "attempts")}
        columns = {table: [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
                   for table in rows}
    return {"captured_utc": now(), "database": str(QUEUE), "columns": columns, "rows": rows}


def snapshot():
    if AUDIT.exists() or REVIEW.exists():
        raise FileExistsError("Fresh input-audit and input-review directories required")
    paths = set()
    # Historical media/runtime/input receipts and camera settings are immutable;
    # active mvp/orchestration source edits belong to the other worker.
    for dirname in ("runtime/EXP-0034", "outputs/exp0034", "outputs/mvp0001"):
        paths.update(p for p in (ROOT / dirname).rglob("*") if p.is_file())
    inherited = ROOT / "runtime/EXP-0037/protected-files.json"
    if inherited.is_file():
        for name in read_json(inherited)["files"]:
            if name.startswith(("outputs/", "data/", "configs/", "records/")):
                paths.add(ROOT / name)
    paths.update(ROOT / f"configs/mvp0001_{name}.json" for name in ("cameras", "settings", "sources"))
    files = {}
    for path in sorted(paths):
        if not path.is_file():
            raise FileNotFoundError(path)
        files[str(path.relative_to(ROOT))] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    write_fresh(AUDIT / "protected-before.json", {
        "captured_utc": now(), "files": files,
        "answer_access": "opaque byte hashing only; historical response content not parsed",
        "active_source_files_excluded": ["mvp/", "orchestration/"],
        "inherited_snapshot": str(inherited.relative_to(ROOT)),
    })
    write_fresh(AUDIT / "queue-before.json", queue_snapshot())
    print(json.dumps({"protected_files": len(files), "snapshot": str(AUDIT.relative_to(ROOT))}))


def audit(receipt_name="input-audit.json"):
    from mvp.exp0034_appearance import bind_inputs, load_manifest, verify_native_crops
    started = time.perf_counter()
    if sha(MANIFEST) != EXPECTED_SHA:
        raise ValueError("EXP34 exact manifest SHA mismatch")
    manifest = load_manifest()
    counts = [len(pair["before_images"]) + len(pair["after_images"]) for pair in manifest["pairs"]]
    if counts != EXPECTED_COUNTS:
        raise ValueError("Frozen six-pair image-slot counts changed")
    bound = bind_inputs()
    native = verify_native_crops()
    if native["native_crops_checked"] != 27 or len(bound["appearance_crops"]) != 27:
        raise ValueError("27 native image slots and 27 crop files required")
    result = {"checked_utc": now(), "experiment": "EXP-0038", "cpu_only": True,
              "manifest_sha256": sha(MANIFEST), "expected_manifest_sha256": EXPECTED_SHA,
              "pair_counts": counts, "pairs": 6, "image_slots": sum(counts),
              "bind_inputs": bound, "verify_native_crops": native,
              "elapsed_seconds": time.perf_counter() - started,
              "audit_implementation": {name: sha(ROOT / name) for name in
                                       ("scripts/exp0038_input_audit.py", "mvp/exp0034_appearance.py",
                                        "sceneguard/appearance_support.py")},
              "cpu_environment": {"python": sys.version, "executable": sys.executable,
                                  "packages": {name: importlib.metadata.version(name)
                                               for name in ("av", "numpy", "Pillow")}},
              "historical_answers_read": False, "new_boxes_or_crops": False,
              "historical_execution_authorization_reused": False,
              "identity_status": "uncertain; provenance verification is not identity truth",
              "source_binding_checks": ["source and observation file SHA256", "one actual observed detection",
                                        "raw ID, cache index, normalized bbox", "exact native PTS/time base",
                                        "exact decoded index and RGB bytes; no preprocessor resize"]}
    write_fresh(AUDIT / receipt_name, result)
    print(json.dumps({key: result[key] for key in ("manifest_sha256", "pair_counts", "image_slots", "elapsed_seconds")}))


def review():
    import numpy as np
    from PIL import Image, ImageDraw
    from mvp.exp0034_appearance import load_crop, load_manifest
    if not (AUDIT / "input-audit.json").is_file():
        raise ValueError("Complete native audit before review preparation")
    if REVIEW.exists():
        raise FileExistsError("Fresh review output required")
    REVIEW.mkdir(parents=True)
    manifest = load_manifest()
    draft_path = ROOT / "runtime/EXP-0034/pair-review-freeze.local.json"
    draft = read_json(draft_path)
    if draft["model_results_seen"] is not False:
        raise ValueError("Expected historical draft frozen before model results")
    draft_pairs = {pair["pair_id"]: pair for pair in draft["pairs"]}
    registry_path = ROOT / "runtime/EXP-0034/delivery/artifacts.json"
    registry = read_json(registry_path)["artifacts"]
    # This is the pre-existing evidence registry, not a new registration.
    inventory = []
    sections = []
    for number, pair in enumerate(manifest["pairs"], 1):
        images = pair["before_images"] + pair["after_images"]
        pairdir = BASELINE / f"p{number:06d}"
        meta = read_json(pairdir / "processor_metadata.json")
        if meta["frame_groups"] != [len(pair["before_images"]), len(pair["after_images"])]:
            raise ValueError("Stored processor A/B group mismatch")
        if meta["image_budget"] != {"min_pixels": 65536, "max_pixels": 262144}:
            raise ValueError("Original processor image budget changed")
        if meta["input_shapes"] != [list(load_crop(im).shape) for im in images]:
            raise ValueError("Original native shape / processor metadata mismatch")
        board = Image.new("RGB", (260 * len(images), 1060), "#101722")
        draw = ImageDraw.Draw(board)
        draw.text((10, 8), f"P{number}: original native crops / stored actual 2B processor input", fill="white")
        draw.text((10, 28), "LOCAL ONLY - identity uncertain; historical visual draft is not user-confirmed truth", fill="#ffd880")
        slots = []
        for index, im in enumerate(images):
            proc_path = pairdir / f"processor_rgb_{index:02d}.npy"
            proc = np.load(proc_path, allow_pickle=False)
            if (proc.dtype != np.uint8 or list(proc.shape) != meta["processor_shapes"][index]
                    or hashlib.sha256(proc.tobytes()).hexdigest() != meta["processor_rgb_sha256"][index]):
                raise ValueError("Stored actual processor RGB mismatch")
            side = "A" if index < len(pair["before_images"]) else "B"
            for row, (array, label) in enumerate(((load_crop(im), "native"), (proc, "actual 2B processor"))):
                y = 55 + row * 495
                draw.text((index * 260 + 5, y), f"{side} slot {index + 1}: {label}\nPTS {im['pts']:.6f}; {array.shape[1]}x{array.shape[0]}", fill="white")
                pic = Image.fromarray(array)
                pic.thumbnail((250, 430))
                board.paste(pic, (index * 260 + (260 - pic.width) // 2, y + 48))
            slots.append({"slot": index + 1, "side": side, "native": im,
                          "processor_path": str(proc_path.relative_to(ROOT)), "processor_file_sha256": sha(proc_path),
                          "processor_rgb_sha256": meta["processor_rgb_sha256"][index],
                          "processor_shape": list(proc.shape)})
        name = f"p{number}-native-actual2b.jpg"
        board.save(REVIEW / name, quality=92)
        artifact_id = f"exp0034-p{number}-pair"
        existing = registry[artifact_id]
        source_panel = ROOT / existing["path"]
        if not source_panel.is_file():
            raise FileNotFoundError(source_panel)
        historical = draft_pairs[pair["pair_id"]]
        processor_id = f"exp0034-p{number}-processor"
        entry = {"pair": number, "pair_id": pair["pair_id"], "image_count": len(images),
                 "before_count": len(pair["before_images"]), "after_count": len(pair["after_images"]),
                 "source_panel": {"artifact_id": artifact_id, "path": str(source_panel.relative_to(ROOT)),
                                  "sha256": sha(source_panel), "url": f"http://127.0.0.1:8765/artifacts/{artifact_id}"},
                 "existing_processor_panel": registry.get(processor_id),
                 "local_comparison_panel": name, "local_comparison_sha256": sha(REVIEW / name),
                 "processor_metadata_path": str((pairdir / "processor_metadata.json").relative_to(ROOT)),
                 "processor_metadata_sha256": sha(pairdir / "processor_metadata.json"),
                 "baseline_input_tokens": meta["input_tokens"], "baseline_grid": meta["image_grid_thw"],
                 "historical_visual_draft": historical, "identity_status": "uncertain; not new user labels", "slots": slots}
        inventory.append(entry)
        note = html.escape(historical["observation"])
        sections.append(f'<section><h2>P{number} - {len(images)} image slots</h2>'
                        f'<p>Identity uncertain. Historical pre-model visual draft, not user-confirmed truth: {note}</p>'
                        f'<a href="{entry["source_panel"]["url"]}">Existing registered source panel</a>'
                        f'<p><img src="{name}" alt="P{number} native and actual 2B input comparison"></p></section>')
    write_fresh(REVIEW / "inventory.local.json", {
        "created_utc": now(), "local_only": True, "cpu_only": True, "pairs": inventory,
        "historical_draft_path": str(draft_path.relative_to(ROOT)), "historical_draft_sha256": sha(draft_path),
        "historical_draft_is_user_ground_truth": False,
        "historical_user_observations": [
            {"path": name, "sha256": sha(ROOT / name), "scope": scope}
            for name, scope in (
                ("docs/experiments/EXP-0028-user-tracking-review.md",
                 "User qualitative observations of ID discontinuity/duplicate boxes; 007 approach near 56.7s and climbing from about 66s. Not pairwise identity GT."),
                ("docs/experiments/EXP-0024-user-pose-review.md",
                 "User qualitative pose/missing-person review at 030 84/90/94s. Not pairwise identity or precise bbox/joint GT."))],
        "historical_model_answers_read": False, "new_labels_boxes_crops": False,
        "registry_path": str(registry_path.relative_to(ROOT)), "registry_sha256": sha(registry_path),
        "registration_performed": False, "actual_8b_processor_inputs": "pending coordinator execution",
        "image_transform": "display-only thumbnails of stored arrays; no model inputs rewritten",
    })
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>EXP38 local input review</title>'
            '<style>body{background:#101722;color:#eee;font:16px sans-serif;margin:24px}a{color:#9cf}'
            'img{max-width:100%;height:auto}section{border-top:1px solid #567;margin-top:30px}</style>'
            '<h1>EXP38 local input review - identities uncertain</h1>'
            '<p>Six frozen pairs / 27 native slots. No inference, new crops or labels. '
            'Native crops and stored actual 2B processor inputs are shown for input inspection. '
            'Historical model answers remain isolated; actual 8B processor inputs are pending. '
            'Original evidence links reuse the existing local web registration.</p>' + ''.join(sections) + '</html>')
    (REVIEW / "index.html").write_text(page)
    print(json.dumps({"inventory": str((REVIEW / "inventory.local.json").relative_to(ROOT)), "panels": len(inventory)}))


def verify_preservation(receipt_name="preservation-after.json"):
    before = read_json(AUDIT / "protected-before.json")
    changed = [name for name, info in before["files"].items()
               if not (ROOT / name).is_file() or sha(ROOT / name) != info["sha256"]]
    queue_before = read_json(AUDIT / "queue-before.json")
    current = queue_snapshot()
    queue_changed, added = {}, {}
    for table, rows in queue_before["rows"].items():
        old = {row[0]: row for row in rows}
        new = {row[0]: row for row in current["rows"][table]}
        queue_changed[table] = [key for key, row in old.items() if new.get(key) != row]
        added[table] = [key for key in new if key not in old]
    result = {"checked_utc": now(), "protected_files": len(before["files"]), "changed_files": changed,
              "changed_historical_queue_rows": queue_changed, "new_queue_row_ids": added,
              "queue_before_counts": {k: len(v) for k, v in queue_before["rows"].items()},
              "queue_current_counts": {k: len(v) for k, v in current["rows"].items()},
              "historical_answers_read": False, "worker_gpu_or_inference_calls": 0}
    write_fresh(AUDIT / receipt_name, result)
    print(json.dumps(result))
    if changed or any(queue_changed.values()):
        raise ValueError("Protected historical bytes/rows changed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "audit", "review", "verify-preservation"))
    parser.add_argument("--receipt-name", help="Fresh JSON receipt basename for repeat audit/preservation checks")
    args = parser.parse_args()
    if args.receipt_name:
        if (Path(args.receipt_name).name != args.receipt_name or not args.receipt_name.endswith(".json")
                or args.action not in {"audit", "verify-preservation"}):
            parser.error("--receipt-name requires a JSON basename and audit/preservation action")
        {"audit": audit, "verify-preservation": verify_preservation}[args.action](args.receipt_name)
    else:
        {"snapshot": snapshot, "audit": audit, "review": review,
         "verify-preservation": verify_preservation}[args.action]()
