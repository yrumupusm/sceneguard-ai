# EXP-0065 학교 CCTV 저장 행동 점수·입력 진단

2026-11-07 KST. **기존 45영상·공식 시간 참조 52개를 저장된 점수만으로 진단했다.** 시간 후보33·낮은 점수13·부분 관측5·참조 안 실제 관측 없음1이다. EXP-0062 AFTER에서 확인되지 않은15참조는 시간 후보7·낮은 점수5·부분 관측3이다. 시간 후보는 같은 사람·같은 문에 대한 행동 TP나 새 침입 확인이 아니며, 행동 precision/recall/F1·침입 개선량은 모두 `null`이다.

GPU·모델 실행·학습·가중치 읽기·임계값 변경·전체 원본 미디어 해시는 수행하지 않았다. PR2 `d0e813e`를 포함한 `exp0065-followup`에서 CPU 진단 도구와 해당 시험만 수정했다. 기존 출력·정답·DB·기본 모델을 보존하며 commit/push는 총괄 소유다.

## 고정 자료와 실제 PR 검토

실행 Task는 `task_7f2aba8173dc`, Dispatch는 `ctx_f6bdafb3cc3f`다. 작업 시작에 `docs/WEB_REVIEW_WORKFLOW.md`의 기존 labvenv 명령 `pending --include-acknowledged`가 성공했고 `requests: []`였다. 조회 실패를 검수 없음으로 바꾸지 않았으며 새 검수 요청/답변 쓰기는 하지 않았다.

| 실제 입력 | SHA256 |
| --- | --- |
| EXP-0063 `baseline/attempt-002/baseline-lock.json` | `3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40` |
| EXP-0064 `regression-plan-v2/manifest.json` | `f8bea6c8b4b36d5d09daf8f3b43a7e8923319ef5bde3b5c4e5cd5f00f0f7cb17` |
| EXP-0064 all45 attempt `3825ad63d2254611921ccb7b349c2feb/result.json` | `b465170efe203655deb76f857549101180e6ce56171ae510c69347595d7e34a8` |
| 잠긴 `run-001/after-manifest.json` | `c3b43879997033661ac84eb8e8406e328fee95b6779a97ace1f317500a602d19` |
| 잠긴 `run-001/after-scoring.json` | `cc329d88869d5a7b5815693973945158862c3d6900f95ae59a8a029379e4099a` |
| 잠긴 `run-001/evaluation-manifest.json` | `897fb1f18ed63ec61dd8e60f8e2a03e75e7b8ff5e0b39d3ff1dcfb2588ab61dc` |
| 기존 `regression-plan-v2/integration-execution-report-v1.json` | `c615a02b88cd17c41c4b6a6193fc729667cae77f7ec8d02a143766f9c033466b` |

기준 파일의 `run-001`은 `outputs/validation/false-confirmation-guard-all45-v1/run-001/`이다. 나머지 상대 결과 경로는 `outputs/action-recognition/` 아래다. 선택 모델의 고정 식별자는 `best.pt` SHA `8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73`, threshold는0.5다. 현재 가중치 파일을 다시 읽는 대신 저장 점수·추론 결과의 입력 계약과 비교했다.

PR의 로컬 연결과 계약에서 다음을 보완했다.

1. `evaluation-manifest.json`은 `videos[]` 정답 파일이 아닌 provenance envelope다. 새 정답을 만들지 않고 lock의 실제 `after-manifest.json`을 연결했다. `--evaluation-receipt`로 envelope 자체의 잠긴 해시와 reference/report의 `output_hashes` 연결도 검증한다.
2. PR은 불완전 창의 **명목상8시점** 중 하나가 참조와 겹치면 부분 관측으로 셌다. 이제 missing mask를 제외한 **실제 관측 시점**만 사용하고, mask가 frozen sample의 track 관측과 같은지도 대조한다. 명목상 겹침은 별도 필드에 보존한다. 020의 두 번째 참조가 이 차이로 부분 관측에서 관측 없음으로 바뀌었다.
3. 기준 report의 TP truth-ID 집합만 믿지 않고, 중복/미등록 truth-ID·누락 ID·TP/FN/미확정 count를 검증해 각 영상의 전체 참조가 matched/missed로 정확히 나뉘도록 했다.
4. 현재 점수의 snapshot만 만드는 데서 더 나아가 기존 실행 report에 저장된 **45개 JSONL 원래 해시**와 전부 대조했다. 모델·영상·plan·tracking·native sample provenance·queue attempt·후보 flag·flush 시각·예정 전체 창·영상별/전체 집계도 검증한다. 유효한 숫자로 점수만 바꿔도 원래 해시가 다르면 거절한다.

