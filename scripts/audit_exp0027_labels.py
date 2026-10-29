#!/usr/bin/env python3
"""Read-only CPU byte/provenance audit; creates local pending review inventories.

No image library, image decoding, model, network, relabel, or dataset writes.
The pinned freeze authenticates the preparation, not annotation semantics.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, localcontext
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import zipfile

ARCHIVE_SHA256 = "92ee33df46b231e70a26d9901f361a67845c882ce0afd2f0c97e55dca7622549"
FREEZE_SHA256 = "26bee37c0508d86d0f08b3bbd1be348cf8916c54aa1b094710e7b96be50f2606"
CLASSES = ["fence", "people-jump-fence", "person-climbing-fence"]
SPLITS = ("train", "valid", "test")
REVIEW_SCHEMA = {
    "representation": ["one_person", "multiple_people", "scene", "unknown"],
    "extent": ["whole_body", "visible_body_part", "fence_included", "unclear"],
    "unlabelled_people": ["yes", "no", "unknown"],
    "c6_gate_similarity": ["yes", "no", "unknown"],
    "c6_distant_similarity": ["yes", "no", "unknown"],
    "c6_occlusion_similarity": ["yes", "no", "unknown"],
    "converted_bbox_fit": ["suitable", "unsuitable", "unknown"],
}
PENDING_VALUES = {key: "unclear" if key == "extent" else "unknown" for key in REVIEW_SCHEMA}
PENDING_VALUES.update(reviewer="", reviewdate="", note="", review_pending=True)


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def safe_child(root: Path, name: str) -> Path:
    parts = PurePosixPath(name).parts
    require(bool(parts) and not PurePosixPath(name).is_absolute() and
            all(part not in (".", "..") for part in parts) and "\\" not in name,
            "Unsafe inventory path")
    path = root.joinpath(*parts)
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Symlink input forbidden")
    require(path.resolve().is_relative_to(root.resolve()), "Input outside root")
    return path


def tree_hashes(root: Path) -> dict:
    require(root.is_dir() and not root.is_symlink(), "Missing/symlink dataset")
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "Symlink dataset member forbidden")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = file_sha(path)
    return result


def verify_freeze(repo: Path, dataset: Path, freeze: Path, expected_sha: str) -> dict:
    require(file_sha(freeze) == expected_sha, "Dataset freeze SHA256 mismatch")
    frozen = json.loads(freeze.read_text())
    require(isinstance(frozen, dict) and bool(frozen), "Invalid dataset freeze")
    prefix = dataset.relative_to(repo).as_posix() + "/"
    require(all(key.startswith(prefix) for key in frozen), "Freeze outside dataset scope")
    expected = {key[len(prefix):]: value for key, value in frozen.items()}
    current = tree_hashes(dataset)
    require(current == expected, "Dataset file set/hash differs from EXP-0026 freeze")
    return current


def conversion(raw: str) -> dict:
    """Independent scalar check of the documented bbox/min-max polygon mapping."""
    tokens = raw.split()
    require(tokens and tokens[0] in ("0", "1", "2"), "Invalid original class")
    count = len(tokens) - 1
    require(count == 4 or (count >= 6 and count % 2 == 0), "Invalid coordinate arity")
    values = [Decimal(token) for token in tokens[1:]]
    require(all(v.is_finite() and 0 <= v <= 1 for v in values), "Invalid coordinate range")
    with localcontext() as context:
        context.prec = 80
        if count == 4:
            x, y, w, h = values
            require(w > 0 and h > 0 and min(x-w/2, y-h/2) >= 0 and
                    max(x+w/2, y+h/2) <= 1, "Invalid bbox extent")
            output = tokens[1:]
            kind = "bbox"
        else:
            xs, ys = values[::2], values[1::2]
            left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
            require(left < right and top < bottom, "Invalid polygon extent")
            output = [format(v, "f").rstrip("0").rstrip(".") if v else "0"
                      for v in ((left+right)/2, (top+bottom)/2, right-left, bottom-top)]
            kind = "polygon"
    class_id = int(tokens[0])
    converted = "0 " + " ".join(output) if class_id else None
    return {"source_class_id": class_id, "source_class_name": CLASSES[class_id],
            "source_type": kind, "raw": raw, "raw_sha256": sha(raw.encode()),
            "output": converted, "output_row_sha256": sha(converted.encode()) if converted else None}


def row_key(row: dict) -> tuple:
    return row["source_member"], row["source_row_index"]


def priority_inventory(rows: list[dict], panels: list[dict]) -> dict:
    keys = [row_key(row) for row in rows]
    require(len(keys) == len(set(keys)), "Duplicate annotation row")
    by_label = {}
    for panel in panels:
        require(panel["source_label"] not in by_label, "Duplicate panel for source image")
        by_label[panel["source_label"]] = panel["panel_id"]
    people = {row_key(r) for r in rows if r["source_class_id"] == 1}
    polygons = {row_key(r) for r in rows if r["source_class_id"] != 0 and r["source_type"] == "polygon"}
    require(all(key[0] in by_label for key in people | polygons), "Priority row lacks existing panel")
    def sizes(selection):
        images = {key[0] for key in selection}
        return {"rows": len(selection), "unique_images": len(images),
                "unique_panels": len({by_label[label] for label in images})}
    people_images, polygon_images = {k[0] for k in people}, {k[0] for k in polygons}
    ordered = sorted(people | polygons, key=lambda k: (0 if k in people else 1, k))
    return {"people_jump_fence": sizes(people), "person_polygon": sizes(polygons),
            "overlap": {"rows": len(people & polygons),
                        "unique_images": len(people_images & polygon_images),
                        "unique_panels": len({by_label[k] for k in people_images} &
                                             {by_label[k] for k in polygon_images})},
            "deduplicated": sizes(people | polygons),
            "rows": [{"source_member": label, "source_row_index": index,
                      "panel_id": by_label[label],
                      "reasons": (["people_jump_fence"] if (label,index) in people else []) +
                                 (["person_polygon"] if (label,index) in polygons else [])}
                     for label,index in ordered],
            "panel_ids": list(dict.fromkeys(by_label[label] for label,index in ordered))}


def validate_pending_review(record: dict) -> None:
    for key, choices in REVIEW_SCHEMA.items():
        require(record.get(key) in choices, "Invalid review enum: " + key)
    require(record.get("review_pending") is True, "Human review is still pending")
    require(all(record.get(key) == value for key,value in PENDING_VALUES.items()),
            "Preparation cannot invent human semantic reviews")


def audit_inputs(repo: Path, dataset: Path, archive: Path, freeze: Path,
                 expected_archive_sha: str, expected_freeze_sha: str) -> dict:
    before = verify_freeze(repo, dataset, freeze, expected_freeze_sha)
    require(not archive.is_symlink(), "Symlink archive forbidden")
    require(file_sha(archive) == expected_archive_sha, "Original ZIP SHA256 mismatch")
    summary = json.loads((dataset / "summary.json").read_text())
    require(summary["archive_sha256"] == expected_archive_sha, "Preparation archive mismatch")
    for key in ("D0_passed", "training_approved", "usable_for_training", "semantic_person_approval"):
        require(summary.get(key) is False, "Unexpected preparation state: " + key)
    require(summary.get("status") == "review_pending" and summary.get("human_review") == "pending",
            "Unexpected human review state")
    require(summary.get("source_classes") == CLASSES, "Class mapping differs")
    manifest = json.loads((dataset / "manifest.json").read_text())
    provenance = [json.loads(line) for line in (dataset / "provenance.jsonl").read_text().splitlines()]
    source_members = manifest["source_members"]
    require(len({r["name"] for r in source_members}) == len(source_members), "Duplicate source manifest member")
    expected_members = {r["name"]: r for r in source_members}
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist()
        indices = defaultdict(list)
        for index,info in enumerate(infos):
            if info.is_dir():
                continue
            require(info.filename in expected_members, "Uninventoried ZIP member")
            indices[info.filename].append(index)
            member = expected_members[info.filename]
            require(sha(zipped.read(info)) == member["sha256"], "Original ZIP member mismatch")
        require(set(indices) == set(expected_members), "ZIP source inventory mismatch")
        for name,member in expected_members.items():
            require(indices[name] == member["archive_indices"], "ZIP member index mismatch")
            require(file_sha(safe_child(dataset / "source", name)) == member["sha256"], "Source member hash mismatch")
    require({p[len("source/"):] for p in before if p.startswith("source/")} == set(expected_members),
            "Source tree inventory mismatch")
    samples = manifest["samples"]
    require(len({s["image"] for s in samples}) == len(samples) and
            len({s["source_label"] for s in samples}) == len(samples), "Duplicate sample")
    rebuilt, counts, split_images = [], Counter(), Counter()
    by_label = {}
    for sample in samples:
        image, label = sample["image"], sample["source_label"]
        ip, lp = PurePosixPath(image), PurePosixPath(label)
        require(len(ip.parts) == 3 and len(lp.parts) == 3 and ip.parts[0] in SPLITS and
                ip.parts[0] == lp.parts[0] and ip.parts[1] == "images" and lp.parts[1] == "labels" and
                ip.stem == lp.stem, "Image/label matching failure")
        split_images[ip.parts[0]] += 1
        require(file_sha(safe_child(dataset,image)) == sample["image_sha256"] ==
                expected_members[image]["sha256"], "Prepared/source image mismatch")
        require(file_sha(safe_child(dataset / "source",label)) == sample["source_label_sha256"] ==
                expected_members[label]["sha256"], "Source label mismatch")
        rows, output_rows = [], []
        for index,raw in enumerate(safe_child(dataset / "source",label).read_text(encoding="utf-8-sig").splitlines(),1):
            if not raw.strip():
                continue
            row = conversion(raw)
            row.update(source_member=label, source_member_index=expected_members[label]["archive_indices"][0],
                       source_row_index=index, output_row_index=len(output_rows)+1 if row["output"] else None)
            if row["output"]:
                output_rows.append(row["output"])
                counts["person_" + row["source_type"]] += 1
                counts[ip.parts[0] + "_person_rows"] += 1
            else:
                counts["fence_removed"] += 1
            counts["source_rows"] += 1
            rows.append(row)
        expected_output = (("\n".join(output_rows)+"\n") if output_rows else "").encode()
        require(safe_child(dataset,label).read_bytes() == expected_output and
                sample["output_label_sha256"] == sha(expected_output), "Converted label mismatch")
        require(sample["person_rows"] == len(output_rows), "Sample row count mismatch")
        for row in rows:
            row["output_label_sha256"] = sha(expected_output)
        rebuilt.extend(rows)
        by_label[label] = {"sample":sample, "rows":rows}
    require(rebuilt == provenance, "Provenance does not match original/converted rows")
    require({name for name in expected_members if "/images/" in name} == {s["image"] for s in samples} and
            {name for name in expected_members if "/labels/" in name} == set(by_label), "Source sample coverage mismatch")
    for split in SPLITS:
        counts[split + "_images"] = split_images[split]
    counts["person_rows"] = counts["person_bbox"] + counts["person_polygon"]
    require(dict(counts) == summary["counts"], "Preparation counts mismatch")
    require(summary["images"] == summary["labels"] == len(samples) and summary["images_excluded"] == 0,
            "Preparation image count mismatch")
    # Reconstruct the documented representative + all priority-row selection using names only.
    representatives = {}
    for sample in sorted(samples, key=lambda s:(PurePosixPath(s["image"]).parts[0],PurePosixPath(s["image"]).stem)):
        representatives.setdefault(PurePosixPath(sample["image"]).stem.split(".rf.")[0], sample["source_label"])
    selected = set(representatives.values())
    selected.update(r["source_member"] for r in provenance if r["source_class_id"] == 1 or
                    (r["source_class_id"] != 0 and r["source_type"] == "polygon"))
    overlays = manifest["review_overlays"]
    require({p["source_label"] for p in overlays} == selected, "Review selection mismatch")
    require(len(overlays) == len(selected) == summary["review_overlays"], "Duplicate/missing review panels")
    require(summary["filename_base_groups"] == len(representatives), "Filename candidate group count mismatch")
    panels = []
    for index,panel in enumerate(sorted(overlays,key=lambda p:p["overlay"]),1):
        source = by_label[panel["source_label"]]
        image = source["sample"]["image"]
        parts = PurePosixPath(image).parts
        require(panel["source_image"] == image and panel["overlay"] == f"review/{parts[0]}/{PurePosixPath(image).stem}.png" and
                panel["filename_base"] == PurePosixPath(image).stem.split(".rf.")[0], "Panel/image/label matching failure")
        require(file_sha(safe_child(dataset,panel["overlay"])) == panel["sha256"], "Review PNG mismatch")
        panels.append({**panel, "panel_id": f"panel_{index:03d}", "split":parts[0],
                       "source_image_path":"source/"+image, "prepared_image_path":image,
                       "source_label_path":"source/"+panel["source_label"],
                       "prepared_label_path":panel["source_label"], "annotation_rows":source["rows"],
                       **PENDING_VALUES})
    require({p for p in before if p.startswith("review/")} == {p["overlay"] for p in panels}, "Uninventoried panel")
    priority = priority_inventory(provenance, panels)
    after = verify_freeze(repo,dataset,freeze,expected_freeze_sha)
    require(after == before and file_sha(archive) == expected_archive_sha, "Input mutated during audit")
    return {"dataset":str(dataset), "archive":str(archive), "freeze":str(freeze),
            "freeze_sha256":expected_freeze_sha, "archive_sha256":expected_archive_sha,
            "dataset_file_hashes_before":before, "dataset_file_hashes_after":after,
            "all_input_bytes_preserved":True, "counts":dict(counts), "source_members":len(source_members),
            "archive_file_entries":sum(len(r["archive_indices"]) for r in source_members),
            "samples":samples, "panels":panels, "rows":provenance, "priority":priority,
            "filename_candidate_groups":len(representatives), "independent_groups_proven":False,
            "D0_passed":False, "human_review":"pending", "image_content_reviewed":False,
            "annotation_opinion":"format/provenance verified; semantics pending",
            "test_split_used_for_model_evaluation":False, "GPU_jobs":0}


def json_bytes(value) -> bytes:
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()


def write_new(root: Path, name: str, value: bytes) -> None:
    with (root / name).open("xb") as stream:
        stream.write(value)


def csv_bytes(records: list[dict]) -> bytes:
    buffer = io.StringIO(newline="")
    fields = list(records[0]) if records else []
    writer = csv.DictWriter(buffer,fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue().encode()


def write_audit(repo: Path, dataset: Path, archive: Path, freeze: Path, output: Path,
                expected_archive_sha: str = ARCHIVE_SHA256, expected_freeze_sha: str = FREEZE_SHA256) -> dict:
    repo, dataset, archive, freeze = (p.absolute() for p in (repo,dataset,archive,freeze))
    output = output.absolute()
    require(not any(p.is_symlink() for p in (output,*output.parents)), "Symlink output forbidden")
    output = output.resolve()
    require(not output.is_relative_to(dataset.resolve()) and not dataset.resolve().is_relative_to(output) and
            not archive.resolve().is_relative_to(output) and not freeze.resolve().is_relative_to(output),
            "Output overlaps protected inputs")
    if output.exists():
        raise FileExistsError("Audit output exists; never overwrite pending review work")
    result = audit_inputs(repo,dataset,archive,freeze,expected_archive_sha,expected_freeze_sha)
    panels = result["panels"]
    panel_lookup = {p["source_label"]:p for p in panels}
    priority_keys = {(r["source_member"],r["source_row_index"]) for r in result["priority"]["rows"]}
    panel_reviews, row_reviews = [], []
    for panel in panels:
        record = {"panel_id":panel["panel_id"], "overlay":panel["overlay"], "source_image":panel["source_image_path"],
                  "source_label":panel["source_label"], **PENDING_VALUES}
        validate_pending_review(record)
        panel_reviews.append(record)
    for index,row in enumerate(result["rows"],1):
        if row["source_class_id"] == 0:
            continue
        panel = panel_lookup.get(row["source_member"],{})
        record = {"row_id":f"annotation_{index:04d}", "source_label":row["source_member"],
                  "source_row_index":row["source_row_index"], "output_row_index":row["output_row_index"],
                  "source_class":row["source_class_name"], "source_type":row["source_type"],
                  "panel_id":panel.get("panel_id",""), "priority":row_key(row) in priority_keys, **PENDING_VALUES}
        validate_pending_review(record)
        row_reviews.append(record)
    public_counts = {"dataset_files_verified":len(result["dataset_file_hashes_before"]),
                     "source_members_verified":result["source_members"], "source_zip_file_entries_verified":result["archive_file_entries"],
                     "images":len(result["samples"]), "counts":result["counts"],
                     "panels":len(panels), "panel_review_status_counts":{"review_pending":len(panels),"reviewed":0},
                     "row_review_status_counts":{"review_pending":len(row_reviews),"reviewed":0},
                     "priority":{k:v for k,v in result["priority"].items() if k not in ("rows","panel_ids")},
                     "filename_candidate_groups":result["filename_candidate_groups"], "independent_groups_proven":False,
                     "all_input_bytes_preserved":True, "D0_passed":False, "image_content_reviewed":False,
                     "annotation_opinion":result["annotation_opinion"], "GPU_jobs":0,
                     "model_test_evaluation_performed":False}
    output.mkdir(parents=True,exist_ok=False)
    write_new(output,"manifest.local.json",json_bytes(result))
    write_new(output,"counts.local.json",json_bytes(public_counts))
    write_new(output,"review-schema.local.json",json_bytes({"fields":REVIEW_SCHEMA, "pending_values":PENDING_VALUES,
              "unit_note":"Panel fields are whole-panel notes; row records independently describe each source person annotation; missing panel_id means no existing selected panel, never create new media.",
              "reviewdate_format":"YYYY-MM-DD when a human completes review; blank during preparation"}))
    write_new(output,"panel-review-template.local.json",json_bytes(panel_reviews))
    write_new(output,"panel-review-template.local.csv",csv_bytes(panel_reviews))
    write_new(output,"row-review-template.local.json",json_bytes(row_reviews))
    write_new(output,"row-review-template.local.csv",csv_bytes(row_reviews))
    write_new(output,"priority.local.json",json_bytes(result["priority"]))
    def link(label,path):
        return f"[{label}]({quote(os.path.relpath(dataset / path,output),safe='/')})"
    lines = ["# EXP-0027 local pending annotation review index", "",
             "LOCAL ONLY. Image content UNKNOWN; all panels review_pending. No human review or D0 pass.",
             "Existing panels only; links open existing files. No images decoded/copied/modified by this audit.",
             "test17 is unused by training; metadata review is not model test evaluation.", "",
             "## Deduplicated priority panels", ""]
    by_id = {p["panel_id"]:p for p in panels}
    for panel_id in result["priority"]["panel_ids"]:
        panel = by_id[panel_id]
        priority_rows = [r for r in result["priority"]["rows"] if r["panel_id"] == panel_id]
        reasons = "; ".join(f"source row {r['source_row_index']}: {', '.join(r['reasons'])}" for r in priority_rows)
        lines.append(f"- {panel_id}: {link('existing comparison',panel['overlay'])}; {link('raw source image',panel['source_image_path'])}; {reasons}")
    lines.extend(["", "## All existing panels", "", "| ID | Split | Existing comparison | Raw source image | Raw label | Converted label | Status |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for panel in panels:
        lines.append(f"| {panel['panel_id']} | {panel['split']} | {link('comparison',panel['overlay'])} | {link('source',panel['source_image_path'])} | {link('raw rows',panel['source_label_path'])} | {link('bbox rows',panel['prepared_label_path'])} | review_pending |")
    write_new(output,"index.local.md",("\n".join(lines)+"\n").encode())
    # Re-read every input after output construction; write preservation evidence last.
    after = verify_freeze(repo,dataset,freeze,expected_freeze_sha)
    require(after == result["dataset_file_hashes_before"] and file_sha(archive) == expected_archive_sha,
            "Input mutated during output construction")
    preservation = {"archive_sha256_before":expected_archive_sha,"archive_sha256_after":file_sha(archive),
                    "freeze_sha256_before":expected_freeze_sha,"freeze_sha256_after":file_sha(freeze),
                    "dataset_file_hashes_before":result["dataset_file_hashes_before"],"dataset_file_hashes_after":after,
                    "all_input_bytes_preserved":True,
                    "output_file_hashes":{p.name:file_sha(p) for p in sorted(output.iterdir())}}
    write_new(output,"preservation.local.json",json_bytes(preservation))
    return public_counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--dataset",type=Path,default=Path("data/climbing_fence/person_bbox_draft_v1"))
    parser.add_argument("--freeze",type=Path,default=Path("runtime/BATCH-0007/training/dataset-freeze.local.json"))
    parser.add_argument("--output",type=Path,default=Path("runtime/EXP-0027/label-audit"))
    args = parser.parse_args()
    repo = args.repo.absolute()
    rooted = lambda p: p if p.is_absolute() else repo / p
    print(json.dumps(write_audit(repo,rooted(args.dataset),rooted(args.archive),rooted(args.freeze),rooted(args.output)),indent=2))


if __name__ == "__main__":
    main()
