# EXP-0063 — 첫 행동 학습 전 월담 원본·라벨 감사

- 날짜: 2026-11-06 (KST), Orca supervised audit worker.
- 범위: 사용자 제공 AI-Hub 173 월담 Training 원본/JSON, binary climbing/not climbing 실험의 데이터 준비 근거.
- 기준 HEAD: `3692a93791307cba3e2557a85c8f142edea5e737` + 미커밋 감사 코드. 실제 코드 SHA256는 로컬 `summary.json`에 기록한다.
- 상태: 1,056쌍 전체 SHA256·packet PTS·라벨 감사와 원본 그룹 분할 제안 완료. 시간/행동 의미 검수와 학습 가능 음성 확보는 미완료다. 학습/기본 모델 변경/정확도 측정은 이 감사 범위 밖이다.

## 목적과 보호 범위

처음부터 프레임을 무작위로 분할하지 않고 원본 영상·동시 촬영·촬영 세션을 먼저 묶는다. JSON의 선언된 사건/배우 박스와 실제 MP4 메타데이터·native packet PTS를 대조하고, 원본·라벨 해시와 제외 사유를 보존한다. 기존 production, all45 회귀 데이터와 과거 출력은 변경하지 않았다. GPU·모델 실행·다운로드·미디어 업로드·커밋·푸시는 수행하지 않는다.

작업 시작 시 `docs/WEB_REVIEW_WORKFLOW.md`의 읽기 전용 `pending --include-acknowledged`를 실행했으며 반환값은 `{"requests": []}`였다. 기존 웹 DB를 수정하지 않았다. 이번 데이터의 의미/박스/시간 검수는 별도 미완료 상태다.

## 입력과 제외

데이터는 AI-Hub 173의 `01.데이터/1.Training`을 기준으로 한다. 원본은 `원천데이터/TS_행위(불법행위)데이터2/1.불법행위/4.월담행위`, 라벨은 `라벨링데이터/TL_행위(불법행위)데이터2/1.불법행위/4.월담행위`만 읽는다. 정확한 로컬 절대 경로는 Git 제외 manifest와 실행기 기본값에 보관한다. 정상행동 ZIP 및 다른 범주는 포함하지 않았다. 라이선스/재배포 가능성을 이 감사로 인증하지 않는다.

초기 디스크 명단은 MP4 1,056개와 JSON 1,056개다. 상대 폴더 경로와 stem으로 쌍을 확인하며 basename만으로 합치지 않는다. 사용자 제외 범위 `4-19…4-35`, `4-69…4-70`은 양 끝 포함 313쌍이고, 남은 743쌍을 후속 실험 후보로 표시한다. 제외 원본도 SHA/packet 검사를 하되 split은 `excluded`로 고정한다.

| 포함 장소 | 원본 수 | wall_over 사건 | stand 사건 | 기타 선언 사건 |
| --- | ---: | ---: | ---: | --- |
| busan_citizen-park | 236 | 494 | 0 | 없음 |
| busan_yongdusan-park | 279 | 1,282 | 2 | trash_dump 3 |
| busan_children-grand-park | 96 | 399 | 3 | 없음 |
| busan_national-temperament-park | 132 | 837 | 0 | damage_to_facilities 1 |

선언 actor/object를 모두 일치시키고 그 사건 프레임 구간에 있는 annotation의 `class_name`으로 사건 종류를 집계한다. 사람 박스 수·동시 카메라 뷰 수를 독립 사건/정답 수로 취급하지 않는다. 포함 자료에서 wall_over 3,012, stand 5, trash_dump 3, damage_to_facilities 1 사건이 확인됐다. annotation은 각각 42,074 / 253 / 49 / 12개다.

## 시간·박스 해석과 검수 필요성

첫 실제 MP4는 H.264, 1,920×1,080, 3 fps, stream 선언 361프레임, 120.333333초다. JSON은 fps=3, frame=361, video_length=120초다. 정수 초 video_length와 마지막 프레임 노출을 포함하는 실제 stream duration은 구분한다. `ffprobe` 대신 기존 `.venv-cv-batch02`의 PyAV 16.0.1을 사용한다.

