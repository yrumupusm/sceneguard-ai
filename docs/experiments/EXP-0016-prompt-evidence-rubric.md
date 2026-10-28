# EXP-0016 — Qwen 시간적 행동 근거 프롬프트 비교

- 날짜: 2026-10-28
- 상태: 비교 사양·코드·CPU 테스트 준비 완료; 실행 담당이 resource gate에서 중단해 GPU 추론/행동 비교 미실행. 코드와 최초 report/metrics 바인딩에 대한 Astra 검토는 완료했다. 새 사전검사 수치가 반영된 report/metrics의 Astra addendum, 로컬 결과 등록·화면 확인, GitHub 확인은 남았다.
- 담당: Orca Run `run_3d23462a014a`; 구현 `gpt-6.1-sol/high` Dispatch `ctx_d6e47aa9926b`, 독립 비교 구현 `gpt-6.1-sol/high` Dispatch `ctx_ac13ea840666`, 실행 사전검사 Task `task_305549d14771` / Dispatch `ctx_65256d02af82` (`gpt-6.1-sol/high`) 완료. 마지막 Dispatch의 `failed` 상태는 resource gate 차단이며 inference failure/OOM이 아니다.
- 결정: [ADR-0017](../decisions/ADR-0017-qwen-temporal-evidence-prompt.md)

## 가설과 목적

EXP-0015의 사용자 확인에서 접근/대기 q02·q05와 시도가 없는 q03에 후보가 있었고, 실제 시도/진행 q04는 C만 후보였다. q02 B는 걷기/차량을 말하면서 stepping 및 완료를 기록했고, q03 C와 q05 B/C는 사용자 관찰에 없는 stepping을 주장했다. q04 C는 climbing attempt를 말하고 완료는 확정하지 않았다.

원인은 현재 저장 결과만으로 확정할 수 없다. 이전 실행의 일부 입력 metadata는 확장된 원문 프롬프트를 보존하지 않아, 프롬프트 문구가 직접 원인이라는 설명은 **가설**이다. 비교 목적은 접근·대기/접촉과 신체를 올리거나 경계를 넘는 시도/진행의 구분을 개선할 수 있는지 확인하는 것이며, 출입 권한이나 법률 위반을 판단하지 않는다.

## 선택한 단일 변경

기존 Qwen3-VL-2B-Instruct, 가중치, BF16, greedy/max-new-token·배치 설정, 공식 processor, parser/postprocessor, 시간창, 입력 프레임, PTS, ROI/view를 유지한다. 한 축인 공통 prompt만 교체한다. 새 prompt는 프레임 순서상의 신체 움직임과 경계 상대 진행을 관찰 근거로 설명하게 하고, 접근·대기·단순 접촉만으로 시도라 하지 않으며, 문 개방·근접·횡단보도·타인 동작에서 추론하지 않게 한다. 완료는 같은 인물의 반대편 이동이 현재 창에 확인될 때만 기록한다. Schema는 그대로다.

비교 대안의 선택 이유와 채택 중단 조건은 [ADR-0017](../decisions/ADR-0017-qwen-temporal-evidence-prompt.md)에 기록했다. 특정 창/시간 예외는 코드에 넣지 않는다.

## 개발 회귀 세트와 고정 조건

EXP-0015 사용자가 확인한 여섯 5초 창을 고정 manifest에서 다시 사용한다. 라벨은 inference 코드/manifest에 포함하지 않는다. 각 prompt 조건은 full-frame B와 기존 고정 ROI C를 별도 실행한다. 과거 EXP-0013 B/C 원문 응답은 불변 기준이다. 새 모델 답이 나올 때까지 결과 칸은 미측정이다.

