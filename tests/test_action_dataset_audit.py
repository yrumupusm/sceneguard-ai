"""Synthetic integrity tests; no private source media or GPU required."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts/audit_action_dataset.py'
SPEC = importlib.util.spec_from_file_location('action_audit', MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def label():
    return {'info': {'filename': 'a.mp4', 'height': 60, 'width': 80,
                     'date_captured': '2021/08/31 12:00:00', 'frame': 12,
                     'fps': 3, 'location': 'site-a', 'video_length': '00:00:04'},
            'events': [{'actor_id': 0, 'object_id': 4, 'ev_start_frame': 3,
                        'ev_end_frame': 5, 'start_time': '00:00:01', 'end_time': '00:00:01'}],
            'annotations': [{'actor_id': 0, 'object_id': 4, 'cur_frame': frame,
                             'class_name': 'wall_over', 'bbox': [[10, 10], [20, 30]]}
                            for frame in (3, 4, 5)]}


def row(key, site='site-a', scenario=1, capture='2021/08/31 12:00:00', digest=None, excluded=False):
    return {'source_id': key, 'scenario': scenario, 'excluded': excluded,
            'source_sha256': digest or key, 'label_sha256': key + '-label', 'errors': [],
            'label': {'info': {'location': site, 'date_captured': capture, 'video_length': '00:02:00'}},
            'video': {'stream_duration_seconds': 120}}


class LabelAuditTests(unittest.TestCase):
    def test_both_origins_are_retained_and_absence_never_negative(self):
        result = audit.audit_label(label(), 'a.mp4')
        self.assertFalse(result['errors'])
        self.assertEqual(result['frame_origin'], 'unresolved')
        self.assertFalse(result['trainable'])
        self.assertEqual(result['events'][0]['training_label'], None)
        alternatives = result['events'][0]['origin_alternatives']
        self.assertEqual(alternatives['0']['start_seconds_cfr'], 1)
        self.assertAlmostEqual(alternatives['1']['start_seconds_cfr'], 2 / 3)

    def test_missing_actor_not_replaced_by_other_actor_boxes(self):
        data = label()
        data['events'][0]['actor_id'] = 5
        result = audit.audit_label(data, 'a.mp4')
        self.assertIn('event_without_declared_actor_boxes', [e['code'] for e in result['errors']])
        self.assertEqual(result['events'][0]['matching_box_count'], 0)

    def test_classes_resolved_per_event_not_entire_actor(self):
        data = label()
        other = deepcopy(data['annotations'][0])
        other.update(cur_frame=9, class_name='stand')
        data['annotations'].append(other)
        result = audit.audit_label(data, 'a.mp4')
        self.assertEqual(result['event_classes'], {'wall_over': 1})
        self.assertIn('boxes_outside_declared_actor_events', [w['code'] for w in result['warnings']])

    def test_bbox_bounds_and_nonfinite_rejected(self):
        for box in ([[0, 0], [81, 60]], [[20, 20], [10, 30]], [[float('nan'), 0], [10, 10]]):
            with self.subTest(box=box):
                data = label()
                data['annotations'][0]['bbox'] = box
                self.assertTrue(audit.audit_label(data, 'a.mp4')['errors'])

    def test_frame_sparse_duplicate_and_range_checks(self):
        data = label()
        data['annotations'].pop(1)
        data['annotations'].append(deepcopy(data['annotations'][0]))
        result = audit.audit_label(data, 'a.mp4')
        self.assertEqual(result['events'][0]['missing_box_frames'], [4])
        self.assertIn('duplicate_actor_object_frame', [w['code'] for w in result['warnings']])
        data['events'][0]['ev_end_frame'] = 99
        self.assertIn('event_frame_out_of_range', [e['code'] for e in audit.audit_label(data, 'a.mp4')['errors']])

    def test_bad_schema_and_event_order_are_explicit(self):
        self.assertEqual(audit.audit_label({}, 'a.mp4')['errors'][0]['code'], 'schema_top_level')
        data = label()
        data['events'][0].update(ev_start_frame=7, ev_end_frame=2)
        self.assertIn('event_reversed', [e['code'] for e in audit.audit_label(data, 'a.mp4')['errors']])


class GroupingTests(unittest.TestCase):
    def test_multiview_and_same_day_other_scenario_join(self):
        rows = [row('a'), row('b'), row('c', scenario=9, capture='2021/08/31 18:00:00'),
                row('test', site='site-b'), row('val', site='site-c')]
        result = audit.grouped_split(rows)
        assigned = {r['source_id']: r for r in result['assignments']}
        self.assertEqual(len({assigned[k]['group_id'] for k in ('a', 'b', 'c')}), 1)
        self.assertTrue(any(e['reason'].startswith('overlapping_capture|') for e in result['connections']))

    def test_same_scenario_location_connects_different_days(self):
        rows = [row('a'), row('b', capture='2021/09/01 12:00:00'), row('c', site='site-b'), row('d', site='site-c')]
        assigned = {r['source_id']: r for r in audit.grouped_split(rows)['assignments']}
        self.assertEqual(assigned['a']['group_id'], assigned['b']['group_id'])

    def test_midnight_capture_connects_next_day_scenario(self):
        rows = [row('a', capture='2021/08/31 23:59:30'), row('b', scenario=8, capture='2021/09/01 00:00:10'),
                row('c', site='site-b'), row('d', site='site-c')]
        assigned = {r['source_id']: r for r in audit.grouped_split(rows)['assignments']}
        self.assertEqual(assigned['a']['group_id'], assigned['b']['group_id'])

    def test_cross_site_exact_duplicate_quarantined(self):
        rows = [row('a', digest='identical'), row('b', site='site-b', digest='identical'), row('c', site='site-c')]
        result = audit.grouped_split(rows)
        assigned = {r['source_id']: r for r in result['assignments']}
        self.assertEqual(assigned['a']['group_id'], assigned['b']['group_id'])
        self.assertEqual(assigned['a']['split'], 'quarantine')
        self.assertEqual(assigned['b']['split'], 'quarantine')

    def test_excluded_scenario_never_becomes_training_and_missing_metadata_quarantined(self):
        rows = [row('excluded', excluded=True), row('bad'), row('c', site='site-b'), row('d', site='site-c')]
        rows[1]['label']['info'].pop('date_captured')
        assigned = {r['source_id']: r for r in audit.grouped_split(rows)['assignments']}
        self.assertEqual(assigned['excluded']['split'], 'excluded')
        self.assertEqual(assigned['bad']['split'], 'quarantine')
        self.assertTrue(all(not r['training_eligible'] for r in assigned.values()))

    def test_exclusion_boundaries(self):
        self.assertTrue(all(audit.excluded_scenario(n) for n in (19, 35, 69, 70)))
        self.assertFalse(any(audit.excluded_scenario(n) for n in (18, 36, 68, 71)))


class VideoAndInventoryTests(unittest.TestCase):
    def test_pairing_is_relative_path_and_orphans_visible(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            for branch in (audit.SOURCES, audit.LABELS):
                (base / branch / '4-1one').mkdir(parents=True)
            (base / audit.SOURCES / '4-1one/a.mp4').touch()
            (base / audit.LABELS / '4-1one/b.json').touch()
            rows = audit.inventory(base)
            self.assertEqual(len(rows), 2)
            self.assertTrue(any(r['source_path'] is None for r in rows))
            self.assertTrue(any(r['label_path'] is None for r in rows))

    def test_pyav_packets_sorted_by_presentation_without_decode(self):
        import argparse
        import av
        import numpy as np
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.mp4'
            with av.open(str(path), 'w') as container:
                stream = container.add_stream('libx264', rate=3)
                stream.width, stream.height, stream.pix_fmt = 80, 60, 'yuv420p'
                stream.options = {'bf': '2', 'g': '12'}
                for index in range(12):
                    frame = av.VideoFrame.from_ndarray(np.full((60, 80, 3), index * 10, dtype=np.uint8), format='rgb24')
                    for packet in stream.encode(frame):
                        container.mux(packet)
                for packet in stream.encode():
                    container.mux(packet)
            result = audit.audit_video(path)
            self.assertEqual(result['packet_count'], 12)
            self.assertEqual(result['packet_pts_missing'], 0)
            self.assertEqual(result['packet_pts_duplicate_count'], 0)
            self.assertEqual(result['_sorted_pts'], sorted(result['_packet_records']['pts']))
            self.assertIsNone(result['decoded_frame_count'])
            self.assertFalse(result['packet_is_frame_assumption'])
            # A synthetic end-to-end review verifies hash binding and both origins.
            label_path = Path(tmp) / 'a.json'
            audit.write_json(label_path, label())
            source = row('a')
            source.update(source_path=str(path), label_path=str(label_path),
                          source_sha256=audit.sha256(path), label_sha256=audit.sha256(label_path),
                          label=audit.audit_label(label(), 'a.mp4'))
            output = Path(tmp) / 'audit'
            output.mkdir()
            audit.write_jsonl(output / 'manifest.jsonl', [source])
            audit.write_jsonl(output / 'packet-pts.jsonl', [{'pts': result['_packet_records']['pts']}])
            split = audit.grouped_split([source])
            split.update(source_manifest_sha256=audit.sha256(output / 'manifest.jsonl'),
                         packet_pts_sha256=audit.sha256(output / 'packet-pts.jsonl'))
            audit.write_json(output / 'split-manifest.json', split)
            audit.build_overlays(argparse.Namespace(output=output))
            evidence = json.loads((output / 'overlay-manifest.json').read_text())
            self.assertEqual(len(evidence['samples']), 1)
            sample = evidence['samples'][0]
            self.assertEqual([p['origin_hypothesis'] for p in sample['panels']], [0, 1])
            with av.open(sample['video_path']) as clip:
                self.assertEqual(sum(1 for _ in clip.decode(video=0)), sample['video_frames'])

    def test_overlay_requires_preexisting_split_before_decoding(self):
        import argparse
        with TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                audit.build_overlays(argparse.Namespace(output=tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_event_statistics_preserve_scene_overlap_and_do_not_make_negatives(self):
        data = label()
        stand_event = deepcopy(data['events'][0])
        stand_event.update(actor_id=1, object_id=33)
        data['events'].append(stand_event)
        for annotation in deepcopy(data['annotations']):
            annotation.update(actor_id=1, object_id=33, class_name='stand')
            data['annotations'].append(annotation)
        audited = audit.audit_label(data, 'a.mp4')
        source = row('a')
        source['label'] = audited
        split = audit.grouped_split([source, row('b', site='site-b'), row('c', site='site-c')])
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit.write_jsonl(root / 'manifest.jsonl', [source])
            split['source_manifest_sha256'] = audit.sha256(root / 'manifest.jsonl')
            audit.write_json(root / 'split-manifest.json', split)
            audit.save_event_statistics(root)
            result = json.loads((root / 'event-statistics.json').read_text())
            stand = result['explicit_non_wall_actor_events'][0]
            self.assertEqual(stand['overlapping_declared_wall_over_event_indices'], [0])
            self.assertFalse(stand['scene_negative_certified'])
            self.assertIsNone(stand['training_label'])
            self.assertEqual(stand['both_origin_intersection_decoded_indices_inclusive'], [3, 4])
            self.assertEqual(result['negative_labels_created'], 0)

    def test_regression_lock_overlap_blocks_and_preserves_evidence(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = row('a', digest='protected-bytes')
            audit.write_jsonl(root / 'manifest.jsonl', [source])
            split = audit.grouped_split([source])
            split['source_manifest_sha256'] = audit.sha256(root / 'manifest.jsonl')
            audit.write_json(root / 'split-manifest.json', split)
            lock = root / 'baseline-lock.json'
            audit.write_json(lock, {'regression_only_videos': [
                {'video_id': f'E01_{i:03}', 'sha256': 'protected-bytes' if i == 1 else str(i)}
                for i in range(1, 46)]})
            with self.assertRaisesRegex(ValueError, 'regression-only source overlap'):
                audit.verify_regression_lock(root, lock)
            evidence = json.loads((root / 'regression-overlap.json').read_text())
            self.assertEqual(evidence['overlaps'][0]['regression_video_ids'], ['E01_001'])


if __name__ == '__main__':
    unittest.main()
