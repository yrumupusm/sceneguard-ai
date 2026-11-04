"""Independent synthetic passage contracts; never CCTV accuracy or foot truth.

Run against the implementation checkout with its root first on PYTHONPATH.
The pre-implementation review revision has no dual_boundary module and skips.
"""
import unittest
from copy import deepcopy
from dataclasses import asdict

try:
    from sceneguard.dual_boundary import Corridor, PassageState
except ModuleNotFoundError as error:
    if error.name != 'sceneguard.dual_boundary':
        raise
    Corridor = PassageState = None


def scene():
    return dict(source_size=[1000, 1000],
        line=[[.4, .2], [.4, .8]], inner_line=[[.6, .2], [.6, .8]],
        approach_polygon=[[.2, .05], [.8, .05], [.8, .95], [.2, .95]],
        zones={'outside': [[0, 0], [.39, 0], [.39, 1], [0, 1]],
               'inside': [[.61, 0], [1, 0], [1, 1], [.61, 1]]},
        directions=['outside_to_inside', 'inside_to_outside'])


def observe(positions):
    state = PassageState(Corridor(scene()))
    for i, (x, y) in enumerate(positions):
        # Exactly (x,y) at the documented 65%-height image proxy.
        state.step(dict(pts=i/10, frame_index=i, cache_index=0,
            bbox=[x-.03, y-.13, x+.03, y+.07], observed=True))
    return state


def mirror(positions):
    return [(1-x, y) for x, y in positions]


def passage():
    return [(.35, .5), (.36, .5), (.37, .5)] + [
        (x, .5) for x in (.41, .45, .50, .55, .60, .65, .66, .67)]


def production_fixture(positions, *, absent=(), paths=True, selected_scene=None):
    """Independent actual-measurement fixture; use the real run builder/backend.

    No helper-created observation runs are supplied to analyze_observations.
    Four saved points move with the box; no optical flow is computed.
    """
    from sceneguard.approach_disappearance import Policy
    from sceneguard.incident_cards import GroupPolicy
    from sceneguard.portal_births import make_region
    sc = deepcopy(selected_scene or scene())
    frames, rows = [], []
    for i, (x, y) in enumerate(positions):
        row = dict(pts=i/10, frame_index=i, cache_index=0,
            bbox=[x-.03, y-.13, x+.03, y+.07])
        box = dict(cache_index=0, bbox=deepcopy(row['bbox']), score=.9,
            observed=True, track_ids=[7], assignment='confirmed_track')
        if i not in absent:
            rows.append(row)
        frames.append(dict(frame_index=i, pts=i/10, native_pts=i, time_base='1/10',
            actual_boxes=[] if i in absent else [box], camera_step_pixels=[0., 0.],
            point_paths=[dict(window_id='review-points', seed_pts=0., seed_cache_index=0,
                seed_track_ids=[7], point_ids=[0, 1, 2, 3],
                points_original_pixels=[[x*1000, y*1000-15+j*5] for j in range(4)])] if paths else []))
    event = dict(event_id='review-event', decision_time_pts=.1, track_ids=[7],
        status='침입 의심', session_id='review-recording', camera_id='review-camera',
        gate_id='review-gate', video_id='review-synthetic',
        source_ref=dict(collection='events', source_pointer='/events/0'),
        source_event=dict(segment='review-segment', raw_id=7,
            decision_time_pts=.1, reason='recent_gate_presence_then_loss'))
    baseline = dict(video_id='review-synthetic',
        segments=[dict(id='review-segment', raw_id=7, rows=rows)], policy=asdict(Policy()))
    bundle = dict(video_id='review-synthetic', events=[event], decisions=[],
        source_window=[0., frames[-1]['pts']], policy=asdict(GroupPolicy()))
    region = make_region(sc, 'review-camera', sc['approach_polygon'], reference_pts=0.,
        note='Independent synthetic finite-passage review, not CCTV truth')
    return baseline, bundle, frames, sc, region


def analyze_fixture(args):
    from sceneguard.mvp_pipeline import analyze_observations
    before = deepcopy(args)
    result = analyze_observations(*args,
        dict(session_id='review-recording', camera_id='review-camera', gate_id='review-gate'),
        'independent-dual-review')
    assert args == before, 'Production pipeline mutated source fixture'
    return result