| ID | 원본/구간 | 사용자 확인 | EXP-0013 B / C | EXP-0016 새 prompt B / C | 변경이 겨냥하는 근거 | 남은 불확실성 |
|---|---|---|---|---|---|
| q01 | E01_007, 0–5 s | 시도 없음 | absent / absent | 미실행 / 미실행 | 차량/근접성에서 시도를 추론하지 않는 negative regression check | 시도 없음은 지정 5초에만 적용; 전체 장면 정답 아님 |
| q02 | E01_007, 47.5–52.5 s | 접근만, 시도 없음 | candidate / absent | 미실행 / 미실행 | B는 보도 보행·차량 근거와 stepping/completion이 불일치; ordered body-motion 요구가 이를 줄이는지 확인 | 원래 프롬프트 전체가 캐시 metadata에 없어 원인 귀속은 가설 |
| q03 | E01_007, 52.5–57.5 s | 시도 없음 | absent / candidate | 미실행 / 미실행 | C의 stepping 주장을 실제 신체 진행 근거와 분리해 보도록 함 | 가림/인물 겹침이 모델 시각 판단에 미친 정도 미확정 |
| q04 | E01_007, 62.5–67.5 s | 시도/진행 있음, 완전히 넘기 전 창 종료 | absent / candidate | 미실행 / 미실행 | 실제 시도 후보 유지가 falsifiable target; 완료는 관찰되지 않음 | B miss를 prompt-only로 해소할지, C 설명이 실제 장면에 맞는지는 출력 전 미측정 |
| q05 | E01_030, 50–55 s | 세 명 중 한 명 접근만, 시도 없음 | candidate / candidate | 미실행 / 미실행 | 양쪽 stepping 주장을 접근과 ordered body movement로 구분; 인접창 일관성만으로는 해결 근거가 약함 | 화면 내 사람별 행동과 가림의 세부 범위 미확정 |
| q06 | E01_030, 155–160 s | 사람/사건 없음 | absent / absent | 미실행 / 미실행 | no-person/no-event positive/negative guard | 확인은 E01_030 지정 5초에만 적용; E01_031 관찰을 전이하지 않음 |

목표 검사는 q04 candidate 유지, q02/q03/q05 candidate 감소, q01/q06 신규 candidate 없음이다. 모두 삭제·보류 또는 q04 소실은 개선이 아니다. 6개 개발 회귀창은 최종 일반화 테스트가 아니다.

### 추가 사용자 검수 창 — 별도 개발외 확인

기존 q01–q06과 분리해 사용자가 원본 전용 4개를 검수했다. v01은 E01_004 60–65초에서 시도/진행, completion은 답변되지 않아 미평가; v02는 E01_004 0–5초 비사건; v03은 E01_021 65–70초에서 시도/진행이나 문 자체가 아니라 옆 빈틈이고 정확한 경계 위치 관계는 애매함, completion은 미평가; v04는 E01_021 0–5초 비사건이다. 검수 단위는 해당 5초뿐이다. 다른 인접창의 정답이나 영상 전체 라벨로 확장하지 않는다.

이 네 창에는 기존 calibrated camera ROI가 없으므로 full-frame만 prompt A/B 대조에 쓴다. v01/v02는 같은 E01_004 영상·카메라이고 v03/v04는 같은 E01_021 영상·카메라라 표본 그룹은 네 개가 아니라 두 개다. 원본 시각 PTS 30fps에서 지정한 다섯 초만 자른 미디어와 원본 파일은 ignored local outputs/data에만 있다. inference는 익명 창 ID와 해당 프레임만 보며 사용자 라벨, 공식 event time/annotation, 영상 파일명, 이전 답변은 전달하지 않는다. 이는 분리된 검수 창 비교이지 camera/site-independent blind test가 아니다. 긍정 2/음성 2의 극소 purposive set이며 정량 성능을 주장하지 않는다.

## 구현·재현

- phase: 기존 `mvp-0001`의 canonical shared GPU queue 내 `prompt-regression`; 같은 Run과 batch-1 model lease를 사용한다.
- model: 기존 Qwen3-VL-2B-Instruct, pinned Hugging Face revision `89644892e4d85e24eaac8bacfd4f463576704203`, 로컬 `model.safetensors` SHA-256 `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`; EXP-0008에서 기록한 Apache-2.0 모델 카드/기존 BF16 CUDA 0 환경을 재사용하고 새 가중치를 받지 않는다. 전체 package/runtime 정보는 [EXP-0008](EXP-0008-qwen-batch01.md).
- unchanged generation: batch 1, BF16, SDPA/CUDA0, greedy (`do_sample=false`), `max_new_tokens=384`, repetition penalty 1.0; existing Qwen processor shortest-edge 16384 / longest-edge 3584000.
- q 입력: 원본 007/030 전체를 기존 PTS decoder로 처리해 여섯 frozen windows만 선택, 각 window 10개 real frame at 2 fps. B full frame / C 기존 ROI.
- 독립 입력: E01_004/E01_021에서 고정한 네 5초 원본 구간, full frame only; 기존 prompt 및 revised prompt.
- 로컬 runtime 산출물, 입력/코드/model/prompt hash, raw response와 처리량은 Git에 올리지 않는다. 화면 evidence는 original-only local preview를 사용하고 web artifact로 올릴 수 없다.
- 구현 phase는 자원 확인 전 모델 라이브러리를 import하지 않고, 변경 코드·설정 해시와 새 EXP-0016 output directory를 pin한다. 기존 EXP-0013/14/15 출력·라벨은 보존한다.
- 재현 명령은 코드를 고정한 뒤 보고서에 실제 명령과 queue attempt를 추가한다. 현재는 GPU queue job을 enqueue/run하지 않았다.

