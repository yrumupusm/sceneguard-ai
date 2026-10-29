# EXP-0024 independent review

2026-10-29. **Independent PASS for faithful documentation and interpretation of the supplied user-observation summary only.** The local observation text is a coordinator-authored summary of the user's answer, not a verbatim transcript; the reviewer checks report fidelity to that supplied text and does not independently certify the original answer or image content. This is not an independent image inspection, joint-accuracy assessment, new experiment, model adoption or delivery-completion verdict. The reviewer read text and source code and checked file hashes/JSON; no source media or annotation image was opened, decoded or uploaded, and no model, GPU job, queue operation, environment change or Git action was performed.

Review identity: existing Run `run_3d23462a014a`, Task `task_1f2434dfb816`, Dispatch `ctx_b499f7a6ad59`. The reviewer owns only this document. Registration, web verification, public binding and GitHub delivery remain the coordinator's responsibility.

## Accepted bytes

| Artifact | SHA256 |
| --- | --- |
| [EXP-0024 report](../experiments/EXP-0024-user-pose-review.md) | `11be179d4f4559f5aed4633b43cf00e4ddea577e9ce92888984f6eca9c58914f` |
| [EXP-0024 metrics](../../records/EXP-0024/metrics.json) | `2cf69f32a5d3a970a6d54a9d1f0bd25516adbfff5707a2b3812c32f0b6174066` |
| Coordinator summary of user answer, local only | `6dc4adc89c4717d9f6093e375303f39f6953c2eabfcf2e3af93a6a2c3b66f9c0` |

These hashes were computed independently from current bytes and match the owner's freeze. Any report or metrics byte change requires renewed review/binding.

## User-text fidelity

| Time | Supported interpretation | Required limit retained in report |
| --- | --- | --- |
| 84 s | The user thought all three C6 boxes and their joints looked good. | Qualified, qualitative approval; not confirmation of every COCO17 joint, exact coordinates or climbing-pose performance. |
| 90 s | Of three people climbing the gate, only the rightmost has a box, its joint positions do not fit well, and the other two are missed. | The one row and twelve retained estimates are not twelve correct joints or successful person/pose recovery. |
| 94 s | The user sees one person on the gate and one already across it; full and C6 both return zero rows. | Two visible people are missed according to the user. The observed state of a particular person does not establish completion for everybody, person tracking or a legal judgment. |

The report matches the supplied text without inventing person IDs, detailed occlusion/duplicate/crop-truncation findings, anatomical GT, completion times or a causal explanation for the misses. The local hand-marked image is a user reference, not agent pixel inspection, machine GT or model input. The new AGENTS, CODEX_NEXT_TASK and HANDOFF introductory observations are consistent with this bounded interpretation. Earlier unanswered-review statements remain historical records.

The cited output counts match the preserved EXP-0023 summary: full/C6 rows and retained estimates are 2/24 versus 3/38 at 84 s, 0/0 versus 1/12 at 90 s, and 0/0 versus 0/0 at 94 s. Five new sample calls and one separate warmup belong to EXP-0023; the 90 s full result is reused from EXP-0022. EXP-0024 creates no predictions. Historical technical success and insufficient evidence for climbing behavior are correctly distinguished.

## No intentional one-person cap

Read-only inspection confirms `max_det=300` in [the fixed public kwargs](../../orchestration/batch04_pose_command.py), imported unchanged by the batch05 command and passed to `model.predict` by [the runner](../../batch05_pose/runner.py). The runner's single `Results` requirement means one input image, not one person. [result_rows](../../batch04_pose/api.py) loops over every matched box/keypoint row; [ROI translation](../../batch05_pose/geometry.py) preserves those rows; [the renderer](../../batch05_pose/visuals.py) loops over all stored `persons`. There is no top-one selection in these inspected paths, and the historical 84 s C6 output has three rows.

This supports rejection of an intentional one-person selection/display explanation. It does not establish why the model returned only one person at 90 s or why its joints were misplaced; threshold, pose, occlusion, scale or model-internal causes are not diagnosed by this documentation review.

## Metrics and preservation

The existing metrics validator and independent JSON/source-hash checks pass on the final bytes. Exactly three metrics are recorded: `new_gpu_calls=0` with `sample_n=1` for the documentation operation, `actual_joint_accuracy=null` with `sample_n=0`, and `behavior_f1=null` with `sample_n=0`. All three bind the accepted report SHA. The first denominator is not a person/frame/joint evaluation sample. `execution_status=succeeded` describes this documentation task; it does not certify pose quality. No accuracy, precision, recall, FPR, operational or generalization result is manufactured.

The five protected EXP-0023 files below independently match the coordinator's pre-task baseline. This is a file-preservation check, not a new queue/runtime or image-content audit.

| Preserved artifact | SHA256 |
| --- | --- |
| EXP-0023 report | `0978d472573ac037a268483b8b358b8d8b5b359f7557c372fc621f9a1dab1e36` |
| EXP-0023 metrics | `1143c6d5e7f6587a63047edcf7a711564f7eed5ddb42118c489b4de89ce18070` |
| EXP-0023 independent review | `821d16917c385fcd64ddc01522971da55ca7833cfac48b1d0dcf7258601ce28b` |
| EXP-0023 binding | `d85cc51c6dda4e7b06016e7c4f735b303ced1bd9b5186f9b6e2bda184058ee7d` |
| BATCH-0005 summary | `a197b5247ae9202f65234996304e5ca1c6a18d283a36581d7cbc4808ecf4d910` |

The accepted report/metrics contain non-identifying summaries and provenance, not media, raw person/joint coordinates, weights or credentials. Default adoption, tracking, behavior rules, combination and full267 processing remain held. No additional experiment is authorized by this PASS; final registration and delivery evidence are separate coordinator work.
