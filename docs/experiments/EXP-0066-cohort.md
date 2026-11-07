# EXP-0066 비교 cohort·native FCOS 저장 검출 전수 감사

2026-11-07. **45개 원본의184,300개 native 프레임에 대해 저장 FCOS person cache 전수를 CPU로 읽고, 새 모델 입력을 FCOS 제안에 종속하지 않는 전구간 계획을 생성했다.** 1초 간격 주 관측 창6,177개, 별도 진단 창42개, 고정 smoke7창이다. 실제 새 모델·GPU·학습·가중치 로딩·설치는0회다.

검출 cache 전수 감사 완료와 **사람별 누락 정답 목록 완성은 다르다.** 과거006/007/030/031의 특정 프레임 실패 근거와 최근015/039/043의 사용자 박스 공백 관찰을 연결했다. 전체45에서 모든 관심 인물의 정밀 가시성·bbox 정답은 확보되지 않아 전체 detector recall/precision/F1·누락 총수·모델별 승자는 `null`이다. 추적/표시 공백이나 EXP-0062의 사건 확인 누락15건을 FCOS FN 정답으로 대체하지 않았다.

## 권한·보존·검수

새 Task `task_78ac69e418bb`, Dispatch `ctx_8ca44a1ee076`를 사용했다. 앞선 새 terminal 시작 실패 `task_118404fa2231`과 settled EXP-0065 배정은 실행 권한으로 재사용하지 않았다. 시작 HEAD는 `cbf89c236d0b0f3316362f6a31510a552e2d8f79`이며, 이 worker는 queue/생산 코드/DB/기존 출력/sg-passage 디렉터리를 수정하거나 commit/push하지 않았다. 담당 변경은 준비 스크립트·집중 시험·이 보고서와 새 cohort/runtime 산출물뿐이다.

`AGENTS.md` 및 `WEB_REVIEW_WORKFLOW.md`를 읽고 기존 labvenv의 `pending --include-acknowledged`가 성공해 `requests: []`임을 확인했다. 그 뒤 실제 `configured_store.list('EXP-0065')`의 **읽기 전용 SQLite transaction**으로9개 원문·메모·이력·source binding을 읽었다. 모두 version4/answer_version1/applied다. 과거 snapshot의8applied/1pending 상태를 현재 상태로 재사용하지 않았다. 새 snapshot은 `runtime/model-comparison/exp0066/cohort/current-review-snapshot.json`이며 원래 snapshot/DB/처리 이력은 보존했다. 새 질문·대리 답변·ack/resolve 쓰기는 없다.

검수 범위는 다음과 같이 유지한다.

| 기존 자료 | 재사용 범위·한계 |
| --- | --- |
| 015 입력60–62.333초 | 넘는 대상 포착 및 약61초부터 박스 불연속 관찰. 원본 종료/침입 완료나 공백 원인은 확정하지 않음 |
| 039 입력59–61.333초 | 두 사람 겹침과 약57초 시작·58–59초 표시 공백. 사람별 bbox/ID 대응과 detector 누락 원인은 미확정 |
| 043 입력65–67.333초 | 16/17은 넘는 대상, 본격 동작·박스 소실 약68초는 선택 입력 뒤. 입력 안 넘기 성공으로 승격하지 않음 |
| 026 입력65–67.333초 | 대상 넘기 및 주변64–70초 박스 관찰. 이후 문 가림을 visible-person FN으로 만들지 않음 |
| 028 입력66–68.333초 | 대상 넘기와 회색ID3→빨강ID4 동일인 관찰. ID 변경을 다른 사람/검출 소실로 만들지 않음 |
| 034 입력33–35.333초 | 문 앞 서 있기·넘기 없음의 선택 입력 대조. 영상 전체를 정상으로 라벨하지 않음 |
| 021 입력72–74.333초 | 두 사람의 문 옆 별도 경로 통과. 일반적인 문 월담과 구별, C5 영역 확장 이력 보존 |
| 공원 오판1 입력16.667–19초 | 공식 stand와 실제 넘기 관찰의 의미 충돌. 라벨/기존 지표를 소급 수정하지 않음 |
| 공원 오판2 입력85.667–88초 | 빨간 라벨 박스가 비어 보이고 약89초 회색 annotation 인물이 넘기 시작. 시각/대상 불확실성 유지, 새 detector 출력으로 바꾸지 않음 |

