"""Local-only detector + adjacent IoU + configured boundary diagnostic CLI."""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

from .boundary import BoundaryTracker
from .detectors import SPECS, build_detector

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_output(path):
    path = path.resolve()
    if not any(path.is_relative_to(ROOT/p) for p in ['data', 'outputs', 'runs']):
        raise ValueError('Media/results must remain in local ignored data/outputs/runs')
    return path


def json_save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')


def parse_args():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--detector',choices=list(SPECS),default='ssdlite320')
    p.add_argument('--weights',type=Path,default=None)
    p.add_argument('--download-weights',action='store_true',help='Explicit official weight download only')
    p.add_argument('--cache-person',action='store_true',help='Cache post-model person results before project score filter')
    p.add_argument('--diagnose-fcos',action='store_true',help='Read-only stage logging; timings not comparable')
    p.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    p.add_argument('--start',type=float,default=0.)
    p.add_argument('--end',type=float,default=None)
    args=p.parse_args()
    if args.start < 0 or (args.end is not None and args.end <= args.start):
        p.error('Require 0 <= start < end')
    return args


def preview(rgb, rows, cfg, pts, path):
    from PIL import Image, ImageDraw
    im=Image.fromarray(rgb);im.thumbnail((960,540));w,h=im.size;draw=ImageDraw.Draw(im)
    draw.line([(x*w,y*h) for x,y in cfg['line']],fill='yellow',width=3)
    draw.rectangle([cfg['roi'][0]*w,cfg['roi'][1]*h,cfg['roi'][2]*w,cfg['roi'][3]*h],outline='cyan',width=2)
    for row in rows:
        box=[v*(w if i%2==0 else h) for i,v in enumerate(row['bbox'])]
        draw.rectangle(box,outline='red',width=2)
        draw.text((box[0],max(0,box[1]-12)),f"id={row['track_id']} {row['score']:.2f}",fill='red')
    draw.text((8,8),f'PTS {pts:.6f} | candidate only',fill='yellow')
    im.save(path)


