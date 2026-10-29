# 다음 작업 — BATCH-0006 / EXP-0025 C6 ROI 해상도 640→960 단일 실험 (사용자 승인)

## 최신 결과 — EXP-0028 실제 추적 비교 완료·일반 적용 보류

2026-10-30. [experiments/EXP-0028-results.md](experiments/EXP-0028-results.md)를 우선한다. 기존 FCOS 030480/007600프레임 strict·gap3초를 실제 CPU 재생했고 strict는 EXP5C를 정확히 재현했다. gap에서030후보2개 유지·007접근 후보2→0, 그러나030전후ID단절은 남았다. 이에 승인된 BoT-SORT+공식 pretrained nanoReID 한 구성을 실제1080프레임/6878crop에 CPU로 실행(41.186초,오류/retry0)했다.030후보2개와후기ID단절 지속,007후보가1개 재발했다. 긴ID유지·부분박스·서로다른ID의관측 재배정을 정체복원 성공으로 바꾸지 않는다.

원본/strict/gap 및 원본/gap/ReID의 연속·표시확대 비교8영상은 `outputs/exp0028/practical-v1/review030`, `review007`, `review030_reid`, `review007_reid`에 있다. 실제 관측만 경계 입력으로 사용하며, 예측은 별도 표시다. 파인튜닝 best/last·Roboflow자료는 미사용이고 검수완료를 진행조건으로 두지 않는다. 기존 환경·결과·기본구성·canonical44jobs/attempts를 보존하고 GPU작업은0이다.

**실행·영상제작 완료 / 제한적 접근후보 억제 확인 / 전후동일인물 연결과 일반 행동 성능 미충족 / 기본 자동교체 없음.** 핵심두영상의 정체 대응 질문은 선택적으로 한 번 묶어 요청했고 답변 전 새 정답을 만들지 않는다. 다음작업은 이 실제 비교 근거로 남은 검출공백·부분신체박스와 ID연결 문제를 구분해 결정한다. 이번한구성 비교 종료 후 무인추가실험은 시작하지 않는다. 기존웹/GitHub 확인은 별도 전달 기록을 따른다.

---

## 현재 승인 — EXP-0028 실용형 연속 추적 비교

2026-10-30. 최신 사용자 지시와 [CODEX_PRACTICAL_TRACKING.md](CODEX_PRACTICAL_TRACKING.md)를 우선한다. 기존 FCOS 캐시030/007의 strict·3초 누락 허용 구성을 실제 재생하고 연속 비교 영상을 만든다. ID 단절·오연결이 주요 문제로 남으면 동일 검출 입력의 BoT-SORT+사전학습 ReID 한 구성을 비교한다. 파인튜닝 모델은 사용하지 않으며 Roboflow 검수는 진행 조건이 아니다. 기존 결과·모델 기본값을 보존하고 실제 관측/예측과 후보/확정 사건을 구분한다. 기존 Orca·단일 GPU 큐·Sol high·Astra high 독립 검토와 로컬 미디어 보존을 유지한다.

---

## 최신 결과 — EXP-0027 낮은 점수 진단 완료·시각 검수 대기

2026-10-29. [진단 결과](experiments/EXP-0027-detection-low-confidence-diagnosis.md)와 [라벨 감사](data/EXP-0027-label-audit.md)를 우선한다. 기존 두 Detection×7캐시에 conf0.05만 적용한14회가 canonical 단일GPU큐에서 성공했다. 새 결과의>=0.25 행은 기존14조건과 좌표·점수·순서까지 정확히 같았다. 030:90은 pretrained6/best1개의 낮은 점수 행,94초는 두 모델0행이다. 실제 사람/부분 신체/중복/배경 대응은 미검수이고0.05에서도 없는 출력이 내부 전체 후보 부재를 뜻하지 않는다.

**기술 실행 완료 / 핵심 누락 원인 일부만 좁힘 / 사람 검수·D0 미완료 / 기본 적용 보류**다. 원본·준비파일1,108개·과거43jobs/43attempts를 보존했고 신규1job/1attempt만 추가했다. 전체113라벨 패널·354사람행은 모두review_pending이며 우선27행은15패널이다. 사용자에게 새7장 비교를 한 번에 요청했고 답변 전 실제 인물 복원이나 정확도로 표시하지 않는다.

다음은 새 낮은 점수 출력과 우선15라벨 패널의 사람·신체 범위를 확인하는 한 가지 검수다. 비교이미지는 로컬 `outputs/exp0027/EXP-0027/diagnose/111e49f413a4446586e629cd65419721/`, 라벨 인덱스/양식은 `runtime/EXP-0027/label-audit/`에 있다. GPU한도14회를 마쳤고 **추가학습·threshold/해상도/ROI sweep·새모델·추적/행동실험을 자동 시작하지 않는다**. 기존 EXP26 실패·기본구성은 보존한다. [전달 확인](experiments/EXP-0027-delivery.md)은 웹등록·실제렌더·GitHub게시를 별도로 기록한다.

---

## 현재 승인 — EXP-0027 낮은 점수 Detection 진단·라벨 검수 준비

2026-10-29. 사용자 지시에 따라 GitHub `b79a9eb`의 [신규 진단 계획](experiments/EXP-0027-detection-low-confidence-diagnosis-plan.md)을 실행한다. EXP-0026 종료/추가 학습 금지는 보존하고, 이번 범위에서는 기존 Detection 두 가중치×기존7프레임에 conf0.05만 적용하는 최대14회 추론을 승인한다. 기존0.25 결과·모델·입력·ROI·라벨/113검수 패널을 보존한다. 추가 학습·새 모델/프레임·threshold sweep·기본값 변경은 없다.

기존 Orca Run/단일GPU큐·Sol high 담당·Astra high 독립 검토를 사용한다. 먼저CPU 무결성과 라벨 검수 목록을 정리하고 소스·입력 사전검토 후 실행한다. 새 낮은 점수 결과의>=0.25 부분과 과거 캐시를 대조한다. 낮은 점수 출력도 내부 전체 후보가 아니며 박스 수를 사람 검출 성공으로 바꾸지 않는다. 모든 라벨 이미지 의미는 사람 검수 전 review_pending이다. 코드·집계·검토·기존 웹/GitHub 전달 후 종료한다.

---

## 최신 결과 — EXP-0026 탐색 학습 완료·채택 보류

2026-10-29. [실행 결과](experiments/EXP-0026-exploratory-person-finetune.md)를 우선한다. YOLO26m Detection으로 미검수 train210/valid20을 사용해 고정20epoch를 기존 단일 GPU 큐에서 완료했다(학습223.544초,오류/OOM/retry0). test17은 미사용했고 원본·과거 준비 metadata·기존 결과/환경/모델 기본값을 보존했다. 기존42jobs/attempts에 신규1회만 추가했다.

