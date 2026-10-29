# BATCH-0003 전달·오류 기록

2026-10-29 KST. 기술 실행, 실제 관절 품질, 독립 검토, 로컬 웹 동작, GitHub 게시를 별도로 기록한다. 미완료 단계는 완료로 간주하지 않는다.

## 시작과 사전 고정

로컬 main `4573be9`의 clean 상태를 확인하고 사용자 지침 `b2e6d083eada27db2bc560f89db5aa3a09bdb41d`를 fast-forward로 받았다. reset/stash/강제 덮어쓰기를 하지 않았다. 기존 Run과 canonical GPU queue를 재사용하고 총괄을 추가하지 않았다.

Sol high Task `task_7c8a851c6d27` / Dispatch `ctx_b15556efe8cd`와 Astra high 검토 Task `task_92d8e7d273a0` / Dispatch `ctx_197b8cccbac5`의 requested/effective 모델·추론 수준이 일치했다. 최초 Linux 경로 selector는 Orca가 등록한 WSL identity와 달라 시작 전에 거부됐다. Task 미생성을 확인한 뒤 정확한 기존 workspace identity로 연결했으며 중복 작업자를 만들지 않았다.

EXP-0021을 담당 1에 배정했다. 기존 실제 브라우저에서 담당 카드와 EXP-0021의 `진행 중`/`결과 미등록` 표시를 확인했다(`runtime/BATCH-0003/working-card.json`). 이는 모델 추론 진행을 뜻하지 않는다. `.venv-pose-batch03` ignore, 실행/평가 계약과 배정은 `738cac9`로 게시했다.

실행 전 검토에서 manifest membership 검증과 가상환경 Python 경로 검사, 초기 검증을 제외하던 타이머 범위를 수정했다. 신규 환경의 interpreter만 복사해 경로 조건을 지켰고 기존 환경은 변경하지 않았다. 68개 CPU 검사 중 67통과/기존 1skip, 독립 검사 7개 통과를 확인했다. 기존 파일 3,000개와 이전 환경 5개의 보존을 검사했다.

267개 고유 입력(2 smoke + 265 remaining), 단일 공식 checkpoint/고정 설정 및 13개 실행 의존 파일을 `b52ac221a2e43924f86efd8fbd32a0df4973ceec`에 고정해 게시했다. 총괄은 실제 Git 객체와 현재 파일 해시를 대조했다(`commit-byte-verification.json`). 독립 사전 검토는 입력·환경·코드 계약에 PASS를 주었으며 실제 사람/관절 품질이나 행동 규칙에는 PASS를 주지 않았다.

## 최초 smoke 실패 보존

기존 canonical queue의 job `66f232ed6a8f4376b0f7ac5e7777d7d4`, attempt `152d45f0113f4c94b44c69961a677023`는 free VRAM 7172MiB에서 공식 모델을 로딩한 뒤 구조 검사에서 실패했다. 모델 로딩 0.3475초, 완료 forward 0회, 입력 프레임 추론 0개이며 inference-started marker가 없다. **실제 모델 로딩이 발생한 실패**로 기록하며 준비-only 실패로 표현하지 않는다.

공식 버전의 predictor/backend는 `nms=False`일 때 `model.end2end=True`를 명시한다. 직접 unfused 경로에서 이 초기화가 누락된 정황을 공식 코드와 checkpoint ZIP/pickletools 데이터 검사로 확인했다. CPU에서 checkpoint를 역직렬화하거나 모델을 추가 구성하지 않았다. 최초 summary는 결합된 구조 assertion의 실제 속성값을 남기지 않았으므로 정확히 어떤 항목이 실패했는지는 최초 로그만으로 확정하지 않는다.

같은 모델·입력·설정에서 공식 setter를 적용하고 assertion 전후 속성을 남기는 수정만 준비한다. 원 실패·소스·허가·38개 기존 queue row를 보존하고, 검토된 별도 correction job을 최초 실패에 연결하여 **논리적 retry 최대 1회**로 제한한다. 기존 job의 소스나 실패 상태를 덮어쓰지 않으며 세 번째 시도를 허용하지 않는다. 수정·재시도 결과와 최종 전달 검증은 실제 확인 후 후속 기록으로 추가한다.

미디어·원시 관절·가중치·환경·DB·raw log·receipt는 로컬 전용이다. GitHub에는 코드·문서·공개 가능한 비식별 집계만 게시한다.
