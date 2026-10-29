#!/usr/bin/env python3
"""CPU-only, non-overwriting preparation of an explicitly unreviewed bbox draft."""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

from PIL import Image, ImageDraw
import yaml


ARCHIVE_SHA256 = "92ee33df46b231e70a26d9901f361a67845c882ce0afd2f0c97e55dca7622549"
CLASSES = ["fence", "people-jump-fence", "person-climbing-fence"]
SPLITS = ("train", "valid", "test")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def safe_members(archive: zipfile.ZipFile) -> tuple[dict, dict]:
    """Read by ZipInfo (never last-name-wins), validating before any extraction."""
    members, indices = {}, {}
    infos = archive.infolist()
    if len(infos) > 4096 or sum(i.file_size for i in infos) > 256 * 1024**2:
        raise ValueError("ZIP resource limit exceeded")
    directories = set()
    for index, info in enumerate(infos):
        name = info.filename
        trimmed = name[:-1] if info.is_dir() else name
        path = PurePosixPath(trimmed)
        if (not trimmed or "\\" in name or ":" in name or "\x00" in name
                or path.is_absolute() or any(p in ("", ".", "..") for p in trimmed.split("/"))):
            raise ValueError("Unsafe ZIP path")
        kind = stat.S_IFMT(info.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or (kind and (kind == stat.S_IFDIR) != info.is_dir()):
            raise ValueError("ZIP symlink/special member forbidden")
        if info.is_dir():
            if trimmed in members or trimmed in directories:
                raise ValueError("Duplicate/conflicting ZIP directory")
            directories.add(trimmed)
            continue
        if info.file_size > 32 * 1024**2 or info.flag_bits & 1:
            raise ValueError("ZIP oversized/encrypted member forbidden")
        content = archive.read(info)  # also checks CRC
        if name in members:
            if name != "data.yaml" or content != members[name] or len(indices[name]) >= 3:
                raise ValueError("Duplicate/conflicting ZIP member")
        else:
            members[name] = content
            indices[name] = []
        indices[name].append(index)
    for name in members:
        if name in directories or any(str(p) in members for p in PurePosixPath(name).parents if str(p) != "."):
            raise ValueError("ZIP file/directory conflict")
    for name in directories:
        if any(str(p) in members for p in PurePosixPath(name).parents if str(p) != "."):
            raise ValueError("ZIP file/directory conflict")
    return members, indices


def decimal_text(value: Decimal) -> str:
    return format(value, "f").rstrip("0").rstrip(".") if value else "0"


def convert_row(raw: str) -> dict:
    """Validate each annotation independently, including annotations being dropped."""
    tokens = raw.split()
    if not tokens or tokens[0] not in ("0", "1", "2"):
        raise ValueError("Unknown/non-integer class id")
    count = len(tokens) - 1
    if count != 4 and (count < 6 or count % 2):
        raise ValueError("Expected bbox xywh or polygon with at least three xy pairs")
    try:
        values = [Decimal(x) for x in tokens[1:]]
    except InvalidOperation as exc:
        raise ValueError("Invalid numeric coordinate") from exc
    if any(not x.is_finite() or x < 0 or x > 1 for x in values):
        raise ValueError("Nonfinite/out-of-bounds coordinate")
    with localcontext() as context:
        context.prec = 80
        if count == 4:
            x, y, w, h = values
            if w <= 0 or h <= 0 or min(x - w / 2, y - h / 2) < 0 or max(x + w / 2, y + h / 2) > 1:
                raise ValueError("Degenerate/out-of-bounds bbox edges")
            output_tokens = tokens[1:]  # preserve original xywh tokens exactly
            source_type = "bbox"
        else:
            xs, ys = values[::2], values[1::2]
            left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
            if left == right or top == bottom:
                raise ValueError("Degenerate polygon extent")
            output_tokens = [decimal_text(v) for v in ((left + right) / 2, (top + bottom) / 2, right - left, bottom - top)]
            source_type = "polygon"
    class_id = int(tokens[0])
    output = "0 " + " ".join(output_tokens) if class_id else None
    return {"source_class_id": class_id, "source_class_name": CLASSES[class_id],
            "source_type": source_type, "raw": raw, "raw_sha256": sha(raw.encode()),
            "output": output, "output_row_sha256": sha(output.encode()) if output else None}


def write_new(root: Path, name: str, content: bytes) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)


