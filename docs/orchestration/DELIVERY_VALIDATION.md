# 실험 배정·완료 등록·게시와 화면 확인

2026-10-28. 사용자 운영 지시를 [EXPERIMENT_DELIVERY](EXPERIMENT_DELIVERY.md)에 고정하고 재사용 명령을 구현했다. **새 CV/VLM 실험은 배정하거나 실행하지 않았다.** 실제 실험의 진행 카드부터 결과 화면까지 확인하는 것은 다음 승인된 실험의 필수 완료 조건으로 남는다.

## 구현과 실제 확인의 구분

| 항목 | 확인 결과 | 근거/범위 |
| --- | --- | --- |
| 코드 구현 | 완료 | 배정 등록, SHA에 연결된 완료 등록, 상태 카드, 게시/브라우저 별도 검사 |
| 자동 fixture | 통과 | Python 63개/6.554초, Node 카드·통신 실패와 원문 펼침 검사 |
| 실제 에이전트 작업 | 수행 | 아래 native Task/Dispatch 및 실제 세션 모델/effort |
| TEST 배정 상태 화면 | 실제 Orca 브라우저 확인 | 담당 2 진행 중, 실패, 관측 만료/ID 불일치 미확인, 완료 |
| TEST 완료 자료 화면 | 실제 Orca 브라우저 확인 | 보고서 펼침, metrics 표/그래프, 기존 EXP5 영상 재생/seek, 별도 검토 |
| 기존 결과 서비스 | 실제 확인 | `127.0.0.1:8765`의 EXP5 보고서·그래프·007/030 영상 두 개·총괄 검토 |
| 첫 실제 새 실험 | **미실행** | 공개 배정 목록은 비어 있고, 카탈로그는 기존 EXP-0001~0007만 포함 |
| GitHub 게시 | 별도 확인 완료 | 코드/운영 기록 12커밋, 원격 `5bca66b`와 각 source tree 일치, EXP5 원천/검토 파일 대조. [게시 이력](DELIVERY_PUBLICATION.md) |

화면 테스트는 로컬 DOM·표 값·해시·미디어 디코딩 상태를 조회했다. CCTV 픽셀/프레임/스크린샷을 클라우드 도구에 보내지 않았다. 영상 재생 성공은 행동 정답 검수나 새 모델 실험 성공을 뜻하지 않는다. 007/030 자료는 기존 비교 영상을 참조했으며 새 영상·추론·가중치는 만들지 않았다.

## 실제 역할과 통합

같은 Orca 1.4.240 Run `run_3d23462a014a`와 Astra max 총괄을 유지했다. 구현자는 서로 다른 worktree에서 소유 파일만 수정하고 총괄이 검토해 통합했다. 계정이나 유료 API 경로를 바꾸지 않았고 기존 CV/VLM 환경을 변경하지 않았다.

| 역할 | 실제 모델 / effort | native Task / Dispatch | 결과 |
| --- | --- | --- | --- |
| 총괄 | gpt-6-astra / max | 기존 Run 재사용 | 배정·검토·통합·브라우저/게시 확인 |
| 완료 등록 | gpt-6.1-sol / high | task_e8b245453626 / ctx_954f6ad7899f | 등록 CLI·24 fixture, 로컬 b29d7b2 |
| 담당 카드 | gpt-6.1-terra / high | task_c5a84d290224 / ctx_9bd0273b55a4 | 상태/보고서 연결·조회 테스트, 로컬 f9a1895 |
| 독립 검토 | gpt-6-astra / high | task_c57455ecf1f8 / ctx_2155bbec2e41 | needs_revision, F1~F4 발견, ff8216c |
| 좁은 재검토 | gpt-6-astra / high | task_178adb28e83c / ctx_13c04199fc39 | [F1~F4 해결](../reviews/DELIVERY-recheck.md), f059f5a |

Codex worker CLI는 0.165.0. 현재 총괄 세션의 생성 메타데이터는 0.164.0을 기록한다. `worker-start --terminal`의 launch 모델 필드는 null이므로 모델 자기소개/요청값 대신 metadata-only thread 조회와 실제 실행을 대조했다. normal automatic approval review와 workspace-write를 유지했다. 중첩 작업자나 총괄을 추가하지 않았다.

## 완료 절차와 오류 수정