공원2개 답변은 의미 해석의 한계로 재사용하며 학교45 cohort에 원본을 섞지 않았다. 모든 요청ID·정확한 version/answer_version·artifact/source binding SHA·원문은 `failure-evidence.json`에 포함했다. 원시 답변과 좌표는 로컬 전용이다.

## 실제 입력·cache lineage

기준은 EXP-0063 baseline attempt-002의 EXP-0062 AFTER lock SHA `3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40`다. 잠긴 `after-manifest.json`의 SHA `c3b43879997033661ac84eb8e8406e328fee95b6779a97ace1f317500a602d19` 및 inventory SHA `3616ad42ac430310dc6a2e38d1616adb10f4ca5e86d128daa55cad157ea2f239`를 사용했다. 실제 inventory는 `outputs/validation/mvp-all-v3/evaluation-inputs/inventory.json`이며, 그 안에서45개 `mvp-all-v1/inventory/native-pts/E01_XXX.json`의 원본 SHA와 native clock 파일 SHA를 바인딩한다.

45개 detector metadata 중39개는 `outputs/exp0037/detector/<attempt>/cache/run.json`, C5의014/016/018/020/021/038은 `runtime/MVP-0006/execution/cache-views/E01_XXX/run.json`이다. 모두 lock의 정확한 해시로 검증했다. C5 view는 `geometry_reuse_provenance.original_directory`의 metadata와 person cache SHA를 다시 대조했다. **검출은 전체 화면에서 원래 계산한 동일 바이트이며 ROI/선만 바뀐 view**다. mtime이나 새 파일명으로 새 추론을 추정하지 않았다.

FCOS 식별자는 `fcos_resnet50_fpn.COCO_V1`, 가중치 SHA `99b0c9b7cfb1527d782db86b91d207f00547c792fb4103fc612b651d0a07b9e7`다. 가중치 파일을 읽지 않고 frozen metadata의 식별자를 검증했다. cache는 원본 pixel 좌표의 `pts/native_pts/time_base/source_size/boxes/scores` JSONL이며 class1 person만 포함한다. 저장 단계는 **내부 score0.2·top-k1000·NMS0.6·전체 클래스100 cap 이후, project score0.5 이전**다. raw라는 말이 prefilter logits나 제거된 모든 후보를 뜻하지 않는다. 추적 ID/예측·보간 박스는 이 전수 분모에 넣지 않았다.

231,507,132bytes의45개 cache를 읽고 각각의 고정 SHA, 모든 native PTS·time_base·프레임 수·영상 크기, box/score 유한성·범위,0.5 이후 run 통계를 대조했다. project0.5 count는 원래 run의 person_boxes/frames_with_person와 모두 일치했다. 실행 종료 전에 소비한160개 파일 해시를 다시 대조했다. 원본 영상의 전체 SHA를 새로 읽은 것은 아니며, frozen source SHA와 현재 byte length·PyAV header(크기/time_base/frame count)를 확인했다. 픽셀 디코딩은 없다. 새 모델 실행자는 별도로 실제 원본 바이트를 검증해야 한다.

006은29.97계열이며4006프레임·한 번의6006tick gap을 보존했다. `index/30`으로 시각을 만들지 않았다. 전체 native 끝133.700233333초와 이전 duration133.666866667초를 별도 필드에 유지했다. 공식006 시간 미확정1건과008 의미 보류도 그대로이며 정답/평가를 변경하지 않았다.

