"""One notification per short entrance episode; never merge identities or detections.

Pure stdlib. Event clocks are ORIGINAL decision/emission PTS, not last-seen PTS.
Defaults are UI grouping choices, not calibrated intrusion thresholds.
"""
from copy import deepcopy
from dataclasses import dataclass, asdict
import hashlib
import json
import math


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be finite and nonnegative')
    return float(value)


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')
    return value


@dataclass(frozen=True)
class GroupPolicy:
    gap_seconds: float = 3.0
    max_span_seconds: float = 10.0

    def validate(self):
        gap = finite(self.gap_seconds, 'gap_seconds')
        span = finite(self.max_span_seconds, 'max_span_seconds')
        if gap <= 0 or span < gap:
            raise ValueError('Require 0 < gap_seconds <= max_span_seconds')
        return self


class IncidentGrouper:
    """Append in nondecreasing decision time per (session,camera,gate).

    push() returns created/updated/duplicate. Only created has notify=True.
    Repeat delivery of an identical event is idempotent. A later new event is
    never suppressed: it updates a card or immediately starts a new one.
    Callers must persist notification_key delivery receipts across restarts.
    """
    def __init__(self, policy=GroupPolicy()):
        self.policy = policy.validate()
        self._cards, self._active, self._seen, self._watermarks = {}, {}, {}, {}

    def push(self, event):
        e = deepcopy(event)
        scope = tuple(text(e.get(k), k) for k in ('session_id', 'camera_id', 'gate_id'))
        eid = text(e.get('event_id'), 'event_id')
        at = finite(e.get('decision_time_pts'), 'decision_time_pts')
        if e.get('status') != '침입 의심':
            raise ValueError('Grouping accepts existing suspicions only; no status promotion')
        tids = e.get('track_ids', [])
        if not isinstance(tids, list) or any(type(i) is not int or i < 0 for i in tids):
            raise ValueError('track_ids must be a list of nonnegative raw IDs')
        payload = canonical(e)
        key = (*scope, eid)
        if key in self._seen:
            old, cid = self._seen[key]
            if payload != old:
                raise ValueError('The same event_id has conflicting content')
            return dict(action='duplicate', incident_id=cid, event_id=eid,
                        decision_time_pts=at, notify=False, notification_key=None)
        if at < self._watermarks.get(scope, -math.inf):
            raise ValueError('New events must be ordered by decision PTS per stream')
        self._watermarks[scope] = at
        cid = self._active.get(scope)
        card = self._cards.get(cid)
        fits = (card is not None and
                at-card['last_alert_pts'] <= self.policy.gap_seconds+1e-9 and
                at-card['first_alert_pts'] <= self.policy.max_span_seconds+1e-9)
        if not fits:
            first_key = canonical([*scope, eid])
            cid = 'incident-' + hashlib.sha256(first_key.encode()).hexdigest()[:24]
            card = dict(incident_id=cid, session_id=scope[0], camera_id=scope[1],
                        gate_id=scope[2], status='침입 의심', first_alert_pts=at,
                        last_alert_pts=at, first_notification_pts=at,
                        notification_key='notify:'+cid, version=0, alert_count=0,
                        track_ids=[], event_ids=[], source_refs=[],
                        identity_merged=False, automatic_confirmation=False,
                        person_count=None)
            self._cards[cid] = card
            self._active[scope] = cid
        card['last_alert_pts'] = at
        card['version'] += 1
        card['alert_count'] += 1
        card['event_ids'].append(eid)
        card['track_ids'] = sorted(set(card['track_ids']).union(tids))
        card['source_refs'].append(deepcopy(e.get('source_ref', {})))
        card['accept_until_pts'] = min(at+self.policy.gap_seconds,
                                      card['first_alert_pts']+self.policy.max_span_seconds)
        self._seen[key] = payload, cid
        return dict(action='updated' if fits else 'created', incident_id=cid,
                    event_id=eid, decision_time_pts=at, notify=not fits,
                    notification_key=None if fits else card['notification_key'],
                    card=deepcopy(card))

    def cards(self):
        return deepcopy(list(self._cards.values()))


def group_events(events, policy=GroupPolicy()):
    """Offline replay produces time-scoped snapshots, NOT future-filled early cards."""
    original = deepcopy(list(events))
    ordered = sorted(original, key=lambda e: (finite(e['decision_time_pts'], 'decision_time_pts'),
                      e['session_id'], e['camera_id'], e['gate_id'], e['event_id']))
    grouper = IncidentGrouper(policy)
    timeline = [grouper.push(e) for e in ordered]
    cards = grouper.cards()
    return dict(policy=asdict(policy), cards=cards, timeline=timeline, events=original,
                counts=dict(input_alert_rows=len(original),
                            unique_alerts=sum(t['action'] != 'duplicate' for t in timeline),
                            duplicate_deliveries=sum(t['action'] == 'duplicate' for t in timeline),
                            incident_cards=len(cards),
                            notification_intents=sum(t['notify'] for t in timeline),
                            silent_card_updates=sum(t['action'] == 'updated' for t in timeline)),
                scope='presentation_grouping_not_incident_ground_truth',
                same_person_required=False, detection_rules_changed=False,
                notification_delivery_measured=False)


def cards_at(timeline, pts):
    """Safe for video seek: fields contain only observations already emitted by pts."""
    pts = finite(pts, 'playback PTS')
    cards = {}
    for item in timeline:
        if item['decision_time_pts'] <= pts+1e-9 and item['action'] != 'duplicate':
            cards[item['incident_id']] = deepcopy(item['card'])
    for card in cards.values():
        card['grouping_window_open'] = pts <= card['accept_until_pts']+1e-9
        # Closed grouping is NOT a reviewed/confirmed/negative intrusion verdict.
    return list(cards.values())
