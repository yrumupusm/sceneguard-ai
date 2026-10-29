# 최신 인수인계 — BATCH-0005 고정 ROI 비교 실행 완료

2026-10-29 KST. [종합 결과](experiments/BATCH-0005-summary.md), [EXP-0023](experiments/EXP-0023-c6-pose-roi-comparison.md), [전달 기록](experiments/BATCH-0005-delivery.md)을 우선한다. 고정84/90/94초 full/C6에서 신규5개·기존90 full 재사용1개를 완료했다. 박스/관절 추정은84 full2/24→ROI3/38,90 full0/0→ROI1/12,94둘다0/0이다. 오류/retry0, sample forward5·별도 warmup1이며 출력 증가가 실제 관절 복원이나 행동 성능 충족은 아니다.

세 비교 이미지의 사용자 검수를 한 번 묶어 요청했고 실제 인물/관절 대응·가림/중복/ROI 절단은 답변 전 미확정이다. 기본 적용·추적·행동 규칙·결합은 보류한다. 기존40 jobs/attempts·공식 라벨·CV/VLM·weights·환경·기본 설정을 유지하며 **추가 GPU 작업이나267전체 처리를 자동 시작하지 않는다**. 다음 결정은 새 세 이미지의 실제 대응 확인 한 가지다. 아래 승인 문단은 완료된 이번 배치의 범위 이력이다.

---

# 신규 인수인계 — BATCH-0005 C6 고정 ROI vs 전체화면 Pose 비교 (2026-10-29)

**새 사용자 승인:** E01_030 84/90/94초에서 사전 고정 카메라 C6 ROI를 이용해 YOLO26m-Pose 사람·관절 누락이 개선되는지 비교한다. [이번 고정 실험 계획](experiments/BATCH-0005-c6-pose-roi-comparison-plan.md), [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md) 최우선.

- 이전 BATCH-0004/EXP-0022의 **공식 YOLO.predict(030_090 full-frame) 사람0/관절0 실제 Results를 그대로 재사용**, 이전 007_064 full-frame 출력2행/추정23은 다른 장면 참고 결과로만 보존한다. 이전 실험 이력·코드/weight/기준·queue/검토 등은 불변.
- **총 6개 조건, 새5회만**: 030 84 full/C6, 030 90 full(기존 재사용)/C6, 030 94 full/C6. C6 normalized xyxy `[0.28,0.20,0.75,0.80]`; 원본1920×1080의 crop `RGB[216:864,537:1440]`이며 사람/라벨에 맞춰 ROI를 다시 선택하지 않는다. 같은 공식 YOLO26m-Pose 8.4.192 / 640 / FP32 / conf0.25 / nmsFalse public API, weight/학습/새 데이터/VLM 재추론 없음.
- 별도 batch05_pose/EXP-0023 경로, CPU 색상/좌표 offset·PTS·legacy raw90 hash 테스트 → source/config 고정 및 Astra 독립 검토 → 기존 Run/canonical GPU queue 직렬·free≥6144MiB 게이트 → 실제5회 실행. 90 C6가 0개여도 기술 성공이라면 나머지84/94까지 비교.
- ROI 결과는 local crop coordinates: 원본 좌표로 x+537,y+216 **한 번만**. full-frame 결과는 원래 native 원본좌표. 실제 사람 bbox/손목·엉덩이·무릎·발목 일치 여부, crop 절단·가림·중복/오검출을 **원본/원래 Full overlay/C6 overlay 3시점**으로 검수. 개수만으로 복원이라 말하지 않음; 물리 울타리 상단/완료/추적/규칙/결합 판단 이번 배치 아님.
- 독립 리뷰/metrics/기존 웹 등록·이미지 display 검증/GitHub remote byte 확인까지 진행. CCTV·좌표·weights·오버레이/raw artifact/receipt는 **로컬만**, 코드/비식별 결론만 GitHub. 배치 종료 뒤 자동 후속 모델·실험 예약하지 않음. 현재 문서 게시 = **로컬 추론 시작 아님**.

---

# 최신 인수인계 — BATCH-0004 공식 추론 성공·관절 품질 확대 보류

2026-10-29 KST. [종합 결과](experiments/BATCH-0004-summary.md), [EXP-0022](experiments/EXP-0022-yolo26-public-predict.md), [독립 검토](reviews/EXP-0022-independent-review.md), [전달 기록](experiments/BATCH-0004-delivery.md)을 따른다. 공식 public API의 두 Results/비교 이미지 생성은 성공했다. 오류/retry0이며 sample forward2와 warmup1을 구분한다. 030:90은 기존 사람 관찰에도 출력0,007:64는2행/관절 추정23개로 실제 대응은 별도 검수다. 필수030 근거가 없어 remaining265·규칙·추적·추가 GPU 작업을 보류한다. 기존 EXP-0021 실패 및 환경/기본 모델은 유지한다.

---

# 보존된 신규 인수인계 — BATCH-0004 공식 YOLO26m-Pose API 복구 (2026-10-29)

- 사용자는 **BATCH-0003의 두 실험이 모델 품질 문제가 아닌 자체 adapter의 end2end 및 visualize 인자 오류**였음을 확인하고, **같은 공식 yolo26m-pose.pt를 YOLO.predict() 공개 API로 고쳐 실제 원본 두 프레임의 관절 출력을 확보**하도록 별도 신규 범위를 승인했다. **실행 명세:** [BATCH-0004 계획](experiments/BATCH-0004-yolo26-pose-recovery-plan.md) + [현재 지시](CODEX_NEXT_TASK.md).
- **역사 보존:** BATCH-0003/EXP-0021은 실제 모델 load2/정상 출력0/두 adapter 오류/남은265장 미실행으로 종료했다. 그 실패 jobs/reviews/metrics/과거 소스 freeze를 덮거나 세 번째 재시도 하지 않는다. 이번 실행은 **BATCH-0004/EXP-0022의 새 코드·job/attempt/보고서**로 기록한다.
- **동일 자료:** ultralytics 8.4.192 및 공식 pose checkpoint SHA 2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4, .venv-pose-batch03, frozen267 source/native PTS/RGB. 다른 모델/학습 없이 새 구현의 **공식 YOLO.predict** 실행, 원본 RGB→연속 BGR numpy, Results 박스/17관절 데이터를 직접 사용. 원래 low-level inference와 달리 공식 predictor는 fuse+warmup을 수행하므로 실제 실행 조건·시간을 별도 구분.
- **실행 전 CPU 게이트:** 정확한 공식 함수 signature/모든 인자 확인 + RGB/BGR/Results/unknown0명/NaN/좌표·해시·native PTS·큐 보존 synthetic tests, 별도 source freeze 및 Astra 독립 검토. GPU는 기존 Run/canonical queue/free≥6144MiB·live lease만 사용.
- **실측 우선:** 030_090, 007_064 정확한 source native PTS에서 실제 **2개 pose 결과 및 원본/관절 overlay**를 먼저 만든다. 인물·관절이 원본에 맞게 보이는지 확인하고 품질이 충분한 경우에만 smoke2 재사용 + remaining265장 한 번. 실패/품질 불충분 시 규칙·추적·fusion하지 않는다. 개발 장면의 사건 완료/사람별 정확도/F1/FPR은 근거 없음.
- **전달:** 신규 결과 독립 리뷰와 로컬 원본/overlay·보고서·metrics 기존 웹 등록/실제 재생·seek 및 GitHub remote commit/hash를 각각 확인. 미디어/weights/raw coordinates/receipts 등은 로컬 전용. 이번 approval을 끝내면 새로운 무인 GPU 작업·모델 개선은 시작하지 않는다. **현재 GitHub 문서 게시 자체는 실제 로컬 실행이 아니다.**

---

# 최신 인수인계 — BATCH-0003 실행 실패·종료

2026-10-29 KST. [종합 결과](experiments/BATCH-0003-summary.md), [EXP-0021](experiments/EXP-0021-yolo26m-pose.md), [독립 검토](reviews/EXP-0021-independent-review.md), [전달 기록](experiments/BATCH-0003-delivery.md).

YOLO26m-Pose/ultralytics8.4.192 한 모델을 격리하고267고유 입력을 고정했다. 원소스 b52ac22의 smoke는 로딩 후 구조 검사 실패, 수정소스1b12d85의 유일한 retry는 첫호출 visualize 인자 TypeError다. 모델 로딩2회/완료예측0개/저장pose0개이며 remaining265·규칙은 미실행. 원 실패38개 queue row를 보존한 별도 correction job으로 논리적 retry1을 소진했다. 실패는 어댑터 문제이고 실제 관절 품질은 미측정이다. **새 GPU 작업을 예약하지 않는다.** 기존 CV/VLM·환경·라벨·결과를 유지한다.

---

# SceneGuard — 다음 작업과 대화 인수인계

## 신규 사용자 승인 / 다음 실행 — BATCH-0003 YOLO26m-Pose (2026-10-29)

- **새 범위:** 사용자는 기존 모델 교체만으로 행동 분류가 해결되지 않은 점을 확인하고, **재학습 없이 YOLO26m-Pose 사전학습 가중치로 사람 관절·울타리 넘기 동작 단서**를 검증하라고 승인했다. [고정 계획](experiments/BATCH-0003-yolo26-pose-plan.md)과 [현재 지시](CODEX_NEXT_TASK.md) 우선.
- **베이스라인 보존:** BATCH-0002는 입력 감사 완료, FCOS vs RF-DETR Medium 11프레임 품질 미확정, Qwen2B vs 4B 16 view에서 4B 형식 실패6, 새 모델 두 개 기본 적용 보류, CV+VLM 미연결 상태로 종료. 현재 main의 기존 실험/채택 상태를 덮어쓰지 않는다.
- **실험:** 신규 weight 1개 `yolo26m-pose.pt`만, 격리 환경·GPU canonical queue/free6144MiB gate. 11개 정확한 native PTS + 030[88,94), 007[62.5,67.5), 007[47.5,52.5), 030[50,55), 004[60,65)에서 원본≤10fps/고유≤300프레임. 2프레임 smoke 후 1회 실행. 사람/관절의 **실제 관측 가시성**부터 검토; 좋을 때만 단1개 무학습 사전등록 규칙과 시간 일관성 평가. VLM 재추론, 새 기본 모델 채택, 전체 영상 처리나 별도 학습 없음.
- **한계:** q04 시도/발 올림 완료 미관찰, 030 약90초 여러 사람 올라탐·개별 완료 미확정, q02/q05 접근뿐, v01 줄 넘음. 사람별 박스/관절 프레임 GT 없음. 정확도/F1/시간당 오탐률 주장 금지. 사람 누락 시 규칙/결합 구현을 멈추고 그 실패를 보고한다.
- **전달:** 기존 Astra max/Sol high/Astra high·단일 Run/queue, 독립 리뷰, 기존 읽기전용 로컬 결과 페이지 및 정상 GitHub push/원격 byte 확인. 공개 코드/비식별 요약만, 원본·weights·raw 좌표·영상은 로컬. 사용자가 승인한 한도를 완료하면 후속 실험 자동 실행 없이 종료. 현재 GitHub 문서 갱신은 **실제 로컬 GPU 실행이 아님**.

