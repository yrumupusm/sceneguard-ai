"""Candidate admission and unchanged primary routing; no video accuracy claims."""
from copy import deepcopy
from dataclasses import asdict
import unittest
from unittest.mock import patch

from sceneguard.legacy_directional import inner_loss_candidates, loss_appearance_candidates, RULE
from sceneguard.mvp_pipeline import analyze_observations, RuleBackend
from sceneguard.incident_cards import GroupPolicy
from sceneguard.portal_births import make_region
from test_legacy_directional import fixture, SCOPE


def bundle(frames):
    return dict(video_id='synthetic', events=[], policy=asdict(GroupPolicy()),
                source_window=[frames[0]['pts'], frames[-1]['pts']])


def generate(data, original=None):
    b, fs, s = data
    return inner_loss_candidates(b, bundle(fs) if original is None else original, fs, s, SCOPE, 'run')


def analyze(data, original=None):
    b, fs, s = data
    region = make_region(s, 'C3', s['approach_polygon'], reference_pts=0, note='synthetic')
    return analyze_observations(b, bundle(fs) if original is None else original,
                                fs, s, region, SCOPE, 'run')


class InnerLossCandidateTests(unittest.TestCase):
    def test_actual_inner_support_is_suspicion_with_explicit_source(self):
        data = fixture(); before = deepcopy(data)
        events, sources = generate(data)
        self.assertEqual(len(events), 1)
        e = events[0]; raw = e['source_event']
        self.assertEqual(e['source_ref']['collection'], 'inner_boundary_loss_candidates')
        self.assertEqual(raw['original_source_ref']['source_pointer'], '/segments/0')
        self.assertEqual(raw['original_source_ref']['segment'], 'source')
        self.assertEqual(sources[0]['rows'], data[0]['segments'][0]['rows'])
        self.assertEqual(raw['decision_time_pts'], 3.)
        self.assertEqual(raw['last_observed_pts'], 2.)
        self.assertFalse(raw['automatic_confirmation'])
        self.assertFalse(raw['confirmed_intrusion'])
        self.assertEqual(data, before)
        sources[0]['rows'][0]['bbox'][0] = 0.
        raw['near_observation_refs'][0]['bbox'][0] = 0.
        self.assertEqual(data, before)

    def test_default_minimum_two_near_measurements(self):
        for x, expected in ((.481, 1), (.469, 0)):
            data = fixture(); data[2]['inner_line'] = [[x,.2],[x,.8]]
            events, _ = generate(data)
            self.assertEqual(len(events), expected)
            if events:
                self.assertEqual(len(events[0]['source_event']['near_observation_refs']), 2)

    def test_recent_support_expires_after_existing_three_seconds(self):
        data = fixture(total=81); b, fs, s = data
        for i in range(21,61):
            x = min(.9, .63+(i-20)*.025)
            box = dict(cache_index=0, score=.9, bbox=[x-.025,.4,x+.025,.6], observed=True)
            fs[i]['actual_boxes'] = [deepcopy(box)]
            b['segments'][0]['rows'].append(dict(pts=i/10, frame_index=i, **box))
        self.assertEqual(generate(data), ([], []))

    def test_finite_endcaps_do_not_become_infinite_line(self):
        for end, expected in ((.5, 1), (.2, 0)):
            data = fixture(); data[2]['inner_line'] = [[.6,.1],[.6,end]]
            self.assertEqual(len(generate(data)[0]), expected)

    def test_bottom_center_not_old_box_midpoint(self):
        data = fixture(); b, fs, s = data
        s['inner_line'] = [[.6,.58],[.6,.8]]
        for row in b['segments'][0]['rows']:
            row['bbox'][1] = .3
            fs[row['frame_index']]['actual_boxes'][0]['bbox'] = deepcopy(row['bbox'])
        events, _ = generate(data)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['source_event']['boundary_position_formula'], 'bbox_bottom_center')

    def test_outside_no_inner_and_disabled_direction_no_change(self):
        cases = [fixture(True), fixture(), fixture()]
        del cases[1][2]['inner_line']
        cases[2][2]['directions'] = ['outside_to_inside']
        for data in cases:
            self.assertEqual(generate(data), ([], []))

    def test_predicted_unobserved_unconfirmed_or_wrong_refs_not_sources(self):
        for flag, value in (('predicted',True), ('observed',False), ('confirmed',False)):
            for location in ('source', 'actual'):
                data = fixture()
                row = data[0]['segments'][0]['rows'][-1] if location == 'source' else data[1][20]['actual_boxes'][0]
                row[flag] = value
                self.assertEqual(generate(data), ([], []))
        data = fixture(); data[0]['segments'][0]['rows'][-1]['cache_index'] = 99
        self.assertEqual(generate(data), ([], []))

    def test_eof_and_source_clock_gap_do_not_supply_loss_wait(self):
        data = fixture(total=30)
        self.assertEqual(generate(data), ([], []))
        data = fixture()
        for f in data[1][25:]:
            f['pts'] += .2; f['native_pts'] += 2
        self.assertEqual(generate(data), ([], []))

    def test_continued_source_rejects_even_changed_raw_id(self):
        data = fixture()
        box = deepcopy(data[1][20]['actual_boxes'][0]); box.update(cache_index=99, track_ids=[999])
        data[1][27]['actual_boxes'].append(box)
        self.assertEqual(generate(data), ([], []))

    def test_stationary_and_retreating_losses_are_not_motion_filtered(self):
        for retreat in (False, True):
            data = fixture()
            for n, row in enumerate(data[0]['segments'][0]['rows']):
                x = .63+n*.003 if retreat else .63
                row['bbox'] = [x-.025,.4,x+.025,.6]
                data[1][row['frame_index']]['actual_boxes'][0]['bbox'] = deepcopy(row['bbox'])
            self.assertEqual(len(generate(data)[0]), 1)

    def test_existing_same_source_loss_not_duplicated_or_mutated(self):
        data = fixture(); original = bundle(data[1])
        original['events'] = [dict(**SCOPE, event_id='original', video_id='synthetic',
            status='침입 의심', decision_time_pts=3., track_ids=[7],
            source_ref=dict(collection='events', source_pointer='/events/0'),
            source_event=dict(segment='source', raw_id=7, reason='recent_gate_presence_then_loss',
                decision_time_pts=3., last_observed_pts=2.))]
        before = deepcopy(original)
        self.assertEqual(generate(data, original), ([], []))
        result = analyze(data, original)
        self.assertIn(before['events'][0], result['cards']['events'])
        self.assertEqual(original, before)

    def test_future_reused_raw_id_does_not_erase_or_rewrite_candidate(self):
        data = fixture(total=71); b, fs, _ = data
        expected = generate((deepcopy(b), deepcopy(fs[:31]), deepcopy(data[2])))
        for i in range(50,56):
            box = deepcopy(fs[20]['actual_boxes'][0])
            fs[i]['actual_boxes'].append(box)
            b['segments'][0]['rows'].append(dict(pts=i/10, frame_index=i, **deepcopy(box)))
        events, sources = generate(data)
        self.assertEqual([e for e in events if e['decision_time_pts'] <= 3.], expected[0])
        self.assertEqual(sources[0], expected[1][0])
        self.assertEqual(analyze(data)['seed_decisions'][1]['direction']['direction'], 'unknown')

    def test_unknown_direction_stays_suspicion_and_auxiliary_evidence_is_identical(self):
        data = fixture(); expected_events, expected_decisions = loss_appearance_candidates(*data, SCOPE, 'run')
        before = deepcopy(data); result = analyze(data)
        auxiliary = [d for d in result['seed_decisions'] if d['rule_id'] == RULE]
        self.assertEqual(auxiliary, expected_decisions)
        self.assertTrue(all(e in result['cards']['events'] for e in expected_events))
        new = [d for d in result['seed_decisions'] if d['source_ref']['collection'] == 'inner_boundary_loss_candidates']
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]['direction']['direction'], 'unknown')
        self.assertFalse(new[0]['automatic_confirmation'])
        self.assertEqual(new[0]['status'], '침입 의심')
        self.assertEqual(data, before)

    def test_existing_target_bound_features_can_confirm_new_candidate(self):
        data = fixture(); b, fs, _ = data
        for row in b['segments'][0]['rows']:
            x = (row['bbox'][0]+row['bbox'][2])*500
            fs[row['frame_index']]['point_paths'] = [dict(window_id='target', seed_pts=1.,
                seed_cache_index=0, seed_track_ids=[7], point_ids=[0,1,2,3],
                points_original_pixels=[[x-3,450],[x-1,460],[x+1,470],[x+3,480]])]
        result = analyze(data)
        new = [d for d in result['seed_decisions'] if d['source_ref']['collection'] == 'inner_boundary_loss_candidates']
        self.assertEqual(new[0]['direction']['direction'], 'outward')
        self.assertTrue(new[0]['automatic_confirmation'])
        self.assertEqual(new[0]['rule_id'], 'outward_gate_loss_v1')

    def test_shared_saved_and_live_route_uses_original_auxiliary_inputs(self):
        data = fixture(); b, fs, s = data
        original = loss_appearance_candidates
        with patch('sceneguard.legacy_directional.loss_appearance_candidates', wraps=original) as helper:
            analyze(data)
        self.assertIs(helper.call_args.args[0], b)
        # execute uses this same analysis entrypoint after current measurements.
        import inspect
        from sceneguard.mvp_pipeline import execute
        self.assertIn('results = analyze_observations(baseline, bundle, observations,', inspect.getsource(execute))

    def test_causal_prefix_pipeline_notifications_and_timeline(self):
        data = fixture(total=61); full = analyze(data)
        short = (deepcopy(data[0]), deepcopy(data[1][:31]), deepcopy(data[2]))
        prefix = analyze(short)
        self.assertEqual(prefix['seed_decisions'], [d for d in full['seed_decisions'] if d['decision_time_pts'] <= 3.])
        for key in ('notification_intents', 'timeline'):
            self.assertEqual(prefix['cards'][key], [r for r in full['cards'][key] if r['decision_time_pts'] <= 3.])


if __name__ == '__main__':
    unittest.main()