C6의84/90/94초 박스 수는3→1/0→0/0→0이며 접근 대조 일부도 감소했다. **기술 실행 성공 / 핵심 누락 개선 미확인 / 라벨·새 박스 의미 검수 미완료 / 적용 보류**다. valid20의 mAP는 제공된 잠정 라벨에 대한 진단이며 CCTV 정확도가 아니다. 학습 승인은 D0 통과가 아니고, 이전 준비 단계의 학습 미승인 기록은 당시 이력이다. 추가 학습·모델/임계값/ROI 변경을 자동 시작하지 않는다. 다음은 사용자의 추후 라벨 의미·누락 검수이며 현재 작업을 추가 질문으로 중단하지 않는다.

기존 결과 화면의 보고서·측정값·검토·이미지8개와 GitHub 게시를 각각 확인했다. [전달 기록](experiments/EXP-0026-delivery.md)을 따른다. 이번 배치는 종료하며 자동 후속 학습은 없다.

---

## 최신 범위 — BATCH-0007 사람 박스 준비 사본 (검수는 나중에)

2026-10-29. 사용자가 여러 사람을 감싼 라벨일 가능성은 우선 보류하고 변환을 진행하도록 승인했다. 이 지시는 기존 BATCH-0007 계획의 시각 검수 전 변환 금지를 **준비용 사본 생성에 한해서만** 대체한다. 각 사람 라벨 하나를 임시 박스 하나로 취급하며, 개인별 정답이 확인됐다고 기록하지 않는다. 원본 ZIP/라벨/이미지와 기존 실험을 보존한다.

이번 범위는 CPU 변환·형식 검증·나중에 볼 로컬 검수 자료·코드/문서 기록이다. 클래스0 울타리는 제외하고 사람 클래스1/2는 person0으로 합친다. 기존 사람 xywh는 유지하며 사람 다각형만 min/max 외접 박스로 바꾼다. 검수 미완료와 학습 미승인을 명시한다. GPU 학습·추론·새 가중치·모델/기본값 변경은 포함되지 않는다. 데이터 준비는 모델 비교 실험 성공이나 Gate D0 통과가 아니다.

CPU 변환 결과: 이미지/라벨247개와 기존 split210/20/17을 유지했다. 기존 사람 박스335개 유지·사람 다각형19개 변환으로 person354행을 만들고 울타리247행을 제외했다. 이미지 제외0, 나중에 볼 로컬 비교113장이다. 원본 ZIP과 기존42jobs/42attempts는 그대로이며 새 GPU 작업0이다. 결과·검증·재현 방법은 [준비 기록](data/CLIMBING_FENCE_PREPARATION.md)을 따른다. 사용자 시각 검수와 학습 가능성 판단은 미완료다. 아래 종료 배치와 초기 계획은 이력으로 보존한다.

---

## 최신 결과 — BATCH-0006 / EXP-0025 종료·기본 적용 보류

2026-10-29 KST. [종합 결과](experiments/BATCH-0006-summary.md), [EXP-0025](experiments/EXP-0025-c6-pose-960.md), [전달 기록](experiments/BATCH-0006-delivery.md)을 우선한다. YOLO26m-Pose·고정C6·동일PTS에서 imgsz만640→960으로 바꾼 신규3회가 성공했다. 기존640캐시3개 재사용·640재추론0, 오류/OOM/retry0이다. 박스/관절 추정은84초3/38→3/37,90초1/12→0/0,94초0/0→1/11이다.

새 이미지에 대한 사용자 검수: **84초는 잘 됨,90초는 이전 실험과 동일한 수준,94초는 문 위 사람이 생각보다 잘 잡혔고 이미 넘어간 사람은 누락**. 90초의 정성 평가는 출력 개수 동등성을 뜻하지 않는다. 94초 한 사람의 제한된 관측 개선과90초 관절 근거 부재를 함께 기록하며 관절별 정밀GT·행동 성능·일반화 개선을 확정하지 않는다. **기술 실행 완료 / 사용자 정성 비교 완료 / 핵심 누락 지속·기본 적용 보류**다.

기존 결과·공식 라벨·환경·640소스와canonical41개 과거jobs/attempts를 보존했다. 이번 신규3회 한도를 마쳤으며 **추가 GPU·해상도/ROI/threshold 변경·모델·추적·행동규칙·후속 실험을 자동 시작하지 않는다**. 아래 승인·미검수 문단은 실행 및 답변 이전 이력이다.

---

2026-10-29 KST. 사용자는 [EXP-0024 사용자 검수](experiments/EXP-0024-user-pose-review.md) 이후, **기존 pretrained YOLO26m-Pose의 C6 고정 ROI에 대해 입력 해상도만 640에서 960으로 바꾸는 1차 검증**을 새 범위로 명시 승인했다. **최우선 고정 계약:** [BATCH-0006 계획](experiments/BATCH-0006-c6-pose-960-resolution-plan.md). **이번 승인 전의 '추가 GPU 작업 없음'은 BATCH-0005/EXP-0024 종료 기록**이며, 오직 이번 3회 GPU 추론 범위 안에서만 대체된다.

## 기존 Orca 총괄에 대한 실행 지시

