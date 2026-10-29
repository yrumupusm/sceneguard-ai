# Codex 프로젝트 작업 지침 — SceneGuard

**최우선:** 이 저장소는 완성한 시스템을 꾸미는 곳이 아니라, **근거에 기반한 설계·실험·문제 해결 과정**을 남기는 포트폴리오 프로젝트다. 코드를 만들기 전 `README.md`, `docs/PROJECT_CHARTER.md`, `docs/WORK_PLAN.md`, `docs/decisions/`를 읽는다.

## 현재 신규 승인 — BATCH-0005 C6 ROI 자세 추정 비교 (2026-10-29)

**최신 작업 지침:** [BATCH-0005 비교 계획](docs/experiments/BATCH-0005-c6-pose-roi-comparison-plan.md)과 [CODEX_NEXT_TASK](docs/CODEX_NEXT_TASK.md). 사용자가 이전 BATCH-0004의 실제 원본/관절 오버레이(030 90초 full-frame 검출0, 007 64초 출력2행)를 보고, **E01_030 84/90/94초 원본 전체화면과 기존 C6 고정 ROI를 비교**하도록 새 범위를 승인했다. 이전 '추가 GPU 실험 금지'는 **해당 종료 배치에 대한 기록**이며 이번 BATCH-0005 / EXP-0023의 신규 5개 조건으로만 대체한다. 이전 실험/보고/실패 원본·설정·가중치/큐를 변경하지 않는다.

**정확한 한도:** 기존 030:90 full-frame 결과 **재사용**. 새 공식 YOLO26m-Pose `YOLO.predict` **딱5개**: 030:84 full/C6, 030:90 C6, 030:94 full/C6. 동일 공식 Ultralytics8.4.192·weight·640/FP32/conf.25/nmsFalse/공개 kwargs, 새 weight/학습/VLM 없음. 고정 `configs/mvp0001_cameras.json` C6 ROI `[.28,.2,.75,.8]` → 원본1920×1080 **x537:1440,y216:864**. source SHA/native PTS/RGB 및 crop SHA 확인. ROI local Results boxes/keypoints는 원본 좌표로 offset(+537,+216)을 **한 번만** 적용; full Results는 무변경. 90 ROI가 empty여도 84/94의 사전 지정된 비교를 생략하지 않는다.

**실행:** 기존 Astra max 총괄1/Sol high 담당 최대2/Astra high 독립 리뷰1, Run `run_3d23462a014a`와 **한 개 canonical 직렬 GPU 큐**, free VRAM≥6144MiB gate, 사전 CPU crop/color/offset/해시/오프라인·공식 API 계약 테스트와 source commit/review. 새 단순 batch05_pose 구현만 작성하고 검증된 batch04_pose 공식 경로/기존 03090 Results는 **읽기 전용** 사용. 실제 원본/전체/ROI 오버레이 3시점의 bbox·관절 시각 대응을 평가해, **계수만으로 사람/관절 복원 성공을 주장하지 않음**. C6 ROI의 calibrated 플래그가 실제 fence top/far-side 교정은 아니므로 추적/규칙/CV+VLM 결합과 완전 행동 성능/F1/FPR은 범위 밖.

**전달:** 실제5회/재사용1회 분리 계수와 비용·사람 관절 일치 미확정·실패 사유를 신규 EXP-0023 report/metrics/review/binding, 기존 웹 이미지 표시, GitHub 원격 해시로 확인. CCTV 원본·프레임·raw bbox/관절 좌표·오버레이·weights·runtime/receipts·민감정보는 로컬만, 공개는 코드/비식별 요약. 완료 후 새 GPU 작업 자동 진행 없음.

## 최신 관측 — BATCH-0004 공식 추론 성공·확대 보류 (2026-10-29)

[종합 결과](docs/experiments/BATCH-0004-summary.md), [EXP-0022](docs/experiments/EXP-0022-yolo26-public-predict.md), [전달 기록](docs/experiments/BATCH-0004-delivery.md)을 우선한다. 같은 모델/환경/입력으로 public YOLO.predict 두 프레임이 성공했고 원본/관절 비교 이미지2개를 로컬에 확보했다. 오류/retry0, sample forward2와 warmup1을 구분한다. 030:90은 기존 사용자 관찰상 사람이 있지만 정상 반환0행으로 관절 근거를 얻지 못했다. 007:64는2행/관절 추정23개이며 실제 위치 검수는 별도다. **remaining265·규칙·추적·추가 GPU 실행을 자동 시작하지 않는다.** 기술 복구 성공이 관절 품질/행동 성능 충족은 아니며 기존 기본 구성과 과거 실패를 보존한다.

## 보존된 명시 승인 — BATCH-0004 공식 YOLO 추론 경로 복구 (2026-10-29)

**지금의 최우선 과제:** [BATCH-0004 기술 복구 계획](docs/experiments/BATCH-0004-yolo26-pose-recovery-plan.md), [CODEX_NEXT_TASK](docs/CODEX_NEXT_TASK.md). 기존 BATCH-0003은 **두 smoke에서 adapter 호출 문제로 실패한 종료 기록**이고 새 GPU 실행 권한이 없었다. 사용자가 **이번 별도 BATCH-0004/EXP-0022에 한해** 같은 pretrained YOLO26m-Pose/가중치·동일 267개 원본 입력으로 공식 public YOLO.predict() API를 통한 재실행을 새로 승인했다. 이력 소스·큐 row·등록/해시·라벨은 그대로 보존하고, 이전 실패 작업을 다시 시도하지 않는다.

