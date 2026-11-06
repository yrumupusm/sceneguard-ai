# EXP-0065 — 기존 다운로드 자료의 정상행동 보강 감사

**추가 장소 Taejongdae에서 공식 `stand` 10구간·6원본·2시나리오 묶음을 찾았다.** 새 검증 후보에는 이 중 7구간을 제안할 수 있지만, 검증용 걷기와 균형 잡힌 새 장소 평가는 확보하지 못했다. 실제 다운로드된 원본/라벨 목록, 고정 보호 분할, 96원본의 새 SHA256·제한된 내용 중복 검사, 구간별 검수 후보를 저장했다. **학습 가능 라벨 0개, 학습·모델 실행·GPU 작업 0회**다.

2026-11-07. [후속 지침](EXP-0065-followup.md)의 데이터 보강 담당 범위다. 기존 EXP-0063/0064 학습·시험·45회귀와 모델·임계값·기본 파이프라인은 보존했다. 실행 시작의 웹 `pending --include-acknowledged`는 정상 조회되어 `requests=[]`였다. 기존 박스 정렬 관찰을 행동 의미 정답으로 승격하거나 재질문하지 않았다. 검수 미디어 생성과 최종 웹 전달은 root의 별도 범위다.

## 실제 목록과 명시적 라벨

공원 데이터 Training/Validation의 행동 라벨 ZIP 6개를 실제 읽었다. 행동 원본/라벨 **6,534쌍**, 명시된 배우/객체 사건 **33,796개**, 장소 10개·촬영일 26개다. 6,534개 모두 원본 ZIP member가 유일하게 대응한다. 라벨 JSON과 archive의 실제 member 경로·크기·CRC·라벨 SHA256을 보존했다. 원본 ZIP 전체 수백 GB를 다시 해시하거나 전체 드라이브를 조사하지 않았다.

| 공급 범위 | 행동 라벨 JSON |
|---|---:|
| Training 불법행위 1 / 2 / 3 / 4 | 1,104 / 2,208 / 1,056 / 1,056 |
| Training 정상행위 | 384 |
| Validation 불법/정상 통합 | 726 |

객체 전용 ZIP의 51,841개 still-image 라벨은 시간 행동 음성으로 만들지 않았다. 행동 라벨 오류 파일 124개는 선언 프레임 역전/범위 밖·배우 박스 대응 부재 등이 있어 격리했다. 경고나 시간 원점은 자동 보정하지 않았다.

다음 수는 공식 event의 배우/객체와 annotation class를 연결한 선언 구간 수다. 실제 행동·독립 사람 수·침입 정상 정답으로 인증한 수가 아니다.

| info.location | 원본 쌍 | moving | stand | wall_over | 라벨 오류 파일 |
|---|---:|---:|---:|---:|---:|
| busan_central-park | 187 | 0 | 0 | 0 | 7 |
| busan_children-grand-park | 681 | 0 | 24 | 1,019 | 12 |
| busan_citizen-park | 3,135 | 1,413 | 1,898 | 1,410 | 92 |
| busan_daesin-park | 192 | 0 | 0 | 0 | 4 |
| busan_geumgang-park | 225 | 0 | 0 | 0 | 1 |
| busan_minrak-waterfront-park | 663 | 0 | 0 | 0 | 6 |
| busan_national-temperament-park | 461 | 0 | 0 | 913 | 1 |
| busan_song-sang-hyeon-square | 167 | 0 | 0 | 0 | 0 |
| busan_taejongdae-amusement-park | 152 | 0 | 10 | 0 | 0 |
| busan_yongdusan-park | 671 | 0 | 4 | 1,374 | 1 |

기존 4장소 외 새 장소는 6개지만, 그중 명시적 moving/stand가 있는 곳은 Taejongdae뿐이다. 그 장소에는 stand 10구간만 있으며 moving과 wall_over는 없다. 나머지 새 5장소의 다른 불법행위 라벨을 `not climbing`으로 바꾸지 않았다. `moving`은 접근 후 돌아가기 정답이 아니며, `stand`는 문 앞 대기·접촉 후 미통과 정답이 아니다. 해당 어려운 음성의 명시적 전용 라벨 또는 완전한 사람 검수 구간은 이번에 확보한 수가 0이다.

## 보호·그룹·새 분할 제안

기존 v3의 **1,440개 원본 전체 배정**은 바꾸지 않았다. 고정 SHA256 `bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499`를 대조했고 기존 학습 671·검증 153·시험 296·사용자 제외 313·오류 격리 7을 유지한다. 실제 assignment를 기준으로 시험 296원본이 속한 8개 묶음을 보호했다. clip에 사용된 원본만 골라 보호하지 않았다. 별도로 회귀 45원본 전체를 잠금 해시로 보호한다.

