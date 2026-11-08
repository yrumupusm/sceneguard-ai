# EXP-0066 사람 위치 라벨 보완 독립 검토

2026-11-08. Task `task_afb675685e58`, Dispatch `ctx_629b843a1093`. 최종 상태는 **정확한 단일75프레임 초안 실행 결과·편집 package·비교 영상·실제 편집 화면·EXP-0067 보고를 한정 수용**이다. 217개 모델 박스 행은 미검수 초안이며 사람 정답 완성이나 추가 학습 완료를 인증하지 않는다. 검토자는 생산 코드·실제 큐·원본·GT·모델을 변경하지 않았고 GPU/forward·cloud media·commit/push를 하지 않았다. 아래 초기 대기·보류는 발견 및 수정 과정의 이력이며 마지막 최종 판정을 따른다.

## 실제 답변과 범위

WEB-0005 `pending --include-acknowledged` 조회는 성공했고 미처리 답변0이었다. 적용 문서와 실제 `reviewed-v1/resolved-answers.json`의 여섯 답변·처리 이력을 읽었다.3번은 수정 answer_version2/request version5, 나머지는 answer_version1/request version4이며 모두 applied다.5번은 사용자 채팅 원문을 명시적으로 전사한 것이고 웹에서 사용자가 제출한 답변으로 바꾸지 않았다. Applied는1/3/5의 보완 대상 제외 목록 반영이며 박스 수정 완료가 아니다.

| 사례 | 기존 split | native frame | 기존 origin1 박스 행 | 이번 처리 |
|---|---|---|---:|---|
| 1 | train | 99–123 | 12 | 미주석 주변 사람 보완, 아직 held |
| 2 | train | 40–64 | 50 | 기존 준비 자료 유지 |
| 3 | train | 159–183 | 49 | 주석 경계·누락 보완, 아직 held |
| 4 | train | 47–71 | 25 | 기존 준비 자료 유지 |
| 5 | validation | 40–64 | 18 | 뒤따르는 사람 보완, 아직 held |
| 6 | validation | 10–34 | 25 | 기존 준비 자료 유지 |

고정 split SHA `bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499`에 source SHA와 event group을 직접 대조했다. 여섯 사례의 원래 split이 일치하며 보호 test source/group 및 학교45 source와 교집합0이다. 보완은1/3/5 각25개의 실제3FPS native frame, 총75개로 제한한다. 같은3FPS 영상을16입력 slot으로 반복해 만든 표본을 새 관측으로 세지 않는다.5번은 validation에 남기며 최종 사용자가 수정한 라벨도 split을 바꾸는 근거가 아니다.

기존75프레임 준비 manifest SHA `1df00c365ed086e3d6a2fa801a65fdf78bda5f41361c600c3ce3c237385ff814`에서 모든 PNG/label 파일 hash, 실제 RGB hash·원본 크기·native PTS와 기존100개 박스의 YOLO 좌표 변환을 독립 확인했다. Train50/validation25, 사례2/4/6이며 `training_release`, 정밀좌표·frame origin·행동GT 인증은 모두false다. 근거는 reviewer runtime의 `existing-scope-review.json`이다. 전체797개나 보이지 않는 구간의 완전성을 인증하지 않는다.

## 사람 검수 부담을 줄이는 현실적인 경로

기존2/4/6의 답변과100개 박스는 재활용 가능한 준비 근거다. 같은 누락 여부를 다시 질문하지 않고 보존하되, 필요한 정밀좌표/시각 정렬 확인과 이후 데이터 release를 별도로 둔다.1/3/5도 기존 origin1 박스79행을 지우고 처음부터 그릴 필요가 없다. 원래 주석이라는 출처를 표시한 초깃값으로 제공하고, 빠진 사람의 모델 초안과 사용자의 수정을 별도 층으로 기록할 수 있다. 원래 actor/action 정보는 삭제·병합하지 않으며 동일 actor0가 서로 다른 박스에 재사용됐다는 이유로 사람 신원을 합치지 않는다.