## 전수 출력 통계 — 정답 기반 성능이 아님

| 항목 | 실제 개수 |
| --- | ---: |
| 전체 원본 / native 프레임 | 45 / 184,300 |
| post-internal person 박스 행 | 2,134,924 |
| project0.5 이상 박스 행 | 161,834 |
| raw person 출력이 있는 프레임 | 181,454 |
| project0.5 출력이 있는 프레임 | 85,731 |
| 기존 고정 ROI와 양의 면적으로 겹치는 raw / project 박스 | 795,582 / 84,649 |

박스 행은 중복/부분 신체/다른 사람/오검출을 포함할 수 있다. ROI 통계는 박스와 고정 영역의 양의 면적 교집합이며 기존 tracker의 실제 입력 재현이나 같은 사람 판정이 아니다. 출력0인 프레임도 사람이 없다는 정답이나 detector FN이 아니다.

| 영상 | 카메라 | native 프레임 | raw 행 | project0.5 행 | 주 창 |
| --- | --- | ---: | ---: | ---: | ---: |
| 001 | C1 | 4112 | 42393 | 1713 | 138 |
| 002 | C1 | 4142 | 39126 | 473 | 139 |
| 003 | C1 | 4172 | 23587 | 1706 | 140 |
| 004 | C2 | 3761 | 57745 | 5841 | 126 |
| 005 | C3 | 4101 | 19824 | 2332 | 137 |
| 006 | C3 | 4006 | 30100 | 5404 | 134 |
| 007 | C3 | 4171 | 34401 | 4300 | 140 |
| 008 | C8 | 4042 | 62535 | 5931 | 135 |
| 009 | C1 | 4321 | 24205 | 1113 | 145 |
| 010 | C4 | 3782 | 53052 | 3075 | 127 |
| 011 | C4 | 4180 | 65681 | 4011 | 140 |
| 012 | C4 | 4212 | 54140 | 2634 | 141 |
| 013 | C4 | 3781 | 52086 | 2551 | 127 |
| 014 | C5 | 4141 | 91507 | 5121 | 139 |
| 015 | C4 | 3922 | 60994 | 6041 | 131 |
| 016 | C5 | 4212 | 31496 | 1561 | 141 |
| 017 | C4 | 4411 | 63455 | 4615 | 148 |
| 018 | C5 | 4132 | 30464 | 1635 | 138 |
| 019 | C4 | 4551 | 49737 | 2599 | 152 |
| 020 | C5 | 4202 | 60897 | 2473 | 141 |
| 021 | C5 | 4171 | 70694 | 4829 | 140 |
| 022 | C1 | 4261 | 36099 | 2579 | 143 |
| 023 | C4 | 3971 | 57067 | 3497 | 133 |
| 024 | C1 | 4111 | 24112 | 307 | 138 |
| 025 | C1 | 4200 | 32469 | 709 | 140 |
| 026 | C6 | 3962 | 17755 | 1109 | 133 |
| 027 | C1 | 4291 | 53373 | 958 | 144 |
| 028 | C6 | 3962 | 21532 | 447 | 133 |
| 029 | C1 | 4502 | 17119 | 1183 | 151 |
| 030 | C6 | 4802 | 25089 | 4513 | 161 |
| 031 | C7 | 3606 | 56811 | 3635 | 121 |
| 032 | C3 | 3606 | 15072 | 2956 | 121 |
| 033 | C4 | 3578 | 75765 | 7266 | 120 |
| 034 | C1 | 3608 | 20904 | 1155 | 121 |
| 035 | C4 | 3607 | 75216 | 4521 | 121 |
| 036 | C4 | 3608 | 82007 | 7557 | 121 |
| 037 | C4 | 3844 | 85748 | 5092 | 129 |
| 038 | C5 | 5408 | 71138 | 8158 | 181 |
| 039 | C4 | 3908 | 102245 | 17849 | 131 |
| 040 | C1 | 4058 | 15159 | 401 | 136 |
| 041 | C1 | 4057 | 17699 | 911 | 136 |
| 042 | C1 | 4204 | 21392 | 1127 | 141 |
| 043 | C4 | 4207 | 84690 | 3817 | 141 |
| 044 | C1 | 4208 | 20659 | 108 | 141 |
| 045 | C4 | 4206 | 87685 | 12021 | 141 |

