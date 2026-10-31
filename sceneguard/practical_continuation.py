"""EXP-0040: soft short-image continuity, not person identity or intrusion truth.

No blanket overlap/static/partial-body veto. Proposed loss-notification filtering
uses image correspondences, not proximity alone. Baseline events stay immutable.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
import numpy as np


@dataclass(frozen=True)
class PracticalPolicy:
    history_seconds: float = 3.0
    seed_count: int = 3
    max_points: int = 60
    min_points: int = 3
    fb_error: float = 1.5
    lk_error: float = 30.0
    max_frame_gap: float = .10
    score_threshold: float = .70

    def validate(self):
        values = asdict(self)
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values.values()):
            raise ValueError('Positive finite policy values required')
        if any(type(values[k]) is not int for k in ('seed_count','max_points','min_points')):
            raise ValueError('Integer counts required')
        if not 1 <= self.seed_count <= 3 or not 3 <= self.min_points <= self.max_points or self.score_threshold > 1:
            raise ValueError('Invalid bounded policy')
        return self


def pixels(bbox, size):
    b = np.asarray(bbox, dtype=float)
    if b.shape != (4,) or not np.isfinite(b).all() or not (0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1):
        raise ValueError('Normalized nonempty actual bbox required')
    return b * np.tile(size, 2)


def contains(points, bbox, size):
    b = pixels(bbox, size)
    return ((points[:, 0] >= b[0]) & (points[:, 0] <= b[2]) &
            (points[:, 1] >= b[1]) & (points[:, 1] <= b[3]))


def overlap_fraction(bbox, candidates, own, size):
    b = pixels(bbox, size); area = (b[2]-b[0])*(b[3]-b[1])
    ratios = []
    for c in candidates:
        if c['cache_index'] == own:
            continue
        a = pixels(c['bbox'], size)
        ratios.append(max(0., min(a[2],b[2])-max(a[0],b[0])) *
                      max(0., min(a[3],b[3])-max(a[1],b[1])) / area)
    return max(ratios, default=0.)


def seed_pool(rows, policy):
    """Candidate frames before loss; no labels or future endpoints used for selection."""
    last = rows[-1]['pts']; selected = []
    for r in rows:
        if .10 <= last-r['pts'] <= policy.history_seconds+1e-9:
            if not selected or r['pts']-selected[-1]['pts'] >= .24:
                selected.append(r)
    return selected


def corners(gray, row, candidates, size, policy):
    import cv2
    b = pixels(row['bbox'], size); x1,y1,x2,y2 = b
    dx,dy = .1*(x2-x1), .1*(y2-y1)
    mask = np.zeros_like(gray)
    mask[int(y1+dy):math.ceil(y2-dy), int(x1+dx):math.ceil(x2-dx)] = 255
    # Prefer exclusive pixels but retain overlapped pixels as a second pool.
    exclusive = mask.copy()
    for c in candidates:
        if c['cache_index'] != row['cache_index']:
            a = pixels(c['bbox'], size)
            exclusive[int(a[1]):math.ceil(a[3]),int(a[0]):math.ceil(a[2])] = 0
    points = []
    for m, cap in ((exclusive, max(3, policy.max_points*2//3)), (mask, policy.max_points)):
        for p in points:
            cv2.circle(m, tuple(np.rint(p).astype(int)), 3, 0, -1)
        found = cv2.goodFeaturesToTrack(gray, maxCorners=cap, qualityLevel=.02,
                                       minDistance=3, mask=m, blockSize=3)
        if found is not None:
            points.extend(found.reshape(-1,2).tolist())
        if len(points) >= policy.max_points:
            break
    return np.asarray(points[:policy.max_points], dtype=np.float32).reshape(-1,2)


def choose_seeds(rows, grays, catalogs, size, policy):
    candidates = []
    areas = [(r['bbox'][2]-r['bbox'][0])*(r['bbox'][3]-r['bbox'][1]) for r in rows]
    typical = float(np.median(areas))
    for r in seed_pool(rows, policy):
        i = r['frame_index']; pts = corners(grays[i], r, catalogs[i], size, policy)
        b = pixels(r['bbox'], size)
        area = (r['bbox'][2]-r['bbox'][0])*(r['bbox'][3]-r['bbox'][1])
        stability = math.exp(-abs(math.log(area/max(typical, 1e-12))))
        overlap = overlap_fraction(r['bbox'], catalogs[i], r['cache_index'], size)
        rank = .65*min(1., len(pts)/20) + .25*stability + .10*min(1., (b[2]-b[0])*(b[3]-b[1])/2500) - .10*overlap
        candidates.append((rank, r, pts, overlap))
    chosen = []
    for item in sorted(candidates, key=lambda x:(-x[0], -x[1]['pts'])):
        if all(abs(item[1]['pts']-old[1]['pts']) >= .4 for old in chosen):
            chosen.append(item)
        if len(chosen) == policy.seed_count:
            break
    return chosen


def patch_similarity(a, p, b, q):
    import cv2
    x = cv2.getRectSubPix(a,(11,11),tuple(map(float,p))).astype(float).ravel()
    y = cv2.getRectSubPix(b,(11,11),tuple(map(float,q))).astype(float).ravel()
    x -= x.mean(); y -= y.mean()
    norm = np.linalg.norm(x)*np.linalg.norm(y)
    return float(np.clip(np.dot(x,y)/norm, 0, 1)) if norm > 1e-6 else 0.


def trace(gray_frames, stamps, seed, points, rows, size, policy):
    """Permanent point IDs, forward/backward checks, no re-seeding after loss."""
    import cv2
    start = seed['frame_index']; last_i = rows[-1]['frame_index']
    observed = {r['frame_index']:r for r in rows}
    p = points.copy(); ids = np.arange(len(p)); anchors = points.copy()
    anchor_gray = gray_frames[start]; records = []
    membership = np.zeros(len(points)); checks = np.zeros(len(points))
    previous = start
    for i in sorted(k for k in gray_frames if k >= start):
        gray = gray_frames[i]
        if gray.dtype != np.uint8 or gray.ndim != 2 or gray.shape != gray_frames[start].shape:
            raise ValueError('Unchanged native grayscale dimensions required')
        if i != start:
            dt = stamps[i]-stamps[previous]
            if dt <= 0:
                raise ValueError('Increasing frame times required')
            if dt > policy.max_frame_gap+1e-9:
                p,ids = p[:0],ids[:0]
            if len(p):
                opts = dict(winSize=(21,21), maxLevel=3,
                    criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
                q,s,e = cv2.calcOpticalFlowPyrLK(gray_frames[previous],gray,p[:,None],None,**opts)
                if q is None or s is None or e is None:
                    p,ids = p[:0],ids[:0]
                else:
                    q = q.reshape(-1,2); safe = q.copy()
                    safe[~np.isfinite(safe).all(axis=1)] = p[~np.isfinite(safe).all(axis=1)]
                    back,bs,_ = cv2.calcOpticalFlowPyrLK(gray,gray_frames[previous],safe[:,None],None,**opts)
                    good = np.zeros(len(p),dtype=bool)
                    if back is not None and bs is not None:
                        good = ((s.ravel()==1)&(bs.ravel()==1)&np.isfinite(q).all(axis=1)&
                            np.isfinite(back.reshape(-1,2)).all(axis=1)&np.isfinite(e.ravel())&
                            (e.ravel()<=policy.lk_error)&
                            (np.linalg.norm(back.reshape(-1,2)-p,axis=1)<=policy.fb_error)&
                            (q[:,0]>=5)&(q[:,0]<size[0]-5)&(q[:,1]>=5)&(q[:,1]<size[1]-5))
                    p,ids = q[good],ids[good]
        if i <= last_i and i in observed:
            membership[ids] += contains(p, observed[i]['bbox'], size)
            checks[ids] += 1
        if i == last_i:
            anchors[ids] = p; anchor_gray = gray
        records.append(dict(frame_index=i, pts=stamps[i], ids=ids.tolist(), points=p.tolist()))
        previous = i
    quality = np.asarray([patch_similarity(anchor_gray,anchors[k],gray_frames[previous],q)
                          for k,q in zip(ids,p)])
    return dict(records=records, ids=ids, points=p, anchors=anchors[ids],
                patch_quality=quality, source_membership=membership[ids]/np.maximum(1,checks[ids]),
                initial_points=len(points))


def evidence_score(*, appearance, coverage, persistence, coherence, count,
                   source_membership, overlap, ambiguity, crossing):
    """Heuristic support, NOT a calibrated probability. Missing pieces are not vetoes."""
    raw = (.30*appearance + .25*coverage + .15*persistence + .10*coherence +
           .10*min(1.,count/8) + .10*source_membership - .06*overlap -
           .18*ambiguity - .45*crossing)
    return float(np.clip(raw,0,1))


def assess(path, catalogs, size, line, last_pts, overlap, policy):
    p = path['points']; end = path['records'][-1]['frame_index']
    result = dict(score=0., recommendation='keep', reason='no_visual_support',
                  point_count=len(p), initial_points=path['initial_points'],
                  endpoint_cache_index=None, identity_verified=False, probability=None)
    if len(p) < policy.min_points:
        return result
    candidates = []
    for c in catalogs[end]:
        if c['score'] < .20:
            continue
        idx = np.flatnonzero(contains(p,c['bbox'],size))
        if len(idx) < policy.min_points:
            continue
        ids = set(path['ids'][idx].tolist())
        tail = [r for r in path['records'] if r['pts']>last_pts and r['pts']>=path['records'][-1]['pts']-.3]
        supported = []
        for r in tail:
            arr = np.asarray(r['points'],dtype=float).reshape(-1,2)
            take = [j for j,k in enumerate(r['ids']) if k in ids]
            supported.append(max((float(contains(arr[take],d['bbox'],size).mean())
                for d in catalogs[r['frame_index']] if d['score']>=.20), default=0.) if take else 0.)
        displacement = p[idx]-path['anchors'][idx]
        spread = np.median(np.linalg.norm(displacement-np.median(displacement,axis=0),axis=1))
        coherence = float(np.exp(-spread/6.))
        crossing = 0.
        if line:
            a,b = np.asarray(line,dtype=float)*np.asarray(size)
            v=b-a; n=np.linalg.norm(v)
            if n <= 1e-9: raise ValueError('Nondegenerate line required')
            def side(x): return (v[0]*(x[:,1]-a[1])-v[1]*(x[:,0]-a[0]))/n
            s,t = side(path['anchors'][idx]),side(p[idx])
            crossing = float(np.mean((s*t<0)&(np.abs(s)>3)&(np.abs(t)>3)))
        components = dict(appearance=float(np.median(path['patch_quality'][idx])),
            coverage=len(idx)/len(p), persistence=float(np.mean(supported)) if supported else 0.,
            coherence=coherence, count=len(idx), source_membership=float(np.mean(path['source_membership'][idx])),
            overlap=float(overlap), ambiguity=0., crossing=crossing)
        candidates.append(dict(candidate=c, indices=idx.tolist(), components=components,
                               score=evidence_score(**components)))
    candidates.sort(key=lambda x:-x['score'])
    if not candidates:
        return result
    best=candidates[0]
    # Boxes supported by the same points are not counted as distinct people.
    for other in candidates[1:]:
        a,b=set(best['indices']),set(other['indices'])
        if len(a&b)/len(a|b)<.5 and best['score']-other['score']<.10:
            best['components']['ambiguity']=1.
    score=evidence_score(**best['components'])
    result.update(score=score, components=best['components'],
        endpoint_cache_index=best['candidate']['cache_index'],
        endpoint_track_ids=best['candidate']['track_ids'], endpoint_bbox=best['candidate']['bbox'],
        supported_points=best['indices'], evidence_until_pts=path['records'][-1]['pts'],
        recommendation='review_only' if score>=policy.score_threshold else 'keep',
        reason='image_continuation' if score>=policy.score_threshold else 'weak_or_conflicting_support')
    return result


def notification_partition(events, audits):
    """Partition original normalized alerts; do not renumber or re-hash their IDs."""
    decisions={r['source_pointer']:r for r in audits}
    active, review = [], []
    for event in events:
        audit=decisions.get(event['source_ref']['source_pointer'])
        eligible=(event['source_ref']['collection']=='events' and
            event['source_event'].get('reason')=='recent_gate_presence_then_loss')
        independent=any(other['decision_time_pts']<=event['decision_time_pts'] and
            bool(set(other['track_ids'])&set(event['track_ids'])) and
            other['source_event'].get('reason')!='recent_gate_presence_then_loss'
            for other in events)
        if eligible and not independent and audit and audit['recommendation']=='review_only':
            if abs(audit['evidence_until_pts']-event['decision_time_pts'])>1e-6:
                raise ValueError('Evidence must end at the original notification time')
            if audit['raw_id'] not in event['track_ids']:
                raise ValueError('Audit target differs from event')
            review.append(deepcopy(event))
        else:
            active.append(deepcopy(event))
    return active,review
