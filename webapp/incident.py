"""Registered, hash-bound EXP-0036 timelines and local notification claims."""
import hashlib
import json
import math
import os
import re
import sqlite3
from pathlib import Path

from fastapi import HTTPException, Request

from .app import app, artifact, catalog, config, safe_open

HEX = re.compile(r'^[0-9a-f]{64}$')
INCIDENT = re.compile(r'^incident-[0-9a-f]{24}$')
POINTER = re.compile(r'^/(?:(?:events|existing_alerts)/[0-9]+|transition_events/[0-9a-f]{64})$')


def number(x):
    if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
        raise ValueError('invalid timestamp')
    return x


def ref(value):
    pointer = value['source_pointer']
    if not isinstance(pointer, str) or not POINTER.fullmatch(pointer) or value['collection'] != pointer.split('/')[1]:
        raise ValueError('invalid source reference')
    raw = value.get('raw_id')
    if raw is not None and (type(raw) is not int or raw < 0):
        raise ValueError('invalid raw id')
    segment = value.get('segment')
    if segment is not None and type(segment) not in (int, str):
        raise ValueError('invalid segment')
    return dict(collection=value['collection'], source_pointer=pointer, raw_id=raw, segment=segment)


def load_exp0041(data, entry, bundle_id, media):
    """Validate saved grouping by replaying the same causal, CPU-only contract."""
    from sceneguard.incident_cards import group_events
    from sceneguard.incident_notifications import group_notifications

    start, end = data['source_window']
    number(start); number(end)
    media_start = number(entry.get('media_start_pts', start))
    if end <= start or media_start > start or entry.get('notification_enabled') is not False:
        raise ValueError('invalid comparison registration')
    if data.get('experiment') == 'EXP-0036':
        baseline = group_events(data['events'])
        if any(data[k] != baseline[k] for k in ('policy', 'timeline', 'cards', 'counts')):
            raise ValueError('invalid baseline grouping')
        grouped = group_notifications(data['events'])
    elif data.get('experiment') in ('EXP-0041', 'EXP-0042') and data.get('contract') == 'group_all_then_notify_v1':
        if data.get('live_notifications_enabled') is not False:
            raise ValueError('comparison notifications must be disabled')
        review_ids = [e['event_id'] for e in data['review_only_events']]
        if data['experiment'] == 'EXP-0042' and (review_ids or data.get('comparison_mode') not in ('baseline', 'transition-only', 'combined')):
            raise ValueError('invalid all-active comparison')
        grouped = group_notifications(data['events'], review_ids)
        for key in ('policy', 'events', 'active_events', 'review_only_events', 'cards',
                    'alert_cards', 'review_only_cards', 'timeline', 'counts'):
            if data[key] != grouped[key]:
                raise ValueError('invalid notification grouping or partition')
    else:
        raise ValueError('invalid comparison contract')
    if grouped['policy'] != {'gap_seconds': 3.0, 'max_span_seconds': 10.0}:
        raise ValueError('invalid grouping policy')
    session = entry.get('session_id')
    if not isinstance(session, str) or not session or len(session) > 256:
        raise ValueError('invalid session')
    ids = set()
    for event in grouped['events']:
        eid = event['event_id']
        if not HEX.fullmatch(eid) or eid in ids or event['session_id'] != session:
            raise ValueError('invalid event')
        ids.add(eid)
        if not start <= number(event['decision_time_pts']) <= end:
            raise ValueError('event outside window')
        source = ref(event['source_ref'])
        if source['collection'] == 'transition_events':
            if data.get('experiment') != 'EXP-0042' or source['source_pointer'] != '/transition_events/' + eid:
                raise ValueError('invalid transition candidate reference')
            if event['source_event'].get('evidence_until_pts') != event['decision_time_pts']:
                raise ValueError('invalid transition evidence time')
        if data.get('experiment') == 'EXP-0042':
            if data['comparison_mode'] == 'baseline' and source['collection'] == 'transition_events':
                raise ValueError('new candidate in baseline')
            if data['comparison_mode'] == 'transition-only' and source['collection'] != 'transition_events':
                raise ValueError('original candidate in diagnostic')
        if any(type(i) is not int or i < 0 for i in event['track_ids']):
            raise ValueError('invalid track ids')
    return dict(grouped, notification_enabled=False, source_window=[start, end],
                experiment=data.get('experiment'), comparison_mode=data.get('comparison_mode'),
                media_start_pts=media_start, media_artifact_id=media,
                bundle_sha256=entry['sha256'], session_id=session,
                source_label=entry.get('source_label', bundle_id),
                view_label=entry.get('view_label', ''),
                provenance_label=entry.get('provenance_label', '저장 결과 재생'))


