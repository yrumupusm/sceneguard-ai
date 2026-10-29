# EXP-0023 — YOLO26m-Pose 전체화면 / 기존 C6 고정 ROI 비교

2026-10-29, Sol high 실행 담당. BATCH-0005의 별도 실험이며 [승인 계획](BATCH-0005-c6-pose-roi-comparison-plan.md), [ADR-0022](../decisions/ADR-0022-c6-pose-roi.md)를 따른다. **신규 public YOLO.predict 5회가 모두 정상 반환했고 기존 90초 전체화면 Results 1개를 재사용했다. 90초는 full0행 대비 ROI1행/관절 추정12개이며, 실제 관심 사람·관절의 복원 여부는 사용자 이미지 검수 전 미확정이다.** 오류0/retry0이며 더 GPU 작업은 실행하지 않는다.

## 가설·데이터·평가 단위

기존 EXP-0022에서 030:90 full은 정상 0행이었다. 고정 배경 ROI에서 입력상 사람 크기가 커지면 관절 근거를 얻을 수 있다는 가설만 비교한다. 같은 640에서도 원본 공간 범위·resize/letterbox가 달라지므로 이를 분리한 비교는 아니다. 같은 원본의 기존 exact native PTS 84/90/94초 RGB 세 장을 재사용했다. native PTS는 각각1290240/1382400/1443840, time base1/15360이다. source SHA256 `2a8006450e18c1d6fe8b5022302cc7d75066ebbe356c6aab453147c5c4f48f88`, RGB/file/crop 해시는 manifest에 고정했다. 재추출·인접 frame 대체·라벨 변경은 없다.

개발용 같은 장면 세 시점이며 독립 카메라/최종 행동 평가가 아니다. 90초 사람·문 올라탐은 기존 사용자 관찰이고, 84/94 각 사람의 동작·완료를 새로 확정하지 않는다. 사람별 정밀 bbox/keypoint GT가 없다. accuracy/precision/recall/F1/FPR·완료/위법성은 null이다. 031의 종료 관찰을030에 전이하지 않는다.

## 환경·고정 입력·좌표 계약

기존 Python3.10.12/Torch2.5.1+cu124/Torchvision0.20.1+cu124/Ultralytics8.4.192·RTX3080·공식 YOLO26m-Pose를 재사용했다. 체크포인트49,036,866bytes, SHA256 `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4`. 새 환경/weight 다운로드/학습/VLM은0이다. AGPL-3.0 로컬 연구 조건과 기존 ADR-0020/0021의 출처를 유지한다.

기존 C6 [0.28,0.20,0.75,0.80] → floor/ceil x537:1440,y216:864, RGB[216:864,537:1440],903×648. 사람/출력으로 ROI를 선택하지 않았다. camera config SHA256 `d37fbc699a84fae72ae236f4ae40e01bfb8d58b2fbe3b746eba0e6fb55624f18`. 원본 RGB→연속 BGR 변환·공식 public kwargs 전체·observer는 batch04의 검증된 코드를 읽기 전용으로 재사용했다. imgsz640/rectFalse/batch1/conf.25/deviceCUDA0/quantizeNone(FP32)/nmsFalse/max_det300/iou.7/classes[0]/agnosticFalse/augmentFalse/compileFalse/channels_lastFalse/save·save_txt·save_crop·show·verbose·stream·visualizeFalse/embedNone이다.

공식 ROI Results 좌표는 crop-local이다. 기존 result_rows로 crop bounds/confidence/(0,0) unknown을 **먼저** 판단하고 원본 표현에는 (+537,+216)을 **한 번만** 적용했다. local/raw 좌표·unknown status를 따로 보존하며 sentinel을 이동한 뒤 retained 여부를 다시 판단하지 않는다. full은 무변환이다. 관절 confidence≥0.5는 기록 기준이며 정답이 아니다. 모든 실제 입력 tensor는 CUDA0/FP32/(1,3,640,640), backend는pt/end2endTrue/fp16False/kpt_shape17×3/stride32/fusedTrue/done_warmupTrue다.

## CPU 검증·실제 실행·보존

CPU에서 CUDA를 숨기고 모델/가중치를 로드하지 않은 채 새9개+기존queue14개, 총23개 테스트를 통과했다. crop 픽셀·색상·원본 불변·offset 한 번·unknown/empty/malformed/nonfinite/boundary·exact PTS·cached hash·새5개 disjoint·설치된 official config/signatures·lease·free6144 gate·큐 additive migration/과거 row 보존을 검사했다. 독립 Astra 사전 PASS 후 총괄이 exact source commit `62fe072bdd70f4e3eeb8c51a4984b96f221fea41`과 모든 source byte를 검증해 실행을 명시 승인했다.

