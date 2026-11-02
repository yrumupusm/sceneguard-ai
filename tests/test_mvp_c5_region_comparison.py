"""CPU runner safety and evaluation contracts, without real inference or video."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import mvp_c5_region_comparison as runner


class CacheReuse(unittest.TestCase):
    def setUp(self):
        self.config = dict(line=[[0.1, 0.2], [0.8, 0.9]], roi=[0., 0., 1., 1.],
            selection='original', boundary_id='C5_fence', camera_group='C5',
            score_threshold=.5, band=.005, directions=['a', 'b'], dwell_seconds=.1)

    def test_only_geometry_may_change(self):
        changed = deepcopy(self.config)
        changed.update(line=[[0., .1], [1., .2]], roi=[.1, .1, .9, .9], selection='new static image')
        runner.geometry_only(self.config, changed)
        for key, value in [('score_threshold', .4), ('band', .01), ('boundary_id', 'other'),
                           ('camera_group', 'C3'), ('directions', ['a']), ('dwell_seconds', .2)]:
            bad = changed | {key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner.geometry_only(self.config, bad)
        for bad in (changed | {'new_setting': 1}, {k: v for k, v in changed.items() if k != 'line'}):
            with self.assertRaises(ValueError):
                runner.geometry_only(self.config, bad)

    def test_derived_view_preserves_original_files_and_all_detector_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp)
            runner.write(original / 'run.json', {'historical': True}, exclusive=True)
            (original / 'person_cache.jsonl').write_bytes(b'exact original bytes\n')
            cfgpath = original / 'new-config.json'
            config = self.config | {'selection': 'new', 'roi': [.1, .1, .9, .9]}
            runner.write(cfgpath, config, exclusive=True)
            meta = dict(config=deepcopy(self.config), config_sha256='historical-config-hash',
                model_sha256='same model', model_input={'min_size': 800, 'max_size': 1333},
                model_postprocess={'nms_thresh': .6}, frames=10, person_cache={'sha256': 'raw'},
                processing_wall_seconds=100., device='cuda')
            before = deepcopy(meta)
            original_bytes = (original / 'run.json').read_bytes()
            view = runner.derived_metadata(meta, config, original, cfgpath)
            self.assertEqual(meta, before)
            self.assertEqual((original / 'run.json').read_bytes(), original_bytes)
            for key in set(meta) - {'config', 'config_sha256'}:
                self.assertEqual(view[key], meta[key])
            provenance = view['geometry_reuse_provenance']
            self.assertEqual(provenance['original_boundary_config'], self.config)
            self.assertEqual(provenance['original_person_cache_sha256'],
                             runner.vc.sha256(original / 'person_cache.jsonl'))
            self.assertEqual(provenance['detector_frames_this_execution'], 0)


class ExecutionGates(unittest.TestCase):
    def test_missing_or_mismatched_authorization_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, approval_path, review = root / 'plan', root / 'approval', root / 'review'
            runner.write(plan_path, {'plan': True}, exclusive=True)
            runner.write(review, {'review': 'accepted'}, exclusive=True)
            plan = {'analysis_code_digest': 'frozen-code'}
            approval = dict(plan_sha256=runner.vc.sha256(plan_path), execution_permitted=True,
                cpu_only=True, profiles_code_frozen=True, independent_review_accepted=True,
                analysis_code_digest='frozen-code',
                independent_review=dict(path=str(review), sha256=runner.vc.sha256(review)))
            runner.write(approval_path, approval)
            runner.verify_authorization(approval_path, plan_path, plan)
            for key in ('plan_sha256', 'execution_permitted', 'cpu_only', 'profiles_code_frozen',
                        'independent_review_accepted', 'analysis_code_digest', 'independent_review'):
                bad = deepcopy(approval)
                bad.pop(key)
                runner.write(approval_path, bad)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    runner.verify_authorization(approval_path, plan_path, plan)
            runner.write(approval_path, approval)
            runner.write(review, {'review': 'changed'})
            with self.assertRaises(ValueError):
                runner.verify_authorization(approval_path, plan_path, plan)

    def test_code_and_preserved_file_mutations_rejected(self):
        plan = dict(code_sha256={'code': 'a'}, preserved_sha256={'old': 'b'},
                    input_sha256={'new': 'c'}, environment={'python': 'frozen'})
        with patch.object(runner, 'code_binding', return_value=plan['code_sha256']), \
                patch.object(runner, 'bindings', side_effect=lambda x: x), \
                patch.object(runner, 'environment_binding', return_value=plan['environment']):
            runner.verify_plan(plan)
        with patch.object(runner, 'code_binding', return_value={'code': 'changed'}), \
                self.assertRaises(ValueError):
            runner.verify_plan(plan)
        with patch.object(runner, 'code_binding', return_value=plan['code_sha256']), \
                patch.object(runner, 'bindings', return_value={'old': 'changed'}), self.assertRaises(ValueError):
            runner.verify_plan(plan)
        with patch.object(runner, 'code_binding', return_value=plan['code_sha256']), \
                patch.object(runner, 'bindings', side_effect=lambda x: x), \
                patch.object(runner, 'environment_binding', return_value={'python': 'changed'}), \
                self.assertRaises(ValueError):
            runner.verify_plan(plan)

    def test_command_is_exact_whole_original_with_explicit_cache_and_no_queue(self):
        row = dict(video_path='source', scene='scene', portal='portal', cache='cache', output_path='new-output')
        cmd = runner.command(dict(python='python', registry_path='registry'), row)
        self.assertIn('--whole', cmd)
        self.assertEqual(cmd[cmd.index('--cache') + 1], 'cache')
        self.assertIn('--camera-registry', cmd)
        self.assertFalse(any('queue' in item or 'cuda' in item for item in cmd))

    def test_registry_rejects_source_assignment_and_non_c5_change(self):
        original = dict(schema_version=1, sources={'source': {'camera_id': 'C5', 'sha256': 'same'}},
                        cameras={'C5': {}, 'C3': {'frozen': True}})
        for mutation in ('source', 'other_camera', 'missing_camera'):
            changed = deepcopy(original)
            if mutation == 'source':
                changed['sources']['source']['sha256'] = 'different'
            elif mutation == 'other_camera':
                changed['cameras']['C3']['frozen'] = False
            else:
                changed['cameras'].pop('C3')
            with patch.object(runner.vc, 'read', return_value=changed), self.assertRaises(ValueError):
                runner.validate_registry('unused', [], original)


class TruthAndNotices(unittest.TestCase):
    def test_later_hit_does_not_erase_early_unknown_notice(self):
        from sceneguard.accuracy_evaluation import score_video
        row = dict(video_id='synthetic', split='additional', duration_seconds=20., processed_seconds=20.,
            execution_status='complete', truth_basis='official_reference',
            events=[dict(id='gold', gate_id='gate', start=10., end=12., onset_precise=False,
                         provenance='synthetic fixture')],
            verified_non_event_intervals=[], predictions=[dict(id='card', gate_id='gate',
                suspicion_evidence_pts=[5., 11.], confirmation_evidence_pts=[],
                notifications=[dict(kind='suspicion', pts=5.)])])
        result = score_video(row, 'suspicion')['counts']
        self.assertEqual((result['tp'], result['fn']), (1, 0))
        self.assertEqual(result['early_first_notices_for_matched_events'], 1)
        self.assertEqual(result['unreviewed_notices'], 1)
        self.assertEqual(result['false_notices_in_verified_negative'], 0)
        row['verified_non_event_intervals'] = [dict(gate_id='gate', start=4., end=6.,
                                                  provenance='synthetic reviewed fixture')]
        result = score_video(row, 'suspicion')['counts']
        self.assertEqual(result['tp'], 1)
        self.assertEqual(result['false_notices_in_verified_negative'], 1)


if __name__ == '__main__':
    unittest.main()
