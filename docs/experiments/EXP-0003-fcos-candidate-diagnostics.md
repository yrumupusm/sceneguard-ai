# EXP-0003 — E01_030 FCOS person 후보의 단계별 소실 진단

- 2026-10-27 / Codex 계측·로컬 검토 / **진단 완료, 시각적 원인은 미확정**.
- 사용자 확인: 84초에는 서 있거나 접근하는 사람 3명과 최종 검출 3개, 90초에는 문을 넘는 사람 3명이 보이지만 최종 검출 0개. 자세·울타리·사람 겹침이 달라졌으나 인과 원인은 아직 확정하지 않음.
- 기존 [EXP-0002](EXP-0002-fcos-detector-comparison.md), [ADR-0008](../decisions/ADR-0008-fcos-detector-comparison.md) 보존. 모델 변경을 결정하는 실험이 아니라 사용자 승인된 읽기 전용 계측이다.
- 실행 기준 HEAD `39544d81be9655d6bcdd028414d53ba9b54f1292` + 이번 계측 코드 수정(git_dirty=true). 추론 파일의 정확한 SHA256은 아래와 로컬 run.json에 기록한다.

## 질문에 대한 답

**90초에도 실제 사람이 보이는 위치와 겹치는 낮은 점수 person 후보가 만들어졌다. “후보 자체가 없었다”는 결론은 틀리다.** NMS/전체 수 제한을 통과해 모델이 반환한 person 4개의 점수는 **0.337676, 0.302212, 0.296940, 0.295868**이며, 최종 person≥0.5 필터에서 모두 제외됐다.

더 이른 단계도 확인했다. 90초의 전체 21,486개 anchor 위치에서 raw person 결합 점수의 최대가 **0.337676**으로, **어느 위치에도 0.5 이상 person 후보가 없었다**. 따라서 NMS가 고득점 사람 후보를 모두 지워 최종 0이 된 사례가 아니다. 사람 부근의 일부 후보는 내부 0.2 필터, NMS, 전체 상위 100개 제한에서 각각 제거됐지만, 그 후보들도 0.5 미만이었다. ROI가 최종 검출을 지운 것도 아니다.

이는 점수·후처리 단계에 대한 확인이다. 왜 자세 변화 장면에서 person 점수/박스 품질이 약해졌는지(자세·가림·학습 분포·특징 등)는 이 계측만으로 확정하지 않는다. “0.5를 낮추면 사람 검출 문제가 해결된다”는 처방도 도출하지 않는다.

## 실제 코드의 처리 순서

