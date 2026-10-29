# EXP-0021 — YOLO26m-Pose native PTS 관절 진단

2026-10-29 KST. 상태: **267개 입력·환경·코드 고정 준비, GPU 실행 전 총괄·독립 검토 대기.** 결과 수치·행동 개선은 아직 미측정이다.

승인/설계는 [BATCH-0003](BATCH-0003-yolo26-pose-plan.md), [실행 계약](BATCH-0003-execution-contract.md), [ADR-0020](../decisions/ADR-0020-yolo26m-pose.md)를 따른다. 독립 설치·checkpoint1개와 CPU 검사만 완료했다. 모델 구성/추론은 canonical queue에서 smoke2개→성공 시 remaining265개이며 성공한 프레임은 재생성하지 않는다.

입력은 기존 EXP-0019 native11과 climb030[88,94), climb007[62.5,67.5), approach007[47.5,52.5), approach030[50,55), rope004[60,65)의 원본10fps(60/50/50/50/50개)다. 중복 제거 총267개, smoke는030_090/007_064다. 원본/PTS/RGB 해시·환경/가중치·전처리를 `configs/batch0003_pose_manifest.json`에 고정한다. full-frame640 square, batch1 FP32, conf>0.25, retained joint confidence>=0.5, NMS-free end2end 하나다.

사용자 구간 관찰을 관절/사람별 GT로 확대하지 않는다. q/v 개발 자료에서 accuracy/precision/recall/F1/FPR/일반화/완료율은 산출하지 않는다. 출력 row는 사람 ID가 아니고 retained joint는 실제 일치가 확인된 관절이 아니다. 경계 geometry·사람/관절 correspondence가 검증되지 않으면 rule을 실행하지 않는다.

재현 준비: `.venv-pose-batch03/bin/python -m batch03_pose.prepare`, CPU import/source parity, `.venv-pose-batch03/bin/python -m batch03_pose.freeze`. 실행은 총괄의 source commit·authorization 및 Astra 검토 뒤 `.venv-pose-batch03/bin/python -m batch03_pose.cli enqueue --stage smoke`와 `run-once`, 기술 통과 후 remaining 동일 절차다. `batch03_pose.report`는 저장 결과만으로 공개 비식별 집계/metrics와 로컬 원본·pose 비교 자료를 반복 생성한다.

기술 실행, 실제 사람/관절 품질, 행동 구분, 독립 리뷰, 웹/GitHub 전달은 각각 별도 판정한다. 원본·좌표·이미지·영상·가중치·raw arrays·runtime/log/receipt는 로컬 전용이다. 완료 등록과 실제 웹/영상 playback·seek, GitHub 원격 byte 확인은 총괄 담당이며 본 준비 완료로 대체하지 않는다.