고정 해시·45영상·52참조 검사는 유지했다. 실행 중 읽은97개 JSON/JSONL snapshot은 완료 직전에 다시 바이트 대조했다. 전체 미디어나 원본 tracking을 새로 해시한 것이 아니라, 저장된 계획/점수와 과거 provenance의 일치를 검사했다.

## 전체 및 기준37/15 분리

| 진단 | 전체52 | 기준 확인37 | 기준 미확인15 |
| --- | ---: | ---: | ---: |
| 시간 후보 | 33 | 26 | 7 |
| 낮은 점수 | 13 | 8 | 5 |
| 부분 관측 | 5 | 2 | 3 |
| 참조 안 실제 관측 없음 | 1 | 1 | 0 |

시간 관계는 실제 sample 중 하나가 공식 반열린 `[start,end)` 안에 있는지로 정한다. 낮은 점수는 겹치는 완전 입력이 있지만 모두0.5미만이라는 뜻이다. 부분 관측은 완전 입력이 없고 불완전 창의 실제 관측 중 하나가 참조 안에 있다는 뜻이다. 관측 없음은 이 저장된3fps 관측/창 안에서의 진단이며 실제 영상에 사람이 없었다거나 검출기 실패라는 원인 판정이 아니다.

020 `official-row-001`(C5,73.366667–78.333333초)은 완전 입력0, 참조 안 실제 부분 관측0, 명목상만 겹치는 부분 창2개다. 이 참조는 이전 기준에서는 확인됐으므로 현재 행동 입력 부족을 기준 확인 FN이나 성능 저하로 바꾸지 않는다. 기준과 행동 입력의 관측 방식·단위가 다르다.

006은 `truth_basis=unresolved`, 시간 미확정1개를 그대로 두고52행에 임의 추가하지 않았다. 008의 공식 참조에는 시간 후보가 있지만 **기존 의미 검수 보류는 그대로**다. 공식 matching이나 이번 시간 겹침이 보류를 해소하지 않는다. 공식 시각의 기존 frame-origin/onset 한계도 그대로다.

## 공식52참조 전수 표

표의 시각과 최대 점수는 표시용 반올림이며 CSV/JSON에는 원래 정밀도를 보존한다. 기준 확인은 EXP-0062 AFTER의 공식 참조 matching 여부다. 새로운 actor/gate 행동 정답 열이 아니다. `관측 없음`도 detector FN으로 확정하지 않는다.

