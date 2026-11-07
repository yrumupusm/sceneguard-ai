# EXP-0066 canonical execution: eight models

**Current native-boxes-v3 wave: 8/8 smokes and 8/8 full45 passes succeeded.** Historical timeout-v2 STM failure and invalid EVAD geometry remain preserved with their original statuses; they are excluded from current successful full-pass proofs.

Actual execution state: `all8_raw_execution_verified_handoff_ready`. This dispatch has 24 completed canonical attempts, including 8 completed full45 stages; control state records 8 started full45 attempts. Queue observed 124 jobs / 124 attempts with statuses `{'failed': 6, 'succeeded': 118}`. Smoke authorization does not authorize full45; each full pass requires the coordinator's separate GO and an actual successful same-source smoke. Human person recovery, climbing precision/recall and intrusion metrics remain null.

Active Run `run_3d23462a014a`, Task `task_00aa7de4d1c9`, Dispatch `ctx_9d72cfbeabc7`, owner `term_7f1bc18c-bed6-4684-9360-b82bb35be69c`. Earlier settled tasks were not reused. WEB `pending --include-acknowledged` succeeded with zero pending answers at start, source resumes including native-boxes-v3, and the final handoff check. The nine existing EXP-0065 answers remain confined to their actual reviewed contexts; no review DB was modified.

## Authority and revision history

- `initial-v1`: root GO `msg_7ab3e549265b`, HEAD `5c7b88f743fa5e13728e41c315f48167d308a70b`, readiness SHA `d03365fcc1ecc8692302a32f71ee73f7dd8dcca9edd049557016f7d56535a268`. Five encoder/R3D smokes succeeded. Original true authorization flags were explicitly delegated by root.
- Initial conditional full GO `msg_ccfc335cd3df` / cap agreement `msg_fee735a5f91d` produced no full attempt. Root expanded this same Task to joint3 at HEAD350998b (`msg_b751963aca48`), but only CPU preparation occurred before hold `msg_166ac3cd26e3`.
- `timeout-v2`: root GO `msg_4b2d6ced885d`, HEAD `de8c22bc1df8c77269b035b3e5df51f8bf9a94ce`, review SHA `b7e2317892ebf25e9a3a72cd6411236345c6a73b4989cdbf6d83abe0c02070f3`. Model-compare timeout cap became14400; numerical inputs remained fixed. EVAD-B/L completed technically but their coordinates were invalid; STM failed the final UTF8 input check after seven saved forwards. No v2 encoder/full attempts occurred. EVAD-B full GO `msg_7f00183f1dee` was explicitly revoked by `msg_8d5f412d9de1`.
- `native-boxes-v3`: root GO `msg_b3d588409075`, exact HEAD `0624f5b7785ed4662f258fe7141dde22edb9ab1f`, readiness `independent-joint-review/native-boxes-v3-eight-model-readiness.json` SHA `3fa9b61e5b496d35c92a1f7ce10f238e6134fe76053b308a9f7354d1706a1240`. Reviewed fixes use EVAD native original boxes with normalized native-action correspondence and explicit UTF8 comparison I/O. Joint specs use `joint/queue-specs-native-boxes-v3`; encoder specs remain `model-specs-v1`. Root explicitly authorized eight fresh smokes, joint3 first, then encoder5, with stop/report on any canonical failure. Old receipts are history, never resume authority.
- Full45 GO `msg_8eaa42d05f42` initially covered EVAD-B after the smoke wave. Root `msg_caa4553ef4f8` then explicitly delegated all8 full45 jobs with exact auth flags, only after all8 v3 smokes succeed and each actual smoke is independently accepted by Astra, timeout14400/batch1/frozen HEAD0624f5b. Per-model immutable `fullpass-go-MODEL.json` binds the actual independent review; failures stop further enqueue and require root direction.

## Frozen inputs and interpretation

Cohort `outputs/model-comparison/exp0066/cohort-v1/manifest.json` SHA `480b1410c568b9a038c7be6d124f7be1890b3b7375cbed43e87b165346a2aa18`; smoke windows SHA `8ee64caa28fed6b756aecf39c5d392c6b544f204ad12ed39ed617d727a3481c0`; baseline attempt-002 lock SHA `3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40`.

Full45 means184300 native frames /6177 regular+42 supplemental=6219 windows. Smoke is seven windows from six complete decoded originals,24155 native frames:006124.991533333,00766,02867,03090/94,03140,03434 seconds. Common16 native samples target `anchor+(i-8)*4/30`, center index8, nearest PTS with earlier ties, explicit edge/duplicate masks, `available_after_pts=max(actual sample PTS)`. Inputs are wholeframe without FCOS gating. R3D's original epoch6 actor-context8frames/3Hz differs from this16frame wholeframe condition.

