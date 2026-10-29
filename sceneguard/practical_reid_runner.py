"""Run the single conditionally authorized EXP-0028 cached-detection ReID comparison."""
import argparse
from fractions import Fraction
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

from .gap_boundary import GapTolerantBoundary
from .practical_reid import create_adapter, MODEL_SHA, MODEL_URL
from .replay_gap_tracking import load_cache, sha256, write_json


def native_frames(source, cached):
    """Decode local original media and require exact native PTS/time-base matches."""
    import av
    with av.open(str(source)) as container:
        stream = container.streams.video[0]
        stream.thread_count = 1
        container.seek(cached[0]['native_pts'], stream=stream, backward=True)
        wanted = iter(cached)
        target = next(wanted)
        for video in container.decode(stream):
            if video.pts is None:
                continue
            actual = video.pts * video.time_base
            expected = target['native_pts'] * Fraction(target['time_base'])
            if actual < expected:
                continue
            if (actual != expected or video.pts != target['native_pts']
                    or str(video.time_base) != target['time_base']
                    or abs(float(expected) - target['pts']) > 1e-9):
                raise ValueError('Original/cache native timing mismatch or skipped native frame')
            yield target, video.to_ndarray(format='bgr24')
            target = next(wanted, None)
            if target is None:
                return
        raise ValueError('Original video ended before all cached native frames')


