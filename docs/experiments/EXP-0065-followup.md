# EXP-0065 — 학교 CCTV 행동 후보·입력 부족 진단과 정상 자료 보강

2026-11-07. 사용자가 EXP-0064 후속 진단과 데이터 보강을 진행하도록 요청했다.

**후속 상태: 실행 PC에서 실제 저장 점수 진단과 검수 자료 생성을 진행했다.** 최신 결과는 [EXP-0065 결과](EXP-0065-results.md), 사건별 실제 대조는 [52참조 진단](EXP-0065-coverage-results.md)을 따른다. 아래 준비 지침의 “이번 환경에서 읽지 못함”은 PR 작성 당시의 이력이다. 실제 실행·의미 검수·성능 개선은 별도로 보고하며 새 학습은 하지 않는다.

## 목표와 기준

EXP-0064의 고정 R3D-18 선택 가중치와 임계값 0.5, EXP-0062 AFTER를 그대로 사용해 다음을 먼저 확인한다.

1. 공식 사건 시간대에 실제로 어떤 사람의 행동 후보가 나왔는가?
2. 행동 후보가 없을 때 입력은 있었으나 점수가 낮았는가, 관측 부족으로 입력 자체가 없었는가?
3. 다른 장소의 정상 사례 오판은 대상 행동, 입력 영역의 다른 사람, 라벨/시간 대응 중 무엇과 관련되는가?
4. 다음 학습과 독립 평가에 필요한 정상·접근·돌아가기 자료를 어디에서 얼마나 확보할 수 있는가?

학습에 사용한 공원 영상의 공식 라벨 대조 F1 99.83%와 학교 CCTV 침입 성능은 서로 다른 평가다. 별도 장소 시험은 넘기 330·정상 2개 전부 넘기로 분류했으며, 검증 음성은 앉기만 포함한다. 이것으로 모델이 배경을 학습했다고 단정하지는 않는다.

EXP-0064의 467개 후보는 겹치는 입력 창이다. EXP-0062의 37/52 확인과 직접 뺄셈하지 않는다. 기존 45개는 계속 회귀·진단 전용이며 새 학습/검증/임계값 선택에 넣지 않는다. 이번 진단으로 살펴본 자료를 향후 독립 최종 시험이라고 부르지 않는다.

## 로컬 Codex 실행 순서

### 1. 현재 작업과 검수 상태 확인

기존 작업 디렉터리의 미커밋 변경을 보존하고 이 변경의 브랜치/커밋을 확인한다. 실행 PC의 `docs/WEB_REVIEW_WORKFLOW.md`에 따라 `pending --include-acknowledged`로 신규·수정 답변을 읽는다. 정확한 답변 버전과 반영 범위를 기록한다. 이미 확인한 박스 정렬 질문을 반복하지 않는다. 현재 로컬 Run/Task/Dispatch와 기존 CPU/웹 환경을 재사용한다.

다음 고정 자료를 먼저 찾는다. 전체 미디어·가중치를 다시 해시하거나 학습을 다시 실행할 필요는 없다.

| 입력 | 기존 로컬 경로 | 고정 SHA256 |
|---|---|---|
| 기준 잠금 | `outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json` | `3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40` |
| 45개 입력 계획 | `outputs/action-recognition/exp0064/regression-plan-v2/manifest.json` | `f8bea6c8b4b36d5d09daf8f3b43a7e8923319ef5bde3b5c4e5cd5f00f0f7cb17` |
| 실제 추론 결과 | `outputs/action-recognition/exp0064/queued-inference/all45/3825ad63d2254611921ccb7b349c2feb/result.json` | `b465170efe203655deb76f857549101180e6ce56171ae510c69347595d7e34a8` |
| 선택 가중치의 식별자 | EXP-0064 `best.pt` | `8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73` |

각 영상의 점수는 추론 결과와 같은 디렉터리의 `E01_XXX/window-scores.jsonl`에 있다. 진단 도구는 가중치 파일을 읽거나 모델을 실행하지 않는다.

### 2. 기존 정답·평가 파일을 실제 스키마에 연결

기준 잠금의 `verified_paths`에서 **EXP-0062가 사용한 45영상·공식 52시간 참조의 평가 manifest**를 찾는다. 필요한 구조는 `videos[]` 안의 `video_id`, `video_sha256`, `truth_basis`, `events[{id,gate_id,start,end}]`, `unresolved_reference_events`, `verified_non_event_intervals`다. `sceneguard/accuracy_evaluation.py`와 `scripts/mvp_full_evaluation_adapter.py`의 기존 계약을 따른다.

