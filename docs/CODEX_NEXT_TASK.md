# 다음 작업 — EXP-0014 사람 확인 후 CPU 평가 revision

2026-10-28. 최신 지침은 [EXP-0014](experiments/EXP-0014-mvp-small-evaluation.md) 저장 출력 평가·문서 마감까지 완료됐다. 이 문서가 GitHub에 게시되고 결과가 기존 화면에 반영됐는지는 [HANDOFF](HANDOFF.md) 및 전달 receipt로 확인한다.

## 현재 상태

- 최신 코드/문서 지침의 기준 commit: `c73d217`.
- EXP-0013 원본 전체 실행과 후보/근거 저장은 기능 프로토타입으로 완료. 자동 테스트와 실행 기능 완료는 행동 정확성 입증과 다르다.
- EXP-0014는 사전 고정한 12개 5초 창, B/C 24개 저장 응답을 새 GPU 실행 없이 추출·대조했다. CPU 테스트와 source immutability를 검증했다.
- 표본 선정은 inference 및 aggregate report 노출 뒤였고 itemized 응답을 열기 전이다. 결과 인식 가능한 개발/진단 표본이며 blind/independent test가 아니다.
- 현재 사람 근거는 030 87.5–92.5초 창 안 약90초 넘기 행동 존재라는 **부분 양성 관찰** 하나다. 전체 창의 onset·사람별 완료는 정답이 아니다. 030의 84초 관찰도 순간적인 서기/접근뿐이다. 031 종료 시 집단 미완료는 030에 이전하지 않는다. 007의 56.633→56.667 박스 관찰은 ChatGPT 시각 초안이다.
- 전체 12개 중 full-window 확인 양성 0, 확인 음성 0, 검수 전 uncertain 11. 따라서 정확도/precision/recall/F1/FPR/시간당 오탐은 null. Candidate 빈도는 정답률이 아니다.
- 007/030 여섯 개 이하의 원본 전용 질문 클립은 Git 제외 로컬 `outputs/mvp0001_evaluation/EXP-0014/question_clips/`에 보관한다. 파일은 q01–q06이며 다음 질문에서 실제 질문 목적과 원본 PTS를 표시한다.
- EXP-0014 기본 채택은 보류. Astra high 독립 검토 2회가 최종 report/metrics hash까지 통과했다. 초기 review의 metrics schema 차단은 여섯 진단 graph row를 추가하고 기존 validator로 재검증해 해소했다. Reviews: [초기 산술 검토](reviews/EXP-0014-coordinator-review.md), [최종 등록 준비 검토](reviews/EXP-0014-delivery-review.md). `complete` 등록, GitHub 게시, 원격 report/metrics/review/binding 해시 확인, 기존 서비스의 실제 화면 검증이 통과했다. 요약의 행동 성능은 여전히 미확정이다.

## 다음 단계

1. 완료 등록 결과는 EXP-0014 `accepted_for_comparison`/adoption hold다. Metrics schema 결함을 수정하고 report/metrics/source 해시 및 validator 결과를 독립 검토했다. 이는 행동 성능 승인이 아니다.
2. 기존 사용자 관찰을 재질문하지 않는다. Codex는 필요 구간을 한 번에 최대 6개로 모아 원본 전용 클립을 제시한다. 질문별 대답은 `넘기 시도/진행 보임`, `이 구간에는 안 보임`, `가려져 판단 불가`로 받으며, 동작 완료·개인별 행위는 별도 확정 근거가 없으면 미정이다.
3. 새 사람 답변을 받으면 선택 manifest를 불변으로 두고 label revision에 출처·정확 구간·범위·검수자 입력 상태를 기록한다. 한 순간의 부재를 5초 음성으로 일반화하지 않는다. 새로 확인되지 않은 구간은 `uncertain`을 유지한다.
4. EXP-0013의 선택된 창 응답만 다시 CPU 평가한다. 필요한 분모가 확보되지 않으면 점수는 계속 null이다. C4의 exact reuse, 013의 과거 노출, 카메라/세션 중복을 독립 증거로 세지 않는다.
5. EXP-0014 완료 등록, GitHub 게시, 실제 local browser 검증을 완료했다. 담당3 카드, report, 6 metrics, 2 graphs, 검토문, q01–q06 원본 영상 재생/seek가 확인됐다. 다음 작업은 한 번의 사람 검수 응답을 label revision으로 기록하고 같은 CPU 평가를 재집계하는 것이다. 사람 확인이 충분하지 않으면 “평가 수행 완료·행동 성능 미확정/부족”으로 종료한다.

## 범위와 금지

- 새 GPU/VLM/CV 추론, 모델·가중치 추가, 재학습, threshold·prompt·ROI·판정 규칙 튜닝, 웹 기능 확장은 시작하지 않는다.
- 원본 영상·검수 클립·프레임·가중치·raw 모델 응답·로컬 artifact manifest·runtime DB/log/receipt는 GitHub에 넣지 않는다.
- 사람이 검수하지 않은 unknown/indeterminate/parse failure/ROI 밖을 TN이나 정상 행동으로 세지 않는다. 공식 annotation 시각은 시각 참고이며 사람 행동 ground truth와 혼합하지 않는다.
- 수치 성능이 여전히 확정되지 않으면 임의 채택 기준을 만들거나 개발 표본을 독립 테스트로 이름 바꾸지 말고 멈춘다.

## 기준 문서

- [평가 계획](data/MVP_SMALL_EVALUATION_PLAN.md)
- [출처 정정](data/EXP-0013-observation-errata.md)
- [EXP-0014 평가 보고서](experiments/EXP-0014-mvp-small-evaluation.md)
- [종합 요약](experiments/MVP-0001-summary.md)
- [실험 완료 등록 절차](orchestration/EXPERIMENT_DELIVERY.md)