Four encoders return features without a climbing head. Joint models return100 independent learned queries and80 AVA scores, not100 people or CCTV climbing probabilities. R3D threshold remains0.5. No labels, training, threshold selection, fallback precision, smaller substitutes, or model tuning were introduced. All45 and EXP-0064 test embargo remain protected.

## Exact model bindings

| revision | model | spec SHA256 | checkpoint SHA256 |
| --- | --- | --- | --- |
| initial-v1 | r3d18_exp0064 | `42fd653f6727348ee843323d32b873179cffadb6272d565f2429b239821d9fe4` | `8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73` |
| initial-v1 | videomaev2_b | `4cafaae8e57e5fc67948b3317c4dcab3645dc55fd673dc7c2c5318ea6d1f5935` | `8141a6955e0700d11bf15928fe6d61e5cfe482606fed8cfdddb1b922c0fd88ec` |
| initial-v1 | vjepa2_l | `206e0e07a6313ee48e72b3eed25753dbe7eda517ed5a4387c116c24bd049c3e7` | `5346856ec9df69487fe72a25bf2632aaa8112df33fb67708e3f7374edc1f7012` |
| initial-v1 | vjepa2_1_l | `63c6133ab0bf2d94dbe648dac90dc82f58f612a927309a40007a0ed820d6f847` | `7ea9b7cb4a75d10644a8a8d42cff9e177b10dca8f02173f0eaf2b0bed82838c6` |
| initial-v1 | internvideo_next_s2_l | `dd983c9877da65bc5aaf843fe315fd215e05447276ca6914780faaaf06f603b6` | `538d64384706e96b7b01844bd9debc8fe8f9e3c86ee0162d8d0cb51c28fea51d` |
| timeout-v2 | evad_vitb_vmaev2 | `338774d022c8e2d18f40ffc38c3d578253b22527348de79295b8398f5bd6b577` | `c58dbffc3137638230a8a67a5bac1e2c5a9186ba653fb516ff7931e45389d645` |
| timeout-v2 | evad_vitl | `699640e6dfa04ea4560307a3216ecf65464a55aaf068ce0ad059a8368e88dfc2` | `141d40fe36d9ccbe7792d62503358dc8b1eeaab3bf9006c2d94290744fb8ac93` |
| timeout-v2 | stmixer_vitb_vmaev2 | `218847e02e2d31e35c92d12f41fa0742c20990801bcfb7e8bff576462ea5a9a2` | `e9d6c69c47d7e13efc84d7147b3527c5cff9e21b148e18062cf66fec2101f6a1` |
| native-boxes-v3 | evad_vitb_vmaev2 | `8c12b8d184189573695e03ec4d99a3cedca5df30500371849e0d9c64b8eb048c` | `c58dbffc3137638230a8a67a5bac1e2c5a9186ba653fb516ff7931e45389d645` |
| native-boxes-v3 | evad_vitl | `3d330688aadc60f3c50c47d9b362d1cba06ce404cb965b9049505f3cb0ac8fb7` | `141d40fe36d9ccbe7792d62503358dc8b1eeaab3bf9006c2d94290744fb8ac93` |
| native-boxes-v3 | stmixer_vitb_vmaev2 | `9b662cf66a689dc2c277624438a3b5e5cafae3aab60b85c4873ae0ac4128487e` | `e9d6c69c47d7e13efc84d7147b3527c5cff9e21b148e18062cf66fec2101f6a1` |
| native-boxes-v3 | r3d18_exp0064 | `42fd653f6727348ee843323d32b873179cffadb6272d565f2429b239821d9fe4` | `8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73` |
| native-boxes-v3 | videomaev2_b | `4cafaae8e57e5fc67948b3317c4dcab3645dc55fd673dc7c2c5318ea6d1f5935` | `8141a6955e0700d11bf15928fe6d61e5cfe482606fed8cfdddb1b922c0fd88ec` |
| native-boxes-v3 | vjepa2_l | `206e0e07a6313ee48e72b3eed25753dbe7eda517ed5a4387c116c24bd049c3e7` | `5346856ec9df69487fe72a25bf2632aaa8112df33fb67708e3f7374edc1f7012` |
| native-boxes-v3 | vjepa2_1_l | `63c6133ab0bf2d94dbe648dac90dc82f58f612a927309a40007a0ed820d6f847` | `7ea9b7cb4a75d10644a8a8d42cff9e177b10dca8f02173f0eaf2b0bed82838c6` |
| native-boxes-v3 | internvideo_next_s2_l | `dd983c9877da65bc5aaf843fe315fd215e05447276ca6914780faaaf06f603b6` | `538d64384706e96b7b01844bd9debc8fe8f9e3c86ee0162d8d0cb51c28fea51d` |

