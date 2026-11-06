# EXP-0064 첫 행동 모델 실제 실행

2026-11-06–07(KST). **수정된 AMP 실행은 10epoch 학습과 검증 선택 checkpoint의 시험 1회까지 완료했다.** 2,250개 update 경계 중 AdamW 실제 적용은 2,248회, AMP overflow skip은 2회다. 검증 CE 최저인 epoch6을 선택했다. 같은 장소 공식 참조 F1은 1.0, 별도 장소는 0.996978852이지만, **별도 장소의 정상 stand 2클립은 모두 오탐**이다. 사람 기준 precision/recall/F1·침입 완료 정확도는 모두 `null`이다.

첫 전체 학습의 nonfinite gradient 실패도 별도 시도로 보존했다. 그 뒤 총괄이 승인한 제한된 AMP 구현 수정, 독립 CPU 검토, 새 revision의 실제 smoke와 별도 train GO를 거쳤다. 같은 실패 job의 자동 재시도·학습 기준 탐색·기본 모델 교체는 하지 않았다. 기존 95개 queue job/attempt 행과 이후 추가된 이전 시도들도 보존했다.

## 실제 최종 결과

완료 출력은 `outputs/action-recognition/exp0063/queued-training/train/67e95fc8cf204de7be9627e81f524931/`다. `result.json`의 상태는 `trained`, 완료 epoch는 10이다. 선택 기준은 시험 점수가 아닌 **최저 validation cross entropy**이며 epoch6의 값은 `0.002244211687293118`이다. 전체 학습은 공식 사전학습 가중치에서 새로 시작했고 smoke checkpoint를 사용하지 않았다.

| 공식 actor-action 참조 시험 | 클립 / 원본 / event group | TP | FP | FN | TN | precision | recall | F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 같은 장소 | 1,099 / 188 / 5 | 252 | 0 | 0 | 847 | 1.0 | 1.0 | 1.0 |
| 별도 장소 | 332 / 95 / 3 | 330 | 2 | 0 | 0 | 0.993975904 | 1.0 | 0.996978852 |

같은 장소의 음성은 moving304·stand543이고 모두 TN이다. 별도 장소 `busan_children-grand-park`는 월담330·stand2뿐이며 stand의 공식 참조 FPR은 **2/2=1.0**이다. 양성 비중이 큰 시험의 높은 F1을 낮은 오경보나 충분한 장소 일반화로 해석하지 않는다. 같은 장소 시험도 카메라·배경·actor가 독립인 일반화 평가로 부르지 않는다. 단위는 겹칠 수 있는 **클립**이며 사람 수나 독립 사건 수가 아니다.

`test-scores.json`은 manifest 순서 그대로 1,431개 고유 시험 클립을 담는다. `test-failures.json`에는 위 두 공식 참조 FP만 있고 FN은 없다. CPU 감사에서 라벨·source·event group·위치·PTS·actor/action·evidence metadata를 manifest와 대조하고 모든 혼동행렬과 지표를 재계산했다. 모델이나 시험을 다시 실행하지 않았다.

두 FP 구간은 기존 검수 장면이다. `4-61` actor0 stand50–59는 `request-5beb7b452b1d4abd82f3e198c0f14cb2`/`exp0063-wall-00-video`, `4-62` actor1 stand162–361은 `request-f6003c590bd64bb3afa7fb1a7f75866e`/`exp0063-wall-05-video`와 연결된다. 해당 답변은 구간 차이가 작고 오른쪽 박스가 더 맞는다는 **정렬 관찰**이며 전체 음성 의미나 정밀 경계의 사람 정답이 아니다. 기존 답변을 재사용하고 반복 질문·자동 정답 승격을 하지 않았다. 이 보고서의 FP는 공식 annotation과 모델의 불일치를 뜻한다.

## 입력·분할·검수 범위

Run `run_3d23462a014a`, Task `task_097e754be4db`, Dispatch `ctx_1518122215d9`, owner `term_7f1bc18c-bed6-4684-9360-b82bb35be69c`의 새 live 배정을 사용했다. 이전 terminal 재사용 실패는 권한으로 사용하지 않았다. 실제 context·HEAD·source·입력 digest와 총괄의 단계별 GO를 canonical queue adapter가 검증했다.

