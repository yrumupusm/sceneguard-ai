# MVP-0001 — 결과 요약 및 적용 판단

2026-10-29, EXP-0017 실제 비교까지 반영. **기능 프로토타입은 세 원본 처리와 근거 저장을 마쳤고, 고정 prompt 개선 비교도 4개 GPU 작업·20개 응답으로 완료했다. 그러나 접근/대기와 넘기 시도를 구분하는 행동 성능 개선은 확인되지 않아 수정 prompt와 운영 채택은 보류한다.** 6개 q 창은 다섯 개 no-crossing, 한 개 attempt/progress positive이며 primary positive는 0개다. 법적 무단침입·출입 권한을 판단하는 도구가 아니다.

## 최신 개선 결과 — EXP-0017

[새 보고서](EXP-0017-prompt-evidence-results.md)의 단일 prompt 변경에서 q 비시도 5개의 잘못된 후보 창 수는 B 2→3, C 2→2다. q04 C 후보는 유지됐지만 완료를 관찰했다고 과장했고, B는 계속 놓쳤다. 별도 사용자 검수 v의 시도 양성 후보 1→0, 비사건 후보 1→1로, 후보 감소는 양성 소실이다. v 네 창은 두 source group이며 완료는 v01/v03 모두 미평가다. 일반화 성능이나 최적 모델을 주장하지 않는다.

21개 새 CPU 계약 테스트와 실제 입력/출력 대조는 통과했다. 코드/실행 성공과 성능 개선은 별개다. 추가 튜닝·새 모델 없이 이번 비교를 종료하고 원래 구성을 유지한다. 원래 구성도 행동 성능 부족/채택 보류다. 독립 검토·웹·GitHub의 각각의 전달 증거는 [EXP-0017 전달 기록](EXP-0017-delivery.md)에 남긴다. EXP-0016 차단 기록과 아래 EXP-0013/14/15 이력은 보존한다.

## 완료 상태

| 영역 | 확인된 결과 | 상태 |
|---|---|---|
| 기능 통합 | 전체화면/고정 ROI Qwen 구성에서 원본 007·030·013을 끝까지 처리하고 시간창, 후보/판단 불가, 겹치는 후보 정리, 근거 구간을 기록했다. | 프로토타입 동작 확인 |
| 자동 검증 | MVP 코드 검증은 EXP-0013에 기록. EXP-0014 테스트 21개 및 EXP-0015 label revision focused CPU 테스트 16개 통과. | 해당 범위 통과 |
| 저장 결과 평가 | EXP-0013의 고정 12개 창, B/C 24개 출력 레코드를 CPU만으로 추적·비교. 24/24 연결 및 88개 소비 파일의 불변성 확인. | 재현 가능한 추출 완료 |
| 행동 정답 평가 (EXP-0015 revision) | q01/q02/q03/q05/q06는 해당 5초에 넘기 시도/진행이 확인되지 않음(5개 no-crossing). q04는 시도/진행 positive 1개, 클립은 완료 전에 끝남. primary q01/q02/q05에는 positive 0개. | revision 라벨 적용 완료; 성능 점수 산출 불가 |
| 게시/화면 | EXP-0015는 기존 결과 화면에 등록됐고 실제 브라우저에서 담당 카드·보고서·metrics 그래프·검토·6개 영상 재생/seek를 확인했다. GitHub `main` 게시와 report/metrics/review/binding 원격 해시도 별도 확인했다. | 등록·로컬 화면·GitHub 확인 통과 |

상세 비교는 [EXP-0013](EXP-0013-mvp-comparison.md), 저장 출력 평가 [EXP-0014](EXP-0014-mvp-small-evaluation.md), 사용자 라벨 revision [EXP-0015](EXP-0015-user-label-revision.md), [고정 manifest](../../configs/mvp_small_eval_manifest.json)에 있다. EXP-0011/12의 자원 차단 기록과 EXP-0013 원문·공식 라벨은 보존한다. 해당 표본은 개발/진단이며 완전한 사전 등록·독립 테스트가 아니다.

## B/C 출력 비교 — 정답 성능으로 읽지 않기