def load_bundle(c, bundle_id):
    entry = c['incident_bundles'][bundle_id]
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', bundle_id) or not HEX.fullmatch(entry['sha256']):
        raise ValueError('invalid registration')
    media = entry['media_artifact_id']
    from .app import read_json
    cat = catalog(c)
    try:
        assignments = read_json(c['repo_root'], 'records/assignments.json')['assignments']
    except FileNotFoundError:
        assignments = []
    if not (any(e.get('experiment_id') == entry['experiment_id'] for e in cat['experiments']) or
            any(a.get('experiment_id') == entry['experiment_id'] for a in assignments)):
        raise ValueError('experiment not registered')
    catalog_media = any(e.get('artifact_id') == media and e.get('kind') == 'video'
                        for exp in cat['experiments'] for e in exp.get('evidence', []))
    assigned_media = (entry['experiment_id'] == 'EXP-0037' and
                      any(a.get('experiment_id') == 'EXP-0037' for a in assignments) and
                      c['artifacts'].get(media, {}).get('kind') == 'video')
    if not (catalog_media or assigned_media):
        raise ValueError('media not registered')
    f, ext = artifact(c, media)
    f.close()
    if ext != '.mp4':
        raise ValueError('invalid media')
    with safe_open(c['artifact_allow_root'], entry['path']) as f:
        raw = f.read()
    if hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise ValueError('bundle hash mismatch')
    data = json.loads(raw)
    if entry['experiment_id'] in ('EXP-0041', 'EXP-0042'):
        if entry['experiment_id'] == 'EXP-0042' and data.get('experiment') != 'EXP-0042':
            raise ValueError('wrong comparison experiment')
        return load_exp0041(data, entry, bundle_id, media)
    comparison = entry['experiment_id'] == 'EXP-0040'
    if (data['experiment'] not in (('EXP-0036', 'EXP-0040') if comparison else ('EXP-0036',))
            or data['policy'] != {'gap_seconds': 3.0, 'max_span_seconds': 10.0}):
        raise ValueError('invalid bundle')
    if comparison and data['experiment'] == 'EXP-0040':
        original, active, excluded = (data['full_original_alerts'], data['events'], data['review_only_events'])
        if not all(isinstance(rows, list) for rows in (original, active, excluded)):
            raise ValueError('invalid comparison partition')
        originals = {e['event_id']: e for e in original}
        partition = active + excluded
        if (len(originals) != len(original) or len(partition) != len(original)
                or len({e['event_id'] for e in partition}) != len(partition)
                or any(originals.get(e['event_id']) != e for e in partition)):
            raise ValueError('invalid comparison partition')
    start, end = data['source_window']
    number(start); number(end)
    media_start = number(entry.get('media_start_pts', start))
    if media_start > start:
        raise ValueError('invalid media origin')
    if end <= start or not isinstance(data['events'], list) or not isinstance(data['timeline'], list):
        raise ValueError('invalid window or timeline')
    session = entry.get('session_id')
    events = {}
    for event in data['events']:
        eid = event['event_id']
        if session is None:
            session = event['session_id']
        if not isinstance(session, str) or not session or event['session_id'] != session:
            raise ValueError('invalid session')
        if not HEX.fullmatch(eid) or eid in events:
            raise ValueError('invalid event')
        events[eid] = dict(event_id=eid, decision_time_pts=number(event['decision_time_pts']),
                           source_ref=ref(event['source_ref']), track_ids=event['track_ids'])
        if any(type(i) is not int or i < 0 for i in events[eid]['track_ids']):
            raise ValueError('invalid track ids')
    timeline = []
    last = start
    seen = set()
    snapshots = {}
    consumed = set()
    for item in data['timeline']:
        t = number(item['decision_time_pts']); action = item['action']; cid = item['incident_id']
        if t < last or t > end or not INCIDENT.fullmatch(cid) or item['event_id'] not in events or events[item['event_id']]['decision_time_pts'] != t:
            raise ValueError('invalid timeline')
        last = t
        if action == 'duplicate':
            if item['notify'] is not False or item['notification_key'] is not None:
                raise ValueError('invalid duplicate')
            continue
        if action not in ('created', 'updated') or item['notify'] is not (action == 'created'):
            raise ValueError('invalid action')
        card = item['card']; ids = card['event_ids']; key = card['notification_key']
        if key != 'notify:' + cid or item['notification_key'] != (key if action == 'created' else None):
            raise ValueError('invalid notification')
        if card['session_id'] != session or card['incident_id'] != cid or card['status'] != '침입 의심' or not ids or len(ids) != card['alert_count'] or any(i not in events for i in ids) or item['event_id'] not in ids:
            raise ValueError('invalid card')
        if item['event_id'] in consumed:
            raise ValueError('duplicate event membership')
        expected = snapshots.get(cid, []) + [item['event_id']]
        if ids != expected or card['track_ids'] != sorted({track for eid in ids for track in events[eid]['track_ids']}):
            raise ValueError('invalid snapshot membership')
        if card['first_alert_pts'] != events[ids[0]]['decision_time_pts'] or card['last_alert_pts'] != t:
            raise ValueError('invalid snapshot times')
        consumed.add(item['event_id'])
        snapshots[cid] = ids
        if action == 'created':
            if cid in seen or len(ids) != 1:
                raise ValueError('invalid creation')
            seen.add(cid)
        elif cid not in seen:
            raise ValueError('missing creation')
        clean = {k: card[k] for k in ('incident_id', 'gate_id', 'status', 'first_alert_pts', 'last_alert_pts', 'alert_count', 'track_ids', 'event_ids')}
        if any(type(i) is not int or i < 0 for i in clean['track_ids']):
            raise ValueError('invalid track ids')
        number(clean['first_alert_pts']); number(clean['last_alert_pts'])
        timeline.append(dict(action=action, incident_id=cid, event_id=item['event_id'], decision_time_pts=t,
                             notify=item['notify'], notification_key=item['notification_key'], card=clean))
    if consumed != set(events) or len(timeline) != data['counts']['unique_alerts'] or len(events) != data['counts']['input_alert_rows'] or len(seen) != data['counts']['incident_cards']:
        raise ValueError('partial bundle')
    if not isinstance(session, str) or not session or len(session) > 256:
        raise ValueError('missing session')
    review_only = []
    review_events = data.get('review_only_events', []) if comparison and data['experiment'] == 'EXP-0040' else data.get('review_only_alerts', [])
    for event in review_events:
        if event['session_id'] != session or not HEX.fullmatch(event['event_id']):
            raise ValueError('invalid review-only alert')
        review_only.append(dict(event_id=event['event_id'], decision_time_pts=number(event['decision_time_pts']), source_ref=ref(event['source_ref'])))
    notification_enabled = entry.get('notification_enabled', bundle_id in ('007', '030'))
    if type(notification_enabled) is not bool or (comparison and notification_enabled):
        raise ValueError('invalid notification setting')
    result = dict(notification_enabled=notification_enabled, source_window=[start, end], media_start_pts=media_start, media_artifact_id=media, timeline=timeline, events=list(events.values()),
                  bundle_sha256=entry['sha256'], session_id=session, review_only_alerts=review_only,
                  source_label=entry.get('source_label', bundle_id), view_label=entry.get('view_label', ''))
    if 'provenance_label' in entry:
        result['provenance_label'] = entry['provenance_label']
    return result