1. **BATCH-0006 / EXP-0025 새로운 결과 ID/별도 코드·job만 생성**. 종료된 EXP-0023/0024·이전 모든 sourcefreeze/원본·모델/라벨·리뷰/binding/큐 기록을 덮거나 재실행하지 않는다. 기존 Run `run_3d23462a014a`, Astra max 총괄1/Sol high 구현·실험 최대2/Astra high 독립 리뷰1, existing canonical single GPU queue/free VRAM≥6144MiB gate/lease/parent-child·source/commit/input hash를 유지한다.
2. **입력 정확히 E01_030의 84/90/94초 원본 native PTS**. 기존 `configs/mvp0001_cameras.json` C6 ROI normalized [0.28,0.20,0.75,0.80] = original 1920×1080의 **RGB[216:864,537:1440]**(648×903) 그대로. 원본 SHA/PTS, ROI/crop hash와 이전 결과를 검증해 재사용. 사건에 맞춰 crop 변경 금지. **기존 EXP-0023 C6 640 3개 Results는 재추론하지 않는다.**
3. **유일한 설정 차이:** 원래 `orchestration/batch04_pose_command.py`의 공식 v8.4.192 public YOLO.predict kwargs를 신규 dict에 복제하여 **`imgsz=960` 한 값만 변경**. 나머지 FP32/rectFalse/batch1/conf0.25/nmsFalse/classes[0]/max_det300/외부API금지 등 설정, 공식 `yolo26m-pose.pt` weight SHA/설치 가상환경/모델은 동일. 신규 가중치0/재학습0/다른 모델·VLM0. 기존 `batch04_pose`, `batch05_pose` 불변; 필요한 코드만 작게 별도 경로에 작성.
4. **실행 전 CPU 계약:** 전체 kwargs 중 해상도 외 값 동등, PTS/RGB/crop/source hash, cached 640 Results/binding, BGR·ROI offset(+537,+216) 한 번, 17관절/empty/unknown/복수사람, 960 공개 API/type/expected tensor 1×3×960×960, 전용 큐 stage/새 결과 ID 검증. 정확한 설치 소스 확인, code/input manifest 커밋과 독립 Astra high 사전 검토 뒤 실제 GPU 실행 허가.
5. **실제 GPU:** 기존 큐에서 **960 C6 세 프레임만, 각 1회**. 권장 순서 `030_090_C6_960`→`030_084_C6_960`→`030_094_C6_960`, 한 번의 모델 로드와 공식 warmup(샘플 예측과 별도). **90에서 정상 0명이라도 84/94 계속**. OOM·호환 예외는 정확히 보고하고 무음 설정 하향/프로세스 강제 종료하지 않는다. 오류 코드 correction 최대1회(원인 증거·CPU 회귀/독립검토·새 freeze 필요), 성공 프레임 재생성 금지.
6. **비교:** **640 cached vs 960 new** 세 PTS를 로컬 원본 위에 좌표 복원해 원본/640관절/960관절 triptych 3장. 사람 후보 수와 retained 관절 수뿐 아니라 **실제 사람별 bbox 대응·손목/골반/무릎/발목 위치/가림·오배정**을 품질 판단과 구분. 기존 사용자 관찰은 84에서3명 대체로 양호, 90에서 넘는3명 중 오른쪽1명만 잘못된 관절, 94에서 보이는2명 모두 누락. 새 출력을 시각 검수하지 않고 개선 성공이라 하지 않는다. 인물별 GT·정밀F1/recall/FPR/완료 여부 창작 금지.
7. **납품:** 기존 `orchestration.complete` 결과 등록/독립 리뷰 및 hash binding → 로컬 페이지에 **이미지3장 실재 표시**·보고서/지표 확인 → GitHub push/원격 byte 확인. 원본 영상/프레임·weights/raw 좌표·원본/960 이미지·tensor·logs/DB/receipts는 로컬에만. 최종 **시각별 640/960 표, 90/94 검출 누락 감소 여부·실제 관절 대응, GPU/시간 비용, 미확정·다음 하나**를 보고한 뒤 **추가 모델/해상도/SAHI/추적/규칙/VLM 결합/전체 영상 처리 없이 멈춘다**.

이 배치는 **해상도 한 축만의 통제 비교**이며, 기존 완료 배치에 허가되지 않은 자동 재실험을 재개하는 지시가 아니다. 승인된 3개 입력·독립검토·기존 웹/원격 전달은 세부 재승인을 반복 요구하지 말고 완료한다. 사용자 이미지 품질 판정이 필요한 부분은 실제 로컬 3장 자료로 한 번 묶어 요청할 수 있으나 판단 전에는 미확정으로 명시한다.

---

# 다음 판단 — 사용자 검수 반영, 추가 실험 자동 진행 없음

2026-10-29. [사용자 검수 기록](experiments/EXP-0024-user-pose-review.md)을 최신 판단으로 사용한다. EXP-0023의 실행·출력·검토본은 변경하지 않는다. 이번 기록은 기존 자료에 대한 사용자 정성 검수이며 신규 GPU 추론은0회다.

사용자 관찰: **84초 C6는3명 박스와 관절이 대체로 양호**, **90초는 넘는3명 중 맨 오른쪽1명만 검출되고 그 관절도 어긋남**, **94초는 문에 올라간1명과 넘어가 있는1명이 보이지만 양쪽 모두 검출0**이다.90초의1개 제한은 의도하지 않았으며 max_det300/all-row 표시다. 모델 내부 누락 원인은 이 답변으로 확정하지 않는다.84초의 정성적 양호를 정밀 관절 정확도·넘기 자세 성공으로 일반화하지 않는다.94초 관찰은 그 시점의 사람 상태이며 모든 사람의 완료나 법적 판단을 확정하지 않는다.

**기술 실행 성공 / 넘기 장면의 사람·관절 근거 부족 / 기본 적용 보류**로 구분한다. 손표시 이미지는 로컬 참고자료로 보존하며 정밀GT·학습·크롭 입력으로 사용하지 않는다. 다음 검토 대상은 넘기 자세에서의 검출 누락과 검출된 사람의 관절 오류를 분리해 평가하는 기준이다. 새 추론·모델·ROI/임계값 변경·규칙·추적은 자동 진행하지 않는다. 아래 미검수 상태와 승인 문단은 답변 이전의 이력이다.

---

# 다음 결정 — BATCH-0005 종료 후 실제 관절 대응 확인

2026-10-29 KST. [종합 결과](experiments/BATCH-0005-summary.md), [EXP-0023](experiments/EXP-0023-c6-pose-roi-comparison.md), [전달 기록](experiments/BATCH-0005-delivery.md)을 우선한다. 고정84/90/94초 full/C6에서 신규5개·기존90 full 재사용1개를 완료했다. 박스/관절 추정은84 full2/24→ROI3/38,90 full0/0→ROI1/12,94둘다0/0이다. 오류/retry0, sample forward5·별도 warmup1이며 출력 증가가 실제 관절 복원이나 행동 성능 충족은 아니다.

세 비교 이미지의 사용자 검수를 한 번 묶어 요청했고 실제 인물/관절 대응·가림/중복/ROI 절단은 답변 전 미확정이다. 기본 적용·추적·행동 규칙·결합은 보류한다. 기존40 jobs/attempts·공식 라벨·CV/VLM·weights·환경·기본 설정을 유지하며 **추가 GPU 작업이나267전체 처리를 자동 시작하지 않는다**. 다음 결정은 새 세 이미지의 실제 대응 확인 한 가지다. 아래 승인 문단은 완료된 이번 배치의 범위 이력이다.

---

# 다음 작업 — BATCH-0005 / EXP-0023 고정 C6 ROI로 YOLO26m-Pose 검출 비교

