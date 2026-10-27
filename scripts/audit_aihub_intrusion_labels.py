"""Audit local AI-Hub labels and extract evidence for previously decoded clips.
No download, models, or uploads. Requires existing native PTS manifest.
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from audit_aihub_intrusion import ROOT, OUT, save


def main():
    import imageio_ffmpeg
    from PIL import Image, ImageDraw
    labels={}
    records=[]
    for path in sorted((ROOT/'data/TL_침입').rglob('*.json')):
        row=json.loads(path.read_text());meta=row['metadata'];ann=row['annotations'];name=meta['file_name']
        if name in labels:raise ValueError('Duplicate video key')
        labels[name]=row
        ranges=ann['event_frame'];count=meta['frame_count']
        if any(not (isinstance(a,int) and isinstance(b,int) and 0<=a<=b<count) for a,b in ranges):
            raise ValueError('Invalid event frame bounds')
        ordered=sorted(ranges)
        records.append({'name':name,'label_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'range_count':len(ranges),'sorted':ranges==ordered,
            'overlap':any(b>=c for (a,b),(c,d) in zip(ordered,ordered[1:])),
            'event_length':ann['event_length'],'frame_span_sum':sum(b-a for a,b in ranges),
            'camera_field':meta['cctv_distribution']})
    videos={p.name for p in (ROOT/'data/TS_침입').glob('*.mp4')}
    if set(labels)!=videos:raise ValueError('Label/video mapping mismatch')
    manifest=json.loads((OUT/'manifest.json').read_text())
    if len(manifest)>10:raise ValueError('Sample limit exceeded')
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();sample=[]
    for clip in manifest:
        name=clip['name'];row=labels[name];meta=row['metadata'];ann=row['annotations'];pts=clip['native_pts']
        if meta['frame_count']!=len(pts) or [meta['width'],meta['height']]!=clip['metadata']['size']:
            raise ValueError('Label/media metadata mismatch')
        mappings=[];indices=set()
        for first,last in ann['event_frame']:
            # Exact boundary, quarter points, +/-1 s contexts. Not continuous review.
            indices.update([max(0,first-30),min(len(pts)-1,last+30)])
            indices.update(round(first+(last-first)*i/4) for i in range(5))
            mappings.append({'frames':[first,last],'zero_based_pts':[pts[first],pts[last]],
                'one_based_pts':[pts[max(0,first-1)],pts[max(0,last-1)]]})
        ordered=sorted(indices)
        folder=OUT/'label_previews'/Path(name).stem;folder.mkdir(parents=True,exist_ok=True)
        for path in list(folder.glob('[0-9][0-9][0-9].jpg'))+list(folder.glob('sheet_*.jpg')):path.unlink()
        select='+'.join(f'eq(n\\,{i})' for i in ordered)
        cmd=[ffmpeg,'-hide_banner','-xerror','-threads','2','-i',str(ROOT/'data/TS_침입'/name),'-an',
            '-vf',f'select={select},showinfo,scale=640:-2','-fps_mode','passthrough','-y',str(folder/'%03d.jpg')]
        run=subprocess.run(cmd,capture_output=True,text=True,check=True)
        actual=[float(t) for t in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)',run.stderr)]
        paths=sorted(folder.glob('[0-9][0-9][0-9].jpg'))
        if len(paths)!=len(ordered) or len(actual)!=len(ordered) or any(abs(p-pts[i])>.0001 for i,p in zip(ordered,actual)):
            raise ValueError('Selected frame PTS mismatch')
        for start in range(0,len(paths),12):
            sheet=Image.new('RGB',(1440,3*230),'white');draw=ImageDraw.Draw(sheet)
            for j,path in enumerate(paths[start:start+12]):
                x,y=(j%4)*360,(j//4)*230
                with Image.open(path) as im:
                    im.thumbnail((360,202));sheet.paste(im,(x,y+25))
                draw.text((x+3,y+3),f'{Path(name).stem} PTS {actual[start+j]:.3f}s',fill='black')
            sheet.save(folder/f'sheet_{start//12}.jpg')
        span=sum(x['zero_based_pts'][1]-x['zero_based_pts'][0] for x in mappings)
        sample.append({'name':name,'annotation':ann,'mapping':mappings,'span_sum_seconds':span,
            'event_length_minus_span':ann['event_length']-span,'preview_indices':ordered,'preview_pts':actual})
        save(OUT/'label_sample_audit.json',sample)
        print(name,'mapped',len(mappings),'ranges',len(paths),'evidence frames',flush=True)
    save(OUT/'label_audit.json',{'time_utc':datetime.now(timezone.utc).isoformat(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'base_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'labels':len(labels),'videos':len(videos),'events':sum(r['range_count'] for r in records),
        'classes':dict(Counter(r['annotations']['event_class'] for r in labels.values())),
        'unsorted':[r['name'] for r in records if not r['sorted']],
        'overlap':[r['name'] for r in records if r['overlap']],
        'camera_values':len({r['camera_field'] for r in records}),
        'camera_equals_stem':sum(r['camera_field']==Path(r['name']).stem for r in records),
        'records':records,'sample_count':len(sample)})


if __name__=='__main__':main()