확인한 기존 train/validation feature-full 캐시는 VideoMAE·V-JEPA2·V-JEPA2.1·InternVideo의 full-scene encoder 결과다. 이 특징을 새 사람 위치 박스로 해석할 수 없다. 앞선 YOLO/FCOS/joint 학교45 결과는 다른 원본이고 보호 평가자료이므로 이번75프레임 라벨을 대신하지 않는다. 기존 객체 ZIP 조사 기록은 person이 없는18클래스와 빈JSON1개를 기록한다. 그 기록을 읽었지만 전체 ZIP을 재감사하거나 시설물 박스를 사람으로 바꾸지 않았다. 정확한 동일source/native frame·모델·전처리 hash에 맞는 박스 캐시가 없다면 이번 고정75프레임 초안 추론이 제한된 보조 경로다.

한 프레임의 모델 박스를 모두 수락했다는 사실과 그 화면의 모든 사람을 확인했다는 사실은 별개다. 사용자가 실제 프레임에서 추가/수정/거부한 뒤 별도의 완전성 결정을 내려야 한다. 가림·화질 때문에 결정할 수 없는 프레임은 unknown/incomplete로 남기며, 빈 결과를 빈 배경 정답으로 자동 승격하지 않는다.3번의 주석 종료 이후를 자동 연장하거나5번의 뒤따르는 사람에게 이후 월담 행동을 추정하지 않는다.

## 정확한 후보와 editor에 요구하는 검증

- 고정 source/checkpoint/vendor/environment·review/answer version·선택75frame·split/origin·source RGB/PTS binding을 실제 바이트로 묶는다. 새로운 root release 전에는 실행 준비도를 승인하지 않는다.
- canonical 단일 job/shared lock·기존 GPU resource gate·활성 context·source/input 재검사와 실패 시 중지를 유지한다. 이번 작업은 proposal inference뿐이며 training/default/threshold 변경을 포함하지 않는다.
- 원본 주석과 모델 초안, 사용자 확정/수정 박스를 구분하고 모든 최종 박스에 원본 또는 초안 출처와 revision을 남긴다. 원래 GT 파일을 덮어쓰지 않는다.
- 저장은 frame/source hash와 기대 revision에 묶고 stale save를 거부한다. 완전성 확인 이후 박스가 바뀌면 다시 확인하도록 하며, 미완료·불확실·명시적 빈 화면을 구별한다. 모델 초안 수락만으로 completeness나 training release를 만들지 않는다.
- 실제 생성된75프레임과 모든 제안의 원본좌표·PNG RGB·PTS·해시·canonical receipt를 검증하고, editor의 조작/재시작/다중화면 충돌/서버 거부를 검토자 소유 임시 저장소에서 확인한다. 실제 사용자의 답변·annotation DB에는 시험 저장을 하지 않는다.

초기에는 최종 후보와 editor가 도착하기 전 위 계약을 고정했다. 이후 정확한 소스와 실제 결과에 대한 발견·수정·최종 판정을 아래에 기록했다.

## Editor 초안의 실제 발견과 회귀

초기 app SHA `3273dddaa11220ddecee44e616f49259cb648549fb58825efec6b782d86c21da`에서 지연된 frameA 저장 도중 frameB로 이동·편집하면 A응답이 B의 revision을 덮고 dirty를false로 바꾸는 문제를 실제 app handler의 synthetic delayed-fetch로 재현했다. Root가 saving lock과 현재 이미지 준비 검사를 추가했다. 저장 실패에서도 편집 내용을 보존하고 잠금을 해제하는지, 오래된 응답/빈화면 확인/수정 뒤 completeness 해제를 검증 대상으로 삼았다.

Server SHA `e0080c025f57674f3f4b6bbf3f8edb4c4c7bd985faade1aab71843a5127a77f0`의 기존11시험과 별도 실제 local HTTP 시험이 통과했다. 동시 저장 두 건은200/409 하나씩이며 재시작 뒤 같은 revision, 이전 이력 보존, 수동 추가, 부정확한 좌표/확인 누락/이미지 변조/잘못된 origin 거부를 확인했다. 모두 검토자 소유 synthetic store만 사용했다.

