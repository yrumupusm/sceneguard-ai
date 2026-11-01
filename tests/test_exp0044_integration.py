"""Real notification contracts and optional local-input preflight; no inference."""
import json
from pathlib import Path
import unittest
from copy import deepcopy

from test_directional_loss import fixture, scene, normalized
from sceneguard.directional_loss import SavedGateDirection, annotated_bundle
from sceneguard.incident_notifications import group_notifications, notification_cards_at
from sceneguard.exp0044_application import prepared_inputs, sha


class RealNotificationContract(unittest.TestCase):
    def events(self):
        events=[normalized('a',1), normalized('b',2), normalized('c',15,raw=9)]
        for e in events:e.update(session_id='session',camera_id='camera',gate_id='gate')
        return events

    def test_real_grouping_preserves_payload_ids_and_notice_clocks(self):
        events=self.events(); baseline=group_notifications(events)
        before=deepcopy(baseline)
        decisions=[dict(event_id='b',notify=True,automatic_confirmation=True,decision_time_pts=2)]
        proposal=annotated_bundle(baseline,decisions,group_notifications)
        self.assertEqual(baseline,before)
        self.assertEqual(proposal['events'],events)
        for a,b in zip(baseline['cards'],proposal['cards']):
            for key in ('incident_id','event_ids','first_notification_pts','notification_key'):
                self.assertEqual(a[key],b[key])
        self.assertEqual([r['notify'] for r in baseline['timeline']],
                         [r['notify'] for r in proposal['timeline']])
        self.assertFalse(notification_cards_at(proposal['timeline'],1.999)[0]['automatic_confirmation'])
        self.assertTrue(notification_cards_at(proposal['timeline'],2)[0]['automatic_confirmation'])
        self.assertFalse(notification_cards_at(proposal['timeline'],1)[0]['automatic_confirmation'])
        self.assertEqual(proposal['cards'][0]['decision_source'],'automatic_rule')
        self.assertFalse(proposal['cards'][0]['human_verified'])

    def test_real_deferral_preserves_other_person_and_group_membership(self):
        events=self.events(); events[1]['track_ids']=[99]
        baseline=group_notifications(events)
        d=[dict(event_id='a',notify=False,automatic_confirmation=False,decision_time_pts=1)]
        proposal=annotated_bundle(baseline,d,group_notifications)
        self.assertEqual([c['event_ids'] for c in baseline['cards']],
                         [c['event_ids'] for c in proposal['cards']])
        self.assertEqual(proposal['cards'][0]['active_event_ids'],['b'])
        self.assertEqual(proposal['cards'][0]['first_notification_pts'],2)
        self.assertFalse(notification_cards_at(proposal['timeline'],1))

    def test_prior_camera_offset_cannot_hide_observed_crossing(self):
        f,s,e=fixture(end=True,cross=True); f[0]['camera_step_pixels']=[100,0]
        result=SavedGateDirection(f,scene()).classify(e,s)
        self.assertEqual(result['continuation'],'cross_side_observation')
        self.assertTrue(result['notify'])

    def test_crossing_during_wait_cannot_be_erased_by_return(self):
        f,s,e=fixture(end=True)
        f[3]['point_paths'][0]['points_original_pixels']=[[550,300+j*10] for j in range(4)]
        f[3]['actual_boxes'][0]['bbox']=[.53,.35,.58,.55]
        result=SavedGateDirection(f,scene()).classify(e,s)
        self.assertEqual(result['continuation'],'cross_side_observation')
        self.assertTrue(result['notify'])

    def test_future_crossing_not_used_for_deferral(self):
        f,s,e=fixture(end=True)
        future=deepcopy(f[-1]);future.update(frame_index=5,pts=2)
        future['point_paths'][0]['points_original_pixels']=[[550,300+j*10] for j in range(4)]
        future['actual_boxes'][0]['bbox']=[.53,.35,.58,.55]
        f.append(future)
        self.assertEqual(SavedGateDirection(f,scene()).classify(e,s)['continuation'],'same_side_continuation')


class LocalSavedInputPreflight(unittest.TestCase):
    @unittest.skipUnless(Path('outputs/exp0042/007-v1/frame-evidence.jsonl').exists(),'local preserved inputs unavailable')
    def test_real_validated_catalogs_and_original_notification_bundles(self):
        for key,expected in [('007',1710),('030',480)]:
            baseline,base,frames,scene,group,before=prepared_inputs(
                f'outputs/exp0035/{key}-v1.json',f'outputs/exp0042/{key}-v1')
            self.assertEqual(len(frames),expected)
            engine=SavedGateDirection(frames,scene)
            self.assertEqual(len(engine.frames),expected)
            self.assertEqual(base['experiment'],'EXP-0042')
            self.assertEqual(base['comparison_mode'],'baseline')
            self.assertEqual(base['events'],group(base['events'],[])['events'])
            self.assertEqual(before,{p:sha(p) for p in before})
            self.assertEqual(sum(e['source_event'].get('reason')=='recent_gate_presence_then_loss'
                                 for e in base['events']),9 if key=='007' else 5)

class MediaCausality(unittest.TestCase):
    def test_no_future_box_direction_or_verdict(self):
        from sceneguard.exp0044_media import causal_case
        f,s,e=fixture();engine=SavedGateDirection(f,scene());d=engine.classify(e,s)
        self.assertIsNone(causal_case(s,d,-.1,engine))
        before=causal_case(s,d,.25,engine)
        self.assertEqual(before['automatic_status'],'pending')
        self.assertEqual(before['last']['pts'],.25)
        self.assertLessEqual(before['motion']['end_pts'],.25)
        self.assertIsNone(before['decision_time_pts'])
        self.assertEqual(causal_case(s,d,1.5,engine)['automatic_status'],'confirmed')
        self.assertEqual(causal_case(s,d,.25,engine)['automatic_status'],'pending')

    def test_exact_native_clock(self):
        from sceneguard.exp0044_media import frame_clock
        self.assertEqual(float(frame_clock(dict(native_pts=512,time_base='1/15360',pts=1/30))),1/30)
        with self.assertRaises(ValueError):frame_clock(dict(native_pts=512,time_base='1/15360',pts=.1))

class CrossingDirectionSymmetry(unittest.TestCase):
    def test_outward_cross_side_cannot_cancel_loss(self):
        f,s,e=fixture(end=True)
        for row in f:
            if row['point_paths']:
                row['point_paths'][0]['points_original_pixels'][0][0]=510 if row['frame_index']<=2 else 480
            if row['actual_boxes']:row['actual_boxes'][0]['bbox']=[.43,.35,.54,.55]
        for r in s['rows']:r['bbox']=[.43,.35,.54,.55]
        result=SavedGateDirection(f,scene()).classify(e,s)
        self.assertEqual(result['continuation'],'cross_side_observation')
        self.assertTrue(result['notify'])

class StaleDirectionDisplay(unittest.TestCase):
    def test_last_valid_time_retained_but_old_arrow_hidden(self):
        from sceneguard.exp0044_media import motion_display, AUTOMATIC_LABELS
        motion=dict(end_pts=55,direction='inward')
        self.assertTrue(motion_display(motion,56)['arrow_visible'])
        self.assertFalse(motion_display(motion,56.033333)['arrow_visible'])
        self.assertAlmostEqual(motion_display(motion,56.033333)['age_seconds'],1.033333)
        self.assertFalse(motion_display(None,55)['arrow_visible'])
        self.assertEqual(AUTOMATIC_LABELS['confirmed'],'침입 확인 · 자동')


if __name__=='__main__': unittest.main()
