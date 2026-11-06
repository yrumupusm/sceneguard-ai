# EXP-0064 행동 관측층 구현 인계 — 실행 전

2026-11-06. EXP-0063 고정 통합 계획에 따른 **별도 advisory 구성 구현과 CPU 준비만** 수행했다. 실제 행동 모델 로드·GPU 추론·canonical 큐 등록/변경·기존45 원본 픽셀 디코딩·기존 사건 규칙/상태 변경은 없다. 학습·단독 평가 완료, 최종 독립 검토와 root GO 및 실제 큐 migration/등록은 별도로 필요하다. 이후 root가 GPU 작업/authorization이 아직 없음을 확인하고 2026-11-06 13:48:38 UTC 안전한 source window에서 queue.py 최소 수정 권한을 명시 확장했으므로 그 소스 패치는 구현했다. 코드 커밋은 실행 중 학습의 HEAD 바인딩을 보호하기 위해 root의 안전한 시점 지시까지 보류한다.

작업 시작에 `docs/WEB_REVIEW_WORKFLOW.md`의 기존 가상환경 `pending --include-acknowledged`를 실행했고 `{"requests": []}`를 받았다. 검수 DB 변경이나 새 사용자 질문은 없다. 전체45 정답·공식52 시간참조·006 미확정·008 보류를 모델/임계값 선택에 사용하지 않았다.

## 구현 및 보존 계약

- `scripts/prepare_action_regression.py`: 원본 PTS0에 고정한 3FPS 목표 격자와 가장 가까운 native PTS를 선택한다. 동률은 앞 프레임이다. 실제 PTS/native PTS/time_base/원본 프레임 번호를 보존하고 전체 격자에서 8표본/3표본 간격 창을 만든다. 같은 track_id의 observed=true 실제 박스가 여덟 표본 모두에 있어야 실행 대상이다. 예측 박스·보간·소실 채움·영상/트랙별 예외는 없다.
- 보호된 `/source/analysis/analysis.json`의 `parents[2]`에서 measurement를 찾고 `source/tracking/frames.jsonl`을 읽는다. `input-manifest-007.json`은 `E01_007`로 검증한다. 잠긴 tracking stage의 frames artifact 해시와 요청/분석/원본/AFTER 바인딩을 사용한다. 준비 단계는 기존 baseline lock에 묶인 원본 해시를 재사용하며, 실제 실행 전에는 선택된 원본과 소비 입력 해시를 반드시 다시 검증한다. 수만 개 과거 입력 전체 재감사는 하지 않는다.
- `orchestration/action_inference_command.py`: canonical Run/Task/Dispatch/owner의 현재 정확한 worker liveness, 같은 canonical 큐의 실제 running job/attempt, supervisor identity, 등록 input/config/source/commit 해시, 실제 gpu.lock의 상속된 held FD, GPU0 및 6144MiB 자원 문턱을 검사한다. 독립 검토·완료한 단독 평가·root GO·명시 GPU GO를 정확한 소스/입력/HEAD에 바인딩해야 한다. 소스에는 `action-infer` 연결을 구현했지만 실제 canonical 큐 schema/job에는 아직 등록되지 않았고 running attempt 없는 우회 실행은 거절된다. 자동 재시도는 거절한다.
- 단독 학습의 같은 attempt에 속한 성공 receipt·adjacent `action-training-config.json`·최종 `result.json`·10 epoch history·`best.pt`·전체 test score inventory를 확인한다. manifest/config/baseline 파일 바인딩, 고정 설정, 최소 validation loss로 선택한 epoch, checkpoint 해시, test clip ID의 정확한 집합/개수/고유성/라벨, 유한 0..1 점수 및 점수로 다시 계산한 시험 보고서가 일치해야 한다. 최종 checkpoint 내부의 config/epoch/training manifest도 모델 생성 전에 확인한다. 45 결과를 보고 재선택하지 않는다.
- `scripts/infer_action_regression.py`: guarded queue child에서만 모델을 생성한다. 전체 영상은 EOF까지 한 번 순차 decode하면서 **모든 native PTS**를 tracking과 대조한다. 선택한 3FPS 프레임만 RGB로 바꾸고 표본 원본 이미지는 deque 최대8개, 전처리 clip은 batch 최대4개로 제한한다. 같은 정적 union ROI를 여덟 관측에 적용하며 기하 합집합의 폭3배/높이2배 확장·clamp·112 letterbox·훈련과 같은 RGB mean/std·batch4 AMP float16을 사용한다. 마지막 batch는 잔여 수를 그대로 처리한다.
- 각 창은 track/표본 목표·실제 PTS/native frame/관측 박스/ROI/점수/모델·소스·tracking·계획·queue attempt provenance를 저장한다. `available_after_pts`는 마지막 실제 표본 PTS이고 `batch_flushed_at_source_pts`는 해당 batch를 실제 내보낸 원본 시각이다. 둘을 첫 실제 통지 시각으로 부르지 않으며 실시간 통지는 미측정이다.
- 점수0.5 이상은 오직 `climbing_action_candidate`다. 기존 AFTER JSON 아홉 개씩 총405개를 별도 결과 디렉터리에 원래 바이트 그대로 복사하고 원본/복사본 해시를 모두 대조한다. 상태·첫 통지·확인·해제는 재직렬화하거나 갱신하지 않는다. 기존 카드와는 시간 구간의 관측상 겹침만 연결하고 동일인/원인/침입 완료를 추정하지 않는다. 침입 수치 동일성은 이 구성의 보존 성질이며 정확도 개선이 아니다.