def draw_review(image_bytes: bytes, rows: list[dict]) -> bytes:
    """Local raw-annotation / tentative-box comparison, never a semantic verdict."""
    with Image.open(io.BytesIO(image_bytes)) as opened:
        image = opened.convert("RGB")
    width, height = image.size
    before, after = image.copy(), image.copy()
    for row in rows:
        values = [float(x) for x in row["raw"].split()[1:]]
        color = (170, 170, 170) if row["source_class_id"] == 0 else ((255, 160, 30) if row["source_class_id"] == 1 else (30, 245, 90))
        draw = ImageDraw.Draw(before)
        if row["source_type"] == "polygon":
            points = [(x * width, y * height) for x, y in zip(values[::2], values[1::2])]
            draw.line(points + points[:1], fill=color, width=2)
            origin = points[0]
        else:
            x, y, w, h = values
            origin = ((x - w / 2) * width, (y - h / 2) * height)
            draw.rectangle((*origin, (x + w / 2) * width, (y + h / 2) * height), outline=color, width=2)
        draw.text(origin, f"r{row['source_row_index']} c{row['source_class_id']}", fill=color)
        if row["output"]:
            x, y, w, h = map(float, row["output"].split()[1:])
            draw = ImageDraw.Draw(after)
            box = ((x - w / 2) * width, (y - h / 2) * height, (x + w / 2) * width, (y + h / 2) * height)
            draw.rectangle(box, outline=color, width=2)
            draw.text(box[:2], f"r{row['source_row_index']} person?", fill=color)
    canvas = Image.new("RGB", (width * 2, height + 44), "#202020")
    canvas.paste(before, (0, 44))
    canvas.paste(after, (width, 44))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), "BEFORE: raw boxes/polygons; gray=fence orange=people green=person", fill="white")
    draw.text((width + 8, 8), "AFTER: tentative person boxes; HUMAN REVIEW PENDING / NO TRAINING", fill="white")
    result = io.BytesIO()
    canvas.save(result, format="PNG")
    return result.getvalue()


