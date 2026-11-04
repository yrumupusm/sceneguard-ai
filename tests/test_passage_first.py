"""EXP0051 measured passage contracts; synthetic boxes are not CCTV truth."""
from copy import deepcopy
from dataclasses import asdict
import unittest

from test_dual_boundary import fixture, row, scene, state
from sceneguard.dual_boundary import Corridor, DualBoundaryDirection, RULE, distinct_paths, replay
from sceneguard.incident_cards import GroupPolicy
from sceneguard.incident_lifecycle import CONFIRMED, SUSPECTED
from sceneguard.lifecycle_followup import ObservationHistory
from sceneguard.mvp_pipeline import analyze_observations


PASSAGE = [400, 410, 420, 460, 490, 520, 560, 570, 580]


def duplicate(args, indices, shift):
    for i in indices:
        frame = args[3][i]
        box = deepcopy(frame['actual_boxes'][0]); box['cache_index'] = 1
        box['track_ids'] = [999]
        box['bbox'] = [v+(shift if k % 2 == 0 else 0) for k,v in enumerate(box['bbox'])]
        frame['actual_boxes'].append(box)


def analyze(args):
    b,h,r,f,s,p = args
    before = deepcopy(args)
    result = analyze_observations(b,h,f,s,p,
        dict(session_id='recording',camera_id='C',gate_id='G'),'passage-first-contract')
    assert args == before
    return result['scoped_lifecycle']


def decisions(result):
    return [r['source_decision'] for r in result['resolutions'] if r.get('confirmation_source') == RULE]


def newer(args, at, name='fresh'):
    h = args[1]
    event = deepcopy(h['events'][0]); event.update(event_id=name, decision_time_pts=at)
    h['events'].append(event)
    h['policy'] = asdict(GroupPolicy(gap_seconds=.05, max_span_seconds=10.))


