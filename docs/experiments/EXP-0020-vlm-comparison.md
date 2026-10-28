# EXP-0020 — Qwen4B comparison completed; adoption held

2026-10-29 KST. **The fixed 16-condition comparison completed, but the 4B configuration is not adopted.** It retains q04_C's attempt candidate and removes several old negative candidates, while six outputs fail the unchanged response schema, q04_B remains noncandidate, v01 denies the reviewed boundary cue, and unsupported completion claims remain. Candidate counts do not establish correct grounding or operational accuracy.

The [reproducible comparison](../../records/EXP-0020/comparison.json) and [registration metrics](../../records/EXP-0020/metrics.json) compare **16 view conditions across 10 unique five-second windows**, four sources and seven unique negative windows. q has six windows × B/C; v has four full-frame windows. These selected development/diagnostic conditions are not an independent camera/site test. Accuracy, precision, recall, F1 and FPR remain null.

## Execution and frozen configuration

One official Qwen3-VL-4B-Instruct checkpoint at revision `ebb281ec70b05090aa6165b016eac8ec08e71b17` was loaded with NF4 language weights, double quantization, uint8 storage, BF16 compute/nonquantized modules and explicit whole-model CUDA0 placement. Vision/mergers and tied embeddings/output remain BF16; all 16 loads verified **252 language Linear4bit modules**, all parameter/buffer/quantization-state devices on CUDA0 and no CPU/disk/meta offload. This compares old **2B BF16** with **4B NF4 language/BF16 vision and compute**; capacity and quantization effects cannot be separated. [ADR-0019](../decisions/ADR-0019-batch0002-vlm-candidate.md) and the [readiness report](BATCH-0002-vlm-readiness.md) retain the official-source/license evidence; the card declares Apache-2.0, and no separate checkpoint LICENSE file was downloaded.

The new isolated `.venv-vlm-batch02` retains Python 3.10.12, torch 2.5.1+cu124, Transformers 4.57.1 and Accelerate 1.11.0, adding only bitsandbytes 0.48.1 to the old pinned requirements. Pip check/freeze and **19,041 installed-file hashes** are bound by the environment receipt. Old environments, MVP defaults, labels, results and reports are preserved.

| Verified official shard | Bytes | SHA-256 |
| --- | ---: | --- |
| model-00001-of-00002.safetensors | 4,967,229,296 | `30a01a0556622645a3cce87b655bbbbbc1f170c196099f1b666c93202c3339a9` |
| model-00002-of-00002.safetensors | 3,908,490,048 | `046296a2a387efb43b0c997d5833c789604d168834f6e0d3064bf7bb13d002a6` |

Batch 1, SDPA, seed 0, greedy generation, max-new-tokens 384 and repetition penalty 1.0 remained fixed. Model-card sampling defaults were explicitly neutralized and saved alongside effective settings, preserving official BOS/EOS/pad IDs. All outputs stayed below the token limit. No 2B model was rerun; its 12 q answers are EXP-0013 outputs under the historical EXP-0012 storage namespace, and its four v answers are EXP-0017 **independent-original** only. Revised EXP-0017 answers are excluded.

Smoke q04_C then q05_B each generated once and are members of the final 16. The disjoint remaining conditions followed serially through the existing canonical queue. No prompt, ROI, frames, dtype, quantization or resolution tuning occurred, and no extra model/condition/PoC was run.

## Response schema and behavior are separate

| Response measure | Stored 2B | New 4B |
| --- | ---: | ---: |
| Strict response schema valid | 11 | 10 |
| Valid after existing common outer-fence handling | 16 | 10 |
| Unscorable schema failures | 0 | 6 |
| Candidate tags in valid responses | 7 | 1 |
| Indeterminate action tags in valid responses | 0 | 0 |
| Other valid responses | 9 | 9 |

All 16 new responses have valid JSON-object syntax. **q01_B/C, q06_B/C, v01 and v03 have empty action lists**, rejected by the unchanged nonempty action schema; fence removal cannot repair them. Their candidate/indeterminate/completion judgments remain null, not correct negatives. Five old strict-schema rejections are recovered by existing outer-fence handling; all 16 old responses are common-schema valid. The same frozen parser/rubric is used for both models.

