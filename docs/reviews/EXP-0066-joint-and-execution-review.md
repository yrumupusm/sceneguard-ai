# EXP-0066 joint 모델 및 실제 실행 독립 검토

**최신 판정: 수정 후 8개 모델의 실제 smoke 계약을 확인했다. 이전 두 EVAD smoke의 좌표 오류 및 STMixer 첫 실패는 그대로 유지한다.** root의 실제 렌더링에서 발견한 좌표 몰림을 독립 재현했고, vendor in-place 변경과 adapter 이중 역변환을 수정한 새 결과만 받아들였다. 아래 이전 통과 기록은 실행 출처·개수·유한값·shape 검사 이력으로 보존하며 올바른 좌표 인증으로 재사용하지 않는다. Head 구현·실제 CPU 준비도 별도 검토해 수용했다. 8개 모델 모두 전체45 실제 결과의 계약 검증을 통과했으며, 정확한 결과·영수증을 묶은 immutable raw8 완료 증거를 발행했다. 최종 실행 후보 v1의22개 alias 창 입력 오류를 차단한 뒤 수정된 commit `36d14d4`와 v2 후보를 검토해 고정21단계 실행 준비도를 수용했다. 실제 실행에는 정확한 root GO가 필요하며, 실제 head 결과와 행동 성능은 아직 인증하지 않았다.

2026-11-07. Orca Task `task_a005e3d1bd50`, Dispatch `ctx_d755ff30c48e`. 이전 encoder 준비도 검토는 그대로 보존한다. 이 문서는 실제 도착한 근거만 순차 기록하며, 미완료 실행·task head·행동 성능을 인증하지 않는다. 검토자는 GPU/모델 forward/설치/큐 변경/생산 코드 수정/commit을 하지 않았다. 시작 시 WEB-0005 `pending --include-acknowledged` 조회는 성공했고 요청은 0개였다.

## 최초 Joint canonical smoke 준비도 이력 (EVAD 좌표 판정 철회)

초기에는 **검토된 세 명세로 첫 smoke를 진행할 준비도를 통과**로 판정했으나, 이후 EVAD 좌표 오류를 발견해 해당 승인을 철회했다. root의 기존 승인·활성 배정·자원 검사·canonical 단일 GPU lock·정확한 소스 commit·실행 승인이 별도로 적용된다. CPU strict load는 GPU 실행 성공이나 메모리 적합성을 보장하지 않는다. 전체 45개 실행에는 해당 모델의 실제 성공 smoke가 추가로 필요하다.

| 모델 | root queue-specs-v1 SHA256 | 공식 checkpoint SHA256 |
|---|---|---|
| EVAD ViT-B VideoMAEv2 | `338774d022c8e2d18f40ffc38c3d578253b22527348de79295b8398f5bd6b577` | `c58dbffc3137638230a8a67a5bac1e2c5a9186ba653fb516ff7931e45389d645` |
| EVAD ViT-L | `699640e6dfa04ea4560307a3216ecf65464a55aaf068ce0ad059a8368e88dfc2` | `141d40fe36d9ccbe7792d62503358dc8b1eeaab3bf9006c2d94290744fb8ac93` |
| STMixer ViT-B VideoMAEv2 | `218847e02e2d31e35c92d12f41fa0742c20990801bcfb7e8bff576462ea5a9a2` | `e9d6c69c47d7e13efc84d7147b3527c5cff9e21b148e18062cf66fec2101f6a1` |

실행 소스 묶음 SHA256은 `dcd7b75462f47fc5ed3b6c4dce29313497239f2f11504ff9492bdf147da3d248`, adapter는 `2562274f3a68ab78536b066dbb2eaafd7b8202609da0627f9250cd9bb05a2f17`, tests는 `fb140c907b2c4c75b1a0f56882598e6bb21ad0f18d4d7e2006e3ad5e5a14cef6`다. 정확한 10개 실행 파일과 각각의 해시는 `runtime/model-comparison/exp0066/independent-joint-review/bindings-and-geometry.json`에 있다.

공식 EVAD `0efdb7e1156d4b0b419cd240555f8bbca45e4bf6`, STMixer `2c3cd1de2623fc47ad93cfda3a8fcb9713736a55`의 README에 있는 AVA checkpoint 링크와 다운로드 receipt의 Drive ID가 일치한다. 각 checkpoint 실제 바이트를 다시 해시하고 strict load했다. EVAD의 torchvision 버전 판독은 `0.20`을 `0.2`로 오인하는 비교 두 곳만 tuple 비교로 바꾼 호환 패치다. 추가 추론 알고리즘 변경은 없다.

root wrapper는 원래 `specs-v2`의 모든 값을 보존하고 `bindings`, `environment_path`만 추가했다. EVAD 각 1,516개, STMixer 497개 binding을 실제 바이트와 대조했다. vendor 전체 Python 소스, config, checkpoint, label map, 의존성 소스와 native extension, 설치 환경 snapshot을 포함한다. 환경 SHA256은 `eb30f02e790170923a52362b2a7c98acc03028de05ba5c7d769d509816fcbd1a`다. canonical adapter의 source/input binding·실행 HEAD 대조·공유 lock·실제 queue job/attempt 및 smoke 영수증 검사는 이전 검토한 동일 바이트다.

세 모델 모두 CUDA를 숨긴 별도 프로세스에서 실제 생성 및 `strict=True` load 성공, missing/unexpected key 0, forward 0, CUDA 초기화 0이다. EVAD-B 529 keys, EVAD-L 793 keys, STMixer 529 keys이며 STMixer만 모든 key의 `module.` 접두사를 일괄 제거했다. 실제 key 수는 각각의 `*-cpu.json`을 최종 근거로 삼는다. 기존 joint 17개 시험을 직접 실행해 통과했고, 독립적으로 네 화면 비율의 원본↔resize/normalized 좌표 왕복 8개씩 총 24개를 확인했다. torchvision ROIAlign CUDA dispatch 등록은 확인했으나 kernel 실행은 하지 않았다.

검토한 출력 계약은 다음과 같다.

- 전체 시야 16개 RGB 표본, 물리 간격 4/30초, 첫 표본부터 마지막까지 2초다. EVAD short side 288, STMixer 256이며 RGB mean .45/std .225와 오른쪽·아래 normalized-zero padding을 사용한다. 구현 시험은 각 공식 전처리의 실제 CPU 결과와 비교한다. 인물 crop·FCOS 입력·GT proposal을 사용하지 않는다.
- EVAD는 자체 learned boxes와 query features로 시작한다. STMixer도 자체 spatial/temporal query에서 시작한다. 원래 person threshold .7/.6을 출력 보존 목적의 0으로 명시하고, 100개 query 순서를 유지한다. AVA 80개 sigmoid 점수와 person 2-logit softmax, 원래 person/action logits를 보존하며 둘을 곱하지 않는다. EVAD action top-k도 끈다.
- EVAD의 resize 좌표는 실제 가로·세로 배율로 나누고, STMixer의 normalized 좌표는 원본 폭·높이로 복원한다. padding은 원점 이동이 없어 별도 offset이 없다. clamp 뒤 면적 0인 query도 삭제하지 않고 valid flag로 남긴다. person 및 action 점수의 100/80 shape·유한값·범위를 검사한다.
- AVA의 일반 `climb (e.g., a mountain)` 점수는 CCTV 담넘기·침입 확률이 아니다. task-specific probability와 person recovery accuracy는 null이다. raw query 100개를 사람 100명 또는 복구 성공 100건으로 세면 안 된다.
- GPU 동기화 timing은 CPU resize/정규화·전송, 전체 vendor forward와 그 내부 후처리, 원본 좌표 복원·CPU 전송·list 변환을 구분한다. decode는 root가 별도 측정한다. native forward 내부 후처리가 inference 시간에 포함된다는 제한이 명시돼 있다.

정확한 첫 smoke 준비도 영수증은 `independent-joint-review/joint-smoke-readiness-v1.json`, SHA256 `8f01e7627f5253118320d867b6227078c1003774d8deda698d9ace9804b0ba28`이다.

## 실제 encoder/R3D smoke 확인

아래 첫 5건은 timeout 변경 이전 소스의 실제 성공 이력이다. 이후 timeout-v2 source로 전체 실행하려면 같은 새 source의 smoke를 다시 통과해야 하며, 과거 성공을 그대로 재사용하지 않는다.

독립 `audit_execution.py`는 출력 JSON 전체의 유한값, 고정 창 객체와 frame index·PTS·중복 수, 원본 source hash, 모델별 출력 shape/의미, 결과/JSONL/영수증 해시, 읽기 전용 canonical DB의 job/attempt 성공과 등록 필드 일치를 확인한다. root의 completion 요약만 신뢰하지 않는다.

| 모델 | 실제 smoke attempt | 창 / 영상 / native frames | 결과 |
|---|---|---|---|
| R3D EXP0064 | `c8a7d4c94ced4d678280cfeba6e0ff1e` | 7 / 6 / 24,155 | 통과 |
| VideoMAEv2-B | `ffc3ff29239045839aeb2609ad0d7750` | 7 / 6 / 24,155 | 통과 |
| V-JEPA2-L | `7c37a1cb173f4ec59356685d16eaaf6f` | 7 / 6 / 24,155 | 통과 |
| V-JEPA2.1-L | `c81251c5e8b54aa18f1c27337e6f24ac` | 7 / 6 / 24,155 | 통과 |
| InternVideo Next S2-L | `0f4b227d296042d6b0de66dfacfc07cc` | 7 / 6 / 24,155 | 통과 |

근거는 `independent-joint-review/actual-smoke-first2.json`, `actual-smoke-next2.json`, `actual-smoke-internvideo.json`이다. 모든 실행의 source hash는 이전 승인한 `9c884306bc5ea014b83166516d05473ee9ba6f680e44ad92d1faeeb624233293`다. R3D 점수는 0.2145268172–0.5682211518이지만 이전 actor-crop 학습 모델을 새 fullframe 16-frame 조건에 적용한 값이다. 새 encoder는 유한한 pooled feature만 반환하고 climbing score는 null이다. 이 다섯 실행은 같은 소스·명세·cohort의 root 승인 전체 실행 전제를 충족한다. 성공한 7개 smoke 창을 전체 행동 성능이나 전체 45개 완료로 해석하지 않는다.

## timeout-v2 제한 변경 독립 검토

실측 처리량상 긴 전체 실행에 기존 3,600초 상한의 여유가 부족해 root가 큐가 idle임을 확인한 뒤 `model-compare` 상한만 14,400초로 바꿨다. `orchestration/queue.py` 두 줄 및 경계 시험 12줄 외 실행 소스 변화가 없음을 대조했다. 유한한 양수·상한 검사, 다른 command의 상한, 단일 lock, input/source binding·실제 smoke 검증은 유지된다. numerical adapter/명세/가중치/cohort 변경은 없다.

독립적으로 CUDA-hidden joint 환경에서 comparison/queue/joint 38개, action guard 11개 시험이 통과했다. root의 첫 51개 묶음 시험은 이전 cv 환경에서 joint 전처리 의존성 `iopath` 부재로 2개 import 오류가 있었으며 실패 로그를 보존했다. 환경 설치 변경 없이 올바른 joint 환경으로 재시험했다.