Root가 제공한 로컬 shared library 경로로 별도 GPU-disabled Chromium을 실행할 수 있게 됐다. app SHA `4e7da947c927197ae5cd45437ebf2359e1686aad0b2f41b9b5670f1e791c8aea`의 실제 브라우저에서 저장 lock·실패 복구·편집 후 완료 해제·stale save409를 확인했다. 그러나 같은 프레임의 reload GET 대기 중 새 편집은 generation이 바뀌지 않아 응답 도착 때 사라진다. 실제 candidate1개/dirtytrue가 boxes0/dirtyfalse로 바뀌는 반례를 `editor-browser-review-v1.json`에 기록하고 수정을 요청했다. 아직 editor 최종 수용은 아니다. 원본 미디어 screenshot/cloud전송이나 실제 사용자 annotation 저장은 하지 않았다.

Root의 두 번째 수정 app SHA `2cc46ec302d88b2a015ecf5ac60df50569ab08c37036cd0101b45f5b2ef43531`를 실제 Chromium으로 재검사했다. 저장·reload 대기 중 조작/이동이 잠기며 양쪽 실패에서 잠금이 풀린다. 좌표 편집 후 완료 확인 해제, stale save409, 명시적 reload와 낮은 점수 표시를 확인했다. 현재 프레임 이미지 요청을 브라우저에서 차단한 반례에서는 canvas가 준비되지 않고 저장이 거부됐다. `editor-browser-review-v2.json`은 이 synthetic 상호작용 범위를 수용하며 실제75프레임 package 자체의 검증은 별도다.

Package builder 초기 SHA `04d672edcf7097e583fffb3210aec4bfcc58e8d40e2279e161f409ab50ff3c2f`는 실제 prepared75 입력과 검토자 소유 가짜 proposal JSONL만으로 package를 만들었다. 해당 초안은 미실행 모델명·0으로 채운 spec SHA였고 canonical result/receipt가 없었다. 실제frame에 연결됐다는 사실만으로 모델 실행 출처가 검증되지 않는 문제다. `package-provenance-gap-v1.json`에 재현하고 canonical 성공 result/receipt/proposals SHA와 모델/weight/source/context 연결 및 package 내 보존을 요청했다. 모델 초안 자체를 GT로 승인한 것은 아니지만 실행 근거 없는 초안을 실제 YOLO 출력으로 전달할 수 있어 해결 전 해당 builder의 provenance 수용을 보류한다.

Queue registry 변경은 실제 DB의 읽기 전용 backup을 검토자 소유 디렉터리로 복사한 뒤 그 복사본에서 검사했다.143jobs/143attempts 모든 행, 추가 index/trigger, foreign key를 보존하며 CHECK에 새 command만 추가하고 백업을 남겼다. 두 번째 migration은 idempotent였다. 원래 큐에는 migration/등록을 하지 않았다. 근거 `queue-migration-review-v1.json`이다.

## 구간 단위 직접 검수의 한계

75개 같은 질문을 반복할 필요는 없다. 새 preview의 각25개 실제frame 전체에서 표시된 주황색 박스의 위치·대상과 모든 보이는 사람의 누락/중복/배경박스 여부를 명시적으로 확인한 새 답변은 그 정확한 표시 집합의 직접 검수 근거가 될 수 있다. Preview/frame/proposal ID·hash·표시threshold0.5·answer version을 묶고, 일시정지/프레임별 확인을 제공하며 오류/불확실 답변은 대상 시각의 editor 수정으로 이어간다. 숨겨진 낮은 점수 박스, 다른 원본/프레임, 기존 박스의 자동 합집합, 행동·정밀 경계·origin 전체 인증으로 확대하지 않는다. 이 후속 답변은 아직 없고 자동 import/training release를 승인한 것도 아니다.

## 정확한 단일 실행 준비도 수용

Root의 최종 candidate `candidate-9c73cea12004295a.json` SHA `7e2b5acbb27880dbef10e1f7987d81cffd603e9dd190f76f5e404e33c7760b61`, executor SHA `49e47666418e4d735c359b37787676742cfc7d7b54e9c628d7ba4b8adac314dd`, committed HEAD `a8dfd8fdd63d22902de807a591fca2e6d5dd6b44`를 확인했다.10개 실행 소스가 해당 commit의 실제 바이트와 일치하고 독립 input contract 재계산 SHA `6d19a93022cef1ea1feeb47dd7352180797e5285d36aa6399cede227a07e860b`가 후보와 동일하다.357개 model/vendor/환경 binding, 기존 YOLO26x checkpoint SHA `9fdd44a31c504547ffb81d2c6d9e6dac3493c8eaa8b0398d3f43bae6c7003e92`, 환경 SHA `ec5f796ce1f16f1de83b69c479dee33a9039fd98ba6314e6bf749fb87d38a81c`를 실제 재해시했다.