설치된 **TorchVision 0.20.1**의 FCOS.postprocess_detections 소스를 읽고 런타임 값과 대조했다. [공식 버전 소스](https://github.com/pytorch/vision/blob/v0.20.1/torchvision/models/detection/fcos.py), [공식 0.20 문서](https://docs.pytorch.org/vision/0.20/_modules/torchvision/models/detection/fcos.html). 아래 프로젝트 부분은 로컬 run_cv.py / boundary.py의 실제 처리다.

| 단계 | 실제 설정/처리 | 이번 진단에서 구분한 것 |
| --- | --- | --- |
| 입력/헤드 | 원본 전체 1920×1080→resize 749×1333, pad 768×1344, FP32. 5 FPN 레벨 총 21,486 위치, COCO 91 class 차원 | 사람 검수 위치로 입력을 자르지 않음 |
| 점수 구성 | `sqrt(sigmoid(person_logit) * sigmoid(centerness_logit))` | class 확률과 centerness도 별도 저장. softmax나 class 확률 단독 0.5 필터 아님 |
| 내부 점수 | 각 레벨의 모든 anchor×class 중 **score > 0.2** | 0.2 이하 person도 진단용 decode·저장하되 모델 반환/추적에 넣지 않음 |
| 레벨 후보 제한 | 각 FPN 레벨에서 **전체 class 합쳐 상위 1,000개** | person별 1,000개가 아님. 필터 후 topk 이전 후보와 비교 |
| 박스 복원 | 선택 anchor의 회귀값 decode, 변환 영상 경계로 clip | 후보 ID는 FPN 순서로 누적한 anchor index, 사람 ID 아님 |
| NMS | **클래스별 batched_nms IoU 0.6** | 다른 클래스의 울타리/차량 박스가 직접 person을 억제하는 방식 아님. 동일 person 클래스 억제 박스 기록 |
| 이미지 후보 제한 | NMS 생존 후보 중 **모든 class 합쳐 상위 100개** | NMS에서 살아도 여기서 탈락할 수 있음 |
| 모델 반환 | 원본 영상 좌표로 복원된 boxes/scores/labels | 이 결과만으로 내부 후보 부재를 판단할 수 없음 |
| 프로젝트 최종 필터 | label==1 및 **score≥0.5**, 좌표 정규화·clamp, 면적 0 박스 제외 | 기존 frames.jsonl은 이 이후만 저장하므로 앞 단계는 복원 불가 |
| 추적/ROI/경계 | 기존 IoU≥0.3 연결, ROI 밖 하단 중심은 경계 상태 초기화. 모든 입력 검출을 rows에 그대로 기록 | ROI는 person bbox 삭제 필터가 아님. band/dwell/유한 선분은 이벤트 후보에만 적용 |

NMS 수치 0.6과 추적 IoU 0.3은 다른 처리다. ROI·경계 config 및 추적 코드는 EXP-0002와 그대로다.

## 데이터·실행 범위·동일성

기존 원시 헤드/내부 후보가 저장되지 않았으므로 E01_030만 **84.000000~96.000000초 포함, 361프레임** 재실행했다. CLI의 end가 exclusive이므로 `--end 96.000001` 사용. 다음 96.033333초 프레임은 포함하지 않았다. 모든 프레임 추론, PTS 보간 없음.

- 동일 FCOS COCO_V1, weight SHA `99b0c9b7cfb1527d782db86b91d207f00547c792fb4103fc612b651d0a07b9e7`.
- 동일 C6 config SHA `feea6703d31f21a1aa7f45a6843fe938f8887b7a8ba729a5be62f6a07785509b`.
- RTX 3080 10GB, torch 2.5.1+cu124 / torchvision 0.20.1+cu124 / PyAV 16.0.1 / Python 3.10.12. 입력/seed/threads/warmup 및 라이선스는 EXP-0002와 동일.
- 계측 wrapper는 **원래 공식 후처리를 먼저 호출**하고 동일 입력 tensor의 처리 경로를 별도로 재현한다. 공식 반환값은 수정하지 않고 그대로 돌려준다.
- **361프레임 모두** shadow의 boxes/scores/labels와 원래 내부 반환값을 torch.equal로 검사해 완전 일치.
- EXP-0002의 같은 PTS에 저장된 최종 bbox·점수·순서·track_id·observed·native PTS/time_base와 **361개 전체 레코드 완전 일치**. 후보 이벤트도 0.
- 영상/config/가중치/추적 코드 SHA 동일. 독립 감사 PTS 최대 오차 약 3.34e-7초(반올림 수준). 96초 마지막 프레임 포함 확인.
- 단계 집계는 361개, 전체 raw person 후보 배열/score·class probability·centerness·terminal stage 및 NMS 억제 관계는 **84/88/90/92/94/96초 6개 프레임**에 저장했다. 다른 프레임의 모든 raw 후보를 보관했다는 뜻은 아니다.
- 원본 JSON/공식·사용자 정답은 추론에서 읽거나 변경하지 않음. 현재 development, G1E/정답 평가 미완료. 이 결과로 precision/recall/F1/FP-hour 산출 안 함.
- 계측의 추가 decode/후처리/동기화/파일 기록 비용이 있으므로 **새 실행 시간은 기존 FPS와 직접 비교하지 않는다**. 메타데이터 timing_comparable=false.

## 단계별 person 후보 수

아래 수는 사람 수/정답 recall이 아니다. raw 21,486개 중 대부분은 배경 위치다. 내부 탈락 수를 실제 사람 미탐 수로 읽지 않는다. 마지막 열을 제외한 탈락 열은 해당 단계에서 처음 제거된 수이며 상호 배타적이다.

| PTS | 내부 >0.2 통과 | 레벨 topk 탈락 | NMS 탈락 | 전체 100개 제한 탈락 | 반환 후 <0.5 탈락 | 최종 person≥0.5 | raw person 최고점 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 84 | 119 | 0 | 100 | 11 | 5 | 3 | 0.760994 |
| 88 | 201 | 0 | 171 | 15 | 11 | 4 | 0.753085 |
| 90 | 57 | 0 | 46 | 7 | 4 | 0 | 0.337676 |
| 92 | 127 | 0 | 111 | 5 | 9 | 2 | 0.647004 |
| 94 | 48 | 0 | 39 | 5 | 4 | 0 | 0.359924 |
| 96 | 41 | 0 | 36 | 0 | 4 | 1 | 0.728548 |

6개 선택 시점에서 레벨당 내부 통과한 전체 클래스 후보 수가 모두 1,000 미만이므로 level topk 제한은 사람 후보를 제거하지 않았다. **전체 100개 제한은 실제로 작동했다.** 90초에는 person 57개→NMS 후 11개→전체 cap 후 4개→최종 0개다.

## 실제 사람 위치와 후보 대응 — 84초 vs 90초

사용자가 제공한 것은 장면 해석과 인원수이며 **사람별 bbox 좌표는 제공하지 않았다**. Codex가 후보 점수를 보기 전에 기존 원본 미리보기에서 대략적인 위치 사각형을 지정했다. 이것은 수동 진단 위치 초안이고 사용자 승인 정답/사람 추적 ID가 아니다. 위치 좌표는 로컬 review_locations.json에만 보관했다.

해당 위치와 bbox IoU≥0.3인 후보 중 최고점 후보를 표에 제시했다. 0.3은 **오프라인 진단 대응 규칙**으로 모델/추적 설정을 바꾸지 않는다. 넘기 자세·가림에서는 부분 신체 bbox와 사각형의 IoU가 낮을 수 있으므로 이 규칙만으로 사람 인식 성공/실패를 확정하지 않는다. 특히 90초 중앙/앞 인물의 영역이 겹쳐 같은 후보가 두 영역과 대응할 수 있다.

| PTS·위치 | 후보 ID | 점수 | class probability / centerness | 검수 영역 IoU | 마지막 처리 |
| --- | --- | --- | --- | --- | --- |
| 84 left | 7634 | 0.760994 | 0.675070 / 0.857854 | 0.733 | final_person |
| 84 rear_right | 18101 | 0.642059 | 0.646938 / 0.637217 | 0.557 | final_person |
| 84 front | 18436 | 0.610207 | 0.496395 / 0.750113 | 0.630 | final_person |
| 90 left | 7305 | 0.244445 | 0.089901 / 0.664659 | 0.386 | global_cap |
| 90 rear_middle | 7143 | 0.302212 | 0.119708 / 0.762954 | 0.414 | returned_below_0.5 |
| 90 front_right | 18106 | 0.296940 | 0.126645 / 0.696226 | 0.615 | returned_below_0.5 |

84초 세 후보는 최종 검출이고 사용자 확인 사람 위치와 대응한다. 90초 왼쪽 최고점 #7305는 몸의 일부만 포함하는 박스로 NMS는 통과했으나 global cap에서 제거됐다. 이보다 검수 영역과 더 넓게 겹치는 #17932(IoU 0.623)는 0.198535여서 내부 score 필터에서 제거됐다. 중앙 #7143과 앞쪽 #18106은 모델 반환까지 살아남았지만 0.5 미만이다.

90초 raw 최고점 **#6305, 0.337676**은 중앙 인물의 머리/상체 일부를 감싸는 작은 박스다. 검수 사각형 IoU 0.3 규칙에서는 빠지므로 위 최고점 위치 표만 보고 최고점이 0.302212라고 결론내리면 안 된다. 이 후보도 모델이 반환했으나 최종 필터에서 탈락했다. 부분 신체·사람 겹침 때문에 “서로 다른 세 사람을 정확히 구성한 후보 세 개”로 확정할 수 없다.

84초 최고점 대응 후보들의 class probability는 약 0.496~0.675, 90초 표의 대응 후보들은 약 0.090~0.127로 낮다. centerness만 낮아졌다고 설명할 수 없으며, 서로 다른 anchor/자세를 비교한 관찰이므로 점수 하락의 시각적 인과 요인을 증명하지 않는다.

## NMS에서 누가 누구를 제거했는가

선택 시점의 NMS 생존 순서에서 동일 클래스·더 높은 점수·IoU>0.6인 먼저 선택된 박스를 억제 박스로 기록했다. 전체 cap 이전 생존자를 사용하므로 나중에 cap으로 잘린 박스도 억제자가 될 수 있다. 아래 사례는 점수가 서로 달라 동점 선택 모호성이 없다.

| PTS·위치 | 제거된 후보 / 점수 | 억제 박스 / 점수 | 두 박스 IoU | 억제 박스의 최종 상태 |
| --- | --- | --- | --- | --- |
| 84 left | #7466 / 0.724234 | #7634 / 0.760994 | 0.908984 | final_person |
| 84 rear_right | #7642 / 0.632082 | #18101 / 0.642059 | 0.907954 | final_person |
| 84 front | #18352 / 0.576400 | #18436 / 0.610207 | 0.958853 | final_person |
| 90 left | #7304 / 0.233008 | #7305 / 0.244445 | 0.646194 | global_cap |
| 90 rear_middle | #6807 / 0.296255 | #7143 / 0.302212 | 0.623245 | returned_below_0.5 |
| 90 front_right | #18022 / 0.295166 | #18106 / 0.296940 | 0.986434 | returned_below_0.5 |

따라서 “NMS가 전혀 작동하지 않았다”도 틀리지만 **90초 최종 0개를 NMS 탓으로 단정할 근거는 없다**. 고득점 person≥0.5가 NMS 이전부터 하나도 없었다. 낮은 점수·부분 신체·중복 후보가 실제 존재한다는 사실과 안정적인 사람 검출을 달성했다는 주장은 다르다.

## 로컬 검수 자료와 재현

- outputs/cv_phase2c/diagnostic030/: 원시 person NPZ 6개, 단계 JSONL 361개, diagnostic_config.json, 기존 형식의 최종 frames/events/run.
- outputs/cv_phase2c/review030_v2/: **원본 / 기존 기준 최종 검출 / 진단 후보** 3패널 이미지 6개, 84/90초 candidate_cards 이미지, associations.csv/json.
- cards의 열은 위치, 행은 최고점·내부 score 탈락 예시·NMS 탈락 예시다. 회색=내부 탈락, 빨강=NMS 탈락, 자홍=global cap, 주황=반환 후 0.5 미만. cards의 초록은 **NMS 억제 박스**이며 최종 검출이라는 뜻이 아니다(제목에 명시).
- 대략적인 검수 위치는 cyan. 낮은 점수 후보는 **DIAGNOSTIC ONLY**로 표시하고 최종 bbox/추적에 주입하지 않았다. 이미지 확대는 추론 후 표시 전용이며 입력 crop 추론이 아니다.
- 추가 90초 모델 반환 4개만 표시한 확대 근거: outputs/cv_phase2c/review030/returned90_focus.jpg. 이미지·원시 후보·영상·가중치는 Git에 올리지 않는다.

```bash
.venv/bin/python -m sceneguard.run_cv --detector fcos800 --diagnose-fcos --video data/TS_침입/E01_030.mp4 --config data/cv_phase2a/configs/C6.json --output outputs/cv_phase2c/diagnostic030 --start 84 --end 96.000001
python3 scripts/check_cv_runs.py outputs/cv_phase2c/diagnostic030
.venv/bin/python scripts/review_fcos_diagnostics.py --run outputs/cv_phase2c/diagnostic030 --baseline outputs/cv_phase2b/fcos030 --previews outputs/cv_phase2b/review030 --locations outputs/cv_phase2c/review_locations.json --output outputs/cv_phase2c/review030_v2
.venv/bin/python -m unittest discover -s tests -v
```

출력은 새 디렉터리만 허용한다. 원본 미리보기 재사용은 해당 SSD 시점의 bbox가 0임을 검사한 후 수행한다. 스크립트의 기본 검수 시점은 이번 030 진단에 고정돼 있다.

총 테스트 **14개 통과**. 새 합성 테스트는 내부 필터/NMS/global cap/level topk 단계를 각각 확인하며, NMS 억제 ID·IoU와 원래 반환값 불변성을 검증한다. 합성 테스트에서만 cap/topk를 작게 만들어 분기를 검사했으며 **실제 영상의 설정은 변경하지 않았다**. 실제 361프레임 동일성 검사와 별도로 구분한다.

| 실행 추론 파일 | SHA256 |
| --- | --- |
| sceneguard/run_cv.py | `17a29d6d0025933579502270c731b5b616d1bfc6e30c77bc8b136aabe7605d56` |
| sceneguard/boundary.py | `cd2010444a4a35d13b8a88e713594f9b13be52bd3b2b93ff83cebd47553688b9` |
| sceneguard/detectors.py | `ea07dbfbe9f6d813c699a386d2f12ab7c4214b6fdf6868386b95f8fa21866141` |
| sceneguard/fcos_diagnostics.py | `48b2c3a8686fa56f584f3e0649a55fb3157b5af7fc7c14cf365990747a96fa5c` |

설치된 공식 postprocess 함수 source SHA256은 `a8a6ecd9c15efb3b0b7a35e0df386ff2b532fb6801c710f44b435a3bfabe5fdd`. 공식 소스 파일 자체를 저장소에 복제하지 않았다.

## 다음 실험 제안 — 이번에는 실행하지 않음

1. 사용자와 84/90초 위치·부분 신체 후보·겹치는 사람 대응을 검수하고, 88/92/94/96초에도 사람별 관측 가능 범위를 별도 확정한다. 예측을 자동 정답으로 만들지 않는다.
2. 같은 FCOS/입력/필터를 유지한 소량 검수 프레임에서 서기·넘기·가림 정도별 **사람 위치의 raw 결합 점수/class probability/centerness/박스 대응**을 비교하는 진단을 설계한다. 모델 score 하락과 위치 회귀 실패를 분리하며, 자세가 원인이라는 결론은 추가 통제 없이는 유보한다.
3. 독립 검수 음성 구간/카메라 그룹/정밀 사람별 시각/G1E를 먼저 확정한다. 현재 표본으로 임계값을 맞추거나 최종 정확도를 주장하지 않는다.
4. 현재 증거는 NMS·ROI 변경의 우선 필요성을 지지하지 않는다. threshold/NMS/해상도/crop 변경·새 모델·추적기·VLM·학습은 이번에 실행하지 않았고 후속 도입도 확정하지 않았다.
