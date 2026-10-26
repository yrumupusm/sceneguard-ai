"""Phase 1B: inspect pinned annotations and exactly eight local-only clips.
Run with uv run --no-project --with imageio-ffmpeg==0.6.0 --with pillow==12.3.0.
No models, dataset-wide media download, or upload operations are performed.
Use --details-only to regenerate only the declared close-inspection windows.
"""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

import imageio_ffmpeg
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / 'data/isafetybench_audit'
HF = '8336f1c57076d598677effa1da9870b300790804'
GH = '01dc96e882aa9e615d2eb6e13050be753f24a8c1'
HUB = 'https://huggingface.co/datasets/raiyaanabdullah/isafety-bench'
RAW = f'https://raw.githubusercontent.com/iSafetyBench/data/{GH}'
# Deliberate coverage sample, selected from annotations before viewing the clips.
SELECTION = [
    ('hazard', '-0zRCAh9_N4_trim_0.mp4', 'structural collapse'),
    ('hazard', '-NF8DZCdcUQ_trim_1.mp4', 'forklift and shelves'),
    ('hazard', '-BzGMvclD88_trim_1.mp4', 'fall and assistance'),
    ('hazard', '_2tSBxyAwLs_trim_25.mp4', 'fire and response'),
    ('normal', '_g7R05NOikU_trim_0.mp4', 'routine vehicle operation'),
    ('normal', '_Juow4q7js0_trim_2.mp4', 'routine assembly'),
    ('normal', '3hOGpHBJ0e4_trim_0.mp4', 'normal group with person-fall caption'),
    ('normal', 'oyRnP9p0KIs_trim_44.mp4', 'normal group: object-fall caption versus falling-down tag'),
]


