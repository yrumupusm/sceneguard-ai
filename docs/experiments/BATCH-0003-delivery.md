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

당시 같은 모델·입력·설정에서 공식 setter를 적용하고 assertion 전후 속성을 남기는 수정을 준비했다. 원 실패·소스·허가·38개 기존 queue row를 보존하고, 검토된 별도 correction job을 최초 실패에 연결하여 **논리적 retry 최대 1회**로 제한했다. 기존 job의 소스나 실패 상태를 덮어쓰지 않았으며 세 번째 시도를 허용하지 않았다. 실제 후속 결과는 아래와 같다.

미디어·원시 관절·가중치·환경·DB·raw log·receipt는 로컬 전용이다. GitHub에는 코드·문서·공개 가능한 비식별 집계만 게시한다.

## 단 한 번의 retry와 종료

공식 setter 및 한도 검증을 `1b12d85c20ba922de5062148045281849055ef9e`로 게시하고, 수정된 13개 실행 의존 파일의 Git 객체·현재 bytes·사전 고정 hashes가 모두 일치함을 확인했다. CPU 검사 70개 중 69통과/기존 1skip, 독립 검사 9개 통과 뒤 기존 manifest·모델·조건을 유지한 correction만 실행했다.

job `3b5125ac3e26401296bfe3e44e202ecd`, attempt `070b7d4885154095bb84299b8f5916b8`는 free VRAM 7169MiB에서 모델 로딩을 0.3690초에 완료했다. 실제 head 선택 false→true가 기록됐지만 첫 호출의 `visualize=False`가 설치된 `BaseModel.predict`에서 지원되지 않아 TypeError로 종료됐다. `embed`는 지원되는 인자다. 입력 전송과 외부 모델 호출은 있었으나 network prediction의 완료 반환은 없었다.

**모델 로딩 2회 성공 / smoke 2회 실패 / 논리적 retry 1회 소진 / 완료 예측·관절 출력 0개.** 사전 계약 검사가 실제 API 호출 인자까지 검증하지 못한 연결 코드의 오류다. GPU 메모리 부족이나 관절 인식 성능의 실패로 설명하지 않는다. 나머지265개·규칙·추적은 enqueue/실행하지 않았고 세 번째 시도·후속 GPU 작업도 없다. 최종 queue는39 jobs/39 attempts이며 이전38개 row와 원 실패 출력을 보존했다.

두 실패 summary SHA256은 각각 `593ebd605f6555dba9f426b81d6499878e03a8adfad0686ea5602bd3cb33eadb`, `2acff1ceae9d44e1ad2cc7acfb90ee3ffea25375ec22926963d9a04ed682ccf8`다. 실행 소스는 그대로 두고 `scripts/summarize_exp0021_failure.py`가 저장 실패 기록만 CPU로 집계한다. 관절 품질·행동 구분·FPS는 미측정이다.

## 독립 검토와 등록

Astra high는 실패 원문·소스·실측 비용·보존 범위와 최종 문서/측정값을 대조하여 **실패 보고의 충실성에 PASS**를 주었다. 기술 실행이나 행동 성능의 PASS가 아니다. 최종 검토 SHA256은 `c81e6b27b1a73215d26360dba3e358c5cd71261d991640044a5a7dcec9b10522`다. 검토는 보고서 `a64b18fd230d318504d580c6fe4f4ff584edce151fb17c98efd0f931a917f482`, metrics `fff6e18af58434efb77fcf110cdb00b51b64d07b8e34c496b9b12cb6a2945e61`, 총괄 요약 `1eeca829a461f2a4e50cfa852d118e2fbee97078fe4323a25bf2735ee9d28b4d`에 묶였다.

실행 담당의 native `worker_done`은 failed, 검토 담당은 succeeded로 종료됐다. 두 Dispatch 모두 정확한 완료 메시지를 수용한 뒤 native `worker-release`로 해제했으며, 기존 총괄·다른 사용자 터미널을 닫지 않았다. 해당 Run의 reclaimable workers는0이다.

