# EXP-0064 첫 행동 학습·별도 비교 독립 검토

2026-11-07. **실제 실행·수치·입력 계약·기존 결과 보존 검증은 통과했으며 모델 채택은 보류한다.** 총괄의 후속 배정으로 준비부터 실제 결과와 공개 지표까지 읽기 전용으로 검토했다. 구현·원본·큐/DB 변경, GPU 실행·다운로드·추가 학습은 하지 않았다. 저장된 checkpoint는 CPU로만 검사했다.

전체 5,741개 입력, 수정 smoke의 32학습/4검증·실제 갱신 2회·시험 제외, 10 epoch의 2,250회 갱신 시도/2,248회 적용/2회 AMP 건너뜀을 확인했다. validation CE로 epoch 6을 선택한 뒤 전체 시험 1,431개를 한 번 평가했으며, 실제 점수·모델/optimizer 유한성·선택 기준을 독립 재계산했다. 원래 실패 attempt와 기존 큐 기록은 보존됐다. 수치·출처 복구 관련 100개 CPU 시험도 독립 통과했다.

공식 주석 참조 시험은 TP 582/FP 2/FN 0/TN 847이지만, **별도 장소의 음성 2개를 모두 오판했다.** 검증 음성은 앉기만 포함한다. 여덟 사용자 답변은 표본 박스 정렬 관찰이며 전체 행동 의미·정밀 시작/끝의 사람 정답이 아니다. 두 오판 구간은 이미 검수한 장면이라 기존 관찰을 재사용했고 반복 질문하지 않았다. 사람 기준 precision/recall/F1은 미측정이며 독립 일반화 성능을 입증하지 못했다.

별도 45개 비교에서 184,300 native 프레임·3,573개 점수·467개 후보 창, 모든 창의 실제 박스/PTS/ROI·batch 처리 시각 및 기존 원본/복사 출력 405개씩의 SHA를 확인했다. 이전 큐의 99개 job/attempt 각각의 행도 보존됐다. 후보는 사람·침입 사건·TP 수가 아니며 기존 사건 판단 변경 0은 보존 설계의 결과다. 관측 부족을 사람 검증 검출 FN으로 바꾸지 않는다.

전체 score에서 원본 시간 기준 입력 준비부터 batch 처리까지 최대 차이는 85.9초다. E01_040의 window `000141-1`에서 49.333333→135.233333초로 재현했다. 이는 **오프라인 비교**이며 wall-clock 실시간 알림 지연 측정이 아니다. 늦게 계산한 점수를 과거 시각의 알림으로 소급하지 않으며 실시간 침입 알림 개선을 주장할 근거가 없다.

| 최종 검토 대상 | SHA256 |
|---|---|
| [공개 보고서](../experiments/EXP-0064-results.md) | `d222f1e8f2055c8a0a68d799157ff2b5ec0622b81c74d9f8ff531b9e1aa37337` |
| `records/EXP-0064/metrics.json` | `ef39ca9ab51c1abebd3a31debf8bf5fa32b5879a008f95eaee1de3bf5eb688f2` |
| 실제 학습 result | `9a8bb01f62973b91d959c3e8f9d3bfc80d9ef2094dc6169905295bc44aa8eaf5` |
| 선택 best.pt | `8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73` |
| 실제 45개 inference result | `b465170efe203655deb76f857549101180e6ce56171ae510c69347595d7e34a8` |

39개 공개 지표의 수치 33개·미측정 null 6개, 출처 SHA·분모·범위를 확인했다. 공개 보고서는 위 실패·정답 부족·오프라인 한계와 채택 보류를 명시하며 완전한 사람 정답이나 독립 일반화를 주장하지 않는다. 실제 실행 source HEAD는 `166c96aa0ee3de18b8d1fe01f26b7430084adef3`, freeze-v5 SHA는 `de1b2368f7fda067422732d1e402da9631adca2361a7857b7bc17fca2ecafe5f`다. 실행 종료 확인 후 보고서만 갱신했다.

상세한 정책·반례·수정·실제 증거와 과거 단계별 기록은 [학습 준비·실제 결과 독립 검토](EXP-0063-training-readiness-review.md), [통합 준비·실제 결과 독립 검토](EXP-0064-integration-readiness-review.md)를 따른다. runtime의 `training-v2-result-independent-audit.json`, `training-checkpoints-v2-independent-audit.json`, `actual-inference-independent-audit.json`, `actual-inference-exit-proof.json`, `final-public-report-metrics-review.json`에 독립 산술·종료 근거를 보존했다. 초기 통합 v1 계획 재생성 전 바이트 보존은 인증하지 않지만 실제 v2 전체 계획은 별도 oracle로 대조했다.

계산·계약·보존 검토의 미해결 차단 사유는 없다. 충분한 사람 정답과 별도 장소 정상/접근/돌아가기 평가 부족은 성능·채택의 미해결 한계다. 추가 튜닝을 자동 시작하지 않는다. 실제 등록·브라우저 재생/되감기/polling·GitHub 게시 완료는 본 검토에서 인증하지 않았으며 총괄의 별도 전달 증거가 필요하다. 최종 보고서·등록·검토 문서의 합동 커밋은 총괄이 수행한다.
