"""Exclusive local evidence clips in the original field of view, without overlays."""

from datetime import datetime, timezone
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import time
import uuid

import av


DEFAULT_OUTPUT_ROOT = Path("/home/jhc7484/dev/sceneguard-ai/outputs/mvp0001")


def timestamp(started=None):
    now = time.monotonic_ns()
    return {"utc": datetime.now(timezone.utc).isoformat(), "monotonic_ns": now,
            "elapsed_seconds": None if started is None else (now - started) / 1e9}


def create_output(path, roots=None):
    """Require an unused absolute directory inside explicitly trusted local roots."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("output must be an absolute path without traversal")
    allowed = [Path(r).resolve() for r in (roots or [DEFAULT_OUTPUT_ROOT])]
    if not any(path.resolve().is_relative_to(r) and path.resolve() != r for r in allowed):
        raise ValueError("output is outside the safe output roots")
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise ValueError("symlink output components are forbidden")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(exist_ok=False)
    return path


def write_json(path, value, *, replace=False):
    """Flush to disk, replacing only files explicitly owned by this run."""
    path = Path(path)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                         allow_nan=False) + "\n"
    if not replace:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        write_json(temporary, value)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_json(handle, value):
    handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def save_evidence(video, output, *, interval, source_bounds, context_seconds=2.0):
    """Re-encode only arrived source frames in clipped native-PTS bounds.

    No audio, crop, annotation, resizing or model frames are substituted. Source
    native timestamps remain in the sidecar; MP4 timestamps start at zero.
    """
    if not math.isfinite(context_seconds) or context_seconds < 0:
        raise ValueError("invalid evidence context")
    lower = max(float(source_bounds[0]), float(interval[0]) - context_seconds)
    upper = min(float(source_bounds[1]), float(interval[1]) + context_seconds)
    if not all(math.isfinite(x) for x in (lower, upper)) or upper <= lower:
        raise ValueError("empty evidence interval")
    output = Path(output)
    if output.is_symlink():
        raise ValueError("evidence must not be a symlink")
    # Exclusive creation preserves old evidence even on reruns or collisions.
    with output.open("xb") as target, av.open(str(video)) as source:
        stream = source.streams.video[0]
        rate = stream.average_rate or stream.guessed_rate
        time_base = Fraction(1, 90000)
        first = last = None
        native_first = native_last = None
        count = 0
        last_duration = None
        with av.open(target, mode="w", format="mp4") as encoded:
            destination = encoded.add_stream("libx264", rate=rate)
            destination.width = stream.codec_context.width
            destination.height = stream.codec_context.height
            destination.pix_fmt = "yuv420p"
            destination.time_base = time_base
            destination.codec_context.time_base = time_base
            destination.options = {"crf": "18", "preset": "fast"}
            for frame in source.decode(stream):
                if frame.pts is None or frame.time_base is None:
                    raise ValueError("evidence source lost native timestamps")
                pts = float(frame.pts * frame.time_base)
                if pts < lower:
                    continue
                if pts >= upper:
                    break
                duration = float(frame.duration * frame.time_base) if frame.duration else 1 / float(rate)
                native = {"pts": frame.pts, "time_base": str(frame.time_base), "seconds": pts}
                if first is None:
                    first, native_first = pts, native
                last, native_last = pts, native
                last_duration = min(duration, upper - pts)
                # A fresh frame avoids mutating the source's timing metadata.
                original = av.VideoFrame.from_ndarray(frame.to_ndarray(format="rgb24"), format="rgb24")
                original.pts = round((pts - first) / float(time_base))
                original.time_base = time_base
                original.duration = max(1, round(last_duration / float(time_base)))
                for packet in destination.encode(original):
                    encoded.mux(packet)
                count += 1
            if not count:
                raise ValueError("no source frames in evidence bounds")
            for packet in destination.encode():
                encoded.mux(packet)
        target.flush()
        os.fsync(target.fileno())
    result = {"file": output.name, "requested_interval": list(interval),
              "clipped_interval": [lower, upper], "source_bounds": list(source_bounds),
              "first_source_pts": first, "last_source_pts": last,
              "native_first": native_first, "native_last": native_last,
              "source_duration_seconds": last + last_duration - first,
              "frames": count, "original_field_of_view": True,
              "reencoded": True, "saved_at": timestamp()}
    # Read actual output duration rather than treating metadata as a measurement.
    with av.open(str(output)) as check:
        result["encoded_duration_seconds"] = (float(check.duration / av.time_base)
                                               if check.duration is not None else None)
    write_json(output.with_suffix(".json"), result)
    return result
