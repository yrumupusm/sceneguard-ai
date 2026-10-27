"""Extract local user-review evidence; never change official labels or run models."""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from audit_aihub_intrusion import ROOT, OUT, save

WINDOWS = {'001': [(45, 65)], '007': [(47, 66)],
           '030': [(10, 16), (84, 97)], '031': [(30, 46), (115, 120.2)],
           '006': [(64, 74), (117, 133.67)]}


def main():
    import imageio_ffmpeg
    from PIL import Image, ImageDraw
    manifest = {r['name']: r for r in json.loads((OUT/'manifest.json').read_text())}
    if len(manifest) > 10:
        raise ValueError('Sample budget exceeded')
    labels = sorted((ROOT/'data/TL_침입').rglob('*.json'))
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in labels}
    records = []
    for suffix, windows in WINDOWS.items():
        name = f'E01_{suffix}.mp4'
        clip = manifest[name]
        path = next(p for p in labels if p.stem == Path(name).stem)
        label = json.loads(path.read_text())
        pts = clip['native_pts']
        matched = label['metadata']['frame_count'] == len(pts)
        mapping = []
        for first, last in label['annotations']['event_frame']:
            mapping.append({'frames': [first, last],
                'decoded_index_pts_zero_based': [pts[first], pts[last]],
                'decoded_index_pts_one_based': [pts[first-1], pts[last-1]] if first else None,
                'status': 'count_matched_base_unconfirmed' if matched else 'provisional_frame_count_mismatch'})
        evidence = []
        for start, end in windows:
            indices = [i for i,t in enumerate(pts) if start <= t <= end and i % 30 == 0]
            folder = OUT/'user_review'/f'{Path(name).stem}_{start:g}_{end:g}'
            folder.mkdir(parents=True, exist_ok=True)
            for p in list(folder.glob('*.jpg')):
                p.unlink()
            select = '+'.join(f'eq(n\\,{i})' for i in indices)
            cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-xerror', '-threads', '2',
                   '-i', str(ROOT/'data/TS_침입'/name), '-an', '-vf',
                   f'select={select},showinfo,scale=960:-2', '-fps_mode', 'passthrough',
                   '-y', str(folder/'%03d.jpg')]
            run = subprocess.run(cmd, capture_output=True, text=True, check=True)
            actual = [float(x) for x in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)', run.stderr)]
            images = sorted(folder.glob('[0-9][0-9][0-9].jpg'))
            if len(images) != len(indices) or len(actual) != len(indices) or any(abs(t-pts[i])>0.0001 for t,i in zip(actual,indices)):
                raise ValueError('Evidence PTS mismatch')
            for offset in range(0,len(images),12):
                sheet = Image.new('RGB',(1440,690),'white');draw=ImageDraw.Draw(sheet)
                for j,p in enumerate(images[offset:offset+12]):
                    x,y=(j%4)*360,(j//4)*230
                    with Image.open(p) as im:
                        im.thumbnail((360,202));sheet.paste(im,(x,y+25))
                    draw.text((x+3,y+3),f'{Path(name).stem} {actual[offset+j]:.3f}s',fill='black')
                sheet.save(folder/f'sheet_{offset//12}.jpg')
            evidence.append({'requested_window_seconds':[start,end], 'indices':indices,'pts':actual})
        records.append({'name':name,'video_sha256':clip['sha256'],'label_sha256':before[str(path)],
            'metadata':clip['metadata'],'label_frame_count':label['metadata']['frame_count'],
            'decoded_frame_count':len(pts),'frame_count_matches':matched,
            'max_pts_step':max(b-a for a,b in zip(pts,pts[1:])),
            'official_mapping':mapping,'evidence':evidence})
        print(name, 'count_match',matched,'frames',sum(len(x['pts']) for x in evidence),flush=True)
    if before != {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in labels}:
        raise ValueError('Official label changed')
    save(OUT/'user_review/run.json', {'time_utc':datetime.now(timezone.utc).isoformat(),
        'base_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'official_labels_unchanged':True,'records':records})


if __name__ == '__main__':
    main()
