# Orca에서 SceneGuard 실험실 세팅

작성 2026-10-28. **이 문서는 세팅 승인·구현 지시서다. 사용자의 PC에 설치/실행됐다는 보고서가 아니다.** 기준 저장소 이력 df922a0 및 EXP-0001~0007을 보존한다.

## 0. 이번에 만드는 것과 범위

기존 `sceneguard-ai` 하나에서 총괄 1명 + 역할별 작업자 + 단일 GPU 실행 대기열 + 읽기 전용 로컬 결과 페이지를 세팅한다. 별도 GitHub 저장소, 무인 클라우드 운영, 유료 API 전환, 새 실험 모델 다운로드는 이번 범위가 아니다.

허용: 환경/계정의 비밀 아닌 가용성 진단, 현재 로그인으로 짧은 에이전트 호출 검증, 프로젝트 범위 지침·설정 작성, 필요한 최소 의존성의 새 환경 설치, CPU mock 대기열 테스트, 기존 보고서의 표시와 검토, 코드/문서 커밋. 기존 .venv/.venv-vlm·데이터·가중치·공식 라벨·이전 보고서는 변경하지 않는다.

세팅이 끝나면 실측된 동작 확인과 미완료 항목을 보고하고 멈춘다. 다음 실제 VLM 후보 비교 배치는 별도 하나의 범위 승인으로 진행하며, 그 배치 내부의 작은 작업마다 재승인을 요구하지 않는다.

## 1. 먼저 실제 Orca/Codex 환경 확인

작업 위치: 현재 Orca의 SceneGuard Codex 세션. Windows/WSL 중 실제 GPU·기존 .venv가 있는 WSL 실행 경로와 Orca runtime 경로를 먼저 확인한다. 서로 다른 경로를 같은 것으로 가정하지 않는다.

가능한 읽기 전용 진단부터 수행:

```bash
git status --short
git rev-parse --show-toplevel
codex --version
codex --help
command -v orca
orca status --json
orca skills get orchestration --full
nvidia-smi
```

위 명령은 설치 버전의 도움말과 대조한다. `orca`가 없거나 runtime이 닿지 않으면 추측한 endpoint/토큰/내부 DB를 사용하지 않는다. 현재 공식 UI는 Settings → Experimental → CLI 등록 및 Orchestration 활성화를 안내한다. 사용자 UI 동작이 필요하면 해당 항목만 알린다. 자동 전역 업그레이드/재설치/전체 상태 reset 금지.

Orca Codex의 기본 계정은 ~/.codex, 별도 관리 계정은 분리 home을 사용할 수 있다. 어느 계정 컨텍스트인지 확인하되 인증파일 내용은 읽거나 복사하지 않는다. 긴 관리 home 때문에 Codex daemon이 꺼진 경우가 있으므로 `codex agents`/resume이 반드시 된다고 가정하지 않는다.

## 2. AI 역할 모델과 사용권 확인

정책 원본: [model_policy.json](../../configs/orchestration/model_policy.json).

| 역할 | 목표 모델 | 추론 수준 |
| --- | --- | --- |
| 총괄 | gpt-6-astra | runtime이 허용하는 최고: max 우선, xhigh/high 순으로 가용성 확인 |
| 후보별 실험 담당 1~3 | gpt-6.1-sol | high |
| 실행기/연결 구현 | gpt-6.1-sol | high |
| 별도 맥락의 검토 담당 | gpt-6-astra | high |
| 웹페이지 구현 | gpt-6.1-terra | high |

이것은 OpenAI 공식 API 모델 목록을 바탕으로 한 **목표 배정**이다. API 존재와 현재 ChatGPT 로그인 Codex에서의 가용성은 다르다. 일부 Codex 문서는 이전 세대를 표시하므로 버전·계정별 실제 가용 목록과 성공 호출로 최종 확인한다. ChatGPT의 Astra Pro라는 표시를 보고 임의의 CLI model ID를 만들지 않는다. 실제 런타임에서 더 높은 Astra Pro 모델과 필요한 도구가 제공되면 그 정확한 ID를 기록하고 총괄로 선택한다.

