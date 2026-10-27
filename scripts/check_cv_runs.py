"""Verify diagnostic outputs against independently audited native PTS, not labels."""
import argparse
import json
from pathlib import Path


def check(folder, manifest):
    run=json.loads((folder/'run.json').read_text())
    assert run['status']=='complete', 'Incomplete run'
    clip=manifest[run['video_id']+'.mp4']
    assert run['source_sha256']==clip['sha256'], 'Source changed'
    start,end=run['requested_window']
    expected=[t for t in clip['native_pts'] if start<=t and (end is None or t<end)]
    pts=json.loads((folder/'native_pts.json').read_text())
    assert len(pts)==len(expected)==run['frames'], 'Native count mismatch'
    assert all(abs(a-b)<1e-6 for a,b in zip(pts,expected)), 'Native PTS mismatch'
    assert all(a<b for a,b in zip(pts,pts[1:])), 'Non-monotonic PTS'
    rows=[json.loads(line) for line in (folder/'frames.jsonl').read_text().splitlines()]
    assert len(rows)==len(pts) and all(r['pts']==t for r,t in zip(rows,pts))
    assert sum(bool(r['detections']) for r in rows)==run['frames_with_person']
    assert sum(len(r['detections']) for r in rows)==run['person_boxes']
    events=[json.loads(line) for line in (folder/'events.jsonl').read_text().splitlines()]
    assert len(events)==run['candidate_count']
    for e in events:
        assert e['observed_pts_before']<e['observed_pts_after']<=e['emitted_at_pts']
        assert e['physical_climb_completion']=='unknown' and e['legal_status']=='unknown'
        assert e['model_sha256']==run['model_sha256'] and e['config_sha256']==run['config_sha256']
    assert run['ground_truth_loaded'] is False and run['split']=='development_only'
    return {'run':folder.name,'frames':len(pts),'max_pts_difference':max(abs(a-b) for a,b in zip(pts,expected)),
            'candidates':len(events),'verified':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folders',type=Path,nargs='+')
    parser.add_argument('--audit-manifest',type=Path,default=Path('data/aihub_intrusion_audit/manifest.json'))
    args=parser.parse_args()
    manifest={r['name']:r for r in json.loads(args.audit_manifest.read_text())}
    for folder in args.folders:print(json.dumps(check(folder,manifest)))