새 queue SHA256 `4b4eb83411055d630dd42c41b7fd8a8bd10e0128c355e87c3d057d7cd3292209`, comparison test SHA256 `c687daecab52b0efcd18d1d8d1dfcf37e35a1368ad1d14f1899091c6dca96e22`를 승인했다. 새 실행 source digest는 encoder/R3D `78d0df1f7b1ce4a4a0bc2c9b5be29805bc83543aac18ba44bea74997391c7ced`, joint `faddb505d61520c48302e122b3915c804156a9cc9f779481fcd97447a0779b00`다. 정확한 8개 명세와 source를 연결한 `timeout-v2-eight-model-readiness.json` SHA256은 `b7e2317892ebf25e9a3a72cd6411236345c6a73b4989cdbf6d83abe0c02070f3`다. root가 이 정확한 바이트를 commit하고 기존 canonical 조건을 충족한 첫 smoke를 진행할 준비도만 승인한다. task head나 행동 성능 승인이 아니다.

root commit `de8c22bc1df8c77269b035b3e5df51f8bf9a94ce`의 실행 파일 11개가 검토 영수증 및 현재 파일과 동일함을 `timeout-v2-committed.json`으로 확인했다.

## timeout-v2 실제 smoke

| 모델 | 실제 attempt | 창 / 영상 / native frames | peak allocated / reserved bytes | 독립 결과 |
|---|---|---|---|---|
| EVAD-B | `ff2c9a438c984f59a58b6417fbf33cfd` | 7 / 6 / 24,155 | 2,964,866,048 / 3,988,783,104 | 실행 성공·좌표 오류 |
| EVAD-L | `815139b6611b4eff99b5308875cf2597` | 7 / 6 / 24,155 | 4,702,206,464 / 6,075,449,344 | 실행 성공·좌표 오류 |

EVAD-B 결과 SHA256 `5c50ee0ad5a76a4e64f1e620e85261b34d51e7715191156636d00eaedd22d06b`, 실제 영수증 및 출력 JSONL의 해시는 `timeout-v2-evad-b-smoke.json`에 기록했다. 7개 창의 모든 100 query × 80 AVA 확률과 raw logits, person softmax, 원본 box 범위와 validity flag를 독립 대조했다. 실제 확률은 raw logits의 sigmoid/softmax와 허용 오차 0.000002 이내로 일치한다. precision은 검토한 float32이고 작은 모델·해상도·AMP fallback은 없다. canonical DB 성공 row와 결과/영수증의 등록 필드 및 새 source/spec 해시가 일치한다. 이 수치 검사로 처음에는 all45 전제를 충족한다고 판단했으나, 아래 실제 좌표 오류 때문에 그 승인을 철회했다.

EVAD-L도 초기 산술·좌표 범위·canonical 출처 검사를 통과했으나 동일한 좌표 의미 오류가 확인돼 승인을 철회했다. 결과 SHA256 `02b3a805ce124e0b8f21b8c758a7a5b85aab61823117a376ef7594287c7ce0e5`, 전체 근거는 `timeout-v2-evad-l-smoke.json`이다.

## 중요 발견: EVAD 원본 좌표 이중 역변환 — 실행 보류

`E2EDetector.head_forward`의 `boxes_per_image`는 hook이 보존한 `output['pred_boxes']`의 view다. vendor `clip_boxes_tensor`는 이 view를 제자리 변경하고, 이후 `detector_postprocess(..., norm_scale=False)`가 같은 tensor에 원본/resize 배율을 곱한다. 따라서 native forward가 끝난 뒤 hook의 box는 이미 원본 pixel 좌표다. adapter는 이를 resize 좌표로 오인해 `boxes_to_original`로 다시 나누어 화면 끝으로 밀고 clamp한다.

공식 후처리 함수를 실제 CPU로 호출하여 모델 forward 없이 재현했다. resize 좌표 `[100,50,200,150]`, 512×288→1920×1080 변환에서 native의 올바른 결과는 `[375,187.5,750,562.5]`다. hook도 같은 메모리 주소의 그 결과를 보지만 기존 adapter 결과는 `[1406.25,703.125,1920,1080]`가 된다. normalized native action box를 원본 크기로 곱한 값은 올바른 native person box와 일치한다. 근거 `evad-inplace-coordinate-reproduction.json`에 CUDA 초기화·모델 forward 0도 기록했다.

권고: native `persons['boxes'][0]`를 원본 pixel 좌표로 직접 보존하고 유한값/범위/validity를 검사한다. 회귀는 고립된 역변환 함수뿐 아니라 vendor의 실제 in-place 후처리와 hook alias까지 통과한 adapter 결과를 native person box 및 normalized action box와 대조해야 한다. 기존 출력은 clamp로 정보가 사라져 단순 사후 역보정하면 안 된다. root가 소유한 최소 수정 후 새 source/spec readiness 및 canonical smoke가 필요하다.

기존 독립 검토의 shape·범위·sigmoid 검사는 이 의미 오류를 발견하지 못했다. synthetic 좌표 왕복 검사도 vendor alias를 포함하지 않아 불충분했다. 이 한계를 인정하고 두 EVAD의 all45 전제 승인을 명시적으로 철회했다. 철회 근거 `evad-readiness-revocation-v1.json`은 기존 준비도와 성공 실행 증거를 덮어쓰지 않는 추가 기록이다. source/checkpoint/count/logit 검증이 사실이라는 점과 box 좌표 오류를 구분한다. 현재 adapter SHA256 `2562274f…`의 EVAD 출력을 사람 복구 성능 평가에 사용하지 않는다.

## native-boxes-v3 수정 준비도 — 실제 재실행 대기

root 수정은 EVAD의 native original person box를 직접 보존하고 normalized action box×원본 크기와 clamp 전에 대조한다. 입력 1개의 batch index 0 및 query 100개 정렬도 확인한다. 출력에 `native_action_boxes_normalized`와 `box_coordinate_source`를 추가해 저장 결과에서도 독립 검증할 수 있다. 네 화면 비율에서 공식 후처리의 alias 변화·올바른 결과·퇴화 box 보존·잘못된 대응 거절을 별도 CPU 시험으로 확인했다. 증거 `native-boxes-v3-independent-regression.json`이며 모델 forward는 0이다.

STMixer 첫 attempt `4ebd7864eaec417c8e114d24fa81988e`는 7개 출력 뒤 최종 입력 재검증에서 한글 UTF-8 cohort를 기본 ASCII 인코딩으로 읽어 실패했다. canonical status는 failed이고 result.json/result SHA는 없다. OOM이나 모델 forward 실패로 기록하지 않는다. `stmixer-failed-smoke-v2.json`에 실패 로그·영수증·부분 출력 해시를 보존했다. 명시적 UTF-8 읽기를 comparison command/runner/joint adapter에 국한해 적용한 수정과 LC_CTYPE=C 회귀를 검토했으며 다른 학습 command를 변경하지 않았다.

독립 comparison/queue/action/joint 51개 시험이 통과했다. model constructor/load 함수의 AST는 이전 strict-load 검증본과 동일하며 가중치·config·vendor·환경은 그대로다. 새 joint spec은 adapter와 test 두 파일 해시만 바뀌었고 모든 현재 binding을 다시 대조했다. 새 joint 명세 SHA는 B `8c12b8d184189573695e03ec4d99a3cedca5df30500371849e0d9c64b8eb048c`, L `3d330688aadc60f3c50c47d9b362d1cba06ce404cb965b9049505f3cb0ac8fb7`, STMixer `9b662cf66a689dc2c277624438a3b5e5cafae3aab60b85c4873ae0ac4128487e`다.

정확한 첫 재실행 준비도는 `native-boxes-v3-eight-model-readiness.json`, SHA256 `3fa9b61e5b496d35c92a1f7ce10f238e6134fe76053b308a9f7354d1706a1240`에 한정해 승인했다. 새 source digest는 joint `d8a44962bc41f010c6eb82ae325cddd74e8fded770cdfff06f18ff62f815870c`, encoder/R3D `7dcb22123f1f5715680a17d6eaf53aa6ed521208328615c301beccbd179d44fd`다. 이전 EVAD 좌표 오류 출력과 STMixer 실패를 소급 성공으로 바꾸지 않는다. 수정본의 실제 smoke 및 all45는 별도 확인해야 한다.

root commit `0624f5b7785ed4662f258fe7141dde22edb9ab1f`와 현재 11개 실행 파일의 정확한 바이트 일치를 `native-boxes-v3-committed.json`으로 확인했다.

## 수정 후 실제 smoke

| 모델 | 실제 attempt | 창 / 영상 / native frames | 독립 판정 |
|---|---|---|---|
| EVAD-B | `73b214d6facc4a01bfac9581a9a5fec9` | 7 / 6 / 24,155 | 출처·수치·native 좌표 일치 통과 |
| EVAD-L | `36efa618144344db9284ba6a69740ed1` | 7 / 6 / 24,155 | 출처·수치·native 좌표 일치 통과 |
| STMixer-B | `ee03c8ea379c44c083c0efa2617c127c` | 7 / 6 / 24,155 | 실제 출처·수치 계약 통과 |
| R3D EXP0064 | `5e066f42ccf349fa8db3406118297227` | 7 / 6 / 24,155 | 실제 출처·수치 계약 통과 |
| VideoMAEv2-B | `653f72c63fc44ea88bfb410672c7713b` | 7 / 6 / 24,155 | 실제 출처·수치 계약 통과 |
| V-JEPA2-L | `ad4064952d59473b8c6a16780ef0f2b1` | 7 / 6 / 24,155 | 실제 출처·수치 계약 통과 |
| V-JEPA2.1-L | `272c8df0d53b453e97b4fe70baa76a8c` | 7 / 6 / 24,155 | 실제 출처·수치 계약 통과 |
| InternVideo Next S2-L | `2adbff9e08b94478a609559106ae5346` | 7 / 6 / 24,155 | 실제 출처·수치 계약 통과 |

EVAD-B 결과 SHA256 `4b50911e1759397dcc4d7f2cda3f1eeb2d0e7b5e06816086732736d3cf74320e`를 실제 canonical 영수증과 대조했다. 저장된 700개 query의 원본 좌표와 normalized native action box×원본 크기의 최대 차이는 0.000152588 pixel이다. 이전 오류와 달리 700개 box의 면적은 모두 양수이며 threshold .7 이상의 6개 query도 모두 유효 box다. 이 query 수는 사람 수나 복구 성공 수가 아니다. 006의 .7 이상 query는 0개다. 모든 raw logits와 확률도 일치하며 새 source `d8a44962…`/spec `8c12b8d1…`가 정확하다. `native-boxes-v3-evad-b-smoke.json`, `native-boxes-v3-evad-b-coordinate-proof.json`을 근거로 **이 수정된 attempt만** 같은 조건의 root 승인 all45 전제에 인정한다. 이전 EVAD 결과의 좌표 오류 판정은 유지한다.

