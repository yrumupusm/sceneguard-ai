"""EXP-0049 grouping-only replay of frozen EXP48 evidence and EXP42 detections.

Source outcome selection, confirmations, releases, bindings and decision PTS are
not recomputed. Only card membership, observation closure and notice deduplication
change. Current portal observations use the frozen EXP46 polygon convention.
"""
from __future__ import annotations
from bisect import bisect_left
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import argparse
import hashlib
import json
import time

from .gate_activity_episodes import ActivityPolicy, GateActivityEpisodes, clock, digest


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def activity_references(frame, portal, detection_floor=.25):
    """Only saved current measurements count; LAST/predicted boxes do not."""
    result = []
    if not 0 <= detection_floor <= 1:
        raise ValueError('Bounded saved detector score floor required')
    for box in frame['actual_boxes']:
        if box.get('observed') is False or box.get('predicted') is True:
            continue
        score = box['score']
        if type(score) not in (int, float) or not 0 <= score <= 1:
            raise ValueError('Invalid actual detector score')
        if score < detection_floor:
            continue
        if portal.locate(box['bbox'])['inside_birth_site']:
            result.append(dict(frame_index=frame['frame_index'], pts=frame['pts'],
                               cache_index=box['cache_index']))
    return result


def source_state(state):
    result = deepcopy(state)
    result['incident_id'] = result.pop('source_incident_id')
    return result


def frozen_schedule(prior, frames):
    """Read causal snapshots, NEVER seed replay with final evidence states."""
    if prior.get('experiment') != 'EXP-0048':
        raise ValueError('Successful frozen EXP-0048 lifecycle output required')
    stamps = [clock(r['pts']) for r in frames]
    if (not stamps or any(a >= b for a, b in zip(stamps, stamps[1:]))
            or any(r['frame_index'] != i for i, r in enumerate(frames))):
        raise ValueError('Complete chronological saved source frames required')
    def locate(at):
        index = bisect_left(stamps, at-1e-9)
        if index == len(stamps) or abs(stamps[index]-at) > 1e-9:
            raise ValueError('Frozen decision must bind to an actual source frame')
        return index
    by_id = {e['event_id']: deepcopy(e) for e in prior['events']}
    if not by_id or len(by_id) != len(prior['events']):
        raise ValueError('Nonempty unique frozen candidate stream required')
    scopes = {tuple(e[k] for k in ('session_id','camera_id','gate_id')) for e in by_id.values()}
    if len(scopes) != 1:
        raise ValueError('Do not mix recording/camera/gate streams')
    candidates, updates = defaultdict(list), defaultdict(dict)
    for event in by_id.values():
        candidates[locate(clock(event['decision_time_pts']))].append(event)
    latest = {}; last = -1.
    for snapshot in prior['timeline']:
        at = clock(snapshot['decision_time_pts'])
        if at < last:
            raise ValueError('Source snapshot time went backwards')
        last = at; index = locate(at)
        for state in snapshot['evidence']:
            eid = state['event_id']
            if (eid not in by_id or by_id[eid]['decision_time_pts'] > at
                    or state['incident_id'] != snapshot['incident_id']):
                raise ValueError('Source snapshot has unknown/future/misbound evidence')
            if eid not in latest and by_id[eid]['decision_time_pts'] != at:
                raise ValueError('Missing evidence at its actual opening timestamp')
            if latest.get(eid) != state:
                if eid in updates[index] and updates[index][eid] != state:
                    raise ValueError('Conflicting evidence snapshots at the same timestamp')
                updates[index][eid] = deepcopy(state)
                latest[eid] = deepcopy(state)
    final = {s['event_id']: s for s in prior['evidence']}
    if len(final) != len(prior['evidence']) or latest != final or set(final) != set(by_id):
        raise ValueError('Source timeline does not reproduce its frozen final evidence')
    return candidates, updates, dict(zip(('session_id','camera_id','gate_id'), next(iter(scopes))))