## 최신 상태 — BATCH-0002 모델 대안 비교 종료 (2026-10-29)

- 최신 [종합 결론](experiments/BATCH-0002-summary.md), [입력 감사 EXP-0018](experiments/EXP-0018-input-audit.md), [CV EXP-0019](experiments/EXP-0019-cv-comparison.md), [VLM EXP-0020](experiments/EXP-0020-vlm-comparison.md), [전달 기록](experiments/BATCH-0002-delivery.md)을 우선한다. 사용자 지침 `1a06f6c`는 로컬 변경·기존 결과를 보존해 fast-forward로 받았으며 강제 reset/stash는 없었다.
- 기존 Astra max 총괄, Sol high 담당, Astra high 검토와 Run `run_3d23462a014a`/canonical GPU queue를 사용했다. CV 담당 `task_5dbd99e6ff9a` / `ctx_0578048b13d3`, VLM 담당 `task_cf14cc142ed2` / `ctx_0d176c9c2889`, VLM 독립 검토 `task_f5ce741eef6c` / `ctx_0fd8c4b82c38`. 실효 모델·역할과 검토별 별도 Task는 각 보고서에 기록했다.
- 입력 감사 20개 저장 variant/200개 프레임 관측/103개 고유 source RGB를 대조했다. q original processor RGB/expanded prompt 미저장 한계는 유지한다. v original 입력과 새 4B의 RGB/확장 질문은 정확히 대조했다. 사용자 새 관찰 q04 발 올림, v01 줄 넘은 뒤 반대편에 서 있음, v03 문 옆 바위 올라섬을 별도 revision으로 기록했다.
- RF-DETR Medium FP32는 11개 native PTS에서 예측을 한 번씩 완료했다. FCOS 030:90 최종 박스 0→RF 1이지만 실제 사람 대응·부분 신체·배경 구분은 미확정이다. 박스 수를 복원 성공으로 해석하지 않는다. CV 2개 job/attempt, 오류/OOM/retry 0이다.
- Qwen4B NF4는 원래 질문/기존 ROI/10프레임 2fps를 유지해 16개 view를 한 번씩 생성했다. q01/q06 B·C, v01/v03의 6개 형식 실패를 판정 null로 남겼다. q02/q03/q05의 여섯 유효 view에서 잘못된 후보 4→0, q04 C 유지/B 누락, v04 후보 제거를 확인했으나 완료 근거 오류와 양성 v01 출력 실패가 남았다. 기본 적용은 보류다.
- 오류 복구: v01 첫 attempt `c3ae75c0bcdc4ce0af2cfb4a694edd1b`가 모델 로딩 전 과거 metadata의 `rgb_sha256` 부재로 실패했다. 원 메타데이터·원 실패·12개 성공 출력/old33 rows를 보존하고 per-frame/full-frame 집계 해시를 함께 확인하는 CPU 호환성 수정만 했다. 별도 source freeze `78ba67d`, 연결된 retry1 job의 첫 생성 attempt `3bc7c54ea12d47edaadb45da6025e618`로 논리적 retry 한 번을 사용했다. 기존 q 소스는 `952c52f`, 나머지 네 v는 수정 소스다. SQL trigger/queue schema 변경이나 source hash 우회는 없다.
- 28개 관련 회귀 검사와 전체 115개 중 113개 통과/2개 skip, 실제 네 v의 CPU processor parity 검증을 기록했다. 초기 fixture 오류와 기존 interruption 테스트의 순서 경합 실패는 별도 보존한다. VLM 새 queue 합계17 jobs/17 attempts는 16성공+준비 실패1이며 생성은16회다. 추론 오류/OOM과 파싱/행동 오류를 분리한다.
- 비용: 동일 저장16 view의 2B 평균 생성3.105초·준비/전송/생성 allocator peak 최대4.345GiB, 4B 평균7.430초·생성 peak3.763GiB/로딩 peak3.830GiB. 초기화 시점이 달라 동일 범위의 메모리 절감률로 읽지 않는다. 새 load/원본 디코딩/processor/파일 검증/queue 비용은 별도다. 용량과 양자화가 함께 달라진 관측이며 실시간 관제 지연이나 모델 크기 단독 효과가 아니다.
- **결정:** 신규 두 모델 기본 적용 보류, CV+VLM PoC는 실제 상호 보완 증거 부족으로 미실행. 기존 CV/MVP/EXP-0006 보류 유지. 개발창·미확정 사람 정답으로 정확도/F1/FPR을 만들지 않는다. 다음 별도 검증 후보는 동일4B/질문에서 배경 기준 고정 ROI 입력 한 축이며 이번에 실행하지 않는다.
- 입력/CV/VLM의 독립 검토·기존 웹 등록·실제 브라우저·GitHub 확인은 전달 기록을 따른다. 주요 단계 커밋은 `3e9a6bb`(감사 계약), `e0dc11a`(검토/검출기 소스), `d5f6406`(입력 전달), `952c52f`(4B 소스), `9ee6753`(CV 결과), `78ba67d`(입력 호환성/한정 retry)이며 최종 결과/전달 커밋은 별도 이어진다. 로컬 미디어·raw 결과·weights·환경·DB·인증정보는 제외한다. **배치 종료 후 추가 GPU 작업·모델 탐색·자동 재시도를 남기지 않는다.**

## 보존된 상태 — EXP-0017 실제 비교 종료 (2026-10-29)

- 사용자가 인증을 완료한 뒤 기존 미게시 main을 정상 HTTPS git push로 `64ab297`까지 동기화했다. 강제 push/reset/stash는 하지 않았다.
- GPU 최초 여유 8129 MiB, 각 runner gate 8015–8026 MiB로 고정 최소 6144 MiB를 통과했다. 기존 Run/단일 queue에서 4개 job·20개 새 응답 완료, 오류/OOM/retry 0. 원래 EXP-0016 저장 namespace의 새 attempt들을 EXP-0017로 별도 기록했다.
- 실행 Sol high Task `task_032ba4cbc816` / Dispatch `ctx_65e6cdf6b6f4`, CPU 평가 Sol high `task_92a58bc9727e` / `ctx_cce6645f155d`, 독립 Astra high `task_deaaa68f6feb` / `ctx_027c0ebf6c1f`. 실제 launch receipt로 model/effort를 확인했다.
- [비교 결과](experiments/EXP-0017-prompt-evidence-results.md): q 비시도 5창의 candidate B 2→3, C 2→2. q04 C 후보 유지와 완료 과장 공존, B 누락 지속. v 양성 후보 1→0, 음성 후보 1→1. 수정 prompt 기본 적용 보류; 기존 구성도 성능 부족이다.
- [평가 코드/노트](experiments/EXP-0017-evaluation-notes.md): 21개 CPU 테스트,131개 실제 파일 대조. q 과거 processor RGB/확장 prompt 미저장 한계, v 2 source group·완료 미평가를 보존한다. 정확도/F1/오탐률은 null.
- [전달 기록](experiments/EXP-0017-delivery.md)에 독립 검토·등록·실제 브라우저와 GitHub 증거를 따로 기록한다. 실행 중 담당3 카드 표시는 확인했다. 종료 이후 새 GPU 작업/튜닝은 자동 시작하지 않는다.
- Astra 독립 검토 PASS와 immutable binding/등록 완료. 실제 브라우저 담당3 → EXP-0017에서 보고서·14 metrics/2 graphs·review와 기존 원본 참고 클립8개 재생/seek/poll 보존 통과. 공개 모델 raw 답변/UI 기능 추가는 하지 않았다. GitHub commit `622e360de27329777a0964dde11c76333acac2ed`의 정상 push 및 원격 assignment/catalog/report/metrics/review/binding byte 검증 통과. 후속 전달 문서 커밋의 최종 HEAD 검증은 로컬 receipt에 남긴다.
- 아래 EXP-0016의 미실행·인증 차단은 당시 이력이며 EXP-0017의 현재 상태로 읽지 않는다. 영상/프레임/가중치/raw 응답/runtime/receipts는 로컬 전용이다.

## 최신 상태 — EXP-0016 단일 프롬프트 변경 (2026-10-28)

EXP-0015 사용자 라벨과 원응답을 대조해 q02/q03/q05 false candidates의 공통 문제를 “접근/보행 서술만으로 stepping/completion 선택”으로 좁혔다. 저장 결과는 관찰된 오류 양상을 보여주지만 원인 설명은 확정할 수 없다. 개선 가설은 Qwen shared prompt 하나에 프레임 순서에 따른 신체/경계 상대 움직임을 요구하는 것이다. 모델, weights, resolution/ROI, frame sampling/PTS, generation, schema, parser/postprocess는 유지한다. [ADR-0017](decisions/ADR-0017-qwen-temporal-evidence-prompt.md), [EXP-0016](experiments/EXP-0016-prompt-evidence-rubric.md) 참고.