**필수 실행 순서:** 공식 Ultralytics 8.4.192 호출 signature/전체 kwargs, source RGB→BGR ndarray, Results.boxes/keypoints Nx17x3 및 empty/unknown 처리의 **CPU 호환성 테스트**를 기존 GPU queue 실행 전에 마련하고 독립 검토한다. 이전의 잘못된 inner.predict(visualize=False) 및 수동 head 설정/좌표 재변환을 새 경로에 복제하지 않는다. 공식 predictor의 fuse/첫 warmup은 이번 실행과 과거 unfused/no-warmup 실패 경로의 차이로 보고한다. 실행은 기존 Astra max 총괄·Sol high 담당 최대2·Astra high reviewer, 같은 Run/canonical GPU 직렬 큐/free VRAM≥6144MiB, 정확한 source/config/weights/PTS hash·lease 보호 안에서만 한다. 새 환경·weight/학습·외부 API·VLM 재추론·정책 완화 금지.

**산출물 우선순위:** 원본030:90/007:64의 두 native frame에서 **실제 새 pose Results 및 원본/관절 오버레이 두 장**을 먼저 확보; 정상 반환 0명과 기술 실패를 분리. **인물·관절의 정합성이 확인되는 경우에만** 나머지 기존265 프레임 처리와 시도/접근 구간 비교로 확대. 관절·person ID·경계 top/far-side 의미 불명확 시 규칙/추적/결합 보류. 기술 smoke·시각 품질·행동 구분·독립 검토·기존 로컬 웹·GitHub remote byte를 각각 따로 기록한다. 사람별 정밀 GT/정확도/F1/FPR/위법성 판정을 창작하지 않는다.

**실험 기록:** 새로운 EXP-0022 / BATCH-0004 계정과 분리된 결과 디렉터리만 사용. 기존 EXP-0021 실패를 수정하거나 세 번째 재시도 처리하지 않는다. 새 배치에서 오류 수정 재시도도 최대1번, 실패 시 근거 기록 후 중단. 영상·이미지·raw 관절 좌표/weights/runtime/receipts는 로컬 전용, 배포/AGPL 조건 유지. 이 승인 이후 별도 GPU 작업·새 모델/무인 개선을 자동 시작하지 않는다.

## 최신 상태 — BATCH-0003 실행 실패·재시도 한도 종료 (2026-10-29)

[종합 결과](docs/experiments/BATCH-0003-summary.md)와 [전달 기록](docs/experiments/BATCH-0003-delivery.md)을 우선한다. 공식 YOLO26m-Pose 한 모델과 267개 입력을 준비했으나, 두 smoke가 각각 head 초기화 누락/지원하지 않는 visualize 인자로 실패했다. 실제 모델 로딩은 2회, 완료 forward·pose 출력은 0개다. 이는 어댑터 호환성 실패이며 모델 관절 품질 실패라는 뜻이 아니다. 한 번의 논리적 retry를 소진했고 나머지265개·행동 규칙은 실행하지 않았다. **추가 GPU 실행·세 번째 시도·모델 변경을 자동 시작하지 않는다.** 기존 CV/VLM·공식 라벨·결과와 기본 적용 보류를 유지한다. 다음 별도 범위 전에는 실패 기록/CPU 검사와 전달 증거만 활용한다.

## 보존된 승인 — BATCH-0003 YOLO26m-Pose 무학습 자세 추정 (2026-10-29)

**최우선:** [BATCH-0003 전체 계획](docs/experiments/BATCH-0003-yolo26-pose-plan.md) 및 [CODEX_NEXT_TASK](docs/CODEX_NEXT_TASK.md). 사용자는 **추가 학습 없이 공식 COCO 사전학습 `yolo26m-pose.pt` 1개**를 RTX3080에서 사용해, 실제 울타리 넘는 순간 사람 검출과 17개 관절의 시각적 정확성·시간 변화·접근/대기 오판을 확인하는 제한된 실험을 승인했다. 이번 신규 승인은 이전 **BATCH-0002 종료/추가 GPU 작업 금지의 역사적 상태**를 이 범위 한정으로만 대체한다.

**범위/게이트:** 기존 EXP-0019 native PTS 11개 + 사전 고정 5개 구간에서 원본10fps 이하, 총 고유300프레임 이하. YOLO26m-Pose 640/FP32/conf0.25의 한 조건, 2프레임 smoke→성공 시 나머지 단일 직렬 실행. 모델버전/가중치 SHA/환경/코드/PTS/경계를 실행 전 고정. `.venv-pose-batch03` 격리, AGPL-3.0 및 결과 공개 범위 검토. free VRAM≥6144MiB gate와 기존 Orca Run/Task/Dispatch·단일 canonical GPU queue·Astra max/Sol high/Astra high 체계 유지. 새 학습·파인튜닝·추가 모델/가중치·대안 프롬프트·외부 AI API·유료 결제·기본 CV/VLM 교체·새 UI·무허가 이미지 업로드 금지.

