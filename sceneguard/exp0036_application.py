"""EXP-0036 presentation-only grouping of saved EXP-0035 + preserved gap alerts.

No media inference, tracker, identity merge, ROI change or candidate deletion.
The raw EXP-0035 file is read-only. losses/review_changes are not counted twice.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .incident_cards import GroupPolicy, canonical, finite, text, group_events


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def normalize_result(result, camera_id, gate_id, session_id):
    if result.get('experiment') != 'EXP-0035':
        raise ValueError('Expected saved EXP-0035 result, not a new analysis')
    video = text(result.get('video_id'), 'video_id')
    scope = dict(session_id=text(session_id, 'session_id'),
                 camera_id=text(camera_id, 'camera_id'), gate_id=text(gate_id, 'gate_id'))
    if len(result.get('source_window', [])) != 2:
        raise ValueError('Actual source PTS window required')
    start, end = [finite(x, 'source PTS') for x in result['source_window']]
    if end <= start:
        raise ValueError('Empty or reversed source PTS window')
    normalized, ignored = [], []
    for collection in ('events', 'existing_alerts'):
        if not isinstance(result.get(collection), list):
            raise ValueError(f'Expected source collection {collection}')
        for index, raw in enumerate(result[collection]):
            pointer = f'/{collection}/{index}'
            if collection == 'events' and raw.get('status') != '침입 의심':
                ignored.append(dict(source_pointer=pointer, source_event=deepcopy(raw)))
                continue
            if collection == 'existing_alerts':
                if raw.get('video_id', video) != video or raw.get('condition', 'gap') != 'gap':
                    raise ValueError('Preserved alert video/condition mismatch')
                at = finite(raw.get('emitted_at_pts'), 'existing alert emission PTS')
                tid = raw.get('track_id')
            else:
                at = finite(raw.get('decision_time_pts'), 'actual decision PTS')
                tid = raw.get('raw_id')
            if not start-1e-6 <= at <= end+1e-6:
                raise ValueError('Alert time outside actually observed input window')
            if raw.get('boundary_id') not in (None, gate_id):
                raise ValueError('Alert belongs to a different gate')
            if tid is not None and (type(tid) is not int or tid < 0):
                raise ValueError('Invalid original tracking ID')
            binding = dict(video_id=video, collection=collection, row=index, raw=raw, **scope)
            eid = _sha(canonical(binding).encode())
            normalized.append(dict(**scope, event_id=eid, video_id=video,
                decision_time_pts=at, status='침입 의심', track_ids=[] if tid is None else [tid],
                source_ref=dict(collection=collection, source_pointer=pointer,
                    segment=raw.get('segment'), raw_id=tid), source_event=deepcopy(raw)))
    return normalized, ignored


def make_bundle(result, camera_id, gate_id, session_id, policy=GroupPolicy()):
    events, ignored = normalize_result(result, camera_id, gate_id, session_id)
    bundle = group_events(events, policy)
    bundle.update(experiment='EXP-0036', baseline_experiment='EXP-0035',
        video_id=result['video_id'], source_window=deepcopy(result['source_window']),
        available_after_pts=result.get('available_after_pts', result['source_window'][1]),
        ignored_non_alert_rows=ignored,
        source_alert_policy='events + existing_alerts only; losses/review_changes not re-counted',
        status='grouped_review_candidates_not_verified_intrusions',
        false_alarm_status='unchanged_underlying_candidates; regrouping_does_not_remove_false_alarms',
        identity_verified=False, detector_calls=0, tracker_calls=0, vlm_calls=0)
    return bundle


def execute(result_path, output, camera_id, gate_id, session_id, policy=GroupPolicy()):
    src, dst = Path(result_path), Path(output)
    if (dst.exists() or dst.is_symlink() or any(p.is_symlink() for p in dst.parents)
            or not dst.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Use a NEW non-symlink local outputs file')
    raw = src.read_bytes()
    result = json.loads(raw)
    bundle = make_bundle(result, camera_id, gate_id, session_id, policy)
    bundle['provenance'] = dict(source_result=str(src), source_sha256=_sha(raw),
        code_sha256={p.name:_sha(p.read_bytes()) for p in
                     (Path(__file__), Path(__file__).with_name('incident_cards.py'))},
        utc=datetime.now(timezone.utc).isoformat())
    if src.read_bytes() != raw:
        raise ValueError('Source changed while grouping')
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open('x', encoding='utf-8') as stream:
        json.dump(bundle, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return bundle


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--result', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--camera-id', required=True)
    p.add_argument('--gate-id', required=True)
    p.add_argument('--session-id', required=True, help='Distinct recording session, not raw person ID')
    a=p.parse_args()
    bundle=execute(a.result,a.output,a.camera_id,a.gate_id,a.session_id)
    print(json.dumps(bundle['counts'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
