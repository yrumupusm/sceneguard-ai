"""EXP-0046: fixed IMAGE portal for birth cues; keep the ground line for motion.

The polygon covers the visible gate and its immediately adjoining inner emergence
area, NOT the entire inside ground plane. It cannot prove which physical side a
person occupies. A hit is only a location cue; existing temporal birth bookkeeping
still applies. No model, new optical flow, or automatic confirmation is added.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json

from .gate_episode_evidence import EpisodePolicy, Gate, InsideBirths, in_polygon, number

KIND = 'projected_gate_emergence_v1'
MIN_BOX_OVERLAP = .5  # initial geometry convention, not calibrated confidence


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def area(poly):
    return abs(sum(a[0]*b[1]-b[0]*a[1]
                   for a,b in zip(poly, poly[1:]+poly[:1])))/2 if poly else 0.


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def on_segment(a, b, c):
    return (abs(cross(a,b,c)) <= 1e-12 and
            min(a[0],b[0])-1e-12 <= c[0] <= max(a[0],b[0])+1e-12 and
            min(a[1],b[1])-1e-12 <= c[1] <= max(a[1],b[1])+1e-12)


def intersects(a, b, c, d):
    u,v,x,y = cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    return ((u*v < 0 and x*y < 0) or on_segment(a,b,c) or on_segment(a,b,d)
            or on_segment(c,d,a) or on_segment(c,d,b))


def validate_polygon(value):
    if not isinstance(value, (list,tuple)) or not 3 <= len(value) <= 12:
        raise ValueError('Use 3 to 12 perimeter vertices, without repeated closing point')
    poly = []
    for p in value:
        if not isinstance(p, (list,tuple)) or len(p) != 2:
            raise ValueError('Each normalized vertex requires x,y')
        q = tuple(number(x) for x in p)
        if not all(0 <= x <= 1 for x in q):
            raise ValueError('Use normalized ORIGINAL-frame coordinates, not preview pixels')
        poly.append(q)
    if len(set(poly)) != len(poly) or area(poly) <= 1e-10:
        raise ValueError('Distinct nondegenerate portal vertices required')
    edges = list(zip(poly,poly[1:]+poly[:1]))
    for i,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges):
            if j <= i or j == i+1 or (i == 0 and j == len(edges)-1):
                continue
            if intersects(a,b,c,d):
                raise ValueError('Portal polygon self-intersects')
    return poly


def clipped_area(poly, bbox):
    """Clip a simple polygon by a rectangle; coordinates share one image plane."""
    result = list(poly)
    for axis,bound,lower in ((0,bbox[0],True),(0,bbox[2],False),
                             (1,bbox[1],True),(1,bbox[3],False)):
        if not result:
            return 0.
        output = []
        for a,b in zip(result[-1:]+result[:-1], result):
            ai = a[axis] >= bound if lower else a[axis] <= bound
            bi = b[axis] >= bound if lower else b[axis] <= bound
            if ai != bi:
                ratio = (bound-a[axis])/(b[axis]-a[axis])
                output.append(tuple(a[k]+ratio*(b[k]-a[k]) for k in (0,1)))
            if bi:
                output.append(b)
        result = output
    return area(result)


def make_region(scene, camera_id, polygon, *, reference_pts, note):
    """One-time static-camera calibration, NOT person training annotations."""
    if not isinstance(camera_id,str) or not camera_id.strip():
        raise ValueError('Camera ID required')
    if number(reference_pts) < 0 or not isinstance(note,str) or not note.strip():
        raise ValueError('Record static reference PTS and calibration rationale')
    points = validate_polygon(polygon)
    return dict(schema_version=1,kind=KIND,camera_id=camera_id,
        source_size=deepcopy(scene['source_size']),scene_digest=digest(scene),
        polygon=[list(p) for p in points],
        provenance=dict(source='static_background',reference_pts=reference_pts,
                        note=note,review_status='draft'))


class PortalGate(Gate):
    """Replace B's location test only. A and the original scene remain unchanged."""
    def __init__(self, scene, region, camera_id, policy=EpisodePolicy()):
        super().__init__(scene, policy)
        if (region.get('schema_version') != 1 or region.get('kind') != KIND or
                region.get('camera_id') != camera_id or
                region.get('source_size') != scene['source_size'] or
                region.get('scene_digest') != digest(scene)):
            raise ValueError('Portal must bind to this camera, original size and selected scene')
        provenance = region.get('provenance', {})
        if (provenance.get('source') != 'static_background' or
                not provenance.get('note') or
                number(provenance.get('reference_pts')) < 0):
            raise ValueError('Static-background calibration provenance required')
        self.region = deepcopy(region)
        self.polygon = validate_polygon(region['polygon'])
        self.region_digest = digest(region)

    def locate(self, bbox, *, birth=True):
        if not birth:
            return super().locate(bbox, birth=False)
        b = self.box(bbox)
        c = ((bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2)
        center_in = in_polygon(c, self.polygon)
        fraction = min(1., max(0., clipped_area(self.polygon,bbox)/
                        ((bbox[2]-bbox[0])*(bbox[3]-bbox[1]))))
        hit = center_in or fraction >= MIN_BOX_OVERLAP-1e-12
        # Ground geometry is retained as diagnostic data, NEVER as another veto.
        legacy = super().locate(bbox, birth=True)
        return dict(inside_birth_site=bool(hit),geometry_kind=KIND,
            center_pixels=[(b[0]+b[2])/2,(b[1]+b[3])/2],
            portal_center_inside=center_in,portal_box_overlap=fraction,
            portal_region_digest=self.region_digest,
            membership_rule='center_inside_or_half_box_overlap',
            legacy_ground_test=legacy,
            ground_inside_is_not_required=True,physical_inside_verified=False)


class PortalBirths(InsideBirths):
    """Use unchanged EXP45 association, warm-up and short observation support.

    First location is latched by the parent: moving into the portal later is not
    a birth; moving away after birth does not erase it. IDs are not identities.
    Long gaps, merged boxes and projections of outside people remain limitations.
    """
    def __init__(self, scene, region, camera_id, policy=EpisodePolicy()):
        super().__init__(scene, policy)
        self.gate = PortalGate(scene,region,camera_id,policy)

    def step(self, frame):
        result = super().step(frame)
        for event in result:
            event.update(rule_id=KIND,
                warning='Projected portal appearance is only a suspicion; outside people, redetection and occlusion can overlap it.')
        return result


def compare_births(frames, scene, region, camera_id, policy=EpisodePolicy()):
    """Replay one fixed polygon vs the existing ground test, on identical boxes."""
    old = InsideBirths(scene,policy); new = PortalBirths(scene,region,camera_id,policy)
    before,after = [],[]
    observations = {}
    for frame in frames:
        before.extend(old.step(frame));after.extend(new.step(frame))
        # Check the entire association state, including support/short-gap history,
        # rather than merely checking that the first boxes happen to agree.
        excluded = {'site', 'eligible', 'emitted'}
        state = lambda engine: [{k:v for k,v in r.items() if k not in excluded}
                                for r in engine.runs]
        if state(old) != state(new):
            raise ValueError('Geometry-only comparison changed observation association')
        actual = {b['cache_index']:b for b in frame['actual_boxes']}
        for run in new.runs:
            if run['last_pts'] != frame['pts']:
                continue
            ref = run['observations'][-1]
            rows = observations.setdefault(run['run_id'], [])
            if not rows or rows[-1]['pts'] != ref['pts']:
                rows.append(dict(ref, bbox=deepcopy(actual[ref['cache_index']]['bbox'])))
    if len(old.audit) != len(new.audit) or any(
            any(a[k] != b[k] for k in ('run_id','birth_pts','bbox','warmed'))
            for a,b in zip(old.audit,new.audit)):
        raise ValueError('Geometry-only comparison changed observation bookkeeping')
    return dict(legacy_events=before,portal_events=after,
                legacy_audits=old.audit,portal_audits=new.audit,
                observation_runs=observations,observation_bookkeeping_unchanged=True)