수정된 EVAD-L도 700 query의 저장된 normalized/original 좌표 대응과 raw logits, actual queue 출처 검사를 통과했다. 결과 SHA256 `1cdd11edb34670b64ff1f4028513c5efe2e12acb49ad15da2337b84bfc053af6`, 상세는 `native-boxes-v3-evad-l-smoke.json`이다. 이 새 source/spec의 동일 조건 all45 전제만 인정한다.

나머지 여섯 모델의 새 source 실제 결과도 전수 확인했다. 합계 8개 모델 각각의 고정 7개 창/6개 원본/24,155 native frames, 실제 성공 DB row/영수증/모든 결과·출력 해시, 유한값과 모델별 shape/의미가 일치한다. 통합 근거 `native-boxes-v3-all8-smoke-acceptance.json` SHA256 `d27401dab8ff55d967b96f8801488d5d3c2684f782d81bf949470f2f121034e4`이며, root의 `msg_5c479178022c` 조건부 all45 GO에 따라 실행 담당자에게 정확한 8개 attempt를 전달했다. **모델별 같은 source/spec의 전체 실행 전제만 충족했다. 전체45 완료나 행동 성능은 아직 인증하지 않는다.**

## 로컬 비교 표시·요약 코드 검토

root의 초기 renderer가 전체 대용량 JSONL을 한꺼번에 읽어 보관하고, 별도 head가 없는 모델의 요약에 climbing candidate 0을 표시하는 문제를 전달했다. 수정본은 canonical SQLite/receipt/result/spec를 검증하는 별도 `comparison_saved_evidence.py`를 사용하며 전체 행은 순차 검사하고 필요한 diagnostic 행만 보관한다. duplicate model/window, source/window 불일치, 전체 6,219개 누락을 거절한다. 수정 전 EVAD 좌표 증거가 없는 결과도 거절하며, 미측정 person/head count는 null로 구분한다.

실제 R3D/VideoMAEv2의 이전 성공 영수증으로 7개씩의 summary와 나머지 6개 미제공 상태를 확인했고, 원래 EVAD 오류 출력·중복 window·잘못된 source hash를 거절하는 CPU 시험을 수행했다. `local-evidence-helper-review.json`에 정확한 세 스크립트 해시와 결과를 남겼다. 원본 PTS 정지화면 선택 및 canvas의 각각의 x/y 배율은 소스 수준에서 대조했다. 기존 검수 답변은 정확한 snapshot 해시에 연결하며 새 박스 정답으로 승격하지 않는 설명을 유지한다. 이번 검토자는 실제 브라우저 재생·시각적 박스 대응을 확인한 것은 아니다.

## 새 task-head 입력 계획의 별도 감사

`head-plan-v1/manifest.json` SHA256 `53f0165b2fa437362117d7e00ee25edd382b609ab60103268ceee8d526dfeac0`의 3,984개 고유 fullframe 창과 4,309개 actor target을 독립 산술 및 실제 annotation으로 대조했다. 797개 train/validation label 파일을 재해시·읽었으며 source hash 792개, event group 33개다. train 양성/명시 음성 1,571/1,711, validation 411/291이다. 두 frame origin의 해당 actor 실제 box·class·event 내부, 원본 전체 annotation/event의 wall conflict, source/event split 및 protected test/school45 hash 비중첩을 확인했다. test label/pixel은 읽지 않았다. 16개 요청 슬롯은 실제 7개 frame을 반복한다. 독립 근거 `head-plan-independent.json`, 구현 시험 4개 통과 로그 `head-plan-tests.log`를 남겼다.

quarantine와 같은 바이트를 가진 한 clip은 보수적으로 제외됐다. **14개 target은 다른 이름의 같은 영상 바이트에서 합쳐져 window의 대표 label 경로와 target의 원래 label 경로·SHA가 다르다.** 예: `head-497f09de3cfca9402e96c296` 안의 `clip-e30b8fee4dc1046db97f6a98`. 같은 split/group이며 그 자체로 누출은 아니다. target의 `source_clip_id`와 고정 원본 manifest로 provenance를 복원할 수 있다. 후속 joint matcher는 대표 window label을 모든 target의 원본으로 취급하지 말고, 동일 query 중복·충돌 label 대응을 명시적으로 해소해야 한다. 이 구체적 우려를 root에 전달했다.

**입력/annotation 감사만 통과하며 학습 release는 아니다.** 실제 source bytes·decode/native PTS 확인, 불변 release, matching 기준·모호성·중복 query 처리, train-only fitting 및 validation-only 선택 계약은 후속 검토가 필요하다. validation 음성은 앉기뿐이므로 걷기·대기·되돌아가기 오경보 수준을 보장하지 못한다. 전체 화면 label은 공식 참조의 약한 장면 label이며 annotation이 없는 다른 사람까지 사람 검수 음성으로 확정하지 않는다.

### head-plan-v2 및 구현 초안 추가 검토

v2 SHA256 `28cd2ad0f57ec2230c8de5acf18dae56046ecf512e0e46f917de6c4c577add18`는 v1의 3,984개 window 표본/label/split을 그대로 보존했다. 4,309개 target에 각각의 source·annotation 경로/해시 및 실제 anchor index/PTS를 추가했음을 고정 원본 clip manifest와 대조했다. 앞선 14개 alias 출처 우려를 계획 수준에서 해소했다. smoke는 train 32/validation 8개이며 test가 없고, 두 split 각각 양성·음성을 포함한다. 근거 `head-plan-v2-delta-review.json`이다.

초안은 train만으로 표준화/균형 class weight를 계산하고, validation CE로 epoch를 선택한 뒤 validation 음성의 엄격한 quantile로 threshold를 정한다. unknown query를 음성으로 추가하지 않고, 양 frame-origin IoU≥.5의 최선 query에 한 가중치만 부여하며 충돌은 unknown으로 남긴다. 이는 공식 참조의 provisional threshold로 명시되고, 사람 검수된 동일 FPR 운영점이 아니다. 실제 fitting/모델 forward 없이 matching/threshold/feature completeness/CPU pixel/queue guard 초기 시험 19개를 실행해 통과했다.

다만 최초 코드에서 두 사전 release 차단 사항을 발견해 root에 전달했다. (1) head command와 데이터 reader가 기본 인코딩을 사용해 STMixer의 실제 한글 JSON 실패를 재현할 수 있다. 명시적 UTF-8 경로가 필요하다. (2) feature extractor는 전체 native 출력의 hash만 남기고 데이터를 버려 unmatched query, 최선 query/충돌 판정 및 native 좌표 증거를 다시 감사할 수 없다. 전체 query 근거를 파일에 보존하고 canonical feature proof가 그 byte hash·coverage·matching 대응을 검사해야 한다. head 원본 픽셀 준비 완료와 최종 수정 바이트/불변 release/큐 등록의 검토 전에는 feature 추출·학습을 승인하지 않는다.

## 보존 확인

실제 다섯 smoke 뒤 기존 보호 파일 6개와 이전 100개 jobs/100개 attempts의 정렬된 전체 row 값이 시작 snapshot과 동일했다. canonical counts는 새 성공 5건씩만 늘어 105/105다. 근거 `independent-joint-review/protection-after5smokes.json`이며 기존 DB를 변경하지 않고 SQLite 읽기 전용 연결로 확인했다.

## 남은 범위와 보고 제한

root가 승인한 전체 45개 실행과 task-head 추출/학습 계약은 아직 이 문서에서 인증하지 않았다. 준비되는 증거에 따라 별도 추가한다. protected school45/EXP0064 test를 학습·선택·튜닝에 사용하면 안 된다. 3FPS 원본에서 새 16x4/30 표본을 만들 경우 약 7개 실제 프레임의 반복이며 16개 독립 관측이나 5초 clip이라고 쓰면 안 된다.

공식 annotation 기반 약한 장면 label은 화면의 모든 사람에 대한 human negative 정답이 아니다. joint head는 예측 query와 annotation actor를 대응한 학습 자료 및 unmatched query의 unknown 처리가 별도로 검토돼야 한다. 입력에 GT box crop/proposal을 넣으면 독립 검출 비교 조건을 깨뜨린다. feature/AVA/native R3D 출력의 수치 유효성은 human precision/F1·동일인·침입 완료·독립 일반화 성능을 뜻하지 않는다.

### Head 최종 구현·실제 CPU 준비 검토 (실행 release 아님)

`heads/implementation-handoff.json`의 8개 소스 해시를 현재 바이트와 모두 대조했다. 앞서 지적한 locale 의존 JSON 읽기는 명시 UTF-8로 수정됐고, `native-outputs.jsonl`에 미매칭 query를 포함한 전체 adapter 출력을 보존한다. canonical predecessor 검사는 실제 성공 SQLite 행·영수증·두 JSONL 해시를 확인한 뒤 모든 matching/unknown/conflict/feature 결정을 다시 계산한다. 독립 실행한 22개 비-forward 시험(기존 21개와 NativeAuditTests 1개)이 통과했다. 실제 모델 forward 또는 head fitting은 이 검토에서 실행하지 않았다.

실제 준비 envelope `2a0e0c3f71d273a68229e8982b5cd3967c8b5117d8a46f17642592611cb0bb28`와 raw result `889e6d1a1d3da27feee68f866eea4397868ae0110582b21b71c12a7060746a81`를 비교했다. envelope 차이는 영수증 경로의 절대경로 정규화와 원본 binding/설명뿐이며 원본은 보존됐다. 792개 영수증을 직접 재해시하고 전체 3,984개 창·24,616개 native tick·원본 크기·timebase·source stat를 계획과 대조했다. 797개 annotation과 5개 alias 영상도 재해시했다. train/validation × 양성/음성의 첫 결정적 창 4개와 alias target 창 1개는 실제 RGB를 독립 재디코딩해 프레임 및 16-slot 해시가 일치함을 확인했다. 이는 792개 원본 전체를 독립 재디코딩했다는 뜻은 아니다.

독립 근거: `runtime/model-comparison/exp0066/independent-joint-review/head-final-source-and-preparation-review.json`, SHA256 `79a44fed8897f37860a6c6ab9128bc065200935ca0a2703af577cf6eeaba8fc1`. 실제 실행 preparation snapshot과 최종 prepare 소스의 차이는 UTF-8 입출력 지정 및 output.resolve()뿐이며 디코딩·선택 알고리즘은 동일하다.

최종 source SHA256:

| 파일 | SHA256 |
|---|---|
| prepare_comparison_head_data.py | bf79a63857606ed863a8b65132ac698bf1783fd5c6fa34119239b217bebd0cd2 |
| extract_comparison_head_features.py | 5d7986ccc6d45f874077cbfaaf558da524ed41b1f8d94b7c67a41fb6bf3d3f36 |
| train_comparison_heads.py | ff36daa7dde4299cfe10ce76c841484d808b232641a082113c35b1dc97dcb71c |
| comparison_head_command.py | 0ee920bb0ad140fff40e5fcdce0d3d5312091a9017e4379519098de72039a5ae |
| EXP-0066-head-protocol.md | 0dc9032ff5d489f3b2f4902221c146a1721c05b243d40ef262891164d5a82fd7 |

