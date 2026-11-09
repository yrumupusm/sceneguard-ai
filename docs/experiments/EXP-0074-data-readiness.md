# EXP-0074 — 사람 라벨 감사와 고정 자료 내보내기

2026-11-09. **기존 검수 197프레임을 기준선용으로 고정했다. 수정 초안 71프레임은 완전성 미확인으로 별도 보류하고, 야간 index70/23.333초 한 프레임은 전체 제외했다.** 새 학습·모델 추론·GPU 작업·외부 이미지 수집·웹 변경은 없다. 이 문서는 데이터 준비 결과이며 다른 담당의 기준선 실행이나 성능 개선 완료를 뜻하지 않는다.

## 목적과 승인 범위

EXP67/71의 기존 사람 검수 결과를 정확한 이미지·좌표 그대로 재사용하고, EXP73의 명시적으로 승인된 대체 좌표 5개만 별도 수정 자료에 적용했다. 사용자가 관찰을 대화로 직접 전달했다는 현재 지시는 다른 모든 박스나 프레임 완전성의 승인이 아니다. 이미 승인한 주간1·야간4 좌표를 다시 묻지 않았다.

원본 승인·기존 manifest·검수DB·영상·초안은 변경하지 않았다. 출력 디렉터리는 새로 만들며 JSON/라벨/이미지를 배타 생성한다. 기존 출력 경로를 재사용하면 실패한다. 고정 manifest는 생성 직후 경로와 SHA256을 총괄에게 전달했으며, 이후 수정하지 않았다.

## 실제 사용 가능한 자료: 검수 197프레임

| 출처 | 학습 프레임/사람 박스 | 개발 프레임/사람 박스 | 명시적 빈 프레임 |
| --- | ---: | ---: | ---: |
| EXP67 confirmed-person-v1 | 50 / 151 | 25 / 31 | 0 |
| EXP71 confirmed-person-v1 | 72 / 182 | 50 / 25 | 개발 25 |
| EXP74 고정 합계 | **122 / 333** | **75 / 56** | **개발 25** |

모든 197프레임의 기존 이미지 SHA256·라벨 SHA256·PNG 해상도·YOLO 좌표 왕복을 확인했다. 기존 좌표와 박스 ID, frame ID는 그대로다. `image`와 `label`은 기존 산출물의 절대 경로이며 197장의 재인코딩이나 좌표 재계산은 하지 않았다. `split`은 `train`/`development`로 정규화하고 `confirmed_person_boxes`, `source_size`, `source_pts`, `event_group`, `capture_reservation`, `person_completeness_verified` 및 원본 manifest 경로·해시를 기록했다. EXP71의 기존 완전성 승인은 당시 내보내기·완료 기록을 근거로 가져왔으며 새 모델 제안을 정답으로 승격하지 않았다.

P05의 검수된 54–62초 사람 25프레임과 0–8초 명시적 빈 25프레임을 모두 개발에 포함한다. 원본 전체가 다른 행동 문맥을 포함한다는 이유로 정상 이동/빈 구간이나 사람 라벨을 제외하지 않는다. 행동·신원 정답은 별개이며 인증하지 않았다.

## 원본·사건·촬영 예약 분리와 한계

EXP70 `source-inventory.jsonl`, `split-proposal.json`, `group-closures.json`에서 원본 SHA/ID, `group_id`의 closure membership, 원래 촬영 예약을 연결했다. EXP70 조사 뒤 원본 SHA가 채워진 P05는 원본 ID를 통해 조사 결과의 정확한 SHA와 대조했다. 원본이 일치하지 않거나 예약 분할이 바뀌는 경우는 실패한다.

