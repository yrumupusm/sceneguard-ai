# EXP-0063 첫 행동 학습 준비 독립 검토

2026-11-06. Astra 검토 역할의 독립 코드·계약 검토다. 실제 학습 결과, 사용자 행동 정확도 또는 운영 채택의 인증이 아니다. 구현 파일을 수정하지 않았으며 GPU·다운로드·공유 큐/DB 변경을 실행하지 않았다.

현재 판정은 **정확히 고정된 v2 입력의 CPU preflight/prepare GO, GPU smoke 및 전체 학습 GO 대기**다. 최종 소스·후보·release 검사는 통과했다. 실제 prepared 픽셀·실행 배정·큐 authorization·smoke 결과는 아직 검토하지 않았으므로 GPU 실행 가능이나 학습 완료를 인증하지 않는다.

## 승인 및 정답 범위

첫 사전학습 영상 모델 한 개의 미세조정은 기존 사용자 승인 범위다. 여덟 답변은 여섯 오른쪽 박스 선호와 두 차이 없음이며 전체 자료의 의미·행동 시작/종료·ROI를 사람 검수 완료 정답으로 만들지 않는다. `EXP-0063-user-review-followup.md`의 두 시간 원점 공통 내부 구간 및 공식 actor-event 참조 라벨 정책은 이 구분을 지킨다. 같은 표본을 재질문할 필요는 없다.

작업 시작의 `pending --include-acknowledged`는 성공했고 요청은 0개였다. 보존된 적용 snapshot의 여덟 `version=4`, `answer_version=1`과 답변 원문을 읽었다. 원래 수신 `version=2` 및 확인·반영 이후 버전과 혼동하지 않는다.

공식 annotation ROI를 사용한 분류 지표와 실제 검출 ROI의 통합 행동 성능은 별개다. 사람 검증 precision/recall/F1, 침입 완료 정확도는 부족한 정답 범위에서 null을 유지해야 한다. 같은 장소 시험은 카메라·배경·배우 독립 일반화 시험이 아니다. 별도 장소 음성 부족도 합산 지표로 가리지 않는다.

## 독립 확인한 고정 입력

| 입력 | SHA256 |
| --- | --- |
| 통합 split v3 | `bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499` |
| 월담 감사 manifest | `8fef23cf8410a27f64a43d1ae5bba1e461e176e549ccf908a213c0cbaa0d9c69` |
| 정상 감사 manifest | `52cfe8864a0fe189672acdf8573aca26138a7b06bd99637f57dd2c46e8b87d46` |
| baseline attempt-002 lock | `3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40` |
| 적용 후 검수 snapshot | `89406b2aece60120e68daf86dfa24a7c8b19e569b6b829f3a122ac3d6247cc48` |

두 감사에서 v3 assignments·groups·connections를 재생성해 정확히 일치했다. 원본 분할은 학습671/검증153/시험296/제외313/격리7이다. 동일 장소·행동군·시나리오의 분할 교차는 0이며 별도 장소의 사용 가능96개는 시험에만 있다. 보호45개 SHA는 서로 다르고 전체 감사 원본과 SHA 교차는 0이다. 재인코딩 중복이나 촬영 메타데이터의 독립 실재 검증을 수행했다는 뜻은 아니다.

로컬 근거는 `runtime/action-recognition/exp0063/independent-readiness-review/`에 보존한다.

## 초기 발견과 재검토 항목

1. 초기 smoke 선택은 학습 두 클립뿐이라 설정 microbatch4의 메모리 적합성을 검증하지 못한다. 실제 네 학습 클립 이상을 사용하거나 batch4 미검증을 명시해야 한다. 총괄에게 전달했다.
2. 초기 config의 `reviewed_actor_plus_fence_context_roi_letterbox` 및 `explicit_reviewed_action_interval` 표현은 전체 ROI·의미 경계의 사람 검수로 오해할 수 있다. 공식 annotation과 표본 정렬 검수 범위를 나타내도록 수정 요청했다.
3. 최종 source SHA/commit, 후보 manifest·release, 전처리 해시, 가중치 전체 SHA와 큐 authorization의 실제 연결을 확인한 뒤에만 실행 준비 판정을 내린다.