def run(args):
    import av
    import numpy as np
    import torch
    import torchvision
    if args.diagnose_fcos and args.detector != 'fcos800':
        raise ValueError('Diagnostics require FCOS')
    output=safe_output(args.output)
    output.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(args.config.read_text())
    tracker=BoundaryTracker(cfg)
    if not 0 < cfg['score_threshold'] < 1:
        raise ValueError('Invalid score threshold')
    if args.device=='cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; choose CPU explicitly, no silent fallback')
    torch.set_num_threads(2)
    torch.manual_seed(0)
    torch.backends.cudnn.benchmark=False
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    spec=SPECS[args.detector]
    weight_url='https://download.pytorch.org/models/'+spec['filename']
    args.weights=(args.weights or ROOT/'weights'/spec['filename']).resolve()
    if not args.weights.is_relative_to(ROOT/'weights'):
        raise ValueError('Weights must remain in ignored weights/')
    if not args.weights.exists():
        if not args.download_weights:
            raise FileNotFoundError('Missing local weights; use explicit --download-weights')
        args.weights.parent.mkdir(parents=True,exist_ok=True)
        torch.hub.download_url_to_file(weight_url,str(args.weights),hash_prefix=spec['hash_prefix'])
    if not digest(args.weights).startswith(spec['hash_prefix']):
        raise ValueError('Weight hash does not match selected detector')
    model=build_detector(args.detector)
    model.load_state_dict(torch.load(args.weights,map_location='cpu',weights_only=True))
    model.to(args.device)
    postprocess_settings={k:getattr(model,k,None) for k in ['score_thresh','topk_candidates','nms_thresh','detections_per_img']}
    diagnostics=None
    if args.diagnose_fcos:
        from .fcos_diagnostics import FCOSDiagnostics
        diagnostics=FCOSDiagnostics(model,output,cfg['score_threshold'])
    def sync():
        if args.device=='cuda':torch.cuda.synchronize()
    source_hash=digest(args.video)
    code_files=[Path(__file__),ROOT/'sceneguard/boundary.py',ROOT/'sceneguard/detectors.py']
    if diagnostics:code_files.append(ROOT/'sceneguard/fcos_diagnostics.py')
    meta=dict(started_utc=datetime.now(timezone.utc).isoformat(),
              video_id=args.video.stem, source_sha256=source_hash,
              config_sha256=digest(args.config), config=cfg, model_sha256=digest(args.weights),
              model_bytes=args.weights.stat().st_size,model_url=weight_url,
              model=spec['name'], model_input=spec['input'], model_postprocess=postprocess_settings,
              model_parameters=sum(p.numel() for p in model.parameters()),
              code_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              code_file_sha256={str(p.relative_to(ROOT)):digest(p) for p in code_files},
              git_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
              python=platform.python_version(), platform=platform.platform(),
              torch=torch.__version__,torchvision=torchvision.__version__,av=av.__version__,numpy=np.__version__,
              cuda_runtime=torch.version.cuda,device=args.device,
              gpu=torch.cuda.get_device_name() if args.device=='cuda' else None,
              gpu_total_bytes=torch.cuda.get_device_properties(0).total_memory if args.device=='cuda' else None,
              ffmpeg_libraries={k:list(v) for k,v in av.library_versions.items()},
              requested_window=[args.start,args.end], seed=0, batch_size=1,precision='float32',
              warmup_frames=10, threads=2, sampling='none', split='development_only',
              ground_truth_loaded=False, completion='unknown')
    def record_transform(module, inputs, transformed):
        images=transformed[0]
        meta['model_input_observed']={'resized_hw':[list(s) for s in images.image_sizes],
                                      'padded_nchw':list(images.tensors.shape)}
    model.transform.register_forward_hook(record_transform)
    json_save(output/'run.json',meta)
    timings={k:[] for k in ['decode','preprocess','detector','rules','output','total']}
    count=0;nonempty=0;boxes=0;events_all=[];pts_values=[];preroll=0.;decode_eof=False
    last_preview=-float('inf'); previous_decoded=None;warm=False;started=None
    try:
        with av.open(str(args.video)) as container, (output/'frames.jsonl').open('w') as frames_out, (output/'events.jsonl').open('w') as events_out, ((output/'person_cache.jsonl').open('w') if args.cache_person else nullcontext(None)) as cache_out:
            stream=container.streams.video[0];stream.thread_count=2
            meta.update(source_size=[stream.width,stream.height],display_fps=float(stream.average_rate) if stream.average_rate else None)
            iterator=iter(container.decode(stream))
            while True:
                frame_started=time.perf_counter()
                try:frame=next(iterator)
                except StopIteration:
                    decode_eof=True;break
                decoded=time.perf_counter()
                if frame.pts is None:raise ValueError('Missing native PTS')
                pts=float(frame.pts*frame.time_base)
                if previous_decoded is not None and pts <= previous_decoded:raise ValueError('Non-monotonic native PTS')
                previous_decoded=pts
                if pts < args.start:
                    preroll+=time.perf_counter()-frame_started;continue
                if args.end is not None and pts >= args.end:break
                if not warm:
                    warmup_start=time.perf_counter()
                    with torch.inference_mode():
                        dummy=torch.zeros((3,frame.height,frame.width),device=args.device)
                        for _ in range(10):model([dummy])
                        del dummy
                    sync();meta['warmup_seconds']=time.perf_counter()-warmup_start
                    if args.device=='cuda':torch.cuda.reset_peak_memory_stats()
                    warm=True;started=time.perf_counter()
                    # First frame's measured decode happened before warmup; account separately.
                    frame_started=started-(decoded-frame_started)
                    decoded=started
                preprocess_start=time.perf_counter()
                rgb=frame.to_ndarray(format='rgb24')
                tensor=torch.from_numpy(rgb).permute(2,0,1).to(args.device,dtype=torch.float32)/255.
                sync();preprocessed=time.perf_counter()
                if diagnostics:diagnostics.pts=pts
                with torch.inference_mode():prediction=model([tensor])[0]
                sync();inferred=time.perf_counter()
                if cache_out is not None:
                    person=prediction['labels']==1
                    cache_out.write(json.dumps(dict(pts=pts,native_pts=frame.pts,time_base=str(frame.time_base),
                        source_size=[frame.width,frame.height],boxes=prediction['boxes'][person].cpu().tolist(),
                        scores=prediction['scores'][person].cpu().tolist()))+'\n')
                # Person label 1 in TorchVision COCO; output boxes normalized to source image.
                mask=(prediction['labels']==1)&(prediction['scores']>=cfg['score_threshold'])
                box_list=prediction['boxes'][mask].cpu().tolist();scores=prediction['scores'][mask].cpu().tolist()
                detections=[]
                for box,score in zip(box_list,scores):
                    normalized=[max(0.,min(1.,v/(frame.width if i%2==0 else frame.height))) for i,v in enumerate(box)]
                    if normalized[0]<normalized[2] and normalized[1]<normalized[3]:
                        detections.append(dict(bbox=normalized,score=score))
                rows,events=tracker.step(pts,detections)
                ruled=time.perf_counter()
                for e in events:
                    e.update(video_id=args.video.stem,boundary_id=cfg['boundary_id'],
                             model_sha256=meta['model_sha256'],config_sha256=meta['config_sha256'],
                             code_sha=meta['code_sha'],evidence_refs={'video':args.video.name,'pts':e['candidate_interval']})
                    events_out.write(json.dumps(e)+'\n');events_all.append(e)
                frames_out.write(json.dumps(dict(pts=pts,native_pts=frame.pts,time_base=str(frame.time_base),detections=rows))+'\n')
                if events or pts-last_preview >= 5:
                    preview(rgb,rows,cfg,pts,output/f'frame_{count:06d}.jpg');last_preview=pts
                finished=time.perf_counter()
                for k,v in [('decode',decoded-frame_started),('preprocess',preprocessed-preprocess_start),
                            ('detector',inferred-preprocessed),('rules',ruled-inferred),
                            ('output',finished-ruled),('total',finished-frame_started)]:timings[k].append(v*1000)
                count+=1;nonempty+=bool(rows);boxes+=len(rows);pts_values.append(pts)
                if count%900==0:print(args.video.stem,count,'frames',len(events_all),'candidates',flush=True)
            frames_out.flush();events_out.flush()
            if cache_out is not None:cache_out.flush()
        wall=time.perf_counter()-started if started else 0.
        if not count:raise ValueError('No frames in requested window')
        meta.update(status='complete',frames=count,frames_with_person=nonempty,person_boxes=boxes,
                    candidate_count=len(events_all),tracker_stats=tracker.stats,
                    first_pts=pts_values[0],last_pts=pts_values[-1],decoded_to_eof=decode_eof,
                    preroll_decode_seconds=preroll,processing_wall_seconds=wall,
                    throughput_fps=count/wall,processing_wall_scope='post-warmup frame loop, decode/conversion/inference/rules/JSON/previews/flush; excludes model setup, preroll, first frame decode and final summary',
                    peak_allocated_bytes=torch.cuda.max_memory_allocated() if args.device=='cuda' else None,
                    peak_reserved_bytes=torch.cuda.max_memory_reserved() if args.device=='cuda' else None,
                    active_tracks_at_end=len(tracker.tracks),end_state='observation_stopped_not_completion',
                    stage_ms={k:dict(mean=float(np.mean(v)),p50=float(np.percentile(v,50)),p95=float(np.percentile(v,95))) for k,v in timings.items()})
        if args.cache_person:
            meta['person_cache']=dict(schema=1,stage='model_return_after_internal_filters_nms_global_cap_before_project_score',
                sha256=digest(output/'person_cache.jsonl'),coordinate_space='original_pixels',class_id=1)
            meta['timing_comparable']=False
        if diagnostics:
            diagnostics.finish()
            meta['diagnostic_logging']=True
            meta['timing_comparable']=False
        json_save(output/'timings_ms.json',timings)
        json_save(output/'native_pts.json',pts_values)
        json_save(output/'run.json',meta)
        print(json.dumps({k:meta[k] for k in ['video_id','frames','candidate_count','throughput_fps','peak_allocated_bytes']}),flush=True)
    except Exception as e:
        meta.update(status='failed',processed_frames=count,error_type=type(e).__name__,error=str(e))
        json_save(output/'run.json',meta)
        raise


if __name__=='__main__':run(parse_args())