R3D uses `.venv-cv-batch02/bin/python`, encoder4 use `.venv-exp0066-encoders/bin/python`, joint3 use `.venv-exp0066-joint/bin/python`, joint precision float32. Exact vendor/config/checkpoint/package/import-origin snapshots are bound by each spec and input contract. Worker installed nothing and changed no production sources/tests/specs/environments/weights.

## Actual canonical results

| revision | model | stage | job | attempt | canonical status / exit | windows / decoded frames |
| --- | --- | --- | --- | --- | --- | --- |
| initial-v1 | r3d18_exp0064 | smoke | `e4b5548f9ab24836b150a5e72a45e165` | `c8a7d4c94ced4d678280cfeba6e0ff1e` | succeeded / 0 | 7 / 24155 |
| initial-v1 | videomaev2_b | smoke | `b4a9eb5c7cb643dab96c771c9f3277c8` | `ffc3ff29239045839aeb2609ad0d7750` | succeeded / 0 | 7 / 24155 |
| initial-v1 | vjepa2_l | smoke | `6cc06908dca04989a1f8f7b86d554297` | `7c37a1cb173f4ec59356685d16eaaf6f` | succeeded / 0 | 7 / 24155 |
| initial-v1 | vjepa2_1_l | smoke | `7980ef1408f0457388aec24ea98fb8a7` | `c81251c5e8b54aa18f1c27337e6f24ac` | succeeded / 0 | 7 / 24155 |
| initial-v1 | internvideo_next_s2_l | smoke | `952fe8713e164e7f9751184501245305` | `0f4b227d296042d6b0de66dfacfc07cc` | succeeded / 0 | 7 / 24155 |
| timeout-v2 | evad_vitb_vmaev2 | smoke | `b0d9ff43acd54539b9456ee21255ffc9` | `ff2c9a438c984f59a58b6417fbf33cfd` | succeeded / 0 | 7 / 24155 |
| timeout-v2 | evad_vitl | smoke | `563565fe014c4efbb80cb72b82d9dc9d` | `815139b6611b4eff99b5308875cf2597` | succeeded / 0 | 7 / 24155 |
| timeout-v2 | stmixer_vitb_vmaev2 | smoke | `76fea8646250431ca232dfddbac8224d` | `4ebd7864eaec417c8e114d24fa81988e` | failed / 1 | 7 / final validation failed |
| native-boxes-v3 | evad_vitb_vmaev2 | smoke | `47bd142d4392461ba14c51e56ffa40ad` | `73b214d6facc4a01bfac9581a9a5fec9` | succeeded / 0 | 7 / 24155 |
| native-boxes-v3 | evad_vitl | smoke | `0681e595711f45e8aa7fd99f99dbcc0a` | `36efa618144344db9284ba6a69740ed1` | succeeded / 0 | 7 / 24155 |
| native-boxes-v3 | stmixer_vitb_vmaev2 | smoke | `46b261d916cc4f10a86bed439876fa42` | `ee03c8ea379c44c083c0efa2617c127c` | succeeded / 0 | 7 / 24155 |
| native-boxes-v3 | r3d18_exp0064 | smoke | `6dfac0a3c19f48a2a858a6f5e686ce20` | `5e066f42ccf349fa8db3406118297227` | succeeded / 0 | 7 / 24155 |
| native-boxes-v3 | videomaev2_b | smoke | `7ec01194b5e94af6add609217352d3a8` | `653f72c63fc44ea88bfb410672c7713b` | succeeded / 0 | 7 / 24155 |
| native-boxes-v3 | vjepa2_l | smoke | `bb21111ca2bc4d3ba04c7bf17fc0b506` | `ad4064952d59473b8c6a16780ef0f2b1` | succeeded / 0 | 7 / 24155 |
| native-boxes-v3 | vjepa2_1_l | smoke | `c22277d25ee744a48b1fbb4ca05f0eea` | `272c8df0d53b453e97b4fe70baa76a8c` | succeeded / 0 | 7 / 24155 |
| native-boxes-v3 | internvideo_next_s2_l | smoke | `f5c1de91015d4b86a3947a9bd624f721` | `2adbff9e08b94478a609559106ae5346` | succeeded / 0 | 7 / 24155 |
| native-boxes-v3 | evad_vitb_vmaev2 | all45 | `3050fdc685864c1b871084f31c7c5f91` | `02c84b75712f426384078b70720ee69d` | succeeded / 0 | 6219 / 184300 |
| native-boxes-v3 | evad_vitl | all45 | `871569076d0541d3afb7141f509e4a4a` | `4a58c755ac3749edb41d1c56a98144bf` | succeeded / 0 | 6219 / 184300 |
| native-boxes-v3 | stmixer_vitb_vmaev2 | all45 | `acead3494b9b489083a254f9c11c7aea` | `8a321630f48b442ca7748914759cd222` | succeeded / 0 | 6219 / 184300 |
| native-boxes-v3 | r3d18_exp0064 | all45 | `2009ccb8ac68454f819e348e8410f1b8` | `ee5981a15aeb4969995ab133c8df547a` | succeeded / 0 | 6219 / 184300 |
| native-boxes-v3 | videomaev2_b | all45 | `a78e906f5ce141c788f4afcf9330bbd3` | `2f85f753a2504ea7abfbe166d802da6b` | succeeded / 0 | 6219 / 184300 |
| native-boxes-v3 | vjepa2_l | all45 | `708ac71f4fca4c5cb7cb14335954f13b` | `64c8a4e94d7c44deafb269b6b7fcd85c` | succeeded / 0 | 6219 / 184300 |
| native-boxes-v3 | vjepa2_1_l | all45 | `5dafe32f8e924d599325c0d8e32c532e` | `7d47ac73df514e538ff95badf8042767` | succeeded / 0 | 6219 / 184300 |
| native-boxes-v3 | internvideo_next_s2_l | all45 | `092268bce16542979061b7f2ab448c04` | `8c00a20e847449ddb7a23f25f194587b` | succeeded / 0 | 6219 / 184300 |