고정197 및 수정72를 합친 269프레임에서도 원본 SHA·사건 묶음·촬영 예약의 학습/개발 교집합은 각각 0이다. 학교45와 EXP64 시험296에 해당하는 보존된 341개 원본 SHA를 차단했고, inventory의 보호/사용자 제외 상태와 기존 closure 근거를 확인했다. EXP64 시험 및 연결 촬영/멀티카메라 보호를 해제하지 않았고 새 시험 자료를 학습·개발에 넣지 않았다.

**이 검사는 메타데이터·기존 화면 관찰에 따른 보수적 예약 일관성 검사다. 물리적으로 독립된 촬영·장소·카메라·배경임을 인증하지 않는다.** 개발 자료를 독립 일반화 시험으로 부르지 않는다.

특히 옛 case5의 정확한 원본 SHA와 촬영 메타데이터를 대조했다. EXP70 closure는 `aug-409dbbc92fa789ba34f9`의 `retained_validation`이며, 번호가 있는 촬영 예약에 속하지 않는다. 따라서 `capture_reservation=legacy-closure-aug-409dbbc92fa789ba34f9`로 명시하고 기존 개발25프레임을 유지했다. `capture-reservation-19`는 P26/P27/P28의 세 다른 group만 포함하므로 case5를 여기에 임의 배정하지 않았다. EXP65의 유사도/촬영 연관 보류는 해결되지 않았으며, 이 개발 자료는 기존 진단 범위다. 같은 장소·날짜의 실제 촬영 연관 가능성을 숫자상 교집합 0으로 해소했다고 해석하지 않는다.

## 수정 자료: 71보류 + 1전체 제외, 신규 완전 정답 0

EXP73 repaired-drafts 72프레임/169개 초안 박스를 보존해 승인5를 적용했다. 주간 index60은 밑변을 올린 최종 승인 좌표를 사용하고 이전 수정안은 사용하지 않는다. 정확한 좌표는 로컬 승인·보완 manifest에 보존했다. 야간 index71/72/73/75는 승인 파일의 네 좌표를 그대로 썼다. 승인 대상 외 좌표와 ID는 그대로다.

| 구분 | 프레임 | 박스 | 사용 상태 |
| --- | ---: | ---: | --- |
| 별도 수정 보류 | 71 | 167 = 승인 대체5 + 미확인162 | 완전성 미확인, 표준 학습/전프레임 지표 금지 |
| 야간 index70 / 23.333초 | 1 | 기존 진단 후보2 | 프레임 전체 제외, YOLO 파일 없음 |
| 합계 | 72 | 169 | 신규 완전 사람 정답0 |

배경으로 승인된 17개 후보/13프레임 제거를 그대로 유지했다. 그 제거는 특정 위치의 해당 후보에 한정하며, 남은 작은 박스나 프레임 전체를 빈 배경/정답으로 만들지 않는다. 전체72의 미확인 후보는 제외 프레임의2개를 포함해164개다. `incomplete-yolo/`의 71개 파일은 미확인 후보까지 담은 **불완전 수정 아티팩트**다. 이 폴더에는 학습용 dataset YAML을 만들지 않았고 `standard_train_eligible=false`, `full_frame_metrics_eligible=false`, `person_completeness_verified=false`, `training_release=false`를 기록했다.

세 원본의 실제 바이트 SHA를 다시 읽어 확인하고, 72프레임의 native PTS/RGB SHA를 대조했다. 승인 화면5개는 이전 PNG 바이트를 그대로 복사했고, 나머지는 같은 원본 RGB에서 새 PNG로 저장했다. 72이미지·71라벨 해시와 초안 좌표 왕복을 확인했다. 모르는 야간 작은 후보만 지워 나머지를 완전 정답으로 내보내지 않았다.

## P01의 실제 미해결 범위와 최소 추가 확인 후보

P01/R03은 승인된 상단 배경 후보17개를 제거한 뒤에도 **남은 박스의 실제 사람 대응·중복·누락과 완전성**이 미해결이다. 월담 장면이라는 이유로 사람 검출 자료 전체를 거절하지 않는다. 완전성까지 확인되면 예약된 개발 사람 자료로 사용할 수 있으나, 현재24프레임 전체는 보류다.

