"""Synthetic contracts only; no actual CCTV accuracy or service claims."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from sceneguard.continuation_audit import (ContinuationPolicy,audit_continuations,
                                           notification_view,_iou,_zone)
from sceneguard.review_store import ReviewStore, ReviewConflict


def sample():
    scene={'zones':{
        'outside':[[0,0],[.45,0],[.45,1],[0,1]],
        'inside':[[.55,0],[1,0],[1,1],[.55,1]]}}
    def seg(sid,raw,times,box):
        return dict(id=sid,raw_id=raw,rows=[dict(pts=t,frame_index=round(t*30),cache_index=0,
                                               bbox=list(box)) for t in times])
    before=seg('s1',1,[0.,.1,.2,.3,.4],[.1,.2,.2,.6])
    after=seg('s2',2,[.5,.6,.7,.8,.9,1.,1.1,1.2,1.3,1.4],[.105,.2,.205,.6])
    event=dict(segment='s1',raw_id=1,pts=1.4,decision_time_pts=1.4,last_observed_pts=.4,
               status='침입 의심',reason='recent_gate_presence_then_loss')
    result=dict(experiment='EXP-0035',video_id='SYNTHETIC',segments=[before,after],
                events=[event],existing_alerts=[dict(track_id=7,emitted_at_pts=.35)])
    return result,scene


class ContinuationTests(unittest.TestCase):
    def test_clear_measured_same_side_continuation(self):
        r,s=sample(); a=audit_continuations(r,s)
        self.assertEqual(a['proposed_review_only'],1)
        self.assertFalse(a['audits'][0]['identity_verified'])

    def test_default_is_audit_not_suppression(self):
        r,s=sample();old=deepcopy(r);a=audit_continuations(r,s)
        self.assertEqual(notification_view(r,a)['events'],r['events'])
        self.assertEqual(r,old)

    def test_apply_preserves_line_alerts_and_original_payload(self):
        r,s=sample();old=deepcopy(r);a=audit_continuations(r,s)
        v=notification_view(r,a,True)
        self.assertEqual(v['events'],[])
        self.assertEqual(v['existing_alerts'],r['existing_alerts'])
        self.assertEqual(v['review_only_events'][0]['source_event'],old['events'][0])
        self.assertEqual(v['automatic_negative_decisions'],0)
        self.assertEqual(r,old)

    def test_no_reappearance_keeps_candidate(self):
        r,s=sample();r['segments']=r['segments'][:1]
        self.assertEqual(audit_continuations(r,s)['proposed_review_only'],0)

    def test_other_side_keeps_candidate(self):
        r,s=sample()
        for row in r['segments'][1]['rows']:row['bbox']=[.7,.2,.8,.6]
        self.assertEqual(audit_continuations(r,s)['proposed_review_only'],0)

    def test_unknown_side_does_not_erase_suspicion(self):
        r,s=sample()
        for seg in r['segments']:
            for row in seg['rows']:row['bbox']=[.46,.2,.54,.6]
        self.assertEqual(audit_continuations(r,s)['proposed_review_only'],0)

    def test_predicted_boxes_are_not_measurements(self):
        r,s=sample();r['segments'][1]['rows'][0]['observed']=False
        with self.assertRaises(ValueError):audit_continuations(r,s)

    def test_two_competing_targets_keeps_candidate(self):
        r,s=sample();other=deepcopy(r['segments'][1]);other.update(id='s3',raw_id=3)
        r['segments'].append(other)
        a=audit_continuations(r,s)['audits'][0]
        self.assertEqual(a['recommendation'],'keep')
        self.assertEqual(a['reason'],'competing_continuations')

    def test_overlapping_bystander_keeps_candidate(self):
        r,s=sample();other=deepcopy(r['segments'][0]);other.update(id='s3',raw_id=3)
        r['segments'].append(other)
        self.assertEqual(audit_continuations(r,s)['audits'][0]['reason'],
                         'overlapping_person_or_duplicate_unresolved')

    def test_preexisting_track_is_not_a_new_continuation(self):
        r,s=sample()
        r['segments'][1]['rows'].insert(0,dict(pts=.3,frame_index=9,bbox=[.105,.2,.205,.6]))
        self.assertEqual(audit_continuations(r,s)['proposed_review_only'],0)

    def test_long_gap_keeps_candidate(self):
        r,s=sample();r['segments'][1]['rows']=r['segments'][1]['rows'][3:]
        self.assertEqual(audit_continuations(r,s)['proposed_review_only'],0)

    def test_too_short_post_loss_observation_keeps_candidate(self):
        r,s=sample();r['segments'][1]['rows']=r['segments'][1]['rows'][:3]
        self.assertEqual(audit_continuations(r,s)['proposed_review_only'],0)

    def test_source_scale_jump_keeps_candidate(self):
        r,s=sample();r['segments'][0]['rows'][-1]['bbox']=[.1,.2,.2,.35]
        self.assertEqual(audit_continuations(r,s)['proposed_review_only'],0)

    def test_destination_stops_being_visible_before_decision(self):
        r,s=sample();r['segments'][1]['rows']=r['segments'][1]['rows'][:5]
        self.assertEqual(audit_continuations(r,s)['proposed_review_only'],0)

    def test_prior_independent_suspicion_not_overruled(self):
        r,s=sample();r['events'].insert(0,dict(segment='s1',raw_id=1,pts=.3,decision_time_pts=.3,
                                status='침입 의심',reason='observed_side_transition'))
        self.assertEqual(audit_continuations(r,s)['audits'][0]['reason'],'independent_suspicion_preserved')

    def test_future_frames_do_not_change_current_decision(self):
        r,s=sample();a=audit_continuations(r,s)
        r['segments'][1]['rows'].append(dict(pts=2,frame_index=60,bbox=[.7,.1,.9,.9]))
        future=deepcopy(r['segments'][1]);future.update(id='future',raw_id=9)
        future['rows']=[dict(pts=2.1,frame_index=63,bbox=[.1,.2,.2,.6])]
        r['segments'].append(future)
        self.assertEqual(a,audit_continuations(r,s))

    def test_bad_source_partition_is_rejected(self):
        r,s=sample();r['segments'][1]['raw_id']=1
        r['segments'][1]['rows'][0].update(pts=.4,frame_index=12)
        with self.assertRaises(ValueError):audit_continuations(r,s)

    def test_apply_rejects_wrong_audit_source(self):
        r,s=sample();a=audit_continuations(r,s);r['events'][0]['reason']='other'
        with self.assertRaises(ValueError):notification_view(r,a,True)

    def test_invalid_policy_rejected(self):
        for p in [ContinuationPolicy(max_gap_seconds=0), ContinuationPolicy(min_observations=True),
                  ContinuationPolicy(min_iou=1.2),ContinuationPolicy(competition_iou=.8)]:
            with self.assertRaises(ValueError):p.validate()

    def test_overlap_math_and_boundary_unknown(self):
        self.assertAlmostEqual(_iou([0,0,.2,.2],[0,0,.2,.2]),1)
        r,s=sample();s['zones']['inside']=s['zones']['outside']
        self.assertIsNone(_zone([.1,.1,.2,.3],s['zones']))


class ReviewStoreTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.path=Path(t.name)/'review.sqlite3';self.s=ReviewStore(self.path)
        self.key=('session','incident-1','a'*64)

    def test_default_no_review_does_not_claim_confirmed(self):
        self.assertIsNone(self.s.get(*self.key))
        self.assertEqual(self.s.history(*self.key),[])

    def test_save_is_separate_and_persists_restart(self):
        machine={'status':'침입 의심'}
        value=self.s.save(*self.key,status='침입 확인',reviewer='local-user',expected_version=0,note='영상 확인')
        self.assertEqual(value['version'],1)
        self.assertEqual(ReviewStore(self.path).get(*self.key)['status'],'침입 확인')
        self.assertEqual(machine,{'status':'침입 의심'})

    def test_updates_append_history_and_reset_is_explicit(self):
        for i,status in enumerate(('침입 확인','침입 아님','판단 불가','침입 의심')):
            self.s.save(*self.key,status=status,reviewer='reviewer',expected_version=i)
        self.assertEqual([r['version'] for r in self.s.history(*self.key)],[1,2,3,4])
        self.assertEqual(self.s.get(*self.key)['status'],'침입 의심')

    def test_stale_version_does_not_overwrite(self):
        self.s.save(*self.key,status='침입 확인',reviewer='a',expected_version=0)
        with self.assertRaises(ReviewConflict):
            self.s.save(*self.key,status='침입 아님',reviewer='b',expected_version=0)
        self.assertEqual(len(self.s.history(*self.key)),1)

    def test_new_bundle_does_not_inherit_old_review(self):
        self.s.save(*self.key,status='침입 확인',reviewer='a',expected_version=0)
        self.assertIsNone(self.s.get('session','incident-1','b'*64))
        self.assertIsNone(self.s.get('different','incident-1','a'*64))

    def test_concurrent_edits_one_wins(self):
        def save(status):
            try:return self.s.save(*self.key,status=status,reviewer='a',expected_version=0)['version']
            except ReviewConflict:return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(save,('침입 확인','침입 아님')))
        self.assertEqual(results.count(1),1)
        self.assertEqual(results.count('conflict'),1)
        self.assertEqual(len(self.s.history(*self.key)),1)

    def test_invalid_inputs(self):
        for overrides in [dict(status='safe'),dict(expected_version=True),dict(note='x'*2001),dict(reviewer='')]:
            args=dict(status='침입 확인',reviewer='a',expected_version=0);args.update(overrides)
            with self.assertRaises(ValueError):self.s.save(*self.key,**args)
        with self.assertRaises(ValueError):self.s.get('session','incident','invalid')

    def test_sql_strings_are_data_not_queries(self):
        key=("'; DROP TABLE incident_review; --",'case','a'*64)
        self.s.save(*key,status='침입 확인',reviewer='a',expected_version=0)
        self.assertEqual(self.s.get(*key)['status'],'침입 확인')
        self.assertIsNone(self.s.get(*self.key))

    def test_symlink_storage_is_rejected(self):
        link=self.path.parent/'link.sqlite3';link.symlink_to(self.path)
        with self.assertRaises(ValueError):ReviewStore(link)


if __name__=='__main__':unittest.main()
