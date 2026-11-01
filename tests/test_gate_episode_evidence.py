"""Synthetic geometry/stream tests. They are NOT CCTV intrusion accuracy tests."""
from copy import deepcopy
from dataclasses import replace
import math
import unittest
from sceneguard.gate_episode_evidence import (
    EpisodePolicy, Gate, InsideBirths, history_decision, revised_scene)


def scene():
    return dict(source_size=[1000,1000], line=[[.5,.2],[.5,.8]],
        zones=dict(outside=[[0,0],[.49,0],[.49,1],[0,1]],
                   inside=[[.5,0],[1,0],[1,1],[.5,1]]))


def detection(x=.54,y=.5,w=.04,h=.10, index=0, tid=1, score=.8, observed=True):
    return dict(bbox=[x-w/2,y-h/2,x+w/2,y+h/2],cache_index=index,
                score=score,track_ids=[tid],observed=observed)


def frame(at, boxes=()):
    return dict(pts=round(at,6),frame_index=round(at*30),actual_boxes=list(boxes))


def ready():
    engine=InsideBirths(scene())
    for n in range(11): engine.step(frame(n/10))
    return engine


def stream(engine, start, boxes, n=5):
    return [e for i in range(n) for e in engine.step(frame(start+i/30, boxes))]


def old_loss(direction='inward', continuation='unresolved'):
    return dict(segment='s1', raw_id=8, decision_time_pts=5., last_observed_pts=4.,
        status='침입 의심',automatic_confirmation=False,notify=True,
        reason='existing_suspicion_without_terminal_gate_proximity',
        direction=dict(direction=direction,end_pts=4.),continuation=continuation)


def segment(first_time=2.):
    return dict(id='s1',raw_id=8,rows=[dict(pts=first_time,frame_index=round(first_time*30),
        bbox=detection(.48,h=.20)['bbox']),dict(pts=4.,frame_index=120,
        bbox=detection(.75,w=.025,h=.029)['bbox'])])


class GeometryTests(unittest.TestCase):
    def test_inside_near_gate(self): self.assertTrue(Gate(scene()).locate(detection()['bbox'])['inside_birth_site'])
    def test_outside_is_not_inside(self): self.assertFalse(Gate(scene()).locate(detection(.47)['bbox'])['inside_birth_site'])
    def test_far_inside_is_not_birth(self): self.assertFalse(Gate(scene()).locate(detection(.8)['bbox'])['inside_birth_site'])
    def test_gate_line_extension_excluded(self): self.assertFalse(Gate(scene()).locate(detection(.52,.9)['bbox'])['inside_birth_site'])
    def test_exact_line_not_inside_birth(self): self.assertFalse(Gate(scene()).locate(detection(.5)['bbox'])['inside_birth_site'])
    def test_reversed_line_same_meaning(self):
        a=scene(); b=deepcopy(a); b['line'].reverse()
        self.assertEqual(Gate(a).normal,Gate(b).normal)
    def test_large_box_not_unlimited_near(self):
        self.assertFalse(Gate(scene()).locate(detection(.8,h=.8)['bbox'])['inside_birth_site'])
    def test_inside_polygon_required(self):
        s=scene();s['zones']['inside']=[[.5,.2],[.7,.2],[.7,.4],[.5,.4]]
        self.assertFalse(Gate(s).locate(detection()['bbox'])['inside_birth_site'])
    def test_degenerate_line_rejected(self):
        s=scene();s['line'][1]=s['line'][0]
        with self.assertRaises(ValueError): Gate(s)
    def test_invalid_policy(self):
        for field,value in [('history_seconds',0),('birth_lookback',float('nan')),('association_overlap',1.1),('birth_support_seconds',1.1)]:
            with self.subTest(field=field),self.assertRaises(ValueError): replace(EpisodePolicy(),**{field:value}).validate()
    def test_bad_box(self):
        with self.assertRaises(ValueError): Gate(scene()).locate([.6,.4,.5,.6])