`orchestration.complete assign`은 실제 배정을 담당 카드에 연결한다. `complete`는 별도로 작성된 보고서·숫자/출처가 있는 metrics·총괄 검토의 SHA·등록 미디어만 받아 catalog와 로컬 allowlist를 연결한다. 동일 요청 재실행은 `already_registered`이고 중복 결과를 만들지 않는다. 명령이 에이전트/모델/GPU 실행이나 GitHub push를 시작하지 않는다. [COMPLETE_CLI](COMPLETE_CLI.md)에 입력 계약과 예외가 있다.

초기 [독립 검토](../reviews/DELIVERY-independent-review.md)의 needs_revision 기록을 보존했다.

| 문제 | 수정과 검증 |
| --- | --- |
| F1: catalog 저장 실패 후 attempt만 바꾸면 다른 결과 등록 가능 | EXP ID 하나당 고정 binding 파일로 변경. catalog/config 실패 후 다른 attempt·내용 거부와 같은 요청 재시도를 검사 |
| F2: 같은 report/metrics에 다른 서비스의 검토가 붙어도 화면 통과 가능 | catalog 상태/native IDs/evidence, 실제 4개 원천 해시, 선택 DOM의 해시를 대조. 검사 후 로컬 snapshot과 서버 응답도 다시 확인 |
| F3: 목록 조회 실패 때 이전 카드 상태가 계속 표시 | 이전 목록은 유지하되 카드/선택 항목을 미확인으로 갱신. 실제 브라우저에서 두 조회를 실패시켜 영상 노드는 유지됨을 확인 |
| F4: 접힌 원문 textContent만 보고 report_opened 기록 | 실제 summary 클릭으로 펼치고 표시 높이를 확인. 열리지 않는 합성 DOM은 실패하도록 Node fixture 추가 |

화면 확인 자체의 실패도 보존했다. 통합 worktree의 새 탭은 생성 응답 뒤 `browser_tab_not_found`가 나왔고, 원인은 확정하지 않았다. 전체 Orca를 재시작하지 않고 `tab list --worktree all`에 실제 남아 있는 기존 실험실 탭을 재사용했다. `loadedmetadata` 직후 play는 0초에서 멈추는 사례가 있었고, 300ms 대기를 늘리는 것만으로 해결되지 않았다. 로컬 seek 후 play와 `preload=auto`+`loadeddata` 대기를 비교한 뒤 후자를 검사에 적용했다. 최종 검사는 최소 0.2초의 실제 재생 진행 후 seek를 확인한다. 원본 MP4나 코덱을 수정하지 않았다.

최종 구현 검토 기준은 `2d88656`, 준비 상태/지속 재생 보완은 `1f89f92`/`a639352`다. [재검토](../reviews/DELIVERY-recheck.md)는 F1~F4 해결과 두 보완 diff 검토를 기록했다. 테스트는 새 테스트용 임시 파일만 사용했고 기존 실험을 재실행하지 않았다. 최초 reviewer의 sandboxed 전체 fixture는 socket 제한으로 timeout했고, 허용된 같은 로컬 테스트 재실행 61개는 통과했다. 이를 실제 실험 실패나 모델 문제로 기록하지 않는다.

## 실제 브라우저 관측

격리 TEST 서버 8766의 `TEST-LIFECYCLE`은 합성 배정/측정/검토이며 실제 native 실험 작업이 아니다. 등록 전 카드 상태는 진행 중/작업자 실패/관측 만료·다른 dispatch의 미확인을 확인했다. 완료 명령의 첫 호출 `registered`, 동일 재시도 `already_registered`, status의 source/review current를 확인했으며 GitHub/browser 필드는 계속 unverified였다.