준비 manifest SHA `758660c56333e6712c980c6f0f8eddaff93fcc9d7594fcc8dadf5c8191324aa8`의75PNG native RGB/PTS/index/크기·3원본·3라벨과 원본79행·both origins를 독립 검증했다. 이 이미지를16slot broadcast view에 놓지만 기존 adapter는 실제 한 RGB의 slot8만 읽는다. 추가 시간 관측이 아니고 공식 640 letterbox/BGR/FP32/native end2end/conf0.05와 표시0.5를 유지한다.10개 source contract 시험과3개 executor 반례 시험이 통과했다. 검토자 소유 임시 경로만 사용했으며 실제 모델·GPU·큐 작업은0이다.

독립 receipt `reviewer/execution-release-v1.json` SHA `896eda0c60ad9e603f516494b5bb56b639e8214767438a8f7b1cedf22b981459`의 status는 `accepted_person_label_repair_execution_release`다. 새 root GO 이후 한 번의1800초 제한 draft75 job에만 적용한다.6144MiB preflight와 canonical shared lock/상속FD/live assignment·supervisor·source/input 검사는 그대로이며 실패 시 자동 재시도/학습/GT 승격은 없다. 수용 시143jobs/143attempts가 전부 초기 값과 같고 idle였다. `Queue.run_once`는 실제로 detached `_supervise` subprocess를 만들고 wait하므로 호출 controller가 supervisor라는 우려는 코드에서 해소됐다.

Editor package의 수정 builder SHA `4cca54841182434f1faf403174848c95d8aa64ab5eac36535f30f7a0e2921987`는 앞선 임의 JSONL 반례를 canonical result/receipt 경로 검사에서 출력 생성 전에 거절한다. Actual 성공 result/proposals·receipt/queue/context/model binding과 각 native proposal 재생성 대조를 추가했다. 이후 실제 성공 package도 아래와 같이 독립 검증했다.

## 실제 단일 실행과 출력 검증

Root GO `msg_1ed0343480bd`와 grant SHA `167cc09435396ccc0ebbe7a6c805c5243c44d4a69a5ceba71a919d20d64bb535` 이후 job `3b29e75eea2b47afb706520b5f6de728`, attempt `7aa4c4bb65ec46ac9d4cd4f4dcb00775` 한 건이 성공했다. 독립 `reviewer/actual-proposals-review-v1.json`은 실제 result SHA `f1b71dc1756c5d1a32c38a13dd96e6197680c3bca7d670ed1ab86ba2e05dec63`, proposals SHA `bab8bf53add31dca3715f413d09b1cc1e280eecf08cfd81c5355cc004371fb60`, canonical receipt SHA `7ae47e95258e59f13745ffbe687bce1abf43e96fc2e55d1d8f956811881793e3`, completion SHA `1e7c49994fce3bbdae196d954c3e7fa3787218c409ecc81ce25629ad8e790ecd`를 묶는다.

75개의 정확한 native frame에 대해 source/model 출처, 고유 proposal ID, 원본 좌표·점수·class와 미검수/training false 상태를 확인했다. 사례1/3/5의 반환 행은98/84/35로 합계217, 표시0.5 이상 유효 행은77/74/31로 합계182, 잘못된 좌표 행은0이다. 원래79개 주석과 양쪽 origin 해석을 보존했다. 이는 사람 수·누락 복원 성공·정답 수가 아니다. 기존143jobs/143attempts 모든 행은 그대로이고 새 성공1개만 추가돼144개씩이며, 큐 idle과 실제 child/supervisor 프로세스 identity 종료를 확인했다.

실행 경과10.984834885923192초, PyTorch peak allocated439168512/reserved635437056바이트는 실제 result와 같다. 이는 원본 전체 처리 속도나 GPU 전체 메모리 사용량이 아니다. Warmup은75개 출력과 별도이며 총 forward 수를75회라고 인증하지 않는다. 검토자가 모델을 실행한 횟수는0이다.

## 실제 편집 자료·비교 영상·브라우저 검증

