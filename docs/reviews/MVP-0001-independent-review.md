# MVP-0001 independent review

2026-10-28. **Bounded independent review complete: CPU code/input-preparation checks pass; real model integration and action performance remain unverified because the resource gate blocked inference. MVP-0001 is not complete and no adoption is recommended.** The reviewer owns only the evaluation manifest, evaluation scope and this report. No helpers, model calls, downloads, official-label changes or new pixel inspection. Raw media and receipts stay local. Coordinator owns integration, HANDOFF and publication.

## Evaluation freeze and provenance

Initial scope commit `a12d7d9` freezes [manifest](../../configs/mvp0001_eval_manifest.json) SHA256 `f8e8a6892cb5b98ffb09a9eb99163edeec926ab3ef2d2cb237bbb17fcd176824` and [evaluation scope](../data/MVP-0001-evaluation.md) SHA256 `8973e0b8a08f9258a6f743ef02377777dd223e6948364eece8c652cf4b01b1a1`. Independently checked six selections, three full sources, development/reserved camera-role separation and eight document hash bindings. Source hashes are copied from existing local audit/input metadata, not newly asserted rehashes of all media.

Before inference, coordinator message `msg_5f34fa10853b` supplied a missing explicit user observation: original-scene approach/standing around 84s and climbing around 90s in 030. Correction commit `32bc166` preserves this as user evidence with relay provenance and unknown original message date; it does not create precise onset, identity, completion or three-event GT. Current frozen manifest SHA256 is **`fae2f70a46b6073b3d65c0581db6ee7df1a9b0e137257673d59800ba1641fc4d`**, evaluation SHA256 **`a48027c8229cdff64d4e6095693353dd0975ed15b3120b4762d263ca9f483216`**. These supersede the initial hashes above without changing selection or model conditions.

The frozen inference files at coordinator commit `c7eff04` match the evaluation IDs, source hashes and camera groups. Sources SHA256: `29e1d71a189c4512baba3c053b2a288cfed5ad10e6195973fee5a0ba37fd5de4`; cameras SHA256: `d37fbc699a84fae72ae236f4ae40e01bfb8d58b2fbe3b746eba0e6fb55624f18`. C1/C4 full fallback is explicit; C3/C6/C7 current ROI values match their embedded historical config. This does not independently revalidate the original pixel calibration or establish independent sites.

Inspected coordinator metadata-only session receipt, SHA256 `29a77bf13df8b29eab6e8d58b5f8663e45e4d4bed7f4f5f901bff9f8438a667b`, recorded at 10:33:25 UTC. Exact current reviewer session `01a18211-7689-72f3-8ae2-edb364e671f5` has `gpt-6-astra/high`, Codex 0.165.0, and the assigned review workspace. The receipt's separate `current_session` is coordinator Astra/max and is not attributed to this reviewer; catalog visibility alone is not invocation proof. Current review tool work and native Task `task_903274b61857` / Dispatch `ctx_8512d0d66d37` provide the execution context.

## Early draft findings

Read worker drafts without modifying them. Native message `msg_94c94fe543c0` routed these integration issues to the coordinator before inference; fixes require committed recheck.

