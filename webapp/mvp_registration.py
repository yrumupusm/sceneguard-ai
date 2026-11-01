"""Register a completed local MVP manifest without replacing existing registrations."""
import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from orchestration.complete import Registry
from .app import safe_open
from .incident import load_activity


def register(config_path, manifest_path, registration_id, *, make_default=False):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,70}', registration_id):
        raise ValueError('invalid registration id')
    config_path = Path(config_path).absolute()
    registry = Registry(config_path)
    with registry.locked():
        config = registry.config
        root = Path(config['artifact_allow_root'])
        def checked(path, digest=None, *, read=True):
            path = Path(path)
            if not path.is_absolute(): raise ValueError('absolute artifact path required')
            relative = path.relative_to(root)
            with safe_open(root, relative) as f:
                if read:
                    raw = f.read()
                    actual = hashlib.sha256(raw).hexdigest()
                else:
                    h = hashlib.sha256()
                    for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
                    actual, raw = h.hexdigest(), None
            if digest is not None and actual != digest:
                raise ValueError('artifact hash mismatch')
            return raw
        m = json.loads(checked(Path(manifest_path).absolute()))
        if (m.get('kind') != 'sceneguard_mvp_viewer_v1' or m.get('experiment') != 'MVP-0002'
                or m.get('contract') != 'gate_activity_episodes_v1' or m.get('live_notifications_enabled') is not False
                or m.get('manual_reviews_modified') is not False or m.get('session_id') != m.get('run_id')):
            raise ValueError('invalid manifest')
        output = Path(manifest_path).absolute().parent
        status = json.loads(checked(output / 'status.json'))
        request = json.loads(checked(output / 'request.json'))
        if (status.get('state') != 'analysis_complete' or Path(status.get('manifest_path', '')) != Path(manifest_path).absolute()
                or request.get('video') != m.get('source_path') or request.get('camera') != m.get('camera_id')
                or request.get('input_sha256', {}).get(m.get('source_path')) != m.get('source_sha256')
                or Path(m['cards_path']).parent != output / 'decision'):
            raise ValueError('incomplete or mismatched analysis')
        data = json.loads(checked(m['cards_path'], m['cards_sha256']))
        if (data.get('analysis_run_id') != m['run_id'] or data.get('source_evidence_mode') != 'computed_in_current_run'
                or data.get('source_window') != m['source_window'] or data.get('video_id') != m['video_id']):
            raise ValueError('manifest provenance mismatch')
        checked(m['source_frames_path'], m['source_frames_sha256'])
        originals = [item for item in m['media'] if item.get('key') == 'original']
        if len(originals) != 1: raise ValueError('original media required')
        media = originals[0]
        if Path(media['path']).suffix.lower() != '.mp4': raise ValueError('invalid video')
        checked(media['path'], media['sha256'], read=False)
        artifact_id = registration_id + '-video'
        mode = {'saved_cache': '저장 검출 기반 분석', 'new_detector_canonical_queue': '기존 모델 새 검출 분석'}.get(m['execution_mode'])
        if mode is None:
            # Explicitly supported pipeline mode values only.
            mode = {'cache': '저장 검출 기반 분석', 'queue': '기존 모델 새 검출 분석'}.get(m['execution_mode'])
        if mode is None: raise ValueError('unknown execution mode')
        entry = dict(experiment_id='MVP-0002', media_artifact_id=artifact_id,
            media_start_pts=media['source_start_pts'], notification_enabled=False,
            path=str(Path(m['cards_path']).relative_to(root)), sha256=m['cards_sha256'],
            session_id=m['run_id'], source_label=Path(m['source_path']).stem,
            view_label='영상 분석', provenance_label=mode,
            manifest_path=str(Path(manifest_path).absolute().relative_to(root)),
            manifest_sha256=hashlib.sha256(checked(Path(manifest_path).absolute())).hexdigest())
        load_activity(data, entry, registration_id, artifact_id)
        artifact = dict(kind='video', path=media['path'])
        for mapping, key, value in ((config['artifacts'], artifact_id, artifact), (config['incident_bundles'], registration_id, entry)):
            if key in mapping and mapping[key] != value: raise ValueError('registration id already exists')
            mapping[key] = value
        if make_default:
            config['mvp_default_registration'] = registration_id
        fd, tmp = tempfile.mkstemp(prefix='.mvp-registration-', dir=config_path.parent)
        try:
            os.fchmod(fd, config_path.stat().st_mode & 0o777)
            with os.fdopen(fd, 'w') as f:
                json.dump(config, f, ensure_ascii=False, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, config_path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        return entry


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--manifest', required=True); p.add_argument('--registration-id', required=True)
    p.add_argument('--make-default', action='store_true', help='select this registration as the default MVP view')
    args = p.parse_args()
    print(json.dumps(register(args.config, args.manifest, args.registration_id, make_default=args.make_default), ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
