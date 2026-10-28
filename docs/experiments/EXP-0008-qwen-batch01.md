# EXP-0008 — Qwen3-VL-2B 기준 실행

- 날짜/담당: 2026-10-28, slot1 / gpt-6.1-sol high. 실효 모델·effort는 총괄이 실제 세션 증거로 확인해 native 메시지와 배정 자료에 기록했다.
- 상태: **실제 공통 큐 실행 성공, 6클립 생성 완료. 행동 판정·모델 채택은 보류.** 첫 attempt에서 종료했고 재시도는 0회다.
- 계약: [BATCH-0001](BATCH-0001-plan.md), [공통 질문](../../configs/vlm_batch01_prompt.txt), [전달 절차](../orchestration/EXPERIMENT_DELIVERY.md). 관련 결정은 ADR-0015와 기존 ADR-0012다.
- 소스: worker `dcaab6fc64df57f82fca8f605bfb3b7d37920a20`, 실제 실행 통합 commit `f33c439058d23fdb91b05ece1b6462d6c8cf6418`.
- native Run `run_3d23462a014a`, Task `task_0bfc2bc3eafc`, Dispatch `ctx_c9acf995dc40`.
- queue job `e15b2f2fe1744eac816fef216a131374`, attempt `8b93c06304724009b8ca5a0d15a28288`, attempt_no 1, exit 0.

## 가설과 목적

EXP-0007과 같은 기존 Qwen 가중치·10프레임 처리 예산으로, 이번 배치의 중립 영어 질문에 대한 행동 설명·형식 준수·실행 비용을 기록한다. 다른 모델과 공통 질문을 고정하는 개발 비교이며, 기존 한국어 EXP7의 재현이나 언어만의 효과 측정은 아니다. 생성 성공과 JSON 파싱 성공을 행동 정답으로 취급하지 않는다.

## 데이터와 평가 범위

AI-Hub 71850 침입 범주의 기존 EXP7 clip01~06 RGB cache와 input JSON을 그대로 재사용했다. [선정 manifest](../../configs/vlm_exp0007_manifest.json)의 6개 의도적 개발 구간이며, 독립 테스트셋·검수 완료 음성 구간이 아니다. 01/03/04는 C3 카메라가 중복된다. 원본 영상·라벨·가중치·기존 출력은 보존했고, 원본 영상 재배포 허용을 새로 확정하지 않았다.

각 클립은 약 5초 구간에서 원본 순서 10프레임이다. 명목 2fps이고 마지막 표본은 대개 시작 후 4.5초다. clip03은 실제 FPS 29.97002997, 간격 0.5005초, 마지막 상대 시각 4.5045초다. 실제 PTS/native PTS/time base/index는 클립별 로컬 측정 파일에 보존했다. 모델에는 RGB와 익명 clip ID 및 고정 질문만 넣었다. 원본 파일명·관찰 초안·공식 라벨·이전 답변·CV 표시를 넣지 않았다.

정답 단위는 아직 확정하지 않았다. 기존 사용자 관찰과 Codex 초안에 대한 부합 여부·넘기 누락·근거 없는 완료 주장·판단 유보를 총괄/독립 검토가 비교한다. 본 작업자는 새 영상 의미 검수나 독립 GT를 만들지 않았다. 최종 정확도·precision/recall/F1·사건 시점 오차는 미측정이다.

## 실행 전 고정과 큐 보존

독립 검토가 동일 소스에 대해 26개 CPU fixture 통과와 조건부 Qwen 실행 가능을 확인한 뒤 총괄이 명시적으로 GO를 보냈다. 작업자 자체 검증은 기존 큐 14개와 신규 8개, 총 22개 통과였다. 이는 GPU 실험 수치가 아니다.

실제 기존 SQLite의 command CHECK를 확장하기 전에 백업했고, 트랜잭션 안에서 테이블을 재구성했다. 기존 **8개 job/8개 attempt의 모든 열 값**, foreign key, 백업 내용이 사전 snapshot과 일치함을 확인했다. 종료 후에도 기존 행이 동일했다. 새 큐를 만들거나 기존 기록을 지우지 않았다. 백업 SHA256은 `363b80f4810d6c4a3c526872825517759733f66c54f4f4d1c34c68bc39abcbc3`이고, 사전 snapshot SHA256은 `c38c8ce8da4982e93b81c277af707460d90cdc192ee784a1d7c8f5c5466cc996`다. 원본 DB·백업·receipt는 로컬 전용이다.

