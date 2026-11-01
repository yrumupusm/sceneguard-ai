"""Synthetic integrity tests: no video/media upload, model or GPU dependency."""
from copy import deepcopy
from collections import defaultdict
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import mvp_full_evaluation_adapter as adapter
from sceneguard.accuracy_evaluation import evaluate


def card_result():
    """One card, early ordinary approach, later positive, one confirmed support."""
    events = [dict(event_id=f'e{i}',gate_id='C3_fence',decision_time_pts=t)
              for i,t in enumerate((.1,.4,.5))]
    evidence = [dict(event_id=f'e{i}',incident_id='incident',opened_pts=t,
                    automatic_status='침입 확인' if i==1 else '침입 의심',
                    first_confirmation_pts=.6 if i==1 else None)
                for i,t in enumerate((.1,.4,.5))]
    notices = [dict(incident_id='incident',kind=k,decision_time_pts=t,notification_key=k)
               for k,t in [('suspicion',.1),('confirmation',.6)]]
    return dict(execution_mode='current_input_analysis',source_evidence_mode='computed_in_current_run',
        contract='gate_activity_episodes_v1',events=events,evidence=evidence,
        cards=[dict(incident_id='incident',gate_id='C3_fence',event_ids=['e0','e1','e2'],
                    first_confirmation_pts=.6,suspicion_notified=True,confirmation_notified=True)],
        notification_intents=notices,
        timeline=[dict(incident_id=n['incident_id'],notification_kind=n['kind'],notify=True,
                       decision_time_pts=n['decision_time_pts'],notification_key=n['notification_key']) for n in notices])


def source_row():
    return dict(video_id='E01_007',camera_id='C3',gate_id='C3_fence',sha256='source',
        media=dict(duration_seconds=1.,decoded_frame_count=30),split='development',
        official_label_sha256='official',official_annotations=dict(event_frame=[[12,24]]),
        original_event_row_count=1,label_frame_count_matches=True,label_size_matches=True)


class TruthTests(unittest.TestCase):
    def test_bases_are_separate_native_clocks_and_original_order_is_preserved(self):
        row = source_row()
        row['official_annotations']['event_frame'] = [[4,6],[1,3]]
        pts = [0.,.033,.068,.101,.135,.170,.204]
        zero = adapter.official_truth(row,pts,0)
        one = adapter.official_truth(row,pts,1)
        self.assertEqual(zero['original_event_frame'],[[4,6],[1,3]])
        self.assertEqual(zero['events'][0]['original_row_indices'],[1])
        self.assertEqual(zero['events'][0]['start'],.033)
        self.assertEqual(one['events'][0]['start'],0.)
        self.assertEqual(zero['events'][1]['end'],.204)
        self.assertFalse(zero['events'][0]['onset_precise'])

    def test_frame_count_mismatch_keeps_rows_and_no_fabricated_pts(self):
        row = source_row(); row['label_frame_count_matches'] = False
        for base in (0,1):
            gold = adapter.official_truth(row,[i/30 for i in range(30)],base)
            self.assertEqual(gold['truth_basis'],'unresolved')
            self.assertEqual(gold['events'],[])
            self.assertEqual(gold['unresolved_reference_events'],1)
            self.assertEqual(gold['original_event_frame'],[[12,24]])

    def test_one_based_zero_reference_is_unresolved_not_clamped(self):
        row = source_row(); row['official_annotations']['event_frame']=[[0,3]]
        self.assertEqual(adapter.official_truth(row,[i/30 for i in range(30)],1)['events'],[])

    def test_overlapping_same_gate_unioned_before_predictions_with_lineage(self):
        row=source_row(); row['official_annotations']['event_frame']=[[4,12],[10,18],[20,24]]
        gold=adapter.official_truth(row,[i/30 for i in range(30)],0)
        self.assertEqual(gold['original_event_row_count'],3)
        self.assertEqual(len(gold['events']),2)
        self.assertEqual(gold['events'][0]['original_row_indices'],[0,1])
        self.assertEqual(gold['events'][0]['end'],.6)

    def test_known_camera_and_fractional_fps_restrictions_are_distinct(self):
        info=dict(exact_native_30fps=False,stream_start_pts=0,first_native_pts=0)
        actual=adapter.support_for('E01_006',info)
        self.assertEqual(actual['camera_id'],'C3')
        self.assertIn('native_rate_or_PTS_spacing_not_exact_30fps',actual['reasons'])
        self.assertNotIn('camera_identity_unresolved',actual['reasons'])
        info['exact_native_30fps']=True
        self.assertEqual(adapter.support_for('E01_002',info)['camera_id'],None)

    def test_existing_review_masks_do_not_promote_006_or_positive_windows(self):
        # No dependency on ignored local CCTV/artifact files in a fresh clone.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            tracked=('configs/mvp_small_eval_labels_r1.json',
                'docs/experiments/EXP-0016-prompt-evidence-rubric.md',
                'docs/experiments/EXP-0040-user-review.md',
                'docs/experiments/EXP-0041-user-review.md',
                'docs/experiments/EXP-0048-user-review.md',
                'docs/data/AIHUB_INTRUSION_USER_REVIEW.md')
            for name in tracked:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes((adapter.ROOT/name).read_bytes())
            for vid, clips in [('007',[('s0007',58.4,60.166666666666664),('s0008',60.13333333333333,63.)]),
                               ('030',[('s0002',84.,86.53333333333333)])]:
                path=root/f'outputs/exp0040/{vid}-v1/evidence/render-receipt.json'
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps(dict(videos=[dict(path=s+'.mp4',pts_mapping=[
                    dict(source_pts=a),dict(source_pts=b)]) for s,a,b in clips])))
            masks, positives, candidates=adapter.reviewed_evidence(root)
        self.assertFalse(masks['E01_006'])
        self.assertEqual(candidates['E01_006'][0]['status'],'user_reviewed_non_event_candidate_not_verified')
        self.assertEqual(len(positives['E01_007']),1)
        self.assertEqual(sum(m['end']-m['start'] for m in masks['E01_007'] if m['evidence_id']=='EXP48-late-pedestrians'),20)
        wait=next(m for m in masks['E01_007'] if m['evidence_id']=='EXP-0041-s0008')
        self.assertEqual(wait['end'],63.)
        self.assertLess(wait['end'],65.)


