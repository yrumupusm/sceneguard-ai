"""Explicit human questions and their processing history; no inference or reviews import.

The separate database is created on the first write, never by a list operation.
Source bindings are immutable: changing a registration or its bytes requires a new
request, rather than silently transferring an old answer to different evidence.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import uuid


STATUSES = ('pending', 'answered', 'acknowledged', 'applied', 'deferred')
IDENTIFIER = re.compile(r'^[A-Za-z0-9_-]{1,160}$')
SPEC_FIELDS = {'id', 'experiment_id', 'title', 'question', 'options', 'bundle_id',
               'artifact_id', 'source_time', 'end_time', 'source_label'}


class RequestConflict(Exception):
    """The request or answer version is no longer current."""


class StaleBinding(RequestConflict):
    """The registered source no longer matches the question's immutable binding."""


def text(value, field, maximum=2000, *, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f'invalid {field}')
    return value


def identifier(value, field):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f'invalid {field}')
    return value


def integer(value, field, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f'invalid {field}')
    return value


def timestamp(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('invalid source timestamp')
    return value


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def file_sha256(source):
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b''):
        digest.update(chunk)
    return digest.hexdigest()


def experiment_entry(config, experiment_id):
    from .app import catalog
    identifier(experiment_id, 'experiment_id')
    matches = [e for e in catalog(config)['experiments'] if e.get('experiment_id') == experiment_id]
    if len(matches) != 1:
        raise ValueError('unknown or ambiguous catalog experiment')
    return matches[0]


def _registered_bytes(config, path, digest=None):
    from .app import safe_open
    root = Path(config['artifact_allow_root'])
    relative = Path(path)
    if relative.is_absolute():
        relative = relative.relative_to(root)
    with safe_open(root, relative) as source:
        raw = source.read()
    actual = hashlib.sha256(raw).hexdigest()
    if digest is not None and digest != actual:
        raise ValueError('registered source hash mismatch')
    return raw, actual


def source_binding(config, row):
    """Validate only catalog-registered IDs and hash their current saved sources.

    Timestamps require a saved bundle with its registered playback clock.
    An artifact alone with no clock metadata can still be requested without a
    timestamp; guessed durations or arbitrary client-supplied paths are rejected.
    """
    from .app import artifact, safe_open
    exp = experiment_entry(config, row['experiment_id'])
    binding = {'experiment_id': row['experiment_id'], 'documents': {},
               'scope': {k: row.get(k) for k in ('bundle_id', 'artifact_id', 'source_time', 'end_time', 'source_label')}}
    for field in ('report_path', 'metrics_path'):
        path = exp.get(field)
        if path is not None:
            prefix = 'docs/experiments/' if field == 'report_path' else 'records/' + row['experiment_id'] + '/'
            suffix = '.md' if field == 'report_path' else '.json'
            if not isinstance(path, str) or not path.startswith(prefix) or not path.endswith(suffix):
                raise ValueError('invalid registered document')
            with safe_open(config['repo_root'], path) as source:
                digest = file_sha256(source)
            binding['documents'][field] = {'path': path, 'sha256': digest,
                                         'registered_sha256': exp.get(field.replace('_path', '_sha256'))}
    bundle_id, artifact_id = row.get('bundle_id'), row.get('artifact_id')
    window = None
    entry = None
    if bundle_id is not None:
        identifier(bundle_id, 'bundle_id')
        entry = config.get('incident_bundles', {}).get(bundle_id)
        if not isinstance(entry, dict) or entry.get('experiment_id') != row['experiment_id']:
            raise ValueError('bundle does not belong to experiment')
        raw, digest = _registered_bytes(config, entry['path'], entry['sha256'])
        data = json.loads(raw)
        window = data['source_window']
        binding['bundle'] = {'registration': entry, 'sha256': digest}
        if entry.get('manifest_path'):
            _, digest = _registered_bytes(config, entry['manifest_path'], entry['manifest_sha256'])
            binding['bundle']['manifest_sha256'] = digest
        if artifact_id is not None and artifact_id != entry.get('media_artifact_id'):
            raise ValueError('artifact does not match bundle media')
    selected_artifact = artifact_id if artifact_id is not None else (entry or {}).get('media_artifact_id')
    if selected_artifact is not None:
        identifier(selected_artifact, 'artifact_id')
        evidence = [e for e in exp.get('evidence', []) if e.get('artifact_id') == selected_artifact]
        if entry is None and not evidence:
            raise ValueError('artifact does not belong to experiment')
        media_entry = config.get('artifacts', {}).get(selected_artifact)
        if not isinstance(media_entry, dict):
            raise ValueError('unregistered artifact')
        source, _ = artifact(config, selected_artifact)
        with source:
            digest = file_sha256(source)
        if media_entry.get('sha256') is not None and media_entry['sha256'] != digest:
            raise ValueError('registered artifact hash mismatch')
        binding['artifact'] = {'id': selected_artifact, 'registration': media_entry,
                               'evidence': evidence, 'sha256': digest}
        if window is None:
            window = media_entry.get('source_window')
            if window is None and len(evidence) == 1:
                window = evidence[0].get('source_window')
    if window is not None:
        if not isinstance(window, list) or len(window) != 2:
            raise ValueError('invalid registered source window')
        start, end = map(timestamp, window)
        if end < start:
            raise ValueError('invalid registered source window')
        binding['source_window'] = window
    at, end = row.get('source_time'), row.get('end_time')
    if at is not None:
        if bundle_id is None:
            raise ValueError('timestamped requests require a bundle with a registered media clock')
        timestamp(at)
        if window is None or not window[0] <= at <= window[1]:
            raise ValueError('timestamp outside registered source window')
    if end is not None:
        timestamp(end)
        if at is None or window is None or not at <= end <= window[1]:
            raise ValueError('invalid source time interval')
    return hashlib.sha256(canonical(binding).encode()).hexdigest()


