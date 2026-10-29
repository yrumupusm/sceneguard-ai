# BATCH-0005 — YOLO26m-Pose 전체 화면 vs 기존 C6 고정 ROI 비교

2026-10-29 KST. **사용자가 이번 제한된 후속 실험을 승인했다.** 목표는 **사전 설정된 감시 영역 crop이 E01_030의 문 넘기 자세에서 사람·관절 검출 누락을 개선하는지** 확인하는 것이다. **계획 게시 ≠ 실제 로컬 GPU 실행/성능 개선.**

## 1. 고정 사실과 가설

- [EXP-0022](EXP-0022-yolo26-public-predict.md)에서 **공식 Ultralytics 8.4.192 / YOLO26m-Pose / public YOLO.predict / full-frame / 640 / FP32 / conf0.25 / nms=False**가 실제 정상 작동했다. E01_030 **정확한 native PTS 90.0초의 full-frame 결과는 사람 0, 관절 0**. E01_007 64초는 출력 2행/관절 추정23개지만 정확한 사람-관절 대응은 별도 문제. 기존 두 출력/원본/해시/최종 리뷰는 바꾸지 않는다.
- [고정 카메라 설정](../../configs/mvp0001_cameras.json)의 **C6 ROI = normalized original xyxy [0.28, 0.20, 0.75, 0.80]**. 문이 아닌 사람 또는 모델 결과에서 ROI를 추정하지 않고, **원래 PTS 0 정지 배경을 기준으로 선정됐던 영역을 그대로 사용**한다. C6의 calibrated=true는 감시용 ROI 지정이며 **실제 울타리 상단·바닥·경계 건너편의 물리적 교정 증거는 아니다.**
- 원본 1920×1080 기준 crop 계약은 원래 구현의 floor(min), ceil(max)를 검증해 **x=[537,1440), y=[216,864), W903×H648**을 사전 고정한다. 모델/오버레이에 넘기기 전 원본 ROI가 실제 관심 인물을 포함하는지는 **로컬 원본으로 확인**, 미확인일 때 그 한계를 남긴다. crop 경계의 사람·관절 일부가 잘리는 경우도 보존·명시한다.
- 유일한 가설: **고정 ROI crop에서 인물의 입력상 픽셀 크기가 상대적으로 커지면, 전체화면에서 빠진 사람·관절이 일부 검출될 수 있다**. 개선을 보장하지 않는다. 같은 640 모델 입력이라도 원본 공간 범위와 resize/letterbox가 달라진다. 점수 0.25가 실제 확률이나 정확도 GT는 아니다.

## 2. 딱 세 시점 × 두 보기 = 여섯 조건

| exact original source PTS | 전체 화면 full | 사전 고정 C6 ROI |
| --- | --- | --- |
| **030_084** | 이번에 1회 새 추론 | 이번에 1회 새 추론 |
| **030_090** | **EXP-0022 기존 실제 Results 재사용, GPU 재추론 금지** | 이번에 1회 새 추론 |
| **030_094** | 이번에 1회 새 추론 | 이번에 1회 새 추론 |

