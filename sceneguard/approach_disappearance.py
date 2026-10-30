"""EXP-0034: measured approach/exit/loss evidence; never an identity oracle.

Offline add-on for existing gap/frames.jsonl. Predictions are NOT measurements.
All defaults are initial heuristics, not calibrated intrusion probabilities.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import hashlib
import json
import math
import statistics as st


@dataclass(frozen=True)
class Policy:
    loss_wait: float = 1.0
    direction_window: float = 1.0
    max_direction_step: float = 0.25
    min_motion_pixels: float = 3.0
    scale_jump: float = 1.8
    stable_seconds: float = 0.2
    stable_observations: int = 3
    near_line_heights: float = 0.8
    pair_seconds: float = 6.0
    pair_distance_heights: float = 3.0

    def validate(self):
        for k, v in asdict(self).items():
            if type(v) not in (int, float) or not math.isfinite(v) or v <= 0:
                raise ValueError(f'Invalid policy {k}')
        if type(self.stable_observations) is not int or self.stable_observations < 2 or self.scale_jump <= 1:
            raise ValueError('Invalid observation count / scale ratio')
        return self


def polygon(point, poly):
    x, y = point
    inside = False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ax, ay = a
        bx, by = b
        cross = (bx-ax)*(y-ay)-(by-ay)*(x-ax)
        if abs(cross) < 1e-9 and min(ax,bx)-1e-9 <= x <= max(ax,bx)+1e-9 and min(ay,by)-1e-9 <= y <= max(ay,by)+1e-9:
            return True
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside


def validate_scene(s):
    if len(s['source_size']) != 2 or any(type(v) is not int or v <= 0 for v in s['source_size']):
        raise ValueError('Original pixel width/height required')
    if len(s['line']) != 2 or s['line'][0] == s['line'][1]:
        raise ValueError('Nondegenerate finite line required')
    polys = [s['approach_polygon'], s['zones']['outside'], s['zones']['inside']]
    for o in s.get('occlusions', []):
        if o['from_side'] not in s['zones'] or o['to_side'] not in s['zones'] or o['from_side'] == o['to_side']:
            raise ValueError('Occlusion requires distinct known from/to sides')
        if not o.get('id'):
            raise ValueError('Occlusion label required')
        polys.append(o['polygon'])
    for poly in [s['line']] + polys:
        if any(len(p) != 2 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= 1 for v in p) for p in poly):
            raise ValueError('Normalized finite scene coordinates required')
    for p in polys:
        if len(p) < 3 or abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))) < 1e-9:
            raise ValueError('Degenerate scene polygon')
    if not set(s['directions']) <= {'outside_to_inside', 'inside_to_outside'}:
        raise ValueError('Invalid alarm direction')


def center(row, size, fraction=0.5):
    x1,y1,x2,y2 = row['bbox']
    return ((x1+x2)*size[0]/2, (y1+fraction*(y2-y1))*size[1])


def zone(row, scene):
    # Same proxy as prior regions: not true feet / reconstructed ground position.
    x1,y1,x2,y2 = row['bbox']
    pts=[(x1+f*(x2-x1),y1+0.65*(y2-y1)) for f in (.35,.5,.65)]
    found=[name for name, p in scene['zones'].items() if sum(polygon(q,p) for q in pts)>=2]
    return found[0] if len(found)==1 else None


def signed_distance(p, scene):
    w,h=scene['source_size']
    (ax,ay),(bx,by)=[(x*w,y*h) for x,y in scene['line']]
    dx,dy=bx-ax,by-ay
    return (dx*(p[1]-ay)-dy*(p[0]-ax))/math.hypot(dx,dy)


def line_distance(p, scene):
    w,h=scene['source_size']
    a,b=[(x*w,y*h) for x,y in scene['line']]
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.dist(p,(a[0]+t*dx,a[1]+t*dy))


def measured_segments(frames, policy):
    """Preserve raw IDs; split actual observation gaps, not extrapolated tracks."""
    segments=[]
    active={}
    previous=-math.inf
    for i,frame in enumerate(frames):
        pts=frame['pts']
        if type(pts) not in (int,float) or not math.isfinite(pts) or pts<=previous:
            raise ValueError('Strictly increasing finite source PTS required')
        previous=pts
        seen=set()
        for d in frame['detections']:
            if not d.get('observed',False) or not d.get('confirmed',True):
                continue
            tid=d['track_id']
            b=d['bbox']
            if type(tid) is not int or tid<0 or tid in seen:
                raise ValueError('Unique nonnegative raw IDs required')
            if len(b)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in b) or not (0<=b[0]<b[2]<=1 and 0<=b[1]<b[3]<=1):
                raise ValueError('Invalid observed bbox')
            seen.add(tid)
            if tid not in active or pts-active[tid]['rows'][-1]['pts']>policy.loss_wait:
                seg={'id':f's{len(segments)+1:04d}','raw_id':tid,'rows':[]}
                segments.append(seg)
                active[tid]=seg
            active[tid]['rows'].append({'pts':pts,'frame_index':i,'cache_index':d.get('cache_index'),'bbox':b})
    return segments


def motion(rows, size, policy):
    tail=[r for r in rows if rows[-1]['pts']-r['pts']<=policy.direction_window+1e-9]
    vectors=[]
    rejected=0
    for a,b in zip(tail,tail[1:]):
        dt=b['pts']-a['pts']
        aw,ah=a['bbox'][2]-a['bbox'][0],a['bbox'][3]-a['bbox'][1]
        bw,bh=b['bbox'][2]-b['bbox'][0],b['bbox'][3]-b['bbox'][1]
        if dt>policy.max_direction_step or max(aw/bw,bw/aw,ah/bh,bh/ah)>policy.scale_jump:
            rejected+=1
            continue
        p,q=center(a,size),center(b,size)
        vectors.append(((q[0]-p[0])/dt,(q[1]-p[1])/dt))
    span=tail[-1]['pts']-tail[0]['pts']
    velocity=[st.median([v[k] for v in vectors]) for k in (0,1)] if vectors else [0.,0.]
    speed=math.hypot(*velocity)
    consistency=sum(v[0]*velocity[0]+v[1]*velocity[1]>0 for v in vectors)/len(vectors) if vectors and speed else 0.
    reliable=len(vectors)>=2 and speed*span>=policy.min_motion_pixels and consistency>=0.65
    return {'velocity_pixels_per_second':velocity,'reliable':reliable,
            'span_seconds':span,'usable_steps':len(vectors),'rejected_steps':rejected,
            'consistency':consistency,'origin_pixels':list(center(rows[-1],size))}


def angle_degrees(velocity, displacement):
    a,b=math.hypot(*velocity),math.hypot(*displacement)
    if a<1e-9 or b<1e-9:
        return None
    return math.degrees(math.acos(max(-1.,min(1.,sum(x*y for x,y in zip(velocity,displacement))/(a*b)))))


def analyze(frames, scene, policy=Policy()):
    policy.validate()
    validate_scene(scene)
    if not frames:
        raise ValueError('Empty source')
    segments=measured_segments(frames,policy)
    end=frames[-1]['pts']
    w,h=scene['source_size']
    losses=[]
    events=[]
    for seg in segments:
        rows=seg['rows']
        origin=stable=pending=None
        streak=[]
        entered=False
        crossed=False
        gap_uncertain=False
        exited=False
        previous=None
        for row in rows:
            z=zone(row,scene)
            point=center(row,(1,1),.65)
            in_roi=polygon(point,scene['approach_polygon'])
            if previous is not None and row['pts']-previous['pts']>policy.max_direction_step:
                streak=[]
                gap_uncertain=True
            entered=entered or in_roi
            if z is None:
                streak=[]
                pending=None
            elif z!=pending:
                pending=z
                streak=[row]
            else:
                streak.append(row)
            if len(streak)>=policy.stable_observations and streak[-1]['pts']-streak[0]['pts']>=policy.stable_seconds-1e-9:
                if origin is None:
                    origin=z
                if stable is not None and stable!=z and entered:
                    # Require observations near the FINITE gate, not merely an infinite line.
                    height=st.median((r['bbox'][3]-r['bbox'][1])*h for r in rows)
                    near=any(line_distance(center(r,(w,h)),scene)<=max(12,height*policy.near_line_heights)
                             for r in rows if r['pts']<=row['pts'])
                    direction=f'{stable}_to_{z}'
                    if near:
                        crossed=True  # Do not erase a real side transition on a later return.
                    if near and direction in scene['directions']:
                        events.append({'segment':seg['id'],'raw_id':seg['raw_id'],'pts':row['pts'],
                                       'status':'침입 의심','reason':'observed_side_transition',
                                       'direction':direction,'identity_verified':False})
                        crossed=True
                stable=z
            if entered and not in_roi and previous is not None:
                was_in=polygon(center(previous,(1,1),.65),scene['approach_polygon'])
                if was_in:
                    if stable==origin and z==origin and not crossed and not gap_uncertain:
                        events.append({'segment':seg['id'],'raw_id':seg['raw_id'],'pts':row['pts'],
                                       'status':'침입 아님','reason':'observed_same_side_exit',
                                       'scope':'this_observed_episode_only'})
                    exited=True
            previous=row
        mv=motion(rows,(w,h),policy)
        last=rows[-1]
        loss={'segment':seg['id'],'raw_id':seg['raw_id'],'last_pts':last['pts'],
              'origin_side':origin,'motion':mv,'right_censored':end-last['pts']<policy.loss_wait,
              'status':'판단 불가','reason':'unresolved_loss','confirmed_intrusion':False,
              'last_bbox':last['bbox'],'ever_crossed':crossed}
        # Ending the file is not a disappearance. An observed exit is not a loss.
        if loss['right_censored']:
            loss['reason']='recording_ended_before_loss_wait'
        elif exited and not polygon(center(last,(1,1),.65),scene['approach_polygon']):
            loss['reason']='observed_exit_not_disappearance'
        elif origin and entered and mv['reliable']:
            anchor=next((r for r in rows if zone(r,scene)==origin),None)
            sign=math.copysign(1.,signed_distance(center(anchor,(w,h)),scene))
            p=center(last,(w,h))
            v=mv['velocity_pixels_per_second']
            projected=(p[0]+v[0],p[1]+v[1])
            toward=(signed_distance(projected,scene)-signed_distance(p,scene))*sign < -policy.min_motion_pixels
            height=st.median((r['bbox'][3]-r['bbox'][1])*h for r in rows[-10:])
            near=line_distance(p,scene)<=max(12.,height*policy.near_line_heights)
            occ=[o for o in scene.get('occlusions',[]) if o['from_side']==origin
                 and f"{o['from_side']}_to_{o['to_side']}" in scene['directions']
                 and polygon(center(last,(1,1),.65),o['polygon'])]
            loss.update(toward_boundary=toward,near_finite_line=near,occlusions=[o['id'] for o in occ])
            if toward and near and occ:
                loss.update(status='침입 의심',reason='approach_to_known_occlusion_loss')
                events.append({'segment':seg['id'],'raw_id':seg['raw_id'],
                               'pts':last['pts']+policy.loss_wait,'status':'침입 의심',
                               'reason':loss['reason'],'last_observed_pts':last['pts'],
                               'reappearance_required':False,'identity_verified':False})
        losses.append(loss)
    pairs=[]
    by_loss={l['segment']:l for l in losses}
    for a in segments:
        last=a['rows'][-1]
        p=center(last,(w,h))
        height=st.median((r['bbox'][3]-r['bbox'][1])*h for r in a['rows'][-10:])
        for b in segments:
            dt=b['rows'][0]['pts']-last['pts']
            if a['id']==b['id'] or not 0<dt<=policy.pair_seconds:
                continue
            q=center(b['rows'][0],(w,h))
            distance=math.dist(p,q)
            if distance>max(60.,height*policy.pair_distance_heights):
                continue
            mv=by_loss[a['id']]['motion']
            angle=angle_degrees(mv['velocity_pixels_per_second'],(q[0]-p[0],q[1]-p[1])) if mv['reliable'] else None
            pairs.append({'pair_id':a['id']+'__'+b['id'],'before':a['id'],'after':b['id'],
                          'gap_seconds':dt,'distance_pixels':distance,'angle_degrees':angle,
                          'in_forward_90':None if angle is None else angle<=90.+1e-9,
                          'same_raw_id':a['raw_id']==b['raw_id'],'decision':'not_compared',
                          'identity_verified':False})
    # Angle is an annotation: no pair is rejected or accepted because of +/-90.
    for loss in losses:
        loss['possible_new_ids']=[p['after'] for p in pairs if p['before']==loss['segment']]
        loss['id_fragmentation_possible']=bool(loss['possible_new_ids'])
    return {'experiment':'EXP-0034','mode':'offline_measured_evidence','policy':asdict(policy),
            'events':events,'losses':losses,'pairs':pairs,'segments':segments,
            'warning':'Initial heuristics; no probability, identity or physical intrusion truth.'}


def angle_audit(pairs, human_labels):
    """Only separately human-verified matches enter the angular hit denominator."""
    known={p['pair_id']:p for p in pairs}
    if any(k not in known or v not in ('same','different','unknown') for k,v in human_labels.items()):
        raise ValueError('Review labels must refer to exported pairs')
    verified=[known[k] for k,v in human_labels.items() if v=='same']
    usable=[p for p in verified if p['angle_degrees'] is not None]
    return {'human_verified_same':len(verified),'direction_available':len(usable),
            'within_90':sum(p['in_forward_90'] for p in usable),
            'within_90_fraction':sum(p['in_forward_90'] for p in usable)/len(usable) if usable else None,
            'unobserved_disappearances_excluded':True,'not_intrusion_probability':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames',type=Path,required=True)
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--human-pair-labels',type=Path)
    a=p.parse_args()
    if (a.output.exists() or a.output.is_symlink() or any(x.is_symlink() for x in a.output.parents)
        or not a.output.resolve().is_relative_to(Path('outputs').resolve())):
        p.error('Use a NEW non-symlink file under local outputs/')
    fb,sb=a.frames.read_bytes(),a.scene.read_bytes()
    frames=[json.loads(x) for x in fb.splitlines() if x.strip()]
    result=analyze(frames,json.loads(sb))
    result['input_sha256']={'frames':hashlib.sha256(fb).hexdigest(),'scene':hashlib.sha256(sb).hexdigest()}
    if a.human_pair_labels:
        result['angle_audit']=angle_audit(result['pairs'],json.loads(a.human_pair_labels.read_text()))
    if a.frames.read_bytes()!=fb or a.scene.read_bytes()!=sb:
        raise ValueError('Inputs changed while analyzing')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')
    print(json.dumps({'events':len(result['events']),'pairs':len(result['pairs']),
                      'status':'CPU analysis complete; actual event quality unverified'},ensure_ascii=False))


if __name__=='__main__':
    main()