최종 구현에서 1·2는 수정됐다. smoke는 학습32/검증4개의 실제 클립을 선택하며 batch4·누적4로 두 optimizer step을 수행해 첫 step 이후 Adam 상태가 남은 backward까지 검증한다. test 원본과 준비 픽셀을 smoke에서 해시·디코딩·로드·평가하지 않는다. 실제 smoke 결과의 동일 manifest/config, 전체 microbatch 크기, 누적4, 최소 두 step과 test 미접근을 train 단계에서 요구한다. config는 공식 박스 합집합과 두 원점 교집합으로 표현을 수정했다.

## 검증 음성 분포와 v2 범위 결정

원본 감사에서 정상 validation40개에는 선언 `sit_down_bench`183·`sit_down_floor`184건만 있고 moving/stand는 없다. 학습은 moving753/stand996/bench172/floor419, 시험은 moving427/stand665이며 이 수는 클립 적격성 검사 전 공식 선언 사건 수다. 따라서 v1 moving/stand-only 후보는 양쪽 검증 클래스 조건을 충족하지 않는다.

총괄의 제안에 대해, 사용자가 승인한 정상행위 자료에서 명시적인 앉기 actor-event를 v2 음성에 추가하는 것은 첫 모델 결과를 보기 전의 허용 가능한 범위 결정이라고 답했다. 전제는 v1 보존, 새 정책 addendum·manifest·release, 동일v3 분할 및 동일 제외/중첩 규칙, 행동 세부 유형별 분모 공개다. 분할을 이동하거나 무주석·파일명으로 음성을 만들 수 없다.

이는 검증 데이터의 보행/대기 부재를 해결하지 않는다. 앉기 음성의 validation CE로 선택한 checkpoint가 보행/대기 구분에 최적이라는 결론을 내릴 수 없고, 원래 목표의 달성 여부는 미확정이다. 첫 실행은 **넘기 대 명시적 정상행위의 공식 annotation 참조 실험**으로 한정한다. 여덟 답변은 앉기 의미를 새로 사람 검증한 근거가 아니다.

## 최종 바이트와 실제 후보 검증

총괄이 확인한 최종 HEAD는 `c3ff68ff055ea1f8ed44088156cad3464386aa68`이다. 학습기/큐는 `0d6167e96e8497240dba14e595726bb8f22b61dc`, 생성기는 위 HEAD의 commit이다. 파일 내용 SHA와 해당 commit의 Git blob을 모두 대조했고 시험 뒤에도 동일했다.

| 항목 | SHA256 |
| --- | --- |
| builder | `9c7d8f728d8b5c80d1bc12a94e351c2a1741cfe6b5aff27bd4f34abc81036ce5` |
| trainer | `2a0d01de3ec9b872c99761472b0626ba1e5f41a5b9f2c9be4eef4fe5626ff350` |
| action queue adapter | `8e0b776ec5ce7e1dfadd2b622975ac48017f21c480e9d2fa779ecf3779a185d9` |
| canonical queue source | `c9353aa5264ae13f2b42e320b35b2ed96f221758903522a7fe10288ffc02c601` |
| training config | `7c94f0e183151e489b6de23e0d20fa827bf1fd7fb9aa5737aee34e513196d25b` |
| v2 candidate manifest | `72912fab027a068d0e6043f328d86a2c7d15a239afa751d126984c5c10498931` |
| external review release v2 | `7305b347f9783ca29d1055c3002cc6135ad41144e75874f153031d0d2fa3635b` |
| source freeze v2 | `e3457837595f5b0e89ee8fe6921d4f35ea923caddd6bc105f35f61e7e8857b3c` |

생성기를 import하지 않는 독립 검사로 1,081개 원본 JSON의 SHA와 모든5,741후보를 확인했다. 공식 actor/object/event, 두 원점의 공통8프레임, 필요한9개 주석의 유일성·class, 같은 actor의 다른 object_id까지 포함한 중첩, 음성의 타인 월담 중첩, 양쪽 박스 합집합과 실제 ROI, 분할/장소/보호45개 제외를 확인했고 위반은0이다. 픽셀 의미나 전체 ROI의 사람 검수를 대신하는 검사는 아니다.

