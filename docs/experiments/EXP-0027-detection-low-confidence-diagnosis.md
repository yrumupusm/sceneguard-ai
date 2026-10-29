# EXP-0027 — Detection 낮은 점수 후보 진단

2026-10-29. **기술 실행 완료 / 90초 낮은 점수 출력 확인 / 실제 인물 대응·라벨 의미 검수 미완료 / 기본 적용 보류.** [GitHub 계획](EXP-0027-detection-low-confidence-diagnosis-plan.md)의 두 Detection×기존7프레임을 각각 한 번 실행했다. 90초의 사전학습6행·학습 후1행은 모두0.25 미만이며, 94초는 양쪽 모두0.05에서도0행이다. 이것은 출력 단계의 진단이고 사람 복원 성공이나 학습 효과 확정이 아니다.

## 고정 조건과 실행 이력

GitHub `b79a9eb652187f5b3aad9fcda10b0fd3cd9aaed1`을 깨끗한 main에 fast-forward했다. 실행 소스는 `f8360446b68a8807a4b07a7f8dad1c9b52ec7330`, source digest `6cc2e1f9facccacc9ed4b55f57ccfd3c17b6837068ccdbb48cac1a0470c41e52`, input digest `4653a95ef86e3a15b40a11523b891d8aa017a2642c82f8f02f3f108e7e2f6621`에 고정했다. 기존 Run `run_3d23462a014a`, Sol high Task `task_e36f02bf0722` / Dispatch `ctx_75d3dc7cb54f`, Astra high 독립 검토를 사용했다. 새 canonical job `3eda4fd66f9c4fed9ef98997436362cb`, attempt `111e49f413a4446586e629cd65419721` 한 번이다.

| 항목 | 이번 조건 |
|---|---|
| 모델 | YOLO26m Detection pretrained COCO80 / EXP-0026 best person1 |
| 가중치 SHA256 | pretrained `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`; best `1b120a24c8983507e137304ec3ef814a2415d97c866113df80a6cb61c260dd4f` |
| 실행 환경 | 기존 Ultralytics8.4.192, torch2.5.1+cu124, Python3.10.12, RTX3080 CUDA0 FP32 |
| 입력 | 기존 RGB/crop/native PTS7개; 새 디코딩0; batch1, 실제 tensor1×3×640×640 |
| 유지값 | imgsz640, rectFalse, classes[0], max_det300, iou0.7, nmsFalse, augmentFalse; 전체 kwargs는 manifest |
| 유일 변경 | 공식 predict conf0.25→0.05. 기본 모델·기본 점수 기준 불변 |
| ROI | 030 C6 [537,216,1440,864], 007 C3 [1152,0,1728,648]; 원본 좌표 offset 한 번 |
| 추가 작업 | 새 가중치·학습·추적·VLM·프레임 선택·threshold sweep·웹 기능0 |

원본 tb1/15360, 030의84/90/94/50/55초 PTS1290240/1382400/1443840/768000/844800, 007의47.5/52.5초729600/806400을 유지했다. 평가 manifest SHA는 `d5f55a213f002a335da610cafdd42803fc9b1f96dc205bc47e0de980451187cf`다. 실제 RGB→BGR→공식 전처리와 letterbox/원본 복원 경로를 보존했고 입력 tensor·원시 좌표는 로컬에만 저장했다. 두 모델의 출력 class 수 차이는 학습 전후에 이미 있던 조건이며 이번 threshold 변경에서 새로 만든 차이가 아니다.

## 무엇이 언제 필터되는가

실제 설치 소스 `Detect.postprocess/get_topk_index` → `DetectionPredictor.postprocess` → `non_max_suppression`의 end-to-end 분기 → 원본 crop 좌표 Results 순서를 확인했다. head는 anchor별 최대 class 점수 top-k를 고른 뒤 anchor×class 점수 top-k를 다시 고른다. **person0 선택보다 앞의 상위300 제한**이므로 pretrained80과 fine-tuned1의 class 경쟁을 동일하다고 가정하지 않는다.

