# BATCH-0004 — YOLO26m-Pose 공식 추론 API 복구

**2026-10-29 사용자 승인.** BATCH-0003 기술 실패를 별도의 BATCH-0004 / EXP-0022에서 복구하고 실제 관절 출력부터 확인한다. **현재 상태는 계획 승인·GitHub 게시이며 실제 로컬 추론의 성공을 뜻하지 않는다.**

## 0. 해결하려는 문제와 이력 보호

- [BATCH-0003 결과](BATCH-0003-summary.md), [EXP-0021](EXP-0021-yolo26m-pose.md), [독립 검토](../reviews/EXP-0021-independent-review.md)는 변경하지 않는다. 최초 smoke는 head/end2end 초기화 검증에서, 유일한 retry는 공식 BaseModel.predict가 지원하지 않는 visualize=False 호출 인자로 실패했다. 모델 로딩 2회/성공 예측 0회이며 사람·관절 성능은 **전혀 미측정**이다.
- 새로운 실행 코드·등록 명령·metrics/로컬 출력은 EXP-0022의 **완전히 별도 경로**에 작성한다. batch03_pose, configs/batch0003_pose_manifest.json, 과거 두 실패 job/attempt 및 원본 bytes, 기타 EXP-0001~0021의 결과는 변경하지 않는다. 기존 BATCH-0003 재시도 한도를 초기화하거나 실패 job을 되살리지 않는다.
- **추가 학습/파인튜닝/새 가중치/새 데이터/다른 모델/Qwen 재추론/모델 기본 교체 없음.** 목표는 공인 사전학습 YOLO26m-Pose를 정상 실행해 관절 품질을 관찰하는 것이다.

## 1. 공식 공개 API 경로만 사용

- 새 경로 batch04_pose 및 orchestration/batch04_pose_command.py에 구현한다. 지난 저수준 runner의 직접 inner(tensor, augment=False, visualize=False, embed=None) 호출 및 별도 end2end head 수동 초기화/직접 좌표 변환/NMS 코드를 복사해 새 infer 경로로 가져오지 않는다.
- Ultralytics 8.4.192, 기존 격리 환경 .venv-pose-batch03, 공식 yolo26m-pose.pt 체크포인트 하나(49,036,866 bytes, SHA256 2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4)를 **로컬에서 재사용**하고 버전/환경·가중치·manifest/입력 해시 재확인. 공식 모델 카드·고정 태그/라이선스 AGPL-3.0을 유지한다. 추가 다운로드 없이 오프라인 실행한다.
- [공식 YOLO.predict](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/engine/model.py), [공식 predictor](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/engine/predictor.py), [pose result](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/models/yolo/pose/predict.py), [Results keypoints](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/engine/results.py) **이 고정 버전**을 기준으로 구현한다.
- 공식 모델 객체를 **공식 공개 YOLO.predict(source=..., **kwargs)** 로 호출한다. 저장된 원본 입력은 RGB uint8 H×W×3 NPY이므로 연속 BGR numpy 배열(np.ascontiguousarray(rgb[..., ::-1]))로 변환해 source로 전달한다. URL/기본 예시 이미지/웹캠/외부 서비스 전송을 차단한다. bbox/관절의 실제 예측 결과는 model.predict 반환 Results의 boxes.xyxy/conf/cls, keypoints.data(N×17×3)에서 얻는다. N 불일치, NaN, 좌표 이상을 표시한다. **Results 좌표는 이미 원본 크기이므로 다시 scale_boxes/scale_coords 하지 않는다.**
- 설정 의도는 **full-frame / imgsz640 / rect=False / batch1 / conf0.25 / CUDA0 / FP32 / nms=False / max_det300 / no augmentation / no external media / no train/export**. 공식 모델의 public kwargs가 8.4.192에서 허용되는지 전체 검증 후 전달한다. save/show/verbose=False, stream=False. unsupported private kwargs를 우회적으로 전달하지 않는다. 빈 boxes/관절 N=0는 정상 API 출력일 수 있고, 구현 오류와 분리한다.
- **변경된 처리 경로를 기록:** 8.4.192의 공식 predictor는 setup_model에서 fuse=True를 사용하고 최초 입력에서 warmup을 수행한다. 이는 BATCH-0003의 unfused/no-warmup 직접 추론과 동일한 실행 경로가 아니다. 워밍업은 별도 기록, 원본 샘플 예측 개수로 계수하지 않는다. 이전 FP32·전처리/원본 PTS의 취지는 유지하되 실제 input shape/dtype, head/end2end, 공식 preprocess, forward/warmup 횟수, 전처리·추론·후처리/VRAM/시간의 측정 범위를 구분한다. Model 자체를 수정/재학습했다고 주장하지 않는다.

## 2. CPU preflight — GPU 등록 전 필수

1. EXP-0021의 두 예외를 회귀 목록으로 동결한다. **공식 설치 버전 함수 시그니처와 public argument config를 전부 검사**하고, 잘못된 visualize 인자 및 head 누락이 신규 경로에서 발생하지 않음을 테스트한다. 기존에 놓친 API 계약 검사를 반드시 추가한다.
2. CUDA 숨김, **모델 가중치 미로딩·모델 실제 추론 없음**으로 RGB→BGR·연속배열, 원본 native PTS/267 입력 hash parity, 모의 Results → row/keypoints 17개 변환, 정상/사람0명/불일치/NaN/낮은 confidence·unknown/중복 스케일 방지 테스트를 시행한다.
3. 새 코드+계약+실행 허가를 **GPU 실행 전 새 commit/source hash로 고정**, Astra high로 공식 시그니처 및 경로 중심 독립 리뷰를 거친다. 예전처럼 준비 1만 건 해시와 mock 통과만으로 실제 인퍼런스 성공을 추정하지 않는다.

