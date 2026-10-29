# EXP-0028 — 조건부 BoT-SORT + 사전학습 ReID 비교

2026-10-30 KST. 상태: **독립 사전 검토 PASS 후 한 고정 CPU 비교 1,080프레임 완료. 030의 후기 ID 단절 지속, 007의 긴 ID 유지와 경계 후보 재발이 함께 관측되어 일괄 채택은 보류한다.** 실제 동일 인물 대응·물리 통과는 미확정이며 정확도 수치는 산출하지 않는다.

조정자는 strict/gap 1,080프레임 실행 뒤 030의 초기 ID가 92초 부근에서 종료하고 뒤에 다른 ID가 생기는 등 실질적 ID 단절이 남았다고 보고했다. 이에 사용자 승인에 포함된 **BoT-SORT + 사전학습 ReID 구성 한 개**를 활성화했다. 이 관측은 사람별 정밀 GT나 모든 새 ID가 오연결이라는 판정이 아니다. 기존 검출기/캐시/strict/gap/이전 실험은 보존한다.

## 선택과 고정 설정

설치된 **Ultralytics 8.4.192**의 공식 `BOTSORT.update(results, img=original_bgr)`를 사용한다. 외부 서비스·새 검출기 추론·자체 학습·EXP-0026 best/last 사용은 없다. 공식 [추적 문서](https://docs.ultralytics.com/modes/track/)와 [ReID API](https://docs.ultralytics.com/reference/trackers/utils/reid/)가 지원하는 `yolo26n-reid.onnx` 하나를 선택했다. 원래 BoT-SORT/FastReID나 추가 tracker 패키지는 설치하지 않는다.

가중치는 [Ultralytics 공식 v8.4.0 asset](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-reid.onnx) 9,873,245 bytes, SHA256 `8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb`다. 공식 release API digest와 다운로드 바이트가 일치했다. ONNX metadata는 MSMT17-v1으로 사전학습한 `YOLO26n-reid-2psa`, embedding512, 동적 BCHW, export crop448×448, export version8.4.62를 명시한다. 분류 모델 특징을 사람 전용 ReID라고 부르는 방식은 사용하지 않았다. 코드와 모델 metadata의 **AGPL-3.0**을 유지하며 연구용 로컬 실험 범위다. [공식 라이선스](https://github.com/ultralytics/ultralytics/blob/main/LICENSE)를 따른다. 데이터셋별 일반화나 별도의 모델 성능 수치는 이 실험으로 확인되지 않았다.

| 항목 | 한 개 고정 구성 |
|---|---|
| 검출 입력 | 기존 pretrained FCOS COCO_V1 `cache030` 480장 + `cache007` 600장 |
| 시각 | 030 84–99.967초 / 007 48–67.967초, 약30Hz native PTS |
| high / low / new | .5 / .25 / .6 (과거 ByteTrack 시작점과 정렬) |
| buffer / match / fuse_score | 90프레임 / .8 / true |
| GMC | none: 고정 카메라, 추가 영상 움직임 보정 없음 |
| proximity / appearance | .5 / .8: 공식 기본값 유지 |
| ReID | true, 공식 nano ONNX 하나, 원본 BGR에서 실제 crop |
| crop | 공식 `save_one_box` gain1.02/pad10/squareFalse, RGB 변환/0–1, 448×448 bilinear |
| 장치 | CPU만 명시. ONNX CPUExecutionProvider만 허용 |
| thread | ONNX intra4/inter1/sequential, Torch4/OpenCV1 |
| 경계 | 기존 gap과 동일: 기억3초/dwell.2초/최소3관측/cooldown2초 |

공식 low stage는 `score > .25`, 기존 ByteTrack adapter는 `score >= .25`다. 두 실제 캐시에서 정확히 .25인 행은 0개이므로 이 경계 차이로 실입력이 달라지지 않는다. BoT-SORT의 Kalman/association 구현 자체가 기존 ByteTrack과 다르므로 ReID 단독 원인 효과 비교라고 주장하지 않는다. **proximity .5는 IoU<.5일 때 appearance 비용을 차단한다.** 따라서 먼 위치/겹침 없는 재등장을 외형만으로 연결하는 실험이 아니다. 유사 복장·부분 신체·새 검출 부재·긴 가림의 한계는 남는다.

## 구현과 CPU 사전 검증

`sceneguard/practical_reid.py`는 기존 코드나 공식 library를 수정하지 않고 작은 NumPy results protocol을 제공한다. 공식 tracker가 high/low 분리 뒤 복원한 전체 detection index로 현재 cache row를 연결한다. 실제 관측 bbox/score/cache_index를 그대로 출력하고 Kalman bbox는 `filter_bbox`에 분리한다. lost 상태는 `observed=false,bbox=null,prediction_bbox=...`이며 경계 근거에 넣지 않는다. ReID feature가 비거나 유효하지 않으면 geometry-only로 조용히 대체하지 않고 실패한다.

공식 ONNX backend가 제공하는 session_options를 지역 AutoBackend subclass로 전달하여 스레드 수를 고정한다. 공식 ReID의 crop/resize/feature forward와 공식 BoT-SORT association을 그대로 호출한다. 동적 입력 크기는 공개 asset의 448×448로 고정했다. 표준 ReID 생성자의 동적 입력 fallback224를 사용하지 않는다.

`sceneguard/practical_reid_runner.py`는 원본 SHA, 캐시 hash/기존 FCOS 모델 SHA, 원본 크기, native PTS/time_base를 확인한다. 원본 영상을 seek/decode하여 각 정확한 native frame의 BGR을 사용하고 누락·시각 불일치·EOF 시 실패한다. 관측/예측·후보·재관측과 원본 BGR 누적 SHA, 모델 호출 수/crop 수/유효 embedding 수 및 실제 장치를 로컬에 저장한다. 신규 `outputs/`만 생성하며 기존 결과를 덮지 않는다. GPU 경로는 제공하지 않는다. GPU가 필요해질 경우 canonical queue 사용은 별도 실행 경로가 필요하며 자동 변경하지 않는다.

CPU 테스트 11개가 통과했다. 합성 비디오 exact PTS/누락/EOF, raw bbox와 Kalman bbox 구별, unconfirmed 제외, lost 예측 제외, 잘못된 모델 SHA 거부, 조건부 실행 근거 필수, 공식 tracker의 high/low full index·empty·재관측과 실제 합성 이미지 crop 전달을 확인했다. 이 테스트는 pretrained model inference 없이 실행했으며 실제 CCTV 품질 검증이 아니다.

기존 환경을 수정하지 않고 `runtime/EXP-0028/reid-deps`에 onnx1.19.1/onnxruntime1.23.2/protobuf6.33.0/flatbuffers25.9.23/coloredlogs15.0.1/humanfriendly10.0/ml_dtypes0.5.3만 `--no-deps`로 설치했다. 실행은 기존 `.venv`의 tracking/Torch와 `.venv-pose-batch03`의 Ultralytics를 읽기 전용으로 참조하는 명시적 PYTHONPATH overlay다. 완전한 독립 가상환경이라고 표현하지 않는다.

```bash
PYTHONPATH="$PWD/runtime/EXP-0028/reid-deps:$PWD/.venv-pose-batch03/lib/python3.10/site-packages" \
YOLO_AUTOINSTALL=false OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 \
.venv/bin/python -m unittest discover -s tests -p 'test_practical_reid.py' -v

# 독립 사전 검토 뒤 실행. 실제 조정자 ID 단절 확인 메시지를 근거로 보존한다.
PYTHONPATH="$PWD/runtime/EXP-0028/reid-deps:$PWD/.venv-pose-batch03/lib/python3.10/site-packages" \
YOLO_AUTOINSTALL=false OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 \
.venv/bin/python -m sceneguard.practical_reid_runner 030 007 \
  --output-root outputs/exp0028/reid-v1 \
  --trigger-evidence 'msg_a69399e3cd0d: completed strict/gap leaves material ID breaks; coordinator activates one configuration'
```

실제 출력: `outputs/exp0028/reid-v1/track030/botsort_reid/` 및 `track007/botsort_reid/`의 frames/events/reobservations/manifest/summary. 미디어·좌표·원본 프레임·모델·runtime metadata는 로컬만 유지한다. embedding은 메모리에서 association에 사용하고 별도 공개하지 않는다. accuracy/F1/FPR·법적 침입·물리적 월장 완료를 만들지 않는다.

## 실제 결과와 비용

독립 검토자가 11개 테스트·공식 소스·ONNX provenance·실제 입력 경계 조건을 확인하여 사전 PASS했다. 로컬 `runtime/EXP-0028/review-reid-preflight.json`에 결속하고, 검토 뒤 소스/설정을 바꾸지 않은 채 030→007 순서로 각 한 번 실행했다. 설치된 tracker/ReID/association/AutoBackend/ONNX backend 여섯 파일이 공식 commit `922563eab42b778445e55a2edbabb6974eed8e4b`와 바이트까지 같았다. 코드·입력·설정 freeze는 `reid-preflight-freeze.json`, 공식 source binding은 `reid-source-binding.json`에 로컬 보존한다.

| 구간 | gap→BoT-ReID 관측 행 | 관측 ID | 재관측 | 경계 후보 | gap 연결 표시 후보 |
|---|---:|---:|---:|---:|---:|
| 030, 480장 | 700→677 | 8→9 | 12→9 | 2→2 | 0→1 |
| 007, 600장 | 1279→1278 | 9→11 | 11→12 | 0→1 | 0→0 |

| 구간 | 실제 임베더 호출 | crop / 유효 embedding | CPU 처리 시간 | 실제 provider |
|---|---:|---:|---:|---|
| 030 | 771 | 2837 / 2837 | 18.595초 | CPUExecutionProvider |
| 007 | 1152 | 4041 / 4041 | 22.591초 | CPUExecutionProvider |

합계 1,080장/1,923 임베더 호출/6,878 crop·유효 embedding, 처리 시간 합계 **41.186초**다. 각 구간의 모델 세션 준비·decode·crop/ReID·tracking·경계·JSON·해시 재검사를 포함하지만 프로세스 import 초기 비용과 사전 모델 다운로드·의존성 설치는 제외한다. 원본 검출 추론 비용을 포함한 전체 시스템 FPS가 아니다. Torch CUDA는 끝까지 초기화되지 않았고 GPU job/queue 추가는0이다. CPU 선택은 사전에 조정자가 명시적으로 승인했으며 GPU 큐 우회 실행이 아니다. 오류/OOM/retry0, 학습0, 새 검출 추론0이다.

1,955개 실제 confirmed 관측을 전부 감사하여 native PTS/time_base/원본 cache_index/bbox/score가 일치함을 확인했다. lost 예측1,422행은 bbox가 없고 경계 입력에서 제외된다. 저장 관측만 경계 모듈에 다시 입력한 세 후보는 저장 이벤트와 정확히 같다. 두 cache/metadata/source/model SHA는 실행 후에도 동일하다. 실제 원본 BGR 누적 SHA는 각 실행 summary에 보존하며, 의미 검수나 성능 정답을 대신하지 않는다.

## ID 연결과 후보 해석

**030의 후기 단절은 해결하지 못했다.** gap의 초기 #1은84–92.033초였으나 BoT-ReID #1은84–90.6초, 같은 gap #1의 후기 cache 행 일부는 새 #8(91.867–92.033초)이 받았다. 후기 #12(95.333–96.733초), #13(97.333–98.233초)은 여전히 새 ID다. 초기 #3의84–92.4초 관측은 유지됐다. 관측 ID 수8→9와 후기 새 ID 존재를 실제 누락 복원 성공으로 표현하지 않는다.

030의 두 후보 중 #3은90.4초에 발생하며 gap과 같다. #5는91.167초에 발생하고 `bridged_observation_gap=true`, 기록된 최대 실제 관측 누락 간격은0.3초다. 이는 같은 ID에 실제 재관측이 이어져 gap 경계 메모리로 후보가 나온 **기능적 사례**다. 확인 단계의 누락은 최초 반대쪽 관측90.467초 뒤에 발생하므로, 이 flag만으로 관측되지 않은 통과를 복원했다고 해석하지 않는다. 사람별 동일성이나 물리적 울타리 통과를 확인한 성공1건은 아니다. 해당 경계 양측의 실제 관측 anchor는89.867/90.467초이며 사이의 이동은 추론이다.

**007은 초기 ID의 수치적 연속성이 늘었으나 연결 정확성은 미확정이다.** BoT-ReID #1은49.033–67.967초(541관측, 최대 관측 간격.7초), #2는49.1–61.9초(375관측, 최대.333초)까지 간다. gap 초기 #1/#2는55/56.8초에 끝났다. 같은 시각·같은 cache 행의 중첩을 비교하면 새 #1은 gap #1의125행/#5의95행/#7의26행/#8의282행과 겹친다. 반대로 gap #1 일부49행은 새 #6이 받고 gap #2 일부도 새 #1로 간다. 기존 tracker의 조각화 개선과 새 tracker의 오연결 가능성을 이 중첩표만으로 분리할 수 없으므로 동일 사람 복원으로 확정하지 않는다.

007은 이전 접근·서기 중 신체 박스 범위 변화가 문제가 된 개발 대조 구간이다. gap에서는 후보0이었는데 ReID 구성에서는 #2의 후보가56.733초에 한 번 다시 발생했다. 실제 cache 대조에서 이 ID는 낮은 점수의 짧은 신체 범위 박스들로.2초 dwell을 채우는 동안 gap 쪽은 높고 긴 다른 박스 행을 받았다. 이는 관측 좌표/연결 배분의 차이이지 신체 의미의 새 시각 정답은 아니다. 기존 후보 억제의 이점이 유지되지 않는 국소적 관측이며, 새 후보가 실제 통과인지/동일 인물 오연결인지/박스 범위 변화인지는 별도 연속 영상 검수 대상이다. 후보1을 실제 통과1건이나 오탐률 수치로 바꾸지 않는다.

관측 ID/행 증가나 긴 유지시간은 성공 지표가 아니다. 이번 결과는 **030의 미해결 단절 + 007의 긴 ID 지속/연결 혼합 가능성 + 접근 대조 후보 재발**로 정리한다. 같은 검출 캐시로 추적 구성만 바꾸었으므로, 새 검출 자체가 없던 사람·가림 속의 정확한 이동을 ReID가 만들어낸 것은 아니다. 같은 모델의 추가 설정·스윕·대체 임베더·GPU 실행을 자동 시작하지 않는다.

독립 outcome 감사가 PASS했다. 검토자가1,080장의 raw cache index/bbox/score와 원본 BGR 재decode hash/native PTS, source/model/code hash, 누적 호출/crop 계수 및 저장 이벤트 재계산을 별도로 확인했다. 로컬 receipt는 `runtime/EXP-0028/review-reid-outcomes.json`이다. 조정자와 렌더 담당자에게 실제 결과를 전달했고, 기존 renderer가 별도의 원본/gap/ReID 연속·집중 영상을 만들고 있다. 실제 사람의 시각 대응 판정과 결과 화면 등록·사용자 화면 검수는 기술 실행과 별도다. 최종 전달 상태는 [종합 결과](EXP-0028-results.md) 및 [독립 검토](../reviews/EXP-0028-independent-review.md)를 따른다. 추가 모델·학습·설정 sweep은 시작하지 않았다.