## 알려진 실패와 최신 검수 공백의 연결

과거 실패의 정확한 native 시각은 기존 `outputs/cv_phase2b/fcos006|007|030|031/frames.jsonl`에서 현재 fullvideo clock과 연결했다. 과거 파일은 project0.5 이후의 normalized detection 출력이며 raw internal 반환이 아니다. 006 표시 반올림 시각은 아래 실제 native PTS로 바인딩한다. 같은 프레임의 출력 수가 같아도 박스/사람 복구가 같다는 뜻은 아니다.

| 근거 | 실제 native 초 | 과거 project 행 | 현재 raw / project 행 | 해석 |
| --- | --- | ---: | --- | --- |
| 030_climbing_90 | 90.000000000 | 0 | 4 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 030_occlusion_94 | 94.000000000 | 0 | 4 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 031_occluded_person | 36.000000000 | 0 | 13 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 031_occluded_person | 38.000000000 | 0 | 17 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 031_occluded_person | 40.000000000 | 0 | 14 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 031_occluded_person | 42.000000000 | 1 | 10 / 1 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 031_occluded_person | 44.000000000 | 1 | 14 / 1 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 006_distant_person | 120.987533333 | 0 | 2 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 006_distant_person | 122.989533333 | 0 | 3 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 006_distant_person | 124.991533333 | 0 | 3 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 006_distant_person | 126.993533333 | 0 | 5 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 006_distant_person | 128.995533333 | 0 | 6 / 0 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 007_overlap_climbing | 66.000000000 | 1 | 19 / 1 | 특정 시점의 저장 출력; 대상 복구 미확정 |
| 007_approach_control | 56.700000000 | 4 | 14 / 4 | 특정 시점의 저장 출력; 대상 복구 미확정 |

03090/94초의 기존0행은 project0.5 기준이다. 현재 raw cache에는 각각4행이 있지만 관심 사람을 적절히 잡은 것인지는 미확정이다. 006의 다섯 표본도 raw2/3/3/5/6행과 project0행을 구분한다. 03142/44초의 project1행은 과거 관심 인물 대신 배경 의심 출력이라는 제한을 유지한다. 00766초는 보이는 두 사람과 project1행의 개별 관측 실패 근거이며 단순 raw19행을19명 복구로 읽지 않는다. 00756.7초 접근 대조는 정밀 음성 시작/끝 정답이 아니다.

이 과거 자료는 정성적으로 알려진 특정 프레임 실패 근거이며 모든 사람·모든 프레임의 bbox GT가 아니다. 과거 RF-DETR 출력 행 수·YOLO 진단 결과도 새8구성의 복구 성공으로 소급 사용하지 않는다. 실패 근거 원문은 [EXP-0002](EXP-0002-fcos-detector-comparison.md), [EXP-0024](EXP-0024-user-pose-review.md), [EXP-0028](EXP-0028-user-tracking-review.md)를 따른다.

최근 관찰의 원인 미확정/대조 구분은 다음과 같다. 모든 수치는 같은 native 초의 전체 화면 출력 수이며 관심 actor의 IoU/정체를 확인한 TP/FN이 아니다.