## 3. 먼저 두 개의 실제 원본 프레임 — 기존 단일 GPU 큐

- 기존 Run run_3d23462a014a, 기존 **canonical 단일 GPU 직렬 큐**, free VRAM 최소 6144MiB 게이트, lease/실제 부모·자식·Task/Dispatch·source/input/config hash 검증을 유지한다. Astra max 총괄 1, Sol high 구현/실행 최대 2, Astra high 독립검토 1. 다른 GPU 프로세스 종료/큐 우회/리소스 게이트 낮춤 금지.
- **기술 smoke 2개만 먼저:** E01_030 원본 90초 (030_090), E01_007 원본 64초 (007_064), 각 EXP-0019/0021이 고정한 exact native PTS/RGB. 공식 public API의 실제 Results와 box/17관절, confidence 및 원본 좌표를 검증하고 **원본 + 관절 overlay 로컬 비교 이미지**를 생성한다. 공식 warmup은 원본 2개 카운트에 포함하지 않되 실제 모델 호출/시간을 기록. 두 smoke 성공 출력은 후속 단계에서 재사용하고 재생성하지 않는다.
- 실제 사람이 보이지만 pose가 없거나 손/발 등 필수 관절이 엉뚱한 위치에 있다면 **기술 실행 성공 / 행동 근거 불충분**으로 판단한다. 동일 인물의 관절 일치, 가림·중복·부분몸/배경 오탐·좌우 혼동을 원본과 비교하며, 정확한 사람/관절 GT 없이는 사람 복원이나 정확도 성공을 선언하지 않는다. 사람의 시각적 품질이 불확실하면 두 장을 하나의 로컬 사람 검수 묶음으로 제시하고 자동 확대를 보류한다.
- 2개 실제 결과가 기술적으로 정상이고 유용한 관절 관측 근거가 있으면 **기존 BATCH-0003 입력 267개 중 smoke 2개를 제외한 remaining 265개 한 번만** 실행한다. 새 프레임/추가 가중치/입력 해상도 sweep/사건 위치 사후 crop/설정 튜닝 없음. 원본 10fps 이하·5개 고정 구간/11 diagnostic과 기존 PTS를 유지한다. 성공한 입력은 동일 배치에서 다시 생성하지 않는다.
- 신규 복구 배치에서 **GPU smoke 오류 재시도 최대 1회**, 단 정확한 adapter 오류를 CPU에서 고치고 독립 리뷰/새 freeze 후 새 attempt에만 허용. 원래 실패 기록을 지우지 않으며 같은 종류 반복 오류·추론 외 오류 무시·자동 재실행은 금지. 사람 감지 0은 adapter 오류라고 재시도하지 않는다.

## 4. 그 다음에만 무학습 행동 단서 확인

- 030[88,94), 007[62.5,67.5)는 실제 시도 구간, 007[47.5,52.5), 030[50,55)는 접근-only 비교, 004[60,65)는 줄 넘기/별도 domain으로 취급. **q04는 문을 잡고 발을 올렸으나 구간 내 넘기 완료는 보이지 않았음**. E01_030 약90초 세 인물의 개별 완료 여부 미확정, E01_031 종료 미완료를 이전하지 않음.
- 관절 사람이 실제로 대응하고 사람별 시간 연결과 물리적 fence top/far-side geometry가 충분히 확인된 경우에만 **사전 등록 무학습 규칙 1개**를 시간적 움직임과 함께 평가한다. 기존 camera virtual line을 fence-top으로 승격하지 않는다. 사람 ID 불안정·관절 누락·가림·미교정 경계이면 규칙 미실행/unknown으로 남긴다. PoseC3D 학습/ByteTrack 임의 도입/VLM 통합은 이번 범위가 아니다.
- 선택된 개발 클립만 있으므로 accuracy/precision/recall/F1/시간당 false positive나 다른 카메라 일반화, 법적 침입·개인별 완료를 주장하지 않는다.

## 5. 검토·전달·종료

- EXP-0022 신규 결과 ID와 기존 결과 화면만 활용해 소스/실제 GPU job·출력(또는 실제 차단), 모델/환경/입력 provenance, 2프레임 overlay(실제 있을 때만), 후속 265 성공/미실행, 행동 관찰 여부, 비용·메모리, null 성능 지표, 독립 Astra 보고서·SHA binding을 등록한다.
- **기술 실행 / 사람·관절 시각 품질 / 시간적 행동 판단 / 독립 검토 / 기존 웹·GitHub 전달**을 분리한다. 로컬 127.0.0.1:8765 페이지에서 실제 보고서/지표/이미지·영상이 로드되는지 확인하고, GitHub 원격 commit/blob byte를 별도로 검증한다.
- 공개 가능한 코드·비식별 집계·한계만 GitHub. **원본 CCTV/프레임/관절 raw 좌표·모델 tensor·weights/모델 입력·오버레이/동영상·private runtime DB·queue logs/receipts·실제 로컬 절대 경로는 공개하거나 외부 에이전트에게 전송하지 않는다.** AGPL-3.0 검토와 제3자 참고 코드 무단 복제 금지 유지.
- 사용자 승인 범위 안에서는 작은 단계 재승인을 반복 요청하지 않는다. 단, 새로운 사람별 GT가 꼭 필요한 부분은 실제 로컬 자료를 묶어 **한 번에** 검수받고 검수 미확정은 미확정으로 남긴다. 완료 또는 하드 게이트/재시도 한도 도달 시 결과·미실행 이유를 기록하고 더 자동 실행하지 않는다.

**가장 중요한 산출물은 '실제 사람의 관절이 원본 CCTV에서 제대로 추정되는지 보여주는 두 장의 새 결과'이다.**