def run(cache_directory, source, output_directory, weights, trigger_evidence):
    """CPU execution only; caller supplies the coordinator's material-break evidence."""
    if not trigger_evidence or not trigger_evidence.strip():
        raise ValueError('Conditional execution requires recorded material ID-break evidence')
    output = Path(output_directory)
    if (not output.resolve().is_relative_to(Path('outputs').resolve()) or output.exists()
            or output.is_symlink() or any(p.is_symlink() for p in output.parents)):
        raise FileExistsError('Use a new non-symlink output directory under outputs/')
    meta, cached, interval, input_hashes = load_cache(cache_directory)
    source = Path(source).resolve(strict=True)
    if sha256(source) != meta['source_sha256']:
        raise ValueError('Original source SHA differs from fixed detection cache')
    if sha256(weights) != MODEL_SHA:
        raise ValueError('Unexpected pretrained encoder SHA')
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    try:
        import torch
        import cv2
        torch.set_num_threads(4)
        cv2.setNumThreads(1)
        adapter = create_adapter(weights, interval)
        config = dict(meta['config'], dwell_seconds=.2, cooldown_seconds=2.)
        boundary = GapTolerantBoundary(config, 3., min_observations=3)
        encoder = adapter.tracker.encoder
        session = encoder.model.session
        manifest = dict(status='frozen', condition='botsort_reid', settings=vars(adapter.tracker.args),
                        trigger_evidence=trigger_evidence, input_sha256=input_hashes,
                        source_sha256=meta['source_sha256'], weights_sha256=MODEL_SHA,
                        weights_url=MODEL_URL, source_model='pretrained FCOS COCO_V1',
                        boundary_config=config, retain_seconds=3., min_observations=3,
                        device=str(encoder.device), providers=session.get_providers(),
                        onnx_input_shape=session.get_inputs()[0].shape,
                        onnx_input_type=session.get_inputs()[0].type,
                        crop_hw=encoder.imgsz, crop_gain=1.02, crop_pad=10,
                        crop_square=False, crop_bgr_to_rgb=True,
                        exact_low_threshold_rows=sum(s==.25 for f in cached for s in f['scores']),
                        onnx_intra_threads=session.get_session_options().intra_op_num_threads,
                        onnx_inter_threads=session.get_session_options().inter_op_num_threads,
                        torch_threads=torch.get_num_threads(), opencv_threads=cv2.getNumThreads(),
                        versions={n: importlib.metadata.version(n) for n in
                                  ('ultralytics','torch','numpy','lap','onnx','onnxruntime')},
                        code_sha256={Path(__file__).name:sha256(__file__),
                                     'practical_reid.py':sha256(Path(__file__).with_name('practical_reid.py'))})
        write_json(output / 'manifest.json', manifest)
        events, gaps, seen, ids = [], [], {}, set()
        observations = count = frames_with_observations = 0
        native_digest = hashlib.sha256()
        with (output / 'frames.jsonl').open('x') as sink:
            for frame, bgr in native_frames(source, cached):
                native_digest.update(bgr.tobytes())
                obs, states, unmatched = adapter.step(frame, bgr)
                emitted = boundary.step(frame['pts'], obs)
                for row in obs:
                    tid = row['track_id']; ids.add(tid)
                    if tid in seen and frame['pts'] - seen[tid] > interval + 1e-6:
                        gaps.append(dict(track_id=tid, before=seen[tid], after=frame['pts'],
                                         seconds=frame['pts']-seen[tid]))
                    seen[tid] = frame['pts']
                count += 1
                observations += len(obs)
                frames_with_observations += bool(obs)
                record = {k:frame[k] for k in ('pts','native_pts','time_base')}
                record.update(detections=obs, states=states, unmatched=unmatched,
                              reid_calls=encoder.calls, reid_patches=encoder.patches)
                sink.write(json.dumps(record, allow_nan=False)+'\n')
                events.extend(e | dict(video_id=meta['video_id'], condition='botsort_reid') for e in emitted)
                if count % 120 == 0:
                    sink.flush()
                    print(json.dumps(dict(video_id=meta['video_id'], frames=count,
                                          patches=encoder.patches, elapsed=time.perf_counter()-started)), flush=True)
        if count != len(cached):
            raise ValueError('Decoded frame count mismatch')
        for name, rows in (('events',events), ('reobservations',gaps)):
            with (output / (name+'.jsonl')).open('x') as stream:
                for row in rows:
                    stream.write(json.dumps(row, allow_nan=False)+'\n')
        if (sha256(Path(cache_directory)/'person_cache.jsonl') != input_hashes['cache']
                or sha256(Path(cache_directory)/'run.json') != input_hashes['metadata']
                or sha256(source) != meta['source_sha256'] or sha256(weights) != MODEL_SHA):
            raise ValueError('Frozen source/cache/weights changed during execution')
        summary = dict(status='complete', condition='botsort_reid', frames=count,
                       observed_boxes=observations, frames_with_observations=frames_with_observations,
                       observed_ids=len(ids), candidates=len(events),
                       bridged_gap_candidates=sum(e.get('bridged_observation_gap',False) for e in events),
                       reobservations_after_gap=len(gaps), boundary_stats=boundary.stats,
                       tracker_buffer_frames=adapter.tracker.max_frames_lost,
                       input_sha256=input_hashes, decoded_bgr_sha256=native_digest.hexdigest(),
                       reid_calls=encoder.calls, reid_patches=encoder.patches,
                       valid_embeddings=encoder.valid_embeddings,
                       elapsed_seconds=time.perf_counter()-started,
                       timing_scope='CPU model setup/decode/crop/ReID/tracking/rules/JSON/hash checks; no detector inference',
                       device=str(encoder.device), providers=session.get_providers(),
                       torch_cuda_initialized=torch.cuda.is_initialized(),
                       uses_finetuned_model=False, uses_reid=True, identity_verified=False,
                       actual_video_review='pending', cctv_accuracy=None,
                       note='Diagnostics, not correct people/crossings; BoT-SORT plus ReID is a package comparison')
        write_json(output/'summary.json', summary)
        return summary
    except Exception as exc:
        write_json(output/'failure.json',dict(status='failed',error_type=type(exc).__name__,error=str(exc)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('clips', nargs='+', choices=['030','007'])
    parser.add_argument('--cache-root', type=Path, default=Path('outputs/cv_phase2d'))
    parser.add_argument('--media-root', type=Path, default=Path('data/TS_침입'))
    parser.add_argument('--output-root', type=Path, default=Path('outputs/exp0028/reid-v1'))
    parser.add_argument('--weights', type=Path, default=Path('weights/exp0028/yolo26n-reid.onnx'))
    parser.add_argument('--trigger-evidence', required=True)
    args = parser.parse_args()
    for clip in args.clips:
        print(json.dumps(run(args.cache_root/('cache'+clip), args.media_root/('E01_'+clip+'.mp4'),
                             args.output_root/('track'+clip)/'botsort_reid', args.weights,
                             args.trigger_evidence), allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
