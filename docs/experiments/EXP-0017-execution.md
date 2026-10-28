# EXP-0017 — Frozen prompt comparison execution

Date: 2026-10-28 UTC / 2026-10-29 KST. This is the user-authorized actual continuation of the immutable, GPU-blocked [EXP-0016 specification](EXP-0016-prompt-evidence-rubric.md), following [ADR-0017](../decisions/ADR-0017-qwen-temporal-evidence-prompt.md). This report records execution metadata only; behavior comparison, independent review, adoption, registration and delivery remain coordinator work.

Run `run_3d23462a014a`, execution Task `task_032ba4cbc816`, Dispatch `ctx_65e6cdf6b6f4`. The coordinator confirmed the registered slot3 assignment through the required blocking orchestration ask before the first enqueue. Execution source HEAD is `64ab297775d712a18f5149c0fd8f3d8d19dec848`; all 23 bound implementation/configuration files match frozen implementation commit `5d4a8af0f83975f430922fcda03c0aef5a34734a` byte for byte.

The existing `.venv-vlm`, pinned Qwen3-VL-2B-Instruct and canonical queue were reused. The implementation preserves its `outputs/mvp0001/EXP-0016` output contract and creates unique attempt directories; these new attempts belong to actual continuation EXP-0017. No inference source, configuration, input, model, prompt, generation setting or historical result was changed. Raw responses, generated token IDs, processor RGB arrays, memory samples, queue receipts, exact commands and the run index remain in ignored local storage.

All four sequential jobs and all 20 generations completed successfully: **6/6/4/4 records, four attempts, zero execution failures and zero retries**. Each job used `mvp.cli enqueue` followed by `mvp.cli run-once`; no direct runner invocation was made. A fresh read-only queue check found no pending/running/unknown work before each enqueue and only the intended queued job before each run-once. The initial queue contained 14 historical jobs/14 attempts; the final queue contains 18/18 with no pending/running/unknown work.

## Queue execution evidence

| # / frozen phase / view | Job ID | Attempt ID | Queue / runner / child exit |
| --- | --- | --- | --- |
| 1 / prompt-regression / full_frame | 596d4cdda8ca459ca3b4d482e4b00d1c | 9555b3da23aa4c10bfd9a8ed0d0dd237 | succeeded / succeeded / 0 |
| 2 / prompt-regression / fixed_roi | 8dd7e861561b43769a50a58ee6c247b4 | b8de7de3d3e84ee3a2e7d1c4d2af7e63 | succeeded / succeeded / 0 |
| 3 / independent-original / full_frame | 0cc1dba95f044984b923a2ba78170c73 | b04048ea75cf4658827111d6d3305f5b | succeeded / succeeded / 0 |
| 4 / independent-revised / full_frame | 6faf6a018e764d518e371fcf2cd4dca1 | 8d06e5084efd4310a19ff7b6a7c1e947 | succeeded / succeeded / 0 |

| # | Attempt start UTC | Attempt finish UTC | Queue attempt wall s | Enqueue / run-once / runner gate free MiB |
| --- | --- | --- | --- | --- |
| 1 | 2026-10-28 15:06:07.967 | 2026-10-28 15:07:03.700 | 55.734 | 8018 / 8030 / 8025 |
| 2 | 2026-10-28 15:07:51.115 | 2026-10-28 15:08:42.123 | 51.007 | 8024 / 8028 / 8015 |
| 3 | 2026-10-28 15:08:56.269 | 2026-10-28 15:09:32.472 | 36.203 | 8007 / 8001 / 8019 |
| 4 | 2026-10-28 15:09:46.427 | 2026-10-28 15:10:23.440 | 37.014 | 8024 / 8020 / 8026 |

All fresh gates exceeded the unchanged 6144 MiB minimum. Attempt intervals do not overlap. Runner source verifies the inherited canonical lock, live exact parent, current attempt, Run/Task/Dispatch and source/input/config hashes before model construction, then verifies the environment lease again in the analyzer. The final live attempt was additionally observed with both exact supervisor/child identities live and file descriptors referencing canonical lock inode 510365; this local observation corroborates the frozen lease checks.

