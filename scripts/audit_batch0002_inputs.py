#!/usr/bin/env python3
"""CPU-only saved-input audit. No model/processor/queue imports or semantic inference.

Only selected source PTS are converted to RGB. Decoder preroll is counted separately.
Public output uses explicit fields; paths and display-only media stay in ignored storage.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CODE = ('scripts/audit_batch0002_inputs.py', 'tests_mvp/test_batch0002_input_audit.py',
        'configs/batch0002_input_audit.json')
OUTPUT = 'outputs/batch0002/input-audit'
RUNTIME = 'runtime/BATCH-0002/input-audit'
PUBLIC = 'records/EXP-0018/input_audit.json'
Q = [('q01', 'E01_007', 'w000001', 0, 5),
     ('q02', 'E01_007', 'w000020', 47.5, 52.5),
     ('q03', 'E01_007', 'w000022', 52.5, 57.5),
     ('q04', 'E01_007', 'w000026', 62.5, 67.5),
     ('q05', 'E01_030', 'w000021', 50, 55),
     ('q06', 'E01_030', 'w000063', 155, 160)]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad(value):
        raise ValueError('nonfinite JSON value')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=bad)


class Reader:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.files = {}
        self.index = {}

    def path(self, name):
        path = self.root / name
        require(not path.is_symlink(), 'symlink input refused')
        path = path.resolve()
        require(path.is_relative_to(self.root), 'input outside repository')
        return path

    def bind(self, name, expected=None, indexed=False):
        path = self.path(name)
        if indexed:
            require(path in self.index, 'input missing from EXP17 index')
            expected = self.index[path]
        digest = file_sha(path)
        require(expected is None or expected == digest, 'input SHA mismatch: ' + path.name)
        require(path not in self.files or self.files[path] == digest, 'input changed')
        self.files[path] = digest
        return path

    def json(self, name, expected=None, indexed=False):
        return strict_json(self.bind(name, expected, indexed).read_bytes())

    def verify(self):
        require(all(file_sha(p) == digest for p, digest in self.files.items()),
                'consumed input changed during audit')


def timing(source):
    pts, native = source['pts_seconds'], source['native_pts']
    bases = source['time_base']
    bases = bases if isinstance(bases, list) else [bases] * len(pts)
    require(len(pts) == len(native) == len(bases) == 10, 'ten observations required')
    require(all(type(p) is int for p in native), 'integer native PTS required')
    require(all(math.isfinite(p) for p in pts), 'finite PTS required')
    require(all(abs(float(Fraction(b) * p) - s) < 1e-6
                for b, p, s in zip(bases, native, pts)), 'native PTS/time base mismatch')
    require(all(a < b for a, b in zip(pts, pts[1:])), 'unordered PTS')
    start, end = source['window_start'], source['window_end']
    require(end - start == 5 and all(start <= p < end for p in pts), 'window mismatch')
    gaps = [b-a for a, b in zip(pts, pts[1:])]
    return dict(pts_seconds=pts, native_pts=native, time_base=bases,
                observed_frames=len(pts), scheduled_seconds=[start, end],
                first_to_last_span_seconds=pts[-1]-pts[0],
                start_to_first_seconds=pts[0]-start, last_to_end_seconds=end-pts[-1],
                adjacent_gap_seconds=gaps, maximum_gap_seconds=max(gaps),
                effective_sample_fps=1/(sum(gaps)/len(gaps)))


def geometry(source, info, shape):
    n, height, width, channels = shape
    require([n, channels, height, width] == info['resized_shape'], 'saved RGB shape mismatch')
    require(channels == 3 and n == 10, 'saved RGB observations mismatch')
    for a, b in [('source_pts', 'pts_seconds'), ('native_pts', 'native_pts'),
                 ('time_base', 'time_base'), ('source_size', 'source_size'), ('roi', 'roi'),
                 ('window_start', 'window_start'), ('window_end', 'window_end')]:
        require(info[a] == source[b], 'processor/source metadata mismatch: ' + a)
    require(info['observed_frames'] == info['processor_frames'] == n
            and info['extra_sampling'] is False and info['temporal_padding_frames'] == 0,
            'unrecorded sampling or padding')
    sw, sh = source['source_size']
    roi = source['roi']
    require(len(roi) == 4 and 0 <= roi[0] < roi[2] <= 1
            and 0 <= roi[1] < roi[3] <= 1, 'invalid ROI')
    bounds = [math.floor(roi[0]*sw), math.floor(roi[1]*sh),
              math.ceil(roi[2]*sw), math.ceil(roi[3]*sh)]
    require(bounds == info['crop_bounds_xyxy'], 'ROI integer bounds mismatch')
    cw, ch = bounds[2]-bounds[0], bounds[3]-bounds[1]
    require(info['cropped_shape'] == [n, ch, cw, 3], 'crop shape mismatch')
    grid = info['video_grid_thw']
    require(len(grid) == 1 and grid[0][0]*2 == n
            and grid[0][1]*16 == height and grid[0][2]*16 == width
            and math.prod(grid[0])//4 == info['visual_tokens'], 'visual grid/token mismatch')
    require(info['processor_timestamp_coordinates'] == [
        (p-source['window_start'])*source['fps'] for p in source['pts_seconds']],
        'processor timestamp coordinate mismatch')
    return dict(source_wh=[sw, sh], crop_bounds_xyxy=bounds, crop_wh=[cw, ch],
                roi_normalized=roi, source_area_retained_fraction=cw*ch/(sw*sh),
                saved_processor_wh=[width, height],
                resize_xy_scale=[width/cw, height/ch],
                visual_tokens=info['visual_tokens'], input_tokens=info['input_tokens'],
                video_grid_thw=grid, temporal_patch_frames=2,
                processor_timestamp_coordinates=info['processor_timestamp_coordinates'],
                processor_timestamp_quantization=info['processor_timestamp_quantization'],
                extra_sampling=False, temporal_padding_frames=0,
                person_size_pixels=None, person_size_reason='no documented human location boxes for these exact q/v samples',
                action_visible=None, action_vs_approach_distinguishable=None,
                actual_input_human_review='not_performed')


def project_location(box, preview_wh, source_wh, crop, output_wh):
    """Geometry of a prior manual diagnostic rectangle, never a person GT box."""
    sx, sy = source_wh[0]/preview_wh[0], source_wh[1]/preview_wh[1]
    x1, y1, x2, y2 = [v*s for v, s in zip(box, [sx, sy, sx, sy])]
    require(x2 > x1 and y2 > y1, 'invalid prior review rectangle')
    cw, ch = crop[2]-crop[0], crop[3]-crop[1]
    ix, iy = max(0, min(x2, crop[2])-max(x1, crop[0])), max(0, min(y2, crop[3])-max(y1, crop[1]))
    return dict(source_rectangle_wh=[x2-x1, y2-y1],
                rectangle_area_retained_fraction=ix*iy/((x2-x1)*(y2-y1)),
                projected_visible_rectangle_wh=[ix*output_wh[0]/cw, iy*output_wh[1]/ch],
                interpretation='approximate prior Codex manual review region, not user-provided person bbox, not GT')


def exact_frames(path, wanted):
    """Seek per selected native PTS; never convert/export preroll frames."""
    import av
    frames, inventory = {}, []
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = 'NONE'
        for native, base in sorted(wanted):
            require(Fraction(base) == stream.time_base, 'decoder time base differs')
            container.seek(native, stream=stream, backward=True, any_frame=False)
            traversed = 0
            for frame in container.decode(stream):
                traversed += 1
                if frame.pts is None or frame.pts < native:
                    continue
                require(frame.pts == native, 'exact requested native PTS absent')
                rgb = frame.to_ndarray(format='rgb24')
                frames[(native, base)] = rgb
                inventory.append(dict(native_pts=native, time_base=base,
                                      pts_seconds=float(Fraction(base)*native),
                                      rgb_sha256=sha(rgb.tobytes()), source_wh=[frame.width, frame.height],
                                      decoded_frames_including_seek_preroll=traversed))
                break
            else:
                raise ValueError('decoder EOF before selected PTS')
    return frames, inventory


def collect(reader, config):
    """Read only metadata and exact cached RGB; no model output fields become evidence."""
    import numpy as np
    for name, digest in config['pins'].items():
        reader.bind(name, digest)
    idx = reader.json(config['saved_file_index'])
    reader.index = {reader.path(x['path']):x['sha256'] for x in idx['files']}
    require(len(reader.index) == len(idx['files']), 'duplicate saved-file index entry')
    run = reader.json(config['run_index'], indexed=True)
    require(run['experiment'] == 'EXP-0017' and run['state'] == 'completed', 'unfinished EXP17')
    jobs = {(j['phase'], j['view']):reader.path(j['output_path']) for j in run['jobs']}
    require(len(jobs) == 4 and all(j['state'] == 'succeeded' for j in run['jobs']), 'incomplete EXP17 jobs')
    parents = reader.json('records/EXP-0015/window_reviews.json')
    vmanifest = reader.json('configs/mvp_exp0016_independent_manifest.json')
    vlabels = reader.json('configs/mvp_exp0016_independent_evaluation.json')['labels']
    rows, requests, source_hashes = [], defaultdict(set), {}
    def add(qid, sid, wid, directory, condition, label, old=None):
        source = reader.json(directory/'input.json', indexed=True)
        info = reader.json(directory/'result.json', indexed=True)['input_metadata']
        path = reader.bind(directory/'processor_rgb.npy', indexed=True)
        pixels = np.load(path, allow_pickle=False)
        require(pixels.dtype == np.uint8 and pixels.ndim == 4, 'uint8 RGB required')
        tm = timing(source)
        geo = geometry(source, info, pixels.shape)
        require(sid not in source_hashes or source_hashes[sid] == source['source_sha256'], 'source hash varies')
        source_hashes[sid] = source['source_sha256']
        requests[sid].update(zip(tm['native_pts'], tm['time_base']))
        row = dict(review_id=qid, source_id=sid, window_id=wid, condition=condition,
                   prior_user_clip_label=label, timing=tm, geometry=geo,
                   source_sha256=source['source_sha256'],
                   saved_input_metadata_file_sha256=file_sha(directory/'input.json'),
                   saved_result_metadata_file_sha256=file_sha(directory/'result.json'),
                   recorded_source_aggregate_RGB_sha256=source.get('rgb_sha256'),
                   recorded_crop_RGB_sha256=info['crop_sha256'],
                   saved_processor_file_sha256=file_sha(path), saved_processor_payload_sha256=sha(pixels.tobytes()),
                   saved_processor_frame_sha256=[sha(p.tobytes()) for p in pixels],
                   historical_q_processor_RGB='unavailable_not_saved' if old else 'not_applicable')
        if old:
            historical = reader.path(config['historical_q_roots'][old['method']])/sid/'windows'/wid
            old_input = reader.json(historical/'input.json', old['provenance']['input_file_sha256'])
            old_info = reader.json(historical/'result.json', old['provenance']['result_file_sha256'])['input_metadata']
            require(not (historical/'processor_rgb.npy').exists(), 'historical RGB availability changed; revise contract')
            require(old_input['pts_seconds'] == source['pts_seconds']
                    and old_input['native_pts'] == source['native_pts']
                    and old_input['time_base'] == source['time_base']
                    and old_input['rgb_sha256'] == source['rgb_sha256'] == old['decoded_source_rgb_sha256'],
                    'historical q source timing/RGB differs')
            require({k:v for k,v in old_info.items() if k != 'input_tokens'} ==
                    {k:v for k,v in info.items() if k != 'input_tokens'}, 'historical visual metadata differs')
            row['historical_q_recorded_visual_metadata_equal'] = True
            row['historical_q_actual_processor_pixel_equality'] = 'not_established'
        rows.append((row, source, info, pixels))
    for method, view in [('B', 'full_frame'), ('C', 'fixed_roi')]:
        for qid, sid, wid, start, end in Q:
            matches = [p for p in parents if p['method'] == method and
                       p.get('user_label_revision', {}).get('user_label', {}).get('review_clip_id') == qid]
            require(len(matches) == 1, 'missing/duplicate q reference')
            old = matches[0]
            label = old['user_label_revision']['user_label']
            require((label['source_id'], label['window_id'], label['interval_seconds']) ==
                    (sid, wid, [start, end]), 'q label mapping differs')
            add(qid, sid, wid, jobs[('prompt-regression',view)]/sid/'windows'/wid,
                'q_'+method+'_EXP0017_saved', label, old)
    for phase in ['independent-original', 'independent-revised']:
        for label in vlabels:
            frozen = next(w for w in vmanifest['windows'] if w['window_id'] == label['window_id'])
            sid, wid = frozen['source_id'], frozen['window_id']
            add(label['review_clip_id'], sid, wid, jobs[(phase,'full_frame')]/'windows'/wid,
                'v_'+phase.split('-')[1]+'_EXP0017_saved', label)
            source = rows[-1][1]
            require(all(source[k] == v for k,v in frozen['timing'].items())
                    and source['frame_sha256'] == frozen['frame_sha256'], 'v manifest binding differs')
    require(len(rows) == 20, '20 saved input variants required')
    return rows, requests, source_hashes


def verify_pixels(source, info, rgb):
    """Source decode and crop hashes are independent of saved processor RGB."""
    import numpy as np
    frames = [rgb[(p,b)] for p,b in zip(source['native_pts'], source['time_base'])]
    stacked = np.stack(frames)
    require(stacked.shape[1:3] == tuple(reversed(source['source_size'])), 'decoded source size differs')
    if 'rgb_sha256' in source:
        require(sha(stacked.tobytes()) == source['rgb_sha256'], 'decoded source RGB differs')
    else:
        require([sha(f.tobytes()) for f in frames] == source['frame_sha256'], 'source frame RGB differs')
    x1,y1,x2,y2 = info['crop_bounds_xyxy']
    require(sha(stacked[:, y1:y2, x1:x2].tobytes()) == info['crop_sha256'], 'decoded crop differs')
    return [sha(f.tobytes()) for f in frames]


def render_sheet(destination, row, originals, pixels):
    """Display only: original source and exact saved processor RGB, never inference crops."""
    from PIL import Image, ImageDraw
    canvas = Image.new('RGB', (1280, 10*285), 'black')
    draw = ImageDraw.Draw(canvas)
    for i, pts in enumerate(row['timing']['pts_seconds']):
        top = i*285
        draw.text((8,top+5), f"{row['review_id']} {row['condition']} | ORIGINAL PTS {pts:.6f}s | native {row['timing']['native_pts'][i]} x {row['timing']['time_base'][i]}", fill='white')
        draw.text((8,top+21), 'SOURCE (display resized) | right: EXACT SAVED processor RGB (display resized); known 2fps; no semantic review',fill='white')
        for j, array in enumerate([originals[i], pixels[i]]):
            image = Image.fromarray(array)
            image.thumbnail((630,240))
            canvas.paste(image, (j*640, top+40))
    canvas.save(destination, quality=92)


def render_review_clip(destination, review_id, variants, decoded):
    """One 5-second local display clip; all panels show the SAME known 2fps PTS."""
    import av
    import numpy as np
    from PIL import Image, ImageDraw
    row, source, _, _ = variants[0]
    width, height = 640*(len(variants)+1), 440
    with av.open(str(destination), mode='w') as container:
        stream = container.add_stream('libx264', rate=2)
        stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
        stream.options = {'crf':'18', 'preset':'fast'}
        for i, pts in enumerate(source['pts_seconds']):
            canvas = Image.new('RGB',(width,height),'black')
            draw = ImageDraw.Draw(canvas)
            draw.text((8,8), f"{review_id} | ORIGINAL PTS {pts:.6f}s | SAME 2fps samples in every panel; no interpolation",fill='white')
            draw.text((8,26), 'Display resized only. Prior full-rate clip label is separate; exact sampled-input action adequacy UNKNOWN.',fill='white')
            native = decoded[row['source_id']][(source['native_pts'][i],source['time_base'][i])]
            panels = [('SOURCE native sampled frame',native)] + [(r['condition'],pixels[i]) for r,_,_,pixels in variants]
            for j,(label,pixels) in enumerate(panels):
                draw.text((j*640+8,55),label,fill='white')
                draw.text((j*640+8,72),f"native {source['native_pts'][i]} x {source['time_base'][i]} | pixels {pixels.shape[1]}x{pixels.shape[0]}",fill='white')
                image = Image.fromarray(pixels);image.thumbnail((632,350))
                canvas.paste(image,(j*640+4,92))
            frame = av.VideoFrame.from_ndarray(np.array(canvas), format='rgb24')
            frame.pts, frame.time_base = i, Fraction(1,2)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def same_pairs(rows):
    for qid in [q[0] for q in Q] + ['v01','v02','v03','v04']:
        pair = [r for r in rows if r['review_id'] == qid]
        require(len(pair) == 2 and pair[0]['timing'] == pair[1]['timing']
                and pair[0]['source_frame_sha256'] == pair[1]['source_frame_sha256'], 'paired source differs')
        if qid.startswith('v'):
            require(pair[0]['saved_processor_file_sha256'] == pair[1]['saved_processor_file_sha256'],
                    'v saved processor pixels differ')


def safe_write(root, name, raw):
    path = Path(root)/name
    require(path.resolve().is_relative_to(Path(root).resolve()), 'output outside repository')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink output refused')
    if path.exists():
        require(path.stat().st_nlink == 1 and path.read_bytes() == raw, 'refusing changed existing output')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def freeze(root, commit):
    actual = subprocess.check_output(['git','rev-parse',commit],cwd=root,text=True).strip()
    require(len(actual) == 40, 'full source commit required')
    hashes = {}
    for name in CODE:
        committed = subprocess.check_output(['git','show',actual+':'+name],cwd=root)
        require(committed == (Path(root)/name).read_bytes(), 'audit source differs from frozen commit')
        hashes[name] = sha(committed)
    return actual, hashes


def audit(root, commit):
    import av
    import numpy as np
    from PIL import __version__ as pillow_version
    root = Path(root).resolve()
    commit, code_hashes = freeze(root, commit)
    # Fresh output namespace only; no historical artifacts are overwritten.
    for name in [OUTPUT, RUNTIME]:
        path = root/name
        require(not path.exists() and not path.is_symlink(), 'audit namespace already exists')
        require(not any(p.is_symlink() for p in path.parents), 'symlink output parent')
    require(not (root/PUBLIC).exists(), 'public result already exists')
    reader = Reader(root)
    config = reader.json(CODE[2])
    rows, requests, source_hashes = collect(reader, config)
    diagnostics = []
    locations = reader.json(config['prior_review_locations'])
    for sid, seconds in config['diagnostic_instants'].items():
        cv = reader.json(config['prior_cv_runs'][sid]+'/run.json')
        require(cv['source_sha256'] == source_hashes[sid], 'prior CV/source differs')
        frames_path = reader.bind(config['prior_cv_runs'][sid]+'/frames.jsonl')
        frames = [strict_json(line) for line in frames_path.read_bytes().splitlines()]
        for t in seconds:
            matches = [f for f in frames if f['pts'] == t]
            require(len(matches) == 1, 'diagnostic PTS not in prior CV cache')
            f = matches[0]
            requests[sid].add((f['native_pts'], f['time_base']))
            diagnostic = dict(source_id=sid, pts_seconds=t, native_pts=f['native_pts'], time_base=f['time_base'],
                              prior_review_reference='EXP-0002/0003 diagnostic only; no GT or input selection by model boxes',
                              exact_actual_processor_RGB='not_saved' if sid == 'E01_030' else 'q04 B/C EXP17 saved',
                              action_visible=None, actual_input_human_review='not_performed', manual_location_projections=[])
            if sid == 'E01_030':
                wid = config['diagnostic_historical_windows'][str(t)]
                for method in ['B','C']:
                    directory = reader.path(config['historical_q_roots'][method])/sid/'windows'/wid
                    old_source = reader.json(directory/'input.json')
                    info = reader.json(directory/'result.json')['input_metadata']
                    require(t in old_source['pts_seconds'], 'diagnostic not in historical sampled metadata')
                    require(not (directory/'processor_rgb.npy').exists(), 'diagnostic pixel availability changed')
                    for name, box in locations.get(str(t),{}).items():
                        diagnostic['manual_location_projections'].append(dict(
                            method=method, location_alias=name, prior_author=locations['author'],
                            prior_coordinate_space=locations['coordinate_space'],
                            **project_location(box, [960,540], info['source_size'], info['crop_bounds_xyxy'],
                                               [info['resized_shape'][3],info['resized_shape'][2]])))
            diagnostics.append(diagnostic)
    require(sum(map(len, requests.values())) == config['maximum_unique_selected_source_frames'],
            'selected source frame inventory differs from frozen scope')
    decoded, inventory = {}, []
    for sid, wanted in sorted(requests.items()):
        path = reader.bind(config['source_paths'][sid], source_hashes[sid])
        decoded[sid], entries = exact_frames(path, wanted)
        inventory.extend(dict(source_id=sid, **entry) for entry in entries)
    public_rows = []
    for row, source, info, pixels in rows:
        rgb = decoded[row['source_id']]
        row['source_frame_sha256'] = verify_pixels(source, info, rgb)
        row['decoded_source_and_crop_hashes_verified'] = True
        public_rows.append(row)
    same_pairs(public_rows)
    # Verify consumed bytes before any output, including original media.
    reader.verify()
    for name in [OUTPUT, RUNTIME]:
        (root/name).mkdir(parents=True, exist_ok=False)
    for row, source, info, pixels in rows:
        rgb = decoded[row['source_id']]
        original = [rgb[(p,b)] for p,b in zip(source['native_pts'],source['time_base'])]
        render_sheet(root/OUTPUT/(row['review_id']+'-'+row['condition']+'.jpg'),row,original,pixels)
    bundle = []
    for qid in config['bounded_human_check']:
        variants = [v for v in rows if v[0]['review_id'] == qid
                    and (qid.startswith('q') or v[0]['condition'] == 'v_original_EXP0017_saved')]
        name = qid+'-source-versus-actual.mp4'
        render_review_clip(root/OUTPUT/name,qid,variants,decoded)
        bundle.append(dict(review_id=qid, local_clip=name,
                           source_panel_sampling='same 10 native frames at 2fps, not full-rate source playback',
                           processor_panels=[v[0]['condition'] for v in variants],
                           actual_input_action_adequacy='unknown_pending_human_view'))
    safe_write(root, OUTPUT+'/human-check-bundle.local.json',encoded(dict(
        clips=bundle, request_count=1, question='For q04/v01/v03, do exact actual samples show body lift/leg-over or boundary-relative progress distinct from approach, or insufficient/uncertain? If clear, list PTS. Prior original-clip labels are retained; completion is not being re-labeled.')))
    # Diagnostic originals only; no synthetic processor pixels masquerade as actual inputs.
    from PIL import Image, ImageDraw
    for d in diagnostics:
        image = Image.fromarray(decoded[d['source_id']][(d['native_pts'],d['time_base'])])
        image.thumbnail((960,540))
        canvas = Image.new('RGB',(960,580),'black');canvas.paste(image,(0,40))
        ImageDraw.Draw(canvas).text((8,8),f"{d['source_id']} ORIGINAL PTS {d['pts_seconds']} | DIAGNOSTIC ONLY; actual processor pixels not shown",fill='white')
        canvas.save(root/OUTPUT/(d['source_id']+'-'+str(d['pts_seconds'])+'-source.jpg'),quality=92)
    reader.verify()
    result = dict(schema_version=1, experiment_id='EXP-0018', batch_id='BATCH-0002',
                  scope='CPU saved-input and selected-source audit; development diagnostics only',
                  source_commit=commit, source_file_sha256=code_hashes,
                  environment=dict(python=sys.version.split()[0],av=av.__version__,numpy=np.__version__,
                                   pillow=pillow_version, ffmpeg_libraries={k:list(v) for k,v in av.library_versions.items()}),
                  measurements=dict(unique_scheduled_windows=10, saved_processor_variants=20,
                                    unique_source_frames=len(inventory),saved_processor_frame_observations=200,
                                    decoder_frames_including_repeated_seek_preroll=sum(i['decoded_frames_including_seek_preroll'] for i in inventory),
                                    later_CV_comparison_frames_executed=0),
                  inputs=public_rows, diagnostic_instants=diagnostics, selected_source_frame_inventory=inventory,
                  prior_locations=dict(file_sha256=file_sha(reader.path(config['prior_review_locations'])),
                                       source=locations['author'], ground_truth=False, inference_crop=False),
                  native_CV_feasibility=dict(
                      status='grounded_for_tiny_native_frame_comparison_at03084_and90',
                      prior_human_review=config['prior_native_user_review'],
                      exact_source_SHA_and_native_PTS_bound=True,
                      measured_here='native RGB hashes and prior CV cache native PTS only',
                      semantic_review_here=False,
                      note='Prior user native-frame observations support detector diagnostics independently of unknown Qwen sampled/downsized adequacy; do not treat approximate rectangles as GT.'),
                  gate_recommendation=dict(status='hold_semantic_input_sufficiency_pending_small_human_check',
                      exact_inputs_distinguish_action_from_approach='unknown',
                      metadata_proves='source/native PTS, saved RGB, crop, resize, tokens and sampling only',
                      sampling_or_scale_caused_failures='not_established',
                      human_check=dict(review_ids=['q04','v01','v03'], bundled_request_count=1,
                        instruction='View local source-versus-actual saved-input sheets for q04 B/C and v01/v03 full-frame. For each, say whether actual samples show body lift/leg-over or boundary-relative progress distinct from approach, or insufficient/uncertain; list visible PTS if clear. Do not re-label the original clips or infer completion; v03 boundary relation remains ambiguous.'),
                      coordinator_owns_final_gate=True),
                  semantic_review=dict(performed=False, raw_media_sent_to_agent_image_tools=False,
                                       model_predictions_used_as_GT=False, prior_clip_labels_are_sample_adequacy=False),
                  limitations=['Historical q processor RGB absent: metadata equality does not establish past pixel equality.',
                               'Diagnostic030 processor pixels absent; manual-region projection is geometric, not a measured person bbox or action observation.',
                               'No documented coordinate boxes for q/v,03094,00764/66: exact person size unavailable.',
                               'Official resize is described by saved metadata; this audit does not recompute processor transforms or hidden tensors.',
                               'Display sheets rescale both panels for viewing only; exact cached RGB bytes are separately bound.',
                               '10 selected development windows, shared sources; no accuracy/F1 or generalization inference.',
                               'Seek preroll frames are decoded internally but not RGB-converted, selected or exported. 240-frame CV budget is a separate later stage.'])
    safe_write(root, PUBLIC, encoded(result))
    safe_write(root, RUNTIME+'/consumed-files.local.json',encoded(dict(
        source_commit=commit,files=[dict(path=str(p),sha256=d) for p,d in sorted(reader.files.items())],
        display_artifacts=[dict(path=str(p),sha256=file_sha(p)) for p in sorted((root/OUTPUT).iterdir())])))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--source-commit',required=True,help='Coordinator-committed code freeze, checked byte for byte')
    args = parser.parse_args(argv)
    result = audit(args.root,args.source_commit)
    print(json.dumps(dict(experiment_id=result['experiment_id'],measurements=result['measurements'],
                          gate=result['gate_recommendation']['status']),sort_keys=True))


if __name__ == '__main__':
    main()