**평가:** 모델 성공/박스 개수와 사람·관절 실재 복원·행동 구분을 별도 판단. 원본/로컬 오버레이에 대한 정확한 사람별 관절 검수 전에는 RF-DETR 030:90의 0→1이나 새 pose 개수를 사람 복원 성공으로 간주하지 않는다. 사람/관절 관측이 부족하면 규칙을 **건너뛴다**. 충분하면 고정 감시 경계와 손·무릎·발·체중 이동의 **사전 등록 규칙 단1개**를 독립 구현해 접근/시도 창을 비교한다. 관절은 YOLO COCO 17개, 시도/완료/법적 침입의 GT가 아니다. q/v는 개발/진단 표본이고 정확도/F1/FPR/일반화·사람별 완료를 만들지 않는다. 이전 031 종료 미완료는 030 사실로 전이하지 않는다.

**제3자 참고:** 공개 YOLOv8-Pose fence rule 예시는 아이디어 참고용이다. 명시적 라이선스가 없는 제3자 프로젝트 구현 코드를 복사/벤더링하지 않는다. Ultralytics AGPL-3.0의 파생물 공개 의무 및 향후 상용 통합은 별도 검토 전 연구/기술 실험 밖으로 확대하지 않는다. 원본 CCTV/프레임·사람 좌표/raw 응답·가중치·DB·runtime·receipts는 로컬 전용. 코드·비식별 수치/해석/독립 리뷰만 GitHub. 기존 Orca 결과 등록, 실제 웹·영상 재생/seek, GitHub 원격 byte 확인을 분리한다. 승인 배치 종료 후 새 GPU 작업 자동 시작 금지.

## 최신 상태 — BATCH-0002 고정 비교 종료·기본 적용 보류 (2026-10-29)

[종합 결과](docs/experiments/BATCH-0002-summary.md), [EXP-0018 입력 감사](docs/experiments/EXP-0018-input-audit.md), [EXP-0019 CV 비교](docs/experiments/EXP-0019-cv-comparison.md), [EXP-0020 VLM 비교](docs/experiments/EXP-0020-vlm-comparison.md), [전달 기록](docs/experiments/BATCH-0002-delivery.md)을 우선한다. RF-DETR Medium 11프레임과 Qwen3-VL-4B NF4 16개 view를 각각 한 번 생성했다. v01의 모델 로딩 전 메타데이터 오류는 기존 실패·12개 q 출력을 보존한 단 한 번의 논리적 retry로 복구했다. 새 모델 2개·고정 비교 한도는 종료했으며 **추가 GPU 작업·모델·튜닝·자동 재시도는 예약하거나 시작하지 않는다.** 아래 승인 문단은 이 배치의 실행 이력이다.

기술 실행과 행동 성능은 구별한다. RF-DETR의 030:90 박스 0→1은 실제 사람 복원 확정이 아니다. 4B는 접근 세 창의 여섯 유효 view에서 잘못된 후보 4→0, q04 C 후보 유지였지만 q04 B 누락, v01의 양성 출력 실패, 전체 6/16 형식 실패 및 근거 없는 완료 주장을 남겼다. **신규 두 모델 기본 적용 보류, CV+VLM PoC 미실행**, 기존 CV/MVP·원래 질문·ROI·경계 규칙·EXP-0006 보류 상태 유지다. 용량/양자화 또는 모델/전처리가 함께 달라진 비교다.

새 사용자 관찰은 별도 기록이다: q04 문 잡기/발 올림, v01 줄 넘기 후 반대편에 서 있음, v03 문 옆 바위에 올라서며 종료. v01의 새 한정 완료 관찰은 과거 미평가 이력을 덮어쓰지 않고, v03의 바위 올라섬은 경계 넘기 확정이 아니다. q04 B/C 가시성을 각각 확인한 것으로 확대하지 않는다. q/v 개발 자료로 정확도/F1/FPR을 만들지 않는다. 독립 검토·기존 웹·GitHub 확인은 전달 기록의 별도 증거를 따른다.

## 보존된 승인 — BATCH-0002 모델 대안 검증 (2026-10-29)

**현재 최우선 작업:** [BATCH-0002 계획](docs/experiments/BATCH-0002-model-upgrade-plan.md), [CODEX_NEXT_TASK](docs/CODEX_NEXT_TASK.md)을 따른다. 기존 EXP-0017 프롬프트 개선 실패/종료, FCOS/ByteTrack 보류, EXP-0001~0017 원본·라벨·보고서·결과를 보존한다. 사용자 승인에 따라 이번 배치에 한해 CV/VLM 후보 1개씩의 신규 로컬 모델 비교 및 조건부 오프라인 결합 PoC(최대1)를 진행할 수 있다. 과거 `새 GPU 실험 자동 실행 금지`는 종료된 구 승인 상태이며, 이번 구체적 신규 승인 범위로만 대체된다. 다른 향후 모델/튜닝을 자동 승인하지 않는다.