2026-10-29 KST. 사용자가 **E01_030의 84·90·94초에서 기존 YOLO26m-Pose 전체화면 vs 사전 고정 C6 ROI**를 비교하는 신규 실험을 승인했다. 전체 실행·평가·기록 계약: [BATCH-0005-c6-pose-roi-comparison-plan.md](experiments/BATCH-0005-c6-pose-roi-comparison-plan.md).

## 총괄이 지금 수행할 일

1. 이전 **BATCH-0004/EXP-0022 종료·추가 GPU 금지**는 기존 배치의 종료 기록으로 보존한다. 새로운 사용자의 명시적 승인 범위에서만 **BATCH-0005 / EXP-0023 새 코드, 새 큐 job, 새 출력**을 만들 수 있다. 기존 결과/해시/queue job/가중치/설정/공식 라벨은 덮어쓰지 않는다. 기존 Run `run_3d23462a014a`·Astra max 총괄·Sol high 담당 최대2·Astra high 독립 검토·canonical GPU 단일 직렬 큐/free VRAM≥6144MiB gate를 유지한다.
2. 정확히 **030:84/90/94 원본 native PTS × full-frame/C6 fixed ROI** 6조건만 비교. **030:90 full-frame의 EXP-0022 실제 zero-person Results는 재사용·재추론하지 않는다**. **신규 YOLO.predict 최대5회**: 84 full/ROI, 90 ROI, 94 full/ROI. 한 번의 모델 로드/queue 작업으로 처리 가능. 90 ROI가 empty라도 기술 성공이면 84/94는 반드시 실행해 시간대별 비교를 완성한다. 새 weight/학습/VLM 추론/설정 sweep 금지.
3. camera C6의 기존 `configs/mvp0001_cameras.json` ROI **[0.28,0.20,0.75,0.80]**만 사용. 원본1920×1080 기준 **x537:1440, y216:864, crop903×648**, floor(min)/ceil(max)과 실제 소스 검증. 사람/예측을 보고 재선정하지 않는다. crop RGB→연속 BGR로 공식 `YOLO.predict` 사용, **same 640/FP32/conf.25/nms=False/기타 8.4.192 public kwargs**. ROI 결과는 **crop-local** 원본좌표이므로 crop offset x+537/y+216을 **정확히 한 번**, 전체화면 Results에는 offset/resize를 적용하지 않는다.
4. 기존 `batch04_pose` 공식 API 유틸과 `EXP-0022` 본 결과는 읽기 전용. 새 소형 `batch05_pose` 구현에서 CPU crop/color/offset/native PTS/기존90 full artifact 해시/empty result/공식 signature 및 GPU lease 사전검증을 통과하고 source/manifest commit·독립 검토 후 5개의 실제 GPU 예측을 실행한다. 예외 시 부분 결과·한도를 보존하며, 정상 0사람 결과는 코드 오류나 자동 retry로 취급하지 않는다.
5. 84/90/94의 원본 + full overlay + ROI overlay를 비교해 실제 인물 bbox/손목·골반·무릎·발목 관절 위치 일치, 가림·중복·ROI 절단·비사람 의심을 기록. 기존 90 full 0과 신규 ROI 차이가 사람/관절 **복원인지 시각적으로 확인**하기 전 성능 개선 주장 금지. C6 가상선은 물리적 울타리 상단이 아니다. 이번 배치에서는 사람별 추적/행동 규칙/CV+VLM 결합/전체267 처리하지 않고, q/v 일부 선택창으로 F1/FPR도 계산하지 않는다.
6. 신규 EXP-0023 보고서·metrics(미측정=null)·원본/오버레이 참고 자료·Astra 독립 리뷰/해시 binding → 기존 `orchestration.complete` 등록 → 기존 로컬 결과 페이지 이미지 표시·보고서/지표 확인 → 정상 GitHub push/원격 파일-byte 확인. 원본 CCTV/이미지·사람 좌표·raw Results·weights/DB/runtime/receipt는 공개하지 않는다. 영상이 없으면 동영상 seek는 해당 없음. 완료 후 3개 시점의 조건별 표·관절 일치·GPU 비용·남은 한계를 짧게 요약하고 **자동 후속 GPU 작업 없이 종료**한다.

**이번 배치는 모델 교체가 아니라 입력 영역 변경의 단일 축 검증이다.** 코드/해시/테스트 준비 완료를 실제 inference 완료로 말하지 않고, 사용자에게 단계별 소규모 재승인을 반복 요구하지 않는다.

---

# 다음 작업 — BATCH-0004 기술 복구 확인·확대 보류

2026-10-29 KST. [종합 결과](experiments/BATCH-0004-summary.md), [EXP-0022](experiments/EXP-0022-yolo26-public-predict.md), [전달 기록](experiments/BATCH-0004-delivery.md)을 우선한다. 공식 API로030_090/007_064의 실제 Results 및 원본/overlay 두 장을 생성했다. 오류/retry0이다. 030은 사람/관절0,007은 사람 후보2행/관절 추정23개이며 위치 정확성과 별개다. 030의 기존 사용자 관찰과 대비해 필수 넘기 장면의 관절 근거가 없으므로 remaining265·규칙·추적은 미실행한다. 새 GPU 작업이나 설정 변경을 자동 예약하지 않는다.

007의 새 관절 위치는 두 로컬 이미지로 한 번 묶어 검수 요청했고 미확정 내용은 유지한다. 다음 별도 판단에는 핵심 누락에서 관절 단서를 확보할 근거가 필요하다. 기존 EXP-0021 실패·CV/VLM·공식 라벨·기본 모델은 바꾸지 않는다. 아래 승인 지시는 이 실행의 범위 이력이다.

---

# 보존된 다음 작업 — BATCH-0004 YOLO26m-Pose 공식 API 복구 (신규 승인)

2026-10-29 KST. 사용자는 BATCH-0003에서 실행 어댑터가 실패한 YOLO26m-Pose를 **같은 체크포인트와 기존 원본 입력으로, 공식 public YOLO.predict 경로로 복구**하고 **030_090/007_064의 실제 관절 결과 두 장을 먼저 확보**한 후 조건에 따라 고정 입력을 분석하는 신규 작업을 승인했다. 이 배치에 대한 구체 상한/차단/출력 계약: [BATCH-0004-yolo26-pose-recovery-plan.md](experiments/BATCH-0004-yolo26-pose-recovery-plan.md).

## 총괄 실행 지시

