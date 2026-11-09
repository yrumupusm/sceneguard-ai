"""Apply bounded EXP72 observations as versioned annotation repairs, not GT.

No detector, NMS, tracking, training, or action/identity label release. Only five
new box envelopes are proposed for confirmation; an uncertain frame is held.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / 'outputs/model-comparison/exp0072/person-drafts-v1'
READY = ROOT / 'outputs/model-comparison/exp0070/data-readiness-v1'
OBS = ROOT / 'runtime/model-comparison/exp0072/user-observations'
# Manual annotation selection for this user's fixed-camera background location.
# This is not a deployment ROI, detector filter, or whole-region empty label.
BACKGROUND_SELECTION = [720, 35, 760, 90]
REPAIR_INDICES = {'R01': {60}, 'R02': {71, 72, 73, 75}}
HOLD_INDICES = {'R02': {70}}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)


def envelope(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def contained(box, area):
    return area[0] <= box[0] < box[2] <= area[2] and area[1] <= box[1] < box[3] <= area[3]


def rewrite(rid, old):
    """Keep exact provenance and every non-target box; never approve envelopes."""
    i = old['decoded_index']
    rows = old['model_proposals']
    assert len(rows['boxes']) == len(rows['person_scores']) == len(rows['valid_boxes'])
    assert all(rows['valid_boxes'])
    boxes = [dict(id=f'{rid}-{i}-model-{j}', xyxy=copy.deepcopy(b),
                  source_proposal_index=j, origin='model_proposal_retained_unconfirmed')
             for j, b in enumerate(rows['boxes'])]
    changes = []
    if rid == 'R03':
        removed = [b for b in boxes if contained(b['xyxy'], BACKGROUND_SELECTION)]
        boxes = [b for b in boxes if b not in removed]
        if removed:
            changes.append(dict(kind='remove_user_identified_background_proposals',
                                removed=removed, selector=BACKGROUND_SELECTION,
                                basis='user_location_observation_no_stable_box_id'))
    elif i in REPAIR_INDICES.get(rid, set()):
        if rid == 'R01':
            assert len(boxes) == 3
            # Screenshot shows a head/extended leg beyond the detector fragments.
            # Original actor is a reference only, never a certified label.
            actors = old['original_annotations_origin1']
            assert len(actors) == 1 and actors[0]['cur_frame'] == 61
            (x1, y1), (x2, y2) = actors[0]['bbox']
            reference = [x1, y1, x2, y2]
            affected = boxes
            xyxy = envelope([b['xyxy'] for b in affected] + [reference])
            basis = 'unverified_original_actor_and_three_model_fragments_envelope'
        else:
            affected = [b for b in boxes if b['xyxy'][0] > 1200]
            expected = {71: 4, 72: 3, 73: 2, 75: 3}[i]
            assert len(affected) == expected and len(boxes) == expected + 1
            xyxy = envelope([b['xyxy'] for b in affected])
            reference = None
            basis = 'envelope_of_user_identified_single_right_person_proposals'
        proposal = dict(id=f'{rid}-{i}-repair', xyxy=xyxy, source_proposal_index=None,
                        origin='assistant_coordinate_proposal_requires_confirmation')
        changes.append(dict(kind='propose_single_person_box', replaced=copy.deepcopy(affected),
                            replacement=proposal, basis=basis,
                            unverified_actor_reference=reference, coordinate_confirmed=False))
        boxes = [b for b in boxes if b not in affected] + [proposal]
    for b in boxes:
        assert contained(b['xyxy'], [0, 0, 1920, 1080])
    return dict(decoded_index=i, source_pts=old['source_pts'],
                source_rgb_sha256=old['source_rgb_sha256'], boxes=boxes, changes=changes,
                coordinate_confirmation_required=i in REPAIR_INDICES.get(rid, set()),
                whole_frame_hold=i in HOLD_INDICES.get(rid, set()),
                hold_reason='right_edge_person_candidate_uncertain_not_negative' if i in HOLD_INDICES.get(rid, set()) else None,
                complete_person_ground_truth=False, training_release=False)


def main(answers_path, output):
    import av
    from PIL import Image, ImageDraw, ImageFont
    answers = read(answers_path)
    by_artifact = {a['artifact_id']: a for a in answers}
    assert len(by_artifact) == 3
    observation_files = ['r01-20sec-duplicate-v1/observation.json',
                         'r02-right-person-v1/observation.json',
                         'r03-upper-road-v1/observation.json']
    bindings = {str(answers_path.resolve().relative_to(ROOT)): sha(answers_path)}
    for rel in observation_files:
        p = OBS / rel
        obs = read(p)
        answer = by_artifact[obs['artifact_id']]
        assert obs['request_id'] == answer['id'] and obs['answer_version'] == answer['answer_version'] == 1
        assert obs['source_binding_sha256'] == answer['source_binding_sha256']
        assert answer['status'] == 'applied'
        bindings[str(p.relative_to(ROOT))] = sha(p)
    for path, expected in read(READY/'input-bindings.json').items():
        assert sha(ROOT/path) == expected
        bindings[path] = expected
    for eid in ('exp0067', 'exp0071'):
        p = ROOT / f'outputs/model-comparison/{eid}/confirmed-person-v1/manifest.json'
        bindings[str(p.relative_to(ROOT))] = sha(p)
    cases = {c['candidate_id']: c for c in read(READY/'split-proposal.json')['cases']}
    output.mkdir(parents=True, exist_ok=False)
    (output/'images').mkdir(); (output/'media').mkdir()
    font = ImageFont.truetype('/home/jhc7484/.local/share/fonts/sceneguard-portfolio/malgun.ttf', 24)
    editor_frames = []; exports = []; previews = {'R01': [], 'R02': []}
    for rid in ('R01', 'R02', 'R03'):
        path = DRAFT/f'{rid}-drafts.json'; draft = read(path)
        bindings[str(path.relative_to(ROOT))] = sha(path)
        assert sha(DRAFT/draft['video']) == draft['video_sha256']
        case = cases[draft['candidate_id']]
        assert case['capture_reservation'] == draft['capture_reservation']
        assert case['reserved_split'] == draft['reserved_split']
        assert case['reserved_split'] == ('development' if rid == 'R03' else 'train')
        frames = [rewrite(rid, f) for f in draft['frames']]
        lookup = {f['decoded_index']: f for f in frames}
        originals = {f['decoded_index']: f for f in draft['frames']}
        ref = case['source_reference']
        if 'path' in ref:
            raw = Path(ref['path']).read_bytes()
        else:
            with zipfile.ZipFile(ref['archive_path']) as z:
                raw = z.read(ref['member'])
        assert hashlib.sha256(raw).hexdigest() == draft['source_sha256']
        seen = set()
        with av.open(io.BytesIO(raw)) as source:
            stream = source.streams.video[0]; stream.codec_context.thread_count = 1
            assert stream.average_rate == 3 and stream.start_time == 0
            source.seek(int(min(lookup)/3/float(stream.time_base)), stream=stream, backward=True)
            for frame in source.decode(stream):
                t = float(frame.pts*frame.time_base); i = round(t*3)
                if i > max(lookup): break
                if i not in lookup: continue
                row = lookup[i]; old = originals[i]; rgb = frame.to_ndarray(format='rgb24')
                assert abs(t-row['source_pts']) < 1e-6 and hashlib.sha256(rgb.tobytes()).hexdigest() == row['source_rgb_sha256']
                seen.add(i)
                if row['coordinate_confirmation_required']:
                    fid = f'exp0073-{rid.lower()}-frame-{i:06d}'
                    image = output/'images'/f'{fid}.png'; frame.to_image().save(image)
                    editor_frames.append(dict(frame_id=fid, case_number=int(rid[1:]),
                        split='train', event_group=case['capture_reservation'],
                        source_sha256=draft['source_sha256'], source_size=[1920,1080],
                        source_pts=t, native_pts_tick=frame.pts, frame_index=i,
                        source_rgb_sha256=row['source_rgb_sha256'], image_path=str(image.resolve()),
                        image_sha256=sha(image), candidates=[], review_id=rid,
                        proposed_boxes=[dict(id=b['id'],xyxy=b['xyxy'],source_id=None) for b in row['boxes']],
                        review_guidance=('주간 20초: 머리·뻗은 다리·아래 발을 포함하도록 만든 한 박스 수정안입니다.' if rid=='R01' else '오른쪽 한 사람의 중복 박스를 한 박스로 묶은 수정안입니다. 왼쪽 인물의 박스는 그대로입니다.')))
                    pic = frame.to_image(); before = pic.copy(); after = pic.copy()
                    d = ImageDraw.Draw(before)
                    for box in old['model_proposals']['boxes']: d.rectangle(box, outline='#ff9900', width=4)
                    d = ImageDraw.Draw(after)
                    for box in row['boxes']: d.rectangle(box['xyxy'], outline='#00ffff' if box['origin'].startswith('assistant') else '#ff9900', width=4)
                    canvas = Image.new('RGB',(1920,640),'#151515')
                    canvas.paste(before.resize((960,540)),(0,65)); canvas.paste(after.resize((960,540)),(960,65))
                    d = ImageDraw.Draw(canvas)
                    d.text((12,4),f'{rid} 원본 {t:.3f}초 | 왼쪽: 기존 초안 / 오른쪽: 좌표 수정안',font=font,fill='white')
                    d.text((12,33),'청록색 = 새 좌표안(미확인). 주황색 = 유지한 초안. 행동 정답이 아닙니다.',font=font,fill='#00ffff')
                    d.text((12,608),'새 박스가 보이는 사람의 머리·몸·팔다리를 적절히 감싸는지만 확인해 주세요.',font=font,fill='white')
                    still = output/'media'/f'{fid}-comparison.jpg'; canvas.save(still,quality=96)
                    previews[rid].append(canvas)
        assert seen == set(lookup)
        exported = dict(review_id=rid, source_id=draft['source_id'], source_sha256=draft['source_sha256'],
                        reserved_split=draft['reserved_split'], capture_reservation=draft['capture_reservation'],
                        answer_version=by_artifact[f'exp0072-{rid.lower()}-comparison']['answer_version'],
                        frames=frames, training_release=False, input_draft_sha256=sha(path))
        save(output/f'{rid}-repaired-draft.json',exported); exports.append(exported)
    # These are labelled still-image sequences at 1FPS, not real-time video.
    for rid, pics in previews.items():
        target = output/'media'/f'{rid}-coordinate-review.mp4'
        shown = [pics[0]]*3 if len(pics)==1 else pics
        with av.open(str(target),'w') as video:
            stream = video.add_stream('libx264',rate=1); stream.width=1920; stream.height=640; stream.pix_fmt='yuv420p'
            stream.options={'crf':'18','preset':'fast','threads':'2'}
            for pic in shown:
                for packet in stream.encode(av.VideoFrame.from_image(pic)): video.mux(packet)
            for packet in stream.encode(): video.mux(packet)
        with av.open(str(target)) as video: assert sum(1 for _ in video.decode(video=0)) == len(shown)
    save(output/'editor-package.json',dict(schema_version=1,experiment_id='EXP-0073',
        training_release=False,purpose='five new coordinates only; unknown R02 23.333 excluded',frames=editor_frames))
    all_frames = [f for e in exports for f in e['frames']]
    removed = [c for f in all_frames for c in f['changes'] if c['kind']=='remove_user_identified_background_proposals']
    assert len(editor_frames)==5 and sum(f['whole_frame_hold'] for f in all_frames)==1
    assert len(removed)==13 and sum(len(c['removed']) for c in removed)==17
    assert sum(len(f['boxes']) for f in all_frames)==169
    for path,h in bindings.items(): assert sha(ROOT/path)==h
    summary = dict(experiment_id='EXP-0073',reviewed_observations_reused=3,
        input_frames=72,input_proposals=196,output_draft_boxes=169,
        background_removed_proposals=17,background_affected_frames=13,
        duplicate_coordinate_proposal_frames=5,uncertain_whole_frames_held=1,
        new_ground_truth_frames=0,training_release=False,training_runs=0,new_model_inference=0,
        input_sha256=bindings,script_sha256=sha(Path(__file__)),
        preview_kind='noncontinuous source stills at 1FPS; R01 single frame repeated3',
        editor_package_sha256=sha(output/'editor-package.json'))
    save(output/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='input_sha256'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--answers',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    main(args.answers,args.output)