def replay_activity(prior, frames, portal, *, policy=ActivityPolicy(), detection_floor=.25,
                    namespace=None):
    candidates, updates, scope = frozen_schedule(prior, frames)
    namespace = namespace or 'EXP-0049:'+digest(dict(scope=scope, policy=policy.__dict__))[:16]
    life = GateActivityEpisodes(scope, namespace=namespace, policy=policy)
    expected = {}
    for i, frame in enumerate(frames):
        batch = list(updates[i].values())
        expected.update({s['event_id']: deepcopy(s) for s in batch})
        refs = activity_references(frame, portal, detection_floor)
        life.step(i, frame['pts'], portal_refs=refs, candidates=candidates[i], evidence_updates=batch)
        # Membership may change; EVERY source evidence field must remain exact.
        if {eid: source_state(s) for eid, s in life.evidence.items()} != expected:
            raise ValueError('Regrouping changed an evidence state or its source time')
    result = life.export()
    if {e['event_id']: e for e in result['events']} != {e['event_id']: e for e in prior['events']}:
        raise ValueError('Frozen raw candidates changed')
    result.update(video_id=prior['video_id'], source_window=deepcopy(prior['source_window']),
        available_after_pts=prior.get('available_after_pts', prior['source_window'][1]),
        source_experiment='EXP-0048', source_candidate_sha256=digest(prior['events']),
        source_resolution_log=deepcopy(prior.get('resolutions', [])),
        source_resolution_ids_refer_to_prior_cards=True,
        source_outcome_routing=deepcopy(prior.get('outcome_routing', [])),
        preserved_confirmation_source_pts=deepcopy(prior.get('preserved_confirmation_source_pts', {})),
        evidence_prefix_checks=len(frames), source_evidence_states_preserved=True,
        source_frames_with_portal_presence=sum(r['portal_present'] for r in result['activity_audit']),
        source_end_pts=frames[-1]['pts'], detector_calls=0, tracker_calls=0,
        flow_calls=0, vlm_calls=0, release_rule_changed=False, direction_rule_changed=False)
    mapping = defaultdict(set)
    for e in result['evidence']:
        mapping[e['source_incident_id']].add(e['incident_id'])
    result['source_to_activity_cards'] = {k: sorted(v) for k, v in mapping.items()}
    return result


