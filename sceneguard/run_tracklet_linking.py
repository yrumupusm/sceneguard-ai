"""EXP-0029 local offline runner: cached measurements -> tracklets -> links.

Uses the EXP-0028 pinned CPU ReID encoder on a few real crops per endpoint.
Does not call a detector, train, invoke BOTSORT.update, or alter historical IDs.
Local camera-side polygons are optional for linking, required for event output.
"""
import argparse
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time

import numpy as np

from .tracklet_linking import (LinkSettings, build_tracklets, endpoint_rows,
                              link_tracklets, region_events, unit_features, validate_zones, valid_box)

FCOS_SHA = '99b0c9b7cfb1527d782db86b91d207f00547c792fb4103fc612b651d0a07b9e7'
REID_SHA = '8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb'
CACHE_STAGE = 'model_return_after_internal_filters_nms_global_cap_before_project_score'


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def load_inputs(cache_directory, track_path, source):
    cache_directory, track_path, source = map(Path, (cache_directory, track_path, source))
    meta_path, cache_path = cache_directory/'run.json', cache_directory/'person_cache.jsonl'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    hashes = dict(metadata=sha256(meta_path), cache=sha256(cache_path),
                  tracks=sha256(track_path), video=sha256(source))
    if (meta.get('status') != 'complete' or meta.get('model_sha256') != FCOS_SHA or
            meta.get('source_sha256') != hashes['video'] or
            meta['person_cache'].get('stage') != CACHE_STAGE or
            meta['person_cache'].get('schema') != 1 or
            meta['person_cache'].get('sha256') != hashes['cache']):
        raise ValueError('Intact pretrained FCOS cache and matching original video required')
    cached, tracked = read_jsonl(cache_path), read_jsonl(track_path)
    if len(cached) != meta['frames'] or len(tracked) != len(cached) or len(cached) < 2:
        raise ValueError('Cache/tracking frame counts differ')
    dimensions = cached[0]['source_size']
    if len(dimensions) != 2 or any(type(v) is not int or v <= 0 for v in dimensions):
        raise ValueError('Invalid source dimensions')
    previous, intervals = None, []
    for frame, record in zip(cached, tracked):
        if any(frame[k] != record[k] for k in ('pts', 'native_pts', 'time_base')):
            raise ValueError('Tracking/cache native timing mismatch')
        pts = frame['pts']
        if (not math.isfinite(pts) or abs(float(Fraction(frame['time_base'])*frame['native_pts'])-pts) > 1e-6
                or frame['source_size'] != dimensions or len(frame['boxes']) != len(frame['scores'])):
            raise ValueError('Invalid cache timing, dimensions or arrays')
        if previous is not None:
            if pts <= previous:
                raise ValueError('Frame timestamps must increase')
            intervals.append(pts-previous)
        previous = pts
        used = set()
        for row in record['detections']:
            if not row.get('observed', False) or not row.get('confirmed', True):
                continue
            index = row['cache_index']
            if type(index) is not int or not 0 <= index < len(frame['boxes']) or index in used:
                raise ValueError('Duplicate/invalid measured cache index')
            used.add(index)
            expected = np.clip(np.array(frame['boxes'][index], dtype=float)/np.tile(dimensions, 2), 0, 1)
            if (not np.allclose(expected, row['bbox'], atol=1e-7, rtol=0)
                    or not math.isclose(frame['scores'][index], row['score'], abs_tol=1e-7, rel_tol=0)):
                raise ValueError('Tracking rows must be original measured cache boxes/scores')
    interval = statistics.median(intervals)
    if any(abs(dt-interval) > 1e-6 for dt in intervals):
        raise ValueError('Unsampled constant-frame-interval cache required')
    return meta, cached, tracked, interval, hashes


def decode_native(source, cached):
    """Yield exact native PTS BGR frames, never closest-frame substitutions."""
    import av
    with av.open(str(source)) as container:
        stream = container.streams.video[0]
        container.seek(cached[0]['native_pts'], stream=stream, backward=True)
        index = 0
        for video in container.decode(stream):
            if video.pts is None:
                continue
            target = cached[index]
            actual = video.pts*video.time_base
            expected = target['native_pts']*Fraction(target['time_base'])
            if actual < expected:
                continue
            if actual != expected or video.pts != target['native_pts'] or str(video.time_base) != target['time_base']:
                raise ValueError('Missing/misaligned native frame')
            yield index, video.to_ndarray(format='bgr24')
            index += 1
            if index == len(cached):
                return
        raise ValueError('Video ended before the cached evaluation window')


