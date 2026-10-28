"""EXP-0010: the sole Qwen contrast, frozen before generation at 5d6ef40.

Only the official video processor's total pixel budget changes. Model loading,
ten full-screen frames, prompt, timestamps and generation inherit the baseline.
"""
from vlm_batch.qwen import Adapter as BaselineAdapter


class Adapter(BaselineAdapter):
    PROCESSOR_SIZE = {'shortest_edge': 16384, 'longest_edge': 7168000}
