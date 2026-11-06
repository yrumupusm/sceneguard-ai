# EXP-0063 재현과 재개

2026-11-06 준비 체크포인트다. 실제 학습 가중치는 아직 없으며 아래 학습 명령은 준비 템플릿이다. 사용자 검수 답변의 정확한 버전, 정답 정책·ROI, canonical GPU 큐 어댑터·배정·독립 검토를 갖추기 전에는 실행하지 않는다. 기존 첫 학습 승인은 유지되며 재승인을 요구하지 않는다.

## 완료한 실행

프로젝트 루트, 기존 `.venv-cv-batch02`에서 실행했다. 이미 존재하는 output은 재사용하지 말고 새 revision 경로를 지정한다. `data-audit/executed-script.py`, `normal-audit-v1/executed-script.py`는 각각 최초 실행 코드다. 현재 코드에는 명시적 검수 표본 선택과 재분할 전용 CLI가 추가됐다.

```bash
.venv-cv-batch02/bin/python scripts/audit_action_dataset.py --workers 2 --code-sha 3692a93791307cba3e2557a85c8f142edea5e737
.venv-cv-batch02/bin/python scripts/freeze_action_baseline.py --output outputs/action-recognition/exp0063/baseline/attempt-002
.venv-cv-batch02/bin/python scripts/prepare_action_normal_data.py --wall-audit outputs/action-recognition/exp0063/data-audit --baseline-lock outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json --output outputs/action-recognition/exp0063/normal-audit-v1
.venv-cv-batch02/bin/python scripts/audit_action_dataset.py --output outputs/action-recognition/exp0063/normal-review-v1 --overlays-only --overlay-selection outputs/action-recognition/exp0063/normal-review-v1/selection.json
.venv-cv-batch02/bin/python -m unittest discover -s tests -p 'test_action*.py' -v
```

정상 검수 경로의 manifest/packet 목록은 정상 감사의 바이트 복사본이며 split에는 최종v3 부모 해시와 두 목록의 SHA를 바인딩했다. selection은 선언 moving/stand 중15–90프레임 구간·박스 존재·오류 없음 조건을 만족하는 source_id/event_index 사전순 첫 항목을 각각 택했다. 원본/표본을 보고 좋은 장면만 골랐다는 의미가 아니다. 모든 선택·영상 프레임·원본PTS는 로컬에 저장했다.

최종 분할은 다음 독립 재현 명령으로 확인했다. 코드 버전 SHA 필드를 제외한 전체 JSON이 고정v3와 동일했다. 최초 결과를 덮어쓰지 않고 재현 결과를 새 경로에 보존했다.

```bash
.venv-cv-batch02/bin/python scripts/prepare_action_normal_data.py --wall-audit outputs/action-recognition/exp0063/data-audit --normal-audit outputs/action-recognition/exp0063/normal-audit-v1 --baseline-lock outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json --output outputs/action-recognition/exp0063/combined-split-v3-reproduction
```

`readiness-v3/preflight-rejected.json`에 실제 명령·예상 거절·표준오류를 저장했다. 빈 pending manifest는 검수 근거 부족으로 GPU/출력 생성 전에 거절됐다. 이것은 학습 실패나 실제 데이터 smoke 결과가 아니다. `protection-check.json`에서 기존 production 코드 해시와 과거 catalog 행 보존을 확인했다.

## 검수 뒤 이어갈 순서

1. 기존 웹 검수 workflow의 `pending --include-acknowledged`로8표본 답변을 읽는다. 정확한 version/answer_version으로 확인하고 반영 근거 또는 보류 이유를 남긴다. 단순 의견을 모든 파일의 정답으로 확대하지 않는다.
2. 시간 원점·박스 대응·행동 구간/음성 의미와 문·담장 맥락 ROI 정책을 근거에 맞게 고정한다. 오류7파일·사용자 제외313파일·불명확 구간을 포함하지 않는다. 공식 라벨과 별도 사람 검수의 출처를 보존한다.
3. 최종v3 source/group/split을 유지하는 reviewed-clips manifest와 불변 검수 영수증 연결을 구현/검토한다. 현재 truthy review_evidence 검사만으로 사람 검수 사실을 인증하지 않는다.
4. 공식 R3D-18 Kinetics400 가중치를 받아 전체 SHA를 고정하고, 기존 canonical GPU 큐의 작업 배정/락/자원 점검을 통해 소량 forward/backward·검증을 실제 확인한다. 큐 연결은 아직 구현 완료가 아니다. 단독 GPU 실행으로 우회하지 않는다.
5. 같은 첫 설정으로 학습을 완료한 뒤 검증 CE로 checkpoint를 선택하고 시험을 한 번 평가한다. 같은 장소/별도 장소를 구분한 지표·대표 실패 자료를 저장한다.
6. 그 다음 별도 통합 모드의 점수 사용 정책을 먼저 고정해 검출/추적을 유지한45회귀를 비교한다. 행동 점수와 침입 완료를 동일시하지 않는다. 미검수 지표는 미측정으로 남긴다.

아래는 필요한 입력이 준비된 뒤 사용할 학습기 인터페이스이며 현재 실행된 명령이 아니다. `reviewed-clips.json`, `prepared`, 가중치와 큐 작업은 아직 없다. 큐 어댑터가 동일 인자를 전달하고 canonical lock FD를 상속해야 한다.

```bash
.venv-cv-batch02/bin/python scripts/train_action_recognizer.py --manifest runtime/action-recognition/exp0063/reviewed-clips.json --baseline-lock outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json --split-manifest outputs/action-recognition/exp0063/combined-split-v3/split-manifest.json --config configs/exp0063_action_training.json --output outputs/action-recognition/exp0063/preflight-reviewed --mode preflight
.venv-cv-batch02/bin/python scripts/train_action_recognizer.py --manifest runtime/action-recognition/exp0063/reviewed-clips.json --baseline-lock outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json --split-manifest outputs/action-recognition/exp0063/combined-split-v3/split-manifest.json --config configs/exp0063_action_training.json --output outputs/action-recognition/exp0063/prepared --mode prepare
# 큐 어댑터에서 위 공통 인자에 --mode train --prepared ... --weights ... --weights-sha256 ...를 전달한다.
```

새 실제 학습 결과는 이미 등록한 준비 보고서/검수 바인딩을 수정하지 않는 별도 후속 결과로 저장한다. 기본 시연/기존45결과와 별도로 보존한다.
