"""Export exact human-reviewed EXP0071 frames, without releasing training.

Uses editor corrections for the disputed 25 frames and exact web observations
for the other 97. No original-actor union, interpolation or model inference.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

DRAFT=ROOT/'outputs/model-comparison/exp0071/person-drafts-v1'
PREP=ROOT/'outputs/model-comparison/exp0071/review-repairs-v1'
DONE=ROOT/'runtime/model-comparison/exp0071/coordinate-completion-v1'
REVIEWS=ROOT/'runtime/model-comparison/exp0071/review-application-v1'
READY=ROOT/'outputs/model-comparison/exp0070/data-readiness-v1'
CONFIG=Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json')


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def save(p,x):
    with Path(p).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)


def current(responses,after):
    # Use the existing web environment without installing web dependencies into
    # the decoder environment or changing either environment.
    check = '''import json,sys
from webapp.review_request_store import configured_store, validate_binding
config=json.load(open(sys.argv[1]))
live={r['id']:r for r in configured_store(config).list('EXP-0071')}
for answer in json.load(sys.stdin):
    actual=live[answer['id']]
    for key in ('answer_version','answer','note','artifact_id','source_binding_sha256'):
        if answer[key]!=actual[key]:raise ValueError('Web answer changed: '+key)
    if actual['status']!='applied':raise ValueError('Web answer not applied')
    validate_binding(config,actual)
'''
    subprocess.run([str(CONFIG.parents[2]/'.venv-orca-lab/bin/python'),'-c',check,str(CONFIG)],
                   input=json.dumps(responses),text=True,cwd=ROOT,check=True)
    dbpath=REVIEWS/'coordinate-reviews.sqlite3'
    with sqlite3.connect(f'file:{dbpath}?mode=ro',uri=True) as db:
        assert db.execute('select sha from binding').fetchall()==[(sha(PREP/'editor-package.json'),)]
        for fid,expected in after.items():
            row=db.execute('select payload from revisions where frame=? order by version desc limit 1',(fid,)).fetchone()
            if row is None or json.loads(row[0])!=expected:raise ValueError('Coordinate revision changed')


def box_valid(box,width,height):
    if len(box)!=4 or not all(type(v) in (int,float) and math.isfinite(v) for v in box):
        raise ValueError('Invalid coordinates')
    x1,y1,x2,y2=box
    if not (0<=x1<x2<=width and 0<=y1<y2<=height):raise ValueError('Out-of-bounds coordinates')


def export(out):
    import av
    inputs=read(READY/'input-bindings.json')
    for path,h in inputs.items():assert sha(ROOT/path)==h
    responses=read(REVIEWS/'resolved.json');after=read(DONE/'after.json');before=read(DONE/'before.json')
    scope=read(DONE/'completion-scope.json');package=read(PREP/'editor-package.json')
    assert scope['package_sha256']==sha(PREP/'editor-package.json')
    assert scope['before_sha256']==sha(DONE/'before.json')
    assert scope['kind']=='explicit_current_user_chat_completion'
    assert len(after)==25 and set(after)==set(before)
    assert all(after[k]['boxes']==before[k]['boxes'] and after[k]['confirmed'] and after[k]['status']=='complete' for k in after)
    current(responses,after)
    answers={r['artifact_id']:r for r in responses}
    editor={f['frame_id']:f for f in package['frames']}
    plan=read(READY/'split-proposal.json');cases={c['candidate_id']:c for c in plan['cases']}
    protected={r['sha256'] for r in read(ROOT/'outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json')['regression_only_videos']}
    fingerprints=[json.loads(line) for line in (ROOT/'outputs/action-recognition/exp0065/augmentation-v1/protected-content-fingerprints.jsonl').read_text().splitlines()]
    protected.update(p['recorded_source_sha256'] for p in fingerprints)
    # Read the existing protected IDs through the source inventory as well as hashes.
    inventory={r['source_id']:r for r in [json.loads(line) for line in (READY/'source-inventory.jsonl').read_text().splitlines()]}
    legacy=read(ROOT/'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json')
    old_keys={(f['source_sha256'],f['frame_index']) for f in legacy['frames']}
    out.mkdir(parents=True,exist_ok=False)
    records=[]; corrected=set()
    for rid in ('R01','R02','R03','R04','R05'):
        draft=read(DRAFT/f'{rid}-drafts.json');case=cases[draft['candidate_id']]
        assert inventory[draft['source_id']]['proposed_partition']!='protected_exp0064_test'
        assert not inventory[draft['source_id']]['excluded']
        assert draft['source_sha256'] not in protected
        answer=answers[f'exp0071-{rid.lower()}-comparison']
        assert sha(DRAFT/draft['video'])==draft['video_sha256']
        if rid=='R05':assert answer['answer']=='전 구간에서 보이는 사람이 없음'
        elif rid!='R02':assert answer['answer']=='이 구간의 모든 보이는 사람에게 박스가 맞음'
        ref=case['source_reference']
        if 'path' in ref:raw=Path(ref['path']).read_bytes()
        else:
            with zipfile.ZipFile(ref['archive_path']) as z:raw=z.read(ref['member'])
        assert hashlib.sha256(raw).hexdigest()==draft['source_sha256']
        wanted={f['decoded_index']:f for f in draft['frames']};found=set()
        with av.open(io.BytesIO(raw)) as source:
            stream=source.streams.video[0];stream.codec_context.thread_count=1
            source.seek(int(min(wanted)/3/float(stream.time_base)),stream=stream,backward=True)
            for frame in source.decode(stream):
                pts=float(frame.pts*frame.time_base);i=round(pts*3)
                if i>max(wanted):break
                if i not in wanted:continue
                old=wanted[i];rgb=frame.to_ndarray(format='rgb24');fid=f'exp0071-{rid.lower()}-frame-{i:06d}'
                assert abs(pts-old['source_pts'])<1e-6 and hashlib.sha256(rgb.tobytes()).hexdigest()==old['source_rgb_sha256']
                assert (draft['source_sha256'],i) not in old_keys
                revision=None
                if fid in after:
                    e=editor[fid];revision=after[fid];corrected.add(fid)
                    assert e['source_rgb_sha256']==old['source_rgb_sha256'] and sha(e['image_path'])==e['image_sha256']
                    boxes=revision['boxes'];method='user_saved_coordinates_and_explicit_chat_completion'
                elif rid=='R05':
                    assert not old['model_proposals']['boxes'];boxes=[];method='explicit_web_empty_frame_review'
                else:
                    assert rid!='R02'
                    boxes=[dict(id=f'{fid}-reviewed-{j}',xyxy=b) for j,(b,v) in enumerate(zip(old['model_proposals']['boxes'],old['model_proposals']['valid_boxes'])) if v]
                    assert boxes;method='explicit_web_review_of_displayed_boxes_with_source_audit'
                for b in boxes:box_valid(b['xyxy'],1920,1080)
                split='train_candidate' if case['reserved_split']=='train' else 'development_diagnostic'
                image=out/'images'/split/f'{fid}.png';label=out/'labels'/split/f'{fid}.txt'
                image.parent.mkdir(parents=True,exist_ok=True);label.parent.mkdir(parents=True,exist_ok=True)
                frame.to_image().save(image)
                lines=[]
                for b in boxes:
                    x1,y1,x2,y2=b['xyxy'];lines.append(f'0 {(x1+x2)/3840:.10f} {(y1+y2)/2160:.10f} {(x2-x1)/1920:.10f} {(y2-y1)/1080:.10f}')
                label.write_text('\n'.join(lines)+ ('\n' if lines else ''))
                records.append(dict(frame_id=fid,review_id=rid,split=split,source_sha256=draft['source_sha256'],source_id=draft['source_id'],
                    source_size=[1920,1080],frame_index=i,source_pts=pts,native_pts_tick=frame.pts,
                    source_rgb_sha256=old['source_rgb_sha256'],capture_reservation=case['capture_reservation'],
                    image=str(image.relative_to(out)),image_sha256=sha(image),label=str(label.relative_to(out)),label_sha256=sha(label),
                    person_boxes=boxes,annotation_method=method,web_request_id=answer['id'],web_answer_version=answer['answer_version'],
                    source_binding_sha256=answer['source_binding_sha256'],editor_revision=revision['version'] if revision else None,
                    review_note=revision['note'] if revision else answer['note'],empty_human_confirmed=rid=='R05',
                    action_ground_truth_verified=False,training_release=False))
                found.add(i)
        assert found==set(wanted)
    assert corrected==set(after) and len(records)==122
    assert sum(len(r['person_boxes']) for r in records)==207
    for r in records:
        # Check YOLO coordinate round-trip, including real empty labels.
        lines=(out/r['label']).read_text().splitlines()
        assert len(lines)==len(r['person_boxes'])
        for line,box in zip(lines,r['person_boxes']):
            cls,cx,cy,w,h=map(float,line.split());assert cls==0
            restored=[(cx-w/2)*1920,(cy-h/2)*1080,(cx+w/2)*1920,(cy+h/2)*1080]
            assert max(abs(a-b) for a,b in zip(restored,box['xyxy']))<1e-5
    current(responses,after)
    for path,h in inputs.items():assert sha(ROOT/path)==h
    save(out/'manifest.json',dict(schema_version=1,experiment_id='EXP-0071',purpose='exact_human_reviewed_person_annotations',
        training_release=False,frames=records,frame_counts=dict(Counter(r['split'] for r in records)),
        box_counts={s:sum(len(r['person_boxes']) for r in records if r['split']==s) for s in {r['split'] for r in records}},
        empty_reviewed_frames=25,coordinate_correction_frames=25,old75_overlap_frames=0,
        web_responses_sha256=sha(REVIEWS/'resolved.json'),editor_package_sha256=sha(PREP/'editor-package.json'),
        completion_scope_sha256=sha(DONE/'completion-scope.json'),editor_revisions_sha256=sha(DONE/'after.json'),
        exporter_sha256=sha(Path(__file__)),legacy75_manifest_sha256=sha(ROOT/'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json'),
        protected_input_sha256=inputs,source_pts_and_rgb_verified=True,label_geometry_and_roundtrip_verified=True,
        training_runs=0,model_inference=0,limitations=['Person review only; no action/identity truth.',
            'New train frames share the same two conservative capture reservations as prior training examples.',
            'Development P05 remains auxiliary diagnostic; not an independent test.',
            'No unseen frames, original-actor union, guessed hidden boxes, or automatic dataset release.']))
    print(json.dumps(dict(frames=122,person_boxes=207,corrected_frames=25,empty_reviewed_frames=25,training_release=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);export(p.parse_args().output)
