"""Import only the three saved P01 revisions completed explicitly in user chat.

Preserves editor draft states; confirmation is the saved completeness checkbox
PLUS the separately bound current chat completion, never a generic draft rule.
No training, prediction-based labels, or changes to the original197 frames.
"""
import argparse
import copy
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_exp0074_person_data import protected_hashes, validate_splits, validate_frame
from scripts.prepare_person_bn_comparison import dataset_contract, sha, write_json

BASE = ROOT/'outputs/model-comparison/exp0074/person-data-v1/manifest.json'
BASE_SHA = '01a08a3d42e610a3489b05859c9425ffe462b3709f46f967ea4537a48df2cf90'
PACKAGE = ROOT/'outputs/model-comparison/exp0074/targeted-review-v1/editor-package.json'
PACKAGE_SHA = '19277457498fd266d91af1848878704274b006ebe0859796ef016b599799cfe6'


def read(path):
    return json.loads(Path(path).read_text())


def confirmed_rows(package, snapshot, completion):
    ids = {f'exp0074-p01-frame-{i:06d}' for i in (168, 175, 185)}
    if ({f['frame_id'] for f in package['frames']} != ids
            or snapshot['frames'] != [{k:v for k,v in f.items() if k!='image_path'} for f in package['frames']]
            or set(snapshot['revisions']) != ids
            or snapshot['package_sha256'] != PACKAGE_SHA
            or completion['package_sha256'] != PACKAGE_SHA
            or completion['source'] != 'current_user_chat'
            or completion['verbatim'] != '검수완료'
            or completion['training_authorized'] is not False):
        raise ValueError('Exact package and explicit current chat completion required')
    rows = []
    for frame in package['frames']:
        fid = frame['frame_id']; revision = snapshot['revisions'][fid]
        if (revision['version'] != completion['editor_versions'][fid]
                or revision['version'] < 1 or revision['confirmed'] is not True
                or revision['status'] not in ('draft', 'complete')
                or revision['package_sha256'] != PACKAGE_SHA
                or revision['image_sha256'] != frame['image_sha256']
                or revision['frame_id'] != fid or revision.get('note', '').strip()
                or not revision['boxes'] or revision['empty_confirmed']):
            raise ValueError('Incomplete, uncertain, qualified or different saved revision')
        rows.append((frame, revision))
    return rows


def export(evidence, output):
    if sha(BASE) != BASE_SHA or sha(PACKAGE) != PACKAGE_SHA:
        raise ValueError('Frozen source changed')
    package = read(PACKAGE); snapshot = read(evidence/'editor-snapshot.json')
    completion = read(evidence/'chat-completion.json')
    rows = confirmed_rows(package, snapshot, completion)
    base = read(BASE); dataset_contract(BASE)
    case = next(c for c in read(ROOT/'outputs/model-comparison/exp0070/data-readiness-v1/split-proposal.json')['cases'] if c['candidate_id']=='P01')
    protected, protection_paths = protected_hashes()
    if case['reserved_split'] != 'development' or case['capture_reservation'] != 'capture-reservation-01':
        raise ValueError('Development reservation changed')
    output.mkdir(parents=True, exist_ok=False); (output/'labels').mkdir()
    added = []
    for frame, revision in rows:
        if frame['source_sha256'] != case['source_sha256'] or frame['source_sha256'] in protected:
            raise ValueError('Protected or wrong source')
        if sha(frame['image_path']) != frame['image_sha256']:
            raise ValueError('Image changed')
        f = {k:copy.deepcopy(frame[k]) for k in ('frame_id','source_sha256','source_size','source_pts','native_pts_tick','frame_index','source_rgb_sha256','image_sha256')}
        f.update(split='development', event_group=case['original_group_id'],
            capture_reservation=case['capture_reservation'], source_id=case['source_id'],
            image=frame['image_path'], confirmed_person_boxes=copy.deepcopy(revision['boxes']),
            person_completeness_verified=True, training_release=False,
            action_ground_truth_verified=False, physical_capture_independence_certified=False,
            annotation_method='saved_editor_coordinates_and_completeness_plus_explicit_current_chat_completion',
            editor_revision=revision['version'], editor_status_preserved=revision['status'],
            review_evidence_sha256={n:sha(evidence/n) for n in ('editor-snapshot.json','chat-completion.json')})
        width,height = f['source_size']; lines=[]
        for b in f['confirmed_person_boxes']:
            x,y,u,v=b['xyxy']
            if not (0 <= x < u <= width and 0 <= y < v <= height):
                raise ValueError('Invalid saved coordinates')
            lines.append('0 '+' '.join(f'{n:.12f}' for n in ((x+u)/2/width,(y+v)/2/height,(u-x)/width,(v-y)/height)))
        label=output/'labels'/(f['frame_id']+'.txt');label.write_text('\n'.join(lines)+'\n')
        f.update(label=str(label),label_sha256=sha(label)); validate_frame(f);added.append(f)
    combined=copy.deepcopy(base);combined['frames']+=added;validate_splits(combined['frames'])
    if any(f['source_sha256'] in protected for f in combined['frames']):
        raise ValueError('Protected data used')
    combined.update(purpose='reviewed200_person_development_followup',
        parent_manifest_sha256=BASE_SHA,review_package_sha256=PACKAGE_SHA,
        frame_counts=dict(Counter(f['split'] for f in combined['frames'])),
        box_counts={s:sum(len(f['confirmed_person_boxes']) for f in combined['frames'] if f['split']==s) for s in ('train','development')},
        limitations=[x for x in base['limitations'] if not x.startswith('Only exact existing')]+[
            'Only three P01 frames newly confirmed; no approval of the other candidate frames',
            'Editor draft state preserved; current chat completion and saved confirmed=true jointly bind approval'],
        followup_exporter_sha256=sha(Path(__file__)),
        protected_input_sha256={str(p):sha(p) for p in protection_paths})
    write_json(output/'manifest.json',combined);dataset_contract(output/'manifest.json')
    subset=copy.deepcopy(combined);subset['frames']=added;subset['frame_counts']={'development':3};subset['box_counts']={'development':sum(len(f['confirmed_person_boxes']) for f in added)};subset['explicit_empty_frame_counts']={'development':0}
    write_json(output/'new-frames-only.json',subset)
    write_json(output/'import-receipt.json',dict(parent_manifest_sha256=BASE_SHA,
        combined_manifest_sha256=sha(output/'manifest.json'),new_frames=3,
        new_boxes=subset['box_counts']['development'],original197_preserved=combined['frames'][:197]==base['frames'],
        training_rows_unchanged=True,editor_database_unchanged=True,training_executed=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();export(a.evidence.resolve(),a.output.resolve())
