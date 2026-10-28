# SceneGuard Orca 로컬 세팅 검증 보고서

후속 상태: 첫 실제 모델 배치 EXP-0008~0010을 같은 실험실에서 실행했다. 최신 역할/큐/실험 전달 확인은 [BATCH-0001_DELIVERY](BATCH-0001_DELIVERY.md), 행동 비교는 [배치 보고서](../experiments/BATCH-0001-vlm-comparison.md)를 따른다. 아래의 “새 실험 미실행”은 최초 세팅 당시의 보존된 기록이다.

검증일: 2026-10-28 KST. **승인된 로컬 세팅과 기능 검증 완료. 독립 검토 R1~R4 수정·재검토 완료.** 새 CV/VLM 비교 실험은 실행하지 않았다. 웹 주소는 **http://127.0.0.1:8765/** 이다.

## 시작 상태와 보존

시작 시 main과 작업 디렉토리가 깨끗한지 확인한 뒤 origin/main을 fetch하고 `83ce1b56ba4d9e73bae5f1c48856d73a4c371d83`까지 fast-forward했다. reset·강제 덮어쓰기·stash를 사용하지 않았다. 통합은 `setup/orca-lab`, 구현·화면·검토는 각각 독립 worktree에서 진행했다.

기존 `.venv`/`.venv-vlm`을 쓰거나 갱신하지 않고 Python 3.10.12의 `.venv-orca-lab`을 만들었다. FastAPI 0.162.0, Uvicorn 0.54.0, markdown-it-py 4.2.0 등 정확한 20개 버전은 `requirements-orca-lab-lock.txt`에 고정했다. 새 CV/VLM 가중치 다운로드·추론·학습은 없었다.

마지막 보존 검사는 **2,086개 파일의 크기/mtime, 그중 430개 작은 메타데이터·보고서 등의 SHA256, 두 기존 환경의 package freeze가 모두 일치**했다. 전체 영상/가중치 바이트를 다시 해싱했다고 주장하지 않는다. 기존 공식 라벨·실험 보고서·CV/추적/경계 코드 변경은 없다. 대조 원본과 결과는 로컬 `runtime/orca-lab/preservation-before.json`, `preservation-final.json`이다.

## 실제 환경과 모델 배정

- Windows Orca **1.4.240**, WSL **Ubuntu-22.04**, Linux **6.6.87.2**. 선택 CLI는 `orca-ide`; GNOME의 `/usr/bin/orca`를 사용하지 않았다.
- 설치 Codex는 사용자 업데이트 후 **0.165.0**. 현재 총괄 thread의 생성 메타데이터에는 이전 **0.164.0**이 남아 있으며 현재 설치 버전과 구분했다.
- 기존 ChatGPT 로그인 컨텍스트를 재사용했다. API key 발급·유료 API 전환·계정 변경 없음. 에이전트 호출은 현재 계정의 사용량을 사용한다.
- 사전 GPU 조회: **RTX 3080, 10,240 MiB 중 1,745 MiB 사용**. 이는 조회 당시 장치 상태이며 이 세팅의 GPU 성능 측정이 아니다.

| 역할 | 요청 | 실제 확인 | 근거와 결과 |
| --- | --- | --- | --- |
| 총괄 1명 | gpt-6-astra / max | 동일 | 기존 thread 메타데이터 + 현재 도구 실행, 새 총괄 없음 |
| 실행기 구현 | gpt-6.1-sol / high | 동일 | Codex thread 메타데이터 + Orca provider/도구 실행 + 큐 구현·14개 테스트 완료 |
| 화면 구현 | gpt-6.1-terra / high | 동일 | 동일 유형의 근거 + 화면 구현·초기 테스트 완료 |
| 독립 검토 | gpt-6-astra / high | 동일 | 별도 thread + 실제 읽기/검사 + 최초/수정 후/최종 검토 완료; 각 실제 thread에서 같은 배정 확인 |
| 향후 담당 1·2·3 | gpt-6.1-sol / high 예정 | **미배정** | 세 모델 실험을 실행한 것이 아님 |