- 담당 구현 Sol high `task_0d088b4695b4` / `ctx_d6e47aa9926b` 완료; independent-v comparison Sol high `task_6eb2c3c319d6` / `ctx_ac13ea840666` 완료. 같은 Run `run_3d23462a014a`.
- CPU: `.venv-vlm`에서 `tests_mvp` 107 tests, `.venv-orca-lab`에서 queue suite 14 tests 통과. 새 prompt 12 / independent path 15를 포함. 기본 system Python에서는 PyAV 미설치로 decoder 3개가 skip됐으나 VLM 환경에서 통과. 한 번의 queue attempt-order 테스트 실패는 isolated 및 전체 재실행 통과로 보고서에 보존.
- **실제 새 모델 실행 없음.** EXP-0016 실행 사전검사 Sol high Task `task_305549d14771` / Dispatch `ctx_65256d02af82`가 14:36 UTC GPU 8464 MiB used / 1590 MiB free / 99%를 보고하고 중단했다. canonical MVP preflight 6144 MiB free 미달. queue aggregate EXP-0016 jobs/attempts 0/0, model load/inference 0. 기존 큐 우회/종료, preflight 완화 금지.
- 추가 사용자 라벨: v01 E01_004 60–65 attempt/progress (completion not assessed); v02 E01_004 0–5 non-event; v03 E01_021 65–70 attempt at a gap beside the door, not door passage, exact boundary association ambiguous (completion not assessed); v04 E01_021 0–5 non-event. q01–q06과 다른 source windows지만 camera/site independent blind test는 아님. 프레임에 라벨/file/event metadata를 함께 넣지 않음.
- MVP summary의 현재 수치는 EXP-0015 기준: no-crossing 5, attempt/progress positive 1, primary positive0. q06 only E01_030 155–160 no person/event. E01_031 EOF observation is not transferred to E01_030.
- 코드·CPU 테스트 및 최종 resource-gate 기록에 대한 Astra review와 report/metrics SHA addendum이 통과했다. 행동 출력/성능 검토는 아니며 inference 결과는 없다.
- 로컬 완료 등록: EXP-0016 `inconclusive / blocked / adoption_on_hold`; report/metrics/review hash current. Astra final binding addendum PASS. 브라우저 `http://127.0.0.1:8765/`에서 slot3 카드, report, metrics 2 graphs, review 및 v01–v04 원본 참고 클립 재생/1.5초 seek/decode와 polling 유지 확인; receipt `runtime/EXP-0016/browser-local.json` (ignored). 카드 작업 상태는 resource gate에서 실패로 표시되며, 이는 추론 실패가 아니다.
- GitHub: WSL `git push` 인증은 사용할 수 없었으나, connected GitHub Git Data API로 동일한 local tracked tree를 fast-forward 게시했고 `verify_delivery github` passed. remote main commit `80ac3d36705132bc27324c04796da945bec3b64c`; receipt `runtime/EXP-0016/github-local-r2.json` (ignored). 로컬 commit IDs와 API 생성 remote commit IDs는 다르다.
- EXP-0016 세팅/차단 기록 및 화면/게시 전달 완료. 성능 효과·모델 비용·q/v 출력은 미측정. prompt 채택 보류; GPU 여유 ≥6144 MiB인 새 실행 Task에서만 비교 재개.

## 최신 상태 — EXP-0015 사용자 검수 반영

2026-10-28. 사용자는 EXP-0014에서 만든 원본 전용 q01–q06을 직접 확인해 다음과 같이 한정된 창 라벨을 제공했다: q01 차량만 통행, q02 접근 후 종료, q03 접근만, q04 넘기 시도/진행은 보이나 완료 전 종료, q05 세 명 중 한 명 접근, q06 사람/사건 없음. 이를 저장 응답에 별도 EXP-0015 revision으로 반영했다. EXP-0014 parent records와 EXP-0013 원문/공식 라벨은 불변이다.

- 결과: primary 3개는 모두 비사건이며 후보 B 2/3, C 1/3. 진단 q03/q04/q06은 후보 B 0/3, C 2/3. 6개 전체는 B 2/6, C 3/6. 확인된 비사건 5개에서 양쪽 각각 2개 후보가 남고, 유일한 시도 양성 q04에서는 B가 놓치고 C가 후보를 냈다. 이는 작은 개발 표본 진단이지 오류율/정확도 추정이 아니다.
- 미확정 5개는 unknown으로 유지하고, d030_90은 독립된 부분 양성으로 보존했다. primary 양성 0이므로 정확도·precision·recall·F1·FPR·시간당 오탐은 null. 모델/구성 자동 채택 보류다.
- 담당 Sol high Task `task_dbf80c1a9687` / Dispatch `ctx_f36ccf3479f0`, 독립 검토 Astra high Task `task_ff0208b63e32` / Dispatch `ctx_155bbf7a2164`; 기존 Run을 재사용했다. 16개 focused CPU tests와 metrics validator 통과. 등록은 담당3에 연결됐다.
- 기존 화면 `http://127.0.0.1:8765/`에서 실제 slot3 카드, report/reviewer, 6 metrics·2 graphs, q01–q06 영상 재생/seek를 확인했다. GitHub 게시 확인과 브라우저 확인은 별도 receipt로 각각 통과했다. GitHub 검증 commit `b0bceb41d4b397c834668d33a445fdd687a4b893`; 뒤이은 handoff 상태 반영은 최종 커밋으로 추가 게시한다.
- 새 추론/모델/GPU/web 개발 없음. 로컬 미디어·runtime receipt는 Git 제외. 다음 작업은 독립 카메라/세션을 평가 단위로 하는 사전 고정 검증 계획이다. [EXP-0015](experiments/EXP-0015-user-label-revision.md), [다음 작업](CODEX_NEXT_TASK.md), [전달 기록](orchestration/MVP-0001_DELIVERY.md).

## 최신 상태 — EXP-0014 저장 출력 평가 (2026-10-28)

- 최신 사용자 지침 commit `c73d217`을 fast-forward로 가져왔다. local 작업 상태를 확인·보존했으며, 평가 전에는 frozen manifest 이외의 미커밋 파일이 없었다.
- EXP-0013 실제 전체 처리와 기능 prototype은 완료. 새 GPU 추론 없이 EXP-0013의 12개 창 B/C 24개 결과를 EXP-0014로 추출·대조했다. 24/24 pair trace와 88 source file unchanged, 평가기와 event 회귀 포함 CPU 테스트 21개 통과.
- B candidate 4/12, C 5/12는 출력 빈도만 뜻한다. unknown 11개, 부분 양성 1개, full-window 확정 음성 0개라 행동 정확도/precision/recall/F1/FPR/시간당 오탐 null. 둘 다 자동 적용 보류. 세부 표는 [EXP-0014](experiments/EXP-0014-mvp-small-evaluation.md), 정리 요약 [MVP-0001](experiments/MVP-0001-summary.md).
- 출처 정정 적용: 사용자의 030 약90초 언급은 행동 존재 부분 관찰, 030 약84초는 해당 순간 서기/접근, 031 종료 시 집단 미완료는 030의 근거가 아님. 007 56.633→56.667 박스 변화는 ChatGPT 시각 검토이지 사용자 확정 정답이 아님.
- Astra high 독립 검토 2회가 final hash에 연결됐다. 초기 review에서 완료 등록이 막힌 metrics schema 누락을 발견했고, standard `experiment_id`/`metrics[]`를 추가해 실제 validator와 graph source hash를 검증했다. 최종 바인딩된 report `f6c591...d1f75`, metrics `433b93...8de1685`; 최신 review [EXP-0014 delivery review](reviews/EXP-0014-delivery-review.md)는 등록 준비를 통과했지만 행동 성능을 승인하지 않는다. EXP-0014 완료 등록과 기존 로컬 화면 검증, GitHub 게시 및 원격 main 파일 검증은 통과했다. GitHub commit `8cb71f5fca7c01fe6c5a21843da78dfd3d4b66f6`; verification receipt는 로컬 `runtime/EXP-0014/github-verification-final-local.json`에만 보관한다.
- 검수용 원본 구간 최대6개는 `outputs/mvp0001_evaluation/EXP-0014/question_clips/`에 로컬만 생성했다. GitHub·로컬 서비스 확인 뒤 한 번에 질문하고, 새 답은 CPU label revision에만 반영한다.
- 원본 영상·검수 클립·캐시·모델·raw 응답·runtime receipt는 Git 제외. 새 GPU 실행, 새 모델, UI 변경은 하지 않는다.

## 과거 상태 — MVP-0001 실제 처리 및 전달 (EXP-0013 이전)

- **기능 구현·자동 테스트·실제 모델 실행 완료; 행동 성능 및 제품 채택 보류.** 세 원본을 끝까지 처리했으며 결과는 새 단일 비교 ID [EXP-0013](experiments/EXP-0013-mvp-comparison.md)다. EXP-0011/12의 자원 차단 기록과 기존 실험은 덮어쓰지 않았다.
- 전체화면 Qwen과 고정 카메라 ROI Qwen을 기존 GPU 큐에서 순차 실행했다. 새 가중치/탐지기 없이 47개 MVP 테스트, 75개 Orca 테스트가 통과하고 1개 조건부 skip이었다. 실제 결과에서 행동 분류 정답은 확정할 수 없고 accuracy/F1/오탐률을 산출하지 않았다.
- 핵심 사람 확인은 007의 52.5–57.5초 후보(이전 Codex 접근·대기 초안은 확정 정답이 아님), 030 약90초 후보 및 EOF 불완전 상태로 제한한다. 비교 영상은 기존 로컬 웹 페이지에서 접근 가능하도록 등록한다.
- 결과는 담당 슬롯3에 등록했다. GitHub 게시 검증 당시 main HEAD `610bd32508c16359f8f166c377bd236ef9a24a59`와 기존 로컬 화면 `http://127.0.0.1:8765/`을 각각 확인했다. [전달 기록](orchestration/MVP-0001_DELIVERY.md)에 source hash와 local-only receipt 경로가 있다. 웹 기능/디자인 확장은 없다.
- 새 GPU 실행은 이어서 자동 시작하지 않는다. 다음 사용자 확인은 EXP-0013의 007 약56초와 030 약90초/EOF 근거 장면만 검토하면 된다. 확인 전 채택·정답 라벨·성능 주장은 확정하지 않는다.

- 마지막 정리: 2026-10-28
- 현재 단계: **MVP-0001 CPU 구현·입력 준비 완료 / GPU 자원 부족으로 실제 모델 검증 미실행·MVP 미완료. EXP8~10 및 EXP6 채택 보류 보존.**
- 저장소: https://github.com/yrumupusm/sceneguard-ai
- 이전 감사 실행 기준 HEAD: `ba43440`. 감사 문서·검사 스크립트는 같은 작업 단위로 GitHub에 기록하며, 원본 영상·추출 이미지·메타데이터는 Git 제외 경로에만 보관.
- 사용자 운영 지시: 이후에도 작업 단위별 코드·실험 결과·기술 선택 근거·오류 해결 기록을 검토 후 커밋·푸시한다. 상세 절차는 `AGENTS.md` 참고.

## 최신 결과 — MVP-0001 핵심 실행 흐름·자원 차단

