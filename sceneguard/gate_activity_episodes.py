"""EXP-0049: group frozen evidence by CURRENT portal observations, not alert gaps.

No new intrusion/release decisions. A closed observation episode is not a cleared
suspicion. Source evidence and its timestamps remain immutable. A card may be
confirmed while individual supporting observations remain unresolved.
"""
from __future__ import annotations

from copy import copy, deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math

SUSPECTED, CONFIRMED, RELEASED = '침입 의심', '침입 확인', '의심 해제'
STATES = {SUSPECTED, CONFIRMED, RELEASED}
CONTRACT = 'gate_activity_episodes_v1'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def clock(value):
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError('Finite nonnegative original source PTS required')
    return float(value)


@dataclass(frozen=True)
class ActivityPolicy:
    empty_grace_seconds: float = 3.0
    source_gap_seconds: float = .12

    def validate(self):
        if any(clock(v) <= 0 for v in asdict(self).values()):
            raise ValueError('Positive activity policy required')
        if self.source_gap_seconds >= self.empty_grace_seconds:
            raise ValueError('Source gap must be shorter than empty grace')
        return self


class GateActivityEpisodes:
    """One recording/camera/gate. Presence alone creates no suspicion/card.

    The fixed 10-second alert span is NOT used. Only fresh actual observations
    refresh the idle clock. A source gap ends grouping as interrupted, without
    asserting that the gate was empty or that the event was normal.
    """
    def __init__(self, scope, *, namespace='EXP-0049', policy=ActivityPolicy()):
        if set(scope) != {'session_id', 'camera_id', 'gate_id'} or any(
                not isinstance(v, str) or not v.strip() for v in scope.values()):
            raise ValueError('Explicit single recording/camera/gate scope required')
        if not isinstance(namespace, str) or not namespace:
            raise ValueError('Stable notification namespace required')
        self.scope, self.namespace, self.policy = dict(scope), namespace, policy.validate()
        self.cards, self.events, self.evidence, self.assignments = {}, {}, {}, {}
        self.timeline, self.notifications, self.activity_audit = [], [], []
        self._seen_frames = {}
        self._index, self._pts = -1, None
        self._active, self._last_presence, self._presence_started = None, None, None
        self._last_refs = []

    def step(self, frame_index, pts, *, portal_refs=(), candidates=(), evidence_updates=()):
        at = clock(pts)
        if type(frame_index) is not int or frame_index < 0:
            raise ValueError('Nonnegative source frame index required')
        refs, events, updates = map(lambda x: deepcopy(list(x)),
                                    (portal_refs, candidates, evidence_updates))
        signature = digest(dict(index=frame_index, pts=pts, refs=refs,
                                candidates=events, evidence_updates=updates))
        if frame_index in self._seen_frames:
            if self._seen_frames[frame_index] != signature:
                raise ValueError('An already observed source frame changed')
            return []
        if frame_index != self._index + 1 or (self._pts is not None and at <= self._pts):
            raise ValueError('Process every source frame in increasing PTS order')
        keys = []
        for r in refs:
            if (r.get('frame_index') != frame_index or clock(r.get('pts')) != at
                    or type(r.get('cache_index')) is not int or r['cache_index'] < 0):
                raise ValueError('Presence must refer to THIS actual source frame')
            keys.append(r['cache_index'])
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate presence reference')
        incoming = {}
        for event in events:
            eid = event.get('event_id')
            if (not isinstance(eid, str) or not eid or event.get('status') != SUSPECTED
                    or clock(event.get('decision_time_pts')) != at
                    or any(event.get(k) != v for k, v in self.scope.items())
                    or eid in self.events or eid in incoming):
                raise ValueError('New, scoped, frozen candidate at its original PTS required')
            incoming[eid] = event
        update_map = {}
        for state in updates:
            eid = state.get('event_id'); event = incoming.get(eid, self.events.get(eid))
            if (event is None or eid in update_map or state.get('automatic_status') not in STATES
                    or clock(state.get('opened_pts')) != event['decision_time_pts']
                    or not event['decision_time_pts'] <= clock(state.get('last_state_change_pts')) <= at
                    or not isinstance(state.get('incident_id'), str)):
                raise ValueError('Causal source evidence for a known event required')
            for field in ('first_confirmation_pts', 'released_pts'):
                if state.get(field) is not None and not event['decision_time_pts'] <= clock(state[field]) <= at:
                    raise ValueError('Future or backdated source state')
            if state['automatic_status'] == CONFIRMED and state.get('first_confirmation_pts') is None:
                raise ValueError('Confirmation needs its original source timestamp')
            if state['automatic_status'] == RELEASED and state.get('released_pts') is None:
                raise ValueError('Release needs its original source timestamp')
            for handoff in state.get('observation_history', []):
                if clock(handoff['pts']) > at:
                    raise ValueError('Future observation routing in source snapshot')
            old = self.evidence.get(eid)
            if old and old['automatic_status'] == CONFIRMED and state['automatic_status'] != CONFIRMED:
                raise ValueError('A prior confirmation cannot be cleared')
            update_map[eid] = state
        if not set(incoming) <= set(update_map):
            raise ValueError('Each new candidate needs its contemporaneous evidence, not final evidence')
        # Transactional working state, without quadratic copies of historical logs.
        trial = copy(self)
        for field in ('cards', 'events', 'evidence', 'assignments', '_last_refs'):
            setattr(trial, field, deepcopy(getattr(self, field)))
        trial.timeline, trial.notifications, trial.activity_audit = [], [], []
        trial._advance(frame_index, at, refs, incoming, update_map)
        new_rows = deepcopy(trial.timeline)
        trial.timeline = self.timeline + trial.timeline
        trial.notifications = self.notifications + trial.notifications
        trial.activity_audit = self.activity_audit + trial.activity_audit
        trial._seen_frames = dict(self._seen_frames)
        trial._seen_frames[frame_index] = signature
        trial._index, trial._pts = frame_index, at
        self.__dict__.update(trial.__dict__)
        return new_rows

    def _close(self, at, reason, touched):
        if self._active is not None:
            card = self.cards[self._active]
            card.update(observation_status='closed', observation_closed_pts=at,
                        observation_close_reason=reason, grouping_window_open=False)
            touched.add(self._active)
        self._active = None
        self._last_presence = self._presence_started = None
        self._last_refs = []

    def _advance(self, index, at, refs, incoming, updates):
        touched = set()
        gap = self._pts is not None and at-self._pts > self.policy.source_gap_seconds+1e-9
        if gap:
            self._close(at, 'source_gap_not_verified_empty', touched)
        anchor = self._last_presence
        if anchor is None and self._active is not None:
            anchor = self.cards[self._active]['first_alert_pts']
        if anchor is not None:
            elapsed = at-anchor
            expired = (elapsed > self.policy.empty_grace_seconds+1e-9 if refs
                       else elapsed >= self.policy.empty_grace_seconds-1e-9)
            if expired:
                self._close(at, 'no_current_portal_observation_for_grace', touched)
        if refs:
            if self._presence_started is None:
                self._presence_started = at
            self._last_presence, self._last_refs = at, deepcopy(refs)
            if self._active is not None:
                touched.add(self._active)
        for eid, event in sorted(incoming.items()):
            if self._active is None:
                cid = 'activity-' + digest([self.namespace, self.scope, eid])[:24]
                self._active = cid
                self.cards[cid] = dict(incident_id=cid, **self.scope, status=SUSPECTED,
                    automatic_status=SUSPECTED, automatic_confirmation=False,
                    first_alert_pts=at, last_alert_pts=at, event_ids=[], source_refs=[],
                    source_incident_ids=[], track_ids=[], alert_count=0,
                    first_notification_pts=None, first_confirmation_pts=None,
                    confirmation_notified=False, suspicion_notified=False,
                    observation_status='open', observation_closed_pts=None,
                    observation_close_reason=None, grouping_window_open=True,
                    activity_started_pts=self._presence_started,
                    last_gate_observation_pts=self._last_presence,
                    last_gate_observation_refs=deepcopy(self._last_refs),
                    lifecycle_version=0, human_verified=False, identity_merged=False,
                    person_count=None, decision_source='frozen_EXP0048_evidence',
                    manual_reviews_modified=False)
            card = self.cards[self._active]
            card['event_ids'].append(eid); card['source_refs'].append(deepcopy(event.get('source_ref', {})))
            card['track_ids'] = sorted(set(card['track_ids']).union(event.get('track_ids', [])))
            card.update(last_alert_pts=at, alert_count=card['alert_count']+1)
            self.events[eid], self.assignments[eid] = deepcopy(event), self._active
            touched.add(self._active)
        if self._active is not None:
            card = self.cards[self._active]
            card.update(last_gate_observation_pts=self._last_presence,
                        last_gate_observation_refs=deepcopy(self._last_refs),
                        activity_started_pts=self._presence_started,
                        accept_until_pts=(self._last_presence if self._last_presence is not None
                                          else card['first_alert_pts'])+self.policy.empty_grace_seconds)
        for eid, state in updates.items():
            cid = self.assignments[eid]
            self.evidence[eid] = dict(deepcopy(state), source_incident_id=state['incident_id'], incident_id=cid)
            sources = self.cards[cid]['source_incident_ids']
            if state['incident_id'] not in sources:
                sources.append(state['incident_id'])
            touched.add(cid)
        for cid in sorted(touched):
            card = self.cards[cid]; states = [self.evidence[e] for e in card['event_ids']]
            confirmed = [s for s in states if s['automatic_status'] == CONFIRMED]
            pending = [s for s in states if s['automatic_status'] == SUSPECTED]
            released = [s for s in states if s['automatic_status'] == RELEASED]
            status = CONFIRMED if confirmed else SUSPECTED if pending else RELEASED
            card.update(automatic_status=status, automatic_confirmation=bool(confirmed),
                confirmed_event_ids=[s['event_id'] for s in confirmed],
                unresolved_event_ids=[s['event_id'] for s in pending],
                released_event_ids=[s['event_id'] for s in released],
                first_confirmation_pts=min((s['first_confirmation_pts'] for s in confirmed), default=None),
                lifecycle_updated_pts=at, lifecycle_version=card['lifecycle_version']+1)
            if status == RELEASED and cid == self._active:
                self._close(at, 'all_linked_suspicions_released', touched)
            kind = None
            if confirmed and not card['confirmation_notified']:
                kind = 'confirmation'; card['confirmation_notified'] = True
            elif pending and card['first_notification_pts'] is None:
                kind = 'suspicion'; card['suspicion_notified'] = True
            key = None
            if kind:
                if card['first_notification_pts'] is None:
                    card['first_notification_pts'] = at
                key = f'{self.namespace}:{cid}:{kind}'
                self.notifications.append(dict(notification_key=key, incident_id=cid,
                    kind=kind, status=status, decision_time_pts=at, delivery_measured=False))
            self.timeline.append(dict(incident_id=cid, decision_time_pts=at,
                automatic_status=status, notification_kind=kind, notify=kind is not None,
                notification_key=key, card=deepcopy(card), evidence=deepcopy(states)))
        self.activity_audit.append(dict(frame_index=index, pts=at, source_gap=gap,
            portal_observation_refs=deepcopy(refs), portal_present=bool(refs),
            current_incident_id=self._active, last_gate_observation_pts=self._last_presence))

    def export(self):
        cards = deepcopy(list(self.cards.values()))
        return dict(schema_version=1, contract=CONTRACT, experiment='EXP-0049',
            activity_policy=asdict(self.policy), events=deepcopy(list(self.events.values())),
            evidence=deepcopy(list(self.evidence.values())), cards=cards,
            active_cards=[c for c in cards if c['observation_status']=='open'],
            closed_cards=[c for c in cards if c['observation_status']=='closed'],
            released_cards=[c for c in cards if c['automatic_status']==RELEASED],
            timeline=deepcopy(self.timeline), notification_intents=deepcopy(self.notifications),
            activity_audit=deepcopy(self.activity_audit),
            counts=dict(raw_candidates=len(self.events), incident_cards=len(cards),
                open_cards=sum(c['observation_status']=='open' for c in cards),
                closed_cards=sum(c['observation_status']=='closed' for c in cards),
                suspected_cards=sum(c['automatic_status']==SUSPECTED for c in cards),
                confirmed_cards=sum(c['automatic_status']==CONFIRMED for c in cards),
                released_cards=sum(c['automatic_status']==RELEASED for c in cards),
                suspicion_notifications=sum(n['kind']=='suspicion' for n in self.notifications),
                confirmation_notifications=sum(n['kind']=='confirmation' for n in self.notifications)),
            candidate_generation_changed=False, evidence_decisions_changed=False,
            grouping_rule_changed=True, maximum_alert_span_applied=False,
            closure_is_release=False, source_end_forced_close=False,
            source_end_forced_release=False, manual_reviews_modified=False,
            live_notifications_enabled=False, notification_delivery_measured=False,
            accuracy=None, realtime=False, identity_verified=False)


def activity_cards_at(timeline, pts, *, include_closed=True):
    at = clock(pts); cards = {}
    for row in timeline:
        if row['decision_time_pts'] <= at+1e-9:
            cards[row['incident_id']] = deepcopy(row['card'])
    return [c for c in cards.values() if include_closed or c['observation_status']=='open']
