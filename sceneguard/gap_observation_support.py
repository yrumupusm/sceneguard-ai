"""EXP-0039: cached detections + short native-image flow, as read-only support.

No training, detector invocation, identity merge, or automatic alarm cancellation.
A cached box is a detector output, not a person ground truth. LK points are
image-derived correspondences, not observations of an invisible person's body.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import math
from typing import Any


def finite(value, name='value'):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def box(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError('Normalized xyxy box required')
    b = [finite(v, 'bbox') for v in value]
    if not (0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1):
        raise ValueError('Nonempty normalized box required')
    return b


def intersection(a, b):
    return max(0., min(a[2], b[2])-max(a[0], b[0])) * max(0., min(a[3], b[3])-max(a[1], b[1]))


def iou(a, b):
    overlap = intersection(a, b)
    return overlap / ((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-overlap)


def expanded(b, margin=.5):
    b = box(b)
    x, y = (b[2]-b[0])*margin, (b[3]-b[1])*margin
    return [max(0., b[0]-x), max(0., b[1]-y), min(1., b[2]+x), min(1., b[3]+y)]


def catalog_frame(cache: dict, tracked: dict, floor=.25) -> list[dict]:
    """Include all returned cache boxes, with traceable measurement association.

    States duplicate detections in existing files; deduplicate by cache_index.
    Predicted lost boxes are never measurements. Below-floor outputs are audit
    evidence only and are NOT silently fed into the existing tracker.
    """
    for key in ('pts', 'native_pts', 'time_base'):
        if tracked.get(key) != cache.get(key):
            raise ValueError('Cache/track frame timing differs: '+key)
    w, h = cache['source_size']
    if w <= 0 or h <= 0 or len(cache['boxes']) != len(cache['scores']):
        raise ValueError('Invalid source dimensions or cache lengths')
    catalog = []
    for index, (b, score) in enumerate(zip(cache['boxes'], cache['scores'])):
        normalized = box([max(0., min(1., finite(v)/(w if k % 2 == 0 else h))) for k,v in enumerate(b)])
        score = finite(score, 'score')
        if not 0 <= score <= 1:
            raise ValueError('Score outside [0,1]')
        catalog.append(dict(cache_index=index, bbox=normalized, score=score, track_ids=[],
                            assignment='cached_below_tracker_floor' if score < floor else 'cached_not_exported'))
    for collection in ('unmatched', 'states', 'detections'):
        for row in tracked.get(collection, []):
            if collection != 'unmatched' and not row.get('observed', False):
                continue
            if collection == 'unmatched' and row.get('observed') is False:
                continue
            index = row.get('cache_index')
            if type(index) is not int or not 0 <= index < len(catalog):
                raise ValueError('Actual row must reference a cache index')
            item = catalog[index]
            if any(abs(a-b) > 1e-6 for a,b in zip(box(row['bbox']), item['bbox'])):
                raise ValueError('Tracked box differs from actual cache measurement')
            if 'score' in row and abs(finite(row['score'])-item['score']) > 1e-6:
                raise ValueError('Tracked score differs from cache')
            if collection == 'unmatched':
                item['assignment'] = 'unmatched_detection'
                continue
            tid = row.get('track_id')
            if type(tid) is not int or tid < 0:
                raise ValueError('Invalid measured track ID')
            if item['track_ids'] and tid not in item['track_ids']:
                raise ValueError('One measurement assigned to conflicting track IDs')
            if tid not in item['track_ids']:
                item['track_ids'].append(tid)
            if row.get('confirmed', True):
                item['assignment'] = 'confirmed_track'
            elif item['assignment'] != 'confirmed_track':
                item['assignment'] = 'unconfirmed_track'
    return catalog


def audit_loss(event: dict, segment: dict, cached: list, tracked: list) -> dict:
    """Read exactly the measurement gap ending at the original alert decision."""
    if len(cached) != len(tracked):
        raise ValueError('Cache/tracking lengths differ')
    last = segment['rows'][-1]
    at, end = finite(last['pts']), finite(event['decision_time_pts'])
    if at >= end or event.get('segment') != segment['id'] or event.get('raw_id') != segment['raw_id']:
        raise ValueError('Loss event does not bind to segment')
    if abs(finite(event['last_observed_pts'])-at) > 1e-6:
        raise ValueError('Loss timestamp differs from final measurement')
    region = expanded(last['bbox'])
    timeline, counts = [], Counter()
    for index, (cache, frame) in enumerate(zip(cached, tracked)):
        pts = finite(cache['pts'])
        if not at < pts <= end+1e-9:
            continue
        candidates = [r for r in catalog_frame(cache, frame) if intersection(region,r['bbox']) > 0]
        eligible = [r for r in candidates if r['score'] >= .25]
        if any(segment['raw_id'] in r['track_ids'] for r in eligible):
            kind = 'same_raw_id_observed_again'
        elif any(r['assignment']=='confirmed_track' for r in eligible):
            kind = 'other_confirmed_detection_nearby'
        elif eligible:
            kind = 'unconfirmed_or_unmatched_detection_nearby'
        elif candidates:
            kind = 'only_below_tracker_floor_nearby'
        else:
            kind = 'no_local_box_in_saved_cache'
        counts[kind] += 1
        timeline.append(dict(frame_index=index, pts=pts, classification=kind, candidates=candidates))
    if not timeline or abs(timeline[-1]['pts']-end) > 1e-6:
        raise ValueError('Full original waiting interval required')
    return dict(segment=segment['id'], raw_id=segment['raw_id'], last_observed_pts=at,
                decision_time_pts=end, search_box=region, timeline=timeline, counts=dict(counts),
                scope='nearby_detector_outputs_not_identity_or_visibility_truth',
                baseline_status=event['status'], proposed_status=event['status'],
                cancel_alarm=False, identity_verified=False)


@dataclass(frozen=True)
class FlowPolicy:
    history_seconds: float = .4
    max_history_seconds: float = .75
    max_gap_seconds: float = .10
    fb_error_pixels: float = 1.5
    max_lk_error: float = 30.
    max_points: int = 60
    minimum_points: int = 6
    minimum_survival: float = .35
    minimum_relative_motion: float = 2.
    minimum_endpoint_fraction: float = .6

    def validate(self):
        for name, value in asdict(self).items():
            if finite(value,name) <= 0:
                raise ValueError('Positive flow parameter required')
        if (type(self.max_points) is not int or type(self.minimum_points) is not int
                or self.minimum_points > self.max_points or self.history_seconds > self.max_history_seconds
                or not 0 < self.minimum_survival <= 1 or not .5 < self.minimum_endpoint_fraction <= 1):
            raise ValueError('Invalid flow policy')
        return self


def select_seed(segment: dict, policy=FlowPolicy()):
    """Choose a real earlier measurement, NOT a predicted box or a future crop."""
    policy.validate()
    last = segment['rows'][-1]['pts']
    rows = [r for r in segment['rows'] if .1 <= last-r['pts'] <= policy.max_history_seconds+1e-9]
    return min(rows, key=lambda r: (abs(last-r['pts']-policy.history_seconds), r['pts'])) if rows else None


def flow_crop(seed_box, last_box, size):
    w, h = size
    a, b = box(seed_box), box(last_box)
    union = [min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]
    margin = .75*max((union[2]-union[0])*w, (union[3]-union[1])*h)
    return [max(0,int(math.floor(union[0]*w-margin))),max(0,int(math.floor(union[1]*h-margin))),
            min(w,int(math.ceil(union[2]*w+margin))),min(h,int(math.ceil(union[3]*h+margin)))]


def _mask_rectangle(mask, b, origin, size, value):
    w,h = size
    x,y = origin
    x1,y1,x2,y2 = [b[0]*w-x,b[1]*h-y,b[2]*w-x,b[3]*h-y]
    x1,y1 = max(0,int(math.floor(x1))),max(0,int(math.floor(y1)))
    x2,y2 = min(mask.shape[1],int(math.ceil(x2))),min(mask.shape[0],int(math.ceil(y2)))
    if x1<x2 and y1<y2:
        mask[y1:y2,x1:x2]=value


class ShortImageFlow:
    """Forward/backward checked LK on a fixed native-resolution crop.

    Never reseed after loss; once a feature is lost it stays lost. Background
    motion is recorded separately to avoid interpreting static gate points as
    continued motion of the intended target. Ambiguous flow is support only.
    """
    def __init__(self, gray, seed, size, origin, candidates, policy=FlowPolicy()):
        import cv2
        import numpy as np
        self.policy = policy.validate()
        if gray.dtype != np.uint8 or gray.ndim != 2:
            raise ValueError('Native grayscale uint8 crop required')
        self.size, self.origin, self.seed = size, origin, seed
        mask = np.zeros_like(gray)
        b = box(seed['bbox'])
        dx,dy=.1*(b[2]-b[0]),.1*(b[3]-b[1])
        _mask_rectangle(mask,[b[0]+dx,b[1]+dy,b[2]-dx,b[3]-dy],origin,size,255)
        self.seed_competition = False
        for candidate in candidates:
            if candidate['cache_index'] != seed['cache_index']:
                if intersection(b,candidate['bbox']) > 0:
                    self.seed_competition = True
                _mask_rectangle(mask,candidate['bbox'],origin,size,0)
        background = np.full_like(gray,255)
        for candidate in candidates:
            _mask_rectangle(background,expanded(candidate['bbox'],.15),origin,size,0)
        _mask_rectangle(background,expanded(b,.15),origin,size,0)
        self.p = self._corners(gray,mask)
        self.bg = self._corners(gray,background)
        self.p0,self.bg0 = self.p.copy(),self.bg.copy()
        # IDs are allocated once at the seed and filtered with their points.
        # Array position after dropout is never a correspondence identity.
        self.point_ids = np.arange(len(self.p),dtype=int)
        self.background_ids = np.arange(len(self.bg),dtype=int)
        self.initial_count = len(self.p)
        self.prev = gray.copy()
        self.last_pts = finite(seed['pts'])
        self.records = []
        self.broken = False
        self._record(seed['pts'],seed['frame_index'])

    def _corners(self, gray, mask):
        import cv2
        import numpy as np
        points=cv2.goodFeaturesToTrack(gray,maxCorners=self.policy.max_points,qualityLevel=.02,
                                       minDistance=3,mask=mask,blockSize=3)
        return np.empty((0,2),dtype=np.float32) if points is None else points.reshape(-1,2)

    def _advance(self, current, points):
        import cv2
        import numpy as np
        if not len(points):
            return points.copy(),np.zeros(0,dtype=bool)
        opts=dict(winSize=(21,21),maxLevel=3,
                  criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
        q,st,err=cv2.calcOpticalFlowPyrLK(self.prev,current,points.reshape(-1,1,2),None,**opts)
        if q is None or st is None or err is None:
            return points.copy(),np.zeros(len(points),dtype=bool)
        coords=q.reshape(-1,2)
        finite_q=np.isfinite(coords).all(axis=1)
        safe=coords.copy();safe[~finite_q]=points[~finite_q]
        back,bst,_=cv2.calcOpticalFlowPyrLK(current,self.prev,safe.reshape(-1,1,2),None,**opts)
        if back is None or bst is None:
            return coords,np.zeros(len(points),dtype=bool)
        good=(st.ravel()==1)&(bst.ravel()==1)&finite_q&np.isfinite(back.reshape(-1,2)).all(axis=1)
        good &= np.linalg.norm(back.reshape(-1,2)-points,axis=1) <= self.policy.fb_error_pixels
        good &= np.isfinite(err.ravel()) & (err.ravel() <= self.policy.max_lk_error)
        good &= (coords[:,0]>=0)&(coords[:,0]<current.shape[1])&(coords[:,1]>=0)&(coords[:,1]<current.shape[0])
        return coords,good

    def update(self, gray, pts, index):
        if gray.shape != self.prev.shape or gray.dtype != self.prev.dtype:
            raise ValueError('Native crop shape/type changed')
        pts=finite(pts)
        if pts <= self.last_pts:
            raise ValueError('Increasing original PTS required')
        if pts-self.last_pts > self.policy.max_gap_seconds+1e-9:
            self.p,self.p0=self.p[:0],self.p0[:0]
            self.bg,self.bg0=self.bg[:0],self.bg0[:0]
            self.point_ids=self.point_ids[:0]
            self.background_ids=self.background_ids[:0]
            self.broken=True
        else:
            q,good=self._advance(gray,self.p);self.p,self.p0=q[good],self.p0[good]
            self.point_ids=self.point_ids[good]
            q,good=self._advance(gray,self.bg);self.bg,self.bg0=q[good],self.bg0[good]
            self.background_ids=self.background_ids[good]
        self.prev=gray.copy();self.last_pts=pts
        return self._record(pts,index)

    def _record(self, pts, index):
        import numpy as np
        bg=(np.median(self.bg-self.bg0,axis=0) if len(self.bg)>=self.policy.minimum_points else None)
        displacement=(np.median(self.p-self.p0,axis=0) if len(self.p) else None)
        relative=displacement-bg if displacement is not None and bg is not None else None
        row=dict(pts=pts,frame_index=index,point_count=len(self.p),
                 survival_fraction=len(self.p)/self.initial_count if self.initial_count else 0.,
                 points_original_pixels=(self.p+np.asarray(self.origin)).tolist(),
                 point_ids=self.point_ids.tolist(),
                 background_point_ids=self.background_ids.tolist(),
                 background_points_original_pixels=(self.bg+np.asarray(self.origin)).tolist(),
                 background_point_count=len(self.bg),
                 background_displacement=None if bg is None else bg.tolist(),
                 relative_displacement=None if relative is None else relative.tolist(),
                 image_correspondences_only=True)
        self.records.append(row)
        return row

    def summary(self, last_observed_pts, end_candidates):
        import numpy as np
        last=self.records[-1]
        before=[r for r in self.records if r['pts']<=last_observed_pts+1e-9]
        moved=any(r['relative_displacement'] is not None and
                  math.hypot(*r['relative_displacement'])>=self.policy.minimum_relative_motion for r in before)
        tracked=last['point_count']>=self.policy.minimum_points and last['survival_fraction']>=self.policy.minimum_survival
        pts=np.asarray(last['points_original_pixels'],dtype=float).reshape(-1,2)
        matches=[]
        w,h=self.size
        for c in end_candidates:
            if c['score']<.25 or not len(pts):
                continue
            b=c['bbox']
            inside=(pts[:,0]>=b[0]*w)&(pts[:,0]<=b[2]*w)&(pts[:,1]>=b[1]*h)&(pts[:,1]<=b[3]*h)
            fraction=float(inside.mean())
            if fraction>=self.policy.minimum_endpoint_fraction:
                matches.append(dict(cache_index=c['cache_index'],track_ids=c['track_ids'],
                    assignment=c['assignment'],point_fraction=fraction,bbox=c['bbox']))
        if self.initial_count < self.policy.minimum_points:
            outcome='insufficient_seed_features'
        elif self.broken:
            outcome='source_gap_flow_not_used'
        elif not tracked:
            outcome='feature_continuation_unresolved'
        elif last['background_displacement'] is None:
            outcome='background_reference_unresolved'
        elif not moved:
            outcome='static_or_background_ambiguous'
        elif self.seed_competition or len(matches)>1:
            outcome='overlap_or_multiple_targets_ambiguous'
        elif len(matches)==1:
            outcome='image_continuation_supported_review_only'
        else:
            outcome='feature_path_without_detector_confirmation'
        return dict(outcome=outcome,seed_pts=self.seed['pts'],seed_frame_index=self.seed['frame_index'],
            initial_points=self.initial_count,endpoint_points=last['point_count'],
            preloss_relative_motion=moved,seed_competition=self.seed_competition,
            endpoint_background_points=last['background_point_count'],
            endpoint_background_displacement=last['background_displacement'],
            endpoint_matches=matches,frames=len(self.records),evidence_until_pts=last['pts'],
            cancel_alarm=False,identity_verified=False,baseline_alert_unchanged=True,
            warning='Flow loss is not intrusion; survival is not identity or a negative intrusion verdict.')
