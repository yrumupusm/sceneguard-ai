"""Phase 1D: public Kaggle v9 metadata and exactly five selected real CCTV clips.
Run: uv run --no-project --with imageio-ffmpeg==0.6.0 --with pillow==12.3.0 python scripts/audit_accident.py
No credentials, full ZIP, synthetic media, models, or upload operations.
"""
import csv
import hashlib
import json
import platform
import re
import subprocess
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/accident_audit'
API = 'https://www.kaggle.com/api/v1/datasets'
VERSION = 9
SELECTED = ['-FQxK6HdxNU_00.mp4', '-Qt5bDJNT84_00.mp4', '-_J5xdxCZZU_00.mp4',
            '04O2SOGSG_U_00.mp4', '651RQwxB3WA_12_00.mp4']
LOG = []


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def fetch(url, path, limit, expected=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Small metadata is refreshed; media is reused only when size matches.
    cached = expected is not None and path.exists() and path.stat().st_size == expected
    if not cached:
        with urllib.request.urlopen(url, timeout=45) as response:
            body = response.read(limit + 1)
            if len(body) > limit:
                raise ValueError('Response exceeds per-file limit')
            if 'text/html' in response.headers.get('Content-Type', ''):
                raise ValueError('HTML response instead of dataset file')
            if expected is not None and len(body) != expected:
                raise ValueError('API size mismatch')
            path.write_bytes(body)
            status = response.status
    else:
        status = None
    LOG.append({'url': url, 'local': str(path.relative_to(OUT)), 'status': status,
                'cached': cached, 'bytes': path.stat().st_size,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    save(OUT / 'request_log.json', LOG)
    return path


def main():
    import imageio_ffmpeg
    from PIL import Image, ImageDraw
    OUT.mkdir(parents=True, exist_ok=True)
    meta = json.loads(fetch(f'{API}/view/picekl/accident', OUT/'dataset.json', 1000000).read_text())
    if meta['currentVersionNumber'] != VERSION:
        raise ValueError('Dataset version changed; review before downloading')
    files, token, seen = {}, '', set()
    for page in range(60):
        query = urllib.parse.urlencode({'pageSize': 200, 'datasetVersionNumber': VERSION, 'pageToken': token})
        data = json.loads(fetch(f'{API}/list/picekl/accident?{query}', OUT/f'listing/{page:02}.json', 2000000).read_text())
        for f in data['datasetFiles']:
            if f['name'] in files:
                raise ValueError('Repeated listing entry')
            files[f['name']] = f
        token = data.get('nextPageToken', '')
        if not token:
            break
        if token in seen:
            raise ValueError('Repeated page token')
        seen.add(token)
    else:
        raise ValueError('Pagination limit reached')
    def download(name, limit):
        url = f'{API}/download/picekl/accident/{urllib.parse.quote(name, safe="")}?datasetVersionNumber={VERSION}'
        return fetch(url, OUT/name, limit, files[name]['totalBytes'])
    rows = list(csv.DictReader(download('metadata-real.csv', 1000000).open()))
    download('annotation_classes.yaml', 10000)
    by_name = {r['path']: r for r in rows}
    media = {n for n in files if n.startswith('real_videos/') and n.endswith('.mp4')}
    if len(by_name) != len(rows) or set(by_name) != media:
        raise ValueError('Real annotation/media mapping is not one-to-one')
    source = defaultdict(list)
    for r in rows:
        # Source candidates only: not original URL or verified event identity.
        source[Path(r['path']).stem[:11]].append(r)
    stats = {
        'file_count': len(files), 'listed_bytes': sum(f['totalBytes'] for f in files.values()),
        'real_mp4': len(media), 'synthetic_mp4': sum(n.startswith('synthetic_videos/') and n.endswith('.mp4') for n in files),
        'metadata_rows': len(rows), 'columns': list(rows[0]),
        'missing_fields': dict(Counter(k for r in rows for k,v in r.items() if not v.strip())),
        'types': dict(Counter(r['type'] for r in rows)),
        'splits': {k:dict(Counter(r[k] for r in rows)) for k in ['split_in_distribution','split_geo_aware']},
        'out_of_range_times': [r['path'] for r in rows if not 0 <= float(r['accident_time']) <= float(r['duration'])],
        'out_of_range_boxes': [r['path'] for r in rows if not (0 <= float(r['x1']) <= float(r['x2']) <= 1 and 0 <= float(r['y1']) <= float(r['y2']) <= 1)],
        'source_candidate_groups': len(source),
        'repeated_source_groups': sum(len(v)>1 for v in source.values()),
        'cross_split_source_candidates': {k:[s for s,v in source.items() if len({r[k] for r in v})>1] for k in ['split_in_distribution','split_geo_aware']},
        'non_media_files': [n for n in files if not n.endswith(('.mp4','.png','.jpg','.jpeg'))],
    }
    save(OUT/'annotation_report.json', stats)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    results = []
    for name in SELECTED:
        path = download('real_videos/'+name, 4000000)
        ann = by_name['real_videos/'+name]
        stream = imageio_ffmpeg.read_frames(str(path), pix_fmt='rgb24', output_params=['-fps_mode', 'passthrough'])
        info = next(stream)
        count = sum(1 for _ in stream)
        check = subprocess.run([ffmpeg,'-v','error','-xerror','-i',str(path),'-f','null','-'],capture_output=True,text=True,check=True)
        folder = OUT/'previews'/path.stem
        folder.mkdir(parents=True,exist_ok=True)
        # Remove only generated previews so reruns cannot mix stale frame counts.
        for old in list(folder.glob('[0-9][0-9][0-9].png')) + list(folder.glob('sheet_*.jpg')):
            old.unlink()
        step = max(1, round(info['fps']/2))
        t = float(ann['accident_time'])
        # Every ~0.5 s, ALL frames within +/-0.6 s of GT, and final frame.
        expr = f'select=not(mod(n\\,{step}))+between(t\\,{max(0,t-.6)}\\,{t+.6})+eq(n\\,{count-1}),showinfo'
        run = subprocess.run([ffmpeg,'-hide_banner','-i',str(path),'-vf',expr,'-fps_mode','vfr','-y',str(folder/'%03d.png')],capture_output=True,text=True,check=True)
        times = [float(t) for t in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)',run.stderr)]
        images = sorted(folder.glob('[0-9][0-9][0-9].png'))
        if len(images)!=len(times) or not count:
            raise ValueError('Frame/PTS extraction failed')
        for start in range(0,len(images),16):
            sheet=Image.new('RGB',(1280,4*210),'white');draw=ImageDraw.Draw(sheet)
            for j,impath in enumerate(images[start:start+16]):
                x,y=(j%4)*320,(j//4)*210
                with Image.open(impath) as im:
                    im.thumbnail((320,180));sheet.paste(im,(x,y+25))
                draw.text((x+3,y+3),f'{times[start+j]:.3f}s (GT {t:.3f})',fill='black')
            sheet.save(folder/f'sheet_{start//16}.jpg')
        results.append({'name':name,'annotation':ann,'bytes':path.stat().st_size,
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'metadata':info,
                        'decoded_frames':count,'decode_errors':check.stderr,'preview_pts':times,
                        'gt_box_area_fraction':(float(ann['x2'])-float(ann['x1']))*(float(ann['y2'])-float(ann['y1']))})
        save(OUT/'manifest.json',results)
        print(name,count,'frames',info['size'],info['fps'],'fps',flush=True)
    save(OUT/'run.json', {'time_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
          'platform':platform.platform(),'base_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'dataset_version':VERSION,
          'ffmpeg':subprocess.check_output([ffmpeg,'-version'],text=True).splitlines()[0]})
    print('Completed five-clip audit; raw files remain under ignored data/.')


def details():
    """Recheck native PTS and make local enlarged GT-region contact sheets."""
    import imageio_ffmpeg
    from PIL import Image, ImageDraw
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    manifest = json.loads((OUT/'manifest.json').read_text())
    for r in manifest:
        run = subprocess.run([ffmpeg, '-hide_banner', '-i', str(OUT/'real_videos'/r['name']),
            '-vf', 'showinfo', '-fps_mode', 'passthrough', '-f', 'null', '-'],
            capture_output=True, text=True, check=True)
        pts = [float(t) for t in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)', run.stderr)]
        if len(pts) != r['decoded_frames']:
            raise ValueError('Independent native frame count mismatch')
        ann = r['annotation']; t = float(ann['accident_time']); index = int(ann['accident_frame'])
        r['native_pts'] = pts
        r['gt_index_pts'] = pts[index] if 0 <= index < len(pts) else None
        r['nearest_gt_index'] = min(range(len(pts)), key=lambda i:abs(pts[i]-t))
        folder = OUT/'previews'/Path(r['name']).stem
        candidates = [i for i,p in enumerate(r['preview_pts']) if abs(p-t)<=.65]
        if len(candidates)>12:
            candidates = [candidates[round(i*(len(candidates)-1)/11)] for i in range(12)]
        sheet=Image.new('RGB',(1200,3*230),'white');draw=ImageDraw.Draw(sheet)
        w,h=r['metadata']['size']
        # Include surroundings; GT box is a region, not a tracked object box.
        box=(max(0,int((float(ann['x1'])-.10)*w)),max(0,int((float(ann['y1'])-.10)*h)),
             min(w,int((float(ann['x2'])+.10)*w)),min(h,int((float(ann['y2'])+.10)*h)))
        for j,i in enumerate(candidates):
            with Image.open(folder/f'{i+1:03}.png') as im:
                crop=im.crop(box);crop.thumbnail((300,200))
                # Upscale small source crops only for viewing, not new detail.
                scale=min(300/crop.width,200/crop.height)
                crop=crop.resize((round(crop.width*scale),round(crop.height*scale)))
                x,y=(j%4)*300,(j//4)*230;sheet.paste(crop,(x,y+25))
                draw.text((x+3,y+3),f"PTS {r['preview_pts'][i]:.3f}s",fill='black')
        sheet.save(folder/'gt_region.jpg')
    save(OUT/'manifest.json',manifest)
    save(OUT/'details_run.json', {'time_utc':datetime.now(timezone.utc).isoformat(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'base_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
    print('Verified native PTS counts and generated five GT-region sheets.')


if __name__=='__main__':
    import sys
    if '--details-only' not in sys.argv:
        main()
    details()
