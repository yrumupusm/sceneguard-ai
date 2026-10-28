# BATCH-0002 — VLM official-source and execution readiness

2026-10-29 KST. **Preparation complete; installation/download/inference not started.** [ADR-0019](../decisions/ADR-0019-batch0002-vlm-candidate.md) selects one conditional future candidate. This report implements the documentation-only dispatch under existing Run `run_3d23462a014a`, Task `task_1c28910c950d`, Dispatch `ctx_2061417a366a`.

The worker read AGENTS, README, charter/work plan, BATCH-0002/CODEX_NEXT_TASK, ADR-0017 and EXP-0017 reports, and inspected `mvp`, `vlm_batch` and canonical queue integration. Only the two readiness documents and ignored metadata under `runtime/BATCH-0002/vlm-readiness/` were written. No model weights, package wheels, installation, torch import/CUDA query, GPU call, queue mutation, model generation, media upload, external inference, registration or Git operation was performed. Local raw responses were not copied into the readiness artifacts.

## 1. Official checkpoint evidence

Sources were retrieved on **2026-10-28 UTC / 2026-10-29 KST**. A local source index records individual UTC times, URLs, byte counts and SHA-256 hashes. HF API metadata reports:

| Field | Verified value |
| --- | --- |
| Repository | `Qwen/Qwen3-VL-4B-Instruct` |
| Revision | `ebb281ec70b05090aa6165b016eac8ec08e71b17` |
| Last modified | `2025-10-15T16:15:55.000Z` (repository metadata, not retrieval time) |
| Access | public, `private=false`, `gated=false`; no account/API payment needed for public metadata |
| License | model card SPDX `apache-2.0`; no separate LICENSE file among the 14 repository files; a direct LICENSE request returned 404 |
| Native architecture | `Qwen3VLForConditionalGeneration`, `model_type=qwen3_vl`; no remote model code required |