- 새 사용자 승인과 [고정 계획](experiments/MVP-0001-plan.md): 최대3구성, 기존 가중치만 사용, 기존 Run/공통 GPU 큐. 방법 담당 Sol/high `task_d32fef262394`, 통합 담당 Sol/high `task_c466b62bf289`, 별도 Astra/high 검토 `task_903274b61857`를 실제 세션 metadata로 확인했다.
- A는 기존 FCOS/ByteTrack C 결과 재사용, B는 EXP8/10 전체화면 Qwen 기준 보존, C는 같은 모델의 기존 배경 ROI 입력. 모델·질문을 사건별로 조정하지 않는다. C1/C4는 전체화면 fallback,006 후기 보행은 ROI 밖이다.
- 원본007/030 개발과013 C4 진단 검증을 고정했다.013은 이전 감사 노출이 있어 blind/독립 장소 테스트가 아니다. 평가 manifest의030 약84/90초 사용자 관찰을 Codex 초안과 구분했으며 정확한 onset/완료 정답은 만들지 않았다.
- 원본3개 CPU 디코딩·시간창 검증:12,754프레임/853고유 표본/172창, 모두EOF.030 마지막 창은 실제1표본이므로 근거 부족 대상. **모델 미실행 준비 검사이며 전체 행동 파이프라인 성공이 아니다.**
- 고정계획·입력·평가·배정은 GitHub `9482dc9`에 게시했고 실제 기존 브라우저에서 EXP11/12 담당 카드의 진행 중·Sol/high·결과 미등록을 확인했다. 새 결과 등록/게시/화면 검증은 별도로 진행한다.
- 실제 GPU job/attempt/generation0. 마지막 durable 관측 여유1,806MiB·사용률99%로 고정 최소6,144MiB 미달이다. 외부 작업 종료·queue 우회 없이 자원 차단으로 정리했다. [종합 결과](experiments/MVP-0001-summary.md), [전달 기록](orchestration/MVP-0001_DELIVERY.md), [독립 검토](reviews/MVP-0001-independent-review.md)를 따른다. 담당2명은 실제 목표 미완료로 native failed이며 코드/CPU 실패나 모델 OOM으로 해석하지 않는다.
- 기존6클립 실제 CPU 전처리와 C1 저장 입력·tensor 동등성을 확인했다. 실제 응답/후보/행동 성능은 없다. 과거 adapter budget 상수 추출 때문에 첫 재사용 검사가 멈춘 것을 특정 소스 SHA·차이 증명으로 수정해 한 번 준비를 다시 했고 실패도 보존했다.
- 후속은 같은 승인 한도에서 GPU 여유 확인→C 개발 비교→B/C 원본3개 전체 분석·평가다. 이번 불변 등록 ID/보고서를 덮어쓰지 않고 새 실행/전달 ID를 사용한다. 자동 대기 job·무인 재개·새 모델 다운로드를 남기지 않는다. 원본·기존 결과·환경·공식 라벨은 보존했다.

## 이전 확인 결과 — 첫 실제 VLM 배치 (2026-10-28)

- [비교표·총괄 결론](experiments/BATCH-0001-vlm-comparison.md), [선정 ADR-0015](decisions/ADR-0015-first-vlm-comparison-batch.md), [전달 상태](orchestration/BATCH-0001_DELIVERY.md). 기존 Qwen에 SmolVLM2-2.2B 한 모델만 추가했다. 후보2개, 기준2+개선1조건, 같은6클립의 총18개 응답이며 독립 표본18개가 아니다.
- 실제 Sol/high 담당3개 Task와 Astra/high 독립 검토, 기존 Astra/max 총괄/Run/공통 GPU 큐를 사용했다. 준비는 병렬, GPU는 세 job이 순차 실행됐으며 inference retry/OOM0. 기존8job/8attempt 및 결과/입력/두 환경을 보존했다.
- Qwen 기준 strict2/6→펜스 제거6/6, 평균 생성2.692초·peak4.342GiB. Smol strict6/6,1.874초·4.519GiB. Qwen 픽셀 예산 대조 strict1/6→6/6,2.919초·4.663GiB. 형식/실행 비용과 행동 이해를 구분한다. 원본 최초 디코딩·클립 확보·큐 대기 제외, 온라인 탐지 FPS 아님.
- Qwen은 넘기를 대기로 설명하거나 근거 없이 완료를 선언했다. 전체 화면 입력을448×768→608×1120으로 늘려도 유효한 행동 개선을 확인하지 못했다. Smol은 enum/근거 모순과 선택지 반복이 남아 추가 조정 없이 보류했다. 기본 CV에 연결하지 않았다.
- 담당1에 EXP8/10, 담당2에 EXP9를 연결한다. `complete` 등록과 `verify_delivery github/browser`를 사용한다. GitHub 반영·실제 서비스/화면 검증 결과는 전달 기록과 로컬 receipt가 원본이며 실행 성공만으로 추정하지 않는다.
- 오류 기록: 준비 단계 Smol 설정 계약/Clip ID/29.97fps PTS 검사 수정; 이후 추론 오류0. Smol 담당이 결과 작성 후 Sol capacity로 멈췄지만 같은Sol/high로 한 번 이어서 커밋·worker_done 완료, 모델 대체·GPU 재실행 없음. 브라우저 이미지 확인 중 timeout은 결과 탭만 재생성해 복구했고 서비스/큐/Orca runtime reset은 하지 않았다.
- **남은 확인:** 02/06 중심으로 원본·실제 입력 시트를 사람이 확인해야 한다. 현재 의미 평가는 기존 검수 초안과 응답 대조이며 정밀GT/독립 평가가 아니다. 자동 다음 실험은 없다. 이번 배치는 보고 후 종료한다.

## 이전 확인 결과 — 실험 전달 절차 (2026-10-28)

- 사용자 지시를 [EXPERIMENT_DELIVERY](orchestration/EXPERIMENT_DELIVERY.md)와 AGENTS/NEXT에 반영했다. 앞으로 배정부터 실제 결과 화면 확인까지 한 작업으로 처리한다. 세부 명령과 최신 검증 범위는 [DELIVERY_VALIDATION](orchestration/DELIVERY_VALIDATION.md)을 따른다.
- Sol high는 등록 CLI, Terra high는 담당 카드, Astra high는 독립 검토를 실제 native Task/Dispatch로 수행했다. 기존 Astra max 총괄/Run/환경/공통 runtime을 재사용했다. 새 모델 다운로드·실험·학습은 없다.
- `complete assign/complete/status`는 보고서·metrics·별도 검토 SHA와 로컬 artifact를 검증한다. 동일 재시도는 중복 없이 처리하며 실패 도중 남은 binding도 EXP ID로 고정한다. `verify_delivery`는 GitHub ref/파일 대조와 실제 브라우저 확인을 분리한다.
- 63개 Python fixture와 Node 카드/보고서 펼치기 검증을 통과했다. 최초 독립 검토의 F1~F4와 수정/재검토는 삭제하지 않는다. 실제 브라우저 결과와 게시 상태는 검증 보고서가 원본이며 코드 통과만으로 화면 완료를 추정하지 않는다.
- **남은 작업:** 첫 실제 새 실험은 아직 배정/실행하지 않았다. 다음 승인된 실험에서 native 진행 상태 카드와 완료 후 보고서·그래프·등록 영상·총괄 검토까지 다시 확인해야 한다. TEST 합성 자료는 격리 runtime 전용이며 공개 카탈로그에는 EXP-0001~0007만 남아 있다.

## 이전 확인 결과 — Orca 로컬 실험실 (2026-10-28)

- [실제 세팅 보고서](orchestration/LOCAL_SETUP_REPORT.md), [ADR-0013](decisions/ADR-0013-orca-local-experiment-lab.md). clean main에서 최신 지시를 fast-forward한 뒤 lab/infra/web/review worktree로 분리했다. 원본·기존 환경 변경 없이 새 `.venv-orca-lab`만 사용했다.
- 총괄 Astra max, 실행기 Sol high, 화면 Terra high, 독립 검토 Astra high를 실제 thread 메타데이터와 실행 기록으로 확인했다. 하나의 Orca Run을 유지하며 세팅 작업만 배정했다. 담당1/2/3은 앞으로의 실험 슬롯으로 아직 미배정이다.
- 공통 runtime `/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab`, GPU 큐는 그 아래 `gpu-queue`. 서로 다른 worktree도 반드시 같은 절대 runtime을 사용한다. SQLite+flock CPU mock 직렬화, 실패 후 다음 작업, 중복 방지/장애 복구를 검사했다. 현재 실제 GPU 명령은 미등록이다.
- 웹 **http://127.0.0.1:8765/**: 총괄→담당1·2·3/미배정→선택 보고서/동일 metrics 그래프/근거 미디어/검토/다음 작업. EXP-0001~0007의 실제 기록을 표시하고 과거 미기록 모델·effort와 최종 정확도는 null이다. EXP5/6 영상4개 재생·seek, EXP7 이미지6개 decode, 파일 부재 안내 확인. 미디어는 로컬 브라우저만 읽었다.
- **32개 fixture 통과** 및 실제 queue/web 재시작 smoke 통과. 기존 2,086파일 size/mtime, 선택430파일 SHA256, 두 환경 freeze 일치. 독립 검토가 stale review/수집기 startup/FIFO/재시작 근거 문제를 찾아 수정했고 초기 보고서들을 보존했다. 최종 좁은 재검토에서 R4도 해결로 판정했다. 전체 검증·게시 내역은 LOCAL_SETUP_REPORT를 따른다.
- 신뢰/업데이트는 사용자가 직접 완료했다. WSL bridge 승인, null launch 모델 필드, TIME_WAIT 재시작 실패, 새 터미널의 빈 환경변수 문제와 해결을 기록했다. 완료 작업자는 worker_done 확인→release→ack로 정리한다.
- **남은 문제:** supervisor 사망 중 timeout 강제 불가, 협력하지 않는 외부 GPU 프로세스 제어 불가, 무인 운영/실제 모델 작업 미검증. 사용자 행동 정답과 카메라 독립성은 여전히 미확정이다.
- **다음 결정:** 기존 VLM 실제 입력 시트와 사용자 검수를 기준으로 소규모 비교 배치의 manifest·중단 조건·후보 제한을 제안만 한다. 새 다운로드/추론/학습/CV 연동은 배치 승인 전 실행하지 않는다. 시작·중지·복구 명령은 LOCAL_SETUP_REPORT를 사용한다.

## 최근 확인 결과 — EXP-0007 독립 로컬 VLM (2026-10-28)