이 바이트의 **구현·CPU 준비 완료**는 수용한다. 실제 canonical queue 통합은 아직 없고, 이후 queue/source 변경을 포함한 최종 commit·source map·release·authorization 재검토가 필요하다. 현재 문서를 GPU/head fitting 실행 허가로 사용하지 않는다. validation 정상은 sitting만 있으며, 약한 공식 참조 label·저점수 자동 query까지 포함한 조건부 matching·7개 실관측의 16-slot 반복이라는 한계를 유지한다. 사람 검수 precision/recall/F1, 사람 검출 회복, 독립 일반화 및 침입 완료 성능은 미측정이다.

최종 중간 보존 대조: 수정 smoke 8건과 첫 all45 등록 뒤 canonical jobs/attempts는 117/117이다. 기존 100개 행의 직렬화 SHA256 및 보호 파일 6개는 최초 snapshot과 동일하다. 근거는 `independent-joint-review/protection-after8-corrected-smokes.json`이다. 신규 17개 행에는 보존한 실패·좌표 무효 시도도 포함되며 이를 성공 모델 수로 세지 않는다.

### 미적용 head queue 패치 독립 시험

root가 별도 runtime 경로에 작성한 `head-queue-integration/queue.py` (`35305f61943c2438fc62ffac6650b6d64a4bfa95105e754501c1b8119116b878`)와 `queue.patch` (`d345269472a95cf06fe1128aef5caabe9fd22b126a4510d363aa038617e57782`)를 읽었다. 실제 `orchestration/queue.py`는 현재 실행 바이트 `4b4eb83411055d630dd42c41b7fd8a8bd10e0128c355e87c3d057d7cd3292209`를 유지한다.

독립 임시 SQLite·합성 자식 프로세스 시험 6개 통과: 기존 행/명령 보존과 backup·멱등 migration, held lock/running/unknown 거부, feature 14,400초·train 1,800초 상한 및 비유한값/assignment 거부, 실제 상속 FD·동일 inode·lock contention과 feature CUDA0/train CUDA-hidden 전달, 성공 exit의 result 누락 실패, result가 있어도 실패 exit는 실패 유지, timeout 부분 산출물 보존과 lock 해제·retry 거부를 확인했다. 실제 모델이나 canonical queue에는 실행하지 않았다. 첫 시험은 `run_once`가 현재 production 모듈을 다시 실행해 staged 패치를 시험하지 못했으므로 오류 로그를 보존하고 staged `supervise_once`를 직접 호출하는 fixture로 수정했다.

근거는 `independent-joint-review/staged-head-queue-review.json`과 `staged-head-queue-tests.log`다. 이는 **별도 저장된 패치의 시험**이며 아직 실제 적용·commit·최종 release 검토가 아니다. 모든 raw 8개 전체 실행 종료 뒤 실제 소스에 적용한 바이트, source map, 독립 detached 실행 경로 및 승인 artifact를 확인해야 한다.

### Head 점수 표시 연결부의 추가 발견

`comparison_saved_evidence.py` SHA256 `8333dec2ad81345206f8fc4c95598820eedc24c4f20d31cc67dc0ef282accc45`의 새 `checked_head_scores`는 실제 head 영수증을 확인하지만 이후 점수 행의 model ID·원본 query 좌표/점수·고정 query 수·person+action candidate와 report의 source/input bindings를 충분히 대조하지 않았다. canonical-head 검사는 격리 목적으로 stub 처리한 합성 fixture에서 잘못된 `WRONG_MODEL`, EVAD query 1개, person score 0의 combined candidate true, 존재하지 않는 scorer binding을 받아들였다. 이는 canonical 출처 검사를 우회했다는 주장이 아니라 이후 대응 검사 누락의 재현이다.

`independent-joint-review/head-display-gap.json`과 `reproduce_head_display_gap.py`에 반례를 보존하고 root에게 전달했다. 원본/점수 JSONL을 정확한 window로 stream-join하여 native boxes/person scores/validity와 candidate를 대조하고 source bindings를 검증한 수정본 확인 전에는 head 표시 연결을 최종 수용하지 않는다. 실제 head 점수는 아직 생성되지 않았다.

수정 helper `8ae3bc7de1ac6350e529909b715b2a93c4cc3fb13ab986b5ff438c5bb2779730`는 정확한 7개 source/input binding을 재해시하고 raw/score 행을 순서·window 단위로 대조한다. model·native boxes/person scores·100/1 query 수·native validity와 person/action threshold에 따른 combined candidate 검사를 확인했다. 기존 10개 시험과 별도 독립 EVAD 100-query fixture를 통과했고, 99-query·다른 geometry/query index·낮은 person score/무효 박스의 combined candidate·누락 source binding 반례는 거부됐다. 이전 발견은 이 소스 수준에서 해소됐다. renderer `822fbd9f6e94dc6722c5229edf453791413c216e35da80a7a24490777dd67b23`, panels `ee2da99459f1b1365fcf382a66dfc53a9d8e0d9ecc03c2693c8d8f64f3e65803`은 task-head 점수를 AVA와 구분하며 intrusion completion으로 표시하지 않는다. 실제 head 산술·산출물·브라우저 재생 검증은 여전히 별도다.


### EVAD-B 실제 전체45 결과 — 독립 수용 (8개 중 첫 1개)

Attempt `02c84b75712f426384078b70720ee69d`의 canonical 성공 행/영수증과 실제 전체 JSONL을 읽었다. 45개 영상 각각의 native 프레임 수, 총184,300프레임, 고정 6,219개 고유 창, 원본 SHA·native PTS·출력 가용 시점을 대조했다. 45개 window-plan 파일 SHA와 queue config/input digest도 별도 확인했다. 모든 621,900개 query의 4좌표/원본 bounds/valid area/native normalized 좌표 대응, 80개 action logits와 sigmoid, person 2-logit softmax 대응을 검사했다. 실제 GPU peak allocated/reserved는 2,964,866,048 / 3,988,783,104 bytes다.

- result SHA256: `827966ffb9abe51dcc17857a9b3a5c226e795f1c3380b33902e35f4ffd8b575e`
- receipt SHA256: `61263c89135d567a9c2f56dbedf3dea19b50912986cd498447809591fb30dadc`
- windows SHA256: `a06ec894815dab7da5e0a78064848bf1416f97146f13d1e5f5d58253624e3b27`
- source SHA256: `d8a44962bc41f010c6eb82ae325cddd74e8fded770cdfff06f18ff62f815870c`, commit `0624f5b7785ed4662f258fe7141dde22edb9ab1f`.

근거는 `independent-joint-review/full45-evad-b.json`과 `full45-evad-b-metadata.json`이다. root 및 실행 담당자에게 결과를 전달했다. 이 수용은 저장 출력의 실행 계약·완전성·숫자 일관성에 한정하며 사람 검출 회복, CCTV 담넘기 precision/recall/F1, 침입 완료 성능은 여전히 미측정이다. 다른 모델의 전체 결과 완료를 대신하지 않는다.

root가 작성한 로컬 브라우저 증거 `local-headless-browser-v4-range.json` (SHA256 `a4b82a729375c99db13476519c43abd3b5ab595439c24a3df72690d88553404d`)도 읽었다. 별도 GPU-disabled Chromium의 localhost Range 서버에서 6개 원본에 대응하는 smoke 미리보기 7개(030 두 창), 모델 선택 63회, 각 play/seek/rewind 및 video error 없음이 기록돼 있다. 이는 root 실행 증거를 읽은 것이며 검토자가 브라우저를 독립 재실행한 것은 아니다. 전체45 최종 보기, 실제 head 보기, Orca 내장 브라우저 전달 완료로 확대하지 않는다.

### Head 실행 드라이버 v2 소스 검토

v1 `9f1c671d31c6e724c506e39fab254c64e073dca0a8d73f3e202d33a6afcd25ef`에서 이전 모델의 성공 단계가 현재 fixed-sequence grant와 같은지 확인하지 않는 재개 공백을 발견해 전달했다. 각 모델 내부 predecessor 검사는 있어도 다음 모델 smoke 시작 때 이전 모델이 다른 release/source로 수행됐음을 거부하지 못했다.

수정 v2 `92540dc2dc137a3ba8f95c060a57ee9da150063ee78035299c416cb9c58236d5`, handoff `d24aca6b1dfd54a0be6ca08d84dc6ef5eb0817053245b9d0be7f1eaaf934e9e1`의 모든 파일 해시를 대조했다. 모든 이전 단계의 invocation/prepared/completion 및 실제 등록 config·revision·code/source·base files·authorization을 현재 정확한 grant와 대조한다. 변경 grant/revision/code/source/release의 cross-model 재사용을 거부하는 시험을 포함해 8개 합성 시험을 독립 재실행했고 통과했다. 시험용 임시 파일은 검토자 runtime 디렉터리만 사용했다.

실제 raw8 완료 영수증·commit 동결·독립 fixed-sequence review·root GO, 정확한 순서의 21단계(7모델×smoke/full/train), idle queue/기존 행 보존, 실패 STOP/no retry, canonical 결과와 실제 종료 상태 확인 설계도 읽었다. 현재 receipt `independent-joint-review/head-driver-v2-source-review.json`은 **소스 검토만 수용**하며 `accepted_head_fixed_sequence_execution_release`가 아니다. 실제 큐 적용·commit/source map·8개 전체 raw 결과·정확한 release/grant 확인은 남아 있다.

Head 집계의 완료 분모도 검토했다. 초안은 `raw_summary.models`에서 예상 head 집합을 유도해 잘못된 완료 boolean이 모델 누락을 숨길 수 있었다. 수정 `summarize_model_comparison_heads.py` SHA256 `d3bdb318cbe38a57008a85c2a6804e5bbdfea4bfad81e6c207cf6b79a0ec2fe1`는 고정8 모델과 R3D 포함 각 실제 canonical full45의 상태/6,219창/184,300프레임/45영상 및 provenance를 요구하고 head 분모도 고정7로 검사한다. 누락 모델과 R3D smoke 대체 반례 2개 시험을 독립 실행해 통과했다. query/action-only와 native-person+action 수, regular/diagnostic·camera 구분, scene-level/conditional validation·sitting-only negative·사람 성능 null 표시는 유지된다. 실제 head 집계 결과는 아직 없으므로 소스 검토만 수용했다.

공식 사건 시간 문맥 진단 소스 `summarize_model_comparison_events.py` (`cc4bc7ced1358f5f80acd50f3a01e18524ca78041d44785316d330ed4ea18804`)를 읽고 3개 CPU 시험을 재실행해 통과했다. 실제 고정 EXP0065 per-video SHA `9d5cc2359cbc1f2bafdea0b9157c57a5d3202e1578ab2c9da3113c713e7b4295`의 공식52건·baseline37건·미확정1건을 확인했다. 공식 시간 안의 regular anchor만 포함하고 extra diagnostic anchor는 제외한다. 시간상 후보/행동 기준 미달/사람 조건 미달을 구분하며 동일인·gate·TP·침입 완료·online delay는 미측정으로 남긴다. 이 진단은 사건 recall 계산이 아니다.

