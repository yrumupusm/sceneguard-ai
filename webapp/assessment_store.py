"""Versioned human assessments; independent of automatic state and legacy reviews."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3

from sceneguard.review_store import ReviewConflict, _key, _text

EVENT_ASSESSMENTS = ('unreviewed', 'correct_event', 'false_alert', 'uncertain')
BBOX_QUALITIES = ('unreviewed', 'good', 'poor', 'uncertain', 'none')
OMISSION_STATUSES = ('unreviewed', 'missed', 'none', 'uncertain')


class AssessmentStore:
    """Callers must authorize the source binding and card before accessing storage."""

    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink() or any(p.is_symlink() for p in self.path.parents):
            raise ValueError('Assessment storage must not follow symlinks')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS assessment (
                  session TEXT NOT NULL, subject TEXT NOT NULL, bundle TEXT NOT NULL,
                  version INTEGER NOT NULL, payload TEXT NOT NULL,
                  PRIMARY KEY(session, subject, bundle));
                CREATE TABLE IF NOT EXISTS assessment_history (
                  session TEXT NOT NULL, subject TEXT NOT NULL, bundle TEXT NOT NULL,
                  version INTEGER NOT NULL, payload TEXT NOT NULL,
                  PRIMARY KEY(session, subject, bundle, version));
            ''')

    def _connect(self):
        return sqlite3.connect(str(self.path), timeout=10)

    def get(self, session, subject, bundle):
        key = _key(session, subject, bundle)
        with self._connect() as db:
            row = db.execute('SELECT payload FROM assessment WHERE session=? AND subject=? AND bundle=?', key).fetchone()
        return json.loads(row[0]) if row else None

    def history(self, session, subject, bundle):
        key = _key(session, subject, bundle)
        with self._connect() as db:
            rows = db.execute('SELECT payload FROM assessment_history WHERE session=? AND subject=? AND bundle=? ORDER BY version', key).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save(self, session, subject, bundle, *, expected_version, reviewer, note, **assessment):
        key = _key(session, subject, bundle)
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError('Nonnegative integer version required')
        _text(reviewer, 'reviewer', 128)
        if not isinstance(note, str) or len(note) > 2000:
            raise ValueError('Note must be at most 2000 characters')
        if subject == 'video-omission':
            if set(assessment) != {'status', 'time_pts'} or assessment['status'] not in OMISSION_STATUSES:
                raise ValueError('Invalid omission assessment')
            at = assessment['time_pts']
            if at is not None and (type(at) not in (int, float) or not math.isfinite(at) or at < 0):
                raise ValueError('Invalid omission timestamp')
        elif set(assessment) != {'event_assessment', 'bbox_quality'} or assessment['event_assessment'] not in EVENT_ASSESSMENTS or assessment['bbox_quality'] not in BBOX_QUALITIES:
            raise ValueError('Invalid event or bbox assessment')
        value = dict(session_id=session, subject=subject, bundle_sha256=bundle,
                     version=expected_version + 1, reviewer=reviewer, note=note,
                     updated_utc=datetime.now(timezone.utc).isoformat(), **assessment)
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
        db = self._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT version FROM assessment WHERE session=? AND subject=? AND bundle=?', key).fetchone()
            if (row[0] if row else 0) != expected_version:
                raise ReviewConflict('Stale assessment version')
            values = (*key, value['version'], raw)
            db.execute('INSERT INTO assessment_history VALUES (?,?,?,?,?)', values)
            db.execute('''INSERT INTO assessment VALUES (?,?,?,?,?) ON CONFLICT(session,subject,bundle)
                          DO UPDATE SET version=excluded.version,payload=excluded.payload''', values)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return value
