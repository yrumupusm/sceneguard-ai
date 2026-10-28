# EXP-0010 — Qwen 전체 화면 픽셀 예산 대조

- 날짜/담당: 2026-10-28, slot1 / gpt-6.1-sol high. 실효 모델·effort의 실제 세션 증거는 총괄 소유다.
- 상태: **실제 공통 큐 실행 성공, 6클립 생성 완료. 행동 개선 입증 안 됨·채택 보류.** 첫 attempt에서 종료했고 재시도0회다.
- 사전 결정: [픽셀 예산 계획](EXP-0010-qwen-pixel-budget-plan.md), 고정 commit `5d6ef40`. 공통 계약은 [BATCH-0001](BATCH-0001-plan.md)이다.
- native Run `run_3d23462a014a`, Task `task_be6c4ddef130`, Dispatch `ctx_735ddbea9bba`.
- 구현 commit `4a87233`, 실행 통합 commit `cdfee87a2e8457367736588d73bfa11769ef562c`.
- queue job `fed21175b81040ae817bd51993fade70`, attempt `c0fd8f0c63154c5d837d5c149bf948b5`, attempt_no1, exit0.

## 질문과 고정 변화

[EXP-0008](EXP-0008-qwen-batch01.md)의 행동 누락 및 근거 없는 완료 서술을 바탕으로, 전체 화면을 더 크게 처리하면 기존 관찰 초안과 행동 설명의 부합이 나아지는지 한 번 확인한다. 작은 사람의 입력 정보 손실이 원인이라는 주장은 **가설**이다. 특정 사람 크롭·정답 제공·시간/프레임 재선택은 없다.

변화는 Qwen 공식 video processor의 `size.longest_edge` **3,584,000→7,168,000** 하나다. `shortest_edge=16384`, 원본 전체 화면10프레임·순서·native PTS·공통 영어 질문, 같은 2B 가중치/revision, BF16/SDPA/cuda:0, seed0/greedy/384토큰/rep1/batch1을 유지한다. baseline과 같은 모델·환경을 재사용하고 새 설치/다운로드는 없다. OOM이면 실패를 보존하며 예산을 자동 조정하지 않는다. 후보별 개선 한 번 예산을 소모하며 후속 조건 탐색은 없다.

## CPU 검증과 기준 보존

공식 로컬 Transformers4.57.1 processor만 로딩한 synthetic 테스트이며 가중치/CUDA/생성을 사용하지 않았다. baseline은10×3×448×768, grid `[5,28,48]`, 시각 토큰1,680·전체1,943를 유지했다. 변형은 **10×3×608×1120**, grid **`[5,38,70]`**, 시각 토큰**3,325**·전체**3,588**이었다. 총 픽셀 예산 두 배가 공간 크기나 토큰의 정확한 두 배를 뜻하지 않는다. 설치된 공식 `smart_resize`는 영상 전체 픽셀과32배수 반올림/내림을 적용한다. 실제6개 클립 실행에서도 이 shape/grid/token 값이 모두 같았다.

원본 순서별 synthetic 색 표식10개, 네 가장자리, 추가 sampling 호출 금지, 시간 padding0, resize1회, 공통 질문 포함 및 평가 메타데이터 제외를 확인했다. 고정 registry/동일 Qwen 자산과 interpreter/별도 EXP-0010 출력/기본 Qwen 코드 의존 source hash/큐 보존·timeout·retry를 포함해 **26개 테스트 통과(8.765초)**였다. `e0401dd`의 변경 전 Qwen과 현재 기본 Qwen에 같은 synthetic 입력을 넣어 모든 processor tensor·metadata·RGB가 정확히 같았다. Smol adapter·runner·공통 parser·prompt의 바이트도 같았다. 실제 생성 응답의 재현을 위해 baseline을 다시 실행하지 않았다.

검증 명령은 기존 VLM 환경의 `python -m unittest tests_orca.test_qwen_pixels tests_orca.test_vlm_batch tests_orca.test_queue -v`다. CPU 로그·공식 processor 소스 해시·baseline 대조 receipt는 Git 제외 로컬 artifact다. `qwen_high_pixels`는 별도 command나 임의 경로/옵션 없이 동일 `vlm-batch01` allowlist 안에서만 선택된다. 실제 `qwen.py`와 하위 adapter를 함께 source hash에 포함한다. 기본 Qwen/Smol 모델 매핑과 settings는 유지하며 큐 schema를 변경하지 않는다. 과거 job의 source/result는 갱신하지 않는다.

## 데이터와 해석 한계