학습의 공식 actor annotation ROI와 이번 기존 검출/추적 ROI는 입력 분포가 다르다. 관측 부족은 사람 정답으로 확인된 detector FN이 아니다. 행동 annotation-reference 불일치, 기존 침입 판정 오류 및 인과 진실은 별개이며, 현재 정답 부족으로 precision/recall/F1 및 오류 진실은 null이다.

## 실제 CPU 준비 결과

실행 대상 계획은 `outputs/action-recognition/exp0064/regression-plan-v2/manifest.json`이다. 각 영상 JSON에 모든 표본·실행 창·누락 위치·출처 해시와 명시 분모를 저장했다. 최종 v2의 전체45 source plan을 고정 tracking에서 독립 재계산하여 완전히 같은지 대조했다. 원본은 container header만 읽었고 원본 픽셀/모델은 읽지 않았다.

| CPU 집계 | 값 | 의미 |
|---|---:|---|
| 원본 native tracking frames | 184,300 | 전체45 전구간 |
| 선택한 3FPS native 표본 | 18,459 | 실제 PTS 유지 |
| global temporal windows | 6,053 | 트랙과 별개인 전역8/3 격자 |
| 관측된 track ID 합계 | 1,408 | 사람 수 정답 아님 |
| 전체 track × global window 분모 | 187,875 | 이력 감사용 |
| 같은 track 실제8관측 충족 | 3,573 | 추론 예정 창, 아직 score 없음 |
| 실제 관측이 하나 이상인 창 분모 | 8,630 | eligible 3,573 + partial 5,057 |
| 일부 관측 부족 | 5,057 | 주요 coverage 부족, detector FN 아님 |
| 관측0인 track/window 조합 | 179,245 | track lifetime 바깥 조합 포함, 운영상 누락으로 세지 않음 |
| 전체 감사용 관측 미충족 창 | 184,302 | 0관측+부분 관측의 cross-product 합계 |
| 창·표본 관측 분모/부족 | 1,503,000 / 1,456,266 | 전체 감사용8표본 분모 |

`E01_011/013/015/017/035`의 canonical all45 AFTER 경로는 기존 `false-confirmation-guard-v1/run-001/after`의 symlink 디렉터리다. 초기 strict lookup이 이를 미등록 경로로 거절한 뒤, 실제 target이 이미 같은 immutable lock에 묶여 있음을 확인했다. canonical alias와 resolve한 target을 함께 기록하고 잠긴 target 해시를 대조한다. baseline을 새로 동결하거나 변경한 것이 아니다.

## 계획 v1 재생성의 증거 한계

처음 생성한 미등록 v1을 보고한 뒤, root의 분모/flush 시각 수정에 따라 이 작업자가 소유한 새 출력만 재생성하기 시작했다. **그 재생성 tool call 중에** root의 “v1 보존·v2 생성” 후속 지시가 도착했고, 읽기 전에 초기 v1 디렉터리가 삭제되었다. 초기 v1 해시는 삭제 전에 독립 기록되지 않았다. 따라서 현재 v1은 이전 생성 규칙에서 추가 count 필드 두 개를 제거해 다시 만든 **recreated diagnostic**이며, 최초 v1의 바이트 보존을 입증했다고 주장하지 않는다.

현재 recreated v1과 v2의 45개 실제 `samples`, eligible `windows`, `missing_windows`, 입력 및 baseline 해시 목록은 정확히 동일하다. 추가로 최종 v2를 고정 원본 tracking에서 독립적으로 모두 재계산하여 일치시켰다. 모델 추론은 한 번도 없으며, 이 재생성은 보호 baseline/원본/큐를 변경하지 않았다. 이 경위 이후 파일은 삭제하지 않는다. v2는 첫 실행 후보 manifest로 별도 검토해야 한다.

