# MVP-0002 — Independent review of EXP-0013

Date: 2026-10-28. Task: `task_75e5ce5d2661`; dispatch: `ctx_788b5f7159b2`.

**Recommended `review_status`: `approved_with_limitations`.** All 39 published metric values agree with the three permitted local summaries, with the now-documented source-ID lookup needed for four values. All three summary-file SHA256 hashes agree. The coordinator corrected the report's reproducibility claims and 007 wording during review; the final revision is acceptable as a scoped execution-summary comparison. This approval does not certify behavior performance, raw execution provenance, exact reuse, or adoption, which remain unverified/on hold.

Requested reviewer role: Astra/high. This review does not independently certify the effective runtime model/effort; that requires coordinator session evidence outside this content review.

## Reviewed revision and boundary

| Artifact | SHA256 of bytes reviewed |
|---|---|
| `docs/experiments/EXP-0013-mvp-comparison.md` | `c24f2499bb139e33b1e1285e0a67edff6493dd08ad6d41e0936c9cc0da092b1e` |
| `records/EXP-0013/metrics.json` | `93cc8a8ffb032fe35b52bceded01b158509a4491a6e09da5098412c9bb3f5528` |

The initial assignment named report SHA256 `1b376a138bb663180baaf9e88822b655c69defe0fa9e607e4d459f01677bf69f`. The working report differed. Coordinator message `msg_2c995a55521b` authorized intermediate report hash `10dd668e87a0ce8a7fecca691f789b95db14135806788da0beaa0722a065b377` after correcting the attribution of the 007 approach/waiting description. Message `msg_d1579324c0c5` then authorized intermediate hash `6e86fbe7efc9c3da6e009c135ce819f5cbca360a5c41d90ece891679d9049e70`. Messages `msg_304e7a208777` and `msg_aa6748ab0bf6` authorized further corrections, followed by final exact-hash authorization `msg_81f75e753772`; I reread it and computed the final hash in the table. This verdict covers that final authorized revision, not the initially assigned bytes, either intermediate revision, or any subsequent revision.

Content evidence was limited to the report, metrics, and the three referenced sanitized `metrics-source.json` files. Repository/Orca operating instructions and coordinator messages supplied task authority only. No original media, generated videos/images, raw responses, result/window/event files, metrics-inputs file, prior answer artifacts, official labels, code, or runtime logs were opened. References to prior drafts and user observations below are attributed statements in the permitted report, not independent inspections. No GPU/model calls or experiment reruns were performed. Only this review file was written.

## Local source hashes

The source paths below identify the permitted local summaries; their underlying media/raw artifacts were not accessed.

| Summary | Local source path | SHA256 | Metric entries |
|---|---|---|---:|
| D: C development | `outputs/mvp0001/EXP-0011/8905b9f968b543f9bc9fd5f8ffcf5f1e/metrics-source.json` | `c0360866a319d6f55e9a21c5952a417ca31bc833d1661dcd40cbde584f5cc1ba` | 7 |
| B: whole-frame full sources | `outputs/mvp0001/EXP-0012/49cad0749df04995bb55727d57946fec/metrics-source.json` | `39d9c2cb48d3332856213911c8d9bdb714881ef925e51e6e185daa1f47b19a69` | 16 |
| C: fixed-ROI full sources | `outputs/mvp0001/EXP-0012/a546b67626e54ef79cdf9bee1c70b3bf/metrics-source.json` | `2626d81a4642f361a9d690da8c2eb5219e4a38f56925db5927efe563a5b4d15d` | 16 |

Independently recomputed SHA256 from file bytes: **3/3 unique files match; 39/39 `source_sha256` references match**. These are summary-file integrity checks. They do not independently authenticate the embedded `source_hash`, `input_hash`, `config_hash`, code SHA, model weights, original media, or cached-response bytes.

## Independent numeric checks

Parsed JSON locally and followed every `source_pointer`. Entries 1–35 resolve by ordinary object-key traversal. For entries 36–39, `sources` is an array rather than an object keyed by source ID; I explicitly selected its unique element whose `source_id` equals the next pointer segment. With that declared interpretation, **39/39 values match exactly**. Literal JSON traversal alone resolves **35/39**; this is a pointer-contract ambiguity, not a numerical discrepancy.

The following tables enumerate the checked values, retaining full JSON precision for times.

| C development metric (entries 1–7) | Value |
|---|---:|
| Input records | 6 |
| New generations | 5 |
| Reused responses | 1 |
| Newly generated tokens | 475 |
| Generation seconds | 18.230874929009588 |
| Queue attempt seconds | 29.064964294433594 |
| Wrapper seconds | 30.591328209993662 |

