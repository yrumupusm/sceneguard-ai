"""Local-only four-scene EXP0060 review from saved observations; no inference."""
import argparse
import csv
from fractions import Fraction
import hashlib
import html
import json
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'outputs/validation/combined-all45-v1/run-001'
SPECS = [('017', 54, 88, 64.133333, '첫 확인 앞당김'),
         ('017', 99, 119, 109.3, '추가 확인'),
         ('037', 72, 93, 82.633333, '추가 확인'),
         ('039', 114, 134, 124.233333, '추가 확인')]
PURPLE, CYAN, GREEN, RED = '#d06aff', '#36dfff', '#46e895', '#ff534d'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def clock(row):
    return row['native_pts'] * Fraction(row['time_base'])


def observed_tracks(row):
    return [b for b in row['actual_boxes'] if b.get('observed') is not False
            and b.get('assignment') == 'confirmed_track']


def prepare(spec, comparison):
    number, start, end, target, title = spec
    vid = f'E01_{number}'
    manifest_path = RUN / f'input-manifest-{number}.json'
    manifest = read(manifest_path)
    request_path = Path(manifest['measurement_source']) / 'request.json'
    request = read(request_path)
    video_path = Path(request['video'])
    source_dir = RUN / 'inputs' / number
    paths = [manifest_path, request_path, video_path] + [source_dir / n for n in
             ('frame-evidence.jsonl', 'scene.json', 'portal.json')]
    hashes = {str(p): sha(p) for p in paths}
    assert hashes[str(video_path)] == request['input_sha256'][str(video_path)]
    assert hashes[str(request_path)] == manifest['protected_sources'][str(request_path)]
    for p in paths[3:]:
        assert hashes[str(p)] == manifest['replay_inputs'][str(p)]
    with av.open(str(video_path)) as src:
        s = src.streams.video[0]
        eof = s.duration * s.time_base
        rate = s.average_rate
        tb = s.time_base
    bounded_end = min(Fraction(end), eof)
    rows = []
    with (source_dir / 'frame-evidence.jsonl').open() as f:
        for line in f:
            r = json.loads(line)
            if clock(r) >= bounded_end:
                break
            if clock(r) >= start:
                # Retain only fields used by the display, never point paths or inference.
                rows.append({k: r[k] for k in
                             ('pts', 'native_pts', 'time_base', 'frame_index', 'actual_boxes')})
    assert rows and len({clock(r) for r in rows}) == len(rows)
    notice = [n for n in comparison['notices']['after']['confirmation']
              if n['video_id'] == vid and abs(n['pts'] - target) < 1e-6]
    assert len(notice) == 1, (vid, target)
    events = [r for r in comparison['per_event']
              if r['video_id'] == vid and r['mode'] == 'confirmation']
    return dict(video_id=vid, start=start, requested_end=end, end=float(bounded_end),
                eof=float(eof), rows=rows, rate=rate, time_base=tb,
                source=video_path, hashes=hashes, scene=read(source_dir / 'scene.json'),
                portal=read(source_dir / 'portal.json'), notice=notice[0], events=events,
                title=title, slug=f'{number}_{start}-{end}')


def paint(frame, row, item, overlay, fonts):
    w, h = item['scene']['source_size']
    assert (frame.width, frame.height) == (w, h)
    canvas = Image.new('RGB', (w, h + 96), '#122028')
    canvas.paste(frame.to_image(), (0, 96))
    d = ImageDraw.Draw(canvas)
    player = float(clock(row) - clock(item['rows'][0]))
    mode = '저장된 실제 관측 박스' if overlay else '원본 영상'
    d.text((18, 10), f"{item['video_id']} · 원본 {row['pts']:.6f}초 · 재생 {player:.3f}초 · {mode} · 미검수", font=fonts[0], fill='white')
    if not overlay:
        d.text((18, 52), '원본 전체 화면 · 영상 상단은 원본 시각 / 플레이어는 잘라낸 구간의 상대 시각', font=fonts[1], fill='white')
        return canvas
    x = 18
    for text, color in [('보라: 바깥·공통선', PURPLE), ('하늘: 안쪽선', CYAN),
                        ('초록: 추적 관측 박스', GREEN), ('빨강점: 박스 하단 중앙 (발 위치 아님)', RED)]:
        d.text((x, 52), text, font=fonts[1], fill=color)
        x += d.textlength(text, font=fonts[1]) + 30
    for key, color in [('line', PURPLE), ('inner_line', CYAN)]:
        d.line([(round(x*w), 96+round(y*h)) for x, y in item['scene'][key]],
               fill=color, width=4)
    for b in observed_tracks(row):
        x0, y0, x1, y1 = [round(v * (w if i % 2 == 0 else h))
                          for i, v in enumerate(b['bbox'])]
        d.rectangle((x0, y0+96, x1, y1+96), outline=GREEN, width=3)
        cx, cy = (x0+x1)/2, y1+96
        d.ellipse((cx-5, cy-5, cx+5, cy+5), fill=RED)
        label = 'ID ' + ','.join(map(str, b['track_ids']))
        xy = (max(0, x0), max(96, y0+72))
        bounds = d.textbbox(xy, label, font=fonts[2])
        d.rectangle(bounds, fill='#122028')
        d.text(xy, label, font=fonts[2], fill=GREEN)
    return canvas


