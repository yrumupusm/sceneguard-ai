# 로컬 결과 조회 계약 v1

Orca가 Task/Dispatch의 원본이다. `orchestration/orca_adapter.py`는 native CLI의 상태를 읽어 로컬 JSON projection만 갱신한다. 연결 실패와 오래된 관측은 종료/실패로 바꾸지 않는다. 웹은 큐나 에이전트를 실행하지 않는다.

- `records/catalog.json`: `experiments` 배열. experiment_id, 제목/요약, 기존 원문 report_path/report_sha256, metrics_path, review_path, evaluated_model, 별도 agent model/effort, execution/review/decision 상태, limitations, next_step, evidence 목록.
- `records/EXP-xxxx/metrics.json`: 그래프와 표의 동일 원천. 각 metric은 label/value/unit/sample_n/scope/source/source_pointer/source_sha256/verification. null은 미측정/부재이며 0이 아니다. 서로 다른 실험의 집계·추론·생성 시간을 한 순위로 합치지 않는다.
- 과거 실행의 agent model/effort/task ID가 기록되지 않았으면 null이다. 새 세팅 총괄/작업자의 모델을 과거 실험 담당 모델로 소급하지 않는다. 통합 config/data/code 해시를 확정할 수 없는 과거 항목도 null로 두고 측정별 원천 해시를 유지한다.
- `records/roles.json`: 확인된 세팅 역할과 미래 실험 슬롯을 구분. 담당1/2/3은 아직 실험 미배정이다. 과거 결과는 미배정에서 열며 첫 선택은 EXP-0007이다.
- 로컬 config는 `repo_root`, `runtime_dir`, `artifact_allow_root`, `artifacts`를 갖는다. artifacts는 ID → `{path, kind}`. 절대 경로는 이 Git 제외 config에만 저장한다. 공개 catalog에는 artifact ID와 설명만 기록한다.
- `runtime_dir/orca_projection.json`: observed_at/connected/run_id/workers/stale_after_seconds. `preflight.json`과 원시 launch/agent 로그도 runtime에만 둔다. 응답이나 파일 부재를 실행 성공으로 바꾸지 않는다.
- 읽기 전용 서버 API: `GET /api/catalog`, `GET /api/experiments/{id}`, `GET /api/status`, `GET/HEAD /artifacts/{id}`. 보고서는 서버가 등록된 원문 하나를 읽어 HTML 비활성화 Markdown으로 렌더링한다. 임의 path API와 원본 data 정적 mount는 없다.
- API 상세 응답은 catalog 레코드와 `report_html`, `review_html`, `metrics` 배열, evidence별 `available`을 포함한다. 화면은 source와 hash를 접힌 기술 상세로 보여준다. reviewer 의견은 해당 report/metrics 해시를 참조하는 별도 파일이며 원문을 고치지 않는다.

원천 importer는 `python -m orchestration.catalog --source EXISTING_REPO --destination CODE_REPO`다. 원본 JSON에서 선택된 숫자만 내보내며 원시 예측/응답/미디어는 복사하지 않는다. EXP-0001~0007의 모든 실측을 복구했다고 주장하지 않는다. 각 보고서 전체 표는 원문에서 확인할 수 있다.