Canonical success establishes technical execution, receipt and exit status; it does not certify actor/action semantics. The old EVAD rows remain geometrically unusable despite canonical success. Failed STM partial seven-window output is not a smoke pass.

| revision/model/stage | load s | result elapsed s | wrapper elapsed s | peak allocated / reserved bytes |
| --- | ---: | ---: | ---: | --- |
| initial-v1/r3d18_exp0064/smoke | 1.093243209994398 | 26.59340039489325 | 34.611653511063196 | 231705088 / 255852544 |
| initial-v1/videomaev2_b/smoke | 3.3206922080134973 | 28.566831208998337 | 36.16258320095949 | 733531648 / 864026624 |
| initial-v1/vjepa2_l/smoke | 3.5699988349806517 | 32.180140160024166 | 47.52923424600158 | 1892184064 / 1944059904 |
| initial-v1/vjepa2_1_l/smoke | 3.5853973500197753 | 32.26750815403648 | 46.829616039060056 | 2069168128 / 2214592512 |
| initial-v1/internvideo_next_s2_l/smoke | 3.5942889789585024 | 31.622787892934866 | 39.82303790003061 | 3565298688 / 4150263808 |
| timeout-v2/evad_vitb_vmaev2/smoke | 3.546056321938522 | 30.14121873897966 | 38.45492432801984 | 2964866048 / 3988783104 |
| timeout-v2/evad_vitl/smoke | 6.216198284062557 | 34.22557846305426 | 44.07202623097692 | 4702206464 / 6075449344 |
| timeout-v2/stmixer_vitb_vmaev2/smoke | null | null | 38.975721555994824 | null / null |
| native-boxes-v3/evad_vitb_vmaev2/smoke | 5.137267258018255 | 33.06920062797144 | 41.94409135496244 | 2964866048 / 3988783104 |
| native-boxes-v3/evad_vitl/smoke | 7.1172381460200995 | 36.58765607501846 | 46.646342281019315 | 4702206464 / 6075449344 |
| native-boxes-v3/stmixer_vitb_vmaev2/smoke | 3.749506324995309 | 30.65077408205252 | 39.318700328003615 | 2575862784 / 2610954240 |
| native-boxes-v3/r3d18_exp0064/smoke | 1.088458391954191 | 25.79604876297526 | 33.560760832973756 | 231705088 / 255852544 |
| native-boxes-v3/videomaev2_b/smoke | 2.420985938049853 | 27.443461177055724 | 35.00882314098999 | 733531648 / 864026624 |
| native-boxes-v3/vjepa2_l/smoke | 3.2222214770736173 | 31.007383052026853 | 45.01278815895785 | 1892184064 / 1944059904 |
| native-boxes-v3/vjepa2_1_l/smoke | 2.9714891359908506 | 31.024868128006347 | 45.08218745002523 | 2069168128 / 2214592512 |
| native-boxes-v3/internvideo_next_s2_l/smoke | 3.49905102502089 | 31.247736199991778 | 39.353320615016855 | 3565298688 / 4150263808 |
| native-boxes-v3/evad_vitb_vmaev2/all45 | 3.35758152208291 | 1439.0428281400818 | 1447.3572836710373 | 2964866048 / 3988783104 |
| native-boxes-v3/evad_vitl/all45 | 7.287555418093689 | 2770.433529498987 | 2787.440053867991 | 4702206464 / 6075449344 |
| native-boxes-v3/stmixer_vitb_vmaev2/all45 | 5.54569519800134 | 1550.9030628389446 | 1561.030422618962 | 2575862784 / 2610954240 |
| native-boxes-v3/r3d18_exp0064/all45 | 1.4120587159413844 | 327.5755240409635 | 337.73970167094376 | 231705088 / 255852544 |
| native-boxes-v3/videomaev2_b/all45 | 2.7821611099643633 | 412.6144839610206 | 420.8883916049963 | 733531648 / 864026624 |
| native-boxes-v3/vjepa2_l/all45 | 10.067224817932583 | 788.9558436259395 | 825.1102186839562 | 1892184064 / 1944059904 |
| native-boxes-v3/vjepa2_1_l/all45 | 6.117022268008441 | 1259.9283127840608 | 1295.634304938023 | 2069168128 / 2214592512 |
| native-boxes-v3/internvideo_next_s2_l/all45 | 4.751359995920211 | 2304.7377660489874 | 2313.0238581740996 | 3565298688 / 4150263808 |