| ID | Draft finding | Required verification |
| --- | --- | --- |
| R1 | Window producer emits `window000001`; adapter accepts only `w` followed by digits. | Agree anonymous ID contract and exercise actual producer-to-adapter CPU path. |
| R2 | Window source returns elapsed-PTS-based float `relative_indices`; adapter requires integers. | Preserve actual timing, including VFR, without misleading rounding; inspect actual official-processor timestamp interpretation. |
| R3 | Adapter indexes `pts[-1]` before insufficient-frame handling; sparse gaps can produce zero-sample windows. | Empty and one-real-frame windows must retain an insufficient/unknown record without model generation or a model retry. |
| R4 | `run_full` loads window `result.json` directly, but `ExactReuseAnalyzer` accesses a nonexistent nested `previous['analysis']`. | Align saved-result/reuse shape and test the actual pipeline storage path; otherwise C4 fallback reuse fails. |
| R5 | A later preparation failure can leave the prior clip's cached token IDs; the development runner's catch path then attributes them to the failed clip. Full-pipeline text-decode failure also needs current-token retention. | Clear per-call caches before validation/preparation and bind retained failure tokens to the current window; verify with synthetic failure tests. Routed in `msg_fe053e572d66`. |
| R6 | Full C4 reuse initially identifies a successful baseline attempt and semantic-input key without binding the exact saved response-result bytes. | Record and verify baseline window-result hashes before reuse, retaining those hashes in provenance. Routed to coordinator in `msg_891252999b88` and method owner in `msg_3ad5894244c1`. |

Read the installed Transformers Qwen3VL processor source: model captions divide indices by FPS, average each temporal pair and format to one decimal second; odd tails repeat the last index. Native PTS preservation is therefore distinct from lossless model timestamp representation. Routed this disclosure via `msg_2d36e0062985`; check actual inputs and cross-module CPU tests before accepting the timing contract.

Draft-stage independent CPU checks passed: pipeline **18 tests / 0.697s**, adapter **7 tests / 3.980s**, plus a direct synthetic VFR producer-to-official-processor check over three windows including odd-tail padding. No model was loaded and CUDA stayed uninitialized. The latter receipt SHA256 is `2532bbf21f8cf7a17049548b9a20a3ad27c8ebfcf03e05eccc75a49098172cf6` and binds both draft source hashes. It checks actual caption tokens against averaged native-PTS-relative times rounded to one decimal, not merely advertised metadata. Current draft IDs and separated decoded ordinals/elapsed PTS resolve the observed interface mismatch; final committed source recheck remains required. R4 and these results were routed in `msg_21dfd69960e7`.

Independently ran the new command/lease/migration fixtures: **10 passed / 0.760s**, then the integrated prior queue/VLM/parser regressions at `2f815c1`: **28 passed / 8.040s**. Regression receipt SHA256 `5d8f41ff2004f15ce09593824b50f8c1ce34b3ef7b327f5bbedade318015e202` binds the log and relevant source hashes. Fixtures cover queue serialization, exact child ownership, inherited lock, timeout/cancel, single retry, tampered hashes, historical-row preservation and parser behavior. Reviewer did not migrate or enqueue against the live queue. Supervisor death can still suspend timeout enforcement; inherited locking is not an unconditional orphan-runtime deadline.

## Preserved baseline text audit

Independently reread all twelve EXP8/EXP10 raw Qwen responses and compared parser outputs with their stored result objects. Strict parsing remains 2/6 and 1/6 respectively; fence-only parsing is 6/6 for both. The hash-map digest over each condition's six raw responses, results and expanded prompts is `a275aaa0b24767155fdf77a01762871795229a88d0076327f4843f87146cc517` for EXP8 and `717c743c824ddb758998bd5eedc30d8f76cfa5f0644b24339fb2f336bdc66fb0` for EXP10. Local audit receipt SHA256: `48caf23d46fae5ad6f85aeb3f2e1b185c88fa94a968dba6a29acc9ce46b08511`.

The prior semantic conclusions remain: EXP8 clip02 uses stepping but describes an open gate/crosswalk instead of the recorded climbing; clips04/05 substitute standing/waiting for body-rise drafts. EXP10 retains those latter omissions and asserts completion on all six. EXP10 clip02 explicitly claims opposite-side movement, unlike its other five evidence-poor completion explanations, but that claim remains unverified against prior observations. Neither label presence nor a completion sentence establishes true crossing. Clip03 remains outside the monitored ROI and clip06 still requires uncertain-contact handling. This is stored-text review against prior evidence, not renewed pixel review or measured false-positive counts.

## Full-source CPU preparation audit

