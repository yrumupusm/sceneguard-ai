# EXP-0065 저장 행동 진단·자료 보강 독립 검토

2026-11-07. **최종 판정: 저장 진단·선정 미디어·보강 자료 감사와 아래 정확한 해시의 공개 보고서는 검토 범위에서 통과했다.** 실제 45개/52참조, 25개 미디어, 6,534개 라벨, 96개 보강 후보의 제한적 중복 검사와 33개 공개 지표를 독립 대조했다. 발견한 관측 분류·미디어 출처 연결·실패 그룹 격리 문제는 보완됐고 해당 실제 결과를 다시 확인했다. 사람 행동 성능·침입 개선·새 장소 일반화는 미측정이며 학습 release는 0개다. 모델·가중치·임계값·EXP-0062 AFTER는 고정하며 추가 학습·추론·운영 채택을 승인하는 문서가 아니다.

독립 검토자는 구현·원본·과거 출력·공유 큐/DB를 수정하지 않았고 GPU·모델·다운로드를 실행하지 않았다. 배정된 검토 문서와 `runtime/action-recognition/exp0065/independent/`만 작성한다. 원본 픽셀을 클라우드 이미지 도구로 전송하지 않는다. 실제 웹 전달·게시 완료는 별도 증거가 필요하다.

## 승인·검수·고정 입력

`EXP-0065-followup.md`, 웹 검수 절차와 현재 지침을 읽고 `pending --include-acknowledged`를 조회했다. 조회는 성공했고 미처리 답변은 0개였다. 기존 EXP-0063의 여덟 답변은 표본 박스 정렬 관찰이며 전체 행동 의미·정밀 시작/끝의 사람 정답으로 승격하지 않는다. 기존 45개는 계속 회귀·진단 전용이고 이미 열어 본 시험을 학습·검증·독립 신규 시험으로 옮기지 않는다.

| 고정 입력 | SHA256 |
|---|---|
| baseline attempt-002 lock | `3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40` |
| EXP-0064 plan v2 | `f8bea6c8b4b36d5d09daf8f3b43a7e8923319ef5bde3b5c4e5cd5f00f0f7cb17` |
| EXP-0064 inference result | `b465170efe203655deb76f857549101180e6ce56171ae510c69347595d7e34a8` |
| 실제 reference after-manifest | `c3b43879997033661ac84eb8e8406e328fee95b6779a97ace1f317500a602d19` |
| 기존 AFTER scoring | `cc329d88869d5a7b5815693973945158862c3d6900f95ae59a8a029379e4099a` |

원래 PR에서 경로 후보로 언급한 `evaluation-manifest.json`은 `videos[]` 정답 목록이 아니라 평가 출처와 산출물 해시 묶음이다. 실제 고정 `after-manifest.json`과 `after-scoring.json`의 계약을 확인해 담당자에게 전달했다. 최종 진단은 기존 해시 검사를 제거하지 않고 해당 정답·평가 파일과 평가 receipt를 연결한다.

## 실제 52참조 독립 재계산

구현 모듈을 import하지 않는 별도 `audit_saved_coverage.py`로 모든 계획·3,573개 점수의 입력·가중치·영상 연결을 읽었다. 공식 사건과 기존 prediction의 gate 및 confirmation evidence 시간 관계를 이분 그래프로 구성해 최대 매칭 37개를 독립 재현했고, 원래 report의 각 TP 연결·누락 15개 목록을 확인했다. 새로운 행동 점수의 시간 겹침은 그 사람·그 문에 대한 TP가 아니다.

| 사건 시간대 진단 | 전체 52 | 기존 확인 대응 37 | 기존 확인 누락 15 |
|---|---:|---:|---:|
| 넘기 후보 점수와 시간 겹침 | 33 | 26 | 7 |
| 입력은 있지만 점수 0.5 미만 | 13 | 8 | 5 |
| 실제 부분 관측만 있음 | 5 | 2 | 3 |
| 해당 시간대 실제 관측 입력 없음 | 1 | 1 | 0 |

원래 PR은 부분 창의 예정 시점 중 하나가 사건 시간대에 있으면 실제 관측도 있는 것으로 분류했다. E01_020 `official-row-001`은 예정 창이 겹치지만 실제 관측은 모두 시간대 밖이다. 담당자가 실제 관측 시점만 사용하도록 보완했고, 독립 계산도 원래 33/13/6/0에서 33/13/5/1로 바뀌었다. 이 사건은 기존 확인 **대응** 그룹이므로 누락 15개의 7/5/3 구성은 변하지 않는다. 최초 nominal 계산은 runtime `original-pr-nominal-partial/`에 보존한다. 중간 메시지의 대응/누락 분할 오기는 즉시 정정했으며 최종 표와 oracle JSON이 정확한 값이다.