## 검증

`.venv-cv-batch02/bin/python -m unittest tests.test_action_regression tests_orca.test_action_inference -v`: **18개 CPU 시험 통과**. 29.97/native PTS·global grid·observed=false/다른 ID의 대체 거절·미래 박스 배제·ROI 훈련 일치·trainer decode와 실제 letterbox 픽셀 동등·ring8/batch4·flush 시각·EOF/PTS 실패·바이트 보존을 검증했다. authorization/현재 assignment/상속 FD/실제 running row/자원/미등록 queue source 거절 및 완료 단독 평가의 누락·중복·잘못된 라벨·범위 밖/비유한 점수·다른 manifest/config/baseline 계약을 반례로 검증했다. 큐 row 시험은 임시 SQLite 파일과 CPU fake scorer만 썼으며 실제 큐를 변경하지 않았다.

추가 실제자료 CPU 대조는 v2 `verification.json`에 기록했다. 45개 manifest 재계산·184,300 native frames·405 baseline 파일 바인딩·recreated v1 대비 표본/창 동일성을 확인했다. 실제 canonical 큐 schema/job가 아직 미등록이므로 실제 canonical supervisor의 `action-infer` 성공 실행은 이 단계의 시험 범위가 아니다.

## root의 권한 확장으로 구현한 최소 queue.py 패치 — 실제 DB 미적용

처음에는 아래 내용을 권고로만 준비했다. 이후 root는 GPU authorization/job가 아직 없고 CPU 준비가 계속되는 안전한 coordinated source window임을 확인했으며, 위 Orca 후속 지시로 이 작업자에게 queue.py 최소 수정 권한을 확장했다. 다음 항목은 소스에 적용했으며 실제 canonical DB는 변경하지 않았다. 기존 training adapter/trainer/config/builder의 바이트는 유지했다.

1. `source_hash('action-infer', config)`가 이 adapter의 `digest(sources(config))`를 반환하도록 분기한다.
2. 기존 backup+held-lock+무결성 보존 migration에 `include_action_infer=False`를 추가하고 target/가드/새 CHECK/backup label에만 `'action-infer'`를 추가한다. 기존 job/attempt와 action-train을 모두 유지한다. 활성 reservation/unknown job에서 migration을 허용하지 않는다.
3. enqueue command allowlist와 CLI choices에 action-infer를 추가한다. `validate(config,input_value,self.runtime)` 뒤 등록 context가 enqueue의 run/task/dispatch/owner와 같고 job_key가 `job_key(config)`와 같은지 확인한다. 기존 finite timeout 상한3600초를 유지한다. enqueue 직전 위 migration 분기만 연결한다.
4. `supervise_once`의 command 분기에 `action_inference_command.command(config,inputs,runtime,attempt,lock.fileno())`를 연결한다. 기존 `pass_fds=(lock.fileno(),)`를 유지하고 action-infer에도 `SCENEGUARD_GPU_LOCK_FD`와 `CUDA_VISIBLE_DEVICES=0` env를 상속한다. 프로세스 그룹/pidfd/heartbeat/timeout 코드는 그대로 사용한다.
5. `_finish`에 기존 action-train과 같은 비합성 실행 receipt를 추가한다. 실제 command/job/assignment/source/input/config/commit/attempt, interpreter와 `output_path('all45',attempt)`를 기록한다. exit success만으로 성능 성공을 주장하지 않는다.
6. `retry` 분기에서 이 adapter의 `retry_guard`를 호출하여 자동/암묵 재시도를 거절한다.
7. private snapshot migration 보존/idempotency/foreign_key_check, 기존95 job/95 attempt 바이트 값 보존, CPU FD/env supervisor probe와 기존 queue/training 회귀를 검증했다. root가 독립 diff 검토 뒤에만 소스 커밋과 새로운 source/input/HEAD authorization을 허용한다. 실제 큐 migration/등록/추론은 아직 수행하지 않는다.

실행 config의 stage는 `all45`, files는 `manifest`, `baseline_lock`, `checkpoint`, `training_result`, `training_history`, `test_scores`, `training_config`, `training_manifest`, `training_receipt`, `training_queue_config`의 **absolute path + sha256**다. authorization에는 현재 context/stage/input_hash/sources/code_sha와 `confirmed`, `inference_authorized`, `standalone_evaluation_complete`, `independent_review_passed`, `root_go`, `explicit_gpu_go`가 모두 true여야 한다. 값은 root가 실제 완료 결과/새 실행 assignment를 확인한 뒤 작성하며 이 구현 작업의 dispatch를 재사용하지 않는다.