Independently inspected the coordinator's text/numeric receipt, SHA256 `2f4dd388fdc0a8d4bdb4ea679cba103d97da66e951166906b6c3d748952cdc9b`, recorded 10:44:47–10:45:31 UTC against `d6bf473bf4cb0095964240981a47167e6312b775`. It is explicitly **decoder/window preparation with no analyzer or model call**. Recomputed source-hash agreement with the frozen manifest, all window IDs/bounds/stride, native PTS/timebase relationships, sampling targets, decoded-index bounds, causality and EOF availability, unique sample counts and spacing. Reviewer audit receipt SHA256: `910363d165902079089c3cbebe310da6dbe589a71a082071d8f9e08cc17c839e`.

| Source | Decoded frames | Unique samples | Windows | Last-window real samples |
| --- | ---: | ---: | ---: | ---: |
| 007 development | 4,171 | 279 | 56 | 4 |
| 030 development | 4,802 | 321 | 65 | 1 |
| 013 reserved diagnostic | 3,781 | 253 | 51 | 3 |

All three receipt streams reach EOF: **12,754 decoded frames, 853 unique samples and 172 overlapping windows**. The maximum selected-sample spacing is 0.5 seconds on each source. The last sample-to-last-decoded gap is zero for 007/013 and approximately 0.033333 seconds for 030. These counts are not independent behavioral samples or evidence that every transient action was observed. Periodic coverage removes CV gating, not the risk of action occurring between selected frames.

030's final window `[160.0,160.06666666666666)` has one real sample and must remain insufficient evidence, with no generation or normal-success credit. Those are measured input bounds, not action timestamps. The EOF receipt supports source decoding only; it does not satisfy the full three-video analyzer/candidate/evidence integration gate or establish output delay, GPU cost or action discrimination.

## Committed code recheck

Reviewed integration `5adaa32` in an isolated local snapshot and independently ran all **46 MVP CPU tests in 8.052 seconds**, no skips or failures. Source hashes were unchanged during the run; receipt SHA256 `356f162de89e208694d3a79ce78c124ca2420ccc65b81270293576c5a57f338c`. These include real pipeline-written result reuse, altered-result rejection, original decoded indices versus fractional/gapped PTS captions, zero/one/odd EOF input, current-token retention after decode failure, stale-token clearing after a subsequent prepare failure, raw evidence/uncertainty retention and queue contracts. **R1–R6 are resolved** in this committed code and its fixtures.

A prior combined run on moving integration `ad72490` is explicitly not acceptance: 41 tests ran with one missing `read_baseline_results` import while its owner commit was arriving, and the source-hash guard detected changes during execution. Receipt SHA256 `5b57984c1b30fa11616dc43e3bcfd3b47a2ea66e6fbd13ce06978ef5c4da1d81` preserves that failed transitional check. The isolated passing run supersedes it; no unresolved import defect is claimed.

Code review confirms periodic analysis is independent of CV candidates; only fixed ROI and measured timing reach the analyzer; completion alone does not create a crossing candidate; unknown/parse failure/insufficient input remain review states; overlapping same-action groups retain original records and grounds. Source availability, last input PTS, first result persistence, final merge and evidence-write times remain separate. EOF availability includes the observed final frame coverage. Offline processing time is not a real-time detection delay. Reuse requires successful native baseline ownership, matching run/config/source/input identity and exact saved result bytes, with null new generation timing and separately retained historical costs. None of these implementation properties establishes action correctness.

## Actual six-input CPU preparation and historical reuse correction

Method-worker preparation-v2 summary SHA256 `48a886df988373a5c09ed52491b6d5682f8da2b242e869b02c35d1527fc60fd3` records six CPU-prepared caches, zero model construction/inference and no CUDA initialization. Independently checked each preparation JSON, original input-JSON hash, frame order/native PTS/FPS, frozen ROI/outward crop bounds, exact question suffix and official timestamp captions against the preserved baseline. All retain ten observations without extra sampling or padding. Reviewer text/metadata audit receipt SHA256: `c23df8a4427ef7d1ba1f02d0dc42854ce06562bc46fa62e5b4faee52cfaa2fbe`. No actual image/array was newly viewed by this reviewer.

