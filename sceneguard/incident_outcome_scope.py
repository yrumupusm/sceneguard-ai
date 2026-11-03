"""EXP-0048: one linked outcome updates one incident, not every aliased card.

Observation handoffs remain fallible visual continuity, not person identities.
Inward loss may support an incident even with mixed people. Outward loss must
not erase multiple independent origins merely because their keys were aliased.
No candidate/direction/zone threshold is changed here; no notifications are sent.
"""
from __future__ import annotations
from copy import deepcopy

from .incident_lifecycle import IncidentLifecycle, CONFIRMED, canonical, digest, scope


class ScopedIncidentLifecycle(IncidentLifecycle):
    """Keep the original grouping and add outcome ownership, not identity gates.

    A positive outcome confirms one evidence anchor in the latest linked card.
    It does not turn all older approach observations into verified intrusions.
    Owners survive retries and later handoffs, so the same loss cannot fall back
    to an older card after the newest evidence is no longer pending.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcome_routing = []
        self._owners = {}
        self._origin_sets = {}
        self._outcome_claims = {}
        self._outcome_anchors = {}
        self._routed_payloads = {}
        self._physical_batch = []

    def _process(self, at, candidates, resolutions):
        # All candidates are installed by the base transaction before _resolve.
        # Inspect the whole equal-time batch so input order cannot award an old
        # event a physical endpoint shared with a newer linked candidate.
        self._physical_batch=[r for r in resolutions if r.get('physical_loss_ref')]
        try:return super()._process(at,candidates,resolutions)
        finally:self._physical_batch=[]

    def _key(self, eid, observation):
        return (*scope(self.events[eid]), observation)

    def _candidate(self, row, at, touched):
        super()._candidate(row, at, touched)
        eid = row['event']['event_id']; observation = row.get('observation_key')
        if observation is None:
            return
        key = self._key(eid, observation)
        source = row.get('binding', {}).get('source_observation_key') or observation
        roots = self._origin_sets.get(self._key(eid, source), {source})
        self._origin_sets.setdefault(key, set()).update(roots)
        owner = (at, self._event_cards[eid])
        self._owners[key] = max(self._owners.get(key, owner), owner)

    def _resolve(self, resolution, at, touched):
        item = deepcopy(resolution); rid = item['resolution_id']
        payload = canonical(item)
        if rid in self._routed_payloads:
            if self._routed_payloads[rid] != payload:
                raise ValueError('Outcome routing ID has conflicting content')
            return
        # Validate the ENTIRE request before filtering. Do not mask an invalid
        # clock, source scope, unbound event or stale direction by dropping it.
        probe = deepcopy(self)
        IncidentLifecycle._resolve(probe, item, at, set())
        self._routed_payloads[rid] = payload
        ids = item['event_ids']; kind = item['kind']
        delayed=item.get('confirmation_source')=='delayed_raw_gate_loss_v1'
        if kind == 'preserved_confirmation' and not delayed:
            super()._resolve(item, at, touched)
            self.outcome_routing.append(dict(resolution_id=rid, decision_time_pts=at,
                reason='preserved_source_confirmation', selected_event_ids=ids,
                excluded_event_ids=[]))
            return
        key = self._key(ids[0], item['observation_key'])
        if kind == 'observation_handoff':
            dest = self._key(ids[0], item['next_observation_key'])
            roots = self._origin_sets.get(key, {item['observation_key']})
            self._origin_sets.setdefault(dest, set()).update(roots)
            owners = [self._owners[k] for k in (key, dest) if k in self._owners]
            if owners:
                self._owners[dest] = max(owners)
            super()._resolve(item, at, touched)
            self.outcome_routing.append(dict(resolution_id=rid, decision_time_pts=at,
                reason='continuity_not_identity', selected_event_ids=ids,
                excluded_event_ids=[], origin_count=len(self._origin_sets[dest])))
            return
        # Stable physical-evidence key excludes the later decision time and the
        # remaining pending-ID subset: retries must not claim an older card.
        physical=item.get('physical_loss_ref')
        outcome = (digest(dict(scope=list(key[:-1]),measured_loss=physical)) if physical else
                   digest(dict(scope=list(key[:-1]),kind=kind,passage=item['physical_crossing_ref']))
                   if kind=='observed_gate_crossing' else
                   digest(dict(scope=list(key[:-1]), observation=key[-1], kind=kind,
                               last_observed_pts=item['last_observed_pts'])))
        candidate_owner = self._owners.get(key)
        if candidate_owner is None:
            latest = max(ids, key=lambda eid:(self.evidence[eid]['opened_pts'], eid))
            candidate_owner = (self.evidence[latest]['opened_pts'], self._event_cards[latest])
        batch_ids=list(ids)
        if physical:
            for other in self._physical_batch:
                if other.get('physical_loss_ref')!=physical:continue
                other_ids=other['event_ids']
                if scope(self.events[other_ids[0]])!=scope(self.events[ids[0]]):continue
                batch_ids.extend(other_ids)
                other_key=self._key(other_ids[0],other['observation_key'])
                latest=max(other_ids,key=lambda eid:(self.evidence[eid]['opened_pts'],eid))
                candidate_owner=max(candidate_owner,self._owners.get(other_key,
                    (self.evidence[latest]['opened_pts'],self._event_cards[latest])))
        owner = self._outcome_claims.setdefault(outcome, candidate_owner[1])
        selected = [eid for eid in ids if self._event_cards[eid] == owner]
        roots = self._origin_sets.get(key, {key[-1]})
        reason = 'latest_linked_incident'
        if not selected:
            reason = 'outcome_owned_by_other_incident'
        elif kind == 'outward_loss' and len(roots) > 1:
            # Does not block inward incident evidence. Prevents one departure
            # from clearing all suspicions that joined across several sources.
            selected = []; reason = 'mixed_origins_not_blanket_release'
        elif delayed or kind in ('inward_loss', 'outward_crossing_loss', 'observed_gate_crossing'):
            eligible=[eid for eid in batch_ids if self._event_cards[eid]==owner]
            existing = [eid for eid in eligible
                        if self.evidence[eid]['automatic_status'] == CONFIRMED]
            anchor = self._outcome_anchors.setdefault(outcome, max(existing or eligible,
                key=lambda eid:(self.evidence[eid]['opened_pts'], eid)))
            selected = [anchor] if anchor in selected else []
            if physical and self.evidence[anchor]['automatic_status']==CONFIRMED:
                selected=[]
            reason = ('one_confirmation_anchor_in_owner_incident' if selected
                      else 'outcome_anchor_already_applied')
        audit = dict(resolution_id=rid, decision_time_pts=at, kind=kind,
            outcome_key=outcome, owner_incident_id=owner, origin_count=len(roots),
            selected_event_ids=selected,
            excluded_event_ids=[eid for eid in ids if eid not in selected], reason=reason)
        self.outcome_routing.append(audit)
        if selected:
            item['event_ids'] = selected
            item['routing_source_resolution_id'] = rid
            item['outcome_key'] = outcome
            item['owner_incident_id'] = owner
            item['resolution_id'] = digest(dict(source=rid, outcome=outcome,
                                               owner=owner, selected=selected))
            super()._resolve(item, at, touched)

    def export(self):
        result = super().export()
        result.update(experiment='EXP-0048', outcome_scope_policy='latest_linked_incident_v1',
            outcome_routing=deepcopy(self.outcome_routing),
            outcome_owners=deepcopy(self._outcome_claims),
            outcome_anchors=deepcopy(self._outcome_anchors),
            ownership_is_identity_proof=False,
            old_pending_cards_auto_cleared=False)
        return result