설치 스키마의 authenticated `model/list`와 metadata-only `thread/read`/`thread/list`를 사용했다. 목록 노출만으로 호출 성공으로 세지 않았다. 선택한 `worker-start --terminal` 경로의 launch.requested/effective는 null이므로 그것을 모델 증거로 쓰지 않았다. 모델의 자기소개도 근거가 아니다. 비밀 없는 실제 thread/CLI 관측은 로컬 `worker-metadata/`, `reviewer-metadata/`, `final-capabilities/`와 Orca receipt에 남겼다.

목록에는 ultra도 있지만 자동 task delegation 성격이므로 중첩 fanout 금지와 정책의 max 우선순위를 따라 **Astra max**를 유지했다. 따라서 모든 모드 중 가장 높은 이름을 사용했다고 표현하지 않는다. 현재 계정 목록에는 별도의 Astra Pro ID가 반환되지 않았으며 임의 ID나 무음 대체를 쓰지 않았다. 이 결과는 해당 시점 계정/버전에서의 관측이다.

## Orca 연결과 작업 결과

하나의 native Run **`run_3d23462a014a`**를 사용했다. 사용자 재시작 후 기존 총괄 terminal의 operator_close를 확인하고 같은 Run의 coordinator binding만 회복했다. 새 Run이나 두 번째 총괄, Codex 내장 하위 에이전트를 만들지 않았다.

| Task | 결과 | 근거 |
| --- | --- | --- |
| `task_0260be022067` 실행기 | 완료 | 성공 Dispatch `ctx_999991dd888d`, worker commit `7719e417` |
| `task_26414da24d11` 화면 | 완료 | 성공 Dispatch `ctx_43f7fb7e2369`, worker commit `7753d482` |
| `task_04b30e2b4072` 최초 독립 검토 | 검토 완료·수정 필요 판정 | `ctx_de43aa938f48`, [최초 검토](../reviews/ORCA-SETUP-independent-review.md), worker commit `21faaccd` |
| `task_fe187221831e` 수정 후 독립 검토 | R1~3 해결 확인·R4 수정 필요 | `ctx_122e03a75ad2`, [재검토](../reviews/ORCA-SETUP-recheck.md), worker commit `0da4064b` |
| `task_715d3de8b377` R4 최종 독립 검토 | R4 해결·해당 범위 수락 | `ctx_93637ad8e5d9`, [최종 검토](../reviews/ORCA-SETUP-final-review.md), worker commit `d649d93f` |
| `task_8f5422de0169` 총괄 로컬 검증 | native Task 완료 | CPU 큐·웹·미디어·보존 검사; AI worker Dispatch를 위조하지 않음 |

native 완료 메시지의 Task/Dispatch를 대조하고 수락한 다음 release, delivery ack 순서로 처리했다. 직접 생성한 terminal은 release가 `external_terminal / retained / processAction none`을 반환하므로, 완료·idle·소유권을 확인해 해당 terminal만 닫았다. 세팅 worker는 모두 정리됐고 담당 슬롯은 미배정이다. 불명확한 release를 강제 종료로 대체하지 않았다. 원래 총괄과 사용자 터미널은 종료하지 않았다.

## 구현과 실제 검증