| 분할 | 넘기 | moving | stand | bench | floor | 합계 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 학습 | 1,571 | 569 | 893 | 159 | 393 | 3,585 |
| 검증 | 411 | 0 | 0 | 134 | 180 | 725 |
| 시험 | 582 | 304 | 545 | 0 | 0 | 1,431 |

별도 장소는 넘기330/stand2뿐이다. 음성2개의 공식 참조 지표를 보고하더라도 충분한 정상 coverage나 일반화 성능으로 해석할 수 없다. 전체 시험 합산으로 이 한계를 가리지 않으며, 사람 기준 지표는 계속 null이다.

실제 전체 manifest에 대해 최종 trainer의 `validate_manifest`, `validate_config`, `validate_release`를 실행해 통과했다. 외부 release와 manifest의 동일 snapshot·정확한8버전·정책 바인딩, 모든 builder 입력의 현재 SHA, 후보5,741+제외2,437=8,178 event의 중복 없는 회계, smoke 학습32/검증4·시험0을 추가 확인했다. `final-contract-audit.json`에 결과를 저장했다.

## 독립 재실행 시험과 큐 검토

기존 `.venv-cv-batch02/bin/python`에서 builder17·trainer24·adapter9·기존 queue14, 총64시험을 독립 재실행해 모두 통과했다. 실제 synthetic encode/decode의 native PTS 오류 거절, 원본/사건/장소 누수·45제외, 검수 snapshot/release의 버전·SHA 변조, smoke test 픽셀 배제, 완전 microbatch 및 두 step 조건, 사람 지표 null,6144MiB 경계, 잘못되거나 미보유 lock FD, live assignment·명시적 GO·commit 바인딩과 기존 queue 회귀를 확인했다. 이 시험은 실제 자료 GPU smoke가 아니다.

큐 migration 시험은 실제 큐의 읽기 전용 복사본에서만 실행했다. 본 검토 전후 실제 canonical 큐는95 jobs/95 attempts이며 전체 행 digest `7b84bd024f4ba360b28e7bb38783ead2cdda73fea806e5cb3cb320953ffafcc9`가 동일하다. 공유 GPU lock의 inode와 실제 보유 여부, 자식 상속 FD, 실행 중인 정확한 queue attempt·supervisor identity·Orca context, 전체 source/input/config SHA를 확인하는 경로를 검토했다. 기존 등록을 보존하는 추가 command migration이며 자동 retry는 거절한다.

가중치는 adapter에서 공식 R3D-18 전체 SHA `b3b3357ead25631ec9c57362ff2128a92d0427e01e2cd184951a44380c3f2e9d`를 요구한다. 본 검토자는 다운로드나 가중치 로드를 수행하지 않았다. 실제 GPU 단계에서는 해당 파일 바이트와 prepared 픽셀, 현재 실행 배정 및 source commit을 다시 연결해야 한다.

## 단계별 판정

1. **CPU preflight/prepare: GO.** 위 고정 소스·v2 manifest·release·config·baseline·split만 사용하고 새 출력 경로에 원본 SHA 및 exact native PTS를 확인해 준비한다. 실패 프레임을 가까운 프레임·반복·보간으로 대체하지 않는다.
2. **GPU smoke: 대기.** 실제 prepared receipt의 manifest/config/pixel SHA, 공식 weight 바이트, 현재 Run/Task/Dispatch/owner와 큐 authorization을 확인한 뒤 별도 판단한다. 지금은 큐 enqueue나 GPU GO를 뜻하지 않는다.
3. **전체10epoch 학습: 대기.** 같은 검토 소스·입력으로 실제 smoke32train/4val, batch4/누적4, 두 optimizer step 및 test 미접근이 성공해야 한다. smoke checkpoint를 이어 학습하지 않고 공식 사전학습 weight에서 고정 조건을 시작한다. validation CE로만 선택하고 test는 선택 후 한 번 평가한다.
4. **45개 통합·운영 적용: 본 판정 밖.** 추가 배정된 관측층 CPU 소스/큐 준비 검토는 `EXP-0064-integration-readiness-review.md`에 기록했다. 실제 학습·시험 완료와 별도 GPU 추론 GO는 여전히 필요하다. 행동 점수만으로 침입 완료를 생성하는 권한은 없다.

