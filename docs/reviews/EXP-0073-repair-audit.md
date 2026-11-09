# EXP-0073 bounded annotation repair audit

2026-11-09. **Accepted for bounded coordinate review; no critical bug found in the audited outputs.** Independent arithmetic, change-set, provenance and byte checks passed. This is not visual semantic validation, person ground truth, a detector/NMS policy, a training release, or a performance result.

The audit read `AGENTS.md` and `WEB_REVIEW_WORKFLOW.md` and ran the prescribed read-only `pending --include-acknowledged` query successfully: zero outstanding requests. All three EXP-0072 answers in the supplied snapshot matched the current read-only review store exactly, at answer version 1 and request version 4 with status `applied`. Their original registered document/media source bindings were independently recomputed and matched, and their reviewed comparison-media hashes matched the original drafts. This audit did not acknowledge, resolve, edit or create any review requests.

The independently written checker did not import or execute the repair script. It checked the actual `box-repairs-v1` artifacts, the script hash, every one of the 16 declared input bindings, the editor-package hash, and all 17 output files. It also checked the three original source and label byte hashes, including the archived R03 members, without decoding media pixels. Detailed checks and hashes are local in `outputs/model-comparison/exp0073/repair-audit-v1/`; the compact durable record is [repair-audit.json](../../records/EXP-0073/repair-audit.json).

| Case | Input boxes | Output boxes | Change |
| --- | ---: | ---: | --- |
| R01 / train / reservation 19 | 29 | 27 | Three fragments replaced by one unconfirmed envelope on frame 60 |
| R02 / train / reservation 19 | 38 | 30 | Twelve right-side fragments replaced by four unconfirmed envelopes; frame 70 held intact |
| R03 / development / reservation 01 | 129 | 112 | Seventeen location-selected proposals removed across thirteen frames |
| Total / 72 frames | 196 | 169 | `196 - 17 - 15 + 5 = 169` |

All **164 non-target boxes** retain their exact original numeric coordinates, original proposal indices, deterministic IDs and retained-unconfirmed origin. Every input frame retains its original decoded index, source PTS and RGB-hash metadata; no frame is added, dropped or reordered. Original confidence/class metadata remains in the immutable, hash-bound source drafts rather than being copied into the repaired box schema.

| User seconds | Case / decoded index | Exact native PTS | Tick at time base 1/12288 | Disposition |
| ---: | --- | --- | ---: | --- |
| 20.000 | R01 / 60 | 60/3 = 20 | 245760 | Unconfirmed envelope |
| 23.333 | R02 / 70 | 70/3 | 286720 | Entire frame held; existing boxes retained |
| 23.667 | R02 / 71 | 71/3 | 290816 | Unconfirmed envelope |
| 24.000 | R02 / 72 | 72/3 = 24 | 294912 | Unconfirmed envelope |
| 24.333 | R02 / 73 | 73/3 | 299008 | Unconfirmed envelope |
| 25.000 | R02 / 75 | 75/3 = 25 | 307200 | Unconfirmed envelope |

The six mappings match the displayed milliseconds exactly after rounding; the maximum decimal-rounding difference is 1/3000 second. Compressed video packet metadata independently confirms all 72 selected native PTS values, 3 FPS, start time zero and native 1920×1080 dimensions. No pixel decoding or fresh RGB-digest calculation was performed by this audit; it compared RGB hashes as stored metadata.

R03 deletion is confined to boxes fully contained in the user-identified upper-path selector `[720,35,760,90]` in native pixels. The thirteen affected decoded indices and deletion counts are `168:1, 176:1, 178:1, 180:2, 181:1, 182:2, 183:1, 184:1, 185:1, 186:2, 187:2, 188:1, 190:1`. Every other R03 box is unchanged. The selector implements this bounded manual annotation edit; it neither labels the whole region empty nor defines a runtime filter. Its semantic appropriateness comes from the supplied user observation and task specification, not an independent visual finding.

R01 frame 60 uses the exact min/max envelope of its three original model fragments and the **unverified original actor reference**, drawn from origin1 frame 61. That reference does not certify actor alignment, frame-origin correctness or person completeness. R02 frames 71/72/73/75 use only their respective 4/3/2/3 right-side proposals; the other person's box is preserved exactly. The user-confirmed same-person observation supplies the R02 semantic basis, while every new coordinate remains unconfirmed. All five replacements have `coordinate_confirmed=false`, assistant-proposal origins and confirmation-required frame flags. The editor package contains exactly those five source frames, exact proposal coordinates, source identities, image-byte hashes and train reservations.

R02 frame 70 preserves every proposal and has `whole_frame_hold=true` with reason `right_edge_person_candidate_uncertain_not_negative`. It is absent from the five coordinate-review frames and has no deletion, replacement, empty-background designation, complete-ground-truth flag or training release. Its uncertainty is not converted into a negative label.

The prior EXP-0067/0071 manifests match their frozen pre-EXP-0072 hashes and still contain exactly 75+122=197 unique reviewed frames. All 394 referenced image/label files match those manifests' recorded byte hashes. None overlaps the new 72 source/time pairs. The EXP-0070 split proposal matches its pre-EXP-0072 frozen hash, all eight inherited protected bindings match, and the three case source/split/reservation fields agree across the old manifest, split proposal and repaired output. R01/R02 remain in their shared train reservation; R03 remains development. Protected raw corpora and the previous 432-source inventory were not reaudited.

Static code review found annotation rewriting, source verification and preview rendering, with no detector invocation, NMS-policy change, tracking, GPU work or training invocation. The output flags consistently report zero new GT frames and no training release. The two preview videos are explicitly labelled still-image sequences at 1 FPS, with the single R01 still repeated three times; this audit hashed their bytes but did not verify playback, visible content or frame count by decoding.

The script is specific to the supplied frozen inputs. It checks observation/request/version/hash equality but does not itself recompute the live registered review-source binding or validate changed observation semantics before using hard-coded target indices and selectors. The independent audit supplied these binding checks for this actual run; broader reuse would need equivalent guards. No fix to source code was made or required for this bounded result.

Validation: **1,346 checks passed, zero failed**, using the existing lab Python and a subprocess of the existing `.venv` solely for compressed packet metadata. Initial audit-tool attempts encountered Python 3.10 `hashlib.file_digest` incompatibility, missing PyAV in the lab environment, and absent `ffprobe`; the checker was adjusted to streaming SHA256 and the existing PyAV environment, then completed successfully. These were audit-environment issues, not failures of repair generation. New coordinates still require user confirmation; visual fit, person completeness, action/identity labels, independent-event claims, browser delivery and final registration remain outside this worker's acceptance.

Reproduce locally:

```sh
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python outputs/model-comparison/exp0073/repair-audit-v1/audit.py
```
