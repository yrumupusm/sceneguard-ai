"""Meaningful synthetic checks for the unreviewed CPU dataset preparation."""
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

from PIL import Image
import yaml

SPEC = importlib.util.spec_from_file_location("prepare_climbing_fence", Path(__file__).resolve().parents[1] / "scripts/prepare_climbing_fence.py")
PREP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREP)

CONFIG = yaml.safe_dump({"nc": 3, "names": PREP.CLASSES}).encode()


def image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, "PNG")
    return buffer.getvalue()


def fixture(path, label="2 .5 .5 .4 .4\n", extras=()):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("data.yaml", CONFIG)
            for split in PREP.SPLITS:
                archive.writestr(f"{split}/images/example.png", image_bytes())
                archive.writestr(f"{split}/labels/example.txt", label)
            for name, content in extras:
                archive.writestr(name, content)
    return PREP.sha(path.read_bytes())


class RowTests(unittest.TestCase):
    def test_polygon_minmax_and_class_remap(self):
        row = PREP.convert_row("2 .1 .2 .7 .2 .4 .8")
        self.assertEqual(row["output"], "0 0.4 0.5 0.6 0.6")
        self.assertEqual(row["source_type"], "polygon")

    def test_bbox_xywh_tokens_unchanged_for_both_person_classes(self):
        for class_id in (1, 2):
            self.assertEqual(PREP.convert_row(f"{class_id} 0.5000 5e-1 .40 .40")["output"], "0 0.5000 5e-1 .40 .40")

    def test_fence_is_validated_before_drop(self):
        self.assertIsNone(PREP.convert_row("0 .5 .5 .4 .4")["output"])
        with self.assertRaises(ValueError):
            PREP.convert_row("0 .5 .5 nan .4")

    def test_invalid_rows_and_bounds_rejected_without_clipping(self):
        for row in ("", "3 .5 .5 .2 .2", "1.0 .5 .5 .2 .2", "2 .1 .1", "2 .1 .2 .3 .4 .5",
                    "2 .1 .1 .2 .2 .3 .3 .4", "2 NaN .5 .4 .4", "2 .5 Infinity .4 .4",
                    "2 .5 .5 0 .4", "2 .1 .5 .4 .4", "2 .9 .5 .4 .4", "2 -.1 .5 .2 .2",
                    "2 .5 .5 1.01 .2", "2 .1 .2 .1 .5 .1 .8", "2 .1 .2 1.1 .2 .4 .8"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                PREP.convert_row(row)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive, self.output = self.root / "input.zip", self.root / "output"

    def run_prepare(self, label="2 .5 .5 .4 .4\n", extras=(), overlays=False):
        digest = fixture(self.archive, label, extras)
        return PREP.prepare(self.archive, self.output, digest, overlays)

    def test_mixed_rows_counts_raw_preservation_images_and_local_config(self):
        raw = "0 .5 .5 .8 .8\n2 .5 .5 .2 .2\n1 .1 .2 .7 .2 .4 .8\n"
        result = self.run_prepare(raw, overlays=True)
        self.assertEqual(result["counts"]["person_bbox"], 3)
        self.assertEqual(result["counts"]["person_polygon"], 3)
        self.assertEqual(result["counts"]["fence_removed"], 3)
        self.assertFalse(result["usable_for_training"])
        self.assertFalse(result["D0_passed"])
        self.assertEqual(result["status"], "review_pending")
        self.assertEqual(result["images_excluded"], 0)
        for split in PREP.SPLITS:
            self.assertEqual((self.output / split / "labels/example.txt").read_text(), "0 .5 .5 .2 .2\n0 0.4 0.5 0.6 0.6\n")
            self.assertEqual((self.output / "source" / split / "labels/example.txt").read_text(), raw)
            self.assertEqual((self.output / split / "images/example.png").read_bytes(), image_bytes())
        config = yaml.safe_load((self.output / "data.yaml").read_text())
        self.assertEqual(config["names"], ["person"])
        for split_key in ("train", "val", "test"):
            self.assertTrue((Path(config["path"]) / config[split_key]).is_dir())
        provenance = [json.loads(line) for line in (self.output / "provenance.jsonl").read_text().splitlines()]
        self.assertEqual(len(provenance), 9)
        for row in provenance:
            self.assertEqual(row["raw_sha256"], PREP.sha(row["raw"].encode()))
            self.assertEqual(row["output_row_sha256"], PREP.sha(row["output"].encode()) if row["output"] else None)
            self.assertIsInstance(row["source_member_index"], int)

    def test_invalid_input_never_creates_output(self):
        with self.assertRaises(ValueError):
            self.run_prepare("2 .1 .5 .4 .4\n")
        self.assertFalse(self.output.exists())

    def test_no_images_excluded_for_fence_only_or_group_annotations(self):
        for raw in ("0 .5 .5 .8 .8\n", "1 .5 .5 .8 .8\n"):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary)
                archive = path / "input.zip"
                digest = fixture(archive, raw)
                result = PREP.prepare(archive, path / "out", digest)
                self.assertEqual(result["images"], 3)
                self.assertEqual(result["images_excluded"], 0)

    def test_three_identical_yaml_members_allowed(self):
        result = self.run_prepare(extras=[("data.yaml", CONFIG)] * 2)
        self.assertEqual(result["duplicate_data_yaml_members"], 3)
        manifest = json.loads((self.output / "manifest.json").read_text())
        member = next(row for row in manifest["source_members"] if row["name"] == "data.yaml")
        self.assertEqual(len(member["archive_indices"]), 3)

    def test_conflicting_yaml_and_any_other_duplicate_rejected(self):
        for extras in ([("data.yaml", b"bad")], [("data.yaml", CONFIG)] * 3,
                       [("train/labels/example.txt", b"2 .5 .5 .4 .4\n")],
                       [("train/images/example.png", b"bad")]):
            with self.subTest(extras=extras), self.assertRaises(ValueError):
                self.run_prepare(extras=extras)
            self.assertFalse(self.output.exists())

    def test_unsafe_paths_symlink_special_members_and_conflicts_rejected(self):
        symlink = zipfile.ZipInfo("link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        fifo = zipfile.ZipInfo("fifo")
        fifo.create_system = 3
        fifo.external_attr = (stat.S_IFIFO | 0o600) << 16
        for name in ("../escape", "/absolute", "train/../escape", "a//b", "a/./b", "C:/bad", "a\\bad", symlink, fifo, "train"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.run_prepare(extras=[(name, b"bad")])
            self.assertFalse(self.output.exists())
        self.assertFalse((self.root / "escape").exists())

    def test_existing_output_and_symlinks_never_overwritten(self):
        self.run_prepare()
        before = (self.output / "summary.json").read_bytes()
        with self.assertRaises(FileExistsError):
            PREP.prepare(self.archive, self.output, PREP.sha(self.archive.read_bytes()))
        self.assertEqual((self.output / "summary.json").read_bytes(), before)
        link = self.root / "link"
        link.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            PREP.prepare(self.archive, link, PREP.sha(self.archive.read_bytes()))
        with self.assertRaises(ValueError):
            PREP.prepare(self.archive, link / "child", PREP.sha(self.archive.read_bytes()))

    def test_wrong_hash_mapping_unpaired_image_and_same_basename_rejected(self):
        digest = fixture(self.archive)
        with self.assertRaises(ValueError):
            PREP.prepare(self.archive, self.output, "0" * 64)
        cases = [[("train/images/extra.png", image_bytes())], [("train/images/example.jpg", image_bytes())]]
        for extras in cases:
            with self.subTest(extras=extras), self.assertRaises(ValueError):
                self.run_prepare(extras=extras)
        self.assertFalse(self.output.exists())
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("data.yaml", yaml.safe_dump({"nc": 3, "names": list(reversed(PREP.CLASSES))}))
        with self.assertRaises(ValueError):
            PREP.prepare(self.archive, self.output, PREP.sha(self.archive.read_bytes()))


if __name__ == "__main__":
    unittest.main()
