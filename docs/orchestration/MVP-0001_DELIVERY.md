# MVP-0001 전달 — CPU 준비 완료, 실제 모델 실행 차단

2026-10-28. [종합 결과](../experiments/MVP-0001-summary.md)를 먼저 읽는다. **MVP 미완료**이며 코드 구현·실제 모델 실행·결과 등록·GitHub 게시·실제 서비스 확인을 구분한다. 웹 코드/디자인/새 기능은 변경하지 않았다.

## 배정과 범위 종료

기존 Run `run_3d23462a014a`와 Astra max 총괄 하나를 유지했다. 방법 담당 Sol high는 Task `task_d32fef262394` / Dispatch `ctx_7aacfaf52678`, 통합 담당 Sol high는 `task_c466b62bf289` / `ctx_63a22ac17659`, 별도 검토 Astra high는 `task_903274b61857` / `ctx_8512d0d66d37`다. 실제 session metadata와 native receipt를 확인했으며 모델 정책/자기소개만으로 배정을 주장하지 않는다. 새 총괄·큐·가중치·환경·웹 기능은 없다.

초기 worker 실행 명령에서 approve-for-me와 workspace-write sandbox 옵션을 함께 넣어 CLI가 충돌로 종료했다. 실제 terminal/process 상태와 미생성 Task를 확인한 뒤 중복 sandbox 옵션만 제거해 같은 terminal에서 한 번 복구했다. 보호 설정/인증정보/Orca runtime을 우회하거나 reset하지 않았다. 이는 모델 추론 retry가 아니다.

계획·카메라·평가·실제 배정은 `9482dc9`에 먼저 게시했다.10:43:25UTC 실제 브라우저의 담당1/2에서 EXP11/12 각각 진행 중·실효 Sol/high·결과 미등록을 확인했다. 이 카드는 agent 작업 상태이며 GPU 실행 상태와 동일하지 않다.

모델 담당과 통합 담당은 code/CPU 작업을 마쳤지만 실제 모델 목표를 실행하지 못해 총괄이 자원 차단을 수락하고 native worker_done failed로 종료했다. 실패를 모델 OOM/행동 성능 저하로 해석하지 않는다. worker-release는 existing external terminal에 대해 retained/processAction none을 반환했으며 임의 terminal 종료나 다른 프로세스 종료는 하지 않았다. 대기 GPU job은 남기지 않는다.

## 실행·검토·등록

- 원본3개 CPU decode/window:12,754프레임·853고유표본·172창·모두EOF,030 마지막 창1표본. 실제 모델 분석/후보/근거 생성 성공은 아니다.
- 기존6클립 CPU official processor 준비와 C1 정확 동등성을 확인했다. 새로운 모델 generation·실제 결과 재사용 실행·GPU job/attempt 각각0이다. 모델 로딩/생성/VRAM/행동 지표는 null이다.
- 최종 GPU durable 관측10:56:18UTC는 total10,240/used8,248/free1,806MiB/util99%, 고정 최소 free6,144MiB 미달이다. 외부 Windows GPU 작업을 확인하고 사용자에게 필요한 정리를 안내했다.
- [독립 검토](../reviews/MVP-0001-independent-review.md)는 draft 결함/수정/고정 소스 CPU 검사, 원천 hash와 public metrics를 분리해 기록한다. 총괄 [EXP11 검토](../reviews/EXP-0011-coordinator-review.md), [EXP12 검토](../reviews/EXP-0012-coordinator-review.md)는 각각 exact 보고서/측정치 SHA256에 결합했다.
- 기존 complete 명령으로 EXP11/12를 **inconclusive / blocked / adoption_on_hold**로 등록했다. `mvp0001-resource-blocked-no-gpu-attempt`는 미실행 전달 ID이며 실제 GPU attempt가 아니다. 등록 binding은 불변이며 후속 실제 모델 결과는 새 ID로 전달해야 한다. 과거10개 catalog 행은 그대로 보존했다.
- 원본/입력 참고 자료만 연결했다. EXP11은007/030 기존 원본·표본 영상2개와 새 CPU 입력 시트2개, EXP12는 같은 기존 원본 참고 영상2개다. 새 C/B 행동 비교 영상이나 새 MVP 이벤트 영상으로 표시하지 않는다.

## 보존과 남은 확인

CPU 준비 후 기존2,235개 파일의 size/mtime,565개 SHA256 및 두 기존 환경 freeze가 일치했다. 새 입력 준비 산출물만 로컬 제외 경로에 저장했다. canonical DB의 기존11job/11attempt 전 행은 primary key로 대조해 동일했고 새 MVP migration/등록/실행은 없었다. 최초 SQL 비정렬 비교가 다름을 반환한 검증 receipt도 보존하고 primary-key 비교로 바로잡았다. 과거 실행 코드·공식 라벨·원본·가중치·원시 출력은 덮어쓰지 않았다.

공개 대상은 code/config/tests/ADR/report/공개 숫자/검토/binding/catalog뿐이다. 미디어·NPY·가중치·raw response·입력 원문·runtime DB/log/receipt와 인증 관련 자료는 제외했다. GitHub 게시와 실제 main 서비스/브라우저 확인은 아래 후속 관측으로 별도 기록하며 등록 사실만으로 완료 처리하지 않는다.

현재 후속 게시·브라우저 관측은 준비 중이다. 실제 receipt가 생성되면 이 문단을 갱신한다. 자동 실행·새 실험·대시보드 작업을 시작하지 않는다.