기존 EXP7 clip01~06의 같은 cache와 input JSON을 재사용한다. 각5초·10프레임의 의도적 개발 구간이며 01/03/04에 카메라 중복이 있다. clip03의29.97002997fps/0.5005초 간격·마지막4.5045초를 보존한다. 원본 디코딩·최초 입력 준비는 재사용으로 별도 미측정이다. 모델 입력은 RGB·익명 ID·공통 질문이며 라벨/관찰/이전 응답은 평가 때만 사용한다.

기존 관찰 초안과 응답 텍스트를 대조하며 클라우드 이미지 도구로 CCTV 픽셀을 보내거나 새 영상 GT를 만들지 않는다. 넘기 단어만으로 행동 개선을 세지 않는다. 02의 개별 완료, 06의 접촉·가림·완료는 사람의 로컬 확인 대상으로 남는다. 근거 없는 완료는 응답 내부 근거에 대한 평가이며 사람이 확인한 false positive 건수가 아니다. 최종 정확도/F1·일반화·최적 설정·온라인 FPS/지연은 산출하지 않는다. 생성·파싱·검토·채택·웹 전달은 서로 다른 상태다.

## 실행 승인·등록·원천 고정

총괄이 정확한 native Task/Dispatch/slot1 배정과 Sol/high 세션 증거, 통합 소스의 검증을 확인한 뒤 한 번의 GO를 보냈다. 실행은 통합 worktree에서 기존 VLM interpreter·기존 canonical GPU queue의 `vlm-batch01`로만 수행했다. 담당 카드의 API 확인과 실제 브라우저 확인은 총괄의 별도 전달 근거이며, 모델 실행 성공으로 대신하지 않는다.

실행 직전 전체 GPU는10,240MiB 중1,539MiB 사용·8,515MiB 여유였고 compute 프로세스 조회는 비어 있었다. 첫 sandbox 안의 NVML 조회는 OS 접근 차단으로 실패해 권한 있는 로컬 조회로 확인했다. 이는 생성 실패나 queue retry가 아니다. 큐도 queued/running/unknown job 없이 유휴였다.

입력 계약의12개 cache/JSON 및 모델 파일 전체 해시를 baseline job의 저장 계약과 **정확히 대조해 일치**시켰다. Qwen 가중치는 기존 revision `89644892e4d85e24eaac8bacfd4f463576704203`, 4,255,140,312-byte `model.safetensors`이며 실제 SHA256 `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`가 기존 공식 pinned 기록과 같았다. 별도 모델·환경을 만들지 않았다.

| 고정 항목 | SHA256 |
| --- | --- |
| 공통 질문 | `049ec4a6274443fcf8e3069914e53b2913aefa6f4a13ca049cc4001fa8def7a6` |
| 입력 계약, EXP8과 동일 | `0824cc4f5dd8cac66c20af871ed656c82840c19cf0fd0f02a3f088a02855c62d` |
| 변형 설정 계약 | `e7f523248f9811f7e5ea4c91a5f836dc7bd9e29bb7161acfb3fc7f9061737c9d` |
| 변형·기본 adapter·runner·queue·parser·질문 실행 소스 | `1a63de66a92dfc0b01fd420b4ecde7432c07963e565bb952209c27dec83e3d8d` |

큐는 실행 직전에 입력·모델·설정·선택 소스를 다시 검증했고 runner는 canonical inherited flock FD와 정확한 실행 attempt·부모 supervisor를 확인한 후 모델을 로딩했다. 새 job/attempt만 추가했고 **이전10개 job 및10개 attempt의 모든 열 값이 실행 전후 정확히 동일**했다. 기존 EXP8 manifest의40개 artifact도 실제 SHA256이 모두 같았다. baseline 결과/등록 source를 새 코드 해시로 덮어쓰지 않았다. 새 schema migration·큐 우회·직접 추론은 없었다. 프로세스와 timeout은 기존 큐 규칙을 따르며 머신 전체 GPU 통제라는 의미는 아니다.

재현 명령의 공개 표기는 다음과 같다. 실제 절대 경로·cwd·전체 계약·enqueue 및 supervisor receipt는 로컬 전용이다.

```python
from orchestration.queue import Queue
from orchestration.vlm_command import RUNTIME, SETTINGS, input_contract

queue = Queue(RUNTIME)  # 기존 initialized canonical queue, migration 없음
queue.enqueue(
    job_key='BATCH-0001-EXP-0010-high-pixels',
    run_id='run_3d23462a014a', task_id='task_be6c4ddef130',
    dispatch_id='ctx_735ddbea9bba', owner='slot1_qwen_gpt-6.1-sol_high',
    command='vlm-batch01', input_value=input_contract('qwen_high_pixels'),
    config={'adapter': 'qwen_high_pixels', 'settings': SETTINGS}, timeout=900)
```

