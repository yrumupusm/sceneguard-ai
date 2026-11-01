"""Read saved actual observation runs and point paths; no new tracking or model.

Run IDs describe short geometric continuity, not identity. Raw track IDs are not
used to match people. The caller keeps uncertainty rather than fabricating exits.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import math

from .incident_lifecycle import clock, digest


class ObservationHistory:
    def __init__(self, runs, frames, *, source_gap_seconds=.12):
        self.gap_seconds = clock(source_gap_seconds)
        if self.gap_seconds <= 0: raise ValueError('Positive source gap bound required')
        self.rows = defaultdict(list)
        self.by_reference = defaultdict(set)
        self.scheduled = defaultdict(list)
        self.last_pts = None; self.current_index = -1; self.continuous_since = None
        self.bindings = []; self.aliases = {}; self.inherited = defaultdict(list)
        previous = -math.inf
        for i, frame in enumerate(frames):
            if frame['frame_index'] != i or clock(frame['pts']) <= previous:
                raise ValueError('Complete chronological saved source frames required')
            previous = frame['pts']
        self.frames = {r['frame_index']:r for r in frames}
        self.references = {i:{b['cache_index']:b for b in f['actual_boxes']}
                           for i,f in self.frames.items()}
        for rid, rows in runs.items():
            previous = -math.inf
            if not isinstance(rid,str) or not rid: raise ValueError('Observation run key required')
            for row in rows:
                i, ci = row['frame_index'], row['cache_index']
                frame = self.frames.get(i)
                box = self.references.get(i,{}).get(ci)
                if (frame is None or box is None or box.get('observed') is False or
                        abs(clock(row['pts'])-frame['pts']) > 1e-9 or
                        row['pts'] <= previous or row['bbox'] != box['bbox']):
                    raise ValueError('Run must bind to unchanged actual boxes and source PTS')
                previous = row['pts']
                self.scheduled[i].append((rid,deepcopy(row)))
                self.by_reference[(i,ci)].add(rid)

    def advance(self, frame):
        i, at = frame['frame_index'], clock(frame['pts'])
        if i != self.current_index+1 or self.frames[i]['pts'] != at:
            raise ValueError('Advance every saved source frame without skipping')
        if self.last_pts is None or at-self.last_pts > self.gap_seconds+1e-9:
            self.continuous_since = at
        for rid,row in self.scheduled[i]: self.rows[rid].append(deepcopy(row))
        self.last_pts = at; self.current_index = i

    def current_key(self, rid):
        seen = set()
        while rid in self.aliases:
            if rid in seen: raise ValueError('Cyclic observation handoff')
            seen.add(rid); rid = self.aliases[rid]
        return rid

    def motion_rows(self, rid):
        # This is evidence lineage only; original observation runs stay intact.
        by_frame = {r['frame_index']:r for r in self.inherited[rid]}
        by_frame.update({r['frame_index']:r for r in self.rows[rid]})
        return [deepcopy(by_frame[i]) for i in sorted(by_frame)]

    def link(self, old, new):
        new = self.current_key(new)
        if old == new or not self.rows.get(new):
            raise ValueError('Handoff needs a distinct currently observed successor')
        if self.rows[new][-1]['pts'] != self.last_pts:
            raise ValueError('Handoff cannot use a past/future successor')
        self.inherited[new].extend(self.motion_rows(old))
        self.aliases[old] = new

    def bind(self, event, segments):
        """Bind only an actual source reference, never the nearest unrelated person."""
        at = event['decision_time_pts']; raw = event['source_event']
        if self.last_pts is None or at > self.last_pts+1e-6:
            raise ValueError('Cannot bind using future observations')
        rid = raw.get('run_id') if event['source_ref']['collection']=='inside_birth_events' else None
        if rid is not None:
            refs = raw.get('observation_refs', [])
            if (rid not in self.rows or not refs or
                    any(r['frame_index'] > self.current_index or
                        self.frames[r['frame_index']]['pts'] != r['pts'] or
                        r['pts'] > at+1e-6 or rid not in self.by_reference.get(
                        (r['frame_index'],r['cache_index']),set()) for r in refs)):
                raise ValueError('Portal candidate does not bind to its saved observation run')
            binding = dict(method='saved_portal_run', refs=deepcopy(refs))
        else:
            seg = segments.get(raw.get('segment'))
            visible = [] if seg is None else [r for r in seg['rows'] if r['pts'] <= at+1e-6]
            ref = visible[-1] if visible else None
            choices = set() if ref is None else self.by_reference.get((ref['frame_index'],ref['cache_index']),set())
            method = 'exact_actual_reference'
            if not choices and ref is not None:
                # EXP46 removes nested boxes while building runs. Recover only a
                # unique same-frame containment relation under that SAME .9 rule.
                # This remains fallible bookkeeping, not identity verification.
                from .directional_loss import overlap
                choices = {name for name, measured in self.scheduled[ref['frame_index']]
                           if overlap(ref['bbox'], measured['bbox']) >= .9}
                method = 'unique_same_frame_containment'
            rid = next(iter(choices)) if len(choices)==1 else None
            binding = dict(method=method if rid else 'unbound_preserve',
                           reference=deepcopy(ref), alternative_runs=sorted(choices))
        # Do not add a new blanket veto for still-suspected boundary candidates.
        # Known confirmations are sticky in the lifecycle itself. An unrelated
        # unbound candidate remains independent and cannot be cleared by this run.
        protected = False
        original_rid = rid
        if rid is not None: rid = self.current_key(rid)
        binding['source_observation_key'] = original_rid
        result = dict(event=deepcopy(event),observation_key=rid,binding=binding,
                      release_protected=protected)
        self.bindings.append(dict(event_id=event['event_id'],observation_key=rid,
                                  binding=deepcopy(binding),release_protected=protected))
        return result


def followup_run(history, engine, run_id, index):
    """Find a UNIQUE successor run from the SAME surviving target-bound points.

    This is evidence routing only: raw IDs/boxes are never changed. Existing
    minimum-points and 60% coverage conventions match the saved continuation
    helper. Several plausible successors are logged, not merged.
    """
    from .directional_loss import pixel_box, overlap, inside, path_map
    rows = history.motion_rows(run_id); last = rows[-1]
    start = last['frame_index']
    if index <= start: return dict(successor=None,reason='still_observed',matches=[])
    actual = {r['frame_index']:r for r in rows}
    size = engine.geometry['size']; target = pixel_box(last['bbox'],size)
    matches = {}; blocked = []
    for wid,path in engine.paths.get(start,{}).items():
        born,seed = engine.births[wid]; observed = actual.get(born)
        if observed is None: continue
        if (observed.get('cache_index')!=seed['cache_index'] and
                overlap(pixel_box(observed['bbox'],size),pixel_box(seed['bbox'],size)) < .6):
            continue
        anchors = path_map(path)
        anchor_ids = [pid for pid,p in anchors.items() if inside(p,target,.15)]
        current = engine.paths.get(index,{}).get(wid)
        if not current or not anchor_ids: continue
        positions = path_map(current)
        for box in history.frames[index]['actual_boxes']:
            if box.get('observed') is False or box['score'] < .25: continue
            b = pixel_box(box['bbox'],size)
            ids = [pid for pid in anchor_ids if pid in positions and inside(positions[pid],b)]
            if len(ids) < engine.policy.minimum_points or len(ids)/len(anchor_ids) < .6: continue
            choices = history.by_reference.get((index,box['cache_index']),set())
            if len(choices)!=1: continue
            successor = next(iter(choices))
            if successor==run_id: continue
            # A geometric run can be observed again after an earlier handoff.
            # Its old alias is not a current box correspondence. Never route
            # these points to a stale alias (or back into a lineage cycle).
            canonical_successor = history.current_key(successor)
            if canonical_successor != successor:
                blocked.append(dict(observed_run=successor,
                    canonical_run=canonical_successor,target_frame=index,
                    reason='aliased_successor_not_current_correspondence'))
                continue
            evidence = dict(successor=successor,window_id=wid,point_ids=ids,
                source_frame=start,target_frame=index,target_cache_index=box['cache_index'],
                coverage=len(ids)/len(anchor_ids),actual_correspondence=True)
            if successor not in matches or evidence['coverage'] > matches[successor]['coverage']:
                matches[successor] = evidence
    return dict(successor=next(iter(matches)) if len(matches)==1 else None,
        reason='same_points_successor' if len(matches)==1 else
               'competing_successors' if matches else
               'aliased_successor_not_current_correspondence' if blocked else 'no_mapped_successor',
        matches=list(matches.values()),blocked_matches=blocked)


def assess_loss(history, engine, portal, run_id, index, *, loss_wait=1., gate_history=3.):
    """Use recent signed movement and actual absence; no action/deformation score.

    Outward motion is a fallible exit hypothesis; it is not manual verification.
    Stationary, unknown, a data gap, and positive visual continuation cannot clear.
    """
    rows = history.motion_rows(run_id); last = rows[-1]; at = history.frames[index]['pts']
    result = dict(run_id=run_id, decision_time_pts=at,last_observed_pts=last['pts'],
                  outcome=None,reason='waiting_for_absence')
    if at-last['pts'] < loss_wait-1e-6: return result
    if last['pts'] < history.continuous_since-1e-9:
        return dict(result,reason='source_gap_not_person_loss')
    segment = dict(id=run_id,raw_id=None,rows=rows)
    direction = engine.direction(segment)
    continuation = engine.continuation(segment,index)
    contact = [r for r in rows if 0 <= last['pts']-r['pts'] <= gate_history+1e-9
               and portal.locate(r['bbox'])['inside_birth_site']]
    result.update(direction=direction,continuation=continuation,
                  recent_gate_contact=bool(contact),gate_contact=deepcopy(contact[-1]) if contact else None)
    if continuation!='unresolved': return dict(result,reason='observation_continues_not_loss')
    label = direction.get('direction','unknown'); end = direction.get('end_pts')
    if end is None or not 0 <= last['pts']-end <= engine.policy.history_seconds+1e-9:
        return dict(result,reason='no_recent_target_direction')
    if label=='outward': result.update(outcome='outward_loss',reason='outward_motion_then_loss')
    elif label=='inward' and contact: result.update(outcome='inward_loss',reason='inward_motion_then_portal_loss')
    else: result['reason']='direction_unclear_or_no_recent_gate_contact'
    result.update(loss_wait=loss_wait,direction_history_seconds=engine.policy.history_seconds)
    return result


def loss_resolution(assessment, event_ids):
    if assessment.get('outcome') not in ('outward_loss','inward_loss'):
        raise ValueError('Only an evaluated disappearance can resolve a suspicion')
    ids=sorted(event_ids); at=assessment['decision_time_pts']; direction=assessment['direction']
    result=dict(kind=assessment['outcome'],event_ids=ids,observation_key=assessment['run_id'],
        decision_time_pts=at,evidence_until_pts=at,last_observed_pts=assessment['last_observed_pts'],
        loss_wait=assessment['loss_wait'],recording_continuous=True,observation_continues=False,
        direction=direction['direction'],direction_end_pts=direction['end_pts'],
        direction_history_seconds=assessment['direction_history_seconds'],
        recent_gate_contact=assessment['recent_gate_contact'],
        evidence=deepcopy(assessment),human_verified=False)
    result['resolution_id']=digest(result)
    return result
