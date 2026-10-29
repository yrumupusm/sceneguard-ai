# ADR-0020 — YOLO26m-Pose의 제한된 무학습 관절 진단

2026-10-29 KST. 상태: **공식 출처·격리 설치·CPU 계약 확인 후 두 smoke가 adapter 오류로 실패, retry 한도 종료·기본 적용 보류.** BATCH-0003 한도에서 EXP-0021만 추가하고 기존 CV/VLM·환경·결과는 바꾸지 않는다.

이전 FCOS/RF-DETR 박스와 Qwen 답변만으로 접근과 문 올라타기의 사람별 동작이 충분히 관측된다고 확정할 수 없었다. 사용자가 승인한 COCO17 관절 한 모델은 손목·엉덩이·무릎·발목의 관측 가능성을 확인하기 위한 진단이다. COCO AP나 bbox 수는 이 CCTV의 복원·행동 정확도가 아니다. 다른 YOLO 크기·학습형 행동모델·추적기·VLM 재실행은 이번 비교 대안으로 실행하지 않는다.

공식 실시간 PyPI와 GitHub API는 안정판 `ultralytics 8.4.192`, tag `v8.4.192`, commit `922563eab42b778445e55a2edbabb6974eed8e4b`를 반환했다. release 게시 시각은 2026-10-28 23:46:20 UTC다. 브라우저 검색 캐시의 8.4.191은 현재값으로 채택하지 않았다. PyPI 요구사항 Python>=3.8, Torch>=1.8/Torchvision>=0.9와 로컬 Python3.10.12·Torch2.5.1+cu124·Torchvision0.20.1+cu124가 맞는다. 격리 `.venv-pose-batch03`에서 pip check, CPU import, CUDA 미초기화, 공식 tag의 predictor/pose/results/ops/NMS/default/AutoBackend byte parity를 확인했다. CUDA 실제 동작은 queue smoke 전 미검증이다.

유일한 공식 체크포인트는 [Ultralytics assets v8.4.0 yolo26m-pose.pt](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26m-pose.pt)다. GitHub 공식 asset API의 49,036,866 bytes와 SHA256 `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4`에 다운로드 전체 byte가 일치했다. 다른 모델을 다운로드하지 않았다. 환경 파일 전체 해시·lock·원본 SHA·정확한 native PTS/RGB bytes를 manifest와 로컬 파일 인덱스로 고정한다.

기준은 full frame/batch1/640 square/FP32/conf>0.25, `rect=False`, centered LetterBox114/scaleup=True/stride32, end2end=True/max_det300/NMS=False, iou0.7(이 경로에서 억제에 사용하지 않음)/agnostic=False/augment=False다. 공식 checkpoint의 one-to-one end-to-end 출력을 쓰며 별도 NMS를 추가하지 않는다. 공식 LetterBox와 NMS-free confidence/class filter, scale_boxes/scale_coords를 직접 호출한다. `YOLO(local_weight)` 뒤 unfused PyTorch eager forward 한 번만 사용하며 predictor stream·AutoBackend·warmup·AMP autocheck·모델 info/FLOP probe·training/export·compile을 실행하지 않는다. 실제 tensor(1,3,640,640)와 원본/입력 좌표·confidence·raw output indices를 로컬 보존한다. 이 명시적 unfused 경로는 기본 high-level predict의 자동 최적화와 구별한다.

COCO 순서는 nose, left/right eye, left/right ear, left/right shoulder, left/right elbow, left/right wrist, left/right hip, left/right knee, left/right ankle다. confidence>=0.5이며 유한·원본 범위 내·(0,0)이 아닌 좌표만 `retained_estimate`로 표시한다. 나머지는 unknown이며 원시 confidence/좌표는 따로 보존한다. 이는 실제 가시성·정확성 GT가 아니다. row/index는 사람 ID가 아니고 사람 간 관절의 시간 연결·보간을 하지 않는다.

기존 EXP-0019 exact11과 사전 고정 다섯 창에서 원본 native PTS를 0.1초 이상 간격으로 순차 선택해 260개 window sample, 중복 제거 후 총267개 고유 입력을 고정했다. 030_090/007_064의 smoke2개 성공은 본 결과로 재사용하고 remaining265개만 한 번 실행한다. canonical queue의 상속 lock/실제 parent-child identity/RunTaskDispatch/source-input-config hash와 load 전 free6144MiB gate를 그대로 쓴다. 오류 retry 최대1이고 forward-start marker가 생긴 attempt는 부분 성공 재생성을 막기 위해 재시도하지 않는다. 실패·불충분한 관절·미검증 경계면 다른 모델/임계값/규칙으로 대체하지 않고 종료한다.