기존 COMPLETE_CLI로 EXP-0021을 담당1에 `execution_status=failed`, `review_status=accepted_for_comparison`, `decision_status=adoption_on_hold`로 등록했다. 여기서 accepted는 실패 기록을 비교 자료로 수용했다는 뜻이다. immutable binding SHA256은 `c9d2d67c148cc94573b2fdbc00a06b82e03c3406960e7745d668011ca86d077d`다. 로컬 package/등록 영수증은 `runtime/BATCH-0003/delivery/`에만 둔다.

## 실제 서비스·브라우저 확인

2026-10-29 04:08 UTC에 기존 `http://127.0.0.1:8765/`에서 EXP-0021을 선택해 담당1의 실패 상태, 보고서,22개 측정 항목(16개 실측·6개 미측정),기존 그래프2개,독립 검토를 확인했다. 브라우저가 읽은 report/metrics/review/binding bytes가 위 해시와 일치했다. viewer JS SHA256 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`도 기존과 동일하며 웹 기능을 바꾸지 않았다.

등록한 영상2개는 **입력 원본 참고이며 pose 출력이 아니다.** 030 88–94초의10fps 참고 영상(6초/960×540)과 기존007 62.5–67.5초 원본(5초/1920×1080)을 각각 실제 재생·1.5초 seek했고 자동 polling 후 재생 요소도 유지됐다. 새 관절 overlay·원본/pose 비교 영상은 출력이 없으므로 만들지 않았다. `runtime/BATCH-0003/delivery/browser-r1.json`의 PASS는 이 전달 동작만 증명한다.

## GitHub 게시와 최종 상태

검토한 코드·문서·공개 집계15개를 `30cce7ccf3ebf9a620ecbe6aa60ceb32636817a9`로 정상 push했다. 2026-10-29 04:10 UTC의 GitHub 검증은 origin/main의 실제 commit과 로컬 Git 객체의 report/metrics/review/binding hashes가 일치함을 확인했다(`runtime/BATCH-0003/delivery/github-results.json`, PASS). 이는 별도로 확인한 브라우저 서비스 bytes와도 같다. 이 문단을 담는 후속 전달 기록 커밋도 push 후 같은 방식으로 검증하며, 그 최종 receipt는 로컬에 남긴다.

| 커밋 | 범위 |
| --- | --- |
| `738cac9` | 고정 실행/평가 계약·담당 배정·격리 환경 제외 |
| `b52ac22` | 최초 고정 구현·테스트·입력 manifest·모델 선정 근거 |
| `1b12d85` | 유일한 retry용 head 초기화·한도 검사·초기 실패 기록 |
| `30cce7c` | 두 실제 실패의 보고서·공개 집계·독립 검토·기존 결과 등록 |

게시 전 staged 목록을 명시적으로 확인했다. 영상/이미지·weights·환경·raw 출력·runtime/DB/log/receipt는 제외됐고, 실제 checkpoint 및 로컬 원본 참고 영상·실행 결과의 ignore를 확인했다. 기존20개 catalog 항목과 고정된13개 실행 파일은 변경되지 않았다. 실패 이후 소스 수정이나 추가 GPU 실행을 섞지 않았다. 최종 canonical queue는35 succeeded/4 failed이며 queued/running0, 이번 batch의2개 smoke는 모두 failed다.

**종료 판정:** 준비/검사와 실패 기록 전달은 완료, 실제 pose 추론은 실패, 사람·관절 품질 및 행동 성능은 평가 미완료다. 참고 영상 재생 확인을 pose 검수 완료로 바꾸지 않는다. 기존 CV/VLM/기본 구성은 보존하고 새 모델 채택을 보류하며, 이번 승인 한도 종료 후 자동 작업을 시작하지 않는다.