**작업 흐름:** 원본/processor 입력 2fps의 자세·시간 정보 감사 → 기존 FCOS 대비 CV 후보(우선 RF-DETR Medium) 1개 → 기존 Qwen3-VL-2B 대비 VLM 후보(우선 Qwen3-VL-4B) 1개 → 두 결과에 보완 근거가 있을 때만 CV+VLM 오프라인 PoC. 각각 공식 모델 카드·라이선스·revision·장치 호환성/양자화 확인, 사전 PTS·프레임·prompt·분모 고정, 같은 사건과 비사건의 행동 기준 비교가 필요하다. **결합이 목표 자체는 아니며**, 근거가 없으면 단계별 보류. 검출기만으로 VLM을 차단하여 중요한 넘기 장면을 삭제하는 설계는 금지.

**자원·검증:** 기존 Astra max 총괄 1명, Sol high 구현/평가 담당 최대2명, Astra high 독립 검토 1명과 native Orca Task/Dispatch, 기존 공통 GPU 직렬 큐/최소 free VRAM 6144MiB gate를 유지한다. 격리 env에서 새 의존성을 설치하고 기존 가상환경·결과를 덮어쓰지 않는다. GPU job 오류 재시도 최대1회, 무음 모델/양자화/프레임 수 하향 대체 금지. 새 weight 총2개(각 종류 최대1), 재학습·외부 API·추가 결제·새 대시보드 금지. 사용자 q/v 5초창은 개발/진단용이며 정확도/F1/FPR 또는 운영 가능성으로 일반화하지 않는다. 로컬 원본/프레임/weights/raw response/receipts는 GitHub·클라우드 에이전트에 전송하지 않는다. 각 실행을 새 결과 ID·해시·독립 검토·기존 웹/GitHub 확인까지 완료한 뒤 보고하고 멈춘다.

## 최신 결과 — EXP-0017 프롬프트 비교 실행 종료 (2026-10-29)

사용자의 GPU 재확인·재개 지시로 기존 EXP-0016 사양을 새 결과 ID EXP-0017에서 실행했다. [실제 비교 보고서](docs/experiments/EXP-0017-prompt-evidence-results.md), [전달 기록](docs/experiments/EXP-0017-delivery.md), [다음 작업](docs/CODEX_NEXT_TASK.md)을 우선한다. 기존 단일 Run/queue와 Sol high 담당을 재사용했고, free VRAM 8015–8026 MiB가 기존 6144 MiB gate를 통과했다. 4개 직렬 작업·20개 생성 완료, 오류/OOM/retry 0이다. EXP-0016의 차단 보고서/등록과 이전 결과는 불변으로 보존한다.

**기능 실행 완료와 행동 성능 실패를 구분한다.** q 비시도 5개에서 잘못된 후보 창은 B 2→3, C 2→2이며 q04 C 후보는 유지됐으나 완료를 과장했다. 별도 사용자 검수 v 양성 2개에서 후보는 1→0, 음성 2개에서는 1→1이다. 수정 prompt의 기본 적용을 보류하고 기존 설정을 유지한다. 기존 설정도 성능 부족/채택 보류다. v 네 창은 두 source group이며 카메라/장소 독립 최종 테스트가 아니다. accuracy/F1/오탐률을 만들지 않는다.

이번 단일 개선 한도는 종료했다. 추가 prompt 튜닝·모델·GPU 작업을 자동 시작하지 않는다. 모델·가중치·ROI·샘플링·후처리·웹 기능은 바꾸지 않았다. 원본/영상/프레임/raw 응답/weights/runtime은 로컬 전용이다. 아래 EXP-0016 미실행 상태는 과거 차단 이력이다.

## 이전 범위 — EXP-0016 단일 프롬프트 개선 비교 (2026-10-28)

사용자가 EXP-0015, 독립 검토, MVP 요약과 기존 작업 지침을 읽고 단일 개선 구현·비교, q01–q06 회귀 확인, 최대6개 별도 확인창, Astra 검토, 기존 웹 등록 및 GitHub 기록을 승인했다. 최신 상세는 [CODEX_NEXT_TASK](docs/CODEX_NEXT_TASK.md), [EXP-0016 사양/결과](docs/experiments/EXP-0016-prompt-evidence-rubric.md), [ADR-0017](docs/decisions/ADR-0017-qwen-temporal-evidence-prompt.md)이다. 이 범위에서 변경하는 축은 Qwen 공통 prompt 하나뿐이다. 모델/가중치/processor/generation/parser/후처리/ROI/windows를 조합해 바꾸지 않는다. 재학습·외부 API·가중치 다운로드·웹 기능 확장은 금지다.

GPU job은 **기존 canonical queue와 최소 여유 VRAM 6144 MiB resource gate**를 통과할 때만 순차 실행한다. 실행 담당 Sol high Task `task_305549d14771` / Dispatch `ctx_65256d02af82`가 2026-10-28 14:36 UTC RTX 3080에서 8464 MiB used, 1590 MiB free, 99% utilization을 측정해 차단됐다. EXP-0016 job/attempt 0, Qwen model load/inference 0이다. queue 우회·gate 낮춤·다른 프로세스 종료를 하지 않는다. 실제 모델 입력에는 익명 clip ID와 프레임만 전달한다. q/v 라벨과 공식 annotation은 inference path와 분리한다. 기능/테스트 성공, 실행 완료, 행동 개선, 독립 검증은 별도 판정한다. 추론 전에는 행동 성능 효과를 미측정으로 남긴다.

