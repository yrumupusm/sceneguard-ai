"""EXP-0041: replay saved EXP-0040 scores; group before notification filtering.

No video decoding, feature recomputation, detector, tracker, VLM or GPU call.
0.55 is an evaluation candidate, not an automatically adopted operating setting.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from .incident_cards import GroupPolicy, finite, group_events
from .incident_notifications import group_notifications, episode_comparison

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = (.55, .65, .70)
LOSS_REASON = 'recent_gate_presence_then_loss'


def _read_json(data):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('Duplicate JSON key: '+key)
            out[key] = value
        return out
    def invalid(value):
        raise ValueError('Nonfinite JSON number: '+value)
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_saved(baseline, audits):
    """Bind scores to complete original candidate rows, not to labels or ID guesses."""
    if baseline.get('experiment') != 'EXP-0036':
        raise ValueError('Use EXP-0040 baseline-cards.json with its EXP-0036 contract')
    policy = GroupPolicy(**baseline['policy']).validate()
    if policy != GroupPolicy():
        raise ValueError('Keep the existing 3-second / 10-second grouping policy')
    events = baseline['events']
    if len({e['event_id'] for e in events}) != len(events):
        raise ValueError('Saved baseline must contain unique normalized event IDs')
    scopes = {tuple(e[k] for k in ('session_id','camera_id','gate_id')) for e in events}
    if len(scopes) > 1:
        raise ValueError('Compare one source/session/camera/gate per saved input')
    rebuilt = group_events(events, policy)
    for key in ('cards','counts','timeline'):
        if baseline[key] != rebuilt[key]:
            raise ValueError('Saved baseline grouping differs: '+key)
    expected = {}
    for e in events:
        if (e['source_ref']['collection']=='events' and
                e['source_event'].get('reason')==LOSS_REASON):
            pointer = e['source_ref']['source_pointer']
            if pointer in expected:
                raise ValueError('Duplicate loss source pointer')
            expected[pointer] = e
    if not isinstance(audits, list):
        raise ValueError('Saved audits must be a list')
    seen = set()
    for row in audits:
        pointer = row['source_pointer']
        if pointer not in expected or pointer in seen:
            raise ValueError('Unexpected or repeated score audit')
        seen.add(pointer)
        e = expected[pointer]
        at = finite(e['decision_time_pts'], 'original decision PTS')
        if (row['original_event_id'] != e['event_id'] or
                row['original_source_ref'] != e['source_ref'] or
                type(row['raw_id']) is not int or row['raw_id'] not in e['track_ids'] or
                row['segment'] != e['source_ref']['segment']):
            raise ValueError('Audit event/source/target binding differs')
        if any(abs(finite(row[k], k)-at)>1e-6 for k in
               ('decision_time_pts','evidence_until_pts')):
            raise ValueError('Score evidence must end at the original decision time')
        last = finite(row['last_observed_pts'], 'last observation PTS')
        if last >= at or abs(last-e['source_event']['last_observed_pts'])>1e-6:
            raise ValueError('Last-observation binding differs')
        if not isinstance(row['alternatives'], list):
            raise ValueError('Saved seed alternatives required')
        for alt in row['alternatives']:
            score = finite(alt['score'], 'saved continuity score')
            if score > 1:
                raise ValueError('Continuity score outside [0,1]')
            if 'seed_pts' in alt and finite(alt['seed_pts'], 'seed PTS') > last:
                raise ValueError('Future seed must not change an earlier decision')
            if 'evidence_until_pts' in alt and abs(finite(alt['evidence_until_pts'], 'seed evidence PTS')-at)>1e-6:
                raise ValueError('Seed evidence differs from alert time')
            b = alt.get('endpoint_bbox')
            if b is not None:
                if (not isinstance(b, list) or len(b)!=4 or
                        any(finite(x,'box coordinate')>1 for x in b) or
                        not b[0]<b[2] or not b[1]<b[3]):
                    raise ValueError('Invalid saved endpoint box')
            elif score != 0:
                raise ValueError('Positive saved score lacks an endpoint')
    if seen != set(expected):
        raise ValueError('Missing saved audit; do not silently omit a loss case')
    return policy


def replay(baseline, audits, threshold):
    """Use unchanged seed conflict/independent-boundary protection from EXP-0040."""
    if type(threshold) not in (int, float) or threshold not in THRESHOLDS:
        raise ValueError('Compare only the agreed .55/.65/.70 thresholds')
    policy = validate_saved(baseline, audits)
    from .practical_continuation import seed_decision, notification_partition
    decisions = deepcopy(audits)
    for row in decisions:
        row.update(seed_decision(row['alternatives'], threshold))
    active, review = notification_partition(baseline['events'], decisions)
    review_ids = {e['event_id'] for e in review}
    # Saved audits carry the old 0.70 disposition; never expose it as this result.
    for row in decisions:
        removed = row['original_event_id'] in review_ids
        row['notification_action'] = 'review_only' if removed else 'keep'
        row['partition_reason'] = ('independent_boundary_evidence_preserved'
            if not removed and row['recommendation']=='review_only' else row['reason'])
    result = group_notifications(baseline['events'], review_ids, policy)
    if result['active_events'] != active or result['review_only_events'] != review:
        raise ValueError('Notification partition changed original rows')
    for key in ('video_id','source_window','available_after_pts','ignored_non_alert_rows'):
        if key in baseline:
            result[key] = deepcopy(baseline[key])
    result.update(experiment='EXP-0041', baseline_experiment='EXP-0040',
        score_threshold=threshold, evaluation_candidate=(threshold==.55),
        adopted=False, identity_verified=False, automatic_confirmation=False,
        accuracy=None, realtime=False, flow_recomputed=False,
        detector_calls=0, tracker_calls=0, vlm_calls=0,
        decision_audits=decisions, episode_comparison=episode_comparison(baseline,result))
    if result['counts']['notification_intents'] > len(baseline['cards']):
        raise AssertionError('Filtering must not increase episode notifications')
    return result


def execute(saved_results, output):
    begin = time.perf_counter()
    src, dst = Path(saved_results).absolute(), Path(output).absolute()
    for path in (src, dst):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError('Use local paths without symlink redirection')
    if dst.exists() or not dst.resolve().is_relative_to((ROOT/'outputs').resolve()):
        raise ValueError('Use a NEW local outputs directory')
    names = ('baseline-cards.json','audits.json','summary.json','request.json')
    paths = {name: src/name for name in names}
    if any(p.is_symlink() or not p.is_file() for p in paths.values()):
        raise ValueError('Complete saved EXP-0040 results required')
    raw = {name: p.read_bytes() for name,p in paths.items()}
    baseline, audits, summary, request = [_read_json(raw[n]) for n in names]
    if (summary.get('experiment')!='EXP-0040' or request.get('experiment')!='EXP-0040' or
            summary.get('baseline_counts')!=baseline['counts'] or
            summary.get('cases')!=len(audits)):
        raise ValueError('Input is not a complete bound EXP-0040 result')
    source_files = [Path(__file__), Path(__file__).with_name('incident_notifications.py'),
                    Path(__file__).with_name('incident_cards.py'),
                    Path(__file__).with_name('practical_continuation.py')]
    code = {p.name: _sha(p.read_bytes()) for p in source_files}
    results = {f'{t:.2f}': replay(baseline,audits,t) for t in THRESHOLDS}
    prior_review = {e['event_id'] for e in results['0.70']['review_only_events']}
    review_plan = []
    for e in baseline['events']:
        chosen = [key for key,value in results.items()
                  if e['event_id'] in {r['event_id'] for r in value['review_only_events']}]
        if chosen:
            review_plan.append(dict(event_id=e['event_id'],source_ref=e['source_ref'],
                decision_time_pts=e['decision_time_pts'], review_at_thresholds=chosen,
                additional_to_070=e['event_id'] not in prior_review,
                scene_review_status='consult_existing_review_then_review_new_exclusions'))
    receipt = dict(experiment='EXP-0041', source_directory=str(src),
        source_sha256={n:_sha(b) for n,b in raw.items()}, code_sha256=code,
        thresholds=list(THRESHOLDS), baseline_counts=baseline['counts'],
        video_id=baseline.get('video_id'),
        results={k:dict(counts=v['counts'],episode_comparison=v['episode_comparison'])
                 for k,v in results.items()},
        elapsed_seconds=time.perf_counter()-begin, computation='saved_score_replay_only',
        feature_calls=0, detector_calls=0, tracker_calls=0, vlm_calls=0,
        original_inputs_unchanged=True, accuracy=None, adopted=False,
        behavior_review='pending', live_notifications_enabled=False)
    if (any(paths[n].read_bytes()!=raw[n] for n in names) or
            code!={p.name:_sha(p.read_bytes()) for p in source_files}):
        raise ValueError('Input or replay source changed during processing')
    dst.mkdir(parents=True,exist_ok=False)
    def write(name,value):
        with (dst/name).open('x',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
            f.write('\n')
    write('baseline-cards.json',baseline)
    for key,value in results.items():
        write('threshold-'+key.replace('.','')+'.json',value)
    write('review-plan.json',dict(experiment='EXP-0041',cases=review_plan))
    write('summary.json',receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved-results',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    report = execute(args.saved_results,args.output)
    print(json.dumps(dict(video_id=report['video_id'],results=report['results']),
                     ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