Observation renderer `56ab9de594fd06e8dc6fa29f583a21687c14fddc4bd6d7f492c6e9ad86239488`와 Korean panels `644216afabf22e6b9304e6e483c6f2919f032be2381c415d403d4fc24c627dda`도 소스만 검토했다. 실제 panel SHA/원본 PTS를 대조하며 정지 관측 하나를1초 표시하고 원본 속도·연속 추적·박스 보간이 아님을 명시한다. 마지막 입력 가용 시점은 compute/queue 지연을 포함한 online 알림 시각과 구별한다. 실제8모델×52문맥 결과와 생성 sequence의 검증은 아직 수행하지 않았다.

### EVAD-B+FCOS 예비 미디어 실제 대조

`review-first-full45-v1`의 11개 원본·42개 supplemental 창을 독립 대조했다. 42개 EVAD-B payload는 이미 수용한 실제 full45 JSONL과 같고, FCOS 박스/점수는 각 원본 native PTS의 해시 검증 캐시와 같았다. 원본 anchor 프레임 42개를 CPU로 다시 디코딩·동일 크기 JPEG 인코딩해 현재 keyframe 파일 SHA가 전부 일치했다. 입력 MP4 42개는 각각16프레임·7.5Hz, 총672프레임을 디코딩했다. 입력 영상 모든 slot의 픽셀을 독립 재생성한 검사는 아니며 원본 픽셀 재현은 keyframe에 한정된다.

42개 panel SHA, 9개 관측 MP4의 SHA/총38프레임/0,1,…초 시각, 원본 PTS와 panel 소속을 확인했다. 이 9개 영상은 여러 정지 관측을 모은 것이며 연속 추적 영상이 아니다. 예비 보기의 all8/head/semantic 완료 flag는 false다. root 브라우저 증거도 42개 샘플·84개 선택(FCOS+EVAD-B)과 play/seek/rewind·error 없음으로 범위가 맞았다. 검토자가 브라우저를 다시 실행하거나 사람/행동의 의미를 확인한 것은 아니다.

독립 근거 `independent-joint-review/first-full45-media-review.json` SHA256 `92da1e4cae7910d282dc69303330f0c680d9470a99156c7c32184a2409242226`; comparison SHA `ec17d363e681d804e377d22ef1c27afeef2f495826f9ee9535c3d71f82589335`, panels SHA `bd7c809bf3bab3bcfec4935bb96f37dc0fcbf931d87788082a68f55ecc20c65c`, observations SHA `2daa270b559b8678ea26752130bb38964ab970c66f3a9da2e26a871420686b06`.


### EVAD-L 실제 전체45 결과 — 독립 수용 (누적2/8)

Attempt `4a58c755ac3749edb41d1c56a98144bf`도 전체 JSONL과 실제 canonical 영수증/행 검사를 통과했다. 고정45영상·6,219고유창·184,300native프레임, 영상별 프레임 수와45개 계획 SHA, source/config/input digest, 모든 query의 원본↔native normalized 좌표 및 logits/probabilities를 확인했다. GPU peak allocated/reserved는 4,702,206,464 / 6,075,449,344 bytes다.

- result SHA256: `745794e812b4672d1bd75cd306c2e8efa58ef913b9d12781a2b16e5e628ccd42`
- windows SHA256: `fee7239f02089f88be27bb5f2cbc11dd32126e252891a359ed9083725ece1a8a`
- receipt SHA256: `3babfeb403a6c1ff83e37547ea3f4e8a59879d7153cef44580f5160e3c65bb7b`
- spec SHA256: `3d330688aadc60f3c50c47d9b362d1cba06ce404cb965b9049505f3cb0ac8fb7`; source는 동일한 native-boxes-v3 `d8a44962bc41f010c6eb82ae325cddd74e8fded770cdfff06f18ff62f815870c`다.

근거는 `independent-joint-review/full45-evad-l.json`과 `full45-evad-l-metadata.json`이다. root와 실행 담당자에게 수용을 전달했다. 실제 성능·동일인·사람 복구·침입 완료 검증으로 확대하지 않는다.

### 원본 해상도 보기 v5와 인코딩 출처 v6

v5의 7개 원본 anchor를 독립 CPU 디코딩해 원본1920×1080 JPEG 바이트를 재현했다. 모델/window/이전 검수 payload와 작은 keyframe은 v4와 같고, native panel의 source-image SHA·원본 좌표 배율·3840×2552 출력 크기를 확인했다. 근거 `native-preview-review.json`의 renderer는 `0dd71f125ceac1d9d58235bdb4bc85f3a50dcf5213ba13ea0c8fe3f7dee2b2c3`, panel renderer는 `62471b15ba483623a533c902373413dbedf02235507a1c614824f81a78bb490b`다. root의 v5 브라우저 증거는7사례·63선택·native1920 전환·play/rewind·오류 없음이며 검토자가 브라우저를 재실행하지 않았다.

첫 검사는 v4/v5 input MP4 바이트 동일을 가정해 실패했다. 실제로7개 모두 MP4 SHA가 다르고 디코딩 픽셀도 작게 다르지만16프레임·PTS는 같았다. 이 실패와 수치 비교는 `native-preview-byte-identity-first-failure.log`, `native-preview-old-new-decode.json`에 보존했다. root가 기존 표현을 같은 샘플/렌더링 방식이라는 뜻으로 정정했고 정확한 인코더 차이 원인은 미확정으로 남겼다. 재생용 손실 압축 영상의 픽셀을 모델 입력 텐서와 동일하다고 인증하지 않는다.

v6는 별도 경로 `review-smoke-v6-native-provenance`에 원본 RGB slot SHA와 PyAV/OpenCV/libav 및 코덱·CRF·preset·pixel-format·rate·resize를 추가했다. 독립 CPU 디코딩으로7창×16칸=112개 RGB SHA를 전부 재현했고 v5 native/작은 JPEG와 모델 payload가 그대로임을 확인했다. 영상은 각16프레임·7.5Hz다. 현재 renderer SHA `a14b1c1aee91866fa9bd014100f17539c425dd2831a34ce9321499ecce19a6af`, comparison SHA `ad7016f934b97316a0616f0a0668b43c86df4d9ac276f3f378674a26effa629c`; 독립 근거는 `native-preview-v6-review.json`이다. 이 확인은 저장 자료·좌표·출처 검증이며 사람 검출/행동 의미, 전체8모델 완료, 실제 head 성능 검증이 아니다.


### STMixer 실제 전체45 결과 — 독립 수용 (누적3/8)

Attempt `8a321630f48b442ca7748914759cd222`의 canonical 성공 행·영수증·전체6,219개 창을 독립 검사했다. 고정45영상/184,300native프레임과 영상별 계획 SHA·프레임 수·입력 digest·동결 source가 일치하고, 모든100 query의 박스 경계/유효성, 사람2logit softmax와80AVA logit sigmoid 대응·유한값·시각을 통과했다. child/supervisor 저장 identity의 실제 종료도 확인했다.

- result SHA256: `2ee063332ee7415b9f67eedffffd0a83e44ac706b21b9af5ef3e598610798b66`
- windows SHA256: `d45f408225669b18edb23bc3023e4a7a8ee8f8a265769e784c6d135615dd9e0a`
- receipt SHA256: `4185d4f03203d87c5e6c46baa9cea28c7562a7c736886a4d107506d99fd0032a`
- spec SHA256: `9b662cf66a689dc2c277624438a3b5e5cafae3aab60b85c4873ae0ac4128487e`; source 묶음 `d8a44962bc41f010c6eb82ae325cddd74e8fded770cdfff06f18ff62f815870c`.

GPU peak allocated/reserved는2,575,862,784/2,610,954,240 bytes다. 독립 근거 `full45-stmixer.json`, `full45-stmixer-metadata.json`, `full45-stmixer-process-exit.json`에 기록했다. AVA 점수를 CCTV 넘기 확률·정답 사람 복구·침입 완료로 해석하지 않으며 남은5모델 전체 결과와 실제 head는 미완료다.


### R3D 실제 전체45 결과 — 독립 수용 (누적4/8)

Attempt `ee5981a15aeb4969995ab133c8df547a`의6,219창/45영상/184,300native프레임, 모든 점수 유한값·0–1범위·고정0.5 기준 판정, 영상별 계획/프레임 수·config/input/source·canonical 영수증과 실제 프로세스 종료를 확인했다. 점수 범위는0.11109647154808044–0.6452875733375549다. 기존 EXP0064 checkpoint를 새로운 전체 화면16프레임 조건에 적용했으며, 기존 actor-crop 성능·사람 행동 정답·침입 완료로 해석하지 않는다.

- result SHA256: `ac0cf8e4cdc43c7d28f8cc87867b1f31ac63c6f8796d059b9b310410bc8a7eb9`
- windows SHA256: `4a04b0aa08726d6e48aa4cf7124184d153df08dc36b6db607db83a702c121922`
- receipt SHA256: `15b15e7665861b25d5e41b36ddf72a1ecd464cb2538f78620f3ea108d8e3c84f`
- spec SHA256: `42fd653f6727348ee843323d32b873179cffadb6272d565f2429b239821d9fe4`; source 묶음 `7dcb22123f1f5715680a17d6eaf53aa6ed521208328615c301beccbd179d44fd`.

GPU peak allocated/reserved는231,705,088/255,852,544 bytes이며, 근거는 `full45-r3d.json`, `full45-r3d-metadata.json`, `full45-r3d-process-exit.json`이다. 남은4encoder 전체 결과와 실제 head는 아직 인증하지 않았다.


### VideoMAE 실제 전체45 결과 — 독립 수용 (누적5/8)

Attempt `2f85f753a2504ea7abfbe166d802da6b`의6,219창/45영상/184,300native프레임과 모든768차원 nonzero·finite 특징을 확인했다. 영상별 계획 SHA/프레임 수·config/input/source·canonical 영수증 및 실제 child/supervisor 종료가 일치했다. 넘기 점수는null이고 이 특징만으로 사람 박스나 행동 정답을 인증하지 않는다.

- result SHA256: `05dff274e473c3010b47430787e739a3aa09c38e6b2f277f3132a889b6c32047`
- windows SHA256: `8b0181f38f26a504373c7d568ac13b7201a08e8ffc71437eeee798e071da2a71`
- receipt SHA256: `0b84b3be63ebca7e27011c0e494747f1f1e57acd49f474cdd8a1423e0ca91f44`
- spec SHA256: `4cafaae8e57e5fc67948b3317c4dcab3645dc55fd673dc7c2c5318ea6d1f5935`; source 묶음 `7dcb22123f1f5715680a17d6eaf53aa6ed521208328615c301beccbd179d44fd`.

GPU peak allocated/reserved는733,531,648/864,026,624 bytes다. 근거 `full45-vmae.json`, `full45-vmae-metadata.json`, `full45-vmae-process-exit.json`을 보존했다. 나머지3개 encoder 전체와 실제 head는 미완료다.


