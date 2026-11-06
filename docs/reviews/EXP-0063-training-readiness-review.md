# EXP-0063 첫 행동 학습 준비 독립 검토

2026-11-07 최종 보완. Astra 검토 역할의 독립 코드·계약·실제 결과 검토다. 총괄의 후속 배정에 따라 전체 CPU 준비, 수치 오류 복구, 실제 smoke·학습·시험 및 45개 별도 비교까지 읽기 전용으로 확인했다. 구현 파일을 수정하지 않았으며 GPU·다운로드·공유 큐/DB 변경을 실행하지 않았다. 저장된 학습 checkpoint는 CPU로만 검사했다.

현재 판정은 **실제 5,741개 입력 준비·새 smoke·10 epoch 학습·1,431개 공식 참조 시험 검증 통과, 모델 채택 보류**다. 선택 epoch는 6이며 2,250회 갱신 시도 중 2,248회 적용·2회 AMP 건너뜀을 확인했다. 별도 장소 음성 2개를 모두 오판했고 사람 검수 기준 precision/recall/F1은 미측정이다. 높은 공식 참조 수치를 독립 일반화 성능이나 완전한 사람 정답으로 해석할 수 없다. 실제 45개 비교와 공개 보고서/39지표 검토는 마지막 절과 `EXP-0064-integration-readiness-review.md`를 따른다. 브라우저 전달·게시 완료는 본 검토의 인증 범위가 아니다.

**아래의 준비 GO·대기 및 과거 source freeze는 당시 단계별 이력이다. 현재 판정은 위 요약과 마지막 실제 결과 보완 절이 우선한다.** 추가 학습·튜닝·기본 적용을 허가하는 문서가 아니다.

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

## 실제 CPU benchmark·smoke 부분 준비·순차 보존 확인

위 benchmark 대기 상태는 실제 receipt로 해소됐다. 고정17개 전부의 순차/병렬 NPY SHA·배열·shape·dtype가 같았으며, 사전 전체2,162개 원본/주석 hash gate와 직접/중첩 입력 바인딩을 독립 확인했다. 순차 decode15.946199초, 병렬4.351445초로 이17개에서3.664575배였다. 전체 gate 포함662.703202초이며 이 작은 표본의 배수를 전체 corpus 실행 성능으로 확대하지 않는다. 실제 benchmark result SHA는 `ad710c9c8aeb421a2a70fea20dc7b1ec01c29a8c18c43b11d8238169cc5e3780`, 독립 근거는 `benchmark-independent-audit.json`이다.

총괄이 원래 순차 PID2099445의 identity를 대조해 중단했고 pidfd exit를 관찰한 뒤 snapshot을 만들었다. 독립적으로 종료 상태, 실제 완료2,033개 원본/복사 NPY의 모든 SHA·shape·dtype·manifest ID/index 대응과 부분 파일0개를 확인했다. snapshot SHA `080bf01a7cd5c686e73cdd744b2087f46c3631ae73df9371e67b501f2c07633c`와 replacement command SHA `1951dda94db45bf9933a696957984a1eb26dcbdebc1d9368753bcaed2918ea4a`에 대해 별도 prepared-v3 CPU 실행 GO를 전달했다. 기존 순차 파일은 보존한다. 전체5,741개 새 준비와2,033개 전체 동등성은 아직 최종 receipt 대기다.

별도로 frozen `partition_rows(smoke)`의 정확한32train/4validation/test0을 새 prepared-smoke-v1에 순차 준비했다. runtime command SHA `43bef240b927b8735d31760b515c32a48391fc3518f228c83140253eebb9fe74`, plan SHA `1234dfa04552d41005ab63099c535839446ebb2c6b77befc970e1bc6b7415c92`, ordered selection SHA `4a932ac30099a25962a7fa3acd5fe06e5b02ad13c9e5b702af883ba0dd752098`를 검토했다. 실제36개 픽셀·38개 선택 원본/주석 gate·전체/중첩 계약·공식 pretrained 가중치 바이트·현재 실행 배정을 독립 확인했다. prepared SHA `a30c1d9032dc02987796f9bb77444ef77dd1dfe0ea997998deffa4784ddca9c7`, contract SHA `d9226aa7473956281f58594fa51a7a9c3d99f98423ff4a20ebfac4d10ee78fce`이며, adapter의 실제 입력 digest는 `5b23691c4a05a666c8284a776c06035dd39d8fcd3b5109ccdcfa74b05758d6a6`이다. 이 부분 준비는 full_corpus_prepared=false이며 전체 학습 완료가 아니다. 최종 full prepared와 이36개도 전부 바이트 비교해야 한다.

