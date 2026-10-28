# EXP-0014 independent coordinator review

2026-10-28. **Verdict: needs correction before release registration; arithmetic/reproducibility sound within the frozen cached-record scope.** No blocking arithmetic or provenance mismatch was found, but the metrics file fails the existing registration contract (high-severity finding below). This verdict does **not** approve behavioral performance, visual factuality, boundary alignment, or adoption of B/C. Behavioral evaluation remains **평가 준비 완료·사람 확인 대기**.

Review assignment: existing Orca Run `run_3d23462a014a`, Task `task_c04d6a328a22`, Dispatch `ctx_a91450d17437`. This is an independent verifier's report; no model/effort identity is inferred from the assigned role. The only owned file change is this report. No existing report, manifest, evaluator, metric, source output, or historical review binding was edited.

## Evidence binding

SHA256 values below identify the exact reviewed bytes; conclusions do not automatically cover later revisions.

| Artifact | SHA256 |
|---|---|
| `configs/mvp_small_eval_manifest.json` | `ec293844173fe8797b2e518ba1a01b98be2720f766fd4c27bf3d5f278a7186af` |
| `docs/experiments/EXP-0014-mvp-small-evaluation.md` | `1b196229ed54f084bd1b5ddfb9f27ef850c7a8e680394c059ac5103c03271e9e` |
| `records/EXP-0014/metrics.json` | `2ec57d4ba1c475f0ec05aec7f8a4a10ae3b9021cad9b61fdd087c87ba8aa039a` |
| `records/EXP-0014/window_reviews.json` | `427d59cd0d8092a5fb69c936449be9301d1d302285e21381ec7e1d0ada672b1a` |
| `scripts/evaluate_mvp_small.py` | `3d0e16a593678372bb454a7e79fd46806a50ea810d6c57880793f99f0fe7c7af` |
| `tests_mvp/test_small_evaluation.py` | `9e4346a7e1958bb4c06864b7f1abe4721be76a787022fa029b096a952f0dcd04` |
| `mvp/events.py` | `f6353d27fb2e963d21595cd733bb611db66e4f676fd6146e334dabafbcf94a14` |
| `vlm_batch/common.py` | `59ff4f586427373bdd4d9dd72fa1ef125ecc70924f81cc1254534741671a94cf` |
| `docs/experiments/EXP-0013-mvp-comparison.md` | `c24f2499bb139e33b1e1285e0a67edff6493dd08ad6d41e0936c9cc0da092b1e` |
| `docs/data/MVP_SMALL_EVALUATION_PLAN.md` | `a4febe480ac6ec4ac4093024e489f1b19c18cfeac187597e777a2534ec78f398` |
| `docs/data/EXP-0013-observation-errata.md` | `f54f6a947bc64ad15ceda02c21b489418348233ff9f3d7a1156896c85a168423` |
| `docs/orchestration/COMPLETE_CLI.md` | `bc510d47c32361c83a55c4e63f785cd7b4dd626b25eafb4e3269430c430f6a92` |
| `orchestration/complete.py` | `0b36f9dbcb92b69b22103e8204ec058d0450dbc97f81212875e241c86f37b956` |

The canonical item hash in `records/EXP-0014/metrics.json:49`, `4178c85a188117329bc8099138be75c41837a87a84f5c34b7167ef670445d2c4`, was independently recomputed with sorted keys, compact separators and UTF-8. It differs correctly from the pretty-printed item file's byte hash. Manifest, evaluator and EXP-0013 source-report hashes match their metric bindings.

## Checks and source tracing

Read the assigned AGENTS/task/plan/errata, complete manifest and sanitized item/metric data, evaluator and focused tests. Also inspected the pure-Python classifier/parser and the relevant public user-observation provenance. Independent checks used standard-library inline Python, without calling the evaluator's aggregation routine or its real-cache evaluation entrypoint.

Selection checks passed: exactly 12 unique source/window cases, four per source, each five scheduled seconds on the existing grid; no within-source overlap. There are 12 B/C pairs, or **24 method-window records**, not 24 independent pairs. All 24 sanitized records agree with manifest IDs, label status, intervals, sampled PTS, rational native PTS conversion and recorded RGB hashes. All 12 B/C PTS arrays and recorded decoded-source RGB hashes agree. Equality of saved hashes does not establish equality of cropped processor tensors or revalidate media contents.

