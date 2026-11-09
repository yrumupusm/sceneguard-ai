"""Freeze explicit school revisions for regression only; no training release.

The two qualified completeness answers are held as whole frames. Their saved
boxes are preserved, not turned into complete GT or discarded as background.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.prepare_person_bn_comparison import sha,write_json
from scripts.prepare_exp0074_person_data import validate_frame

PACKAGE=ROOT/'outputs/model-comparison/exp0075/school-review-v2/editor-package.json'
PACKAGE_SHA='f5388cf9e1be1c1897aaf7d061f68b612fc09ed5c618e9d5552046abeb57b446'
QUALIFIED_NOTES={
 'school-031-frame-001200':'한명 더 있긴 한데 애매하게 가려져서 박스 안넣었음. 왠지 얼굴에 블러 처리가 돼서 인식을 못하는 것 같음',
 'school-031-frame-000960':'한명 더 있는 것 같지만 가려져서 안보임. 블러처리돼서 인식을 못하는 것 같음',
}
HYPOTHESIS_NOTES={
 'school-043-frame-002040':'마찬가지로 블러처리돼서 못찾는것 같기도 함',
 'school-031-frame-001320':'블러처리 돼서 검출 잘 못하는 것 같음',
}


def classify(frame,revision,completion):
    fid=frame['frame_id']
    if (completion['source']!='current_user_chat' or completion['verbatim']!='검수 완료'
            or completion['training_authorized'] is not False
            or revision['version']!=completion['versions'][fid] or revision['version']<1
            or revision['frame_id']!=fid or revision['image_sha256']!=frame['image_sha256']
            or revision['package_sha256']!=completion['package_sha256']):
        raise ValueError('Exact saved revision and current completion required')
    note=revision.get('note','').strip()
    if fid in QUALIFIED_NOTES:
        if note!=QUALIFIED_NOTES[fid]:raise ValueError('Changed qualified answer requires review')
        return 'held_incomplete_person_visibility'
    if note and note!=HYPOTHESIS_NOTES.get(fid):
        raise ValueError('New note requires semantic review')
    if revision['status'] not in ('draft','complete'):return 'held_user_status'
    if revision['boxes']:
        if not revision['confirmed'] or revision['empty_confirmed']:return 'held_completeness'
    elif revision['empty_confirmed'] is not True:
        return 'held_unconfirmed_empty'
    return 'accepted_explicit_empty' if not revision['boxes'] else 'accepted_person_boxes'


def export(evidence,output):
    if sha(PACKAGE)!=PACKAGE_SHA:raise ValueError('Review package changed')
    package=json.loads(PACKAGE.read_text());snapshot=json.loads((evidence/'editor-snapshot.json').read_text())
    completion=json.loads((evidence/'chat-completion.json').read_text())
    if (snapshot['package_sha256']!=PACKAGE_SHA or completion['package_sha256']!=PACKAGE_SHA
            or snapshot['frames']!=[{k:v for k,v in f.items() if k!='image_path'} for f in package['frames']]
            or set(snapshot['revisions'])!={f['frame_id'] for f in package['frames']}):
        raise ValueError('Snapshot/package binding changed')
    source_evidence=json.loads((PACKAGE.parent/'evidence.json').read_text())
    sources={f['frame_id']:f for f in source_evidence['frames']}
    aihub_path=ROOT/'outputs/model-comparison/exp0074/person-data-v2/manifest.json'
    aihub=json.loads(aihub_path.read_text());other={f['source_sha256'] for f in aihub['frames']}
    output.mkdir(parents=True,exist_ok=False);(output/'evaluation-labels').mkdir()
    frames=[];held=[];processing=[]
    for frame in package['frames']:
        fid=frame['frame_id'];revision=snapshot['revisions'][fid];decision=classify(frame,revision,completion)
        if frame['source_sha256'] in other or frame['training_eligible'] is not False:
            raise ValueError('School regression must stay outside train/development')
        if sha(frame['image_path'])!=frame['image_sha256']:raise ValueError('Image changed')
        processing.append(dict(frame_id=fid,editor_revision=revision['version'],
            editor_status_preserved=revision['status'],decision=decision,boxes=len(revision['boxes']),note=revision['note']))
        if decision.startswith('held'):
            held.append(dict(frame=frame,revision=revision,reason=decision,metrics_eligible=False));continue
        f={k:copy.deepcopy(frame[k]) for k in ('frame_id','source_sha256','source_size','source_pts','frame_index',
            'native_pts_tick','time_base','source_rgb_sha256','image_sha256')}
        f.update(image=frame['image_path'],split='school_regression',
            event_group=sources[fid]['video_id'],camera_group=frame['event_group'],
            capture_reservation=frame['event_group'],confirmed_person_boxes=copy.deepcopy(revision['boxes']),
            person_completeness_verified=True,explicit_empty_verified=not revision['boxes'],
            training_eligible=False,threshold_selection_eligible=False,training_release=False,
            editor_revision=revision['version'],editor_status_preserved=revision['status'],
            annotation_method='saved_human_boxes_or_explicit_empty_plus_current_chat_completion',
            review_note=revision['note'],review_evidence_sha256=sha(evidence/'editor-snapshot.json'))
        w,h=f['source_size'];lines=[]
        for b in f['confirmed_person_boxes']:
            x,y,u,v=b['xyxy'];lines.append('0 '+' '.join(f'{a:.12f}' for a in ((x+u)/2/w,(y+v)/2/h,(u-x)/w,(v-y)/h)))
        label=output/'evaluation-labels'/(fid+'.txt');label.write_text(''.join(line+'\n' for line in lines))
        f.update(label=str(label),label_sha256=sha(label));validate_frame(f);frames.append(f)
    manifest=dict(schema_version=1,experiment_id='EXP-0075',purpose='protected_school_regression_only',
        training_release=False,training_eligible=False,threshold_selection_eligible=False,independent_test=False,
        person_boxes_human_verified=True,protected_school_or_test_used=True,
        frames=frames,frame_count=len(frames),person_box_rows=sum(len(f['confirmed_person_boxes']) for f in frames),
        explicit_empty_frames=sum(not f['confirmed_person_boxes'] for f in frames),
        held_frame_count=len(held),review_package_sha256=PACKAGE_SHA,
        inputs={str(p):sha(p) for p in [evidence/'editor-snapshot.json',evidence/'chat-completion.json',aihub_path]},
        selection='purposeful historical failure/control frames, not school-wide performance',
        export_source_sha256=sha(Path(__file__)))
    write_json(output/'manifest.json',manifest);write_json(output/'held-frames.json',held)
    write_json(output/'review-processing.json',dict(status='applied_with_two_visibility_holds',
        frames=processing,manifest_sha256=sha(output/'manifest.json'),new_training_authorization=False))


def evaluate(manifest_path,output):
    m=json.loads(manifest_path.read_text())
    if (m['purpose']!='protected_school_regression_only' or m['training_eligible'] is not False
            or m['threshold_selection_eligible'] is not False or not m['frames']
            or any(f['split']!='school_regression' or f['training_eligible'] is not False for f in m['frames'])):
        raise ValueError('Only separate protected school regression manifest allowed')
    from scripts.evaluate_exp0074_baseline import execute
    execute(manifest_path,output,evaluation_split='school_regression')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    x=sub.add_parser('export');x.add_argument('--evidence',type=Path,required=True)
    y=sub.add_parser('evaluate');y.add_argument('--manifest',type=Path,required=True)
    for s in (x,y):s.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='export':export(a.evidence.resolve(),a.output.resolve())
    else:evaluate(a.manifest.resolve(),a.output.resolve())