467개 후보 창은 같은 track의 연속 창 193개 검수 묶음으로 표시된다. 묶음은 사람 수나 독립 사건 수가 아니다. 정상 참조 11구간에서 전체 8시점이 포함되는 후보의 구간별 대응은 12개이며, 경계에 걸친 창과 구분했다. 동일 대상·문 대응 검수 전에는 오경보 정답으로 확정하지 않는다. 공식 사건 바깥은 자동 음성이 아니다. 006 미확정 1개, 008 의미 보류를 유지한다.

## 진단 계약·시험·실제 산출물

최종 소스는 TP truth ID 중복/범위와 missed ID의 정확한 분할·집계, 원래 inference receipt의 성공 attempt와 점수 파일 SHA, tracking/native sample/queue provenance를 확인한다. 실제 관측과 missing index가 어긋나면 거절한다. 실제 고정 실행에서는 원래 score-hash receipt가 필수이며 현재 읽은 snapshot만 과거 실행 증명으로 승격하지 않는다.

소스 `scripts/audit_action_event_coverage.py` SHA `1291ea652a3627a44964535c398e11a4307345b9a2bd57c9f50337679fe2cb79`, 초기 시험 SHA `c6653283001430d2a502f116f3e5322e70634d0fefaec55a98f4cd1fd0132daf`에서 관련 30시험을 독립 실행해 통과했다. 이후 원래 receipt의 정상 통과/해시 결측 거절 시험 1개를 별도 실행해 통과했으며, 최종 시험 SHA는 `2a2ebb139605aab352c45980682f95771805e1f052610a7259b9d22d4eb7516e`다. 중복 실행을 합산하지 않은 고유 시험은 31개다. 실제 52행의 모든 진단·창 ID·부분 관측 수, 11정상 구간, 193묶음, CSV와 입력 97개 해시도 별도 oracle과 일치했다. 시험과 실제 산출물 검증은 별개 근거다.

| 실제 coverage-v1 산출물 | SHA256 |
|---|---|
| summary.json | `99db42a936988b94054fb856f593cb8edbae4a0df1619553c39c641c291e69ca` |
| per-video.json | `9d5cc2359cbc1f2bafdea0b9157c57a5d3202e1578ab2c9da3113c713e7b4295` |
| event-diagnostics.csv | `c5e88528176bc8a7993ae8611515fee1d3f3fe7c2ecc1c7a3cc4852431c5b412` |
| review-selection.json | `1689b0f1cd68c156ba805f11549e5690ceb551635728e8e6e915f1ed9b242c17` |

`coverage-actual-comparison.json`과 `coverage-tests.log`에 독립 증거를 남겼다. 사람 기준 precision/recall/F1·침입 개선은 null이다. 33/52를 행동 재현율로 부르거나 467개와 기존 37개를 뺄셈하지 않는다.

## 두 공식 정상 라벨 오판의 annotation 대조

EXP-0064의 실제 두 FP clip과 고정 annotation 해시를 연결했다. 4-61 actor 0의 ROI는 `[229,8,1429,1080]`, 4-62 actor 1은 `[565,212,1148,908]`다. 두 frame origin 각각에서 두 clip 모두 8시점 전체에 대상의 stand annotation이 있고, 같은 시점의 ROI와 교차하는 **다른 actor annotation**은 0개다. 이 결과는 annotation에 없는 사람이 없었다는 증거가 아니며 ROI 혼입·모델 배경 학습·라벨 오류의 원인을 확정하지 않는다.

`failure-roi-annotation-oracle.json`에 두 origin의 모든 시점·대상/다른 actor·공식 event 목록을 보존했다. 기존 박스 정렬 관찰을 재사용하되 새로 필요한 행동 의미·다른 사람의 포함 여부는 별도 검수 범위다. 점수가 높다는 이유로 정상 라벨을 양성으로 바꾸지 않는다.

## 실제 선정 미디어와 질문 명세

초기 renderer는 수정 가능한 `per-video.json`을 독립 검토 해시 없이 읽어 자막·선정을 바꿀 수 있었고, 부분 입력을 선택해도 영상 초점은 사건 첫 구간으로 정했다. 총괄에게 전달했고 최종본은 검토한 summary/per-video SHA를 필수로 받아 고정 plan/result·45영상/52고유참조·분류 합계와 연결한다. 입력/소스 변경을 완료 시 다시 검사하며, 부분 창의 예정 8시점과 실제 관측 유무를 모두 표시한다. 소스 SHA `258dbdcb16d537cfed51fee2412077127319083870355470aa9229dff865f8f9`, 시험 SHA `90ea6801edc962a07e7fabd8724553544c8370cc20d9253fcca9731d03e71d9a`의 7시험을 독립 통과했다.