## CPU 병렬 준비 보완 검토 — 실제 영수증 대기

원래 순차 prepare가 진행 중인 상태에서 총괄이 별도 CPU 병렬 driver와 실제 동등성 benchmark 검토를 배정했다. 고정 trainer의 픽셀 decode 함수·native PTS·ROI·정규화·후보·분할은 바꾸지 않는다. source commit `930e21b`의 `scripts/prepare_action_pixels_parallel.py` SHA256은 `a9184eeae221f52a8033c24212f6c8eb6323525d4e6c24e425c2624f267e451b`, `tests/test_action_parallel_prepare.py`는 `78aee0c5fb7293817d912f9faeeeecd8c05ec454715d257f6fa27b8b5b3e0e01`다. 독립7시험 통과와 시험 전후 동일 소스를 확인했다.

초기 draft의 모든 task 선제 제출은 실패 뒤에도 불필요하게 계속 처리할 수 있어 수정 요청했다. 최종 driver는 spawn4개, 제출+완료 버퍼 최대4개, FIRST_COMPLETED에서 실패를 확인한 뒤에만 새 작업을 제출한다. 실패 시 미시작 작업을 취소하고 이미 진행한 최대4개 종료를 기다린다. frozen trainer.decode_clip을 그대로 호출하고 임시 NPY를 원자적으로 확정한다. 준비 완료 marker는 전체 성공 뒤에만 만든다.

전체 원본/주석 SHA gate를 decode 전에 실행하고, 최종 단계에서 driver/trainer·직접 입력·검수 snapshot/정책 및 contract 자체 SHA를 다시 확인한다. prepared metadata는 실제 contract 경로/SHA와 driver/trainer/worker 수를 연결한다. 새 병렬 prepare는 중단 확인된 순차 작업의 완료 픽셀 snapshot을 받아 모든 해당 clip의 NPY 바이트·배열·dtype·shape를 비교해야 한다.

고정17개 benchmark 계획은 `runtime/action-recognition/exp0063/execution-v1/parallel-benchmark-plan.json` SHA256 `e6792ea989649ec238ffc5a14d2a6be29c7725401bfb0902a9bf8a5daf031b9b`다. 전체 class/split/cohort와 ROI 경계·가로/세로·종횡비 극단을 포함하며, 동일 원본을 순차/병렬로 decode해 NPY 전체 SHA와 배열을 비교한다. 시험 분할 픽셀도 CPU 준비 동등성에만 사용하고 모델 점수·threshold·선택에 사용하지 않는다. 실제 GPU smoke에는 시험 분할이 들어가지 않는다.

현재 허용은 **이 exact17개 CPU benchmark만 GO**다. 실제 benchmark 동등성·시간 receipt 확인 → 총괄의 원래 PID 종료 및 불변 완료-prefix snapshot → 별도 prepared-v3 전체 준비 → 모든 픽셀/계약 독립 확인 순으로 진행한다. 원래 순차 결과를 삭제하거나 미완료 파일을 성공 픽셀로 세지 않는다. 실제 속도 개선·전체 병렬 prepare·GPU smoke·전체 학습은 아직 이 보완 검토에서 완료 인증하지 않았다.

통합 큐 추가 소스 `43867d3a8c937c3096ae7bd2cf972d05e78f0aafef80d1a0c20305c5888e6279`에서는 action-train 동작을 유지하고 action-infer만 추가했다. 최종 소스로 integration/inference/training adapter/queue44시험을 독립 재실행해 통과했다. 따라서 이전 source-freeze-v2의 queue SHA를 실제 GPU authorization에 재사용하지 않고 최종 커밋 HEAD와 현재 소스 전체를 새로 묶어야 한다. 이후 authorization된 단계 동안 HEAD/소스 변경은 금지한다.