Recorded geometry is 608×544 / 1,615 visual tokens for clips01/03/04, 480×704 / 1,650 for clip02, whole-frame fallback 448×768 / 1,680 for clip05, and 736×448 / 1,610 for clip06. These are CPU processor metadata, not measured action improvements or GPU costs. The region can remove useful context; clip03's outside-ROI observation cannot become a normal-discrimination success.

The first preparation attempt stopped at clip05 because its strict historical `qwen.py` byte check rejected EXP10's extraction of two unchanged pixel-budget literals into a class constant. Failed CPU-preparation summary SHA256 `c5b7711865be6fb13f7ac95c983fcfee45ad51c419a756f4c9827afa8a379e09` is retained; this was not a GPU error retry. Independently compared the old adapter SHA256 `56388dfc25fbe926372f1782b689cb440ec182be8073c9a2a39a9111e4447b4f` with current `94d0c64f1355a7f0a3c13b9836d7a0159345fea441464d050fa2c8c998fc237b`. A narrow exception pins those exact bytes and requires AST identity after restoring exactly two identical literals and removing that one constant. Changed budget, prompt, sampling flag or missing replacement is rejected. Reviewer check receipt SHA256: `1a169e484da700680a5e766c40fb974de897036e294c825a52fcedaa9f65f160`.

Clip05's separate worker proof reports exact processor pixels, expanded question, native timing, weights and generation settings against successful EXP8 attempt `8b93c06304724009b8ca5a0d15a28288`, and preserves result/raw SHA256. Inspected its four-tensor parity receipt SHA256 `798cd73fd25a8ef8c7dca0d535ae9e523156f357ea4ba0d9d2fe251b151068df`, which records no CUDA initialization and zero new model calls. This reviewer independently checked the code equivalence and text/timing bindings; this is not a new pixel-semantic review or a newly generated response. Final code and public report/metric bindings follow below.

## Live queue, preservation and resource evidence

Read-only live SQLite inspection at **10:53:41 UTC** independently compared all historical rows by primary key: **11 jobs and 11 attempts exactly unchanged**, **zero MVP jobs**, and the MVP command schema migration had not run. Reviewer receipt SHA256 `91346a3045abefe6ba24c6bb5f63edc6b3113b6cd5b8e2eb00b0b2465f90b028` binds the original queue snapshot `acd99d13fb5139f24b61722e06ec8bd5eeed5ef540f6e185c97862debbc37fd4`. Coordinator's corrected comparison receipt `f9194eb378e7ef3682c1a38dea51374e66c1f5cdc6abc0b7b2b1caadf6104ed0` agrees; an earlier unsorted-row comparison falsely differed and remains retained. SQL row order is not row mutation. Reviewer initially assumed dict rows when the snapshot contained positional rows; that local checker failed before producing a verdict, then was corrected using the live schema's primary-key column positions.

Inspected coordinator preservation receipt SHA256 `9c51d0fa84ab32e0a0d6452b5bfdc8951903dec281a89a70643a7f1c3171bdd3`: 2,235 inventoried files, 565 selected hashes and two environment freezes agree. This is receipt inspection, not an independent rehash of all media. Model generation, live queue migration and full model processing must not be inferred from synthetic migration tests or the decoder's three EOFs.

## Final source and public evidence acceptance