선택적으로 같은 기준의 평가 report도 연결한다. 구조는 `modes.confirmation.by_video[].matches[]`의 `outcome=tp`, `truth_id`다. 이를 연결하면 각 공식 사건이 EXP-0062에서 확인됐는지 함께 표시한다. 없으면 해당 열은 null이며 37/52의 개별 사건 대응을 추측하지 않는다.

**이번 환경에서는 해당 비공개 파일의 실제 경로와 스키마를 읽지 못했다.** 파일명을 추정해 새 정답을 만들지 말고 로컬 `evaluation-manifest.json`, `after-scoring.json`, `final-reports/`의 출처를 확인한다. 형식이 다르면 실제 입력을 확인해 읽기 전용 어댑터와 fixture를 보완한다. 고정 해시 검사를 제거해 통과시키지 않는다. 기존 정답/보고서는 수정하지 않는다. 006의 시간 미확정 1개와 008 의미 검수 보류를 유지한다.

### 3. CPU 진단 실행

```bash
python -m unittest discover -s tests -p 'test_action_event_coverage.py' -v

# 실행 PC의 잠금 목록에서 확인한 실제 자료다.
sg_reference_manifest='outputs/validation/false-confirmation-guard-all45-v1/run-001/after-manifest.json'
sg_baseline_report='outputs/validation/false-confirmation-guard-all45-v1/run-001/after-scoring.json'

python scripts/audit_action_event_coverage.py \
  --baseline-lock outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json \
  --plan outputs/action-recognition/exp0064/regression-plan-v2/manifest.json \
  --inference-result outputs/action-recognition/exp0064/queued-inference/all45/3825ad63d2254611921ccb7b349c2feb/result.json \
  --references "$sg_reference_manifest" \
  --baseline-report "$sg_baseline_report" \
  --evaluation-receipt outputs/validation/false-confirmation-guard-all45-v1/run-001/evaluation-manifest.json \
  --inference-receipt outputs/action-recognition/exp0064/regression-plan-v2/integration-execution-report-v1.json \
  --output outputs/action-recognition/exp0065/coverage-reproduction-new
```

기존 report 계약을 아직 연결하지 못했다면 `--baseline-report`만 생략할 수 있다. 정답 manifest와 45영상/52참조 수 검사는 필수다. 기본 SHA와 개수 인자를 바꾸는 옵션은 합성 fixture나 명시적으로 기록한 새 revision용이며 현재 실제 실행을 우회하기 위한 수단이 아니다.

도구는 고정 plan·result·기준·정답 해시와 점수의 영상/입력/모델 출처, 모든 예정 입력의 점수 존재, 집계 일치를 확인한다. 세부 score JSONL의 현재 바이트 해시를 소비한 snapshot으로 기록하고 실행 중 변경 여부를 확인한다. 이 snapshot 해시는 별도 실행 당시 영수증을 새로 인증하는 것이 아니다. 로컬 기존 실행 영수증과 추가 대조할 수 있다.

출력은 새 디렉터리에만 저장한다.

| 산출물 | 내용 |
|---|---|
| `summary.json` | 읽은 파일의 해시, 전체 분모, 사건 시간대별 진단 개수, 의미 검수 미완료 상태 |
| `event-diagnostics.csv` | 공식 사건별 점수 유무·후보·부분 관측·기존 확인 대응 |
| `per-video.json` | 사건별 관련 창 ID, 정상 구간의 후보, 같은 track의 연속 후보를 묶은 검수 구간 |

시간 관계는 **실제 샘플 중 하나가 공식 `[start,end)` 안에 있는지**로 표시한다. 같은 사람/같은 문인지 확인한 TP가 아니다. 입력 시간과 batch 처리 시각을 구분하고 실시간 경보 시각으로 바꾸지 않는다.

| 진단 | 해석 |
|---|---|
| `candidate_time_overlap` | 사건 시간대와 겹치는 넘기 후보가 있음. 대상·문 대응은 검수 필요 |
| `scored_without_candidate_time_overlap` | 겹치는 입력 점수는 있지만 모두 0.5 미만. 그 입력이 대상 사람인지 별도 확인 |
| `partial_observations_only` | 완전한 입력은 없고, 부분 창의 **실제로 관측된 시점**이 해당 시간대 안에 있음 |
| `no_observed_window_in_reference` | 해당 시간대에 완전한 입력이나 부분 창의 실제 관측 시점이 없음. 예정된 결측 시점만 겹치는 경우는 별도 열에 기록하며 원인의 단정은 금지 |

