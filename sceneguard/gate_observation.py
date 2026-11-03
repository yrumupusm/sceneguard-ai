"""MVP continuation evidence: measured passage, same-side visibility, ambiguity.

No identity inference or new image processing. A legacy one-point crossing vote
is never a positive event here. Existing EXP replay keeps SavedGateDirection.
"""
from copy import deepcopy
import math

from .directional_loss import (SavedGateDirection, inside, overlap, path_map,
    pixel_box, signed, vectors_direction)
from .gate_episode_evidence import Gate
from .approach_disappearance import Policy,center,signed_distance
from .existing_alert_crossing import _crossings


class GateObservationDirection(SavedGateDirection):
    observation_continuation_enabled = True

    def __init__(self, frames, scene, policy=None):
        super().__init__(frames, scene, **({} if policy is None else {'policy':policy}))
        self.scene = deepcopy(scene)
        self.gate = Gate(scene)
        self._last_continuation = None
        self._tail_cache={}
        self._point_crossing_cache={}
        self.window_frames={};self.continuous_start={};first=None;previous=None
        for i,frame in self.frames.items():
            if previous is None or i!=previous+1 or frame['pts']-self.frames[previous]['pts']>self.gate.policy.source_gap_seconds+1e-9:
                first=i
            self.continuous_start[i]=first;previous=i
            for wid in self.paths[i]:self.window_frames.setdefault(wid,[]).append(i)

    def _finite_passage(self, wid, pid, start, end, direction, maps):
        """Follow adjacent original point positions; no chord across a gap."""
        key=(wid,pid,start,end,direction)
        if key not in self._point_crossing_cache:
            if len(self._point_crossing_cache)>=65536:self._point_crossing_cache.clear()
            self._point_crossing_cache[key]=self._compute_finite_passage(wid,pid,start,end,direction,maps)
        return self._point_crossing_cache[key]

    def _compute_finite_passage(self, wid, pid, start, end, direction, maps):
        g = self.geometry
        def along(p):
            return sum((p[k]-g['a'][k])*g['vector'][k] for k in (0,1))/g['length']**2
        previous = None; on_line = []; crossings = []
        for i in range(start,end+1):
            if i not in self.frames or wid not in self.paths.get(i,{}):
                return []
            if i>start and self.frames[i]['pts']-self.frames[i-1]['pts'] > self.gate.policy.source_gap_seconds+1e-9:
                return []
            point = maps[i].get(pid)
            if point is None:
                return []
            distance = signed(point,g)
            if distance is None:
                return []
            if abs(distance)<1e-7:
                on_line.append(along(point)); continue
            if previous is not None:
                j, p, old = previous
                expected = 'inward' if old<0<distance else 'outward' if old>0>distance else None
                if expected == direction:
                    if on_line:
                        positions=on_line
                    else:
                        fraction=old/(old-distance)
                        positions=[along(tuple(p[k]+fraction*(point[k]-p[k]) for k in (0,1)))]
                    if all(-1e-9<=x<=1+1e-9 for x in positions):
                        crossings.append(dict(point_id=pid,before_frame=j,after_frame=i,gate_along=positions))
            previous=(i,point,distance);on_line=[]
        return crossings

    def _connected_boxes(self,a,b):
        policy=Policy();size=self.scene['source_size']
        aw,ah=a['bbox'][2]-a['bbox'][0],a['bbox'][3]-a['bbox'][1]
        bw,bh=b['bbox'][2]-b['bbox'][0],b['bbox'][3]-b['bbox'][1]
        return (b['pts']-a['pts']<=policy.max_direction_step+1e-9
            and max(aw/bw,bw/aw,ah/bh,bh/ah)<=policy.scale_jump
            and math.dist(center(a,size),center(b,size))<=.5*max(ah,bh)*size[1])

    def _origin_support(self,rows):
        policy=Policy();size=self.scene['source_size'];source=rows[-1]
        source_sign=signed_distance(center(source,size,1.),self.scene)
        if abs(source_sign)<policy.min_motion_pixels:
            return []
        origin=[]
        for row in reversed(rows):
            if source['pts']-row['pts']>self.gate.policy.history_seconds+1e-9:
                break
            distance=signed_distance(center(row,size,1.),self.scene)
            if distance*source_sign<=0 or abs(distance)<policy.min_motion_pixels:
                break
            origin.append(row)
        origin.reverse()
        if len(origin)<policy.stable_observations or origin[-1]['pts']-origin[0]['pts']<policy.stable_seconds-1e-9:
            return []
        if any(not self._connected_boxes(a,b) for a,b in zip(origin,origin[1:])):
            return []
        return origin

    def recover_short_origin(self,source,rows,rid):
        """Extend an insufficient origin only through measured inherited rows.

        Retain the first source reference and stop at the first opposite side.
        Once an anchor is viable it is immutable; later people cannot replace it.
        """
        if self._origin_support(source['rows']):return source
        last=source['rows'][-1];size=self.scene['source_size']
        current={r['frame_index']:r for r in rows}
        if any(current.get(r['frame_index'])!=r for r in source['rows']):return source
        sign=signed_distance(center(last,size,1.),self.scene)
        if abs(sign)<Policy().min_motion_pixels:return source
        chosen=None
        for i,row in enumerate(rows):
            if row['pts']<=last['pts']:continue
            distance=signed_distance(center(row,size,1.),self.scene)
            if distance*sign<0 and abs(distance)>=Policy().min_motion_pixels:break
            if self._origin_support(rows[:i+1]):chosen=i
        if chosen is None:return source
        return dict(id=rid,raw_id=None,rows=deepcopy(rows[:chosen+1]),
            recovered_short_origin=dict(observation_key=source['id'],
                original_last_observation=deepcopy(last),original_rows=deepcopy(source['rows'])))

    def _stable_passages(self, segment, matches, passages):
        """Points support actual moving boxes, never a one-frame posture vote."""
        policy=Policy();size=self.scene['source_size'];source=segment['rows'][-1]
        source_sign=signed_distance(center(source,size,1.),self.scene)
        origin=self._origin_support(segment['rows'])
        if not origin:return []
        available={(p['window_id'],p['target_frame'],p['target_cache_index']):p for p in passages}
        windows={}
        for m in matches:
            key=(m['window_id'],m['target_frame'])
            prior=windows.get(key)
            if prior is None or (m['coverage'],-m['target_cache_index'])>(prior['coverage'],-prior['target_cache_index']):
                windows[key]=m
        result=[]
        for wid in sorted({key[0] for key in windows}):
            chain=[source];streak=[];direction=None;cohort=set()
            for key in sorted(k for k in windows if k[0]==wid):
                match=windows[key]
                row=dict(pts=match['target_pts'],frame_index=match['target_frame'],
                    cache_index=match['target_cache_index'],bbox=match['target_bbox'])
                if not self._connected_boxes(chain[-1],row):
                    break
                chain.append(row)
                proof=available.get((wid,row['frame_index'],row['cache_index']))
                distance=signed_distance(center(row,size,1.),self.scene)
                if (proof is None or source_sign*distance>=0 or abs(distance)<policy.min_motion_pixels
                        or (signed(center(source,size,1.),self.geometry)<0) != (proof['direction']=='inward')):
                    streak=[];direction=None;cohort=set();continue
                if direction is not None and direction!=proof['direction']:
                    streak=[];cohort=set()
                common=cohort.intersection(proof['crossing_point_ids']) if streak else set(proof['crossing_point_ids'])
                if len(common)<self.policy.minimum_points or len(common)/proof['anchor_count']<.6:
                    streak=[];common=set(proof['crossing_point_ids'])
                cohort=common
                direction=proof['direction'];streak.append(row)
                if len(streak)<policy.stable_observations or streak[-1]['pts']-streak[0]['pts']<policy.stable_seconds-1e-9:
                    continue
                crossings=_crossings(chain,self.scene,source_sign)
                if not crossings:continue
                corrected_start=self.corrected(proof['source_frame'],wid)
                corrected_end=self.corrected(proof['target_frame'],wid)
                motion=vectors_direction([tuple(corrected_end[pid][k]-corrected_start[pid][k]
                    for k in (0,1)) for pid in cohort],self.geometry,self.policy)
                if motion['direction']!=direction:continue
                result.append(dict(proof,crossing_point_ids=sorted(cohort),crossing_coverage=len(cohort)/proof['anchor_count'],
                    finite_gate_crossings=[p for p in proof['finite_gate_crossings'] if p['point_id'] in cohort],motion=motion,
                    source_cache_index=source['cache_index'],
                    source_bbox=deepcopy(source['bbox']),actual_box_crossings=crossings,
                    origin_observation_refs=deepcopy(origin),destination_observation_refs=deepcopy(streak),
                    stable_seconds=policy.stable_seconds,stable_observations=policy.stable_observations))
        return result

    def continuation_details(self, segment, decision_index):
        rows=segment['rows']; last=rows[-1]; start=last['frame_index']; g=self.geometry
        if decision_index not in self.frames or decision_index<start:
            raise ValueError('Current actual source frame required')
        at=self.frames[decision_index]['pts']
        by_frame={r['frame_index']:r for r in rows}
        cache_key=(decision_index,segment['id'],segment['raw_id'],
                   tuple((r['frame_index'],r.get('cache_index'),tuple(r['bbox'])) for r in rows))
        if self._last_continuation is not None and self._last_continuation[0]==cache_key:
            return deepcopy(self._last_continuation[1])
        source_key=cache_key[1:]
        tail=self._tail_cache.get(source_key)
        if tail is not None and decision_index>tail['index'] and not any(
                tail['index']<i<=decision_index for wid in self.paths.get(start,{}) for i in self.window_frames[wid]):
            result=deepcopy(tail['result'])
            result.update(decision_time_pts=at,current_endpoint_observed=False,same_side_evidence=[],
                source_continuous=start>=self.continuous_start[decision_index])
            if result['crossing'] is None and not result['conflicting_crossing_directions']:
                matches=result['matches']
                result['status']=('recent_bound_continuation' if matches and
                    at-max(m['target_pts'] for m in matches)<self.policy.loss_wait-1e-6 else
                    'ambiguous' if matches else 'unresolved')
            self._last_continuation=(cache_key,deepcopy(result))
            return result
        target=pixel_box(last['bbox'],g['size'])
        matches=[]; passages=[]; same=[];other=[]
        for wid,path in self.paths.get(start,{}).items():
            born,seed=self.births[wid]; measured=by_frame.get(born)
            if measured is None or (measured.get('cache_index')!=seed['cache_index'] and
                    overlap(pixel_box(measured['bbox'],g['size']),pixel_box(seed['bbox'],g['size']))<.6):
                continue
            p=path_map(path); anchors=[pid for pid in p if inside(p[pid],target,.15)]
            if len(anchors)<self.policy.minimum_points:
                continue
            indices=[i for i in self.window_frames[wid] if start<=i<=decision_index]
            maps={i:path_map(self.paths[i][wid]) for i in indices}
            for i in indices:
                if i==start:continue
                # All proofs use a continuous original recording prefix.
                if start<self.continuous_start[i]:
                    continue
                q=path_map(self.paths[i][wid]); corrected_start=self.corrected(start,wid)
                corrected_end=self.corrected(i,wid)
                for box in self.frames[i]['actual_boxes']:
                    if box.get('observed') is False or box.get('score',0)<.25:
                        continue
                    ids=[pid for pid in anchors if pid in q and inside(q[pid],pixel_box(box['bbox'],g['size']))]
                    if len(ids)<self.policy.minimum_points or len(ids)/len(anchors)<.6:
                        continue
                    evidence=dict(window_id=wid,source_frame=start,source_pts=last['pts'],
                        target_frame=i,target_pts=self.frames[i]['pts'],target_cache_index=box['cache_index'],
                        target_bbox=deepcopy(box['bbox']),point_ids=ids,anchor_count=len(anchors),
                        coverage=len(ids)/len(anchors))
                    matches.append(evidence)
                    sides={pid:(signed(p[pid],g),signed(q[pid],g)) for pid in ids}
                    same_ids=[pid for pid,(a,b) in sides.items() if a is not None and b is not None and a*b>0]
                    if i==decision_index and len(same_ids)>=self.policy.minimum_points and len(same_ids)/len(ids)>=.6:
                        same.append(dict(evidence,same_side_point_ids=same_ids))
                    for direction in ('inward','outward'):
                        crossing=[]; paths=[]
                        raw_cross=[]
                        for pid,(a,b) in sides.items():
                            if a is None or b is None:
                                continue
                            if not ((a < -self.policy.normal_pixels and b > self.policy.normal_pixels)
                                    if direction=='inward' else
                                    (a > self.policy.normal_pixels and b < -self.policy.normal_pixels)):
                                continue
                            raw_cross.append(pid)
                            proof=self._finite_passage(wid,pid,start,i,direction,maps)
                            if proof:crossing.append(pid);paths.extend(proof)
                        if i==decision_index and len(raw_cross)>=self.policy.minimum_points and len(raw_cross)/len(anchors)>=.6:
                            other.append(dict(evidence,direction=direction))
                        if len(crossing)<self.policy.minimum_points or len(crossing)/len(anchors)<.6:
                            continue
                        motion=vectors_direction([tuple(corrected_end[pid][k]-corrected_start[pid][k]
                            for k in (0,1)) for pid in crossing],g,self.policy)
                        if motion['direction']!=direction:
                            continue
                        passages.append(dict(evidence,direction=direction,crossing_point_ids=crossing,
                            finite_gate_crossings=paths,crossing_coverage=len(crossing)/len(anchors),motion=motion))
        passages=self._stable_passages(segment,matches,passages)
        directions={e['direction'] for e in passages}
        if len(directions)>1:
            status='ambiguous'
        elif passages:
            status='cross_side_observation'
        elif same:
            status='same_side_continuation'
        elif other:
            status='unvalidated_cross_side_continuation'
        elif any(e['target_frame']==decision_index for e in matches):
            status='boundary_unclear_continuation'
        elif matches and at-max(e['target_pts'] for e in matches)<self.policy.loss_wait-1e-6:
            status='recent_bound_continuation'
        else:
            status='ambiguous' if matches else 'unresolved'
        # Correlated windows/overlapping boxes are alternatives, never summed.
        proof=min(passages,key=lambda e:(e['target_pts'],-e['crossing_coverage'])) if len(directions)==1 else None
        result=dict(status=status,decision_time_pts=at,source_last_observed_pts=last['pts'],
            current_endpoint_observed=any(e['target_frame']==decision_index for e in matches),
            crossing=proof,same_side_evidence=same,matches=matches,
            conflicting_crossing_directions=sorted(directions) if len(directions)>1 else [],
            source_continuous=start>=self.continuous_start[decision_index],
            human_verified=False,identity_verified=False)
        self._last_continuation=(cache_key,deepcopy(result))
        if len(self._tail_cache)>=128:self._tail_cache.pop(next(iter(self._tail_cache)))
        self._tail_cache[source_key]=dict(index=decision_index,result=deepcopy(result))
        return result

    def continuation(self, segment, decision_index):
        details=self.continuation_details(segment,decision_index)
        # Ambiguous correspondence is not an automatic veto of the independent
        # gate-loss evidence. Callers retain details and prohibit release.
        if details['conflicting_crossing_directions']:
            return 'conflicting_observation'
        if details['status']=='unvalidated_cross_side_continuation':
            return 'cross_side_observation'
        return 'unresolved' if details['status']=='ambiguous' else details['status']

    def latest_bound_loss_context(self,segment,details):
        """Advance the loss clock to actual bound observations, not an ID end.

        Only duplicate/contained endpoint footprints can share one geometric
        context; distinct competing people remain unresolved. No history or ID
        is changed, and the actual reference remains available in the audit.
        """
        matches=details['matches']
        if not matches:return deepcopy(segment)
        last=max(m['target_pts'] for m in matches)
        choices={ (m['target_frame'],m['target_cache_index']):m for m in matches if m['target_pts']==last }
        selected=max(choices.values(),key=lambda m:(m['coverage'],-m['target_cache_index']))
        if any(overlap(selected['target_bbox'],m['target_bbox'])<.9 for m in choices.values()):
            return None
        rows=deepcopy(segment['rows'])
        rows.append(dict(pts=selected['target_pts'],frame_index=selected['target_frame'],
                         cache_index=selected['target_cache_index'],bbox=deepcopy(selected['target_bbox'])))
        return dict(segment,rows=rows)

    def observed_crossing(self, segment, decision_index, details=None):
        details=details or self.continuation_details(segment,decision_index)
        proof=details.get('crossing')
        if details['status']!='cross_side_observation' or not proof or not details['source_continuous']:
            return None
        direction='outside_to_inside' if proof['direction']=='inward' else 'inside_to_outside'
        if direction not in self.scene.get('directions',[]):
            return None
        last=segment['rows'][-1]['pts']
        contact=[r for r in segment['rows'] if 0<=last-r['pts']<=self.gate.policy.history_seconds+1e-9
                 and self.gate.locate(r['bbox'],birth=False)['near']
                 and 0<=self.gate.locate(r['bbox'],birth=False)['along']<=1]
        if not contact:
            return None
        at=self.frames[decision_index]['pts']
        return dict(rule_id='observed_gate_continuation_v1',segment=segment['id'],raw_id=segment['raw_id'],
            status='침입 확인',automatic_confirmation=True,notify=True,decision_source='automatic_rule',
            reason='coherent_finite_gate_crossing_in_actual_observations',direction=direction,
            decision_time_pts=at,last_observed_pts=proof['target_pts'],evidence_until_pts=at,
            source_last_observed_pts=last,gate_contact=deepcopy(contact[-1]),
            crossing_evidence=deepcopy(proof),continuation_assessment=details,loss_wait_required=False,
            source_snapshot_recovery=deepcopy(segment.get('recovered_short_origin')),
            human_verified=False,identity_verified=False,confirmation_basis='camera_rule_not_manual_or_ground_truth')

    def classify(self, event, segment):
        previous=super().classify(event,segment)
        ending=next((i for i,f in self.frames.items() if abs(f['pts']-event['decision_time_pts'])<1e-6),None)
        if ending is None or previous.get('reason')=='loss_wait_not_observed':
            return previous
        details=self.continuation_details(segment,ending)
        if not details['source_continuous']:
            return dict(previous,status='판단 불가',automatic_confirmation=False,notify=False,
                        reason='loss_wait_not_observed',loss_observation_failure='source_gap',
                        continuation_assessment=details)
        if details['conflicting_crossing_directions']:
            return dict(previous,status='침입 의심',automatic_confirmation=False,
                        reason='conflicting_observed_crossings',continuation='conflicting_observation',
                        continuation_assessment=details)
        if details['status'] in ('boundary_unclear_continuation','recent_bound_continuation'):
            return dict(previous,status='침입 의심',automatic_confirmation=False,
                        reason='ongoing_or_recent_target_observation',
                        continuation=details['status'],continuation_assessment=details)
        crossing=self.observed_crossing(segment,ending,details)
        if crossing:
            return crossing
        previous['continuation_assessment']=details
        if details['status']=='ambiguous' and previous.get('automatic_confirmation'):
            previous['rule_id']='ambiguous_gate_loss_v1'
            previous['association_ambiguous']=True
        return previous