def confirmations(result):
    return [r for r in result['scoped_lifecycle']['resolutions']
        if r.get('confirmation_source') == 'dual_boundary_passage_v1']


@unittest.skipIf(PassageState is None, 'Implementation module absent at preflight baseline')
class IndependentDualBoundaryReview(unittest.TestCase):
    def test_touch_then_walk_past_endpoint_is_not_finite_passage(self):
        inward = ([(.35, .5)]*3 + [(x, .5) for x in [.4, .45, .5, .55, .6]]
            + [(.6, y) for y in [.55, .6, .65, .7, .75, .8, .85]]
            + [(.65, .85)]
            + [(.65, y) for y in [.8, .75, .7, .65, .6, .55, .5]]
            + [(.65, .5)]*3)
        for positions in (inward, mirror(inward)):
            with self.subTest(start=positions[0]):
                decision = observe(positions).decision((len(positions)-1)/10)
                self.assertFalse(decision['automatic_confirmation'])

    def test_real_two_boundary_crossings_work_symmetrically(self):
        inward = [(.35, .5)]*3 + [(x, .5) for x in [.4, .45, .5, .55, .6]] + [(.65, .5)]*3
        for positions, expected in ((inward, 'outside_to_inside'),
                (mirror(inward), 'inside_to_outside')):
            with self.subTest(direction=expected):
                decision = observe(positions).decision((len(positions)-1)/10)
                self.assertTrue(decision['automatic_confirmation'])
                self.assertEqual(decision['direction'], expected)

    def test_corridor_dwell_retains_origin_beyond_old_three_second_window(self):
        positions = [(.35, .5)]*3 + [(.4, .5), (.45, .5)] + [(.5, .5)]*40 + [(.55, .5), (.6, .5)] + [(.65, .5)]*3
        decision = observe(positions).decision((len(positions)-1)/10)
        self.assertTrue(decision['automatic_confirmation'])

    def test_stationary_corridor_dwell_is_not_passage(self):
        for x in (.4, .5, .6, .65):
            with self.subTest(x=x):
                self.assertFalse(observe([(x, .5)]*50).decision(4.9)['automatic_confirmation'])

    def test_future_destination_dwell_cannot_confirm_prefix(self):
        positions = [(.35, .5)]*3 + [(x, .5) for x in [.4, .45, .5, .55, .6]] + [(.65, .5)]*3
        self.assertFalse(observe(positions[:-1]).decision(.9)['automatic_confirmation'])
        self.assertTrue(observe(positions).decision(1.)['automatic_confirmation'])

    def test_actual_passage_stays_positive_after_continuous_return(self):
        positions = [(.35, .5)]*3 + [(x, .5) for x in [.4, .45, .5, .55, .6]] + [(.65, .5)]*3
        positions += [(x, .5) for x in [.6, .55, .5, .45, .4]] + [(.35, .5)]*3
        for path in (positions, mirror(positions)):
            with self.subTest(start=path[0]):
                self.assertTrue(observe(path).decision((len(path)-1)/10)['automatic_confirmation'])