Allocator peaks are PyTorch peaks, not total device usage. Wrapper time includes source/environment/raw-input validation, decode, inference, output and exit. Per-window synchronized preprocess/inference/postprocess times are saved in output. Failed STM has no final result and peak memory is null, not zero. Seven-window scheduling estimates are not measured full45 speed or completion guarantees.

## Preserved defects and fresh validation

Timeout-v2 EVAD-B/L highest-person-score boxes had zero width on all seven inputs, including `[1920,1080,1920,1080]`. The vendor mutated a captured detection tensor into original coordinates and the adapter inverse-scaled it again. Original outputs remain unchanged and excluded from person recovery/fullpass proof. Evidence: `encoder-execution/timeout-v2/evad-coordinate-concern.json`.

Timeout-v2 STMixer attempt `4ebd7864eaec417c8e114d24fa81988e` failed exit1 after seven forwards at runner final `input_contract`, through comparison_command to action_training_command's default text reader: `UnicodeDecodeError` under ASCII locale on Korean source paths. Both child and supervisor exited. It was not OOM and not a completed smoke; result/peak are null. Preserved windows SHA `f20fba56bc3ae1dd6536ea374dfc853fbda66bfb41364dbda23ba3d71dec346e`, child log SHA `9d653de177eef598c6944cb8b9e3945e626d0fa2bbe5d064b63d978ec7623388`.

The independent source readiness evidence records51 passing CPU regression tests (`native-boxes-v3-tests.log`, SHA `50f614c16d6e15ea5789fc2133b78f2618371ec01cd419f6e02842c6bdb012b6`) and four actual vendor in-place coordinate-conversion regressions at1920x1080,1080x1920,1281x721,640x480 (`native-boxes-v3-independent-regression.json`, SHA `3d674da6e9fa3ab737ed839745bbedf836e965859984af3ba9d2c4d726fd96ca`), with zero model forwards/CUDA initialization by the reviewer. These were independent review checks, not worker-triggered test reruns.

Fresh v3 CPU saved-output audits verify exact window/native sampling metadata, all45 or smoke counts, finite outputs, source/result/windows/receipt hashes and identity-based process exit. EVAD additionally checks every native original box against saved normalized native action boxes times original dimensions, in-bounds coordinates and validity masks. This validates coordinate correspondence, not human/actor identity or action accuracy. Query counts and high scores are never TP labels.

## Exact commands and output hashes

