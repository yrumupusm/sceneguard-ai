# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only profiling of official calls, expecting the new 960 tensor."""
import hashlib
import inspect
import sys
import time
from orchestration.batch06_pose_command import ROOT

class ObserveOfficial:
    """Python profiler observer; never substitutes any model/predictor algorithm.

    Stage times include profiler/synchronization overhead. Results.speed is stored
    separately. Actual tensor capture is before warmup; its copy/save overhead is
    recorded separately from preprocess elapsed, but included in predict wall.
    """
    def __init__(self, torch, folder, frame_id, model):
        from ultralytics.engine.predictor import BasePredictor
        from ultralytics.nn.autobackend import AutoBackend
        from ultralytics.nn.tasks import BaseModel
        self.torch, self.folder, self.frame_id, self.model = torch, folder, frame_id, model
        self.codes = {inspect.unwrap(getattr(BasePredictor,n)).__code__: n for n in ('setup_model','preprocess','inference')}
        self.codes[inspect.unwrap(AutoBackend.warmup).__code__] = 'warmup'
        self.codes[inspect.unwrap(BaseModel.predict).__code__] = 'network_predict'
        self.starts, self.events, self.attempts = {}, [], []
        self.tensor = None
        self.warming = False

    def profile(self, frame, event, arg):
        name = self.codes.get(frame.f_code)
        if name is None or event not in ('call', 'return'):
            return
        if event == 'call':
            self.torch.cuda.synchronize()
            if name == 'warmup':
                self.warming = True
            self.attempts.append(dict(stage=name,warmup=self.warming))
            self.starts[id(frame)] = (time.perf_counter(), self.warming)
        else:
            self.torch.cuda.synchronize()
            start, warm = self.starts.pop(id(frame))
            self.events.append(dict(stage=name, seconds=time.perf_counter()-start,
                warmup=warm, returned_value=arg is not None))
            if name == 'warmup':
                self.warming = False
            if name == 'preprocess' and arg is not None:
                t = time.perf_counter()
                actual = arg.detach().cpu().numpy().copy()
                if list(actual.shape) != [1,3,960,960] or str(actual.dtype) != 'float32' or str(arg.device) != 'cuda:0':
                    raise ValueError('actual official preprocess must be CUDA0 FP32 1x3x960x960')
                import numpy as np
                path = self.folder / (self.frame_id+'-input.npy')
                np.save(path, actual, allow_pickle=False)
                self.tensor = dict(shape=list(actual.shape), dtype=str(actual.dtype), device=str(arg.device),
                    sha256=hashlib.sha256(actual.tobytes()).hexdigest(), path=str(path.relative_to(ROOT)),
                    capture_save_seconds=time.perf_counter()-t)

    def __enter__(self):
        self.previous = sys.getprofile()
        if self.previous is not None:
            raise ValueError('existing Python profiler cannot be displaced')
        sys.setprofile(self.profile)
        return self

    def __exit__(self, *args):
        sys.setprofile(self.previous)
