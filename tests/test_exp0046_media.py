"""Portal schema, native-clock encoding and rewind checks using synthetic pixels."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_exp0046_integration import synthetic_inputs, working_directory
from sceneguard.exp0044_application import save
from sceneguard.exp0046_application import execute as classify
from sceneguard.exp0046_media import causal_observation, validate_mapping, execute


class PortalMedia(unittest.TestCase):
    def test_first_prior_current_and_decision_are_prefix_only_and_rewindable(self):
        box=[.1,.1,.2,.2]
        audit=dict(run_id='r',birth_pts=2.,bbox=box,site={},eligible=True)
        observations=[dict(pts=2.,bbox=box),dict(pts=2.1,bbox=box),dict(pts=2.2,bbox=box)]
        frames=[dict(pts=t,frame_index=i,actual_boxes=[dict(bbox=box)])
                for i,t in enumerate([1.,1.9,2.,2.1,2.2])]
        event=dict(decision_time_pts=2.1)
        self.assertIsNone(causal_observation(audit,observations,frames,1.9,event))
        prefix=causal_observation(audit,observations,frames,2.,event)
        self.assertIsNone(prefix['decision_time_pts'])
        self.assertTrue(prefix['current']);self.assertFalse(prefix['candidate'])
        self.assertEqual([r['pts'] for r in prefix['prior_actual_observations']],[1.,1.9])
        self.assertEqual(len(prefix['observation_refs']),1)
        decision=causal_observation(audit,observations,frames,2.1,event)
        self.assertEqual(decision['decision_time_pts'],2.1)
        self.assertTrue(decision['candidate'])
        self.assertEqual(len(decision['observation_refs']),2)
        self.assertFalse(causal_observation(audit,observations,frames,2.3,event)['current'])
        self.assertEqual(causal_observation(audit,observations,frames,2.,event),prefix)

    def test_mapping_rejects_each_future_portal_field_and_bad_prior(self):
        focus=dict(first_pts=1.,last_pts=1.,decision_time_pts=1.,
                   observation_refs=[dict(pts=1.)],prior_actual_observations=[dict(pts=.9)])
        row=dict(source_pts=1.,native_pts=1000,time_base='1/1000',births=[],cards={},portal_observation=focus)
        validate_mapping([row])
        for key in ('first_pts','last_pts','decision_time_pts'):
            invalid=deepcopy(row);invalid['portal_observation'][key]=2.
            with self.subTest(key=key),self.assertRaises(ValueError):validate_mapping([invalid])
        for key in ('observation_refs','prior_actual_observations'):
            invalid=deepcopy(row);invalid['portal_observation'][key][0]['pts']=2.
            with self.subTest(key=key),self.assertRaises(ValueError):validate_mapping([invalid])

    def test_native_renderer_handles_portal_without_top_level_distance(self):
        import av
        import numpy as np
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);inputs=synthetic_inputs(root,birth=True)
            baseline,base,frames,scene,group,protected,paths,history,region=inputs
            source=root/'synthetic.mp4'
            with av.open(str(source),'w') as container:
                stream=container.add_stream('libx264',rate=30)
                stream.width,stream.height=1000,800;stream.pix_fmt='yuv420p'
                stream.time_base=Fraction(1,90000);stream.codec_context.time_base=Fraction(1,90000)
                for row in frames:
                    image=np.zeros((800,1000,3),dtype=np.uint8)
                    frame=av.VideoFrame.from_ndarray(image,format='bgr24')
                    frame.pts=round(row['pts']*90000);frame.time_base=Fraction(1,90000)
                    for packet in stream.encode(frame):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            with av.open(str(source)) as container:
                clocks=[(f.pts,str(f.time_base)) for f in container.decode(video=0)]
            for row,(native,tb) in zip(frames,clocks):row.update(native_pts=native,time_base=tb)
            baseline['source_paths']=dict(video=str(source))
            baseline_path=root/'baseline.json';save(baseline_path,baseline)
            (paths/'frame-evidence.jsonl').write_text('\n'.join(json.dumps(r) for r in frames))
            with working_directory(root),patch('sceneguard.exp0044_application.prepared_inputs',return_value=inputs[:6]),patch('sceneguard.exp0045_application.select_scene',return_value=scene):
                classify(baseline_path,paths,history,root/'portal.json','outputs/result')
                report=execute(Path('outputs/result'),paths,baseline_path)
            self.assertEqual(report['source_frames_decoded'],61)
            self.assertEqual(report['actual_loss_classifications'],0)
            self.assertTrue(report['pixels_local_only'])
            manifest=json.loads((root/'outputs/result/media/manifest.json').read_text())
            self.assertEqual(len(manifest['videos']),2)
            mapping=manifest['videos'][1]['mapping'];validate_mapping(mapping)
            first=next(r for r in mapping if r['portal_observation'])
            self.assertIsNone(first['portal_observation']['decision_time_pts'])
            self.assertFalse(first['portal_observation']['candidate'])
            site=first['portal_observation']['site']
            self.assertNotIn('distance_pixels',site)
            self.assertIn('legacy_ground_test',site)
            self.assertFalse(mapping[0]['births'])
            self.assertTrue(any(r['births'] for r in mapping))


if __name__=='__main__':unittest.main()
