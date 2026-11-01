# MVP-ALL initial independent protocol review

2026-11-01. **Verdict: the evidence-based scoring contract and revised execution guards are suitable for a limited, explicitly qualified evaluation; whole-source execution and result approval remain pending.** Initial runner coverage and cached-CPU findings were addressed at the synthetic guard level during this review, as recorded below. This is the requested initial contract deliverable, not the later results review. No current inventory total, completed-source total, actual accuracy, or new-camera generalization is certified here.

Run `run_3d23462a014a`, Task `task_da6ff1a01e73`, Dispatch `ctx_8423d37fbcca`. The reviewer changed only this document and local `runtime/MVP-ALL/review/` artifacts, with no analysis-code edits, GPU work, media upload, model/rule tuning, nested workers, commit, or push. The current checkout was `f05d430458150c9b63e04aa9caf93cb85ee18cae`; the requested analysis baseline is `548ff7098045f9efc5bd2edfd5ce61431a5e210e`. Source hashes, not an uncommitted runner's filename alone, identify the reviewed implementation.

## Scope and evidence

Read the repository instructions, `CODEX_NEXT_TASK.md`, `CODEX_MVP_EVALUATE_ALL.md`, the current `accuracy_evaluation`, `mvp_pipeline`, relevant frontend/native decoder and lifecycle code, and the newly available `scripts/mvp_full_run.py` and `docs/experiments/MVP-ALL-evaluation-protocol.md`. Prior validation comes from `MVP_VALIDATION.md` and `MVP-V1-independent-review.md`; the similarly named `MVP-0002-independent-review.md` concerns the older EXP-0013 comparison, not the current integration. User truth was checked against the AI-Hub user-review/evaluation-plan documents and EXP-0048's explicit later normal-passage review.

The prescribed command passed **26/26 synthetic scorer tests**:

```bash
.venv-cv-batch02/bin/python -m unittest discover -s tests -p test_accuracy_evaluation.py -v
.venv-cv-batch02/bin/python runtime/MVP-ALL/review/contract_probes.py
```

The second command reproduced five focused contract observations using synthetic dictionaries and mocked I/O against the **initial runner**. Its historical JSON/log remain preserved; rerunning its cached-CPU failure assertion against the corrected runner is not expected to pass. It did not analyze CCTV or run inference. Its JSON records the exact source hashes, inputs and outputs. These are review probes, not new production tests or measured behavior examples.

| Reviewed fixed file | SHA256 |
|---|---|
| `sceneguard/accuracy_evaluation.py` | `79c4b947590ee329b120fd19cdf7a2d1840f223c1a39800a58cc481bc01639f8` |
| `sceneguard/mvp_pipeline.py` | `192c9152b063543919dbfd6eef38027e4dbf45c104fcaea03c97d1eef418547e` |
| `sceneguard/video_cards.py` | `e186e6ea37b3a8cd41350d862be5e4931be41d4ebb125919a868c17a6cc4b153` |
| `docs/CODEX_MVP_EVALUATE_ALL.md` | `c76882a13d8b6af51aacb1bb042bc3eb3816865db0a896961e4314af2623e330` |

## Scoring behavior that passed review

- Matching uses actual timestamp lists, same gate, half-open `[start,end)` intervals and maximum-cardinality one-to-one matching. A card's open interval cannot make an event a hit. One card cannot claim two truth incidents; unmatched competing cards become duplicate FPs. Same-gate overlapping truth incidents must first be normalized without looking at predictions.
- Suspicion and confirmation have independent matches. Confirmation evidence must come from each evidence item's actual first confirmation, not the final card's aggregate confirmed status. The pipeline's causal timeline and per-evidence export make this extraction possible; the adapter still must prove it uses them correctly.
- A later TP does not erase an earlier notice in a verified-negative interval. Existing tests exercise both early suspicion and early confirmation. Notification intention PTS is not proof of actual user delivery or measured runtime latency.
- Unreviewed time is not negative. Mixed negative/unreviewed unmatched evidence is unscored, not silently scored as a normal FP. Unknown predictions make headline precision and F1 null; the scorer exposes precision on the scored subset and precision bounds.
- Only complete runs enter detector-only event matching. Failed/unrun sources retain their resolved reference count for separate inventory coverage; they are not successful zero-alert videos. Negative exposure is a union per gate, so overlapping masks are not counted twice; the unit is gate-seconds, not automatically unique video-seconds.
- Unknown onset precision gives null action-detection delay. A difference from an official reference start may still be reported with that explicit label. First-notice correctness and evidence-hit correctness require separate tables even when both exist for one card.