1. **역사적 BATCH-0003 실패 기록 불변:** EXP-0021 실패 2건/한도 소진 및 소스 freeze, BATCH-0002 포함 모든 과거 결과·settings·모델/weight/정답은 덮어쓰지 않는다. 새 BATCH-0004 / EXP-0022 결과 ID·새 코드/queue job 및 출력 디렉터리만 사용한다. 새로운 승인은 이전 실패 job의 세 번째 retry 허가가 아니다. 기존 Run과 canonical queue, Astra max 총괄·Sol high 담당 최대2·Astra high 독립 검토, 최소 free VRAM 6144MiB 게이트를 사용한다.
2. **기존 환경/입력 재활용:** ultralytics 8.4.192, .venv-pose-batch03, 기존 공식 yolo26m-pose.pt SHA와 고정 267개 source/native PTS/RGB 입력을 검증 후 재사용. 새 모델·weight 다운로드, 학습·파인튜닝·Qwen/VLM 호출·최적화 튜닝 금지.
3. **이번에 바꿀 유일한 기술 축:** 새 batch04_pose의 실행 경로에서 **공식 YOLO.predict() API를 사용**. 원본 RGB 배열은 연속 BGR ndarray로 변환, full frame/640/FP32/conf0.25/rectFalse/nmsFalse/배치1 유지. 공식 Results.boxes/Results.keypoints.data 17×3를 원본 좌표로 읽는다. 지원 안 되는 visualize/private inner kwargs, 모델 head 수동 경로, 좌표 이중 scaling 등을 제거. 공식 predictor가 **fuse=True 및 최초 warmup을 수행**하는 차이를 분명히 측정·보고한다. 이전 실패 runner 소스는 그대로 둔다.
4. **CPU preflight 필수:** pinned v8.4.192 public 호출 키와 내부 signature 검증, BGR/색상·좌표·17관절/0 검출/unknown·원본/manifest binding·큐/실패 보존 테스트와 독립 Astra 사전 검토. 설치 패키지/공식 소스 기준으로 실제 kwargs 전체를 검사하고 코드와 입력을 먼저 Git commit 해시로 고정한다. GPU/모델 로드는 canonical queue 외 금지.
5. **첫 GPU 결과:** 030:90 정확한 native frame 한 장 + 007:64 한 장만 공식 API로 smoke. 실제 returned Results, 사람/관절, confidence, 시간·메모리 및 original-vs-pose overlay **두 장**을 로컬에 출력. 중간 오류 시 추가 GPU 무인 반복 없이 먼저 CPU contract 수정; 새 배치의 기술 오류 retry 최대1회/독립 검토·별도 기록. 정상 API 출력에 사람0명일 수 있으므로 실행 실패와 품질 실패를 분리한다.
6. **통과 조건부 remaining:** 모델이 실제 인물의 관절을 유용하게 추정했다는 근거가 확인된 경우에만, 기존 고정 267개 중 smoke 2개를 제외한 remaining 265개를 **재생성 없이 한 번만** 실행한다. 손목·엉덩이·무릎·발목의 실제 대응·가림·중복·프레임 간 단절을 원본/오버레이로 검토. 불확실하면 2개 자료를 사람에게 묶어 검수 요청하고 충분하지 않으면 여기서 멈춘다. 규칙·추적은 정확한 사람별 관절과 물리적 경계가 확인된 경우에만 제한된 별도 하위 단계, 불충분 시 미실행. 실제 넘기 완료·위법성/정량 recall/F1/FPR을 새로 만들지 않는다.
7. **전체 전달:** 실제 실행, 근거, 독립 리뷰, EXP-0022 신규 report/metrics/binding, 기존 읽기 전용 웹의 이미지/재생·seek/지표 확인, GitHub push와 원격 SHA 대조까지 각각 분리 완료. CCTV/프레임/weights/raw coords/overlay/runtime/credentials는 로컬만. 완료 후 **실제 관절 두 장의 품질·나머지 실행 수·미실행 이유·비용·다음 한 선택**을 요약하고 새 GPU 작업 예약 없이 멈춘다.

이번 승인은 **기본 호출 오류를 해결해 실제 사람 관절을 확인하는 것**에 초점이 있다. 코드/테스트/해시만 많이 만드는 것으로 성공이라고 보고하지 않는다. 필요한 단계별 작은 재승인을 반복 요청하지 않고 실행과 검토를 연결한다.

---

# 다음 작업 — BATCH-0003 한도 종료, 품질 평가 미완료

2026-10-29 KST. [종합 결과](experiments/BATCH-0003-summary.md), [EXP-0021](experiments/EXP-0021-yolo26m-pose.md), [전달 기록](experiments/BATCH-0003-delivery.md)을 우선한다. 267개 입력 준비 뒤 최초 smoke와 허용된 단 한 번의 retry가 실행 어댑터 오류로 실패했다. 관절 출력0개로 사람/관절 품질·행동 구분은 평가하지 못했다. 모델 자체 성능 부족이나 GPU 메모리 부족으로 해석하지 않는다.

추가 GPU/모델 구성·remaining265·규칙/추적기·새 모델 실행은 승인 한도 밖이므로 자동 시작하지 않는다. 기존 가중치/입력/조건과 두 실패의 소스·queue provenance는 보존한다. 다음 별도 실험을 정한다면 공식 호출 signature와 head 초기화를 먼저 CPU로 검증한 뒤 성공 smoke와 실제 사람/관절 대응 근거가 필요하다. 기존 기본 구성을 교체하지 않는다. 아래 신규 승인 지시는 이번 실패 배치의 이력이다.

---

# 다음 작업 — BATCH-0003 YOLO26m-Pose 무학습 실험 승인·실행

2026-10-29 KST. 사용자는 **YOLO26m-Pose를 사전학습 가중치로만 시험하고, 관절 변화에 기반한 울타리 넘기 후보 검증**을 새 범위로 승인했다. [전체 계획 및 중단 게이트](experiments/BATCH-0003-yolo26-pose-plan.md)를 반드시 먼저 읽고 다음 단계를 완료한다. 기존 BATCH-0002 종료·'자동 추가 GPU 작업 없음'은 **이전 배치 종료 기록**이며, 이 명시적 신규 승인 범위 내에서만 대체된다. 새 배치를 또 자동 시작하지 않는다.

## 총괄 지시