사용자 추가 확인 v01–v04: v01 attempt/progress(완료 미확인), v02 비사건, v03 attempt/progress(게이트가 아닌 옆 틈, 경계 연결은 애매함), v04 비사건. 공개 가능한 사용자 label 요약 외 원본/추출 영상·프레임/가중치/raw 응답은 로컬에만 둔다. v01/v02는 E01_004, v03/v04는 E01_021이며 세션/카메라 독립성을 확정한 테스트가 아니다.

## 최신 범위 — EXP-0015 사용자 라벨 개정 (2026-10-28)

사용자는 최신 지침 `c73d217`에서 기존 EXP-0013 출력만 사용한 평가·정리, 기존 웹 등록 및 GitHub 반영을 승인했다. [CODEX_NEXT_TASK](docs/CODEX_NEXT_TASK.md), [MVP_SMALL_EVALUATION_PLAN](docs/data/MVP_SMALL_EVALUATION_PLAN.md), [EXP-0013 observation errata](docs/data/EXP-0013-observation-errata.md)를 따랐다. 평가는 최대12개 고정 창의 저장 B/C 답변만 CPU로 대조하고, 사용자 제공 q01–q06 검수를 EXP-0015 라벨 revision으로 반영했다. 새 GPU 추론·모델·웹 기능은 금지였으며 실행하지 않았다.

EXP-0015는 EXP-0014의 저장 기록과 EXP-0013의 B/C 출력을 불변으로 유지하며, q01–q06의 사용자 확인을 별도 revision에 적용했다. 16개 CPU 테스트, 기존 metrics validator, Astra high 독립 검토, 완료 등록, 실제 로컬 브라우저 확인이 통과했다. 행동 평가의 주 양성은 여전히 0이고 accuracy/precision/recall/F1/FPR/시간당 오탐은 null이다. 성능 입증과 자동 채택은 보류다. 별도 검증 카메라 작업을 계획하기 전까지 새 추론은 하지 않는다. 결과·공식 라벨·기존 report binding은 덮어쓰지 않는다.

검수 질문용 원본 클립은 `outputs/mvp0001_evaluation/EXP-0014/question_clips/`에 로컬만 둔다. Git에는 코드·문서·식별 가능한 개인 정보가 없는 창별 요약만 포함할 수 있다. 원본 영상, 프레임, 가중치, raw 응답, artifact manifest, runtime DB/log/receipt는 제외한다.

## 상시 사용자 운영 지시 — 실험 전달 완료 절차 (2026-10-28)

**최신 MVP-0001 결과: 코드·CPU 테스트·세 원본 실제 Qwen 처리는 완료. 행동 성능 검증·채택은 보류.** [EXP-0013 비교 보고서](docs/experiments/EXP-0013-mvp-comparison.md), [MVP 요약](docs/experiments/MVP-0001-summary.md), [전달 기록](docs/orchestration/MVP-0001_DELIVERY.md)을 따른다. GPU 자원 부족 당시 EXP-0011/12 차단 결과는 불변으로 보존했고, 후속 실제 실행은 EXP-0013으로 별도 기록한다. 실제 EOF 처리는 사람 행동 구분 정확도나 운영 적합성을 의미하지 않는다. 이번 승인 범위 완료 뒤 GPU 작업을 자동 예약하지 않는다. 웹 기능 확장과 기존 CV/EXP6 기본 교체는 하지 않는다.

**새 승인 범위: MVP-0001 핵심 로컬 실행 흐름 통합.** [고정 계획](docs/experiments/MVP-0001-plan.md)을 따른다. 이전 BATCH-0001 종료/채택 보류는 그대로 보존한다. 원본 전체 영상 2~4개에서 시간창→행동 분석→이벤트 후보/판단 불가→중복 정리→근거 저장을 연결한다. 후보 구성 최대3, 구성별 baseline1+근거 있는 개선 최대1, 새 가중치 최대2, 실행 오류 재시도 job별 최대1. 현 계획은 기존 CV/전체화면 Qwen 기준과 고정 카메라 영역 Qwen 대조이며 새 가중치0이다. 총괄 하나·Sol high 담당 최대2명+Astra high 검토1명, 기존 Run/단일 GPU 큐 순차 실행. 작은 설정의 재승인 없이 총괄이 비교·개선·통합·평가한다. 기존 웹·완료 등록만 재사용하고 답변 표시/디자인/관리 기능을 확장하지 않는다. 재학습·외부 추론 API·유료 전환·미디어 외부 전송 금지. 자동 테스트/기능 통합/행동 성능을 따로 판단하고, 한도 또는 완료 시 보고 후 멈춘다.

**이전 범위: 첫 실제 VLM 배치 종료.** [BATCH-0001 비교 결론](docs/experiments/BATCH-0001-vlm-comparison.md), [전달 기록](docs/orchestration/BATCH-0001_DELIVERY.md)을 먼저 읽는다. Qwen 기준(EXP8), Smol 기준(EXP9), 사전 고정 Qwen 픽셀 예산 대조(EXP10)의 총3조건·18클립 생성을 기존 큐에서 완료했다. 두 후보 모두 채택 보류, 기본 CV/EXP6 상태 유지. 이번 승인으로 추가 조건·모델·무인 반복을 시작하지 않는다. 다음 모델 실험은 별도 사용자 작업 범위를 따른다. 코드 구현·실제 실행·GitHub 게시·서비스/브라우저 확인은 전달 기록에서 구분한다.

