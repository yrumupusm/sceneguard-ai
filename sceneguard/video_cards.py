"""Local selected video -> validated FCOS cache -> measured tracks -> review cards.

Camera selection is explicit. CPU stages never invoke a model. Fresh detection,
when requested, is delegated exclusively to the canonical queue adapter.
"""
import argparse
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from fractions import Fraction
import fcntl
import hashlib
import json
import math
from pathlib import Path
import time
import uuid

from .replay_gap_tracking import load_cache, sha256, make_adapter
from .incident_cards import canonical, GroupPolicy
from .approach_disappearance import Policy, analyze
from .relaxed_suspicion import RelaxedPolicy, add_relaxed_candidates
from .exp0034_application import enrich_timing, validate_scene_binding
from .exp0036_application import make_bundle

ROOT = Path(__file__).resolve().parents[1]
CAMERAS = ROOT/'configs/mvp0001_cameras.json'
SCENES = {'C3': ROOT/'runtime/EXP-0034/scene007.json',
          'C6': ROOT/'runtime/EXP-0034/scene030.json'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def status(path, **value):
    tmp = path.with_name('.status-'+uuid.uuid4().hex)
    save(tmp, dict(utc=datetime.now(timezone.utc).isoformat(), **value))
    tmp.replace(path)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def camera_profile(camera_id, video, camera_registry=None):
    """Resolve a per-run frozen calibration without changing the legacy defaults.

    Registry v1 uses the existing camera fields plus scene_path/scene_sha256 and
    portal_path/portal_sha256. Its sources map absolute paths to {camera_id,
    sha256}; profile paths are relative to the registry's directory.
    """
    if camera_registry is None:
        if camera_id not in SCENES:
            raise ValueError('Explicit existing C3 or C6 camera required')
        return read(CAMERAS)['cameras'][camera_id], SCENES[camera_id], None, CAMERAS
    registry_path = Path(camera_registry).absolute()
    registry = read(registry_path)
    if registry.get('schema_version') != 1 or camera_id not in registry.get('cameras', {}):
        raise ValueError('Explicit frozen camera registry v1/profile required')
    source = registry.get('sources', {}).get(str(Path(video).absolute()))
    if source != dict(camera_id=camera_id, sha256=sha256(video)):
        raise ValueError('Source hash and explicit camera mapping differ from registry')
    camera = registry['cameras'][camera_id]
    boundary = camera.get('legacy_boundary_config', {})
    if (camera.get('camera_id') != camera_id or camera.get('calibrated') is not True
            or boundary.get('camera_group') != camera_id
            or camera.get('roi') != boundary.get('roi')):
        raise ValueError('Calibrated camera/ROI/boundary identity required')
    if camera_id in SCENES:
        original = read(CAMERAS)['cameras'][camera_id]
        if any(camera.get(k) != original.get(k) for k in
               ('camera_id', 'calibrated', 'roi', 'legacy_boundary_config')):
            raise ValueError('Existing C3/C6 calibration and thresholds must be preserved')
    else:
        # Only static geometry and camera identity vary; detector/rule thresholds
        # are inherited verbatim from the existing calibrated profile.
        original = read(CAMERAS)['cameras']['C3']['legacy_boundary_config']
        geometry = {'line', 'roi', 'boundary_id', 'camera_group', 'selection'}
        if {k:v for k,v in boundary.items() if k not in geometry} != {
                k:v for k,v in original.items() if k not in geometry}:
            raise ValueError('New profiles must preserve the existing boundary policy')
    paths = []
    for name in ('scene', 'portal'):
        path = Path(camera[name+'_path'])
        if not path.is_absolute():
            path = registry_path.parent/path
        path = path.absolute()
        if sha256(path) != camera[name+'_sha256']:
            raise ValueError('Frozen '+name+' profile hash differs')
        paths.append(path)
    if camera_id in SCENES:
        from .gate_episode_evidence import revised_scene
        base, selected = read(SCENES[camera_id]), read(paths[0])
        revised_scene(base, selected)
        if camera_id == 'C6' and {k:v for k,v in base.items() if k != 'inner_line'} != {k:v for k,v in selected.items() if k != 'inner_line'}:
            raise ValueError('C6 must retain its current approved scene')
    return camera, *paths, registry_path


def source_scene(camera_id, scene_path, camera_registry=None):
    """Retain the original C3/C6 CPU seed and pre-adoption candidate geometry."""
    return SCENES.get(camera_id, scene_path) if camera_registry is not None else scene_path


def scene_regions(scene, scene_path, *, embedded=False):
    provenance = scene.get('annotation_provenance', {})
    if embedded and 'current_regions_path' not in provenance:
        return scene['zones'], scene_path
    path = Path(provenance['current_regions_path'])
    if not path.is_absolute():
        path = ROOT/path
    if sha256(path) != provenance['current_regions_sha256']:
        raise ValueError('Current user regions differ from the frozen scene')
    return read(path), path


def code_binding():
    # Include transitive rule/tracker/decoder dependencies, not only this entrypoint.
    names = ('video_cards', 'run_cv', 'detectors', 'boundary', 'gap_boundary',
             'byte_adapter', 'replay_thresholds', 'replay_gap_tracking',
             'approach_disappearance', 'relaxed_suspicion', 'exp0034_application',
             'exp0036_application', 'incident_cards', 'run_tracklet_linking',
             'mvp_review_evidence', 'video_cards_registration')
    paths = [ROOT/'sceneguard'/f'{n}.py' for n in names]
    paths += list((ROOT/'sceneguard/vendor').rglob('*.py'))
    return {str(p.relative_to(ROOT)): sha256(p) for p in sorted(paths)}


def probe(video):
    import av
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        rate = stream.average_rate
        if rate != Fraction(30) and getattr(stream, 'base_rate', None) == Fraction(30000, 1001):
            rate = Fraction(30000, 1001)
        if rate not in (Fraction(30), Fraction(30000, 1001)):
            raise ValueError('Only native 30fps or rational 30000/1001 video is supported; no resampling')
        if stream.duration is None or stream.start_time not in (None, 0):
            raise ValueError('Video must have a known duration and source PTS origin zero')
        info = dict(size=[stream.width, stream.height], fps=str(rate),
                    duration=float(stream.duration*stream.time_base), time_base=str(stream.time_base))
        if rate != Fraction(30):
            # Decode the actual source clock, rather than trusting a nominal rate
            # or a cache's frame count. Gaps remain gaps; no source frame is made.
            dt, stamps = 1/rate, []
            for frame in container.decode(stream):
                if (type(frame.pts) is not int or frame.pts < 0
                        or str(frame.time_base) != info['time_base']):
                    raise ValueError('Native source PTS and stable time base required')
                at = frame.pts*frame.time_base
                if stamps:
                    step = (at-stamps[-1]*stream.time_base)/dt
                    if step.denominator != 1 or step < 1:
                        raise ValueError('Native rational cadence with integral PTS gaps required; arbitrary VFR unsupported')
                elif at != 0:
                    raise ValueError('Source PTS origin zero required')
                stamps.append(frame.pts)
            if len(stamps) < 2:
                raise ValueError('At least two actual native source frames required')
            info.update(native_pts=stamps, nominal_interval=str(dt),
                        average_rate=str(stream.average_rate), timing='native_pts_with_integral_gaps',
                        source_end_exclusive=float(stamps[-1]*stream.time_base+dt))
        return info


def validate_cached(video, camera, cache, start, end, info):
    native_dt = Fraction(info['nominal_interval']) if 'native_pts' in info else None
    load_args = {} if native_dt is None else dict(native_interval=native_dt)
    meta, frames, interval, hashes = load_cache(cache, **load_args)
    if (meta.get('source_sha256') != sha256(video)
            or meta.get('source_size') != info['size']
            or meta.get('config') != camera['legacy_boundary_config']
            or meta.get('model') != 'fcos_resnet50_fpn.COCO_V1'
            or meta.get('model_input') != dict(min_size=800, max_size=1333)
            or meta.get('sampling') != 'none'
            or meta.get('precision') != 'float32'
            or meta.get('batch_size') != 1 or meta.get('seed') != 0):
        raise ValueError('Cache source/model/camera/settings binding differs')
    for frame in frames:
        if (type(frame['native_pts']) is not int or frame['native_pts'] < 0
                or frame['time_base'] != info['time_base']
                or float(frame['native_pts']*Fraction(frame['time_base'])) != frame['pts']
                or frame['source_size'] != info['size']):
            raise ValueError('Cache native source PTS binding differs')
        w,h = info['size']
        if any(not 0 <= b[0] < b[2] <= w or not 0 <= b[1] < b[3] <= h for b in frame['boxes']):
            raise ValueError('Cache boxes must be original pixel xyxy')
    if native_dt is None and any(
            Fraction(b['native_pts']-a['native_pts'])*Fraction(a['time_base']) != Fraction(1,30)
            for a,b in zip(frames,frames[1:])):
        raise ValueError('Only exact unsampled native 30fps cache timing is supported')
    selected = [f for f in frames if start-1e-9 <= f['pts'] < end-1e-9]
    if native_dt is not None:
        expected = [p for p in info['native_pts']
                    if start-1e-9 <= float(p*Fraction(info['time_base'])) < end-1e-9]
        if [f['native_pts'] for f in selected] != expected:
            raise ValueError('Cache does not match every actual native source PTS')
        # Coverage follows actual source arrivals, including a requested boundary
        # inside a real timestamp gap, rather than a synthetic constant grid.
        if len(selected) < 2 or not 0 <= start < end <= info['source_end_exclusive']+1e-6:
            raise ValueError('Cache does not cover the entire selected source window')
        return meta, selected, interval, hashes
    if (len(selected) < 2 or selected[0]['pts']-start > interval+1e-6
            or selected[0]['pts'] < start-1e-6 or end-selected[-1]['pts'] > interval+1e-6):
        raise ValueError('Cache does not cover the entire selected source window')
    return meta, selected, interval, hashes


def find_cache(video, camera, start, end, info):
    """Prefer valid existing detector bytes even if --cache was omitted."""
    source_sha = sha256(video)
    for path in sorted((ROOT/'outputs').rglob('run.json')):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            continue
        try:
            meta = read(path)
            if (meta.get('status') != 'complete' or meta.get('source_sha256') != source_sha
                    or meta.get('model') != 'fcos_resnet50_fpn.COCO_V1'
                    or ('native_pts' not in info and (
                        meta.get('first_pts', math.inf) > start+1/30
                        or meta.get('last_pts', -1) < end-1/30-1e-6))
                    or meta.get('config') != camera['legacy_boundary_config']):
                continue
            validate_cached(video,camera,path.parent,start,end,info)
            return path.parent
        except (ValueError,KeyError,TypeError,OSError):
            continue
    return None


def stage(output, name, binding, action):
    """Publish completed stages once; resume only after exact artifact validation."""
    target = output/name
    if target.is_symlink() or (target/'stage.json').is_symlink():
        raise ValueError('Stage directory/receipt must not be a symlink: '+name)
    if target.exists():
        if any(p.is_symlink() for p in target.rglob('*')):
            raise ValueError('Stage artifacts must not be symlinks: '+name)
        receipt = read(target/'stage.json')
        actual = {str(p.relative_to(target)): sha256(p) for p in target.rglob('*')
                  if p.is_file() and p.name != 'stage.json'}
        if (receipt.get('binding') != binding or receipt.get('artifacts') != actual
                or any(p.is_symlink() for p in target.rglob('*'))):
            raise ValueError('Completed stage bytes/binding changed: '+name)
        return target, True
    temporary = output/('.'+name+'-'+uuid.uuid4().hex)
    temporary.mkdir()
    begin = time.perf_counter()
    action(temporary)
    files = {str(p.relative_to(temporary)): sha256(p) for p in temporary.rglob('*') if p.is_file()}
    save(temporary/'stage.json', dict(binding=binding, artifacts=files,
         elapsed_seconds=time.perf_counter()-begin, status='complete'))
    temporary.rename(target)
    return target, False


def track(frames, camera, folder, interval, video_id):
    from .gap_boundary import GapTolerantBoundary
    native_timing = abs(interval-1/30) > 1e-9
    adapter = make_adapter(3.0, interval, **(dict(native_timing=True) if native_timing else {}))
    config = dict(camera['legacy_boundary_config'], dwell_seconds=.2, cooldown_seconds=2.0)
    boundary = GapTolerantBoundary(config, 3.0, min_observations=3)
    events = []
    with (folder/'frames.jsonl').open('x', encoding='utf-8') as stream:
        for frame in frames:
            obs, states, unmatched = adapter.step(frame)
            record = {k:frame[k] for k in ('pts','native_pts','time_base')}
            record.update(detections=obs, states=states, unmatched=unmatched)
            stream.write(json.dumps(record, allow_nan=False)+'\n')
            events.extend(e | dict(video_id=video_id, condition='gap') for e in boundary.step(frame['pts'], obs))
    save(folder/'events.json', events)
    save(folder/'summary.json', dict(frames=len(frames), candidates=len(events), config=config,
         tracker_buffer_frames=adapter.tracker.max_time_lost, detector_calls=0,
         observed_only_boundary=True, identity_verified=False))


def evidence(video, frames, cards, folder, interval):
    from .run_tracklet_linking import decode_native
    from .mvp_review_evidence import _VideoWriter, _validate_video
    dt = Fraction(frames[1]['native_pts']-frames[0]['native_pts'])*Fraction(frames[0]['time_base'])
    native_timing = abs(interval-1/30) > 1e-9
    if native_timing:
        dt = Fraction(1001,30000)
    tb = Fraction(frames[0]['time_base'])
    windows = [('original', 0, len(frames))]
    for card in cards:
        chosen = [i for i,f in enumerate(frames)
                  if card['first_alert_pts']-3 <= f['pts'] <= card['last_alert_pts']+3]
        windows.append((card['incident_id'], chosen[0], chosen[-1]+1))
    with ExitStack() as stack:
        writers = {}
        for name,first,last in windows:
            native_args = dict(time_base=tb) if native_timing else {}
            writer = _VideoWriter(folder/(name+'.mp4'), frames[0]['source_size'], dt, **native_args)
            stack.callback(writer.close)
            writers[name] = writer
        decoded = 0
        for i,bgr in decode_native(video, frames):
            rgb = bgr[:,:,::-1].copy()
            for name,first,last in windows:
                if first <= i < last:
                    native_args = dict(pts=frames[i]['native_pts']-frames[first]['native_pts']) if native_timing else {}
                    writers[name].write(rgb, **native_args)
            decoded += 1
    if decoded != len(frames):
        raise ValueError('Incomplete exact native source decode')
    media = []
    for name,first,last in windows:
        native_args = dict(expected_pts=[(f['native_pts']-frames[first]['native_pts'])*tb
                                        for f in frames[first:last]]) if native_timing else {}
        meta = _validate_video(folder/(name+'.mp4'), last-first, dt, **native_args)
        media.append(dict(key=name, file=name+'.mp4', source_start_pts=frames[first]['pts'],
                     source_last_pts=frames[last-1]['pts'], source_end_exclusive=frames[last-1]['pts']+interval,
                     incident_id=None if name=='original' else name, **meta))
    save(folder/'media.json', media)
    save(folder/'source-frames.json', [dict(frame_index=i, playback_seconds=(
         float((f['native_pts']-frames[0]['native_pts'])*tb) if native_timing else float(i*dt)),
         **{k:f[k] for k in ('pts','native_pts','time_base')}) for i,f in enumerate(frames)])


def execute(video, camera_id, output, *, cache=None, start=None, end=None, whole=False,
            queue_context=None, camera_registry=None):
    begin = time.perf_counter()
    video,output = Path(video).absolute(),Path(output).absolute()
    camera, selected_scene, portal_path, cameras_path = camera_profile(camera_id, video, camera_registry)
    scene_path = source_scene(camera_id, selected_scene, camera_registry)
    if whole == (start is not None or end is not None):
        raise ValueError('Choose --whole or both --start and --end')
    if (output.is_symlink() or any(p.is_symlink() for p in output.parents)
            or not output.resolve().is_relative_to(ROOT/'outputs')):
        raise ValueError('Output must be a local non-symlink outputs directory')
    output.mkdir(parents=True, exist_ok=True)
    if any((output/name).is_symlink() for name in
           ('.pipeline.lock','status.json','request.json','registration.json','queue-job.json')):
        raise ValueError('Pipeline state files must not be symlinks')
    with (output/'.pipeline.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('This analysis is already running') from exc
        try:
            status(output/'status.json', state='validating', camera_id=camera_id)
            info = probe(video)
            if whole:
                start,end = 0.,info.get('source_end_exclusive', info['duration'])
            if (type(start) not in (int,float) or type(end) not in (int,float)
                    or not all(math.isfinite(x) for x in (start,end))
                    or not 0 <= start < end <= info.get('source_end_exclusive', info['duration'])+1e-6):
                raise ValueError('Finite explicit source PTS window within the video required')
            scene = read(scene_path)
            regions, region_path = scene_regions(scene, scene_path, embedded=camera_registry is not None)
            inputs = dict(video=sha256(video), cameras=sha256(cameras_path), scene=sha256(scene_path),
                          regions=sha256(region_path))
            if portal_path is not None:
                from .portal_births import PortalGate
                PortalGate(read(selected_scene), read(portal_path), camera_id)
                inputs['portal'] = sha256(portal_path)
                inputs['decision_scene'] = sha256(selected_scene)
            request = dict(schema=1, video=str(video), camera_id=camera_id, requested_window=[start,end],
                 scope='whole_video' if whole else 'selected_interval', input_sha256=inputs,
                 code_sha256=code_binding(), policy=dict(approach=asdict(Policy()),
                 relaxed=asdict(RelaxedPolicy()), grouping=asdict(GroupPolicy()),
                 continuation_adopted=False, gap_retention_seconds=3.0),
                 cache=str(Path(cache).absolute()) if cache else None,
                 queue_context=queue_context)
            if camera_registry is not None:
                request['camera_registry'] = str(cameras_path)
            request_path = output/'request.json'
            if request_path.exists():
                if read(request_path) != request:
                    raise ValueError('Resume request/source/settings/code differs; use a new output directory')
            else:
                if any(p.name not in ('.pipeline.lock','status.json') for p in output.iterdir()):
                    raise ValueError('Existing output lacks a matching immutable request')
                save(request_path, request)
            request_sha = sha256(request_path)
            mode = 'saved_cache'
            detector_frames = 0
            if cache is None:
                cache = find_cache(video,camera,start,end,info)
            if cache is None:
                if not queue_context:
                    status(output/'status.json', state='blocked', reason='No matching cache; canonical queue context required',
                           fresh_detector_verified=False, detector_calls=0)
                    return read(output/'status.json')
                from orchestration.video_cards_command import generate_cache
                cache,detector_frames = generate_cache(request_path, output, queue_context)
                mode = 'new_detector_canonical_queue'
            elif (output/'queue-job.json').exists():
                mode = 'new_detector_canonical_queue'
            meta,frames,interval,cache_hashes = validate_cached(video,camera,cache,start,end,info)
            validate_scene_binding(scene,frames,regions,camera)
            binding = dict(request_sha256=request_sha, cache_sha256=cache_hashes,
                           selected_native_pts=[frames[0]['native_pts'],frames[-1]['native_pts']])
            session = 'video-'+fingerprint(dict(source=inputs['video'],camera=camera_id,
                       request=request_sha))[:24]
            video_id = meta['video_id']  # Provenance metadata, never used to infer camera.
            status(output/'status.json', state='tracking', mode=mode)
            tracked,reused_track = stage(output,'tracking',binding,
                lambda p:track(frames,camera,p,interval,video_id))
            def analysis_action(folder):
                measured = [json.loads(s) for s in (tracked/'frames.jsonl').read_text().splitlines()]
                result = enrich_timing(analyze(measured,scene),frames,scene)
                result.update(video_id=video_id, source_size=info['size'],
                     source_window=[frames[0]['pts'],frames[-1]['pts']], frames=len(frames),
                     input_sha256=inputs | dict(cache=cache_hashes),
                     source_paths=dict(video=str(video),frames=str(tracked/'frames.jsonl'),
                                       scene=str(scene_path),cache=str(cache)),
                     existing_alerts=read(tracked/'events.json'))
                result = enrich_timing(add_relaxed_candidates(result,scene,[f['pts'] for f in frames]),frames,scene)
                result.update(continuation_applied=False, detector_calls=0, vlm_calls=0,
                              provenance_scope='new_cpu_analysis_of_validated_detector_cache')
                save(folder/'analysis.json',result)
                bundle = make_bundle(result,camera_id,camera['legacy_boundary_config']['boundary_id'],session)
                bundle.update(analysis_mode=mode, analysis_request_sha256=request_sha,
                              manual_review_status='separate_local_store', continuation_adopted=False)
                save(folder/'cards.json',bundle)
            analysis,reused_analysis = stage(output,'analysis',binding | dict(tracking=sha256(tracked/'stage.json')),
                                            analysis_action)
            bundle = read(analysis/'cards.json')
            status(output/'status.json', state='rendering_original_evidence', mode=mode)
            rendered,reused_evidence = stage(output,'evidence',binding | dict(cards=sha256(analysis/'cards.json')),
                lambda p:evidence(video,frames,bundle['cards'],p,interval))
            media = read(rendered/'media.json')
            registration = dict(schema_version=1, experiment='EXP-0037', session_id=session,
                camera_id=camera_id, gate_id=camera['legacy_boundary_config']['boundary_id'],
                video_id=video_id, cards_path=str(analysis/'cards.json'), cards_sha256=sha256(analysis/'cards.json'),
                analysis_path=str(analysis/'analysis.json'), analysis_sha256=sha256(analysis/'analysis.json'),
                source_path=str(video), source_sha256=inputs['video'], source_window=bundle['source_window'],
                requested_window=[start,end], analysis_scope=request['scope'], analysis_mode=mode,
                display_label='저장 검출 결과 사용' if mode=='saved_cache' else '원본 새 검출 분석',
                source_pts_origin=frames[0]['pts'], playback_pts_origin=0.,
                media=[m | dict(path=str(rendered/m['file'])) for m in media],
                source_frames_path=str(rendered/'source-frames.json'), request_sha256=request_sha,
                counts=bundle['counts'], local_only=True, registration_status='ready_for_existing_service')
            actual_inputs = dict(video=sha256(video), cameras=sha256(cameras_path),
                                 scene=sha256(scene_path), regions=sha256(region_path))
            if portal_path is not None:
                actual_inputs['portal'] = sha256(portal_path)
                actual_inputs['decision_scene'] = sha256(selected_scene)
            if (inputs != actual_inputs
                    or request['code_sha256'] != code_binding()
                    or cache_hashes != dict(cache=sha256(Path(cache)/'person_cache.jsonl'),metadata=sha256(Path(cache)/'run.json'))):
                raise ValueError('Source/settings/code/cache changed during analysis')
            reg = output/'registration.json'
            if reg.exists():
                if read(reg) != registration:
                    raise ValueError('Completed registration differs')
            else: save(reg,registration)
            status(output/'status.json', state='complete', mode=mode, frames=len(frames),
                counts=bundle['counts'], registration_path=str(reg),
                reused_stages=dict(tracking=reused_track,analysis=reused_analysis,evidence=reused_evidence),
                detector_frames_this_execution=detector_frames,
                elapsed_seconds=time.perf_counter()-begin, behavior_accuracy=None,
                independent_video_evaluation='not_performed', realtime=False)
            return read(output/'status.json')
        except Exception as exc:
            status(output/'status.json', state='failed', error_type=type(exc).__name__, error=str(exc))
            raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--camera',required=True)
    p.add_argument('--camera-registry',type=Path)
    p.add_argument('--cache',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--whole',action='store_true')
    p.add_argument('--start',type=float); p.add_argument('--end',type=float)
    p.add_argument('--run-id'); p.add_argument('--task-id'); p.add_argument('--dispatch-id'); p.add_argument('--owner')
    p.add_argument('--register-config',type=Path,help='Existing local service config; additive registration only')
    p.add_argument('--registration-id',help='New explicit existing-service bundle ID')
    a = p.parse_args()
    ids = [a.run_id,a.task_id,a.dispatch_id,a.owner]
    if any(ids) and not all(ids): p.error('All four queue identity flags are required together')
    if bool(a.register_config) != bool(a.registration_id):
        p.error('--register-config and --registration-id are required together')
    context = dict(zip(('run_id','task_id','dispatch_id','owner'),ids)) if all(ids) else None
    result = execute(a.video,a.camera,a.output,cache=a.cache,start=a.start,end=a.end,whole=a.whole,
                     queue_context=context,camera_registry=a.camera_registry)
    if result['state']=='complete' and a.register_config:
        from .video_cards_registration import register
        result['service_registration']=register(a.register_config,a.output/'registration.json',a.registration_id)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['state'] != 'complete': raise SystemExit(2)


if __name__=='__main__': main()