| 항목 | 실제 확인 | 한계 |
| --- | --- | --- |
| 공통 실행 대기열 | SQLite 원자적 claim + 공유 flock + 자식에게 잠금 FD 상속 | 협력하는 단일 호스트 큐이며 머신 전체 GPU 접근 제어가 아님 |
| 서로 다른 worktree | lab/infra에서 같은 절대 runtime을 사용한 두 run-once의 실행 구간 중첩 0 | 현재 등록 명령은 CPU mock 하나뿐 |
| 실패 복구 | 성공/성공/의도적 exit 7 실패/다음 성공; 완료 키 재등록·재시작 추가 실행 0 | 실제 모델 장애는 시험하지 않음 |
| 프로세스 장애 | fixture로 caller/supervisor 사망, 잠금 유지, timeout/cancel, PID 재사용·unknown, 한 번의 명시적 retry 검사 | supervisor 사망 중 timeout/heartbeat 강제는 중단됨; bounded mock만 허용 |
| 웹 독립성 | 실행 중 mock을 둔 채 웹/수집기 종료 후 mock 성공, 서비스 재시작 성공 | 웹 stop은 큐/Orca worker stop이 아님 |
| 읽기만 하는 화면 | 조회 3회로 queue attempt 증가 0, POST 거부, loopback·Host/CSP 제약 | 공개 서비스나 인증된 다중 사용자 서비스가 아님 |
| 실제 보고서 | EXP-0001~0007 클릭·원문 표·미측정 표기, 총괄→담당 1·2·3/미배정→상세 구조 확인 | 과거 모델/effort 미기록은 null, 담당 슬롯 실험은 아직 없음 |
| 실제 로컬 미디어 | EXP5/6의 4개 영상 모두 decode/play/1.5초 seek 성공, media error null | 새 행동 정답 검수나 영상 의미 확인을 완료했다는 뜻 아님 |
| 실제 로컬 이미지 | EXP7 검수 시트 6개 모두 decode, 각 1536×2390 | 브라우저 내부 decode 확인만; 픽셀/스크린샷 클라우드 전송 없음 |
| 파일 부재 | 로컬 config의 한 등록 경로만 일시적으로 부재 경로로 바꿔 안내+5개 이미지 확인, 즉시 원복 후 6개 | 실제 출력 파일 이동/삭제 없음 |
| 출처·검토 연결 | 현재 import 해시와 별도 검토 binding을 구분; 재import해도 오래된 검토는 stale | binding 갱신은 실제 재검토 필요 |

통합 fixture suite **32개 통과 / 5.748초 / exit 0**: 큐14, 서비스5, records2, 웹7, 재시작 근거4. 실제 테스트 코드와 결과이지 모델 FPS가 아니다. Starlette의 httpx TestClient deprecated 경고는 남았으나 테스트 실패는 아니다. 도구/서비스 버전 변경 시 lock과 호환성을 다시 검토한다.

영상을 읽기 전용 allowlist로 연결했다. EXP5 영상은 1800×780, EXP6는 1800×980이며 007은15.666667초, 030은14.666667초다. 로컬 브라우저의 메타데이터만 확인했고 외부 resource 요청은 없었다. 화면은 같은 metrics JSON으로 표/그래프를 만들며 단위·측정 범위를 나눠 표시한다. 진단 박스/ID/후보 수를 정확도·성공 수로 바꾸지 않고 final accuracy는 null이다.

실제 증거 파일은 runtime의 `setup001-queue-smoke.json`, `setup002-service-smoke.json`, `setup003-service-smoke.json`, `setup004-service-smoke.json`, `browser-reports.json`, `browser-all-videos.json`, `browser-images-run2.json`, `browser-missing-run2.json`이다. raw receipt/log/DB는 게시하지 않는다.

## 실패·수정 이력