같은 장소/행동군/시나리오의 여러 날짜·뷰, 같은 장소에서 시각이 겹치거나 닿는 모든 원본, 기존 원본 묶음과 SHA를 보수적으로 연결했다. 총 211개 메타데이터 연결 묶음이다. 서로 다른 행동 폴더라도 동시 촬영 가능성이 있으면 연결했다. 그룹은 실제 사건이나 독립 사람 수가 아니다.

`camera_code_from_filename=DF4` 같은 값은 **검증되지 않은 파일명 suffix token**이다. a/b/c도 검증된 카메라 ID로 해석하지 않았다. 제공된 info에 검증된 카메라 신원이 없으므로 `camera_metadata_verified=false`를 유지한다. 그룹 보호는 이 token의 정확성에 의존하지 않는다.

| 새 목록의 제안 구분 | 전체 member | 기존 원본과 다른 member | 메타 묶음 | 새 moving 구간 | 새 stand 구간 |
|---|---:|---:|---:|---:|---:|
| augmentation_train | 1,654 | 1,654 | 52 | 0 | 6 |
| augmentation_validation | 448 | 448 | 18 | 0 | 7 |
| excluded_user_scenario | 362 | 49 | 12 | 0 | 0 |
| new_evaluation_exposed_test_place | 484 | 484 | 16 | 0 | 20 |
| new_evaluation_reserved_place | 1,416 | 1,416 | 58 | 0 | 0 |
| new_evaluation_same_place | 541 | 541 | 19 | 0 | 2 |
| protected_exp0064_test | 327 | 31 | 8 | 52 | 95 |
| quarantine | 415 | 340 | 42 | 12 | 3 |
| retained_train | 758 | 118 | 23 | 114 | 136 |
| retained_validation | 129 | 13 | 4 | 0 | 0 |

표의 member 수는 **학습 원본 확보량이나 음성 수가 아니다**. target-normal 라벨이 없는 다른 행위 원본도 메타 목록에 포함된다. `retained_*`는 같은 원래 학습/검증 묶음에 속하는 새 member의 제안 위치다. 기존 원본을 비춘 행의 quarantine은 새 보강 연결 묶음의 준비 상태이며 기존 v3 배정을 다시 쓴 것이 아니다. 원래 배정 전체는 별도 `existing-partition-preservation.json`에 보존했다.

사용자 제외 wall 4-19–4-35·4-69–4-70은 양 끝을 포함해 유지한다. 새 Validation member까지 같은 조건을 적용한 제외는 362개이며, 기존 제외 313개를 보존한다. 시험 원본/사건/멀티카메라 closure에 연결된 다운로드 member 327개는 새 학습/검증에 넣지 않았다.

새 장소 중 target-normal가 없는 5장소는 장소 전체를 평가용으로 예약하되, 목표 행동 라벨이 부족한 상태다. 기존 heldout children-grand-park의 새 다른 촬영 자료도 평가 전용으로 제안하고 이미 시험 결과를 열어 본 장소라는 사실을 기록했다. Taejongdae는 새 학습/검증 제안용으로 사용하고 동시에 새 장소 평가로 세지 않았다. 원래 장소의 새 촬영 평가와 처음 보는 장소 평가는 구분한다.

**새 장소에 wall_over와 여러 정상행동이 모두 있는 독립 평가 cohort는 0개다.** 새 장소 목록 6개 또는 다른 행위 원본의 존재만으로 일반화 평가를 확보했다고 하지 않는다. 분할과 96원본 선택은 영상 내용 지문이나 모델 결과를 보기 전에 메타데이터/명시 class/고정 seed로 정했다. 임계값·모델 결과는 선택에 사용하지 않았다.

## 제한된 실제 내용·해시 검사

메타데이터 후보에서 partition/place/action/group 순환 방식으로 최대 **96개 새 원본 member**를 선택했다. 합계 **2,931,022,843 bytes**의 member를 메모리 상한 512MiB/파일 안에서 읽고 실제 SHA256을 계산했다. 파일을 풀어 대량 원본 복사본을 남기지 않았다.

기존 시험 296+회귀 45의 **341개 원본 전부**와 선택된 96개 새 원본에서 각각 상대 시점 10/30/50/70/90%의 5개 CPU 지문을 만들었다. 총 2,185개 지문 샘플이며 codec seek의 내부 preroll 디코딩 프레임 수와 같다는 뜻은 아니다. 작은 grayscale hash와 64bit 평균 기반 비교를 사용하고 원본 프레임은 저장하지 않았다.

| 실제 검사 결과 | 수 |
|---|---:|
| 보호 원본의 5시점 지문 완료 | 341 / 341 |
| 새 member SHA256·지문 완료 | 96 / 96 |
| 기존 전체 감사 corpus/앞선 새 선택과 exact SHA 중복 | 0 |
| 직접 의심 내용 match | 7 |
| 양쪽/같은 사건 묶음까지 보류한 원본 | 29 (11묶음) |
| 제한된 검사 통과·의미 검수 대기 | 67 |
| 학습 release | 0 |

