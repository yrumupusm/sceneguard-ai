"""EXP0071: bounded CPU-only person proposals, never ground truth or training.

Uses original native-PTS frames after checking EXP0070 split reservations and
exact prior-review exclusions. This is a separate annotation-preparation mode,
not the canonical CUDA benchmark adapter. All outputs stay local.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

os.environ['CUDA_VISIBLE_DEVICES'] = ''

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'outputs/model-comparison/exp0070/data-readiness-v1'
WEIGHT = ROOT / 'runtime/model-comparison/exp0066/yolo26-preparation-v1/yolo26x.pt'
WEIGHT_SHA = '9fdd44a31c504547ffb81d2c6d9e6dac3493c8eaa8b0398d3f43bae6c7003e92'
# Each tuple is one small, explicit question, not a release of the whole source.
SELECTION = [('R01', 'P16', 0, 1), ('R02', 'P20', 0, 1),
             ('R03', 'P05', 0, 1), ('R04', 'P18', 0, 2), ('R05', 'P05', 1, 2)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def get_bytes(ref):
    if 'path' in ref:
        return Path(ref['path']).read_bytes()
    with zipfile.ZipFile(ref['archive_path']) as z:
        return z.read(ref['member'])


def preflight(out):
    split = read(OLD / 'split-proposal.json')
    reuse = read(OLD / 'review-reuse.json')['EXP0067']
    for path, expected in read(OLD / 'input-bindings.json').items():
        assert sha(ROOT / path) == expected, path
    assert sha(WEIGHT) == WEIGHT_SHA
    by_id = {r['candidate_id']: r for r in split['cases']}
    reservations = {r['reservation_id']: r for r in split['captures']}
    members = split['closure_members']
    selected = []
    for rid, cid, wi, batch in SELECTION:
        case = by_id[cid]
        assert case['disposition'] == 'review_candidate'
        reservation = reservations[case['capture_reservation']]
        assert reservation['reserved_split'] == case['reserved_split']
        closure = [m for m in members if m['capture_reservation'] == case['capture_reservation']]
        assert closure and {m['reserved_split'] for m in closure} == {case['reserved_split']}
        check = read(OLD / f'{cid}-source-check.json')
        assert not check['exact_protected_or_other_split_match']
        assert not check['protected_content_suspects']
        pts = case['proposed_windows'][wi]['actual_pts']
        for old in reuse:
            if old['source_sha256'] == case['source_sha256']:
                assert all(not old['pts_range'][0]-1e-6 <= p <= old['pts_range'][1]+1e-6 for p in pts)
        selected.append(dict(review_id=rid, batch=batch, case=case, window_index=wi,
                             pts=pts, reserved_members=len(closure)))
    # Explicitly distinguish reservation checks from unknown capture identity.
    save(out / 'selection-before-inference.json', dict(
        selection=selected, exact_old_review_overlap=0,
        known_reservation_conflicts=0, camera_identity_certified=False,
        event_independence_certified=False, training_release=False,
        old_input_bindings=read(OLD / 'input-bindings.json'),
        split_sha256=sha(OLD / 'split-proposal.json')))
    return selected


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    selected = preflight(out)
    # Offline setup is shared; the CUDA adapter and its queue guard are untouched.
    from exp0066_yolo import configure_offline, validate_loaded_model, result_rows
    configure_offline(out / 'runtime-settings')
    import av
    import numpy as np
    import torch
    import ultralytics
    from ultralytics import YOLO
    from ultralytics.utils import SETTINGS
    from PIL import Image, ImageDraw, ImageFont
    assert ultralytics.__version__ == '8.4.192'
    assert not torch.cuda.is_available()
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    SETTINGS.update({k: False for k in ('sync', 'clearml', 'comet', 'dvc', 'mlflow',
                                       'raytune', 'tensorboard', 'wandb')})
    model = YOLO(str(WEIGHT), task='detect')
    validate_loaded_model(model)
    model.model.to('cpu').eval()
    predict = dict(imgsz=640, rect=False, batch=1, conf=.05, device='cpu',
                   nms=False, max_det=300, iou=.7, agnostic_nms=False,
                   classes=[0], augment=False, compile=False, half=False,
                   save=False, save_txt=False, save_crop=False, show=False,
                   verbose=False, stream=False, visualize=False)
    font = ImageFont.truetype('/home/jhc7484/.local/share/fonts/sceneguard-portfolio/malgun.ttf', 24)
    media = out / 'media'; media.mkdir()
    manifest = dict(experiment_id='EXP-0071', status='unreviewed_annotation_drafts',
                    mode='CPU_annotation_preparation_not_benchmark', device='cpu',
                    pretrained_model='yolo26x', checkpoint_sha256=WEIGHT_SHA,
                    ultralytics=ultralytics.__version__, torch=torch.__version__,
                    predict_kwargs=predict, training_executed=False,
                    training_eligible=False, complete_person_ground_truth=False,
                    old_review_overlap_frames=0, inference_frames=0, cases=[])
    for selection in selected:
        case = selection['case']; rid = selection['review_id']; cid = case['candidate_id']
        raw = get_bytes(case['source_reference'])
        assert hashlib.sha256(raw).hexdigest() == case['source_sha256']
        labelraw = get_bytes(case['label_reference'])
        assert hashlib.sha256(labelraw).hexdigest() == case['label_sha256']
        labels = json.loads(labelraw)
        wanted = {round(p*3): p for p in selection['pts']}
        frames = []; pics = []
        with av.open(io.BytesIO(raw)) as source:
            stream = source.streams.video[0]; stream.codec_context.thread_count = 1
            assert stream.average_rate == 3 and stream.start_time == 0
            source.seek(int(min(wanted)/3/float(stream.time_base)), stream=stream, backward=True)
            for frame in source.decode(stream):
                pts = float(frame.pts * frame.time_base); index = round(pts*3)
                if index > max(wanted): break
                if index not in wanted: continue
                assert abs(wanted[index]-pts) < 1e-6
                rgb = frame.to_ndarray(format='rgb24')
                with torch.inference_mode():
                    result = model.predict(np.ascontiguousarray(rgb[:, :, ::-1]), **predict)[0]
                assert all(p.device.type == 'cpu' for p in model.model.parameters())
                assert model.predictor.model.end2end and not model.predictor.model.fp16
                rows = result_rows(result, rgb.shape[0], rgb.shape[1])
                row = dict(decoded_index=index, source_pts=pts,
                           source_rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),
                           model_proposals=rows, human_review_status='unreviewed',
                           complete_person_labels=False, empty_background_confirmed=False,
                           original_annotations_origin0=[a for a in labels.get('annotations', []) if a.get('cur_frame') == index],
                           original_annotations_origin1=[a for a in labels.get('annotations', []) if a.get('cur_frame') == index+1])
                # Keep original actor annotations in JSON, separate from all-person proposals.
                # No interpolation, association, semantic assignment, or GT union is made.
                original = Image.fromarray(rgb); marked = original.copy(); draw = ImageDraw.Draw(marked)
                for bi, (box, score) in enumerate(zip(rows['boxes'], rows['person_scores'])):
                    if not rows['valid_boxes'][bi]: continue
                    draw.rectangle(box, outline=(255, 150, 0), width=4)
                    draw.text((box[0], max(0, box[1]-28)), f'{bi+1}: {score:.2f}',
                              fill=(255,150,0), font=font, stroke_width=1, stroke_fill='black')
                canvas = Image.new('RGB', (1920, 640), '#151515')
                canvas.paste(original.resize((960,540)), (0,65))
                canvas.paste(marked.resize((960,540)), (960,65))
                d = ImageDraw.Draw(canvas)
                d.text((12,4), f'{rid} / {cid}  원본 {pts:.3f}초  |  왼쪽: 원본  /  오른쪽: 모든 사람 박스 초안', font=font, fill='white')
                d.text((12,33), '주황색 = 모델 제안(미검수). 숫자는 사람 점수이며 넘기 점수가 아닙니다.', font=font, fill='#ffb14a')
                d.text((12,608), '박스가 없어도 사람 없음이 아닙니다. 작은 사람·가려진 사람·동행자도 확인해 주세요.', font=font, fill='white')
                pics.append(canvas); frames.append(row)
                if len(frames) == len(wanted)//2+1:
                    original.save(media / f'{rid}-original.jpg', quality=96)
                    marked.save(media / f'{rid}-proposals.jpg', quality=96)
                manifest['inference_frames'] += 1
        assert len(frames) == len(wanted)
        path = media / f'{rid}-comparison.mp4'
        with av.open(str(path), 'w') as output:
            stream = output.add_stream('libx264', rate=3)
            stream.width=1920; stream.height=640; stream.pix_fmt='yuv420p'
            stream.options={'crf':'18','preset':'fast','threads':'2'}
            for pic in pics:
                for packet in stream.encode(av.VideoFrame.from_image(pic)): output.mux(packet)
            for packet in stream.encode(): output.mux(packet)
        with av.open(str(path)) as rendered:
            count = sum(1 for _ in rendered.decode(video=0))
        assert count == len(frames)
        item = dict(review_id=rid, candidate_id=cid, batch=selection['batch'],
                    source_id=case['source_id'], source_sha256=case['source_sha256'],
                    label_sha256=case['label_sha256'], reserved_split=case['reserved_split'],
                    capture_reservation=case['capture_reservation'],
                    source_pts=[r['source_pts'] for r in frames], frame_count=len(frames),
                    proposal_count=sum(len(r['model_proposals']['boxes']) for r in frames),
                    zero_proposal_frames=sum(not r['model_proposals']['boxes'] for r in frames),
                    video=str(path.relative_to(out)), video_sha256=sha(path),
                    verified_video_frames=count, complete_person_ground_truth=False,
                    coordinates_are_draft=True, training_eligible=False, frames=frames)
        save(out / f'{rid}-drafts.json', item)
        manifest['cases'].append({k:v for k,v in item.items() if k!='frames'})
        print(json.dumps(manifest['cases'][-1], ensure_ascii=False), flush=True)
    assert sha(WEIGHT) == WEIGHT_SHA
    for path, expected in read(OLD / 'input-bindings.json').items(): assert sha(ROOT/path) == expected
    manifest['inputs_and_checkpoint_preserved']=True
    save(out / 'manifest.json', manifest)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