| 영상 | 참조 row | 문 | 시작–끝 초 | 기준 확인 | 진단 | 완전/후보/부분 창 | 최대 점수 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 001 | 000 | C1_fence | 60.867–95.133 | 예 | 시간 후보 | 58/34/33 | 0.999581 |
| 002 | 000 | C1_fence | 58.300–76.133 | 예 | 시간 후보 | 2/2/15 | 0.998121 |
| 003 | 000 | C1_fence | 46.733–79.567 | 예 | 시간 후보 | 18/14/65 | 0.999762 |
| 004 | 000 | C2_fence | 60.100–62.267 | 예 | 낮은 점수 | 10/0/0 | 0.067240 |
| 005 | 000 | C3_fence | 58.333–74.133 | 예 | 시간 후보 | 9/5/31 | 0.933066 |
| 007 | 000 | C3_fence | 63.100–73.733 | 예 | 시간 후보 | 10/5/16 | 0.998817 |
| 008 | 000 | C8_fence | 63.300–73.033 | 예 | 시간 후보 | 34/1/8 | 0.551211 |
| 009 | 000 | C1_fence | 66.400–77.833 | 예 | 시간 후보 | 5/4/6 | 0.926968 |
| 010 | 000 | C4_fence | 62.067–66.033 | 예 | 시간 후보 | 2/2/2 | 0.891717 |
| 011 | 000 | C4_fence | 67.700–76.433 | 아니오 | 낮은 점수 | 1/0/5 | 0.183887 |
| 012 | 000 | C4_fence | 53.433–76.133 | 예 | 시간 후보 | 19/17/20 | 0.981453 |
| 013 | 000 | C4_fence | 60.600–66.067 | 아니오 | 낮은 점수 | 16/0/12 | 0.080864 |
| 014 | 000 | C5_fence | 67.167–77.167 | 예 | 낮은 점수 | 6/0/11 | 0.001652 |
| 015 | 000 | C4_fence | 49.867–69.633 | 아니오 | 시간 후보 | 12/4/24 | 0.888081 |
| 016 | 000 | C5_fence | 69.233–76.967 | 예 | 시간 후보 | 4/1/13 | 0.987216 |
| 017 | 000 | C4_fence | 79.467–86.633 | 예 | 시간 후보 | 14/10/10 | 0.970212 |
| 018 | 000 | C5_fence | 68.267–75.067 | 예 | 시간 후보 | 4/1/5 | 0.649801 |
| 019 | 000 | C4_fence | 75.000–87.500 | 예 | 시간 후보 | 9/2/15 | 0.839471 |
| 020 | 000 | C5_fence | 6.467–20.033 | 예 | 낮은 점수 | 1/0/40 | 0.021206 |
| 020 | 001 | C5_fence | 73.367–78.333 | 예 | 관측 없음 | 0/0/0 | — |
| 021 | 000 | C5_fence | 64.233–78.667 | 아니오 | 시간 후보 | 11/3/27 | 0.985950 |
| 022 | 000 | C1_fence | 70.300–78.000 | 예 | 시간 후보 | 5/3/7 | 0.924824 |
| 023 | 000 | C4_fence | 62.233–70.133 | 예 | 낮은 점수 | 2/0/4 | 0.047825 |
| 024 | 000 | C1_fence | 67.400–75.033 | 예 | 시간 후보 | 1/1/4 | 0.529415 |
| 025 | 000 | C1_fence | 66.133–76.333 | 예 | 시간 후보 | 6/3/7 | 0.653127 |
| 026 | 000 | C6_fence | 63.633–70.267 | 아니오 | 시간 후보 | 6/6/3 | 0.990064 |
| 027 | 000 | C1_fence | 67.933–80.933 | 예 | 시간 후보 | 5/1/10 | 0.829768 |
| 028 | 000 | C6_fence | 44.700–69.233 | 아니오 | 시간 후보 | 6/5/13 | 0.999742 |
| 029 | 000 | C1_fence | 62.200–89.133 | 예 | 시간 후보 | 12/8/26 | 0.951729 |
| 029 | 001 | C1_fence | 135.267–143.867 | 예 | 부분 관측 | 0/0/11 | — |
| 030 | 000 | C6_fence | 88.933–96.933 | 예 | 시간 후보 | 1/1/24 | 0.824603 |
| 031 | 000 | C7_fence | 43.600–120.167 | 예 | 시간 후보 | 13/1/82 | 0.521007 |
| 032 | 000 | C3_fence | 55.000–72.433 | 예 | 낮은 점수 | 10/0/12 | 0.122313 |
| 033 | 000 | C4_fence | 35.933–67.667 | 예 | 시간 후보 | 79/1/64 | 0.790773 |
| 034 | 000 | C1_fence | 26.633–66.700 | 아니오 | 시간 후보 | 7/5/22 | 0.954774 |
| 035 | 000 | C4_fence | 0.033–2.300 | 아니오 | 부분 관측 | 0/0/4 | — |
| 035 | 001 | C4_fence | 60.600–63.533 | 아니오 | 낮은 점수 | 2/0/9 | 0.287318 |
| 035 | 002 | C4_fence | 104.000–109.467 | 예 | 낮은 점수 | 6/0/15 | 0.124532 |
| 036 | 001 | C4_fence | 16.667–32.600 | 아니오 | 낮은 점수 | 36/0/73 | 0.280025 |
| 036 | 000 | C4_fence | 49.433–74.533 | 예 | 시간 후보 | 26/8/49 | 0.818882 |
| 037 | 000 | C4_fence | 65.700–73.533 | 예 | 시간 후보 | 9/1/23 | 0.631197 |
| 038 | 000 | C5_fence | 37.633–114.567 | 예 | 시간 후보 | 69/17/97 | 0.964589 |
| 039 | 000 | C4_fence | 12.100–33.500 | 예 | 시간 후보 | 57/8/44 | 0.914138 |
| 039 | 002 | C4_fence | 53.300–76.767 | 아니오 | 시간 후보 | 79/1/198 | 0.652906 |
| 039 | 001 | C4_fence | 78.600–117.967 | 예 | 시간 후보 | 198/6/231 | 0.795142 |
| 040 | 000 | C1_fence | 65.267–79.433 | 예 | 부분 관측 | 0/0/5 | — |
| 041 | 000 | C1_fence | 64.067–80.333 | 예 | 낮은 점수 | 3/0/18 | 0.153676 |
| 042 | 000 | C1_fence | 69.167–78.467 | 아니오 | 부분 관측 | 0/0/3 | — |
| 043 | 000 | C4_fence | 63.633–72.067 | 아니오 | 시간 후보 | 3/1/19 | 0.675069 |
| 044 | 000 | C1_fence | 59.433–79.267 | 아니오 | 부분 관측 | 0/0/6 | — |
| 045 | 001 | C4_fence | 9.000–14.433 | 아니오 | 낮은 점수 | 15/0/29 | 0.156362 |
| 045 | 000 | C4_fence | 56.800–110.900 | 예 | 낮은 점수 | 49/0/136 | 0.496216 |