def registered(bundle_id):
    try:
        return load_bundle(config(), bundle_id)
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError, json.JSONDecodeError):
        raise HTTPException(404, 'incident bundle unavailable')


@app.get('/api/incident-registrations')
def incident_registrations(experiment_id: str = 'EXP-0037'):
    if experiment_id not in ('EXP-0037', 'EXP-0040', 'EXP-0041', 'EXP-0042'):
        return []
    result = []
    for bundle_id, entry in config().get('incident_bundles', {}).items():
        if entry.get('experiment_id') != experiment_id:
            continue
        try:
            bundle = load_bundle(config(), bundle_id)
            result.append(dict(id=bundle_id, source_label=bundle['source_label'],
                               view_label=bundle['view_label'], source_window=bundle['source_window'],
                               provenance_label=bundle.get('provenance_label', '저장 결과 재생')))
        except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError, json.JSONDecodeError):
            continue
    return result


def same_origin_json(request):
    if (request.headers.get('origin') != str(request.base_url).rstrip('/') or
            request.headers.get('sec-fetch-site', 'same-origin') != 'same-origin' or
            request.headers.get('content-type') != 'application/json'):
        raise HTTPException(403, 'same-origin JSON required')


def review_key(bundle_id, incident_id):
    bundle = registered(bundle_id)
    if incident_id not in {item['incident_id'] for item in bundle['timeline']}:
        raise HTTPException(404, 'unregistered card')
    return bundle['session_id'], incident_id, bundle['bundle_sha256']


