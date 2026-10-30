"""CPU evidence renderer for a finished, unadjudicated MVP review feed.

Only saved measured observations are drawn. Possible matches are annotations,
never additions to the automatic chain mapping. All media stays in outputs/.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import html
import json
import math
from pathlib import Path
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .run_tracklet_linking import decode_native, sha256, write_json
from .tracklet_linking import validate_zones, valid_box


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _font(size):
    try:
        return ImageFont.truetype('DejaVuSans.ttf', size)
    except OSError:
        return ImageFont.load_default()


def _safe_output(output):
    output = Path(output)
    if (not output.resolve().is_relative_to(Path('outputs').resolve()) or output.is_symlink()
            or any(p.is_symlink() for p in output.parents)):
        raise ValueError('Evidence must use a local outputs/ directory without symlinks')
    target = output/'evidence'
    if target.exists() or target.is_symlink():
        raise FileExistsError('Evidence must not overwrite an earlier run')
    return target


def _observations(cached, tracked, segments, associations):
    """Validate a partition of real cache rows; predicted boxes are never displayed."""
    if len(cached) < 2 or len(cached) != len(tracked):
        raise ValueError('Matching nonempty cached/tracked frames required')
    dimensions = cached[0]['source_size']
    if len(dimensions) != 2 or any(type(v) is not int or v <= 0 or v % 2 for v in dimensions):
        raise ValueError('Even positive native dimensions required for H264 yuv420p')
    stamps = [Fraction(f['time_base'])*f['native_pts'] for f in cached]
    dt = stamps[1]-stamps[0]
    if dt <= 0 or any(b-a != dt for a, b in zip(stamps, stamps[1:])):
        raise ValueError('Native PTS must be contiguous at one constant interval')
    expected = {}
    for i, (frame, record) in enumerate(zip(cached, tracked)):
        if (frame['source_size'] != dimensions or not math.isfinite(frame['pts'])
                or abs(float(stamps[i])-frame['pts']) > 1e-6
                or any(frame[k] != record[k] for k in ('pts', 'native_pts', 'time_base'))):
            raise ValueError('Native cache/tracking timing or dimensions mismatch')
        for row in record['detections']:
            if not row.get('observed', False) or not row.get('confirmed', True):
                continue
            key = (i, row['cache_index'])
            ci = row['cache_index']
            if (key in expected or type(ci) is not int or not 0 <= ci < len(frame['boxes'])
                    or ci >= len(frame['scores'])):
                raise ValueError('Invalid or repeated measured cache row')
            box = np.clip(np.asarray(frame['boxes'][ci])/np.tile(dimensions, 2), 0, 1)
            valid_box(row['bbox'])
            if (not np.allclose(box, row['bbox'], atol=1e-7, rtol=0)
                    or not math.isclose(frame['scores'][ci], row['score'], abs_tol=1e-7, rel_tol=0)):
                raise ValueError('Display boxes must be saved measured cache boxes')
            expected[key] = row
    found, by_frame, ids = set(), {}, set()
    for segment in segments:
        sid = segment['id']
        if sid in ids or sid not in associations['mapping']:
            raise ValueError('Duplicate or unmapped tracklet')
        ids.add(sid)
        for row in segment['rows']:
            key = (row['frame_index'], row['cache_index'])
            saved = expected.get(key)
            if (key in found or saved is None or row['raw_id'] != saved['track_id']
                    or row['raw_id'] != segment['raw_id'] or row['bbox'] != saved['bbox']
                    or row['pts'] != cached[key[0]]['pts'] or row['score'] != saved['score']):
                raise ValueError('Tracklet must reference each saved measured row exactly once')
            found.add(key)
            by_frame.setdefault(key[0], []).append(dict(row, tracklet_id=sid,
                chain_id=associations['mapping'][sid]))
    if found != set(expected):
        raise ValueError('Tracklets omit measured rows')
    return by_frame, dt


def _frame_window(cached, window):
    if (len(window) != 2 or any(not math.isfinite(v) for v in window)
            or window[1] < window[0]):
        raise ValueError('Finite, ordered evidence interval required')
    selected = [i for i, f in enumerate(cached) if window[0]-1e-9 <= f['pts'] <= window[1]+1e-9]
    if not selected:
        raise ValueError('Evidence interval contains no source frames')
    return selected[0], selected[-1]+1


def _evidence_plan(cached, segments, associations, feed):
    """One row per claim/pair; only identical frame windows share media files."""
    by_id = {s['id']: s for s in segments}
    rows, clips = [], {}
    dt = float(Fraction(cached[1]['time_base'])*cached[1]['native_pts']
               - Fraction(cached[0]['time_base'])*cached[0]['native_pts'])

    def evidence(window):
        first, stop = _frame_window(cached, window)
        key = (first, stop)
        if key not in clips:
            cid = f'clip-{len(clips)+1:04d}'
            clips[key] = dict(id=cid, path=f'clips/{cid}-original.mp4', first_frame=first,
                stop_frame_exclusive=stop, frames=stop-first,
                source_pts=[cached[first]['pts'], cached[stop-1]['pts']],
                native_pts=[cached[first]['native_pts'], cached[stop-1]['native_pts']],
                source_time_base=cached[first]['time_base'], source_frame_map='source-frames.json',
                comparison=dict(path='comparison.mp4', start_seconds=first*dt,
                                end_seconds=stop*dt), referenced_by=[])
        return clips[key]

    def attach(row, windows):
        quality = feed.get('input_quality', {})
        sids, raw_ids = set(row['tracklet_ids']), set(row['raw_ids'])
        overlaps = [i for i, item in enumerate(quality.get('concurrent_overlaps', []))
                    if sids & set(item['tracklets']) or raw_ids & set(item['raw_ids'])]
        extents = [i for i, item in enumerate(quality.get('extent_changes', []))
                   if item['raw_id'] in raw_ids or {item['before_tracklet'], item['after_tracklet']} & sids]
        appearance = {sid: quality.get('appearance', {})[sid] for sid in sorted(sids)
                      if sid in quality.get('appearance', {})}
        row['input_quality'] = dict(path='input-quality.json', status='diagnostic_possibilities_not_person_truth',
            concurrent_overlap_indices=overlaps, concurrent_overlap_count=len(overlaps),
            extent_change_indices=extents, extent_change_count=len(extents), appearance=appearance)
        # Include the actual saved representative's original context when an
        # outlier is flagged. Do not replace/remove its feature or adjudicate it.
        for pair in appearance.values():
            for endpoint in ('head', 'tail'):
                diagnostic = pair.get(endpoint, {})
                least = diagnostic.get('least_consistent_representative_index')
                if diagnostic.get('possible_inconsistent_representative') and least is not None:
                    pts = diagnostic['representative_rows'][least]['pts']
                    windows.append([max(cached[0]['pts'], pts-.75), min(cached[-1]['pts'], pts+.75)])
        refs = []
        for window in windows:
            clip = evidence(window)
            if clip['id'] not in refs:
                refs.append(clip['id'])
                clip['referenced_by'].append(row['evidence_id'])
        row['evidence_refs'] = refs
        row['identity_verified'] = False
        row['physical_climb_completion'] = 'unknown'
        rows.append(row)

    for event in feed['events']:
        row = dict(event)
        row.update(evidence_id=f'event-{event["id"]}', kind='event',
                   raw_ids=sorted({by_id[s]['raw_id'] for s in event.get('tracklet_ids', [])}
                                  | ({event['raw_track_id']} if event.get('raw_track_id') is not None else set())),
                   tracklet_ids=event.get('tracklet_ids', []),
                   chain_ids=event.get('associated_chain_ids', []),
                   link_reasons=[], review_status='needs_review')
        selected = set(row['tracklet_ids'])
        row['link_reasons'] = [dict(link) for link in feed['link_suggestions']
            if {link['before_tracklet'], link['after_tracklet']} & selected]
        attach(row, [event['evidence_window']])

    # Preserve both the limited feed suggestions and Q01-Q08 audit-only pairs.
    pairs = {}
    for item in feed['link_suggestions']:
        pairs.setdefault((item['before_tracklet'], item['after_tracklet']), {})['suggestion'] = item
    for item in feed.get('question_audit', []):
        pairs.setdefault((item['before_tracklet'], item['after_tracklet']), {})['audit'] = item
    for i, ((before, after), provenance) in enumerate(pairs.items()):
        a, b = by_id[before], by_id[after]
        original = next((dict(link) for link in associations.get('links', [])
                         if (link['before'], link['after']) == (before, after)), None)
        suggestion, audit = provenance.get('suggestion'), provenance.get('audit')
        status = (suggestion or audit)['status']
        accepted = original is not None and original.get('status') == 'accepted'
        row = dict(evidence_id=f'pair-{i+1:04d}', kind='link_pair', category='identity_link_review',
            at_pts=b['start'], estimated_interval_pts=[a['end'], b['start']],
            before_tracklet=before, after_tracklet=after, raw_ids=[a['raw_id'], b['raw_id']],
            tracklet_ids=[before, after],
            chain_ids=[associations['mapping'][before], associations['mapping'][after]],
            status=status, review_status='needs_review', auto_accepted=accepted,
            question=audit.get('question') if audit else None, provenance=provenance,
            link_reasons=original,
            uncertainty=['identity_not_verified', 'partial_or_multi_person_crop_possible'],
            user_context=audit.get('user_context', []) if audit else [],
            review_context=audit.get('review_context', []) if audit else [],
            note=('Existing automatic association; not verified identity' if accepted else
                  'Review evidence only; NOT an accepted identity link'))
        windows = [[max(cached[0]['pts'], a['end']-1.5), min(cached[-1]['pts'], a['end']+1.5)],
                   [max(cached[0]['pts'], b['start']-1.5), min(cached[-1]['pts'], b['start']+1.5)]]
        if row['question'] == 'Q02':
            # User concern includes the earliest raw11 representative, which can
            # be far from the tail used for the proposed link.
            windows.append([max(cached[0]['pts'], a['start']-1.5), min(cached[-1]['pts'], a['start']+1.5)])
        attach(row, windows)
    for i, context in enumerate(feed.get('user_context', [])):
        if context.get('algorithm_detection') is not False:
            raise ValueError('User context must be explicitly separate from algorithm detections')
        row = dict(context, evidence_id=f'context-{i+1:04d}', kind='user_observation',
            category='user_observed_approach_not_climb', at_pts=context['pts'], raw_ids=[],
            tracklet_ids=[], chain_ids=[], uncertainty=['user_context_not_model_event'], link_reasons=[])
        attach(row, [[max(cached[0]['pts'], context['pts']-3), min(cached[-1]['pts'], context['pts']+3)]])
    return rows, list(clips.values())


class _VideoWriter:
    """Software H264 writer with an explicit, relative playback clock."""
    def __init__(self, path, size, dt):
        import av
        if path.exists():
            raise FileExistsError(path)
        self.path, self.dt, self.count = path, dt, 0
        self.container = av.open(str(path), 'w', options={'movflags': '+faststart'})
        self.stream = self.container.add_stream('libx264', rate=1/dt)
        self.stream.width, self.stream.height = size
        self.stream.pix_fmt = 'yuv420p'
        self.stream.options = dict(crf='22', preset='ultrafast', threads='2')

    def write(self, rgb):
        import av
        frame = av.VideoFrame.from_ndarray(np.asarray(rgb), format='rgb24')
        frame.pts, frame.time_base = self.count, self.dt
        for packet in self.stream.encode(frame):
            self.container.mux(packet)
        self.count += 1

    def close(self):
        try:
            for packet in self.stream.encode():
                self.container.mux(packet)
        finally:
            self.container.close()


def _validate_video(path, expected_frames, dt):
    import av
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        codec, pixel_format = stream.codec_context.name, stream.codec_context.format.name
        size = [stream.width, stream.height]
        stamps = [frame.pts*frame.time_base if frame.pts is not None else None
                  for frame in container.decode(stream)]
    if codec != 'h264' or pixel_format != 'yuv420p' or len(stamps) != expected_frames:
        raise ValueError('Evidence H264 format or decoded frame count mismatch')
    if any(stamp is None or abs(float(stamp-i*dt)) > 1e-5 for i, stamp in enumerate(stamps)):
        raise ValueError('Rendered playback PTS mismatch')
    return dict(frames=expected_frames, decoded_frames=len(stamps), codec=codec,
        pixel_format=pixel_format, size=size, sha256=sha256(path), bytes=path.stat().st_size,
        faststart=True, playback_start_seconds=0., playback_duration_seconds=float(expected_frames*dt))


def _color(key):
    return tuple(90+v % 166 for v in hashlib.sha256(str(key).encode()).digest()[:3])


def _annotate(source, measured, zones, mode, pair_labels):
    image = source.copy()
    draw, font = ImageDraw.Draw(image), _font(18)
    width, height = source.size
    for name, color in [('outside', (75, 220, 100)), ('inside', (65, 165, 250))]:
        points = [(round(x*(width-1)), round(y*(height-1))) for x, y in zones[name]]
        draw.line(points+[points[0]], fill=color, width=3)
    for row in measured:
        sid, raw, chain = row['tracklet_id'], row['raw_id'], row['chain_id']
        box = [round(v*n) for v, n in zip(row['bbox'], [width-1, height-1, width-1, height-1])]
        if mode == 'raw':
            label, key = f'raw {raw} / {sid}', raw
        else:
            label, key = f'{chain} / {sid} / raw {raw}', chain
        if mode == 'review' and sid in pair_labels:
            label += ' | REVIEW '+','.join(pair_labels[sid])
        color = _color(key)
        draw.rectangle(box, outline=color, width=3)
        x, y = box[0], max(0, box[1]-24)
        label_box = draw.textbbox((x, y), label, font=font)
        draw.rectangle(label_box, fill=(15, 15, 15))
        draw.text((x, y), label, font=font, fill=color)
    return image


def _with_header(image, title, clocks):
    result = Image.new('RGB', (image.width, image.height+96), (12, 15, 20))
    result.paste(image, (0, 96))
    draw = ImageDraw.Draw(result)
    for y, line in zip((5, 34, 63), [title]+clocks):
        draw.text((10, y), line, font=_font(20), fill=(245, 245, 245))
    return result


def _candidate_banner(feed, pts):
    """Never display a motion candidate before its original emission PTS."""
    due = [event for event in feed['events'] if event['at_pts'] <= pts+1e-9]
    motion = [e for e in due if e['source'] == 'existing_gap_line']
    regions = [e for e in due if e['source'] == 'current_polygon_two_side']
    label = (f'CANDIDATES NEEDS REVIEW: motion {len(motion)}, two-side {len(regions)} '
             '| physical completion UNKNOWN')
    details = [f'{e["id"]} raw {e.get("raw_track_id")} @ SOURCE PTS {e["at_pts"]:.3f}' for e in due[-4:]]
    return [label, ' | '.join(details) or 'No emitted/confirmed candidate yet in source timeline']


def _comparison(original, raw, auto, review, clocks, active_pairs, candidate_lines):
    # Two rows retain the full field. No crop, perspective change, or ROI zoom.
    panel_w = min(960, original.width)
    panel_w -= panel_w % 2
    panel_h = round(panel_w*original.height/original.width)
    panel_h += panel_h % 2
    stride, header, footer = panel_h+30, 96, 160
    canvas = Image.new('RGB', (2*panel_w, header+2*stride+footer), (12, 15, 20))
    draw = ImageDraw.Draw(canvas)
    for y, line in zip((3, 32, 61), ['OFFLINE REVIEW - identity and physical completion UNVERIFIED']+clocks):
        draw.text((8, y), line, font=_font(18), fill='white')
    for i, (image, title) in enumerate(zip((original, raw, auto, review),
            ('ORIGINAL - FULL FIELD', 'MEASURED RAW IDs / TRACKLETS',
             'SAVED AUTO CHAINS - UNVERIFIED', 'POSSIBLE / AUDIT PAIRS - NEEDS REVIEW'))):
        x, y = (i % 2)*panel_w, header+(i//2)*stride
        draw.text((x+6, y+3), title, font=_font(17), fill='white')
        canvas.paste(image.resize((panel_w, panel_h), Image.Resampling.BILINEAR), (x, y+30))
    note = (' | '.join(active_pairs) if active_pairs else 'No review pair endpoint observed in this frame')
    lines = candidate_lines+textwrap.wrap(note, max(30, 2*panel_w//10))[:3]
    for i, line in enumerate(lines):
        draw.text((8, header+2*stride+3+28*i), line, font=_font(17), fill=(255, 210, 110))
    return canvas


def _write_index(path, index):
    """A static evidence list, with no new server or interactive dashboard."""
    escape = lambda value: html.escape(str(value), quote=True)
    clips = {c['id']: c for c in index['clips']}
    items = []
    for row in index['rows']:
        links = []
        for ref in row['evidence_refs']:
            clip = clips[ref]
            comp = clip['comparison']
            anchor = f'{comp["path"]}#t={comp["start_seconds"]:.6f},{comp["end_seconds"]:.6f}'
            links.append(f'<a href="{escape(clip["path"])}">Original {escape(clip["source_pts"])}</a> '
                         f'<a href="{escape(anchor)}">Comparison interval</a> '
                         f'<small>{escape(ref)} (shared only for identical source frames)</small>')
        detail = dict(time_pts=row.get('at_pts'), estimated_interval_pts=row.get('estimated_interval_pts'),
            category=row['category'], uncertainty=row.get('uncertainty'), raw_ids=row['raw_ids'],
            tracklet_ids=row['tracklet_ids'], chain_ids=row['chain_ids'],
            status=row.get('status', row.get('review_status')), question=row.get('question'),
            link_reasons=row.get('link_reasons'), user_context=row.get('user_context'),
            review_context=row.get('review_context'),
            input_quality=row.get('input_quality'),
            algorithm_detection=row.get('algorithm_detection'),
            original_emitted_at_pts=row.get('original_emitted_at_pts'),
            available_after_pts=index['available_after_pts'],
            feed_prepared_utc=index.get('feed_prepared_utc'), media_finished_utc=index['finished_utc'])
        items.append(f'<tr id="{escape(row["evidence_id"])}"><td>{escape(row["evidence_id"])}<br>'
                     f'{escape(row.get("question") or "")}</td><td><pre>'
                     f'{escape(json.dumps(detail, ensure_ascii=False, indent=2))}</pre></td>'
            f'<td>{"<br>".join(links)}<br><a href="input-quality.json">Saved input-quality diagnostics</a></td></tr>')
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Local evidence list</title>'
            '<style>body{font:16px sans-serif;margin:24px}td{vertical-align:top;padding:12px;border:1px solid #bbb}'
            'pre{white-space:pre-wrap;max-width:56em}a{display:inline-block;margin:4px}</style>'
            f'<h1>{escape(index["video_id"])} — local evidence</h1>'
            '<p>Offline review candidates. Identity, physical climb completion, and legal status are unverified. '
            'Possible matches do not change automatic IDs. Source PTS differs from playback time. '
            'Green: current outside polygon; blue: current inside polygon; box proxy is not a ground point.</p>'
            '<p><a href="original.mp4">Continuous original</a><a href="raw_ids.mp4">Raw IDs</a>'
            '<a href="auto_chains.mp4">Saved automatic chains</a><a href="comparison.mp4">2×2 comparison</a>'
            '<a href="evidence-index.json">Complete machine readable evidence</a>'
            '<a href="source-frames.json">Native source PTS mapping</a></p>'
            '<p><a href="input-quality.json">Full saved overlap, extent and representative consistency diagnostics</a></p>'
            '<table><tr><th>Separate claim</th><th>Time, category, uncertainty, IDs and link reasons</th>'
            f'<th>Local evidence</th></tr>{"".join(items)}</table></html>')
    with path.open('x', encoding='utf-8') as stream:
        stream.write(page+'\n')


def render_review_bundle(video, cached, tracked, segments, associations, feed, zones, output):
    """Render saved data only; no model forward, tracking, association, or region A/B.

    The supplied output may exist (the integration runner owns it); evidence/
    must be new. The feed is left intact. Only synthetic tests call this directly;
    the integration owner invokes the one real CPU run after preflight review.
    """
    target = _safe_output(output)
    validate_zones(zones)
    measured, dt = _observations(cached, tracked, segments, associations)
    rows, clips = _evidence_plan(cached, segments, associations, feed)
    started = _utc_now()
    target.mkdir(parents=True, exist_ok=False)
    (target/'clips').mkdir()
    source_map = [dict(source_frame_index=i, source_pts=f['pts'], native_pts=f['native_pts'],
                       time_base=f['time_base'], playback_seconds=float(i*dt)) for i, f in enumerate(cached)]
    write_json(target/'source-frames.json', source_map)
    write_json(target/'input-quality.json', feed.get('input_quality', {}))
    pair_rows = [r for r in rows if r['kind'] == 'link_pair']
    pair_labels = {}
    for row in pair_rows:
        for sid in row['tracklet_ids']:
            pair_labels.setdefault(sid, []).append(row['question'] or row['evidence_id'])
    width, height = cached[0]['source_size']
    shapes = dict(original=(width, height), raw_ids=(width, height+96), auto_chains=(width, height+96))
    names = ['original', 'raw_ids', 'auto_chains', 'comparison']
    count = 0
    with ExitStack() as stack:
        writers = {}
        for i, bgr in decode_native(video, cached):
            if i != count or bgr.shape != (height, width, 3) or bgr.dtype != np.uint8:
                raise ValueError('Invalid, repeated or missing full native source frame')
            original = Image.fromarray(bgr[:, :, ::-1])
            raw = _annotate(original, measured.get(i, []), zones, 'raw', pair_labels)
            auto = _annotate(original, measured.get(i, []), zones, 'auto', pair_labels)
            review = _annotate(original, measured.get(i, []), zones, 'review', pair_labels)
            clocks = [f'SOURCE PTS {cached[i]["pts"]:.6f} | native {cached[i]["native_pts"]} * {cached[i]["time_base"]}',
                      f'OFFLINE available_after SOURCE PTS {feed.get("available_after_pts", cached[-1]["pts"]):.6f} | measured boxes only']
            visible = {r['tracklet_id'] for r in measured.get(i, [])}
            active = [f'{r["question"] or r["evidence_id"]}: {r["before_tracklet"]} -> {r["after_tracklet"]} '
                      + ('AUTO unverified' if r['auto_accepted'] else 'NEEDS REVIEW (no ID merge)')
                      for r in pair_rows if visible & set(r['tracklet_ids'])]
            images = dict(original=original,
                raw_ids=_with_header(raw, 'MEASURED RAW IDs / TRACKLETS - identity unverified', clocks),
                auto_chains=_with_header(auto, 'SAVED AUTO CHAINS - identity unverified / no review-pair merges', clocks),
                comparison=_comparison(original, raw, auto, review, clocks, active,
                                       _candidate_banner(feed, cached[i]['pts'])))
            if not writers:
                shapes['comparison'] = images['comparison'].size
                for name in names:
                    writers[name] = _VideoWriter(target/f'{name}.mp4', shapes[name], dt)
                    stack.callback(writers[name].close)
            for name in names:
                writers[name].write(images[name])
            count += 1
    if count != len(cached):
        raise ValueError('Source decode count mismatch')
    videos = {name: dict(path=f'{name}.mp4', **_validate_video(target/f'{name}.mp4', count, dt))
              for name in names}
    # One second native decode produces all deduplicated short ORIGINAL clips.
    # Original pixels have no annotations; the separate JSON records exact PTS.
    count = 0
    with ExitStack() as stack:
        active = {}
        for i, bgr in decode_native(video, cached):
            if i != count or bgr.shape != (height, width, 3) or bgr.dtype != np.uint8:
                raise ValueError('Invalid source frame during original clip production')
            for clip in clips:
                if clip['first_frame'] == i:
                    writer = _VideoWriter(target/clip['path'], (width, height), dt)
                    active[clip['id']] = writer
                    # Close every still-active writer if decoding/encoding fails.
                    stack.callback(lambda w=writer: w.close() if w.container is not None else None)
            for clip in clips:
                writer = active.get(clip['id'])
                if writer is not None:
                    writer.write(bgr[:, :, ::-1].copy())
                    if clip['stop_frame_exclusive'] == i+1:
                        writer.close()
                        writer.container = None
                        del active[clip['id']]
            count += 1
    if count != len(cached) or active:
        raise ValueError('Original evidence clip source decode count mismatch')
    for clip in clips:
        clip['media'] = _validate_video(target/clip['path'], clip['frames'], dt)
    finished = _utc_now()
    index = dict(schema=1, video_id=feed['video_id'], rows=rows, clips=clips, videos=videos,
        source_frame_map='source-frames.json', source_window=[cached[0]['pts'], cached[-1]['pts']],
        available_after_pts=feed.get('available_after_pts', cached[-1]['pts']),
        feed_prepared_utc=feed.get('output_utc'), render_started_utc=started, finished_utc=finished,
        original_pixels='full field, unannotated; exact native PTS in source-frames.json and clip metadata',
        annotation_mode='current_polygons_only_measured_boxes_only',
        row_policy='each event and pair retained separately; only identical frame windows deduplicated',
        identity_verified=False, physical_climb_completion='unknown', legal_status='unknown')
    for row in rows:
        if not row['evidence_refs'] or not all(ref in {c['id'] for c in clips} for ref in row['evidence_refs']):
            raise ValueError('Missing row evidence reference')
    for clip in clips:
        if not (target/clip['path']).is_file() or not (target/clip['comparison']['path']).is_file():
            raise ValueError('Missing local media reference')
    write_json(target/'evidence-index.json', index)
    _write_index(target/'index.html', index)
    artifacts = [str(p.relative_to(Path(output))) for p in sorted(target.rglob('*')) if p.is_file()]
    return dict(status='complete', evidence_index='evidence/evidence-index.json',
        evidence_html='evidence/index.html', artifacts=artifacts,
        videos={name: dict(metadata, path=f'evidence/{metadata["path"]}') for name, metadata in videos.items()},
        source_frames=count, source_decode_passes=2, original_clips=len(clips), separate_review_rows=len(rows),
        source_native_pts_verified=True, all_clip_references_exist=True,
        detector_calls=0, tracker_calls=0, encoder_calls=0, association_calls=0, polygon_comparisons=0,
        full_field=True, predicted_boxes_drawn=0, identity_verified=False,
        physical_climb_completion='unknown', human_visual_review='pending_root_review',
        feed_prepared_utc=feed.get('output_utc'), render_started_utc=started, finished_utc=finished)
