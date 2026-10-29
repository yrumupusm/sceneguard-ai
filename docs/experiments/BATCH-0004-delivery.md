# BATCH-0004 전달 기록

2026-10-29 KST. [사용자 승인 계획](BATCH-0004-yolo26-pose-recovery-plan.md)에 따른 EXP-0022 기록이다. 실제 추론, 관절 품질, 행동 해석, 웹 등록과 GitHub 게시를 별도로 확인한다.

## 시작 상태와 역할

main `e0840a2`의 clean 상태를 확인하고 `73e2b733f668c681f1844444ed50f0cdc2968897`까지 fast-forward했다. reset/stash/강제 덮어쓰기를 하지 않았다. 기존 BATCH-0003의 두 실패와 267개 입력·가중치·환경을 보존하며 신규 결과만 별도 경로에 둔다.

기존 Run `run_3d23462a014a`와 canonical GPU 큐를 재사용한다. Sol 담당 Task `task_5df19346a61c` / Dispatch `ctx_9a8df3d90186`의 실효 모델은 `gpt-6.1-sol/high`, 독립 검토 Task `task_656ab1d8e0c9` / Dispatch `ctx_633012716c3a`는 `gpt-6-astra/high`다. native launch receipt와 live provider 상태로 확인했다. 총괄을 추가하지 않았다.

EXP-0022를 기존 담당2 카드에 배정했다. 실제 브라우저에서 `진행 중`, `결과가 아직 등록되지 않았습니다`, 실효 Sol/high 표시를 확인했다. 이는 추론 성공을 뜻하지 않는다. 초기 GPU 여유는7671MiB였으며 실행 직전 기존6144MiB 기준을 다시 확인한다.

## 실행 전 판정 기준

공식 public `YOLO.predict` 경로의 전체 인자와 설치 버전을 CPU에서 확인하고, 코드·입력을 고정해 독립 검토한 뒤 두 native frame만 먼저 실행한다. 공식 predictor의 fuse/첫 warmup은 기존 실패 경로와 다르게 기록한다. 정상0명 반환은 기술 오류로 재시도하지 않는다.

두 이미지에서 실제 인물과 손목·엉덩이·무릎·발목의 대응이 확인돼야 remaining265로 확대한다. 픽셀·관절 원시값을 클라우드 에이전트에 보내지 않으며, 필요한 사람 확인은 두 로컬 비교 이미지로 묶어 요청한다. 신뢰도·관절 개수만으로 이 품질 조건을 통과시키지 않는다.

실제 실행·검토·등록·원격 게시 결과는 각 단계 확인 후 아래에 기록한다. 원본·오버레이·원시 좌표·가중치·환경·DB·로그·receipt는 로컬 전용이다.
