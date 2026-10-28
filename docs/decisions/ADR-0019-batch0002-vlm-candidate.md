# ADR-0019 — BATCH-0002 VLM candidate and bounded execution proposal

- Date: 2026-10-29 KST; official-source retrieval 2026-10-28 UTC.
- Status: **readiness decision only; installation, weights and inference not executed**. Input sufficiency and coordinator-owned code freeze remain prerequisites.
- Scope: one new VLM checkpoint, Qwen3-VL-4B-Instruct, compared with stored Qwen3-VL-2B-Instruct outputs on 10 development windows / 16 view conditions.
- Contract: [BATCH-0002 plan](../experiments/BATCH-0002-model-upgrade-plan.md), [next task](../CODEX_NEXT_TASK.md), [readiness evidence and interface proposal](../experiments/BATCH-0002-vlm-readiness.md).

## Problem and evidence

[EXP-0017](../experiments/EXP-0017-prompt-evidence-results.md) completed its prompt comparison but did not improve the required behavior: q04 full-frame missed the attempt, its ROI output overstated completion, v01 lost its candidate and v03 remained missed. The revised prompt from [ADR-0017](ADR-0017-qwen-temporal-evidence-prompt.md) is not the BATCH-0002 baseline. The original `configs/vlm_batch01_prompt.txt` remains fixed; its SHA-256 is `049ec4a6274443fcf8e3069914e53b2913aefa6f4a13ca049cc4001fa8def7a6`.

The authorized question is whether one larger local VLM improves the same observable actions. A model change cannot recover visual information absent from the input. The separate input audit must establish the available evidence before execution; this ADR makes no visual sufficiency finding.

## Alternatives considered

| Alternative | Evidence and disposition |
| --- | --- |
| Keep the existing 2B BF16 results | Required comparison baseline; all 16 results exist locally. Existing quality is insufficient, and maintaining defaults is not adoption. |
| Qwen3-VL-4B-Instruct, full BF16 | Same native architecture/processor family. Official shard payload alone is about 8.27 GiB, excluding activations, KV cache and allocator/runtime costs; not selected for this 10 GiB target. |
| **Official 4B checkpoint, on-load NF4 language quantization / BF16 compute and vision** | Selected future candidate. Native Transformers support and compatible bitsandbytes binary metadata exist. Memory fit and behavior remain unmeasured. |
| Another VLM or a community prequantized checkpoint | Not authorized as a second checkpoint. Qwen3.5 and other sizes remain untested alternatives; no secondary weights were downloaded. |
| More prompt, ROI, pixel-budget or frame-count tuning | Would change the comparison and repeat the failed prompt search; excluded from this proposal. |

## Decision

Use only the official [Qwen4B repository at revision `ebb281ec70b05090aa6165b016eac8ec08e71b17`](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/tree/ebb281ec70b05090aa6165b016eac8ec08e71b17), conditionally after the coordinator's input gate and code freeze. Its [revision-pinned card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/blob/ebb281ec70b05090aa6165b016eac8ec08e71b17/README.md) declares Apache-2.0; the HF API reports public/ungated access. The model repository has no separate LICENSE file: do not claim that a checkpoint LICENSE was downloaded. The official Qwen code repository separately supplies an [Apache-2.0 license](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/LICENSE); this is corroborating code-license evidence, not a replacement checkpoint license file.

Create a future `.venv-vlm-batch02` from the existing fully pinned `requirements-vlm-lock.txt`, adding **only `bitsandbytes==0.48.1`**. Retain Python 3.10.12, torch 2.5.1+cu124, torchvision 0.20.1+cu124, Transformers 4.57.1 and Accelerate 1.11.0. Preserve `.venv` and `.venv-vlm`. The pinned [Transformers implementation](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/models/qwen3_vl/modeling_qwen3_vl.py) supports Qwen3VL and SDPA; its locally installed source matches the official release bytes. The [bitsandbytes 0.48.1 requirements and CUDA targets](https://github.com/bitsandbytes-foundation/bitsandbytes/blob/0.48.1/docs/source/installation.mdx) cover Python ≥3.9, torch ≥2.3, CUDA 12.4 and sm86. These are dependency/hardware eligibility findings, not a successful installation or inference test.

Freeze NF4, double quantization enabled, BF16 compute, uint8 quantized storage, BF16 nonquantized modules, SDPA and explicit whole-model CUDA0 placement. Exclude `model.visual` and `lm_head` from Linear4bit replacement: vision/mergers and tied embeddings/output remain BF16. The name `llm_int8_skip_modules` also controls the pinned four-bit quantizer; its use is verified in the official source. Record the actual replaced module names/dtypes before generation. Any mismatch stops the job; no automatic switch to quantizing vision, FP16, another backend or CPU/disk offload.

Use 10 observed frames per five-second window, original PTS and fixed B/C geometry, original prompt, seed 0, batch size 1, greedy generation, 384 new tokens and repetition penalty 1.0. The candidate's sampling defaults must not override this contract. This compares **2B BF16 against 4B with NF4 language weights and BF16 vision/compute**; architecture capacity and quantization effects cannot be separated by this experiment.

## Reuse and execution bounds

Reuse the 12 original-prompt q B/C outputs from EXP-0013 and the four `independent-original` v outputs generated in EXP-0017. Historical q processor RGB and expanded prompts are absent; source/PTS/decoded-RGB/recorded-processor metadata parity can be checked, but historical byte identity for the missing artifacts must remain unestablished. Do not silently rerun 2B to erase this limitation. Any fresh baseline would require a separate frozen result and coordinator decision.

Proposed smoke: **q04 C**, which exercises the positive attempt ROI, then **q05 B**, which exercises the false-candidate negative and full-frame token budget. These two conditions belong to the final 16; remaining work is their set complement, 14 conditions. Smoke is a technical gate, not an outcome-selected prompt/model search. Report poor behavior without changing the settings.

Existing `mvp-0001` and `vlm-batch01` registrations deliberately pin 2B and old phases/inputs. They cannot run 4B merely by passing a new path. The coordinator may add one narrow `vlm-batch02` command to the **same canonical queue**, with one condition per job and an immutable batch manifest. Preserve lease verification, process identity, source/input/config hashes, one explicit error retry maximum and free VRAM ≥6144 MiB. No new queue, direct model launcher or modification of the old MVP behavior is proposed. This worker made no queue or MVP code changes.

## Consequences and reversal conditions

- Expected benefit is a more capable representation under nearly identical preprocessing; no SceneGuard quality gain is established.
- NF4 does not make the whole model four-bit. BF16 vision/embeddings, cache, activations, quantization state and loading peaks remain; **10 GiB fit is not promised**, and 6144 MiB free is only a minimum gate.
- q04 completion was not observed; v01/v03 completion is unassessed, and v03 is at the gap beside the gate with ambiguous boundary relation. Preserve these facts separately from candidate and completion claims.
- If input sufficiency fails, compatibility/parity fails, licensing/access changes, or load/smoke OOM occurs, stop that stage and report the blocker. Do not fetch another checkpoint or lower frames/resolution/gate.
- If the bounded comparison produces no useful improvement, retain adoption on hold. No accuracy/F1/FPR, camera-independent generalization, operational readiness or automatic CV+VLM integration follows from these development windows.

The next decision belongs to the coordinator: accept this candidate/interface proposal together with the input audit, implement and freeze the minimal command, then issue a fresh execution dispatch if gates pass. Preparation is complete without waiting for that later dispatch.