def review_store():
    from sceneguard.review_store import ReviewStore
    try:
        return ReviewStore(Path(config()['runtime_dir']) / 'incident-reviews.sqlite3')
    except (OSError, ValueError, sqlite3.Error, KeyError):
        raise HTTPException(503, 'review store unavailable')


@app.get('/api/incidents/{bundle_id}/reviews/{incident_id}')
def get_review(bundle_id: str, incident_id: str, bundle_sha256: str, session_id: str):
    key = review_key(bundle_id, incident_id)
    if (session_id, bundle_sha256) != (key[0], key[2]):
        raise HTTPException(409, 'bundle changed; reload the card')
    store = review_store()
    return dict(review=store.get(*key), history=store.history(*key))


@app.post('/api/incidents/{bundle_id}/reviews/{incident_id}')
async def save_review(bundle_id: str, incident_id: str, request: Request):
    from sceneguard.review_store import ReviewConflict
    same_origin_json(request)
    key = review_key(bundle_id, incident_id)
    try:
        body = await request.json()
        if not isinstance(body, dict) or set(body) != {'status', 'reviewer', 'note', 'expected_version', 'session_id', 'bundle_sha256'}:
            raise ValueError('invalid review')
        if (body.pop('session_id'), body.pop('bundle_sha256')) != (key[0], key[2]):
            raise HTTPException(409, 'bundle changed; reload the card')
        store = review_store()
        review = store.save(*key, **body)
        return dict(review=review, history=store.history(*key))
    except ReviewConflict:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content=dict(review=store.get(*key), history=store.history(*key)))
    except (ValueError, TypeError):
        raise HTTPException(400, 'invalid review')
    except (OSError, sqlite3.Error):
        raise HTTPException(503, 'review store unavailable')


@app.get('/api/incidents/{bundle_id}')
def incident_bundle(bundle_id: str):
    return registered(bundle_id)


@app.post('/api/incidents/{bundle_id}/claim')
async def claim(bundle_id: str, request: Request):
    origin = request.headers.get('origin')
    if origin != str(request.base_url).rstrip('/') or request.headers.get('sec-fetch-site', 'same-origin') != 'same-origin' or request.headers.get('content-type') != 'application/json':
        raise HTTPException(403, 'same-origin JSON required')
    try:
        body = await request.json()
        if not isinstance(body, dict) or set(body) != {'notification_key'} or not isinstance(body['notification_key'], str):
            raise ValueError('invalid claim')
    except (ValueError, TypeError):
        raise HTTPException(400, 'invalid claim')
    bundle = registered(bundle_id)
    key = body['notification_key']
    if not bundle['notification_enabled']:
        raise HTTPException(404, 'notifications disabled')
    if key not in {t['notification_key'] for t in bundle['timeline'] if t['notify']}:
        raise HTTPException(404, 'unregistered notification')
    try:
        root = Path(config()['runtime_dir'])
        # Validate the directory chain without following symlinks.
        if not root.is_absolute() or any(p.startswith('.') for p in root.parts[1:]):
            raise ValueError('invalid runtime directory')
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in root.parts[1:]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd); fd = next_fd
            dbfd = os.open('exp0036-notification-receipts.sqlite3', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            os.close(dbfd)
            # proc fd binds SQLite to the verified directory for the connection lifetime.
            dbpath = f'/proc/self/fd/{fd}/exp0036-notification-receipts.sqlite3'
            with sqlite3.connect(dbpath, timeout=5) as db:
                db.execute('CREATE TABLE IF NOT EXISTS claims (notification_key TEXT PRIMARY KEY, claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
                cur = db.execute('INSERT OR IGNORE INTO claims(notification_key) VALUES (?)', (key,))
                claimed = cur.rowcount == 1
        finally:
            os.close(fd)
        return {'claimed': claimed, 'delivery': 'not_verified'}
    except (OSError, ValueError, sqlite3.Error, KeyError):
        raise HTTPException(503, 'receipt store unavailable')