## 카메라별 분포와 대표 검수 제안

| 카메라 | 시간 후보 | 낮은 점수 | 부분 관측 | 관측 없음 |
| --- | ---: | ---: | ---: | ---: |
| C1 | 10 | 1 | 4 | 0 |
| C2 | 0 | 1 | 0 | 0 |
| C3 | 2 | 1 | 0 | 0 |
| C4 | 12 | 8 | 1 | 0 |
| C5 | 4 | 2 | 0 | 1 |
| C6 | 3 | 0 | 0 | 0 |
| C7 | 1 | 0 | 0 | 0 |
| C8 | 1 | 0 | 0 | 0 |

`review-selection.json`은 기준 matched/missed×진단×카메라의 각 존재하는 층에서1개를 제안한다. 같은 층에서는 저장 최대 점수가 높은 항목, 동률이면 ID 순서로 정했다. 모델/임계값 선택용이 아니며 실제 등록 질문 목록도 아니다. 선택21개(기준 미확인7·확인14), 미선택31개 전부와 사유를 기록했다. C1–C8을 모두 포함한다. 이미 검수한 장면의 새로운 요청 여부와 매체 구성은 총괄이 결정한다.

이21개는 진단상 대표 제안이며 총괄의 실제 렌더 선택과 구분한다. 실제 `outputs/action-recognition/exp0065/review-media-v2/review-manifest.json`은 기준 미확인15개 전부와 카메라/진단 대조를 포함한 학교23개 및 별도 장소 오판2개를 기록한다. 실제 매체 선택·입력·출력 근거는 그 manifest를 따른다. 이 worker는 해당 매체의 재생이나 의미 검수 완료를 인증하지 않는다.

기준 미확인15의 우선 대표는 다음7개다. 미선택8개도 같은 유형의 다른 장면으로 보존하며, 하나의 대표가 그 전체 정답을 대신하지 않는다.

| 영상·참조 | 카메라 | 진단 | 선정 이유 |
| --- | --- | --- | --- |
| 034 official-row-000 | C1 | 시간 후보 | 해당 미확인/유형/카메라 층 대표 |
| 015 official-row-000 | C4 | 시간 후보 | 해당 미확인/유형/카메라 층 대표 |
| 021 official-row-000 | C5 | 시간 후보 | 해당 미확인/유형/카메라 층 대표 |
| 028 official-row-000 | C6 | 시간 후보 | 해당 미확인/유형/카메라 층 대표 |
| 042 official-row-000 | C1 | 부분 관측 | 해당 미확인/유형/카메라 층 대표 |
| 035 official-row-000 | C4 | 부분 관측 | 해당 미확인/유형/카메라 층 대표 |
| 035 official-row-001 | C4 | 낮은 점수 | 해당 미확인/유형/카메라 층 대표 |

기준 확인 대조에는 C1/C3/C4/C5/C6/C7/C8 시간 후보, C1 부분 관측, C1/C2/C3/C4/C5 낮은 점수, C5 관측 없음 대표가 있다. 특히020의 명목상 부분 창만 남은 경우를 별도 자료로 확인해야 한다. 008 대표는 기존 보류를 함께 표시해야 한다.

남은 질문은 (1) 입력 track이 공식 사건의 그 사람·그 문인지, (2) 확대 ROI에 다른 넘는 사람이 섞였는지, (3) 입력 시점이 실제 행동을 담는지, (4) 불완전 관측이 해당 사람의 동작 중 어디까지를 담는지다. 낮은 점수의 원인을 배경 학습·행동 실패로 단정하지 않는다. 공식 참조 밖 후보285창은 미주석일 수 있어 자동 음성이 아니다.

기존 [EXP-0062 장면 관찰](EXP-0062-user-scene-review.md)의005/033 이동 방향과037/043 시각 관찰, [EXP-0060 검수](EXP-0060-user-scene-review.md)의 구간별 판단은 원래 문맥으로만 재사용한다. 예를 들어043 약67초 시작·70/72초 두 사람 완료 관찰이 각 모델 track의 일대일 대응을 확정하지 않으며,039124.233초 수용이 이번53.3–76.767초 참조의 모델 입력을 검수한 것도 아니다. 같은 영상이라는 이유로 새 입력 전체를 승인하지 않는다.