1. 기존 Run `run_3d23462a014a`, Astra max 총괄 1명·Sol high 작업자 최대2·Astra high 독립검토1 및 canonical GPU queue, free VRAM≥6144MiB gate를 재사용한다. 기존 Task/Dispatch/환경·기본값·EXP-0001~0020 보존. 역할/실효 모델과 로컬 현재 상태 확인 후 배정한다.
2. 공식 `yolo26m-pose.pt` (COCO 17관절) **신규 체크포인트 딱1개**만 사용한다. 공식 버전·가중치·라이선스(AGPL-3.0)·환경을 검증해 `.venv-pose-batch03`로 격리하고 고정 manifest/ADR·source SHA 먼저 commit. 별도 학습·파인튜닝·다른 모델·VLM 재추론 금지. 라이선스/리소스 미충족 시 우회하지 말고 차단 결론.
3. 입력은 이전 EXP-0019 정확한 native PTS 11프레임 + 030[88,94), 007[62.5,67.5), 007[47.5,52.5), 030[50,55), 004[60,65)의 원본 최대10fps, **배치 고유 최대300프레임**. q04/030 시도와 q02/q05 접근, v01 줄 넘기/다른 장면을 구분해 기록. 원본 full-frame, 고정 기본 imgsz640/conf0.25/FP32, 보안/정보 비유입, 사전 기록 없는 ROI·threshold 변경 금지.
4. GPU smoke는 030:90과 007:64 2프레임만. bbox·17관절·confidence/NaN/원본 좌표·메모리/해시/큐 계약을 검사하고 통과할 때만 나머지를 한 번씩 직렬 실행한다. 성공한 smoke/기존 결과는 재실행하지 않는다. 오류 job당 최대1회 retry, gate/큐 우회·타 프로세스 종료·모델 크기 무음 변경 금지.
5. 사람 검출과 관절 정확성, 가림/미검출·좌우 관절 뒤바뀜·연속 변화의 신뢰도를 **로컬 원본/오버레이로 확인**한다. 정확한 사람·관절 GT 없는 숫자만으로 개선 판정 금지. **관절이 불충분하면 여기서 종료**. 충분할 때만 사전 고정 규칙 1종으로 손·무릎·발·울타리와의 시간적 관계를 관찰하고 접근/시도 구분을 시험한다. 새 별도 행동 학습·후보별 맞춤 임계값 변경/추적 ID의 무근거 연결 금지.
6. 소규모 사용자 관찰의 범위를 유지한다: 030:90 여러 사람 올라탐(개별 완료 미확정), q04 007 62.5–67.5 문 잡고 발 올림(완료 미관찰), q02/q05 접근-only, v01 줄 넘고 반대편에 선 한정 관찰. 사람별 정밀 F1/FPR/완료율·일반화 수치 만들지 않는다.
7. 기존 `orchestration.complete` 및 읽기 전용 로컬 결과 페이지에서 보고서·측정/그래프·독립 Astra 리뷰·원본/pose 오버레이 근거를 등록하고 브라우저 실재 표시·영상 재생/seek 확인, GitHub push 후 원격 실제 SHA/공개 경계 검증까지 수행. 데이터·프레임·개인 식별/관절 raw·weights/receipts/runtime은 로컬만. 실행/품질/행동/전달을 별도 판정하고 **한도 종료 후 멈춘다**.

사용자는 이 배치의 구현·검증·결과 등록까지 승인했다. 범위 안에서 작은 재승인을 반복 요청하지 않는다. 실행 불가능·품질 불충분이면 실패 이유와 재현 가능한 관찰을 정리한 **부분 완료**로 보고한다.

---

# 다음 작업 — BATCH-0002 비교 종료, 자동 후속 실행 없음

2026-10-29 KST. [종합 결과](experiments/BATCH-0002-summary.md)와 [전달 기록](experiments/BATCH-0002-delivery.md)을 먼저 읽는다. 입력 감사 → RF-DETR Medium 11개 고유 프레임 → Qwen3-VL-4B NF4 16개 view의 사전 고정 비교를 완료했다. 기존 2B 원래 질문 출력과 FCOS 캐시를 재사용했고 신규 가중치는 종류별 한 개다. 실제 CV 사람 대응은 미확정, 4B는 부분 후보 개선과 양성 출력 손실·6개 형식 실패가 공존해 둘 다 기본 적용 보류다. 결합 PoC는 근거 게이트를 충족하지 않아 실행하지 않았다.

- **완료한 실행:** CV 2개 queue 작업/11회 예측, 오류/OOM/retry 0. VLM 17개 job/attempt 중 16개 생성 성공과 v01의 보존된 준비 실패 1개; 논리적 오류 retry는 v01 한 번뿐이다. 모델 로딩 전 오류 복구를 성능 개선 설정으로 세지 않는다. 성공한 결과는 재생성하지 않았다.
- **형식과 행동:** 접근 q02/q03/q05의 유효 여섯 view에서는 잘못된 후보가 4→0이고 q04 C는 유지됐다. q04 B 누락, q03 B/q05 B의 근거 없는 완료 주장, q01/q06 B·C 및 v01/v03의 빈 행동 목록 실패가 남았다. v04 후보는 사라졌지만 세부 행동의 근거를 확정하지 않았다. 파싱 실패를 정상 또는 적절한 판단 유보로 처리하지 않는다.
- **관찰 범위:** q no-crossing 5/attempt-progress 1/primary positive 0, q06은 030 155–160초만 no-person/event. v01 새 관찰은 줄을 넘어 반대편에 서는 행동에 한정하고 과거 완료 미평가는 이력으로 둔다. v03의 바위 올라섬과 이전 옆 틈 시도 기록은 경계 통과 정밀 정답이 아니다. 031의 종료 미완료를 030에 전이하지 않는다.
- **전달:** 새 보고서/metrics/review/binding과 로컬 원본 참고·실제 입력 표시를 기존 완료 CLI/웹에 연결한다. 원격 GitHub byte 확인과 실제 브라우저 보고서·그래프·영상 재생/seek 확인은 각각 전달 기록을 따른다. 원본·프레임·가중치·원시 응답·receipt·DB·환경은 로컬 전용이다.

이번 배치의 고정 비교는 종료했다. 기존 MVP·CV/ByteTrack·원래 질문·ROI·경계와 EXP-0006 기본 보류는 그대로 둔다. 새 모델/프롬프트/해상도/추론을 자동 실행하지 않는다. 다음 별도 검증 후보 한 가지는 **같은 4B와 원래 질문에서 배경 기준 고정 감시 영역 입력 한 축의 효과**를 검토하는 것이다. q04 B/C 차이는 가설의 근거이지 원인 확정이 아니며, v01의 전체 화면 양성 실패가 출발점이다. 정답 사람 위치/사건 시각으로 crop하거나 이 개발 결과를 독립 성능으로 주장하지 않는다. 이 후속 실행은 이번 배치에 포함되지 않는다.

---

# 보존된 실행 전 지침 — BATCH-0002 CV/VLM 대안 검증

2026-10-29. 사용자가 **모델 개선 단계 진행**을 승인했다. 이 문서의 이전 `EXP-0017 종료 / 새 GPU 실행 없음` 지시는 역사적 범위의 종료 기록이며, **이번 명시적 승인 한도에서만** 아래 작업으로 대체한다. [BATCH-0002 고정 상한·평가 계획](experiments/BATCH-0002-model-upgrade-plan.md)을 처음부터 끝까지 읽고, AGENTS/관련 실험 문서와 적용 충돌을 확인한 뒤 진행한다.