실제 package SHA `f5c327472fe72da00c19ffe895d24d2267b869c2aee0f641e601db225ef5546a`, preview manifest SHA `2471d865d4245b2764c237ea7880c832747005531b4f61ebdb59b4f2a8444960`를 수용한다. 각 frame의 split/source RGB/PTS/origin, 원래79개 후보와217개 모델 후보의 실제 실행 출처, 표시182개 ID·좌표·점수가 원본 결과와 일치한다. 세 비교 영상의75프레임 전체를 로컬에서 디코딩해 native 순서·3FPS를 대조하고, 원본/원래 주석/새 초안 세 패널을 독립 재구성한 픽셀과 비교했다. 압축 영상의 최대 패널 평균 절대오차는2.6463792438271603/255, 박스 경계 최대 평균 절대오차는16.454528786211956/255였다. 근거는 `reviewer/actual-editor-and-preview-review-v1.json`이다. 이 검사는 표시·출처의 일치이며 사람 대응 의미 정답 판정이 아니다.

실제 `http://127.0.0.1:8769/`를 별도 GPU-disabled Chromium에서 읽기 전용으로 검증했다. 모든75개 이미지의 native 시각·1920×1080 canvas와 실제 그리기 좌표·개수, 재생/이전 frame/seek/낮은 점수 토글을 확인했다. 초기와 종료 모두75개 pending/version0으로 동일했고 실제 사용자 store에 POST는0이었다. 근거는 `reviewer/actual-editor-browser-review-v1.json`이다. 저장·수정·경합·실패·재시작 시험은 앞서 별도 synthetic store에서만 수행했다. 검토자 시험 서버와 브라우저는 종료했다.

초기 저장 응답 경합, reload 중 편집 소실, 미실행 proposal의 package 유입이라는 세 발견은 각각 수정 소스와 반례 재검증으로 해소됐다. 현 검토 범위에서 미해결 구현 차단 사항은 없다. 실제 사람 누락/오박스 확인과 좌표 수정은 아직 사용자 작업으로 남는다.

## EXP-0067 최종 보고와 판정

최종 보고 문구를 읽고 공개 집계와9개 metric을 실제 출력 및 독립 검증 자료에 대조했다. 사람 정밀도·재현율·학교 학습 전후 개선의3개 값은 null이며 추가 학습0회를 유지한다. 모두 사람 검수된 라벨, 전체797개 완전성, 독립 일반화나 학습 개선 완료를 주장하지 않는다. `reviewer/public-report-review-v1.json`에 다음 정확한 바이트를 수용했다.

| 파일 | SHA256 |
|---|---|
| `docs/experiments/EXP-0067-protocol.md` | `7d97c088f818d63af0dadb75052c242b0538a95c9ed80d6642d2b7553359557b` |
| `docs/experiments/EXP-0067-results.md` | `2b78bb016e77a6ac55cc4c84c054b94c95a43f5f6af73f038188b4267a994047` |
| `records/EXP-0067/results.json` | `7e73bbfb7548439f4cd04752353b9815078e412d0a2d38e671ed8756a35918ff` |
| `records/EXP-0067/metrics.json` | `cccc309e3e7ad1127a27c235482bf7796d9ab1f3c7476d89e1b7d6dd20f8c09a` |

최종 판정은 **한정된 초안 비교·사용자 검수 전달용 결과 수용**이다. 현재 검수된 출력은 정답 release가 아니며 자동 training을 허용하지 않는다. 새 세 구간 답변은 정확한 표시 집합과 답변 버전으로만 적용하고 오류/불확실은 대상 frame의 수정·완전성 확인으로 이어가야 한다. 보호 학교45/EXP-0064 및 기존 선택 가중치/기준을 이 결과로 튜닝하지 않는다. 새 답변·사람 정답 보완·실제 추가 학습과 학교 전후 평가는 남아 있다. 마지막 WEB-0005 읽기 전용 조회도 성공했고 미처리 답변0이었다.

이 독립 검토는 로컬 편집 화면과 비교 자료까지 확인했다. EXP-0067 주 웹서비스 등록·실제 주 웹화면 재생·게시 완료는 root의 별도 전달 기록 범위이며 여기서 인증하지 않는다. 본 문서와 검토자 runtime artifacts만 작성했으며 commit/push는 하지 않았다.
