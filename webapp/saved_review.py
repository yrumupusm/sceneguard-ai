"""Review saved results and render exact saved observations; never run analysis."""
from collections import OrderedDict
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import threading
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from .app import app, artifact, config, safe_open
from .assessment_store import AssessmentStore
from sceneguard.review_store import ReviewConflict


def binding(bundle_id, session_id, bundle_sha256, incident_id=None):
    from .incident import registered
    bundle = registered(bundle_id)
    if (session_id, bundle_sha256) != (bundle['session_id'], bundle['bundle_sha256']):
        raise HTTPException(409, 'bundle changed; reload the saved result')
    if incident_id is not None and incident_id not in {r['incident_id'] for r in bundle['timeline']}:
        raise HTTPException(404, 'unregistered card')
    return bundle


def store():
    try:
        return AssessmentStore(Path(config()['runtime_dir']) / 'saved-result-assessments.sqlite3')
    except (OSError, ValueError, sqlite3.Error, KeyError):
        raise HTTPException(503, 'assessment store unavailable')


def result(store, key):
    return dict(review=store.get(*key), history=store.history(*key))


def read_assessment(bundle_id, session_id, bundle_sha256, subject, *, omission=False):
    binding(bundle_id, session_id, bundle_sha256, None if omission else subject)
    try:
        return result(store(), (session_id, subject, bundle_sha256))
    except (OSError, ValueError, sqlite3.Error, KeyError):
        raise HTTPException(503, 'assessment store unavailable')


async def write_assessment(bundle_id, subject, request, *, omission=False):
    from .incident import same_origin_json
    same_origin_json(request)
    try:
        body = await request.json()
        fields = {'status', 'time_pts'} if omission else {'event_assessment', 'bbox_quality'}
        if not isinstance(body, dict) or set(body) != fields | {'session_id', 'bundle_sha256', 'expected_version', 'reviewer', 'note'}:
            raise ValueError('invalid assessment fields')
        session, digest = body.pop('session_id'), body.pop('bundle_sha256')
        bundle = binding(bundle_id, session, digest, None if omission else subject)
        at = body.get('time_pts')
        if at is not None and (type(at) not in (int, float) or not math.isfinite(at) or not bundle['source_window'][0] <= at <= bundle['source_window'][1]):
            raise ValueError('timestamp outside saved source window')
        db = store()
        key = (session, subject, digest)
        review = db.save(*key, **body)
        return dict(review=review, history=db.history(*key))
    except ReviewConflict:
        return JSONResponse(status_code=409, content=result(db, key))
    except (ValueError, TypeError):
        raise HTTPException(400, 'invalid assessment')
    except (OSError, sqlite3.Error, KeyError):
        raise HTTPException(503, 'assessment store unavailable')


@app.get('/api/incidents/{bundle_id}/assessments/{incident_id}')
def get_assessment(bundle_id: str, incident_id: str, session_id: str, bundle_sha256: str):
    return read_assessment(bundle_id, session_id, bundle_sha256, incident_id)


@app.post('/api/incidents/{bundle_id}/assessments/{incident_id}')
async def save_assessment(bundle_id: str, incident_id: str, request: Request):
    return await write_assessment(bundle_id, incident_id, request)


@app.get('/api/incidents/{bundle_id}/omission-review')
def get_omission(bundle_id: str, session_id: str, bundle_sha256: str):
    return read_assessment(bundle_id, session_id, bundle_sha256, 'video-omission', omission=True)


@app.post('/api/incidents/{bundle_id}/omission-review')
async def save_omission(bundle_id: str, request: Request):
    return await write_assessment(bundle_id, 'video-omission', request, omission=True)


def checked(c, path, digest=None):
    path = Path(path)
    root = Path(c['artifact_allow_root'])
    relative = path.relative_to(root) if path.is_absolute() else path
    with safe_open(root, relative) as source:
        raw = source.read()
    if digest is not None and hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('saved evidence hash mismatch')
    return raw