## 총괄 실행 순서 (세부 단계 재승인 불필요)

1. **입력 충분성 감사:** q01~q06/v01~v04 + 기존 030/007 문제 장면의 원본과 실제 Qwen processor 입력·PTS·2fps·ROI/resize 정보를 로컬에서 확인. 미저장 q processor RGB는 과거 byte 동등성으로 주장하지 않는다. 입력에 시도 자세가 보이는지 미확정인지를 기록.
2. **CV 새 후보 1개:** FCOS/ByteTrack 과거 실패를 기준으로, 우선 RF-DETR Medium의 공식 오픈 체크포인트·라이선스·의존성을 검토. 소량 사람 검출 프레임(전체 최대240장)을 같은 PTS로 FCOS와 비교. 과거 FCOS 캐시가 동일하지 않으면 고정 FCOS만 재측정. 검출 개수·COCO AP는 SceneGuard 정확도가 아니다. 실제 넘기 순간의 사람 존재·중복·박스 안정성을 우선 점검.
3. **VLM 새 후보 1개:** 우선 Qwen3-VL-4B-Instruct를 공식 카드/라이선스/10GB 양자화 호환성 검증 후, q04/q05 1~2건 smoke → q/v 총10개 5초 개발창의 baseline 대조. 기존 ORIGINAL prompt(실패한 EXP-0017 수정본 아님), 원본 PTS·프레임·평가 기준 고정. 새 모델 4bit와 기존 2B BF16은 양자화도 달라진 비교임을 기록.
4. **결합은 조건부:** CV가 사건 순간 사람 관측을 개선하고 VLM과 상호 보완 근거가 확인될 때만, 저장 결과 중심의 오프라인 통합 PoC **최대 1개**. 조건 불충족 시 결합 **실행하지 않고 보류 결론**으로 종료. CV 검출 성공만을 VLM 호출의 필수 게이트로 삼지 않는다.
5. **독립 검토/배포:** 기존 총괄 Astra max, Sol high 담당(최대2)·Astra high reviewer, native Task/Dispatch, 기존 GPU 단일 queue 및 **여유 VRAM≥6144MiB** 게이트 유지. 정해진 상한 내 CPU 준비 병렬/GPU 직렬. 기존 완료 CLI와 웹 결과 등록, GitHub push·원격/실제 로컬 화면 검증을 별개로 완료. 한 페이지 비교 요약을 제출하고 멈춤.

**범위:** 신규 CV 체크포인트 최대1, 신규 VLM 최대1, 모델당 사전 고정 baseline 1회와 최소 smoke, 결합 PoC 최대1; 별도의 무제한 개선 실행·정답별 프롬프트 튜닝 없음. 신규 학습/파인튜닝/외부 추론 API/유료 결제/새 웹 UI/별도 큐/기존 파일 덮어쓰기는 금지. 새로운 라벨·영상 정답을 AI가 창작하지 않고, 10개 q/v는 개발 자료로서 독립 테스트/F1/FPR을 만들지 않는다. 원본 미디어/모델 가중치/raw inference/runtime은 로컬 전용. 게이트 실패 시 우회하지 않고 미실행 사유·부분 성과·다음 하나의 의사결정을 보고한다.

---

# 다음 작업 — EXP-0017 비교 종료, 자동 후속 실행 없음

2026-10-29 KST. 사용자가 승인한 단일 prompt 개선의 실제 비교를 완료했다. [EXP-0017 결과](experiments/EXP-0017-prompt-evidence-results.md), [실행 기록](experiments/EXP-0017-execution.md), [평가 코드 검증](experiments/EXP-0017-evaluation-notes.md), [전달 기록](experiments/EXP-0017-delivery.md)을 우선한다. EXP-0016은 실행 전 자원 차단 이력이며 그 보고서·binding은 변경하지 않았다.

## 현재 판단

- 기능 실행: 기존 canonical GPU queue에서 4개 job·20개 응답 저장, 오류/OOM/retry 0. 준비된 단일 prompt만 바뀌었으며 새 모델/가중치/설정 튜닝은 없다.
- 평가: q01–q06 기존 사용자 확인과 새 v01–v04 확인을 분리 적용했다. 저장된 131개 입력/결과 파일 검증과 21개 CPU 계약 테스트를 완료했다. 과거 q의 processor RGB/확장 질문은 미저장으로 byte 동등성을 확정할 수 없다.
- 성능: q02/q03/q05 잘못된 후보 감소 실패. q04 C 후보는 유지됐지만 완료 과장, B 누락은 지속. v01 후보 소실·v03 누락·v04 잘못된 후보 지속. **수정 prompt 채택 보류, 기존 구성도 성능 충족 선언 불가.**
- 정답: q no-crossing 5, attempt/progress positive 1, primary positive 0. q06 사람/사건 없음은 030 155–160초에만 해당한다. 031 영상 종료 미완료 관찰을 030에 전이하지 않는다. v01/v03 완료는 미평가, v03은 문 옆 틈의 시도다. v 4창은 2 source group이며 독립 카메라/장소 검증은 부족하다.

## 이후 제안과 종료 기준

추가 개선은 경계 근처 보행/대기와 실제 몸 올림/상대 이동을 구별할 시각 근거가 충분한지 확인하는 별도 계획부터 시작한다. 이번 결과에 맞춘 prompt 재튜닝, 새 입력/모델 비교를 자동 실행하지 않는다. 기존 기본값·CV·EXP-0006 적용 보류는 유지한다. 사람에게 이미 확인받은 q/v 전체를 다시 검수시키지 않는다.

이번 작업은 독립 Astra 검토, 담당3 완료 등록, 실제 보고서·14측정값/2그래프·검토·원본 참고 영상8개 재생/seek, 정상 GitHub push와 원격 byte 검증까지 통과했다. 각각의 receipt와 해시는 전달 기록을 따른다. 승인된 단일 개선 비교를 종료하고 추가 추론/튜닝 없이 멈춘다. 기능 실행·비교 평가 완료가 행동 성능 충족을 뜻하지 않는다.

---

## 보존된 이전 지침 — EXP-0016

# 다음 작업 — EXP-0016 단일 프롬프트 개선 비교 마무리

2026-10-28. 이 범위는 사용자가 승인했다. 작은 단계별 재승인을 요청하지 않는다. 작업 단위는 담당 배정 → 준비/실행 → 기록 → 독립 검토 → 기존 결과 화면 등록 → GitHub 게시와 실제 화면 확인까지다.

