# EXP-0037 독립 검토 — 제한된 기능 마무리

2026-10-30. **기능 구현·개발 영상 시연은 확인했고, 추적 단절 후처리는 감소 효과0으로 미채택한다. 침입 판별 성능 개선·독립 평가·실시간 성능은 확인하지 않았다.** 아래 결속 대상의 코드와 로컬 실행·브라우저 영수증을 독립 검토했다. 원본 CCTV를 외부 이미지 도구에 보내거나 새 사람 정답을 만들지 않았다. 검토자가 모델을 실행하거나 실제 영상의 행동 의미를 새로 판정한 것은 아니다.

## 고정 비교와 원본 보존

실제 EXP-0035 결과에 대한 한 차례 비교의 저장 자료를 읽고 원래 event ID/source pointer/판단 시각, 전체 알림, 카드, timeline을 대조했다. 제안 화면의 `events`와 `full_original_alerts`는 baseline과 같고 검토 전용 목록은 두 영상 모두0개다. 007은10알림/2카드,030은8알림/3카드를 유지한다. 007 정상 접근52.5–58초의3개 오탐,70–73초의3개 의심 및 기존 경보,03090–94초의6개 의심이 모두 남는다. 사람 수·독립 사건 수·정확도 통계가 아니다.

감사는 `recent_gate_presence_then_loss`만 대상으로 삼고, 경보 시각 이전 실제 측정의 같은 쪽 연속성·새 segment 시작·유일한 상대·겹침 경쟁을 확인한다. 미래 재등장으로 과거 경보를 지우지 않고 기존 양측 의심·경계 경보를 보존한다. ID 병합·자동 침입 아님 판정은 없다. 출발 쪽/박스 불확실성은 알림을 없애지 못하는 이유이며 EXP-0035 의심 생성의 새 차단 조건이 아니다. 실제 두 결과에 감소가 없어 후처리 미채택이라는 결론은 근거와 일치한다. 정상 접근 오탐 감소나 핵심 침입 검출 개선을 주장할 수 없다.

## 분석 경로와 실제 GPU 실행의 구분

명시적 C3/C6와 로컬 원본 선택에서 시작하는 실제 CLI를 확인했다. 캐시의 원본 SHA, 고정 FCOS 가중치/입력/후처리 설정, 카메라 설정, native PTS/time_base와 범위를 검사하고, 기존 ByteTrack gap·접근/소실·완화 의심·사건 카드 모듈을 재사용한다. 선택 구간과 `--whole`을 구분하며30fps 외 자료를 조용히 재샘플링하지 않는다. 저장 검출 캐시를 읽은 CPU 분석을 새 검출로 표시하지 않는다. 근거 영상은 원본 시야의 재인코딩이고 원본 파일과 비트 동일한 사본이 아니다.

최종 `video007-v4`, `video030-v3`, `fresh007-reuse-v2`의 request는 현재 pipeline 코드 SHA에 결속되고, 완료 단계 전체 파일·원본/카드/분석/미디어 해시를 독립 대조했다. 각각1710/480/90프레임이며 완료 단계의 재사용도 확인했다. 새 추적/후처리와 근거 제작, 저장 결과 재생, 기존 검출 재사용을 구별한다. 이 실제 시연은 선택 구간이며 원본 전체 영상의 처리 성능 검증이 아니다.

별도로 canonical 큐의 job `92e148bdde734d3d9360a5b5014e83ab`, attempt `e852959a32d84224a96e795f16545233` 한 번이 실제 성공했다. 원본00745–48초90프레임, 기존10warmup, freeVRAM6699MiB, 신규 가중치/학습0이며0알림/0카드다. 원본/모델/설정/캐시/PTS와 큐 input/config 해시·exit0을 독립 대조했다. 이0개는 검수된 정상 구분 성공이 아니다.

GPU 실행 당시27개 소스의 보존본을 다시 해시해 등록 aggregate `4b260b84b776ac177347cc68e814619e5f3dafea837bdc887c032df22913d391`와 정확히 일치함을 확인했다. 이후 `queue.py`, `video_cards_command.py`, `video_cards_registration.py`가 수정됐다. **최종 exact-job 선택 보호와 등록 helper 수정은 CPU 테스트 결과이며 새 GPU 실행으로 검증했다고 쓰지 않는다.** 동일 source를 강제로 다시 추론하지 않았다. 최종 큐 경로는 기존 canonical lock을 상속하고 실제 parent/child identity, Run/Task/Dispatch/owner, 입력/설정/소스/commit을 모델 호출 전에 검사한다. 다른 queued job을 대신 실행하지 않도록 lock 안에서 요청 job ID만 claim한다.

## 검토 저장과 실제 화면

서버가 allowlist의 등록 bundle bytes/SHA, session, incident membership을 검증하며 클라이언트가 표시한 SHA/session도 읽기·쓰기 때 비교한다. 미등록 카드·임의 경로·다른 Origin·잘못된 JSON은 거부한다. 자동 카드 상태와 수동 검토는 독립이고, 로컬 검토 DB는 canonical GPU DB 및 알림 영수증 DB와 별도다. `BEGIN IMMEDIATE`와 expected version으로 동시 수정을 직렬화하고 이전 이력을 UPDATE/DELETE하지 않는다. 메모는 DOM text로 출력한다. 이는 로컬 저장 기능이지 사용자 인증 시스템이 아니다.