### V-JEPA2 실제 전체45 결과 — 독립 수용 (누적6/8)

Attempt `64c8a4e94d7c44deafb269b6b7fcd85c`의6,219창/45영상/184,300native프레임과 모든1024차원 nonzero·finite 특징을 검사했다. 영상별 계획·프레임 수·config/input/source/spec·canonical 영수증과 두 프로세스 종료를 확인했다. 넘기 점수는null이다.

- result_sha256: `51448e2fc3f155fd340970dbf3f69712ea6366503219057cdd5c28f314ff0ed1`
- windows_sha256: `57b529e210fecd3784d12a0ff5ba6f50c53e34b38db4d1bd149190419df157a9`
- receipt_sha256: `5c5ff1dc7a3cc89b0ffa4fa9844aadeff1851472491339c63f1190176cc9f2bb`
- model_spec_sha256: `206e0e07a6313ee48e72b3eed25753dbe7eda517ed5a4387c116c24bd049c3e7`
- source_hash: `7dcb22123f1f5715680a17d6eaf53aa6ed521208328615c301beccbd179d44fd`

GPU peak allocated/reserved는1,892,184,064/1,944,059,904 bytes다. 근거는 `full45-vjepa2.json`, `full45-vjepa2-metadata.json`, `full45-vjepa2-process-exit.json`이며, 특징 출력을 사람 검출이나 넘기·침입 성능으로 해석하지 않는다. 마지막2모델과 실제 head는 미완료다.


### V-JEPA2.1 실제 전체45 결과 — 독립 수용 (누적7/8)

Attempt `7d47ac73df514e538ff95badf8042767`의 6,219창 / 45영상 / 184,300 native프레임과 모든 1,024차원 nonzero·finite 특징을 검사했다. 영상별 계획·프레임 수·config/input/source/spec·canonical 영수증과 두 프로세스 종료를 확인했다. 넘기 점수는 null이다.

- result_sha256: `fbabc763ed5c7d4cf5a1c0c1e96412477256b9770e142192b979b22d17ee7284`
- windows_sha256: `b6cb2ae81208a5ba4eebd38a8c1a3b2bf650888572bf85f75e664b5eca916c5d`
- receipt_sha256: `d6793e1abee3d2d776dc0b8644c02e4762a187561bc7ba1c4fbb2e67b80d1daf`
- model_spec_sha256: `63c6133ab0bf2d94dbe648dac90dc82f58f612a927309a40007a0ed820d6f847`
- source_hash: `7dcb22123f1f5715680a17d6eaf53aa6ed521208328615c301beccbd179d44fd`

GPU peak allocated/reserved는 2,069,168,128 / 2,214,592,512 bytes다. 근거는 `full45-vjepa21.json`, `full45-vjepa21-metadata.json`, `full45-vjepa21-process-exit.json`이다. 실제 InternVideo 전체 결과와 head 실행 검증은 아직 남아 있다.

### 8모델 점수표 실제 산술 검토와 임계값 표시 잔여 문제

새 panel renderer `b01dbad1d2bc87e73e626b2b25bf065e8bafc9635464b1d2d7ec2f38ee940cbf`의 점수표는 joint의 유효 박스·native 사람 기준을 통과한 후보 중 최대와 q index만 표시한다. encoder/R3D는 전체 장면 점수로 표시하고, head 부재를 0점이나 음성이 아닌 null로 보존한다. 낮은 사람 점수·무효 박스의 높은 행동 점수 제외, head 부재·장면 비지역화 반례 2개를 독립 실행해 통과했다.

실제 v6의 7이미지×8모델=56행을 저장 payload와 독립 대조했다. 각 R3D 점수와 고정0.5 판정이 일치하고 나머지7모델은 실제 head가 없으므로 score/threshold/candidate가 모두 null이다. 모든 panel SHA·native source JPEG SHA·3840×3172 크기도 확인했다. panel-manifest SHA는 `749a1d56811763cf34882bf0fd86b477aeee5fdc5910c9a73042b0a8f0d89cfa`; 근거는 `score-table-actual-v6-review.json`이다.

표와 최신 HTML은 threshold>1을 모든 점수 제외로 표시하지만, panel 상단 header에는 `.4g`가 남아 `nextafter(1,+inf)`를1로 반올림하는 문제를 발견했다. 같은 이미지 안에 상충하는 표시가 생길 수 있어 root에 `msg_bf59c87b0744`로 전달했다. 현재 실제 이미지는 head가 없어 이 경로가 실행되지 않았으며, 향후 실제 head panel 소스는 수정 확인 전까지 수용하지 않는다.

후속 수정 panel source `be148bba9a63a3c55b30cfc562269d0b71a78739560fd1a7a51ea0c8ba61f15e`는 header에도 같은 `threshold_text`를 적용했고 joint scope도 ‘사람 표시 기준 통과 후보 중 최대’로 명확히 했다. 두 반례 시험을 재실행해 통과했으며 실제 HTML formatter `146c3bdd85e9e034433b981937c72edcf98fc2cc4c51f71f30d7a14a15c072cf`를 Node에서 실행해1초과 경계가 모든 점수 제외로 표시됨을 확인했다. 소스 문제는 해소됐고 `score-table-fixed-source-review.json`에 수용을 기록했다. 이전 v6 실제 이미지 검토는 이전 source의 증거로 그대로 보존하며 아직 생성되지 않은 head 이미지 검토로 확대하지 않는다.


### InternVideo 실제 전체45 결과와 raw8 완료 증거 — 독립 수용 (8/8)

Attempt `8c00a20e847449ddb7a23f25f194587b`의 6,219창 / 45영상 / 184,300 native프레임과 모든 1,024차원 nonzero·finite 특징을 검사했다. 영상별 계획·프레임 수·config/input/source/spec·canonical 영수증과 두 프로세스 종료를 확인했다. 넘기 점수는 null이다.

- result_sha256: `be6e017faadcad01efe04c55ac6720d5195b76c0b6e999e6caf3f0bf88721807`
- windows_sha256: `100baf2be4692137909eaaef18575cb98de7c3b2f77dec3333e9427d4b0f7de6`
- receipt_sha256: `f3b7a43f1eb922f4295bec1cfa874a76ebf761e11670af8f87d6fbef20bb3f06`
- model_spec_sha256: `dd983c9877da65bc5aaf843fe315fd215e05447276ca6914780faaaf06f603b6`
- source_hash: `7dcb22123f1f5715680a17d6eaf53aa6ed521208328615c301beccbd179d44fd`

GPU peak allocated/reserved는 3,565,298,688 / 4,150,263,808 bytes다. 근거는 `full45-internvideo.json`, `full45-internvideo-metadata.json`, `full45-internvideo-process-exit.json`이다.

`independent-joint-review/raw8-completion-barrier.json` SHA256 `da9a32c122e0ef41520b3b454e7e3cd47b9c0f865f1c2cc8d905c3aa3e2dd8a4`는 고정 HEAD `0624f5b7785ed4662f258fe7141dde22edb9ab1f`의 정확한8모델 결과/영수증/stream 및 독립 감사 해시·실제 종료를 묶는다. 모든 stream을 다시 해시하고 최초100 jobs/attempts 행과6개 보호 파일이 시작 시점과 같음을 확인했다. 실제 검토된 driver의 `raw8_barrier` 함수도 통과했다. 최초 통합 시 EVAD-B의 오래된 metadata 증거에 새 boolean 필드가 없어 중단됐으며, 이전 증거를 보존한 채 같은 실제 결과를 현재 metadata 검사로 다시 확인한 `full45-evad-b-metadata-final.json`을 사용했다. 해당 감사 스키마 불일치 로그도 보존했다.

이 증거는 `eight_raw45_canonical_passes_complete`이며 `head_execution_authorized:false`, `semantic_performance_verified:false`다. 정확한 최종 head queue 적용·commit·source maps·release·root grant의 독립 검토는 아직 남아 있다.

### 실제8 집계와 공개용 수치 대조

저장된8개 stream 전체를 다시 읽어 112개 camera/role 그룹을 독립 집계했다. 모델별 regular6,177 / diagnostic42창, EVAD-B·EVAD-L·STMixer 사람 기준 통과 query 총5,476 / 6,535 / 6,696개, R3D 고정기준 후보592창 및 모든 adapter timing 합계가 일치했다. query는 인원수나 포착 성공 수가 아니며 후보창은 사건 수가 아니다. elapsed/load/peak memory는 실제 result와 같고 사람·넘기 precision/recall·침입 개선은 null이다.

Raw summary SHA `70ae4f53326e2d84ba3097a2360f2d0fc3c337ff70db9222c8fe4c22b1b68b9f`, 공개용 SHA `3a78842723c4d25cb88e2f00f0c13a13ed1fea9774821bc2169661e8adf1f132`를 확인했다. 공개용은 모든 모델 수치/그룹을 정확히 보존한다. 절대 경로 외에 top-level summarizer/verifier SHA와 중복 model_spec provenance 객체도 생략했으며, model_spec SHA 자체는 각 모델 필드에 남고 원문 source SHA로 코드 출처를 복구할 수 있다. 이를 root에 정확히 전달하고 두 top-level 코드 해시 보존을 권고했다. 증거는 `raw8-summary-review.json`이다.

### 실제 적용 head queue 파일 검사

Raw8 완료 뒤 root가 적용한 `orchestration/queue.py` SHA `35305f61943c2438fc62ffac6650b6d64a4bfa95105e754501c1b8119116b878`는 기존 검토 후보와 바이트 동일하다. 실제 import된 모듈을 대상으로 독립6개 임시 lifecycle 시험을 다시 실행해 통과했다. additive migration·backup·원래 행 보존·held lock/running/unknown 거부, feature/CPU child의 실제 상속FD와 GPU visibility, stage timeout/context, 결과 없는 성공·실패 결과의 오승격 방지·retry 거부·timeout partial/lock 해제를 검증했다. `applied-head-queue-tests.log`에 기록했으며 실제 canonical DB migration/enqueue는 수행하지 않았다. 최종 commit/source maps/release/grant 검토는 별도다.

### 최종 실행 후보 v1 차단 — 실제 alias 입력 계약 실패

커밋 `1ab54357b5f662fed472bb6709a8de5d00c5cc36`의 15개 실행 소스와7모델 map·spec, driver v2, raw8 완료 증거, 고정21단계 matrix, 실제 활성 배정과 idle 큐124행은 일치했다. 후보 SHA `75ffd8f477c08072c75fac271d09ccad1ae003e845238e0fd26f7da3160f4e0c`, weak-data release SHA `1c1d4387753e86b1a18fa92bcb95ab8ba9bec0ea9359d9f62356230aa7554ce4`의 실제 `comparison_head_command.input_contract` 호출은 첫 smoke에서 실패했다.

