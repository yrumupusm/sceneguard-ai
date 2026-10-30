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
POINTER = re.compile(r'^/(events|existing_alerts)/[0-9]+$')


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


def load_bundle(c, bundle_id):
    if bundle_id not in ('007', '030'):
        raise ValueError('unregistered')
    entry = c['incident_bundles'][bundle_id]
    if entry['experiment_id'] != 'EXP-0036' or not HEX.fullmatch(entry['sha256']):
        raise ValueError('invalid registration')
    media = entry['media_artifact_id']
    from .app import read_json
    cat = catalog(c)
    try:
        assignments = read_json(c['repo_root'], 'records/assignments.json')['assignments']
    except FileNotFoundError:
        assignments = []
    if not (any(e.get('experiment_id') == 'EXP-0036' for e in cat['experiments']) or
            any(a.get('experiment_id') == 'EXP-0036' for a in assignments)):
        raise ValueError('experiment not registered')
    if not any(e.get('artifact_id') == media and e.get('kind') == 'video'
               for exp in cat['experiments'] for e in exp.get('evidence', [])):
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
    if data['experiment'] != 'EXP-0036' or data['policy'] != {'gap_seconds': 3.0, 'max_span_seconds': 10.0}:
        raise ValueError('invalid bundle')
    start, end = data['source_window']
    number(start); number(end)
    if end <= start or not isinstance(data['events'], list) or not isinstance(data['timeline'], list):
        raise ValueError('invalid window or timeline')
    events = {}
    for event in data['events']:
        eid = event['event_id']
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
        if card['incident_id'] != cid or card['status'] != '침입 의심' or not ids or len(ids) != card['alert_count'] or any(i not in events for i in ids) or item['event_id'] not in ids:
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
    return dict(source_window=[start, end], media_artifact_id=media, timeline=timeline, events=list(events.values()))


def registered(bundle_id):
    try:
        return load_bundle(config(), bundle_id)
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError, json.JSONDecodeError):
        raise HTTPException(404, 'incident bundle unavailable')


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