@unittest.skipIf(PassageState is None, 'Implementation module absent at preflight baseline')
class IndependentProductionReview(unittest.TestCase):
    def test_real_backend_symmetric_passage_and_sticky_return(self):
        for path in (passage(), mirror(passage())):
            with self.subTest(start=path[0]):
                first = analyze_fixture(production_fixture(path))
                returned = analyze_fixture(production_fixture(path + list(reversed(path))))
                self.assertEqual(len(confirmations(first)), 1)
                self.assertEqual(returned['cards']['counts']['confirmation_notifications'], 1)
                self.assertEqual(first['scoped_lifecycle']['evidence'][0]['first_confirmation_pts'], 1.)
                self.assertEqual(returned['scoped_lifecycle']['evidence'][0]['first_confirmation_pts'], 1.)
                self.assertTrue(first['cards']['dual_boundary_rules_enabled'])
                self.assertTrue(all(not d['automatic_confirmation'] for d in first['seed_decisions']))
                self.assertFalse(any(r['kind'] == 'outward_loss' for r in returned['scoped_lifecycle']['resolutions']))

    def test_every_production_prefix_preserves_decision_clock(self):
        path = passage() + list(reversed(passage()))
        full = analyze_fixture(production_fixture(path))
        for length in range(3, len(path)):
            with self.subTest(length=length):
                prefix = analyze_fixture(production_fixture(path[:length]))
                at = (length-1)/10
                self.assertEqual(prefix['scoped_lifecycle']['timeline'],
                    [row for row in full['scoped_lifecycle']['timeline'] if row['decision_time_pts'] <= at])
                self.assertEqual(prefix['cards']['timeline'],
                    [row for row in full['cards']['timeline'] if row['decision_time_pts'] <= at])

    def test_contiguous_competing_boxes_cannot_inherit_origin(self):
        for mirrored in (False, True):
            path = mirror(passage()) if mirrored else passage()
            args = production_fixture(path, paths=False)
            for frame in args[2][3:]:
                competitor = deepcopy(frame['actual_boxes'][0])
                competitor['cache_index'] = 1
                shift = .04 if mirrored else -.04
                competitor['bbox'] = [v + (shift if k % 2 == 0 else 0)
                    for k, v in enumerate(competitor['bbox'])]
                frame['actual_boxes'].append(competitor)
            with self.subTest(mirrored=mirrored):
                self.assertEqual(len(confirmations(analyze_fixture(args))), 0)

    def test_many_sources_to_one_contiguous_box_is_not_identity_proof(self):
        args = production_fixture(passage(), paths=False)
        for frame in args[2][:3]:
            competitor = deepcopy(frame['actual_boxes'][0]); competitor['cache_index'] = 1
            competitor['bbox'] = [v - (.04 if k % 2 == 0 else 0)
                for k, v in enumerate(competitor['bbox'])]
            frame['actual_boxes'].append(competitor)
        self.assertEqual(len(confirmations(analyze_fixture(args))), 0)

    def test_endpoint_touch_walk_past_then_return_cannot_confirm(self):
        path = passage()[:8] + [(.6, y) for y in (.55,.6,.65,.7,.75,.8,.85)]
        path += [(.65,.85)] + [(.65,y) for y in (.8,.75,.7,.65,.6,.55,.5)] + [(.65,.5)]*3
        for p in (path, mirror(path)):
            self.assertEqual(confirmations(analyze_fixture(production_fixture(p))), [])

    def test_five_vertex_inner_joint_and_chord_difference(self):
        sc = scene(); sc['inner_line'] = [[.6,.2],[.62,.35],[.68,.5],[.62,.65],[.6,.8]]
        stopped = passage()[:8] + [(.65,.5)]*4
        self.assertEqual(confirmations(analyze_fixture(production_fixture(stopped, selected_scene=sc))), [])
        crossed = stopped + [(.68,.5)] + [(.72,.5)]*3
        result = analyze_fixture(production_fixture(crossed, selected_scene=sc))
        self.assertEqual(len(confirmations(result)), 1)
        self.assertEqual(len(result['cards']['dual_boundary_audit']['geometry']['inner_pixels']), 5)

    def test_long_corridor_origin_and_explicit_episode_expiry(self):
        path = passage()[:5] + [(.5,.5)]*40 + passage()[6:]
        self.assertEqual(len(confirmations(analyze_fixture(production_fixture(path)))), 1)
        expired = passage()[:5] + [(.5,.5)]*605 + passage()[6:]
        self.assertEqual(confirmations(analyze_fixture(production_fixture(expired))), [])

    def test_unique_saved_point_gap_and_same_numeric_id_without_points(self):
        for points, expected in ((True, 1), (False, 0)):
            args = production_fixture(passage(), absent=(6,7), paths=points)
            result = analyze_fixture(args)
            with self.subTest(points=points):
                self.assertEqual(len(confirmations(result)), expected)
                if expected:
                    decision = confirmations(result)[0]['source_decision']
                    self.assertEqual(decision['exit']['measurement'], 'saved_point_path')
                    self.assertTrue(decision['associations'][0]['missing_box_interval_is_not_measured_box_path'])
                    self.assertTrue(all(r['frame_index'] not in (6,7)
                        for r in decision['passage']['destination_observation_refs']))

    def test_loss_wait_fresh_direction_stationary_tail_and_eof(self):
        moving = passage()[:7]  # actual entry and opposing corridor half, no inner crossing
        for path in (moving, mirror(moving)):
            self.assertEqual(confirmations(analyze_fixture(production_fixture(path))), [])
            for points, expected in ((True, 1), (False, 0)):
                extended = path + [path[-1]]*15
                result = analyze_fixture(production_fixture(extended,
                    absent=range(len(path),len(extended)), paths=points))
                with self.subTest(start=path[0], points=points):
                    self.assertEqual(len(confirmations(result)), expected)
                    if expected:
                        decision = confirmations(result)[0]['source_decision']
                        self.assertAlmostEqual(decision['decision_time_pts'], 1.6)
                        self.assertNotIn('passage', decision)
                        self.assertEqual(decision['reason'], 'origin_entry_progress_and_directed_corridor_loss')
            stopped = path + [path[-1]]*15
            result = analyze_fixture(production_fixture(stopped + [path[-1]]*15,
                absent=range(len(stopped), len(stopped)+15)))
            self.assertEqual(confirmations(result), [])

    def test_same_side_return_neither_confirms_nor_releases(self):
        path = passage()[:7] + list(reversed(passage()[:7])) + [(.35,.5)]*15
        args = production_fixture(path, absent=range(14,len(path)))
        result = analyze_fixture(args)
        self.assertEqual(confirmations(result), [])
        self.assertTrue(all(e['released_pts'] is None for e in result['scoped_lifecycle']['evidence']))

    def test_existing_alert_requires_exact_anchors_and_emission(self):
        for after, expected in ((.8, 1), (.85, 0), (1.1, 0)):
            args = production_fixture(passage())
            e = args[1]['events'][0]; e['decision_time_pts'] = 1.
            e['source_ref']['collection'] = 'existing_alerts'
            e['source_event'] = dict(track_id=7, observed_pts_before=.2,
                observed_pts_after=after, emitted_at_pts=1.)
            with self.subTest(after=after):
                self.assertEqual(len(confirmations(analyze_fixture(args))), expected)

    def test_one_passage_confirms_only_latest_linked_evidence(self):
        from sceneguard.incident_cards import GroupPolicy
        args = production_fixture(passage()+[(.67,.5)]*15)
        args[1]['policy'] = asdict(GroupPolicy(gap_seconds=.05, max_span_seconds=10.))
        old = deepcopy(args[1]['events'][0]); old['event_id'] = 'older'; old['decision_time_pts'] = 0.
        late = deepcopy(args[1]['events'][0]); late['event_id'] = 'late'; late['decision_time_pts'] = 1.1
        args[1]['events'] = [old, args[1]['events'][0], late]
        result = analyze_fixture(args)
        evidence = {e['event_id']:e for e in result['scoped_lifecycle']['evidence']}
        self.assertEqual(evidence['review-event']['automatic_status'], '침입 확인')
        self.assertEqual(evidence['older']['automatic_status'], '침입 의심')
        self.assertEqual(evidence['late']['automatic_status'], '침입 의심')
        self.assertEqual(len(confirmations(result)), 1)

    def test_source_gap_cannot_supply_loss_or_inherit_origin(self):
        args = production_fixture(passage())
        for frame in args[2][6:]:
            frame['pts'] += 1.; frame['native_pts'] += 10
        for row in args[0]['segments'][0]['rows'][6:]: row['pts'] += 1.
        args[1]['source_window'][1] += 1.
        self.assertEqual(confirmations(analyze_fixture(args)), [])

    def test_self_overlapping_and_malformed_contours_fail_closed(self):
        for inner in ([[.6,.2],[.6,.7],[.6,.4],[.6,.8]],
                [[.6,.2],[.7,.4],[.6,.2],[.6,.8]],
                [[.6,.2],[float('inf'),.5],[.6,.8]], [], [[.6,.2],[.6,.2]]):
            sc = scene(); sc['inner_line'] = inner
            with self.subTest(inner=inner), self.assertRaises(ValueError):
                # Use production so validation is tested before any positive path.
                analyze_fixture(production_fixture(passage(), selected_scene=sc))

    def test_saved_point_gap_competitors_and_interrupted_point_paths(self):
        for mode in ('competing', 'interrupted'):
            args = production_fixture(passage()+[(.67,.5)]*10, absent=(6,7))
            if mode == 'competing':
                for frame in args[2][8:]:
                    other = deepcopy(frame['actual_boxes'][0]); other['cache_index'] = 1
                    other['bbox'] = [v + (.015 if k % 2 == 0 else 0) for k,v in enumerate(other['bbox'])]
                    frame['actual_boxes'].append(other)
            else:
                args[2][7]['point_paths'] = []
            with self.subTest(mode=mode):
                self.assertEqual(len(confirmations(analyze_fixture(args))), 0)

    def test_stale_saved_direction_cannot_confirm_new_motion_loss(self):
        path = passage()[:4] + [(.42+i*.005,.5) for i in range(27)]
        args = production_fixture(path+[path[-1]]*15, absent=range(len(path),len(path)+15))
        for frame in args[2][5:]: frame['point_paths'] = []
        self.assertEqual(len(confirmations(analyze_fixture(args))), 0)

    def test_disabled_direction_predicted_input_and_no_candidate(self):
        sc = scene(); sc['directions'] = ['inside_to_outside']
        self.assertEqual(len(confirmations(analyze_fixture(production_fixture(passage(), selected_scene=sc)))), 0)
        args = production_fixture(passage()); args[2][4]['actual_boxes'][0]['predicted'] = True
        with self.assertRaises(ValueError): analyze_fixture(args)
        args = production_fixture(passage()); args[1]['events'] = []
        result = analyze_fixture(args)
        self.assertEqual(result['cards']['counts']['confirmation_notifications'], 0)
        self.assertEqual(result['cards']['events'], [])

    def test_later_competition_never_erases_confirmed_passage(self):
        args = production_fixture(passage()+list(reversed(passage())), paths=False)
        for frame in args[2][11:]:
            other = deepcopy(frame['actual_boxes'][0]); other['cache_index'] = 1
            other['bbox'] = [v + (.04 if k % 2 == 0 else 0) for k,v in enumerate(other['bbox'])]
            frame['actual_boxes'].append(other)
        result = analyze_fixture(args)
        self.assertEqual(result['scoped_lifecycle']['evidence'][0]['first_confirmation_pts'], 1.)
        self.assertEqual(result['scoped_lifecycle']['evidence'][0]['automatic_status'], '침입 확인')
        self.assertEqual(result['cards']['counts']['confirmation_notifications'], 1)

    def test_known_limit_ambiguous_run_veto_suppresses_even_fresh_episode(self):
        # Deliberately records a recall limitation, not successful recovery.
        # A future episode-reset design must also quarantine old pending evidence.
        from sceneguard.incident_cards import GroupPolicy
        path = [(.35,.5)]*7 + passage()[3:]
        args = production_fixture(path, paths=False)
        for frame in args[2][:2]:
            other = deepcopy(frame['actual_boxes'][0]); other['cache_index'] = 1
            other['bbox'] = [v - (.04 if k % 2 == 0 else 0) for k,v in enumerate(other['bbox'])]
            frame['actual_boxes'].append(other)
        new = deepcopy(args[1]['events'][0]); new['event_id'] = 'fresh-episode'
        new['decision_time_pts'] = .6; new['source_event']['decision_time_pts'] = .6
        args[1]['events'].append(new)
        args[1]['policy'] = asdict(GroupPolicy(gap_seconds=.05, max_span_seconds=10.))
        result = analyze_fixture(args)
        evidence = {e['event_id']:e for e in result['scoped_lifecycle']['evidence']}
        self.assertEqual(evidence['fresh-episode']['automatic_status'], '침입 의심')
        self.assertEqual(evidence['review-event']['automatic_status'], '침입 의심')
        self.assertEqual(confirmations(result), [])


if __name__ == '__main__':
    unittest.main()