총괄의 실제 Orca 브라우저 명령과 결과에서 UI 저장1/2, 동시 API수정3, 오래된 UI의409와 초안 유지, 명시적 재저장4 및 이력4개를 확인했다.16.5초 자동 폴링·수동 갱신·되감기·새로고침·서비스 재시작 후 선택 영상/재생시각/열린 상세와 검토가 유지됐다. 시연 메모와 판단 불가 상태는 Codex 기능 시험으로 표시되며 새 사용자 정답이 아니다.

최종 CLI007/030 재생은 새 세션의 최초 토스트2/3개와 반복0개, 원본 PTS에 맞는 근거 이동을 확인했다. 첫007 시험이 목표 끝 전에 멈춘 기록과 후속 확인을 함께 읽었으며 영수증을 초기화하지 않았다. 새 bundle에는 기존 수동 검토를 복사하지 않고 새 검토 버전1을 별도 저장했다. 최초 claim은 DOM 표시나 사용자의 실제 인지를 보장하는 영수증이 아니다. 선택기에는 bundle ID를 사용하여 같은 영상·동일 표시 이름의 여러 분석을 구별한다.

## 검토 중 수정과 검증 범위

오래된 화면이 새 bundle에 메모를 저장할 수 있던 문제, 완료 stage 루트/영수증 symlink 읽기, 일반 큐 실행기가 다른 대기 작업을 선택할 수 있던 문제, 반복 분석의 선택기 중복을 총괄에게 전달했다. 담당 수정 후 표시 SHA/session 비교, 읽기 전 symlink 거부, job ID를 지정한 canonical claim, bundle ID 선택으로 해소했다. 검토자는 제품 코드를 직접 수정하지 않았다.

독립 실행한 합성 검사는 continuation/store29개, pipeline/큐연결19개, 기존 큐14개, 웹7개와 두 JavaScript fixture suite다. 웹7개에는 기존 bundle을 같은 card ID의 새 bytes로 교체한 뒤 오래된 GET/POST409와 새 bundle 미작성 상태를 확인하는 별도 시험이 포함된다. 실제 GPU·실제 브라우저 증거는 이 합성 테스트와 분리했다. 전체 저장소 테스트 완료나 침입 정확도로 확대하지 않는다.

## 최종 보존과 결속

최종 독립 검사에서 보호1,447파일과 이전 등록128개 파일이 모두 동일했고, canonical 큐의 기존47jobs/47attempts 모든 행도 그대로였다. 승인된 실제 검출1job/1attempt만 추가되어48/48이다. 기존 EXP-0036 claim5행은 시각까지 그대로이며, 새 CLI 시연의 claim5행만 추가되어 총10행이다. 검토 저장은 현재2행/이력5행이고 재시작 검증 당시의 이전 이력4행을 모두 보존한다. 승인된 새 CLI/큐 연결·기존 웹 변경과 과거 결과 보존을 구분한다. 실제 서비스가 제공한 JS/HTML/CSS 해시도 현재 파일과 일치한다.

최종 metrics의14개 측정값은 원천 SHA와 JSON pointer 값이 모두 일치하고, 정확도1개는 null/미평가로 남아 있다. 초기 GPU 메모리 MiB 값이 raw-byte pointer와 맞지 않던 기록은 총괄이 raw bytes로 바로잡은 뒤 결속했다. 아래 결론은 동결된 결과/측정치와 코드의 기능 검토이며 침입 성능 채택이 아니다.

| 최종 대상 | SHA-256 |
|---|---|
| `docs/experiments/EXP-0037-results.md` | `1dc079d8b13ab45d3bce903ef14abdced68a598e6a3908fb0b21f52f04ebafec` |
| `records/EXP-0037/metrics.json` | `f9fb9fa35d49da89e146a53992672796077b275559a840d99f2815b91064249b` |
| `sceneguard/video_cards.py` | `e186e6ea37b3a8cd41350d862be5e4931be41d4ebb125919a868c17a6cc4b153` |
| `sceneguard/video_cards_gpu.py` | `656a34b8dc247b7587a9e4057091d55c9eb12595c4ecd3ef5152d81eb1b6d2d6` |
| `sceneguard/video_cards_registration.py` | `196c93cdb57934c19b3c507dd925a721d01da7160b443f8247f0d6de9fb4bc9c` |
| `orchestration/video_cards_command.py` | `de8b91d4ea912ca7c25d7f2da0aa669c3e41cfca40c47d1120b5b8c544536bc3` |
| `orchestration/queue.py` | `94d6da1a28566d26c5043e8722275d2c5ec2105e8df869088e113e58398c96a5` |
| `webapp/incident.py` | `607d92bc23726f9d8c48e7d07bd33b3d1594e29eb9fa1bdeb5af93059314050d` |
| `webapp/app.js` | `eaeacb17fd50c5cabb536baeb5ad156c8bd462c7ae387682245709a872b30e5d` |

로컬 상세 감사는 `runtime/EXP-0037/independent-comparison-audit.json`, `independent-gpu-audit.json`, `independent-gpu-source-audit.json`, `independent-final-audit.json`과 독립 테스트 로그에 있다. 바이트가 바뀌면 이 검토를 새 자료의 검토로 재사용할 수 없다. 서비스 최종 등록/게시 결과와 GitHub 원격 바이트 확인은 총괄의 별도 전달 기록이며 이 문서가 선행 인증하지 않는다. 이번 기능 범위를 넘어 새 모델·튜닝·추론·학습을 승인하지 않는다.