실제 실행은 `python -m orchestration.queue --runtime "$SCENEGUARD_QUEUE_RUNTIME" run-once` 한 번이다. 같은 job 재시도는 실행하지 않았고, 900초 timeout에 도달하지 않았다. 이후 다른 모델/개선 조건/예산 탐색을 시작하지 않았다.

## 실제 입력·환경·시간 결과

실제 로컬 환경은 Python3.10.12, torch2.5.1+cu124, CUDA12.4, Transformers4.57.1, numpy2.2.6, RTX3080이다. 기존 환경을 변경하지 않았다. BF16/SDPA/비양자화/cuda:0를 지정했으며 실제 모든 모델 parameter가 cuda:0에 있었다. 전체 패키지 목록은 로컬 summary에 있다.

각 클립의 원본 순서10프레임→**10×3×608×1120 RGB**, grid `[5,38,70]`, 시각3,325·전체3,588토큰이었다. resize1회·extra sampling0·temporal padding0이며, **source PTS/native PTS/time base/relative index/FPS/frame order를 각 클립의 EXP8 측정치와 직접 대조해 모두 일치**했다. 실제 resize RGB 배열·시트·확장 prompt·native PTS·token IDs는 로컬에 보존했다. 영상을 다시 추출하지 않았다.

실행 시각은2026-10-28 **09:09:45.815~09:10:10.513 UTC**(KST18:09:45.815~18:10:10.513)이다. queue claim→완료 **24.697621초**, 모델·processor 로드 및 CUDA동기화 **2.163436초**였다. 큐 경과에는 자산 재검증/시작/저장이 들어가며 대기는 빠진다. 생성은 generate+CUDA동기화이며 입력 시트 저장은 제외한다.

| 클립 | cache 읽기 s | 전처리 s | 생성 s | 출력 token | torch 할당 최고 GiB | torch 예약 최고 GiB | 엄격 파싱 | 펜스 제거 후 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 01 | 0.021971 | 0.118767 | 3.195967 | 73 | 4.661799 | 4.972656 | 실패 | 통과 |
| 02 | 0.005139 | 0.141662 | 3.268699 | 93 | 4.662646 | 4.972656 | 실패 | 통과 |
| 03 | 0.009264 | 0.117597 | 2.404217 | 68 | 4.662646 | 4.972656 | 실패 | 통과 |
| 04 | 0.013179 | 0.109749 | 3.103371 | 83 | 4.662646 | 4.972656 | 실패 | 통과 |
| 05 | 0.010010 | 0.119436 | 2.978451 | 96 | 4.662646 | 4.972656 | 실패 | 통과 |
| 06 | 0.016478 | 0.112916 | 2.563327 | 74 | 4.662646 | 4.972656 | 통과 | 통과 |

생성 합17.514032초·평균**2.919005초**, 범위2.404217~3.268699초다. EXP8 평균2.692196초 대비 약8.42% 증가했지만, 출력 길이/내용도 변했고 반복 측정이 아니므로 해상도의 독립적인 속도 효과나 온라인 처리 FPS로 일반화하지 않는다. 총 출력487토큰(EXP8:507),384토큰 상한0/6·OOM0/6이다.

실제 torch peak allocated **5,006,478,336 bytes**, reserved **5,339,348,992 bytes**였다. EXP8의4,662,626,816/4,844,421,120 bytes 대비 늘었다. 약0.5초 간격 전체 장치 polling41개·오류0개, 관측 최고**6,902MiB**였으며 다른 프로세스/화면 점유를 포함하고 순간 최고를 보장하지 않는다. 장치 전체 polling과 torch 프로세스 메모리는 별개 지표다.

엄격 공통 schema는**1/6**(06), 허용한 전체 펜스 제거 후**6/6**이었다. EXP8은2/6·6/6이므로 이번 결과에서 형식 개선도 확인되지 않았다. 응답 내부 JSON/enum/문장은 수정하지 않았다. 모델 로그의 torch_dtype deprecation·greedy에서 무시되는 기본 sampling flag 안내는 보존했다. 실행 오류는 없었다.

## 여섯 응답의 대조와 실패 해석

아래는 **기존 관찰 초안 대비 작업자 텍스트 검토**이며 새 사람 검수/실제 GT 정확도가 아니다. 원문과 generated token은 로컬 전용이다.