## 해시와 남은 단계

| 파일 | SHA256 |
|---|---|
| immutable EXP-0063 integration plan | `25e9a1d0c839c45a29f658fb247ee2658738f378f921c62bba0a6ab0896c3868` |
| frozen EXP0062 baseline attempt-002 lock | `3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40` |
| recreated diagnostic v1 manifest | `ca28d0622eda1b43d2940a5735e453a968116702b9d5edd7976be584fca2d3ef` |
| candidate execution v2 manifest | `f8bea6c8b4b36d5d09daf8f3b43a7e8923319ef5bde3b5c4e5cd5f00f0f7cb17` |
| v2 CPU verification | `5bc641a1a6d678d66b0109e56092f7b8588b6e6e635597528bca60c1d43e92f6` |
| queue.py 최초 동결 해시 (수정 전) | `c9353aa5264ae13f2b42e320b35b2ed96f221758903522a7fe10288ffc02c601` |
| untouched action_training_command.py | `8e0b776ec5ce7e1dfadd2b622975ac48017f21c480e9d2fa779ecf3779a185d9` |
| untouched train_action_recognizer.py | `2a0d01de3ec9b872c99761472b0626ba1e5f41a5b9f2c9be4eef4fe5626ff350` |
| untouched build_action_training_clips.py | `9c7d8f728d8b5c80d1bc12a94e351c2a1741cfe6b5aff27bd4f34abc81036ce5` |
| untouched training config | `7c94f0e183151e489b6de23e0d20fa827bf1fd7fb9aa5737aee34e513196d25b` |

실제 모델 점수/행동 성능/운영 알림/침입 개선/웹 전달은 미실행이다. root의 안전한 commit 시점, 독립 최종 검토, 단독 학습·시험 완료, 실제 queue migration/등록 및 새 GO는 다음 별도 단계다. 로컬 outputs는 gitignored 자료로 보존하며 원격 push는 하지 않는다.

구현 소스 SHA256 (최종 CPU 시험 대상):

- `scripts/prepare_action_regression.py`: `71c5b07d088467afa89991709f3c59df39af2324fe9bd1dede79e8c7cdad2ba2`
- `scripts/infer_action_regression.py`: `7bccb00554f9b7ba248f7b009b553882a2e61d12fc4638e5e56d079b1c9faf4c`
- `orchestration/action_inference_command.py`: `3dc6a86c9fbb49588e382b78b869c393ee3db502ed13e0a774e69dc01099eb37`
- `tests/test_action_regression.py`: `99cc53b2fe17ae543a0323d8de6cc6f3d1b6a22ab932f15f161af5a2d578b425`
- `tests_orca/test_action_inference.py`: `bed054d2eb7ce9560a081d7004938e4b54bbcc9ecfcf62583a89311e8641b1f4`

## queue 권한 확장 후 최종 CPU 회귀

`.venv-cv-batch02/bin/python -m unittest tests.test_action_regression tests_orca.test_action_inference tests_orca.test_action_training tests_orca.test_queue -v`: **44개 통과 (8.100초)**. 신규 action-infer의 additive migration/idempotency/foreign key, canonical DB의 read-only backup을 이용한 임시 사본의 기존95 jobs/95 attempts 값 동일성, 현재 owner/job key/timeout 거절, 실제 임시 supervisor의 held FD/GPU0 env/비합성 receipt, 이전 job/attempt 보존, 실패 후 자동 retry 거절과 reservation/unknown job migration 거절을 검증했다. 기존 action-train의9개 및 queue의14개 시험도 그대로 통과했다.

최종 read-only canonical 확인은 jobs95/attempts95, action-infer jobs0, action-infer schema 미등록이다. 실제 DB mutation은 없다. 최소 source patch 후 `orchestration/queue.py` SHA256은 `43867d3a8c937c3096ae7bd2cf972d05e78f0aafef80d1a0c20305c5888e6279`다. 이 해시 변경은 root의 명시 권한 확장에 따른 것이며 최초 동결 해시와 구분한다.

최종 runtime parity 점검에서 frozen trainer와 동일하게 torch import 전에 `CUBLAS_WORKSPACE_CONFIG=:4096:8` 기본값을 설정했다. 실제 모델을 로드하지 않고 수정했으며 같은44 CPU 시험이 다시 통과했다 (8.097초). source window의 학습 설정/배치/threshold는 변하지 않았다.