- [EXP-0007](experiments/EXP-0007-local-vlm-action-analysis.md), [ADR-0012](decisions/ADR-0012-local-vlm-clip-analysis.md). 이번 사용자 승인으로만 VLM 금지를 제한 해제. Qwen3-VL-2B-Instruct 한 모델, `.venv-vlm` 분리, 기존 `.venv`/CV/추적/경계 변경 없음. EXP-0006 기본 적용 보류 유지.
- 원본5초6클립(007접근/넘기,030넘기,006통행,001넘기,031접촉·가림), 실행 전 manifest/prompt 고정. 전체화면10프레임/약2fps, 실제448×768/1680영상토큰, 원본PTS·추가sampling0·중복0 확인. 익명 독립대화, 라벨/보고서/CV표시 미제공, 로컬 offline 추론.
- BF16 비양자화 RTX3080 GPU 전용, OOM0. run02 로딩1.205초(캐시 warm), 클립 전처리.111~.141초/생성2.805~10.595초, peak allocated 약4.346GiB. 영상 확보/추출 시간을 제외한 생성 시간을 실시간 탐지지연으로 쓰지 않음.
- 접근/보행 일부 부합하지만 넘기를 문 열기/이동으로 설명하고 의도·문 개폐 근거 환각. 030은 반복으로384토큰 중단. 031 가림도 적절한 판단 유보 못함. 모든 strict JSON 파싱 실패(코드펜스;030은본문도미완결). **기본 도입/자동 CV 연동 보류**.
- 최초run01은 생성 후 UnicodeEncodeError로 응답 본문 저장 실패. 로그/빈파일 보존, UTF-8 명시·token IDs 선저장 후 같은조건run02완료. 원응답/실패 로컬 보존, 프롬프트 수정·의미별 재질문 없음.
- 다음: `outputs/vlm_exp0007/run02/clip*/actual_input_review.jpg`와 보고서 요약을 대조해 검수 기준 확정. 정밀GT/범용성/오탐률 미주장. 사용자 선택 클립 분석이지 자동 사건 발견이 아님. 미디어/가중치/원응답 로컬, 코드/manifest/ADR/요약/lock GitHub.

## 최근 확인 결과 — EXP-0006 후보 뒤 박스 일관성 검토

- [EXP-0006](experiments/EXP-0006-candidate-box-consistency.md), [ADR-0011 고정 기준](decisions/ADR-0011-candidate-box-consistency.md). 기존 C 네 구간 2,060프레임/네 후보 그대로 사용. 검출·추적·경계 후보 생성 재실행 없음.
- 후보 전후 .2초 실제 관측, ≤.2초 쌍의 높이/폭 배율≥1.5 및 상하단 이동 차이 검사. 실행 전 한 세트 고정, 결과 보고 튜닝 없음.
- 007 두 후보는 큰 박스 변화 증거가 있으나 대기 중 관측 누락으로 **근거 부족**(56.833333/56.966667 결정). 030 #3/#4 모두 **판단 유보**(90.5 결정). 모두 emission+.2초. 통과 0, 실제 넘기 후보도 유보해 **기본 적용 보류**.
- 기존 후보를 지우지 않고 pending/통과/유보/근거 부족을 별도 부가. 통과≠침입, 유보≠정상. 006/031 후보0은 개선 아님. 새 모듈은 기본 CV 경로에 연결하지 않음.
- 35테스트, disabled 원래 후보 정확 재현·입력 객체 불변·미래 관측 방지 검증. 핵심 영상은 `outputs/cv_phase2g/video{007,030}/raw_C_review_normal_then_quarter.mp4` 두 개. 원본/기존 후보/검토 상태, 정상→.25배속.
- 사용자 메시지의 007 순간 박스 변화 관찰은 대화 속 ChatGPT 프레임 관찰이며 전 구간 사용자 확정 정답 아님. 030은 Codex 초안 유지. 남은 문제: 과도 유보 비용·안정 부분 박스 통과·정밀 사건 정답 부족. 다음은 두 자료의 검토 효용 확인, 자동 설정 교체/추가 튜닝 없음.

## 최근 확인 결과 — EXP-0005 두 후보 구간 집중 검수

- [집중 검수 초안](experiments/EXP-0005-candidate-focus-review.md). 007 55.9~57.0 / 030 89.6~90.5의 62연속 프레임과 저장된 관측·경계 조건 대조. 새 검출/추적 실행 없음.
- 007 #2는 앞 분홍 신발 인물의 부분→긴 신체 박스 변화(②)가 우세. 56.633→56.667 하단 y 114.70px 변화. 명확한 ID 이동은 관찰 못했으며 겹친 신체 소유 범위는 유보.
- 030 #3 오른쪽/#4 중앙 인물 대응 초안. 실제 넘기와 박스 축소가 함께 작용(④=②+③). 두 track이 모두 한 사람 중복이라고 확정하지 않으며 독립 성공 2건으로도 세지 않음.
- 네 후보 anchor~emission 실제 관측 연속. 007 반대 방향 후보는 방향이 바뀌면 cooldown 대기 없이 허용하는 기존 코드로 설명. ID 연결의 적절성과 bbox 하단의 경계 기준 적절성은 별개.
- 로컬 `outputs/cv_phase2f/{007,030}/raw_B_C_normal_then_quarter.mp4`: 각 파일 정상→0.25배속, 원본 PTS/RAW/B/C/ID·H/L·하단 중심점/예측 점선 표시. 각각 ±1초 포함. 자료 2개만 먼저 사용자 검수.
- **남은 문제:** 사용자 확정 정답 아님. 가림/중복 소유 범위/실제 통과 시점 미확정. **다음 결정:** 박스 범위 시간적 일관성을 확인해 경계 후보를 유보하는 방안 한 가지 제안, 미구현·설정 불변. ID 이동이 확인되면 우선순위 재검토.
- 기존 보고서·출력·공식 라벨 보존. 새 코드도 표시/수치 감사만 수행. 전체 35프레임 재검수 요청으로 확대하지 않음.

## 최근 확인 결과 — EXP-0005 ByteTrack 캐시 비교 (2026-10-28)

- [EXP-0005](experiments/EXP-0005-bytetrack-cache-comparison.md), [35프레임·연속 후보 검수](experiments/EXP-0005-visual-review.md), [ADR-0010 사전 설정](decisions/ADR-0010-bytetrack-cache-comparison.md).
- FCOS 재추론/가중치 다운로드 없이 기존 네 구간 2,060 person 캐시 재사용. A=기존 IoU ≥.5, B=ByteTrack high ≥.5, C=B+low ≥.25·<.5의 2차 연결. 신규 ≥.6, buffer30 등 B/C 공통 고정. 공식 MIT tracker subset 고정 SHA·변경 내역·최소 의존성 기록.
- A 전체 레코드와 기존 EXP-0004/0002 결과 정확 일치. 24테스트, 모든 실제 관측의 캐시 대조, 예측 이벤트 금지, 후보 anchor~emission 연속 관측 검사 통과. 이전 출력/캐시/JSON/config 412파일 보존.
- 경계는 ByteTrack ID와 실제 대응 검출 bbox만 사용. Kalman 예측/미확인 상태는 별도 저장하며 경계 입력 제외. 빈 관측 프레임·PTS gap>.1초는 경계 상태 reset.
- B의 007 50→52초 두 사람 연결, C의 030 넘기/006·031 일부 low 관측 연결에서 국소 이점. C의 007 중복·배경 track 유지, 031 후반 누락 및 가림 정체 불확실도 남음.
- 후보는 A/B 모두 0, C 030 2개(90.300초)·007 2개(56.633/56.767초). 030 실제 넘기와 겹치지만 bbox 부분/완료 판정 유보. 007은 문 밖 접근·서기 중 bbox 하단 변화에 의한 실패 의심, 침입 성공으로 세지 않음.
- 로컬 `outputs/cv_phase2e/review{ID}/continuous_ABC.mp4` 네 영상 + 동일 35이미지 + 030/007 후보 전후 62연속 프레임 카드. 원본 상대 PTS/프레임 수 검증. 관측·예측·low·unconfirmed 표시 구분. 전체 영상 사람별 수동 정답은 미완료.
- **남은 문제/다음 결정:** ByteTrack은 후속 검증 후보이며 기본 tracker 교체 보류. 030 #3/#4, 007 #2·중복·배경, 031 #1의 정체/부분 신체를 사용자와 검수. 006 ROI 밖/프레임 불일치, 카메라 누수/G1E 미확정 유지. 최종 IDF1/HOTA/침입 정확도 없음.
- CPU 캐시 추적/경계 시간만 측정, 전체 영상 추론 FPS 아님. 코드·문서·라이선스만 게시, 영상·이미지·캐시·원시 결과 로컬. 상세 다음 작업은 CODEX_NEXT_TASK.

이하 EXP-0004 및 이전 내용은 당시 이력이며 최신 결정은 EXP-0005를 따른다.

## 최근 확인 결과 — EXP-0004 최종 점수 기준 비교 (2026-10-28)

- [EXP-0004](experiments/EXP-0004-fcos-score-threshold-comparison.md), [35프레임 검수 초안](experiments/EXP-0004-visual-review.md), [ADR-0009](decisions/ADR-0009-fcos-threshold-adoption-hold.md).
- 같은 네 구간 2,060프레임을 각 한 번 추론해 모델 반환 person 캐시를 로컬 저장. 내부 score/top-k/NMS/global cap/입력/가중치 고정, 마지막 ≥0.5/0.4/0.3/0.25만 비교. 조건별 tracker 새로 생성.
- 수집 0.5와 캐시 재생 0.5 모두 기존 EXP-0002의 2,060프레임 레코드 정확 일치. 고정 35검수 PTS 동일, 테스트 16개 통과, 이전 출력·공식 JSON·config 258파일 보존 해시 확인.
- 030 90초 0/0/2/4박스: 일부 인물 부근 복원이나 부분·중복 포함, 왼쪽 사람은 누락. 006/031도 일부 복원. 007 중복과 배경 의심 증가. 차량 앞유리 내부의 실제 사람 유무 등 불확실 판정은 확정 오탐으로 계수하지 않음.
- 030 90초 복원 ID는 0.3에서 2~3프레임, 0.25에서 각각 1프레임. 031/0.4 최장 15.967초 ID는 상점 고정 물체 의심 영역. ID 통계를 실제 사람/성공 건수로 해석하지 않음. 16조건 경계 후보 모두 0.
- **남은 문제:** 사용자 정밀 시각 검수·개별 사람의 연속 대응 미완료, 가림·부분 신체·배경 유보, 006 ROI 밖/4006·4011 차이, 031 접촉/공식 시작/미완료 종료, G1E·카메라 분할 미확정.
- **다음 결정:** 기준 하향 채택 보류, 기본 0.5 유지(최적성 주장 아님). 같은 로컬 비교 이미지의 의미 검수와 연속 구간 정답 확정 우선. 재생 FPS를 모델 속도로 쓰지 않음. 모델/VLM/학습/고급 tracker 추가 없음.
- 로컬 `outputs/cv_phase2d/`: cache{ID}, replay{ID}/t050,t040,t030,t025, review{ID}/compare_*.jpg, temporal_review.json. 미디어/캐시/가중치는 Git 제외. 코드·테스트·문서만 게시.

