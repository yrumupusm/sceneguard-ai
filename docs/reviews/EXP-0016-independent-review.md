# EXP-0016 independent review — blocked before inference

Date: 2026-10-28. Repository baseline: `fedb278d42f12f13a47b51bcd8ec6dbc387fd8f7`, with the working-tree implementation bound below. Orca Run: `run_3d23462a014a`; task: `task_2ef3108a1af8`; dispatch: `ctx_871a248197e5`.

**Verdict: PASS for recording the corrected, exact package as BLOCKED-before-inference. This is not an outcome or performance review, permission to bypass the resource gate, or an adoption decision.** One report/metrics consistency defect was reported before final binding and corrected by the coordinator. No unresolved blocking correctness issue was found for this limited preflight package.

**Behavioral outputs, change effect, model load time, generation time, peak VRAM and adoption cannot be reviewed because no inference occurred.** Implementation and CPU test success do not establish behavioral improvement, completed comparison, generalization or operational suitability. Registration, browser verification and publication remain separate coordinator-owned delivery steps.

## Artifact binding and resolved finding

The initially dispatched report and metrics matched their supplied hashes. The report still said 92 MVP tests and described the independent implementation as ongoing, while metrics claimed 107 tests. This inconsistency was escalated before final binding. The coordinator corrected the report to 107 tests (including 12 prompt and 15 independent tests), updated implementation status, added the two-source grouping limitation, and refreshed every metric source hash. The final pair below was supplied as frozen and independently rehashed; every metric now points to the final report hash.

| Artifact/version | SHA-256 |
| --- | --- |
| Initial report, superseded | `2da86c3e8349cac04fbf4ca365b3144767241cb375c820fb671ad4dc46b0bb35` |
| Initial metrics, superseded | `af7cfe4ebf368bf3949c6a145b6f9736f35c9335a700cc2a47438019c70912dd` |
| Final `docs/experiments/EXP-0016-prompt-evidence-rubric.md` | `d75a81d86bd47471e99487ef6e182996ebae9cfd75dbd93827060dd015fc8794` |
| Final `records/EXP-0016/metrics.json` | `40cc28dd4eda164bde10d150804bd588214b373bad94d39016b01360c3c3d14f` |

The verdict applies to the final pair, not the superseded pair. Subsequent artifact changes require renewed binding.

## Design, labels and preservation

The experimental change is the shared Qwen prompt's temporal body-motion evidence requirement. The JSON response schema, parser/postprocessor, model, generation settings, processor size, five-second windows, 2 fps sampling and existing q-window views remain fixed. The prompt distinguishes approach/waiting/contact from visible attempt/progress and limits completion to the same person's observed movement to the opposite side within the window. It contains no q/v labels, source filenames, official annotation, previous responses or window-specific answer rules. The hypothesis that prompt wording caused historical errors remains a hypothesis.

The six manifest entries match the preserved EXP-0015 user-label source/window/interval mappings exactly:

| Review | Source/window | Seconds | User scope | Historical B / C |
| --- | --- | --- | --- | --- |
| q01 | E01_007 / w000001 | 0–5 | No attempt/progress | absent / absent |
| q02 | E01_007 / w000020 | 47.5–52.5 | Approach only; no attempt/progress | candidate / absent |
| q03 | E01_007 / w000022 | 52.5–57.5 | No attempt/progress | absent / candidate |
| q04 | E01_007 / w000026 | 62.5–67.5 | Attempt/progress; clip ends before completion | absent / candidate |
| q05 | E01_030 / w000021 | 50–55 | One of three people approaches; no attempt/progress | candidate / candidate |
| q06 | E01_030 / w000063 | 155–160 | No person/event | absent / absent |

These are six scheduled five-second development windows: five no-attempt windows and one diagnostic attempt-positive, not 12 independent samples from the B/C rows. Primary reviewed positives remain zero. q04 is not a completed-crossing label; q06 does not inherit a source-031 observation or imply whole-video normality. The separate partial-positive and unknown historical cases are not relabeled or counted as these six. The historical B/C entries are inherited public summaries, not fresh raw-response adjudications. Reduced candidates alone, particularly replacing everything with indeterminate or losing q04, would not establish improvement.

