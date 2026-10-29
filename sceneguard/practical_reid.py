"""EXP-0028 fixed BoT-SORT/ReID adapter for historical FCOS measurements.

Uses installed Ultralytics (AGPL-3.0) without copying or modifying its code.
CPU only: a GPU implementation must use the project's canonical queue separately.
"""
import importlib.metadata
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from .replay_gap_tracking import sha256
from .replay_thresholds import normalize

VERSION = '8.4.192'
MODEL_SHA = '8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb'
MODEL_URL = 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-reid.onnx'
SETTINGS = dict(tracker_type='botsort', track_high_thresh=.5, track_low_thresh=.25,
                new_track_thresh=.6, match_thresh=.8, fuse_score=True,
                gmc_method='none', proximity_thresh=.5, appearance_thresh=.8,
                with_reid=True, device='cpu')


class CachedBoxes:
    """Small NumPy results protocol accepted by official BOTSORT.update()."""
    def __init__(self, data):
        self.data = np.asarray(data, dtype=np.float64).reshape(-1, 6)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, mask):
        return CachedBoxes(self.data[mask])

    @property
    def conf(self):
        return self.data[:, 4]

    @property
    def cls(self):
        return self.data[:, 5]

    @property
    def xyxy(self):
        return self.data[:, :4]

    @property
    def xywh(self):
        result = self.xyxy.copy()
        result[:, 2:] -= result[:, :2]
        result[:, :2] += result[:, 2:] / 2
        return result


def create_adapter(weights, interval, retain_seconds=3.0):
    """Load exactly the pinned local encoder; never resolve/download a model name."""
    weights = Path(weights).resolve(strict=True)
    if weights.suffix != '.onnx' or sha256(weights) != MODEL_SHA:
        raise ValueError('Expected pinned official yolo26n-reid.onnx bytes')
    if importlib.metadata.version('ultralytics') != VERSION:
        raise ValueError('Expected the inspected Ultralytics 8.4.192 implementation')
    # Import lap explicitly before ultralytics can attempt an automatic installation.
    import lap  # noqa: F401
    import onnx  # noqa: F401
    import onnxruntime  # noqa: F401
    import torch
    from ultralytics.trackers.bot_sort import BOTSORT
    from ultralytics.trackers.utils.reid import ReID
    from ultralytics.nn.autobackend import AutoBackend
    from ultralytics.nn.backends.onnx import ONNXBackend
    from functools import partial

    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL

    class CPUBackend(AutoBackend):
        # Official ONNX backend exposes session_options; AutoBackend does not.
        # A local subclass supplies them without editing the shared library/map.
        _BACKEND_MAP = AutoBackend._BACKEND_MAP | {
            'onnx': partial(ONNXBackend, session_options=options)}

    class CPUReID(ReID):
        def __init__(self):
            self.is_pt = False
            self.device = torch.device('cpu')
            self.model = CPUBackend(str(weights), device=self.device, fp16=False, verbose=False)
            self.fp16 = self.model.fp16
            shape = self.model.session.get_inputs()[0].shape
            if len(shape) != 4:
                raise ValueError('Expected BCHW encoder input')
            # Official asset is dynamic; use its published/exported 448 crop size.
            self.imgsz = tuple(x if isinstance(x, int) and x > 0 else 448 for x in shape[2:])
            if self.imgsz != (448, 448):
                raise ValueError('Expected the fixed 448x448 pretrained encoder setting')
            self.batch_size = shape[0] if isinstance(shape[0], int) and shape[0] > 0 else None
            self.calls = self.patches = self.valid_embeddings = 0

        def __call__(self, img, dets):
            features = super().__call__(img, dets)
            self.calls += 1
            self.patches += len(dets)
            self.valid_embeddings += sum(f is not None for f in features)
            if len(features) != len(dets) or any(f is None or not np.all(np.isfinite(f))
                                                or np.linalg.norm(f) < 1e-12 for f in features):
                raise ValueError('Missing/invalid embedding: refuse silent geometry-only fallback')
            return features

    args = SimpleNamespace(**SETTINGS, model=str(weights),
                           track_buffer=math.ceil(retain_seconds / interval - 1e-9))
    # Defer external encoder construction so the documented ONNX thread options
    # can be supplied; all association/crop/resize/forward logic remains upstream.
    args.with_reid = False
    tracker = BOTSORT(args)
    args.with_reid = True
    tracker.encoder = CPUReID()
    encoder = tracker.encoder
    providers = encoder.model.session.get_providers()
    if str(encoder.device) != 'cpu' or providers != ['CPUExecutionProvider']:
        raise RuntimeError('Expected explicit CPU encoder and CPUExecutionProvider only')
    return PracticalReIDAdapter(tracker)


class PracticalReIDAdapter:
    def __init__(self, tracker):
        self.tracker = tracker
        self.last_seen = {}
        self.previous_pts = None

    def step(self, frame, bgr):
        pts = frame['pts']
        if not math.isfinite(pts) or (self.previous_pts is not None and pts <= self.previous_pts):
            raise ValueError('Finite increasing PTS required')
        width, height = frame['source_size']
        if bgr.dtype != np.uint8 or bgr.shape != (height, width, 3):
            raise ValueError('Original-size uint8 BGR image required for real crop encoding')
        eligible = []
        for index, (box, score) in enumerate(zip(frame['boxes'], frame['scores'])):
            rows = normalize(dict(source_size=[width, height], boxes=[box], scores=[score]), .25)
            if rows:
                eligible.append(rows[0] | dict(cache_index=index))
        scale = np.array([width, height, width, height])
        inputs = CachedBoxes([[*(np.array(d['bbox']) * scale), d['score'], 0] for d in eligible])
        self.tracker.update(inputs, img=bgr)
        self.previous_pts = pts
        observations, states, used = [], [], set()
        for track in self.tracker.tracked_stracks:
            if track.frame_id != self.tracker.frame_id:
                raise AssertionError('Tracked state lacks a current measurement')
            index = int(track.idx)
            if index != track.idx or not 0 <= index < len(eligible) or index in used:
                raise AssertionError('Invalid or duplicate official full-detection index')
            used.add(index)
            d = eligible[index]
            if not math.isclose(float(track.score), d['score'], rel_tol=0, abs_tol=1e-7):
                raise AssertionError('Official track and cache measurement score disagree')
            self.last_seen[int(track.track_id)] = pts
            row = d | dict(track_id=int(track.track_id), observed=True,
                           confirmed=bool(track.is_activated),
                           state='tracked' if track.is_activated else 'unconfirmed',
                           association='high' if d['score'] >= .5 else 'low_second',
                           filter_bbox=(track.xyxy / scale).tolist(),
                           last_observed_pts=pts, unobserved_seconds=0.)
            # Boundary receives raw cache coordinates, never the filtered box.
            states.append(row)
            if track.is_activated:
                observations.append(row)
        for track in self.tracker.lost_stracks:
            # Removed stale tracks may remain in upstream lost pool for one step.
            if int(track.state) != 2:
                continue
            tid = int(track.track_id)
            last = self.last_seen[tid]
            states.append(dict(track_id=tid, observed=False, confirmed=bool(track.is_activated),
                               state='lost_prediction', bbox=None,
                               prediction_bbox=(track.xyxy / scale).tolist(),
                               last_observed_pts=last, unobserved_seconds=pts-last))
        return observations, states, [d for i, d in enumerate(eligible) if i not in used]