| Negative group | Planned negative view conditions | 2B false candidates | 4B false candidates among valid responses | 4B valid responses | 4B unscorable views |
| --- | ---: | ---: | ---: | ---: | ---: |
| q_B | 5 | 2 | 0 | 3 | 2 |
| q_C | 5 | 2 | 0 | 3 | 2 |
| v_negative | 2 | 1 | 0 | 2 | 0 |

The six valid q approach/no-attempt views q02/q03/q05 B/C all lack candidates. **Four other q negative views remain unresolved**, so this is not ten successful negative decisions. v02/v04 also lack candidates. Valid new q03_B and q05_B still claim observed completion without candidate tags or sufficient crossing evidence; no candidate alone is not correct grounding. Raw q01_B also claims completion inside a schema-invalid response and is not promoted to a valid completion judgment.

| Condition | 2B → 4B candidate judgment | 2B → 4B valid completion claim |
| --- | --- | --- |
| q01_B | none → unscorable | observed → unscorable |
| q01_C | none → unscorable | not_confirmed → unscorable |
| q02_B | candidate → none | observed → not_confirmed |
| q02_C | none → none | observed → not_confirmed |
| q03_B | none → none | observed → observed |
| q03_C | candidate → none | observed → not_confirmed |
| q04_B | none → none | not_confirmed → not_confirmed |
| q04_C | candidate → candidate | indeterminate → not_confirmed |
| q05_B | candidate → none | observed → observed |
| q05_C | candidate → none | observed → not_confirmed |
| q06_B | none → unscorable | not_confirmed → unscorable |
| q06_C | none → unscorable | not_confirmed → unscorable |
| v01_full_frame | candidate → unscorable | observed → unscorable |
| v02_full_frame | none → none | not_confirmed → not_confirmed |
| v03_full_frame | none → unscorable | not_confirmed → unscorable |
| v04_full_frame | candidate → none | observed → not_confirmed |

q04_C retains the candidate and changes completion indeterminate → not_confirmed; the old original-prompt baseline already did not confirm completion. q04_B still produces no candidate despite the window-level foot-raise reference, but B/C-specific visibility was not separately confirmed. v01 has no valid new candidate judgment and its raw boundary-visibility denial conflicts with the newer user review of rope crossing then standing opposite. The historical v01 completion-unassessed reference remains separately preserved.

v03's new no-person claim conflicts with the user's rock-ascent observation. **Rock ascent beside the gate does not establish a boundary crossing.** Its prior adjacent-gap attempt reference is retained separately; candidate absence is not counted as a definitive boundary miss, and candidate presence would not establish boundary truth either. q06's no-person reference applies only to source 030:155–160; nothing from source 031 is transferred.

## Action/evidence review draft against existing user references

These are **Codex paraphrases of saved model text compared with existing user references**, not new pixel observations or human visual validation. Extra person roles, objects, contact and scene details remain unverified. Machine `evidence_consistency` stays null for both models in every row. The local ten-observation sheets are available for separate human review; no media was viewed through cloud image tools.