def render(item, folder, overlay, fonts, preview):
    path = folder / ('overlay.mp4' if overlay else 'original.mp4')
    rows = item['rows']
    first = clock(rows[0])
    by_clock = {(r['native_pts'], Fraction(r['time_base'])): r for r in rows}
    seen = []
    with av.open(str(item['source'])) as src, av.open(str(path), 'w', options={'movflags': '+faststart'}) as dst:
        source_stream = src.streams.video[0]
        source_stream.codec_context.thread_count = 2
        out = dst.add_stream('libx264', rate=item['rate'])
        w, h = item['scene']['source_size']
        out.width, out.height = w, h+96
        out.pix_fmt = 'yuv420p'
        out.time_base = item['time_base']
        out.codec_context.time_base = item['time_base']
        out.codec_context.thread_count = 2
        out.options = {'crf': '19', 'preset': 'veryfast', 'threads': '2'}
        src.seek(int(first / source_stream.time_base), stream=source_stream, backward=True)
        for frame in src.decode(video=0):
            current = frame.pts * frame.time_base
            if current < first:
                continue
            if current > clock(rows[-1]):
                break
            row = by_clock[(frame.pts, frame.time_base)]
            assert abs(float(current)-row['pts']) < 1e-8
            im = paint(frame, row, item, overlay, fonts)
            if overlay and abs(row['pts']-item['notice']['pts']) < 1e-6:
                im.save(preview)
            vf = av.VideoFrame.from_image(im)
            vf.time_base = frame.time_base
            vf.pts = int((current-first) / frame.time_base)
            assert vf.pts * vf.time_base == current-first
            for packet in out.encode(vf):
                dst.mux(packet)
            seen.append(row['frame_index'])
        for packet in out.encode():
            dst.mux(packet)
    assert seen == [r['frame_index'] for r in rows]
    expected = [clock(r)-first for r in rows]
    with av.open(str(path)) as decoded:
        decoded.streams.video[0].codec_context.thread_count = 2
        frames = [(f.pts * f.time_base, f.width, f.height) for f in decoded.decode(video=0)]
        duration = decoded.streams.video[0].duration * decoded.streams.video[0].time_base
    assert [f[0] for f in frames] == expected, 'Output clock changed'
    assert all(f[1:] == (w, h+96) for f in frames)
    assert duration == expected[-1] + 1/item['rate']
    return dict(path=str(path), sha256=sha(path), decoded_frames=len(frames),
                every_native_clock_preserved=True, playback_start=0,
                playback_last=float(expected[-1]), duration_seconds=float(duration),
                width=w, height=h+96, decode_passed=True)