후속 end-to-end 분기는 `score > conf`와 class0 mask 후 기존 순서의 첫 max_det개를 반환한다. **엄격 > 비교**이며 이 분기는 IoU 기반 NMS를 실행하지 않는다. iou0.7과 nmsFalse는 기존값으로 유지했다. 모델 head·선행 제한을 통과하지 못한 후보를 이번에 복구하거나 계측하지 않았다. 참고 공식 자료: [Predict](https://docs.ultralytics.com/modes/predict/), [Detection head](https://docs.ultralytics.com/reference/nn/modules/head/). 온라인 문서는 최신 버전으로 바뀔 수 있어 이번 실제 판정은 보존된8.4.192 설치 소스·SHA와 합성 테스트를 기준으로 한다.

따라서0.05 Results도 최종 출력이다. **0행은 내부 모든 위치/후보에서 사람 반응이 없었다는 증명이 아니다.** 이전 EXP-0026은 최종0.25 Results만 저장했으므로 캐시 재필터만으로 낮은 점수를 복구할 수 없었고, 이번14회가 실제 새 추론이다.

## 14조건의 점수 구간과 기존 캐시 대조

아래 수치는 **기계가 반환한 박스 행 수**이며 실제 사람 수·TP·recall·정확도가 아니다. 설치 필터가 >0.05이므로 첫 구간의 정확한0.05 경계는 실제 출력에 포함되지 않는다. 표의 구간 정의는 사전 계획대로 유지했다.

| 프레임 | 모델 | [0.05,0.10) | [0.10,0.25) | [0.25,1] | 전체 | 최대 점수 | ≥0.25 vs 기존0.25 |
|---|---|---:|---:|---:|---:|---:|---|
| 030_084 | 사전학습 | 0 | 2 | 3 | 5 | 0.866473 | 정확 일치 |
| 030_084 | 학습 후 best | 1 | 2 | 1 | 4 | 0.317847 | 정확 일치 |
| 030_090 | 사전학습 | 3 | 3 | 0 | 6 | 0.176766 | 정확 일치 |
| 030_090 | 학습 후 best | 0 | 1 | 0 | 1 | 0.108089 | 정확 일치 |
| 030_094 | 사전학습 | 0 | 0 | 0 | 0 | 없음 | 정확 일치 |
| 030_094 | 학습 후 best | 0 | 0 | 0 | 0 | 없음 | 정확 일치 |
| 030_050 | 사전학습 | 0 | 1 | 1 | 2 | 0.790312 | 정확 일치 |
| 030_050 | 학습 후 best | 0 | 2 | 0 | 2 | 0.122157 | 정확 일치 |
| 030_055 | 사전학습 | 0 | 0 | 2 | 2 | 0.914042 | 정확 일치 |
| 030_055 | 학습 후 best | 0 | 1 | 1 | 2 | 0.252819 | 정확 일치 |
| 007_047p5 | 사전학습 | 0 | 0 | 0 | 0 | 없음 | 정확 일치 |
| 007_047p5 | 학습 후 best | 0 | 0 | 0 | 0 | 없음 | 정확 일치 |
| 007_052p5 | 사전학습 | 0 | 0 | 2 | 2 | 0.920202 | 정확 일치 |
| 007_052p5 | 학습 후 best | 0 | 0 | 2 | 2 | 0.749543 | 정확 일치 |

14조건 모두 새 결과의 `>=0.25` 부분이 과거0.25 캐시와 **박스 좌표·점수·class·행 순서까지 정확히 일치**했다. 점수 정확히0.25인 행은0개여서 strict `>0.25` 대조의 경계 차이는 이번 실측에서 없었다. 최대 좌표/점수 차이0, 사전 허용오차0.001pixel/0.000001 기준도14/14 통과했다. 행을 재정렬하거나 가까운 박스로 대응해 일치시킨 것이 아니다. 원시 Results14개와 기존summary를 CPU에서 재대조했다.

## 해석과 아직 답하지 못한 질문

- **030:90:** 사전학습 최대0.176766, 학습 후 최대0.108089의 person 출력이 있다. 이 행들은0.25 필터에서 제외되는 범위였음을 확인했다. 다만6행이 실제3명을 적절히 감싼 것인지, 부분 신체·중복·배경인지 미검수다. ‘90초 실제 사람 누락이 전부 최종 threshold 탓’이라고 단정하지 않는다.
- **030:94:** 두 모델 모두0.05에서도0행이다. 기존 사용자 관찰의 문 위1명·이미 넘어간1명에 대한 검출 근거를 이 진단 범위에서 얻지 못했다. 원인이0.05 미만 점수인지 head 상위 제한 등 이전 단계인지 현재 자료로 분리하지 못했다.
- **030:84:** 사전학습3→5행, 학습 후1→4행이다. 기존 관찰의3명과 대응하거나 늘어난 행의 중복을 판정하지 않았다. 낮은 점수까지 포함해 개수가 늘었다는 이유로 성능 향상을 주장하지 않는다.
- **접근 대조:** 030:50은1→2/0→2, 030:55는2→2/1→2, 007:47.5는0→0/0→0, 007:52.5는2→2/2→2다(pretrained/best). 실제 사람·배경·중복/부분 박스 여부는 별도 검수 대상이다. 0행을 사람 부재나 정상 행동 판별 성공으로 세지 않는다.

같은7개 개발 프레임의 진단이며 독립 카메라 검증이 아니다. bbox 정답·실제 사람 대응이 충분하지 않아 정확도/F1/mAP/recall/행동 성능을 산출하지 않았다. EXP-0004 FCOS의 결과나 기존 Pose640/960 실험을 이번 Detection의 증거로 대체하지 않는다. 학습 데이터 라벨/도메인 차이와 클래스 경쟁 변화는 원인 가설로 남으며 이번 결과만으로 인과를 확정하지 않는다.

## 라벨 감사와 사람 검수 상태

[별도 CPU 감사](../data/EXP-0027-label-audit.md)에서 원본 ZIP과 준비 파일1,108개, 원본601주석행의 변환 출처, split210/20/17, 기존113PNG를 검증했다. people-jump-fence8행/3패널과 person polygon19행/12패널의 교집합은0이며 우선 합집합은 **27행/15패널**이다. 27명이나27오류라는 뜻이 아니다.

전체113패널과354사람행은 **review_pending, 완료0**이다. 개인/복수/장면, 전신/부분/울타리 포함, 미라벨 인물, C6구도 유사성, 외접 bbox 적합성은 모두 미확정이다. 감사 의견은 `format/provenance verified; semantics pending`이며 사람이 검수한 의견과 구분한다. D0false와 준비 당시 metadata·원본 라벨을 보존했다. test17 목록/바이트 감사는 모델 test 평가가 아니다.

사용자에게 새7장 비교의 핵심 대응 항목을 한 번에 요청했다. **이 보고서 작성 시 답변 미수신**이며 새 이미지 의미를 Codex나 독립 검토자가 확정하지 않았다. 미디어는 외부 에이전트/API에 전송하지 않았다. 기존84/90/94초 사용자 관찰은 원본 장면에 관한 근거로만 재사용하고 새 출력의 정답으로 확장하지 않는다.

## 실행 비용·오류·보존

| 항목 | 실측 |
|---|---:|
| 실제 sample 호출 / 반환 / forward | 14 / 14 / 14 |
| 공식 warmup forward | 2, 각 모델 최초1회; sample과 별도 |
| 모델 로딩 pretrained / best | 0.076825 / 0.030220초 |
| 7장 predict·저장·캐시 대조 단계 pretrained / best | 1.407521 / 0.864704초 |
| runner 전체 | 27.240360초 |
| PyTorch peak allocated / reserved | 191.832 / 212.000MiB |
| 전체 장치 표본 최대 사용 / 최소 여유 | 1943 / 8111MiB, 105회 표본 |
| 실행 직전 여유 | 8622MiB; gate≥6144MiB |
| 실행 오류 / OOM / 재시도 | 0 / 0 / 0 |

단계 시간은 최초 setup/fuse/warmup, tensor 계측, 동기화, CPU Results 저장과 과거 캐시 대조를 포함한다. runner전체는 무결성 해시·import·그림 생성·종료 재검증도 포함한다. 모델 로딩은 공식 YOLO 객체 생성 구간이며 CUDA 준비 전체가 아니다. 장치 표본은 다른 프로세스도 포함하고 allocator peak와 별개다. 이번 시간은 계측이 추가돼 EXP-0026 속도나 연속 영상 FPS와 직접 비교하지 않는다.

CPU39개(EXP27계약15+기존큐14+EXP26회귀10), 라벨 감사13개 테스트 통과. 합성 결과의 경계값·empty/비정상 Nx6·유한 좌표·class/offset·kwargs 한축 차이·설치 top-k/strict필터·입력/가중치/환경 해시·lease/authorization·덮어쓰기/재시도 거부·기존큐 보존을 검증했다. 초기 테스트 기대값의 device0 대 cuda:0 오류와 합성 head의 보조함수 바인딩 누락을 CPU 단계에서 수정했으며 GPU 실패/재시도와 혼동하지 않는다.

기존43jobs/43attempts의 모든 행을 그대로 보존하고 새1job/1attempt만 추가해44/44가 됐다. 원본/준비 라벨·이미지·환경·가중치·이전 결과·보고서/검토 결속은 유지한다. 새 코드·집계만 공개하며 로컬 media/raw좌표/cache/weights/runtime는 Git에서 제외한다.

## 로컬 결과와 재현 경로

로컬 결과 루트: `outputs/exp0027/EXP-0027/diagnose/111e49f413a4446586e629cd65419721/`. summary SHA256 `68d3bc88789fdfb17c2669a6951e353128c89dca73d753f7254bf7916e5c548b`. 각 프레임의 `*-triptych.png`는 **원본 / pretrained low-score / fine-tuned low-score**다. 원본 전체1920×1080과 각 모델의 모든 행을 보존했으며, 주황[.05,.10), 노랑[.10,.25), 초록[.25,1]·행번호·점수를 표시한다. 총7장5760×1140; 더 크게 볼 수 있는 개별 원본/모델 패널21장과 원시 순위/점수 자료도 로컬에 있다. 표시를 위해 박스를 삭제하지 않았다. bbox는 관절·발 위치·행동 판정이 아니다.

```bash
# CPU 회귀 검사: 새 모델/추론 없이 실행
CUDA_VISIBLE_DEVICES='' .venv-pose-batch03/bin/python -m unittest tests_orca.test_exp27_detect tests_orca.test_queue tests_orca.test_batch07_detect -v
python3 -m unittest discover -s tests_data -p 'test_exp0027_labels.py' -v
# 실행 당시 native 담당·검토 source/input/commit·authorization·canonical lease 필요
.venv-pose-batch03/bin/python -m exp27_detect.cli enqueue
.venv-pose-batch03/bin/python -m exp27_detect.cli run-once
.venv-pose-batch03/bin/python -m exp27_detect.cli status
```

이 명령은 실제 사용한 경로의 기록이며 완료 후 재실행 지시가 아니다. 같은 job/출력 덮어쓰기와 retry는 거부한다. source commit은 실행 시점의 것으로 보존하며 결과 문서 커밋 이후 현재 HEAD에 맞춰 실행 권한을 자동 갱신하지 않는다. [공개 측정값](../../records/EXP-0027/metrics.json), [독립 검토](../reviews/EXP-0027-independent-review.md), [전달 확인](EXP-0027-delivery.md)을 별도로 확인한다. 웹 등록 자체와 실제 브라우저 렌더·GitHub 원격 게시 확인은 서로 다른 검증이다.

## 결정과 다음 한 가지

**두 모델 모두 기본 적용 보류**다. 90초 낮은 점수 출력의 존재를 확인했지만 실제 사람 복원은 미확정이고,94초는 두 모델 모두 검출 근거가 없다. 단순 임계값 하향을 채택하지 않는다. 다음 한 가지는 **새 낮은 점수 박스와 우선15개 학습 라벨 패널의 실제 사람·신체 범위 대응을 사람 검수로 확인하는 것**이다. 그 결과 전에는 라벨 문제나 threshold 문제 하나로 원인을 확정하지 않는다. 이번14회 한도를 마쳤으며 추가 학습·threshold sweep·해상도/ROI·모델·추적·행동 실험은 예약하거나 실행하지 않는다.
