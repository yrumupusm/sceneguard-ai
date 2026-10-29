# EXP-0026 — 미검수 사람 박스의 첫 탐색적 학습

2026-10-29. 사용자의 최신 **“학습 시작해볼래?”**에 따른 신규 실행 범위다. 앞선 준비 사본의 `training_approved:false`는 생성 당시의 기록으로 보존한다. 지금의 학습 승인은 라벨 의미 검수나 Gate D0 통과를 뜻하지 않는다. [초기 계획](BATCH-0007-roboflow-person-finetune-plan.md)의 시각 검수 선행 제한을 이번 탐색 실행에 한해서 대체한다.

## 목적과 종료 기준

미검수 라벨로도 학습 경로가 실제 작동하는지, 월장 자세의 사람 박스에 비교할 가치가 있는 변화가 생기는지 확인한다. Detection 학습 전 기준 → 단일 설정 학습 → 동일 CCTV 표본 예측 → 독립 검토 → 기존 결과 화면 등록/GitHub 확인까지 수행한다. 학습 실행 성공과 실제 사람 검출 개선은 구분한다. 행동·관절·법적 무단침입 판단은 평가하지 않는다.

새 설정은 하나이며 결과를 보고 튜닝하지 않는다. 최대 20 epoch, 큐 실행 시간 상한 3,600초, 오류 수정 재시도 최대 1회다. 오류 시 자동 설정 축소·다른 모델·큐 밖 실행은 없다. 기존 모델·기본 설정은 유지한다.

## 고정 데이터

[준비 기록](../data/CLIMBING_FENCE_PREPARATION.md)의 `data/climbing_fence/person_bbox_draft_v1` 사본을 사용한다. 247장 중 train210/valid20, test17은 이번에 사용하지 않는다. 원본 ZIP, 원본/변환 라벨 및 준비 manifest는 변경하지 않는다. 캐시·학습 YAML 등은 별도의 로컬 실행 사본에 둔다.

사람 bbox335행 유지, 사람 polygon19행 외접 박스 변환, 울타리247행 제외라는 **형식 변환만 검증**됐다. 복수 사람/부분 신체/누락 라벨의 의미, 촬영 그룹 독립성은 미확정이다. 각 라벨 하나를 임시 person 박스 하나로 취급한다. 사용자 검수는 나중에 진행하며 학습을 멈추기 위한 추가 질문을 반복하지 않는다. CCTV 평가 프레임은 학습에 포함하지 않는다.

기존 train은 원본70개 후보의 증강본210장이다. 추가 온라인 증강은 끈다. 일반 보행자 자료의 혼합은 이번에 하지 않았으며 일반 사람 검출 저하 위험이 남는다. valid20에 대한 수치는 **미검수 제공 라벨과의 일치 진단**이며 독립 CCTV 정확도가 아니다.

## 사전 고정 설정

| 항목 | 설정/이유 |
|---|---|
| 모델 | COCO 사전학습 **YOLO26m Detection**, 공식 `yolo26m.pt` 한 개. Pose 체크포인트 사용 안 함 |
| 환경 | 기존 `.venv-pose-batch03`, Ultralytics8.4.192 / torch2.5.1+cu124, 변경 없이 사용 |
| API | 공식 `YOLO.predict()` / `YOLO.train()` |
| 입력/배치 | 640 / batch2 / CUDA0 / workers0 |
| 길이 | 20 epoch, patience0, resumeFalse |
| 정밀도 | FP32, ampFalse. AMP 검사에 따른 별도 모델 다운로드도 피함 |
| 학습 | AdamW, lr0=0.0001, lrf=0.1, weight_decay=0.0005, warmup_epochs=1, warmup_bias_lr=0, nbs64(명목 gradient accumulation32) |
| 동결 | freeze10. 작은 데이터에서 앞단 특징 변화를 제한하는 첫 설정이며 최적값 아님 |
| 재현 | seed0, deterministicTrue; 실제 유효 인수·패키지·가중치 해시 보존 |
| 추가 증강 | HSV/회전/이동/scale/shear/perspective/flip/mosaic/mixup/cutmix/copy_paste/bgr=0, augmentations=[] |
| checkpoint | 고정 valid fitness로 선택한 best 및 last를 로컬 보존; CCTV 결과로 epoch 선택 안 함 |
| 예측 | person0, conf0.25, imgsz640, rectFalse, halfFalse, iou0.7, max_det300, nmsFalse |
| 자원 | 기존 단일 GPU 큐, 시작 전 free VRAM≥6144MiB, 실제 lease/부모·자식/source/input/commit 검증 |