- 대화형 `/model` 또는 설치 버전이 지원하는 모델 목록 API로 model_id와 supported effort를 확인한다. App Server의 model/list를 쓴다면 설치 버전 스키마를 따른다. `codex models`라는 명령을 임의로 가정하지 않는다.
- 프로필별 짧은 무해한 read-only 호출로 실제 모델을 검증한다. 예: 비밀/미디어 없는 저장소 파일의 존재만 확인. 모든 미디어 접근은 차단한다.
- Orca launch.requested/effective, Codex 세션/이벤트 메타데이터 등 실제 근거를 남긴다. 모델이 자기 이름을 말한 답변만으로 확인하지 않는다. 숨은 fallback이 있으면 verified가 아니다.
- 최고 모델이 불가하면 자동 하향·새 API 결제 없이 해당 역할을 blocked로 두고 사용자에게 가능한 선택을 알린다. 다른 모델로 몰래 대체하지 않는다.
- 모델은 가능하지만 max만 불가하면 같은 모델에서 runtime이 제공하는 최고 effort를 사용하고 차이를 명시한다. `.codex/config.toml`에 지원 안 되는 값을 억지로 넣지 않는다.
- 기존 로그인/계정 유지, 새 구독·토큰 발급·구매·API key 전환 금지. 현재 계정 사용량/크레딧이 소모될 수 있음을 보고한다. 조직 정책이 막으면 우회하지 않는다.

세팅 진단 결과는 로컬 runtime/orca-lab/preflight.json 및 공개 가능한 요약 docs/orchestration/LOCAL_SETUP_REPORT.md에 저장한다. 버전·가용 모델·요청/실효 effort·검증 상태·확인시각을 기록하고 계정 ID/토큰/원시 credential 로그는 공개하지 않는다.

## 3. 오케스트레이션은 한 계층만 사용

**우선 경로: Orca native Run/Task/Dispatch + supervised worker.** 역할 지침은 [AGENT_ROLES](AGENT_ROLES.md). 기존 제품의 세션·메시지 기능을 새로 복제하지 않는다.

버전별 `orca skills get orchestration --full`을 읽고, 지원되면:
- 하나의 Run과 총괄 inbox를 만들고, scope가 겹치지 않는 Tasks를 등록한다.
- `worker-start`로 Codex 작업자를 역할별 model/effort와 별도 worktree에 실행한다. 실효 모델 설정을 launch receipt에서 확인한다.
- `worker_done`에는 taskId와 dispatchId, succeeded/failed, 결과 파일을 포함한다. stale dispatch가 새 작업을 완료시키지 못하게 한다.
- 총괄은 `check --wait`로 완료/실패/질문을 수신하고 결과·결정을 기록한 뒤 Delivery를 ack한다. GUI의 녹색 상태나 idle을 테스트 성공으로 해석하지 않는다.
- 완료 작업은 release/read 계약으로 관리하고 관계없는 사용자 터미널을 닫지 않는다.
- `orca orchestration run`, `run-stop`, `coordinator-start` 등 폐기된 예전 명령을 사용하지 않는다. Run 생성 자체는 스케줄러가 아니다. 총괄이 다음 task를 결정/dispatch한다.

Orca 기능이 없는 버전이면 missing capability를 명시한다. 기존 Codex native custom subagent가 실제 지원되면 **이번 세팅 세션 안의 bounded fallback**으로 사용 가능하나, Orca와 Codex를 동시에 중첩 총괄로 가동하지 않는다. 프로젝트 `.codex/agents/*.toml`의 name/description/developer_instructions/model/effort는 설치 버전의 스키마로 생성·검증한다. 원치 않는 전역 config 덮어쓰기 금지. 자동화 기능이 실제로 없으면 문서상의 역할을 실행 중인 에이전트처럼 표시하지 않는다.

동시 작업자 최대 3명, 별도 reviewer는 자리가 난 뒤 실행한다. 후보 1/2/3은 고정 역할이 아니라 실험 모델 슬롯이다. 하위가 다시 하위를 만드는 재귀 확장 금지.

## 4. 하나의 저장소와 공통 로컬 상태

새 구조를 필요한 만큼만 추가:

```text
orchestration/       Orca 연결 adapter, 작업 상태 조회, GPU 실행기
webapp/              Python 기반 읽기 전용 화면
configs/orchestration/  모델 정책·공개 가능한 작업 정의
.codex/agents/      가용성 검증 후 생성하는 Codex 프로젝트 역할 설정
records/            공개 가능한 run metadata·metrics·artifact 참조
docs/experiments/   기존 및 새 실험 보고서
docs/reviews/       원문을 고치지 않는 별도 총괄/평가 의견
runtime/            로컬 DB·잠금·heartbeat·launch receipt (Git 제외)
outputs/            기존 및 새 원시 결과·영상 (Git 제외)
```

- 모든 worktree는 하나의 canonical runtime/output registry를 사용한다. 실제 절대 경로는 로컬 설정에만 저장한다. 기존 Git 제외 data/weights/env가 새 worktree에 없는 경우 재다운로드·복사하지 말고 허가된 원본 경로를 참조한다.
- worktree branch는 setup/orca-lab 계열로 분리. dirty main에서 임의 stash/reset/overwrite 금지. 총괄이 검토 후 통합·push한다.
- Orca가 Task/Dispatch 생명주기의 원본이다. SQLite는 GPU job/실험 artifact/review와 UI projection을 관리하고 Orca task ID를 참조한다. 동일 상태를 두 곳에서 서로 덮어쓰는 이중 총괄 금지.
- runtime DB/원시 로그는 Git 제외. 선택된 공개 JSON/Markdown은 완료 작업 단위로 내보내어 Git에 기록. heartbeat마다 commit하지 않는다.
- instruction/roles 파일만 만드는 것으로 세팅 완료 처리하지 않는다. 실제 호출/메시지·동작 테스트가 필요하다.

## 5. GPU 큐와 작업 계약

호스트에서 실행 중인 GPU 실험은 1개. 에이전트 모델 호출은 클라우드이고, 로컬 영상 모델 실험만 이 GPU 큐를 사용한다.

구현할 최소 기능:
- 사전 등록된 script/argv/cwd만 실행. shell=True나 웹 입력 임의 명령 실행 금지.
- canonical 경로의 GPU OS lock과 SQLite 원자적 claim으로 동시 실행을 제어한다. 잠금 파일을 worktree마다 만들지 않는다.
- task/run/attempt ID, owner, expected input/config hash, pid, started/finished time, exit code, heartbeat, timeout, result manifest를 기록한다.
- 재시작 시 이전 PID와 실제 생존 여부를 대조. 동일 job을 자동 중복 실행하지 않는다. active process가 있는데 잠금을 강제 해제하거나 관계없는 프로세스를 kill하지 않는다.
- 완료·실패·취소/중단 구분, bounded retry(최대 1회), 실행 실패 보고. sleep/CPU mock job으로 직렬화·실패해제·재시작을 먼저 테스트한다. GPU가 실제로 사용된 것처럼 mock 테스트를 보고하지 않는다.
- 세팅 단계는 코드/화면/큐 smoke만. 새 VLM 추론·대규모 다운로드는 없으며 기존 결과로 viewer를 검증한다.

실행 결과 공통 필드:
`schema_version, experiment_id, run_id, task_id, attempt_id, role, agent_model_requested, agent_model_effective, reasoning_effective, evaluated_model, config_hash, data_manifest_hash, code_sha, execution_status, review_status, decision_status, metric_definitions, metrics, limitations, evidence, created_at, updated_at`.

metrics는 단위·표본수·평가범위·출처를 포함하고 미측정은 null이다. 모델 판단 요약으로 측정값을 새로 만들지 않는다. 보고서는 기존 Markdown 원본을 링크/렌더링한다. 그래프와 표는 같은 metrics 원본에서 만든다. reviewer 의견은 source report/metrics hash를 참조하는 별도 불변 기록이다.

## 6. 직관적인 결과 웹페이지

네가 요청한 구조 그대로: 위에 총괄 카드 → 아래 담당 1/2/3과 미배정 카드 → 아래 선택된 항목의 넓은 상세 영역. 읽기 전용 첫 버전이다.