| Full-source metric (B entries 8–21; C entries 22–35) | B | C |
|---|---:|---:|
| Scheduled windows | 172 | 172 |
| New generations | 171 | 120 |
| Reused records | 0 | 51 |
| Insufficient-input records | 1 | 1 |
| Newly generated tokens | 16238 | 10773 |
| Generation seconds | 504.86880223607295 | 325.554145382921 |
| Sources reporting EOF | 3 | 3 |
| Candidate-labelled windows | 34 | 38 |
| Contact-review-labelled windows | 0 | 3 |
| Parse-failed windows | 3 | 2 |
| Queue attempt seconds | 751.6433641910553 | 622.9014799594879 |
| Wrapper seconds | 787.4492428270023 | 653.5855527069943 |
| Total device peak used, MiB | 7020.0 | 6877.0 |
| Minimum device free, MiB | 3034.0 | 3177.0 |

| Source-specific candidate-labelled windows (entries 36–39) | B | C |
|---|---:|---:|
| E01_007 / 56 scheduled windows | 7 | 9 |
| E01_030 / 65 scheduled windows | 18 | 20 |

Additional arithmetic was checked from the permitted summaries:

- Development: `5 + 1 = 6` records; `88 + 82 + 101 + 95 + 0 + 109 = 475` newly generated tokens. The five non-null generation durations sum to `18.230874929009588` seconds. Five records report strict parse success and six report postprocessed parse success; the reused clip05 is the exception to strict success. Neither parser result establishes action correctness.
- Full-source scheduling: `56 + 51 + 65 = 172` for each configuration; B `171 + 0 + 1 = 172`, C `120 + 51 + 1 = 172`.
- B state totals: candidates `7 + 9 + 18 = 34`, other `48 + 40 + 46 = 134`, parse failures `1 + 2 + 0 = 3`, insufficient `1`; `34 + 134 + 3 + 1 = 172`.
- C state totals: candidates `9 + 9 + 20 = 38`, other `47 + 40 + 41 = 128`, parse failures `2`, contact review `3`, insufficient `1`; `38 + 128 + 2 + 3 + 1 = 172`. Every individual source's state counts also sum to its completed-window count.
- Each configuration has three source records with `eof_reached=true` and `functional_success=true`, consistent with the aggregate flags and EOF count. This independently checks summary consistency, not actual decoded EOF or event completeness.
- Evidence counts in the report match the summary: B `4 + 4 + 4 = 12`; C `7 + 4 + 6 = 17`. Existence, playability, content, deduplication quality, and the meaning of “new” evidence were not checked.
- Each queue duration equals `finished_at - started_at` exactly at parsed numeric precision. The three recorded queue intervals do not overlap. All reported queue, wrapper, and generation times round correctly to the report's three decimals. Wrapper duration has no independent start/end pair here.
- Recorded start-gate free memory is 8284/8293/8219 MiB, each above the claimed 6144 MiB threshold. Device peak/free pairs are 6690/3364, 7020/3034, and 6877/3177 MiB. These are whole-device summary observations, not isolated model VRAM measurements or independently inspected GPU samples.
- C total response tokens `16148` minus new tokens `10773` equals `5375` tokens attributed to reuse; development `569 - 475 = 94`. Reused response lengths must not be charged as new generation or counted as additional independent trials.

Full-source generation time and token totals are copied consistently into metrics but cannot be independently re-summed from per-call data: those data are absent from the allowed summaries. This is a narrower check than the development per-clip re-summation.

Reproduction rule for the four source-specific values: after loading `summary["sources"]`, require exactly one row satisfying `row["source_id"] == pointer[1]`, then traverse the remaining keys. Do not silently interpret these paths as standard JSON Pointer paths or use an arbitrary matching row.

## Findings, corrections, and residual limits

The intermediate review recommendation was `needs_revision`. The final report addresses the actionable wording and reproducibility findings as follows; absent underlying evidence remains a limit rather than an independently verified claim.

1. **Input-measurement location corrected.** Earlier revisions claimed detailed input times, resize, visual tokens, and condition-specific frame ranges were in the metrics. The final report correctly says the public metrics contain only an overall `processor_observed_frames_range: [3, 10]`, with no separated B/C ranges. It explicitly attributes full-source ROI 4–10 to the worker and says this is not independently reproducible here. Neither full-source summary contains observed-frame ranges or the detailed processor measurements. Development per-clip values cannot substantiate full-source ranges. The corrected attribution is acceptable; the original location claim was inaccurate for the permitted evidence bundle.