GPU smoke 입력 준비는 통과했으나 확인 당시 GPU0 여유3,290MiB로 고정6,144MiB 조건에 미달했다. 총괄에게 실행 보류를 전달했고 이 검토는 GPU·모델 로드·enqueue를 수행하지 않았다. 현재 자원은 실행 직전에 다시 확인해야 하며, 과거 준비 통과만으로 새 소스/HEAD authorization을 생략하지 않는다. 실제 smoke 성공·전체10epoch 학습·시험 평가·45개 추론은 미완료다.

runtime queue wrapper의 enqueue 직후 caller interruption을 not_enqueued로 잘못 기록할 수 있는 모호함을 지적했다. 최종 SHA `bc6cceff5aa14f55fa266b0db30c295e986deede3bf3abe007dd3cc3db94a634`는 enqueue_started를 먼저 저장하고 이후 예외를 unknown으로 남기며 deterministic job_key로 SQLite mode=ro 조회만 한다. 자동 재호출/retry는 없다. invocation 수는 executor smoke input-contract1회와 reviewer1회를 분리해 총2회로 정정했다. wrapper 자체는 실행하지 않았다.

## GPU 자원 보류 중 train-only provenance adapter 수정 독립 검토

총괄은 실제 GPU authorization/attempt가 없는 상태에서 adapter·그 시험·설명 문서만 수정하는 별도 창을 명시적으로 열었다. 이전 after-smoke 시점 제한은 이 지시로 대체됐다. trainer·CPU driver·queue·config·모델·분할·review release·inference 소스는 그대로다.

| 최종 검토 파일 | SHA256 |
|---|---|
| orchestration/action_training_command.py | `87eb7009455d295335eb0b53e301b55fea34fc09533b1ce5e784d8fde4abecb8` |
| tests_orca/test_action_training_provenance.py | `3b90ae7774ef4685edf8cb983eeb2c2b751868fe6edcfc94aa3d3aa9db9d0058` |
| docs/orchestration/EXP-0063-action-training-adapter.md | `74f34ceb7fcaeb39cd81381a6f1631b13fcc44e4f976746d1922ff8ef2d1d5c0` |

Smoke는 기존7개 파일과 선택 원본 hash 검증을 유지한다. Train만 정확한 preparation_evidence 바인딩을 추가한다. 전체 prepared·동일 producer contract·성공 result·전체 원본/주석 receipt·동등성 report와 고정2,033 snapshot을 검증하며, 매 guard에서 실제 소비하는 모든 NPY와 현재 공식 주석 바이트를 해시한다. 현재 학습에서 사용하지 않는 MP4는 다시 열지 않는다. 출력은 이를 준비 시점의 원본 검증 provenance로 명시하며 현재 원본을 재검증했다고 주장하지 않는다. 기존4개 guard의 원본 반복 읽기 제거는 논리적 읽기량 변경이며 실제 전체 시간 개선 측정은 아니다.

Train의 smoke proof는 canonical DB의 실제 succeeded job/attempt, 비합성 receipt, 인접 input/config snapshot/digest, 정확한 job key·context·기존 authorization와 해당 커밋 source를 읽기 전용으로 대조한다. 원래 draft의 과거 trainer 코드와 현재 trainer 코드 불일치 가능성을 지적했고 최종본은 두 SHA가 같아야 한다. 정확한32/4/0·8개 batch4·누적4·2optimizer step·training_complete=false와 동일 manifest/config/weights/release, 실제 full prepared의 대응36 pixel SHA를 요구한다. result JSON 하나만으로 이 증명을 대신할 수 없다.

