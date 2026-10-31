import unittest
from sceneguard.exp0039_evidence import extend_paths, alarm_label, render_segment, unchanged_proposal

class SavedPathsTests(unittest.TestCase):
    def test_proposal_preserves_loss_bilateral_gap_rows_and_card_grouping(self):
        import copy
        from sceneguard.exp0036_application import make_bundle
        baseline=dict(experiment='EXP-0035',video_id='test',source_window=[0,10],events=[
            dict(status='침입 의심',raw_id=1,segment='s1',decision_time_pts=3.,reason='recent_gate_presence_then_loss'),
            dict(status='침입 의심',raw_id=2,segment='s2',decision_time_pts=4.,reason='observed_side_transition')],
            existing_alerts=[dict(video_id='test',condition='gap',track_id=2,emitted_at_pts=4.)])
        cards=make_bundle(baseline,'C3','gate','session')
        diagnostic=dict(results=[dict(source_pointer='/events/0',flow_support=dict(
            outcome='overlap_or_multiple_targets_ambiguous',seed_competition=True))])
        before=copy.deepcopy((baseline,cards,diagnostic))
        result=unchanged_proposal(baseline,cards,diagnostic)
        self.assertEqual(result['proposal']['events'],cards['events'])
        self.assertEqual(result['proposal']['cards'],cards['cards'])
        self.assertEqual(result['counts']['suppressed'],0)
        self.assertEqual(len(result['row_decisions']),3)
        self.assertTrue(all(r['proposed_status']=='침입 의심' for r in result['row_decisions']))
        self.assertEqual((baseline,cards,diagnostic),before)
        diagnostic['results'][0]['flow_support']['outcome']='image_continuation_supported_review_only'
        with self.assertRaises(ValueError):unchanged_proposal(baseline,cards,diagnostic)

    def test_dropout_retains_identity_instead_of_array_position(self):
        a=dict(point_ids=[0,1,2],points_original_pixels=[[0,0],[10,10],[20,20]])
        b=dict(point_ids=[2],points_original_pixels=[[21,21]])
        paths=extend_paths({},a,initial=True)
        self.assertEqual(extend_paths(paths,b),{2:[[20,20],[21,21]]})

    def test_reappearing_point_rejected_even_after_every_point_lost(self):
        with self.assertRaises(ValueError):
            extend_paths({},dict(point_ids=[1],points_original_pixels=[[1,1]]))

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            extend_paths({},dict(point_ids=[1,1],points_original_pixels=[[1,1],[2,2]]),initial=True)

    def test_alarm_stays_pending_until_original_decision(self):
        self.assertEqual(alarm_label(55.,56.),'PENDING (not yet emitted)')
        self.assertEqual(alarm_label(56.,56.),'SUSPECTED')

    def test_nonzero_source_pts_renders_as_short_zero_based_clip(self):
        import av
        import numpy as np
        from fractions import Fraction
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)/'source.mp4';target=Path(temporary)/'target.mp4'
            with av.open(str(source),'w') as container:
                stream=container.add_stream('libx264',rate=30)
                stream.width=300;stream.height=200;stream.pix_fmt='yuv420p'
                for i in range(5):
                    frame=av.VideoFrame.from_ndarray(np.full((200,300,3),80+i,dtype=np.uint8),format='bgr24')
                    frame.pts=i;frame.time_base=Fraction(1,30)
                    for packet in stream.encode(frame):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            cached=[];tracked=[];records=[]
            for i in range(5):
                c=dict(pts=i/30,native_pts=i*512,time_base='1/15360',source_size=[300,200],boxes=[],scores=[])
                cached.append(c);tracked.append(dict(c,detections=[],states=[]))
                if i>=2:records.append(dict(pts=c['pts'],native_pts=c['native_pts'],time_base=c['time_base'],frame_index=i,
                    point_ids=[4],points_original_pixels=[[100+i,100]],background_point_ids=[9],
                    background_points_original_pixels=[[10,10]]))
            support=dict(flow_records=records,working_crop=[0,0,300,200],flow_support=dict(outcome='test_only'),
                detector_audit=dict(segment='s1',raw_id=1,last_observed_pts=3/30,decision_time_pts=4/30))
            result=render_segment(source,cached,tracked,support,target,width=640)
            self.assertEqual(result['frames'],3)
            self.assertEqual(result['first_pts'],0.)
            self.assertAlmostEqual(result['last_pts'],2/30)
            self.assertAlmostEqual(result['source_first_pts'],2/30)
            self.assertEqual(result['pts_mapping'][0]['native_pts'],1024)
