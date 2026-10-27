"""Local-only AI-Hub 71850 audit. No download, credentials, models or uploads.
Run with uv --with imageio-ffmpeg==0.6.0 --with pillow==12.3.0 (see report).
A maximum of ten explicit source videos may be inspected per invocation.
"""
import argparse
import hashlib
import json
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/aihub_intrusion_audit'
DEFAULT_IDS = ['001','004','007','013','021','030','039','045']


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')


def main():
    import imageio_ffmpeg
    from PIL import Image, ImageDraw
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'data/TS_침입')
    parser.add_argument('--ids',nargs='+',default=DEFAULT_IDS)
    args=parser.parse_args()
    if not 1<=len(set(args.ids))<=10 or any(not re.fullmatch(r'\d{3}',s) for s in args.ids):
        parser.error('Select 1–10 unique three-digit IDs')
    files=sorted(args.source.glob('*.mp4'))
    save(OUT/'inventory.json',{'source_files':[{'name':p.name,'bytes':p.stat().st_size} for p in files],
        'label_candidates':[str(p.relative_to(ROOT/'data')) for p in (ROOT/'data').rglob('E01_*.json')]})
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    results=[]
    for suffix in args.ids:
        path=args.source/f'E01_{suffix}.mp4'
        stream=imageio_ffmpeg.read_frames(str(path),pix_fmt='rgb24',output_params=['-fps_mode','passthrough'])
        info=next(stream);stream.close()
        folder=OUT/'previews'/path.stem;folder.mkdir(parents=True,exist_ok=True)
        for old in list(folder.glob('[0-9][0-9][0-9][0-9].jpg'))+list(folder.glob('sheet_*.jpg')):
            old.unlink()
        step=max(1,round(info['fps']*5))
        # Log ALL native PTS before selecting preview frames. Decode full video.
        cmd=[ffmpeg,'-hide_banner','-xerror','-threads','2','-i',str(path),'-an',
             '-vf',f'showinfo,select=not(mod(n\\,{step})),scale=480:-2',
             '-fps_mode','passthrough','-y',str(folder/'%04d.jpg')]
        result=subprocess.run(cmd,capture_output=True,text=True,check=True)
        pts=[float(t) for t in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)',result.stderr)]
        images=sorted(folder.glob('[0-9][0-9][0-9][0-9].jpg'));times=pts[::step]
        if len(images)!=len(times) or not pts:
            raise ValueError('Native PTS/preview count mismatch')
        for start in range(0,len(images),16):
            sheet=Image.new('RGB',(1280,4*210),'white');draw=ImageDraw.Draw(sheet)
            for j,p in enumerate(images[start:start+16]):
                x,y=(j%4)*320,(j//4)*210
                with Image.open(p) as im:
                    im.thumbnail((320,180));sheet.paste(im,(x,y+25))
                draw.text((x+4,y+4),f'{path.stem} PTS {times[start+j]:.3f}s',fill='black')
            sheet.save(folder/f'sheet_{start//16}.jpg')
        digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256(path.read_bytes()).hexdigest()
        results.append({'name':path.name,'bytes':path.stat().st_size,'sha256':digest,
            'metadata':info,'decoded_frames':len(pts),'native_pts':pts,'preview_pts':times,
            'decode_returncode':result.returncode,'official_json_matched':False})
        save(OUT/'manifest.json',results)
        print(path.name,len(pts),'frames',info['duration'],'s',flush=True)
    save(OUT/'run.json',{'time_utc':datetime.now(timezone.utc).isoformat(),
        'python':platform.python_version(),'platform':platform.platform(),
        'base_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'command_args':vars(args)|{'source':str(args.source)},
        'ffmpeg':subprocess.check_output([ffmpeg,'-version'],text=True).splitlines()[0]})


def access():
    """Public metadata and read-only permission check; never request data files."""
    import urllib.request
    import urllib.parse
    import urllib.error
    base='https://www.aihub.or.kr'
    checks=[]
    urls=[('dataset',base+'/aihubdata/data/view.do?dataSetSn=71850',None),
          ('policy',base+'/intrcn/guid/usagepolicy.do?currMenu=151&topMenu=105',None),
          ('files',base+'/aihubdata/data/aJaxS3FileList.do',{'dataSetSn':'71850','dataPckageSn':''}),
          ('permission',base+'/apishell/aJaxCheckApiDwld.do',{'dataSetSn':'71850','dataPckageSn':''})]
    for name,url,params in urls:
        request=urllib.request.Request(url,data=urllib.parse.urlencode(params).encode() if params else None)
        entry={'name':name,'url':url,'time_utc':datetime.now(timezone.utc).isoformat()}
        try:
            with urllib.request.urlopen(request,timeout=30) as response:
                raw=response.read(2000001)
                if len(raw)>2000000:
                    raise ValueError('Metadata exceeds 2 MB limit')
                entry['http_status']=response.status
        except urllib.error.HTTPError as error:
            entry['http_status']=error.code;raw=error.read(4096)
        except (urllib.error.URLError,TimeoutError,ValueError) as error:
            entry['error']=str(error);raw=b''
        dest=OUT/'access'/(name+('.json' if params else '.html'))
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        entry.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        checks.append(entry)
    save(OUT/'access/report.json',checks)
    print('Public access probes recorded; no authentication or data download.')


def details():
    """Two observation-driven windows; not official event ground truth."""
    import imageio_ffmpeg
    from PIL import Image,ImageDraw
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    windows={'E01_004':(28,45),'E01_021':(63,81)}
    records=[]
    for name,(start,end) in windows.items():
        folder=OUT/'details'/name;folder.mkdir(parents=True,exist_ok=True)
        cmd=[ffmpeg,'-hide_banner','-xerror','-threads','2','-i',str(ROOT/'data/TS_침입'/f'{name}.mp4'),
            '-an','-vf',f'select=between(t\\,{start}\\,{end})*not(mod(n\\,30)),showinfo,scale=960:-2',
            '-fps_mode','passthrough','-y',str(folder/'%03d.jpg')]
        run=subprocess.run(cmd,capture_output=True,text=True,check=True)
        pts=[float(t) for t in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)',run.stderr)]
        paths=sorted(folder.glob('[0-9][0-9][0-9].jpg'))
        if len(paths)!=len(pts):raise ValueError('Detail PTS mismatch')
        for start_i in range(0,len(paths),12):
            sheet=Image.new('RGB',(1440,3*295),'white');draw=ImageDraw.Draw(sheet)
            for j,path in enumerate(paths[start_i:start_i+12]):
                with Image.open(path) as im:
                    im.thumbnail((360,270));x,y=(j%4)*360,(j//4)*295;sheet.paste(im,(x,y+25))
                    draw.text((x+4,y+4),f'{name} {pts[start_i+j]:.3f}s',fill='black')
            sheet.save(folder/f'sheet_{start_i//12}.jpg')
        records.append({'name':name,'window':[start,end],'pts':pts})
    save(OUT/'details.json',records)
    print('Detail windows generated; no new source videos inspected.')


def examples():
    """Map PUBLIC PAGE examples, never substitute them for downloaded GT JSON."""
    import html
    text=html.unescape(re.sub('<[^>]+>',' ',(OUT/'access/dataset.html').read_text())).replace(chr(160),' ')
    manifest={r['name']:r for r in json.loads((OUT/'manifest.json').read_text())}
    result=[]
    for name in ['E01_021.mp4','E01_039.mp4']:
        start=text.index('"file_name": "'+name+'"')
        section=text[start:]
        frame_count=int(re.search(r'"frame_count":\s*(\d+)',section).group(1))
        value=section.index('[',section.index('"event_frame"'))
        frames=json.JSONDecoder().raw_decode(section[value:])[0]
        r=manifest[name];pts=r['native_pts']
        mapped=[]
        for first,last in frames:
            if not 0<=first<=last<len(pts):raise ValueError('Example frames outside local video')
            mapped.append({'example_frames':[first,last], 'zero_based_pts':[pts[first],pts[last]],
                'one_based_pts':[pts[first-1],pts[last-1]] if first>0 else None})
        result.append({'name':name,'source':'public_page_example_not_downloaded_ground_truth',
            'page_frame_count':frame_count,'local_frame_count':len(pts),
            'page_ranges_sorted':frames==sorted(frames),'mapping':mapped})
    save(OUT/'page_example_mapping.json',result)
    save(OUT/'supplement_run.json',{'time_utc':datetime.now(timezone.utc).isoformat(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    import sys
    if '--access-only' in sys.argv:
        access()
    elif '--examples-only' in sys.argv:
        examples()
    elif '--details-only' in sys.argv:
        details()
    else:
        main()