def gallery(items):
    cards = []
    for i, item in enumerate(items):
        notice = item['notice']['pts']
        refs = '; '.join(f"{r['reference']['start']:.6f}–{r['reference']['end']:.6f}초"
                         for r in item['events'])
        context = f'공식 참조 구간(해당 영상): {refs}.'
        if i == 0:
            before = item['events'][0]['before_first_confirmation_or_suspicion_notice_pts']
            context += f' 이전 첫 확인 {before:.6f}초 → 이번 첫 확인 {notice:.6f}초.'
        else:
            context += ' 이 추가 확인 시각은 위 공식 참조 구간 밖입니다. 실제 행동은 미검수입니다.'
        if item['end'] < item['requested_end']:
            context += f" 요청 종료 {item['requested_end']}초는 원본 끝 {item['end']:.6f}초로 제한했습니다."
        slug = item['slug']
        cards.append(f'''<article data-start="{item['start']}" data-folder="{slug}">
<h2>{i+1}. {item['video_id']} · {item['title']} · {notice:.6f}초 <small>미검수</small></h2>
<p>원본 구간 {item['start']}–{item['end']:.6f}초 · 종료 시각 제외<br>{html.escape(context)}</p>
<div class="controls"><button data-view="original">원본</button><button data-view="overlay" aria-pressed="true">박스 겹쳐 보기</button>
<button data-seek="{notice-item['start']}">확인 통지 {notice:.6f}초로</button>
<button data-rate="0.5">0.5배속</button><button data-rate="1">1배속</button></div>
<video controls preload="metadata" src="{slug}/overlay.mp4"></video>
<p class="clock">플레이어 0초 = 원본 {item['start']}초</p>
<p class="legend"><span style="color:{PURPLE}">━ 바깥·공통선</span>　<span style="color:{CYAN}">━ 기존 안쪽선</span>　<span style="color:{GREEN}">□ 저장된 추적 관측</span>　<span style="color:{RED}">● 박스 하단 중앙</span></p>
<p><a href="{slug}/frame_mapping.csv">프레임 시각 대응표</a> · <a href="{slug}/receipt.json">원본·출력 SHA256 영수증</a></p></article>''')
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>EXP0060 새 테스트 · 미검수 네 장면</title>
<style>body{max-width:1400px;margin:28px auto;padding:0 18px;background:#111b24;color:#e9f0f5;font:17px/1.6 system-ui,sans-serif}h1{font-size:29px}h2{font-size:23px}article{margin:30px 0;padding:22px;background:#1c2a35;border-radius:12px}small{font-size:15px;color:#ffda85}video{width:100%;max-height:78vh;background:#000}button{font:inherit;margin:4px;padding:8px 14px;border:1px solid #718a9e;border-radius:6px;background:#263e50;color:white;cursor:pointer}button[aria-pressed=true]{background:#416780}a{color:#a2d7ff}.clock{font-variant-numeric:tabular-nums}.legend{font-size:16px}</style>
<h1>새 테스트에서 새로 확인 통지가 나온 미검수 네 장면</h1>
<p>EXP0060 new36 중 지정된 017 두 장면, 037·039 각 한 장면입니다. 이미 검수한 영상은 제외했습니다.<br>
영상 상단은 원본 시각이며 플레이어 시각은 각 클립 시작부터 셉니다. 확인 통지는 시스템 출력이며 사용자 검수 완료를 뜻하지 않습니다.</p>
<p>전체 화면의 저장된 실제 추적 관측만 표시합니다. 미연결·미확정 검출 후보는 생략했습니다.<br>
추적 ID는 사람 신원이나 동일인 정답이 아닙니다. 빨간 점은 박스 하단 중앙이며 실제 발 위치를 복원하지 않았습니다.<br>
공식 구간은 문맥용 참조이며 정밀 행동 경계가 아닙니다(0-based 참조, 원본 인덱싱 미확정). 이 페이지는 로컬 영상 열람용입니다.</p>
''' + '\n'.join(cards) + '''
<script>
for(const card of document.querySelectorAll('article')){
 const v=card.querySelector('video'),clock=card.querySelector('.clock');
 let desiredTime=0,desiredRate=1,pending=false;
 function update(){clock.textContent=`원본 ${(Number(card.dataset.start)+v.currentTime).toFixed(3)}초 · 플레이어 ${v.currentTime.toFixed(3)}초 · ${v.playbackRate}배속`;}
 v.addEventListener('timeupdate',update);v.addEventListener('ratechange',update);
 v.addEventListener('loadedmetadata',()=>{if(pending){v.currentTime=Math.min(desiredTime,Math.max(0,v.duration-1/30));v.playbackRate=desiredRate;pending=false;}update();});
 card.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;
  if(b.dataset.view){desiredTime=pending?desiredTime:v.currentTime;desiredRate=pending?desiredRate:v.playbackRate;pending=true;v.pause();v.src=card.dataset.folder+'/'+b.dataset.view+'.mp4';
   for(const x of card.querySelectorAll('[data-view]'))x.setAttribute('aria-pressed',String(x===b));
  }else if(b.dataset.seek){desiredTime=Number(b.dataset.seek);if(v.readyState>=1&&!pending)v.currentTime=desiredTime;else pending=true;
  }else if(b.dataset.rate){desiredRate=Number(b.dataset.rate);v.playbackRate=desiredRate;}
 });
}
</script></html>'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('/mnt/c/Users/jhc74/AppData/Local/Temp/SceneGuard_새테스트_미검수_20261105'))
    p.add_argument('--runtime', type=Path, default=ROOT/'runtime/exp0060-new-scenes')
    p.add_argument('--font', type=Path, default=Path('/home/jhc7484/.local/share/fonts/sceneguard-portfolio/malgun.ttf'))
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    args.runtime.mkdir(parents=True, exist_ok=True)
    comparison_path = RUN/'event-comparison.json'
    protected = [comparison_path, ROOT/'scripts/render_saved_box_review.py']
    protected += list((ROOT/'docs/experiments').glob('EXP-0060*'))
    protected += list((ROOT/'docs/reviews').glob('EXP-0060*'))
    before = {str(f): sha(f) for f in protected if f.is_file()}
    comparison = read(comparison_path)
    fonts = [ImageFont.truetype(str(args.font), n) for n in (27, 24, 20)]
    items = [prepare(spec, comparison) for spec in SPECS]
    reports = []
    for item in items:
        folder = args.output/item['slug']
        folder.mkdir()
        first = clock(item['rows'][0])
        mapping = [dict(frame_index=r['frame_index'], native_pts=r['native_pts'],
                        time_base=r['time_base'], source_pts=r['pts'],
                        playback_pts=float(clock(r)-first), playback_exact=str(clock(r)-first),
                        tracked_observed_boxes=len(observed_tracks(r))) for r in item['rows']]
        with (folder/'frame_mapping.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=mapping[0].keys())
            writer.writeheader(); writer.writerows(mapping)
        outputs = []
        for overlay in (False, True):
            print(f"Rendering {item['slug']} {'overlay' if overlay else 'original'}", flush=True)
            outputs.append(render(item, folder, overlay, fonts, args.runtime/f"render-preview-{item['slug']}.jpg"))
        receipt = dict(video_id=item['video_id'], source=str(item['source']),
                       source_interval=[item['start'], item['end']], requested_end=item['requested_end'],
                       source_eof=item['eof'], frames=len(mapping), first_actual_pts=item['rows'][0]['pts'],
                       last_actual_pts=item['rows'][-1]['pts'], notice=item['notice'],
                       official_context_per_event=item['events'], inputs_sha256=item['hashes'],
                       frame_mapping_sha256=sha(folder/'frame_mapping.csv'), outputs=outputs,
                       renderer_sha256=sha(__file__), observed_only=True, unassigned_candidates_shown=False,
                       reconstructed_feet=False, geometry_changed=False, inference_calls=0,
                       encoder_threads=2, encoders_run_serially=True)
        write(folder/'receipt.json', receipt)
        reports.append(receipt)
    all_hashes = dict(before)
    for item in items:
        all_hashes.update(item['hashes'])
    unchanged = all(sha(path) == digest for path, digest in all_hashes.items())
    assert unchanged, 'Input/protected file changed'
    index = args.output/'index.html'
    index.write_text(gallery(items))
    report = dict(status='complete', output=str(args.output), index=str(index), scene_count=4,
                  video_count=3, mp4_count=8, source_frames=sum(r['frames'] for r in reports),
                  decoded_output_frames=sum(o['decoded_frames'] for r in reports for o in r['outputs']),
                  all_inputs_unchanged=unchanged, protected_inputs_sha256=all_hashes,
                  every_output_decode_passed=True, every_output_exact_native_clock_passed=True,
                  public_bound_files_unchanged=True, web_pending_check={'requests': []},
                  media_local_only=True, db_writes=0, inference_calls=0, clips=reports,
                  index_sha256=sha(index), renderer_sha256=sha(__file__))
    write(args.runtime/'render-report.json', report)
    write(args.output/'source-receipts.json', report)
    hashes = {str(f.relative_to(args.output)): sha(f) for f in args.output.rglob('*') if f.is_file()}
    (args.output/'SHA256SUMS.txt').write_text(''.join(f'{digest}  {path}\n' for path, digest in sorted(hashes.items())))
    print(json.dumps({k: report[k] for k in ('status', 'index', 'scene_count', 'mp4_count', 'source_frames')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