17개 새 provenance/smoke proof 시험을 포함한 관련85개를 최종 바이트에서 독립 재실행해16.823초에 모두 통과했다. MP4가 모두 없는 fixture와 raw 읽기 trap, 네 번 guard의 실제 pixel hash 재검증, 변경/누락 NPY·주석·중복/누락 source receipt·부분/실패 준비·review/producer binding·regression45 누수·가짜/다른 smoke/훈련 코드 반례를 확인했다. 시험 전후 최종 SHA가 같고 금지된 변경 대상 소스와 기존95 jobs/95 attempts 각 행도 보존됐다. `train-provenance-tests.log`, `train-provenance-reviewed-hashes.json`이 근거다.

**최종 adapter 수정 파일 커밋 GO**를 총괄에게 전달했고 구현 commit `4db1231`의 세 파일이 위 검토 SHA와 동일함을 확인했다. 실제 full prepared receipt가 아직 없으므로 실제 자료로 새 train input-contract가 통과했다고 인증하지 않는다. 실제 canonical smoke가 없으므로 전체 학습 GO도 아니다. 새 source freeze를 만든 뒤 정확한 실제 입력·현재 자원·현재 배정을 연결해야 한다. 원본/픽셀 준비와 합성 시험 통과를 사람 행동 성능 또는 완전한 사람 정답으로 해석하지 않는다.


## 실제 전체 준비·원래 smoke와 첫 전체 학습 실패

전체 prepared-v3의5,741개 NPY는 실제 ID·SHA·8×112×112×3 uint8 형식을 독립 확인했다. 먼저 완료한2,033개 순차 snapshot과 smoke36개도 전부 바이트·배열·형식이 같다. prepared SHA는 `9d8d05f20da34a797a0619c066e9142df3ad15d8aafb6b1f991290a83631f1b4`, 전체 준비 증거 SHA는 `06d666053fdc08209a86a01fbf32b5ee5b2e892972fbc119824dfaba9ba8e97b`다. 독립 근거는 `prepared-independent-audit.json`과 `train-evidence-independent-audit.json`이다.

원래 core2a0d의 canonical smoke attempt `c386b63a5265425f85659d1015253c21`는 실제32train/4validation/test0,8microbatch4/누적4/2update로 성공했다. result SHA `e855631708e133c2ccdc670760399bd31a2e75a5ab55a4452e8535b1ca60eb09`와 canonical receipt·실제4개 검증 ID·유한 손실을 독립 확인했다. 작은 검증4개의 결과는 전체 행동 성능 근거가 아니다.

첫 전체 학습 attempt `058639f80f394a71b345eb4eae5ceacb`는 exit1로 실패했다. `clip_grad_norm_(..., inf, error_if_nonfinite=True)`의 비유한 전체 노름 오류이며 첫 history/result가 없다. supervisor2286288과 child2287648의 종료를 확인했다. traceback만으로 개별 기울기 overflow와 노름 합산 overflow 중 하나를 확정하지 않는다. 실제 실패 전 update 수나 GPU peak는 기록 부재를0으로 바꾸지 않는다. 원래96행씩은 변함없으며 실패까지97 jobs/97 attempts를 각 행 SHA로 보호했다. 실패 receipt SHA `2d52713873d3a28363b2786fba3518ee9b473bc550cb757680b6bea0c11d6c5b`와 로그 SHA `4ec93636a582f7d016e8345a309b7a34c751587ae34eaa965849e931b6be1f6c`를 보존했다.

## amp-overflow-v2 독립 수치·출처 검토

총괄이 종료 증명 뒤 연 제한된 수정 창에서, 기존 무한 clipping을 제거하고 표준 GradScaler의 skip/backoff와 실제 ordinary AdamW post-step hook을 사용했다. attempted/actual/skipped,scale 전후를 JSONL로 기록하고 epoch당 실제 update0·비유한 forward loss·모델 parameter/buffer·Adam state는 거절한다. smoke는 고정32/4의 두 경계에서 실제 update2회여야 한다. skipped optimizer update가 forward의 BatchNorm buffer까지 변하지 않았다는 뜻은 아니다.