작업 시작과 GPU 전·수정 실행 전·최종 감사 후에 `docs/WEB_REVIEW_WORKFLOW.md`의 `pending --include-acknowledged`를 성공적으로 조회했고 미처리 요청은 없었다. 적용 snapshot의 여덟 답변(`version=4`, `answer_version=1`)을 읽었으며 여섯 오른쪽 박스 선호·두 차이 없음의 제한된 관찰 범위를 유지한다. 검수 원문·기존 처리 이력은 보존한다.

아래 경로는 별도 표시가 없으면 `outputs/action-recognition/exp0063/` 아래다.

| 고정 입력 | SHA256 |
| --- | --- |
| `clip-plan-v2/candidate-manifest.json` | `72912fab027a068d0e6043f328d86a2c7d15a239afa751d126984c5c10498931` |
| `baseline/attempt-002/baseline-lock.json` | `3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40` |
| `combined-split-v3/split-manifest.json` | `bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499` |
| runtime `review-followup-v1/review-release-v2.json` | `7305b347f9783ca29d1055c3002cc6135ad41144e75874f153031d0d2fa3635b` |
| runtime `review-followup-v1/source-freeze-v2.json` | `e3457837595f5b0e89ee8fe6921d4f35ea923caddd6bc105f35f61e7e8857b3c` |
| `configs/exp0063_action_training.json` | `7c94f0e183151e489b6de23e0d20fa827bf1fd7fb9aa5737aee34e513196d25b` |
| `weights/action-recognition/exp0063/r3d_18-b3b3357e.pth` | `b3b3357ead25631ec9c57362ff2128a92d0427e01e2cd184951a44380c3f2e9d` |

사전학습 가중치는 공식 `R3D_18_Weights.KINETICS400_V1`, 133,546,016bytes이며 같은 디렉터리 `provenance.json`에 출처를 보존했다. 이 파일과 아래의 학습된 `best.pt`를 구분한다.

| 분할 | wall_over | moving | stand | sit_down_bench | sit_down_floor | 합계 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 학습 | 1,571 | 569 | 893 | 159 | 393 | 3,585 |
| 검증 | 411 | 0 | 0 | 134 | 180 | 725 |
| 시험 | 582 | 304 | 545 | 0 | 0 | 1,431 |

1,081개 원본, 5,741클립이다. 검증 음성이 앉기만 포함하므로 CE 선택을 보행·대기 검증으로 확대하지 않는다. 보호된 기존 45원본은 학습·검증·시험·threshold 선택에서 제외했다. 고정 설정은 seed6301, native3fps의 연속8프레임, RGB112×112 letterbox, batch4/accumulation4, AdamW lr/weight_decay 각0.0001, 10epoch, threshold0.5, AMP float16이다. 설정 JSON의 `actual_gpu_smoke:false`는 원래 준비 단계의 동결 표기이며 실행 성공은 설정을 고쳐 쓰지 않고 실제 receipt/result로 증명한다.

## CPU 준비와 동등성

최초 CPU GO 뒤 순차 `prepared-v2`를 한 번 시작했고 별도 전체 preflight 해시를 중복하지 않았다. 낮은 처리량을 보고한 뒤 총괄이 CPU 전용 `scripts/prepare_action_pixels_parallel.py`와 `tests/test_action_parallel_prepare.py`의 별도 구현을 승인했다. 기존 decoder·정책·설정은 그대로 두고 spawn4와 최대 in-flight4, 첫 오류의 대기 작업 취소, 원래 인덱스/순서, 전체 성공 뒤 atomic `prepared.json` 게시를 적용했다. 실제 합성 encode/decode·변조·실패·정책 변경·순차 동등성 7시험이 통과했고 독립 검토를 받았다. 승인된 commit window에서 두 파일만 `930e21b`로 commit했다.

