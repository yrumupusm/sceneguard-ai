import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import av
import numpy as np

from sceneguard.mvp_review_evidence import (
    _candidate_banner, _evidence_plan, _observations, _safe_output, _validate_video, render_review_bundle,
)


def fixture(source):
    """Small synthetic full-field video; no CCTV or model is involved."""
    width, height = 320, 180
    with av.open(str(source), 'w') as writer:
        stream = writer.add_stream('libx264', rate=10)
        stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
        for i in range(12):
            rgb = np.zeros((height, width, 3), dtype=np.uint8)
            rgb[:, :width//2, 0] = 50+i*10
            rgb[:, width//2:, 1] = 200-i*5
            frame = av.VideoFrame.from_ndarray(rgb, format='rgb24')
            frame.pts, frame.time_base = i, Fraction(1, 10)
            for packet in stream.encode(frame):
                writer.mux(packet)
        for packet in stream.encode():
            writer.mux(packet)
    with av.open(str(source)) as reader:
        stamps = [(f.pts, str(f.time_base)) for f in reader.decode(video=0)]
    cached, tracked = [], []
    segments = [dict(id='t1', raw_id=1, rows=[]), dict(id='t2', raw_id=2, rows=[]),
                dict(id='t3', raw_id=3, rows=[])]
    for i, (native, tb) in enumerate(stamps):
        pts = float(native*Fraction(tb))
        selected = [segments[0]] if i < 6 else segments[1:]
        boxes, scores, detections = [], [], []
        for ci, segment in enumerate(selected):
            box = [.1+ci*.3, .1, .3+ci*.3, .6]
            boxes.append([v*n for v, n in zip(box, [width, height, width, height])])
            scores.append(.9)
            row = dict(frame_index=i, pts=pts, raw_id=segment['raw_id'], bbox=box,
                       score=.9, cache_index=ci)
            segment['rows'].append(row)
            detections.append(dict(track_id=segment['raw_id'], bbox=box, score=.9,
                                   cache_index=ci, observed=True))
        # Predictions are deliberately retained in the input and never drawn.
        detections.append(dict(track_id=99, bbox=[.1, .1, .9, .9], observed=False))
        cached.append(dict(pts=pts, native_pts=native, time_base=tb, source_size=[width, height],
                           boxes=boxes, scores=scores))
        tracked.append(dict(pts=pts, native_pts=native, time_base=tb, detections=detections))
    for segment in segments:
        segment.update(start=segment['rows'][0]['pts'], end=segment['rows'][-1]['pts'])
    link = dict(before='t1', after='t2', status='rejected', reason='low_similarity', similarity=.54)
    associations = dict(mapping=dict(t1='p1', t2='p2', t3='p3'), links=[link])
    event = dict(id='line-0001', at_pts=.7, source='existing_gap_line', raw_track_id=2,
        category='boundary_motion_requires_review', evidence_window=[0., 1.1],
        tracklet_ids=['t2'], associated_chain_ids=['p2'], estimated_at_pts=.6,
        estimated_interval_pts=[.5, .7], original_emitted_at_pts=.7,
        uncertainty=['partial_box_possible'], available_after_pts=1.1)
    other = dict(event, id='line-0002', raw_track_id=3, tracklet_ids=['t3'], associated_chain_ids=['p3'])
    suggestion = dict(before_tracklet='t1', after_tracklet='t2', status='possible_match_needs_review',
        original_reason='low_similarity', similarity=.54, identity_verified=False)
    audit = dict(before_tracklet='t1', after_tracklet='t2', question='Q02',
        status='possible_match_needs_review', user_context=[],
        review_context=[dict(observation='possible_raw_id_drift',
            source='continuation_instruction_previous_review_draft',
            status='review_concern_not_identity_ground_truth', identity_verified=False)])
    feed = dict(video_id='SYNTHETIC', events=[event, other], link_suggestions=[suggestion],
        question_audit=[audit], interval=[0., 1.2], available_after_pts=1.1,
        output_utc='2026-01-01T00:00:00+00:00', user_context=[])
    zones = dict(outside=[[0, 0], [.3, 0], [.3, 1], [0, 1]],
                 inside=[[.7, 0], [1, 0], [1, 1], [.7, 1]])
    return cached, tracked, segments, associations, feed, zones


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        Path('outputs').mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='test-evidence-', dir='outputs')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root/'synthetic.mp4'
        self.args = fixture(self.source)

    def test_real_render_preserves_claim_rows_ids_native_pts_and_full_field(self):
        before = copy.deepcopy(self.args)
        output = self.root/'render'
        output.mkdir()
        receipt = render_review_bundle(self.source, *self.args, output)
        self.assertEqual(self.args, before)
        self.assertEqual(receipt['source_frames'], 12)
        self.assertTrue(receipt['source_native_pts_verified'])
        self.assertTrue(receipt['all_clip_references_exist'])
        self.assertEqual(receipt['predicted_boxes_drawn'], 0)
        self.assertEqual(receipt['association_calls'], 0)
        self.assertEqual(receipt['human_visual_review'], 'pending_root_review')
        for video in receipt['videos'].values():
            self.assertEqual(video['codec'], 'h264')
            self.assertEqual(video['pixel_format'], 'yuv420p')
            self.assertEqual(video['decoded_frames'], 12)
            self.assertTrue((output/video['path']).is_file())
        self.assertEqual(receipt['videos']['original']['size'], [320, 180])
        self.assertEqual(receipt['videos']['raw_ids']['size'], [320, 276])
        evidence = output/'evidence'
        index = json.loads((evidence/'evidence-index.json').read_text())
        self.assertEqual(len(index['rows']), 3)
        a, b, pair = index['rows']
        self.assertEqual(a['raw_ids'], [2])
        self.assertEqual(b['raw_ids'], [3])
        self.assertEqual(a['evidence_refs'], b['evidence_refs'])
        self.assertEqual(pair['chain_ids'], ['p1', 'p2'])
        self.assertFalse(pair['auto_accepted'])
        self.assertEqual(pair['status'], 'possible_match_needs_review')
        self.assertEqual(pair['question'], 'Q02')
        self.assertEqual(pair['review_context'][0]['status'], 'review_concern_not_identity_ground_truth')
        self.assertEqual(pair['user_context'], [])
        self.assertIn('NOT an accepted identity', pair['note'])
        self.assertEqual(index['feed_prepared_utc'], self.args[4]['output_utc'])
        self.assertNotEqual(index['finished_utc'], index['feed_prepared_utc'])
        points = json.loads((evidence/'source-frames.json').read_text())
        self.assertEqual([p['native_pts'] for p in points], [f['native_pts'] for f in self.args[0]])
        for clip in index['clips']:
            self.assertTrue((evidence/clip['path']).is_file())
            self.assertTrue((evidence/clip['comparison']['path']).is_file())
            self.assertEqual(clip['media']['decoded_frames'], clip['frames'])
            first = clip['first_frame']
            self.assertEqual(clip['source_pts'][0], self.args[0][first]['pts'])
            self.assertEqual(clip['native_pts'][0], self.args[0][first]['native_pts'])
        text = (evidence/'index.html').read_text()
        self.assertIn('Comparison interval', text)
        self.assertIn('possible_match_needs_review', text)
        self.assertIn('low_similarity', text)
        self.assertIn('#t=', text)
        self.assertNotIn('<script', text)
        with self.assertRaises(FileExistsError):
            render_review_bundle(self.source, *self.args, output)

    def test_misaligned_native_timestamp_rejected_before_output(self):
        args = copy.deepcopy(self.args)
        args[1][1]['native_pts'] += 1
        with self.assertRaisesRegex(ValueError, 'timing'):
            render_review_bundle(self.source, *args, self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_predicted_rows_excluded_and_cache_box_substitution_rejected(self):
        cached, tracked, segments, associations, _, _ = self.args
        measured, _ = _observations(cached, tracked, segments, associations)
        self.assertEqual({r['raw_id'] for rows in measured.values() for r in rows}, {1, 2, 3})
        tracked[0]['detections'][0]['bbox'][0] += .02
        with self.assertRaisesRegex(ValueError, 'measured cache'):
            _observations(cached, tracked, segments, associations)

    def test_omitted_segment_row_rejected(self):
        cached, tracked, segments, associations, _, _ = self.args
        segments[0]['rows'].pop()
        with self.assertRaisesRegex(ValueError, 'omit measured'):
            _observations(cached, tracked, segments, associations)

    def test_user_approach_context_separate_from_algorithm_event(self):
        cached, _, segments, associations, feed, _ = copy.deepcopy(self.args)
        for frame in cached:
            frame['pts'] += 56.
        for segment in segments:
            segment['start'] += 56.
            segment['end'] += 56.
        feed['events'] = []
        feed['user_context'] = [dict(pts=56.7, observation='approach_not_actual_climb',
                                    algorithm_detection=False, source='previous_user_observation')]
        rows, clips = _evidence_plan(cached, segments, associations, feed)
        self.assertEqual([r['kind'] for r in rows], ['link_pair', 'user_observation'])
        context = rows[-1]
        self.assertEqual(context['at_pts'], 56.7)
        self.assertFalse(context['algorithm_detection'])
        self.assertEqual(context['raw_ids'], [])
        self.assertEqual(context['category'], 'user_observed_approach_not_climb')
        self.assertTrue(context['evidence_refs'])

    def test_audit_only_pair_gets_evidence_without_becoming_automatic_link(self):
        cached, _, segments, associations, feed, _ = self.args
        feed['link_suggestions'] = []
        feed['question_audit'][0]['status'] = 'outside_original_time_limit_audit_only'
        rows, _ = _evidence_plan(cached, segments, associations, feed)
        self.assertEqual(rows[-1]['status'], 'outside_original_time_limit_audit_only')
        self.assertFalse(rows[-1]['auto_accepted'])
        self.assertTrue(rows[-1]['evidence_refs'])

    def test_html_escapes_untrusted_reason(self):
        from sceneguard.mvp_review_evidence import _write_index
        cached, _, segments, associations, feed, _ = self.args
        associations['links'][0]['reason'] = '<script>alert(1)</script>'
        rows, clips = _evidence_plan(cached, segments, associations, feed)
        index = dict(video_id='SYNTHETIC', rows=rows, clips=clips, available_after_pts=1.1,
                     finished_utc='finished')
        _write_index(self.root/'escaped.html', index)
        text = (self.root/'escaped.html').read_text()
        self.assertNotIn('<script>', text)
        self.assertIn('&lt;script&gt;', text)

    def test_wrong_decode_count_is_failure(self):
        with self.assertRaisesRegex(ValueError, 'frame count'):
            _validate_video(self.source, 11, Fraction(1, 10))

    def test_candidate_banner_waits_for_original_emission_and_keeps_simultaneous_rows(self):
        feed = self.args[4]
        before = _candidate_banner(feed, .6)
        self.assertIn('motion 0', before[0])
        self.assertNotIn('line-0001', before[1])
        emitted = _candidate_banner(feed, .7)
        self.assertIn('motion 2', emitted[0])
        self.assertIn('line-0001', emitted[1])
        self.assertIn('line-0002', emitted[1])
        feed['events'].append(dict(feed['events'][0], id='region-0001',
            source='current_polygon_two_side', at_pts=1., region_confirmed_at_pts=1.))
        self.assertIn('two-side 0', _candidate_banner(feed, .9)[0])
        self.assertIn('two-side 1', _candidate_banner(feed, 1.)[0])
        self.assertIn('completion UNKNOWN', emitted[0])

    def test_quality_outlier_has_own_original_clip_ref_and_does_not_change_pair_status(self):
        cached, _, segments, associations, feed, _ = self.args
        diagnostic = dict(least_consistent_representative_index=0,
            possible_inconsistent_representative=True, representative_rows=[dict(pts=0.)],
            mean_similarity_to_others=[.2, .7, .7], representatives_retained=3)
        feed['input_quality'] = dict(appearance=dict(t1=dict(head=diagnostic)),
            concurrent_overlaps=[dict(tracklets=['t1', 't3'], raw_ids=[1, 3])],
            extent_changes=[dict(raw_id=1, before_tracklet='t1', after_tracklet='t1')])
        rows, clips = _evidence_plan(cached, segments, associations, feed)
        pair = rows[-1]
        self.assertEqual(pair['input_quality']['concurrent_overlap_count'], 1)
        self.assertEqual(pair['input_quality']['extent_change_count'], 1)
        self.assertEqual(pair['input_quality']['appearance']['t1']['head'], diagnostic)
        self.assertEqual(pair['status'], 'possible_match_needs_review')
        self.assertFalse(pair['auto_accepted'])
        self.assertTrue(any(c['source_pts'] == [0., .7] for c in clips))

    def test_missing_source_frame_is_failure(self):
        from sceneguard.mvp_review_evidence import decode_native
        def truncated(source, cached):
            yield from ((i, frame) for i, frame in decode_native(source, cached) if i < 11)
        with patch('sceneguard.mvp_review_evidence.decode_native', truncated):
            with self.assertRaisesRegex(ValueError, 'decode count'):
                render_review_bundle(self.source, *self.args, self.root/'truncated')

    def test_outputs_only_and_no_symlink_parent(self):
        with self.assertRaises(ValueError):
            _safe_output(Path('/tmp/disallowed-evidence'))
        link = self.root/'linked'
        link.symlink_to(self.root.resolve(), target_is_directory=True)
        with self.assertRaises(ValueError):
            _safe_output(link/'nested')


if __name__ == '__main__':
    unittest.main()