## Concrete findings and required handling

### R1 — Full-source cache validation can omit the first frame

**Reproduced execution-integrity gap**, not a measured failure in an existing source. For a synthetic one-second, native-30fps source with frames at ticks `0..29`, pass only ticks `1..29` into the real `video_cards.validate_cached` with requested `[0,1)`. All normal metadata and clock checks pass and it accepts 29 frames starting at `1/30`. The first-frame test allows a gap equal to one frame interval. `decode_native` then starts from the cache's first timestamp and returns after the cache length; it does not establish that an earlier source frame was included.

The initial runner's explicit-cache preparation already rejects `frames[0]['pts'] != 0`, which mitigates this particular case for those admitted caches. It does not by itself prove whole-source completion for every path, including implicit cache discovery and fresh detection. The initial runner marks `processed_seconds=duration_seconds` solely from successful pipeline status.

**Required acceptance evidence:** independently bind the full decoded source PTS/index sequence to the frames actually processed, including first/last native PTS, frame count, no missing/duplicate frames, and the actual EOF/end-exclusive boundary. Do not change the frozen analysis algorithm to satisfy this review; a runner/adapter guard or explicit non-complete status is sufficient. Escalated early to the coordinator in `msg_452e6b83fbbb`.

### R2 — Initial runner blocks valid cached CPU work on GPU availability

**Reproduced runner bug at the reviewed draft.** `execute()` checks GPU free memory and canonical queue pending work before branching on `row['cache']`. A synthetic `not_run` row with a valid cache and `detector_required=False`, combined with `gpu.available=False`, returns `blocked_gpu_free_below_6144_mib` without invoking the CPU pipeline. The same unconditional queue branch can block cached work for unrelated pending GPU jobs.

GPU/queue resource gates should protect detector work only; cached CPU execution should continue within the existing resource policy. This does not authorize bypassing the queue for new detection. Escalated in `msg_db374d374597`; the local probe uses the real runner function with file writes, reads and GPU inspection mocked. Any revised runner requires a new exact-byte check, and the original probe output must remain as historical evidence.

### R3 — Notice omission is an adapter integrity risk

**Reproduced validation gap, not proof that an actual adapter omitted a notice.** Synthetic truth `[10,20)`, negative mask `[0,10)`, card evidence `[5,12]`, and a suspicion notice at `5` yields TP=1 and false notice=1. Removing only `notifications` leaves TP=1, is accepted by the scorer, and yields false notice=0. The scorer cannot reconstruct upstream notice intentions from this lossy manifest.

The adapter must bind *all* `notification_intents` to the exported incidents and prove no omissions, duplicates, reassignment, or invented PTS. Compare exact kind/incident/time tuples and hash the originating current-run artifact. Do not fabricate a suspicion notice when the pipeline emitted only confirmation; source equality, not a blanket notice requirement, is the rule. Apply the same completeness check to every original candidate decision and every individually confirmed evidence item. Candidate counts, timestamp deduplication counts and ID-to-card ownership should remain auditable locally.

### R4 — Inventory coverage is resolved-only; unresolved references still need a denominator

**Reproduced reporting hazard, not incorrect arithmetic in the named underlying count.** Aggregate one completed TP/resolved event with a second source holding one unresolved event and no predictions. Output is `reference_coverage_across_inventory=1.0`, `inventory_resolved_events=1`, `unresolved_reference_events=1`. Thus the metric is 1/1 resolved references across execution statuses, not 1/2 all known reference records. In normal `evaluate()` output different truth bases are grouped separately, which also prevents treating one group's coverage as the whole inventory's coverage.

Publish resolved references, unresolved reference records and unexecuted references separately, with numerators and denominators. Never label that 1.0 as “100% of all provided events.” If a conservative accounting ratio is added, explain that unresolved counts may still be original person-level annotation records whose incident merging is unestablished; it is not a detector-recall estimate. Timing-unresolved references must not become empty negative videos or disappear through default-zero counts.