최종 trainer SHA `770114f8eb9c09a44be33232c99b687e10989e5622eba82cd675d50e5156478a`, test SHA `276716c33e322a2635740cf50b3c0472ccedc76108a619191e16637ec3200fc7`에서31시험을 독립 실행해 모두 통과했다. 추가 실제 CPU GradScaler 반례로 scale0.5→0.25 skip 뒤 정상 update, 유한 gradient가 비유한 Adam moment를 만들 때 치명적 거절을 확인했다. CUDA는 초기화하지 않았다. 수치 수정은 `24bf0139733276adbdc4054b1c6b97f4e9b57df7`에 커밋됐다.

초기 adapter draft는 smoke7파일을 fulltrain8파일과 비교해 거절하는 문제가 있었다. 또 신규 helper 이름과 main return annotation 등 정의 메타데이터가 기존 전처리 의존성을 가릴 수 있었다. 담당자에게 전달했고 최종본은 smoke의 공통6개 입력/train의 전체8개 입력을 구분하며, 신규 helper3개 이름만 허용하고 main 정의·기존10helper 원문/AST·import/global·AdamW 생성까지 main prefix를 대조한다. 원래 producer Git99d18b3/SHA2a0d와 현재 실행 SHA770114f8을 별도로 기록하고 기존 prepared metadata를 덮어쓰지 않는다.

최종 adapter SHA `cddc583c53b2264d39fe412ca97c32e9ec93dd0cff30e8a2a7efff162edbf95c`, adapter test `3ad26b00cb749bfc90172d885a621ccbbeddc42e25d5e49e4bc760edd64ffbaa`, provenance test `61853fe0495245add25c17c1c0f98f7f9096ef94753fe9dcb7931bf9d256e809`, 설명 문서 `9f975604242b2a18728323f46b0496b130e43226b32a663549c828345c730886`에서 관련100시험을 독립 재실행해15.480초에 통과했다. 전후 바이트가 같고 실제 기존 smoke/fulltrain parent 바인딩도 읽기 전용으로 통과했다. 새 stage job key는 명시적인 amp-overflow-v2를 포함하며 Queue.retry를 사용하지 않는다. 기존 smoke는 새 core의 성공으로 사용할 수 없고 새 smoke의2actual/2attempt/0skip,유한 상태·scale·SHA 연결된 두 update를 요구한다.

총괄 커밋 `166c96aa0ee3de18b8d1fe01f26b7430084adef3`, source-freeze-v5 SHA `de1b2368f7fda067422732d1e402da9631adca2361a7857b7bc17fca2ecafe5f`의21파일을 현재 및 Git 바이트와 대조했다. 새 smoke input digest `a27d7d4ea7b546e6081ff329b4f8fbb17850c693777ad306333794eae59771f6`, train digest `4d6491241b70643ea98743064e3dda478e2b812c15094668933e6f5ef5db052c`는 execution_revision과 train preprocessing_compatibility 증명 외 기존 입력과 완전히 같다. 실제36smoke 픽셀을 재해시했고 원본 영상 중복 scan이나5,741개 재추출은 하지 않았다.

새 smoke 실행 전 root GO `msg_2f38dab66070`, authorization SHA `5b5a1d770d950df4e3b1863d62f1cc053f7f17ce2445c48f0ce6610d702c1ca5`, config SHA `4875e28fe5c2349ddf41bcc5f19ccae34858c4d7c2402d83cbf131affdd04217`, wrapper SHA `e56bf5c93240714dfc9c9167d6ae5727be8abd01e2bad22787d559b85418acf7`를 확인했다. 동결 문서/소스는 실행 동안 수정하지 않았고, 아래 완료 증거까지 runtime 검토에 보관한 뒤 프로세스 종료 후 이 문서에 반영했다.

## 실제 revised smoke 독립 확인

새 job `17ca440f9cd7453982a45e2b96e830a8`·attempt `e880e2d07ff1406793fd762fb7582416`는 canonical exit0/succeeded다. result SHA `296138bf10cb8484660dff856703ac0f8428407bc48865e146bd0bd71c945dab`를 실제 새 train 입력과 대조해 현재 adapter의 canonical smoke 증명이 통과했다. 같은166c96aa/770114f8/amp-overflow-v2,정확한36픽셀,2attempt/2actual/0skip,scale65536·유한 모델102/optimizer186tensor,events SHA `7fd142c64c852456df9ca762087bd6ab60084921f994ae00687ac9c334967f4e`를 확인했다. 검증4개 ID·점수와 train/validation 유한 손실, 시험 미접근·시험 출력 부재도 확인했다. 원래 작은 smoke와 손실이 같지만 전체 성능 증거로 해석하지 않는다.

