# BATCH-0006 — C6 고정 ROI에서 YOLO26m-Pose 640 → 960 입력 해상도 1차 검증

**승인:** 2026-10-29 KST. 사용자는 같은 사전학습 YOLO26m-Pose를 이용해 **C6 고정 ROI 입력 해상도만 640에서 960으로 변경**하여 E01_030의 **84/90/94초 세 프레임**을 비교하는 1차 검증을 명시 승인했다.

**상태:** 계획/실행 지침. GitHub 게시가 로컬 GPU 추론을 수행하거나 새로운 관절 품질을 확정하지 않는다.

## 1. 기준 자료와 단 하나의 변경 축

- 최신 사용자 시각 검수는 [EXP-0024](EXP-0024-user-pose-review.md). **84초 C6**는 세 사람이 대체로 잘 보이고 관절도 괜찮아 보임(정성), **90초 C6**는 넘는 3명 중 오른쪽 1명만 박스가 나오고 관절도 어긋남, **94초 C6**는 문에 올라탄 사람 1명·반대편에 있는 사람 1명이 원본에 보이지만 모두 검출 실패. 정확한 person/keypoint GT는 없으며 이 관찰을 모델 결과 수정이나 독립 카메라 테스트로 사용하지 않는다.
- [EXP-0023](EXP-0023-c6-pose-roi-comparison.md) **기존 C6 ROI 640** 실측 baseline을 **그대로 재사용**: 84초 3 person rows / retained joint estimates 38, 90초 1 / 12, 94초 0 / 0. 원본 exact PTS **1290240/1382400/1443840**, time_base **1/15360**, source E01_030, 저장된 원본 RGB·ROI crop·기존 640 native Results·모델/환경 SHA를 읽기 전용 확인한다. **640 재추론 0회**.
- C6 고정 ROI는 [camera config](../../configs/mvp0001_cameras.json)의 normalized xyxy **[0.28,0.20,0.75,0.80]** = 원본 1920×1080 기준 pixel **x[537,1440),y[216,864)**, RGB crop 648×903×3. 사람/사건 위치·기존 결과에 맞춰 재설정하지 않는다. 기존 `batch05_pose.geometry.crop` 함수와 `batch04_pose.api.bgr_source`를 읽기 전용으로 재사용한다.
- 오직 새 inference `imgsz=960` **한 축만 변경**. `orchestration/batch04_pose_command.py`의 원래 22개 공식 `PREDICT_KWARGS`를 복사한 새 dict에서 **`imgsz`만 640→960**, 나머지 **device cuda:0, quantize=None(FP32), rect=False, batch1, conf=0.25, classes=[0], nms=False, max_det=300, iou=.7, agnostic_nms=False, augment/compile/channels_last=False, 저장/표시/stream/visualize=False, embed=None**를 완전히 동일하게 유지한다. 기존 파일/상수·모델/가중치·Ultralytics 8.4.192·환경은 변경하지 않는다. 신규 모델/가중치·환경 설치·파인튜닝·추가 학습·외부 추론 API 없음.
- 원본 903×648 ROI의 960 입력은 **인터폴레이션 확대가 포함**될 수 있다. 새 세부 영상 정보가 창조되는 것은 아니다. 가설은 기존 640 downsampling에서 잃은 공간 정보가 덜 소실되어 모델의 person/pose 출력이 달라질 수 있다는 것. 통과/실패는 모델 출력과 원본 시각 대응으로 평가하며 원인을 단정하지 않는다.
- 기준은 **정확히 3 paired PTS comparisons**. 960의 3회와 **기존 640의 3개 cached 결과**를 나란히 비교한다. 전체화면 960, 두 번째 ROI, threshold sweep, conf 0.1/0.2, 타 모델, tracking, 규칙, VLM 호출, SAHI는 **이번 배치 범위 밖**.

## 2. 실행 전 CPU 계약 — 구현을 간소화하되 추론 경로 검증

1. 기존 소스와 EXP-0023·EXP-0024·EXP-0022의 report/review/binding, base model·ROI manifest, queue row 및 저장 원본을 보존한다. 신규 **BATCH-0006 / EXP-0025**와 별도 `batch06_pose/`, `orchestration/batch06_pose_command.py`, 실험 output/report/metrics/review ID를 사용한다. 이미 승인/완료된 BATCH-0005 job/attempt를 재시작하거나 cached result를 수정하지 않는다.
2. CPU에서 원본 native PTS/source/RGB/기존 crop 648×903 및 640 cached native Results·local artifact의 SHA 검증, 정확한 **3개 960 condition**과 cache disjoint, 전달 인자에서 `imgsz` 외 21개 값 동등성 검증을 우선한다. `rect=False`로 공식 input tensor shape (1,3,960,960)/CUDA FP32가 예상되며, **실제 shape는 GPU 실행 시 다시 검증·기록**한다. API/config signature는 설치된 v8.4.192에서 확인하고, ROI-local keypoints/bbox 좌표 offset(+537,+216) 한 번, unknown/empty/NaN 및 복수 사람 행 유지 합성 검사를 한다.
3. 기존 재사용 가능한 **공식 public YOLO.predict** 와 색상/ROI/좌표/오버레이 코드 위주로 소형 새 adapter를 작성한다. 준비·해시 관리만 과도하게 확장해 모델 호출을 누락하지 않는다. 코드/manifest/version·원본/cached/model SHA를 **실행 전 커밋 고정**하고 독립 Astra high의 CPU/source preflight 검토를 받는다. CPU-only 작업에서 모델을 로드하거나 GPU를 사용하지 않는다.

