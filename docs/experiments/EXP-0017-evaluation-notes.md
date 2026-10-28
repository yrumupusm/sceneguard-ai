# EXP-0017 CPU evaluation notes

The frozen EXP-0016 comparison was evaluated against four successful resumed jobs: revised q full-frame and fixed-ROI, six windows each, and original/revised v full-frame, four windows each. The evaluator consumes local JSON, expanded text and saved processor RGB bytes only; it imports no model, decoder, processor, numpy or queue code. The unchanged pure MVP classification and common response parser supply output states. No inference, queue mutation, prompt/config/runner change, media upload, commit or push was performed by this evaluator worker.

The publishable result is [comparison.json](../../records/EXP-0017/comparison.json). It contains model claims, user references, trace checks, counts and measurements; no raw response text, token IDs, images or absolute paths. The exact local path/hash inventory of 131 consumed files remains ignored at `runtime/EXP-0017/evaluation-input-index.json`.

## Reproduction

```bash
python3 -B -m unittest tests_mvp.test_exp0017_evaluation -v
python3 -B scripts/evaluate_exp0017.py
```

The default input is the completed `runtime/EXP-0017/run-index.json`. Alternatively supply all four explicit output roots using `--q-full-frame`, `--q-fixed-roi`, `--v-original`, `--v-revised`; both historical baseline roots can be supplied using `--baseline-b` and `--baseline-c`. Labels are read separately from the model inputs. Frozen public configs and EXP-0015 records are hash pinned. An identical rerun preserves output bytes and modification times; a differing existing comparison is refused. Source bytes are rechecked before writing. The CLI only writes its comparison and ignored local input index.

**21 synthetic CPU contract tests passed.** They include changed frame/source/native PTS, prompt hash and expanded text, generation settings despite rehashed config, processor pixels despite equal metadata, missing results, unfinished source coverage, stored-parser disagreement, source mutation, malformed metadata, raw JSON versus whole-response fence parsing, and completion/reference separation. Parse failures remain in denominators. Indeterminate is never converted into a confirmed negative; candidate plus indeterminate remains candidate. Removing every candidate while losing q04 cannot pass the regression guard.

## Trace findings and limits

For q, exact q01–q06 case/source/window/interval mappings come from the pinned EXP-0015 user revision. Historical EXP-0013 loading, run, input and result files are reopened and checked against its hashes. New source hashes, native PTS/time bases and decoded original RGB hashes match those records. All recorded visual processor metadata, including crop hash, dimensions, frame order, timestamp coordinates and size, match the historical output after excluding text input-token count. The newly saved processor RGB artifacts have the recorded shapes.

Historical q input files lack source hash and ROI; their pinned source-run metadata supplies these fields. Historical q processor RGB and expanded prompts were not saved. Their actual pixel/tensor equality and expanded text parity therefore cannot be established from this evaluation. This is recorded as a limit, rather than claiming that matching window names or metadata prove identical model tensors. Source videos and weights were not reopened or redecoded by the evaluator.

For v, each input matches the frozen original-source manifest's native timing, decoded indices and per-frame RGB hashes. Original and revised inputs are identical except prompt hash. Model-file bindings, generation, pipeline, package/runtime and processor metadata match. Saved processor RGB payloads and NPY bytes match exactly. Replacing the original anonymous-ID prompt with the revised anonymous-ID prompt reproduces the complete revised expanded text, establishing no other saved text difference. Unrecorded internal processor tensors were not recomputed. Source summaries decode through EOF and cover each frozen window exactly, independently of manifest listing order.

## Descriptive behavior

Every state below is a parsed model claim, not ground truth. `other` means the unchanged classifier emitted neither candidate nor indeterminate, not that the model correctly established a negative.

| Window | Full-frame q old → new | Fixed-ROI q old → new |
| --- | --- | --- |
| q01 | other → other | other → other |
| q02 | candidate → candidate | other → other |
| q03 | other → candidate | candidate → candidate |
| q04 | other → other | candidate → candidate |
| q05 | candidate → candidate | candidate → candidate |
| q06 | other → other | other → indeterminate |

Full-frame candidates increase from 2 to 3; q04 attempt/progress remains missed and q03 gains a candidate despite its no-attempt reference. Fixed-ROI candidates remain 3; q04 retains a candidate, while q06 becomes indeterminate. Neither view supports the intended improvement. q04 completion was not observed before clip end and is distinct from its attempt/progress label.

| Window | User reference | Original → revised |
| --- | --- | --- |
| v01 | attempt/progress; completion not assessed | candidate → indeterminate |
| v02 | non-event | other → other |
| v03 | attempt/progress in gap beside gate; boundary association ambiguous; completion not assessed | other → other |
| v04 | non-event | candidate → candidate |

The v candidate total falls from 2 to 1 because v01 becomes indeterminate, while v04's candidate persists and v03 has no candidate in either condition. The lower count is not success. v01/v02 share E01_004 and v03/v04 share E01_021: four windows form two source groups, without demonstrated camera/site independence or a blind held-out test. Completion for v01/v03 remains `not_assessed`, regardless of model wording. Semantic conflict flags are drafts against existing user observations, without new media adjudication; final semantic discussion belongs to the coordinator.

All 32 old/new window results pass common parsing. Strict raw JSON counts are q full-frame 3/6 → 3/6, q ROI 6/6 → 6/6, and v 2/4 → 2/4. Whole-response JSON fence removal is nonsemantic parsing, distinct from strict compliance. No actual result is missing or parse-failed.

## Matching-window costs

These are saved inference measurements for the same selected windows, not CPU evaluator timings or whole-video wall times.

| Group | Generation seconds old → new | Output token counts old → new | Preparation seconds old → new |
| --- | --- | --- | --- |
| q full-frame, six windows | 16.892447 → 23.572352 | 531 → 655 | 0.655715 → 0.728969 |
| q fixed-ROI, six windows | 18.133003 → 22.083944 | 593 → 647 | 0.307505 → 0.335114 |
| v full-frame, four windows | 14.653707 → 16.198070 | 389 → 488 | 0.408517 → 0.385771 |

Per-window and maximum allocated/reserved GPU bytes are in the comparison. Per-job model loading is separate: new q full-frame 3.458207 s, q ROI 2.308833 s, original v 2.387542 s and revised v 2.299523 s. Historical q loading is also retained separately. Decoder and queue overhead are not measured here; background GPU load was uncontrolled. These timings establish no causal speed improvement or real-time suitability.

Accuracy, precision, recall, F1, FPR and hourly false alarms remain null. No automatic adoption decision is made. The coordinator owns the final report, metrics, independent review and delivery.

## Exact artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| Evaluator | `dbb1c35e6dc4205dd8a6091c00046a2d99ea0058c95a892a682758dfe7b2975f` |
| Contract tests | `fd0948e295ca5a9961eef1ce553cc15c4d71b66db9308ba1a74c83b7d13cad90` |
| Comparison | `a4003df7447b70fc591dfabb4251e0704de0b3f53a5ef183b9211c1ded8a9b3c` |
| Final execution index, local only | `b5cd2d62d4c451d0b59505f77715e268c6440c6ac557d393e143d8861d7e33bb` |
| Consumed-file index, local only | `b7327a9ce68041af5fb95be1052ea5d21e0c9e9758aab3d787fa782e469e6565` |
