# EXP-0033 — 저장된 CV 후보 → Qwen3-VL 행동 검토 3장면 실험

2026-10-30 사용자가 승인한 최신 한 차례 실험. **코드는 준비됐으나 실제 로컬 GPU 추론·장면별 결과·웹 전달은 아직 수행되지 않았다.** 이번 목적은 '이미 존재하는 CV 후보의 주변 원본 영상을 기존 Qwen이 재판독하면 월장 시도/단순 접근을 구분하는 데 도움이 되는가'를 확인하는 것이다. 결과가 부정적이면 자동 판정에 적용하지 않는다.

## 범위 확정

| 분석 | 원본 PTS | 출처 | 행동 관찰 참고 |
|---|---|---|---|
| 030 후보 | 85~95초 | 기존 gap 선 후보 raw3, output 90.4초 | 약 90초 몸 올림; 사람별 완료 미확정 |
| 007 후보 | 64~74초 | 기존 gap 선 후보 raw8, output 70.133333초 | 약 66초부터 월장 시도·진행 |
| 007 정상 대조 | 52.5~57.5초 | **CV 후보가 아니다.** 모델 비교용 독립 대조 | 사용자가 q03에서 시도 없음 확인 |

- 새 FCOS 검출·ByteTrack·ReID·특징 추출·학습·모델 다운로드는 0회. EXP-0029/0030/0031과 사용자가 수정한 현행 polygon·ROI는 그대로 보존.
- CV 후보의 원래 이벤트/ID/time/source SHA를 CPU 선행 검증한다. 모델 입력은 **원본 RGB 프레임, native PTS, 익명 창 번호, 고정 ROI, 셋 모두 같은 질문**이다. CV 경보값/원래 이벤트 시각/영상 이름/사용자 정답/기존 VLM 답변을 Qwen의 텍스트 프롬프트로 전달하지 않는다.
- 10초 원본에는 실측 10장(약1fps), 5초 정상 대조에는 10장(약2fps)을 동일 시간순으로 전달한다. 샘플은 원래 native PTS에 대응하는 실제 원본 프레임만 사용하며 가상 프레임으로 채우지 않는다. 이는 **시간 맥락과 샘플링 밀도를 함께 바꾸는 작은 파일럿**이다. 이전 5초/2fps 대비 어떤 요소가 인과적 개선인지는 분리할 수 없다.
- 기존 Qwen3-VL-2B-Instruct **핀 고정 모델**과 원래 FP32 전처리/모델 BF16 생성 정책, 384 출력 토큰, 고정 C3/C6 카메라 ROI를 재사용한다. 기존 파서로 5개 행동 상태와 완료 주장의 불확실성을 기록한다.
- 모델 결과를 자동 확정된 침입·정체·완료로 표시하지 않는다. '월장 가능' 여부는 **모델 주장**이며 실제 시연에서는 검토 단계다.

## GitHub에 구현된 경로

- 입력: `configs/exp0033_cv_vlm_manifest.json`; 모델 프롬프트: `configs/exp0033_cv_vlm_prompt.txt`; **추론 완료 후에만 사용하는 사람 관찰 대조**: `configs/exp0033_review_reference.json`.
- 핵심: `mvp/candidate_vlm.py`; 합성 계약 테스트: `tests_mvp/test_candidate_vlm.py`.
- 공통 큐 연동: `orchestration/mvp_command.py`에 `phase=candidate-vlm` 추가, `mvp/method.py`에서 동일 고정 prompt 사용, `mvp/runner.py`에서 세 장면만 실행. 기존 `mvp-0001` 큐 명령·lease·resource gate 사용한다. **새 GPU queue/DB migration 불필요**.
- 모델은 `mvp/runner.py`의 기존 코드가 정상적인 Orca task/dispatch와 공통 GPU 잠금 확인을 거친 뒤에만 생성한다. 정답 파일은 source hash/input contract에 넣지 않는다.
- 새 결과는 기존 `outputs/mvp0001/EXP-0033/<attempt>/` 아래에만 생성. `candidate_vlm_results.json`, 모델 입력 근거, 원본 MP4 3개, `index.html`을 만든다. `posthoc-reference-review.json`은 완전한 결과 이후 CPU에서 추가한다.

## 로컬 Codex에 줄 실행 작업