예를 들어 첫 영상의 사건은 start_time=29초, ev_start_frame=89이다. origin=0이면 프레임 시각은 29.666667초, origin=1이면 29.333333초다. 종료 104도 각각 34.666667/34.333333초다. 전체 포함 사건에서 frame/fps−정수초 차이가 0, 1/3, 2/3초로 바뀌므로 단일 고정 오프셋을 강제로 적용하지 않는다. 정수 초의 양자화만으로 0/1 기준을 확정할 수 없다. manifest는 두 가설의 CFR 시각과 sorted native packet PTS를 함께 보존하며 `frame_origin=unresolved`다.

| origin=0 가설의 프레임 시각−선언 초 | start 경계 수 | end 경계 수 |
| --- | ---: | ---: |
| 0초 | 1,050 | 1,000 |
| +1/3초 | 1,029 | 1,062 |
| +2/3초 | 942 | 959 |

origin=1 가설은 위 각 차이에서 1/3초를 뺀다. 수치상 더 가까운 가설만으로 실제 box/action alignment를 인증하지 않는다. 원점이 바뀌면 3 fps에서 박스와 영상이 1/3초 이동하므로 빠른 월담의 시작/착지 검수가 필요하다.

포함 741파일은 두 원점 모두 index bounds에 들어가지만, children의 scenario62 한 파일과 national의 scenario66 한 파일은 선언 frame361을 사용한다. 총 361프레임인 영상에서 361은 origin=0 범위를 벗어나고 origin=1 범위에는 들어간다. 원본 ID는 로컬 manifest에 남긴다. 이는 해당 파일의 1-based 경계 근거로 보존하지만 전체 JSON의 의미/시간 원점을 자동 확정하지 않는다. 로컬 영상의 마지막 비교 패널은 가설별 bounds 밖임을 명시한다.

박스는 `[[x1,y1],[x2,y2]]`의 두 모서리로 읽고 finite·순서·영상 경계를 검사한다. actor_id와 object_id가 모두 맞는 사건 범위 박스만 연결한다. 포함 JSON 구조/박스/배우 연결 오류는 0건이며 sparse box 사건 24건과 actor/object/frame 중복이 있는 파일 4개는 경고로 남긴다. 결측 박스를 보간하거나 다른 배우 박스로 채우지 않는다.

`stand` 5사건은 yongdusan scenario52 한 영상 2사건, children scenario61 한 영상 1사건과 scenario62 한 영상 2사건이다. 총 3원본·2장소이며 보수적 scene group도 2개다. stand/trash/damage가 있는 원본 모두 wall_over 사건도 가진다. 따라서 배우의 stand 라벨을 영상 전체의 not climbing 정답으로 승격하지 않는다. 라벨 없는 구간/인물도 unknown이다. 생성한 학습 음성 라벨은 0개이며 모든 원본의 `training_eligible=false`다.

9개 non-wall 선언 사건 구간과 같은 원본의 선언 wall_over 구간은 서로 겹치지 않는다. 이는 **선언 라벨상의 비중첩**이며 다른 인물/미주석 행동이 없음을 인증하지 않는다. 음성 후보를 전혀 찾을 수 없다는 뜻도 아니므로, 배우·시간·전체 장면 의미를 로컬에서 확인할 후속 후보로 보존한다.

| 선언 class | 사건 수 | 8 native frames 이상 | 16 native frames 이상 |
| --- | ---: | ---: | ---: |
| wall_over | 3,012 | 2,881 | 1,288 |
| stand | 5 | 5 | 3 |
| trash_dump | 3 | 3 | 2 |
| damage_to_facilities | 1 | 1 | 0 |

3 fps에서 8개 프레임의 첫–마지막 시각 span은 2.333333초, 16개는 5초다. 프레임 수는 inclusive `(end-start+1)`이며 단순 `(end-start)/fps`와 다르다. 이 수는 선언 라벨 길이이며 실제 행동 완료/독립 사건/검수된 음성 수가 아니다. 두 origin의 index 교집합 `[start,end-1]`은 후속 **가설적 label-native interior**로 통계만 보존한다. 이 정책도 시간 의미/배우/장면 음성을 검증하지 않으므로 학습 라벨을 확정하지 않는다.

wall_over span의 최소/중앙/최대는 0.333333 / 4.333333 / 73.333333초, stand는 2.333333 / 5 / 66.333333초다. 두 origin 교집합까지 적용하면 8/16프레임 이상 wall_over는 2,577/1,127사건, stand는 4/2사건이다. 원래 inclusive 길이 2,881/1,288을 이 보수적 교집합의 수로 대신 쓰지 않는다. 전체 histogram과 기타 class 분모는 `event-statistics.json`에 남겼다.

## 원본 그룹과 분할 제안