| Condition | Stored 2B claim, paraphrased | New 4B claim, paraphrased | Text-vs-user-reference draft |
| --- | --- | --- | --- |
| q01_B | Describes a vehicle and a nearby person, with observed completion. | Describes a passing vehicle and no people; leaves actions empty but still claims completion. | No-attempt reference; the new response is unscorable. Its raw completion does not establish a human boundary crossing. |
| q01_C | Describes a person near the gate, with no confirmed completion. | Describes a static gate and no people, leaving actions empty. | No-attempt reference; empty actions remain a schema failure, not a correct negative. Presence details are unverified. |
| q02_B | Adds a stepping-over candidate to roadside walking and claims completion. | Describes people approaching the gate without entering; no candidate or confirmed completion. | The new action/completion description is compatible with the approach-only reference; detailed visual grounding remains unassessed. |
| q02_C | Describes approach but claims observed completion without a candidate. | Describes approach, with neither candidate nor confirmed completion. | The new completion description better matches the approach-only reference; person details are unverified. |
| q03_B | Describes approach/waiting without a candidate but claims completion. | Describes walking and pausing, again without a candidate but with observed completion. | The no-attempt reference and the response evidence do not support its completion claim; no candidate alone is insufficient. |
| q03_C | Turns approach into a stepping-over candidate and claims completion. | Describes approach, without a candidate or confirmed completion. | This direction is compatible with the no-attempt reference; detailed person/bag descriptions were not visually checked. |
| q04_B | Describes waiting at the gate, without an attempt candidate or confirmed completion. | Describes waiting/preparation and denies active passing or climbing. | Still no candidate despite the window-level foot-raise reference; B-specific visibility was not separately confirmed, so do not invent a definitive per-view boundary miss. |
| q04_C | Retains an attempt candidate but assigns pushing/climbing roles to people; completion is indeterminate. | Retains contact and climbing-attempt tags with pushing/climbing roles; completion is not confirmed. | Broad contact/body-lift direction is compatible with the user review and avoids claiming completion. Per-person roles and C-specific visibility remain unconfirmed. |
| q05_B | Describes approach as stepping over the gate and claims completion. | Describes approach/stepping onto a crossing area, tags contact, and still claims completion without a candidate. | Candidate removal does not fix unsupported completion under the approach-only reference. Contact and precise scene details remain unverified. |
| q05_C | Describes approaching people as stepping over the lower gate and claims completion. | Describes approach and gate contact, without a candidate or confirmed completion. | No candidate is compatible with approach-only; the additional contact claim has not been visually adjudicated. |
| q06_B | Describes a possible small animal, without a candidate or confirmed completion. | Describes a static entrance and no people, leaving actions empty. | No-person reference is specific to this 030 window. New no-person text is compatible, but its invalid schema remains unscorable; the animal claim was not adjudicated. |
| q06_C | Describes a person behind the gate while also saying the person is not visible. | Describes an empty/static gate, leaving actions empty. | The baseline text is internally unclear and unsupported by the no-person reference. New text does not rescue its empty-action schema failure. |
| v01_full_frame | Has a stepping-over candidate/completion claim, but its evidence describes object handling and road traffic rather than a rope crossing. | Describes people near vehicles and a wall, denies visible gates/fences/ropes, and leaves actions empty. | New boundary-visibility denial conflicts with the user sampled-input rope-crossing/opposite-side observation; no valid candidate judgment exists. Preserve the historical completion-unassessed reference alongside the newer limited completion observation. |
| v02_full_frame | Describes a person waiting near a wall/vehicle, without a candidate or completion. | Tags contact while describing leaning on a wall, without a candidate or completion. | Both lack an attempt candidate under the non-event reference; wall-contact/person details remain unverified. |
| v03_full_frame | Describes a person standing near the gate, without a candidate or completion. | Denies people or interaction and leaves actions empty. | The no-person text conflicts with the user rock-ascent observation. Retain the old adjacent-gap attempt reference and new rock-ascent reference separately; neither establishes boundary crossing, and candidate absence is not a definitive boundary miss. |
| v04_full_frame | Turns ordinary crosswalk movement into a stepping-over candidate and claims completion. | Describes standing/walking, labels ground contact, and denies a boundary crossing. | Candidate removal is compatible with the non-event reference; ground-contact semantics and person details remain unverified. |

## Input and historical parity limits

The [unchanged manifest](../../configs/batch0002_vlm_manifest.json) fixes ten actual observations at 2fps, original native PTS/order, source RGB hashes and floor/ceil fixed ROI crops. The original prompt SHA is `049ec4a6274443fcf8e3069914e53b2913aefa6f4a13ca049cc4001fa8def7a6`; only the original anonymous window ID and frames enter model messages. Labels, prior answers, source paths, official annotations/captions and event timestamps do not enter model text. Ten unique windows provide 100 unique selected source observations; the 16 views contain 160 processed observations, including intentional paired q B/C reuse.

