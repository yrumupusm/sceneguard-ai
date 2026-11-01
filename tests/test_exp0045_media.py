"""Causal geometry/PTS mapping and synthetic native-video integration; no CCTV semantics."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

from test_directional_loss import fixture, scene, normalized
from test_exp0045_integration import bundle
from sceneguard.directional_loss import SavedGateDirection
from sceneguard.exp0045_application import evaluate
from sceneguard.exp0045_media import (causal_history, causal_birth, inward_band,
    validate_mapping, displayed_motion, execute)
from sceneguard.gate_episode_evidence import Gate
from sceneguard.incident_notifications import group_notifications


class CausalMedia(unittest.TestCase):
    def test_history_first_box_motion_and_decision_are_prefix_only_and_rewindable(self):
        frames,seg,event=fixture(); gate=Gate(scene()); engine=SavedGateDirection(frames,scene())
        decision=engine.classify(event,seg)
        self.assertIsNone(causal_history(seg,decision,-.1,gate,engine))
        prefix=causal_history(seg,decision,.25,gate,engine)
        self.assertEqual(prefix['last']['pts'],.25)
        self.assertTrue(prefix['current'])
        self.assertIsNone(prefix['decision_time_pts'])
        self.assertLessEqual(prefix['contact']['pts'],.25)
        self.assertLessEqual(prefix['motion']['end_pts'],.25)
        final=causal_history(seg,decision,1.5,gate,engine)
        self.assertEqual(final['automatic_status'],'confirmed')
        self.assertFalse(final['current'])
        self.assertEqual(causal_history(seg,decision,.25,gate,engine),prefix)

    def test_birth_first_box_never_leaks_before_decision(self):
        event=dict(event_id='new',decision_time_pts=2.1,source_event=dict(birth_pts=2.,
            first_actual_bbox=[.51,.4,.55,.6],current_actual_bbox=[.52,.4,.56,.6],
            observation_refs=[dict(pts=2.),dict(pts=2.1)],birth_site={}))
        self.assertIsNone(causal_birth(event,2.099))
        self.assertTrue(causal_birth(event,2.1)['current'])
        self.assertFalse(causal_birth(event,2.2)['current'])
        self.assertIsNone(causal_birth(event,1.9))
        event['source_event']['observation_refs'][-1]['pts']=3
        with self.assertRaises(ValueError):causal_birth(event,2.1)

    def test_finite_inward_band_has_exact_endpoint_projections_and_sign(self):
        gate=Gate(scene()); band=inward_band(gate,75)
        for p,along,signed in zip(band,(0,1,1,0),(0,0,75,75)):
            self.assertAlmostEqual(sum((p[k]-gate.a[k])*gate.v[k] for k in (0,1))/gate.length**2,along)
            self.assertAlmostEqual(sum((p[k]-gate.a[k])*gate.normal[k] for k in (0,1)),signed)

    def test_unknown_motion_has_no_arrow_and_stale_motion_is_hidden(self):
        self.assertFalse(displayed_motion(dict(direction='unknown'),2)['arrow_visible'])
        self.assertFalse(displayed_motion(dict(direction='inward',end_pts=0),2)['arrow_visible'])

    def test_mapping_rejects_future_contact_birth_review_and_card(self):
        row=dict(source_pts=1.,native_pts=1000,time_base='1/1000',births=[],cards={})
        validate_mapping([row])
        for key in ('last_actual_pts','gate_contact_pts','motion_end_pts','decision_time_pts'):
            with self.subTest(key=key), self.assertRaises(ValueError):validate_mapping([dict(row,**{key:2.})])
        with self.assertRaises(ValueError):validate_mapping([dict(row,births=[dict(first_pts=2,last_pts=2,decision_time_pts=2)])])
        with self.assertRaises(ValueError):validate_mapping([dict(row,reviewed_first_observation=dict(first_pts=2))])
        with self.assertRaises(ValueError):validate_mapping([dict(row,cards={'combined':[dict(first_notification_pts=.5,first_confirmation_pts=2)]})])

    def test_real_native_renderer_on_synthetic_pixels_and_engine_schema(self):
        import av
        import numpy as np
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary); paths=directory/'paths';paths.mkdir()
            frames,seg,raw=fixture(); video=directory/'synthetic.mp4'
            with av.open(str(video),'w') as container:
                stream=container.add_stream('libx264',rate=4);stream.width=1000;stream.height=800
                stream.pix_fmt='yuv420p';stream.time_base=Fraction(1,1000);stream.codec_context.time_base=Fraction(1,1000)
                for row in frames:
                    image=np.zeros((800,1000,3),dtype=np.uint8)
                    frame=av.VideoFrame.from_ndarray(image,format='bgr24')
                    frame.pts=round(row['pts']*1000);frame.time_base=Fraction(1,1000)
                    for packet in stream.encode(frame):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            with av.open(str(video)) as container:
                clocks=[(f.pts,str(f.time_base)) for f in container.decode(video=0)]
            for row,(native,tb) in zip(frames,clocks):row.update(native_pts=native,time_base=tb)
            baseline=dict(video_id='synthetic',segments=[seg],policy=dict(loss_wait=1.),source_paths=dict(video=str(video)))
            event=normalized('loss',1.5);event['source_event']=raw
            base=bundle([event]);views,decisions,births,audits=evaluate(baseline,base,frames,scene(),group_notifications)
            def save(path,value):path.write_text(json.dumps(value))
            baseline_path=directory/'source.json';save(baseline_path,baseline)
            save(directory/'baseline-cards.json',base)
            for mode,view in views.items():save(directory/(mode+'-cards.json'),view)
            for name,value in [('scene-used',scene()),('history-decisions',decisions),('inside-birth-events',births),('birth-audits',audits)]:
                save(directory/(name+'.json'),value)
            (paths/'frame-evidence.jsonl').write_text('\n'.join(json.dumps(row) for row in frames))
            report=execute(directory,paths,baseline_path)
            self.assertEqual(report['source_frames_decoded'],5)
            self.assertEqual(report['actual_loss_classifications'],0)
            manifest=json.loads((directory/'media/manifest.json').read_text())
            mapping=manifest['videos'][0]['mapping'];validate_mapping(mapping)
            self.assertEqual(mapping[0]['source_pts'],0.)
            self.assertEqual(mapping[-1]['decision_time_pts'],1.5)


if __name__=='__main__':unittest.main()