All forwards went through `Queue.enqueue(command='model-compare')` then `Queue.run_once(job_id=...)` in Orca Lab's canonical `runtime/orca-lab/gpu-queue` (logical service-relative path; exact local paths remain in invocation/receipt metadata). Exact config/input/source hashes, live assignment, free-memory gate and GPU lock were mandatory. No direct forward, Queue.retry, DB rewriting, commits, push, web DB writes or external media upload occurred.

Exact executed stage commands are transcribed below from immutable `invocation.json` records; CPU preparation binds each saved configuration to its actual root GO.

The windows hashes below come from canonical results whose actual bytes are checked by the saved-output audits; report regeneration does not repeat full-output scans. Every stage directory preserves authorization/prepared/input-contract/queue-config/invocation/enqueue/completion files. Authorization records actual GO and reviewed committed HEAD; specs and source bytes are checked against the exact receipt and Git commit before enqueue. Canonical attempts preserve `manifest.json`, `child.log`, config and assignment. New source revisions use separate namespaces and never replace old attempts.

| revision/model/stage | result SHA256 | windows SHA256 |
| --- | --- | --- |
| initial-v1/r3d18_exp0064/smoke | `3941eff38278bd30bfa3ae0088d6d9a1653105868242ae1545a681fbb30dfa45` | `94a8953a114c4410a382650f17b5b014d565597a3cca4d6b27685b32e35d3ec1` |
| initial-v1/videomaev2_b/smoke | `cc7c13669386702bdf970a1742ef3a61037742390ddc2d8ca9d8cee9a561e9f0` | `c4477e9e6d4319db40d33e5527291133dca01991bbb26863ef5920fc42e97a01` |
| initial-v1/vjepa2_l/smoke | `0e8a8a29846c4a1a6c3e2fadd543585432f5ab9da86913113bb6b6da869f1cd7` | `d0271c20515d7d6e4409b60bda2b1fed3fbe991dc1e924f08af9bfbc97eef1c6` |
| initial-v1/vjepa2_1_l/smoke | `0700f6369c0120fcccc12b6dc84b8cb362c81a4866f0dc02443d9392189f5cca` | `c9affe22a6d2d2d3ac27b32c3bf3d667be2066ea754a4c7f008111b344761f8a` |
| initial-v1/internvideo_next_s2_l/smoke | `1ac8fe1a03eef6cdbde7c635271c9b4b9df8fbc3279a72f4a3a948605be52cc4` | `9c10bdd35d6a7fcb934224675a9a9b2fbf360347f09b673bec794b3b606c8d03` |
| timeout-v2/evad_vitb_vmaev2/smoke | `5c50ee0ad5a76a4e64f1e620e85261b34d51e7715191156636d00eaedd22d06b` | `5dcd0f6b1dd515313fe7b0d1c05c9f05e1e8cb8b5b1b9618ef9709bd47e8b87b` |
| timeout-v2/evad_vitl/smoke | `02b3a805ce124e0b8f21b8c758a7a5b85aab61823117a376ef7594287c7ce0e5` | `50551b5824f3ec22d31e641df4fdb14da0ede7dfac159fcee547a8aa805d8149` |
| timeout-v2/stmixer_vitb_vmaev2/smoke | `absent` | `f20fba56bc3ae1dd6536ea374dfc853fbda66bfb41364dbda23ba3d71dec346e` |
| native-boxes-v3/evad_vitb_vmaev2/smoke | `4b50911e1759397dcc4d7f2cda3f1eeb2d0e7b5e06816086732736d3cf74320e` | `09ff37146955833e37e99e86e732192140dd1404a839df311939d6d2d83590fd` |
| native-boxes-v3/evad_vitl/smoke | `1cdd11edb34670b64ff1f4028513c5efe2e12acb49ad15da2337b84bfc053af6` | `55f0a2dfb3dd1699e0a6b3ba6db51e9da97453b117cd7a4518c4d8f64fca6780` |
| native-boxes-v3/stmixer_vitb_vmaev2/smoke | `287f944654039d82f44229f4b07bba3128f28ef82b34e31e12ba26d016ffe9ef` | `7c9e0f2c2b4d9ce07a9e2a7ab51e5ebc77bde7cee2e69b192a4d6435ef8c6b73` |
| native-boxes-v3/r3d18_exp0064/smoke | `9bab2ae3d8299580d1f5564f4fb44f417274145c5edc1c821af17efb17bec8fb` | `2b7cfbe5bc6ea9bfcd76769e505b4f1ce54626d4cb70ceda47793df86ee6c2e8` |
| native-boxes-v3/videomaev2_b/smoke | `550cc73c516696b400673485901119731b1ad32248651b3637dcd8856bcee0ec` | `c6ec233d8f32625490440676b4eb760e5f455280579835dc27de4daf2bae18e3` |
| native-boxes-v3/vjepa2_l/smoke | `bc3f840dc51c0601c7649a0ea321119877038bf16bf8a4c31ddba737d6cc4371` | `1d30f24b1e5a74d61809358cb0979f7220af2fdb4c324020ca516b69ba09c63d` |
| native-boxes-v3/vjepa2_1_l/smoke | `26d58d34af90900ac54a5a630bcf1ba2c4a637b22bc13b15468b8998f2ed4e32` | `f22f425714b9fc3dd3bac63d55ad60e19f7e3ee66e1dfba61a5f66070132d91a` |
| native-boxes-v3/internvideo_next_s2_l/smoke | `f721d554526c2bfb524172531a58f808eac0b012395a2f90f50a3d4cc94dfbcd` | `4d82eaac94b62125413ad78c0e9b77c27a5248b443016d2b82ee507cf8dcdec5` |
| native-boxes-v3/evad_vitb_vmaev2/all45 | `827966ffb9abe51dcc17857a9b3a5c226e795f1c3380b33902e35f4ffd8b575e` | `a06ec894815dab7da5e0a78064848bf1416f97146f13d1e5f5d58253624e3b27` |
| native-boxes-v3/evad_vitl/all45 | `745794e812b4672d1bd75cd306c2e8efa58ef913b9d12781a2b16e5e628ccd42` | `fee7239f02089f88be27bb5f2cbc11dd32126e252891a359ed9083725ece1a8a` |
| native-boxes-v3/stmixer_vitb_vmaev2/all45 | `2ee063332ee7415b9f67eedffffd0a83e44ac706b21b9af5ef3e598610798b66` | `d45f408225669b18edb23bc3023e4a7a8ee8f8a265769e784c6d135615dd9e0a` |
| native-boxes-v3/r3d18_exp0064/all45 | `ac0cf8e4cdc43c7d28f8cc87867b1f31ac63c6f8796d059b9b310410bc8a7eb9` | `4a04b0aa08726d6e48aa4cf7124184d153df08dc36b6db607db83a702c121922` |
| native-boxes-v3/videomaev2_b/all45 | `05dff274e473c3010b47430787e739a3aa09c38e6b2f277f3132a889b6c32047` | `8b0181f38f26a504373c7d568ac13b7201a08e8ffc71437eeee798e071da2a71` |
| native-boxes-v3/vjepa2_l/all45 | `51448e2fc3f155fd340970dbf3f69712ea6366503219057cdd5c28f314ff0ed1` | `57b529e210fecd3784d12a0ff5ba6f50c53e34b38db4d1bd149190419df157a9` |
| native-boxes-v3/vjepa2_1_l/all45 | `fbabc763ed5c7d4cf5a1c0c1e96412477256b9770e142192b979b22d17ee7284` | `b6cb2ae81208a5ba4eebd38a8c1a3b2bf650888572bf85f75e664b5eca916c5d` |
| native-boxes-v3/internvideo_next_s2_l/all45 | `be6e017faadcad01efe04c55ac6720d5195b76c0b6e999e6caf3f0bf88721807` | `100baf2be4692137909eaaef18575cb98de7c3b2f77dec3333e9427d4b0f7de6` |