| 클립 | 기존 관찰 초안 및 EXP8 | EXP10 응답 요약 | 작업자 판단과 한계 |
| --- | --- | --- | --- |
| 01 | 접근·대기 초안. EXP8은 접근/대기를 설명하면서 완료 주장 | 보도에서 접근·대기를 설명하고 완료 주장, 유보 없음 | 행동 서술 일부 부합·완료 근거 부족 지속. 반대편 이동을 근거에 제시하지 않음 |
| 02 | 몸 올리기·겹친 사람, 개별 완료 미확정. EXP8은 열린 문·횡단보도 서술 | 문이 열리는 중 금속문을 넘어 왼쪽→오른쪽 이동했다고 설명하고 완료 주장 | 방향 이동 근거 서술은 새로 생겼으나 신체 상승 과정·개별 완료를 확인한 것은 아님. 문이 열린다는 서술과 실제 영상의 부합은 사람 확인 필요 |
| 03 | 먼 보행·비이벤트 후보 초안, 확정 음성 GT 아님. EXP8은 서 있음으로 설명하되 가림·완료 유보 | 서 있다고 설명하고 완료 주장, 유보 없음 | 초안의 보행과 부분 불일치, 기존 유보가 사라짐. 자기 근거에 반대편 이동도 없음 |
| 04 | 신체 상승 초안. EXP8은 서 있음·대기 중심 | 한 명은 멀어지고 다른 한 명은 서 있다고 설명, 완료 주장 | 상승/넘기 서술 부재 지속, 멀어짐이 반대편 통과 근거는 아님. 유보 없음 |
| 05 | 문 위쪽으로 신체 상승 초안. EXP8은 서 있음·대기 중심 | 서 있음·가방·자전거·열린 문·대기 설명, 완료 주장 | 상승/넘기 서술 부재 지속, 완료 근거 부족. 열린 문·소지품의 사실 여부는 새 검수하지 않음 |
| 06 | 거리·차량 가림·접촉의 사용자 대략 관찰, 완료 미확정. EXP8은 통행/contact와 완료 주장 | 울타리 근처 느린 보행·대기를 설명, contact 없음·완료 주장 | 접촉 표현이 사라졌으나 정확해졌다고 단정 불가. 가림·유보·완료 불확실성 처리 부족 지속 |

모든6개가 `crossing_completion=observed`, `uncertainties` 빈 문자열이었다. 그중01/03/04/05/06의 자기 근거 서술에는 반대편 이동 설명이 없다. **02는 왼쪽→오른쪽 이동을 명시**하므로 동일한 텍스트 근거 부재 사례로 세지 않는다. 그러나 이 이동/문 개방 서술이 실제 관측과 맞는지는 별도 사람 확인 전이다. 이 검토를 실제 완료 오탐5개/6개 같은 GT 통계로 표현하지 않는다.

기존02/04/05의 신체 상승·넘기 초안에 비춰04/05 누락 의심은 그대로다. 02는 표현이 달라졌으나 상승 동작을 더 잘 파악했다고 단정할 수 없다. 입력 픽셀이 늘면 행동 설명이 좋아질 수 있다는 가설을 지지하는 일관된 근거를 얻지 못했다. 입력 예산이 실패의 원인이 아니라는 역증명도 아니다. 프레임 간 시간 정보·가림·모델의 제한·관찰 초안 자체의 불확실성이 분리되지 않았다.

## 저장·전달·남은 결정

공개 [metrics](../../records/EXP-0010/metrics.json)는 값별 원천 상대 참조·JSON pointer·SHA256을 포함한다. 로컬 출력의 상대 위치는 `outputs/vlm_batch01/EXP-0010/c0fd8f0c63154c5d837d5c149bf948b5/`이며 공개 artifact URL이 아니다. summary·클립별 결과/원문/token IDs/확장 prompt/resize RGB/실제 입력 시트·GPU polling·작업자 분석을 보존했다. 전체 경로/크기/SHA256과6개 입력 시트 목록은 Git 제외 `runtime/qwen-high-pixels/worker-artifacts.json`에 있다. 원본5초 참고 영상은 EXP8과 같은 입력이며 시트는 실제 processor 입력이므로 별도 등록한다.

작업자 범위인 코드·CPU 회귀·승인된 단일 큐 실행·보고서·공개 측정값·로컬 manifest를 완료했다. 총괄은 별도 report/metrics SHA 검토, 독립 검토, completion 등록, GitHub 게시 및 실제 화면의 보고서/그래프/등록 미디어/검토 확인을 수행해야 한다. 작업자는 push·공유 문서/HANDOFF·completion 등록을 하지 않았으며, 해당 통합 문서 갱신도 총괄 소유다. 개선 채택은 보류하고 이번 배치의 추가 모델/개선 실험은 종료한다.