Final isolated integration snapshot **`9bec56e4c26a8a0df1c85348c12d25251f12cda0`**, containing method commit `6b9cd3b` and pipeline commit `1d18278`, passed **47 MVP CPU tests / 7.505s**, with no skips or failures and unchanged source hashes throughout. Receipt SHA256 **`4d0b934c7d4f843d79064412267997d5be1aca06d3eb43edca0a23c848a3b747`** binds the complete source inventory and test-log SHA256 `94fb86530910b2e4bd380718eea1558218d3b858dcf46a7b5065dfa96119e292`. This final run includes the narrow historical-refactor acceptance/rejection test and supersedes the earlier 46-test snapshot for code acceptance. The new refactor guard changes provenance validation only; it does not authorize different sampling, prompt, budget or model settings.

Independently checked **all 37 non-null public metrics** against their named local source SHA256 and JSON pointer: 20 for EXP11 and 17 for EXP12. EXP11 contains CPU test/preparation counts and geometry; EXP12 contains CPU test/source-decoding counts. Actual model, action-performance and model-output-delay values remain absent/null. Audit receipts are `f9c8f6de63ced5ff3f8012c6147125afb915f21399628006bb563af0b94488ff` (EXP11) and `c680654a4dfa76e43bca5a3d9a31969ebe0ea28da50314c8da272ea9ecb79c10` (EXP12).

| Reviewed public artifact | SHA256 |
| --- | --- |
| `docs/experiments/EXP-0011-fixed-camera-input.md` | `1cc727e272c4b2e7c16bd510f9dce23aaf76c9d5df22f89f91300b64035d01c6` |
| `records/EXP-0011/metrics.json` | `de09a649bf210fbc0808b38f23c45e7d652a996fd69eee4fd506f1fcf193e5a9` |
| `docs/experiments/EXP-0012-continuous-mvp.md` | `aba34d897902fda29f42afa0264f10d58de55089310b45695009228bd97d83b5` |
| `records/EXP-0012/metrics.json` | `2162b11232d45311a040e49f8940c3106cb6ec3cdd54d4988a2cc124aa45db8c` |

The final coordinator resource receipt, SHA256 **`a744deada5cc1d198f0b6793fbd3da900f2b0659d0f45df44759d1cba952cf46`**, records **1,806 MiB free at 10:56:18 UTC**, below the frozen 6,144 MiB gate, with zero MVP model jobs/generations. EXP12's earlier coordinator observation of 1,561 MiB at 10:55:17 UTC is a different observation; both fail the same gate. The coordinator terminated this bounded attempt without loading the model, killing other processes, changing settings or migrating the live queue. This is **resource-blocked/unstarted**, not a model OOM or failed generation. There are no actual MVP inference-attempt receipts to certify; preserved historical attempts and CPU fixtures must not be substituted for them.

## Independent verdict and remaining work

| Gate | Verdict | Evidence boundary |
| --- | --- | --- |
| Automated tests and inspected code | Pass within reviewed scope | Final 47 synthetic/CPU tests; R1–R6 resolved; safe queue/reuse/timing contracts inspected. |
| Actual input preparation | Pass within measured scope | Six cache preparations and three full-source decoding EOFs; text/numeric receipts audited. |
| Functional three-video model integration | Unverified, resource-blocked | No real full-window model output, candidate/evidence completion or actual model-output delay. Decoder EOFs do not satisfy this gate. |
| Meaningful action discrimination | Unmeasured; adoption hold | No new C responses or full-window behavior evidence; prior six-clip Qwen weaknesses persist in preserved text. |
| Registration, GitHub and browser delivery | Coordinator-owned, not certified here | Separate publication and actual-screen receipts are still required. |

New six-clip model responses and full-window model results do not exist at closure. Accuracy/F1/FPR remain absent without confirmed ground truth; prior A/B adoption holds are preserved and C has no evidence supporting adoption. The reserved exposed 013 diagnostic must remain untuned and must not be described as blind/new-site validation. No new user video-review questions are necessary before nonexistent outputs; after a separately resumed bounded execution, consolidate only action/uncertainty questions needed to interpret those outputs. This review's completion certifies the stated inspection work, not successful MVP execution or deployment.