**추가 승인: 첫 실제 VLM 비교 배치(2026-10-28).** 기존 Qwen3-VL-2B 포함 최대3후보/신규최대2, 후보당 baseline1+총괄 결정 improvement최대1, 실행 오류 job당 retry최대1. 이번 배치는 Qwen3-VL-2B와 SmolVLM2-2.2B 두 후보로 시작한다. 기존 6개 개발 클립, 실행 전 공통 질문·평가 고정. Sol high 담당과 Astra high 독립 검토, 기존 단일 Run/GPU 큐 사용. 최소 명령 등록·설치·추론·결과 검토·기록·웹 반영은 승인됐으며 아래 과거의 새 실험 미승인 상태를 이 배치에 한해 대체한다. 큐 우회 추론, 재학습, 외부 추론 API/새 결제/미디어 외부 전송, 새 총괄/큐/대시보드 확장은 금지. 배치 후 보고하고 멈춘다. 공통 계약은 `docs/experiments/BATCH-0001-plan.md`다.

앞으로 승인된 실험은 **담당 에이전트 배정 → 실행 → 보고서·측정값 저장 → 총괄 검토 → 웹 등록 → GitHub 게시 확인 + 로컬 화면 확인**까지 한 작업이다. [EXPERIMENT_DELIVERY](docs/orchestration/EXPERIMENT_DELIVERY.md), [완료 CLI](docs/orchestration/COMPLETE_CLI.md), [실제 검증 기록](docs/orchestration/DELIVERY_VALIDATION.md)을 따른다.

- 실제 Orca Run/Task/Dispatch와 담당 슬롯을 `orchestration.complete assign`으로 연결한다. 실효 모델은 세션 증거로 확인한다. 작업 상태는 정확히 일치하는 최근 native 관측만 사용하고, 단절·오래됨·다른 dispatch이면 미확인이다.
- 작업자는 자기 보고서/metrics/로컬 artifact 목록을 제출한다. 총괄이 별도 검토와 원문·측정치 SHA256을 작성한 뒤 `complete`로 등록한다. worker_done, 코드 구현, 실험 성공, 검토 판정, 채택은 서로 다른 사실이다.
- `verify_delivery github`와 `verify_delivery browser`로 원격 커밋과 실제 화면을 **각각** 확인한다. 등록 또는 HTTP 200만으로 완료 선언하지 않는다. 첫 실제 실험은 진행 중 담당 카드와 완료 후 보고서 펼치기·그래프·등록 비교 영상 재생/seek·총괄 검토까지 확인하고 로컬 receipt를 남긴다.
- 실패/미측정/영상 부재도 기록한다. TEST 모의 검증을 실제 실험 성공으로 표현하지 않는다. 과거 세팅 당시 비어 있던 배정은 이번 EXP8~10의 실제 native 배정으로 채웠다.
- 코드·문서·공개 가능한 측정 요약만 게시한다. 영상·이미지·가중치·원시 응답·로컬 artifact 경로·DB·로그·receipt·인증정보는 Git 제외다. 같은 runtime/환경을 재사용하며 자동 재실험/자동 채택을 추가하지 않는다.

## 이전 승인 — Orca 세팅 (2026-10-28)

현재 우선 작업은 **Orca 총괄·역할별 작업자 + 단일 GPU 실행 큐 + 읽기 전용 로컬 결과 페이지 세팅**이다. `docs/CODEX_NEXT_TASK.md`, `docs/orchestration/SETUP_ORCA.md`, `docs/orchestration/AGENT_ROLES.md`, `configs/orchestration/model_policy.json`을 따른다. 이 범위의 UI/서버·역할 설정·최소 환경 설치는 승인됐으며, 아래 과거 실험 단계의 UI/서버/새 아키텍처 금지를 이 범위에 한해 대체한다.

- 모델 정책은 목표일 뿐 실제 계정 사용권 확인 전 활성화 성공으로 보지 않는다. 총괄 gpt-6-astra 최고 가용 effort, 구현/실험 gpt-6.1-sol high, 독립 검토 gpt-6-astra high, 화면 gpt-6.1-terra high를 우선 확인한다. 현재 Codex의 실제 모델 ID/effort와 호출 증거를 기록하며 무음 하향·임의 Pro ID·유료 API 전환 금지.
- Orca native Run/Task/Dispatch를 우선 재사용한다. 실행 버전 도움말과 skills를 확인하고 한 총괄만 운영한다. 작업자 최대3, GPU1, 중첩 fanout 금지. Codex 내장 subagent는 지원 확인 후 제한 fallback이며 두 총괄 계층을 동시에 만들지 않는다.
- 새 세팅 환경과 worktree를 사용하고 .venv/.venv-vlm·공식 라벨·기존 출력·EXP-0001~0007은 보존한다. 과거 문서의 실험 상태를 세팅 성공과 혼동하지 않는다.
- 세팅 단계는 무해한 에이전트 호출, CPU mock 큐, 기존 결과 표시 테스트까지만. 새 CV/VLM 가중치·재학습·실제 비교 배치·외부 미디어 전송·공개 배포는 실행하지 않는다.
- raw CCTV/프레임을 클라우드 에이전트 이미지 도구로 자동 전송하지 않는다. 코드·공개가능 요약으로 orchestration을 구성하고 미디어 검수는 로컬 웹에서 사람이 수행한다.
- 기본 보호장치를 끄거나, 계정/credential 내용을 복사하거나, 전체 Orca runtime reset을 하지 않는다. setup 문서가 있는 것과 실제 동작이 검증된 것을 구분해 LOCAL_SETUP_REPORT에 기록한다.

