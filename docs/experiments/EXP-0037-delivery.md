# EXP-0037 전달 확인

2026-10-30. [결과 보고서](EXP-0037-results.md)와 [독립 검토](../reviews/EXP-0037-independent-review.md)를 별도로 결속하고 기존 완료 CLI에 등록했다. **기능·개발 구간 시연 완료 / 후처리 효과0·미채택 / 침입 판별 성능 미충족**이다. 이번 마무리를 종료하고 새 실험을 자동 실행하지 않는다.

## 실제 등록과 화면

기존 서비스 **http://127.0.0.1:8765/ → 담당3 → EXP-0037**에서 확인한다. 후처리 비교는007/030 baseline/proposed, 단일 분석은 E01_007/E01_030을 선택한다.007의45–48초와48–105초는 결과 선택에 표시된 구간으로 구분한다. 전체 원본 분석이나 실시간 처리로 표시하지 않는다.

- 보고서·측정15행·실측 그래프2개·독립 검토가 현재 결속된 원문과 일치했다.
- 등록 영상5개를 실제 브라우저에서 재생/seek하고16.5초 자동 폴링 뒤에도 media DOM과 위치가 유지되는지 확인했다. HTTP 성공만으로 대신하지 않았다.
- CLI007/030의2/3카드, 최초 토스트2/3회·반복0, 근거 시점 이동, 수동 검토 저장을 확인했다. 두 시연의 기존 claim10행(과거5+이번5)은 유지한다. 같은 녹화 세션을 재생할 때 팝업을 다시 띄우려고 DB를 초기화하지 않는다.
- UI 저장/수정/동시 충돌409/이력4, 새 bundle의 별도 검토1, 자동 갱신·새로고침·서비스 재시작 복원을 확인했다. 시험 기록은 Codex 기능검증이며 사용자 확정 행동 정답이 아니다.
- 같은 영상·같은 표시 이름의 여러 분석은 등록 ID로 선택하며 실제 다른 영상 구간이 열린다. 짧은 영상의 자동 재생 검사는 최초 unmuted 상태에서 멈춰 실패를 보존했고 muted 자동 재생으로 확인했다. 제품의 모델·판정·영상은 바꾸지 않았다.

현재 서비스의 JS SHA256은 `eaeacb17fd50c5cabb536baeb5ad156c8bd462c7ae387682245709a872b30e5d`다. 최종 HTML/CSS·API/등록 미디어의 실제 HTTP 바이트도 로컬 파일 해시와 대조했다. 결과 등록 성공, GitHub 게시, 실제 서비스 버전은 별도 확인이다.

| 원문 | SHA256 |
|---|---|
|보고서|`1dc079d8b13ab45d3bce903ef14abdced68a598e6a3908fb0b21f52f04ebafec`|
|측정값|`f9fb9fa35d49da89e146a53992672796077b275559a840d99f2815b91064249b`|
|독립 검토|`3389c76d0d6b8492b6a2a44aa060cd7c7daca352217c34750b044885b42407a9`|
|검토 결속|`a5c032bef789ca85e38054dc3bf6afa08c71485449471db47ea339855e666bc0`|

## 재현·시작·중지·복구

[단일 분석 명령](../design/MVP_FINISH_CLI.md)과 README의007 명령을 실제 실행했다. README 명령을 최종 코드로 다시 확인해 완료 단계만 재사용했고 새 추론은 없었다. 등록 설정은 기존 절대 `local_config.json` 경로를 사용한다. `..`가 포함된 설정 경로는 거부되므로 예제에서 이를 제거했다.

기존 서비스 관리 명령은 저장소 루트에서 실행한다. `SCENEGUARD_LAB_CONFIG`는 **이미 사용 중인 절대 로컬 설정 경로**로 지정한다. 아래 `start/stop/status`는 기존 서비스만 관리하며 Orca나 GPU 큐를 중단하지 않는다.

```bash
../sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.lab \
  --config "$SCENEGUARD_LAB_CONFIG" status
../sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.lab \
  --config "$SCENEGUARD_LAB_CONFIG" stop
../sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.lab \
  --config "$SCENEGUARD_LAB_CONFIG" start
```

중지 전 결과 화면을 닫거나 다른 페이지로 이동해 영상 스트림을 종료한다. 이번 첫 중지는 열린 스트림 때문에 종료 대기를 초과했으나 저장 상태를 유지했고, 연결 종료 뒤 정상 중지/시작했다. `status`에서 기존 프로세스를 확인하며 새 서버를 중복 실행하거나 무관한 프로세스를 강제 종료하지 않는다. 실패/중단 분석은 같은 명령에서 완료 단계의 입력/코드/산출물 결속을 검증해 재사용한다. 새 원본 검출에는 현재 활성 Orca 배정과 canonical 큐 권한 문맥이 필요하다.

## 로컬 자료와 게시 범위

최종 원본 구간은 `outputs/exp0037/video007-v4/evidence/original.mp4`, `video030-v3/evidence/original.mp4`, `fresh007-reuse-v2/evidence/original.mp4`다. 각 폴더의 카드별 MP4와 native PTS 매핑은 로컬에 있다. 새 GPU 실행 계보는 `fresh007-45-48-v1/`와 canonical queue job/attempt에 보존했다. 이후 exact-job 선택 보호는 CPU 회귀 시험만 수행했고 추가 GPU 재실행은 없다.

실제 화면 영수증은 `runtime/EXP-0037/delivery/`, 구현/실행/독립 검토 영수증은 같은 runtime의 상위 폴더다. 검토 DB·메모·원시 결과·영상·이미지·가중치·인증정보는 Git 제외다. 기존1,447보호 파일·128등록 원문·35개 과거 결과와 기존47개 queue job/attempt는 보존했다. 이번 새 결과1행과 GPU job/attempt1개만 추가했다.

기존 Run의 구현 Sol high, 화면 Terra high, 독립 Astra high 배정과 실제 실효 설정을 확인했다. 완료된 이번 작업자4개 배정은 모두 해제했고 정리 대기0이다. 기존 retained 세션22개는 건드리지 않았다. 같은 화면 작업자의 첫 배정 종료 뒤 실제 인수 시험 수정만 후속 배정했으며 총괄 추가 생성/동시 작업자3명 초과는 없다.

GitHub 원격 반영 검증은 게시 후 아래에 기록한다.
