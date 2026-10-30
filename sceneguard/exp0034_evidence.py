"""Local native-frame EXP-0034 rendering and full-target crop provenance; no inference."""
import argparse
from contextlib import ExitStack
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .approach_disappearance import center
from .exp0034_application import fresh_file, validated_inputs
from .mvp_review_evidence import _VideoWriter, _validate_video
from .run_mvp_review import load_json, input_spec
from .run_tracklet_linking import decode_native, sha256, write_json


@lru_cache(maxsize=12)
def font(size=23):
    for path in ('/mnt/c/Windows/Fonts/malgun.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).is_file():
            return ImageFont.truetype(path,size)
    return ImageFont.load_default()


def fresh_dir(path):
    path=Path(path)
    if (path.exists() or path.is_symlink() or any(p.is_symlink() for p in path.parents)
            or not path.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Fresh non-symlink local directory required')
    path.mkdir(parents=True)
    return path


def bound_result(result_path):
    result=load_json(result_path)
    key=result['video_id'][-3:]
    spec,data,scene=validated_inputs(key,result['source_paths']['scene'],result['input_sha256']['scene'])
    if any(data['hashes'][k]!=result['input_sha256'][k] for k in data['hashes']):
        raise ValueError('Result source binding differs')
    return result,spec,data,scene


def crop_bounds(bbox,size):
    w,h=size
    x1,y1,x2,y2=bbox
    bounds=[max(0,math.floor(x1*w)),max(0,math.floor(y1*h)),min(w,math.ceil(x2*w)),min(h,math.ceil(y2*h))]
    if bounds[2]-bounds[0]<16 or bounds[3]-bounds[1]<16:
        raise ValueError('Full native crop too small for existing comparison adapter')
    return bounds


def measured_row(result,segment,frame_index):
    found=[s for s in result['segments'] if s['id']==segment]
    if len(found)!=1:
        raise ValueError('Unknown segment')
    rows=[r for r in found[0]['rows'] if r['frame_index']==frame_index]
    if len(rows)!=1:
        raise ValueError('Requested frame is not an actual segment measurement')
    return found[0],rows[0]


def draw_box(draw,bbox,size,color,label,dashed=False):
    box=tuple(v*size[i%2] for i,v in enumerate(bbox))
    if dashed:
        x1,y1,x2,y2=box
        for a,b in (((x1,y1),(x2,y1)),((x2,y1),(x2,y2)),((x2,y2),(x1,y2)),((x1,y2),(x1,y1))):
            length=math.dist(a,b)
            for d in range(0,int(length),15):
                t=d/max(length,1);u=min(d+8,length)/max(length,1)
                draw.line((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u),fill=color,width=2)
    else:
        draw.rectangle(box,outline=color,width=3)
    draw.text((box[0],max(0,box[1]-27)),label,font=font(),fill=color,stroke_width=2,stroke_fill='black')


def annotate(source,frame,result,scene,index,status=False):
    image=source.copy();draw=ImageDraw.Draw(image);w,h=image.size
    for name,poly in scene['zones'].items():
        draw.line([(x*w,y*h) for x,y in poly+poly[:1]],fill='#77aaff' if name=='outside' else '#aa77ff',width=2)
    draw.line([(x*w,y*h) for x,y in scene['line']],fill='yellow',width=3)
    draw.line([(x*w,y*h) for x,y in scene['approach_polygon']+scene['approach_polygon'][:1]],fill='#999999',width=2)
    if status:
        for occ in scene.get('occlusions',[]):
            poly=occ['polygon'];draw.line([(x*w,y*h) for x,y in poly+poly[:1]],fill='#ff55cc',width=3)
    for row in frame['detections']:
        if row.get('observed') and row.get('confirmed',True):
            draw_box(draw,row['bbox'],(w,h),'#00ff88',f'raw {row["track_id"]} actual')
    for row in frame.get('states',[]):
        if not row.get('observed'):
            box=row.get('filter_bbox',row.get('bbox'))
            if box:
                draw_box(draw,box,(w,h),'#ff9933',f'raw {row["track_id"]} predicted',True)
    if status:
        for segment in result['segments']:
            approach=segment.get('approach_pts')
            if approach is not None and approach<=frame['pts']<=approach+2:
                entry=next(r for r in segment['rows'] if r['pts']==approach)
                p=center(entry,(w,h),.65)
                draw.ellipse((p[0]-12,p[1]-12,p[0]+12,p[1]+12),outline='yellow',width=4)
                draw.text((p[0]+15,p[1]),f'접근 관측 raw{segment["raw_id"]} {approach:.3f}',font=font(),fill='yellow',stroke_width=2,stroke_fill='black')
            rows=[r for r in segment['rows'] if r['frame_index']<=index and frame['pts']-r['pts']<=1.0+1e-9]
            if len(rows)>1:
                draw.line([center(r,(w,h)) for r in rows],fill='#00ffff',width=3)
        for loss in result['losses']:
            if not loss['last_pts']<=frame['pts']<=loss['last_pts']+1.5:
                continue
            mv=loss['motion'];p=mv['origin_pixels'];v=mv['velocity_pixels_per_second']
            if mv['reliable']:
                theta=math.atan2(v[1],v[0]);radius=110
                arc=[(p[0]+radius*math.cos(theta+t*math.pi/180),p[1]+radius*math.sin(theta+t*math.pi/180)) for t in range(-90,91,5)]
                draw.line([tuple(p)]+arc+[tuple(p)],fill='#66ccff',width=2)
                q=(p[0]+radius*math.cos(theta),p[1]+radius*math.sin(theta))
                draw.line((tuple(p),q),fill='#00ffff',width=6)
                for a in (-.4,.4):
                    draw.line((q,(q[0]-20*math.cos(theta+a),q[1]-20*math.sin(theta+a))),fill='#00ffff',width=4)
                draw.text(tuple(p),'+/-90 visual only',font=font(),fill='#66ccff')
            draw.ellipse((p[0]-8,p[1]-8,p[0]+8,p[1]+8),outline='#ff55cc',width=3)
        # Final outcomes are never projected backward onto earlier frames.
        active=[e for e in result['events'] if e['decision_time_pts'] is not None and e['decision_time_pts']<=frame['pts']+1e-9]
        lines=[f'{e["status"]} raw{e["raw_id"]} obs {e["source_observed_pts"]:.3f} decision {e["decision_time_pts"]:.3f}' for e in active[-5:]]
        recent_losses=[l for l in result['losses'] if l['decision_time_pts'] is not None
                       and l['decision_time_pts']<=frame['pts']<=l['decision_time_pts']+2]
        lines.extend(f'{l["status"]} raw{l["raw_id"]} last {l["last_pts"]:.3f} decision {l["decision_time_pts"]:.3f}' for l in recent_losses)
        if not lines:lines=['판단 불가']
        for i,line in enumerate(lines):
            draw.text((20,25+33*i),line,font=font(25),fill='yellow',stroke_width=2,stroke_fill='black')
    return image


def footer(image,frame,available,label):
    """Native source remains full-field; timing occupies a separate lower strip."""
    canvas=Image.new('RGB',(image.width,image.height+72),'#101722')
    canvas.paste(image,(0,0));draw=ImageDraw.Draw(canvas)
    draw.text((12,image.height+3),f'{label} | SOURCE PTS {frame["pts"]:.6f} | native {frame["native_pts"]} * {frame["time_base"]}',font=font(22),fill='white')
    draw.text((12,image.height+36),f'OFFLINE available_after source PTS {available:.6f}; decision PTS is logical evidence timing',font=font(21),fill='white')
    return canvas


def render(result_path,output):
    result,spec,data,scene=bound_result(result_path)
    out=fresh_dir(output);cached=data['cached'];w,h=scene['source_size']
    dt=Fraction(cached[1]['native_pts']-cached[0]['native_pts'])*Fraction(cached[0]['time_base'])
    frame_map=[];count=0
    with ExitStack() as stack:
        writers={}
        for name,size in [('original',(w,h+72)),('observations',(w,h+72)),('direction_loss_status',(w,h+72)),('comparison',(1920,960))]:
            writer=_VideoWriter(out/f'{name}.mp4',size,dt);writers[name]=writer;stack.callback(writer.close)
        for index,bgr in decode_native(spec['video'],cached):
            rgb=bgr[:,:,::-1].copy();source=Image.fromarray(rgb)
            observed=annotate(source,data['tracked'][index],result,scene,index)
            status=annotate(source,data['tracked'][index],result,scene,index,True)
            comparison=Image.new('RGB',(1920,960),'#101722');draw=ImageDraw.Draw(comparison)
            pts=cached[index]['pts']
            for col,(label,img) in enumerate([('원본',source),('관측: 초록 실제 / 주황 예측',observed),('방향 · 소실 · 상태',status)]):
                comparison.paste(img.resize((640,360)),(col*640,70))
                draw.text((col*640+12,20),label,font=font(25),fill='white')
            lines=[f'{result["video_id"]} source PTS {pts:.6f} | native {cached[index]["native_pts"]} * {cached[index]["time_base"]}',
                f'OFFLINE available_after source PTS {result["available_after_pts"]:.6f}; logical decision PTS shown separately',
                '방향과 +/-90 표시는 보조 정보입니다. 실제 관측만 방향 근거로 사용합니다.',
                '침입 확인은 자동 출력하지 않습니다. 기존 경보는 별도로 보존합니다.']
            alerts=[a for a in result['existing_alerts'] if a['emitted_at_pts']<=pts]
            lines.append('기존 침입 의심(구 규칙): '+(', '.join(f'raw{a["track_id"]}@{a["emitted_at_pts"]:.3f}' for a in alerts) or '0'))
            approaches=[s for s in result['segments'] if s['approach_pts'] is not None and s['approach_pts']<=pts]
            lines.extend(f'접근 관측 {s["id"]} raw{s["raw_id"]} | source/decision PTS {s["approach_pts"]:.3f}' for s in approaches[-2:])
            events=[e for e in result['events'] if e['decision_time_pts'] is not None and e['decision_time_pts']<=pts+1e-9]
            lines.extend(f'{e["status"]} {e["segment"]} raw{e["raw_id"]} | {e["reason"]} | observation {e["source_observed_pts"]:.3f}, decision {e["decision_time_pts"]:.3f}' for e in events[-3:])
            losses=[l for l in result['losses'] if l['decision_time_pts'] is not None and l['decision_time_pts']<=pts]
            lines.extend(f'{l["status"]} {l["segment"]} raw{l["raw_id"]} | {l["reason"]} | last {l["last_pts"]:.3f}, decision {l["decision_time_pts"]:.3f}' for l in losses[-3:])
            for i,line in enumerate(lines):draw.text((18,450+i*38),line,font=font(22),fill='white')
            for name,img,label in [('original',source,'원본'),('observations',observed,'관측'),('direction_loss_status',status,'방향 · 소실 · 상태')]:
                writers[name].write(footer(img,cached[index],result['available_after_pts'],label))
            writers['comparison'].write(comparison)
            f=cached[index]
            frame_map.append(dict(frame_index=index,pts=f['pts'],native_pts=f['native_pts'],time_base=f['time_base'],
                                  native_rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),playback_seconds=float(index*dt)))
            count+=1
    if count!=len(cached):raise ValueError('Missing native frames')
    videos={n:dict(path=str(out/f'{n}.mp4'),**_validate_video(out/f'{n}.mp4',count,dt)) for n in writers}
    write_json(out/'source-frames.json',frame_map)
    receipt=dict(result_sha256=sha256(result_path),frames=count,videos=videos,source_native_pts_verified=True,
        source_window=result['source_window'],available_after_pts=result['available_after_pts'],
        full_original_interval=True,predictions='orange dashed; excluded from all direction evidence',
        human_visual_review='pending_root',detector_calls=0,tracker_calls=0,encoder_calls=0)
    write_json(out/'render-receipt.json',receipt)
    return receipt


def segment_boards(result_path,output):
    """Inspection only: first/middle/last observed full crops, never model input."""
    result,spec,data,scene=bound_result(result_path)
    target=fresh_dir(output);requests={};panels={};mapping=[]
    for segment in result['segments']:
        rows=segment['rows']
        chosen=[rows[i] for i in sorted({0,len(rows)//2,len(rows)-1})]
        panel=Image.new('RGB',(1200,650),'#101722');draw=ImageDraw.Draw(panel)
        loss=next(l for l in result['losses'] if l['segment']==segment['id'])
        draw.text((15,10),f'{result["video_id"]}:{segment["id"]} raw{segment["raw_id"]} | {loss["status"]}',font=font(24),fill='white')
        draw.text((15,50),loss['reason'],font=font(19),fill='white')
        panels[segment['id']]=panel
        for col,row in enumerate(chosen):
            requests.setdefault(row['frame_index'],[]).append((segment,col,row))
    for index,bgr in decode_native(spec['video'],data['cached']):
        for segment,col,row in requests.get(index,[]):
            rgb=bgr[:,:,::-1].copy();image=Image.fromarray(rgb);w,h=image.size
            box=[math.floor(row['bbox'][0]*w),math.floor(row['bbox'][1]*h),math.ceil(row['bbox'][2]*w),math.ceil(row['bbox'][3]*h)]
            crop=image.crop(box);crop.thumbnail((380,400))
            panel=panels[segment['id']];panel.paste(crop,(col*400+10,140));draw=ImageDraw.Draw(panel)
            draw.text((col*400+10,100),f'frame {index} | PTS {row["pts"]:.3f}',font=font(19),fill='yellow')
            context=image.copy();d=ImageDraw.Draw(context);d.rectangle(box,outline='yellow',width=5)
            context.thumbnail((190,107));panel.paste(context,(col*400+200,540))
            mapping.append(dict(segment=segment['id'],raw_id=segment['raw_id'],frame_index=index,
                pts=row['pts'],native_pts=row['native_pts'],time_base=row['time_base'],cache_index=row['cache_index'],
                bbox=row['bbox'],crop_bounds=box,native_rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest()))
    for sid,panel in panels.items():panel.save(target/f'{sid}.jpg')
    write_json(target/'inspection-map.json',dict(result_sha256=sha256(result_path),rows=mapping,
        selection='first/middle/last inspection snapshots only; root selects final model inputs separately'))
    return dict(path=str(target),segments=len(panels),snapshots=len(mapping))


def prepare_crops(selection_path,result_paths,output,manifest_path):
    """Root-selected actual rows only. Selection/GT stays separate from model manifest."""
    selection=load_json(selection_path)
    if not 0<len(selection['pairs'])<=6:raise ValueError('Use 1-6 actual selected pairs')
    if len({p['pair_id'] for p in selection['pairs']})!=len(selection['pairs']):raise ValueError('Duplicate selected pair IDs')
    target=fresh_dir(output);manifest_path=fresh_file(manifest_path,'runtime')
    bundles={}
    for path in result_paths:
        result,spec,data,scene=bound_result(path);bundles[result['video_id']]=(result,spec,data)
    manifest=dict(schema_version=1,experiment_id='EXP-0034',run_id='run_3d23462a014a',sources=[],pairs=[],candidate_pairs=[])
    requests={};plans=[];crop_map=[]
    for source_id,(result,spec,data) in bundles.items():
        manifest['sources'].append(dict(source_id=source_id,path=spec['video'],source_sha256=data['hashes']['video'],
            frames_path=spec['tracks'],frames_sha256=data['hashes']['tracks']))
        for p in result['pairs']:
            manifest['candidate_pairs'].append(dict(pair_id=source_id+':'+p['pair_id'],before=source_id+':'+p['before'],after=source_id+':'+p['after']))
    for i,pair in enumerate(selection['pairs']):
        source_id=pair['source_id'];result,spec,data=bundles[source_id]
        item=dict(pair_id=pair['pair_id'],before=source_id+':'+pair['before'],after=source_id+':'+pair['after'],before_images=[],after_images=[])
        if item['before']==item['after']:raise ValueError('Different observed segments required')
        for side in ('before','after'):
            frames=pair[side+'_frames']
            if (not 1<=len(frames)<=3 or any(type(fi) is not int for fi in frames)
                    or frames!=sorted(set(frames))):
                raise ValueError('1-3 strictly increasing actual frame indices per side')
            for j,fi in enumerate(frames):
                segment,row=measured_row(result,pair[side],fi)
                bounds=crop_bounds(row['bbox'],result['source_size'])
                f=data['cached'][fi]
                path=target/f'p{i+1:06d}-{side}-{j+1}.npy'
                meta=dict(path=str(path),source_id=source_id,raw_id=segment['raw_id'],cache_index=row['cache_index'],
                    frame_index=fi,decoded_index=None,native_pts=f['native_pts'],time_base=f['time_base'],pts=f['pts'],
                    bbox_xyxy=row['bbox'],crop_bounds_xyxy=bounds,source_size=f['source_size'])
                item[side+'_images'].append(meta)
                requests.setdefault((source_id,fi),[]).append(meta)
        plans.append(item)
        edge={k:item[k] for k in ('pair_id','before','after')}
        known={p['pair_id']:p for p in manifest['candidate_pairs']}
        if edge['pair_id'] not in known or known[edge['pair_id']]!=edge:
            raise ValueError('Selected pair must be an actual exported CPU candidate')
    # Native decode index is counted from the beginning, not inferred from FPS.
    import av
    for source_id,(result,spec,data) in bundles.items():
        needed={fi for sid,fi in requests if sid==source_id}
        by_native={data['cached'][fi]['native_pts']:fi for fi in needed}
        with av.open(spec['video']) as container:
            stream=container.streams.video[0]
            for decoded_index,frame in enumerate(container.decode(stream)):
                if frame.pts not in by_native:continue
                fi=by_native.pop(frame.pts);expected=data['cached'][fi]
                if str(frame.time_base)!=expected['time_base'] or float(frame.pts*frame.time_base)!=expected['pts']:
                    raise ValueError('Native frame binding mismatch')
                rgb=frame.to_ndarray(format='rgb24')
                for meta in requests[(source_id,fi)]:
                    x1,y1,x2,y2=meta['crop_bounds_xyxy'];crop=rgb[y1:y2,x1:x2].copy()
                    np.save(meta['path'],crop,allow_pickle=False)
                    meta.update(decoded_index=decoded_index,sha256=sha256(meta['path']),
                        rgb_sha256=hashlib.sha256(crop.tobytes()).hexdigest())
                    preview=Path(meta['path']).with_suffix('.png')
                    Image.fromarray(crop).save(preview)
                    crop_map.append(dict(meta,native_rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),
                        bbox_sha256=hashlib.sha256(json.dumps(meta['bbox_xyxy'],separators=(',',':')).encode()).hexdigest(),
                        preview_path=str(preview),preview_sha256=sha256(preview)))
                if not by_native:break
        if by_native:raise ValueError('Requested native frames missing')
    for item in plans:
        board=Image.new('RGB',(1400,620),'#101722');draw=ImageDraw.Draw(board)
        draw.text((15,10),item['pair_id']+' | 판단 불가',font=font(24),fill='white')
        for side,col in (('before',0),('after',1)):
            images=item[side+'_images'];draw.text((col*700+10,50),side+' '+item[side],font=font(20),fill='white')
            for j,meta in enumerate(images):
                img=Image.fromarray(np.load(meta['path'],allow_pickle=False));img.thumbnail((220,450))
                x=col*700+j*230+10;board.paste(img,(x,115))
                draw.text((x,80),f'{meta["pts"]:.3f}s raw{meta["raw_id"]}',font=font(18),fill='yellow')
        board.save(target/f'pair-{len(manifest["pairs"])+1:03d}.jpg')
        manifest['pairs'].append(item)
    write_json(manifest_path,manifest)
    write_json(target/'crop-map.json',crop_map)
    provenance=dict(selection_sha256=sha256(selection_path),manifest_sha256=sha256(manifest_path),
        source_rgb_policy='exact native uint8 RGB; no resize; full floor/ceil observed box; no body slicing',
        result_sha256={str(p):sha256(p) for p in result_paths},pair_ids=[p['pair_id'] for p in plans])
    write_json(target/'provenance.json',provenance)
    return provenance


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('render');r.add_argument('--result',required=True,type=Path);r.add_argument('--output',required=True,type=Path)
    v=sub.add_parser('overview');v.add_argument('--result',required=True,type=Path);v.add_argument('--output',required=True,type=Path)
    c=sub.add_parser('crops');c.add_argument('--selection',required=True,type=Path);c.add_argument('--results',required=True,nargs='+',type=Path)
    c.add_argument('--output',required=True,type=Path);c.add_argument('--manifest',required=True,type=Path)
    a=p.parse_args()
    if a.command=='render':result=render(a.result,a.output)
    elif a.command=='overview':result=segment_boards(a.result,a.output)
    else:result=prepare_crops(a.selection,a.results,a.output,a.manifest)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