def prepare_spec(config, spec):
    if not isinstance(spec, dict) or set(spec) - SPEC_FIELDS:
        raise ValueError('invalid request specification fields')
    row = {k: spec.get(k) for k in SPEC_FIELDS}
    row['id'] = identifier(spec.get('id', 'request-' + uuid.uuid4().hex), 'id')
    identifier(row['experiment_id'], 'experiment_id')
    text(row['title'], 'title', 240, required=True)
    text(row['question'], 'question', 10000, required=True)
    row['options'] = spec.get('options', [])
    if not isinstance(row['options'], list) or len(row['options']) > 32:
        raise ValueError('invalid options')
    for option in row['options']:
        text(option, 'option', 500, required=True)
    if len(set(row['options'])) != len(row['options']):
        raise ValueError('duplicate options')
    if row['source_label'] is not None:
        text(row['source_label'], 'source_label', 240, required=True)
    row['source_binding_sha256'] = source_binding(config, row)
    return row


def validate_binding(config, row):
    try:
        current = source_binding(config, row)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise StaleBinding('source binding unavailable or changed; create a new request') from exc
    if current != row['source_binding_sha256']:
        raise StaleBinding('source binding changed; create a new request')


class ReviewRequestStore:
    def __init__(self, path):
        self.path = Path(path)
        self._safe_path()

    def _safe_path(self):
        if self.path.is_symlink() or any(p.is_symlink() for p in self.path.parents):
            raise ValueError('request storage must not follow symlinks')

    @contextmanager
    def _connect(self, *, write=False):
        self._safe_path()
        if write:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(str(self.path), timeout=10)
            db.executescript('''
                CREATE TABLE IF NOT EXISTS review_requests (
                    id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL,
                    version INTEGER NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_request_history (
                    id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY (id, version));
            ''')
        else:
            db = sqlite3.connect(self.path.absolute().as_uri() + '?mode=ro', uri=True, timeout=10)
            db.execute('BEGIN')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _row(db, request_id):
        result = db.execute('SELECT payload FROM review_requests WHERE id=?', (request_id,)).fetchone()
        if result is None:
            raise KeyError(request_id)
        row = json.loads(result[0])
        row['history'] = [json.loads(h[0]) for h in db.execute(
            'SELECT payload FROM review_request_history WHERE id=? ORDER BY version', (request_id,))]
        return row

    def get(self, request_id):
        identifier(request_id, 'id')
        if not self.path.exists():
            raise KeyError(request_id)
        with self._connect() as db:
            return self._row(db, request_id)

    def list(self, experiment_id=None, *, status=None):
        if experiment_id is not None:
            identifier(experiment_id, 'experiment_id')
        if status is not None and status not in STATUSES:
            raise ValueError('invalid status')
        if not self.path.exists():
            return []
        with self._connect() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM review_requests ORDER BY id')]
            rows = [self._row(db, request_id) for request_id in ids]
        return [r for r in rows if (experiment_id is None or r['experiment_id'] == experiment_id)
                and (status is None or r['status'] == status)]

    def summary(self):
        result = {}
        for row in self.list():
            counts = result.setdefault(row['experiment_id'], dict(total=0, **dict.fromkeys(STATUSES, 0)))
            counts['total'] += 1
            counts[row['status']] += 1
        return result

    @staticmethod
    def _persist(db, row, action):
        row.pop('history', None)
        row['updated_utc'] = datetime.now(timezone.utc).isoformat()
        raw = canonical(row)
        db.execute('INSERT INTO review_requests VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE '
                   'SET version=excluded.version,payload=excluded.payload',
                   (row['id'], row['experiment_id'], row['version'], raw))
        history = canonical(dict(row, action=action))
        db.execute('INSERT INTO review_request_history VALUES (?,?,?)', (row['id'], row['version'], history))

    def create(self, config, spec):
        row = prepare_spec(config, spec)
        row.update(status='pending', version=1, answer_version=0, answer=None, reviewer=None,
                   note='', processing_note='', created_utc=datetime.now(timezone.utc).isoformat())
        with self._connect(write=True) as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM review_requests WHERE id=?', (row['id'],)).fetchone():
                raise RequestConflict('request ID already exists')
            self._persist(db, row, 'created')
            return self._row(db, row['id'])

    def _change(self, config, request_id, expected_version, action, change, answer_version=None):
        identifier(request_id, 'id')
        integer(expected_version, 'expected_version')
        if answer_version is not None:
            integer(answer_version, 'answer_version')
        if not self.path.exists():
            raise KeyError(request_id)
        with self._connect(write=True) as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._row(db, request_id)
            if row['version'] != expected_version or (answer_version is not None and row['answer_version'] != answer_version):
                raise RequestConflict('stale request or answer version')
            validate_binding(config, row)
            change(row)
            row['version'] += 1
            self._persist(db, row, action)
            return self._row(db, request_id)

    def answer(self, config, request_id, *, expected_version, reviewer, answer, note):
        text(reviewer, 'reviewer', 128, required=True)
        text(answer, 'answer', 10000, required=True)
        text(note, 'note')
        def change(row):
            row.update(status='answered', answer_version=row['answer_version'] + 1,
                       answer=answer, reviewer=reviewer, note=note, processing_note='')
        return self._change(config, request_id, expected_version, 'answered', change)

    def acknowledge(self, config, request_id, *, expected_version, answer_version, note=''):
        integer(answer_version, 'answer_version')
        text(note, 'note')
        def change(row):
            if row['status'] != 'answered':
                raise RequestConflict('only a new answered request can be acknowledged')
            row.update(status='acknowledged', processing_note=note)
        return self._change(config, request_id, expected_version, 'acknowledged', change, answer_version)

    def resolve(self, config, request_id, *, expected_version, answer_version, outcome, note):
        integer(answer_version, 'answer_version')
        if outcome not in ('applied', 'deferred'):
            raise ValueError('invalid resolution outcome')
        text(note, 'note', required=True)
        def change(row):
            if row['status'] != 'acknowledged':
                raise RequestConflict('acknowledge the current answer before resolving it')
            row.update(status=outcome, processing_note=note)
        return self._change(config, request_id, expected_version, outcome, change, answer_version)


def configured_store(config):
    return ReviewRequestStore(Path(config['runtime_dir']) / 'review-requests.sqlite3')