The evaluation-only independent JSON faithfully records v01/v03 as `attempt_progress` with completion `not_assessed`; v02/v04 are `non_event`. v03 retains `gap beside gate, not through gate`, ambiguous boundary relation and ambiguous exact location. These references cover only E01_004 60–65/0–5 seconds and E01_021 65–70/0–5 seconds. There are four purposively selected windows, two source-video groups and two attempt/two non-event labels; no camera/site independence, representative test population or blinded generalization result is established.

Historical EXP-0013 and EXP-0015 reports/metrics still match their existing review-binding hashes. Sixteen inspected public historical/config/code files were byte-identical to Git HEAD, including EXP-0015 records and labels, the old prompt, original source/camera/settings configs, decoder, event logic, pipeline and Qwen adapter. Inference code has no official-label rewrite path. Official annotation files and historical raw outputs were deliberately not opened or independently rehashed; preservation of those prohibited artifacts is not newly authenticated by this review.

## Input separation and exactness

`mvp.independent` never loads the evaluation JSON. That JSON is excluded from `input_contract`, queue source-file hashing and prompt construction. Production inference receives anonymous `w...` IDs, frames and measured timing/ROI processing metadata; neither source filename nor evaluation prose is placed in chat. Explicit guarded-file and polluted-metadata tests passed for both independent prompts and the q prompt. Label changes therefore do not change inference inputs or their hashes through this evaluation file.

Independent comparison uses only `full_frame`, enforced by command validation and execution context. The `[0,0,1,1]` rectangle is full-frame processing, not a calibrated second ROI condition. Original versus revised prompt uses the same four input windows; there is no duplicated full-frame result presented as independent ROI evidence.

The independent manifest is hard-pinned by SHA-256 and binds both prompt hashes, two original source hashes, decoder/library versions, native PTS/time bases, decoded and relative indices, dimensions and 40 RGB frame hashes. Source hashes are rechecked before decoding; exact timing dictionaries and frame hashes are checked before each analyzer call. Synthetic drift tests reject altered frames, PTS, indices, dimensions, counts, decoder versions and prompt/manifest bytes. Reviewed-clip hashes in the manifest remain provenance; execution reads originals, and this review did not authenticate media or clip extraction.

For q01–q06, the code pins original source hashes, six source/window/time mappings, C3/C6 ROIs and sampling settings; it requires ten frames and the expected PTS sequence, and records native timing and RGB hashes. It does not itself compare newly decoded q RGB hashes against historical EXP-0013 frame hashes before generation. Thus exact historical-versus-new frame/processor identity still needs confirmation from permitted execution evidence before any later prompt-only outcome attribution. This is an explicit future comparison requirement, not evidence that a second axis changed or a blocker to honestly recording the current preflight state.

## Model, queue and execution gates

The report's Qwen3-VL-2B-Instruct revision `89644892e4d85e24eaac8bacfd4f463576704203` and weight SHA-256 `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0` agree with preserved EXP-0008 documentation and the code's pin. All local model files are hash-bound at enqueue/validation; actual model assets were not opened by this review. Settings remain batch 1, seed 0, BF16, SDPA/CUDA0, greedy generation, 384 maximum new tokens, repetition penalty 1.0 and processor bounds 16384/3584000. No new download or external inference path was added.

The new phases use the existing `mvp-0001` command, canonical shared queue and required Run. Queue registration and child verification reject a different Run; the child checks inherited lock identity/ownership, live exact supervisor, attempt/config identity and source/input/config hashes before model import. New attempt directories use `exist_ok=False`; EXP-0016 paths reject symlink redirection and do not overwrite historical outputs. Queue serialization and explicit retry limits remain in place.

`run()` checks the immutable 6144 MiB minimum-free-memory gate before importing torch or loading the model. Direct model construction also requires the canonical live lease. Tests demonstrate missing/fake leases and resource failures do not reach model loading. The code supports enqueueing a registered job before its execution-time resource check; the recorded earlier preflight prevented enqueueing in this particular run. Those are separate facts.

The report records **1773 MiB free versus 6144 MiB required**, with 8281 MiB used and 99% utilization at 14:29 UTC. This historical snapshot was not replaced by a new GPU measurement. A read-only aggregate query of the canonical queue independently returned **zero EXP-0016 jobs and zero attempts** across all three new phases. Together with the execution guards and report, this supports the recorded zero authorized inferences/model loads; it is not a forensic proof about unrelated processes.

## Tests, metrics and limits

Independently executed with `PYTHONDONTWRITEBYTECODE=1`:

