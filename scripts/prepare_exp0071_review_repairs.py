"""Apply exact EXP0071 observations and prepare only unresolved coordinate work.

No detector, training, inferred two-box selection, or human approval is run.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DRAFT=ROOT/'outputs/model-comparison/exp0071/person-drafts-v1'


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
    with p.open('x') as f: json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)


def main(answers,out):
    import av
    out.mkdir(parents=True,exist_ok=False);(out/'images').mkdir()
    responses=read(answers)
    by_artifact={r['artifact_id']:r for r in responses}
    plan=read(ROOT/'outputs/model-comparison/exp0070/data-readiness-v1/split-proposal.json')
    cases={c['candidate_id']:c for c in plan['cases']}
    frames=[];applications=[]
    for rid in ('R02','R01','R03','R04','R05'):
        path=DRAFT/f'{rid}-drafts.json';draft=read(path)
        answer=by_artifact[f'exp0071-{rid.lower()}-comparison']
        assert answer['answer_version']==1 and answer['status'] in ('answered','acknowledged')
        assert sha(DRAFT/draft['video'])==draft['video_sha256']
        if rid=='R02':
            assert '두명' in answer['answer'] and '가려' in answer['answer']
            repair=draft['frames'];disposition='hold_merged_duplicate_occluded_person_boxes'
        elif rid=='R05':
            assert answer['answer']=='전 구간에서 보이는 사람이 없음'
            assert all(not f['model_proposals']['boxes'] for f in draft['frames'])
            repair=[];disposition='human_observed_empty_exact_25_frames_development_only'
        else:
            assert answer['answer']=='이 구간의 모든 보이는 사람에게 박스가 맞음'
            repair=[f for f in draft['frames'] if not f['model_proposals']['boxes']]
            disposition='displayed_person_boxes_accepted_in_video_review_not_dataset_release'
        applications.append(dict(review_id=rid,request_id=answer['id'],answer_version=answer['answer_version'],
            source_binding_sha256=answer['source_binding_sha256'],answer=answer['answer'],note=answer['note'],
            draft_sha256=sha(path),video_sha256=draft['video_sha256'],source_sha256=draft['source_sha256'],
            source_pts=draft['source_pts'],disposition=disposition,
            coordinate_repair_frames=[f['source_pts'] for f in repair],
            observation_reused=True,action_truth_verified=False,training_release=False))
        if not repair: continue
        case=cases[draft['candidate_id']];ref=case['source_reference']
        if 'path' in ref: raw=Path(ref['path']).read_bytes()
        else:
            with zipfile.ZipFile(ref['archive_path']) as z:raw=z.read(ref['member'])
        assert hashlib.sha256(raw).hexdigest()==draft['source_sha256']
        lookup={f['decoded_index']:f for f in repair}
        with av.open(io.BytesIO(raw)) as video:
            stream=video.streams.video[0];stream.codec_context.thread_count=1
            assert stream.average_rate==3
            video.seek(int(min(lookup)/3/float(stream.time_base)),stream=stream,backward=True)
            for f in video.decode(stream):
                t=float(f.pts*f.time_base);i=round(t*3)
                if i>max(lookup):break
                if i not in lookup:continue
                old=lookup[i];rgb=f.to_ndarray(format='rgb24')
                assert abs(old['source_pts']-t)<1e-6
                assert hashlib.sha256(rgb.tobytes()).hexdigest()==old['source_rgb_sha256']
                fid=f'exp0071-{rid.lower()}-frame-{i:06d}';pic=out/'images'/f'{fid}.png'
                f.to_image().save(pic)
                candidates=[]
                for j,(box,score,valid) in enumerate(zip(old['model_proposals']['boxes'],old['model_proposals']['person_scores'],old['model_proposals']['valid_boxes'])):
                    if valid:candidates.append(dict(id=f'{fid}-model-{j}',kind='model',label=f'미확정 초안 {j+1}',xyxy=box,score=score))
                original=[]
                for j,a in enumerate(old['original_annotations_origin1']):
                    (x1,y1),(x2,y2)=a['bbox']
                    if 0<=x1<x2<=1920 and 0<=y1<y2<=1080:
                        original.append(dict(actor_id=a.get('actor_id'),xyxy=[x1,y1,x2,y2]))
                        candidates.append(dict(id=f'{fid}-original-{j}',kind='original',label=f'기존 actor {a.get("actor_id")} · 1번 시작 가정/미확정',xyxy=[x1,y1,x2,y2],score=None))
                frames.append(dict(frame_id=fid,case_number=int(rid[1:]),split='train',
                    event_group=case['capture_reservation'],source_sha256=draft['source_sha256'],
                    source_size=[1920,1080],source_pts=t,native_pts_tick=f.pts,frame_index=i,
                    source_rgb_sha256=old['source_rgb_sha256'],image_path=str(pic.resolve()),image_sha256=sha(pic),
                    original_boxes_by_origin={'1':original},frame_origin_certified=False,
                    candidates=candidates,review_id=rid,completeness_answer_version=1,
                    correction_reason='overlap and fence occlusion; do not force two boxes on invisible people' if rid=='R02' else 'zero proposal despite video-level approval; empty/person coordinates unresolved'))
    assert len(frames)==25 and sum(f['case_number']==2 for f in frames)==24
    save(out/'editor-package.json',dict(schema_version=1,experiment_id='EXP-0071',training_release=False,
        purpose='R02 coordinate correction24 + R01 ambiguous zero-proposal frame1; no repeat of accepted full clips',
        responses_sha256=sha(answers),frames=frames))
    save(out/'review-application.json',dict(experiment_id='EXP-0071',responses_sha256=sha(answers),
        applications=applications,accepted_observations_frames=97,coordinate_repair_frames=25,
        new_confirmed_coordinate_export=False,training_release=False,training_runs=0,
        script_sha256=sha(Path(__file__))))
    print(json.dumps(dict(editor_frames=len(frames),observations_applied=5,training_release=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--answers',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.answers,a.output)