정상 참조는 여덟 샘플 모두 해당 정상 구간에 들어가는 입력과 경계에 걸친 입력을 분리한다. 구간의 대상·문 대응을 확인하기 전 false alarm으로 확정하지 않는다. 공식 사건 바깥의 후보는 미주석일 수 있어 자동 음성으로 만들지 않는다. 연속 후보 묶음 수는 독립 인원·사건 수가 아니다.

### 4. 실제 원본과 대조할 검수 자료

먼저 전체 52참조의 위 표를 만든다. 이후 기존 확인 누락 15개 중 후보가 생긴 사건, 점수만 낮은 사건, 입력이 없는 사건을 구분해 대표 장면을 고른다. 한 종류·한 카메라만 고르지 말고 각 종류와 카메라를 포함하도록 선정 근거와 미선정 목록을 남긴다. 이미 검수한 의미는 재사용한다.

검수 영상은 로컬에서만 생성한다. 원본 PTS, 대상 track의 **실제** 박스, 모델이 본 문맥 ROI, 원래 입력 8시점, 행동 점수, 기존 사건 근거를 함께 표시한다. 예측 박스로 관측 공백을 메우지 않는다. 사람에게 묻는 내용은 새로 애매한 행동·대상 대응으로 한정한다.

EXP-0064의 별도 장소 오판 두 장면도 기존 자료를 재사용한다.

- `4-61 · 09-38-23_c · actor 0`, 16.667–19.000초
- `4-62 · 10-52-35_b · actor 1`, 85.667–88.000초

기존 답변은 박스 정렬 관찰이다. 대상이 실제로 서 있는지, 시간 구간이 맞는지, 넓힌 ROI에 **다른 넘는 사람**이 포함되는지 확인한다. 점수가 높다는 이유로 정상 라벨을 양성으로 바꾸거나 학습에 사용하지 않는다. ROI 혼입·라벨 차이·모델 오판을 영상 없이 확정하지 않는다.

### 5. 정상·접근·돌아가기 자료 보강

현재 다운로드된 원본/라벨에서 먼저 장소·카메라·날짜·촬영 시나리오별 목록을 만든다. 걷기, 문 앞 대기, 접근 후 돌아가기, 문을 만지지만 넘지 않기, 앉기처럼 구별할 행동의 **명시적 라벨 또는 검수된 구간**을 찾는다. 없는 유형은 확보되지 않았다고 기록한다. 미주석이나 낮은 모델 점수는 정상 정답이 아니다.

새 자료는 원본/연출 사건/멀티카메라 묶음과 해시로 기존 학습·검증·시험 및 보호45와 중복 검사한다. 재인코딩·동시 촬영 중복도 메타데이터와 내용으로 별도 확인한다. 기존 v3 분할과 EXP-0064 시험 결과는 보존하고, 보강 자료용 새 revision에서 학습용과 새 장소 평가용을 **모델 결과를 보기 전에** 나눈다. 새 평가 장소에는 넘기와 여러 정상 행동을 모두 포함시킨다. 확보 장소 수·행동별 독립 촬영 수·검수 비용을 실제 목록으로 보고한다.

보강 우선순위는 다른 장소의 정상·접근·돌아가기 사례다. 검증 정상행위가 앉기에만 치우친 문제도 새 revision에서 해소한다. 보호45의 오판 장면이나 이미 열어 본 시험을 몰래 학습으로 옮기지 않는다. 다음 학습은 이 진단과 데이터 목록을 근거로 입력/데이터 변경 축을 고정한 뒤 별도 결과로 수행한다.

## 완료 기준과 PR 작성 당시 검증 이력

- 이번 코드의 합성/파일 입출력 테스트 **21개 통과**. 타임스탬프 반열린 구간, 입력 부족과 낮은 점수 구분, 무관측 crossproduct 분리, 정상 구간 경계, 모델/영상/입력 불일치, 점수 결측, 기존 출력 보존을 확인했다.
- 실제45의 점수 재집계, 원본 의미 검수, 데이터 보강, 로컬 웹 등록·재생은 **미실행**이다. 전체 저장소 회귀나 독립 에이전트 검토를 수행했다고 주장하지 않는다.
- 로컬 실행 후 45영상/52참조 처리 여부, 006미확정/008보류, 각 진단 수, 필요한 검수, 자료 보강 현황을 실제 수치로 후속 결과 문서에 남긴다. precision/recall/F1과 EXP-0062 대비 개선은 정답·평가 범위가 충족되기 전 null이다.
- 기존 완료/검수 CLI에 후속 결과를 별도 등록하고 실제 화면에서 원본/입력 범위/점수 표시 및 재생을 확인한다. 원본·세부 출력·DB·가중치는 공개하지 않는다. 코드/비식별 집계와 실행/미실행 상태만 GitHub에 기록한다.