최종 `review-media-v2/review-manifest.json` SHA `d1ab37cf391fc7730d7d7d6f1f1715f5fa7e86240d7f33a7e49102af90ae009e`를 확인했다. 23개 학교 자료는 기존 누락 15개 전부와 존재하는 카메라/진단 층을 포함하며, 8카메라·52개 선정/미선정 사유를 재현했다. 별도 장소 오판 2개를 더한 25개 MP4/JPG의 SHA와 실제 생성 MP4 647프레임을 로컬 디코딩해 1280×680·3FPS·프레임 수·출력 시각을 확인했다. 원본 장면의 행동 의미를 검수하거나 클라우드로 보내지는 않았다.

저장된 모든 표시 박스·원본 native PTS·선택 창/점수·ROI·부분 관측 mask가 원래 계획과 같았다. 두 FP의 16개 입력 RGB 해시는 실제 평가한 NPY 배열과 일치한다. 모델 입력 밖의 맥락 영상과 112×112 입력을 구분하고, 부분 관측에는 임의 ROI/점수를 만들지 않는다. 원본 SHA는 renderer의 선택 원본 검사 기록과 고정 plan/clip에 연결했으며 독립 검토에서 원시 영상 전체 해시를 반복하지 않았다. 초기 v1 영상은 실행 중 소스 변경으로 생산 코드 attestation을 인정하지 않는 예비 결과로 보존됐고 등록용은 v2다.

새 질문 명세 9개 SHA `4b21986f88e52b1943c1d1ed9ca379357133d339389116b286e3665cc3c9d587`를 읽어 실제 artifact ID·시각·점수와 대조했다. 7개는 기존 누락 참조의 새 모델 입력/사람·문 대응이며, 2개는 과거 박스 정렬 답변을 재사용하면서 실제 행동과 ROI 안 다른 사람을 묻는다. 판단 어려움 선택을 제공하고 정렬 질문을 반복하지 않는다. 이 검토는 명세의 타당성 확인이며 등록·답변·사람 정답 완료를 뜻하지 않는다.

## 실제 자료 보강 목록·분할 확인

현재 ZIP 라벨 6,534개(압축 해제된 JSON 276,501,784바이트)의 SHA·메타데이터를 독립 대조하고 actor/object/event 대응 33,796행의 명시 행동 종류·박스 수·누락 프레임을 재계산했다. 원천 ZIP의 해당 member 이름·길이·CRC를 확인했지만 CRC를 원본 SHA나 재인코딩 독립성으로 해석하지 않는다. 10개 장소 목록은 사람 의미 검수 완료나 학습 음성 확보 수가 아니다.

기존 split v3와 두 원본 감사 manifest의 고정 SHA, 1,440원본의 출처를 연결했다. 새 목록과 합친 211그룹에서 같은 시나리오/장소·동시 촬영·기존 event/multicamera 그룹의 모든 연결을 대조했다. 기존 시험 296원본·8그룹과 보호 45개를 제외하며, 사용자가 제외한 월담 시나리오도 유지한다. 기존 train/validation을 서로 바꾸지 않는다. 새 후보 96개는 모두 `training_eligible=false`이며 내용/의미 검토 전 학습 허가가 아니다.

| 실제 목록·분할 산출물 | SHA256 |
|---|---|
| inventory.jsonl | `c9085b6c691d333d60d215050dc1d722ab873352fffebdea4db4ab2c6910e09f` |
| split-manifest.json | `938bb20cf6189d6d04fb1f4ba5aafd6448341530c79a6e801db99888b553fa62` |
| candidate-manifest.json | `a1244de138b7f7366d5b05daacfa54a278e370c6effdb832b54dd3cdc01f6726` |
| summary.json | `70a1644ff99f7b0c93e4469c6d28c5aa170a5ff125b9daf99c1a15659995170d` |

새 장소 평가를 준비할 전체 장소 예약과 과거 시험을 본 장소의 평가 전용 분리를 확인했다. 새로 나타난 장소 6개라는 수만으로 정상과 넘기를 모두 갖춘 독립 장소 평가가 준비됐다고 말하지 않는다. `independent_new_place_generalization_evaluation_ready=false`와 접근 후 돌아가기·문을 만지되 넘지 않기 의미 검수 0을 유지한다. 원래 metadata 초안은 decode 전에 별도 보존하고 최종 분할을 먼저 고정했다.