| 고정 항목 | SHA256 |
| --- | --- |
| 공통 질문 | `049ec4a6274443fcf8e3069914e53b2913aefa6f4a13ca049cc4001fa8def7a6` |
| 입력 계약: 12개 cache/JSON 및 모델 파일별 해시 | `0824cc4f5dd8cac66c20af871ed656c82840c19cf0fd0f02a3f088a02855c62d` |
| 설정 계약 | `a176ea703189e851ae8b347106a2ebf9cb3e93e3156f4b23107e8c22c7793a30` |
| 선택 adapter·runner·queue·공통 parser·질문 등 실행 소스 | `2588c324046576bd2a951a34b520a0c5753a1f00bcc817b1a6ec6a703ca8bbfa` |
| Qwen 실행 전 확인 receipt | `e2db007c9c33a2a4d8800835111da89881214eda7e5d6a5bb2c2ea1f1a7f3196` |

실제 12개 입력 해시와 질문 해시를 사전 등록 자료에 대조한 뒤 enqueue했다. 큐는 실행 직전 실행 소스·설정·입력과 모델 파일을 다시 검증했다. runner는 canonical 잠금 FD와 실행 중인 정확한 queue attempt/부모 supervisor의 연결을 확인한 뒤 torch/model 코드를 불러왔다. 기존 단일 GPU flock을 자식이 상속하고, FIFO·정확한 child pidfd·900초 timeout·명시적 retry 최대1회 규칙을 유지했다. 협력하는 큐의 보호이며 머신 전체 GPU 접근 통제는 아니다. supervisor가 사망하면 상속 잠금은 유지되지만 timeout 강제도 중단될 수 있다.

## 환경과 모델

로컬 관측: WSL2 Linux 6.6.87.2, Python 3.10.12, RTX 3080 10,240 MiB, driver 610.88, torch 2.5.1+cu124, CUDA 12.4, transformers 4.57.1, numpy 2.2.6. 기존 VLM 환경을 그대로 사용했고 설치/갱신하지 않았다. 전체 package version 목록은 로컬 summary에 보존했다.

모델은 기존 Qwen/Qwen3-VL-2B-Instruct, revision `89644892e4d85e24eaac8bacfd4f463576704203`이다. 기존 [EXP-0007의 출처 기록](EXP-0007-local-vlm-action-analysis.md)에 있는 공식 LFS 해시와 실제 4,255,140,312-byte 가중치 해시 `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`가 일치했다. 기존 기록의 Apache-2.0 모델이며 새 가중치 다운로드는 없었다.

BF16·SDPA·비양자화·cuda:0를 지정했고, 실제 모든 모델 parameter가 cuda:0에 있음을 확인했다. 한 번 로딩한 adapter로 clip01→06의 독립 대화를 각각 생성했다. seed 0, batch 1, greedy `do_sample=False`, `max_new_tokens=384`, `repetition_penalty=1.0`이다. 외부 추론이나 미디어 전송은 없었다.

Qwen의 기존 size 예산 `shortest_edge=16384`, `longest_edge=3584000`을 유지했다. 실제 모든 클립은 1920×1080 RGB 10장→**768×448 RGB 10장**, grid `[5,28,48]`, visual token **1,680**, 전체 input token **1,943**이었다. resize 호출 1회, 추가 sampling 0, temporal padding 0을 확인했다. grid의 공간 크기는 보존한 resize 결과와 일치한다. 정규화 전 실제 resize RGB·입력 검수 시트·확장 prompt·PTS·grid/token metadata는 로컬에 저장했다. Smol과 같은 해상도/시각 토큰량이라고 해석하지 않는다.

## 실행 명령과 원천

통합 commit의 저장소 루트에서 아래와 같은 고정 API로 등록하고 기존 CLI로 실행했다. 로컬 실행 receipt에는 실제 argv·interpreter·cwd와 전체 입력 계약이 있다. `qwen-preflight.json`, 사전 등록 및 migration receipt는 Git 제외된 동일 batch runtime에 보존했다.