정지 배경이 비슷한 촬영도 지문이 가까울 수 있다. 7개 match를 실제 재인코딩 중복으로 확정하지 않고 의심으로 남겼다. 실패/의심이 뒤에서 발견되어도 앞선 후보와 같은 이벤트/멀티카메라 묶음 전체를 보류했다. 비교 대상은 보호 시험+45 및 선택된 새 원본이다. 기존 학습/검증 전체에 대한 pixel 비교는 하지 않았으며, 그 범위는 기존 SHA/메타데이터 검사다. 시간 이동·crop·부분 중복·재인코딩 부재를 5시점으로 인증하지 않는다. 미선택 원본과 격리 묶음은 해제되지 않았다.

## 실제 구간 후보와 다음 검수 비용

96선택 원본 안의 명시 target actor-event 555개를 실제 라벨에서 읽었다. 0/1 frame origin 교집합 안에서 8개 중심 index를 제안하고 두 origin의 9개 annotation 위치가 모두 유일하고 같은 class인지 확인했다. 459구간(90원본·35묶음)의 annotation 중심이 완전했다. 내용 검사 보류를 제외하면 **269구간·63원본·24묶음**이다. 이 수는 정밀 행동 검수나 실제 중심 8프레임 native 디코딩 완료 수가 아니다.

모든 구간에 source SHA, ZIP/member, label SHA, actor/object/event, 선언 프레임·정수 초, label-only 8index와 9annotation 위치, 제안 ROI·다른 annotation class 및 내용 보류 상태를 저장했다. source SHA와 공식 행동 출처를 연결했지만 `native_center_decode_verified=false`, `semantic_ground_truth_verified=false`, `binary_training_label=null`, `training_eligible=false`다. ROI는 기존 폭 3배·높이 2배 맥락 합집합 정책의 제안이며, annotation 밖에 다른 사람이 없다고 가정하지 않았다.

우선 확인할 Taejongdae 자료는 2021/11/12의 family6/scenario56·57, **6원본·10개 stand actor-event·2묶음**이다. 56의 4원본/7구간을 보강 검증, 57의 2원본/3구간을 보강 학습으로 제안했다. 10개 모두 annotation 중심과 제한된 내용 검사는 통과했지만 실제 행동·다른 사람/ROI 혼입은 미검수다. DF4는 카메라 인증이 아니다.

전체 annotation-complete 목록을 모두 확인하면 459개 actor-event와 3,672개 제안 8시점 view 단위다. 우선순위 10구간은 80개 view 단위와 6개 원본 문맥을 검수할 수 있다. **실제 새 검수 이미지 생성·검수 시간 측정·사람 의미 판정은 0**이다. 이 수는 검수 작업 단위이며 소요 분이나 독립 사람 수를 추정한 값이 아니다. root가 전체를 한꺼번에 새 질문으로 등록할 필요는 없다.

새 walking 원본 중 기존 train 묶음에 남는 자료는 있지만, 원래 val을 몰래 섞지 않으면 **새 검증 moving 후보는 0**이다. 따라서 기존 검증 음성의 앉기 편중을 해소했다고 하지 않는다. stand 7구간의 실제 검수/입력 확인은 가능한 보강 축이며, 걷기·문 앞 대기·접근 후 돌아가기·접촉 후 미통과와 균형 잡힌 새 장소 양성/음성 촬영은 추가 주석/검수 또는 향후 수집 과제로 남는다. 지금 존재하는 공식 구간과 미래 확보를 구분한다.

## 다른 로컬 자료의 실제 확인 범위

AI-Hub 관제 CCTV의 행동 사건 JSON 269개와 269개 원본 ZIP 대응을 확인했다. Gathering63/Fight27/Falldown40/Crowd36/Flood53/Invasion50이며 회귀45는 모두 보호된다. 사건 caption에 걷기/서기가 언급되어도 배우별 정밀 정상 구간·박스 정답으로 바꾸지 않았다. 이번에 바로 사용할 수 있는 actor-normal interval 자격을 확인한 수는 0이다.

스마트 제조 데이터의 읽을 수 있는 Sublabel ZIP은 PNG 10,000/캡션 JSON 10,000의 정지 자료다. Training TS/TL 두 분할 ZIP은 현재 `zipfile` reader에서 `BadZipFile`이고 대체 `7z` 실행기도 없다. 시간 행동 자료를 확인했다고 하지 않으며, 그 안에 자료가 없다는 뜻도 아니다. 다운로드·대규모 병합/압축 해제는 하지 않았다. 이 미확인 범위를 검수·자료 없음으로 치환하지 않았다.

## 실행·재현·보존 근거