17사례 사전 고정 benchmark는 존재하는 행동/분할/cohort 조합과 영상 경계·가로세로·종횡비 극단을 포함했다. 원본/주석2,162파일 전체 해시를 통과하고 모든17 NPY의 바이트·배열·dtype·shape가 같았다. 디코딩은 순차15.946199초, 병렬4.351445초로 **이 표본에서만** 3.664575배였다. 전체 검증 포함662.703초이며 동시 실행 조건의 표본 값을 전체 속도 향상으로 확대하지 않는다. 결과 SHA는 `ad710c9c8aeb421a2a70fea20dc7b1ec01c29a8c18c43b11d8238169cc5e3780`이다.

총괄 승인으로 원래 PID2099445의 명령·boot/start-ticks identity를 확인하고 pidfd SIGTERM을 보냈다. pidfd 종료·`process_state=exited`·launcher exit−15를 확인했으며 원래 출력과 로그는 보존했다. 완성된2,033 NPY(인덱스0–2032, 부분파일0)를 별도 복사해 전부 SHA 대조했다. snapshot SHA는 `080bf01a7cd5c686e73cdd744b2087f46c3631ae73df9371e67b501f2c07633c`다. 구성은 wall_over2029·stand4이며 다른 정상 유형 검증을 대신하지 않는다.

별도 전체 CPU GO 후 `prepared-v3`를 한 번 완료했다. 원본/주석2,162파일의 해시, 전체5,741 NPY/45,928프레임, 원래2,033개 snapshot 전부의 바이트·배열·dtype·shape 동등성을 통과했다. producer `prepared.json` SHA는 **`9d8d05f20da34a797a0619c066e9142df3ad15d8aafb6b1f991290a83631f1b4`**다. 실제 전체 프로세스는2,594.851888초, decoder pool은1,760.706442초(3.260623 NPY/초)였다. producer의2,377.086077초는 초기 contract 검증 뒤부터의 값이다. process start-ticks/CLOCK_BOOTTIME·pidfd 종료 근거는 `execution-v1/full-prepare-measured-timing.json`이다.

총괄이 별도 승인한 smoke 전용 CPU 준비는 train32/validation4/test0만 선택했다. 38개 원본/주석을 해시하고 시험 픽셀에는 접근하지 않았다. `prepared-smoke-v1/prepared.json` SHA는 `a30c1d9032dc02987796f9bb77444ef77dd1dfe0ea997998deffa4784ddca9c7`이다. 최종 전체 corpus와 이36개의 바이트·배열·dtype·shape도 전부 일치했다. 증거는 `execution-v1/full-preparation-validation.json`, `full-smoke-equivalence.json`, strict `preparation-evidence.v1.json`(SHA `06d666053fdc08209a86a01fbf32b5ee5b2e892972fbc119824dfaba9ba8e97b`)이다.

AMP 수정 뒤 원본을 재디코딩하거나 과거 producer SHA를 바꾸지 않았다. `execution-v2/preprocessing-compatibility-source-proof.json`은 이전 Git99d18b3과 기존10개 helper·import/global·AdamW 생성까지의 prelude가 같음을 확인한다. adapter는 이전 producer의 trainer/driver 해시와 현재 소비 NPY/annotation 바이트를 검증한다. 사용하지 않는 원본 영상의 현재 바이트를 새로 검증했다고 주장하지 않는다. `data-identity-vs-v1.json`은 수정 전후 데이터/픽셀 바인딩 동등성을 담는다.

## 네 번의 canonical GPU 단계

초기 GPU는 free3,032MiB/util99%로 6,144MiB gate를 통과하지 못했다. 다른 프로세스를 종료하거나 gate를 낮추지 않았다. 사용자가 다른 GPU 작업 정리를 알리고 총괄이 충분한 여유를 확인한 뒤 실제 GO를 받아 실행했다. 모든 단계는 canonical adapter의 새 stage job으로 한 번씩 제출했으며 `Queue.retry` 호출은 0이다.