### R5 — Required F1 subset/range output is not supplied by the scorer

**Reproduced reporting omission.** A TP card plus an unreviewed unmatched card yields null headline F1, as intended, but the scorer does not emit `f1_on_scored_subset` or F1 bounds, despite the protocol requesting scored-subset results and conservative/optimistic ranges. This is not a reason to fill null with zero or silently ignore the unknown card.

A separate clearly labeled report calculation may supply scored-subset F1 `2TP/(2TP+FP+FN)` without editing the frozen analysis or replacing the original scorer JSON. If broad optimistic/conservative F1 ranges are supplied, state assumptions about unknown predictions, missing reference events and possible duplicate incidents. The existing precision bounds do not resolve unknown truth-event denominators. Alternatively explicitly mark F1 ranges unavailable and record the protocol limitation; do not claim the scorer provides them.

## PTS, label and prior-truth acceptance conditions

1. Keep original label filename/hash, original event frame indices, decoded index/native PTS/time base, and frame-count comparison. Neither average FPS nor `frame/30` proves the mapping. For uncertain 0/1-based indices, preserve both official-reference interpretations or leave precise timing unresolved. Freeze whether an annotation's ending frame is inclusive or exclusive before converting to `[start,end)`; otherwise evidence on that ending frame changes outcome. Do not pick whichever interpretation benefits predictions.
2. Current frontend supports exact constant native 30fps, zero source origin and approved C3/C6 bindings. It rejects incompatible FPS/cameras; an inventory must retain those exclusions. E01_006's known label/decode count mismatch and unsupported native timing are separate reasons, not one interchangeable error. This review has not recounted its current file.
3. Local selected-window `frame_index` is zero-based within the selected partition. For full-source validation compare it against the independently decoded whole-source mapping, not a prior cropped run's indices. Keep exact timestamps rather than display-rounded values for matching; no favorable matching tolerance is added.
4. E01_006's approximate `[119,132)` remains a **non-event candidate** in the user-review record, explicitly not a verified-negative mask. The later explicit EXP-0048 review supports 007 `[84,104)` as normal passage; it does not label 61 people or establish release success. Earlier 007 approach/waiting and other user-confirmed windows require their own provenance and exact review scope.
5. Prior 007/030 integration windows and the initial audit sources are development material. Four successful prior windows are not four independent sources: the 007 normal window overlaps a development interval, and 007 45–48 seconds had previous use. No prior result can substitute for current whole-source execution or justify a blind-test label. Historical window counts/times in prior documents are not current inventory results.
6. Official intrusion intervals are reference incident annotations, not physical completion counts or legal authorization labels. The 031 record explicitly says not all people completed by EOF. Approximate human observations do not become precise onset labels; official-reference and reviewed manifests remain separate.
7. Preserve all unresolved evidence within confirmed cards. In particular, earlier validation documented unresolved later 030 evidence despite the card being confirmed. Observation closure and an alert-free normal passage are not suspicion release; actual release remains unevaluated unless a real reviewed release case is supplied.

## Revised wrappers checked before initial settlement

The runner and adapter arrived and were revised while this review was active. The following checks are scoped to the bytes recorded here, not to subsequent edits or eventual execution:

| Revised file | SHA256 |
|---|---|
| `scripts/mvp_full_run.py` | `8e3bdfa5859bbdb4d95bb1ecd817c5a7f3f60c77d86a516b2b7be799fbade9de` |
| `scripts/mvp_full_evaluation_adapter.py` | `3ae615d50f01dce42e494b45fd6e2ee84f845bd2924fe3b1d7ee2dd010729aa9` |