이하 EXP-0003 및 이전 내용은 당시 이력이며 최신 결정은 위 EXP-0004를 따른다.

## 최근 확인 결과 — EXP-0003 FCOS 후보 소실 진단 (2026-10-27)

- [EXP-0003](experiments/EXP-0003-fcos-candidate-diagnostics.md): 사용자 확인 030 84초/90초의 3명 장면을 기준으로 내부 단계 계측. 원인 가설을 확정하지 않음.
- 같은 설정으로 84~96초 포함 361프레임 재실행, 기존 최종 bbox/score/track_id/PTS 전부 동일. 내부 shadow 후처리도 공식 반환과 매 프레임 정확히 일치.
- 90초 실제 사람 위치와 겹치는 낮은 점수 후보가 있었음. raw 최고 0.337676, 내부 통과 57→NMS 후 11→global cap 후 4→최종 ≥0.5 0. 고득점 후보가 NMS에 모두 제거된 경우 아님. ROI 검출 삭제도 아님.
- 사람별 위치 초안, 내부 score/전체 cap/NMS/최종 필터 탈락 및 억제 박스 관계는 보고서·로컬 검수 카드에 기록. 14개 테스트 통과. 진단용 낮은 점수는 최종 검출과 분리.
- **남은 문제:** 자세/가림에 따른 점수 하락의 인과 원인·사람별 정확한 후보 대응은 미확정. 사용자 제공 bbox는 없으며 Codex 위치 사각형은 진단 초안이다.
- **다음 결정:** 같은 설정의 소량 검수에서 score와 위치 회귀/부분 신체 대응을 분리해 조사할지 검토. 모델 채택/threshold/NMS 변경을 승인한 결과가 아님. 계측 FPS를 기존 FPS와 비교하지 않는다.
- 원본·기존 출력·공식 라벨 보존, 미디어/NPZ/원시 JSON/가중치는 로컬에만 둠. 자세한 다음 작업은 CODEX_NEXT_TASK.

## 최근 확인 결과 — Phase 2B 검출기 비교 (2026-10-27)

- [EXP-0002](experiments/EXP-0002-fcos-detector-comparison.md), [ADR-0008](decisions/ADR-0008-fcos-detector-comparison.md): FCOS ResNet50-FPN COCO_V1 추가 1개, 재학습 없이 실행. 실제 내부 749×1333/padded 768×1344, 모델과 해상도가 함께 변한 비교.
- 같은 네 smoke 구간 2,060프레임, 기존 config/추적 유지. PTS/해시 대조 및 테스트 13개 통과. 기존 EXP-0001·출력·원본 라벨 보존.
- 35개 paired frame에서 사람 일부 복원 확인, 030 넘기 자세/031 가림·006 원거리 누락 잔존. 007 중복 bbox와 연결 모호성, 031 상점 앞 고정 물체 오검출 의심을 기록. 원시 bbox 증가를 정확도 개선으로 취급하지 않음.
- 이번 FCOS 처리 15.285~15.967 FPS, peak allocated 약 434.08 MiB. 기존 SSD 8.937~11.428 FPS/85.35MiB와 비교하되 과거 실행·배경 부하 차이 때문에 속도 우위 확정 안 함.
- 모든 경계 후보 0. FCOS는 후속 검증 후보로 유지하되 메인 채택 보류. 모델/해상도 효과 분리 안 됨. 학습·VLM·고급 tracker·UI 없음.
- **남은 문제/다음 결정:** 031 고정 물체 판정, 중복/미탐 검수, 사람별 시점·음성 범위·카메라 그룹/G1E 확정. 다음 순서는 CODEX_NEXT_TASK를 따른다. 영상 끝 완료 상태와 006 프레임 차이는 해결되지 않음.
- 이미지/추론 JSON/가중치 모두 로컬. GitHub에는 코드·선정 근거·실측 집계·제한/다음 계획만 기록한다.

이하 Phase 2A 및 이전 승인·감사 내용은 당시 이력이다.

## 최근 확인 결과 — Phase 2A 첫 CV 진단 (2026-10-27)

- [EXP-0001](experiments/EXP-0001-phase2a-cv-baseline.md): 사전학습 SSDLite320 COCO_V1 한 개 + 인접 IoU 연결 + 카메라별 유한 경계 규칙을 로컬 CLI로 구현. [실행 계약](design/CV_BASELINE_CLI.md), [선정 근거 ADR-0007](decisions/ADR-0007-phase2a-detector.md).
- RTX 3080 10GB, WSL2/Python 3.10.12, torch 2.5.1+cu124 / torchvision 0.20.1+cu124에서 CUDA 실행 확인. `.venv` 격리, 가중치 14,069,355 bytes 로컬 전용. 학습·VLM·UI 없음.
- 006/007/030/031의 4개 짧은 개발 구간 및 007 전체 클립 진단. 실행별 실제 값·실패·속도·메모리·재현 명령은 EXP-0001의 측정 표를 따른다. 인공 규칙 테스트 11개 통과.
- smoke에서 030은 480프레임 중 1프레임만 사람 검출, 031은 검출 0. 007은 접근 시 일부 검출 후 연결 단절. 낮은 후보 수를 정확도나 정상 판별 성공으로 취급하지 않음.
- 006 후기 보행자는 검출되지 않았고 설정한 가까운 출입문 감시 범위 밖이기도 함. 비이벤트 후보 상태·4006/4011 프레임 불일치 유지. 006/007은 같은 카메라 후보, 전부 development.
- **다음 결정:** 현재 SSDLite320을 메인 모델로 채택하지 않음. 검출 해상도/가림/감시 경계 범위를 먼저 검토하고 다음 비교 실험 여부 결정. tracker 복잡화는 검출 문제와 분리해 판단. 사람별 정밀 시점·검수 음성·카메라 분할/G1E 최종 승인은 계속 미완료.
- 원본/정답/이미지/가중치/추론 JSON/환경 캐시 모두 Git 제외. 출력은 통과 후보이며 물리적 완료·법적 무단침입 판단 unknown.

## 최신 승인/실행 지시 — CV baseline 프로토타입 (2026-10-27)

- **사용자 "응 시작하자" 승인:** [ADR-0006](decisions/ADR-0006-limited-cv-baseline-prototype.md)의 범위에서 **사전학습 사람 검출 1개 + 최소 IoU 연결 + 카메라별 경계 양측 이동**을 소규모로 구현/로컬 실행한다. 이는 **개발 진단 허용**이며 AI-Hub 메인 데이터 최종 G1E 승인, 모델 채택, 정량 성능 검증을 의미하지 않는다.
- Codex가 수행할 지시: [CODEX_NEXT_TASK.md](CODEX_NEXT_TASK.md) (Phase 2A). RTX 3080/WSL2 환경 확인 → 모델·가중치 출처/라이선스 검토 → 최소 Python CLI·PTS 기반 후보 기록·synthetic test → **006,007,030,031 중 2~4개** 로컬 짧은 테스트 → 실패·처리시간 결과 기록/커밋.
- **특히 주의:** 006 공식 JSON frame_count 4,011 vs 실제 디코딩 4,006. 119~132초 근처 보행은 검수된 '정상 정답'이 아니라 **비이벤트 후보**; 사람별 정밀 시작과 카메라 분할 미확정. 초기 실험을 final test나 FP/hour 최종 성능으로 표현 금지.
- 울타리 넘기 시도/물리적 완료·법적 무단침입을 baseline의 단순 2D 선 통과와 동일시하지 않는다. VLM, 재학습, 웹 UI, 대량 추가 자료는 현 범위 밖.
- **지금 GitHub에 업데이트한 것은 작업 지시서·결정 기록·계획이지 로컬 모델 실행 성과가 아님.** Codex 로컬 구현/실험 후 실제 측정 결과를 반영해야 한다.
- 기존 사용자 검수·평가 구성·iSafetyBench/ACCIDENT 등 모든 감사 자료를 보존하고, 다음 실험 결과로 모델/문제 방향을 재검토한다.

## 최근 확인 결과 — 사용자 검수와 baseline 설계 (2026-10-27)

- [별도 사용자 검수](data/AIHUB_INTRUSION_USER_REVIEW.md): 001/007/030 첫 등장≠넘기 시작. 031 약 33초 접촉≠공식 43.600초 시작; 종료까지 모든 사람 완료되지 않음. 미완료 주체 완료 시각은 null로 유지.
- 006 추가로 누적 10개/40,524프레임 디코딩. 약 119~132초 경계 옆 보행 비이벤트 후보를 대조. JSON 4,011 vs 실제 4,006프레임, 표시 FPS 29.97과 PTS 간격 차이 확인. 공식 사건 매핑은 잠정값으로만 기록.
- 후보 `[119,132)`에 실제 390프레임이 있으나 평가 구간 최종 승인 대기. 검수 완료 음성 시간은 아직 0초. 006/007은 새 카메라 중복 후보로 함께 분할.
- [평가 구성안](data/AIHUB_INTRUSION_EVALUATION_PLAN.md): 공식/사용자/평가 레코드 분리, 그룹 누수 방지, 현재 10개는 개발 표본. 최종 blind test 아님.
- [baseline 설계](design/CV_BASELINE.md) / [ADR-0005](decisions/ADR-0005-minimal-boundary-baseline-design.md): 검출+최소 연결+경계 양측 변화 제안. 구현·학습·추론·모델 선택 미실행.
- 실행: `scripts/review_aihub_intrusion_windows.py`, 근거 112프레임 개수/PTS 검사 성공. 공식 JSON 45개 전후 해시와 표본 원본 10개 해시 동일. 원문·이미지 로컬 전용.
- **남은 문제/다음 결정:** 사람별 시작/완료·006 음성 범위 승인, 006 프레임 수 차이 해소, camera/site 그룹 확정, 평가 규칙 동결 후 모델/환경 검토 및 구현 승인. 다음 작업의 구체적 순서는 [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md).

이하 9개 감사 결과는 직전 실행 이력이다.

## 최근 확인 결과 — Phase 1E 실제 JSON 대조 (2026-10-27)