로컬 생성 `last.pt` SHA `0f98fa5dd8f229f5d8318ebb7c6ab166bd42ca4dcd1aea6979859526591f40d3`를 CPU로만 읽어62개 Adam state의 모든 step2와 model/optimizer tensor 유한성을 독립 확인했다. CUDA 초기화는 없었다. 기존97행씩이 같고 새 성공 smoke까지98행씩을 보호했다. `actual-revised-smoke-independent-review.json`, `revised-smoke-checkpoint-independent-audit.json`이 근거다. 총괄에게 `msg_6e1252188a94`로 정확한4d649124 입력·동결 소스의 한 번 전체 학습 준비 GO를 전달했다. 당시 이 GO는 전체 학습 성공 인증과 구분했으며, 이후 실제 결과를 아래와 같이 확인했다.


## 실제 전체 학습·시험 독립 검증 통과

새 job `2bc23fd542bc4b90b9ac22e66c40ab13`·attempt `67e95fc8cf204de7be9627e81f524931`는 canonical exit0/succeeded로10epoch를 완료했다. result SHA `9a8bb01f62973b91d959c3e8f9d3bfc80d9ef2094dc6169905295bc44aa8eaf5`, validation 최저 epoch6의 best.pt SHA `8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73`다. 매 epoch의725개 validation 전체 ID/라벨/메타데이터와 지표, 최저 validation CE 선택, 전체1,431개 test 점수/실패 목록/공식 참조 cohort 및 행동별 수치를 독립 산술로 재현했다. test로 epoch나 threshold를 선택하지 않았으며 재평가·추가 학습은 하지 않았다.

실제2,250update 시도 중2,248회 적용·2회 skip이다. 두 skip은 epoch1과10의 마지막 microbatch897, 각1개 sample을 포함하는 누적그룹이며 scale65536→32768로 감소했다. 총2개 sample 노출의 gradient update가 건너뛰어졌다는 뜻이고 고유2클립·새 정답·학습 실패2회를 뜻하지 않는다. 모든 epoch는 실제 update가 있고, JSONL 전체2,250행과 history/result의 카운터·scale·유한 상태가 일치했다. 학습 중간의 한 skip 관측을 최종2개로 정정한다.

CPU로만 best/last checkpoint를 읽어62개 모든 Adam state step이 각각1,349/2,248이고 저장된 실제 카운터·epoch·config·manifest·scale 및 모델/optimizer tensor 유한성이 일치함을 확인했다. last.pt SHA는 `399202c6fed774d94d2969496eca1a791f2dbbc72865bd797224f72ec0d3dd61`다. 이 점검에서 CUDA는 초기화하지 않았다. `training-v2-result-independent-audit.json`, `training-checkpoints-v2-independent-audit.json`이 근거다. 기존98행씩과 원래 실패 산출물·동결21소스가 보존됐고 새 성공까지99행씩을 보호했다.

| 공식 주석 참조 시험 | TP | FP | FN | TN | 해석 한계 |
|---|---:|---:|---:|---:|---|
| 같은 장소 별도 촬영 | 252 | 0 | 0 | 847 |1,099클립·188원본·5촬영 사건, 독립 장소 일반화 아님|
| 별도 장소 | 330 | 2 | 0 | 0 |332클립·95원본·3촬영 사건, 유일한 음성2개를 모두 오판|

**별도 장소의 정상2개 모두 FP**라는 실패를 높은 전체 F1로 가리지 않는다. 두 실패는4-61/4-62의 서로 다른 촬영 사건에 있는 stand 참조 클립이며 점수는 각각0.9999951124/0.9997382760이다. 공식 참조 전체는TP582/FP2/FN0/TN847이지만 사람 검증 행동 정답·정밀 경계·침입 완료 정확도나 충분한 정상 일반화 성능을 입증하지 않는다. 검증 음성은 앉기만 포함했고, 사람 precision/recall/F1은 계속null이다. 동작/배경 원인을 수치만으로 확정하지 않으며 추가 튜닝을 자동 시작하지 않는다.