source digest `c6de4151fe1c836a8c607db1979e058154368461dc823b3be8187d2cf82f8a16`, 새 manifest SHA256 `a7c01d94d70aafeb6910ec0958fadc8ad5b461005224eaf68fe83c59d553f045`, input contract SHA256 `5078fb94bf0646c082e4ed9ba5198d1230f20a0c86200a9457208302b799682b`다. 기존 canonical Run `run_3d23462a014a`/Task `task_000a7c6dec59`/Dispatch `ctx_f85d0a3a38de`에서 job `7c366be9bf694ce7a476a47119419ca2`, attempt `90784d50902748b9956101771e27662b`가 succeeded다. 실제 parent/child identity·상속 lock·source/config/input/environment/weight hash를 검사하고 모델 로드 전 free8,262MiB로6,144MiB gate를 통과했다.

한 모델 로드로 **030_090_C6 → 030_084_full → 030_084_C6 → 030_094_full → 030_094_C6**를 각각 한 번 실행했다. 정상0행인94 full 뒤에도94 C6를 처리했다. public predict5/정상 Results5/sample model forward 시도5/정상반환5, 별도 공식 warmup forward 시도1/정상반환1이다. 오류0/retry0다. 90 full 재추론은0이다. 기존40jobs/40attempts의 모든 row와 frozen source/input/environment/cache artifact 해시가 보존됐다. 현재 summary SHA256 `1c08d87413a2bc399c2a426f63b865e7f3e2f817c8fc35801781ef206d67c46a`다.

90 full은 EXP-0022 실제 empty native Results/원본/tensor/overlay/관측 JSON과 summary SHA256 `84905e3841a7394f0e3a0e214f7298746f33226fdaa3fafb703c3ded40cf5cde`를 검증해 재사용했다. 과거 결과를 새 성공/새 GPU 비용으로 세지 않았다. raw native Results5개·preprocess tensors5개·관측 JSON5개 및 세 시점 비교 triptych3장/개별 패널9장을 로컬에 저장하고 해시를 확인했다. 기존 배치의 실패/기본 CV/VLM·공식 라벨은 불변이다.

```bash
CUDA_VISIBLE_DEVICES='' YOLO_CONFIG_DIR="$PWD/runtime/BATCH-0005/ultralytics-settings" MPLCONFIGDIR="$PWD/runtime/BATCH-0005/matplotlib" .venv-pose-batch03/bin/python -m unittest tests_orca.test_batch05_pose tests_orca.test_queue -v
CUDA_VISIBLE_DEVICES='' YOLO_CONFIG_DIR="$PWD/runtime/BATCH-0005/ultralytics-settings" MPLCONFIGDIR="$PWD/runtime/BATCH-0005/matplotlib" .venv-pose-batch03/bin/python -m batch05_pose.preflight
# 실제 실행은 종료됨. 아래는 수행 명령이며 완료 입력을 재실행하지 않는다.
.venv-pose-batch03/bin/python -m batch05_pose.cli enqueue --stage comparison
.venv-pose-batch03/bin/python -m batch05_pose.cli run-once
# 아래 CPU 집계만 재생성 가능; 모델/미디어 시각화 없음
PYTHONPATH=. .venv-pose-batch03/bin/python records/EXP-0023/build_summary.py
```

## 출력 진단 — 사람·관절 GT 아님

| exact PTS | full person row / retained joint estimate | C6 person row / retained joint estimate | 해석 |
| --- | ---: | ---: | --- |
| 84초 | 2 / 24 (신규) | 3 / 38 (신규) | ROI에서 출력 증가; 추가 행이 실제 사람인지·기존 행과 같은 사람인지 미검수 |
| 90초 | 0 / 0 (**EXP-0022 cached**) | 1 / 12 (신규) | ROI pose 근거 생성; 실제 관심 인물의 bbox/신체 관절 복원인지는 미확정 |
| 94초 | 0 / 0 (신규) | 0 / 0 (신규) | 양쪽 정상 empty; ROI에서도 pose 근거 없음, 사람 부재/정상 행동 판정 아님 |

retained는 유한·local bounds 내·(0,0)이 아니고confidence≥0.5인 추정치다. 84 full/ROI에서 unknown은 각각10/13개,90ROI는5개다. 0행에는 관절 모집단이 없으며 unknown0을 관절 완전 관측으로 읽지 않는다. output row는 person/track ID가 아니다. 시간 간 사람 대응·관절 보간은 하지 않았다.

각 시점에 원본/full overlay/C6 overlay를 native1920×1080 수준의 패널로 나란히 저장했다. timestamp·고정 ROI 사각형·90full의 cached 표시가 있다. 90full 패널은 기존 zero-person 결과로 생성했으며 가짜 skeleton을 추가하지 않았다. 미디어는 cloud 이미지 도구로 열거나 업로드하지 않았다. 자동 image 생성/decode/hash 검증은 **실제 관절과 신체의 일치 검수와 별개**다.

모든 시점에서 (a) 관심 인물 bbox 대응, (b) 손목·골반·무릎·발목 부착/좌우, (c) 가림/누락·중복·비사람 의심, (d) ROI 경계 절단, (e) 원본 ROI가 관심 인물 전체를 포함하는지는 **사용자 로컬 이미지 검수 전 미확정**이다. 이번 결과는 수치만으로 사람/관절 복원 성공을 주장하지 않는다. C6 calibrated는 감시영역 지정이며 실제 fence top/far-side 교정이 아니다. tracking/행동규칙/CV+VLM·완전 행동 성능은 범위 밖이다.

