"""Local reviewer decisions, separate from immutable machine suspicions.

The web adapter MUST authorize bundle/card membership and same-origin requests
before calling this store. This class is storage, not authentication or an API.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

STATUSES = ('침입 의심', '침입 확인', '침입 아님', '판단 불가')


class ReviewConflict(ValueError):
    """Someone changed this review; reload its version before saving."""


def _text(value, name, max_length):
    if not isinstance(value,str) or not value.strip() or len(value)>max_length:
        raise ValueError(f'Invalid {name}')
    return value


def _key(session_id, incident_id, bundle_sha256):
    _text(session_id,'session_id',256); _text(incident_id,'incident_id',256)
    if not isinstance(bundle_sha256,str) or len(bundle_sha256)!=64 or any(c not in '0123456789abcdef' for c in bundle_sha256):
        raise ValueError('Exact source bundle SHA256 required')
    return session_id,incident_id,bundle_sha256


class ReviewStore:
    def __init__(self, path):
        self.path=Path(path)
        if self.path.is_symlink() or any(p.is_symlink() for p in self.path.parents):
            raise ValueError('Review storage must not follow symlinks')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS incident_review(
              session TEXT NOT NULL, incident TEXT NOT NULL, bundle TEXT NOT NULL,
              version INTEGER NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL,
              reviewer TEXT NOT NULL, updated_utc TEXT NOT NULL,
              PRIMARY KEY(session,incident,bundle));
            CREATE TABLE IF NOT EXISTS incident_review_history(
              session TEXT NOT NULL, incident TEXT NOT NULL, bundle TEXT NOT NULL,
              version INTEGER NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL,
              reviewer TEXT NOT NULL, updated_utc TEXT NOT NULL,
              PRIMARY KEY(session,incident,bundle,version));
            ''')

    def _connect(self):
        db=sqlite3.connect(str(self.path),timeout=10)
        db.row_factory=sqlite3.Row
        return db

    def get(self, session_id, incident_id, bundle_sha256):
        key=_key(session_id,incident_id,bundle_sha256)
        with self._connect() as db:
            row=db.execute('SELECT * FROM incident_review WHERE session=? AND incident=? AND bundle=?',key).fetchone()
        return dict(row) if row else None

    def history(self, session_id, incident_id, bundle_sha256):
        key=_key(session_id,incident_id,bundle_sha256)
        with self._connect() as db:
            rows=db.execute('SELECT * FROM incident_review_history WHERE session=? AND incident=? AND bundle=? ORDER BY version',key).fetchall()
        return [dict(r) for r in rows]

    def save(self, session_id, incident_id, bundle_sha256, *, status, reviewer, expected_version, note=''):
        key=_key(session_id,incident_id,bundle_sha256)
        if status not in STATUSES or type(expected_version) is not int or expected_version<0:
            raise ValueError('Allowed status and nonnegative integer revision required')
        _text(reviewer,'reviewer',128)
        if not isinstance(note,str) or len(note)>2000:
            raise ValueError('Review note must be at most 2000 characters')
        at=datetime.now(timezone.utc).isoformat()
        db=self._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT version FROM incident_review WHERE session=? AND incident=? AND bundle=?',key).fetchone()
            current=row['version'] if row else 0
            if current!=expected_version:
                raise ReviewConflict('Stale review version; reload the latest decision')
            values=(*key,current+1,status,note,reviewer,at)
            db.execute('INSERT INTO incident_review_history VALUES (?,?,?,?,?,?,?,?)',values)
            db.execute('''INSERT INTO incident_review VALUES (?,?,?,?,?,?,?,?)
              ON CONFLICT(session,incident,bundle) DO UPDATE SET
              version=excluded.version,status=excluded.status,note=excluded.note,
              reviewer=excluded.reviewer,updated_utc=excluded.updated_utc''',values)
            db.commit()
        except Exception:
            db.rollback(); raise
        finally:
            db.close()
        # Return the version just written, not a potentially newer concurrent edit.
        return dict(zip(('session','incident','bundle','version','status','note','reviewer','updated_utc'),values))


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',type=Path,required=True)
    p.add_argument('--session-id',required=True); p.add_argument('--incident-id',required=True)
    p.add_argument('--bundle-sha256',required=True)
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('get'); sub.add_parser('history')
    s=sub.add_parser('save'); s.add_argument('--status',choices=STATUSES,required=True)
    s.add_argument('--reviewer',required=True);s.add_argument('--version',type=int,required=True)
    s.add_argument('--note',default='')
    a=p.parse_args()
    # CLI writes only to ignored runtime storage; services pass an authorized path.
    root=Path('runtime').resolve()
    if not a.database.resolve().is_relative_to(root):
        p.error('Use a local runtime/ database; never overwrite a tracked file')
    store=ReviewStore(a.database);key=(a.session_id,a.incident_id,a.bundle_sha256)
    value=(store.save(*key,status=a.status,reviewer=a.reviewer,expected_version=a.version,note=a.note)
           if a.action=='save' else getattr(store,a.action)(*key))
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