- 최종 TEST 확인: 원문 펼침·표 값 `1`과 그래프 1개·총괄 검토, 기존 비교 영상 1800×780/15.666667초. 실제 재생 0.223442초, seek 1.5초, decoded frames 53. 이후 16.5초 기다려 15초 주기 갱신이 영상 DOM을 교체하지 않는지 확인했다. 값 `1`은 합성 fixture이지 성능 지표가 아니다.
- 실제 서비스 EXP5 확인: 기존 metrics 13행(최종 행동 정확도는 미측정), 그래프 1개, 원문 펼침과 기존 검토. 007 영상 15.666667초/재생 0.200811초, 030 영상 14.666667초/재생 0.217622초, 각각 seek 1.5초와 디코딩 성공. 갱신 중 두 영상 노드 유지.
- 게시 후 main 서비스로 전환한 별도 확인(17:15 KST): 같은 원천/검토 4개 해시, 원문 펼침/그래프/검토, 007 재생 0.201070초와 030 재생 0.228892초, 각각 seek 1.5초. 브라우저 receipt는 GitHub 성공을 자동 주장하지 않는다. 실제 제공된 app.js SHA256은 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`다.
- 코드가 실행하는 카드 선택/원문 펼침/재생·seek 결과를 확인한 것이며, 영상의 사람 행동을 새로 의미 검수한 것은 아니다. 실험 간 지표를 범용 성능 순위로 비교하지 않았다.

로컬 증거: 통합 worktree의 `runtime/delivery/registration-lifecycle-receipts.json`, `browser-task-states-v3.json`, `browser-poll-failure.json`, `browser-lifecycle-accepted.json`, `browser-production-exp5.json`, `browser-published-main-exp5.json`, `github-production-exp5.json`, `publication-map.json`, `tests-review-fixes.log`, 모델 메타데이터 및 각 실패 receipt. 이 디렉터리는 Git 제외다. TEST 자료를 공개 `records/`에 옮기지 않는다. 수정 전 TEST의 attempt 포함 binding은 로컬 증거로 그대로 보존했으며 신규 등록 코드는 EXP별 고정 binding을 사용한다.

## 실행·중지·복구와 다음 실험

웹 주소: **http://127.0.0.1:8765/**. 최초 화면 검증은 `sceneguard-workflow`에서 수행했고, 게시 후 config의 `repo_root`를 **`/home/jhc7484/dev/sceneguard-ai`의 main**으로 바꾸어 소유 서비스만 재시작했다. 새 수집기의 connected 상태와 main의 실제 화면 확인이 통과했다. 환경과 공통 runtime은 기존 실험실 경로를 그대로 사용한다. 기존 LOCAL_SETUP_REPORT의 lab 코드 경로는 당시 이력이고, 현재 실행 코드는 이 경로다.

```sh
cd /home/jhc7484/dev/sceneguard-ai
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.lab --config /home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json status
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.lab --config /home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json stop
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.lab --config /home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json start
```

재시작은 status→소유 서비스 stop→start다. 웹 중지는 GPU 큐/Orca 작업자를 종료하지 않는다. 부분 시작 실패는 저장된 정확한 PID/boot/start-ticks로 소유권을 확인하고 stop으로 정리한다. 다른 프로세스/전체 runtime을 종료하지 않는다. 기존 config 원본은 로컬 `production-config-before.json`에 보존했다. 같은 공통 runtime에 `completion.lock`과 기존 GPU 큐를 유지하며 worktree별 큐를 만들지 않는다. 격리 TEST 서버 8766은 소유 PID 확인 후 중지했다. 배정한 작업자는 모두 완료 수락→release→정확한 idle 터미널 정리→ack를 마쳤고, reclaimable 조회는 빈 목록이다.

다음 실제 실험은 [CODEX_NEXT_TASK](../CODEX_NEXT_TASK.md) 순서대로 배정부터 화면 확인까지 수행한다. 새로운 가중치/실제 배치 실행 범위는 이번 운영 요청에 포함되지 않는다. 등록 CLI는 trusted coordinator용이며 역할 인증이나 자동 채택기가 아니다. 파일 검사·hash 연결은 검수의 의미적 정확성을 보장하지 않는다. 영상 부재/실패 시 해당 확인은 미완료로 표시한다.

## 보존과 공개 범위

기존 2,086파일의 size/mtime, 선택 430파일 SHA256, `.venv`와 `.venv-vlm` freeze가 모두 일치했다. 전체 대용량 미디어를 다시 해싱한 것은 아니다. 공식 라벨, EXP-0001~0007 원문, CV/추적/경계 코드와 실험 설정은 변경하지 않았다. 새 의존성/모델 설치도 없다.

게시 대상은 orchestration/webapp/tests_orca의 코드, 빈 배정 인덱스, ADR/운영 문서/검토 기록뿐이다. 로컬 영상·이미지·가중치·캐시·원시 결과·TEST fixture·DB·서비스 로그·receipt·config·인증정보는 제외한다. GitHub 게시와 실제 서비스 반영은 각각 검증하고 완료 메시지에서 구분한다.
