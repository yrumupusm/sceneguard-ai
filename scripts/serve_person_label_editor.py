"""Loopback-only, versioned manual person annotation editor. Never starts training."""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

ASSETS = Path(__file__).resolve().parents[1] / 'webapp/person_label_editor'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, package, database):
        self.path = Path(package).resolve(strict=True)
        self.sha = digest(self.path)
        self.package = json.loads(self.path.read_text())
        self.frames = {f['frame_id']: f for f in self.package['frames']}
        if len(self.frames) != len(self.package['frames']) or not self.frames:
            raise ValueError('Invalid frame IDs')
        for key, frame in self.frames.items():
            if not re.fullmatch(r'[a-zA-Z0-9_-]+', key) or frame['split'] not in ('train', 'validation'):
                raise ValueError('Invalid frame scope')
            if digest(frame['image_path']) != frame['image_sha256']:
                raise ValueError('Image differs')
        self.database = str(database)
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS binding (sha TEXT PRIMARY KEY)')
            bindings = db.execute('SELECT sha FROM binding').fetchall()
            if bindings and bindings != [(self.sha,)]:
                raise ValueError('Database belongs to another immutable package')
            db.execute('INSERT OR IGNORE INTO binding VALUES (?)', (self.sha,))
            db.execute('CREATE TABLE IF NOT EXISTS revisions (frame TEXT, version INTEGER, payload TEXT, PRIMARY KEY(frame, version))')

    def connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def unchanged(self):
        if digest(self.path) != self.sha:
            raise Conflict('Package changed; reopen with a new bound store')

    def current(self, frame_id, db=None):
        if frame_id not in self.frames:
            raise ValueError('Unknown frame')
        if db is None:
            with self.connect() as connection:
                return self.current(frame_id, connection)
        row = db.execute('SELECT payload FROM revisions WHERE frame=? ORDER BY version DESC LIMIT 1', (frame_id,)).fetchone()
        return json.loads(row[0]) if row else dict(version=0, status='pending', boxes=[], reviewer='', note='', empty_confirmed=False)

    def save(self, frame_id, body):
        self.unchanged()
        frame = self.frames.get(frame_id)
        if frame is None or not isinstance(body, dict):
            raise ValueError('Unknown frame or invalid request')
        required = {'expected_version', 'reviewer', 'status', 'boxes', 'note', 'confirmed', 'empty_confirmed'}
        if set(body) != required or type(body['expected_version']) is not int:
            raise ValueError('Invalid revision fields')
        if body['status'] not in ('draft', 'complete', 'incomplete', 'uncertain'):
            raise ValueError('Invalid review status')
        if not isinstance(body['reviewer'], str) or not 1 <= len(body['reviewer'].strip()) <= 100:
            raise ValueError('Reviewer identity required')
        if not isinstance(body['note'], str) or len(body['note']) > 4000:
            raise ValueError('Invalid note')
        if type(body['confirmed']) is not bool or type(body['empty_confirmed']) is not bool:
            raise ValueError('Explicit checkboxes required')
        if body['status'] == 'complete' and (not body['confirmed'] or (not body['boxes'] and not body['empty_confirmed'])):
            raise ValueError('Completeness and empty-frame confirmation required')
        if body['boxes'] and body['empty_confirmed']:
            raise ValueError('Empty confirmation conflicts with boxes')
        if not isinstance(body['boxes'], list) or len(body['boxes']) > 300:
            raise ValueError('Invalid boxes')
        width, height = frame['source_size']
        candidates = {c['id'] for c in frame['candidates']}
        seen = set()
        for box in body['boxes']:
            if not isinstance(box, dict) or set(box) != {'id', 'xyxy', 'source_id'}:
                raise ValueError('Invalid box fields')
            if not isinstance(box['id'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', box['id']) or box['id'] in seen:
                raise ValueError('Invalid or duplicate box ID')
            seen.add(box['id'])
            if box['source_id'] is not None and box['source_id'] not in candidates:
                raise ValueError('Unknown source candidate')
            xy = box['xyxy']
            if not isinstance(xy, list) or len(xy) != 4 or not all(type(x) in (int, float) and math.isfinite(x) for x in xy):
                raise ValueError('Finite coordinates required')
            if not (0 <= xy[0] < xy[2] <= width and 0 <= xy[1] < xy[3] <= height):
                raise ValueError('Box outside image')
        if digest(frame['image_path']) != frame['image_sha256']:
            raise Conflict('Source frame changed')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = self.current(frame_id, db)
            if current['version'] != body['expected_version']:
                raise Conflict('Newer saved revision exists; reload before editing')
            revision = {**body, 'version': current['version'] + 1, 'package_sha256': self.sha,
                        'frame_id': frame_id, 'image_sha256': frame['image_sha256'],
                        'saved_utc': datetime.now(timezone.utc).isoformat(), 'training_release': False}
            del revision['expected_version']
            db.execute('INSERT INTO revisions VALUES (?,?,?)', (frame_id, revision['version'], json.dumps(revision, ensure_ascii=False, allow_nan=False)))
        return revision


def handler(store):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, code, content, mime='application/json'):
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def reply(self, value, code=200):
            self.send_bytes(code, json.dumps(value, ensure_ascii=False, allow_nan=False).encode())

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.valid_host():
                return self.reply({'error': 'Local host required'}, 403)
            try:
                store.unchanged()
                path = urlsplit(self.path).path
                if path == '/api/package':
                    frames = [{k: v for k, v in f.items() if k != 'image_path'} for f in store.frames.values()]
                    return self.reply(dict(package_sha256=store.sha, frames=frames, training_release=False,
                                           revisions={f: store.current(f) for f in store.frames}))
                if path.startswith('/images/'):
                    frame = store.frames[path[len('/images/'):]]
                    data = Path(frame['image_path']).read_bytes()
                    if hashlib.sha256(data).hexdigest() != frame['image_sha256']:
                        raise Conflict('Source frame changed')
                    return self.send_bytes(200, data, 'image/png')
                files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if path not in files:
                    return self.reply({'error': 'Not found'}, 404)
                filename, mime = files[path]
                self.send_bytes(200, (ASSETS / filename).read_bytes(), mime)
            except Conflict as exc:
                self.reply({'error': str(exc)}, 409)
            except (KeyError, OSError, ValueError):
                self.reply({'error': 'Bound artifact unavailable'}, 404)

        def do_POST(self):
            if not self.valid_host() or self.headers.get('Origin') != 'http://' + self.headers.get('Host', '') or self.headers.get('Content-Type') != 'application/json':
                return self.reply({'error': 'Same-origin JSON required'}, 403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 200000 or not self.path.startswith('/api/frames/'):
                    raise ValueError('Invalid request')
                body = json.loads(self.rfile.read(length))
                self.reply(store.save(self.path[len('/api/frames/'):], body))
            except Conflict as exc:
                self.reply({'error': str(exc)}, 409)
            except (ValueError, TypeError, KeyError) as exc:
                self.reply({'error': str(exc)}, 400)

    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args()
    store = Store(args.package, args.database)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(store))
    print(f'http://127.0.0.1:{args.port}/ package={store.sha} frames={len(store.frames)}', flush=True)
    server.serve_forever()