class HistoryTests(unittest.TestCase):
    def test_tiny_last_box_does_not_erase_gate_encounter(self):
        result=history_decision(old_loss(),segment(),scene())
        self.assertTrue(result['automatic_confirmation']);self.assertEqual(result['gate_contact']['pts'],2.)
    def test_far_throughout_not_confirmed(self):
        seg=segment();seg['rows'][0]['bbox']=detection(.8)['bbox']
        self.assertFalse(history_decision(old_loss(),seg,scene())['automatic_confirmation'])
    def test_stale_contact_not_confirmed(self):
        self.assertFalse(history_decision(old_loss(),segment(.5),scene())['automatic_confirmation'])
    def test_direction_unclear_remains_suspicion(self):
        self.assertFalse(history_decision(old_loss('unknown'),segment(),scene())['automatic_confirmation'])
    def test_outward_remains_suspicion(self):
        self.assertFalse(history_decision(old_loss('outward'),segment(),scene())['automatic_confirmation'])
    def test_no_false_disappearance_for_continuation(self):
        self.assertFalse(history_decision(old_loss(continuation='same_side_continuation'),segment(),scene())['automatic_confirmation'])
    def test_cross_side_observation_not_automatically_confirmed(self):
        self.assertFalse(history_decision(old_loss(continuation='cross_side_observation'),segment(),scene())['automatic_confirmation'])
    def test_wait_not_observed_stays_pending(self):
        old=old_loss();old.update(reason='loss_wait_not_observed',notify=False,status='판단 불가')
        self.assertFalse(history_decision(old,segment(),scene())['automatic_confirmation'])
    def test_direction_before_contact_not_used(self):
        old=old_loss();old['direction']['end_pts']=1.5
        self.assertFalse(history_decision(old,segment(),scene())['automatic_confirmation'])
    def test_original_is_immutable(self):
        old,seg=old_loss(),segment();saved=deepcopy((old,seg))
        history_decision(old,seg,scene());self.assertEqual((old,seg),saved)
    def test_prior_confirmation_is_preserved(self):
        old=old_loss();old.update(automatic_confirmation=True,status='침입 확인')
        self.assertTrue(history_decision(old,segment(.5),scene())['automatic_confirmation'])


class BirthTests(unittest.TestCase):
    def test_birth_near_inside_emits_once(self):
        engine=ready();events=stream(engine,1.1,[detection()],12)
        self.assertEqual(len(events),1);self.assertAlmostEqual(events[0]['birth_pts'],1.1)
        self.assertGreaterEqual(events[0]['decision_time_pts'],1.2)
        self.assertFalse(events[0]['automatic_confirmation'])
    def test_one_frame_glitch_does_not_emit(self):
        engine=ready();self.assertFalse(engine.step(frame(1.1,[detection()])))
        self.assertFalse(stream(engine,1.13,[],12))
    def test_far_inside_never_triggers(self): self.assertFalse(stream(ready(),1.1,[detection(.8)]))
    def test_birth_outside_never_triggers(self): self.assertFalse(stream(ready(),1.1,[detection(.47)]))
    def test_line_extension_never_triggers(self): self.assertFalse(stream(ready(),1.1,[detection(.52,.9)]))
    def test_new_id_is_not_new_observation(self):
        e=ready();self.assertEqual(len(stream(e,1.1,[detection()],5)),1)
        self.assertFalse(stream(e,1.266667,[detection(tid=999)],8))
    def test_start_of_recording_not_new_appearance(self):
        self.assertFalse(stream(InsideBirths(scene()),0,[detection()],40))
    def test_predicted_boxes_ignored(self): self.assertFalse(stream(ready(),1.1,[detection(observed=False)]))
    def test_low_score_ignored(self): self.assertFalse(stream(ready(),1.1,[detection(score=.1)]))
    def test_empty_frame_does_not_erase_run(self):
        e=ready();events=stream(e,1.1,[detection()],5)
        events+=stream(e,1.266667,[],5)
        events+=stream(e,1.433334,[detection(tid=99)],5)
        self.assertEqual(len(events),1)
    def test_normal_inside_walker_reaching_gate_is_not_birth(self):
        e=ready();events=[]
        for i in range(14):events+=e.step(frame(1.1+i/30,[detection(.8-i*.02)]))
        self.assertFalse(events)
    def test_first_near_location_kept_when_later_moves_inward(self):
        e=ready();events=[]
        for i in range(9):events+=e.step(frame(1.1+i/30,[detection(.54+i*.025)]))
        self.assertEqual(len(events),1);self.assertTrue(events[0]['birth_site']['inside_birth_site'])
    def test_duplicate_nested_boxes_not_two_births(self):
        self.assertEqual(len(stream(ready(),1.1,[detection(),detection(w=.02,h=.04,index=1,tid=2)])),1)
    def test_two_separated_inside_births_preserved(self):
        self.assertEqual(len(stream(ready(),1.1,[detection(y=.3),detection(y=.7,index=1)])),2)
    def test_source_gap_is_not_disappearance(self):
        e=ready();self.assertFalse(stream(e,3.,[detection()]))
    def test_out_of_order_rejected(self):
        e=ready()
        with self.assertRaises(ValueError):e.step(frame(.9))
    def test_inputs_are_read_only(self):
        e=ready();row=frame(1.1,[detection()]);old=deepcopy(row);e.step(row);self.assertEqual(row,old)
    def test_empty_frames_advance_clock(self): self.assertFalse(stream(ready(),1.1,[],5))