1. Linux 경로 selector와 숨겨진 외부 worktree 때문에 첫 배치가 거부됐다. native 목록에서 정확한 worktree identity를 확인하고 저장소 범위 external visibility를 바꿨다. Task 생성 전 거부임을 확인한 후 진행했다.
2. 신뢰 확인·Codex 업데이트 안내가 시작을 차단했다. 사용자가 직접 저장소 신뢰와 CLI 업데이트를 완료했고 실패한 Dispatch는 보존/정리했다. 화면에 탭이 보이지 않는 문제에는 terminal switch/read를 사용했다.
3. 기본 Orca launch argv에서 sandbox/승인 우회 옵션이 확인됐다. 그 실패 세션에서 작업을 수행하지 않고, 버전 가이드의 명시적 command→native worker-start 연결 경로로 진행했다. infra/web는 workspace-write+on-request, reviewer는 정상 automatic approval review(`--approve-for-me`, workspace-write)를 사용했다. 전역 보호 설정을 끄지 않았다.
4. WSL의 `UtilBindVsockAnyPort ... socket failed 1`로 Orca 읽기 명령이 sandbox에서 막혔다. infra/web는 사용자가 해당 명령 승인을 입력했고, reviewer는 정상 자동 승인 검토를 거쳤다. `input_accepted / provider unsupported`를 완료 증거로 세지 않고 실제 실행 기록을 확인했다. 새 터미널에서 빈 `$SCENEGUARD_ORCA` 변수 문제는 전체 실행 경로를 안내해 해결했다.
5. `--shell wsl.exe`/`powershell.exe`가 workspace 실행 위치와 충돌해 terminal 생성 전에 거부됐다. shell 생략으로 설치판이 해당 UNC worktree의 WSL 환경을 선택했다.
6. settled web/reviewer terminal 재사용은 `agent_unconfigured`로 거부됐고 새 Task가 없음을 확인했다. 강제 재시작/동일 요청 반복 없이 총괄 통합 수정과 별도 검토를 수행했다.
7. 첫 실제 웹 재시작은 TIME_WAIT 때문에 port probe가 실패했다. 활성 listener를 계속 거부하면서 SO_REUSEADDR로 종료 직후 재시작을 허용했다. 실패 기록을 보존하고 setup002/003에서 정상 재시작을 확인했다. 당시 서버가 내려간 상태의 최초 이미지/부재 검사는 실패로 남겼고, 이후 run2 성공과 구분했다.
8. 독립 검토 R1(재import 후 오래된 검토), R2(수집기 중도 종료를 놓친 시작 보고), R3(FIFO open 차단)을 확인했다. 별도 검토 바인딩, 매 시작 launch_id+두 process 생존 확인, nonblocking descriptor 검증으로 수정하고 각각 회귀 테스트를 추가했다. 최초 needs_revision 보고서는 그대로 보존했다.
9. 재검토에서 R4(완료된 mock도 웹 종료 중 유지로 통과시킬 수 있는 검사)를 찾았다. 종료 전후 두 서비스의 소유권/생존, 같은 running attempt/child identity, 웹 종료 반환 이후 실제 mock 완료, 정상 connected 재시작을 요구하도록 수정했다. 이미 끝난 작업·부재 서비스·degraded 재시작은 실패/근거부족 receipt를 보존한다. sleep 2초로 시간을 보장하지 않고 실제 중첩이 없으면 통과시키지 않는다. 새 setup004에서 종료 전후 같은 mock이 살아 있고 웹 종료 완료 후 1.690초 뒤 child가 끝났음을 확인했다. 이전 smoke만으로 이 항목을 확정하지 않는다. 최종 독립 검토가 4개 해당 fixture를 별도로 통과시키고 R4를 해결로 판정했다. 이 판단과 총괄의 32개 전체 테스트/실제 setup004 검증을 합쳐 이번 제한된 세팅을 완료로 기록한다.

## 이 PC에서 시작·중지·복구

현재 코드/새 환경은 `/home/jhc7484/dev/sceneguard-orca-lab`, 미디어 원본은 `/home/jhc7484/dev/sceneguard-ai/outputs`, 공통 runtime은 `/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab`이다. 다른 worktree도 GPU 큐에는 **이 하나의 절대 경로**를 사용한다. 로컬 config를 Git에 넣거나 worktree별 큐로 나누지 않는다.

```bash
cd /home/jhc7484/dev/sceneguard-orca-lab
.venv-orca-lab/bin/python -m orchestration.lab --config runtime/orca-lab/local_config.json status
.venv-orca-lab/bin/python -m orchestration.lab --config runtime/orca-lab/local_config.json start
# 브라우저: http://127.0.0.1:8765/
.venv-orca-lab/bin/python -m orchestration.lab --config runtime/orca-lab/local_config.json stop
```

이미 실행 중이면 start는 중복 프로세스를 만들지 않고 거부한다. 재시작은 status 확인→stop→start다. startup partial failure도 PID/boot/start-ticks 소유권을 보존하므로 status와 로컬 web.log/projection.log 확인 후 stop으로 정리한다. 새 launch_id 관측이 있어야 시작 성공이며 Orca 연결 실패는 degraded/disconnected로 명시한다. 15초 주기의 상태 읽기는 모델 호출이 아니다.

```bash
cd /home/jhc7484/dev/sceneguard-orca-lab
.venv-orca-lab/bin/python -m orchestration.queue --runtime /home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue status
.venv-orca-lab/bin/python -m orchestration.queue --runtime /home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue recover
```

