"""Group ALL candidates first; decide notification eligibility inside each episode.

No detector, flow, identity inference, model or external notification is invoked.
A review-only candidate maintains grouping continuity but never creates a toast.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

from .incident_cards import GroupPolicy, IncidentGrouper, canonical, finite


class NotificationGrouper:
    """Causal wrapper around the unchanged 3-second / 10-second episode grouper.

    push() consumes only this candidate's disposition. The first eligible event
    can be an UPDATED episode, so consumers must use notify, not action=created.
    This class produces notification intentions, not delivery receipts.
    """

    def __init__(self, policy: GroupPolicy = GroupPolicy()):
        self.policy = policy.validate()
        self.grouper = IncidentGrouper(policy)
        self._modes: dict[tuple, bool] = {}
        self._cards: dict[str, dict] = {}

    def push(self, event: dict, *, notify_candidate: bool = True) -> dict:
        if type(notify_candidate) is not bool:
            raise ValueError('notify_candidate must be an explicit boolean')
        key = tuple(event.get(k) for k in
                    ('session_id', 'camera_id', 'gate_id', 'event_id'))
        if key in self._modes and self._modes[key] != notify_candidate:
            raise ValueError('Cannot retroactively change an event disposition')
        item = self.grouper.push(event)
        if item['action'] == 'duplicate':
            item['notification_action'] = 'duplicate'
            return item
        self._modes[key] = notify_candidate
        cid = item['incident_id']
        previous = self._cards.get(cid, {})
        active = list(previous.get('active_event_ids', []))
        review = list(previous.get('review_only_event_ids', []))
        (active if notify_candidate else review).append(item['event_id'])
        first = previous.get('first_notification_pts')
        emit = notify_candidate and first is None
        if emit:
            first = item['decision_time_pts']
        card = item['card']  # Already a detached prefix snapshot from the base.
        card.update(active_event_ids=active, review_only_event_ids=review,
                    active_alert_count=len(active), review_only_alert_count=len(review),
                    first_notification_pts=first, notification_eligible=bool(active),
                    notification_status='alerted' if active else 'review_only')
        # first_alert_pts remains the FIRST RAW candidate, not the first notice.
        item.update(notify=emit,
                    notification_key=card['notification_key'] if emit else None,
                    notification_action=('first_notify' if emit else
                        'silent_update' if active else 'review_only_update'))
        self._cards[cid] = deepcopy(card)
        return item

    def cards(self) -> list[dict]:
        return deepcopy(list(self._cards.values()))


def group_notifications(events, review_only_ids=(), policy=GroupPolicy()) -> dict:
    """Replay all original candidate rows, retaining IDs and full source payloads.

    Decisions must have been computed using evidence available at each event.
    Output cards contains ALL episodes. alert_cards is the notification view.
    Identical redelivery is allowed; a changed payload/disposition is rejected.
    """
    original = deepcopy(list(events))
    review_ids = set(review_only_ids)
    by_id = {}
    for event in original:
        eid = event['event_id']
        if eid in by_id and canonical(by_id[eid]) != canonical(event):
            raise ValueError('Conflicting globally normalized event ID')
        by_id[eid] = event
    if not review_ids.issubset(by_id):
        raise ValueError('Review disposition references an unknown event')
    ordered = sorted(original, key=lambda e: (
        finite(e['decision_time_pts'], 'decision PTS'), e['session_id'],
        e['camera_id'], e['gate_id'], e['event_id']))
    grouper = NotificationGrouper(policy)
    timeline = [grouper.push(e, notify_candidate=e['event_id'] not in review_ids)
                for e in ordered]
    cards = grouper.cards()
    alert_cards = [deepcopy(c) for c in cards if c['notification_eligible']]
    review_cards = [deepcopy(c) for c in cards if not c['notification_eligible']]
    active = [deepcopy(e) for eid, e in by_id.items() if eid not in review_ids]
    review = [deepcopy(e) for eid, e in by_id.items() if eid in review_ids]
    return dict(schema_version=1, contract='group_all_then_notify_v1',
        policy=asdict(policy), events=original, active_events=active,
        review_only_events=review, cards=cards, alert_cards=alert_cards,
        review_only_cards=review_cards, timeline=timeline,
        counts=dict(input_alert_rows=len(original), unique_alerts=len(by_id),
            duplicate_deliveries=len(original)-len(by_id),
            active_alerts=len(active), review_only_alerts=len(review),
            candidate_cards=len(cards), alert_cards=len(alert_cards),
            review_only_cards=len(review_cards),
            notification_intents=sum(t['notify'] for t in timeline),
            silent_card_updates=sum(t['notification_action']=='silent_update' for t in timeline),
            review_only_updates=sum(t['notification_action']=='review_only_update' for t in timeline)),
        same_person_required=False, detection_rules_changed=False,
        notification_delivery_measured=False, live_notifications_enabled=False)


def notification_cards_at(timeline, pts, *, include_review_only=False):
    """Prefix-only snapshots for playback/rewind; no future eligibility or IDs."""
    pts = finite(pts, 'playback PTS')
    cards = {}
    for item in timeline:
        if item['decision_time_pts'] <= pts+1e-9 and item['action'] != 'duplicate':
            card = deepcopy(item['card'])
            card['grouping_window_open'] = pts <= card['accept_until_pts']+1e-9
            cards[item['incident_id']] = card
    return [c for c in cards.values() if include_review_only or c['notification_eligible']]


def episode_comparison(baseline, proposal):
    """One-to-one raw episode correspondence, including completely muted episodes."""
    current = {c['incident_id']: c for c in proposal['cards']}
    if set(current) != {c['incident_id'] for c in baseline['cards']}:
        raise ValueError('Filtering changed the original episode identities')
    rows = []
    for old in baseline['cards']:
        new = current[old['incident_id']]
        if new['event_ids'] != old['event_ids']:
            raise ValueError('Filtering changed episode membership')
        first = new['first_notification_pts']
        rows.append(dict(incident_id=old['incident_id'],
            source_interval=[old['first_alert_pts'], old['last_alert_pts']],
            original_event_ids=deepcopy(old['event_ids']),
            active_event_ids=deepcopy(new['active_event_ids']),
            review_only_event_ids=deepcopy(new['review_only_event_ids']),
            baseline_first_notification_pts=old['first_notification_pts'],
            proposed_first_notification_pts=first,
            notification_shift_pts=None if first is None else first-old['first_notification_pts'],
            notification_eligible=new['notification_eligible']))
    return rows
