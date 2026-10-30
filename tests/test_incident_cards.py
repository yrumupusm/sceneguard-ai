"""Synthetic event/presentation contracts; not CCTV accuracy tests."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from sceneguard.incident_cards import GroupPolicy, IncidentGrouper, group_events, cards_at
from sceneguard.exp0036_application import normalize_result, make_bundle, execute


def event(eid, pts, tid=1, camera='C3', gate='gate1', session='recording1'):
    return dict(event_id=eid, decision_time_pts=pts, status='침입 의심',
                track_ids=[tid], session_id=session, camera_id=camera, gate_id=gate,
                source_ref=dict(original=eid))


def baseline():
    row=dict(status='침입 의심', segment='s1', raw_id=13,
             decision_time_pts=72.433333, last_observed_pts=71.433333,
             confirmed_intrusion=False)
    return dict(experiment='EXP-0035', video_id='E01_007',
                source_window=[48,104.966667], available_after_pts=104.966667,
                events=[row,dict(row,raw_id=8,segment='s2',decision_time_pts=72.6),
                        dict(status='침입 아님',raw_id=18,decision_time_pts=85)],
                losses=[deepcopy(row)],review_changes=[deepcopy(row)],
                existing_alerts=[dict(video_id='E01_007',condition='gap',track_id=8,
                                     emitted_at_pts=70.133333, candidate_pts=69.866667)])


class GroupingTests(unittest.TestCase):
    def test_simultaneous_people_one_card_and_one_notification(self):
        out=group_events([event('a',10,1),event('b',10,2),event('c',11,3)])
        self.assertEqual(out['counts']['incident_cards'],1)
        self.assertEqual(out['counts']['notification_intents'],1)
        self.assertEqual(out['counts']['silent_card_updates'],2)
        self.assertEqual(out['cards'][0]['track_ids'],[1,2,3])
        self.assertIsNone(out['cards'][0]['person_count'])

    def test_first_alert_not_delayed_for_grouping(self):
        g=IncidentGrouper()
        first=g.push(event('a',10))
        self.assertTrue(first['notify'])
        self.assertEqual(first['decision_time_pts'],10)
        self.assertEqual(first['card']['first_notification_pts'],10)
        self.assertEqual(first['card']['alert_count'],1)

    def test_gap_exactly_three_inclusive(self):
        out=group_events([event('a',0),event('b',3)])
        self.assertEqual(len(out['cards']),1)

    def test_long_gap_starts_new_card(self):
        out=group_events([event('a',0),event('b',3.01)])
        self.assertEqual(len(out['cards']),2)
        self.assertTrue(all(x['notify'] for x in out['timeline']))

    def test_cap_prevents_transitive_infinite_group(self):
        out=group_events([event(str(i),i) for i in (0,2,4,6,8,10,12)])
        self.assertEqual([c['alert_count'] for c in out['cards']],[6,1])
        self.assertEqual(out['cards'][1]['first_alert_pts'],12)

    def test_different_cameras_never_group(self):
        out=group_events([event('a',10,camera='A'),event('b',10,camera='B')])
        self.assertEqual(len(out['cards']),2)

    def test_different_gates_never_group(self):
        out=group_events([event('a',10,gate='A'),event('b',10,gate='B')])
        self.assertEqual(len(out['cards']),2)

    def test_recording_sessions_never_group(self):
        out=group_events([event('a',10,session='first'),event('b',10,session='second')])
        self.assertEqual(len(out['cards']),2)

    def test_repeated_delivery_does_not_renotify_or_increment(self):
        a=event('a',10)
        out=group_events([a,a,deepcopy(a)])
        self.assertEqual(out['counts']['unique_alerts'],1)
        self.assertEqual(out['counts']['duplicate_deliveries'],2)
        self.assertEqual(out['counts']['notification_intents'],1)
        self.assertEqual(out['cards'][0]['alert_count'],1)

    def test_conflicting_duplicate_rejected(self):
        g=IncidentGrouper();g.push(event('a',10))
        with self.assertRaisesRegex(ValueError,'conflicting'):
            g.push(event('a',11))

    def test_out_of_order_new_event_not_silently_reassigned(self):
        g=IncidentGrouper();g.push(event('a',10))
        with self.assertRaisesRegex(ValueError,'ordered'):
            g.push(event('b',9))

    def test_old_duplicate_after_new_event_is_safe(self):
        g=IncidentGrouper();g.push(event('a',10));g.push(event('b',11))
        self.assertEqual(g.push(event('a',10))['action'],'duplicate')

    def test_future_counts_not_visible_in_earlier_snapshot(self):
        out=group_events([event('a',10,1),event('b',11,2)])
        self.assertEqual(cards_at(out['timeline'],9),[])
        self.assertEqual(cards_at(out['timeline'],10)[0]['track_ids'],[1])
        self.assertEqual(cards_at(out['timeline'],10)[0]['alert_count'],1)
        self.assertEqual(cards_at(out['timeline'],11)[0]['alert_count'],2)

    def test_group_expiry_not_confirmation_or_no_intrusion(self):
        out=group_events([event('a',10)])
        card=cards_at(out['timeline'],20)[0]
        self.assertFalse(card['grouping_window_open'])
        self.assertEqual(card['status'],'침입 의심')
        self.assertFalse(card['automatic_confirmation'])

    def test_input_and_emitted_snapshot_are_independent(self):
        a=event('a',10);before=deepcopy(a);g=IncidentGrouper()
        first=g.push(a);g.push(event('b',11,2))
        self.assertEqual(a,before)
        self.assertEqual(first['card']['alert_count'],1)
        first['card']['event_ids'].append('bad')
        self.assertNotIn('bad',g.cards()[0]['event_ids'])

    def test_idempotency_keys_stable_across_replay(self):
        events=[event('a',10),event('b',11,2)]
        a,b=group_events(events),group_events(list(reversed(events)))
        self.assertEqual(a['cards'],b['cards'])
        self.assertEqual(a['timeline'],b['timeline'])

    def test_known_false_alarm_is_not_removed_by_grouping(self):
        alerts=[event('fp1',56),event('fp2',57.766667,5),event('fp3',57.8,2)]
        out=group_events(alerts)
        self.assertEqual(out['counts']['input_alert_rows'],3)
        self.assertEqual(out['counts']['incident_cards'],1)
        self.assertEqual(len(out['events']),3)

    def test_empty_feed(self):
        out=group_events([])
        self.assertEqual(out['counts']['notification_intents'],0)
        self.assertEqual(out['cards'],[])

    def test_invalid_policy_and_event_fields(self):
        for p in (GroupPolicy(0,10),GroupPolicy(3,2),GroupPolicy(float('nan'),10)):
            with self.assertRaises(ValueError):p.validate()
        for a in (dict(event('a',1),status='침입 확인'), event('a',float('nan')),
                  event('',1),event('a',1,tid=True),event('a',1,gate='')):
            with self.assertRaises(ValueError):IncidentGrouper().push(a)


class AdapterTests(unittest.TestCase):
    def test_combines_legacy_and_new_alerts_without_loss_mirrors(self):
        data=baseline();before=deepcopy(data)
        out=make_bundle(data,'C3','gate1','recording1')
        self.assertEqual(data,before)
        self.assertEqual(out['counts']['unique_alerts'],3)
        self.assertEqual(out['counts']['incident_cards'],1)
        self.assertEqual(len(out['ignored_non_alert_rows']),1)
        self.assertEqual(out['cards'][0]['first_alert_pts'],70.133333)
        self.assertEqual(out['cards'][0]['track_ids'],[8,13])

    def test_no_hindsight_observation_clock(self):
        events,_=normalize_result(baseline(),'C3','gate1','session1')
        self.assertEqual(events[0]['decision_time_pts'],72.433333)
        self.assertEqual(events[-1]['decision_time_pts'],70.133333)

    def test_source_rows_preserved(self):
        data=baseline();events,_=normalize_result(data,'C3','gate1','session1')
        self.assertEqual(events[0]['source_event'],data['events'][0])
        self.assertEqual(events[0]['source_ref']['source_pointer'],'/events/0')

    def test_missing_time_not_invented(self):
        data=baseline();del data['events'][0]['decision_time_pts']
        with self.assertRaises(ValueError):make_bundle(data,'C3','gate1','session1')

    def test_wrong_video_and_gate_rejected(self):
        data=baseline();data['existing_alerts'][0]['video_id']='wrong'
        with self.assertRaises(ValueError):make_bundle(data,'C3','gate1','session1')
        data=baseline();data['events'][0]['boundary_id']='other'
        with self.assertRaises(ValueError):make_bundle(data,'C3','gate1','session1')

    def test_non_exp35_input_rejected(self):
        data=baseline();data['experiment']='EXP-0034'
        with self.assertRaises(ValueError):make_bundle(data,'C3','gate1','session1')

    def test_event_outside_source_window_rejected(self):
        data=baseline();data['events'][0]['decision_time_pts']=200
        with self.assertRaises(ValueError):make_bundle(data,'C3','gate1','session1')

    def test_unique_alert_count_and_original_payload_not_person_count(self):
        data=baseline();data['events'][1]['raw_id']=13
        out=make_bundle(data,'C3','gate1','session1')
        self.assertEqual(out['counts']['unique_alerts'],3)
        self.assertEqual(out['cards'][0]['track_ids'],[8,13])
        self.assertFalse(out['identity_verified'])

    def test_file_output_is_new_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'base.json';out=root/'outputs'/'cards.json'
            src.write_text(json.dumps(baseline()),encoding='utf-8');before=src.read_bytes()
            import os
            cwd=Path.cwd()
            try:
                os.chdir(root)
                bundle=execute(src,out,'C3','gate1','session1')
                self.assertEqual(src.read_bytes(),before)
                self.assertEqual(json.loads(out.read_text())['counts'],bundle['counts'])
                with self.assertRaises(ValueError):execute(src,out,'C3','gate1','session1')
                with self.assertRaises(ValueError):execute(src,root/'wrong.json','C3','gate1','session1')
            finally:os.chdir(cwd)

class PreviewTests(unittest.TestCase):
    def test_page_embeds_time_scoped_snapshots_and_escapes_json(self):
        from sceneguard.incident_card_preview import write_preview
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'bundle.json';dst=root/'outputs'/'preview.html'
            bundle=make_bundle(baseline(),'C3','gate1','session1')
            bundle['description']='</script><script>alert(1)</script>'
            src.write_text(json.dumps(bundle),encoding='utf-8')
            cwd=Path.cwd()
            try:
                os.chdir(root)
                write_preview(src,dst)
                page=dst.read_text(encoding='utf-8')
                self.assertNotIn('</script><script>alert(1)',page)
                self.assertIn('sessionStorage',page)
                self.assertIn('item.notify',page)
                with self.assertRaises(ValueError):write_preview(src,dst)
            finally:os.chdir(cwd)

    def test_missing_media_is_not_silently_accepted(self):
        from sceneguard.incident_card_preview import write_preview
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'bundle.json'
            src.write_text(json.dumps(make_bundle(baseline(),'C3','gate1','session1')),encoding='utf-8')
            cwd=Path.cwd()
            try:
                os.chdir(root)
                with self.assertRaisesRegex(ValueError,'Existing local'):
                    write_preview(src,root/'outputs'/'page.html',root/'missing.mp4')
            finally:os.chdir(cwd)


if __name__=='__main__':unittest.main()