실제 실행 명령은 같은 저장소와 기존 CPU 환경의 다음 순서였다. 각 단계 출력은 `outputs/action-recognition/exp0065/augmentation-v1`의 새 파일에만 저장했다.

```bash
.venv-cv-batch02/bin/python -m unittest discover -s tests -p 'test_action_augmentation.py' -v
.venv-cv-batch02/bin/python scripts/prepare_action_augmentation.py inventory
.venv-cv-batch02/bin/python scripts/prepare_action_augmentation.py plan --max-new-files 96
.venv-cv-batch02/bin/python scripts/prepare_action_augmentation.py fingerprint
.venv-cv-batch02/bin/python scripts/prepare_action_augmentation.py other-local
.venv-cv-batch02/bin/python scripts/prepare_action_augmentation.py intervals
```

최종 고유 CPU 시험 **20개 통과**다. 시험/45 보호의 다른 행동군 동시 촬영 전파, 같은 시나리오의 다른 날짜, 새 평가 장소 전체 보존, 기존 train/validation 충돌 격리, 오류 member의 sibling 및 양쪽 의심 묶음 보류, 무주석 음성 금지, 두 origin의 9annotation 필요, fresh revision 허용/owned root 밖·symlink 거절을 검증했다. 실제 fingerprint 단계는 한 번 완료했다. source·label 및 모델 의미 검증을 합성 시험으로 대체하지 않았다.

기존 경로 재실행은 exclusive write로 거절한다. 재현 시 5단계 각각 `--output outputs/action-recognition/exp0065/augmentation-v2`처럼 **새 augmentation revision**을 사용한다. 기존 v1은 삭제/덮어쓰기하지 않는다. 현재 CLI 수정만 검증하려고 큰 inventory/미디어 지문을 재실행하지 않았다.

inventory producer는 `f9b217ae9f903cc65c2a39e18268913eaf3c287e077377829e3cadaccff54de0`, 최종 plan/fingerprint producer는 `6df3f0d9cb4f575f793bb9dbd2e3d0c81a466f6388deface67a4b350d0d077ec`이다. 실행 시점별 정확한 source snapshot은 `runtime/action-recognition/exp0065/augmentation/*executed.py`에 있다. 현재 최종 CLI/추가 metadata 단계와 20시험의 script SHA는 `608c2a71c29d62f0b10ac11415ef324dac9b46711a43ad0ba86ea60ebcad8504`다. 최초 metadata 초안은 내용 디코딩 전에 장소 예약 정책을 보완했고 `initial-metadata-proposal-before-decode/`에 보존했다. 초안·실행 producer·현재 코드를 같은 버전이라고 표현하지 않는다.

다음 SHA는 `augmentation-v1/` 아래 로컬 원문이다. 실제 소스 경로/ZIP member·원본·지문·라벨 원문은 로컬에만 보관한다.

| 근거 | SHA256 |
|---|---|
| `inventory.jsonl` | `c9085b6c691d333d60d215050dc1d722ab873352fffebdea4db4ab2c6910e09f` |
| `split-manifest.json` | `938bb20cf6189d6d04fb1f4ba5aafd6448341530c79a6e801db99888b553fa62` |
| `candidate-manifest.json` | `a1244de138b7f7366d5b05daacfa54a278e370c6effdb832b54dd3cdc01f6726` |
| `verified-candidates.jsonl` | `50c2749ee486e1f4a16e98f86f49a5abc19786ba7fa91c0126df2ce44b45d29b` |
| `fingerprint-summary.json` | `60e11934c02b59b1e104d87f53abf69dfee0e6d104ae62abe185fc6a95962dc2` |
| `candidate-event-intervals.jsonl` | `4547bf19bc108bb637db746b4d37ce7219c52c628c56e8be5bf114b6de1ec01e` |
| `interval-summary.json` | `67d4e994ba3bb09697cfefe94aefd38ce20ea7c1053e7c351bbbfe82bdbd556b` |
| `other-local-audit.json` | `f8494b3f456b117139f02427362654f61851e68301ee689bce597f5f5ba6489e` |
| `existing-partition-preservation.json` | `523ce7f67222baac5ea0b92a41e92f872c277d312ab82be78f5f15246ab6aef7` |
| `delivery-summary.json` | `3d0d02135da65d32e34c66aea2da06d10fe5ab23b69d1f25ad3d3ba1de27f7fc` |

영상·가중치·DB·큐·기존 audit/split/clip manifest를 바꾸지 않았다. 커밋·push·브랜치 전환·중첩 작업자는 없다. 이 작업의 실제 데이터 준비/관측·보호 검증은 완료했고, 학습 release·정밀 native clip 검증·의미 검수·성능/개선량·일반화는 미완료다. precision/recall/F1/개선량은 null이다. 최종 웹 검수 자료와 전달은 root가 별도로 기록한다.