## 실행·비용·결과

2026-10-28 14:36 UTC 실행 담당 사전검사에서 RTX 3080 10 GB는 8464 MiB used, 1590 MiB free, 99% utilization이었다. 실행 코드는 commit `5d4a8af0f83975f430922fcda03c0aef5a34734a`에 고정했다. 기존 settings의 6144 MiB free-memory gate 미달로 담당자는 즉시 중단했다. 기존 canonical queue의 읽기 전용 집계에서 EXP-0016 job 0, attempt 0을 확인했다. 네 실행 그룹(revised q full-frame, revised q fixed-ROI, original v full-frame, revised v full-frame)은 전부 미실행이며, model import/load 및 enqueue도 없었다. queue 우회, gate 조정, process 종료 또는 resource retry는 하지 않았다. latency, generation time, peak VRAM, output/parse status는 **측정 불가**이며 0으로 채우지 않는다.

| 측정 | 기준 | 변경 prompt | 상태 |
|---|---:|---:|---|
| q01–q06 candidate / user no-attempt match | 기존 EXP-0013 record | 미측정 | GPU block |
| independent v01–v04 action/completion | 기준 inference pending | revised inference pending | GPU block |
| load/generation wall time | existing Qwen baseline receipt | 미측정 | GPU block |
| peak GPU memory | existing measurement required | 미측정 | GPU block |
| generation failures/retries | historical data only | 0 attempts made | no inference |

## 테스트와 검토

새 prompt phase 12개와 independent comparison phase 15개를 포함해 프로젝트 `.venv-vlm`에서 전체 `tests_mvp` 107 tests가 통과했다. 기존 shared queue `.venv-orca-lab` suite 14 tests도 통과했다. 모델-free input 검증은 원본 두 파일 hash, 네 고정 window의 frame-index/native PTS/RGB hash 40개를 확인했다. `git diff --check` 통과. 최초 system-python 실행은 PyAV 미설치로 decoder test 3개를 skip했으나 프로젝트 VLM 환경에서 모두 재실행 통과했다. 한 번의 전체 queue 테스트 중 attempt order assertion이 실패했으나 해당 테스트 단독 및 이후 전체 재실행은 통과했다; 테스트 순서의 일시적 변동으로 남긴다.

독립 Astra review, 최종 report/metrics binding, 결과 등록, 기존 페이지의 실제 반영, GitHub push 확인은 아직 없다. 행동 성능 개선은 미측정이라 채택/기각 결론을 낼 수 없다. 최종 자동 적용은 하지 않는다.

## 남은 한계와 다음 결정

- GPU free memory가 ≥6144 MiB가 된 뒤에만 동일 코드·manifest·prompt·model 설정으로 네 job을 순차 실행한다. 시스템 프로세스를 종료하거나 threshold를 변경하지 않는다.
- prompt change가 q02/q03/q05를 줄이고 q04를 보존하지 못하면 채택 보류다. 모든 출력을 indeterminate로 바꿔 감소한 candidate를 성공으로 계산하지 않는다.
- v03의 위치는 gate 자체를 통과한 행위가 아니라 옆 빈틈에서의 시도라는 사용자 설명을 유지한다. 행동 종류와 boundary association은 별도다.
- development q와 4개 추가 검수 창만으로 최종 accuracy/F1/FPR, camera/site generalization, real-time suitability는 산출하지 않는다.