## 목표와 현재 상태

EXP-0015에서 사용자 확인한 q02/q03/q05 접근/비사건 장면의 false candidate를 줄이면서 q04 시도/진행 후보를 보존할 수 있는지, **Qwen 공통 prompt 하나만 수정**해 비교한다. 근거와 가설/한계는 [ADR-0017](decisions/ADR-0017-qwen-temporal-evidence-prompt.md), 실험 고정값과 결과는 [EXP-0016](experiments/EXP-0016-prompt-evidence-rubric.md)에 둔다.

- 완료된 준비: 실패 근거 검토, revised prompt, fixed q01–q06 두-view queue phase, CPU tests, 사용자 추가 v01–v04 라벨 수집.
- 현재 확인: 실행 담당 Sol high Task `task_305549d14771` / Dispatch `ctx_65256d02af82`가 2026-10-28 14:36 UTC에 RTX 3080 8464 MiB used / 1590 MiB free / 99% utilization을 측정하고 6144 MiB 최소 gate에서 중단했다.
- 실행 여부: canonical GPU queue에 EXP-0016 job/attempt 0개, Qwen 추론·model load 없음. 아래 모든 model outcome/cost는 미측정이다. Dispatch `failed`는 GPU 부족으로 인한 계획된 차단이며 추론 오류/OOM이 아니다.
- 별도 표본: E01_004 60–65초(v01 attempt/progress, completion not assessed), E01_004 0–5초(v02 non-event), E01_021 65–70초(v03 attempt/progress at adjacent gap, boundary relation ambiguous and completion not assessed), E01_021 0–5초(v04 non-event). 원본 source frame만 모델에 입력하고 prompt 기준/라벨/official timestamps는 전달하지 않는다. 기존 full-frame prompt와 revised prompt를 같은 입력으로 비교할 준비 중이다. E01_004/E01_021에 calibrated ROI가 없으므로 full-frame 하나만 쓴다.

## 현재 완료 상태

단일 공통 prompt 변경 코드, fixed q01–q06 및 v01–v04 경로와 CPU 검증은 구현됐다. `.venv-vlm`의 107 MVP tests와 `.venv-orca-lab`의 14 queue tests가 통과했다. 그러나 실행 담당 GPU 사전검사는 RTX 3080에서 1590 MiB free로 기존 6144 MiB gate를 통과하지 못했다. canonical queue는 EXP-0016 job/attempt 0, model load/inference 0이다. Astra는 blocked-before-inference 기록과 현재 report/metrics hash binding을 PASS했으나 행동 결과를 검토한 것은 아니다. 로컬 결과는 `inconclusive / blocked / adoption_on_hold`로 등록됐다. 기존 로컬 웹 화면에서 담당 slot3 카드, 보고서, 2개 그래프, review와 네 개 사용자 검수 원본 참고 영상의 재생/seek를 확인했다. 실제 행동 비교·비용·prompt 효과는 미측정이며 자동 채택하지 않는다.

이번 전달은 local 결과 등록, 실제 브라우저 확인, GitHub 게시와 원격 verify까지 완료했다. 표준 WSL git push에는 인증이 없어 connected GitHub Git Data API의 fast-forward publication을 사용했다. prompt 효과는 여전히 미측정/채택 보류다. 행동 비교를 재개할 때 GPU free memory가 최소 6144 MiB 이상일 때만 새 attempt를 만들고 기존 prompt·manifest·model·queue·한도를 유지한다.

## 순서

1. 현재 담당 Sol high가 수정한 four-window independent comparison phase와 tests를 총괄이 검토한다. 라벨 비유입, source/window/prompt hash, canonical Run/queue gate, 새 output 경로를 확인한다.
2. 최초 q six-window phase의 tests/code도 검토하고 q labels/EXP-0015 outputs가 바뀌지 않았음을 확인한다. 지원 환경 `.venv-vlm`에서 `tests_mvp`와 queue suite를 실행한다.
3. 코드/spec/docs를 먼저 커밋해 exact source hash를 고정한다. 기존 Run `run_3d23462a014a`와 canonical queue만 사용한다. 실효 담당모델/effort와 실제 card 진행을 확인한다.
4. 실행 직전 GPU free memory≥6144 MiB를 확인한다. 미달이면 실행/모델 load/enqueue를 보류하고, threshold 조정이나 queue 우회/다른 process 종료를 하지 않는다. 자원이 확보되면 q B/C revised prompt와 independent full-frame baseline/revised prompt를 등록된 작업 한도 안에서 직렬 실행한다. job 오류 재시도는 최대1회.
5. 실제 GPU output만으로 q01–q06의 사용자 라벨·기존 B/C·새 B/C·변화·불확실성을 비교한다. 독립 v01–v04에서는 action class와 completion, v03 boundary-location ambiguity를 분리해 본다. 모든 candidate를 제거/indeterminate로 바꾼 결과는 개선으로 보지 않는다. 정밀 정확도/F1/FPR/시간당 false alarms는 산출하지 않는다.
6. 코드, logs binding, report, null-safe metrics를 독립 Astra high에게 검토시킨다. 총괄은 exact report/metrics SHA review 후 기존 `orchestration.complete` 절차로 결과를 등록한다. 점수 성능이 개선되지 않거나 q04를 잃으면 기본 변경 채택 보류.
7. 코드/문서/공개 가능한 요약만 push한다. GitHub remote/ref/파일 해시와 실제 local page/service/browser 반영을 별도로 확인한다. 영상·이미지·weights/raw response/cache/runtime DB/receipts는 GitHub에 올리지 않는다.

## 완료 판단을 나눌 것

- **기능/테스트:** 코드, fixed-conditions, PTS/hash/queue tests가 통과했는가.
- **실행:** GPU queue/attempt, 실제 모델 호출, 메모리/생성 비용이 확인됐는가.
- **행동 성능:** q04 유지와 q02/q03/q05 감소가 동시에 있었는가, 독립 표본에서 behavior evidence가 유효했는가.
- **독립 검토:** Astra가 report/metrics의 고정 byte hashes와 해석을 확인했는가.
- **배포/전달:** 기존 페이지의 result/card/review 등록과 GitHub 게시를 각각 실제로 확인했는가.

필수 요약 상태/최신 사용자 라벨은 [MVP-0001 summary](experiments/MVP-0001-summary.md)를 따른다. q06의 no person/event는 E01_030 155–160초에만 해당하며, E01_031 종료 전 행동 관찰을 E01_030으로 전이하지 않는다. EXP-0014 과거 상태와 모든 원본/기존 결과는 보존한다.
