# BATCH-0003 — YOLO26m-Pose 무학습 자세 추정·울타리 넘기 단서 검증

- 승인일: 2026-10-29 KST
- 상태: **사용자가 새 실험 범위를 승인함. 이 문서 게시만으로 로컬 GPU 실행·성능·모델 적용을 주장하지 않는다.**
- 직전 상태: [BATCH-0002-summary](BATCH-0002-summary.md) / [EXP-0019](EXP-0019-cv-comparison.md) / [EXP-0020](EXP-0020-vlm-comparison.md)
- 사용자 요구: **추가 학습·파인튜닝 없이** 사전학습된 YOLO-Pose와 관절 기반 규칙이 SceneGuard의 접근/대기와 실제 넘기 동작을 구분하는 데 도움이 되는지 실험. 기존 FCOS/RF-DETR/Qwen 기본 파이프라인을 교체하거나 통합하지 않음.

## 1. 가설과 관찰의 분리

**검증 질문:**
1. E01_030 약90초, E01_007 약64–66초에서 **사람별 박스 및 손목·엉덩이·무릎·발목의 2D 좌표와 confidence**가 실제 인물에 대응하는가?
2. 사람·관절이 일시적으로 가려지거나 겹칠 때 실제 관측과 미검출/불확실성이 어떻게 바뀌는가?
3. 같은 영상의 접근·대기 시간대와 비교하여 **시간에 따른 신체/경계 관계**가 후보 생성을 뒷받침하는가? **규칙은 데이터에 맞춰 사후 최적화하지 않는다.**
4. 관절 추정의 품질이 기준에 못 미치면 rule/track/fusion 단계는 **실행하지 않고 보류**할 수 있는가?

**범위 한계:** YOLO-Pose는 사람 검출 + 17개 COCO 관절을 출력할 뿐 **넘기/권한/침입을 자체적으로 분류하지 않는다**. bbox 수나 keypoint 수, single-frame COCO AP, 벤치마크 수치가 넘기 감지 정확도를 뜻하지 않는다. 실제 행동 정답은 사용자 관찰의 제한된 구간 정보만 있고, 사람별/관절별 프레임 정밀 GT는 없다. 따라서 이번 결과에 accuracy, precision/recall/F1, FP/hour, independent generalization을 억지로 계산하지 않는다.

## 2. 모델 한 개, 공식 문서와 법적 주의