def saved_inputs(c, bundle_id, bundle):
    entry = c['incident_bundles'][bundle_id]
    if entry['experiment_id'] != 'MVP-0002':
        raise ValueError('legacy_bundle_without_evidence_mapping')
    manifest = json.loads(checked(c, entry['manifest_path'], entry['manifest_sha256']))
    folder = Path(entry['manifest_path']).parent
    cards = json.loads(checked(c, manifest['cards_path'], bundle['bundle_sha256']))
    if manifest['run_id'] != bundle['session_id'] or manifest['cards_sha256'] != bundle['bundle_sha256']:
        raise ValueError('saved evidence binding mismatch')
    frames = json.loads(checked(c, manifest['source_frames_path'], manifest['source_frames_sha256']))
    decision = json.loads(checked(c, folder / 'decision/stage.json'))
    if decision['status'] != 'complete' or decision['artifacts']['cards.json'] != bundle['bundle_sha256']:
        raise ValueError('saved decision stage mismatch')
    paths = json.loads(checked(c, folder / 'image-paths/stage.json', decision['binding']['paths']))
    if paths['status'] != 'complete':
        raise ValueError('incomplete saved observation stage')
    raw = checked(c, folder / 'image-paths/frame-evidence.jsonl', paths['artifacts']['frame-evidence.jsonl'])
    # Read only saved actual_boxes; point paths, predictions and lost states are ignored.
    observations = {}
    for line in raw.splitlines():
        row = json.loads(line)
        index = row['frame_index']
        if type(index) is not int or index in observations:
            raise ValueError('invalid saved frame index')
        observations[index] = row
    originals = [m for m in manifest['media'] if m['key'] == 'original']
    if len(originals) != 1 or originals[0]['path'] != c['artifacts'][bundle['media_artifact_id']]['path']:
        raise ValueError('original video binding mismatch')
    return cards, frames, observations, originals[0]


def valid_frame(frame):
    if type(frame['frame_index']) is not int or frame['frame_index'] < 0 or type(frame['native_pts']) is not int or frame['native_pts'] < 0:
        raise ValueError('invalid native frame identity')
    for field in ('pts', 'playback_seconds'):
        if type(frame[field]) not in (int, float) or not math.isfinite(frame[field]) or frame[field] < 0:
            raise ValueError('invalid saved frame time')
    tb = Fraction(frame['time_base'])
    if tb <= 0 or abs(float(frame['native_pts'] * tb) - frame['pts']) > 1e-7:
        raise ValueError('native source clock mismatch')


def incident_refs(snapshot, events):
    refs = []
    for evidence in snapshot.get('evidence', []):
        saved_binding = evidence.get('binding', {})
        refs.extend(saved_binding.get('refs', []))
        if saved_binding.get('reference'):
            refs.append(saved_binding['reference'])
    refs.extend(snapshot['card'].get('last_gate_observation_refs', []))
    for event in events:
        if event['event_id'] in snapshot['card']['event_ids']:
            refs.extend(event.get('source_event', {}).get('observation_refs', []))
    return refs


def observed_boxes(row, snapshot, events, at):
    refs = incident_refs(snapshot, events)
    indices = {r['cache_index'] for r in refs if r.get('pts') == at and r.get('frame_index') == row['frame_index']}
    tracks = set(snapshot['card'].get('track_ids', []))
    boxes = []
    seen = set()
    for box in row['actual_boxes']:
        index, coords = box['cache_index'], box['bbox']
        if type(index) is not int or index < 0 or index in seen:
            raise ValueError('invalid actual box reference')
        seen.add(index)
        if (not isinstance(coords, list) or len(coords) != 4 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in coords) or
                not (0 <= coords[0] < coords[2] <= 1 and 0 <= coords[1] < coords[3] <= 1)):
            raise ValueError('invalid actual box')
        # Explicitly reject any future schema that marks an actual entry predicted.
        if ('observed' in box and box['observed'] is not True) or ('predicted' in box and box['predicted'] is not False):
            continue
        if index in indices or tracks.intersection(box.get('track_ids', [])):
            boxes.append(dict(cache_index=index, bbox=coords, track_ids=box.get('track_ids', []),
                              source='saved_actual_observation'))
    return boxes