- **R1 mitigation:** the runner now decodes a complete source clock, compares admitted caches against every native timestamp, and compares detector/tracker/image-path/frontend-render/final-render clocks before retaining complete status. Integrity failure becomes a failed ledger row. The adapter separately checks source count, native partition, whole request, duration and upstream hashes. The permissive frozen frontend validator remains unchanged, so guard receipts must be required by the final review.
- **R2 correction:** the runner now applies low-memory and pending-queue blocking only when `detector_required` is true. Independently ran the seven `test_mvp_full_run.py` tests: all pass, including admission of cached CPU work with both a busy GPU and another queued/running job, rejection of missing first/last frame, changed PTS and changed indices. The worker-local copy of those same seven tests also passed; these are **seven unique tests**, not fourteen.
- **Frozen code:** directly ran the revised runner's read-only `frozen_analysis_bytes()` check. All 89 enumerated analysis/queue dependencies match frozen Git bytes. The wrapper permits a later documentation/wrapper commit before preparation but pins actual execution HEAD and all enumerated bytes during execution. This check does not certify model files, complete inventory or actual execution; those have separate bindings.
- **R3 mitigation:** the adapter now checks card notification flags, exact kind/card ownership, confirmation consistency and complete notification-intent equality against the timeline. The independent local adapter check preserved three original candidates, one individually confirmed candidate and two first notices, and rejected removal of the first suspicion notice. It produced the intended synthetic TP plus early false suspicion without propagating confirmation to the two unresolved candidates. It also checked both index interpretations, unresolved frame-count mismatch and existing q03/late-007 masks while excluding the 006 candidate mask.
- The adapter conservatively leaves reviewed positive *windows* unresolved rather than inventing exact continuous event boundaries. It reads negative windows from prior user records and keeps official-reference variants separate. Those choices support a qualified reviewed-negative notice analysis, not reviewed positive-event recall.
- **Residual R1 inventory-label caveat:** at this inspected adapter revision `inspect_caches()` still derives `whole_source_match` from the permissive frontend validator alone. The same missing-frame counterexample can therefore mislabel a candidate cache in an inventory, even though revised execution/adaptation reject an incomplete result. Require the same decoded-clock equality before publishing that inventory flag. This caveat was sent to the coordinator; no actual inventory cache was found incorrect by this review.

The adapter's first synthetic review attempt correctly rejected an incomplete review fixture that lacked newly required card confirmation metadata; the failure log is preserved. The fixture was completed with the actual exported card/timeline schema and the check passed, including the explicit removed-notice rejection. No production output was edited to pass a test. R4/R5 remain report obligations, and the official endpoint convention remains an explicitly frozen reference assumption, not a verified annotation semantics claim.

Immediately before settlement the production adapter tests became available. Their initial run was **27 passes and one error among 28 tests**: the early-notice test addressed `tp` at the top level instead of `counts.tp`. This assertion-path error was escalated as `msg_22763fb29176` and the owner corrected it; the reviewer reran the suite and **28/28 passed**. The original failure and corrected-run logs are both retained. The later adapter SHA256 `acb7012e8fd7da14764e06230d591091791c565785d3b6d0285c46c3599622e9` also adds the decoded native-partition guard to `inspect_caches()`, addressing the inventory-flag caveat above by code inspection. The corrected test file SHA256 is `967174cd5870e264d3e6d82c8c396934b060887ca6ab6b5f1fcaa0e554ae5dbc`. These revisions remain evaluation guards only; no analysis-module change was made.

## What is still required for the later results review

At final initial-review checkpoint the adapter and revised runner were inspected, but the completed inventory, frozen truth outputs, normalized evaluation manifests and whole-source outcomes were not available for independent inspection. They are not approved executable results. No source count, support count, decoded total or event total is assumed from historical “45” or any expected subtotal. The coordinator confirmed that actual results/report review is a separate dispatch; reported progress or resource availability is not substituted for inspection here.

The later review must bind the actual inventory and no-truth execution list; reject duplicate source SHA entries in a report; check camera/site/prior-use provenance; audit source/label/decode hashes and exact full coverage; verify frozen code/settings and canonical queue receipts where applicable; compare every candidate, per-evidence confirmation and notification intent against current-run outputs; then recompute official 0/1-based and reviewed scores separately. Include misses without prediction-selected review, unresolved counts, complete/partial/unsupported/failed/not_run coverage, first-notice errors with verified exposure, runtime costs, and unsupported/ambiguous cases. Actual browser verification is a separate delivery fact.

The initial contract review is complete with these actionable qualifications. **Final results, runner revisions and adapter acceptance require a separate review; this document does not certify them.**
