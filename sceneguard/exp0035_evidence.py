"""Display-only EXP-0034/0035 comparison of existing full-scene render videos.

No analysis, inference, region edits or identity decisions occur here. Native
source frame maps bind the three panels; playback timestamps must match exactly.
"""
import argparse
from contextlib import ExitStack
from fractions import Fraction
from pathlib import Path

import av
from PIL import Image, ImageDraw

from .exp0034_application import fresh_file
from .exp0034_evidence import font
from .mvp_review_evidence import _VideoWriter, _validate_video
from .run_tracklet_linking import sha256, write_json
from .run_mvp_review import load_json


def compare(key, output):
    old_dir = Path(f'outputs/exp0034/render{key}-v2')
    new_dir = Path(f'outputs/exp0035/render{key}-v1')
    result_path = Path(f'outputs/exp0035/{key}-v1.json')
    result = load_json(result_path)
    baseline_path = Path(result['baseline_path'])
    baseline = load_json(baseline_path)
    if sha256(baseline_path) != result['baseline_sha256']:
        raise ValueError('Baseline differs from application binding')
    maps = [load_json(p/'source-frames.json') for p in (old_dir, new_dir)]
    if maps[0] != maps[1] or len(maps[0]) != result['frames']:
        raise ValueError('Full native frame maps must match exactly')
    frame_map = maps[0]
    dt = Fraction(frame_map[1]['native_pts']-frame_map[0]['native_pts']) * Fraction(frame_map[0]['time_base'])
    if any(Fraction(f['native_pts'])*Fraction(f['time_base']) !=
           Fraction(frame_map[0]['native_pts'])*Fraction(frame_map[0]['time_base'])+i*dt
           for i, f in enumerate(frame_map)):
        raise ValueError('Expected a continuous original interval')
    receipts = [load_json(p/'render-receipt.json') for p in (old_dir, new_dir)]
    if (receipts[0]['result_sha256'] != sha256(baseline_path)
            or receipts[1]['result_sha256'] != sha256(result_path)):
        raise ValueError('Render/result binding differs')
    inputs = [(old_dir/'original.mp4', receipts[0]['videos']['original']),
              (old_dir/'direction_loss_status.mp4', receipts[0]['videos']['direction_loss_status']),
              (new_dir/'direction_loss_status.mp4', receipts[1]['videos']['direction_loss_status'])]
    before = {str(p): sha256(p) for p, _ in inputs}
    for path, receipt in inputs:
        if before[str(path)] != receipt['sha256'] or receipt['frames'] != len(frame_map):
            raise ValueError('Rendered input hash/count differs')
    output = fresh_file(output)
    receipt_path = fresh_file(output.with_suffix('.receipt.json'))
    with ExitStack() as stack:
        containers = [stack.enter_context(av.open(str(p))) for p, _ in inputs]
        decoders = [iter(c.decode(video=0)) for c in containers]
        writer = _VideoWriter(output, (1920, 1000), dt)
        stack.callback(writer.close)
        for index, source in enumerate(frame_map):
            frames = [next(decoder) for decoder in decoders]
            if any(f.pts is None or abs(float(f.pts*f.time_base-index*dt)) > 1e-5 for f in frames):
                raise ValueError('Panel playback/native map alignment differs')
            canvas = Image.new('RGB', (1920, 1000), '#101722')
            draw = ImageDraw.Draw(canvas)
            labels = ['원본 / ORIGINAL', 'EXP-0034 이전 상태', 'EXP-0035 완화 상태']
            for col, (frame, label) in enumerate(zip(frames, labels)):
                # Fit the entire existing render, including its separate PTS footer.
                image = frame.to_image()
                image.thumbnail((640, 384), Image.Resampling.LANCZOS)
                canvas.paste(image, (col*640, 64))
                draw.text((col*640+12, 12), label, font=font(26), fill='white')
            pts = source['pts']
            draw.text((12, 464), f'{result["video_id"]} SOURCE PTS {pts:.6f} | native {source["native_pts"]} * {source["time_base"]}', font=font(25), fill='white')
            draw.text((12, 503), '동일 영역 / 전체 장면 / 실제 PTS 정렬 / 침입 확인 자동 출력 없음', font=font(23), fill='white')
            draw.text((12, 540), f'OFFLINE available_after PTS {result["available_after_pts"]:.6f}; decision PTS = logical evidence timing', font=font(22), fill='white')
            draw.text((12, 590), '기존 경보 보존 / 의심 행 수는 사람 수·정확도가 아닙니다.', font=font(23), fill='white')
            alerts = [e for e in result['existing_alerts'] if e['emitted_at_pts'] <= pts+1e-9]
            for j, event in enumerate(alerts[-4:]):
                draw.text((12, 635+j*65), f'침입 의심 raw{event["track_id"]}\n구 규칙 decision {event["emitted_at_pts"]:.3f}', font=font(21), fill='yellow')
            for col, analysis in ((1, baseline), (2, result)):
                events = [e for e in analysis['events'] if e['decision_time_pts'] is not None and e['decision_time_pts'] <= pts+1e-9]
                draw.text((col*640+12, 590), f'상태 기록 {len(events)}행 (최근 4행)', font=font(23), fill='white')
                if not events:
                    draw.text((col*640+12, 635), '판단 불가', font=font(24), fill='yellow')
                for j, event in enumerate(events[-4:]):
                    source_pts = event['source_observed_pts']
                    draw.text((col*640+12, 635+j*80), f'{event["status"]} raw{event["raw_id"]} {event["segment"]}\nobs {source_pts:.3f} / decision {event["decision_time_pts"]:.3f}', font=font(22), fill='yellow')
            writer.write(canvas)
        if any(next(decoder, None) is not None for decoder in decoders):
            raise ValueError('Unexpected extra panel frames')
    if before != {str(p): sha256(p) for p, _ in inputs}:
        raise ValueError('Display input changed')
    receipt = dict(video_id=result['video_id'], result_sha256=sha256(result_path),
                   baseline_sha256=result['baseline_sha256'], inputs_sha256=before,
                   source_frame_map_sha256=sha256(new_dir/'source-frames.json'),
                   source_window=result['source_window'], full_original_interval=True,
                   full_scene_not_cropped=True, native_frame_maps_exact=True,
                   panel_order=labels, video=_validate_video(output, len(frame_map), dt),
                   human_visual_review='pending_root', inference_calls=0)
    write_json(receipt_path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', choices=('007', '030'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import json
    print(json.dumps(compare(args.key, args.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