- 유일한 신규 가중치: **공식 COCO pretrained `yolo26m-pose.pt`**. `ultralytics` 패키지의 단일 모델 `YOLO("yolo26m-pose.pt")`에 해당하며, 공식 문서에는 기본 640 입력, 17개 COCO 관절, Pose AP50:95 68.8(COCO val2017)로 안내된다. 이는 우리 CCTV의 성능이 아니다.
- 출처: https://docs.ultralytics.com/tasks/pose ; https://docs.ultralytics.com/models/yolo26 ; https://docs.ultralytics.com/modes/predict ; https://docs.ultralytics.com/modes/track .
- **실제 설치 전** 안정 릴리스의 정확한 `ultralytics` 버전, Git tag/release, 공식 체크포인트 다운로드 URL/size/SHA256, Python/Torch/CUDA 호환, license를 확인하고 ADR/manifest에 동결한다. 임의 `latest`에 의존해 기록 없는 업데이트를 하지 않는다. 깨끗한 격리 `.venv-pose-batch03`에서 설치; 기존 venv(특히 transformers 4/5 충돌)는 건드리지 않는다.
- 공식 Ultralytics는 AGPL-3.0 또는 별도 Enterprise 조건을 명시한다. https://docs.ultralytics.com/help/contributing . 이번은 **로컬 연구용 평가**이며, 향후 제품 통합·공개 배포·라이선스 의무는 별도 검토 전 진행하지 않는다. weights/third-party source/vendor 파일을 GitHub에 업로드하지 않는다.
- 행동 규칙 아이디어는 공개된 'Pose-Based Fence / Wall Climb Detection' 사례(https://github.com/Khushnoor-gojwari/Fence_detection_wall_and_iron_fence)를 **개념적으로 참고**하되, 해당 저장소에서 확인되는 명시적 라이선스가 없으므로 구현 코드를 복제·벤더링하지 않는다. 별도 학습 없이 손/발/무릎/몸의 위치를 보는 보편적인 기하학 원리를 **자체 코드로 작성**한다.
- 추가 모델 금지: YOLOv8/YOLO11/YOLO26s/l/x, 새 detector/pose 행동 분류기, 학습형 PoseC3D, 신규 VLM 등 **추가 가중치·유료 API·fine-tuning 없음**. 호환성 또는 자원 실패 시 자동 하향 대체하지 않고 명시적으로 종료.

## 3. 고정 입력·GPU 실행 상한 — 먼저 관절 품질만

**A. 기존 CV 진단 프레임 11개:** EXP-0019에서 사용한 같은 source/native PTS/time_base: `030_084/090/094`, `007_052/064/066`, `031_032/040`, `006_119/125/131`. 006 nominal label은 실제 native PTS≈118.985533/124.991533/130.997533; 같은 시간으로 묶어 정확한 원본 decoded PTS를 재사용한다. 원본 FCOS·RF-DETR 캐시와 동일 시점만 질적으로 비교하고, 모델당 다른 전처리/score를 그대로 명시한다.

**B. 연속 관찰창 — 사전 고정된 다섯 구간, 총 26초:**

| alias | 원본 | 원본 PTS 구간 [start,end) | 기존 사용자 관찰의 범위 |
|---|---|---|---|
| climb030 | E01_030 | [88,94) | 약90초 실제 문 올라타는 사람들 관찰; 개별 완료/정밀 시작 미확정 |
| climb007 | E01_007 | [62.5,67.5) | q04: 문을 잡고 발 올림/시도 진행, 구간 내 완료 미관찰 |
| approach007 | E01_007 | [47.5,52.5) | q02: 접근만, 넘기 시도 없음 |
| approach030 | E01_030 | [50,55) | q05: 접근만, 넘기 시도 없음 |
| rope004 | E01_004 | [60,65) | v01: 줄을 넘어 반대편에 선 모습 관찰; 울타리 넘기/모든 사람 완료로 일반화 금지 |

- **시간 샘플링은 원본 native PTS 기준 고정 10fps 이하, 배치 전체 최대 300 고유 프레임**(진단 프레임 포함·중복 PTS deduplicate). 10fps에서 26초≈260개 프레임이고 기존 11개를 더해도 300 안쪽. 로컬 소스 FPS/PTS 특성에 따라 정확한 개수는 실행 전 manifest에 고정, 미래 프레임 미사용. 2fps VLM과 시간 샘플링이 다르므로 속도/정확도 직접 대조는 하지 않는다. 반복된 GPU 실행 없이 smoke에 사용한 동일 입력은 본 실행의 결과로 재사용한다.
- 원본 전체 프레임만 입력. 첫 baseline은 공식 전처리 `imgsz=640`, `batch=1`, `conf=0.25`로 고정하고 `device=cuda:0`, 모델 FP32/실제 tensor shape, `rect`/padding, 각 반환 confidence·index 및 원본 좌표 변환 결과를 기록한다. 추론 후 `keypoints.data`와 bbox를 사람/관절 순서가 유지된 형태로 보존한다. keypoint confidence 부재를 있다고 만들거나, 낮은 confidence/가림을 (0,0) 정상 좌표로 처리하지 않는다. 선택한 임계값과 출력 계약을 실행 전 ADR에 명시한다.
- 이번 배치는 **고정 감시 영역 크롭, 입력 해상도 변경, threshold sweep, aug/flip, per-clip 모델 튜닝 없음**. 감시 경계는 기존 C3/C6 등 사전 고정된 카메라 설정만 참조. `rope004`는 다른 형태의 경계이므로 넘기 규칙의 주 양성으로 혼합하지 않고 정성적 도메인 차이 표본으로 둔다.
- 최소 smoke는 `030_090` 및 `007_064`의 **2개 고유 프레임**만; 17개 관절 인덱스·사람 매핑·NaN·keypoint shape·VRAM·source hash·원본 좌표 변환을 먼저 검사. 기술 문제가 있으면 나머지를 실행하지 않는다. 통과하면 같은 시점의 재생성 없이 고정 매니페스트 나머지 한 번 실행.
- 모델 구성/추론은 기존 **Orca canonical GPU queue 직렬**, free VRAM≥**6144 MiB** 사전 게이트, 다른 프로세스 강제 종료·gate 하향·큐 우회 금지. 정확한 source/manifest/package/weights SHA + Run/Task/Dispatch, lease/parent/child 검증. 작업별 오류 재시도 **최대1회**, 성공한 결과 재생성 금지. 대체 양자화·CPU offload·모델 다운그레이드로 결과를 조용히 채우지 않는다.
- 기본값·이전 `EXP-0001~0020` 코드/라벨/캐시/가중치/측정 결과 불변. 실제 pose 주석 이미지·원본 비디오·관절 좌표/raw arrays·런타임 DB/receipt는 로컬/ignored 전용, 공개는 개인 식별 불가능한 요약과 테스트 코드만.

## 4. 결과 감사와 조건부 추가학습 없는 단일 규칙 실험

**우선 판단은 관절 품질이고, 행동 분류는 선택 사항이다.**

1. 기존 11개 native 프레임에서는 **실제 사람/부분 신체에 bbox가 대응하는지**, 왼/오른 관절 뒤바뀜, 가림/잘못된 땅·울타리 위 관절, 작은 사람 누락, 중복/배경 의심을 따로 검토한다. `030_090`에 bbox가 나왔다고 곧바로 사람 3명을 복원했다고 주장하지 않는다.
2. 연속창에서는 **각 사람의 관절 관측 커버리지, wrist/hip/knee/ankle의 visible confidence, 시각적 일치, 프레임 간 위치 점프/ID 단절, 카메라 시점에 따른 위치 오해**를 진단한다. 추적 ID는 pose 출력의 보장 사항이 아니며 필요하면 기존 문서/기본 tracker 중 **사전 고정된 한 가지**만 별도 CPU 기반 후처리로 검증한다. 다른 사람의 관절을 같은 track으로 섞을 수 있으면 연속 동작은 '불명'으로 유지한다. 예측/보간 관절과 실제 관측을 분리한다.
3. 사람이 보이는 구간에서도 사람 검출·필수 관절이 불안정하거나, 기존 경계 설정이 울타리 상단/반대편 판정에 불충분하면 **규칙 단계 진입하지 않고 'pose evidence insufficient'로 종료**한다. 최소 기술 통과(모델 실행/정상 tensor)와 행동 충분성을 혼동하지 않는다.
4. 조건 충족 시에만 **사전 등록한 규칙 기반 후보 1종**을 구현. 독립적으로 사람이 그린 고정 경계/울타리 위치와 관절의 상대 위치, 손 올림·무릎 굽힘·발목 높이 변화·몸 위치 이동을 관찰. **접근/접촉만으로 완료 선언 금지**, 단일 프레임 오차에 대해 지속 관찰 조건을 두되 threshold는 테스트 출력에 맞춰 반복 조정하지 않는다. 비사건 q02/q05와 시도 q04/030을 같이 평가하며, 대상별 경계 해석이 불가능한 v01은 별도. 불충분한 경우 후보 없음(normal)이 아니라 **unknown**을 허용한다.
5. **타당한 시간적 관찰이 실제로 추가되는지**만 판단한다. 바운딩박스나 pose skeleton의 수로 recall, person-level track accuracy, crossing 완료율을 계산하지 않는다. 사용자가 이미 확정한 구간 사실을 반전하지 않고, 필요 시 로컬 비교 이미지·짧은 참고 영상의 **한 묶음**으로 최소한의 사람 검수 요청만 한다.
6. 이번에 Qwen 2B/4B **재추론 없음**, CV+VLM 이벤트 파이프라인 통합 없음, 포트폴리오 성능 홍보 없음. 결과가 확인되면 다음 별도 사용자 승인 배치에서 결합을 검토한다.

## 5. 개발·독립 검토·전달

- 기존 Run `run_3d23462a014a` / Astra max 총괄 1명, Sol high 구현·실험 담당 최대2, 독립 Astra high 리뷰1, 필요 시 별도 UI worker 없이 **기존 읽기 전용 웹 결과 페이지** 재사용. native Orca Task/Dispatch의 실제 effective model을 검증. agent 작업 상태는 GPU 사용과 구분한다.
- 진행: 원본/보고서·공식 레퍼런스 확인 → ADR+고정 manifest/계약+소스 커밋 → CPU synthetic tests/설치 호환 → 단일 queue smoke → 고정 구간 실행 → 로컬 pose overlay/원본·기존 CV 비교 → (품질 충분할 때만) 사전등록 규칙 1회 → 독립 리뷰 → 완료 등록 → 기존 로컬 웹 actual browser 확인 → GitHub push / remote SHA 검증.
- 작업자에게 기존 `BATCH-0002` 최종 결과가 보존돼야 함을 재강조. GPU 자원 부족/라이선스 미확정/미디어 검증 부족 시 중단하고 막힌 이유를 결과로 남길 것. 범위 내 작은 작업마다 반복 승인받지 말고 총괄이 완료까지 수행한다.
- 완성 산출물: `EXP-0021`(또는 충돌 시 연속 신규 ID) 실행·진단 보고서, source/input/model/weights/환경 해시, 정확한 PTS별 pose/bbox 커버리지와 원본 대비 관절 일치 검수표(사용자 관찰/에이전트 추정 분리), 원본/overlay 비교 자료(로컬 전용), 비용/VRAM/오류/단절 측정과 근거·한계, 독립 리뷰·SHA binding·기존 결과 웹 등록·GitHub verified delivery. 별도 규칙 검증 시 **다른 신규 결과 ID 또는 명시된 하위 단계**로 구분.
- 종료 판단을 ① 기술 실행 ② 사람/관절 품질 ③ 행동 후보 분별 ④ 독립 검토 ⑤ 웹·GitHub 전달로 나누고 **이번 승인 한도 종료 후 자동 추가 실험 없음**.

**실험의 성공 기준은 모델 실행 자체가 아니라, '접근과 넘기 시도'를 구분하는 데 재현 가능한 관절 단서가 실제로 있는지 확인하는 것**이다. 없으면 그 실패 원인까지 보고하는 것이 유효한 완료다.
