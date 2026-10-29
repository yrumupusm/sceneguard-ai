"""CPU tests for timestamp identity, source integrity and non-overwrite rules."""
from fractions import Fraction
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from scripts import prepare_batch0007_evaluation as prep


class EvaluationPreparationTests(unittest.TestCase):
    def test_fixed_selection_and_camera_pixels(self):
        self.assertEqual(len(prep.FIXED_SAMPLES), 7)
        self.assertEqual([r[2] for r in prep.FIXED_SAMPLES], [84, 90, 94, 50, 55, 47.5, 52.5])
        self.assertEqual(prep.roi_pixels([.28, .2, .75, .8], 1920, 1080), [537, 216, 1440, 864])
        self.assertEqual(prep.roi_pixels([.6, 0, .9, .6], 1920, 1080), [1152, 0, 1728, 648])

    def test_fractional_time_requires_exact_native_pts(self):
        self.assertEqual(prep.exact_native_pts(47.5, "1/15360"), 729600)
        with self.assertRaisesRegex(ValueError, "exact native PTS"):
            prep.exact_native_pts(.01, "1/30")

    def test_invalid_roi_does_not_clip(self):
        for roi in ([0, 0, 1.1, 1], [.8, 0, .5, 1], [0, 0, float("nan"), 1]):
            with self.assertRaises(ValueError):
                prep.roi_pixels(roi, 1920, 1080)

    def test_decode_exact_never_accepts_closest(self):
        class Container:
            streams = SimpleNamespace(video=[SimpleNamespace(time_base=Fraction(1, 30))])
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def seek(self, *args, **kwargs): pass
            def decode(self, stream):
                return iter([SimpleNamespace(pts=29), SimpleNamespace(pts=31)])
        with patch("av.open", return_value=Container()):
            with self.assertRaisesRegex(ValueError, "Exact requested native PTS absent"):
                prep.decode_exact(Path("synthetic.mp4"), 1)

    def test_decode_exact_preserves_rgb_and_pts(self):
        rgb = np.array([[[7, 19, 231]]], dtype=np.uint8)
        class Frame:
            pts = 30
            time_base = Fraction(1, 30)
            def to_ndarray(self, format):
                self.format = format
                return rgb
        frame = Frame()
        class Container:
            streams = SimpleNamespace(video=[SimpleNamespace(time_base=Fraction(1, 30))])
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def seek(self, *args, **kwargs): pass
            def decode(self, stream): return iter([SimpleNamespace(pts=29), frame])
        with patch("av.open", return_value=Container()):
            actual, pts, base, traversed = prep.decode_exact(Path("synthetic.mp4"), 1)
        np.testing.assert_array_equal(actual, rgb)
        self.assertEqual((pts, base, traversed, frame.format), (30, "1/30", 2, "rgb24"))

    def test_cached_rgb_checks_file_bytes_and_exact_pts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rgb = np.array([[[13, 65, 254]]], dtype=np.uint8)
            np.save(root / "rgb.npy", rgb, allow_pickle=False)
            source = dict(source_id="E01_030", sha256="source", relative_video_path="original.mp4")
            row = dict(source_id="E01_030", source_sha256="source", source_path="original.mp4",
                       native_pts=30, time_base="1/30", pts_seconds=1, rgb_path="rgb.npy",
                       rgb_sha256=prep.sha_file(root / "rgb.npy"), rgb_shape=[1, 1, 3],
                       rgb_bytes_sha256=prep.sha_bytes(rgb.tobytes()))
            np.testing.assert_array_equal(prep.cached_rgb(root, row, source, 1), rgb)
            with self.assertRaisesRegex(ValueError, "exact PTS"):
                prep.cached_rgb(root, row, source, 1.1)
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                prep.cached_rgb(root, row, dict(source, sha256="different"), 1)
            with self.assertRaisesRegex(ValueError, "RGB hash/shape"):
                prep.cached_rgb(root, dict(row, rgb_bytes_sha256="different"), source, 1)
            with (root / "rgb.npy").open("ab") as handle:
                handle.write(b"tampered")
            with self.assertRaisesRegex(ValueError, "file hash"):
                prep.cached_rgb(root, row, source, 1)

    def test_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "existing"
            destination.mkdir()
            marker = destination / "old"
            marker.write_text("preserve")
            with self.assertRaises(FileExistsError):
                prep.prepare(root, destination, root / "dataset")
            self.assertEqual(marker.read_text(), "preserve")

    def test_manifest_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text("old")
            with self.assertRaises(FileExistsError):
                prep.prepare(root, root / "new", root / "dataset", manifest)
            self.assertFalse((root / "new").exists())
            self.assertEqual(manifest.read_text(), "old")

    def test_unexpected_training_archive_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text("{}")
            (root / "summary.json").write_text(json.dumps(dict(archive_sha256="wrong")))
            with self.assertRaisesRegex(ValueError, "source archive"):
                prep.audit_dataset(root)


if __name__ == "__main__":
    unittest.main()