fingerprint 실패 행에서 group_id가 빠져 같은 촬영 그룹의 다른 후보를 격리하지 못하는 문제를 발견해 담당자에게 전달했다. 최종 코드가 frozen candidate mapping에서 전체 그룹을 찾아 양쪽과 모든 관련 후보를 격리하도록 보완됐다. 실패 선행/후속 성공 형제와 양방향 충돌 반례를 포함한 18시험이 통과했다. 소스 SHA `6df3f0d9cb4f575f793bb9dbd2e3d0c81a466f6388deface67a4b350d0d077ec`, 시험 SHA `e8ade2beac3ab2d178cfbefc93ac846e4dc1921b2a19095c11e83499b81bdea5`다.

이후 구간 계약과 새 출력 경로 검증 시험 2개를 별도 통과해 고유 보강 시험은 20개다. 잘못 지정한 시험 클래스 이름으로 발생한 최초 loader 오류와 정상 재실행 로그를 모두 보존했다. 최종 시험 SHA는 `d3a2459455391340c6c3fcfc119a80e6d46ddeceaa06fad023b00941379fa06b`, 현재 CLI/추가 metadata 단계 소스는 `608c2a71c29d62f0b10ac11415ef324dac9b46711a43ad0ba86ea60ebcad8504`다. inventory 실행 소스 `f9b217ae9f903cc65c2a39e18268913eaf3c287e077377829e3cadaccff54de0`와 plan/fingerprint 실행 소스 `6df3f0d9cb4f575f793bb9dbd2e3d0c81a466f6388deface67a4b350d0d077ec`는 별도 보존됐으며 현재 코드를 과거 실행 코드라고 바꾸어 쓰지 않는다. 세 영역의 독립 고유 시험은 31+7+20=58개다.

## 실제 제한적 중복 검사와 구간 후보

저장 fingerprint와 고정 원본 해시 목록을 독립 구현으로 비교해 보호 341/341개와 새 96/96개의 완료, exact SHA 중복 0, 의심 비교쌍 7개, 양쪽/같은 촬영 11그룹의 29원본 보류를 재현했다. 제한적 검사 통과·의미 검수 대기는 67원본·24그룹이다. 선택된 새 원본 바이트 합계 2,931,022,843도 일치했다. 독립 검토자는 원시 영상을 다시 디코딩하지 않고 생산 코드와 저장 지문·판정을 감사했다.

| 실제 augmentation-v1 산출물 | SHA256 |
|---|---|
| verified-candidates.jsonl | `50c2749ee486e1f4a16e98f86f49a5abc19786ba7fa91c0126df2ce44b45d29b` |
| protected-content-fingerprints.jsonl | `6ff350866fe044a08a13b948f3776f2ecb86acf0350213a2ced3c2827e26538e` |
| fingerprint-summary.json | `60e11934c02b59b1e104d87f53abf69dfee0e6d104ae62abe185fc6a95962dc2` |
| candidate-event-intervals.jsonl | `4547bf19bc108bb637db746b4d37ce7219c52c628c56e8be5bf114b6de1ec01e` |
| interval-summary.json | `67d4e994ba3bb09697cfefe94aefd38ce20ea7c1053e7c351bbbfe82bdbd556b` |

새 SHA는 기존 전체 감사 corpus와 보호 45개 및 앞선 선택 후보에 대조한다. 내용 fingerprint 비교는 과거 test 296개+보호 45개와 선택한 새 후보 사이의 범위다. 기존 train/validation 전체 내용 비교나 재인코딩/크롭/시간 이동/부분 중복 부재를 인증하지 않는다. 같은 배경의 지문 유사성을 동일 사건이라고 확정하지 않는다.

555개 target actor-event의 중심 index·두 origin의 9annotation·박스와 ROI를 실제 라벨에서 독립 재계산했다. annotation 중심 완전 459개와 불가 96개가 일치한다. **459개 중 190개는 내용 검사에서 보류한 원본에 속한다.** 내용 보류를 제외한 annotation 중심 완전 후보는 269구간·63원본·24그룹이며, 이 역시 native 중심 프레임 디코딩·행동 의미 검수 완료가 아니다. 전체 459개를 학습 가능한 클립으로 부르지 않는다. 모든 행의 `native_center_decode_verified=false`, `semantic_ground_truth_verified=false`, `binary_training_label=null`, `training_eligible=false`를 확인했다.