class RevisionTests(unittest.TestCase):
    def test_only_inside_allowed(self):
        a=scene();b=deepcopy(a);b['zones']['inside'][1]=[.95,0]
        self.assertEqual(revised_scene(a,b),b);self.assertNotEqual(a,b)
    def test_line_change_rejected(self):
        a=scene();b=deepcopy(a);b['line'][0][0]=.4
        with self.assertRaises(ValueError):revised_scene(a,b)
    def test_outside_change_rejected(self):
        a=scene();b=deepcopy(a);b['zones']['outside'][0]=[.1,0]
        with self.assertRaises(ValueError):revised_scene(a,b)



class ApplicationHelpersTests(unittest.TestCase):
    def birth_fixture(self):
        from sceneguard.exp0045_application import normalize_birth
        raw=stream(ready(),1.1,[detection()])[0]
        baseline=dict(video_id='synthetic',events=[dict(session_id='s',camera_id='c',gate_id='g')])
        return normalize_birth,raw,baseline

    def test_normalize_birth_is_stable_without_person_ids(self):
        fn,raw,baseline=self.birth_fixture()
        a=fn(raw,baseline,scene());b=fn(raw,baseline,scene())
        self.assertEqual(a,b);self.assertEqual(a['track_ids'],[])
        self.assertEqual(a['status'],'침입 의심')

    def test_normalizer_rejects_non_gate_birth(self):
        fn,raw,baseline=self.birth_fixture();raw['birth_site']['inside_birth_site']=False
        with self.assertRaises(ValueError):fn(raw,baseline,scene())

    def test_normalizer_rejects_future_evidence(self):
        fn,raw,baseline=self.birth_fixture();raw['evidence_until_pts']+=1
        with self.assertRaises(ValueError):fn(raw,baseline,scene())

    def test_card_state_has_no_future_confirmation(self):
        from sceneguard.exp0045_application import annotate
        first=dict(event_ids=['a'],notification_eligible=True)
        last=dict(event_ids=['a','b'],notification_eligible=True)
        original=dict(cards=[last],timeline=[dict(card=first),dict(card=last)])
        decisions=[dict(event_id='b',automatic_confirmation=True,decision_time_pts=2.)]
        result=annotate(original,decisions)
        self.assertIsNone(result['timeline'][0]['card']['first_confirmation_pts'])
        self.assertEqual(result['timeline'][1]['card']['first_confirmation_pts'],2.)
        self.assertNotIn('automatic_status',original['cards'][0])

    def test_empty_view_stays_empty(self):
        from sceneguard.exp0045_application import annotate
        self.assertEqual(annotate(dict(cards=[],timeline=[]),[])['alert_cards'],[])

if __name__ == '__main__': unittest.main()
