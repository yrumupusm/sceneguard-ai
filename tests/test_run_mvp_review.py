import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sceneguard.run_mvp_review import (SOURCE_FILES, enrich_feed, execute, input_spec,
                                       verify_hashes, validate_saved_observations)
from sceneguard.mvp_review_quality import QualitySettings
from dataclasses import asdict
from sceneguard.run_tracklet_linking import sha256
from sceneguard.tracklet_linking import LinkSettings, build_tracklets, endpoint_rows


def fixture():
    settings = LinkSettings()
    frames = [dict(pts=i/30, detections=[dict(track_id=1, bbox=[.1, .1, .2, .3],
                  score=.9, cache_index=0, observed=True)]) for i in range(5)]
    segments = build_tracklets(frames, settings)
    reps = {'t0001': {end: endpoint_rows(segments[0], end, settings) for end in ('head', 'tail')}}
    associations = dict(chains=[dict(id='p0001', segments=['t0001'])], mapping=dict(t0001='p0001'), links=[])
    return settings, frames, segments, reps, associations


class RunnerTests(unittest.TestCase):
    def test_saved_partition_valid_and_unchanged(self):
        settings, frames, segments, reps, assoc = fixture()
        before = copy.deepcopy((frames, segments, reps, assoc))
        self.assertEqual(validate_saved_observations([], frames, segments, assoc, reps, settings), reps)
        self.assertEqual((frames, segments, reps, assoc), before)

    def test_saved_prediction_substitution_rejected(self):
        settings, frames, segments, reps, assoc = fixture()
        segments[0]['rows'][0]['bbox'][0] = .15
        with self.assertRaisesRegex(ValueError, 'real observed row'):
            validate_saved_observations([], frames, segments, assoc, reps, settings)

    def test_missing_observation_rejected(self):
        settings, frames, segments, reps, assoc = fixture()
        segments[0]['rows'].pop(1)
        segments[0]['observations'] -= 1
        with self.assertRaisesRegex(ValueError, 'omit observed rows'):
            validate_saved_observations([], frames, segments, assoc, reps, settings)

    def test_original_accepted_chain_not_fabricated(self):
        settings, frames, segments, reps, assoc = fixture()
        assoc['links'] = [dict(before='t0001', after='t0001', status='accepted')]
        with self.assertRaisesRegex(ValueError, 'Accepted original links'):
            validate_saved_observations([], frames, segments, assoc, reps, settings)

    def test_representative_removal_rejected(self):
        settings, frames, segments, reps, assoc = fixture()
        reps['t0001']['head'].pop()
        with self.assertRaisesRegex(ValueError, 'representative selections'):
            validate_saved_observations([], frames, segments, assoc, reps, settings)

    def test_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'source'
            path.write_text('before')
            frozen = {str(path): sha256(path)}
            verify_hashes(frozen)
            path.write_text('after')
            with self.assertRaisesRegex(ValueError, 'Frozen file changed'):
                verify_hashes(frozen)

    def test_four_clocks_and_user_context_are_separate(self):
        feed = dict(events=[dict(id='line-0001', source='existing_gap_line'),
                            dict(id='region-0001', source='current_polygon_two_side')], link_suggestions=[])
        line = dict(candidate_pts=69.866, emitted_at_pts=70.133, candidate_interval=[69.8, 69.933], track_id=8)
        region = dict(candidate_interval=[72., 73.], confirmed_at=73.3, chain_id='p1',
                      before_segment='t1', after_segment='t2')
        data = dict(cached=[dict(pts=104.966)], gap_events=[line], region_events=[region],
                    segments=[], associations=dict(mapping={}), tracked=[], saved_features={}, representatives={})
        with patch('sceneguard.run_mvp_review.sha256', return_value='region_sha'), \
                patch('sceneguard.run_mvp_review.question_audit', return_value=[]), \
                patch('sceneguard.run_mvp_review.quality_diagnostics', return_value={}):
            result = enrich_feed(feed, data, input_spec('007'), '2026-10-30T00:00:00+00:00')
        event = result['events'][0]
        self.assertEqual(event['estimated_at_pts'], 69.866)
        self.assertEqual(event['original_emitted_at_pts'], 70.133)
        self.assertEqual(event['available_after_pts'], 104.966)
        self.assertEqual(event['output_utc'], '2026-10-30T00:00:00+00:00')
        self.assertIsNone(result['events'][1]['original_emitted_at_pts'])
        self.assertEqual(result['events'][1]['region_confirmed_at_pts'], 73.3)
        self.assertFalse(result['user_context'][0]['algorithm_detection'])
        self.assertEqual(len(result['events']), 2)

    def run_synthetic_execution(self, directory, renderer):
        settings, frames, segments, reps, assoc = fixture()
        data = dict(cached=[dict(pts=f['pts']) for f in frames], tracked=frames, segments=segments,
                    representatives=reps, associations=assoc, interval=1/30, settings=settings,
                    zones={'current': True}, gap_events=[],
                    saved_features={'features': {'t0001': dict(head=[[1., 0.]], tail=[[1., 0.]])}})
        frozen = dict(specs=[input_spec(k) for k in ('030', '007')],
                      quality_settings=asdict(QualitySettings()), output=str(directory/'result'),
                      region_mode='current_only_no_control', input_sha256={},
                      source_sha256={p: 'frozen' for p in SOURCE_FILES})
        manifest = directory/'manifest.json'
        manifest.write_text(json.dumps(frozen))
        def enriched(feed, data, spec, output_utc):
            feed.update(input_quality={'counts': {}}, question_audit=[], linkage_counts={}, output_utc=output_utc)
            return feed
        with patch('sceneguard.run_mvp_review.OUTPUT', directory/'result'), \
                patch('sceneguard.run_mvp_review.verify_hashes'), \
                patch('sceneguard.run_mvp_review.load_json', side_effect=[frozen, {}]), \
                patch('sceneguard.run_mvp_review.load_video_inputs', side_effect=[copy.deepcopy(data), copy.deepcopy(data)]), \
                patch('sceneguard.run_mvp_review.region_events', return_value=[]) as events, \
                patch('sceneguard.run_mvp_review.enrich_feed', side_effect=enriched):
            result = execute(manifest, renderer=renderer)
            return result, events

    def test_execution_uses_current_regions_once_per_video_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            from unittest.mock import Mock
            renderer = Mock(return_value={'status': 'synthetic_rendered'})
            result, events = self.run_synthetic_execution(directory, renderer)
            self.assertEqual(events.call_count, 2)
            self.assertEqual(renderer.call_count, 2)
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(result['polygon_comparisons'], 0)
            self.assertEqual(result['encoder_calls'], 0)
            self.assertFalse(list((directory/'result').glob('**/*control*')))
            with self.assertRaises(FileExistsError):
                self.run_synthetic_execution(directory, renderer)
            self.assertEqual(renderer.call_count, 2)

    def test_renderer_error_is_receipted_without_automatic_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            from unittest.mock import Mock
            renderer = Mock(side_effect=RuntimeError('synthetic encoder failure'))
            with self.assertRaisesRegex(RuntimeError, 'synthetic encoder failure'):
                self.run_synthetic_execution(directory, renderer)
            self.assertEqual(renderer.call_count, 1)
            failure = json.loads((directory/'result'/'failure-receipt.json').read_text())
            self.assertEqual(failure['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
