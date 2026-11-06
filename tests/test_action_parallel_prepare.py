"""Real spawned decode equivalence and fail-closed CPU publication checks; no GPU."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import prepare_action_pixels_parallel as parallel


class ParallelPreparation(unittest.TestCase):
    @contextmanager
    def fixture(self):
        import av
        import numpy as np
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = parallel.trainer()
            save = module.save
            rows = []
            cases = [('train', 'moving', 0), ('train', 'wall_over', 1),
                     ('validation', 'sit_down_bench', 0), ('validation', 'wall_over', 1),
                     ('test', 'stand', 0), ('test', 'wall_over', 1),
                     ('train', 'sit_down_floor', 0)]
            for i, (split, action, label) in enumerate(cases):
                video = root/f'source-{i}.mp4'
                annotation = root/f'label-{i}.json'
                annotation.write_text(json.dumps(dict(actor=i, action=action)))
                with av.open(str(video), 'w') as container:
                    stream = container.add_stream('libx264', rate=3)
                    stream.width = 32; stream.height = 24; stream.pix_fmt = 'yuv420p'
                    for frame_index in range(12):
                        data = np.full((24, 32, 3), 5+i*20+frame_index, dtype=np.uint8)
                        frame = av.VideoFrame.from_ndarray(data, format='rgb24')
                        for packet in stream.encode(frame):
                            container.mux(packet)
                    for packet in stream.encode():
                        container.mux(packet)
                rows.append(dict(clip_id=f'clip-{i}', source_id=f'source-{i}', source_path=str(video),
                    source_sha256=module.sha(video), label_path=str(annotation),
                    label_sha256=module.sha(annotation), event_group=f'event-{i}', split=split,
                    location='held' if split == 'test' else 'seen', label=label, actor_id=i,
                    sample_pts=[j/3 for j in range(8)], roi_xyxy=[0, 0, 32, 24] if i%2 else [2, 0, 20, 24],
                    source_width=32, source_height=24, verified_action_interval=[0, 3],
                    label_evidence='synthetic_official_fixture', negative_basis='explicit_action_annotation',
                    temporal_alignment='annotation_interior_both_origins',
                    box_alignment='official_annotations_sampled_alignment_review', action_class=action,
                    evaluation_cohort='heldout_place' if split == 'test' else 'same_place_separate_capture'))
            paths = {key: root/(key+'.json') for key in
                     ('manifest', 'baseline_lock', 'split_manifest', 'config', 'review_release')}
            save(paths['config'], json.loads((parallel.ROOT/'configs/exp0063_action_training.json').read_text()))
            save(paths['baseline_lock'], dict(status='verified', baseline_experiment='EXP-0062',
                 regression_only_videos=[dict(path=f'/forbidden/{i}.mp4', sha256=f'forbidden-{i}') for i in range(45)]))
            save(paths['split_manifest'], dict(held_out_test_locations=['held'], assignments=[dict(
                source_id=r['source_id'], source_sha256=r['source_sha256'], label_sha256=r['label_sha256'],
                group_id=r['event_group'], split=r['split'], location=r['location'], excluded=False) for r in rows]))
            snapshot, policy = root/'snapshot.json', root/'policy.md'
            save(snapshot, dict(requests=[dict(id=f'request-{i}', version=4, answer_version=1,
                 experiment_id='EXP-0063', answer='sample alignment only', source_binding_sha256=f'binding-{i}')
                 for i in range(8)]))
            policy.write_text('Official reference; sampled alignment is not full semantic truth.')
            review = dict(review_snapshot=dict(path=str(snapshot), sha256=module.sha(snapshot)),
                          review_policy=dict(path=str(policy), sha256=module.sha(policy)),
                          reviews=[dict(request_id=f'request-{i}', version=4, answer_version=1) for i in range(8)])
            manifest = dict(clips=rows, held_out_test_locations=['held'],
                review_status='sampled_alignment_review_complete', review_evidence=review,
                label_policy='official_actor_action_intervals_sampled_alignment_review',
                config_sha256=module.sha(paths['config']), baseline_lock_sha256=module.sha(paths['baseline_lock']),
                source_split_sha256=module.sha(paths['split_manifest']))
            save(paths['manifest'], manifest)
            def release():
                save(paths['manifest'], manifest)
                save(paths['review_release'], dict(schema_version=1, experiment_id='EXP-0063',
                    manifest_sha256=module.sha(paths['manifest']), split_manifest_sha256=module.sha(paths['split_manifest']),
                    review_snapshot=review['review_snapshot'], interpretation_policy=review['review_policy'],
                    reviews=review['reviews']))
            release()
            def argv(mode):
                result = []
                for key, path in paths.items():
                    result += ['--'+key.replace('_', '-'), str(path)]
                return result+['--review-release-sha256', module.sha(paths['review_release']),
                               '--output', str(root/'output'), '--mode', mode]
            with patch.object(parallel, 'SPLIT_SHA', module.sha(paths['split_manifest'])):
                yield root, rows, manifest, argv, release

    def test_real_spawned_prepare_matches_every_sequential_array_and_npy_byte(self):
        with self.fixture() as (root, rows, manifest, argv, release):
            parallel.main(argv('prepare'))
            prepared = json.loads((root/'output/prepared.json').read_text())
            provenance = prepared['preparation']
            self.assertEqual(provenance['trainer_sha256'], parallel.TRAINER_SHA)
            self.assertEqual(provenance['driver_sha256'], parallel.trainer().sha(parallel.__file__))
            self.assertEqual(provenance['contract']['sha256'], parallel.trainer().sha(root/'output/contract.json'))
            sequential = root/'sequential'; sequential.mkdir()
            expected = parallel.decode_rows(rows, 112, sequential, parallel=False)
            self.assertEqual(list(prepared['clips']), [r['clip_id'] for r in rows])
            self.assertEqual(parallel.compare_entries(expected, prepared['clips'])['compared'], len(rows))
            settings = root/'config.json'
            self.assertEqual(len(parallel.trainer().prepared_entries(root/'output', root/'manifest.json', settings, rows)), len(rows))
            with self.assertRaises(FileExistsError):
                parallel.main(argv('prepare'))

    def test_corrupted_source_fails_before_decode_without_completion_manifest(self):
        with self.fixture() as (root, rows, manifest, argv, release):
            with Path(rows[0]['source_path']).open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'Source/annotation changed'):
                parallel.main(argv('prepare'))
            self.assertFalse((root/'output/prepared.json').exists())
            self.assertFalse(list((root/'output').glob('clip-*.npy')))
            self.assertFalse(json.loads((root/'output/failure.json').read_text())['prepared_published'])

    def test_native_pts_failure_keeps_partial_outputs_unpublished(self):
        with self.fixture() as (root, rows, manifest, argv, release):
            rows[0]['sample_pts'] = [t+.01 for t in rows[0]['sample_pts']]
            release()
            with self.assertRaisesRegex(ValueError, 'PTS mismatch'):
                parallel.main(argv('prepare'))
            self.assertFalse((root/'output/prepared.json').exists())
            self.assertTrue((root/'output/failure.json').is_file())
            # Row0 fails: only the initial four tasks can run; rows4..6 must never be submitted.
            self.assertLessEqual(len(list((root/'output').glob('clip-*.npy'))), 3)
            self.assertFalse((root/'output/clip-000004.npy').exists())

    def test_benchmark_covers_available_classes_splits_cohorts_and_never_publishes_prepared(self):
        with self.fixture() as (root, rows, manifest, argv, release):
            plan = parallel.benchmark_plan(rows)
            self.assertEqual(plan, parallel.benchmark_plan(rows))
            chosen = [rows[x['manifest_index']] for x in plan]
            for field in ['action_class', 'split', 'evaluation_cohort']:
                self.assertEqual({r[field] for r in rows}, {r[field] for r in chosen})
            parallel.main(argv('benchmark'))
            result = json.loads((root/'output/benchmark-result.json').read_text())
            self.assertEqual(result['status'], 'benchmark_passed')
            self.assertTrue(result['equivalence']['npy_sha256_equal'])
            self.assertFalse(result['full_prepared'])
            self.assertFalse((root/'output/prepared.json').exists())

    def test_frozen_decoder_and_conflicting_bindings_are_rejected(self):
        with patch.object(parallel, 'TRAINER_SHA', '0'*64):
            with self.assertRaisesRegex(ValueError, 'Frozen trainer bytes differ'):
                parallel.trainer()
        rows = [dict(source_path='/source', source_sha256='a', label_path='/label', label_sha256='b'),
                dict(source_path='/source', source_sha256='c', label_path='/label', label_sha256='b')]
        with self.assertRaisesRegex(ValueError, 'Contradictory'):
            parallel.source_bindings(rows)

    def test_every_saved_sequential_row_is_compared_before_publication(self):
        import numpy as np
        with self.fixture() as (root, rows, manifest, argv, release):
            sequential = root/'sequential'; sequential.mkdir()
            entries = parallel.decode_rows([rows[0], rows[-1]], 112, sequential, parallel=False)
            last = entries[rows[-1]['clip_id']]
            original = np.load(last['path'], allow_pickle=False)
            np.save(last['path'], original+1, allow_pickle=False)
            last['sha256'] = parallel.trainer().sha(last['path'])
            snapshot = root/'sequential-snapshot.json'
            def snapshot_args():
                parallel.trainer().save(snapshot, dict(manifest_sha256=parallel.trainer().sha(root/'manifest.json'), clips=entries))
                return ['--sequential-snapshot', str(snapshot), '--sequential-snapshot-sha256', parallel.trainer().sha(snapshot)]
            with self.assertRaisesRegex(ValueError, 'equivalence failed'):
                parallel.main(argv('prepare')+snapshot_args())
            self.assertFalse((root/'output/prepared.json').exists())
            np.save(last['path'], original, allow_pickle=False)
            last['sha256'] = parallel.trainer().sha(last['path'])
            args = argv('prepare')+snapshot_args()
            args[args.index('--output')+1] = str(root/'correct-output')
            parallel.main(args)
            check = json.loads((root/'correct-output/sequential-equivalence.json').read_text())
            self.assertEqual(check['compared'], len(entries))
            self.assertTrue((root/'correct-output/prepared.json').is_file())

    def test_nested_review_file_change_blocks_both_completion_markers(self):
        for mode in ['prepare', 'benchmark']:
            with self.subTest(mode=mode), self.fixture() as (root, rows, manifest, argv, release):
                original = parallel.decode_rows
                def change_policy_after_decode(*args, **kwargs):
                    result = original(*args, **kwargs)
                    (root/'policy.md').write_text('changed after the initial release check')
                    return result
                with patch.object(parallel, 'decode_rows', side_effect=change_policy_after_decode):
                    with self.assertRaisesRegex(ValueError, 'Input contract changed.*interpretation_policy'):
                        parallel.main(argv(mode))
                self.assertFalse((root/'output/prepared.json').exists())
                self.assertFalse((root/'output/benchmark-result.json').exists())


if __name__ == '__main__':
    unittest.main()
