"""EXP-0047 causal suspicion lifecycle; raw alerts and human reviews stay immutable.

A short observation key is NOT a person's identity. Outcomes update only linked
pending evidence. Cards aggregate that evidence, and confirmation has its own
idempotent notification intent. This module NEVER sends notifications.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math

from .incident_cards import GroupPolicy, IncidentGrouper

SUSPECTED = '침입 의심'
CONFIRMED = '침입 확인'
RELEASED = '의심 해제'
CONTRACT = 'incident_lifecycle_v1'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def clock(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Finite nonnegative ORIGINAL source time required')
    return float(value)


def scope(event):
    values = tuple(event.get(k) for k in ('session_id', 'camera_id', 'gate_id'))
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError('Explicit session/camera/gate required')
    return values


class IncidentLifecycle:
    """Process a single-time batch atomically; do not hide an upgrade in grouping.

    Candidates contain event, observation_key (optional), binding (audit), and
    release_protected. Resolutions contain kind (outward_loss, inward_loss, or
    preserved_confirmation), event_ids, evidence_until_pts and decision_time_pts.
    An outward loss must name its linked observation_key; nearby other people
    cannot release unrelated evidence. Existing confirmations are sticky.
    """
    def __init__(self, policy=GroupPolicy(), *, namespace='EXP-0047'):
        self.policy = policy.validate()
        if not isinstance(namespace, str) or not namespace:
            raise ValueError('Notification namespace required')
        self.namespace = namespace
        self.grouper = IncidentGrouper(policy)
        self.events = {}
        self.evidence = {}
        self.cards = {}
        self.timeline = []
        self.notifications = []
        self.resolution_log = []
        self._event_cards = {}
        self._candidate_hashes = {}
        self._resolution_hashes = {}
        self._batches = {}
        self._last_pts = -math.inf

    def pending(self, observation_key=None):
        return [eid for eid, item in self.evidence.items()
                if item['automatic_status'] == SUSPECTED and
                (observation_key is None or item['observation_key'] == observation_key)]

    def _candidate(self, row, at, touched):
        event = deepcopy(row['event'])
        eid = event['event_id']
        if abs(clock(event['decision_time_pts'])-at) > 1e-6 or event.get('status') != SUSPECTED:
            raise ValueError('Candidate must be an original suspicion at this batch time')
        scope(event)
        key = row.get('observation_key')
        if key is not None and (not isinstance(key, str) or not key):
            raise ValueError('Observation key must be a nonempty string or None')
        protected = row.get('release_protected', False)
        if type(protected) is not bool:
            raise ValueError('Explicit release-protection boolean required')
        payload = canonical(row)
        if eid in self.events:
            if self._candidate_hashes[eid] != payload:
                raise ValueError('An existing candidate or its binding changed')
            return
        item = self.grouper.push(event)
        cid = item['incident_id']
        previous = self.cards.get(cid, {})
        card = item['card']
        # The base grouper creates notices. Its notice flag is deliberately NOT
        # consumed: same-frame confirmation must produce one stronger notice.
        card.update(first_notification_pts=previous.get('first_notification_pts'),
                    first_confirmation_pts=previous.get('first_confirmation_pts'),
                    suspicion_notified=previous.get('suspicion_notified', False),
                    confirmation_notified=previous.get('confirmation_notified', False),
                    lifecycle_version=previous.get('lifecycle_version', 0))
        self.cards[cid] = card
        self.events[eid] = event
        self._candidate_hashes[eid] = payload
        self._event_cards[eid] = cid
        self.evidence[eid] = dict(event_id=eid, incident_id=cid,
            observation_key=key, binding=deepcopy(row.get('binding', {})),
            release_protected=protected, automatic_status=SUSPECTED,
            opened_pts=at, last_state_change_pts=at,
            first_confirmation_pts=None, released_pts=None, resolution_id=None,
            human_verified=False, identity_verified=False)
        touched.add(cid)

    def _resolve(self, resolution, at, touched):
        item = deepcopy(resolution)
        rid = item['resolution_id']; kind = item['kind']
        if not isinstance(rid, str) or not rid:
            raise ValueError('Stable resolution ID required')
        if (clock(item['decision_time_pts']) != at or
                clock(item['evidence_until_pts']) != at):
            raise ValueError('No future or backdated outcome evidence')
        if kind not in ('outward_loss', 'inward_loss', 'outward_crossing_loss', 'preserved_confirmation', 'observation_handoff'):
            raise ValueError('Unknown lifecycle resolution')
        ids = item['event_ids']
        if not ids or len(ids) != len(set(ids)) or any(eid not in self.events for eid in ids):
            raise ValueError('Outcome must reference known, unique candidate IDs')
        if len({scope(self.events[eid]) for eid in ids}) != 1:
            raise ValueError('Cannot apply one outcome across camera/session/gate scopes')
        if kind == 'observation_handoff':
            key, next_key = item.get('observation_key'), item.get('next_observation_key')
            if (not key or not next_key or key == next_key or
                    any(self.evidence[eid]['observation_key'] != key for eid in ids) or
                    item.get('actual_correspondence') is not True):
                raise ValueError('Handoff requires an actual linked observation, not a nearby person')
        elif kind != 'preserved_confirmation':
            key = item.get('observation_key')
            if not key or any(self.evidence[eid]['observation_key'] != key for eid in ids):
                raise ValueError('Disappearance must bind to the affected observation only')
            last = clock(item['last_observed_pts'])
            wait = clock(item['loss_wait'])
            if (wait <= 0 or at-last < wait-1e-6 or
                    item.get('recording_continuous') is not True or
                    item.get('observation_continues') is not False):
                raise ValueError('Actual absence interval required; not a clip end or ID timeout')
            expected = 'outward' if kind in ('outward_loss', 'outward_crossing_loss') else 'inward'
            if item.get('direction') != expected:
                raise ValueError('Wrong signed movement for outcome')
            direction_at = clock(item['direction_end_pts'])
            history = clock(item['direction_history_seconds'])
            if direction_at > last+1e-6 or last-direction_at > history+1e-6:
                raise ValueError('Last measured direction is stale or from the future')
            if kind == 'inward_loss' and item.get('recent_gate_contact') is not True:
                raise ValueError('Inward loss requires observed gate context')
            if kind == 'outward_crossing_loss':
                decision = item.get('evidence', {}).get('outward_crossing_evidence', {})
                if (decision.get('rule_id') != 'outward_gate_loss_v1'
                        or decision.get('automatic_confirmation') is not True
                        or decision.get('crossing_direction') != 'inside_to_outside'
                        or not decision.get('inside_origin') or not decision.get('gate_contact')
                        or decision.get('last_observed_pts') != last
                        or decision.get('decision_time_pts') != at):
                    raise ValueError('Outward crossing requires linked inside-origin gate evidence')
        elif item.get('confirmation_source') == 'visible_gate_crossing_v1':
            decision = item.get('source_decision', {})
            if (decision.get('rule_id') != 'visible_gate_crossing_v1'
                    or decision.get('automatic_confirmation') is not True
                    or decision.get('direction') not in ('outside_to_inside', 'inside_to_outside')
                    or decision.get('decision_time_pts') != at
                    or decision.get('last_observed_pts') != at
                    or ids != [decision.get('event_id')]):
                raise ValueError('Visible crossing requires current, event-bound observation evidence')
        elif item.get('confirmation_source') == 'outward_gate_loss_v1':
            decision = item.get('source_decision', {})
            if (decision.get('rule_id') != 'outward_gate_loss_v1'
                    or decision.get('automatic_confirmation') is not True
                    or decision.get('crossing_direction') != 'inside_to_outside'
                    or not decision.get('inside_origin') or not decision.get('gate_contact')
                    or decision.get('decision_time_pts') != at
                    or ids != [decision.get('event_id')]):
                raise ValueError('Outward loss requires event-bound inside-origin gate evidence')
        elif item.get('confirmation_source') != 'EXP-0045':
            raise ValueError('Preserved confirmations must retain their source')
        payload = canonical(item)
        if rid in self._resolution_hashes:
            if self._resolution_hashes[rid] != payload:
                raise ValueError('Resolution ID has conflicting contents')
            return
        self._resolution_hashes[rid] = payload
        changed, protected, already_confirmed = [], [], []
        for eid in ids:
            e = self.evidence[eid]
            if e['automatic_status'] == CONFIRMED:
                already_confirmed.append(eid)
                continue
            if kind == 'observation_handoff':
                e.setdefault('observation_history', []).append(dict(
                    from_key=e['observation_key'], to_key=item['next_observation_key'],
                    pts=at, resolution_id=rid))
                e['observation_key'] = item['next_observation_key']
                changed.append(eid); touched.add(self._event_cards[eid])
                continue
            if kind == 'outward_loss' and e['release_protected']:
                protected.append(eid)
                continue
            target = RELEASED if kind == 'outward_loss' else CONFIRMED
            if e['automatic_status'] == target:
                continue
            # A later positive observation can supersede a provisional release.
            # Earlier snapshots and the release history remain unchanged.
            e.update(automatic_status=target, last_state_change_pts=at,
                     resolution_id=rid)
            if target == CONFIRMED:
                e['first_confirmation_pts'] = at
            else:
                e['released_pts'] = at
            changed.append(eid); touched.add(self._event_cards[eid])
        self.resolution_log.append(dict(item, changed_event_ids=changed,
            protected_event_ids=protected, already_confirmed_event_ids=already_confirmed))

    def process(self, pts, candidates=(), resolutions=()):
        """Equal-time redelivery is idempotent; otherwise submit times in order.

        Confirmations run before releases at the same source time. Notification
        decisions are made AFTER the entire batch, so a direct confirmation does
        not send a simultaneous suspicion notification as well.
        """
        at = clock(pts)
        candidates, resolutions = deepcopy(list(candidates)), deepcopy(list(resolutions))
        content = canonical(dict(pts=at, candidates=candidates, resolutions=resolutions))
        if at in self._batches:
            if self._batches[at] != content:
                raise ValueError('Submit all updates for a timestamp in one immutable batch')
            return []
        if at < self._last_pts:
            raise ValueError('Do not rewrite past lifecycle state')
        # Validate on a detached transaction; malformed batches cannot half-mutate state.
        trial = deepcopy(self)
        snapshots = trial._process(at, candidates, resolutions)
        trial._last_pts = at; trial._batches[at] = content
        self.__dict__.update(trial.__dict__)
        return snapshots

    def _process(self, at, candidates, resolutions):
        touched = set()
        for row in sorted(candidates, key=lambda r:(r['event']['decision_time_pts'],r['event']['event_id'])):
            self._candidate(row, at, touched)
        rank = {'preserved_confirmation':0, 'observation_handoff':1, 'inward_loss':2, 'outward_crossing_loss':2, 'outward_loss':3}
        for resolution in sorted(resolutions, key=lambda r:(rank.get(r['kind'],9), r['resolution_id'])):
            self._resolve(resolution, at, touched)
        snapshots = []
        for cid in sorted(touched):
            card = self.cards[cid]
            states = [self.evidence[eid] for eid in card['event_ids']]
            confirmed = [s for s in states if s['automatic_status']==CONFIRMED]
            pending = [s for s in states if s['automatic_status']==SUSPECTED]
            released = [s for s in states if s['automatic_status']==RELEASED]
            status = CONFIRMED if confirmed else SUSPECTED if pending else RELEASED
            card.update(automatic_status=status, automatic_confirmation=bool(confirmed),
                unresolved_event_ids=[s['event_id'] for s in pending],
                released_event_ids=[s['event_id'] for s in released],
                confirmed_event_ids=[s['event_id'] for s in confirmed],
                lifecycle_updated_pts=at, lifecycle_version=card['lifecycle_version']+1,
                human_verified=False, identity_merged=False,
                decision_source='automatic_rule', manual_reviews_modified=False,
                first_confirmation_pts=min((s['first_confirmation_pts'] for s in confirmed), default=None))
            notice = None
            if confirmed and not card['confirmation_notified']:
                notice = 'confirmation'; card['confirmation_notified'] = True
            elif pending and card['first_notification_pts'] is None:
                notice = 'suspicion'; card['suspicion_notified'] = True
            if notice:
                if card['first_notification_pts'] is None: card['first_notification_pts'] = at
                key = f'{self.namespace}:{cid}:{notice}'
                self.notifications.append(dict(notification_key=key,incident_id=cid,
                    kind=notice,status=status,decision_time_pts=at,delivery_measured=False))
            snapshot = dict(incident_id=cid, decision_time_pts=at,
                automatic_status=status, notification_kind=notice, notify=notice is not None,
                notification_key=None if notice is None else key,
                card=deepcopy(card), evidence=[deepcopy(s) for s in states])
            self.timeline.append(snapshot); snapshots.append(deepcopy(snapshot))
        return snapshots

    def export(self):
        cards = deepcopy(list(self.cards.values()))
        return dict(schema_version=1, contract=CONTRACT, experiment='EXP-0047',
            policy=asdict(self.policy), events=deepcopy(list(self.events.values())),
            evidence=deepcopy(list(self.evidence.values())), cards=cards,
            active_cards=[deepcopy(c) for c in cards if c['automatic_status']!=RELEASED],
            released_cards=[deepcopy(c) for c in cards if c['automatic_status']==RELEASED],
            timeline=deepcopy(self.timeline), resolutions=deepcopy(self.resolution_log),
            notification_intents=deepcopy(self.notifications),
            counts=dict(raw_candidates=len(self.events), incident_cards=len(cards),
                suspected_cards=sum(c['automatic_status']==SUSPECTED for c in cards),
                confirmed_cards=sum(c['automatic_status']==CONFIRMED for c in cards),
                released_cards=sum(c['automatic_status']==RELEASED for c in cards),
                suspicion_notifications=sum(n['kind']=='suspicion' for n in self.notifications),
                confirmation_notifications=sum(n['kind']=='confirmation' for n in self.notifications),
                released_evidence=sum(e['automatic_status']==RELEASED for e in self.evidence.values())),
            live_notifications_enabled=False, notification_delivery_measured=False,
            manual_reviews_modified=False, accuracy=None, realtime=False,
            identity_verified=False, source_alerts_deleted=False)


def lifecycle_cards_at(timeline, pts, *, include_released=True):
    """Return detached prefix snapshots; seeking cannot show a future release."""
    at = clock(pts); cards = {}
    for row in timeline:
        if row['decision_time_pts'] <= at+1e-9:
            cards[row['incident_id']] = deepcopy(row['card'])
    return [c for c in cards.values() if include_released or c['automatic_status']!=RELEASED]