공식 [라이선스](https://github.com/ultralytics/ultralytics/blob/v8.4.192/LICENSE)는 AGPL-3.0이고 [Ultralytics licensing](https://www.ultralytics.com/license)은 AGPL/Enterprise 조건을 설명한다. 이번은 로컬 연구·기술 평가로 한정한다. 새 `batch03_pose`와 adapter/tests의 공개 소스에는 `SPDX-License-Identifier: AGPL-3.0-only`를 명시해 해당 공개 코드와 수정의 corresponding source를 같은 저장소에서 제공한다. 이는 과거 프로젝트 전체를 소급 재라이선스하는 선언이 아니다. 미수정 upstream은 정확한 tag/commit·license·package lock으로 출처를 연결하고 vendoring하지 않는다. 상용 통합·네트워크 서비스 배포와 저장소 전체의 결합 라이선스는 별도 검토 전 확대하지 않는다. 원본·사람 좌표·미디어·weights·runtime은 공개하지 않는다. 무라이선스 제3자 fence 예제 구현은 읽어 복제하거나 벤더링하지 않았고 규칙 코드도 추가하지 않았다.

기존 C3/C6 crossing line은 fence-top/far-side 해석이 검증되지 않았다. 관절·사람 대응 및 동일 인물의 시간적 관측과 실제 경계 geometry가 모두 검증되지 않으면 규칙을 건너뛴다. 이번 가설을 뒤집는 근거는 기술 출력 성공이 아닌 로컬 사람/관절 검수와 시간 단서의 충분성이다. 정확도/F1/FPR/완료율은 null로 둔다.

공식 근거: [PyPI8.4.192](https://pypi.org/project/ultralytics/8.4.192/), [release](https://github.com/ultralytics/ultralytics/releases/tag/v8.4.192), [pose](https://docs.ultralytics.com/tasks/pose), [YOLO26](https://docs.ultralytics.com/models/yolo26), [predict 설정](https://docs.ultralytics.com/modes/predict), [고정 source](https://github.com/ultralytics/ultralytics/tree/922563eab42b778445e55a2edbabb6974eed8e4b).

## 첫 smoke 실패와 단 한 번의 초기화 수정 검토

첫 source commit `b52ac221a2e43924f86efd8fbd32a0df4973ceec`의 실제 queue smoke는 official architecture/end2end guard에서 실패했다. 체크포인트 구성/로드는 실행됐지만 forward0, 입력 프레임 추론0, warmup0이며 자원 gate7172MiB는 통과했다. 실패 원문과 원래 queue/source binding은 불변으로 보존한다.

로컬 ZIP/pickletools opcode와 FloatStorage 검사만으로 checkpoint의 kpt_shape17x3, person0, stride8/16/32, legacy end2end=True와 `_end2end` 직렬화 부재를 확인했다. 모델을 CPU에서 구성하거나 unpickle하지 않았다. 설치된 공식 getter는 `_end2end`가 없으면 unfused dual-head에서 False를 반환한다. 첫 실패 summary에는 실제 조건별 attribute가 없어 정확히 어느 항이 실패했는지는 런타임 관측으로 확정하지 않았다. 공식 [PyTorch backend lines57–58](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/nn/backends/pytorch.py#L57)은 `nms=False`에서 받은 override를 `model.end2end=True` setter로 적용하며 [predictor](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/engine/predictor.py#L475)도 이 선택을 명시한다.

후속 수정은 이미 사전 등록한 end2end=True를 공식 setter로 초기화하고 max_det300/agnostic=False를 명시하며, assertion 이전에 전체 architecture_pre/post를 기록하는 최소 보완이다. 모델/가중치/환경/manifest/입력/threshold/FP32/rect/비융합 조건은 동일하다. 별도 고정 `batch0003-exp0021-pose-smoke-retry1` key (stage smoke 동일) 하나는 첫 실패 SHA와 zero-forward/원래 queue row를 검증해야 하고, 원래 실패 job의 source/code hash를 변경하지 않는다. 이 correction은 논리적 smoke의 유일한 retry이며 correction job을 재시도하거나 원래 job을 되살리는 경로를 거부한다. 수정 source를 커밋하고 총괄·독립 검토 후 재승인된 queue 실행만 가능하다. 이후 기술 통과 시 remaining265개를 처음 한 번 실행한다.

## 배치 종료 시 실제 결과

최초 smoke의 architecture guard 뒤 유일한 correction도 `BaseModel.predict`의 미지원 `visualize` 인자로 실패했다. 두 모델 load가 수행됐고 성공 예측/pose 결과는0이며 remaining265는 enqueue하지 않았다. correction의 실제 pre/post 기록은 end2endFalse→True, person0/17x3/stride32를 확인했지만 최초 로그에 없는 조건별 값을 소급 생성하지 않는다. `embed`는 현재 signature에서 지원되고 `visualize`만 미지원이다. 이는 adapter/preflight 누락이며 YOLO 사람/관절 성능 실패가 아니다. 관절·행동 품질, FPS와 full-process peak는 미측정이고 규칙/추적은 건너뛴다. 단1회 retry를 소진했으므로 이번 배치에서 세 번째 GPU 시도나 다른 모델/가중치/설정을 실행하지 않는다. [EXP-0021 실제 실패 보고서](../experiments/EXP-0021-yolo26m-pose.md)와 비용/원문 hash를 따른다.