class PredictionTests(unittest.TestCase):
    def test_per_evidence_confirmation_not_propagated_from_card(self):
        result=adapter.extract_predictions(card_result())
        self.assertEqual(result[0]['suspicion_evidence_pts'],[.1,.4,.5])
        self.assertEqual(result[0]['confirmation_evidence_pts'],[.6])
        self.assertEqual([s['first_confirmation_pts'] for s in result[0]['source_evidence']],[None,.6,None])

    def test_early_first_alarm_remains_negative_even_when_card_is_hit(self):
        manifest=dict(schema_version=1,protocol_id=adapter.PROTOCOL,analysis_revision='a'*40,videos=[dict(
            video_id='synthetic',split='development',duration_seconds=1.,processed_seconds=1.,
            execution_status='complete',truth_basis='reviewed',unresolved_reference_events=0,
            events=[dict(id='event',gate_id='C3_fence',start=.3,end=.8,onset_precise=False,provenance='synthetic')],
            verified_non_event_intervals=[dict(gate_id='C3_fence',start=0.,end=.3,provenance='synthetic')],
            predictions=adapter.extract_predictions(card_result()))])
        report=evaluate(manifest)
        suspicion=report['modes']['suspicion']['by_video'][0]
        self.assertEqual(suspicion['counts']['tp'],1)
        self.assertEqual(suspicion['counts']['false_notices_in_verified_negative'],1)

    def test_timeline_snapshots_do_not_create_new_evidence(self):
        cards=card_result()
        cards['timeline'] += [dict(incident_id='incident',notify=False,decision_time_pts=.7)]*20
        self.assertEqual(adapter.extract_predictions(cards)[0]['suspicion_evidence_pts'],[.1,.4,.5])

    def test_missing_notification_is_rejected(self):
        cards=card_result();cards['notification_intents'].pop()
        with self.assertRaisesRegex(ValueError,'Missing or extra'):
            adapter.extract_predictions(cards)

    def test_changed_notification_clock_is_rejected(self):
        cards=card_result();cards['notification_intents'][0]['decision_time_pts']=.2
        with self.assertRaisesRegex(ValueError,'timeline'):
            adapter.extract_predictions(cards)

    def test_missing_confirmation_intent_flag_is_rejected(self):
        cards=card_result();cards['cards'][0]['confirmation_notified']=False
        with self.assertRaisesRegex(ValueError,'first confirmation intent'):
            adapter.extract_predictions(cards)

    def test_duplicate_owner_rejected(self):
        cards=card_result();cards['cards'][0]['event_ids'].append('e0')
        with self.assertRaisesRegex(ValueError,'multiply assigned'):
            adapter.extract_predictions(cards)

    def test_unassigned_candidate_rejected(self):
        cards=card_result();cards['cards'][0]['event_ids'].pop()
        with self.assertRaisesRegex(ValueError,'missing from incident'):
            adapter.extract_predictions(cards)

    def test_historical_exp_result_rejected(self):
        cards=card_result();cards['execution_mode']='historical_replay'
        with self.assertRaisesRegex(ValueError,'Current mvp_pipeline'):
            adapter.extract_predictions(cards)

    def test_no_mutation_and_empty_actual_result(self):
        cards=card_result();copy=deepcopy(cards)
        adapter.extract_predictions(cards);self.assertEqual(cards,copy)
        for key in ('cards','events','evidence','notification_intents','timeline'):
            cards[key]=[]
        self.assertEqual(adapter.extract_predictions(cards),[])


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.folder=self.root/'run'
        self.folder.mkdir()
        self.expected={'sceneguard/mvp_pipeline.py':'codehash'}
        self.source=self.root/'source.mp4';self.source.write_bytes(b'synthetic original')
        self.row=source_row();self.row['sha256']=adapter.sha256(self.source)
        self.clocks=dict(time_base='1/30',native_pts=list(range(30)))
        clocks_path=self.root/'clocks.json'
        self.write(clocks_path,dict(clocks=self.clocks))
        self.row.update(native_pts_path=str(clocks_path),native_pts_sha256=adapter.sha256(clocks_path))
        request=dict(code_sha256=self.expected,video=str(self.source),camera='C3',whole=True,
                     input_sha256={str(self.source):self.row['sha256']})
        self.write(self.folder/'request.json',request)
        self.write(self.folder/'status.json',dict(state='analysis_complete',frames=30,elapsed_seconds=2.))
        self.write(self.folder/'decision/cards.json',card_result())
        self.frames=[dict(frame_index=i,native_pts=i,time_base='1/30',pts=float(Fraction(i,30))) for i in range(30)]
        for path in ('image-paths/frame-evidence.jsonl','source/tracking/frames.jsonl','cache/person_cache.jsonl'):
            target=self.folder/path;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(''.join(json.dumps(f)+'\n' for f in self.frames))
        self.write(self.folder/'cache/run.json',{})
        self.write(self.folder/'source/analysis/analysis.json',dict(source_paths=dict(cache=str(self.folder/'cache'))))
        viewer=dict(source_sha256=self.row['sha256'],video_id='E01_007',gate_id='C3_fence',
                    cards_path=str(self.folder/'decision/cards.json'),cards_sha256=adapter.sha256(self.folder/'decision/cards.json'),
                    requested_window=[0.,1.])
        self.write(self.folder/'viewer-manifest.json',viewer)
        self.refresh_receipts()

    def write(self,path,data):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data))

    def refresh_receipts(self):
        binding=dict(request_sha256=adapter.sha256(self.folder/'request.json'),
            tracking_sha256=adapter.sha256(self.folder/'source/tracking/frames.jsonl'),
            analysis_sha256=adapter.sha256(self.folder/'source/analysis/analysis.json'),
            cache_sha256=dict(cache=adapter.sha256(self.folder/'cache/person_cache.jsonl'),
                              metadata=adapter.sha256(self.folder/'cache/run.json')))
        for stage,name in [('decision','cards.json'),('image-paths','frame-evidence.jsonl')]:
            self.write(self.folder/stage/'stage.json',dict(binding=binding,artifacts={name:adapter.sha256(self.folder/stage/name)}))

    def adapt(self,status='complete',**extra):
        return adapter.adapt_execution(self.row,dict(execution_status=status,run_directory=str(self.folder),**extra),self.expected,self.root)

    def test_complete_requires_all_native_source_frames_and_bindings(self):
        actual=self.adapt()
        self.assertEqual(actual['processed_seconds'],1.)
        self.assertTrue(actual['execution_binding']['full_native_pts_verified'])
        self.assertEqual(actual['execution_binding']['native_frames'],30)

    def test_explicit_native_eof_keeps_original_exposure_denominator(self):
        self.row['media'].update(duration_seconds=29/30, average_rate='30',
                                 full_native_end_seconds=1.)
        actual=self.adapt()
        self.assertEqual(actual['execution_binding']['native_frames'],30)
        self.assertEqual(actual['processed_seconds'],29/30)

    def test_forged_native_eof_rejected(self):
        self.row['media'].update(average_rate='30',full_native_end_seconds=1.5)
        with self.assertRaisesRegex(ValueError,'Native EOF endpoint'):
            self.adapt()

    def test_missing_frame_zero_rejected_even_with_consistent_stage_hash(self):
        path=self.folder/'image-paths/frame-evidence.jsonl'
        path.write_text(''.join(json.dumps(dict(f,frame_index=i))+'\n' for i,f in enumerate(self.frames[1:])))
        self.refresh_receipts()
        with self.assertRaisesRegex(ValueError,'native source frame partition'):
            self.adapt()

    def test_cache_missing_frame_zero_rejected_even_with_updated_hash(self):
        path=self.folder/'cache/person_cache.jsonl'
        path.write_text(''.join(json.dumps(f)+'\n' for f in self.frames[1:]))
        self.refresh_receipts()
        with self.assertRaisesRegex(ValueError,'native source frame partition'):
            self.adapt()

    def test_inventory_whole_cache_claim_requires_decoded_frame_zero(self):
        self.write(self.root/'configs/mvp0001_cameras.json',dict(cameras=dict(C3={})))
        path=self.folder/'cache/person_cache.jsonl'
        path.write_text(''.join(json.dumps(f)+'\n' for f in self.frames[1:]))
        info=dict(duration_seconds=1.,source_size=[10,10],time_base='1/30')
        with patch('sceneguard.video_cards.validate_cached',return_value=None):
            result=adapter.inspect_caches([(self.folder/'cache/run.json',dict(frames=29))],
                self.source,info,'C3',self.root,self.clocks)
        self.assertFalse(result[0]['whole_source_match'])
        self.assertIn('native source frame partition',result[0]['reason'])

    def test_internal_missing_native_frame_rejected(self):
        path=self.folder/'source/tracking/frames.jsonl'
        path.write_text(''.join(json.dumps(f)+'\n' for f in self.frames if f['frame_index']!=13))
        self.refresh_receipts()
        with self.assertRaisesRegex(ValueError,'native source frame partition'):
            self.adapt()

    def test_crop_cannot_be_declared_complete(self):
        path=self.folder/'request.json';request=adapter.read(path);request['whole']=False
        self.write(path,request);self.refresh_receipts()
        with self.assertRaisesRegex(ValueError,'every original frame'):
            self.adapt()

    def test_wrong_analysis_revision_rejected(self):
        self.expected={'sceneguard/mvp_pipeline.py':'otherhash'}
        with self.assertRaisesRegex(ValueError,'Analysis code'):
            self.adapt()

    def test_source_mutation_rejected(self):
        self.source.write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError,'input changed'):
            self.adapt()

    def test_artifact_mutation_rejected(self):
        path=self.folder/'decision/cards.json';path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'artifact bytes'):
            self.adapt()

    def test_unexecuted_statuses_keep_reason_and_never_become_negative(self):
        for status in ('unsupported','not_run','failed'):
            actual=self.adapt(status,reason='synthetic blocker')
            self.assertEqual(actual['processed_seconds'],0)
            self.assertEqual(actual['execution_status'],status)
        with self.assertRaisesRegex(ValueError,'needs a reason'):
            self.adapt('not_run')

    def test_manifest_retains_nonexecuted_inventory_truth_counts(self):
        inv=self.root/'inventory.json';truth=self.root/'truth.json';executions=self.root/'executions.json'
        self.write(inv,dict(videos=[self.row]))
        self.write(truth,dict(inventory_sha256=adapter.sha256(inv),variant='official-zero-based',
            videos=[adapter.official_truth(self.row,[i/30 for i in range(30)],0)]))
        self.write(executions,dict(videos=[dict(video_id='E01_007',execution_status='not_run',reason='resource block')]))
        with patch.object(adapter,'revision_code_hashes',return_value=self.expected):
            manifest=adapter.build_manifest(inv,truth,executions,'a'*40,self.root/'manifest.json',self.root)
        self.assertEqual(len(manifest['videos']),1)
        self.assertEqual(len(manifest['videos'][0]['events']),1)
        self.assertEqual(manifest['videos'][0]['execution_status'],'not_run')

    def test_manifest_rejects_removed_inventory_row(self):
        inv=self.root/'inventory.json';truth=self.root/'truth.json';executions=self.root/'executions.json'
        self.write(inv,dict(videos=[self.row]))
        self.write(truth,dict(inventory_sha256=adapter.sha256(inv),videos=[]))
        self.write(executions,dict(videos=[]))
        with self.assertRaisesRegex(ValueError,'complete inventory'):
            adapter.build_manifest(inv,truth,executions,'a'*40,self.root/'manifest.json',self.root)

    def test_frozen_truth_keeps_conflicts_separate_and_window_positives_unresolved(self):
        inv=self.root/'inventory.json';self.write(inv,dict(videos=[self.row]))
        for name in ('docs/experiments/EXP-0028-user-tracking-review.md',
                     'docs/experiments/EXP-0041-user-review.md'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic user evidence')
        masks=defaultdict(list,{'E01_007':[dict(start=.4,end=.5,provenance='synthetic verified negative')]})
        positives=defaultdict(list,{'E01_007':[dict(start=.3,end=.8,provenance='synthetic positive window')]})
        with patch.object(adapter,'reviewed_evidence',return_value=(masks,positives,defaultdict(list))):
            adapter.freeze_truth(inv,self.root/'truth',self.root)
        zero=adapter.read(self.root/'truth/official-zero-based.json')['videos'][0]
        reviewed=adapter.read(self.root/'truth/reviewed.json')['videos'][0]
        self.assertEqual(zero['verified_non_event_intervals'],[])
        self.assertEqual(len(zero['conflicting_reviewed_non_event_intervals']),1)
        self.assertEqual(len(zero['events']),1)
        self.assertEqual(reviewed['events'],[])
        self.assertEqual(reviewed['unresolved_reference_events'],1)
        self.assertEqual(reviewed['original_event_frame'],[[12,24]])

    def test_030_repeated_positive_observations_are_one_unresolved_context(self):
        self.row['video_id']='E01_030'
        inv=self.root/'inventory.json';self.write(inv,dict(videos=[self.row]))
        for name in ('EXP-0028-user-tracking-review.md','EXP-0024-user-pose-review.md','EXP-0039-user-review.md'):
            path=self.root/'docs/experiments'/name
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic user evidence')
        with patch.object(adapter,'reviewed_evidence',return_value=tuple(defaultdict(list) for _ in range(3))):
            adapter.freeze_truth(inv,self.root/'truth',self.root)
        gold=adapter.read(self.root/'truth/reviewed.json')['videos'][0]
        self.assertEqual(gold['unresolved_reference_events'],1)
        self.assertEqual(len(gold['qualitative_user_observations']),5)
        self.assertEqual(gold['events'],[])
        self.assertEqual(len({o['event_context_id'] for o in gold['qualitative_user_observations']}),1)

    def test_frozen_output_is_idempotent_and_cannot_be_replaced(self):
        path=self.root/'frozen.json'
        adapter.save(path,dict(value=1));before=path.stat().st_mtime_ns
        adapter.save(path,dict(value=1));self.assertEqual(path.stat().st_mtime_ns,before)
        with self.assertRaisesRegex(ValueError,'overwrite'):
            adapter.save(path,dict(value=2))


if __name__=='__main__':
    unittest.main()