- [감사 결과](data/AIHUB_INTRUSION_SAMPLE_AUDIT.md): 사용자 제공 TL/TS를 재사용. JSON 45개/영상 45개 파일명 연결, 라벨 53구간 구조 검사. 추가 다운로드 없음.
- 표본 9개(기존 8개 + 031), 36,518프레임 전체 디코딩. 실제 JSON 12구간을 원본 PTS에 연결하고 근거 83프레임 추가 검토. 사람의 연속 재생 검수는 미완료.
- 004의 공식 구간은 60.100~62.267초 줄 통과. 이전 28~45초 관찰을 라벨 근거로 사용하지 않음. 공원 울타리 유형 후보 031 추가, 사용자 이미지 4/7번 대응은 최종 확인 필요.
- 021/031/045의 event_length 불일치, 031의 검은 마지막 프레임까지 이어지는 이벤트, 036/039/045의 비시간순 배열 기록. 0/1-based 기준 미확정.
- 013/039/045 같은 구도 후보. 카메라 필드 45개 모두 파일명과 같아 물리 카메라 ID로 신뢰 불가. 검수 완료 비이벤트 0개, Validation 중복 미검사.
- **라벨 확보 문제 해결: 다운로드/로그인 추가 조치 불필요.** 다음은 사용자 연속 재생 의미 검수·정상 구간 확정·카메라 그룹 결정.
- Conditional Go 유지. G1E 최종 승인·모델 구현 보류. 원본/JSON/이미지 Git 제외, 이전 감사 보존.
- 재현: `scripts/audit_aihub_intrusion.py --ids 031 --append`, `scripts/audit_aihub_intrusion_labels.py`. 자세한 환경·명령은 감사 문서.

## 가장 최근 결정 및 현재 지시 — AI-Hub 침입 CCTV (2026-10-27)

- **사용자 선택:** 1차 MVP를 카메라별 출입 경계 통과/넘기 행동 감지와 관제 검토 지원으로 **잠정 선택**. 법적 무단침입·출입 권한은 판정하지 않음. [ADR-0004](decisions/ADR-0004-boundary-crossing-cctv-mvp.md).
- 이유: ACCIDENT의 짧은 사고 클립보다 사용자가 검토한 AI-Hub 침입 영상(일부 약 1~2분)에 정상 전후 구간이 있을 가능성. 단, 실제 정상 정답·길이는 미검증.
- **사용자 제공 전체 미리보기:** 학교 출입구/철제 울타리 구도가 반복. **이미지 4번은 줄 넘기**, **7번은 공원처럼 보이는 장소의 울타리 넘기**. 각 특수 유형은 매우 적어 일반화 성능 주장 불가. 4/7은 공식 파일 ID가 아니라 사용자 제공 이미지 순서.
- 새 자료: [AI-Hub 71850](https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71850) 침입 범주. 로컬 MP4 9개·공식 JSON 대조 결과는 위 최신 기록을 따른다.
- **지금 할 일:** [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md), [AI-Hub 데이터 감사 계획](data/AIHUB_INTRUSION_AUDIT_PLAN.md)을 읽고 이용 조건·로컬 접근 → 6~10개 샘플·시점·카메라 독립성·비이벤트 구간 감사. 산출물 `docs/data/AIHUB_INTRUSION_SAMPLE_AUDIT.md`.
- 판단: Gate G1E 후 메인 데이터 확정 및 **공통 CV 모델+카메라별 ROI/가상선 baseline** 설계 여부 결정. VLM은 CV 실패 사례에 효용이 있는지 이후 평가. 모델 학습·서비스 구현 현재 금지.
- **이 아래 이전 '다음 작업' 표현은 당시 작업 지시의 이력이며 현재 지시가 아님**. Safe and Unsafe Behaviours, iSafetyBench, SteelBench, ACCIDENT 감사 결과·로컬 자료는 모두 보존.

## 최근 확인 결과 — Phase 1D ACCIDENT (2026-10-27)

- [ACCIDENT_SAMPLE_AUDIT](data/ACCIDENT_SAMPLE_AUDIT.md): Kaggle 공식 dataset v9 공개 API 접근·파일별 다운로드 성공. 토큰/인증 파일 접근 없음, 전체 ZIP 미사용.
- 파일 목록 6,452개(33페이지), 실제 MP4 2,027개와 공개 CSV 2,027행 1:1 연결. 대회 hidden test와 별개인 dataset 공개 주석임.
- CCTV 5개만 확보: 2,744,574 bytes, 원본 PTS 유지 전체 420프레임 디코딩 성공. 추출 159프레임과 사고 영역 확대 접촉표 검토, 사람의 연속 재생 검수는 대기.
- 검사 오류 해결: 기본 디코더의 일정 FPS 보정/프레임 복제를 `-fps_mode passthrough`로 해제. 5개 모두 사고 프레임의 PTS와 정답 시각 오차 0.001초 미만. CSV no_frames는 실제 개수보다 1 작음.
- 관찰: 충돌 위치/시점 대체로 부합. A1 전복, A2 single 정의, A3/A4 접촉 부위는 사용자 검수 필요. 전체 2,027개 의미 검수 아님.
- 제약: 원 출처 URL/개별 권리 필드 없음, 정상 영상 유형 없음, 사건 시작/종료·설명 정답 없음. 파일명 출처 후보가 train/test 양쪽에 걸치는 그룹 IID 3개/geographic 1개 발견(실제 사건 누수는 미확정).
- **Conditional Go**: 비상업 로컬 교통 CCTV 사고 검토 연구 후보. 산업→교통 전환·메인 데이터·모델 채택은 미결정. SteelBench와 이전 감사 보존.
- 재현: `uv run --no-project --with imageio-ffmpeg==0.6.0 --with pillow==12.3.0 python scripts/audit_accident.py`. 원본/주석/이미지/응답은 Git 제외 `data/accident_audit/`에만 보관.
- 다음 결정: 5개 영상 사용자 재생 검수 → 권리/평가 분할 보완 → 산업/교통 도메인 및 G1D 판단. 모델 구현 없음.

## ACCIDENT 감사 착수 전 지시 이력 (2026-10-27)