원인은 `orchestration/comparison_head_command.py:72`의 source_path 문자열 동일 조건이다. CPU 준비 영수증은 같은 SHA의 alternate-name 파일을 하나로 묶지만, 계획의22창(5개 SHA)은 영수증과 다른 동등 바이트 경로를 쓴다. source_size와 time_base는 모두 같았다. 예를 들어 `head-173b89f857616d2a1933e060` / SHA `0808bd25cdecfd5c34bc26b720daf2a09eb2dfc4ab14a101d40cb24f8c2c8e38`은 영수증14-59-00_a와 계획15-06-00_a 경로가 다르다. 이 계약은 전체 계획을 확인하므로 smoke 선택 여부와 무관하게 모든 모델 실행을 막는다.

실제 실패 증거 `head-final-candidate-contract-review.log`, 전22창 차이 `head-candidate-input-contract-rejection.json`을 보존하고 root에 `msg_e0becd1876ce`로 차단을 알렸다. 잘못된 경로를 무조건 허용하는 수정 대신 정확한 계획 alias/SHA/기하·시각/픽셀 근거를 유지하는 수정과 실제 alias 입력 계약 회귀가 필요하다. source 변경 뒤 새 commit·candidate/release binding의 독립 검토가 필요하며, **`accepted_head_fixed_sequence_execution_release`는 발행하지 않았다.** 실제 큐 변경·모델 forward·학습은0이다.

후속 alias guard 수정 source `ab2d2d7efb6ab4b9c9dd3e1a846f42563f48bcef1a3c891b3e71423c2e81df44`는 source SHA·크기·timebase를 유지하며, 다른 source_path는 immutable preparation의 정확한 path→SHA alias에만 허용한다. 현재 선택 파일의 SHA 검증도 그대로다. 테스트 source `5652813c2e15cb4bfc571f5b5ce162722b2617e2c994f8b4b9822cec14dae0d5`의2개 시험을 독립 실행해 실제22창과 무등록/잘못된SHA/기하·시각 변경 반례를 확인했다.

수정 뒤7개 모델 모두의 실제 smoke `input_contract`를 mock 없이 호출해 통과했다. source/label/pixel receipts/model/environment의 현재 binding을 읽기 전용으로 검사했으며, 이전 v1의 데이터 release는 이 계약 재현에만 사용하고 실행 권한으로 쓰지 않았다. `head-alias-fixed-smoke-contracts.json`과 로그에 기록했다. v1 실행 후보 차단은 역사로 보존하고, 새 commit/v2 release 확인 전까지 실행 승인 증거는 발행하지 않는다.


### 최종 v2 고정 순서 실행 준비도 수용

커밋 `36d14d4e01987d34eba066fb10313d2f98c21a3f`, revision `frozen-heads-v2`, 후보 `e67069fe3875f3621b57caf8e97250fef4413547c65139d44eddedd9368d8e03`, weak-data release `da8d99cae6ee07b99a6f1aeb3b8830f2b2e6b24f30b965293a05dce04a689df3`를 실제 source/git/spec/driver/data/raw8 해시와 대조했다. 변경은 검토한 alias guard와 시험뿐이며 나머지 실행 소스와 데이터·spec·driver는 같았다.

정확한 새 release로7개 실제 smoke 입력 계약을 다시 수행해 모두 통과했다. 각40개 원본·40개 label과 전체792개 pixel receipt를 검증했고 smoke는 train32 / validation8로 테스트가 없다. 고정7모델×smoke/full/train의21단계 matrix, 실제 활성 배정, idle 큐124 jobs/attempts 보존을 확인했다. root가 수행한 full encoder797 sources/797 labels 및 joint smoke 입력 계약 증거도 읽었으며, 해당 full 호출 자체를 검토자가 재실행한 것으로 표현하지 않는다. 최종 검사는 `head-final-v2-candidate-contract-review.json`에 있다.

**`head-fixed-sequence-execution-release-v2.json` SHA256 `cd1ec210b03c27cb87fed2f9ea3b6f4284ca7a0ff89787b11bb8a5732f7c789c`를 발행했다.** 상태는 `accepted_head_fixed_sequence_execution_release`이고 driver가 요구하는 exact core fields와 두 독립 검토 flag를 포함한다. 실제 root hash-bound GO·활성 담당·canonical queue/lock·resource check·정확한 predecessor·실패 STOP/no retry 조건은 그대로다. 검토자는 실행 권한을 대신 발급하거나 큐·GPU·학습을 실행하지 않았다.

이는 앞으로 수행할 고정 실행의 준비도 검토다. 실제 head 결과는 미검증이며, encoder는 weak full-scene·joint는 자동 matched query 조건부 validation이다. sitting-only 음성으로 사람 검수 오경보율이나 walking/waiting/turnback 기준을 맞췄다고 주장하지 않는다. 사람 precision/recall/F1·actor recovery·침입 완료·독립 일반화는 미측정이고, 학교45/이전 test로 모델·epoch·threshold를 조정하지 않는다.

공개 raw summary에는 권고한 summarizer/verifier 해시가 추가됐다. 최종 SHA `a8181499c00de8541b74270b2fa09ee36016905ad67f60fe3ca937dcda812fe4`의 모든 기존 모델 수치/그룹·한계가 같음을 독립 확인했으며 `raw8-public-provenance-final-review.json`에 기록했다.

### 실제 root GO 및 후속 결과 검토 범위

Root GO `msg_59624e24dcd6`와 `root-head-release-v2/root-go.json` SHA `b5633a6b6578f265374f9e3adde79ae1e19c4c6b9f29978e76bddace91606190`를 실제 driver `checked_grant`로 독립 검증했다. 승인된 v2 review·source·context·revision과 모두 일치하며, 검토자는 이 읽기 전용 확인에서 큐/GPU/forward를 실행하지 않았다. `head-v2-root-grant-review.json`에 기록했다. Root 요청에 따라 이 Dispatch를 유지해 실제 완료 단계/heads와 후속 CPU 점수 산술을 검토한다.

### 최종 지표 exporter 초안의 연결 검증 공백

초안 `export_model_comparison_metrics.py` SHA `053900afad23b0f10b0cafd31cc753c8591165b57384bb0615df10efa7eb1936`는 동일 raw-summary를 참조하는지만 확인하고 model별 head/event score_provenance 및 event/raw provenance가 같은지 확인하지 않았다. 서로 다른 head scoring 실행의 validation 요약과 사건 진단이 한 공개 자료에 섞일 수 있다. 또52개 unique row/37개 baseline flag만 검사해 실제 frozen reference의 video/id/gate/start/end/flag와 다른52개 집합도 허용했다.

독립 synthetic 임시 fixture로 위 두 불일치를 함께 넣어 실제 exporter가 metrics를 생성함을 재현했다. 이는 시험일 뿐 실제 결과로 등록하지 않았고 임시 산출물은 제거했다. `metric-export-initial-gap.json`, 보존된 초안 source와 재현 script가 근거다. 기존2개 denominator/semantic 시험은 통과하지만 이 연결 공백을 다루지 않는다. Root에 정확한 source/score provenance equality와 frozen52 reference field/set 검사, export-level 반례를 요청했으며 수정 전 exporter 소스는 수용하지 않는다.

### 실제 head 단계 검토 — VideoMAE smoke

VideoMAE `feature-smoke` attempt `3a795469682e4407b382a7b0fe0df7ba`의40창·768차원 특징을 보존 native output과 독립 대조했다. 모든 source/sample/RGB receipt와 train32(양성6/음성26)·validation8(양성2/음성6)이 일치했다. 실제 grant/config·canonical result/receipt·이전124행 보존·child/supervisor 종료를 확인했다. Result SHA `26e3d5f0391c628fccc95fd4d5547f4665973cc464c1977997dfe2a4d6aa9c42`, receipt SHA `ac16950730691feab79422f5df1e91f331b8d8c9a731db3a41a9e91ce7fac8f2`; 독립 근거 `head-vmae-smoke.json`이다. 전체 추출·학습 완료나 행동 성능으로 확대하지 않는다.

### 지표 exporter 연결 검증 수정 수용 — 실제 최종 결과는 대기

수정 exporter SHA `52125c99bff9eea8555275b4a2e870a7756faac6f6d827d86b04b4f18e51de7a`는 model별 raw/score provenance를 요약 사이에 정확히 대조하고 frozen reference SHA 및52개 video/id/gate/start/end/baseline flag를 검사한다. 실제 frozen reference와 검토된 raw summary에 synthetic score binding을 결합한 독립 검사에서8모델×2 provenance 불일치와6개 참조 필드 변경, 총22개 반례를 모두 거부했다. Export-level 임시 fixture를 포함한3개 시험도 독립 실행해 통과했다. `metric-export-fixed-source-review.json`과 `metric-export-fixed-tests.log`에 기록했다.

앞선 초안 공백은 이 정확한 source에서 해소됐다. 이 검토는 소스 계약 수용이며 실제7개 head 점수·사건 요약·최종 공개 지표 산술의 수용은 아니다. 실제 결과가 생성되면 그 bytes와 출처를 따로 검증한다. 재개 시 WEB pending 조회도 성공했고 답변 목록은 비어 있었다.

### 실제 head 단계 검토 — VideoMAE 전체 특징

VideoMAE `feature-full` attempt `3eb6972e63254d34bfacb01ee424e085`의3,984창 전체에서768차원 특징과 보존 native pooled feature가 정확히 일치했다. 픽셀 영수증·source/sample/분할과 train 양성1,571/음성1,711, validation 양성411/음성291을 독립 확인했다. 실제 grant/predecessor/config·canonical result/receipt·이전125행 보존·child/supervisor 종료도 통과했다. Result SHA `b6f81cf17567cc3f432428e02ce26582354bd159614abbacf3d1e4f5d9872fa5`, receipt SHA `58c73d3724c445cc13cb4bfca1f010b7b7a7068569437e3495a200c6c514ede1`; 근거는 `head-vmae-full.json`이다. 학습 결과와 학교 점수 검토는 별도이며 특징 추출 완료를 행동 성능으로 해석하지 않는다.

### 실제 head 단계 검토 — VideoMAE 학습·선택

Train attempt `3ad64050026c4d79bce3c3c805c6ce99`의100 epoch history/stream, checkpoint/selection/input·predecessor·grant 바인딩과 이전126행 보존·실제 두 프로세스 종료를 확인했다. 전체3,984 sample key/라벨/분할을 대조하고 train3,282개만으로 계산한 평균·population 표준편차와 class weight를 독립 NumPy 산술로 확인했다. 재학습이나 모델 forward는 수행하지 않았다.

최소 validation CE의 최초 epoch76 선택이 맞으며, 저장된702개 검증 점수/라벨에서 float64 nextafter 임계값 `0.45249477028846746`을 재계산했다. 공식 참조 TP408/FP14/TN277/FN3, 음성291개 중14개 통과(`0.048109965635738834`), 참조 precision `0.966824644549763`, recall `0.9927007299270073`이 일치했다. 사람 검수 precision/recall은null, 동일 인간 오경보율 검증은false, weak full-scene와 sitting-only 음성 한계는 유지된다. 학교45·이전test로 선택한 수치가 아니며 실제 침입 성능을 뜻하지 않는다.