def create_encoder(weights, interval):
    """Reuse the previously inspected CPU encoder; do not run online association."""
    os.environ.update(YOLO_AUTOINSTALL='false', YOLO_OFFLINE='true', ULTRALYTICS_OFFLINE='true')
    from .practical_reid import create_adapter
    adapter = create_adapter(weights, interval)
    return adapter.tracker.encoder


def validate_features(features, selections):
    """Reject incomplete/tampered reuse rather than silently dropping link evidence."""
    if not isinstance(features, dict) or set(features) != set(selections):
        raise ValueError('Feature segments must exactly match eligible tracklets')
    dimension = None
    for sid, endpoints in features.items():
        if not isinstance(endpoints, dict) or set(endpoints) != {'head', 'tail'}:
            raise ValueError('Feature endpoints must be exactly head and tail')
        for end, values in endpoints.items():
            array = unit_features(values)
            if len(array) != len(selections[sid][end]):
                raise ValueError('Feature count must match selected endpoint representatives')
            if dimension is not None and array.shape[1] != dimension:
                raise ValueError('All representative embedding dimensions must agree')
            dimension = array.shape[1]


def encode_selected(source, cached, segments, settings, encoder, decoder=decode_native, review_dir=None):
    requests, selections = {}, {}
    for segment in segments:
        if not segment['eligible']:
            continue
        selections[segment['id']] = {}
        for end in ('head', 'tail'):
            rows = endpoint_rows(segment, end, settings)
            selections[segment['id']][end] = rows
            for row in rows:
                key = (row['frame_index'], row['cache_index'])
                requests[key] = row
    by_frame = {}
    for key, row in requests.items():
        by_frame.setdefault(key[0], []).append((key, row))
    encoded, calls = {}, 0
    if review_dir is not None:
        review_dir.mkdir()
    width, height = cached[0]['source_size']
    seen_frames = set()
    for frame_index, image in decoder(source, cached):
        if frame_index in seen_frames or not 0 <= frame_index < len(cached):
            raise ValueError('Duplicate/invalid decoded frame index')
        seen_frames.add(frame_index)
        if image.dtype != np.uint8 or image.shape != (height, width, 3):
            raise ValueError('Expected full-size uint8 BGR source')
        work = by_frame.get(frame_index, [])
        if not work:
            continue
        boxes = np.array([r['bbox'] for _, r in work])*[width, height, width, height]
        xywh = boxes.copy()
        xywh[:, 2:] -= xywh[:, :2]
        xywh[:, :2] += xywh[:, 2:]/2
        # Official ReID takes center-xywh, NOT xyxy. One row per original crop.
        returned = encoder(image, xywh)
        calls += 1
        if len(returned) != len(work):
            raise ValueError('Encoder returned the wrong number of features')
        for (key, row), feature, box in zip(work, returned, boxes):
            if feature is None:
                raise ValueError('Missing representative embedding')
            feature = unit_features([feature])[0]
            encoded[key] = feature.tolist()
            if review_dir is not None:
                import cv2
                x1, y1, x2, y2 = box
                crop = image[max(0,int(math.floor(y1))):min(height,int(math.ceil(y2))),
                             max(0,int(math.floor(x1))):min(width,int(math.ceil(x2)))]
                if not crop.size or not cv2.imwrite(str(review_dir/f'f{key[0]:06d}-d{key[1]}.jpg'), crop):
                    raise ValueError('Representative crop save failed')
    if len(seen_frames) != len(cached) or set(encoded) != set(requests):
        raise ValueError('Not all requested frames/crops were decoded')
    features = {}
    for sid, endpoints in selections.items():
        features[sid] = {end:[encoded[(r['frame_index'],r['cache_index'])] for r in rows]
                         for end,rows in endpoints.items()}
    return features, selections, dict(encoder_calls=calls, encoded_crops=len(encoded))