Independent actual full-stream acceptance receipts (technical contracts, human metrics null):

| model | attempt | independent proof | proof SHA256 |
| --- | --- | --- | --- |
| evad_vitb_vmaev2 | `02c84b75712f426384078b70720ee69d` | `full45-evad-b.json` | `e886a7dd347cd53552115469b6b485eb229b34ef26dc848a79f5a34a5a98d2c6` |
| evad_vitl | `4a58c755ac3749edb41d1c56a98144bf` | `full45-evad-l.json` | `4cea62c31ebad7caaca0dff9b197754e37a9c56615b9a42065790282a14dfc43` |
| internvideo_next_s2_l | `8c00a20e847449ddb7a23f25f194587b` | `full45-internvideo.json` | `1350b6e94cf4b6700266bd832e9b323110eb82b9afd82bd3a77d70e8911ae825` |
| r3d18_exp0064 | `ee5981a15aeb4969995ab133c8df547a` | `full45-r3d.json` | `f54241f519848ae3fcd71876da239d05dcf1ded530571f4457171371c16b6a93` |
| stmixer_vitb_vmaev2 | `8a321630f48b442ca7748914759cd222` | `full45-stmixer.json` | `a41f97995387bfa975685820c550888a5db5980391007d924c218fafdbebf04d` |
| videomaev2_b | `2f85f753a2504ea7abfbe166d802da6b` | `full45-vmae.json` | `73fc0c0b0fa7879f479d12d0b1d48c9dd2f38920b2ea3bd1973f56020db5a93e` |
| vjepa2_1_l | `7d47ac73df514e538ff95badf8042767` | `full45-vjepa21.json` | `04be572eb9dd5a23daac63e7d6838ebea8de2de8610fd6b98f67932bada31900` |
| vjepa2_l | `64c8a4e94d7c44deafb269b6b7fcd85c` | `full45-vjepa2.json` | `817cc3b99c6e787b6f7298bc2cec4f429693aadccfa90ddbda0cdb7828c2d6f7` |

