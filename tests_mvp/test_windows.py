"""CPU-only synthetic timing tests; never import a model or read CCTV pixels."""

from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import av
import numpy as np

from mvp.windows import iter_windows


def write_video(path, pts=None, *, count=80, fps=10):
    pts = [i / fps for i in range(count)] if pts is None else pts
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=Fraction(fps))
        stream.width, stream.height = 64, 48
        stream.pix_fmt = "yuv420p"
        stream.codec_context.time_base = Fraction(1, 90000)
        stream.options = {"bf": "0", "preset": "ultrafast", "crf": "18"}
        for index, seconds in enumerate(pts):
            rgb = np.full((48, 64, 3), index % 255, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(rgb, format="rgb24")
            frame.pts = round(seconds * 90000)
            frame.time_base = Fraction(1, 90000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_full_video_periodic_windows_through_eof(self):
        video = write_video(self.root / "full.mp4")
        stats = {}
        windows = list(iter_windows(video, stats=stats))
        self.assertEqual([w.start for w in windows], [0, 2.5, 5, 7.5])
        self.assertEqual([len(w.samples) for w in windows], [10, 10, 6, 1])
        self.assertEqual(windows[0].window_id, "w000001")
        self.assertEqual(windows[0].source()["pts_seconds"], [i / 2 for i in range(10)])
        self.assertTrue(stats["eof_reached"])
        self.assertEqual(stats["decoded_frames"], 80)
        self.assertEqual(stats["sampled_frames"], 16)
        self.assertLessEqual(stats["max_buffered_samples"], 10)
        self.assertAlmostEqual(windows[-1].end, 8.0)
        self.assertEqual(windows[-1].last_decoded_pts, 7.9)
        self.assertEqual(windows[-1].source()["available_at_source_time"], 8.0)

    def test_future_boundary_frame_is_arrived_but_never_input(self):
        windows = list(iter_windows(write_video(self.root / "future.mp4")))
        first = windows[0]
        self.assertEqual(first.last_decoded_pts, 5.0)
        self.assertEqual(first.samples[-1].pts, 4.5)
        self.assertTrue(all(s.pts < first.end for s in first.samples))
        self.assertEqual(first.source()["available_at_source_time"], 5.0)

    def test_short_and_single_frame_have_only_real_observations(self):
        short = list(iter_windows(write_video(self.root / "short.mp4", count=13)))
        self.assertEqual(len(short), 1)
        self.assertEqual(len(short[0].samples), 3)
        self.assertAlmostEqual(short[0].end, 1.3)
        self.assertEqual(short[0].samples[-1].pts, 1.0)
        single = list(iter_windows(write_video(self.root / "one.mp4", count=1)))
        self.assertEqual(len(single[0].samples), 1)
        self.assertEqual(single[0].source()["elapsed_pts_seconds"], [0.0])

    def test_variable_pts_and_gaps_keep_native_order(self):
        pts = [0, .1, .6, 1.6, 2.8, 3.2, 4.9, 5.4, 6.3]
        windows = list(iter_windows(write_video(self.root / "vfr.mp4", pts)))
        for window in windows:
            source = window.source()
            self.assertEqual(len(source["native_pts"]), len(set(source["native_pts"])))
            self.assertTrue(all(window.start <= t < window.end for t in source["pts_seconds"]))
            for native, base, seconds in zip(source["native_pts"], source["time_base"], source["pts_seconds"]):
                self.assertAlmostEqual(float(native * Fraction(base)), seconds)
            self.assertEqual(source["relative_indices"], [i - source["decoded_indices"][0]
                                                          for i in source["decoded_indices"]])
            self.assertTrue(all(type(i) is int for i in source["relative_indices"]))
        self.assertEqual(windows[0].source()["pts_seconds"], [0, .6, 1.6, 2.8, 3.2, 4.9])
        self.assertEqual(windows[0].last_decoded_pts, 5.4)

    def test_fractional_fps_is_not_rounded(self):
        video = write_video(self.root / "fractional.mp4", count=180, fps=Fraction(30000, 1001))
        windows = list(iter_windows(video))
        self.assertAlmostEqual(windows[0].fps, 30000 / 1001, places=5)
        source = windows[0].source()
        self.assertAlmostEqual(source["pts_seconds"][1], 15 * 1001 / 30000, places=5)

    def test_missing_or_nonmonotonic_pts_fail_without_synthesis(self):
        class Frame:
            width, height, duration = 64, 48, 1
            time_base = Fraction(1, 10)
            def __init__(self, pts):
                self.pts = pts
            def to_ndarray(self, **kwargs):
                return np.zeros((48, 64, 3), dtype=np.uint8)
        class Stream:
            average_rate = Fraction(10)
        class Source:
            streams = type("Streams", (), {"video": [Stream()]})()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def decode(self, stream):
                return iter(self.frames)
        for frames in ([Frame(None)], [Frame(0), Frame(0)], [Frame(1), Frame(0)], []):
            source = Source()
            source.frames = frames
            with patch("mvp.windows.av.open", return_value=source), self.assertRaises(ValueError):
                list(iter_windows(self.root / "unused.mp4"))

    def test_frozen_window_settings(self):
        with self.assertRaises(ValueError):
            list(iter_windows(self.root / "unused.mp4", stride_seconds=1))


if __name__ == "__main__":
    unittest.main()