def last_observation(snapshot, events, frames, observations, decision_pts):
    """A prior reference gets its own frame and clock; never move its box forward."""
    refs = incident_refs(snapshot, events)
    by_index = {f['frame_index']: f for f in frames}
    candidates = {(r['pts'], r['frame_index']) for r in refs
                  if type(r.get('pts')) in (int, float) and math.isfinite(r['pts'])
                  and 0 <= r['pts'] < decision_pts and type(r.get('frame_index')) is int}
    for at, index in sorted(candidates, reverse=True):
        frame, row = by_index.get(index), observations.get(index)
        if frame is None or row is None or frame['pts'] != at:
            continue
        valid_frame(frame)
        if any(row[k] != frame[k] for k in ('pts', 'native_pts', 'time_base')):
            raise ValueError('prior observation/source clock mismatch')
        # Restrict this image to explicit saved references, not other tracks or
        # current-time predictions. The reference does not establish identity.
        saved = dict(card={'event_ids': [], 'track_ids': [], 'last_gate_observation_refs': refs})
        boxes = observed_boxes(row, saved, [], at)
        if boxes:
            return dict(available=True, reason=None, decision_time_pts=decision_pts,
                        seconds_before_decision=decision_pts - at,
                        frame={k: frame[k] for k in ('pts', 'native_pts', 'time_base', 'frame_index', 'playback_seconds')},
                        boxes=boxes, image_url=None)
    return dict(available=False, reason='no_saved_incident_observation_before_decision',
                decision_time_pts=decision_pts, seconds_before_decision=None,
                frame=None, boxes=[], image_url=None)


def evidence_data(c, bundle_id, incident_id, bundle):
    snapshots = [r for r in bundle['timeline'] if r['incident_id'] == incident_id]
    first = snapshots[0]['card']
    final = snapshots[-1]['card']
    times = [('suspicion', first['first_alert_pts']), ('confirmation', final.get('first_confirmation_pts'))]
    query = urlencode(dict(session_id=bundle['session_id'], bundle_sha256=bundle['bundle_sha256']))
    response = dict(session_id=bundle['session_id'], bundle_sha256=bundle['bundle_sha256'], incident_id=incident_id,
                    original_media_url='/artifacts/' + bundle['media_artifact_id'], items=[])
    try:
        cards, frames, observations, original = saved_inputs(c, bundle_id, bundle)
        error = None
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        cards, frames, observations, original = {}, [], {}, None
        error = 'saved_evidence_mapping_unavailable'
    for kind, at in times:
        item = dict(kind=kind, decision_time_pts=at, available=False, reason=error,
                    frame=None, boxes=[], image_url=None, last_observation=None)
        if at is None:
            item['reason'] = 'no_automatic_confirmation'
        elif error is None:
            try:
                matches = [f for f in frames if f['pts'] == at]
                if len(matches) != 1:
                    raise ValueError('exact source frame unavailable')
                frame = matches[0]
                valid_frame(frame)
                row = observations[frame['frame_index']]
                if any(row[k] != frame[k] for k in ('pts', 'native_pts', 'time_base')):
                    raise ValueError('observation/source frame mismatch')
                # Use only the snapshot existing at this decision, never final tracks.
                snapshot = next(r for r in cards['timeline'] if r['incident_id'] == incident_id and r['decision_time_pts'] == at)
                boxes = observed_boxes(row, snapshot, cards['events'], at)
                item.update(available=True, reason=None if boxes else 'no_incident_observation_at_decision',
                            frame={k: frame[k] for k in ('pts', 'native_pts', 'time_base', 'frame_index', 'playback_seconds')}, boxes=boxes,
                            image_url=f'/api/incidents/{bundle_id}/evidence/{incident_id}/{kind}.jpg?{query}')
            except (ValueError, TypeError, KeyError, StopIteration, ZeroDivisionError):
                item['reason'] = 'exact_saved_frame_unavailable'
            try:
                snapshot = next(r for r in cards['timeline'] if r['incident_id'] == incident_id and r['decision_time_pts'] == at)
                prior = last_observation(snapshot, cards['events'], frames, observations, at)
                if prior['available']:
                    prior['image_url'] = f'/api/incidents/{bundle_id}/evidence/{incident_id}/{kind}-last-observation.jpg?{query}'
                item['last_observation'] = prior
            except (ValueError, TypeError, KeyError, StopIteration, ZeroDivisionError):
                item['last_observation'] = dict(available=False, reason='saved_prior_observation_unavailable',
                    decision_time_pts=at, seconds_before_decision=None, frame=None, boxes=[], image_url=None)
        response['items'].append(item)
    return response, original


