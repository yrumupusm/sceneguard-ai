"""Cache I/O and comparison contracts using a fake adapter, not real ByteTrack."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sceneguard import replay_gap_tracking as replay
from test_gap_boundary import CONFIG


class FakeAdapter:
    def __init__(self, ttl, interval):
        self.tracker = SimpleNamespace(max_time_lost=30 if ttl is None else round(ttl / interval))
    def step(self, frame):
        rows = [dict(track_id=1, bbox=[x/100 for x in box], score=score,
                     observed=True, confirmed=True, state='tracked')
                for box, score in zip(frame['boxes'], frame['scores'])]
        return rows, rows, []


class ReplayGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        frames = []
        for i in range(28):
            y = 40 if i < 10 else 60
            missing = 10 <= i < 18
            frames.append(dict(pts=i/30, native_pts=i, time_base='1/30', source_size=[100,100],
                               boxes=[] if missing else [[45,y-20,55,y]], scores=[] if missing else [.9]))
        self.frames = frames
        self.write_cache(frames)

    def write_cache(self, frames):
        path = self.cache / 'person_cache.jsonl'
        path.write_text(''.join(json.dumps(f)+'\n' for f in frames))
        self.meta = dict(status='complete', frames=len(frames), video_id='SYNTHETIC', config=CONFIG,
                         model_sha256=replay.FCOS_SHA, model_postprocess=replay.POSTPROCESS,
                         person_cache=dict(schema=1, stage=replay.STAGE, sha256=replay.sha256(path)))
        (self.cache/'run.json').write_text(json.dumps(self.meta))

    def test_full_comparison_and_input_preservation(self):
        before = {p.name:p.read_bytes() for p in self.cache.iterdir()}
        values = replay.run(self.cache, self.root/'out', adapter_factory=FakeAdapter)
        self.assertEqual([x['candidates'] for x in values], [0,1])
        self.assertEqual([x['tracker_buffer_frames'] for x in values], [30,90])
        self.assertEqual({p.name:p.read_bytes() for p in self.cache.iterdir()}, before)
        result = json.loads((self.root/'out/summary.json').read_text())
        self.assertEqual(result['actual_video_review'], 'pending')

    def test_existing_output_not_overwritten(self):
        path = self.root/'out';path.mkdir()
        with self.assertRaises(FileExistsError): replay.run(self.cache,path,adapter_factory=FakeAdapter)

    def test_changed_cache_rejected_before_output(self):
        with (self.cache/'person_cache.jsonl').open('a') as f: f.write('{}\n')
        with self.assertRaises(ValueError): replay.run(self.cache,self.root/'out',adapter_factory=FakeAdapter)
        self.assertFalse((self.root/'out').exists())

    def test_other_model_rejected(self):
        self.meta['model_sha256'] = 'finetuned'
        (self.cache/'run.json').write_text(json.dumps(self.meta))
        with self.assertRaises(ValueError): replay.load_cache(self.cache)

    def test_sampled_or_irregular_frame_rate_rejected(self):
        self.frames[10]['pts'] += .001
        self.write_cache(self.frames)
        with self.assertRaisesRegex(ValueError, 'near-30Hz'): replay.load_cache(self.cache)

    def test_bad_box_arrays_rejected(self):
        self.frames[0]['scores'] = []
        self.write_cache(self.frames)
        with self.assertRaisesRegex(ValueError, 'mismatched'): replay.load_cache(self.cache)

    def test_failure_not_marked_complete(self):
        def broken(ttl, interval): raise RuntimeError('synthetic adapter failure')
        with self.assertRaises(RuntimeError): replay.run(self.cache,self.root/'out',adapter_factory=broken)
        self.assertTrue((self.root/'out/failure.json').is_file())
        self.assertFalse((self.root/'out/summary.json').exists())

    def test_output_symlink_rejected(self):
        (self.root/'alias').symlink_to(self.cache, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            replay.run(self.cache,self.root/'alias/out',adapter_factory=FakeAdapter)


if __name__ == '__main__':
    unittest.main()