Exact executed stage commands (from invocation.json):

```bash
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_queue.py execute --model r3d18_exp0064
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_queue.py execute --model videomaev2_b
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_queue.py execute --model vjepa2_l
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_queue.py execute --model vjepa2_1_l
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_queue.py execute --model internvideo_next_s2_l
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_timeout_v2.py execute --model evad_vitb_vmaev2
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_timeout_v2.py execute --model evad_vitl
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_timeout_v2.py execute --model stmixer_vitb_vmaev2
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_native_boxes_v3.py execute --model evad_vitb_vmaev2
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_native_boxes_v3.py execute --model evad_vitl
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_native_boxes_v3.py execute --model stmixer_vitb_vmaev2
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_native_boxes_v3.py execute --model r3d18_exp0064
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_native_boxes_v3.py execute --model videomaev2_b
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_native_boxes_v3.py execute --model vjepa2_l
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_native_boxes_v3.py execute --model vjepa2_1_l
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_native_boxes_v3.py execute --model internvideo_next_s2_l
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_full_native_boxes_v3.py execute --model evad_vitb_vmaev2 --go-message msg_8eaa42d05f42
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_full_native_boxes_v3.py execute --model evad_vitl --go-message msg_caa4553ef4f8
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_full_native_boxes_v3.py execute --model stmixer_vitb_vmaev2 --go-message msg_caa4553ef4f8
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_full_native_boxes_v3.py execute --model r3d18_exp0064 --go-message msg_caa4553ef4f8
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_full_native_boxes_v3.py execute --model videomaev2_b --go-message msg_caa4553ef4f8
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_full_native_boxes_v3.py execute --model vjepa2_l --go-message msg_caa4553ef4f8
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_full_native_boxes_v3.py execute --model vjepa2_1_l --go-message msg_caa4553ef4f8
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/dispatch_full_native_boxes_v3.py execute --model internvideo_next_s2_l --go-message msg_caa4553ef4f8
```

Queue preservation uses exact dictionaries, not whole-DB byte hashes: original100 jobs/attempts in `queue-initial.json`, pre-timeout105 in `timeout-v2/queue-before-revision.json`, and pre-v3 108 in `native-boxes-v3/queue-before-revision.json`. Saved-output audits verify these unchanged. All previous failed/invalid results are retained. Current control state is `encoder-execution/current-state.json`; per-revision audits and receipts are the durable evidence. No human performance winner or intrusion improvement is inferred from execution success.

Final CPU receipt/queue audit: `all8_actual_full45_local_and_independent_audits_verified`; `runtime/model-comparison/exp0066/encoder-execution/native-boxes-v3/final-execution-audit.json` SHA `d895b8398164fc81c7f9352743de460771ef162f95f6c8a851cdcf8f582454e7`. All 24 owned canonical attempts retain their original statuses, all 48 recorded supervisor/child identities are positively exited, and original100 plus all prior queue rows are unchanged. The same45 sources yielded 49752 full-pass model-window outputs across8 models; this is repeated model evaluation, not8 independent datasets. Human metrics remain null.

Independent consolidated raw8 completion barrier: `runtime/model-comparison/exp0066/independent-joint-review/raw8-completion-barrier.json` SHA `da9a32c122e0ef41520b3b454e7e3cd47b9c0f865f1c2cc8d905c3aa3e2dd8a4`. It independently preserves the original100 queue rows and six prior report/registration files; semantic performance and head execution are not certified. Root requested this source-frozen final handoff in `msg_88decc3b04ff`; no further inference was launched.

Final metadata-only verification command (zero model forwards and zero raw-media rehashes):

```bash
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/encoder-execution/final_execution_audit.py
```