총괄에게 `msg_f9291db3ecfb`로 실제 standalone 검증 통과와 위 한계를 전달했다. 45개 기존 회귀는 별도 모델/입력/실행 승인을 확인해야 하며 이 결과만으로 실제 통합 추론이나 운영 개선 완료를 선언하지 않는다.


오판 두 구간은 새 검수 장면이 아니다. 실제 적용 snapshot을 다시 읽어4-61 actor0 stand50–59는 `request-5beb7b452b1d4abd82f3e198c0f14cb2`/`exp0063-wall-00-video`,4-62 actor1 stand162–361은 `request-f6003c590bd64bb3afa7fb1a7f75866e`/`exp0063-wall-05-video`의 기존 답변(version4/answer_version1)임을 확인했다. 두 답변은 시작/종료 차이는 작고 오른쪽 박스가 사람을 더 잘 담는다는 관찰이며, 원래 처리도 전체 음성 정답으로 확대하지 않는다고 명시했다. 검토자가 초기에 새 장면 질문 대상으로 표현한 메시지는 `msg_0f8cccfc8b1e`로 정정했고 실제 새 검수 요청은0개다. 새로 관측된 것은 모델-공식 참조의 불일치이며, 기존 관찰을 재사용하고 반복 질문·정답 자동 승격을 하지 않는다. 근거는 `failure-prior-review-scope-correction.json`이다.

실제 standalone summary SHA `3b9ac6817d3540f41ec808a38cfc8921ab0220c2a41528f95cff56a28e9f69e8`의 수치·가중치·출처 연결과 failure manifest SHA `2abca9ddd2fc2f164af2f83ea55fd557963050704292eb9850f0bab2b881bc54`의 정확한 두 FP를 대조했다. 두 표시 영상은960×630의3FPS·8프레임이며 native PTS/라벨/score/source·미디어 SHA가 일치한다. 모델이 입력받은8개 시점의 원본 문맥에 ROI를 표시한 영상이며,112px 입력 tensor나 원본FPS 연속 영상 자체는 아니다. 로컬 디코딩·메타데이터만 확인했고 원본 미디어를 cloud vision에 보내거나 행동 의미를 새로 확정하지 않았다.


## 최종 연결 결과와 공개 표현 검토

추가 배정한 실제 45개 비교도 attempt `3825ad63d2254611921ccb7b349c2feb`에서 완료됐다. 184,300 native 프레임·3,573개 점수·467개 후보 창, 기존 원본 출력 405개와 별도 복사본의 일치 및 이전 큐 99개 job/attempt 각각의 행 보존을 독립 확인했다. 후보 수는 인원·침입 사건·TP 수가 아니며, 기존 판단 변경 0은 보존 설계의 결과다. 상세 시각·큐·공식 참조와의 분리는 통합 독립 검토 문서를 따른다.

최종 공개 보고서 `docs/experiments/EXP-0064-results.md` SHA `d222f1e8f2055c8a0a68d799157ff2b5ec0622b81c74d9f8ff531b9e1aa37337`와 `records/EXP-0064/metrics.json` SHA `ef39ca9ab51c1abebd3a31debf8bf5fa32b5879a008f95eaee1de3bf5eb688f2`를 실제 결과에 대조했다. 39개 중 수치 33개와 미측정 null 6개, 각 출처 SHA·범위·분모를 확인했다. 전체 공식 참조 precision 582/584, recall 582/582, F1 1164/1166은 산술적으로 맞지만 별도 장소 음성 2/2 FP와 앉기 편중 검증 음성의 한계를 유지한다. 공개 문서는 사람 정답 전체 검증·독립 일반화·실시간 침입 개선을 주장하지 않으며 채택을 보류한다.

계산·계약·보존 검토의 미해결 차단 사유는 없다. 충분한 사람 의미 정답 및 별도 장소의 정상/접근/돌아가기 평가 부족은 성능·채택의 미해결 한계다. 반복 검수나 추가 튜닝을 자동 시작하지 않는다. 웹 등록·실제 브라우저 재생·GitHub 게시 완료는 별도 전달 증거가 필요하며 본 검토에서 인증하지 않았다.