def prepare(archive_path: Path, output: Path, expected_sha256: str, overlays: bool = False) -> dict:
    if output.exists() or output.is_symlink():
        raise FileExistsError("Output already exists; never overwrite")
    # Existing symlink parents must not redirect writes outside the requested tree.
    if any(p.is_symlink() for p in output.absolute().parents):
        raise ValueError("Symlink output parent forbidden")
    archive_bytes = archive_path.read_bytes()
    if sha(archive_bytes) != expected_sha256:
        raise ValueError("Archive SHA256 mismatch")
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members, indices = safe_members(archive)
    config = yaml.safe_load(members.get("data.yaml", b""))
    if not isinstance(config, dict) or config.get("nc") != 3 or config.get("names") != CLASSES:
        raise ValueError("Unexpected original class mapping")
    images, labels = {}, {}
    allowed_metadata = {"data.yaml", "README.dataset.txt", "README.roboflow.txt"}
    for name, content in members.items():
        parts = PurePosixPath(name).parts
        if len(parts) == 3 and parts[0] in SPLITS and parts[1] in ("images", "labels"):
            split, kind, filename = parts
            stem = PurePosixPath(filename).stem
            target = images if kind == "images" else labels
            if (split, stem) in target:
                raise ValueError("Conflicting sample basename")
            if kind == "images":
                if PurePosixPath(filename).suffix.lower() not in (".jpg", ".jpeg", ".png"):
                    raise ValueError("Unsupported image extension")
                with Image.open(io.BytesIO(content)) as image:
                    image.verify()
                with Image.open(io.BytesIO(content)) as image:
                    image.load()
            elif not filename.endswith(".txt"):
                raise ValueError("Unsupported label extension")
            target[split, stem] = name
        elif name not in allowed_metadata:
            raise ValueError("Unexpected archive member")
    if not images or images.keys() != labels.keys() or set(k[0] for k in images) != set(SPLITS):
        raise ValueError("Image/label pairing or split mismatch")
    provenance, files, converted, counts = [], [], {}, Counter()
    sample_rows = {}
    for key, image_name in sorted(images.items()):
        label_name = labels[key]
        rows, output_rows = [], []
        for row_index, raw in enumerate(members[label_name].decode("utf-8-sig").splitlines(), 1):
            if not raw.strip():
                continue  # whitespace is not an annotation
            try:
                row = convert_row(raw)
            except ValueError as exc:
                raise ValueError(f"{label_name} row {row_index}: {exc}") from exc
            row.update(source_member=label_name, source_member_index=indices[label_name][0],
                       source_row_index=row_index, output_row_index=len(output_rows) + 1 if row["output"] else None)
            if row["output"]:
                output_rows.append(row["output"])
                counts["person_" + row["source_type"]] += 1
            else:
                counts["fence_removed"] += 1
            counts["source_rows"] += 1
            rows.append(row)
        label_bytes = (("\n".join(output_rows) + "\n") if output_rows else "").encode()
        converted[label_name] = label_bytes
        for row in rows:
            row["output_label_sha256"] = sha(label_bytes)
        provenance.extend(rows)
        sample_rows[key] = rows
        counts[key[0] + "_images"] += 1
        counts[key[0] + "_person_rows"] += len(output_rows)
        files.append({"image": image_name, "image_sha256": sha(members[image_name]),
                      "source_label": label_name, "source_label_sha256": sha(members[label_name]),
                      "output_label_sha256": sha(label_bytes), "person_rows": len(output_rows)})
    counts["person_rows"] = counts["person_bbox"] + counts["person_polygon"]
    summary = {"status": "review_pending", "human_review": "pending", "usable_for_training": False,
               "D0_passed": False, "training_approved": False, "one_annotation_one_tentative_box": True,
               "semantic_person_approval": False, "archive_sha256": sha(archive_bytes),
               "converter_sha256": sha(Path(__file__).read_bytes()), "counts": dict(counts),
               "images": len(images), "labels": len(labels), "images_excluded": 0,
               "source_classes": CLASSES, "duplicate_data_yaml_members": len(indices["data.yaml"]),
               "split_leakage_ruled_out": False, "filename_base_groups": len({k[1].split(".rf.")[0] for k in images})}
    # All schema/row validation completes before any dataset output is created.
    output.mkdir(parents=True, exist_ok=False)
    for name, content in sorted(members.items()):
        write_new(output, "source/" + name, content)
    for image_name in images.values():
        write_new(output, image_name, members[image_name])
    for name, content in converted.items():
        write_new(output, name, content)
    local_config = {"path": str(output.resolve()), "train": "train/images", "val": "valid/images",
                    "test": "test/images", "nc": 1, "names": ["person"]}
    write_new(output, "data.yaml", yaml.safe_dump(local_config, sort_keys=False).encode())
    write_new(output, "provenance.jsonl", b"".join(json.dumps(row, ensure_ascii=False, sort_keys=True).encode() + b"\n" for row in provenance))
    review_files = []
    if overlays:
        representatives = {}
        for key in sorted(images):
            base = key[1].split(".rf.")[0]
            representatives.setdefault(base, key)
        selected = set(representatives.values())
        selected.update(key for key, rows in sample_rows.items() if any(row["source_class_id"] == 1 or
                        (row["source_class_id"] != 0 and row["source_type"] == "polygon") for row in rows))
        for key in sorted(selected):
            name = f"review/{key[0]}/{key[1]}.png"
            content = draw_review(members[images[key]], sample_rows[key])
            write_new(output, name, content)
            review_files.append({"overlay": name, "sha256": sha(content), "source_image": images[key],
                                 "filename_base": key[1].split(".rf.")[0], "source_label": labels[key]})
    summary["review_overlays"] = len(review_files)
    manifest = {"source_members": [{"name": name, "archive_indices": indices[name], "sha256": sha(content)}
                                    for name, content in sorted(members.items())], "samples": files,
                "review_overlays": review_files}
    write_new(output, "manifest.json", json_bytes(manifest))
    write_new(output, "summary.json", json_bytes(summary))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-sha256", default=ARCHIVE_SHA256)
    parser.add_argument("--overlays", action="store_true", help="Create local PNG review comparisons")
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.output, args.expected_sha256, args.overlays), indent=2))


if __name__ == "__main__":
    main()
