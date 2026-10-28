# EXP-0011 — 고정 카메라 영역 입력 준비 완료·실제 행동 비교 자원 차단

- 날짜/담당: 2026-10-28, MVP 방법 담당 gpt-6.1-sol/high; 실효 배정은 총괄 세션 metadata 확인 기준.
- 상태: **CPU 구현·합성 검증·실제 입력 준비 완료. 실제 C 모델 비교는 resource_blocked / 미시작.** queue job/attempt 없음, 신규 생성0·실험 결과 재사용0. 입력 준비의 EXP8 동일성 증명을 실제 EXP11 생성/재사용 실행으로 세지 않는다.
- 관련: [MVP-0001](MVP-0001-plan.md), [ADR-0016](../decisions/ADR-0016-mvp-fixed-camera-region.md), [공개 측정 요약](../../records/EXP-0011/metrics.json).
- native Run `run_3d23462a014a`, Task `task_d32fef262394`, Dispatch `ctx_7aacfaf52678`.
- 준비 코드 커밋 `4d005f9`, 검토 보완 `1ec6281`; 실제 모델 실행 code SHA는 없음. CPU receipt는 해당 실행 당시 파일 SHA256을 따로 보존한다.

## 목적·자료·조건

기존 EXP8의 작은 사람 넘기 누락이 PTS0 정적 배경에서 정한 고정 감시 ROI 입력으로 줄어드는지 한 번 비교하려던 개발 대조다. B는 EXP8의6개 결과를 보존·재사용하며, 실행이 가능해질 때 C는5개 신규 생성과 C1 clip05 정확 재사용1개로 구분해야 한다. 이번에는 실제 생성에 도달하지 않았다.

자료는 AI-Hub71850의 기존 EXP7 RGB cache6개이며 원본·라벨·가중치·이전 출력을 수정하지 않았다. C3/C6/C7은 기존 정적 감시 ROI 그대로, C1은 전체 화면 fallback이다. C3의006 후기 보행은 영역 밖이어서 무경보라도 영역 안 정상 구분 성공으로 세지 않는다. 동일 카메라 중복과 정밀 사람별 GT 부재가 남으며, 모델 문장을 정답으로 쓰거나 accuracy/F1/시간당 오탐률을 산출하지 않는다. 원본 미디어의 재게시 권리는 새로 확정하지 않았다.

기존 로컬 `.venv-vlm`의 torch2.5.1+cu124/Transformers4.57.1과 Qwen3-VL-2B-Instruct pinned revision `89644892e4d85e24eaac8bacfd4f463576704203`를 사용했다. 이번 작업에서 모델은 구성하지 않았다. 예정 생성 조건은 기존 seed0/greedy/max384/rep1/BF16/SDPA/CUDA0/batch1이며 새 가중치·다운로드·설치·외부 추론 API가 없다. 공식 모델 카드의 Apache-2.0 및 영상/processor 지원 근거는 ADR-0016에 연결했다.

## 실제 CPU 입력 준비

총괄의 별도 CPU 입력 준비 승인 후6개 기존 cache를 공식 AutoProcessor로 처리했고 **CUDA uninitialized, 모델 구성0, 추론 호출0**을 확인했다. 모든 입력은 원본 uint8 RGB10프레임이며 원본 PTS/native PTS/순서를 보존했다. 실제 resized RGB와 입력 시트는 로컬에만 저장했고 픽셀을 클라우드 도구에 보내지 않았다.

| 클립 / 카메라 | 원본 crop xyxy | 실제 processor N,C,H,W | visual tokens | 전체 input tokens |
| --- | --- | --- | ---: | ---: |
| 01 / C3 | 1152,0,1728,648 | 10,3,608,544 | 1615 | 1878 |
| 02 / C6 | 537,216,1440,864 | 10,3,480,704 | 1650 | 1913 |
| 03 / C3 | 1152,0,1728,648 | 10,3,608,544 | 1615 | 1878 |
| 04 / C3 | 1152,0,1728,648 | 10,3,608,544 | 1615 | 1878 |
| 05 / C1 fallback | 0,0,1920,1080 | 10,3,448,768 | 1680 | 1943 |
| 06 / C7 | 825,0,1498,1080 | 10,3,736,448 | 1610 | 1873 |