| 자료 | 초별 raw/project 출력 | 상태 |
| --- | --- | --- |
| 015 | 60초 10/2 · 61초 11/2 · 62초 12/1 · 63초 11/0 | `reviewed_box_gap_cause_unresolved` |
| 039 | 57초 16/2 · 58초 18/1 · 59초 22/2 · 60초 25/1 | `reviewed_box_gap_cause_unresolved` |
| 043 | 67초 21/0 · 68초 13/0 · 69초 17/1 · 70초 18/0 | `reviewed_box_gap_cause_unresolved` |
| 026 | 64초 8/1 · 65초 14/1 · 66초 12/1 · 67초 5/1 · 68초 6/1 · 69초 5/1 · 70초 8/1 | `reviewed_climbing_continuity_control` |
| 028 | 66초 9/1 · 67초 7/1 · 68초 7/1 | `reviewed_identity_transition_control` |
| 034 | 33초 5/1 · 34초 7/0 · 35초 8/1 | `reviewed_standing_action_control` |
| 021 | 72초 33/2 · 73초 34/2 · 74초 20/1 | `reviewed_sidepath_semantic_control` |

01563초와04367/68/70초는 해당 시점 project0행이지만 raw는 남는다. 03958/59초에는 project1/2행이 있어 사용자 표시 공백을 화면 전체 검출 소실이라고 부를 수 없다. 특정 actor와 raw/project 박스의 공간·시간 대응 검수, 가림 중 실제 가시성, tracker/표시 출력의 추가 대조가 필요하다. 이 자료로015/039/043의 모든 공백을 detector FN으로 확정하지 않았다. 026의 양호 관찰·028의 ID 전환·034의 서 있기·021의 문 옆 경로는 서로 다른 문제와 대조를 보존한다.

## FCOS 제안과 독립인 고정 비교 domain

총괄 승인으로 **45개 원본 전구간 전체 화면**을 주 domain으로 고정했다. 실패 근거·사용자 공백·대조 자료의11영상 합집합만 실행하고 전체45 비교라고 부르지 않는다. 전체 native 끝의 합은6,143.500233333초이며 이전 duration 합6,143.466866667초와006 마지막 프레임 지원 끝의 차이를 구분한다. metadata/원본/native-clock/설정 SHA와 실제 시작/끝/프레임 수는 `manifest.json` 각 영상에 담았다.

1초 간격 anchor는0부터 각 원본 전체 끝 전까지이며 총6,177개다. 각 입력은 anchor에 index8을 놓고16개의 목표 시각 `anchor+(i-8)*4/30`을 사용한다. 가장 가까운 실제 presentation timestamp에 대응하며 동률은 앞 프레임이다. 경계 밖은 첫/마지막 실제 프레임 반복으로 기록하고, 반복 mask·duplicate mask·unique native 수를 함께 남긴다. 반복을 새 관측으로 세지 않는다. 실제 입력의 최대 PTS를 `available_after_pts`로 기록해 미래 입력을 anchor 당시 경보로 바꾸지 않는다. 이 간격의 전체 시간 관측은 매 native 프레임에서 새 모델 출력을 계산한다는 뜻이 아니다.

정확한 실패 표본을 포함하는42개 supplemental 창은 주 분모에서 제외한다. root 고정 smoke는006124.991533333초·00766초·03090/94초·03140초·03434초·02867초의7개이며 원래 native frame indices와16시점을 담는다. 이들은 실행 계획이고 모델 smoke 성공 결과가 아니다.

C1–C8의 기존 normalized camera ROI는 authoritative detector metadata에서 그대로 secondary로 저장했다. C5 확장 view를 포함하고 새 ROI/사람 crop은 그리지 않았다. 주 wholeframe과 secondary ROI 어느 쪽도 FCOS 박스 존재로 입력을 허용/차단하지 않는다. 공간 resize/pad·모델별 해상도/head/정밀도와 대안 조건은 [총괄 protocol](EXP-0066-protocol.md) 및 해당 adapter 명세에서 별도 고정한다. 박스가 없는 encoder에 detector recall을 붙이지 않는다.

## 실제 실행·검증·산출물

