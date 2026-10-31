"""Synthetic saved-record tests. No source CCTV or inference is performed."""
from copy import deepcopy
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

from sceneguard.transition_diagnostics import (
    SavedEvidenceAudit, explain_score, overlap_audit, parse_range, summarize_range,
    execute, sha,
)

POLICY = dict(score_threshold=.55, support_window=.35, support_seconds=.10,
              max_frame_gap=.12, cooldown_seconds=1., seed_score=.25,
              window_seconds=2.5, min_support_frames=3, max_windows=16)


def signal(**changes):
    s = dict(proximity=1., crossing_fraction=.35, crossing=1., upward_image_motion=0.,
             local_deformation=0., normal_progress=1., motion_change=0., coherence=1.,
             point_count=8, camera_support=True, score=1., route='boundary_motion')
    s.update(changes)
    return s


def fixture():
    rows = []
    pts = [[20.+i, 20.+i] for i in range(8)]
    for index, tick in enumerate((0, 1, 2, 3, 4)):
        at = tick/10
        path = dict(window_id='w000001', seed_pts=0., seed_cache_index=0,
                    seed_track_ids=[1], point_ids=list(range(8)),
                    points_original_pixels=deepcopy(pts))
        s = signal(**deepcopy(path), reference_pts=0., evidence_until_pts=at)
        event = dict(decision_time_pts=at, evidence_until_pts=at, evidence=deepcopy(s)) if tick==3 else None
        rows.append(dict(frame_index=index, pts=at, native_pts=tick, time_base='1/10',
            camera_support=True, windows=1, point_paths=[path], signals=[s] if tick else [],
            score=1. if tick else 0., event=event,
            actual_boxes=[dict(cache_index=0, bbox=[.1,.1,.4,.4], score=.8, track_ids=[1])]))
    return rows