모든 조건은 기존 총픽셀 예산3,584,000을 유지했다. 위 값은 **실제로 만든 입력량**이고 GPU 시간·행동 성능이 아니다. clip05는 저장된 EXP8 processor RGB·expanded text·native timing·모델/환경/생성 조건과 같았고, 별도 CPU 확인에서 input_ids/attention_mask/pixel_values_videos/video_grid_thw 모두 동등한 원래 adapter 경로와 정확히 같았다. 신규 답변 생성이나 실제 C job 실행은 없었다.

## CPU 검증과 재현

최종 소유 범위 및 통합 CPU 검증 **25개 통과,6.083초, skip0**. 기존 queue14개와 VLM 명령10개 회귀도 별도로 통과했다. `$MVP_PYTHON`은 기존 VLM 환경 interpreter를 가리키며, 통합 checkout에서 다음 명령을 사용한다. 담당 격리 checkout에서는 총괄의 pipeline 모듈을 임시 CPU 합성 harness에 연결해 같은 경계를 검증했다.

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$MVP_PYTHON" -m unittest discover -s tests_mvp -v
```

검사 범위는 baseline 전체 tensor/resize RGB 동일성, 원래 clip03 fractional FPS expanded token 동일성, 실제 디코딩 순번과 PTS 시간 좌표 분리, PTS gap·EOF0/1/odd, 정보 누출 방지, 고정 명령/설정/원본/모델/코드 해시, migration의 모든 과거 행/index/trigger/FK 보존, 살아 있는 상속 lease, 로드 전 자원 차단, job별1회 retry다. 실제 pipeline이 쓴 result의 성공 baseline 재사용 및 원문 바이트 변조 거부, decode 실패의 현재 token IDs 저장과 다음 prepare 실패의 이전 token 제거도 통과했다. 재사용의 새 생성 시간은 null, 기존 답변 길이와 신규 생성 토큰0은 별개다.

## 실패·종료·판단

첫 실제 cache 준비는01~04 이후 clip05의 엄격한 과거 코드 바이트 검사에서 멈췄다. EXP10이 `qwen.py`의 같은16384/3584000 literal 두 개를 class constant로 추출한 차이였다. 실패 receipt를 보존했고, 총괄이 허용한 한 번의 수정 준비에서만 재검증했다. 특정 과거 SHA `56388dfc…`/현재 SHA `94d0c64f…` 쌍과 정확한 constant 추출 AST diff를 고정해 증명하며, 다른 코드 차이를 일반적으로 허용하지 않는다. 생성 runner/parser/prompt·모델·환경·native timing 검사는 엄격하게 유지한다. 추가 C1 tensor 확인도 CPU 동일성 증명이며 모델 job 재시도나 새 실험 조건이 아니다.

총괄은 최신 자원 조회에서 GPU 여유가 동결 최소6,144MiB 미만이고 외부 GPU 작업이 계속됨을 확인해 이번 차단을 수락했다. 이는 총괄 관측이며 담당의 GPU 비용 실측값이 아니다. **enqueue·모델 로드·추론·다운로드를 하지 않았고 실제 비교·전체 영상 통합 실행·행동 성능 평가가 남았다.** 자동 재개·추가 개선·다음 모델 탐색을 시작하지 않는다.

담당 의견: 입력량·경계·재현성과 실패 보존은 확인했지만, ROI 확대가 넘기를 더 잘 이해하게 한다는 근거는 아직 없다. 영역 밖 행동과 주변 맥락을 잃을 수 있다. C 채택은 보류하며 BATCH-0001과 기존 CV/EXP6 판단을 유지한다. 총괄은 별도 검토·공유 HANDOFF·등록·게시·화면 확인을 담당하고, 이 보고서는 그 완료를 주장하지 않는다. 공개 숫자는 metrics의 상대 source/JSON pointer/SHA256으로 로컬 CPU receipt에 연결했다. 원문·NPY·입력 시트·실패 receipt는 Git 제외다.