## Orca 세팅 확인 상태 (2026-10-28)

로컬 기능 검증 결과는 [LOCAL_SETUP_REPORT](docs/orchestration/LOCAL_SETUP_REPORT.md)에 기록했다. Astra max 총괄 1명, Sol high 구현, Terra high 화면, Astra high 독립 검토의 실제 호출을 확인했다. 공통 runtime과 CPU mock 큐, http://127.0.0.1:8765/ 읽기 전용 페이지를 사용한다. 새 `.venv-orca-lab`만 설치했고 기존 두 환경/실험 기록을 보존했다. 32개 fixture와 실제 큐·브라우저·보존 검사가 통과했다. 독립 검토의 수정과 재검토 판정은 해당 보고서가 원본이다.

세팅 완료 뒤 새 실험을 자동 시작하지 않는다. `CODEX_NEXT_TASK`의 다음 배치 준비 범위를 따르며 실제 모델 비교는 별도 배치 승인이 필요하다. 웹/상태 조회는 agent/GPU 작업을 실행하지 않는다. 큐의 등록 명령은 현재 CPU mock뿐이며 실제 GPU 작업으로 확대하기 전 실행 계약을 검토해야 한다.

## 현재 실험 상태와 목표 (세팅 전 이력 보존)
- 현재 실험 단계: **EXP-0007 독립 로컬 VLM 행동 분석 완료·기본 연동 보류**(2026-10-28, ADR-0012). 1차 문제는 CCTV 출입 경계 통과/넘기 **이벤트 후보** 감지. AI-Hub 영상 10개·45개 JSON 구조 감사 및 설계 완료; 최종 메인 데이터·모델·정량 성능은 미확정.
- 이전 감사: Safe and Unsafe Behaviours·iSafetyBench, SteelBench 401, ACCIDENT 5개 CCTV 감사 완료(Conditional Go). 모두 보존. **현재 후보: AI-Hub 지능형 관제 서비스 CCTV 영상 데이터(71850)의 침입 범주, 로컬 10개 감사·사용자 검수 및 평가 설계 기록 보유**. 문서: `docs/data/AIHUB_INTRUSION_AUDIT_PLAN.md`.
- 첫 진단 모델은 **SSDLite320 COCO_V1**(ADR-0007), 검출 누락을 확인해 **메인 모델 채택 보류**. 실제 결과는 `docs/experiments/EXP-0001-phase2a-cv-baseline.md`. Phase 2A 최초 승인 범위는 사전학습 사람 검출 1개 + 최소 IoU 연결 + 카메라별 ROI/경계 통과 후보 **작은 프로토타입**. YOLO/BoT-SORT/VLM 등 특정 브랜드·구성을 당연한 필수로 고정하지 않는다.
- 장비: 로컬 RTX 3080 10GB / WSL2 Ubuntu 22.04 / torch 2.5.1+cu124 / torchvision 0.20.1+cu124. 실측 환경은 EXP-0001/0002 참조.
- 최신 비교: [EXP-0002](docs/experiments/EXP-0002-fcos-detector-comparison.md), [ADR-0008](docs/decisions/ADR-0008-fcos-detector-comparison.md). 사용자 승인으로 FCOS 한 개를 추가해 동일 네 구간 비교 완료. 사람 일부 복원과 중복·배경 오검출 의심·누락·연결 실패가 함께 남아 메인 모델 채택 보류. 모델과 해상도 효과를 분리했다고 주장하지 않는다.

- 최신 진단: [EXP-0003](docs/experiments/EXP-0003-fcos-candidate-diagnostics.md). 030 84~96초 361프레임 동일 설정 계측·최종 출력 불변 확인. 90초 raw person 최고 0.337676, 낮은 점수 후보는 존재하며 시각적 원인은 미확정. 진단 후보/시간과 최종 검출/기존 FPS를 혼동하지 않는다.

- 최신 점수 비교: [EXP-0004](docs/experiments/EXP-0004-fcos-score-threshold-comparison.md), [ADR-0009](docs/decisions/ADR-0009-fcos-threshold-adoption-hold.md). 동일 네 구간 2,060프레임·35검수 프레임, 0.5/0.4/0.3/0.25 비교. 일부 복원과 중복·배경 의심·연결 단절 공존, 기준 하향 채택 보류. 0.5 정확 재현, 테스트 16개 통과. 기본 0.5 유지가 최적성/모델 채택은 아님.