I independently hashed **86 unique source-cache files**: two loading metadata files, six source run metadata files, six window logs and 72 selected input/window/result files. Every hash matched the sanitized provenance, including each selected JSONL line hash. Their hashes and modification times were unchanged across this review's source check. The evaluator's reported 88 consumed files is consistent with these 86 plus the manifest and EXP-0013 report (`scripts/evaluate_mvp_small.py:235`, `:237`, `:347`). This verifies current bindings and review-time preservation; it does not independently reconstruct the earlier evaluation's before/after timestamps.

Source JSON was projected locally to metadata, excluding raw responses, parsed/freeform answer objects and model-claim text from inspection and tool output. Result files were hashed as opaque bytes. No actual response was reparsed by this reviewer. Selected log lines were located by their recorded hash; unselected log content was not interpreted. No media, pixels, official-label files, weights, processor arrays, credentials or application runtime files were accessed. Orca lifecycle commands were used only for the assigned coordination channel.

Representative traces covered **both B and C for one case per source**:

| Case and public record locations | Verified schedule and native PTS | Source metadata / saved output state |
|---|---|---|
| `s007_preevent`; `records/EXP-0014/window_reviews.json:145`, `:1396` | `w000020`, 47.5–52.5s; 10 observations 47.5–52.0s; native endpoints 729600–798720 at 1/15360 | C3; B ROI `[0,0,1,1]`, C ROI `[0.6,0,0.9,0.6]`; B candidate, C observed-other |
| `d030_90`; same file `:668`, `:1920` | `w000036`, 87.5–92.5s; 10 observations 87.5–92.0s; native endpoints 1344000–1413120 at 1/15360 | C6; B full frame, C ROI `[0.28,0.2,0.75,0.8]`; both candidate |
| `s013_mid`; same file `:980`, `:2233` | `w000017`, 40–45s; 10 observations 40–44.5s; native endpoints 614400–683520 at 1/15360 | C4; both full frame; both observed-other; C is reuse |

Each trace checked loading/source attempt and input binding, source/camera IDs and saved source hash, window/log metadata equality, input binding, result pointer, runtime-state equality with the sanitized row, result input PTS/native PTS/time base, frame count, interval and ROI. B attempt is `49cad0749df04995bb55727d57946fec`; C is `a546b67626e54ef79cdf9bee1c70b3bf`. Source metadata points to the manifest's source hashes, without reopening the source media. These public IDs plus the evaluator's resolver at `scripts/evaluate_mvp_small.py:242` identify the local records without publishing private paths.

| Case / method | Window-file SHA256 | Result-file SHA256 |
|---|---|---|
| `s007_preevent` B | `9e1a71b8d34493f040f818f458f30f6de84436d0e69473e0bde1891db9cbc37c` | `3cc1483e3998e707dba14454b2fd248a531ae9f061653128249d49980e772ef3` |
| `s007_preevent` C | `91cf88a519b87e478a6a8a438c3561df7386c15e547b94fa690abb40d9d0f6d2` | `5baaf5a165e38ec1e93f8103b78c405364d6870842175d0bb057a0ebda7718e5` |
| `d030_90` B | `583c6148303f7b62cc5779fa8c3ef8e4af95bf00e3ccef4408d7d2ac7e4e188f` | `3364d6b60193102792a8f61afbbbc371ac864266a3618b2cb5bd923f016cb428` |
| `d030_90` C | `49d385d5cd8bd0b4ca20196e1440e47a4fb8f8be3c5cd97c1fd70687f19debe6` | `ef15e5547ba80f4e2b18d591a82704a35530d17f7b082482e304f13ef0be488c` |
| `s013_mid` B | `e9d883d1f3a270a759e825fe6b44793d0a870ff33a1c4ced8cec8cb783c8f166` | `0e6caaee5a5fdf414bd5a25dad407dc4c678d227c676882a433a83b85ca4069e` |
| `s013_mid` C | `4b3562e1401c9a97241757aaaea15a3dd972ea67c54cd8ee657fd7048ed8af7b` | `27992b6ef74044ab0ff9e57c86b0b011b90573147ab40097d5506fce5c66cfe1` |

