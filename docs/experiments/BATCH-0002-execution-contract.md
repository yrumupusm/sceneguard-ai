# BATCH-0002 — 실행 게이트와 역할 기록

2026-10-29 KST. 사용자 지침 `1a06f6c`를 깨끗한 로컬 `4401dfd` 위로 fast-forward했다. reset/강제 덮어쓰기/stash 없이 기존 결과를 보존했다. 승인 상한은 [원 계획](BATCH-0002-model-upgrade-plan.md)을 따른다. 이 문서는 모델 실행 결과가 아닌 구체 준비·중단 계약이다.

## 실제 역할과 공통 자원

기존 Run `run_3d23462a014a`와 기존 canonical GPU queue를 재사용한다. 설치된 authenticated Codex `thread/read`에서 현재 총괄 `gpt-6-astra / max`를 확인했다. native worker launch의 effective 필드는 두 담당 모두 `gpt-6.1-sol / high`다. 새 총괄/queue/중첩 작업자는 만들지 않는다.

| 역할 | Task / Dispatch | 소유 범위 |
| --- | --- | --- |
| 입력 감사, 후속 CV 준비 | task_806f089dde4f / ctx_f0c0eef8ed14 | 첫 단계 CPU 입력 감사; EXP-0018, 담당1 |
| VLM 후보 준비 | task_1c28910c950d / ctx_2061417a366a | 공식 출처·격리환경·호환성·실행계약 조사; 모델 실행 전 단계 |
| 독립 검토 | 별도 Astra high를 최종 근거가 준비될 때 배정 | 코드/해시/기록/해석 검토, 미디어 전송 없음 |

초기 RTX3080은 total 10240 / used 2278 / free 7776 MiB, utilization 2%였다. 이는 순간 관측이며 실행 가능성 보장이 아니다. 실제 GPU job마다 기존 최소 free 6144 MiB gate와 단일 queue lock을 다시 확인한다. 기존18개 jobs/18개 attempts가 보존되어 있다. raw receipt와 exact native/runtime 경로는 Git 제외 `runtime/BATCH-0002/`에만 둔다.

## 사전 실행 게이트

1. CPU 감사에서 q 6창의 B/C와 v 4창의 원본/수정 prompt 저장 입력(20 variants)을 대조한다. 사용자 원본창 라벨, 실제 sampled/downsized input 가시성, 저장 해시 일치를 서로 대신하지 않는다. 과거 q original processor RGB 미저장은 그대로 한계다. 새 모델/새 답변은 이 단계에 없다.
2. CV 원본 진단 프레임과 VLM 샘플 입력의 충분성을 따로 판단한다. 기존 사용자가 특정 원본 시각에 확인한 030 84/90초는 정확한 source/PTS가 매칭될 경우 native-frame CV 진단의 근거가 될 수 있다. 이것이 2fps 축소 입력에서도 동작을 구별할 수 있다는 보장은 아니다. 미확정은 불충분으로 확정하지도 않는다.
3. 모델 가중치·환경 설치·추론은 필요한 입력/출처 게이트와 구체 사전 manifest가 고정된 후에만 한다. CPU 코드/문서 준비는 병렬 가능하되 실제 실행 코드는 commit과 SHA로 고정한다. model family별 신규 checkpoint는 각1개 이내, 총2개 이내다.
4. CV는 최대240개 고유 원본 프레임 내에서 최소 smoke1–2개와 나머지를 중복 없이 처리한다. 같은 PTS의 FCOS cache 우선 재사용, 없을 때만 같은 고정FCOS 실행. 실제 위치/중복/배경 판단에 충분한 검수 없으면 candidate 수로 검출 향상을 확정하지 않는다.
5. VLM은 원본 prompt 고정, q 6창 B/C와 v 4창 full-frame의 **10개 고유 시간창/16개 view 조건**이다. 사전 smoke q04/q05는 구체 view를 freeze한 뒤 본 실행 분모에 포함하고 중복 생성하지 않는다. 실패 prompt를 다시 적용하거나 label을 inference에 넣지 않는다. 양자화/모델 크기 변화가 함께 있는 비교임을 기록한다.
6. 해당 단계에서 input/환경/여유자원/비교정확성 게이트가 막히면 원인을 기록하고 우회하지 않는다. job별 오류 retry≤1, silent CPU offload/프레임 삭제/해상도 하향/타 프로세스 종료 없음. 결과를 확인한 뒤 반복 튜닝하지 않는다.
7. CV의 실제 사람 복원과 VLM 실패에 대한 상호 보완 근거를 모두 확인한 경우에만 저장 출력 중심 offline PoC≤1. 조건이 미확정/불충족이면 결합을 생략한다. 추적기·기본CV/MVP·웹 기능은 자동 교체하지 않는다.

입력 가시성의 추가 사용자 확인이 꼭 필요하면 기존 행동 라벨을 되묻지 않고 actual input의 핵심 쟁점만 한 묶음으로 제시한다. 인간 확인이 필요한 구간을 모델 응답으로 정답화하거나 미디어를 클라우드 이미지 도구로 보내지 않는다. 최종 실제/미실행·비용·남은 실패·적용 여부는 배치 요약에서 정리하고 기존 등록·브라우저·GitHub 검증을 별도로 수행한다.