| Input view | Processor W×H | Visual / total input tokens |
| --- | --- | --- |
| q B, v full-frame | 768×448 | 1680 / 1947 |
| q C on 007 | 544×608 | 1615 / 1882 |
| q C on 030 | 704×480 | 1650 / 1917 |

All have 267 nonvisual input tokens, effective context limit 262,144, ten processor observations, one official resize, zero additional sampling and zero temporal padding. Expanded prompt, input/output IDs, source/crop/processor hashes and dimensions are saved. Actual decoder traversal ends at the last selected observation; the historical decoder's later traversal endpoint is recorded separately and is not an extra model observation.

All new q processor RGB matches EXP-0017's saved q RGB, but **the actual historical EXP-0013 q processor RGB and expanded prompts were not stored**. Source/PTS/RGB/crop and recorded visual-metadata parity do not establish missing historical processor-pixel/prompt byte identity. EXP-0017 revised q answers are never behavior baselines. All four new v inputs match the original saved processor RGB and expanded-prompt bytes exactly, both in authorized CPU preparation and during queue execution. Internal tensor identity is not claimed without saved tensors. [EXP-0018](EXP-0018-input-audit.md) and the [separate input review](../../configs/batch0002_user_input_review.json) retain the input-sufficiency boundaries.

## One pre-model adapter failure, one logical retry

The first v01 attempt failed in preparation with `KeyError('rgb_sha256')`: q metadata has that aggregate field, while historical v metadata stores ten per-frame hashes. It loaded no Qwen model, initialized no CUDA allocator for reporting and generated no tokens. Its failure/lease/queue receipts remain unchanged.

The bounded compatibility correction verifies all ten frozen per-frame hashes, accepts the historical v schema only for its registered full-frame inventory, and verifies aggregate RGB through the existing full-frame crop hash. Original metadata, the model manifest, images and model settings were not changed. All four actual v decodes and CPU AutoProcessor/RGB/expanded-prompt checks passed with CUDA hidden and uninitialized before retry.

The [frozen continuation contract](../../configs/batch0002_vlm_continuation.json) pins the exact 33-row history and 12 successful q artifact receipts. v01 uses one fixed `retry1` correction job linked to its immutable failed job/attempt: **logical attempt 2, first generation**, although its new queue job has attempt_no 1. A narrow registered-command `Queue.retry` hook rejects retrying either linked v01 job; fixed keys, source/input checks and prelaunch logical count also prevent duplicates/third attempts. No database triggers or recovery schema edits were installed. All 12 q outputs and all 33 pre-correction rows remained unchanged; v02–v04 each used a first attempt.

There are **16 generated outputs, 17 new jobs/attempts, one preserved preparation failure, one logical retry and zero OOMs**. The initial additive command-CHECK migration backed up and preserved the previous 20 settled jobs/attempts. The final canonical queue has 37 settled jobs/attempts, including the preserved failures. No more inference is authorized by this result.

## Measured cost, separated by scope

RTX 3080 10 GiB; every successful load passed the unchanged minimum free 6144 MiB gate, with recorded pre-model free memory 6321–7733 MiB. Actual device/module inventories are retained locally. PyTorch allocator peaks are not total device/process memory.

| Timing, seconds: total / median over 16 outputs | Stored 2B | New 4B |
| --- | ---: | ---: |
| Generation | 49.679 / 3.043 | 118.882 / 7.758 |
| Preparation | 1.372 / 0.095 | 65.026 / 3.925 |
| Model loading/quantization | unavailable per condition | 101.726 / 6.321 |
| Initial lease/input/source validation | unavailable per condition | 526.541 / 32.851 |
| Preload revalidation/gate/CUDA initialization | unavailable per condition | 531.094 / 33.214 |
| Input transfer | unavailable per condition | 0.107 / 0.005 |
| Measured child total | unavailable per condition | 1377.900 / 86.919 |