Evidence: [HF model API with file metadata](https://huggingface.co/api/models/Qwen/Qwen3-VL-4B-Instruct?blobs=true), [revision-pinned card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/blob/ebb281ec70b05090aa6165b016eac8ec08e71b17/README.md), [file tree](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/tree/ebb281ec70b05090aa6165b016eac8ec08e71b17). The API lookup resolved the revision; all subsequent model text/config fetches used that SHA. The official code repository's [separate Apache-2.0 license](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/LICENSE) was captured at code revision `96588727e44c78b25ba03ea03b8e12f7e64fd0da`.

**Expected weight files only — no weight request/download was made:**

| Filename | Expected bytes | API LFS SHA-256 |
| --- | ---: | --- |
| `model-00001-of-00002.safetensors` | 4,967,229,296 | `30a01a0556622645a3cce87b655bbbbbc1f170c196099f1b666c93202c3339a9` |
| `model-00002-of-00002.safetensors` | 3,908,490,048 | `046296a2a387efb43b0c997d5833c789604d168834f6e0d3064bf7bb13d002a6` |

Shard sum is **8,875,719,344 bytes**; the 64,742-byte [index](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/blob/ebb281ec70b05090aa6165b016eac8ec08e71b17/model.safetensors.index.json) reports tensor payload `total_size=8,875,631,616`. The difference is serialization overhead. These are expected upstream sizes/hashes, not verification of downloaded local weights, and not GPU memory estimates.

Future acquisition must allowlist exactly those two shards, `model.safetensors.index.json`, `config.json`, `generation_config.json`, `preprocessor_config.json`, `video_preprocessor_config.json`, `chat_template.json`, `tokenizer_config.json`, `tokenizer.json`, `merges.txt`, `vocab.json`, and optionally README. One official checkpoint with two shards consumes the **one new VLM checkpoint** allowance. Do not obtain a community quantized variant or second model. Download only after the later gate, verify shard sizes and SHA-256 against the table, hash every local model file and freeze the resulting manifest before enqueue.

The [model config](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/blob/ebb281ec70b05090aa6165b016eac8ec08e71b17/config.json) specifies BF16 text weights, 36 text layers, hidden size 2560, 32 attention heads, 8 KV heads, head dimension 128, tied embeddings, maximum positions 262144, and vision depth 24 / hidden size 1024 / patch size 16 / temporal patch size 2 / spatial merge 2. The maximum context is an architectural limit, not the intended allocation. Record actual input tokens plus generation length; do not allocate a 262144-token cache.

The [generation config](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/blob/ebb281ec70b05090aa6165b016eac8ec08e71b17/generation_config.json) defaults to sampling. Override it with the unchanged experiment's greedy settings; record inherited EOS/pad IDs and the effective generation config. The card's source-install recommendation predates the released 4.57.1; use the verified release rather than unpinned Git HEAD.

## 2. Environment and hardware eligibility

Read-only package inventory used `importlib.metadata` without importing torch or contacting CUDA. The host is WSL2 Linux x86-64, Python **3.10.12**, glibc **2.35**. Existing environments:

| Environment | torch / torchvision | Transformers / Accelerate | bitsandbytes |
| --- | --- | --- | --- |
| `.venv` | 2.5.1+cu124 / 0.20.1+cu124 | absent / absent | absent |
| `.venv-vlm` | 2.5.1+cu124 / 0.20.1+cu124 | 4.57.1 / 1.11.0 | absent |
| `.venv-vlm-batch01` | 2.5.1+cu124 / 0.20.1+cu124 | 4.57.1 / 1.11.0 | absent |

The VLM environments also contain numpy 2.2.6, Pillow 12.3.0, PyAV 16.0.1, tokenizers 0.22.2, huggingface-hub 0.36.2 and safetensors 0.8.0. `qwen-vl-utils` is absent and unnecessary for the existing direct preselected-RGB processor path.

Official support checks, retrieved on the date above:

- [Transformers v4.57.1 Qwen3VL source](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/models/qwen3_vl/modeling_qwen3_vl.py) contains the native class and SDPA support. That file and its four-bit quantizer/integration files are byte-identical to installed 4.57.1 sources. [Transformers package metadata](https://pypi.org/pypi/transformers/4.57.1/json) requires Python ≥3.9; its relevant torch/Accelerate/Hub/tokenizer ranges include the proposed pins.
- [bitsandbytes 0.48.1 metadata](https://pypi.org/pypi/bitsandbytes/0.48.1/json) requires Python ≥3.9, torch ≥2.3 and <3, numpy ≥1.17, packaging ≥20.9. [Accelerate 1.11.0 metadata](https://pypi.org/pypi/accelerate/1.11.0/json) requires Python ≥3.10 and torch ≥2.0. These do not require upgrading existing torch.
- The [versioned bitsandbytes build matrix](https://github.com/bitsandbytes-foundation/bitsandbytes/blob/0.48.1/docs/source/installation.mdx) includes CUDA 11.8–12.6 and sm86 in Linux x86-64 wheels, glibc ≥2.24 and NF4 at compute capability ≥6.0. The selected wheel is `bitsandbytes-0.48.1-py3-none-manylinux_2_24_x86_64.whl`, **60,088,899 bytes**, PyPI SHA-256 `3e72cf07ba6d2169e69a61282a6f072fc675efee86049e56a33de099a0363ef2`; only its metadata was fetched.
- [NVIDIA's GPU table](https://developer.nvidia.com/cuda/gpus) identifies RTX 3080 as capability **8.6**. [torch 2.5.1's BF16 check](https://github.com/pytorch/pytorch/blob/v2.5.1/torch/cuda/__init__.py#L132) accepts CUDA ≥11 on capability major ≥8. This is source-based eligibility; current device/driver/BF16 status was not queried. EXP-0017 already records actual 2B BF16 operation on the target RTX 3080, but that historical run does not prove the new binary/model works now.
- [PyTorch's official previous-version instructions](https://pytorch.org/get-started/previous-versions/#v251) provide torch 2.5.1 / torchvision 0.20.1 CUDA 12.4 wheels. No compiler, CUDA toolkit replacement, FlashAttention, vLLM or training stack is needed by the proposed SDPA path.

**Future installation proposal, not executed:**

```bash
python3 -m venv .venv-vlm-batch02
.venv-vlm-batch02/bin/python -m pip install \
  --extra-index-url https://download.pytorch.org/whl/cu124 \
  -r requirements-vlm-lock.txt --only-binary=bitsandbytes bitsandbytes==0.48.1
.venv-vlm-batch02/bin/python -m pip check
```

Use a previously nonexistent target environment; never reuse/overwrite an old environment. Existing lock SHA-256: `139065364e519b2cc24a4225726311a13151d499e129d6d0c5fafa87ba640c9a`. This keeps every transitive dependency pinned and adds one package, rather than installing broad model extras. Save pip resolver/install evidence, `pip freeze --all`, package metadata and exact Python/platform facts locally. No installation or resolver success is claimed here. Stop on resolution/binary mismatch; no unpinned upgrade or source-build fallback.

## 3. Frozen candidate loading proposal

The [official four-bit guide](https://github.com/huggingface/transformers/blob/v4.57.1/docs/source/en/quantization/bitsandbytes.md) documents BF16 computation, NF4 and nested quantization. It describes generic integration, not a certification of this video workload. The [4-bit quantizer](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/quantizers/quantizer_bnb_4bit.py) forwards `llm_int8_skip_modules`; the [replacement implementation](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/integrations/bitsandbytes.py) honors module prefixes in the four-bit path.

This is a **proposal for the later leased runner**, not a direct-run entry point:

```python
quant = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_quant_storage=torch.uint8,
    bnb_4bit_use_double_quant=True,
    llm_int8_skip_modules=["model.visual", "lm_head"],
    llm_int8_enable_fp32_cpu_offload=False,
)
model = Qwen3VLForConditionalGeneration.from_pretrained(
    fixed_verified_local_model_directory,
    local_files_only=True, trust_remote_code=False, use_safetensors=True,
    torch_dtype=torch.bfloat16, attn_implementation="sdpa",
    quantization_config=quant, device_map={"": "cuda:0"},
).eval()
```

Do not append the existing unquantized loader's `.to(...)` to this quantized loader. Do not use `device_map="auto"`, an offload folder, FP32 CPU-offload enablement, or an automatic dtype/backend alternative. Language `Linear` projections become NF4; the full vision branch (including mergers), norms, embeddings and tied output remain nonquantized BF16 where supported by their native modules. Save actual quantized module paths, quantization states/compute dtype, nonquantized dtype summary, `hf_device_map`, and parameter/buffer devices. Reject CPU/disk/meta leftovers or unexpected replacement of vision modules before generation.

**No 10 GiB fit promise:** BF16 vision, large tied embedding, quantization state, temporary loading buffers, video activations, KV cache, CUDA runtime and allocator all consume memory beyond quantized language weights. No new load time, memory peak, latency or output quality is measured. Keep minimum free VRAM **6144 MiB** at enqueue/preload as required; the coordinator may raise it, never lower it. The queue lock does not reserve memory against unrelated processes. Stop on OOM or environment mismatch, preserving the failed attempt and diagnostics.

## 4. Exact input and baseline reuse contract

All rows use `[start,end)` five-second intervals, **10 actual observations**, PTS `start + i/2` for `i=0..9`, unchanged native PTS/time bases and original frame order. q uses the original B full-frame and C fixed ROI; v has full-frame only. No detector gating or label/event timestamp is passed into model text.

| Window | Source / seconds | Views | User reference retained |
| --- | --- | --- | --- |
| q01 | 007 / 0–5 | B,C | no attempt |
| q02 | 007 / 47.5–52.5 | B,C | approach only |
| q03 | 007 / 52.5–57.5 | B,C | no attempt |
| q04 | 007 / 62.5–67.5 | B,C | attempt/progress; completion not observed |
| q05 | 030 / 50–55 | B,C | approach only, no attempt |
| q06 | 030 / 155–160 | B,C | no person/event in this window |
| v01 | 004 / 60–65 | full-frame | attempt/progress; completion unassessed |
| v02 | 004 / 0–5 | full-frame | non-event |
| v03 | 021 / 65–70 | full-frame | attempt/progress beside gate; boundary relation ambiguous; completion unassessed |
| v04 | 021 / 0–5 | full-frame | non-event |

The seven negatives are q01/q02/q03/q05/q06/v02/v04. 031's end-of-video observation must not be assigned to q06/030. These are selected development windows, not independent camera/site tests or completed-crossing positives.

Original prompt SHA-256: `049ec4a6274443fcf8e3069914e53b2913aefa6f4a13ca049cc4001fa8def7a6`. Preserve `Clip ID: <original anonymous window ID>\n` plus stripped original prompt, the official chat template and timestamp formatting. Map q review IDs to the existing anonymous IDs (`w000001`, `w000020`, `w000022`, `w000026`, `w000021`, `w000063`); v uses `w000001`–`w000004` in its separate namespace. Condition identities must include source/view, since these anonymous IDs overlap. Keep q/v labels, source filenames, official captions, past answers and evaluation references outside the inference path.

CPU parity preparation after the gate must reuse native PTS decoder selection and `mvp.method.crop_frames` floor/ceil semantics; decode original sources, not the separately encoded question clips. Verify source hashes and decoded RGB/per-frame hashes against EXP-0015/q and the independent v manifest. Preserve `VideoMetadata` coordinates `(actual_PTS-window_start)*source_fps`, `do_sample_frames=False`, and explicit processor size `shortest_edge=16384, longest_edge=3584000`. Capture expanded prompt, processor RGB, grids, visual/input tokens and effective context length **before** generation. Do not feed already-resized RGB back through a second normal resize.

| View | Original/crop W×H | Official resized W×H | Visual tokens / original-prompt input tokens |
| --- | --- | --- | --- |
| q B | 1920×1080 | 768×448 | 1680 / 1947 |
| q C3 (007) | 576×648; bounds `[1152,0,1728,648]` | 544×608 | 1615 / 1882 |
| q C6 (030) | 903×648; bounds `[537,216,1440,864]` | 704×480 | 1650 / 1917 |
| v full-frame | 1280×720 or 1920×1080 | 768×448 | 1680 / 1947 |

C3 normalized ROI is `[0.6,0,0.9,0.6]`; C6 is `[0.28,0.2,0.75,0.8]`. The official 4B processor configs, chat template and tokenizer configuration exactly match the local 2B files; tokenizer JSON/vocab/merges also match via API Git blob IDs computed from existing local bytes. No large tokenizer file was downloaded during preparation. This strongly supports identical preprocessing under the pinned libraries, but candidate processor execution has not been tested. Reject unexpected size/grid/token/frame/PTS differences; document any official processor difference explicitly before continuing.

**Stored baseline selection:**

- q B: EXP-0013 successful attempt `49cad0749df04995bb55727d57946fec`; q C: `a546b67626e54ef79cdf9bee1c70b3bf`, both preserved under the historical EXP-0012 output namespace. Use the six selected original-prompt results per view, not EXP-0017 revised q outputs and not BATCH-0001's different six clips.
- v: EXP-0017 `independent-original` attempt `b04048ea75cf4658827111d6d3305f5b`, four stored results. Exclude `independent-revised`.
- The read-only inventory found all **16 baseline results**. All 12 old q windows lack saved expanded prompt and processor RGB; all four original v windows have both. q can establish source/PTS/decoded-RGB/recorded-processor metadata parity, but **historical processor RGB and expanded-prompt byte identity remain unestablished**. v can compare saved processor RGB and expanded prompt bytes. Do not claim internal tensor identity without saved tensors.
- The new candidate's q inputs can also be compared with the saved EXP-0017 q processor RGB, because only the question differed there; those revised outputs are never behavior baselines. This does not retroactively prove missing historical q RGB bytes.
- Reuse baseline answers without new 2B generation. If parity cannot be established to the stated level, report a nonexact historical comparison or stop for the coordinator's bounded decision; do not silently add fresh 2B jobs.

## 5. Minimal canonical queue extension proposal

This section is an interface/design proposal only. The coordinator owns implementation, tests, code commit and execution authority. No changes were made to shared queue or MVP code.

Current `orchestration.vlm_command` allows only old adapters and six BATCH-0001 cached clips. `orchestration.mvp_command`, `mvp.runner` and `QwenAnalyzer` pin the 2B model, fixed settings and existing phases; `prompt-regression` always chooses the revised prompt. Consequently **no existing command can correctly execute this 4B matrix**. Repurposing those phases/model directories would break the old contract.

Propose one fixed allowlisted command **`vlm-batch02`**, with an additive registration/runner/CLI, using the existing queue runtime exported as `MVP_QUEUE_RUNTIME`. Reuse the same SQLite database, `gpu.lock`, supervisor, inherited FD lease and process-identity checks. The queue needs explicit dispatch for source hashing, validation, child command creation and result-path status, plus its existing backup/transaction approach to extend the SQL command CHECK without deleting historical rows. Preserve old validators and all `mvp-0001`/`vlm-batch01` behavior. New child verification must demand `command=vlm-batch02`, exact running job/attempt, matching config/input/source hashes, inherited canonical lock ownership and live exact parent **before torch import**.

Bounded proposed configuration:

```json
{
  "batch": "BATCH-0002",
  "candidate": "qwen3-vl-4b-instruct-nf4-bf16",
  "condition_id": "q04_C",
  "manifest_sha256": "<frozen coordinator manifest hash>"
}
```

The manifest fixes the one model/revision/weight hashes, interpreter/environment lock, original prompt hash, source/decoded-frame/crop/processor hashes, all 16 condition identities, generation/quantization settings, 6144 MiB minimum gate and output namespace. The child resolves all paths from that frozen allowlist; no arbitrary user path, shell fragment, model ID, ROI or generation override. The source hash must bind all new files plus reused pure crop/window/parser functions. Reject symlink output redirection; create a new attempt directory exclusively.

**One condition per job** is the proposed smallest reliable way to keep successful smoke outputs and avoid partial-batch regeneration. Use stable job keys incorporating batch/candidate/condition/frozen manifest, and keep run/task/dispatch authority in job metadata. Existing queue enqueue rejects a repeated key with changed dispatch/config/source, so a fresh dispatch must inspect and reuse the existing result or explicitly retry its existing failed job; changing the key to bypass that check is forbidden.

Proposed future frontend grammar (not installed/implemented):

```text
python -m vlm_batch.batch02_cli --runtime "$MVP_QUEUE_RUNTIME" enqueue \
  --condition q04_C --job-key <stable frozen condition key> \
  --run-id run_3d23462a014a --task-id <new live task> \
  --dispatch-id <new live dispatch> --owner <assigned executor>
python -m vlm_batch.batch02_cli --runtime "$MVP_QUEUE_RUNTIME" run-once
```

The CLI should derive the fixed manifest/config itself. Those placeholders must be replaced by coordinator-frozen values in the later dispatch; they are not executable readiness commands. Each job has a frozen 1800-second maximum, batch size 1 and no automatic requeue. `run-once` supervises at most one registered condition. There is no direct child/model execution path.

Execution sequence after the later authorization:

1. Confirm input sufficiency and committed, reviewed source/config hashes, verified local checkpoint and isolated environment. Bind the new live Task/Dispatch to the same Run and canonical queue; this preparation dispatch must not be reused for execution.
2. Run **q04 C**, then **q05 B**, each a normal one-condition queue job with 10 frames, original prompt and production-frozen settings. q04 C tests the known positive ROI; q05 B tests the false-candidate negative and full-frame token budget. Smoke checks load/devices/parity/generation/parsing/artifact completeness; it does not select a new prompt or reject an unfavorable but valid behavior result.
3. After both technical smoke jobs pass, execute exactly `all_16_conditions - {q04_C,q05_B}`: **14 remaining conditions**. Persist the two smoke results as the final outputs for their identities. Do not rerun all ten windows or enqueue an overlapping full batch. Every condition retains its own resource/parity checks; two smoke cases cannot prove every later condition fits.
4. On known execution failure, preserve diagnostics and stop for assessment. At most one explicit retry of that failed job is permitted, with unchanged settings, after its exact process is proven exited and failed output is understood. Never retry a successful condition or an unknown/lost process. If generation token IDs survived a decode/write failure, recover decoding/persistence on CPU instead of generating again. Complete successes must not be regenerated.
5. Save per-condition input/prompt/processor/token-ID/raw-answer hashes, strict/common parse outcome, candidate/indeterminate/completion claims, loading/preparation/generation/queue times, output tokens, peak allocated/reserved bytes and device memory samples. Separate load cost from generation; no runtime cost is measured in preparation. Keep all raw artifacts local and publish only permitted summaries.

## 6. Required tests and remaining gates

These are proposed acceptance tests for the coordinator's code, **not tests run against an implementation that does not exist**:

- CPU/fake queue tests reject wrong canonical runtime/lock/parent/attempt/command, stale source or input/config hashes, forbidden model/condition and unfrozen paths before any model import. Add migration preservation coverage and retain existing queue/MVP compatibility checks.
- Manifest tests enforce ten distinct windows, exactly 12 q B/C + 4 v conditions, two smoke IDs and disjoint 14-condition remainder; reject duplicate window/view IDs and overlapping rerun jobs, including under a fresh dispatch.
- Metadata parity tests compare original PTS/time bases/order, decoded/crop hashes, ten observed/processor frames, no extra sampling/padding, fixed ROI/size/grid/token budget and original prompt. Test q's missing historical artifact status explicitly; never let absent files pass as equality. v can demand saved byte equality.
- Fake loader tests require NF4/BF16/double-quant/storage/vision-skip flags, explicit CUDA0 map, no CPU/disk offload and a ≥6144 MiB gate. Stop before generation on dtype/device mismatch; never test with real GPU during readiness.
- Result/retry tests preserve successful smoke/results, recover saved tokens without regeneration and reject success/unknown retries. Existing parser semantics and label-free inference path remain unchanged. Functional parsing is separate from behavior correctness.

| Gate | Readiness status |
| --- | --- |
| Official checkpoint/revision/access/license declaration and expected weight hashes | complete, text/API only |
| Existing environments and version-level compatibility | complete, metadata/source only |
| Candidate chosen within one-VLM allowance | conditional proposal complete |
| Input sufficiency / meaningful visible evidence | **pending separate input audit and coordinator confirmation** |
| Frozen source/manifest and minimal command implementation/tests | **pending coordinator-owned work** |
| Isolated installation / complete verified checkpoint | not performed |
| Current GPU resource gate / actual bitsandbytes BF16 compatibility / load/smoke | not performed |
| 16-condition behavior comparison / independent review / registration and delivery | not performed |

q04/v01/v03 retention and the seven negative windows must be reported alongside completion overclaims, evidence plausibility, indeterminate/parse failures and cost. Keep q04 completion not observed, v01/v03 completion unassessed and v03's gap ambiguity. Candidate counts are diagnostic counts; accuracy/precision/recall/F1/FPR/hourly false alarms remain null. A reduction caused by losing positive candidates is not improvement. The comparison changes model capacity and language-weight quantization together and does not establish independent generalization or authorize CV-gated suppression of VLM windows.

## 7. Local evidence index and closure

Ignored evidence root: `runtime/BATCH-0002/vlm-readiness/`. It contains `official-source-index.json` with dated fetches/hashes, `hf-model-api.json`, revision-pinned small model metadata, official release source/docs/license captures, package API metadata, `existing-environments.json`, `processor-tokenizer-parity.json`, `baseline-reuse-metadata.json`, `source-snapshot-before.json` and `candidate-proposal.json`. These contain metadata/proposals, not new inference or copied raw answers/media. A final validation record binds local evidence hashes and checks preservation of the inspected protected source/config files.

Readiness-only validation passed **12 metadata/document checks**: 24 official text/API captures (817,968 bytes), their stored hashes, two expected shard records, 16 baseline results, the disjoint 2+14 execution plan, stated missing/present historical artifacts, processor/tokenizer file parity and local Markdown links. All **51 inspected protected source/config files** retained their snapshot hashes. `validation.json` records those checks and document hashes; `fetch-status.json` separately records the checkpoint LICENSE HTTP 404. No model/GPU test or software integration test was run for this documentation change.

Preparation ends here. The coordinator can use this report with the separate input audit to accept, amend within the batch's frozen bounds, or stop the VLM stage, and issue a new execution dispatch only after the input gate and code freeze. No waiting for execution or automatic follow-on work is required from this worker.