- 첫 화면은 최근 실제 보고서/전체 상태. 클릭으로 같은 화면 내용이 전환된다. 기본 정보는 목표, 이번 변경, 좋아진 점, 남은 문제, 총괄 판단, 다음 작업.
- 상세 순서: 쉬운 요약 / 실측 비교표·관련 그래프 1~2개 / 근거 영상 / 담당 의견 / 총괄 검토 / 다음 작업. 명령·해시·패키지는 접힌 기술 상세로 둔다.
- 모델 가용성 검증 전 카드 상태는 미검증/미배정. setup worker와 앞으로의 model slot을 혼동하지 않는다.
- 보고서 없음·미측정·실패·검토 대기·오래된 상태는 사실대로. synthetic 테스트 결과는 TEST 전용 표기하고 실험 목록/랭킹에 합치지 않는다.
- EXP-0001~0007은 읽기 전용으로 가져와 표시. 지표는 실제 근거 확인 후 import하고, 수동 보완은 source reference와 확인상태를 남긴다. 기존 문서 수정 금지. 모든 수치를 자동으로 복구했다는 허위 완료 금지.
- `FastAPI + Jinja2/vanilla JavaScript + SQLite` 같은 최소 구성으로 충분하다. `.venv-orca-lab`을 새로 사용하고 기존 CV/VLM 환경 freeze가 동일한지 검사한다. 모델은 웹 서버에 로딩하지 않는다.
- 기본 bind 127.0.0.1. port 8765는 제안값이며 충돌 시 빈 포트를 확인해 보고한다. 웹을 닫아도 작업이 중단되지 않고 새로고침으로 실행되지 않아야 한다.
- Markdown/모델 응답 escape/sanitize, artifact ID→허용된 경로만 매핑, path traversal/symlink 탈출/환경파일 접근 차단. raw data 전체를 정적 mount하지 않는다. 영상 Range/seek·경로 부재 테스트.
- 네트워크 없이 화면 사용 가능하도록 그래프 자산도 로컬 관리. 공개 배포/휴대폰 외부 연결/포트포워딩/자동 CDN 요청은 이번 범위 밖이다.
- Orca browser로 실제 페이지를 열어 카드 전환/원문/검토 의견/그래프 null/영상 재생/부재상태를 확인한다. built-in browser가 안 되면 일반 브라우저 주소를 알려주되 검증 범위를 구분한다.

## 7. 세팅 완료 기준 — 반드시 실제 결과로 보고

1. OS/Orca/Codex 경로와 버전, 모델 가용성과 실제 effective model/effort를 기록했다. unavailable 역할은 숨기지 않는다.
2. 별도 worker의 결과를 총괄이 받고 별도 review를 작성하는 짧은 무해한 작업 1회가 성공했다. 보고 문구만 출력하는 모의 에이전트를 실제 AI 세션으로 세지 않는다.
3. 같은 GPU 큐에 두 mock 작업을 제출했을 때 실행 구간이 겹치지 않고, 의도적 실패 후 다음 작업이 실행되며 완료 작업은 재시작 때 중복 실행되지 않는다.
4. 실제 기존 EXP-0007과 그 비용/한계를 UI에서 확인하고, 다른 과거 보고서도 열 수 있다. 새 가상 성능을 만들지 않았다.
5. 기존 .venv/.venv-vlm·공식 라벨·이전 결과 보존 및 보안 테스트/구문/스키마 테스트를 통과했다.
6. LOCAL_SETUP_REPORT.md에 완료/차단/미실행, 실제 모델표, 화면 URL, 시작·중지·복구 명령, 테스트 결과, 커밋, 로컬에만 남긴 경로를 적었다.
7. 실행 인스턴스를 임의로 계속 늘리지 않는다. 세팅 끝에서 다음 batch를 제안하고 멈춘다. 총괄·로컬 runtime이 닫혀도 AI가 영구히 스스로 계속 일한다고 약속하지 않는다.

## 8. 설치 버전과 대조할 공식 자료

- Orca orchestration: https://www.onorca.dev/docs/cli/orchestration
- Orca CLI: https://www.onorca.dev/docs/cli/reference
- Orca Codex: https://www.onorca.dev/docs/agents/codex
- Codex 모델/현재 API 목록: https://developers.openai.com/api/docs/models
- Codex 역할/서브에이전트: https://developers.openai.com/codex/subagents
- Codex config: https://developers.openai.com/codex/config-reference
- Codex App Server: https://developers.openai.com/codex/app-server

웹 문서와 설치 버전의 모델/effort/키가 다르면 호환성을 진단하고 실제 가용 설정으로 기록한다. 공식 최신 모델 목록에 존재한다는 이유만으로 해당 계정의 Codex 권한이 있다고 단정하지 않는다.