def fetch(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_suffix(dest.suffix + '.part')
        with urllib.request.urlopen(url, timeout=90) as response, partial.open('wb') as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        partial.replace(dest)
    return dest


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def source_candidate(name):
    # Filename convention only; not verified against original YouTube metadata.
    return re.sub(r'(?:_clip\d+)?_trim_\d+\.mp4$', '', name)


def inspect_annotations():
    for name in ['README.md', 'LICENSE', 'actions.txt', 'annotations_hazard.json', 'annotations_normal.json']:
        fetch(f'{RAW}/{name}', ROOT / name)
    fetch(f'{HUB}/resolve/{HF}/README.md', ROOT / 'HF_README.md')
    taxonomy = {}
    for node in ast.parse((ROOT / 'actions.txt').read_text()).body:
        if isinstance(node, ast.Assign):
            taxonomy[node.targets[0].id] = ast.literal_eval(node.value)
    annotations, files, stats, hashes = {}, {}, {}, defaultdict(list)
    for group in ['hazard', 'normal']:
        annotations[group] = json.loads((ROOT / f'annotations_{group}.json').read_text())
        url = f'https://huggingface.co/api/datasets/raiyaanabdullah/isafety-bench/tree/{HF}/{group}?recursive=true&limit=1000'
        # These pinned directories fit on one API page. Fail rather than silently truncate.
        with urllib.request.urlopen(url, timeout=90) as response:
            if response.headers.get('Link'):
                raise RuntimeError('Unexpected pagination: inspect before continuing')
            listing = json.load(response)
        save(f'files_{group}.json', listing)
        files[group] = {Path(f['path']).name: f for f in listing if f['type'] == 'file'}
        rows = annotations[group]
        names = [r['video_name'] for r in rows]
        if len(set(names)) != len(names) or set(names) != set(files[group]):
            raise RuntimeError('Annotation/media mapping is not one-to-one')
        counts = Counter(t for r in rows for t in r['gt_actions'])
        groups = Counter(source_candidate(n) for n in names)
        for f in files[group].values():
            hashes[f['lfs']['oid']].append(f['path'])
        stats[group] = {
            'rows': len(rows), 'keys': sorted(set().union(*(r.keys() for r in rows))),
            'multi_action_clips': sum(len(r['gt_actions']) > 1 for r in rows),
            'action_instances': sum(counts.values()), 'distinct_actions': len(counts),
            'action_counts': dict(counts), 'singleton_actions': sum(v == 1 for v in counts.values()),
            'source_candidates': len(groups), 'source_groups': dict(groups),
            'repeated_source_groups': sum(v > 1 for v in groups.values()),
            'clips_in_repeated_groups': sum(v for v in groups.values() if v > 1),
            'malformed_source_candidates': [k for k in groups if not re.fullmatch(r'[\w-]{11}', k)],
            'empty_captions': sum(not r['caption'].strip() for r in rows),
            'empty_action_lists': sum(not r['gt_actions'] for r in rows),
        }
    stats['cross_group_source_candidates'] = sorted(set(stats['hazard']['source_groups']) & set(stats['normal']['source_groups']))
    stats['duplicate_media_hashes'] = [v for v in hashes.values() if len(v) > 1]
    stats['taxonomy'] = {key: {'categories': len(value), 'actions': sum(len(v) for v in value.values())} for key, value in taxonomy.items()}
    allowed = {t for d in taxonomy.values() for values in d.values() for t in values}
    stats['unknown_tags'] = sorted({t for a in annotations.values() for r in a for t in r['gt_actions']} - allowed)
    stats['mcq'] = {}
    for group in ['normal', 'hazard']:
        for kind in ['multi', 'single']:
            name = f'{group}_mcq_{kind}.json'
            q = json.loads(fetch(f'{RAW}/mcq/{name}', ROOT / name).read_text())
            truth = {r['video_name']: set(r['gt_actions']) for r in annotations[group]}
            invalid = []
            for row in q:
                chosen = set(row['chosen_gt_actions']) if kind == 'multi' else {row['chosen_gt_action']}
                indices = row['answer_indices'] if kind == 'multi' else [row['answer_index']]
                if (len(row['choices']) != 16
                        or chosen | set(row['other_gt_actions']) != truth.get(row['video_name'])
                        or len(indices) != len(chosen)
                        or not all(isinstance(i, int) and 0 <= i < 16 for i in indices)):
                    invalid.append(row['video_name'])
            stats['mcq'][name] = {
                'count': len(q), 'keys': sorted(set().union(*(r.keys() for r in q))),
                'unique_videos': len({r['video_name'] for r in q}),
                'nonempty_other_gt_actions': sum(bool(r['other_gt_actions']) for r in q),
                'invalid_structure_or_tag_coverage': invalid,
            }
            if invalid:
                raise RuntimeError(f'MCQ integrity check failed: {name}')
    save('annotation_report.json', stats)
    return annotations, files


def inspect_clip(group, name, reason, annotation, listing, ffmpeg):
    url = f'{HUB}/resolve/{HF}/{group}/{name}'
    path = fetch(url, ROOT / 'videos' / group / name)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stat().st_size != listing['size'] or digest != listing['lfs']['oid']:
        raise RuntimeError(f'Size or upstream LFS SHA256 mismatch: {name}')
    stream = imageio_ffmpeg.read_frames(str(path), pix_fmt='rgb24')
    metadata = next(stream)
    count = sum(1 for _ in stream)
    if count == 0:
        raise RuntimeError(f'No frames: {name}')
    check = subprocess.run([ffmpeg, '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'], capture_output=True, text=True, check=True)
    # Save frames and sample PTS in one sequential decode, approximately 0.5 s apart, including the final frame.
    # No AI model is used for decoding or the contact sheets.
    out = ROOT / 'previews' / group / path.stem
    out.mkdir(parents=True, exist_ok=True)
    step = max(1, round(metadata['fps'] / 2))
    command = [ffmpeg, '-hide_banner', '-i', str(path), '-vf', f'select=not(mod(n\\,{step}))+eq(n\\,{count-1}),showinfo', '-fps_mode', 'vfr', '-y', str(out / '%03d.png')]
    extracted = subprocess.run(command, capture_output=True, text=True, check=True)
    times = [float(t) for t in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)', extracted.stderr)]
    images = sorted(out.glob('[0-9][0-9][0-9].png'))
    if len(images) != len(times):
        raise RuntimeError(f'Preview PTS mismatch: {name}')
    for start in range(0, len(images), 12):
        subset = images[start:start + 12]
        sheet = Image.new('RGB', (1120, 6 * 335), 'white')
        draw = ImageDraw.Draw(sheet)
        for j, file in enumerate(subset):
            x, y = (j % 2) * 560, (j // 2) * 335
            with Image.open(file) as im:
                im.thumbnail((560, 310))
                sheet.paste(im, (x, y + 24))
            draw.text((x + 5, y + 4), f'{name} | PTS {times[start+j]:.3f}s', fill='black')
        sheet.save(out / f'sheet_{start//12}.jpg')
    return {'group': group, 'video_name': name, 'selection_reason': reason,
            'source_candidate': source_candidate(name), 'url': url, 'sha256': digest,
            'bytes': path.stat().st_size, 'annotation': annotation, 'metadata': metadata,
            'decoded_frames': count, 'decode_errors': check.stderr, 'preview_pts': times}



# Fixed follow-up windows motivated by the initial contact-sheet audit.
DETAIL_WINDOWS = {
    '-0zRCAh9_N4_trim_0.mp4': (5.1, 6.1),
    '-NF8DZCdcUQ_trim_1.mp4': (4.7, 6.1),
    '-BzGMvclD88_trim_1.mp4': (4.2, 5.1),
    '3hOGpHBJ0e4_trim_0.mp4': (0.4, 1.8),
    'oyRnP9p0KIs_trim_44.mp4': (0.6, 2.0),
}


def inspect_details(manifest, ffmpeg):
    records = []
    for sample in manifest['samples']:
        name = sample['video_name']
        if name not in DETAIL_WINDOWS:
            continue
        start, end = DETAIL_WINDOWS[name]
        path = ROOT / 'videos' / sample['group'] / name
        out = ROOT / 'details' / Path(name).stem
        out.mkdir(parents=True, exist_ok=True)
        step = max(1, round(sample['metadata']['fps'] / 10))
        vf = f'select=between(t\\,{start}\\,{end})*not(mod(n\\,{step})),showinfo'
        run = subprocess.run([ffmpeg, '-hide_banner', '-i', str(path), '-vf', vf, '-fps_mode', 'vfr', '-y', str(out / '%03d.png')], capture_output=True, text=True, check=True)
        times = [float(t) for t in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)', run.stderr)]
        images = sorted(out.glob('[0-9][0-9][0-9].png'))
        if len(images) != len(times):
            raise RuntimeError(f'Detail PTS mismatch: {name}')
        for base in range(0, len(images), 12):
            sheet = Image.new('RGB', (1120, 6 * 335), 'white')
            draw = ImageDraw.Draw(sheet)
            for j, file in enumerate(images[base:base+12]):
                x, y = (j % 2) * 560, (j // 2) * 335
                with Image.open(file) as im:
                    im.thumbnail((560, 310))
                    sheet.paste(im, (x, y + 24))
                draw.text((x+5, y+4), f'{name} | PTS {times[base+j]:.3f}s', fill='black')
            sheet.save(out / f'sheet_{base//12}.jpg')
        records.append({'video_name': name, 'requested_window': [start,end], 'pts': times})
    save('detail_windows.json', records)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    save('revisions.json', {'hf': HF, 'github': GH})
    annotations, files = inspect_annotations()
    assert len(SELECTION) == len({(g,n) for g,n,_ in SELECTION}) == 8
    manifest = {'hf_revision': HF, 'github_revision': GH, 'samples': []}
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for group, name, reason in SELECTION:
        annotation = next(r for r in annotations[group] if r['video_name'] == name)
        row = inspect_clip(group, name, reason, annotation, files[group][name], ffmpeg)
        manifest['samples'].append(row)
        save('manifest.json', manifest)
        print(group, name, row['metadata']['size'], row['metadata']['fps'], row['metadata']['duration'], row['decoded_frames'], flush=True)
    inspect_details(manifest, ffmpeg)
    print('Total bytes:', sum(r['bytes'] for r in manifest['samples']))


if __name__ == '__main__':
    if sys.argv[1:] == ['--details-only']:
        inspect_details(json.loads((ROOT / 'manifest.json').read_text()), imageio_ffmpeg.get_ffmpeg_exe())
    elif sys.argv[1:] == ['--metadata-only']:
        ROOT.mkdir(parents=True, exist_ok=True)
        inspect_annotations()
    elif sys.argv[1:]:
        raise SystemExit('Usage: audit_isafetybench.py [--details-only | --metadata-only]')
    else:
        main()