For all four C4/C rows, additionally checked reuse metadata against the selected B result-file hash, B attempt/window ID, recorded raw-response hash and semantic-input fingerprint, plus zero newly generated tokens and null generation time. All passed. The evaluator explicitly compares raw/parsed responses and input metadata at `scripts/evaluate_mvp_small.py:321`–`:329`; synthetic corruption coverage passed. Independently reading or comparing actual answer contents was outside this review. Exact reuse concerns the answer/input, not identical B/C result-file bytes: reuse provenance and timing legitimately differ. C4's four C rows remain diagnostic reuse, with no independent ROI-success or speedup credit.

## Independent arithmetic and interpretation

Recomputed every metric table from sanitized rows, including unknown-label and reuse counts, and checked the report's tables at `docs/experiments/EXP-0014-mvp-small-evaluation.md:30` and `:69`.

| Group | B candidate / absent / unavailable | C candidate / absent / unavailable | Denominator per method |
|---|---:|---:|---:|
| All selected | 4 / 8 / 0 | 5 / 7 / 0 | 12 |
| Primary | 2 / 1 / 0 | 1 / 2 / 0 | 3 |
| Non-fallback diagnostic | 2 / 3 / 0 | 4 / 1 / 0 | 5 |
| C4 fallback diagnostic | 0 / 4 / 0 | 0 / 4 / 0 | 4 |
| Partial positive subset | 1 / 0 / 0 | 1 / 0 / 0 | 1 |

The last row overlaps the diagnostic group and is not added again. There are 11 unique unknown cases and one partial positive-presence case. All three primary cases are unknown. Confirmed primary positive and negative denominators and verified negative duration are zero. Candidate absence is not a true negative. The null accuracy/precision/recall/F1/FPR/hourly-false-alarm values and rationale at `records/EXP-0014/metrics.json:154`–`:174` are justified. The partial observation near 90s supports diagnostic presence only, with monitored-boundary alignment still unverified; it does not justify a behavioral recall score.

Strict-form compliance is B 4/12 and C 8/12; postprocessed schema validity is 12/12 for each. Fence removal counts are 8 and 4. Completion-observed claims are 8 and 7, including 4 and 3 without a climbing action. Candidate-text categories are B 2 motion-described / 1 explicit-denial / 1 no-motion-described and C 4 / 0 / 1. These sums match the published diagnostics. All 24 explanation-factuality fields remain unresolved. Actual lexical classifications and strict-form status were not independently rederived from real answers; their arithmetic and implementation were checked.

Candidate precedence over indeterminate, deduplication of action words, separation of contact and climbing, and completion-only exclusion agree with `scripts/evaluate_mvp_small.py:96`–`:148` and `mvp/events.py:11`–`:32`. No merged event is loaded to rescue a missed scheduled candidate. The 030 EOF anchor is `w000063`, 155–160s, with ten observations and candidate absence; it is not the historical insufficient-input tail. `configs/mvp_small_eval_manifest.json:532`–`:544`, evaluator `:80`–`:93` and `:302`, and the passing provenance test preserve uncertainty instead of transferring 031's group-noncompletion observation. The 007 box-change remains an AI partial visual observation (`manifest:184`–`:196`), not a user-confirmed five-second negative.

## Findings and required interpretation

**High — release registration blocker: required metrics envelope is absent.** `docs/orchestration/COMPLETE_CLI.md:20` requires `schema_version: 1`, matching `experiment_id`, and a `metrics` array whose rows contain `label`, `value`, `unit`, `sample_n`, `scope`, `source`, `source_sha256`, and `verification`. The reviewed `records/EXP-0014/metrics.json` (SHA256 `2ec57d4ba1c475f0ec05aec7f8a4a10ae3b9021cad9b61fdd087c87ba8aa039a`) has `schema_version: 1` at line 165 and `evaluation_id` at line 34, but no `experiment_id` or `metrics` array anywhere. Its output tables at line 52 are not the required delivery rows. `orchestration/complete.py:191`–`:207` enforces this contract, and the registration path invokes it at line 279. A read-only invocation of the pure `metrics(data, 'EXP-0014')` validator reproduced `ValueError: invalid metrics document`; no registry/config/runtime was opened.