recover는 무신호 조사이며 잠금 busy/정체 unknown이면 무리하게 해제하지 않는다. 대기 작업은 명시적 `run-once` 한 번에 최대 하나다. cancel/retry의 정확한 명령과 한 번 제한은 [QUEUE.md](QUEUE.md)를 따른다. 완료 작업을 다시 실행하거나 DB/잠금 파일을 지우지 않는다. CPU acceptance를 다시 수행할 때는 기존 결과를 덮지 않는 새 tag와 실제 native Task ID를 사용한다.

Orca 조회는 설치된 `orca-ide orchestration worker-list --run run_3d23462a014a --include-remote --json`이다. CLI가 PATH에 없는 별도 WSL 터미널에서는 다음 전체 경로를 사용한다.

```bash
/mnt/c/Users/jhc74/AppData/Roaming/orca/wsl-managed-cli/455214b2c94101df2de8/orca-ide status --json
```

업데이트로 이 관리 경로가 바뀌면 새 Orca 세션의 ORCA_CLI_COMMAND와 도움말에서 다시 확인한다. worker 시작은 설치 guide의 terminal create→실제 ready 확인→worker-start --terminal을 사용하고 native Task/Dispatch를 보존한다. 종료는 수락된 worker_done 후 release이며 active 작업은 근거 없이 close하지 않는다. 전체 runtime reset이나 승인 입력의 무조건 재전송은 하지 않는다.

## 완료 범위와 아직 하지 않은 일

로컬 에이전트 모델 적용·작업 전달·완료 수신, 공통 mock 큐, 실제 기록 조회/미디어 재생, 서비스 복구, 환경 보존을 확인했다. 기본 파이프라인은 변경하지 않았다. EXP-0006 박스 검토와 EXP-0007 VLM 자동 연동은 계속 **채택 보류**다.

기존 terminal 재사용은 이 버전에서 agent_unconfigured가 반복돼 미지원 경로로 기록했다. 신뢰된 새 terminal→native Dispatch 경로는 검증됐다. 정리된 worker를 상시 대기시켜 무인 운용하지 않는다.

실제 GPU 모델 작업 등록/중단 복구, 장시간 무인 운영, 여러 호스트, Windows 재부팅 후 자동 시작, 사용자 시각 정답 확정, 다음 VLM 비교 배치는 미실행이다. 큐는 외부 프로세스의 GPU 사용을 강제로 막지 못한다. 다음에는 먼저 실제 입력 시트의 사용자 검수와 비교표/실험 manifest를 확정하고, 하나의 배치 범위 승인을 받은 뒤에만 후보 다운로드·실험을 시작한다. 이 세팅이 새 모델 성능이나 안전 관제 성공을 입증하지 않는다.

코드·문서·공개 가능한 선택 집계만 GitHub에 반영한다. 원본 영상/이미지/가중치/원시 응답/DB/agent 로그/인증정보는 로컬에 남긴다. 세팅 가이드와 역할 정의는 [ADR-0013](../decisions/ADR-0013-orca-local-experiment-lab.md), [RESULT_CONTRACT](RESULT_CONTRACT.md), [VIEWER](VIEWER.md)를 함께 따른다.

## 커밋과 제외 파일 검토

작업 단위별 로컬·GitHub 커밋과 동일 tree 검증은 [PUBLICATION_MAP](PUBLICATION_MAP.md)에 기록했다. 마지막 문서 커밋에는 이 보고서·AGENTS·HANDOFF·NEXT·실제 역할 상태를 포함한다. 목표 `model_policy.json`은 원래 정책으로 보존하며 실제 확인 상태는 roles.json과 이 보고서가 원본이다. 변경 파일은 orchestration/webapp/tests_orca/records/문서/새 환경 lock/ignore 규칙으로 제한했다. 기존 실험 코드·설정·보고서의 diff는 없었다. 금지 확장자/디렉토리와 credential 패턴 검사에서 게시 대상이 없었고 runtime·세 venv·data·outputs·weights·.env 제외 규칙을 확인했다.