Head SHA `405b22027463586aeafcc4eaef8d96769b9b6e48413d6bd5c4783db4f1aecbaa`, result SHA `06739387dcfada407323f28adf07844fbd5a407557fad9b154e1b48ae94a8199`, receipt SHA `e2ee8181f89bc24099b838f5a188e6976a2ff04c51a8841aef16373a4c07eac8`; 독립 근거 `head-vmae-train.json`이다. 이는1/7개 head 검토 완료이며 학교 저장 점수와 나머지6개 head는 아직 별도 검토 대상이다.

### 실제 head 단계 검토 — V-JEPA 2 smoke

V-JEPA 2-L `feature-smoke` attempt `aac11eed7bf74e049202a6df58f59373`의40창·1,024차원 특징을 native output과 독립 대조했다. 고정 train32/validation8 및 양성6/2·음성26/6, 모든 source/sample/픽셀 영수증, grant/predecessor·canonical binding, 이전127행 보존과 두 프로세스 종료가 통과했다. Result SHA `ec415cfc5cd2ce715acb03a1bc284f916caac582b7b239877eb967a286f282b2`, receipt SHA `322ce1301ab16e8c97138e642e5606f9d9e8217e21d1eabf8c936b9bde6bb63a`; 근거 `head-vjepa2-smoke.json`이다. 전체 추출과 학습·학교 점수는 별도 대기다.

### 실제 head 단계 검토 — V-JEPA 2 전체 특징

V-JEPA 2-L `feature-full` attempt `0d3c12fcc4f04d96b703464d0255c88b`의3,984창 전체에서1,024차원 특징과 보존 native pooled feature가 정확히 일치했다. 고정 source/sample/픽셀 영수증과 train 양성1,571/음성1,711·validation 양성411/음성291, 실제 grant/predecessor/config·canonical binding, 이전128행 보존과 프로세스 종료를 확인했다. Result SHA `82c95373d9557a8a68ee2ac7bd193197abe3c2af85758f39334cb044baf2908a`, receipt SHA `03ea294a3504258e2e2f41914ee37e882bac5faa8f69cdd3dda49c14d41069aa`; 근거 `head-vjepa2-full.json`이다. 학습 선택·학교 점수와 행동 의미 검증은 별도다.

### 실제 head 단계 검토 — V-JEPA 2 학습·선택

Train attempt `6062bfea7a7740439f22a7b60b0ba691`의100 epoch 기록과 모든 checkpoint/selection/input·predecessor·grant binding, 이전129행 보존과 실제 프로세스 종료를 확인했다. 전체3,984 sample key/분할/라벨 및 train-only 평균·population 표준편차·class weight를 독립 계산했다. 재학습·모델 forward는 없다.

최소 validation CE의 최초 epoch7, float64 nextafter 임계값 `0.012240618467330934`, 공식 참조 TP411/FP14/TN277/FN0이 저장된702개 검증 점수/라벨의 재계산과 일치했다. 참조 FPR `14/291`, precision `0.9670588235294117`, recall `1.0`이며 weak full-scene·sitting-only 검증 범위다. 학교 사람/행동 정확도나 일반화 성능으로 확대하지 않는다.

Head SHA `4c74115eb1f16c38b61b94f4bdbdd498bab0f6b05b004383a8a76e975c4f72c1`, result SHA `fe37bed3992474f6ddd680713e4f72f582134f68cc79c785fd29530fef4ac374`, receipt SHA `e5c3e9c63c6927f0d86c6703d6ce5bfa1411abe7e8fd51703b8f8af2b52321ee`; 근거 `head-vjepa2-train.json`이다. 검토 완료2/7개 head이며 나머지 학습과 실제 학교 점수 검토는 미완료다.

### 실제 head 단계 검토 — V-JEPA 2.1 smoke

V-JEPA 2.1-L `feature-smoke` attempt `9ab166a4e6624692bb85517b1c593c9e`의40창·1,024차원 특징/native output, 고정 train32/validation8 및 양성6/2·음성26/6, source/sample/픽셀 영수증, grant/predecessor·canonical binding, 이전130행 보존과 두 프로세스 종료가 독립 검사에 통과했다. Result SHA `4fb80a87223fa19c0045668f653788413a7765f257774eff7421709b3b8bc346`, receipt SHA `fafa31cb53b0455e24070f7b0acdbd2bc583874e2d9b9892ecb10c700f7eb9ad`; 근거 `head-vjepa21-smoke.json`이다. 전체 추출·학습·학교 점수와 의미 성능을 인증한 것은 아니다.

### 게시 중간본과 전체11후보 전후 비교 범위 검토

Root의 `msg_ed00130805fe`에 따라 paired-box 문서·YOLO 추가 명세·게시 초안을 읽었다. 현재 frozen-head는 박스 생성 가중치를 바꾸지 않아 박스 복구 개선 증거가 아니라는 구분, 검출6구성/영상인코더4구성/R3D기준선의 전체11후보 유지, 같은 대상·시점 비교와 정상 오검출, 검증된 박스·행동 정답 확보 및 test/학교 촬영그룹 보호 요구는 적절하다. 향후 추가 미세조정의 실행 설정 동결이나 준비도 인증으로 해석하지 않는다.

추가 ZIP SHA `d8329fa91aa1016851f12aa70ff91d4b0251836f4bde79f7ab0734eef95b49d2`와 intake의5개 파일, 로컬 YOLO m/l/x 세 가중치의 바이트 크기·SHA를 모두 독립 대조했다. 모델 로딩·다운로드·forward·학습은 수행하지 않았다. [Ultralytics 공식 YOLO26 문서](https://docs.ultralytics.com/models/yolo26/)에 m/l/x Detection 지원이 명시되지만, 이는 로컬 설치 버전의 실제 출력 분기/NMS 및 호환성 검증을 대신하지 않는다. 명세의11모델/추가6조건 수와 현 실행 보존 상태도 일치한다. WEB pending 조회는 성공했고 비어 있었다.

두 게시 상태 문구를 root에 즉시 수정 요청했다. YOLO addendum은 실행 순서 답변을 아직 기다린다고 쓰지만 최신 paired-box/JSON에는 전체11후보 유지 정정이 반영돼 있다. Results 도입부도 학습·검수 자료가 진행 전이라고 쓰지만 현재2개 실제 head 검토와 예비 미디어가 존재한다. 전체 미완료와 부분 완료를 정확히 나눠 기록해야 한다. 근거 `publication-scope-initial-review.json`, 메시지 `msg_419292c1c7c1`·`msg_100986120393`다.

Exporter와 시험은 앞서 수용한 SHA `52125c99bff9eea8555275b4a2e870a7756faac6f6d827d86b04b4f18e51de7a` / `d5d68ec9ea77a57e5348f24db7accb677629b8c1f44e43073069abfc2ee7f22c` 그대로다. 동일 바이트의3개 시험·22반례 검증을 재사용하며 미생성 최종 지표를 인증하지 않는다. 실제 게시 checkout/commit의 바이트 일치와 최종 전달 상태는 아직 별도 확인 대상이다.

### 실제 두 학교 점수·공개 부분 스냅샷 수용

Root 요청 `msg_3c0b068ef9df`에 따라 VideoMAE/V-JEPA 2의 실제 저장 학교 점수 각6,219행(정규6,177/진단42)을 검증했다. Canonical raw pass·학습 head·영수증·가중치·7개 source/input binding과 정확한 원본 창·보존 박스/점수·고정 임계값·의미 상태를 대조했다. 학습이나 모델 객체/forward 호출 없이 NumPy로 저장 float32 정규화와 float64 선형식·sigmoid 산술을 독립 계산했다.

저장 점수와 독립 산술의 최대 절대 차이는 각각 `6.545581691663749e-7` / `5.351777188078444e-7`이다. 둘 다 해당 전체 점수의 최소 임계값 거리 `0.00021186470985407047` / `0.000004548579454423732`보다 작으므로 모든12,438개 후보 결정이 일치한다. 보수적인 float32 누적오차 상한 안의 창은 각각7/170개지만, 실제 관측된 독립 산술 차이로 임계값 결정이 달라진 창은0이다. CPU 시간 합계도 저장 결과와 일치하며 온라인 경보 지연으로 해석하지 않는다.

VideoMAE score result SHA `9301f6aabcf80b8ea71b714a9ca087f69aa871d75c589d2c84af4c5440261ae1`, scores SHA `a8b1214f99ee99afe4d0242784cef32d8e8f6f3b78c10c422ab58e3aed41e7af`; V-JEPA 2 result SHA `fac97288c0d26e3adfbc6df4618396eea0e41677f07523887b087c17399c78eb`, scores SHA `9a8a719b43324d76ba792a8b6f49e854ed1d9298ead44851e19ac925b26b51b4`다. 근거는 `school-scores-vmae.json`, `school-scores-vjepa2.json`, `school-two-score-public-snapshot-review.json`이다.

공개 `head-progress-snapshot.json` SHA `eb331a3880c8026aca06a88797bb64c170b6711d34aa156fde8ed5f9141a2ec0`의2개 실제 head/선택 수치/영수증/학교 점수 해시와2/7·전체11후보·paired 미세조정 미완료·학교 사람/행동 성능null 상태가 정확하다. 학교 정규 후보 창 수는 VideoMAE2,742/V-JEPA 2 4,676이지만, 이는 사람이 검수한 성공 수나 성능 순위가 아니다. 앞으로 생성될 나머지5개 head/학교 점수는 이 검토에 포함하지 않는다.

### 검출 추가 학습용 선택 주석 개수 감사와 게시 문구 수정

Root 요청 `msg_77f8d0e5c9ba`의 감사 source SHA `9ccf66dd3861fb39b561031261d79429f73e32c2f1b36d1b727aea1ec028c8b7`와 실제 `audit-v2.json` SHA `a3d7e9f4aec9243c18d23389ce4afa72e3c65cab9d0fd4a7214c8f7f2ab2b852`를 읽고 별도 산술로 재계산했다.3,984창·4,309선택 target 발생·4,298고유 actor/frame 후보·797라벨 해시, train/validation27/6그룹·652/140source SHA, 분할 간 중복0, 누락 box pair0, 유효 기하4,309·양쪽 origin 좌표 차이4,162, 동일 후보 binary 충돌0이 일치한다. 추가 좌표 경계 검사도 화면 밖 box0이다.

이는 전체 보이는 사람의 완전한 정답이나 모든 origin 의미가 검수됐다는 뜻이 아니다. 검증 음성의 sitting 편중과 선택 주석 범위를 유지하며 detector training release는false다. 원본 픽셀·보호 test/학교 라벨·모델을 읽거나 실행하지 않았다. 근거 `paired-detector-label-count-review.json`이며 공개 `paired-data-readiness.json`은 실제 v2 감사와 동일한 내용이다. 초기 corner-list 오계수 감사는 사용하지 않았다.

앞서 지적한 results의 진행 전 문구와 YOLO addendum의 답변 대기 문구는 모두 현재 사실에 맞게 수정됐다. 현재 부분 게시 문서·스냅샷을 `publication-current-corrections-review.json`에 정확한 SHA로 묶었다. 실제 게시 commit/checkout 바이트 검증과 전체 작업 완료는 별도 대기다.
