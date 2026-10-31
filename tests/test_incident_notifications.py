"""EXP-0041 synthetic contracts. These are not CCTV accuracy measurements."""
from copy import deepcopy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from sceneguard.incident_cards import GroupPolicy, group_events
from sceneguard.incident_notifications import (
    NotificationGrouper, group_notifications, notification_cards_at,
    episode_comparison)
from sceneguard import exp0041_application as app


def event(index, at, *, raw=None, reason=app.LOSS_REASON, gate='C3_fence',
          camera='C3', session='recording'):
    raw = index if raw is None else raw
    collection = 'events' if reason==app.LOSS_REASON else 'existing_alerts'
    return dict(event_id=f'e{index}',session_id=session,camera_id=camera,gate_id=gate,
        video_id='fixture',decision_time_pts=at,status='침입 의심',track_ids=[raw],
        source_ref=dict(collection=collection,source_pointer=f'/{collection}/{index}',
                        segment=f's{index}',raw_id=raw),
        source_event=dict(reason=reason,raw_id=raw,last_observed_pts=at-1,
                          decision_time_pts=at,segment=f's{index}',status='침입 의심'))


def baseline(events):
    out = group_events(events)
    out.update(experiment='EXP-0036',video_id='fixture',source_window=[0,120],
               available_after_pts=120,ignored_non_alert_rows=[])
    return out


def audit(e, score=.8, bbox=None):
    at = e['decision_time_pts']
    box = [.1,.1,.3,.5] if bbox is None else bbox
    alt = dict(score=score,seed_pts=at-1.4,endpoint_bbox=box,evidence_until_pts=at)
    return dict(source_pointer=e['source_ref']['source_pointer'],
        original_event_id=e['event_id'],original_source_ref=deepcopy(e['source_ref']),
        segment=e['source_ref']['segment'],raw_id=e['track_ids'][0],
        decision_time_pts=at,evidence_until_pts=at,last_observed_pts=at-1,
        alternatives=[alt])


