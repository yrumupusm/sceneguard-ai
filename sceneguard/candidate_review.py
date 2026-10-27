"""Causal, optional post-candidate review; never generates or edits a candidate."""
from copy import deepcopy
import math

CONFIG = dict(lookback=.2, wait=.2, pair_window=.2, scale=1.5, edge=.3, max_gap=.1)
EPS = 1e-9


def change(a, b):
    h1, h2 = a[3]-a[1], b[3]-b[1]
    w1, w2 = a[2]-a[0], b[2]-b[0]
    top, bottom = (b[1]-a[1])/min(h1,h2), (b[3]-a[3])/min(h1,h2)
    return dict(height_ratio=max(h1,h2)/min(h1,h2),
                width_ratio=max(w1,w2)/min(w1,w2), top_shift=top,
                bottom_shift=bottom, edge_difference=abs(bottom-top))


class CandidateReview:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.history = []
        self.pending = []
        self.last_pts = None
        self.closed = False

    def step(self, pts, observations, candidates):
        if self.closed or not math.isfinite(pts) or (self.last_pts is not None and pts <= self.last_pts):
            raise ValueError('Need increasing finite PTS on an open stream')
        if any(abs(e['emitted_at_pts']-pts)>EPS for e in candidates):
            raise ValueError('Only candidates arriving at this PTS may be submitted')
        self.last_pts = pts
        if not self.enabled:
            return deepcopy(candidates)
        actual = {}
        for r in observations:
            if not r.get('observed') or not r.get('confirmed', True):
                continue
            b=r['bbox']
            if len(b)!=4 or not all(math.isfinite(v) for v in b) or not (b[0]<b[2] and b[1]<b[3]):
                raise ValueError('Invalid actual bbox')
            if r['track_id'] in actual:
                raise ValueError('Duplicate observed track ID')
            actual[r['track_id']] = deepcopy(b)
        self.history.append((pts,actual))
        updates=[]
        for e in candidates:
            self.pending.append(deepcopy(e))
            updates.append(dict(original=deepcopy(e), status='pending', status_at_pts=pts,
                                decision_pts=None, last_observation_pts=None, additional_wait=0.))
        remaining=[]
        for e in self.pending:
            if pts+EPS >= e['emitted_at_pts']+CONFIG['wait']:
                updates.append(self.evaluate(e,pts))
            else:
                remaining.append(e)
        self.pending=remaining
        return updates

    def evaluate(self, event, pts, eof=False):
        start=event['emitted_at_pts']-CONFIG['lookback']
        preceding=[i for i,(t,_) in enumerate(self.history) if t<=start+EPS]
        idx=preceding[-1] if preceding else 0
        window=self.history[idx:]
        assert all(t<=pts+EPS for t,_ in window)
        reasons=[]
        if not preceding or start-window[0][0]>CONFIG['max_gap']+EPS:
            reasons.append('missing_lookback')
        tid=event['track_id']
        missing=[t for t,obs in window if tid not in obs]
        if missing:reasons.append('missing_observation')
        if any(b[0]-a[0]>CONFIG['max_gap']+EPS for a,b in zip(window,window[1:])):
            reasons.append('pts_gap')
        if eof:reasons.append('end_before_deadline')
        actual=[(t,obs[tid]) for t,obs in window if tid in obs]
        pairs=[]
        for i,(t,a) in enumerate(actual):
            for u,b in actual[i+1:]:
                if u-t>CONFIG['pair_window']+EPS:break
                m=change(a,b)
                abnormal=(m['height_ratio']>=CONFIG['scale'] and m['edge_difference']>=CONFIG['edge']) or m['width_ratio']>=CONFIG['scale']
                pairs.append(dict(before_pts=t,after_pts=u,**m,abnormal=abnormal))
        if not pairs:reasons.append('no_comparable_pair')
        abnormal=[p for p in pairs if p['abnormal']]
        status='insufficient' if reasons else 'deferred' if abnormal else 'passed'
        return dict(original=deepcopy(event),status=status,status_at_pts=pts,decision_pts=pts,
                    last_observation_pts=actual[-1][0] if actual else None,
                    additional_wait=pts-event['emitted_at_pts'], requested_range=[start,event['emitted_at_pts']+CONFIG['wait']],
                    used_range=[actual[0][0],actual[-1][0]] if actual else None,
                    missing_pts=missing,reasons=reasons,anomaly_detected=bool(abnormal),
                    abnormal_pairs=abnormal,pairs=pairs,observations=[dict(pts=t,bbox=b) for t,b in actual])

    def finish(self):
        if self.closed:raise ValueError('Already closed')
        self.closed=True
        updates=[self.evaluate(e,self.last_pts,eof=True) for e in self.pending]
        self.pending=[]
        return updates