프레임/크롭 추출 전에 `split-manifest.json`을 저장하도록 구현했다. 각 원본을 노드로 두고 다음 연결의 전이적 폐포를 사용한다.

1. 명시된 location+date_captured의 같은 달력 날짜. 같은 날의 시나리오·a/b/c 뷰·오버랩 세션을 보수적으로 모두 연결한다. 자정을 넘는 영상은 양쪽 날짜에 연결한다.
2. 같은 location+scenario는 날짜가 달라도 연결한다. 재촬영/유사 배경의 누수를 줄이는 보수적 선택이다.
3. 같은 location의 실제 선언 capture interval이 닿거나 겹치면 별도 overlap 근거도 저장한다.
4. 원본 MP4 SHA256가 같으면 location에 관계없이 같은 component에 둔다. 다른 location이 합쳐지거나 명시 메타데이터가 부족한 component는 quarantine한다.

분할 장소는 모델 결과/라벨 수를 보지 않고 포함 원본 수가 작은 순서, 동률이면 location 문자열 순서로 고정한다. test는 children-grand-park 96개, validation은 national-temperament-park 132개, train은 citizen+yongdusan 515개를 제안한다. location-held-out 형태가 가능하다는 것은 충분한 독립 장소/음성 클래스가 확보됐다는 뜻이 아니다. validation에 stand가 없고 training stand도 yongdusan 한 그룹의 2사건뿐이라 현재 자료만의 이진 학습/평가는 불충분하다.

실제 connected component는 전체 5개다. citizen은 날짜/시나리오 연결이 없는 114개와 356개 component로 나뉘지만 모두 train에 유지한다. 나머지 세 장소는 각각 한 component다. 그룹 메타데이터 ambiguity에 의한 quarantine는 0개이며 전체 시간 라벨은 별도 미검수 격리 상태다. 완전 일치 source SHA/JSON SHA duplicate는 각각 0그룹이다.

분할 필드는 원본 그룹 소속이다. 시간 원점의 불확실성은 `training_blockers`와 `training_eligible=false`로 별도 격리하며 분할 제안을 학습 승인으로 읽지 않는다. SHA는 byte-identical 복제만 탐지하며 재인코딩/다른 길이 복제 및 location/date의 사실성은 독립 인증하지 못한다.

## 로컬 산출물과 재현

모든 대용량/미디어 산출물은 Git에서 제외되는 `outputs/action-recognition/exp0063/data-audit/` 아래에만 저장한다.

- `inventory.jsonl`, `manifest.jsonl`: 모든 원본/JSON 상대 ID, 제외 사유, 실제 경로, 크기, SHA256, 메타데이터, 라벨 검사와 시간 가설.
- `packet-pts.jsonl`: 전체 video packet의 PTS/DTS/duration/size와 time_base. B-frame의 demux 순서와 presentation 순서를 구분한다.
- `exclusions.jsonl`, `errors.jsonl`, `events.jsonl`, `summary.json`: 제외 명단, 오류/경고, actor-event별 근거, 범위별/장소별 집계와 provenance.
- `split-manifest.json`: 원본 연결 근거·component·장소 분할 제안, 해시 바인딩, quarantine와 학습 차단 이유.
- `event-statistics.json`: class별 길이 분포·8/16프레임 분모·두 origin 교집합·non-wall 사건과 wall_over 중첩 여부.
- `regression-overlap.json`: coordinator의 `baseline/attempt-002/baseline-lock.json`에 고정된 regression-only 45영상 SHA256와 1,056개 action source SHA256의 비교. 정확 바이트 중복은 0개다. 기존 회귀 파일의 수정/재실행은 하지 않았다.
- `overlays/`, `overlay-manifest.json`: split 저장 후만 만드는 로컬 원본 검수 JPEG/H.264. 양쪽 패널에 origin=0/1, 실제 decoded index/native PTS, 선언 배우 박스를 구분해 표시한다. 사용자 의미/시간 검수는 pending이며 클라우드 이미지 도구로 열지 않는다.

로컬 검수 산출물은 JPEG 6개와 H.264 MP4 6개다. 네 장소의 사례, 두 배우가 순서대로 월담하는 사례, source 마지막 frame361까지 이어지는 긴 stand 사례를 포함한다. 각 선택 사건 전체와 전후 12 native frames(4초)를 보이고, 두 배우 표본은 해당 원본의 선언 사건들을 모두 포함한다. 영상 합계 415프레임·138.333333초이며 6개 모두 실제 CPU decode 프레임 수·크기·SHA256·saved split 바인딩을 확인했다. 긴 사례는 212프레임이고, 이 수와 전체 감사의 `frames_decoded_by_audit=0`는 서로 다른 단계의 기록이다. 인코딩/바인딩 확인은 의미 검수가 아니다.