class GroupingTests(unittest.TestCase):
    def test_middle_filtered_event_bridges_episode(self):
        es = [event(1,57.8),event(2,59.666667),event(3,62.5)]
        old = group_events([es[0],es[2]])
        new = group_notifications(es,{'e2'})
        self.assertEqual(len(old['cards']),2)
        self.assertEqual(len(new['cards']),1)
        self.assertEqual(new['counts']['notification_intents'],1)
        self.assertEqual(new['cards'][0]['event_ids'],['e1','e2','e3'])

    def test_first_review_event_does_not_notify(self):
        out = group_notifications([event(1,10)],{'e1'})
        self.assertFalse(out['timeline'][0]['notify'])
        self.assertEqual(out['counts']['alert_cards'],0)
        self.assertEqual(out['counts']['review_only_cards'],1)
        self.assertIsNone(out['cards'][0]['first_notification_pts'])

    def test_later_active_event_promotes_same_card_at_its_own_time(self):
        out = group_notifications([event(1,10),event(2,12)],{'e1'})
        first,last = out['timeline']
        self.assertEqual(first['incident_id'],last['incident_id'])
        self.assertEqual(last['action'],'updated')
        self.assertTrue(last['notify'])
        self.assertEqual(last['notification_action'],'first_notify')
        self.assertEqual(last['card']['first_alert_pts'],10)
        self.assertEqual(last['card']['first_notification_pts'],12)

    def test_followup_updates_are_silent(self):
        out = group_notifications([event(1,10),event(2,11),event(3,12)],{'e2'})
        self.assertEqual([t['notify'] for t in out['timeline']],[True,False,False])
        self.assertEqual(out['counts']['silent_card_updates'],2)

    def test_all_review_candidates_have_no_alert_view(self):
        out = group_notifications([event(1,10),event(2,12)],{'e1','e2'})
        self.assertEqual(out['alert_cards'],[])
        self.assertEqual(out['counts']['notification_intents'],0)
        self.assertEqual(out['cards'][0]['status'],'침입 의심')
        self.assertFalse(out['cards'][0]['automatic_confirmation'])

    def test_multiple_people_share_one_episode(self):
        out = group_notifications([event(1,10,raw=8),event(2,10.2,raw=13)])
        self.assertEqual(out['cards'][0]['track_ids'],[8,13])
        self.assertIsNone(out['cards'][0]['person_count'])
        self.assertFalse(out['cards'][0]['identity_merged'])
        self.assertEqual(out['counts']['notification_intents'],1)

    def test_three_second_boundary(self):
        out = group_notifications([event(1,10),event(2,13),event(3,16.01)])
        self.assertEqual(len(out['cards']),2)

    def test_ten_second_cap_applies_even_to_silent_candidates(self):
        es=[event(i,10+i*2.5) for i in range(6)]
        out=group_notifications(es,{'e0','e1','e2','e3','e4'})
        self.assertEqual(out['counts']['candidate_cards'],2)
        self.assertEqual(out['counts']['alert_cards'],1)
        self.assertEqual(out['alert_cards'][0]['first_notification_pts'],22.5)

    def test_different_gate_camera_session_not_merged(self):
        es=[event(1,10),event(2,10,gate='other'),event(3,10,camera='C6'),
            event(4,10,session='other')]
        self.assertEqual(len(group_notifications(es)['cards']),4)

    def test_identical_redelivery_does_not_notify_or_count_twice(self):
        e=event(1,10)
        out=group_notifications([e,e,deepcopy(e)])
        self.assertEqual(out['counts']['duplicate_deliveries'],2)
        self.assertEqual(out['counts']['notification_intents'],1)
        self.assertEqual(out['cards'][0]['alert_count'],1)

    def test_conflicting_payload_rejected(self):
        a=event(1,10); b=deepcopy(a); b['decision_time_pts']=11
        with self.assertRaises(ValueError): group_notifications([a,b])

    def test_conflicting_disposition_rejected(self):
        g=NotificationGrouper(); e=event(1,10)
        g.push(e,notify_candidate=False)
        with self.assertRaises(ValueError): g.push(e,notify_candidate=True)

    def test_unknown_filter_id_rejected(self):
        with self.assertRaises(ValueError): group_notifications([event(1,10)],{'missing'})

    def test_inputs_are_immutable(self):
        es=[event(1,10),event(2,12)]; original=deepcopy(es)
        out=group_notifications(es,{'e2'}); out['events'][0]['source_event']['raw_id']=99
        self.assertEqual(es,original)

    def test_card_snapshots_do_not_mutate(self):
        g=NotificationGrouper(); first=g.push(event(1,10),notify_candidate=False)
        frozen=deepcopy(first); g.push(event(2,11))
        self.assertEqual(first,frozen)
        self.assertEqual(first['card']['event_ids'],['e1'])
        self.assertFalse(first['card']['notification_eligible'])

    def test_rewind_does_not_show_future_promotion(self):
        out=group_notifications([event(1,10),event(2,12)],{'e1'})
        self.assertEqual(notification_cards_at(out['timeline'],11),[])
        past=notification_cards_at(out['timeline'],11,include_review_only=True)[0]
        self.assertEqual(past['event_ids'],['e1'])
        self.assertIsNone(past['first_notification_pts'])
        self.assertEqual(len(notification_cards_at(out['timeline'],12)),1)

    def test_all_active_has_original_ids_membership_and_notification_times(self):
        es=[event(1,10),event(2,12),event(3,18)]
        before=group_events(es); after=group_notifications(es)
        for a,b in zip(before['cards'],after['cards']):
            for key in a: self.assertEqual(a[key],b[key])

    def test_empty_input(self):
        out=group_notifications([])
        self.assertEqual(out['cards'],[])
        self.assertEqual(out['counts']['notification_intents'],0)

    def test_out_of_order_stream_is_rejected(self):
        g=NotificationGrouper();g.push(event(1,10))
        with self.assertRaises(ValueError):g.push(event(2,9))

    def test_offline_unsorted_input_replays_chronologically(self):
        out=group_notifications([event(2,12),event(1,10)],{'e1'})
        self.assertEqual([r['event_id'] for r in out['timeline']],['e1','e2'])

    def test_bad_flag_rejected(self):
        with self.assertRaises(ValueError):NotificationGrouper().push(event(1,10),notify_candidate=1)

    def test_random_partitions_never_increase_cards_or_change_membership(self):
        rng=random.Random(41)
        for _ in range(200):
            at=10;es=[]
            for i in range(30):
                at+=rng.choice([.1,1,2.9,3.1,6])
                es.append(event(i,at,raw=i%4))
            review={e['event_id'] for e in es if rng.random()<.5}
            old=group_events(es);new=group_notifications(es,review)
            self.assertEqual([(c['incident_id'],c['event_ids']) for c in old['cards']],
                             [(c['incident_id'],c['event_ids']) for c in new['cards']])
            self.assertLessEqual(new['counts']['notification_intents'],len(old['cards']))
            self.assertEqual(len(episode_comparison(old,new)),len(old['cards']))


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.events=[event(1,10),event(2,12),event(3,14)]
        self.base=baseline(self.events)
        self.audits=[audit(e,s) for e,s in zip(self.events,[.6,.68,.8])]

    def test_three_thresholds_reuse_same_episode(self):
        values=[app.replay(self.base,self.audits,t) for t in app.THRESHOLDS]
        self.assertEqual([v['counts']['active_alerts'] for v in values],[0,1,2])
        self.assertEqual([v['counts']['alert_cards'] for v in values],[0,1,1])
        self.assertEqual(len({v['cards'][0]['incident_id'] for v in values}),1)
        self.assertTrue(all(v['adopted'] is False for v in values))

    def test_independent_boundary_preserves_same_target_loss(self):
        b=event(4,9,raw=1,reason='boundary')
        es=[b,self.events[0]]
        out=app.replay(baseline(es),[self.audits[0]],.55)
        self.assertEqual(out['counts']['active_alerts'],2)
        self.assertEqual(out['counts']['review_only_alerts'],0)

    def test_other_persons_boundary_not_cancelled_by_one_continuation(self):
        b=event(4,9,raw=99,reason='boundary')
        out=app.replay(baseline([b,self.events[0]]),[self.audits[0]],.55)
        self.assertEqual([e['event_id'] for e in out['active_events']],['e4'])
        self.assertEqual(out['counts']['alert_cards'],1)

    def test_future_boundary_does_not_resurrect_earlier_notice(self):
        b=event(4,11,raw=1,reason='boundary')
        out=app.replay(baseline([self.events[0],b]),[self.audits[0]],.55)
        self.assertEqual(out['cards'][0]['first_notification_pts'],11)
        self.assertEqual(notification_cards_at(out['timeline'],10.5),[])

    def test_conflicting_qualifying_seeds_keep_candidate(self):
        self.audits[0]['alternatives'].append(dict(score=.8,endpoint_bbox=[.7,.1,.9,.5]))
        out=app.replay(self.base,self.audits,.55)
        self.assertIn('e1',[e['event_id'] for e in out['active_events']])

    def test_zero_score_without_endpoint_keeps_candidate(self):
        self.audits[0]['alternatives']=[dict(score=0)]
        self.assertEqual(app.replay(self.base,self.audits,.55)['counts']['active_alerts'],1)

    def test_no_alternatives_keeps_candidate(self):
        self.audits[0]['alternatives']=[]
        self.assertEqual(app.replay(self.base,self.audits,.55)['counts']['active_alerts'],1)

    def test_missing_audit_rejected(self):
        with self.assertRaises(ValueError):app.replay(self.base,self.audits[:-1],.55)

    def test_duplicate_audit_rejected(self):
        with self.assertRaises(ValueError):app.replay(self.base,self.audits+[self.audits[0]],.55)

    def test_future_evidence_rejected(self):
        self.audits[0]['evidence_until_pts']+=.1
        with self.assertRaises(ValueError):app.replay(self.base,self.audits,.55)

    def test_future_seed_rejected(self):
        self.audits[0]['alternatives'][0]['seed_pts']=11
        with self.assertRaises(ValueError):app.replay(self.base,self.audits,.55)

    def test_wrong_target_rejected(self):
        self.audits[0]['raw_id']=99
        with self.assertRaises(ValueError):app.replay(self.base,self.audits,.55)

    def test_score_nan_rejected(self):
        self.audits[0]['alternatives'][0]['score']=float('nan')
        with self.assertRaises(ValueError):app.replay(self.base,self.audits,.55)

    def test_invalid_box_rejected(self):
        self.audits[0]['alternatives'][0]['endpoint_bbox']=[.3,.1,.1,.5]
        with self.assertRaises(ValueError):app.replay(self.base,self.audits,.55)

    def test_source_payload_and_audits_remain_unchanged(self):
        before=deepcopy((self.base,self.audits));app.replay(self.base,self.audits,.55)
        self.assertEqual((self.base,self.audits),before)

    def test_changed_original_timeline_rejected(self):
        self.base['timeline'][0]['card']['track_ids']=[999]
        with self.assertRaises(ValueError):app.replay(self.base,self.audits,.55)

    def test_unknown_threshold_rejected(self):
        for t in (.5,.56,True,float('nan')):
            with self.assertRaises(ValueError):app.replay(self.base,self.audits,t)

    def test_notification_shift_is_reported_not_backdated(self):
        self.audits[0]['alternatives'][0]['score']=.8
        self.audits[1]['alternatives'][0]['score']=.1
        out=app.replay(self.base,self.audits,.7)
        row=out['episode_comparison'][0]
        self.assertEqual(row['proposed_first_notification_pts'],12)
        self.assertEqual(row['notification_shift_pts'],2)

    def test_other_scope_in_same_replay_rejected(self):
        es=self.events+[event(4,15,camera='C6')]
        with self.assertRaises(ValueError):app.replay(baseline(es),self.audits+[audit(es[-1])],.55)

    def test_cli_saved_json_path_without_models_or_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source';src.mkdir()
            values={'baseline-cards.json':self.base,'audits.json':self.audits,
                    'summary.json':dict(experiment='EXP-0040',cases=3,baseline_counts=self.base['counts']),
                    'request.json':dict(experiment='EXP-0040')}
            for name,value in values.items():(src/name).write_text(json.dumps(value))
            before={p.name:p.read_bytes() for p in src.iterdir()}
            target=root/'outputs'/'new'
            with patch.object(app,'ROOT',root):
                result=app.execute(src,target)
                with self.assertRaises(ValueError):app.execute(src,target)
            self.assertEqual(result['feature_calls'],0)
            self.assertEqual(result['detector_calls'],0)
            self.assertEqual(set(result['results']),{'0.55','0.65','0.70'})
            self.assertEqual({p.name:p.read_bytes() for p in src.iterdir()},before)
            self.assertTrue((target/'threshold-055.json').is_file())
            self.assertFalse(json.loads((target/'summary.json').read_text())['adopted'])

    def test_saved_old_disposition_is_recomputed(self):
        self.audits[0].update(notification_action='keep',partition_reason='old_reason')
        out=app.replay(self.base,self.audits,.55)
        row=out['decision_audits'][0]
        self.assertEqual(row['notification_action'],'review_only')
        self.assertEqual(row['partition_reason'],'image_continuation')

    def test_independent_protection_reason_is_explicit(self):
        b=event(4,9,raw=1,reason='boundary')
        out=app.replay(baseline([b,self.events[0]]),[self.audits[0]],.55)
        row=out['decision_audits'][0]
        self.assertEqual(row['recommendation'],'review_only')
        self.assertEqual(row['notification_action'],'keep')
        self.assertEqual(row['partition_reason'],'independent_boundary_evidence_preserved')

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError):app._read_json('{"x":1,"x":2}')

    def test_nonfinite_json_rejected(self):
        with self.assertRaises(ValueError):app._read_json('{"x":NaN}')


if __name__=='__main__':
    unittest.main()