def render_comparison(source, cached, tracked, segments, associations, events, path,
                      decoder=decode_native, zones=None, control=(), display_region=None):
    """Local original/raw-ID/linked-ID comparison. No boxes invented in gaps."""
    import cv2
    import av
    width, height = cached[0]['source_size']
    view = valid_box(display_region if display_region is not None else [0,0,1,1])
    left,top = math.floor(view[0]*width),math.floor(view[1]*height)
    right,bottom = math.ceil(view[2]*width),math.ceil(view[3]*height)
    panel_w, panel_h = 640, max(1, round(640*(bottom-top)/(right-left)))
    def display_points(points):
        return (np.asarray(points)*[width,height]-[left,top])*[panel_w/(right-left),panel_h/(bottom-top)]
    # Derive exact playback rate from native rational PTS rather than float noise.
    dt = ((cached[1]['native_pts']-cached[0]['native_pts']) * Fraction(cached[0]['time_base']))
    header_h = 144
    canvas_h = panel_h+header_h
    canvas_h += canvas_h % 2  # yuv420p requires even dimensions
    if Path(path).exists():
        raise FileExistsError('Comparison media must not overwrite existing results')
    mapping = {(r['frame_index'],r['raw_id']):(s['id'],associations['mapping'][s['id']])
               for s in segments for r in s['rows']}
    def color(key):
        raw = hashlib.sha256(key.encode()).digest()
        return tuple(80+int(x)%176 for x in raw[:3])
    count = 0
    with av.open(str(path), 'w', options={'movflags': '+faststart'}) as writer:
        stream = writer.add_stream('libx264', rate=1/dt)
        stream.width, stream.height, stream.pix_fmt = panel_w*3, canvas_h, 'yuv420p'
        stream.options = {'crf': '20', 'preset': 'fast'}
        for frame_index, bgr in decoder(source, cached):
            original = cv2.resize(bgr[top:bottom,left:right], (panel_w,panel_h))
            panels = [original.copy(),original.copy(),original.copy()]
            if zones is not None:
                for panel in panels[1:]:
                    for name, shade in [('outside',(70,220,90)),('inside',(240,190,50))]:
                        polygon = np.rint(display_points(zones[name])).astype(np.int32)
                        cv2.polylines(panel,[polygon],True,shade,2)
            for row in tracked[frame_index]['detections']:
                if not row.get('observed',False) or not row.get('confirmed',True):
                    continue
                sid, chain = mapping[(frame_index,row['track_id'])]
                x1,y1,x2,y2 = np.rint(display_points(np.asarray(row['bbox']).reshape(2,2))).astype(int).ravel()
                for panel,label,key in [(1,f'raw {row["track_id"]}/{sid}',str(row['track_id'])),
                                        (2,f'{chain}/{sid} raw {row["track_id"]}',chain)]:
                    cv2.rectangle(panels[panel],(x1,y1),(x2,y2),color(key),2)
                    cv2.putText(panels[panel], label, (x1,max(15,y1-4)),cv2.FONT_HERSHEY_SIMPLEX,.45,color(key),1)
            canvas = np.zeros((canvas_h, panel_w*3,3),dtype=np.uint8)
            canvas[header_h:header_h+panel_h] = np.concatenate(panels,axis=1)
            for i,title in enumerate(['ORIGINAL'+(' - DISPLAY ZOOM' if display_region else ''),'MEASURED RAW IDs','OFFLINE LINKED IDs - NOT LIVE']):
                cv2.putText(canvas,title,(i*panel_w+8,22),cv2.FONT_HERSHEY_SIMPLEX,.52,(255,255,255),1)
            pts = cached[frame_index]['pts']
            cv2.putText(canvas,f'SOURCE PTS {pts:.3f} | OFFLINE available_after PTS {cached[-1]["pts"]:.3f} | identity unverified',
                        (8,49),cv2.FONT_HERSHEY_SIMPLEX,.55,(200,240,255),1)
            cv2.putText(canvas,'Regions: green OUTSIDE / blue INSIDE; transition excluded; candidates are not climb proof',
                        (8,74),cv2.FONT_HERSHEY_SIMPLEX,.52,(210,210,210),1)
            for panel, candidate_list, label in [(1,control,'UNLINKED'),(2,events,'LINKED')]:
                due = [e for e in candidate_list if e['confirmed_at'] <= pts]
                cv2.putText(canvas,f'Same regions {label}: {len(due)} / {len(candidate_list)} candidates',
                            (panel*panel_w+8,99),cv2.FONT_HERSHEY_SIMPLEX,.48,(200,240,255),1)
                if due:
                    latest = max(due,key=lambda e:e['confirmed_at'])
                    cv2.putText(canvas,f'{latest["chain_id"]} {latest["direction"]} @ {latest["confirmed_at"]:.3f}',
                                (panel*panel_w+8,125),cv2.FONT_HERSHEY_SIMPLEX,.46,(200,240,255),1)
            video = av.VideoFrame.from_ndarray(canvas,format='bgr24')
            video.pts, video.time_base = count, dt
            for packet in stream.encode(video):
                writer.mux(packet)
            count += 1
        for packet in stream.encode():
            writer.mux(packet)
    with av.open(str(path)) as reader:
        media = reader.streams.video[0]
        codec = media.codec_context.name
        pixel_format = media.codec_context.format.name
        decoded = sum(1 for _ in reader.decode(media))
    if count != len(cached) or decoded != count:
        raise ValueError('Rendered comparison frame count mismatch')
    if codec != 'h264' or pixel_format != 'yuv420p':
        raise ValueError('Browser comparison requires H264 yuv420p')
    return dict(frames=count, decoded_frames=decoded, timing='constant-fps display; source PTS in header',
                codec=codec,pixel_format=pixel_format,faststart=True,
                display_region=view,display_only=True,
                regions_visible=zones is not None,unlinked_candidates=len(control),linked_candidates=len(events),
                available_after_pts=cached[-1]['pts'],review='not_yet_human_reviewed', sha256=sha256(path))


