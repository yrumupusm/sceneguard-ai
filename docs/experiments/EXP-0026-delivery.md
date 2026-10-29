# EXP-0026 전달 확인

2026-10-29. [실험 결과](EXP-0026-exploratory-person-finetune.md)와 [Astra 독립 검토](../reviews/EXP-0026-independent-review.md)를 기존 절차로 전달했다. **학습 기능 실행 완료 / 핵심 검출 누락 지속 / 적용 보류**다. 아래 기술 확인은 새 박스의 실제 사람 대응을 검수했다는 뜻이 아니다.

| 구분 | 실제 확인 |
|---|---|
| 담당 배정 | 기존 Run의 Sol high 담당, 담당3 카드 EXP-0026 ‘진행 중’ 실제 DOM 확인 |
| 실행 | 기존 canonical 큐 신규1job/1attempt,20epoch·21validation·14개 비교 예측 성공, 오류/OOM/retry0 |
| 독립 검토 | Astra high의 코드/입력/승인 결속과 실행 산출물/보고서/26개 공개 측정값 대조 완료 |
| 완료 등록 | `orchestration.complete` 성공, report/metrics/review binding current |
| 실제 웹 | `http://127.0.0.1:8765/` → 담당3 → EXP-0026 선택. 보고서·검토 열기,26개 수치와 기존 그래프2개 DOM 확인 |
| 로컬 자료 표시 | 전후 비교PNG7장(각3840×1080),loss PNG1장(1800×600) 실제 decode/render,16.5초 polling 후 유지 확인 |
| 서비스 바이트 | 서비스 API의4개 보고서/지표/검토/binding 해시가 로컬 검토본과 일치. app.js도 기존 소스 SHA와 일치 |
| GitHub | 소스 고정 `1a0a647`, 결과 `83b1220` push 및 origin/main SHA와 등록 자료의 원격 Git 객체 바이트 대조 PASS |
| 보존 | 원본 ZIP/준비 사본/기존 환경/기존42jobs·attempts 보존. 종료 큐39succeeded/과거4failed,queued/running0 |

새 웹 기능이나 새 큐를 만들지 않았다. 영상 자료 대신 고정 이미지 비교 실험이므로 영상 재생·seek는 해당 없음이다. 등록된 미디어8개와 체크포인트·데이터·raw Results·로그·DB·실행 승인 파일은 로컬에만 있으며, 커밋 대상에서 제외됨을 확인했다. 공개 파일은 코드·문서·집계·담당/카탈로그/binding뿐이다.

실행/입력 담당은 완료 후 해제했다. 독립 검토 담당의 해제 요청에 Orca가 `retained / user_takeover`를 반환해 사용자 소유 상태를 존중했으며 강제 종료하지 않았다. 종료 시 회수 결정을 기다리는 worker 목록은0이었다. 추가 학습을 예약하지 않는다.

상세 로컬 영수증은 `runtime/BATCH-0007/training/`의 `browser-assignment.json`, `preservation-after.local.json`, `review-final-binding.json` 및 `delivery/browser-images.json`, `delivery/github-results.json`이다. GitHub 검증과 실제 브라우저 검증은 별도 영수증으로 구분했다. 이번 전달 기록을 추가한 후에도 최종 origin/main과 서비스가 읽는4개 결과 파일의 바이트를 다시 대조한다.

사용자 질문에 대한 결론: **이번 한 설정으로 학습해도90·94초에서 검출되지 않았다.**84초와 일부 접근 장면의 박스 수도 줄었다. 학습 loss 감소나 잠정 valid mAP를 현장 성능 개선이라고 읽지 않으며, 기본 모델을 유지한다. 다음에는 이미 준비한 라벨 검수 자료를 바탕으로 개인별 박스 범위·누락 라벨을 확인한 뒤 새 학습 설계를 판단한다.