## Measured execution metadata

| # | Records | Real / processor frames | Input / visual tokens | New output tokens | Strict / postprocessed parse successes | Token limit hits |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 6 | 60 / 60 | 12438 / 10080 | 655 | 3 / 6 | 0 |
| 2 | 6 | 60 / 60 | 12118 / 9760 | 647 | 6 / 6 | 0 |
| 3 | 4 | 40 / 40 | 7788 / 6720 | 389 | 2 / 4 | 0 |
| 4 | 4 | 40 / 40 | 8292 / 6720 | 488 | 2 / 4 | 0 |

| # | Load s | Prepare sum s | Generation sum s | Peak allocated / reserved MiB | Sampled device used peak / free minimum MiB | Memory samples / errors |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3.458 | 0.729 | 23.572 | 4469.48 / 4618.00 | 6932 / 3122 | 98 / 0 |
| 2 | 2.309 | 0.335 | 22.084 | 4462.10 / 4672.00 | 6982 / 3072 | 91 / 0 |
| 3 | 2.388 | 0.409 | 14.654 | 4448.26 / 4620.00 | 6930 / 3124 | 60 / 0 |
| 4 | 2.300 | 0.386 | 16.198 | 4469.48 / 4618.00 | 6932 / 3122 | 62 / 0 |

Total: 20 generated records, 200 real frame observations, 2179 new output tokens, 76.508 seconds of measured generation, and 179.958 seconds summed queue-attempt wall time. Each record used ten real/processor frames, no extra sampling and no temporal padding. No cached response was reused. The parser counts distinguish strict schema acceptance from success after the existing unchanged postprocessor; they do not establish behavior correctness.

PyTorch peak allocation/reservation are per-record CUDA allocator measurements. The separately sampled device totals include other GPU users and are sampled at approximately 0.5-second intervals; they are not isolated model memory. Queue wall time includes binding validation, load, decoding through EOF, generation and artifact writes. Summed preparation/generation time is not end-to-end throughput or real-time detection latency.

## Frozen inputs and environment verification

The six q-window input JSON records have identical source SHA, decoded indices, native PTS, time bases and raw RGB hashes across full-frame/fixed-ROI jobs, with only the frozen ROI differing. All four independent original/revised pairs have identical timing, frame SHA arrays, crop metadata and byte-identical saved processor RGB arrays; prompt SHA/input token counts are allowed to differ. Both independent conditions match the frozen manifest native PTS/frame hashes. Expanded prompts in all 20 records contain the exact phase-selected frozen prompt and anonymous window ID.

Model: Qwen3-VL-2B-Instruct, pinned revision `89644892e4d85e24eaac8bacfd4f463576704203`, model.safetensors SHA-256 `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`. Local weight bytes and cached revision metadata were checked. All parameters were on CUDA0 on NVIDIA GeForce RTX 3080, using BF16/SDPA, batch 1, seed 0, greedy generation, max_new_tokens 384, repetition_penalty 1.0, unchanged processor size 16384/3584000. Offline/local-files-only loading was retained.

All four complete package inventories match. Recorded versions: `torch 2.5.1+cu124`, `torchvision 0.20.1+cu124`, `transformers 4.57.1`, `tokenizers 0.22.2`, `accelerate 1.11.0`, `safetensors 0.8.0`, `av 16.0.1`, `numpy 2.2.6`, `pillow 12.3.0`, `huggingface_hub 0.36.2`; CUDA 12.4. The PyAV/native FFmpeg library versions match the frozen independent manifest.

| Prompt | SHA-256 |
| --- | --- |
| independent-original | 049ec4a6274443fcf8e3069914e53b2913aefa6f4a13ca049cc4001fa8def7a6 |
| independent-revised | ffc12cd2f9af707e9654acd3eed0449009576e81803206573b17445cde8cf92b |