1. 로컬 파일 변경·기존 결과 보호 및 최신 main 동기화. 먼저 세 원본 장면이 기존 입력/원본 CV 후보에 맞는지 `python -m mvp.candidate_vlm preflight`로 확인한다. **여기서 실패하면 원본을 임의 조작하지 말고 경로/원본 버전 오류만 수정한다.**
2. 기존 `.venv-vlm` 환경에서 `tests_mvp/test_candidate_vlm.py`와 기존 MVP 등록/큐 회귀 테스트를 실행한다. source/config/weights 해시, 기존 jobs/attempts 행, 사용자가 수정한 regions JSON의 SHA를 실행 전 freeze한다. 불일치가 생기면 모델을 로드하지 않는다.
3. 기존 Orca Run의 실행 가능한 Task/Dispatch와 Sol high 실행 담당·Astra high 독립 검토를 활용한다. 새 총괄/큐를 만들지 않는다. **사전 검토가 끝난 후** 기존 canonical GPU 큐의 `mvp-0001` 명령을 다음 config로 단 한 번 등록한다. 실제 Run/Task/Dispatch ID는 로컬에서 조회한 값만 사용하고, 예시·가짜 ID를 넣지 않는다.

       from orchestration.queue import Queue
       from orchestration.vlm_command import SETTINGS, RUNTIME
       from orchestration.mvp_command import input_contract
       config = {"phase":"candidate-vlm", "view":"fixed_roi", "settings":SETTINGS}
       inputs = input_contract("candidate-vlm")
       q = Queue(RUNTIME)
       q.enqueue(job_key="exp0033-fixed-three-vlm", command="mvp-0001",
                 input_value=inputs, config=config,
                 run_id=ACTUAL_RUN_ID, task_id=ACTUAL_TASK_ID,
                 dispatch_id=ACTUAL_DISPATCH_ID, owner=ACTUAL_OWNER,
                 timeout=1200)
       # 기존 orchestrator/queue supervisor로 승인된 job 1회 실행

   반드시 기존 queue를 사용한다. 위 변수들은 placeholder며 실제 배정 ID로 채워야 한다. 별도로 `QwenAnalyzer()`를 직접 호출해 GPU lease를 우회하지 않는다.
4. 실행 결과 `outputs/mvp0001/EXP-0033/<attempt>/`의 `summary.json` 성공·세 창 3개 모델 출력·원본 clip/원시 프레임 수·메모리·native PTS를 확인한다. GPU 오류/OOM이 나면 성공으로 보고하지 않는다. 재시도·임계값/질문 변경 자동 반복 금지.
5. 생성이 완료된 경우 **별도 CPU 프로세스**에서 다음을 실행해 사용자 관찰 참고를 연결한다. Qwen 추론 시 정답이 입력되지 않았는지 대조한다.

       .venv-vlm/bin/python -m mvp.candidate_vlm review \
         --results outputs/mvp0001/EXP-0033/<attempt>/candidate_vlm_results.json \
         --output outputs/mvp0001/EXP-0033/<attempt>/posthoc-reference-review.json

6. 사람이 원본 MP4 3개를 함께 보면서 세 가지를 판정: **030과 007의 실제 몸/다리 올림을 VLM이 적절히 언급하는가? 007 52.5~57.5초를 월장으로 잘못 단정하는가? 확인되지 않은 완료를 확정하는가?** 모델 출력의 생성 완료와 행동 판별 정확도는 별개다.
7. 결과 문서 `docs/experiments/EXP-0033-results.md`와 독립 검토 및 등록/전달 로그는 **실제 로컬 결과가 확인된 후에만** 새로 게시한다. 기존 담당3 뷰어에 EXP-0033 결과와 원본 clip·비식별 상태를 등록하고 실제 play/seek/선택 확인한다. 원본 CCTV·개인 크롭·원시 프레임·raw model answer/weights/권한정보는 Git에 넣지 않는다. 새 웹 UI를 대규모로 만들지 않는다.

## 결정 기준

- **두 월장 후보 구간에서 몸 올림 동작을 실제 근거와 일치하게 구분하고 정상 대조는 넘기 아니라고 판단**한다면, 기존 EXP-0030 검토 화면에 VLM의 *추가 의견*을 보여주는 제한적 MVP 도입 후보로 검토한다. 이 3개의 개발 사례로 일반 CCTV precision/recall/F1을 주장하지 않는다.
- 정상 대조를 월장으로 오판하거나 두 월장 장면을 놓치거나 없는 완료를 창작하면 **VLM 자동 판정 채택을 보류**한다. 모델 학습·다른 VLM·프롬프트 sweep·CV threshold 탐색·영역 변경은 자동 시작하지 않는다.
- CV가 아예 후보를 내지 않은 장면에서는 이 2단계 구조가 VLM 호출을 시작하지 못한다. 전체 사건 recall 개선이라고 주장하지 않는다.
- EXP-0033을 결과 없이 완료라고 하지 않는다. 실패하더라도 기존 EXP-0030 사건 후보·근거 영상 MVP는 보존한다.