- **사용자 승인:** SteelBench 공식 접근 불가가 확인되어 다음 후보 ACCIDENT의 접근 여부부터 검증한다. 산업안전에서 교통 사고 관제로 제품 목표를 최종 변경한 것은 아니다.
- 문서: [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md) · [R-003 데이터셋 후보 조사](research/0003-cctv-dataset-shortlist.md) · [ACCIDENT 공식 GitHub](https://github.com/accidentbench/ACCIDENT).
- 외부 확인: ACCIDENT 논문은 실제 CCTV 2,027개와 합성 영상 2,211개 및 사고 시점·위치·충돌 유형을 보고. 공식 GitHub `dataset/download_dataset.sh`는 Kaggle `picekl/accident` **전체 ZIP 다운로드**, 사전 Kaggle 인증을 요구한다. 착수 전에는 실제 개별 다운로드·정답 범위가 미확인이었으며, 현재 결과는 위 Phase 1D 기록을 따른다.
- 공식 Kaggle **대회**는 실제 영상에 대한 라벨 있는 **학습 데이터**를 제공하지 않는다고 고지. Kaggle 별도 **dataset** 파일 목록 및 공개 정답을 별도 검증해야 한다.
- **Codex 다음 산출물:** `docs/data/ACCIDENT_SAMPLE_AUDIT.md`. 접근 허용·권리·소량 개별 파일 확보 여부를 먼저 검사하고, 가능하면 4~6개 영상만 로컬 감사. 전체 다운로드·모델 구현 금지.
- ACCIDENT도 접근 제약이 크면 CMA 공식 배포 접근만 조사; 전환·모델 선정은 사용자 승인 이후.

## 최근 확인 결과 — Phase 1C 접근 실패 (2026-10-27)

- [STEELBENCH_SAMPLE_AUDIT](data/STEELBENCH_SAMPLE_AUDIT.md): 공식 API·카드·LICENSE·ethics·sample 목록 모두 HTTP 401. 논문의 `SteelBench-release` 주소도 401.
- MP4·정답 JSON 다운로드 0개, 디코딩·시각 감사 미실행. **현재 접근 경로 No-Go**, 데이터 내용 부적합 판정은 아님.
- 공개 복제 후보 `ThinkingHub/PP`의 API/카드는 접근되지만 공식 이전·배포 권한·원본 동일성 미확인. 대체 미디어 다운로드하지 않음.
- 재현: `python3 scripts/check_steelbench_access.py`; 원문 응답/해시/실행 정보는 Git 제외 `data/steelbench_audit/access/`에만 보관.
- 남은 문제: 접근 가능한 공식 경로 또는 작성자 확인 대체본 확보. 이후 조건·revision·주석 확인 후 4~6개 감사 재개. G1C와 모델 단계 보류.
- 이전 두 데이터셋의 결과와 로컬 파일은 보존.

## 다음 우선 작업 — SteelBench (2026-10-27)

- 노타 AI 영상 관제 직무와 촬영 환경 정합성을 고려해 **고정형 산업 CCTV** 샘플을 우선 검증하기로 함. iSafetyBench를 삭제하거나 공식 No-Go로 판단한 것은 아님.
- 조사 기록: [R-003 CCTV 데이터셋 후보](research/0003-cctv-dataset-shortlist.md). 우선 후보: [SteelBench](https://huggingface.co/datasets/steelbench/SteelBench).
- SteelBench의 공개 MP4는 전체 1,345개가 아니라 **50개 샘플**, 그중 정답 JSON이 연결되는 것은 **47개**라고 배포 문서에 기재. 현재 공식 경로는 HTTP 401로 접근 실패. 수량은 기존 조사 기록이며 이번 실측값이 아님.
- **실행 지시:** [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md). 데이터 카드·권리·주석 확인 후 **공개 MP4 4~6개만** 로컬로 검수하고 [STEELBENCH_SAMPLE_AUDIT](data/STEELBENCH_SAMPLE_AUDIT.md)에 기록. 접근 실패와 재개 조건을 해당 문서에 기록했으며 영상 감사는 미완료.
- 과거 Safe and Unsafe Behaviours·iSafetyBench 자료는 보존, 영상/프레임은 Git 제외. **모델 선정·학습·서비스 구현 보류**.

## 최근 확인 결과 — Phase 1B (2026-10-27)

- [Issue #1](https://github.com/yrumupusm/sceneguard-ai/issues/1)과 최신 지시에 따라 [ISAFETYBENCH_SAMPLE_AUDIT.md](data/ISAFETYBENCH_SAMPLE_AUDIT.md) 작성. 실행 기준 HEAD `c15ba05`.
- 공식 GitHub 주석 1,100개와 HF 영상 목록 1:1 연결, 8개(위험 4·정상 4)만 확보. 총 6,437,874 bytes, 전체 1,469프레임 디코딩 성공, 배포 LFS SHA256과 일치.
- 기본 PTS 프레임 103개와 상세 창 62개(중복 시점 포함)를 추출해 시각 감사. 사람의 전체 연속 재생 검수는 미완료.
- 사건 시작·종료, 객체/추적, 공식 학습/평가 분할, 명시적 원 출처 URL 필드는 없음.
- normal 영상에도 사람 넘어짐이 존재하고, 물체 낙하를 `falling down`으로 태깅한 의미 불일치 후보가 있음. 화재 클립 후반에는 별개 차량 장면 혼입. 사람 검수 없이 정상/위험을 사고 이진 정답으로 전환하지 않음.
- MCQ multi 90문항은 전체 행동의 부분집합을 정답으로 묻는다. MCQ 점수와 전체 사건 설명 품질을 분리해야 함.
- 원 출처 후보 151개(1개 ID 형식 불일치). 반복 출처 그룹 소속 클립 1,077개. 공개 LFS 해시상 완전 중복 없음과 사건/시간 중복 없음은 다른 의미임.
- 권리: CC BY-NC-SA 4.0 배포 조건 확인, 원본 YouTube 개별 권리 허가는 미확인. 비상업 로컬 연구 감사만 진행, 영상/이미지는 공개하지 않음.
- 의견: **Conditional Go**. 행동·순서·근거·불확실성을 사람이 수정하는 연구 과제에 적합성이 있으나 원 주석 의미 검수·근거 구간·출처별 분할 보완 필요. 데이터·모델 최종 채택 아님.
- 재현: `uv run --no-project --with imageio-ffmpeg==0.6.0 --with pillow==12.3.0 python scripts/audit_isafetybench.py`.
- 로컬: `data/isafetybench_audit/`의 videos, previews, details, manifest.json, annotation_report.json. 전부 Git 제외. 이전 Safe and Unsafe Behaviours 자료는 보존.

## 남은 문제 — 현재 Phase 1B

- 사용자에게 감사 문서 H1~H4/N1~N4의 실제 재생·태그/주체·근거 시점 검수를 요청. N3/N4 의미 차이, H3 구조/도망, H4 장면 전환이 우선.
- 원 주석과 사람 보정본을 별도로 유지하고 검수자를 기록할 평가 기준 결정.
- 출처 후보를 실제 원본/같은 사건으로 대조하고 개발·평가 분할 독립성 확인. 상용/공개 미디어 사용 권리는 별도 해결.
- 실제 안전 담당자 업무 효용·모델 성능·지연·GPU 자원은 미측정. 이번에는 모델 구현·추론·학습을 하지 않음.

## 다음 결정 — 현재

1. 감사 결과와 사용자 검수로 G1B Go / Conditional Go / No-Go 결정.
2. 관찰 가능한 사건 태그·설명·근거 구간의 검수 기준과 첫 MVP 범위 선택. 사람 넘어짐과 물체/구조물 낙하 구분은 후보이며 미확정.
3. 데이터 조건을 보완한 후에만 G2 모델/최소 구조 비교로 이동. UI/API/검색·VLM 서버 구현은 아직 시작하지 않음.

## 제품 목표 및 감사 착수 전 기록 (2026-10-27, ADR-0003)

- **목표:** 안전 담당자가 **이미 선택한 짧은 사건/이상상황 영상**을 AI 보조로 검토·정리하는 제품 시나리오. 행동/사건 태그, 근거 프레임·구간 후보, 검토용 설명을 사람이 수정·확정하는 흐름을 가정한다.
- **아직 미검증:** 실제 안전 담당자의 요구와 소요 시간 절감, 분석 모델, 아키텍처, 실시간 성능, 검색 품질. 검색·보고서 초안은 후속 기능 후보다.
- **현재 우선순위:** iSafetyBench의 영상 접근, 정답 스키마, clip별 다중 행동, 설명/근거 가능성, 라이선스, 중복 출처 검증.
- 공개 배포 데이터셋 카드에 `cc-by-nc-sa-4.0`가 표시되지만 유튜브 원본 영상 권리는 별개라고 안내한다. 실제 사용·재배포 조건과 파일은 Codex에서 다시 확인한다.
- **Codex 다음 파일:** [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md), [iSafetyBench 감사 계획](data/ISAFETYBENCH_AUDIT_PLAN.md). 산출물: `docs/data/ISAFETYBENCH_SAMPLE_AUDIT.md`.
- **의사결정:** [ADR-0003](decisions/ADR-0003-incident-review-product-direction.md) / [업무 흐름](PRODUCT_WORKFLOW.md).
- 감사 착수 당시 iSafetyBench는 미채택·샘플 미확보였으며, 현재 8개 감사 결과는 위 최신 기록을 따른다. 최종 채택은 여전히 보류한다.
- 예전 `SAMPLE_AUDIT.md`는 이력으로 보존하며, 패널 단순 상태 분류를 다시 메인으로 채택하지 않는다.

## 최신 방향 변경 (2026-10-26, ADR-0002)

- 사용자와 함께 앞쪽 프레스의 **왼쪽 전기함 도어가 닫힌 화면과 열린 화면**을 비교해 패널 라벨 대상을 확인함. 이는 업로드된 비교 이미지에 대한 검수이며 8개 영상 전체 재생 검수를 완료했다는 의미가 아님.
- **패널 열림/닫힘의 단순 상태 분류는 SceneGuard 메인 MVP에서 제외**. 상태는 비교적 명확하지만 문을 여는 시간적 행동·위험 원인까지 뒷받침하지 못하며, 복합 위험행동/사고 맥락 분석이라는 포트폴리오 목표와 범위가 다름.
- 기존 `SAMPLE_AUDIT.md`, 8개 원본 영상, 검사 코드, Conditional Go 판정은 역사적 근거로 **유지**. 기존 판정은 당시 데이터 확보·부분적 라벨 확인에 대한 것.
- 다음 검토 대상은 **iSafetyBench**. 복합 산업안전 행동과 사고 영상에 대한 **사후 사건 분석·검토 보조** 가능성을 조사하되, **메인 데이터로 아직 확정하지 않음**.
- 참조: [ADR-0002](decisions/ADR-0002-reconsider-safety-dataset.md), [Codex 다음 작업](CODEX_NEXT_TASK.md), [새 데이터 감사 계획](data/ISAFETYBENCH_AUDIT_PLAN.md).
- 다음 산출물: `docs/data/ISAFETYBENCH_SAMPLE_AUDIT.md`. 원본 영상은 로컬에만 저장.
- 해당 다음 작업 전까지는 모델·학습·VLM·대시보드 구축을 진행하지 않음.

## 지금까지 결정/완료
- 연구 → 데이터 → 요구·평가 정의 → 모델 선택 순서 유지. YOLO/추적기/VLM 등 모델은 미선정.
- 최초 업데이트 검토에서 소량 데이터 감사를 권장했고, 이후 사용자 요청에 따라 실제 다운로드·검사를 수행함.
- **[SAMPLE_AUDIT.md](data/SAMPLE_AUDIT.md)** 작성: 출처/이용 조건, 공식 배포 라벨 연결, 영상별 관찰 시각, 제약, Conditional Go 의견.
- HF revision `7369ff1830b5f6c00f7d7383eeeaa90704bfc5b5`의 samples.json 확인. 691개 레코드, 영상 단위 단일 클래스, train 566/test 125. frames.json은 비어 있음.
- 정상 4개·위험 4개만 다운로드. 통로 정상/이탈, 패널 닫힘/열림 각 train 1개·test 1개. MP4 총 123,152,506 bytes.
- 8개 영상 전체 1,639프레임 디코딩 성공, FFmpeg 오류 없음. 해상도 1920×1080, 표시 FPS 24.80~25.08.
- 12개 시점/영상의 접촉표 96프레임 및 일부 원해상도 프레임을 Codex가 시각 검토. 사람이 전체 재생 검수한 상태는 아님.
- 6개는 관찰 시점에서 라벨 부합, `4_tr32`는 원거리 통로 경계 불명확, `0_tr19`는 설비 작업 구역과 통로 위반 구분에 추가 검수 필요.
- 원본/배포 페이지 CC BY 4.0 표기 확인. 원본 Mendeley 개별 파일과 라벨·해시 대조 및 공개 이미지 별도 권리 검토는 미수행.

## 로컬 파일·재현
- 영상: `data/safe_unsafe_audit/data/` (8개 MP4).
- 메타데이터, 개별 URL·SHA256·실측값: `data/safe_unsafe_audit/manifest.json` 및 동일 폴더 JSON들.
- 접촉표와 추출 이미지: `data/safe_unsafe_audit/previews/`.
- 스크립트: [audit_samples.py](../scripts/audit_samples.py).
- 실행: `uv run --no-project --with imageio-ffmpeg==0.6.0 --with pillow==12.3.0 python scripts/audit_samples.py`
- 시스템 디코더 부재로 uv 임시 도구 환경 사용. 전체 데이터셋·모델 다운로드, 학습, 업로드는 수행하지 않음.

## 이전 Safe and Unsafe Behaviours 감사의 남은 문제
- 사용자 실제 재생 검수와 G1 최종 승인.
- 라벨 대상 사람/패널과 통로 경계 확인. 정상 클래스는 화면 전체가 안전하다는 뜻이 아님.
- 사건 시작/종료·박스·추적 정답이 이 HF 배포에 없음. 추가 수동 라벨 범위 결정 필요.
- train/test에 같은 설비·유사 구도 존재. 원본 세션·카메라 ID가 없으므로 누수 여부 미확인. 감사에 사용한 test 영상은 최종 블라인드 평가용에서 구분해야 함.
- RTX 3080 VRAM·드라이버·추론 성능은 미확인. 이번에는 GPU 사용 안 함.

## 이전 감사 단계의 다음 결정 (현재 지시 아님)
1. 사용자 검수 후 Go / Conditional Go / No-Go 확정. 현재 Codex 의견은 **Conditional Go**.
2. 첫 후보로 패널 열림/닫힘 **상태**를 추천. 패널을 여는 동작의 시각 검증은 이번 영상으로 입증하지 못함.
3. 통로 후보는 ROI·대상 보행자·설비 작업 구역 예외부터 정의.
4. 평가 단위와 추가 라벨링 계획을 확정한 후 새 ADR에서 최소 모델 후보를 비교. 학습·서버 구축은 아직 시작하지 않음.

## 기존 메모에 대한 안내

위의 '다음 결정'에 있던 패널 첫 후보 추천은 **ADR-0002 이후의 현재 작업 지시가 아니라 과거 감사 단계의 제안**이다. 현재 우선순위는 iSafetyBench 후보의 실제 데이터/주석/라이선스 검증이다.