기존 정상 참조11구간은004/007/021/030에 있다. 8시점이 모두 구간 안인 점수 membership63개 중 후보 membership12개이며, 경계에 걸친 창은 별도로 보존했다. 이들 역시 입력 actor/문 대응 전에는 행동 false alarm으로 확정하지 않는다. 같은 track의 연속 후보를 묶은193개 열람 구간은 독립 사건/인원 수가 아니다. 총3,573점수·467후보, 부분 관측5,057창과 빈 track×시간 조합179,245개를 원래 정의대로 보존했다.

## 실제 명령·검증·해시

기존 `.venv-cv-batch02`만 사용했고 의존성을 설치하지 않았다. 실제 실행 argv와 코드 SHA는 `runtime/action-recognition/exp0065/coverage/diagnosis-command.json` 및 `.sh`, stdout/오류는 `diagnosis.log`에 남겼다. 실제 명령은 다음과 같다.

```bash
.venv-cv-batch02/bin/python scripts/audit_action_event_coverage.py \
  --baseline-lock outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json \
  --plan outputs/action-recognition/exp0064/regression-plan-v2/manifest.json \
  --inference-result outputs/action-recognition/exp0064/queued-inference/all45/3825ad63d2254611921ccb7b349c2feb/result.json \
  --references outputs/validation/false-confirmation-guard-all45-v1/run-001/after-manifest.json \
  --baseline-report outputs/validation/false-confirmation-guard-all45-v1/run-001/after-scoring.json \
  --evaluation-receipt outputs/validation/false-confirmation-guard-all45-v1/run-001/evaluation-manifest.json \
  --inference-receipt outputs/action-recognition/exp0064/regression-plan-v2/integration-execution-report-v1.json \
  --output outputs/action-recognition/exp0065/coverage-v1

.venv-cv-batch02/bin/python -m unittest discover -s tests -p 'test_action_event_coverage.py' -v
```

실제 진단 exit0, 관련 CPU 시험은 기존21+추가10, **31개 통과**다. 추가 시험은 명목상만 겹친 부분 관측·반열린 경계·실제 missing mask 불일치·정수가 아닌 missing index·tracking/native/queue provenance·baseline truth-ID/count 위반·기존 score receipt 변조/결측·정상 receipt 성공·잘못 연결된 evaluation receipt·카메라/분류 대표의 누락 방지를 포함한다. 로그는 `test-action-event-coverage.log`다. 전체 저장소 회귀나 행동 성능 시험이라고 부르지 않는다. `git diff --check`도 통과했다.

독립 담당은 별도 저장자료 oracle로52개 각 행과 창 ID·정상11구간·193묶음·97개 입력 해시·원래 score receipt·37/15 분리를 대조해 일치를 확인했다. 최초 nominal 기준33/13/6/0과 수정된 실제 관측33/13/5/1을 구분한다. 독립 evidence는 `runtime/action-recognition/exp0065/independent/`다.

| 이번 산출물 | SHA256 |
| --- | --- |
| `scripts/audit_action_event_coverage.py` | `1291ea652a3627a44964535c398e11a4307345b9a2bd57c9f50337679fe2cb79` |
| `tests/test_action_event_coverage.py` | `2a2ebb139605aab352c45980682f95771805e1f052610a7259b9d22d4eb7516e` |
| `outputs/action-recognition/exp0065/coverage-v1/summary.json` | `99db42a936988b94054fb856f593cb8edbae4a0df1619553c39c641c291e69ca` |
| `outputs/action-recognition/exp0065/coverage-v1/per-video.json` | `9d5cc2359cbc1f2bafdea0b9157c57a5d3202e1578ab2c9da3113c713e7b4295` |
| `outputs/action-recognition/exp0065/coverage-v1/event-diagnostics.csv` | `c5e88528176bc8a7993ae8611515fee1d3f3fe7c2ecc1c7a3cc4852431c5b412` |
| `outputs/action-recognition/exp0065/coverage-v1/review-selection.json` | `1689b0f1cd68c156ba805f11549e5690ceb551635728e8e6e915f1ed9b242c17` |

이번 worker의 실제 전수 진단·PR 보완·검수 대표 제안은 완료했다. 새 의미 검수·로컬 매체 생성/등록·브라우저 전달은 총괄 소유이며 이 문서가 완료를 주장하지 않는다. 자료 보강은 다른 worker의 별도 목록을 따른다. 기존45영상은 계속 회귀/진단 전용이며 학습·검증·threshold 선택이나 향후 독립 최종 시험으로 재사용하지 않는다. 다음 학습·모델 변경은 이번 범위에 포함하지 않는다.
