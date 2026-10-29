# SPDX-License-Identifier: AGPL-3.0-only
"""CPU native-PTS selection and immutable original RGB binding, before inference."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time
from batch02_cv.prepare import sha
ROOT = Path(__file__).resolve().parents[1]
WINDOWS = [('climb030','E01_030',88,94), ('climb007','E01_007',62.5,67.5),
           ('approach007','E01_007',47.5,52.5), ('approach030','E01_030',50,55),
           ('rope004','E01_004',60,65)]
DIAGNOSTICS = ('030_084','030_090','030_094','007_052','007_064','007_066',
               '031_032','031_040','006_119','006_125','006_131')


def eligible(pts, start, end, previous):
    return Fraction(str(start)) <= pts < Fraction(str(end)) and (previous is None or pts-previous >= Fraction(1,10))


def prepare():
    import av
    import numpy as np
    old = json.loads((ROOT/'configs/batch0002_cv_manifest.json').read_text())
    if tuple(r['frame_id'] for r in old['frames']) != DIAGNOSTICS:
        raise ValueError('EXP19 exact diagnostic set changed')
    destination=ROOT/'outputs/batch0003/inputs';destination.mkdir(parents=True,exist_ok=True)
    frames=[];windows=[];decode={};pins={**old['historical_pins']}
    pins['configs/batch0002_cv_manifest.json']=sha(ROOT/'configs/batch0002_cv_manifest.json')
    pins['configs/mvp0001_cameras.json']=sha(ROOT/'configs/mvp0001_cameras.json')
    for source in sorted({r['source_id'] for r in old['frames']}|{w[1] for w in WINDOWS}):
        source_path=ROOT/'data/TS_침입'/(source+'.mp4');source_sha=sha(source_path)
        diagnostics=[dict(r) for r in old['frames'] if r['source_id']==source]
        if any(r['source_sha256']!=source_sha for r in diagnostics):raise ValueError('historical source changed')
        intervals=[w for w in WINDOWS if w[1]==source];previous={w[0]:None for w in intervals};members={w[0]:[] for w in intervals}
        last=max([float(r['pts_seconds']) for r in diagnostics]+[w[3] for w in intervals]);found=set();n=0;t0=time.perf_counter()
        with av.open(str(source_path)) as container:
            for f in container.decode(video=0):
                if f.pts is None:raise ValueError('missing native PTS')
                pts=Fraction(f.pts)*f.time_base;n+=1
                if pts>Fraction(str(last))+1:break
                matches=[r for r in diagnostics if r['native_pts']==f.pts and r['time_base']==str(f.time_base)]
                aliases=[w[0] for w in intervals if eligible(pts,w[2],w[3],previous[w[0]])]
                if not matches and not aliases:continue
                if len(matches)>1:raise ValueError('duplicate diagnostic PTS')
                frame_id=matches[0]['frame_id'] if matches else source[4:]+'_pts'+str(f.pts)
                rgb=f.to_ndarray(format='rgb24');path=destination/(frame_id+'.npy')
                if path.exists():
                    if not np.array_equal(np.load(path,allow_pickle=False),rgb):raise ValueError('existing original differs')
                else:np.save(path,rgb,allow_pickle=False)
                item=dict(frame_id=frame_id,source_id=source,source_path=str(source_path.relative_to(ROOT)),source_sha256=source_sha,
                    native_pts=f.pts,time_base=str(f.time_base),pts_seconds=float(pts),source_size=[f.width,f.height],
                    rgb_path=str(path.relative_to(ROOT)),rgb_sha256=sha(path),rgb_bytes_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),
                    rgb_shape=list(rgb.shape),windows=aliases,diagnostic=bool(matches))
                if matches:
                    prior=matches[0];found.add(prior['frame_id'])
                    if item['rgb_bytes_sha256']!=prior['rgb_bytes_sha256']:raise ValueError('EXP19 decoded RGB mismatch')
                    item.update(requested_seconds=prior['requested_seconds'],cache_path=prior['cache_path'],fcos_person_count=prior['fcos_person_count'])
                frames.append(item)
                for alias in aliases:previous[alias]=pts;members[alias].append(frame_id)
        if found!={r['frame_id'] for r in diagnostics}:raise ValueError('native diagnostic missing')
        decode[source]=dict(decoded_frames=n,wall_seconds=time.perf_counter()-t0,includes_decode_rgb_save_and_hash=True)
        for alias,_,start,end in intervals:windows.append(dict(alias=alias,source_id=source,start=start,end=end,frames=members[alias]))
    if not 11<=len(frames)<=300 or len({(r['source_id'],r['native_pts'],r['time_base']) for r in frames})!=len(frames):raise ValueError('unique frame bound failed')
    frames.sort(key=lambda r:(r['source_id'],r['pts_seconds']))
    for r in frames:r['windows'].sort(key=lambda a:[w[0] for w in WINDOWS].index(a))
    value=dict(frames=frames,windows=sorted(windows,key=lambda w:[x[0] for x in WINDOWS].index(w['alias'])),historical_pins=pins,decode=decode,
        sampling='Greedy native PTS in [start,end), first observed >=start, next >=previous+1/10s; no nearest future target, no interpolation; exact EXP19 frames union/deduplicated')
    target=ROOT/'runtime/BATCH-0003/frame-binding.json'
    if target.exists():raise ValueError('binding already frozen')
    target.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n');print('Frozen unique frames',len(frames),'windows',[len(w['frames']) for w in value['windows']])

if __name__=='__main__':prepare()