```bash
.venv-cv-batch02/bin/python -m unittest discover -s tests -p 'test_fcos_miss_comparison.py' -v
.venv-cv-batch02/bin/python scripts/prepare_fcos_miss_comparison.py \
  --output /home/jhc7484/dev/sceneguard-ai/outputs/model-comparison/exp0066/cohort-v1
.venv-cv-batch02/bin/python runtime/model-comparison/exp0066/cohort/audit_output.py
```

준비는 실제 exit0,16개 집중 CPU 시험이 통과했다. 빈 frame 보존·raw/project/ROI 분리·정확한 동률·29.97 불규칙 native 시각·index8·미래 입력 시각·경계 반복·원래 cache hash·누락/중복/변경 PTS·크기/time_base·잘못된 bbox/score·run count·review version·기존 출력 거부를 확인했다. 이는 출처/시간/입력 계약 시험이며 행동 성능 시험이 아니다.

준비 모듈을 import하지 않는 별도 CPU 산술 감사에서45개 전체 계획의6,177+42창을 원래 native clock으로 재구성하고 모든16개 frame index/native PTS/시각·available_after·중복 수·7smoke를 대조했다. 원래160개 입력 해시가 그대로이며 native-frame-inventory는184,300행이다. 근거는 `runtime/model-comparison/exp0066/cohort/output-audit.json`이다. 원본 픽셀이나 모델을 사용하지 않았다.

| 산출물 | SHA256 |
| --- | --- |
| `scripts/prepare_fcos_miss_comparison.py` | `226940dc0a5346626a4ee971cc8d71c4d439a215ec847c03c5441b1d75d77a1d` |
| `tests/test_fcos_miss_comparison.py` | `f6002fb431648cf9fa01d3a9fa914fa8adfacc5a7fd2166004110820bb21bc3d` |
| `outputs/model-comparison/exp0066/cohort-v1/manifest.json` | `480b1410c568b9a038c7be6d124f7be1890b3b7375cbed43e87b165346a2aa18` |
| `outputs/model-comparison/exp0066/cohort-v1/summary.json` | `b1047ce989fa53c8d4613bebfbbd58c9b3985befc031c05d43dc74d82076594c` |
| `outputs/model-comparison/exp0066/cohort-v1/native-frame-inventory.jsonl` | `0500d75252da3c890ed4faaeb95df2f191169b8f073ae5ce1f379628ad1379c5` |
| `outputs/model-comparison/exp0066/cohort-v1/failure-evidence.json` | `b2b67e4809d3d2b9fd5af97e272703a7d9230e017f5b4fae4ad4ec65cacda66b` |
| `outputs/model-comparison/exp0066/cohort-v1/smoke-windows.json` | `8ee64caa28fed6b756aecf39c5d392c6b544f204ad12ed39ed617d727a3481c0` |
| `outputs/model-comparison/exp0066/cohort-v1/camera-domains.json` | `748043416feefa56ad4c83aecd745c375d0c48e56f2acd86ccd46f26483544f2` |
| `runtime/model-comparison/exp0066/cohort/current-review-snapshot.json` | `b962c5b7b7b879a9ba94fc8d9d6e6feef557b889a8db5d1ecade544ca27776b9` |

각 `plans/E01_XXX.json`의 SHA는 manifest에, 전체 산출물의 SHA는 output-audit에 있다. 실제 argv·작업 권한·코드 SHA는 `runtime/model-comparison/exp0066/cohort/command.json`/`.sh`, 로그는 `preparation.log`·`tests.log`·`output-audit.log`다. 기존 E: 자료를 정리하거나 외부 이미지/모델 API로 미디어를 보낸 작업은 없다.

이 worker의 CPU 전수 inventory·입력 준비는 완료했다. 사람별 완전한 누락/행동 GT는 미완성이며 source data의 제한으로 명시한다. 새 모델 smoke/전구간 실행·학습 head·박스/행동 의미 비교·새 애매한 장면 검수·최종 commit은 총괄과 각 모델 담당의 별도 작업이다. 후보 모델을 제외하거나 승자를 추정하지 않았다.
