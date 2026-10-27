"""CPU ByteTrack adapter: measured cache boxes and prediction states stay separate."""
from types import SimpleNamespace
import numpy as np
from .vendor.bytetrack.byte_tracker import BYTETracker
from .vendor.bytetrack.basetrack import BaseTrack, TrackState
from .replay_thresholds import normalize

SETTINGS = dict(track_thresh=.5, low_thresh=.25, match_thresh=.8,
                track_buffer=30, mot20=False)


class ByteAdapter:
    def __init__(self, use_low):
        # Experiments are sequential; official BaseTrack uses a process-global counter.
        BaseTrack._count = 0
        self.tracker = BYTETracker(SimpleNamespace(**SETTINGS), frame_rate=30)
        self.use_low = use_low
        self.last_seen = {}
        self.previous_pts = None

    def step(self, frame):
        pts = frame['pts']
        if self.previous_pts is not None and pts <= self.previous_pts:
            raise ValueError('PTS must increase')
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