공식 pretrained 파일은 [Ultralytics assets v8.4.0](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26m.pt)의 `yolo26m.pt`, 44,255,705bytes다. release API digest와 로컬 SHA256 `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`를 대조한다. 이전 Pose 파일은 그대로 보존한다.

Detection 중간 크기는 기존 YOLO26 계열/설치 환경을 재사용하면서 소규모 batch로 비용을 제한하기 위한 선택이다. 10GB에서의 성공을 크기만으로 보장하지 않는다. 기준 모델은 COCO80 클래스에서 person0을 선택하고 학습 모델은 person1클래스다. 설치 버전의 공식 cls_remap=True는 이름이 같은 person 클래스 행의 전이를 시도한다. 실제 전이 로그와 호환되지 않는 텐서를 기록하며 무조건 head 전체/일부가 무작위 초기화됐다고 단정하지 않는다. 출력 클래스 구조가80→1로 달라져 완전히 동일한 출력 head 비교라고 하지 않는다. 기준 예측에서 fuse된 인스턴스를 학습에 재사용하지 않고 원래 pretrained 파일을 새로 로드한다.

실제 설치 코드에서 optimizer/gradient accumulation/validation precision 등 API 내부 동작을 추가 확인해 결과에 기록한다. 요청한 FP32와 실제 validator 정밀도가 다르면 숨기지 않는다. 학습 전 기준과 학습 후 CCTV 예측은 같은 정밀도·입력으로 맞춘다.

첫 GPU 실행 전 Astra 검토에서 설치 trainer의 기본 bias warmup0.1, 선택적 Albumentations 증강, OOM/NaN 자동 복구 경로를 발견했다. 위 warmup_bias_lr0·augmentations[]를 명시해 의도하지 않은 설정을 막는다. 기존 학습 알고리즘은 바꾸지 않고 자동 복구 경고 시 실행을 실패로 종료하는 검사와 합성 테스트를 추가한다. validation 배치는 설치 API의 train batch×2=4이며 checkpoint 저장 정밀도와 실제 계산 정밀도는 별도로 보고한다.

## 고정 평가 표본

| 자료 | 원본 시각 | 입력 | 역할 |
|---|---|---|---|
| E01_030 | 84/90/94초 | 기존 C6 ROI x537:1440,y216:864 | 기존 누락 장면 개발 진단3장 |
| E01_030 | 50/55초 | 동일 C6 | 접근 장면 사람 검출 유지 확인2장 |
| E01_007 | 47.5/52.5초 | 기존 해당 카메라 ROI | 일반 접근 확인2장 |

원본 PTS/timebase/RGB/ROI 해시를 실행 전에 고정한다. 모델 출력이나 정답 인물 위치에 따라 crop을 변경하지 않는다. 같은 카메라의 프레임을 독립 사례 수로 세지 않는다. 사람별 bbox 정답이 없어 CCTV precision/recall/mAP/F1은 산출하지 않는다. 출력 개수와 점수·전후 로컬 비교 이미지를 제공하고 새 박스의 실제 대응은 미검수로 남긴다.

## 전달과 보존

기존 Run `run_3d23462a014a`, 총괄1·Sol high 구현/입력 담당·Astra high 독립 검토를 사용한다. 새 큐/웹 기능을 만들지 않는다. 보고서에는 epoch 완료 수, 학습·예측 시간, peak GPU 메모리, 오류/OOM, 미검수 라벨 진단 수치, CCTV 전후 출력과 불확실성을 분리한다. 보고서·측정값·검토·비교 이미지를 기존 완료 등록 절차로 연결한다. 코드·문서·공개 집계만 커밋한다. 원본/라벨/이미지/weights/checkpoint/원시 결과/로그/runtime DB는 로컬에만 보관한다.

## 공식 근거

- [YOLO26 모델·공식 Detection API](https://docs.ultralytics.com/models/yolo26/)
- [공식 fine-tuning 안내: pretrained 전이와 클래스 수 변경](https://docs.ultralytics.com/guides/finetuning-guide/)
- [공식 train 설정](https://docs.ultralytics.com/modes/train/)
- [Ultralytics 라이선스](https://www.ultralytics.com/license): AGPL-3.0 코드의 공개 실험 범위. 별도 유료 라이선스/서비스 구매 없음.
- [Climbing Fence v1](https://universe.roboflow.com/osborne-rowland-r4w5m/climbing-fence/dataset/1): 배포 메타데이터 CC BY4.0, 원 이미지별 권리/의미 감사 미완료. 가중치·데이터 재배포 없음.