## 비용과 측정 범위

| 실측 | 값 | 범위 |
| --- | ---: | --- |
| checkpoint CPU constructor | 0.205794초 | 모델 생성/체크포인트 읽기와 CUDA sync; 첫 predictor 준비 제외 |
| 최초 setup_model | 0.360853초 | 공식 deepcopy/fuse/CUDA backend 준비, observer/동기화 포함 |
| 최초 공식 warmup | 0.443770초 | 실제 preprocess tensor forward + synthetic random-box NMS |
| warmup 내부 network predict | 0.351836초 | 위 warmup에 포함; 추가 합산 금지 |
| run-entry wall | 6.352339초 | lease/input 검증·추론·결과/비교 PNG 생성 포함; interpreter startup/final summary save 제외 |
| canonical queue attempt wall | 9.631618초 | parent 검증·child startup 포함 |
| allocator allocated / reserved peak | 204,847,616 / 228,589,568bytes | import 후 constructor 전 reset부터 마지막 비교 저장; 장치 전체 아님 |
| device sampled max used / min free | 2,299 / 7,755MiB | 19샘플, 타 프로세스 포함, 정확한 peak 아님; sampler 오류0 |

| 신규 조건 | Results preprocess | Results inference | Results postprocess | public predict wall |
| --- | ---: | ---: | ---: | ---: |
| 90 C6 (첫 호출) | 33.067732ms | 30.990298ms | 27.494115ms | 0.903369초 |
| 84 full | 6.961323ms | 21.175199ms | 1.359436ms | 0.034790초 |
| 84 C6 | 7.892381ms | 10.285679ms | 1.130539ms | 0.024386초 |
| 94 full | 6.084370ms | 20.845624ms | 0.815132ms | 0.033997초 |
| 94 C6 | 4.832965ms | 17.817225ms | 0.523753ms | 0.028063초 |

cached90full의 **이번 신규 GPU 추론 비용은0**이며, 과거 EXP-0022의 Results inference12.631883ms/public predict wall0.909371초는 `costs.cached_prediction`에 역사적 비용으로만 보관했다. 비용 대조에는 같은 실행에서 쌍을 얻은84/94와 첫 setup/warmup을 포함한90ROI를 구분한다.

측정은 중첩된다. Results.speed는 warmup을 제외하나 preprocess에는 observer의 tensor CPU copy/save와 동기화가 포함된다. public predict wall에는 첫 setup/warmup·profiler/tensor 저장이 포함된다. frame wall은 RGB 검증/native Results/JSON 저장도 포함하고, run-entry에는 최종 PNG 생성도 포함된다. setup/warmup/network time을 서로 독립인 것처럼 합산하지 않는다. 계측된 다섯 단발 호출이며 일반 FPS/실시간성·일반 지연은 산출하지 않아 inference_fps=null이다. 같은 GPU의 다른 프로세스와 observer overhead·호출 순서 효과가 있어 단순 ROI 속도 개선 주장도 하지 않는다.

## 판정·남은 검수·전달

- 기술 실행: **5개 신규 조건 성공,1개 기존 결과 재사용**, 오류0/retry0. 신규 모델/환경/학습/VLM0.
- 실제 사람·관절 품질: **미확정**,90ROI는1행/12개 추정치를 얻었으나 관심 인물·실제 신체 대응을 확정하지 않는다.94에서는 ROI도0행이다.
- 행동 정확도/완료·경계/추적/규칙/결합: **미평가·미실행**, 채택 보류.
- 독립 검토: exact source 사전 PASS; 최종 native artifact/report/metrics binding은 독립 리뷰에 따로 기록한다.
- 웹/GitHub: 총괄이 기존 결과 페이지의 지표/리뷰/실제 이미지 표시와 원격 byte를 따로 검증한다. 이 문서는 해당 전달 완료를 선행 선언하지 않는다. 정지 이미지 비교로 영상 playback/seek는 해당 없음이다.

[comparison](../../records/EXP-0023/comparison.json), [costs](../../records/EXP-0023/costs.json), [metrics](../../records/EXP-0023/metrics.json)는 raw 좌표·미디어·실제 절대경로가 없는 공개 진단 집계다. [CPU builder](../../records/EXP-0023/build_summary.py)는 frozen inference sources 밖에 있어 재생성해도 추론 출처를 바꾸지 않는다. 모든 CCTV/source RGB/native Results/raw 좌표·tensor·이미지·weights·runtime/DB/receipt는 로컬만 유지한다.

권고 한 가지는 **84/90/94 세 시점의 원본/full/ROI 비교를 한 묶음으로 사용자가 검수**해90초1행/12개가 실제 관심 인물에 대응하는지와94초 누락을 확인하는 것이다. 그 전 기본 구성 교체·추가 crop/threshold/해상도·267전체/새 모델/규칙 실험을 자동 시작하지 않는다. 승인된 신규5회 한도는 종료했다.