def prepare_inputs(previous_directory, paths_directory, portal_directory):
    """Read-only full-input preflight; never runs the activity replay."""
    from .portal_births import PortalGate
    from .gate_episode_evidence import EpisodePolicy
    previous, paths, portal_dir = map(Path, (previous_directory, paths_directory, portal_directory))
    request, summary = load(previous/'request.json'), load(previous/'summary.json')
    prior = load(previous/'lifecycle-cards.json')
    if request.get('experiment') != 'EXP-0048' or summary.get('experiment') != 'EXP-0048':
        raise ValueError('Use successful EXP48 v2 outputs, not failed or superseded attempts')
    if request['input_sha256'] != summary['input_sha256']:
        raise ValueError('Prior input bindings disagree')
    protected = dict(request['input_sha256'])
    evidence_path = paths/'frame-evidence.jsonl'
    required = (evidence_path, portal_dir/'portal-region.json', portal_dir/'scene-used.json')
    for p in required:
        if str(p) not in protected or sha(p) != protected[str(p)]:
            raise ValueError('Required source is not bound to the prior comparison: '+str(p))
    for p, expected in protected.items():
        if sha(p) != expected:
            raise ValueError('Frozen input changed: '+p)
    for p in (previous/'request.json', previous/'summary.json', previous/'lifecycle-cards.json',
              paths/'summary.json'):
        protected[str(p)] = sha(p)
    frames = [json.loads(line) for line in evidence_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    path_summary = load(paths/'summary.json')
    if (len(frames) != summary['frames'] or len(frames) != path_summary['frames']
            or prior['video_id'] != summary['video_id'] or prior['video_id'] != path_summary['video_id']):
        raise ValueError('Source video or complete frame partition differs')
    for r in frames:
        if abs(float(Fraction(r['native_pts'])*Fraction(r['time_base']))-r['pts']) > 1e-7:
            raise ValueError('Original PTS/time base mismatch')
        indices = [b['cache_index'] for b in r['actual_boxes']]
        if len(indices) != len(set(indices)):
            raise ValueError('Duplicate saved actual box reference')
    scene, region = load(portal_dir/'scene-used.json'), load(portal_dir/'portal-region.json')
    camera = prior['events'][0]['camera_id']
    gate = PortalGate(scene, region, camera)
    policy, floor = ActivityPolicy().validate(), EpisodePolicy().validate().detection_floor
    files = ('exp0049_application.py','gate_activity_episodes.py','portal_births.py','gate_episode_evidence.py')
    code = {str(Path(__file__).with_name(n)): sha(Path(__file__).with_name(n)) for n in files}
    frozen_schedule(prior, frames)
    # Validate every actual portal lookup before creating a comparison output.
    for frame in frames:
        activity_references(frame, gate, floor)
    return prior, frames, gate, policy, floor, protected, code


def execute(previous_directory, paths_directory, portal_directory, output):
    begin = time.perf_counter()
    previous, paths, portal_dir, out = map(Path, (previous_directory, paths_directory, portal_directory, output))
    if (out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents)
            or not out.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Use a new non-symlink output directory under outputs/')
    prior, frames, gate, policy, floor, protected, code = prepare_inputs(previous, paths, portal_dir)
    region = load(portal_dir/'portal-region.json')
    out.mkdir(parents=True, exist_ok=False)
    save(out/'request.json', dict(experiment='EXP-0049', activity_policy=asdict_policy(policy),
        detection_floor=floor, prior_directory=str(previous), paths_directory=str(paths),
        portal_directory=str(portal_dir), input_sha256=protected, code_sha256=code,
        new_inference=False, new_decisions=False, grouping_only=True))
    try:
        result = replay_activity(prior, frames, gate, policy=policy, detection_floor=floor,
            namespace='EXP-0049:'+digest(dict(video=prior['video_id'],region=region,policy=asdict_policy(policy)))[:16])
        if protected != {p: sha(p) for p in protected} or code != {p: sha(p) for p in code}:
            raise ValueError('Source input or code changed during comparison')
        (out/'prior-lifecycle-preserved.json').write_bytes((previous/'lifecycle-cards.json').read_bytes())
        save(out/'activity-cards.json', result)
        save(out/'activity-audit.json', result['activity_audit'])
        save(out/'notification-intents.json', result['notification_intents'])
        save(out/'card-mapping.json', result['source_to_activity_cards'])
        notices = lambda b: [dict(kind=n['kind'], pts=n['decision_time_pts'], incident_id=n['incident_id'])
                             for n in b['notification_intents']]
        report = dict(experiment='EXP-0049', video_id=prior['video_id'], frames=len(frames),
            prior_counts=prior['counts'], counts=result['counts'], prior_notices=notices(prior),
            notices=notices(result), source_evidence_states_preserved=True,
            evidence_prefix_checks=result['evidence_prefix_checks'],
            source_frames_with_portal_presence=result['source_frames_with_portal_presence'],
            closures=[dict(incident_id=c['incident_id'], pts=c['observation_closed_pts'],
                           reason=c['observation_close_reason'], status=c['automatic_status'])
                      for c in result['closed_cards']],
            unresolved_closed_cards=sum(c['automatic_status']=='침입 의심' for c in result['closed_cards']),
            source_end_forced_release=False, input_sha256=protected, code_sha256=code,
            elapsed_seconds=time.perf_counter()-begin, detector_calls=0, tracker_calls=0,
            flow_calls=0, vlm_calls=0, external_notifications_sent=0,
            accuracy=None, realtime=False, visual_validation='pending',
            limitations=['Only grouping changes; frozen per-evidence decisions, including their limitations, remain.',
                'Portal occupancy can include a different passerby or persistent false box.',
                'A detection gap longer than grace can split a physically continuous situation.',
                'Closing observation is not suspicion release, and a merged card does not verify every person.',
                'Confirmations are not backdated; source gaps interrupt grouping without a normal verdict.',
                'Final source frame is not an artificial empty observation or release.',
                'A new viewer adapter is required for open/closed status separate from automatic status.'])
        save(out/'summary.json', report)
        return report
    except Exception as exc:
        save(out/'failure.json', dict(error=repr(exc), elapsed_seconds=time.perf_counter()-begin))
        raise


def asdict_policy(policy):
    return dict(empty_grace_seconds=policy.empty_grace_seconds, source_gap_seconds=policy.source_gap_seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'paths', 'portal-result', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.previous, args.paths, args.portal_result, args.output),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