| 단계 | job | attempt | 실제 결과 |
| --- | --- | --- | --- |
| 원래 smoke | `104cafd4032b4472bb8daf1854dbe8eb` | `c386b63a5265425f85659d1015253c21` | exit0, 32train/4val/2update, 시험 접근false |
| 원래 전체 학습 | `c65a6e699b7b4cebbebfcc042022fa04` | `058639f80f394a71b345eb4eae5ceacb` | exit1, 첫 epoch 완료 전 nonfinite norm 예외 |
| 수정 smoke | `17ca440f9cd7453982a45e2b96e830a8` | `e880e2d07ff1406793fd762fb7582416` | exit0, 32train/4val/실제2update/skip0, 시험 접근false |
| 수정 전체 학습 | `2bc23fd542bc4b90b9ac22e66c40ab13` | `67e95fc8cf204de7be9627e81f524931` | exit0, 10epoch, 실제2,248update/skip2, 시험1회 |

첫 smoke `last.pt`의62 Adam state가 모두 step2임을 CPU로 확인했다. 결과 SHA는 `e855631708e133c2ccdc670760399bd31a2e75a5ab55a4452e8535b1ca60eb09`다. 수정 smoke도 별도로62 state/step2·유한성을 확인했으며 result SHA는 `296138bf10cb8484660dff856703ac0f8428407bc48865e146bd0bd71c945dab`이다. 둘 다 batch4 여덟 번/누적4의 두 실제 update이며 시험 픽셀·평가가 없다. 수정 core의 통과를 원래 smoke에서 빌려오지 않았다.

원래 전체 학습의 고정 trainer SHA `2a0d01de3ec9b872c99761472b0626ba1e5f41a5b9f2c9be4eef4fe5626ff350` line386 `clip_grad_norm_(…, inf, error_if_nonfinite=True)`가 nonfinite total norm으로 실패했다. 완료 epoch0, 저장 history/checkpoint/result/시험 scores 없음이다. epoch 안의 실제 update 수와 peak memory는 기록이 없어 **알 수 없음**으로 남긴다. traceback만으로 원소별 overflow나 정확한 실패 batch를 확정하지 않는다. child/supervisor 모두 identity 기반 종료를 확인했다. `execution-v1/training-failure-evidence.json`에 로그 SHA `4ec93636a582f7d016e8345a309b7a34c751587ae34eaa965849e931b6be1f6c`와 receipt SHA `2d52713873d3a28363b2786fba3518ee9b473bc550cb757680b6bea0c11d6c5b`를 보존했다.