남은 먼 산책로의 작은 후보 위치는 이미 제거한 배경 위치와 다르며 정확한 영역은 로컬 검수 패키지에 기록했다. 겹치는 몸통 박스와 작은 원거리 박스가 실제 서로 다른 사람인지/같은 사람의 중복인지는 자동 결정하지 않았다.

구조 감사는 IoU≥0.5 또는 작은 박스 면적의 겹침≥0.9인 쌍을 **확인 후보**로만 기록한다. R01 index57/61 및 P01의15프레임이 해당하며, 이는 시각적 중복 정답이나 자동 병합 규칙이 아니다. P01은 index168/170/171/174/175/176/177/178/185/186/187/188/189/190/191이다. R02의 구조 후보0도 완전성이나 나머지 박스의 승인을 뜻하지 않는다.

총괄이 선택한 최소 우선 확인 묶음은 **P01 index168/175/185 = 56.0/58.333333/61.666667초의 3장**이다. 현재 남은 근접/원거리 문제를 좁혀 확인할 후보로 기록했으며, 새 질문·검수 렌더링은 총괄 담당이다. 이3장이 다른21장의 정답을 대신하지 않는다. 이미 받은 관찰이나 승인5를 다시 확인하는 범위가 아니다.

## 웹 검수 및 기존 승인 보존

WEB-0005의 `pending --include-acknowledged` 읽기 전용 조회는 성공했고 처음 확인 결과는 빈 목록이다. 이어 EXP67/71/72/73/74의 현재 저장된 질문·답변13건을 실제 읽고 바인딩을 확인했다. 최종 조회도 미처리0건이다. EXP67/71의 정확한 answer version·바인딩은 기존197프레임과 일치한다. EXP71 좌표DB는 `mode=ro`로 읽어 최신 저장 좌표가 이미 수락된 `after.json`과 같은지도 재확인했다.

EXP73 주간 answer_version2와 야간 answer_version1은 승인 파일과 일치한다. 주간 답변 메모의 day-bottom-v2 revision/이미지 SHA도 대조했다. 현재 조회에 EXP74의 모든 박스에 대한 새 명시적 완전성 승인은 없으며, 직접 전달된 관찰을 그 승인으로 해석하지 않았다. DB acknowledge/resolve/질문 생성 등 쓰기 작업은 수행하지 않았다.

## 실행·검증과 고정 산출물

기존 CPU 환경만 사용했다. 수정 원본 디코딩은 PyAV16.0.1/Pillow12.3.0과 기존 `.venv-pose-batch03`에서 수행했다. 모델·가중치·seed는 해당 없고 원본은 1920×1080/3FPS다.

```bash
python3 scripts/prepare_exp0074_person_data.py freeze \
  --output outputs/model-comparison/exp0074/person-data-v1
.venv-pose-batch03/bin/python scripts/prepare_exp0074_person_data.py corrections \
  --output outputs/model-comparison/exp0074/label-corrections-v1
python3 -m unittest tests.test_exp0074_person_data -v
```

위 출력 경로는 이미 고정되어 있으므로 재현은 새 경로를 지정한다. 기존 경로 실행은 의도적으로 실패한다. 시험14개가 통과했다. 실제 원본 좌표/해시 보존, 잘못된 승인 바인딩·완전성 승격 거부,17제거 유지, 야간 전체 제외, 분할 중복 거부, 불완전 파일 분리, 파일 변조 감지, 배타 생성을 검사했다. 처음 원본 매핑에서 P05 inventory의 미기록 SHA를 발견해 원본 ID＋EXP70 실측 SHA로 연결을 보완한 뒤 고정했다. 이것은 라벨 정확도·검출 재현율·행동 성능 측정이 아니며 해당 값은 미측정이다.

`outputs/model-comparison/exp0074/` 아래의 주요 파일과 SHA256:

| 파일 | SHA256 |
| --- | --- |
| `person-data-v1/manifest.json` | `01a08a3d42e610a3489b05859c9425ffe462b3709f46f967ea4537a48df2cf90` |
| `person-data-v1/validation.json` | `7d8c7f610306186b80f8ede847ab99fa9363bac46ccfea0c5bbbf21fdce3248e` |
| `person-data-v1/audit-report.json` | `4ba58398c7880fdddd662fdec916c4cab5da35215d9aaef4e4fa976ed81848ce` |
| `label-corrections-v1/manifest.json` | `39f467258ff66ccf685a362e4fc53f910e9b11df084d070767cb0e68c9a9d1bf` |
| `label-corrections-v1/validation.json` | `2191a6559a34ab210c78d3b815927b4475a3222d721e89fa87bbb49b92ebe540` |
| `label-corrections-v1/structural-duplication-candidates.json` | `ed7b0615b94be31ca1baa46a5890809dd80fbecb35384a0bb15911aa5f5d074a` |
| `label-corrections-v1/background-removals.json` | `c56dea94093c42c07ac8d1c61bfd6b762a9fa7f374120b94be9d648f35827c46` |
| 각 폴더 `web-answers-read-only.json` | `c5b707f84f9a31fcbce39b7f5497f24bdccdc572f05cf077f655d50aa9199117` |

각 `artifact-hashes.json`에 모든 해당 출력 파일 해시를 기록했다. `exporter-source.py`도 고정했다. 기준선 manifest를 먼저 내보낸 시점의 exporter SHA는 `17fe561a24cd387016908c103bee8687b58b897a239c3d4dbe7aad6861d68115`, 수정 내보내기 및 최종 스크립트 SHA는 `2a68f234e3ac5afe9dd19603e93dd5cba2ecd60144408dee882042853cc9cb80`다. 기준선 고정 후 추가한 correction 명령을 기준선의 코드 이력으로 소급하지 않았다. 시험 파일 SHA는 `178d0c602e59296c9deb480db129adbb828b669707beb63c773f17da3cf7581e`다.

주요 기존 runtime 근거(원본 불변, 전체 경로와 해시는 audit-report에도 기록):

| `runtime/model-comparison/` 아래 파일 | SHA256 |
| --- | --- |
| `exp0073/coordinate-approval-v1/approved-replacement-boxes.json` | `1c0f45ed1fb1e11e485d6202f585abdfc52d88c2b63de97f185ce9146b640e63` |
| `exp0073/day-bottom-v2/night-four-box-approval.json` | `07259408bab57fd856119d7d77fbbe7b16faecb27f3011f9ed090959b3937092` |
| `exp0071/coordinate-completion-v1/completion-scope.json` | `2bde66966c2f80acefec1a64a96a86d1cfa9f56cb93013d0c6c46848c7d2399b` |
| `exp0071/coordinate-completion-v1/after.json` | `a91ee9e69956e6641723a371da407044eeb082ce8bf6d2519a24a10ae8074a50` |
| `exp0071/review-application-v1/resolved.json` | `976ac307bb1a2010f74ca00490f0a2b47c2d43b1dcc69333e37cc1cbdf734a1d` |
| `exp0067/review-application-v1/acknowledged-answers.json` | `0acf61f4b9f43d067660a20dc57e43bc9bf5d56222ec82ad1a8a94cd6a15c902` |
| `exp0067/review-application-v1/resolved-answers.json` | `293500265a96275ec8abfe75784c1c9b1b5646e7e4d6c926f747a96e90768c10` |

기준선에는 고정197만 전달했다. 수정71의 편입에는 남은 박스·프레임별 완전성의 실제 확인이 필요하며, 제외1은 현재 보류를 유지한다. 기존 개발 자료의 촬영 독립성 한계와 새로운 독립 시험 부족도 남는다.