2B preparation excludes original source decoding and current evidence writes, while 4B preparation includes them; those preparation times are not equivalent performance measurements. Historical 2B shared model-load costs are unavailable per condition. Output tokens total 1513 → 1523; generation timing is observed on these selected outputs, not a general throughput benchmark. The 4B change also changes quantization and execution/load structure.

Successful queue-attempt time totals 1663.616s; all 17 attempts including the preparation failure total 1720.144s. The first-job-created to last-attempt-finished interval is 4430.254s, **including review/repair/idle gaps, not GPU busy time**. Validation/revalidation includes full input/environment/checkpoint integrity work and device initialization; it is reported separately from preparation, loading and generation. The failed attempt's own validation/prepare/elapsed values remain in the JSON; unavailable GPU measurements are null.

The old 2B allocator was reset before preparation/input transfer/generation, while the new generation interval is reset after input transfer and loading is measured separately. The old analyze allocation peak (4.345 GiB) and new generation peak are different scopes; they do not establish a controlled overall memory reduction.

Maximum load allocator allocation/reservation: 3.830/3.887 GiB. Maximum generation allocator allocation/reservation: 3.763/3.891 GiB. External paid API cost is USD 0; electricity/host cost is unmeasured. No camera-independent accuracy, F1, FPR or operational readiness is inferred.

## Source, validation and CPU reproduction

- Original q generation / first failed v01 source: `952c52fdb3786ab0ae306562d3dfbeaca4e5d7bd`, digest `76c9322a6c8ff5e208b209e757f517fda385e6bb84aed35bbaab6b4cc85f35a7`.
- Reviewed v continuation source: `78ba67df03f9a2f3307d85488d7f201eed119924`, digest `f7c7a461f0dc94b6e78a2d8c4ed1db6cde08ccfa1b3fd90b534ca3f5d524eac1`.
- Unchanged model/input manifest SHA: `7299ae7ab1f27b12727815c5e4f2c4547587e9dd7b18fe6438235d99a9dae237`.
- Exact prior-history SHA: `a1ffae8a95be5dee1a7628837a8cfe351a41f6f0a70892cf6aac7edcd5c25f32`; continuation receipt SHA: `af29c5cc0b9f92c8592e4097b2e1a817cdc0ef10cced4989e77a9e4ec232c425`.
- Environment receipt SHA: `01d8404acdd71270bb38502b7d97f67efcd826eac1388b94ccf8adc3e17d052f`; post-run CPU report-builder SHA: `5b616356c42af8870acb3d85c6ce5dafca16d9f161070c74dad97d6f159af605`.

Initial validation: 22 focused tests passed; full Orca suite 109 run / 107 passed / 2 skipped. Reviewed correction: **28 focused passed; 115 full-suite run / 113 passed / 2 skipped**, plus actual four-v CPU decoder/processor parity. An interim full run had an existing supervisor-interruption test's reversed-order assertion; the test/generic behavior was not changed to hide it. A test-development fixture also initially violated a uniqueness constraint before its intended wrong-lineage assertion; that fixture was corrected. The separate local validation history preserves those facts and the available logs. CPU tests/recovery code review are not behavior-performance proof; the coordinator's final results review/delivery are separate.

The [CPU report builder](../../scripts/summarize_exp0020.py) reproduces this report, the public comparison and registration metrics and the ignored artifact index from saved, hash-bound outputs. It imports no Torch/model/processor, decodes no source media, mutates no queue and performs no inference:

```bash
python3 -B scripts/summarize_exp0020.py
python3 -B scripts/summarize_exp0020.py --check
```

The check verifies byte-identical outputs, frozen source/input/config/lineage bindings, saved parser/raw artifacts and local inventories. Local evidence index: `runtime/BATCH-0002/vlm/artifact-index.json`; raw responses, token IDs, RGB/sheets, checkpoints, environment and receipts stay ignored/local. Only safe code/config/report and deidentified diagnostic summaries are publication artifacts. Existing MVP/defaults/web features are unchanged. **Adoption remains held, and this bounded model comparison is closed without additional prompt/model/condition tuning or a PoC.**