종료 뒤 총괄 `msg_183a69eac79e`가 제한된 수정 창을 열었다. 표준 GradScaler의 nonfinite gradient update skip/backoff 흐름과 실제 AdamW post-step counter, attempted/applied/skipped 및 scale 전후 JSONL, epoch/checkpoint 전 parameter/buffer/optimizer-state 유한성 검사를 추가했다. 무한 norm clipping 자체를 제거했으며 `error_if_nonfinite=False`만 바꿔 inf/inf gradient 변형을 허용하지 않았다. nonfinite forward loss와 epoch 실제 update0은 계속 실패다. 설치된 Torch2.5.1 소스와 [공식 AMP 문서](https://docs.pytorch.org/docs/stable/notes/amp_examples.html)의 scaler 흐름을 대조했다.

모델·seed·lr·epoch·threshold·분할·가중치 설정은 바꾸지 않았다. 기존24개와 실제 CPU GradScaler/AdamW7개, 총31시험 및 독립 반례가 통과했다. scale0.5→0.25, skip 뒤 moment 보존/실제 update, norm reduction overflow, nonfinite model/buffer/moment/step 거절을 확인했다. 총괄이 수정 trainer/tests를 `24bf013`으로 commit하고 adapter 복구와 함께 **`166c96aa0ee3de18b8d1fe01f26b7430084adef3`**에서 동결했다. 동결 전 통합100개 검사가 통과했다. 수정 revision `amp-overflow-v2`는 별도 실패 참조·정확한 source·새 smoke proof·총괄 GO를 바인딩한다.

최종 source freeze는 `execution-v2/coordinated-source-freeze-v5.json`, SHA `de1b2368f7fda067422732d1e402da9631adca2361a7857b7bc17fca2ecafe5f`다. trainer SHA는 `770114f8eb9c09a44be33232c99b687e10989e5622eba82cd675d50e5156478a`, trainer tests는 `276716c33e322a2635740cf50b3c0472ccedc76108a619191e16637ec3200fc7`, adapter command는 `cddc583c53b2264d39fe412ca97c32e9ec93dd0cff30e8a2a7efff162edbf95c`다. 초기 source-freeze-v2와 중간 freeze도 이력으로 남아 있다.

## 최종 학습·메모리·산출물 감사

매 epoch는 3,585개 학습 클립을 896×4+1×1 microbatch로 처리하고 225개 누적 경계를 갖는다. 실제 skip은 epoch1과 epoch10의 마지막 한 표본 경계에서 각1회였고 scale은 둘 다65,536→32,768이었다. 나머지2,248경계는 실제 AdamW update다. 2,250개 `amp-updates.jsonl` 이벤트를 모두 감사해 누적·epoch history와 일치함을 확인했다. 이전 실패의 정확한 위치를 이 새 관찰로 추정하지 않는다.

| epoch | train CE | validation CE | 누적 실제 update | 누적 skip |
| --- | ---: | ---: | ---: | ---: |
| 1 | 0.148595402 | 0.027395310 | 224 | 1 |
| 2 | 0.041710291 | 0.010273138 | 449 | 1 |
| 3 | 0.016485797 | 0.004467446 | 674 | 1 |
| 4 | 0.011204086 | 0.007758647 | 899 | 1 |
| 5 | 0.006640210 | 0.002958794 | 1,124 | 1 |
| 6 | 0.008267300 | **0.002244212** | 1,349 | 1 |
| 7 | 0.006672786 | 0.005138699 | 1,574 | 1 |
| 8 | 0.001955820 | 0.002868576 | 1,799 | 1 |
| 9 | 0.002282950 | 0.004739394 | 2,024 | 1 |
| 10 | 0.003708654 | 0.004610437 | 2,248 | 2 |

매 epoch model102개와 optimizer186개 tensor가 유한성 검사를 통과했다. CPU `map_location` 감사에서도 best/last의 model·optimizer 모든 tensor가 유한하고62 Adam parameter state의 step이 각각1,349/2,248이었다. best는 epoch6, last는 epoch10이다. best-validation scores는 epoch006 validation scores와 같다. 각 epoch validation725개와 최종 test1431개의 정확한 ID·분할·순서도 감사했다.

환경은 RTX3080, Torch2.5.1+cu124, torchvision0.20.1+cu124, CUDA12.4다. 최종 PyTorch peak allocated memory는 **889,882,112bytes**이고 두 smoke는 각각888,636,928bytes다. 이는 allocator 측정값으로 전체 GPU 사용량과 구분한다. 최종 wrapper elapsed는 **966.190405초**이며 입력 gate·학습·검증·checkpoint·시험을 포함한다. 첫 실패 wrapper729.278785초 역시 입력 검증 포함이다. GPU kernel 전용 시간은 별도 계측하지 않았고 파일 mtime으로 추정하지 않는다.

| 최종 산출물 | SHA256 |
| --- | --- |
| `best.pt` | `8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73` |
| `last.pt` | `399202c6fed774d94d2969496eca1a791f2dbbc72865bd797224f72ec0d3dd61` |
| `result.json` | `9a8bb01f62973b91d959c3e8f9d3bfc80d9ef2094dc6169905295bc44aa8eaf5` |
| `history.json` | `9d9b066f1474ffc29c3f6d4a5690dd544abfd3d7375bc6e88d663ccf1069dcf3` |
| `test-scores.json` | `bf9afead01f4c89b0f388e2fd86051058d02ba6d3e684c17ee81fdf93543dc70` |
| `test-failures.json` | `9222727396e5f318c420f891500f5d383e440ca5a08d67604c85fcb50c4176a4` |
| `amp-updates.jsonl` | `1c176f886e6e35b7a81a7df594e70d334929f2d3dbe942ffda13423292dde8e9` |

최종 CPU 감사 `runtime/action-recognition/exp0063/execution-v2/final-training-audit.json`은 `status:passed`다. 감사는 저장 JSON/metadata/산술과 CPU checkpoint 읽기만 사용했고 CUDA를 초기화하거나 모델/시험을 재평가하지 않았다. canonical job은 succeeded/exit0이며 supervisor·child 모두 종료했다. 최종 학습 전98개 job/attempt의 **모든 기존 행이 동일**하고 관찰 시 queue는99jobs/99attempts였다. 초기95행과 원래 smoke·실패 학습·수정 smoke도 그 안에 포함된다. queue DB 파일 자체는 새 행 추가로 바뀌므로 전체 DB 바이트가 같다고 주장하지 않는다.

## 명령·권한·로그 위치

재실행 안내가 아닌 **실제로 한 번 호출한 명령의 기록**이다. repo root에서 기존 `.venv-cv-batch02/bin/python`을 사용했다. 원래 명령/argv·context·시각·exit는 `execution-v1/prepare-command.*`, `parallel-prepare-command.*`, `prepare-smoke-command.py`, `smoke-queue-command.sh`, `train-queue-command.sh`와 대응 log/launch/exit JSON에 있다. CPU 전체 준비·smoke 준비·GPU smoke·전체 학습마다 별도의 총괄 GO를 받았다.

수정 실행의 실제 argv는 `execution-v2/smoke-queue-command.sh`와 `train-queue-command.sh`에 있다. 공통 wrapper는 `execution-v2/execute-action-training-queue.py`(SHA `e56bf5c93240714dfc9c9167d6ae5727be8abd01e2bad22787d559b85418acf7`)이며 canonical queue adapter만 호출한다. `--execution-revision amp-overflow-v2`, smoke timeout1800초/train7200초, 각 exact queue-config/input-contract SHA와 실제 GO message를 전달했다. smoke GO는 `msg_2f38dab66070`, train GO는 `msg_3036d4136990`다.

| 최종 train 바인딩 | 값 |
| --- | --- |
| queue-config SHA | `09883c6399dbef6b7c3c7afdddf02531e6068ef739b253d96a90baf00a22645a` |
| authorization SHA | `ff80fd8ef05f1e85672bb4734c7da1ca2654d58c7e1715bcb90eb27d20f4c93f` |
| input-contract SHA | `b915f832f7d91bf6a238f49057d1e7d26896e975c77370736dbd8041ee3286a8` |
| input digest | `4d6491241b70643ea98743064e3dda478e2b812c15094668933e6f5ef5db052c` |

wrapper는 exclusive stage marker를 만들고 enqueue 전 상태를 남긴다. 예외/응답 소실을 GPU 종료로 간주하지 않고 deterministic job key를 읽기 전용으로 조정한다. 권한 true 플래그는 총괄이 작성한 exact authorization에서만 받았으며 fabricated auth·직접 GPU 실행·queue 초기화·실패 retry는 하지 않았다. canonical receipt와 실제 child command/log/config/live context는 `/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue/attempts/<attempt>/`에 남아 있다.

수정 실행의 `smoke-queue.log`, `smoke-queue-exit.json`, `smoke-result-binding.json`, `smoke-optimizer-state-proof.json`, `train-queue.log`, `train-queue-exit.json`, `train-progress-checkpoint.json`과 최종 감사는 `execution-v2/` 아래다. 원래 queue95행 snapshot은 `execution-v1/queue-before.json`, 수정 전97행은 `execution-v2/queue-before-recovery.json`, 최종 학습 전98행은 `queue-before-revised-train.json`이다.

이번 worker 범위의 학습·저장 결과 감사는 완료했다. 사람 행동·침입 완료 지표는 `null`, 기존45영상 전체 pipeline 비교는 이 실행 결과에서 `not_executed`다. 총괄이 별도 소유하는 후속 inference/요약/실패 영상과 구분한다. 추가 학습·시험 재실행·기준 튜닝·운영 기본 교체·GitHub push는 수행하지 않았다.