| 같은 12개 창 | B 전체 화면 | C 고정 ROI | 해석 |
|---|---:|---:|---|
| Candidate 출력 | 4/12 | 5/12 | 라벨 모르는 11개가 포함된 출력 빈도. 참양성/오탐 수가 아님. |
| Candidate 없음 | 8/12 | 7/12 | 정상 판정 또는 실제 누락으로 해석할 수 없음. |
| 원문 schema 준수 / 허용 후처리 schema 유효 | 4/12 / 12/12 | 8/12 / 12/12 | 형식 준수 차이이며 행동 이해 향상이 아님. |
| completion observed 주장 / 그중 climbing action 없는 주장 | 8 / 4 | 7 / 3 | 완료 주장은 독립된 문장 지원 검사에서 과도하게 나옴. 영상 완료 정답이 아님. |

두 방법 모두 사용자가 말한 약90초 장면이 든 87.5–92.5초 창에 candidate를 출력했다. 이는 행동 존재와 부분적으로 맞지만, 세 사람 전체 검출·정확 onset·개인별 완료나 설명의 시각적 사실성은 입증하지 않는다. 84초 사용 관찰은 그 순간 서기/접근에 한정되어 82.5–87.5초 전체를 음성 라벨로 만들지 않는다. 007의 한 프레임 박스 변화는 ChatGPT 시각 검토이며 사용자 확정 정답이 아니다. 030 EOF에는 사람 정답이 없다. 영상 끝까지 집단 넘기가 완료되지 않았다는 기존 관찰은 031에만 적용한다.

C4/013의 네 C 레코드는 B와 정확 재사용됐다. 이는 ROI 구성 비교에서 독립적인 성공이 아니다. 공식 annotation 시각은 행동 정답으로 전환하지 않았다. **EXP-0014 당시**에는 confirmed primary positive=0, confirmed negative=0, verified negative duration=0초였으므로 점수 산출이 불가했다. 이후의 최신 사용자 확인은 아래 EXP-0015 revision 단락을 따른다.

## 실행 및 재현

실제 전체 영상 실행의 설정·비용·산출물은 EXP-0013을 따른다. EXP-0014는 기존 EXP-0013 저장 JSON·창/PTS/입력 메타데이터만 CPU로 읽었으며 모델·가중치·미디어 디코더·GPU 큐·네트워크를 호출하지 않았다.

```bash
python3 scripts/evaluate_mvp_small.py
python3 -m unittest tests_mvp.test_events tests_mvp.test_small_evaluation -v
```

사용자 확인 후 EXP-0015는 primary no-crossing 3개(q01/q02/q05)에서 B 2개/C 1개 후보, 진단 no-crossing 2개(q03/q06)와 attempt-positive 1개(q04)에서 B 0개/C 2개 후보를 기록했다. q04는 시도/진행 positive이며 완료 전에 창이 끝난다. 확인된 다섯 no-crossing 창 가운데 B/C 각각 두 개에서 candidate가 나왔다. q06의 no-person/no-event 확인 범위는 E01_030 155–160초뿐이다. E01_031 영상 종료 시점에서 완료되지 않은 움직임 관찰을 E01_030에 적용하지 않는다. 별도 부분 양성 d030_90과 미확정 사례들은 no-crossing 5개에 포함하지 않았다. 총 표본은 개발용이라 accuracy/precision/recall/F1/FPR/시간당 오탐을 만들지 않는다. 이 결과는 행동 성능 충족이나 채택 근거가 아니다.

EXP-0014 시점 요약은 역사 기록이다: 당시에는 사용자 revision이 없어 확정 음성 창 0으로 기록됐다. 최신 라벨 상태는 [EXP-0015](EXP-0015-user-label-revision.md)이며 그 과거 요약을 지우지 않고 이 단락이 현재 해석을 우선한다.

EXP-0016 당시에는 단일 prompt 비교 구현/CPU 검증 후 GPU 여유가 6144 MiB gate보다 작아 추론 없이 차단 종료했다. 그 결과와 등록은 [EXP-0016](EXP-0016-prompt-evidence-rubric.md)에 보존한다. 이후 자원 확보 후 동일 사양의 새 실행은 EXP-0017로 분리했으며 최신 결론은 위와 같다.