| # | Bound source hash | Input hash | Config hash |
| --- | --- | --- | --- |
| 1 | ba64888c0fd53e3e8abb6795ca265f1f4ef0d65a10c68986374ae50ad296ff6e | bf4dc671d2e0cea8633271844ecb7c45be8430cd0076764791dc0ea70088ded9 | 62a0a8e96053869e3371d50f2b9f7969c8585575401e19d2f2d2ecb7a13dee6d |
| 2 | ba64888c0fd53e3e8abb6795ca265f1f4ef0d65a10c68986374ae50ad296ff6e | bf4dc671d2e0cea8633271844ecb7c45be8430cd0076764791dc0ea70088ded9 | 9da9881bcb068fc92d1d731d36f9953d2ac084548a72582b0c6621ce469326fb |
| 3 | 269f7d5983a4e30405e45c7e7085fb093c1cfbff2857b8d4576f7c5b42417b56 | c20cdfd80e77775dacc2dd5f89d5155c2ba2e1edff64698517d58c9096003228 | a5e4727abca4c4f7bb453ccdad6e6ea58588d71d06d71343b8683ffa512c8df0 |
| 4 | 269f7d5983a4e30405e45c7e7085fb093c1cfbff2857b8d4576f7c5b42417b56 | c20cdfd80e77775dacc2dd5f89d5155c2ba2e1edff64698517d58c9096003228 | e22e79fa220af136744c3d14c037691fdc4c59a7ec3df79325efe0b24efcea66 |

All manifest registrations point to the canonical frozen runner/interpreter and their unique expected output directories. Current code-file hashes, queue hashes and summary bindings agree. Historical EXP-0016 blocking documentation and existing results were preserved. The local verification receipt also binds each new summary, queue manifest, input/result JSON, expanded prompt and processor RGB file by SHA-256.

## Actual commands

The following show the commands in execution order with local machine paths replaced by repository-relative paths and the existing canonical `MVP_QUEUE_RUNTIME` value. Exact commands are preserved in the ignored run index. Each run-once settled before the next enqueue. This transcript is not an instruction to rerun settled tasks or reuse their lifecycle IDs.

```bash
./.venv-vlm/bin/python -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" enqueue --phase prompt-regression --view full_frame --job-key EXP-0017-01-prompt-regression-full_frame-ctx_65e6cdf6b6f4 --run-id run_3d23462a014a --task-id task_032ba4cbc816 --dispatch-id ctx_65e6cdf6b6f4 --owner EXP-0017-sole-gpu-executor
./.venv-vlm/bin/python -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" run-once
./.venv-vlm/bin/python -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" enqueue --phase prompt-regression --view fixed_roi --job-key EXP-0017-02-prompt-regression-fixed_roi-ctx_65e6cdf6b6f4 --run-id run_3d23462a014a --task-id task_032ba4cbc816 --dispatch-id ctx_65e6cdf6b6f4 --owner EXP-0017-sole-gpu-executor
./.venv-vlm/bin/python -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" run-once
./.venv-vlm/bin/python -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" enqueue --phase independent-original --view full_frame --job-key EXP-0017-03-independent-original-full_frame-ctx_65e6cdf6b6f4 --run-id run_3d23462a014a --task-id task_032ba4cbc816 --dispatch-id ctx_65e6cdf6b6f4 --owner EXP-0017-sole-gpu-executor
./.venv-vlm/bin/python -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" run-once
./.venv-vlm/bin/python -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" enqueue --phase independent-revised --view full_frame --job-key EXP-0017-04-independent-revised-full_frame-ctx_65e6cdf6b6f4 --run-id run_3d23462a014a --task-id task_032ba4cbc816 --dispatch-id ctx_65e6cdf6b6f4 --owner EXP-0017-sole-gpu-executor
./.venv-vlm/bin/python -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" run-once
```

No test suite was rerun because inference code/configuration did not change. Metadata verification completed against saved artifacts and canonical queue receipts; the final queue status and `git diff --check` were checked separately. No commit, push, result registration, behavior conclusion or adoption decision is included in this worker delivery. Coordinator behavior comparison and independent review remain outstanding.