- 최신 추적 비교: [EXP-0005](docs/experiments/EXP-0005-bytetrack-cache-comparison.md), [ADR-0010](docs/decisions/ADR-0010-bytetrack-cache-comparison.md). 사용자 승인으로 ByteTrack high-only/low 2차 연결을 기존 캐시에 비교. 국소 개선과 중복·배경·부분 신체 실패 공존, 기본 tracker 교체 보류. A 정확 재현·24테스트 통과. 예측 좌표로 이벤트 생성 금지.

## 필수 규칙
1. **사실의 출처 분리:** `논문에서 보고`, `데이터셋 문서`, `로컬에서 확인`, `추정/가설`을 명확히 구분. 실측하지 않은 FPS·정확도·지연·VRAM 사용량은 절대 쓰지 않음.
2. **결정 전에 근거:** 기술 선택 시 연구 사례, 현재 요구사항, 데이터/장비 제약, 비교 대안, 선택 근거, 뒤집을 조건을 `docs/decisions/`의 ADR로 기록. 선택 변경 시 기존 ADR 삭제 금지.
3. **실험 재현성:** 실제 실험은 `docs/experiments/TEMPLATE.md`에 따라 입력·라벨·평가 지표·코드 SHA·실행 명령·성공/실패 결과를 기록.
4. **데이터 우선:** 처음부터 전체 데이터셋 다운로드·파인튜닝·웹 앱 제작을 진행하지 않는다. 소량 영상과 라벨 구조·라이선스·시각적 관찰 가능성부터 검증. 현재 별도 승인된 결과 조회 웹은 최상단 세팅 범위로 진행한다.
5. **저작권/보안:** 영상, 원본 데이터, 가중치, 토큰, .env, 개인정보, 대용량 출력은 Git에 추가하지 않음. 게시/재배포 허용 범위는 직접 확인.
6. **안전 판단 범위:** 영상만으로 '권한 없음'이나 '허용 하중 초과'를 판정하지 않음. 우선 시각적으로 확인 가능한 이벤트 후보를 대상으로 함.
7. **평가 무결성:** 정답은 기존 메타데이터 또는 사람이 검수한 라벨만 사용. 모델 예측을 정답으로 취급하지 않음. 영상 누수·카메라 중복·학습/평가 분할 조건 확인.
8. **작업 단위:** 작은 변경 단위로 커밋, 변경 이유·명령어·테스트·한계를 요약. 최신 승인된 세팅 범위의 최소 의존성/역할/웹 구현은 재승인 없이 진행. 범위를 넘는 대량 다운로드·학습·새 API 결제·전역 설정 변경은 별도 확인. 실험의 과거 승인 범위는 해당 ADR에 보존한다.
9. **실패도 기록:** 오탐/미탐, 다운로드 실패, 예상과 다른 데이터, 취소한 모델 후보도 기록.
10. **역할 분담:** 총괄은 작업 배정·검토·통합, 하위는 배정된 구현/실험/평가, 사용자는 영상 의미와 중대한 범위 선택을 담당한다. 모델 기반 검토는 자동 객관성 인증이 아니다.

## 지금 바로 수행할 작업
현재 [LOCAL_SETUP_REPORT](docs/orchestration/LOCAL_SETUP_REPORT.md)의 실제 검증 상태와 [CODEX_NEXT_TASK](docs/CODEX_NEXT_TASK.md)를 읽고 이어간다. 이미 확인한 모델/세팅을 매번 다시 설치하지 않는다. 버전·계정·권한 변경으로 재검증이 필요하면 근거를 기록하고 차단된 항목만 보고한다.

## 세션 종료 전
- `docs/HANDOFF.md`의 '최근 확인 결과', '남은 문제', '다음 결정'을 업데이트.
- 완료·미완료를 명확히 구분하고 실제 변경 파일 및 커밋을 안내.
- 세팅은 `docs/orchestration/LOCAL_SETUP_REPORT.md`에 실제 모델·effort·화면 주소·시작/중지/복구·테스트·미완료를 기록. 문서만으로 설치 완료 선언 금지.

## GitHub 기록 운영 (사용자 지시, 2026-10-26; 세팅 역할 보완)
- 개발·실험은 로컬에서 수행하고, 완료한 작업 단위별 코드와 문서를 검토·커밋·푸시한다. 이 범위의 커밋·푸시는 사용자가 지속적으로 승인했으므로 매번 재승인을 요청하지 않는다.
- 병렬 작업 시 하위는 자기 worktree의 배정 파일만 수정하고 총괄이 검토 후 main 통합/푸시를 관리한다. 공유 main 동시 push 금지.
- 실험 결과·측정 조건·기술 선택 근거·오류 해결은 해당 docs에 기록한다. 미실행 결과나 미확정 결정을 완료로 표현하지 않는다.
- 원본 영상·추출 이미지·모델 가중치·대용량 출력은 Git 제외 로컬 경로에만 보관한다. runtime DB·raw agent 로그·인증 관련 파일도 Git 제외한다.
- 커밋 전 변경 파일, 스테이징 내용, 제외 파일을 확인하고 의도한 코드·문서만 명시적으로 추가한다. 토큰·환경 파일·개인정보는 제외한다.
- 푸시 후 원격 반영을 확인하고 커밋 ID·변경 내용·검증 결과·로컬에만 남긴 파일을 사용자에게 알린다.