Action: have the authorized owner supply a contract-compliant delivery metric document/envelope, preserving the detailed results, with appropriately scoped numeric/null rows and real denominator/source-hash metadata. Keep behavioral scores null and avoid substituting an empty display table for the requested measurements. Revalidate and bind the final metrics bytes in a renewed review before registration; do not change registrar validation or silently reuse this old metrics hash. This worker did not edit the metrics or evaluator.

1. **Informational — no blocking arithmetic/reproducibility correction.** The reviewed hashes, all 24 public row mappings, ten count tables, six representative source metadata traces and four reuse bindings agree. Use the bound verdict only for cached extraction/counting. Keep performance and adoption pending; do not turn 24/24 trace validity or 20 passing tests into a behavioral success rate.

2. **Low — freeze chronology is disclosed, not independently proven.** `configs/mvp_small_eval_manifest.json:5`–`:7` and `records/EXP-0014/metrics.json:168` explicitly disclose retrospective, outcome-aware development selection. The hash proves today's selection bytes, not whether an agent had previously seen itemized answers. The phrase “twelve ... B/C result.json files” also denotes 12 selected windows but corresponds to 24 method-specific result files. Action: retain the outcome-aware disclosure and describe the unit as “12 windows / 24 B/C records” in delivery; preserve any existing freeze receipt privately if chronology is material. Do not rewrite the frozen manifest to repair wording, and do not claim prospective/blind selection from this review.

3. **Informational — human evidence and common-boundary verification remain prerequisites for scoring.** `records/EXP-0014/metrics.json:162`–`:174`, the manifest's `d030_90` partial label at `:464`–`:476`, and unresolved item fields correctly prevent scores. Action: retain null scores and B/C adoption hold; if proceeding under the existing plan, consolidate at most six original-only windows for scoped human review, recording any answers as a new label/evaluation revision. Do not count out-of-ROI exclusion, camera reuse, candidate words, or claimed completion as confirmed success. No new review clips or question batch were produced here.

4. **Low — retain parser/classifier provenance for later reproduction.** `scripts/evaluate_mvp_small.py:18`–`:19` imports behavior from two existing modules, while `metrics.json:47` binds only the evaluator's implementation hash. This review therefore records both dependency hashes above. Action: carry these bindings or the complete repository revision with delivery; a later parser/classifier change needs reevaluation/review even if the evaluator file remains unchanged. This is a reproducibility improvement, not a discrepancy in the current result.

## Focused CPU verification and privacy boundary

Executed once:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests_mvp.test_events tests_mvp.test_small_evaluation -v
```

**20 tests passed in 0.382s**: 16 evaluator fixtures plus four existing state/merger regressions. Fixtures use temporary synthetic answers and never read actual cached answers or media. Coverage includes unavailable positive denominators, unknown-not-negative, missing/invalid output, duplicate log/action handling, source/PTS/hash mismatch, fallback corruption, manifest edits, 031 provenance, candidate/indeterminate coexistence, form/completion separation, source-mutation detection, and deterministic sanitized output. No broad tests or actual-cache evaluator rerun was needed; the latter would read real responses and its CLI would overwrite metrics.

The evaluator's source reads and hash rechecks are separate from its writes (`scripts/evaluate_mvp_small.py:44`–`:64`, `:341`, `:398`–`:410`). It writes only the evaluation destination and rejects output symlinks; consumed source mutations are detected. This is an in-process check, not a filesystem lock or proof against historical/concurrent changes after the last check. Current manifest/metric/item files contain no raw-response/freeform-answer fields or private absolute media paths in the checked schema. The no-network/no-GPU scope is supported by the evaluator's imports and CPU fixtures; no GPU, model, network, clip generation, commit or push was performed by this reviewer.

Sanitized records can establish saved identities, timestamps, numeric/hash bindings, output categories, accounting and declared provenance. They cannot establish the truth of actions in pixels, all-person completion, scene/ROI correspondence, actual decoded-frame contents, model-weight identity beyond recorded metadata, site independence, historical access order, or real-answer lexical accuracy without the corresponding source review. Registration, publication and browser delivery were not part of this worker's verification.