class ScoreTests(unittest.TestCase):
    def test_perfect_crossing(self):
        e=explain_score(signal(),.55)
        self.assertEqual(e['reproduced_score'],1.)
        self.assertTrue(e['reaches_threshold'])

    def test_local_ceiling_case_from_rounded_report_not_raw_cctv(self):
        p,u,progress=.6173,.7778,.4525
        s=signal(proximity=p, crossing_fraction=0., crossing=0., upward_image_motion=u,
            local_deformation=1., motion_change=1., normal_progress=progress,
            route='local_gate_change', score=p*u*(.55+.25+.2*progress))
        e=explain_score(s,.55)
        self.assertAlmostEqual(e['local_ceiling'],p*u)
        self.assertLess(e['local_ceiling'],.55)
        self.assertGreater(e['proximity_ceiling'],.55)
        self.assertFalse(e['reaches_threshold'])
        self.assertIsNone(e['semantic_correctness'])

    def test_camera_penalty(self):
        e=explain_score(signal(camera_support=False,score=.9),.55)
        self.assertAlmostEqual(e['camera_penalty'],.1)

    def test_small_point_quality(self):
        e=explain_score(signal(point_count=3,score=.875),.55)
        self.assertAlmostEqual(e['quality'],.875)

    def test_zero_signal(self):
        e=explain_score(signal(proximity=0.,score=0.),.55)
        self.assertEqual(e['reproduced_score'],0.)

    def test_boundary_route_only_enabled_if_crossing_fraction_positive(self):
        s=signal(crossing_fraction=0.,crossing=0.,score=0.)
        self.assertEqual(explain_score(s,.55)['cross_branch'],0.)

    def test_no_hypothetical_score_replaces_stored_score(self):
        e=explain_score(signal(proximity=.4,score=.4),.55)
        self.assertEqual(e['saved_score'],.4)
        self.assertFalse(e['altered_candidate'])

    def test_bad_score_is_error(self):
        with self.assertRaises(ValueError):explain_score(signal(score=.8),.55)

    def test_bad_route_is_error(self):
        with self.assertRaises(ValueError):explain_score(signal(route='local_gate_change'),.55)

    def test_bad_crossing_normalization_is_error(self):
        with self.assertRaises(ValueError):explain_score(signal(crossing=.3),.55)

    def test_nonfinite_and_missing_values(self):
        for v in (float('nan'),float('inf'),None,True):
            with self.subTest(v=v),self.assertRaises(ValueError):
                explain_score(signal(proximity=v),.55)

    def test_unbounded_and_insufficient_points(self):
        for changes in ({'proximity':1.1},{'point_count':2},{'camera_support':1}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                explain_score(signal(**changes),.55)


class OverlapTests(unittest.TestCase):
    def test_overlap_is_not_person_accuracy(self):
        e=overlap_audit({0:[25,25],1:[80,80]},fixture()[0]['actual_boxes'],[100,100],.25)
        self.assertEqual(e['within_any_box'],1)
        self.assertEqual(e['outside_all_boxes'],1)
        self.assertIsNone(e['semantic_tracking_quality'])

    def test_predicted_and_low_score_boxes_not_counted(self):
        boxes=[dict(cache_index=0,bbox=[0.,0.,1.,1.],score=.9,observed=False),
               dict(cache_index=1,bbox=[0.,0.,1.,1.],score=.1)]
        self.assertEqual(overlap_audit({0:[25,25]},boxes,[100,100],.25)['within_any_box'],0)

    def test_multiple_boxes_recorded_not_identity_merged(self):
        boxes=deepcopy(fixture()[0]['actual_boxes']); boxes.append(dict(boxes[0],cache_index=2,track_ids=[9]))
        e=overlap_audit({0:[25,25]},boxes,[100,100],.25)
        self.assertEqual(e['within_multiple_boxes'],1)
        self.assertEqual(len(e['boxes']),2)

    def test_duplicate_cache_index_rejected(self):
        boxes=fixture()[0]['actual_boxes']*2
        with self.assertRaises(ValueError): overlap_audit({0:[25,25]},boxes,[100,100],.25)


class ReplayTests(unittest.TestCase):
    def run_rows(self, rows):
        engine=SavedEvidenceAudit(POLICY,[100,100])
        out=[engine.push(r) for r in rows]
        return engine,out

    def test_reproduces_existing_event_and_cooldown(self):
        engine,out=self.run_rows(fixture())
        self.assertEqual(engine.event_pts,[.3])
        self.assertEqual(out[1]['stage'],'temporal_support_not_ready')
        self.assertEqual(out[3]['stage'],'candidate')
        self.assertEqual(out[4]['stage'],'cooldown')

    def test_every_signal_including_loser_is_audited(self):
        rows=fixture()
        for r in rows:
            p=deepcopy(r['point_paths'][0]);p['window_id']='w000002'
            r['point_paths'].append(p);r['windows']=2
            if r['signals']:
                s=deepcopy(r['signals'][0]);s.update(window_id='w000002',proximity=.4,score=.4)
                r['signals'].append(s)
        engine,out=self.run_rows(rows)
        self.assertEqual(engine.signal_count,8)
        self.assertEqual(len(out[-1]['signals']),2)

    def test_native_clock_mismatch_rejected(self):
        rows=fixture();rows[2]['native_pts']=99
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_missing_frame_rejected(self):
        rows=fixture();rows[2]['frame_index']=9
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_future_reference_rejected(self):
        rows=fixture();rows[1]['signals'][0]['reference_pts']=.2
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_missing_reference_rejected(self):
        rows=fixture();rows[2]['signals'][0]['reference_pts']=.05
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_dropped_point_cannot_reappear(self):
        rows=fixture()
        for p in (rows[1]['point_paths'][0],rows[1]['signals'][0]):
            p['point_ids']=p['point_ids'][1:];p['points_original_pixels']=p['points_original_pixels'][1:]
        rows[1]['signals'][0].update(point_count=7,score=.975);rows[1]['score']=.975
        with self.assertRaisesRegex(ValueError,'Dropped point'):self.run_rows(rows)

    def test_retired_window_cannot_reappear(self):
        rows=fixture();rows[1].update(point_paths=[],windows=0,signals=[],score=0.)
        with self.assertRaisesRegex(ValueError,'Retired window'):self.run_rows(rows)

    def test_point_coordinates_mismatch_rejected(self):
        rows=fixture();rows[1]['signals'][0]['points_original_pixels'][0][0]+=1
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_frame_max_mismatch_rejected(self):
        rows=fixture();rows[1]['score']=.1
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_event_replay_mismatch_rejected(self):
        rows=fixture();rows[3]['event']=None
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_event_clock_mismatch_rejected(self):
        rows=fixture();rows[3]['event']['decision_time_pts']=.4
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_absent_signal_is_not_hidden_person_truth(self):
        _,out=self.run_rows(fixture())
        self.assertEqual(out[0]['stage'],'no_signal')
        self.assertIsNone(out[0]['intrusion_truth'])

    def test_range_does_not_influence_processing(self):
        _,out=self.run_rows(fixture())
        a=summarize_range(out,parse_range('test=0.1:0.4'))
        self.assertEqual(a['candidate_pts'],[.3])
        self.assertEqual(a['frames'],4)

    def test_missing_range_is_not_success(self):
        _,out=self.run_rows(fixture())
        e=summarize_range(out,parse_range('absent=64:74'))
        self.assertEqual(e['coverage'],'not_available')
        self.assertIsNone(e['highest_score'])

    def test_invalid_ranges_rejected(self):
        for v in ('x','x=2:1','x=nan:2','=1:2','x=-1:2'):
            with self.subTest(v=v),self.assertRaises(ValueError):parse_range(v)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.cwd=Path.cwd();os.chdir(self.tmp.name)
        self.directory=Path('outputs/exp0042/test-v1');self.directory.mkdir(parents=True)
        self.scene=Path('runtime/scene.json');self.scene.parent.mkdir()
        self.scene.write_text(json.dumps(dict(source_size=[100,100],line=[[.5,0],[.5,1]],approach_polygon=[])))
        self.put('request.json',dict(experiment='EXP-0042',policy=POLICY,input_sha256={str(self.scene):sha(self.scene)}))
        self.put('summary.json',dict(experiment='EXP-0042',policy=POLICY,frames=5,video_id='synthetic'))
        self.put('transition-events.json',[dict(decision_time_pts=.3)])
        (self.directory/'frame-evidence.jsonl').write_text('\n'.join(json.dumps(r) for r in fixture()))

    def tearDown(self):
        os.chdir(self.cwd);self.tmp.cleanup()

    def put(self,name,data):
        (self.directory/name).write_text(json.dumps(data))

    def test_file_pipeline_preserves_inputs(self):
        before={p.name:p.read_bytes() for p in self.directory.iterdir()}
        result=execute(self.directory,Path('outputs/audit'),[parse_range('all=0:0.4')])
        self.assertTrue(result['arithmetic_reproduced'])
        self.assertEqual(result['alarm_changes'],0)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.directory.iterdir()})
        self.assertTrue(Path('outputs/audit/signals.csv').is_file())
        self.assertIsNone(result['accuracy'])

    def test_no_output_overwrite(self):
        out=Path('outputs/audit');out.mkdir()
        with self.assertRaises(ValueError):execute(self.directory,out,[])

    def test_incomplete_events_fail(self):
        self.put('transition-events.json',[])
        with self.assertRaises(ValueError):execute(self.directory,Path('outputs/audit'),[])
        self.assertFalse(Path('outputs/audit/summary.json').exists())
        self.assertTrue(Path('outputs/audit/failure.json').exists())

    def test_changed_scene_fail(self):
        self.scene.write_text(self.scene.read_text()+' ')
        with self.assertRaises(ValueError):execute(self.directory,Path('outputs/audit'),[])


if __name__=='__main__':unittest.main()
