"""Sequential native-PTS windows with a bounded sampled-frame buffer."""

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import math
from pathlib import Path

import av
import numpy as np


@dataclass
class Sample:
    rgb: np.ndarray
    pts: float
    native_pts: int
    time_base: str
    decoded_index: int
    target: float


@dataclass
class Window:
    window_id: str
    start: float
    end: float
    nominal_end: float
    samples: tuple
    fps: float
    source_size: tuple
    last_decoded_pts: float
    eof: bool

    @property
    def rgb(self):
        w, h = self.source_size
        return (np.stack([s.rgb for s in self.samples]) if self.samples
                else np.empty((0, h, w, 3), dtype=np.uint8))

    def source(self):
        first = self.samples[0].pts if self.samples else self.start
        first_index = self.samples[0].decoded_index if self.samples else 0
        return {
            "fps": self.fps,
            "pts_seconds": [s.pts for s in self.samples],
            "native_pts": [s.native_pts for s in self.samples],
            "time_base": [s.time_base for s in self.samples],
            # Real decoded ordinals and actual elapsed native PTS stay separate.
            "relative_indices": [s.decoded_index - first_index for s in self.samples],
            "elapsed_pts_seconds": [s.pts - first for s in self.samples],
            "decoded_indices": [s.decoded_index for s in self.samples],
            "sampling_targets_seconds": [s.target for s in self.samples],
            "source_size": list(self.source_size),
            "window_start": self.start, "window_end": self.end,
            "nominal_window_end": self.nominal_end,
            "last_decoded_pts": self.last_decoded_pts,
            "last_input_pts": self.samples[-1].pts if self.samples else None,
            "available_at_source_time": max(self.last_decoded_pts, self.end) if self.eof else self.last_decoded_pts,
            "eof": self.eof,
        }


def iter_windows(video: Path, *, window_seconds=5.0, stride_seconds=2.5,
                 sample_fps=2.0, stats=None):
    """Decode from the beginning through EOF, never seeking to an event time.

    Select the first arrived frame at/after each global sampling target. A gap
    may skip targets, but never duplicates a frame. Windows include only samples
    with actual PTS in [start,end); EOF bounds use the last frame's own duration.
    A frame used to close a window is recorded as arrived, never as its input.
    """
    if (window_seconds, stride_seconds, sample_fps) != (5.0, 2.5, 2.0):
        raise ValueError("MVP-0001 fixes 5s windows, 2.5s stride and 2fps")
    stats = {} if stats is None else stats
    stats.update(decoded_frames=0, sampled_frames=0, windows=0,
                 max_buffered_samples=0, eof_reached=False,
                 first_decoded_pts=None, last_decoded_pts=None)
    with av.open(str(video)) as container:
        if not container.streams.video:
            raise ValueError("source has no video stream")
        stream = container.streams.video[0]
        rate = stream.average_rate or stream.guessed_rate
        fps = float(rate) if rate else 0.0
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("source FPS metadata is unavailable")
        samples = deque()
        origin = None
        next_target = None
        start = None
        number = 0
        previous = None
        source_end = None
        source_size = None

        def build(end, eof):
            nonlocal number
            number += 1
            selected = tuple(s for s in samples if start <= s.pts < end)
            stats["windows"] = number
            return Window(f"w{number:06d}", start, end,
                          start + window_seconds, selected, fps, source_size,
                          stats["last_decoded_pts"], eof)

        for index, frame in enumerate(container.decode(stream)):
            if frame.pts is None or frame.time_base is None:
                raise ValueError("missing native PTS/time_base; no timestamp synthesis")
            pts = float(frame.pts * frame.time_base)
            if not math.isfinite(pts) or (previous is not None and pts <= previous):
                raise ValueError("native presentation timestamps are not strictly increasing")
            previous = pts
            if origin is None:
                origin = start = next_target = pts
                source_size = (frame.width, frame.height)
                stats.update(first_decoded_pts=pts, source_fps=fps,
                             source_size=list(source_size), time_base=str(frame.time_base))
            elif (frame.width, frame.height) != source_size:
                raise ValueError("source dimensions changed")
            duration = float(frame.duration * frame.time_base) if frame.duration else 1 / fps
            source_end = pts + duration
            stats.update(decoded_frames=index + 1, last_decoded_pts=pts,
                         source_end_seconds=source_end)
            # Do not append the closing/future frame to a window's model input.
            while pts >= start + window_seconds:
                yield build(start + window_seconds, False)
                start += stride_seconds
                while samples and samples[0].pts < start:
                    samples.popleft()
            if pts + 1e-9 >= next_target:
                target = next_target
                samples.append(Sample(frame.to_ndarray(format="rgb24"), pts,
                                      int(frame.pts), str(Fraction(frame.time_base)),
                                      index, target))
                stats["sampled_frames"] += 1
                stats["max_buffered_samples"] = max(stats["max_buffered_samples"], len(samples))
                ticks = math.floor((pts - origin) * sample_fps + 1e-8) + 1
                next_target = origin + ticks / sample_fps
        stats["eof_reached"] = True
        if origin is None:
            raise ValueError("source contains no decoded frames")
        while start <= stats["last_decoded_pts"]:
            yield build(min(start + window_seconds, source_end), True)
            start += stride_seconds
            while samples and samples[0].pts < start:
                samples.popleft()
