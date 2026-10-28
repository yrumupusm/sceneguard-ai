# MVP-0001 evaluation scope — frozen before inference

2026-10-28. This is an evaluation contract, not ground truth or a result. The coordinator freezes the commit and SHA256 of [the manifest](../../configs/mvp0001_eval_manifest.json) before inference. The [bounded plan](../experiments/MVP-0001-plan.md) remains authoritative. Manifest source hashes come from existing local text/numeric metadata; actual source rehash belongs to execution preflight. No new pixel inspection was performed.

## Evidence and split

The six existing development clips keep their exact EXP7 selection intervals. These are input bounds, not precise action labels. Human observations, Codex drafts and unresolved meaning are separate fields. Prior approximate times are retained as approximate; official frame times do not replace person-level action onset or completion.

| Input | Evaluation role and limits |
| --- | --- |
| clip01, 007 [54,59) | Prior approach/waiting draft and local box-change observation; not a fully human-labeled negative. |
| clip02, 030 [88,93) | User explicitly reported original-scene inspection: around 84s three people stand/approach; around 90s three people climb over the gate. Prior Codex draft adds body-rise detail; individual completion and overlapping identities remain unresolved. |
| clip03, 006 [120,125) | User-proposed late passage candidate; outside historical C3 ROI. No event under ROI cropping cannot count as in-ROI normal discrimination. |
| clip04, 007 [63,68) | Prior body-rise draft; occlusion and precise completion unresolved. |
| clip05, 001 [61,66) | Prior body-rise draft; C1 remains uncalibrated full-screen fallback. |
| clip06, 031 [31,36) | User approximate contact around 33 seconds; distant/occluded contact is not climbing. Full-video incomplete-group observation is not an all-person negative label. |
| Full 007 / 030 | Development, entire original sources through EOF; known anchors may diagnose failures after execution but never select inference windows. |
| Full 013 | Reserved C4 diagnostic validation; earlier scene/official-interval audit exposure, no recent-setting selection, no blind/new-site claim. No tuning on its result. |
| 039 / 045 | Same C4 group, reserved and excluded from this execution; cannot become independent test samples. |

The 030 user observation was supplied to this reviewer by coordinator native message `msg_5f34fa10853b` at 2026-10-28 10:38:07 UTC, quoting the prior conversation's meaning. The original message date is unknown here; this reviewer has not independently read that original message. The same relay records FCOS final counts of 3 near 84s and 0 near 90s, with cause unconfirmed. Those detector counts are distinct from the user's action observation. Preserve the action observation as user evidence rather than relabeling everything as a Codex draft; it establishes neither exact onset, confirmed identities, three independent events nor opposite-side completion. This pre-inference provenance correction changes no selected clip, camera or parameter.

C3 contains 006/007. C1/C3/C4/C6 school-site independence is unresolved; camera groups do not prove distinct sites. C7 also has no certified independent-site relationship. C3/C6/C7 reuse historical PTS0 background ROIs without new event/person crops. C1/C4 use full-screen fallback, which cannot validate benefits of ROI calibration on unseen cameras. Preserve official labels, prior 0/1-based ambiguity and 006's frame-count discrepancy. Verified non-event duration remains **0 seconds**. Unreviewed and outside-label time is never automatically negative.

## Fixed comparison and behavior reading

A reuses old CV/ByteTrack C caches and EXP6 states, with no detector/tracker run and no common action-classification accuracy ranking. B preserves whole-frame Qwen EXP8/10 development results; its existing pixel-budget contrast consumes its improvement. C changes only fixed background region for the same Qwen, with baseline and at most one evidence-led global improvement frozen before execution. Three methods maximum, no planned new weights, one error retry per job. A crop benefit is an input/preprocessing contrast, not proof of a generally superior model.

Keep the neutral common prompt, parser, generation settings, native PTS and frame choices fixed across B/C. Evaluate raw text as well as parsed objects: format validity, action-word presence and a long explanation cannot establish correct action. Compare meaning to the stated prior evidence as consistent, partial, inconsistent or unresolved; explain the reason. Unsupported completion, invented scene/action details, contact-to-climb escalation, missed body-rise drafts and appropriate uncertainty are distinct findings. An evidence-text completion claim is still not human-confirmed completion. Blanket abstention does not satisfy action discrimination. No accuracy, precision/recall/F1, FPR, hourly false positives or ground-truth onset-delay score is permitted without confirmed labels.

## Independent acceptance gates

1. **Automated tests:** native-PTS ordering and causality; 5-second windows, 2.5-second stride, approximately 2fps first-at-or-after sampling; EOF tails and padding; inference/evaluation separation; unknown and parsing-failure handling; deduplication retaining raw windows; real output timing; canonical queue lease and preservation of prior outputs. CPU fixtures establish implementation behavior only.
2. **Functional integration:** process all three full sources to observed EOF without event-time arguments, save all window responses and parsing/timing records, retain candidate/contact/unknown states, merge overlapping same-camera same-action groups without deleting raw records, and save local source-context evidence. Record actual interruption/partial output if any source fails. Groups are review units, not verified distinct people/events.
3. **Action performance:** independently assess whether approach, body-rise and uncertain contact are meaningfully distinguished without completion inflation. Report limitations even if tests and three-source EOF integration pass. Adoption may remain on hold for every method.
4. **Delivery:** coordinator owns exact native assignments, source-bound public reports/metrics, complete registration, remote GitHub and actual local browser checks; neither an HTTP 200 nor this review certifies delivery.

Periodic full-source analysis bypasses CV gating but still has temporal sampling gaps. Record actual first/last samples, intersample gaps, selected/decoded counts and tail omissions; do not claim that every visible transient was observed. Record window bounds, last used input PTS, source availability/decision PTS, actual first saved UTC and elapsed time, subsequent merge and evidence-write times separately. An EOF-supported or later-frame-supported decision cannot be backdated. File-processing wall time and waiting under real-time playback are different scopes.

After actual outputs, audit every six-clip raw response and full-window integrity, then inspect known failure anchors from EXP5/6 and earlier observations. Anchor times are prior diagnostic coordinates, not newly precise GT. Check report/metric source hashes and real queue receipts. Keep raw responses, local artifact paths, receipts and media outside Git. Consolidate only consequential human questions after outputs, especially ambiguous climbing/completion in clip02 and contact/occlusion in clip06; exhaustive annotation is not a prerequisite for continued bounded development.