@app.get('/api/incidents/{bundle_id}/evidence/{incident_id}')
def get_evidence(bundle_id: str, incident_id: str, session_id: str, bundle_sha256: str):
    bundle = binding(bundle_id, session_id, bundle_sha256, incident_id)
    return evidence_data(config(), bundle_id, incident_id, bundle)[0]


_image_cache = OrderedDict()
_image_lock = threading.Lock()


@app.get('/api/incidents/{bundle_id}/evidence/{incident_id}/{kind}.jpg')
def evidence_image(bundle_id: str, incident_id: str, kind: str, session_id: str, bundle_sha256: str):
    bundle = binding(bundle_id, session_id, bundle_sha256, incident_id)
    if kind not in ('suspicion', 'confirmation', 'suspicion-last-observation', 'confirmation-last-observation'):
        raise HTTPException(404, 'unknown evidence kind')
    c = config()
    data, original = evidence_data(c, bundle_id, incident_id, bundle)
    item = next(i for i in data['items'] if i['kind'] == kind.removesuffix('-last-observation'))
    if kind.endswith('-last-observation'):
        item = item.get('last_observation')
    if not item or not item['available']:
        raise HTTPException(404, item['reason'] if item else 'saved prior observation unavailable')
    # A source FD, never a client path, crosses into the fixed CPU-only helper.
    try:
        with artifact(c, bundle['media_artifact_id'])[0] as video:
            actual = hashlib.file_digest(video, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else None
            if actual is None:
                digest = hashlib.sha256()
                for chunk in iter(lambda: video.read(1024 * 1024), b''):
                    digest.update(chunk)
                actual = digest.hexdigest()
            if actual != original['sha256']:
                raise ValueError('original video hash mismatch')
            video.seek(0)
            cache_key = (actual, json.dumps(item, sort_keys=True))
            with _image_lock:
                image = _image_cache.get(cache_key)
                if image is None:
                    interpreter = Path(c['repo_root']) / '.venv-cv-batch02/bin/python'
                    helper = Path(__file__).with_name('evidence_image.py')
                    completed = subprocess.run([str(interpreter), '-I', str(helper), str(video.fileno())],
                        input=json.dumps(item).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        pass_fds=(video.fileno(),), timeout=30, check=True,
                        env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1'})
                    image = completed.stdout
                    if not image.startswith(b'\xff\xd8') or len(image) > 4 * 1024 * 1024:
                        raise ValueError('invalid evidence JPEG')
                    _image_cache[cache_key] = image
                    if len(_image_cache) > 32:
                        _image_cache.popitem(last=False)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        raise HTTPException(503, 'exact evidence image unavailable')
    return Response(image, media_type='image/jpeg', headers={'Cache-Control': 'private, no-store'})