기존 train 그룹 후보는 70→51원본, validation 그룹은 13→3, 보강 train/validation은 각각 4→4, 평가 전용은 5→5다. 새 장소 Taejongdae의 stand는 2원본/3구간을 학습 제안, 4원본/7구간을 검증 제안으로 나누며 서로 다른 촬영 그룹이지만 같은 장소다. 명시 walking 1,413구간은 모두 기존 citizen-park이고 새 검증 moving 후보는 0이다. 새 장소의 양성·여러 정상 행동을 갖춘 독립 평가도 준비되지 않았다. 이 부족을 원래 val/test 이동이나 무주석 구간의 자동 음성화로 메우지 않는다.

다른 로컬 CCTV의 269라벨과 원본 ZIP member 대응도 독립 확인했고, 최종 재현 가능 목록이 처음 감사한 목록과 일치한다. Gathering63/Fight27/Falldown40/Crowd36/Flood53/Invasion50이며 회귀45를 보호한다. 이 사건 라벨에서 사용 가능한 배우별 정상 구간은 0이다. 제조 자료의 읽을 수 있는 PNG/캡션 정지 자료와 읽지 못한 두 분할 ZIP을 구분하며, 읽기 실패를 자료 부재로 주장하지 않는다. 새 검수 이미지·학습 clip 생성이나 사람 의미 판정은 없다.

## 최종 공개 보고서·수치·보존 판정

| 최종 검토 문서/지표 | SHA256 |
|---|---|
| docs/experiments/EXP-0065-results.md | `eb23fdbef2a9a0f712485826d252e244af1862858392eb4e4f5eedf307f00500` |
| records/EXP-0065/metrics.json | `5518178b289d27e8815e55d701d3be7ef850b5e501abc5aa457c73c3478ae25d` |
| docs/experiments/EXP-0065-coverage-results.md | `b145a7db51d408ec63fd89f6f856f9dad3b00d943aa88c7fa384625b6e540c36` |
| docs/experiments/EXP-0065-augmentation-results.md | `fb5c51cb19efb1f3746b9ce1c1085ceb083cabd53bcc83ae3e93aa0c3786de73` |

공개 33개 지표에서 숫자 28개의 값·분모·범위·실제 출처 SHA가 일치한다. 나머지 5개는 학교 행동 precision/recall/F1, 침입 완료 정확도와 기존 대비 개선량이며 모두 null/미측정이다. null 지표의 개별 source SHA는 비어 있으므로 위 최종 보고서 해시로 보고 범위를 연결한다. 최종 보고서는 시간 겹침을 동일인 TP로, 공식 라벨을 전체 사람 검수 정답으로, 제한된 중복 검사를 독립 일반화로 해석하지 않는다. 보강 459구간의 보류 포함 범위와 학습 release 0을 명시했다.

원래 baseline lock과 총괄의 보호 목록을 대조해 운영 코드 91개, 잠긴 AFTER JSON 471개, 기존 등록 EXP-0064 보고서/지표/검토/binding 4개의 실제 바이트가 보존됨을 확인했다. canonical SQLite 큐는 읽기 전용으로 조회했고 EXP-0065 등록 전 snapshot과 현재의 jobs/attempts 각 100행이 일치한다. `SELECT * ... ORDER BY rowid` tuple 배열을 고정 JSON 형식으로 직렬화한 SHA는 jobs `63b961037c1c19c1205e481830dd65a9487a2e5d83788f89c77d6481c5ca918d`, attempts `a499a329b7c4efdc1f68371837d64f02f9f3e89443fee5b6899da0d78f05b3cc`다. 이는 해당 snapshot 이후 행 보존 확인이며 전체 DB 바이트 동일이나 과거 모든 시점의 추가 증명을 뜻하지 않는다.

실제 독립 증거는 `runtime/action-recognition/exp0065/independent/`의 coverage/media/inventory/fingerprint/interval/public-metrics/preservation 감사 JSON과 시험 로그에 있다. `final-report-arithmetic-and-hashes.json`은 최종 분할·구간 산술과 소스/보고서 해시를 연결한다. 이 문서는 지정한 진단·자료 감사의 완료 판정이며 실제 웹 등록·브라우저 재생·질문 답변·게시 성공을 인증하지 않는다. 그 전달은 총괄이 별도로 확인한다. 다음 단계의 실제 native 입력 확인·사람 의미 검수와 부족한 정상행동/새 장소 자료 확보는 남아 있으며, 이번 검토로 모델/GPU·학습·튜닝을 시작하지 않는다.