class PassageFirstTests(unittest.TestCase):
    def test_equivalent_reset_hypotheses_collapse_without_discarding_distinct_origins(self):
        a = state([400,410,420,460]); b = state([600,590,580,540])
        self.assertEqual(len(distinct_paths([a,b])), 2)
        for path in (a,b):
            path.reset('source_gap_not_person_loss'); path.last = None
            path.step(row(500,20))
        self.assertEqual(len(distinct_paths([a,b])), 1)
        self.assertIsNone(a.origin)
        self.assertFalse(a.decision(2.)['automatic_confirmation'])

    def test_actual_duplicate_and_nearby_passage_both_directions(self):
        for mirrored in (False, True):
            for shift in (0., .004, .04):
                xs = [1000-x for x in PASSAGE] if mirrored else PASSAGE
                args = fixture(xs, paths=False)
                duplicate(args, range(3, len(xs)), shift)
                out = analyze(args)
                with self.subTest(mirrored=mirrored, shift=shift):
                    self.assertEqual(len(decisions(out)), 1)
                    self.assertFalse(decisions(out)[0]['identity_verified'])
                    self.assertEqual(out['events'], args[1]['events'])

    def test_contiguous_merge_is_measured_path_without_saved_points(self):
        for xs in (PASSAGE, [1000-x for x in PASSAGE]):
            args = fixture(xs, paths=False)
            duplicate(args, range(3), -.04)
            self.assertEqual(len(decisions(analyze(args))), 1)

    def test_duplicate_corridor_keeps_measured_origin_beyond_old_window(self):
        xs = PASSAGE[:4]+[490]*45+PASSAGE[5:]
        args = fixture(xs, paths=False); duplicate(args, range(3,len(xs)), -.004)
        decision = decisions(analyze(args))[0]
        self.assertLessEqual(max(r['pts'] for r in decision['origin_observation_refs']), .2)
        self.assertGreater(decision['decision_time_pts'], 3.)
        for ref in decision['origin_observation_refs']:
            self.assertEqual(Corridor(args[4]).classify(ref), 'outside')

    def test_local_ambiguity_recovers_current_candidate_and_keeps_old_pending(self):
        args = fixture([400]*7+PASSAGE[3:], paths=False)
        duplicate(args, range(2), -.04); newer(args, .6)
        out = analyze(args); evidence = {e['event_id']:e for e in out['evidence']}
        self.assertEqual(evidence['e']['automatic_status'], SUSPECTED)
        self.assertEqual(evidence['fresh']['automatic_status'], CONFIRMED)
        self.assertEqual(len(decisions(out)), 1)

    def test_real_break_does_not_transfer_new_independent_proof_to_old_candidate(self):
        for current in (False, True):
            xs = PASSAGE[:4]+[480]+PASSAGE
            args = fixture(xs, paths=False); args[3][4]['actual_boxes'] = []
            args[0]['segments'][0]['rows'] = [r for r in args[0]['segments'][0]['rows'] if r['frame_index'] != 4]
            if current: newer(args, .7)
            out = analyze(args); evidence = {e['event_id']:e for e in out['evidence']}
            self.assertEqual(evidence['e']['automatic_status'], SUSPECTED)
            if current: self.assertEqual(evidence['fresh']['automatic_status'], CONFIRMED)
            self.assertEqual(len(decisions(out)), 1)
            if not current:
                self.assertEqual(out['dual_boundary_audit']['derived_passage_candidates'], 1)

    def test_same_numeric_run_can_reappear_after_adjacent_handoff(self):
        args = fixture(PASSAGE, paths=False)
        b,h,r,f,s,p = args
        rows = r.pop('a')
        r.update(a=rows[:3]+rows[6:], b=rows[3:6])
        out,_ = replay(b,h,[],r,f,s,p)
        self.assertEqual(len(decisions(out)), 1)
        self.assertGreaterEqual(out['followup_counts']['observation_handoffs'], 2)

    def test_gap_duplicate_endpoint_uses_measured_points_not_bbox_chord(self):
        for xs in (PASSAGE, [1000-x for x in PASSAGE]):
            args = fixture(xs)
            for frame in args[3][4:6]: frame['actual_boxes'] = []
            args[0]['segments'][0]['rows'] = [r for r in args[0]['segments'][0]['rows'] if r['frame_index'] not in (4,5)]
            duplicate(args, range(6,len(xs)), .004)
            out = analyze(args); decision = decisions(out)[0]
            self.assertTrue(decision['associations'][0]['missing_box_interval_is_not_measured_box_path'])
            self.assertFalse(any(r['frame_index'] in (4,5) for r in decision['passage']['destination_observation_refs']))

    def test_supported_endpoint_ranking_has_no_crossing_or_identity_score(self):
        args = fixture(PASSAGE, split=6, second=True)
        b,h,r,f,s,p = args
        history = ObservationHistory(r,f)
        for frame in f[:7]: history.advance(frame)
        engine = DualBoundaryDirection(f,s)
        selected = engine.successor(history,'a',6)
        self.assertEqual(selected['successor'], 'b')
        self.assertEqual(len(selected['matches']), 2)
        self.assertEqual(selected['selected']['point_box_displacement_residual_heights'], 0.)
        self.assertFalse(selected['identity_verified'])

    def test_multiple_supported_sources_to_one_endpoint_keep_one_owner(self):
        args = fixture(PASSAGE, split=4)
        b,h,r,f,s,p = args
        r['c'] = []
        for i in range(4):
            other = deepcopy(f[i]['actual_boxes'][0]); other['cache_index'] = 1
            other['bbox'] = [v-(.01 if k%2 == 0 else 0) for k,v in enumerate(other['bbox'])]
            f[i]['actual_boxes'].append(other)
            r['c'].append(dict(row(PASSAGE[i]-10,i),cache_index=1))
        for frame in f:
            path = deepcopy(frame['point_paths'][0]); path['window_id'] = 'z'; path['seed_cache_index'] = 1
            if frame['frame_index'] < 4:
                path['points_original_pixels'] = [[x-10,y] for x,y in path['points_original_pixels']]
            frame['point_paths'].append(path)
        b['segments'].append(dict(id='c',raw_id=99,rows=deepcopy(r['c'])))
        event = deepcopy(h['events'][0]); event['event_id'] = 'other-source'; event['source_event']['segment'] = 'c'
        h['events'].append(event)
        out,_ = replay(b,h,[],r,f,s,p)
        evidence = {e['event_id']:e for e in out['evidence']}
        self.assertEqual(len(decisions(out)), 1)
        self.assertEqual(evidence['e']['automatic_status'], CONFIRMED)
        self.assertEqual(evidence['other-source']['automatic_status'], SUSPECTED)

    def test_no_points_cannot_fill_missing_actual_corridor(self):
        args = fixture(PASSAGE, paths=False)
        for frame in args[3][4:6]: frame['actual_boxes'] = []
        args[0]['segments'][0]['rows'] = [r for r in args[0]['segments'][0]['rows'] if r['frame_index'] not in (4,5)]
        self.assertEqual(decisions(analyze(args)), [])

    def test_weaker_supported_origin_path_is_retained_when_nearest_source_has_no_origin(self):
        xs = [460,465,470,475,490,520,560,570,580]
        args = fixture(xs, split=4, paths=False)
        b,h,r,f,s,p = args; r['c'] = []
        for i,x in enumerate([400,410,420,430]):
            actual = dict(row(x,i),cache_index=1)
            box = dict(cache_index=1,bbox=deepcopy(actual['bbox']),score=.9,observed=True,track_ids=[99])
            f[i]['actual_boxes'].append(box); r['c'].append(actual)
        out,_ = replay(b,h,[],r,f,s,p)
        self.assertEqual(len(decisions(out)), 1)
        self.assertEqual(out['dual_boundary_audit']['derived_passage_candidates'], 1)
        self.assertEqual(next(e for e in out['evidence'] if e['event_id']=='e')['automatic_status'], SUSPECTED)

    def test_target_replacement_and_stationary_edges_are_not_passage(self):
        for xs in ([400]*3+[460]*3+[750]*4, [600]*3+[540]*3+[250]*4,
                   [400,410,420]+[460]*20, [600,590,580]+[540]*20):
            self.assertEqual(decisions(analyze(fixture(xs, paths=False))), [])

    def test_measurement_future_prefix_and_sticky_outward_return(self):
        xs = [1000-x for x in PASSAGE]+PASSAGE
        args = fixture(xs, paths=False); duplicate(args, range(3,len(xs)), .004)
        full = analyze(args)
        self.assertEqual(full['evidence'][0]['first_confirmation_pts'], .8)
        for end in range(3, len(xs)):
            prefix = fixture(xs[:end], paths=False); duplicate(prefix, range(3,end), .004)
            out = analyze(prefix)
            self.assertEqual(out['timeline'], [t for t in full['timeline'] if t['decision_time_pts'] <= (end-1)/10])

    def test_episode_filter_uses_actual_anchor_not_late_candidate_clock(self):
        args = fixture(PASSAGE[:4]+[480]+PASSAGE, paths=False)
        args[3][4]['actual_boxes'] = []
        args[0]['segments'][0]['rows'] = args[0]['segments'][0]['rows'][:4]
        args[1]['events'][0]['decision_time_pts'] = 1.3
        out = analyze(args)
        self.assertEqual(len(decisions(out)), 1)
        self.assertEqual(next(e for e in out['evidence'] if e['event_id']=='e')['automatic_status'], SUSPECTED)
        self.assertTrue(any(a['reason'] == 'pending_anchor_outside_measured_episode' for a in out['followup_audit']))

    def test_no_source_candidates_gets_one_current_causal_passage_event(self):
        args = fixture(PASSAGE+[580]*8, paths=False); args[1]['events'] = []
        out = analyze(args)
        self.assertEqual(len(out['events']), 1)
        self.assertEqual(out['events'][0]['source_ref']['collection'], 'measured_passage_events')
        self.assertEqual(out['events'][0]['decision_time_pts'], .8)
        self.assertEqual(len(decisions(out)), 1)
        self.assertEqual(out['dual_boundary_audit']['original_source_candidates'], 0)
        for length in range(3,len(PASSAGE)+8):
            prefix = fixture((PASSAGE+[580]*8)[:length], paths=False); prefix[1]['events'] = []
            result = analyze(prefix)
            self.assertEqual(result['timeline'], [t for t in out['timeline'] if t['decision_time_pts'] <= (length-1)/10])

    def test_empty_sources_partial_paths_cannot_generate_new_passage(self):
        for xs in ([400]*12, PASSAGE[:6]+[520]*12, [400]*3+[750]*5):
            args = fixture(xs, paths=False); args[1]['events'] = []
            self.assertEqual(analyze(args)['events'], [])

    def test_preexisting_stationary_destination_cannot_steal_crossing_event(self):
        args = fixture(PASSAGE+[580]*4, paths=False)
        b,h,r,f,s,p = args; stationary = []
        for frame in f:
            box = deepcopy(frame['actual_boxes'][0]); box.update(cache_index=1,track_ids=[99],bbox=[.545,.37,.615,.57])
            frame['actual_boxes'].append(box)
            stationary.append(dict(pts=frame['pts'],frame_index=frame['frame_index'],cache_index=1,bbox=box['bbox']))
        b['segments'].append(dict(id='stationary',raw_id=99,rows=stationary))
        event = deepcopy(h['events'][0]); event.update(event_id='stationary',decision_time_pts=.2)
        event['source_event'].update(segment='stationary',raw_id=99); h['events'].append(event)
        h['policy'] = asdict(GroupPolicy(gap_seconds=.05,max_span_seconds=10.))
        out = analyze(args); evidence = {e['event_id']:e for e in out['evidence']}
        self.assertEqual(evidence['e']['automatic_status'], CONFIRMED)
        self.assertEqual(evidence['stationary']['automatic_status'], SUSPECTED)
        self.assertEqual(len(decisions(out)), 1)


if __name__ == '__main__': unittest.main()