```bash
# 저장소 루트에서 실행
.venv-cv-batch02/bin/python scripts/audit_action_dataset.py --workers 2 --code-sha "$(git rev-parse HEAD)"
.venv-cv-batch02/bin/python scripts/audit_action_dataset.py --verify-regression-lock outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json
.venv-cv-batch02/bin/python scripts/audit_action_dataset.py --statistics-only
.venv-cv-batch02/bin/python scripts/audit_action_dataset.py --overlays-only
.venv-cv-batch02/bin/python -m unittest discover -s tests -p test_action_dataset_audit.py -v
```

기존 `manifest.jsonl`/`summary.json`이 있으면 원본 감사의 덮어쓰기를 거절한다. 재감사는 `--output`으로 새 로컬 경로를 지정한다. 실행 환경은 Python 3.10.12 / PyAV 16.0.1 / WSL2 Linux 6.6.87.2, CPU 두 thread다. ffprobe·GPU·torch 모델은 사용하지 않았다. 테스트 17개가 통과했다. 합성 영상의 실제 H.264 encode/decode와 두 origin overlay, actor별 class, scene 중첩, regression-only 해시 일치 시 차단까지 포함한다.

packet count/stream header 일치는 full decode 프레임 수 검증과 구분한다. 이번 전체 감사는 디코딩 없이 packet을 끝까지 읽으며 source SHA와 JSON SHA를 스트리밍 계산한다. 검수 overlay만 저장된 split 이후 일부 프레임을 CPU 디코딩한다. precision/recall/F1·일반화 성능은 측정하지 않는다.

실측 원본 총량은 32,404,620,091 bytes, video packet 합계는 381,216개다. 모든 1,056파일이 H.264/1920×1080/3fps/stream 선언361/packet361/120.333333초이며 PTS 누락·중복·3fps grid 불일치·DTS 비단조·라벨 fps/해상도/stream frame 수 불일치는 0건이다. 전체 label 1,056개와 source 1,056개 해시를 남겼고 검사 오류는 0건, 전체 sparse event 경고79건·중복 actor/object/frame 경고파일9개다. 실행기 monotonic 경과 시간은 690.026832초이며 CPU 해시/전체 demux/JSON 검사를 포함한다. 입력 처리 성능이나 모델 FPS를 뜻하지 않는다.

source manifest SHA256는 `8fef23cf8410a27f64a43d1ae5bba1e461e176e549ccf908a213c0cbaa0d9c69`, split SHA256는 `7c9648bbd087e5ff688fa47ca4946c04024ca772d8554da857547f726daaa3b6`, packet PTS SHA256는 `5bda376a97188bccffa41295a74ab766a59bf3ba1ab66326cb5b66d3a17f1c54`다. split을 저장한 뒤 통계·all45 exact-hash 대조·overlay 순서로 진행했다.

## 남은 판단

로컬 검수에서 실제 actor box가 어느 origin에서 맞는지, 선언 사건의 시작/끝이 목표 climbing과 일치하는지, stand/기타 행위와 동시 wall_over가 어떻게 겹치는지 확인해야 한다. 의미를 확인한 사람의 구간 음성 또는 별도 승인된 정상 자료 없이 unknown을 음성으로 전환하지 않는다. 작은 두 훈련 장소·한 검증 장소·한 테스트 장소의 한계와 3 fps의 빠른 동작 관측 한계를 유지한다. 이 문서는 감사·분할·검수 준비의 결과이며 이진 학습 완료 또는 production 적용 근거가 아니다.

마무리 단계에서 coordinator가 정상행동 자료의 사용자 추가 승인을 전달했다. 현재 산출물은 승인 이전에 감사한 월담-only snapshot으로 보존한다. 정상 자료·새 combined split은 coordinator의 별도 revision이며 이 manifest/분할을 조용히 바꾸지 않는다. 요청받은 trainer/baseline/config의 제한적 읽기 전용 peer check는 로컬 `peer-review.json`과 Orca status로 별도 보고했으며, 전체 독립 검토 또는 GPU 실행 검증으로 취급하지 않는다.
