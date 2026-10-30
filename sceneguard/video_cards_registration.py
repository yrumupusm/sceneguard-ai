"""Add completed local video-card artifacts to the existing service atomically."""
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import re
import uuid

from .video_cards import ROOT, read, save
from .replay_gap_tracking import sha256


def local_path(path, root):
    path=Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.resolve().is_relative_to(root):
        raise ValueError('Registered artifacts must remain inside the existing local outputs allowroot')
    return path.resolve()


def register(config_path, registration_path, bundle_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',bundle_id):
        raise ValueError('Explicit valid registration ID required')
    config_path=Path(config_path).absolute()
    if config_path.is_symlink() or any(p.is_symlink() for p in config_path.parents):
        raise ValueError('Service config must not be a symlink')
    initial=read(config_path)
    runtime=Path(initial['runtime_dir']).resolve()
    if config_path.parent != runtime or config_path.name!='local_config.json':
        raise ValueError('Use the existing runtime local_config.json')
    if (runtime/'completion.lock').is_symlink():
        raise ValueError('Service completion lock must not be a symlink')
    with (runtime/'completion.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        before=config_path.read_bytes()
        config=json.loads(before)
        root=Path(config['repo_root']).resolve()
        allow=Path(config['artifact_allow_root']).resolve()
        if root!=ROOT or allow!=ROOT/'outputs' or Path(config['runtime_dir']).resolve()!=runtime:
            raise ValueError('Existing repository/runtime/output allowlist required')
        assignments=read(root/'records/assignments.json')['assignments']
        if not any(a.get('experiment_id')=='EXP-0037' for a in assignments):
            raise ValueError('Existing EXP-0037 assignment required; no public catalog writes')
        registration_path=local_path(registration_path,allow)
        reg=read(registration_path)
        if read(registration_path.parent/'status.json').get('state')!='complete':
            raise ValueError('Only completed analysis can be registered')
        cards=local_path(reg['cards_path'],allow)
        analysis=local_path(reg['analysis_path'],allow)
        if sha256(cards)!=reg['cards_sha256'] or sha256(analysis)!=reg['analysis_sha256']:
            raise ValueError('Completed bundle/analysis bytes differ')
        bundle=read(cards)
        if (bundle.get('experiment')!='EXP-0036' or bundle['counts']!=reg['counts']
                or bundle.get('analysis_request_sha256')!=reg['request_sha256']
                or bundle['source_window']!=reg['source_window']):
            raise ValueError('Registration/card source binding differs')
        media=next(m for m in reg['media'] if m['key']=='original')
        media_path=local_path(media['path'],allow)
        if media_path.suffix!='.mp4' or sha256(media_path)!=media['sha256']:
            raise ValueError('Original evidence bytes differ')
        artifact_id=bundle_id+'-original'
        entry=dict(path=str(cards.relative_to(allow)),sha256=reg['cards_sha256'],
             media_artifact_id=artifact_id,experiment_id='EXP-0037',session_id=reg['session_id'],
             source_label=reg['video_id'],view_label='영상 분석 · 사건 카드',
             provenance_label=reg['display_label']+' · 오프라인 분석 · 후처리 미채택',
             media_start_pts=media['source_start_pts'],notification_enabled=True)
        artifact=dict(path=str(media_path),kind='video')
        updated=deepcopy(config)
        for mapping,key,value in [('incident_bundles',bundle_id,entry),('artifacts',artifact_id,artifact)]:
            store=updated.setdefault(mapping,{})
            if key in store and store[key]!=value:
                raise ValueError('Conflicting registered alias must be changed explicitly by root: '+key)
            store[key]=value
        if config_path.read_bytes()!=before:
            raise ValueError('Service config changed during registration')
        if updated!=config:
            backup=runtime/('local_config.before-video-cards-'+uuid.uuid4().hex+'.json')
            with backup.open('xb') as stream: stream.write(before)
            temporary=runtime/('.local_config.video-cards-'+uuid.uuid4().hex)
            save(temporary,updated)
            temporary.replace(config_path)
        receipt=dict(bundle_id=bundle_id,artifact_id=artifact_id,cards_sha256=reg['cards_sha256'],
                     config_path=str(config_path),registered=True,service_restart_performed=False,
                     notification_receipts_modified=False,public_catalog_modified=False)
        dst=registration_path.parent/'service-registration.json'
        if dst.exists():
            if read(dst)!=receipt: raise ValueError('Existing registration receipt differs')
        else: save(dst,receipt)
        return receipt