```python
from orchestration.queue import Queue
from orchestration.vlm_command import RUNTIME, SETTINGS, input_contract

queue = Queue.initialize(RUNTIME)  # 실제 migration 및 원본/백업 대조 후 등록
queue.enqueue(
    job_key='BATCH-0001-EXP-0008-baseline',
    run_id='run_3d23462a014a', task_id='task_0bfc2bc3eafc',
    dispatch_id='ctx_c9acf995dc40', owner='slot1_qwen_gpt-6.1-sol_high',
    command='vlm-batch01', input_value=input_contract('qwen'),
    config={'adapter': 'qwen', 'settings': SETTINGS}, timeout=900)
queue.run_once()
```

실제 시작 CLI에서 절대 경로를 치환한 공개 표기는 `python3 -m orchestration.queue --runtime "$SCENEGUARD_QUEUE_RUNTIME" run-once`다. 기존 canonical runtime의 실제 절대 경로와 실행 worktree는 로컬 receipt에 있다. 새 시도나 자동 재실행은 등록하지 않았다.

새 로컬 출력의 상대 위치는 `outputs/vlm_batch01/EXP-0008/8b93c06304724009b8ca5a0d15a28288/`이다. 이 경로는 공개 artifact URL이 아니다. 원문 UTF-8·생성 token IDs·실제 RGB·확장 prompt·GPU polling·측정값을 로컬에만 보존했다. 공개 [metrics](../../records/EXP-0008/metrics.json)의 각 값은 원천 상대 참조·JSON pointer·원천 SHA256과 연결된다. 작업자의 전체 파일/해시 목록은 Git 제외 `runtime/qwen-batch01/worker-artifacts.json`에 있다.

## 실제 정량 결과

실행 시각은 2026-10-28 **08:53:10.997~08:53:34.851 UTC**이며, KST 17:53:10.997~17:53:34.851이다. Queue claim→완료 receipt는 **23.854036초**로 자산 재검증·자식 시작·로딩·저장 등을 포함하고 큐 대기는 제외한다. 모델/processor 로딩과 CUDA 동기화는 **2.493953초**였다.

클립별 각 값은 단일 관측이다. npy 읽기는 기존 RGB cache 로드만, 전처리는 processor와 CUDA 전송/동기화만, 생성은 generate와 CUDA 동기화만 측정했다. 입력 검수 시트·응답 저장은 생성 시간에 포함하지 않았다. 원본 영상 decode는 재사용 때문에 미측정이다.

| 클립 | npy 읽기 s | 전처리 s | 생성 s | 출력 token | torch 할당 최고 GiB | torch 예약 최고 GiB | 엄격 파싱 | 허용 후처리 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| clip01 | 0.013104 | 0.083656 | 2.865687 | 73 | 4.342104 | 4.511719 | 실패(펜스) | 통과 |
| clip02 | 0.007419 | 0.091263 | 2.135669 | 69 | 4.342410 | 4.511719 | 통과 | 통과 |
| clip03 | 0.006278 | 0.080108 | 3.430297 | 106 | 4.342410 | 4.511719 | 실패(펜스) | 통과 |
| clip04 | 0.004601 | 0.072912 | 2.506724 | 85 | 4.342410 | 4.511719 | 실패(펜스) | 통과 |
| clip05 | 0.014980 | 0.074040 | 2.624695 | 94 | 4.342410 | 4.511719 | 실패(펜스) | 통과 |
| clip06 | 0.009568 | 0.065713 | 2.590107 | 80 | 4.342410 | 4.511719 | 통과 | 통과 |

6개 클립 생성의 합은 **16.153179초**, 산술평균 **2.692196초**, 중앙값 **2.607401초**, 범위 **2.135669~3.430297초**다. 서로 다른 6개 개발 입력에 대한 값으로 반복 성능시험·온라인 탐지 지연·영상 FPS가 아니다. 출력은 합계 **507 token**, 토큰 상한 도달 0/6, OOM 0/6이다.

엄격 schema 파싱은 **2/6**, 허용한 전체 단일 JSON 펜스만 제거한 후 파싱은 **6/6**이었다. 펜스 제거가 필요한 클립은 01/03/04/05다. 내부 JSON이나 enum·문장을 수정하지 않았다. 형식 개선을 행동 개선으로 세지 않는다.