## 3. 세 프레임 GPU 실행 상한

- 기존 Orca Run `run_3d23462a014a`, **Astra max 총괄1 / Sol high 담당 최대2 / Astra high 독립 검토1**, native Task/Dispatch는 새 배정하고 실제 effective model/effort 확인. 기존 **canonical 단일 GPU 큐**, inherited lock과 exact parent/child·source/input/config/commit/lease 검증, CUDA0 **실행 전 free VRAM >=6144 MiB**의 동일 gate를 유지한다. 다른 GPU 프로세스 종료/큐 우회/메모리 gate 하향/CPU·모델 무음 fallback 금지.
- **새 960 예측 최대 3회**: `030_090_C6_960`, `030_084_C6_960`, `030_094_C6_960` 순서 권장. 한 번의 모델 construction/load/공식 predictor setup/warmup 뒤 각 원본 입력을 **단 한 번씩** 추론한다. **90초가 정상 empty라도 84·94를 반드시 처리**한다. 960에서 메모리 오류나 기술적인 실제 예외 발생 시 중단·기록; 부분 성공 프레임 재생성 금지. 한 오류 correction을 허용한다면 원인/수정 내용·CPU signature 회귀/독립 검토·신규 frozen 소스/명시 허가를 받은 **최대 1회**뿐이다. 모델·해상도를 몰래 640/768로 대체하지 않는다.
- 사용자가 본 3개 실제 640 원본/관절 비교는 이미 로컬에 있다. 같은 84/90/94원본을 사용해 **960 input의 native Results(person box/keypoints)** 와 640 cached Results를 검증 가능한 원본 좌표로 표시한다. ROI Results는 crop-local: 기존 `batch05_pose.geometry.rows`로 unknown 판단 후 **offset(+537,+216)을 딱 한 번**, 640/960 모두 원본 1920×1080 위에 일치하도록 그린다. 한 프레임에 여러 사람이 있으면 **모든 사람 행을 표시**하고 사람별 confidence/관절 추정치를 구분한다. 0명 정상 반환 ≠ 오류.
- 각 시점에 **original / C6 640 cached overlay / C6 960 new overlay** triptych 3장을 **로컬에 생성**. 기존 640 이미지를 단순 재생성할 때도 기존 native Results/artifact hash로 묶고 **640 새 추론을 하지 않는다**. 원본과 직접 비교해 박스가 실제 인물을 감싸는지, 손목·엉덩이·무릎·발목이 맞는지, 머리/몸/다리 교차 및 울타리 가림·부분몸·오검출, ROI 경계 잘림을 확인한다.
- 84초의 기존 양호한 검출이 960에서도 유지되는가, 90초 실제 넘는 3명의 누락/관절 불일치가 얼마나 남는가, 94초 원본에서 관찰된 2명 중 누가 보이는가를 **사람별 정성 표**로 기록한다. **출력 행 수/관절 수 증가만으로 성능 개선 확정 금지**. 인물별 GT/정확도/recall/F1/FPR 또는 넘기 완료 판정은 만들지 않는다. 새로운 960 이미지의 실제 사람 대응이 클라우드 에이전트에 안 보이면 **사람 검수 필요**라고 쓰고 3개 그림 묶음으로 사용자에게 요청한다.
- 평가상 해상도 증가의 영향을 보려는 **개발용 3프레임**일 뿐 독립 카메라/시간 안정성 검증이 아니다. 후속 추적/관절 행동규칙/다른 모델/SAHI/전체267·5초창은 **실행하지 않는다**. 960이 실패해도 다음 실험을 무인 승인된 것으로 해석하지 않는다.

## 4. 완료·전달

- 기록은 **EXP-0025**에 별도 등록: (1) 공식 API 기술 실행, (2) 사람 검출 대응, (3) 관절 위치 대응, (4) 행동 분별 **미측정**, (5) 독립 검토와 로컬 UI / GitHub 전달 완료 여부로 분리.
- source/manifest/실제 Results·raw 관절 좌표·모델 입력·모든 영상/오버레이·weights·GPU/runtime DB/logs/receipts/실제 개인 경로는 **로컬 전용**. 공개 GitHub에는 일반 코드/합성 테스트/비식별 3행 비교 및 null 지표/독립 검토만. 기존 AGPL-3.0 원칙 및 무라이선스 코드 복제 금지 유지.
- 기존 `orchestration.complete`와 읽기전용 `http://127.0.0.1:8765/`의 **실제 이미지3장·보고서·지표·독립 리뷰 렌더링** 검사, 정상 GitHub push 및 **remote commit/blob byte 검증**까지 작업 범위. 정지 이미지 3장인 경우 영상 재생/seek는 해당 없음.
- 최종 결과는 **3개 시각의 640 cached/960 new 출력 숫자와 실제 신체/관절 정합성, 90·94에서 의미 있는 누락 감소 여부, 비용 및 VRAM, 확인 불가 항목, 다음 한 의사결정**으로 보고하고 **새 GPU/모델/해상도 sweep을 자동 예약하지 않는다**.

**실험의 실제 완료는 960 실측 3개를 반환해 기존 결과와 정직하게 비교한 경우다. 준비 완료/CPU 테스트/수치 증가만으로 검출·행동 개선이라고 주장하지 않는다.**