def run(cache_directory, track_path, source, weights, output_directory,
        settings=LinkSettings(), zones_path=None, features_path=None, render=False,
        encoder_factory=None, decoder=decode_native):
    settings.validate()
    output = Path(output_directory)
    if (not output.resolve().is_relative_to(Path('outputs').resolve()) or output.exists()
            or output.is_symlink() or any(p.is_symlink() for p in output.parents)):
        raise FileExistsError('Use a new directory under local Git-ignored outputs/')
    meta,cached,tracked,interval,hashes = load_inputs(cache_directory,track_path,source)
    if sha256(weights) != REID_SHA:
        raise ValueError('Use the existing pinned EXP-0028 ReID checkpoint')
    segments = build_tracklets(tracked,settings)
    selections = {s['id']:{end:endpoint_rows(s,end,settings) for end in ('head','tail')}
                  for s in segments if s['eligible']}
    zones = None
    if zones_path is not None:
        zones = validate_zones(json.loads(Path(zones_path).read_text(encoding='utf-8')))
        if zones.get('source_sha256') != hashes['video'] or zones.get('source_size') != cached[0]['source_size']:
            raise ValueError('Regions must be bound to the actual source video and dimensions')
    feature_binding = dict(inputs=hashes, weights=REID_SHA, settings=asdict(settings))
    reused = None
    if features_path is not None:
        reused = json.loads(Path(features_path).read_text(encoding='utf-8'))
        if reused.get('binding') != feature_binding:
            raise ValueError('Feature cache belongs to other inputs/settings/model')
        validate_features(reused.get('features'),selections)
    output.mkdir(parents=True,exist_ok=False)
    started = time.perf_counter()
    try:
        if reused is not None:
            features, extraction = reused['features'], dict(encoder_calls=0,encoded_crops=0,reused=True)
        elif selections:
            encoder = (encoder_factory or create_encoder)(weights,interval)
            features,selections,extraction = encode_selected(source,cached,segments,settings,encoder,decoder,output/'representatives')
            extraction['reused'] = False
            session = getattr(getattr(encoder,'model',None),'session',None)
            if session is not None:
                extraction.update(device=str(encoder.device),providers=session.get_providers(),
                                  fp16=encoder.fp16,imgsz=list(encoder.imgsz))
        else:
            features, extraction = {}, dict(encoder_calls=0,encoded_crops=0,reused=False)
        validate_features(features,selections)
        extraction_finished = time.perf_counter()
        associations = link_tracklets(segments,features,settings)
        events = [] if zones is None else region_events(segments,associations,zones,interval,
                          max_gap_seconds=settings.max_gap_seconds,available_after_pts=cached[-1]['pts'])
        # Same-region control separates identity linking from changed event geometry.
        unlinked = dict(chains=[dict(id=s['id'],segments=[s['id']]) for s in segments])
        control = [] if zones is None else region_events(segments,unlinked,zones,interval,
                          max_gap_seconds=settings.max_gap_seconds,available_after_pts=cached[-1]['pts'])
        association_finished = time.perf_counter()
        code_hashes = {Path(__file__).name:sha256(__file__),
                      'tracklet_linking.py':sha256(Path(__file__).with_name('tracklet_linking.py')),
                      'practical_reid.py':sha256(Path(__file__).with_name('practical_reid.py'))}
        write_json(output/'features.local.json',dict(binding=feature_binding,features=features,
            extraction_provenance=reused.get('extraction_provenance') if reused is not None else
                dict(code_sha256=code_hashes,extraction=extraction)))
        write_json(output/'representatives.json',selections)
        write_json(output/'tracklets.json',segments)
        write_json(output/'associations.json',associations)
        write_json(output/'events.json',events)
        write_json(output/'unlinked-region-events.json',control)
        summary = dict(status='complete',mode='offline',frames=len(cached),video_id=meta.get('video_id'),
            evaluated_window=[cached[0]['pts'],cached[-1]['pts']],
            segments=len(segments),eligible_segments=sum(s['eligible'] for s in segments),
            accepted_links=sum(r['status']=='accepted' for r in associations['links']),
            deferred_links=sum(r['status']=='deferred' for r in associations['links']),
            region_status='evaluated' if zones is not None else 'not_configured_no_event_claim',
            candidates=len(events),unlinked_region_candidates=len(control),extraction=extraction,
            identity_verified=False,cctv_accuracy=None,uses_finetuned_model=False,
            source_hashes=hashes,settings=asdict(settings),
            weights_sha256=REID_SHA,regions_sha256=sha256(zones_path) if zones_path else None,
            code_sha256=code_hashes)
        render_started = time.perf_counter()
        if render:
            summary['render'] = render_comparison(source,cached,tracked,segments,associations,
                                                  events,output/'original_raw_linked.mp4',decoder,zones,control)
        render_finished = time.perf_counter()
        summary['phase_wall_seconds'] = dict(extraction=extraction_finished-started,
            linking_and_events=association_finished-extraction_finished,
            rendering=render_finished-render_started if render else 0.)
        for name,path in [('metadata',Path(cache_directory)/'run.json'),('cache',Path(cache_directory)/'person_cache.jsonl'),
                          ('tracks',track_path),('video',source)]:
            if sha256(path) != hashes[name]:
                raise ValueError('Input changed during offline processing')
        if sha256(weights) != REID_SHA:
            raise ValueError('Checkpoint changed during processing')
        summary['wall_seconds'] = time.perf_counter()-started
        write_json(output/'summary.json',summary)
        return summary
    except Exception as exc:
        write_json(output/'failure.json',dict(type=type(exc).__name__,message=str(exc)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',required=True,type=Path)
    parser.add_argument('--tracks',required=True,type=Path)
    parser.add_argument('--video',required=True,type=Path)
    parser.add_argument('--weights',type=Path,default=Path('weights/exp0028/yolo26n-reid.onnx'))
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--settings',type=Path,default=Path('configs/exp0029_tracklet_linking.json'))
    parser.add_argument('--regions',type=Path,help='Local normalized outside/inside polygons bound to source')
    parser.add_argument('--features',type=Path,help='Reuse prior same-input features.local.json without inference')
    parser.add_argument('--render',action='store_true')
    args = parser.parse_args()
    settings = LinkSettings(**json.loads(args.settings.read_text(encoding='utf-8'))).validate()
    print(json.dumps(run(args.cache,args.tracks,args.video,args.weights,args.output,settings,
                         args.regions,args.features,args.render),ensure_ascii=False,allow_nan=False))


if __name__ == '__main__':
    main()