2. **Source-ID selector convention documented.** Entries 36–39 address source IDs within a `sources` array. The final report explicitly documents the unique-source-ID selection rule and distinguishes 35/39 ordinary object traversals from 39/39 values under that rule. This resolves the reproducibility-contract omission without changing the metrics. Consumers still must implement the selector explicitly; these are not standard JSON Pointer array paths.

3. **007 uncertainty and spatial/temporal distinction corrected.** Earlier text called 007 ordinary approach, asked a question presupposing no crossing, and described ROI as reducing a temporal input range. The final version says behavior is unresolved, asks what motion is actually visible, and states that window width/stride remain unchanged. It retains approach/waiting only as an attributed earlier draft, not a verified negative label. These corrections resolve the misleading wording without supplying new behavioral evidence.

4. **Execution and provenance remain explicitly attributed, not independently proven.** Three distinct job IDs, successful exit codes, sequential timestamps, common settings, and EOF/functional flags are present. These support a reported successful execution path. They do not prove the absence of other attempts/OOMs, all runtime gates, unchanged questions, lack of label/candidate leakage, exact cached-input/response identity, pinned model-file hashes, test counts/timings, actual MP4 persistence, viewer availability, or Git publication exclusions. The report's 47/75 tests and one skip are worker-reported, not rerun or independently confirmed. The final report explicitly makes this distinction in its validation and independent-review-scope sections; its headline execution completion must be read with that qualification.

5. **Detailed scene intervals are not reproducible within this review.** The allowed summaries provide counts, not candidate intervals, tail timestamps/frame counts, or action text such as `stepping_over_boundary`. The report's nearest-candidate/no-overlap assertion for 007, 030 interval endpoints, one-observation EOF tail, 006 ROI exclusion, and 031 contact description remain attributed assertions. The final report explicitly identifies interval/action descriptions as worker-transcribed and not independently reverified from these aggregates. Their absence from this evidence bundle is not proof that they are false. Verifying them would require separately authorized sanitized details or human local review, not opening prohibited files during this task.

## Scope and remaining behavioral uncertainty

The central separation between software success, behavior performance, and adoption is appropriate. EOF means the software reports reaching the end of an input; it does not mean every person completed a crossing or that any candidate is correct. `observed_other` is not a verified normal/negative label; `candidate` and `contact_review` are not confirmed actions; parse failures and insufficient input remain unresolved. Overlapping 5-second windows are dependent observations, not distinct people or independent event trials. No final accuracy, F1, FPR, precision/recall, detection-success rate, or false-alarm rate is supported.

**007:** The report attributes abrupt box expansion at 56.633→56.667 seconds without corresponding visible vertical movement to the user, while attributing approach/waiting to an earlier draft. Neither account was re-inspected. C's reported 52.5–57.5-second candidate is a review target, not established improvement or false positive; absence of a reported overlapping B candidate is not established failure. The normal/negative status and actual motion remain unresolved.

**030 crossing and EOF:** The user reportedly observed three people crossing near 90 seconds; individual identities, precise onset, completion, and occluded actions remain uncertain. A model interval including 90 seconds cannot confirm the explanation or count correctly recognized people. The summaries support one insufficient-input state in each configuration but do not locate it in time. The report's EOF placement and adjacent C candidate remain unverified; neither EOF success nor that candidate proves all crossings completed.

**C4/E01_013 fallback:** C records 51 reuses overall and E01_013 has 51 windows with the same state counts as B. This is consistent with the report's fallback account but does not prove which bytes were reused or the exact-input checks. It is not an independent ROI experiment on C4, a second independent performance sample, or evidence of ROI superiority. Prior exposure and camera/session limitations remain. C's lower total generation/wrapper times include reuse, so they do not isolate a causal ROI speedup. Device-wide memory differences also cannot isolate model memory efficiency.

**A and development clips:** Cached CV/ByteTrack output has different semantics and was not rerun or inspected. The report correctly avoids a joint accuracy ranking. Six development clips and three full sources do not establish held-out camera/session generalization; clip03's reported out-of-ROI activity cannot certify in-ROI normal-behavior discrimination. Clip06 does not establish an independently verified classification of 031 contact.

## Recommendation

Approve this exact report/metrics revision as a scoped, internally consistent execution-summary comparison with the limitations above. No unresolved arithmetic mismatch or remaining unqualified input-location/action-certainty claim was found after the final corrections. Retain the 39-value agreement and three-file hash agreement as a data-integrity result under the documented array-selector rule. Behavior validation and automatic adoption remain on hold: human local scene review and an independent evaluation design are necessary for behavior conclusions and are not fulfilled by this document. Any subsequent report/metrics revision requires its own hash binding before this approval can be applied.
