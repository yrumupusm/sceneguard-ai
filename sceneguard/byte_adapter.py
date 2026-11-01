"""CPU ByteTrack adapter: measured cache boxes and prediction states stay separate."""
from types import SimpleNamespace
from fractions import Fraction
import math
import numpy as np
from .vendor.bytetrack.byte_tracker import BYTETracker
from .vendor.bytetrack.basetrack import BaseTrack, TrackState
from .replay_thresholds import normalize

SETTINGS = dict(track_thresh=.5, low_thresh=.25, match_thresh=.8,
                track_buffer=30, mot20=False)


class ByteAdapter:
    def __init__(self, use_low, *, native_interval=None, retain_seconds=None):
        # Experiments are sequential; official BaseTrack uses a process-global counter.
        BaseTrack._count = 0
        self.tracker = BYTETracker(SimpleNamespace(**SETTINGS), frame_rate=30)
        self.use_low = use_low
        self.last_seen = {}
        self.previous_pts = None
        self.native_interval = None if native_interval is None else Fraction(native_interval)
        if self.native_interval is not None and self.native_interval != Fraction(1001, 30000):
            raise ValueError('Native rational 30000/1001 interval required')
        self.retain_seconds = retain_seconds
        self.previous_native = None
        self.gap_prediction_steps = 0

    def step(self, frame):
        pts = frame['pts']
        if not math.isfinite(pts) or (self.previous_pts is not None and pts <= self.previous_pts):
            raise ValueError('PTS must increase')
        if self.native_interval is not None:
            at = frame['native_pts']*Fraction(frame['time_base'])
            if type(frame['native_pts']) is not int or abs(float(at)-pts) > 1e-9:
                raise ValueError('Native clock and actual source timestamp differ')
            if self.previous_native is not None:
                steps = (at-self.previous_native)/self.native_interval
                if steps.denominator != 1 or steps < 1:
                    raise ValueError('Native rational cadence with integral PTS gaps required')
                width,height = frame['source_size']
                # These are internal prediction/aging steps, never source frames,
                # observations, detector calls, boundary evidence or decisions.
                for _ in range(int(steps)-1):
                    self.tracker.update(np.empty((0,5)), (height,width), (height,width))
                    self.gap_prediction_steps += 1
                if self.retain_seconds is not None:
                    for name in ('tracked_stracks', 'lost_stracks'):
                        live = []
                        for track in getattr(self.tracker, name):
                            if pts-self.last_seen[track.track_id] > self.retain_seconds+1e-9:
                                track.mark_removed()
                            else:
                                live.append(track)
                        setattr(self.tracker, name, live)
            self.previous_native = at
        self.previous_pts = pts
        width, height = frame['source_size']
        eligible = []
        for index, (box, score) in enumerate(zip(frame['boxes'], frame['scores'])):
            if score < (.25 if self.use_low else .5):
                continue
            normalized = normalize(dict(source_size=[width, height], boxes=[box], scores=[score]), 0.)
            if not normalized:
                continue
            eligible.append(normalized[0] | {'cache_index': index})
        # Original pixel coordinates; both size arguments equal -> official scale=1.
        inputs = np.asarray([[*(np.asarray(d['bbox'])*[width,height,width,height]), d['score']]
                             for d in eligible], dtype=np.float64).reshape(-1, 5)
        self.tracker.update(inputs.copy(), (height, width), (height, width))
        states = []; observations = []; used = set()
        for track in self.tracker.tracked_stracks:
            if track.frame_id != self.tracker.frame_id:
                raise AssertionError('Tracked output without current measurement')
            d = eligible[track.detection_index]
            raw = track.raw_tlwh.copy(); raw[2:] += raw[:2]
            np.testing.assert_allclose(raw, inputs[track.detection_index, :4], rtol=0, atol=1e-9)
            self.last_seen[track.track_id] = pts
            used.add(track.detection_index)
            row = d | dict(track_id=track.track_id, observed=True, confirmed=track.is_activated,
                           state='tracked' if track.is_activated else 'unconfirmed',
                           association='high' if d['score'] >= .5 else 'low_second',
                           filter_bbox=(track.tlbr/[width,height,width,height]).tolist(),
                           last_observed_pts=pts, unobserved_seconds=0.)
            states.append(row)
            if track.is_activated:
                observations.append(row)
        for track in self.tracker.lost_stracks:
            if track.state != TrackState.Lost:
                continue
            last = self.last_seen[track.track_id]
            states.append(dict(track_id=track.track_id, observed=False, confirmed=track.is_activated,
                state='lost_prediction', bbox=None,
                prediction_bbox=(track.tlbr/[width,height,width,height]).tolist(),
                last_observed_pts=last, unobserved_seconds=pts-last))
        unmatched = [d for i,d in enumerate(eligible) if i not in used]
        return observations, states, unmatched