torch 최고 allocated는 **4,662,626,816 bytes**, reserved는 **4,844,421,120 bytes**로 모델을 포함한다. GPU 전체 polling은 약 0.5초 간격 **37개**, polling 오류 0개, 관측 최고 **6,457 MiB**였다. 다른 프로세스/화면 사용량이 포함되며 순간 최고를 보장하지 않는다. torch 프로세스 메모리와 전체 장치 관측값을 같은 지표로 비교하지 않는다.

## 응답 관찰과 실패

다음은 원문 공개 대신 남기는 작업자 검토용 요약이며 최종 행동 평가/사람 검수 정답은 아니다.

| 클립 | 로컬 응답에서 확인한 경향 | 남는 문제 |
| --- | --- | --- |
| 01 | 접근/대기를 설명하면서 완료를 주장 | 자체 근거 서술이 반대편 이동을 설명하지 않음 |
| 02 | 경계를 넘는 행동과 완료를 주장, 열린 문/횡단보도를 근거로 설명 | 기존 관찰 초안의 신체 상승·개별 완료 미확정과 대조 필요 |
| 03 | 접근/대기, 완료 미확인, 가림으로 불확실성 표현 | 기존 원거리 보행 초안과 정확히 같은 행동 서술은 아님 |
| 04 | 서 있음/대기를 설명하면서 완료를 주장 | 기존 신체 상승 초안 대비 누락 의심과 내부 근거 불충분 |
| 05 | 대기/통행을 설명하면서 완료를 주장 | 기존 신체 상승 초안 대비 누락 의심과 내부 근거 불충분 |
| 06 | 통행/접촉과 완료를 주장하고 불확실성을 비움 | 기존 거리·차량 가림·접촉 초안은 완료 근거가 아니며 사람 재검수 필요 |

완료 관찰을 주장한 **01/02/04/05/06의 5/6**에서 자체 근거 문장은 반대편으로 이동하는 관찰을 제시하지 않았다. 이는 응답 텍스트의 근거 부족에 대한 작업자 검토 의견이며, 실제 완료가 없었다는 새 영상 정답은 아니다. 03이 완료를 유보하고 가림을 언급한 점은 확인되지만 기존 보행 초안과는 부분적으로 다르다. 응답의 서술만으로 반대편 이동이나 출입 권한을 확인했다고 할 수 없다. 특히 02/06의 핵심 의미는 로컬 원본과 실제 입력 시트를 사람이 확인해야 한다. 이 작업자는 픽셀을 클라우드 이미지 도구로 보내지 않았다. 최종 부합 등급과 후보 비교는 총괄/독립 검토가 별도 작성한다.

실제 모델 실행 오류는 없었다. 로그의 `torch_dtype` deprecation 및 greedy에서 무시되는 기본 temperature/top-p/top-k 안내는 보존했다. 샘플링을 활성화하거나 설정을 바꾸지 않았다. 초기 CPU fixture 실행에서는 SQLite가 따옴표를 붙인 테이블명 처리와 수정 중 정규식 오류를 발견했고, 최종 commit 전에 수정·회귀검증했다. 이를 실제 모델 실행 실패/재시도로 세지 않는다.

## 해석과 남은 전달 절차

로컬에서 확인한 것은 고정 Qwen 설정의 실행 가능성, 6개 응답의 형식 차이와 측정 비용이다. 완료 주장에 대한 근거 부족과 기존 넘기 관찰 초안 대비 누락 의심이 남으므로 기본 CV 연동/모델 채택은 보류한다. 기존 EXP7과 질문·schema가 달라 생성 시간/내용 차이를 모델 개선으로 해석하지 않는다.

담당 배정과 실제 진행 카드 확인은 총괄이 수행했다고 통지했으며 원본 browser receipt를 소유한다. 본 보고서 제출 시 작업자 담당인 **코드 구현·실제 기준 실행·측정값/로컬 artifact 저장**을 완료했다. 최종 report/metrics SHA에 연결된 총괄·독립 검토, 완료 등록, GitHub 게시와 원격 SHA 확인, 최종 보고서/그래프/영상/검토의 로컬 화면 확인은 총괄이 별도로 완료해야 한다. 이 작업자는 push나 등록을 실행하지 않았다. 추가 실험은 실행하지 않았다.
