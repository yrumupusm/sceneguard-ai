# EXP-0017 — EXP-0016 고정 프롬프트 비교 재개

2026-10-29 KST (2026-10-28 UTC). 사용자가 Git 인증을 마치고 GPU 여유를 확인해 이전 작업을 재개하도록 지시했다. 최초 coordinator snapshot은 RTX 3080 10240 MiB 중 used 1925 / free 8129 MiB, utilization 22%였다. 기존 최소 여유 6144 MiB를 유지하며 각 실행 전 다시 검사한다.

## 범위와 종료 조건

[EXP-0016 사양](EXP-0016-prompt-evidence-rubric.md)과 [ADR-0017](../decisions/ADR-0017-qwen-temporal-evidence-prompt.md)을 그대로 실행한다. 변경 축은 이미 고정한 공통 prompt 하나다. EXP-0016의 완료 등록은 GPU 차단 기록으로 불변 보존하고 실제 재개는 EXP-0017로 별도 전달한다. 새 추론 구현·모델·가중치·프롬프트 튜닝은 없다.

| 순서 | 기존 queue phase | view | 실제 새 생성 창 |
| --- | --- | --- | ---: |
| 1 | prompt-regression | full_frame | q01–q06, 6 |
| 2 | prompt-regression | fixed_roi | q01–q06, 6 |
| 3 | independent-original | full_frame | v01–v04, 4 |
| 4 | independent-revised | full_frame | v01–v04, 4 |

기존 Run `run_3d23462a014a`와 공통 GPU queue만 사용한다. 실행 담당은 `gpt-6.1-sol/high`, Task `task_032ba4cbc816` / Dispatch `ctx_65e6cdf6b6f4`다. 총 4개 job을 직렬 실행하고 실행 오류 retry는 job당 최대1회다. GPU 여유 기준 미달·해결되지 않은 오류에서는 차단/실패를 그대로 보고한다. 기존 runner의 출력 경로는 frozen EXP-0016 namespace 아래의 새 unique attempt를 유지하고, 새 결과 등록 ID만 EXP-0017로 사용한다. source commit은 `64ab297775d712a18f5149c0fd8f3d8d19dec848`이며 queue의 각 code/input/config hash가 실제 실행을 추가로 고정한다.

## 평가와 전달

q baseline은 EXP-0013 원래 출력/EXP-0015 사용자 창 라벨을 재사용한다. q04 후보 보존, q02/q03/q05의 잘못된 후보 감소, q01/q06 신규 후보 여부를 모두 확인한다. 모두 제거/판단 불가로 만든 결과는 개선이 아니다. 과거/현재 입력의 PTS·RGB 및 가능한 processor metadata 동일성을 검증하며 확인 불가능한 parity는 명시한다.

v01/v03은 사용자 확인 시도·진행, v02/v04는 비사건이다. v03은 문 옆 틈에서의 시도이며 정확한 경계 관계는 애매하다. v01/v03 완료 여부는 사용자 미평가다. 두 원본 그룹의 4개 목적 표본이므로 camera/site 독립 성능 추정이 아니다. 사용자 라벨은 추론 입력에 포함하지 않는다.

실제 행동 부합·남은 누락·근거 없는 완료/행동·판단 유보·형식/파싱을 구분하고 정확도/F1/오탐률을 만들지 않는다. 시간·토큰·GPU 메모리는 실제 실행 값으로만 보고한다. prompt 결과에 맞춘 추가 개선 조건은 이번 재개에 포함하지 않는다. 별도 Astra high가 코드/측정/해석과 최종 report/metrics SHA를 검토한다. 기존 페이지에 등록하고 실제 카드·보고서·그래프·근거 영상·검토를 확인한 후 GitHub 게시를 별도 검증한다. 완료 또는 실행 한도 도달 뒤 멈춘다.

영상·프레임·가중치·raw 응답·runtime/receipt는 로컬 전용이다. 웹 기능 추가는 없다.