```bash
.venv-vlm/bin/python -m unittest tests_mvp.test_prompt_regression tests_mvp.test_independent_comparison tests_mvp.test_command -v
.venv-vlm/bin/python -m unittest tests_orca.test_queue -v
```

Results: **39 focused MVP tests passed** (12 prompt, 15 independent, 12 command), and **14 queue tests passed**, without skips or failures. These runs used temporary synthetic fixtures/mock models, not real source media, cached processor assets or weights. The full suite contains 107 test methods, consistent with the corrected report. Its reported 107-test success is implementation evidence, not a full independent rerun: some existing tests load local processor assets, outside this review's allowed inspection scope. The earlier system-Python run skipped three decoder tests because PyAV was missing; the focused reviewer run used the project environment and exercised them.

The report discloses one initial queue attempt-order assertion failure followed by a passing isolated rerun and passing full rerun. This reviewer also observed a passing 14-test queue run. Those passes do not prove the reported flaky ordering issue's root cause or permanent resolution, and the initial failure must remain disclosed.

The pure `orchestration.complete.metrics` schema/publication validator passed on the actual final metrics. Every metric source hash matches the final report. Behavior comparison and generation latency/peak VRAM values and sample sizes are null; accuracy, precision, recall, F1, FPR and hourly false alarms are also null. The numeric 107/14 values measure software tests, four measures checked windows, and 1773 is a one-snapshot free-memory observation. None measures model performance, generation cost or inference peak memory. Zero attempts/retries means no attempts occurred, not a measured zero-failure rate. Load time is explicitly unmeasured in the report rather than assigned zero.

No new behavioral outputs exist to assess q regressions, independent action/completion, explanation factuality, change effect, load/generation time, peak VRAM or adoption. Adoption remains on hold. The blocked package may be registered with this limitation; a future authorized run must satisfy the unchanged resource gate and undergo a separate output/comparison review.

Only this review file was written. No implementation, labels, metrics, assignments, catalog or website was changed by the reviewer. No raw media, model cache, weights, raw model responses or runtime secrets were inspected; queue access exposed aggregate counts only. No inference, enqueue, GPU probe, commit, push or external-channel message was performed by the reviewer.

## Reviewed implementation bytes

| File | SHA-256 |
| --- | --- |
| `mvp/independent.py` | `96b6e3fad94ccf5dba580d51d852256a4ea9aa24027cac73480e8de812186861` |
| `mvp/method.py` | `92c0a2e3b97747f2582b1f82706639a04ef5753509ae63609a8e1f244d627ed9` |
| `mvp/runner.py` | `3f9de4e684fdd18c0f8414d408fca6a8234371c09979fec8cecc620cefb8a17a` |
| `mvp/cli.py` | `ecbd945328bc7f91895ca596e255d0ada660f7932b4f80aec097eb1842869a71` |
| `orchestration/mvp_command.py` | `f7f1a76d36a1d26e2766f0588dbba19c234b1257d8061cadab135985647ff3d6` |
| `orchestration/queue.py` | `72256b15695786f6c0d3b38a56a8e0ffd448bb4f836ad856fc887fad8aa52f38` |
| `configs/mvp_exp0016_manifest.json` | `e1a00ce51d35e6dea61ade0869db3379cc447a30f6988e5296c7cb0cf6c688b6` |
| `configs/mvp_exp0016_independent_manifest.json` | `68b07ef836422cd9043e4fcb88b40b0f70e256d0024a2bd57ce29a12e08aa765` |
| `configs/mvp_exp0016_independent_evaluation.json` | `e7e59c8ae807ffcea5a606ad4d6618360be43dc62afa83e4abaec88ddd363a0d` |
| `configs/mvp_exp0016_prompt.txt` | `ffc12cd2f9af707e9654acd3eed0449009576e81803206573b17445cde8cf92b` |
| `tests_mvp/test_independent_comparison.py` | `a17fe34eddd439c180cc88db24dc91fa05fd5e7d21ef64380186781cd645eb64` |
| `tests_mvp/test_prompt_regression.py` | `f7ceaa6caeb0aad7fa6d6d9e4f1e37985693f9f320553b6fd1cd64af1ff061d8` |
| `tests_mvp/test_command.py` | `fbadeb05f15e401c738be446ca66a6fb66de1b97ee91dbbf843625cb1efce69c` |
| `tests_mvp/test_pipeline.py` | `efcffb096b4cbafe9d5729f4ca8c96a1ef5f4a6d6508f15f1a628e46bd3ac203` |