- **신규 예측 총 5개, 별도 모델/가중치 다운로드 0, 추가 훈련 0, VLM 호출 0.** E01_030의 소스 SHA, exact native PTS/time base, source RGB와 030_090 full-frame 원래 artifact의 해시를 동결한다. 유사 시각 인접 frame으로 대체하거나 원본 영상을 다시 라벨링하지 않는다.
- E01_030의 약 90초에 사람이 문에 올라타 있는 관찰은 기존 사용자 제공 사실이다. **84초 접근 인물, 94초 관심 인물**은 이전 실험의 관찰 범위에서만 해석하고, 각자의 행동 시작/완료를 임의 확정하지 않는다. 031의 종료 미완료는 030의 정답이 아니다.
- **모델·환경·공식 public API 설정 고정:** 원래 YOLO26m-Pose official checkpoint SHA256 = \`2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4\`, \`.venv-pose-batch03\` / Ultralytics \`8.4.192\`, \`batch04_pose.api.bgr_source\` 와 \`result_rows\`의 검증된 경로를 가능한 한 재사용한다. 전체화면, ROI 모두 \`imgsz=640,rect=False,batch=1,conf=.25,nms=False,max_det=300,quantize=None(FP32),device=cuda:0\` 및 나머지 EXP-0022 \`PREDICT_KWARGS\` 그대로. 모델 교체/실패 장면별 임계값 변경/클래스 변경/추가 해상도 실험 금지.
- **원본 ROI crop 준비:** 원본 RGB에서 \`crop=rgb[216:864,537:1440]\` (실제 카메라 config 좌표의 floor/ceil 계산도 검증)하고 공식 \`YOLO.predict(source=contiguous_BRG_ndarray)\` 호출한다. 입력은 **BGR**, 변수명 오기는 실제 구현에 반영하지 않는다. **출력 Results의 boxes/keypoints는 crop 좌표계**이므로, 정확히 한 번 \`x +=537,y +=216\`를 적용해 **원본 화면 좌표로 재배치**한다. ROI 밖 0개 출력은 원본 전체 0개와 다른 관찰 범위이며 '정상' 판정이 아니다. \`batch04_pose\`의 전체 화면 Results는 이미 원본 좌표이므로 재스케일/offset 금지.
- 결과 이름·좌표계·PTS/source/ROI 해시·모델 설정·관절 confidence의 범위를 명시한다. 17개 COCO keypoints, confidence>=0.5는 **기록용 추정치 기준**이지 실제 관절 정답 아님. 0개 예측, 가려짐, 누락, 좌우 관절 뒤바뀜은 구분한다.

## 3. 구현과 실행: 단순하게, 같은 GPU 경로로

1. **기존 결과/입력 준비를 다시 하지 않는다.** EXP-0022 및 EXP-0021/이전 실험의 raw pose/원본/보고서/queue/작업 상태를 불변으로 보존한다. 새 \`BATCH-0005 / EXP-0023\`의 **작은 별도 실행 모듈**, 입력 manifest/5개 조건, report/metrics/review/artifact 경로를 만든다. 기존 \`batch04_pose\` public API 유틸은 source freeze가 바뀌지 않도록 **읽기 전용으로 재사용**하고 BATCH-0004 runner 재실행/수정 금지.
2. **GPU 전 CPU 테스트 (가중치/모델 구성·추론 없음):** crop 픽셀 좌표·RGB/BGR 순서·원본 해시/PTS/C6 geometry가 정확한지, crop 결과 shape 648×903×3, 박스·관절 offset 정확히 한 번/원본 범위, empty response/clip boundary/NaN 처리, 기존 030_090 전체화면 raw 결과의 SHA 및 새5개 disjoint, 공식 \`YOLO.predict\` 공개 인자와 queue identity 검증. 원래 공개된 interface를 변경하지 않는다. 성공 기준에 불필요한 과도한 테스트·보고서 생성으로 실제 5회 추론을 지연하지 않는다.
3. 기존 **Orca Run \`run_3d23462a014a\` / Astra max 총괄1, Sol high 실행 담당 최대2, Astra high 독립 검토1**. **기존 canonical single GPU queue** 사용, free VRAM ≥6144MiB gate/parent-child lease·버전/해시·source freeze 확인, GPU 작업은 직렬. CPU 문서 작업 병렬 가능. 현행 UI는 그대로 재사용.
4. **CPU 사전 검증과 source/manifest commit, 독립 검토 후**, 한 실행 job에서 **딱 5개 신규 조건**을 순서대로 1회씩 수행한다. \`030_090_C6\`를 첫 기술 smoke로 확인하되 **정상 empty Results(0명)라도 030_084/030_094의 예정 비교는 계속 처리한다.** 기술 API 예외/메모리 제한은 중단·실패 기록, 코드 오류 correction은 고정 config/기존 실패 보존/검토를 거친 **최대1회**만 허용. 성공한 조건은 다시 생성하지 않는다. warmup은 측정하되 원본 프레임 예측으로 세지 않는다.
5. **평가:** 동일 PTS쌍의 full vs C6 crop에 대해 (a) 실제 관심 인물을 감싸는 person bbox, (b) 유효 범위의 손목·엉덩이·무릎·발목과 실제 신체 부착 여부, (c) 가림/누락·중복·배경 의심, (d) ROI 경계 잘림, (e) 시간·GPU 메모리를 별도로 기록한다. 최소 **84/90/94 각 원본 / 전체화면 overlay / ROI overlay**를 나란히 보여 주는 로컬 자료를 제공한다. **전체화면 90은 기존 결과 재사용**임을 표시한다. 모델 출력 count 증가만으로 사람·관절 복원 성공이라 말하지 않는다.
6. **90초 성공 여부를 보기 위해 사건 정답에 맞춰 crop을 수정하지 않는다.** ROI에서 사람 박스가 나와도 신체·관절 대응 확인 전에는 품질을 미확정으로, 90에서 여전히 0이면 ROI 방식만으로 중요한 누락을 해결하지 못한 관측으로 분리한다. 사람별 정확한 GT 없으므로 accuracy/precision/recall/F1/FPR·완료/위법성 판정 없음.
7. **이번 배치는 세 시점 비교에서 종료.** 새 267 전체 처리, YOLO 추적·사전규칙·CV+VLM 결합, ROI 크기/임계값/해상도 추가 조정, 새 체크포인트·추가학습/유료 API/새 웹 UI는 **승인하지 않는다**. 다음 단계가 유망하면 근거와 함께 사용자에게 제안만 한다.

## 4. 납품과 검증

- EXP-0023 별도 **기술 실행/시각 품질/행동 성능(이번 미평가)/독립 리뷰/전달** 판정. 신규 5회 실제 수행과 기존 1회 재사용을 구분. 과거 030 full-frame failure는 새 5회 성공 집계에 포함하지 않는다.
- 최소한 원본/전체화면/고정 ROI의 **3시점 시각 비교 자료**(CCTV/좌표/관절 포함)는 **로컬에만 보관**하고, 사용자 확인이 필요한 경우 **한 묶음**으로 요청한다. 비교 결과의 이미지 존재와 실재 관절 일치 판정은 별개다.
- 독립 Astra review의 report/metrics binding → 기존 \`orchestration.complete\` 등록 → 읽기 전용 \`http://127.0.0.1:8765/\`의 실제 이미지 decode/render·지표/독립 검토 확인 → GitHub push 및 원격 SHA/bytes 별도 확인을 수행한다. 미디어가 정지 화면뿐이면 동영상 재생/seek는 해당 없음으로 기록.
- GitHub에는 구현/테스트/비식별 정량 요약·해석만. **실제 영상·프레임·사람 좌표·관절 원시값·overlays/weights·토큰/raw response·runtime/queue DB/receipts/실제 절대경로**는 로컬 유지. AGPL-3.0/source 관련 기존 방침과 third-party 코드 무단 복제 금지.
- 사용자에게 최종 **세 시점의 full/ROI 박스 개수와 확인 가능한 시각 대응, 90초 관절 복원 여부, 비용, 남은 한계, 권고 한 가지**를 간단히 전달하고 GPU 추가 작업 예약 없이 종료한다.

**이번 승인은 새 입력 방식 한 축을 검증하는 독립 배치에 한한다. 세부 단계마다 재승인받지 말고 CPU preflight→5개 실제 추론→독립검토→기존 웹/원격 GitHub 확인까지 실행하되, 실패/정보 부족이면 미실행 항목과 이유를 정확히 기록한다.**
