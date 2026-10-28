# SceneGuard — 다음 작업과 대화 인수인계

- 마지막 정리: 2026-10-28
- 현재 단계: **MVP-0001 CPU 구현·입력 준비 완료 / GPU 자원 부족으로 실제 모델 검증 미실행·MVP 미완료. EXP8~10 및 EXP6 채택 보류 보존.**
- 저장소: https://github.com/yrumupusm/sceneguard-ai
- 이전 감사 실행 기준 HEAD: `ba43440`. 감사 문서·검사 스크립트는 같은 작업 단위로 GitHub에 기록하며, 원본 영상·추출 이미지·메타데이터는 Git 제외 경로에만 보관.
- 사용자 운영 지시: 이후에도 작업 단위별 코드·실험 결과·기술 선택 근거·오류 해결 기록을 검토 후 커밋·푸시한다. 상세 절차는 `AGENTS.md` 참고.

## 최신 결과 — MVP-0001 핵심 실행 흐름·자원 차단

- 새 사용자 승인과 [고정 계획](experiments/MVP-0001-plan.md): 최대3구성, 기존 가중치만 사용, 기존 Run/공통 GPU 큐. 방법 담당 Sol/high `task_d32fef262394`, 통합 담당 Sol/high `task_c466b62bf289`, 별도 Astra/high 검토 `task_903274b61857`를 실제 세션 metadata로 확인했다.
- A는 기존 FCOS/ByteTrack C 결과 재사용, B는 EXP8/10 전체화면 Qwen 기준 보존, C는 같은 모델의 기존 배경 ROI 입력. 모델·질문을 사건별로 조정하지 않는다. C1/C4는 전체화면 fallback,006 후기 보행은 ROI 밖이다.
- 원본007/030 개발과013 C4 진단 검증을 고정했다.013은 이전 감사 노출이 있어 blind/독립 장소 테스트가 아니다. 평가 manifest의030 약84/90초 사용자 관찰을 Codex 초안과 구분했으며 정확한 onset/완료 정답은 만들지 않았다.
- 원본3개 CPU 디코딩·시간창 검증:12,754프레임/853고유 표본/172창, 모두EOF.030 마지막 창은 실제1표본이므로 근거 부족 대상. **모델 미실행 준비 검사이며 전체 행동 파이프라인 성공이 아니다.**
- 고정계획·입력·평가·배정은 GitHub `9482dc9`에 게시했고 실제 기존 브라우저에서 EXP11/12 담당 카드의 진행 중·Sol/high·결과 미등록을 확인했다. 새 결과 등록/게시/화면 검증은 별도로 진행한다.
- 실제 GPU job/attempt/generation0. 마지막 durable 관측 여유1,806MiB·사용률99%로 고정 최소6,144MiB 미달이다. 외부 작업 종료·queue 우회 없이 자원 차단으로 정리했다. [종합 결과](experiments/MVP-0001-summary.md), [전달 기록](orchestration/MVP-0001_DELIVERY.md), [독립 검토](reviews/MVP-0001-independent-review.md)를 따른다. 담당2명은 실제 목표 미완료로 native failed이며 코드/CPU 실패나 모델 OOM으로 해석하지 않는다.
- 기존6클립 실제 CPU 전처리와 C1 저장 입력·tensor 동등성을 확인했다. 실제 응답/후보/행동 성능은 없다. 과거 adapter budget 상수 추출 때문에 첫 재사용 검사가 멈춘 것을 특정 소스 SHA·차이 증명으로 수정해 한 번 준비를 다시 했고 실패도 보존했다.
- 후속은 같은 승인 한도에서 GPU 여유 확인→C 개발 비교→B/C 원본3개 전체 분석·평가다. 이번 불변 등록 ID/보고서를 덮어쓰지 않고 새 실행/전달 ID를 사용한다. 자동 대기 job·무인 재개·새 모델 다운로드를 남기지 않는다. 원본·기존 결과·환경·공식 라벨은 보존했다.

## 최근 확인 결과 — 첫 실제 VLM 배치 (2026-10-28)

- [비교표·총괄 결론](experiments/BATCH-0001-vlm-comparison.md), [선정 ADR-0015](decisions/ADR-0015-first-vlm-comparison-batch.md), [전달 상태](orchestration/BATCH-0001_DELIVERY.md). 기존 Qwen에 SmolVLM2-2.2B 한 모델만 추가했다. 후보2개, 기준2+개선1조건, 같은6클립의 총18개 응답이며 독립 표본18개가 아니다.
- 실제 Sol/high 담당3개 Task와 Astra/high 독립 검토, 기존 Astra/max 총괄/Run/공통 GPU 큐를 사용했다. 준비는 병렬, GPU는 세 job이 순차 실행됐으며 inference retry/OOM0. 기존8job/8attempt 및 결과/입력/두 환경을 보존했다.
- Qwen 기준 strict2/6→펜스 제거6/6, 평균 생성2.692초·peak4.342GiB. Smol strict6/6,1.874초·4.519GiB. Qwen 픽셀 예산 대조 strict1/6→6/6,2.919초·4.663GiB. 형식/실행 비용과 행동 이해를 구분한다. 원본 최초 디코딩·클립 확보·큐 대기 제외, 온라인 탐지 FPS 아님.
- Qwen은 넘기를 대기로 설명하거나 근거 없이 완료를 선언했다. 전체 화면 입력을448×768→608×1120으로 늘려도 유효한 행동 개선을 확인하지 못했다. Smol은 enum/근거 모순과 선택지 반복이 남아 추가 조정 없이 보류했다. 기본 CV에 연결하지 않았다.
- 담당1에 EXP8/10, 담당2에 EXP9를 연결한다. `complete` 등록과 `verify_delivery github/browser`를 사용한다. GitHub 반영·실제 서비스/화면 검증 결과는 전달 기록과 로컬 receipt가 원본이며 실행 성공만으로 추정하지 않는다.
- 오류 기록: 준비 단계 Smol 설정 계약/Clip ID/29.97fps PTS 검사 수정; 이후 추론 오류0. Smol 담당이 결과 작성 후 Sol capacity로 멈췄지만 같은Sol/high로 한 번 이어서 커밋·worker_done 완료, 모델 대체·GPU 재실행 없음. 브라우저 이미지 확인 중 timeout은 결과 탭만 재생성해 복구했고 서비스/큐/Orca runtime reset은 하지 않았다.
- **남은 확인:** 02/06 중심으로 원본·실제 입력 시트를 사람이 확인해야 한다. 현재 의미 평가는 기존 검수 초안과 응답 대조이며 정밀GT/독립 평가가 아니다. 자동 다음 실험은 없다. 이번 배치는 보고 후 종료한다.

## 이전 확인 결과 — 실험 전달 절차 (2026-10-28)

- 사용자 지시를 [EXPERIMENT_DELIVERY](orchestration/EXPERIMENT_DELIVERY.md)와 AGENTS/NEXT에 반영했다. 앞으로 배정부터 실제 결과 화면 확인까지 한 작업으로 처리한다. 세부 명령과 최신 검증 범위는 [DELIVERY_VALIDATION](orchestration/DELIVERY_VALIDATION.md)을 따른다.
- Sol high는 등록 CLI, Terra high는 담당 카드, Astra high는 독립 검토를 실제 native Task/Dispatch로 수행했다. 기존 Astra max 총괄/Run/환경/공통 runtime을 재사용했다. 새 모델 다운로드·실험·학습은 없다.
- `complete assign/complete/status`는 보고서·metrics·별도 검토 SHA와 로컬 artifact를 검증한다. 동일 재시도는 중복 없이 처리하며 실패 도중 남은 binding도 EXP ID로 고정한다. `verify_delivery`는 GitHub ref/파일 대조와 실제 브라우저 확인을 분리한다.
- 63개 Python fixture와 Node 카드/보고서 펼치기 검증을 통과했다. 최초 독립 검토의 F1~F4와 수정/재검토는 삭제하지 않는다. 실제 브라우저 결과와 게시 상태는 검증 보고서가 원본이며 코드 통과만으로 화면 완료를 추정하지 않는다.
- **남은 작업:** 첫 실제 새 실험은 아직 배정/실행하지 않았다. 다음 승인된 실험에서 native 진행 상태 카드와 완료 후 보고서·그래프·등록 영상·총괄 검토까지 다시 확인해야 한다. TEST 합성 자료는 격리 runtime 전용이며 공개 카탈로그에는 EXP-0001~0007만 남아 있다.

## 이전 확인 결과 — Orca 로컬 실험실 (2026-10-28)

- [실제 세팅 보고서](orchestration/LOCAL_SETUP_REPORT.md), [ADR-0013](decisions/ADR-0013-orca-local-experiment-lab.md). clean main에서 최신 지시를 fast-forward한 뒤 lab/infra/web/review worktree로 분리했다. 원본·기존 환경 변경 없이 새 `.venv-orca-lab`만 사용했다.
- 총괄 Astra max, 실행기 Sol high, 화면 Terra high, 독립 검토 Astra high를 실제 thread 메타데이터와 실행 기록으로 확인했다. 하나의 Orca Run을 유지하며 세팅 작업만 배정했다. 담당1/2/3은 앞으로의 실험 슬롯으로 아직 미배정이다.
- 공통 runtime `/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab`, GPU 큐는 그 아래 `gpu-queue`. 서로 다른 worktree도 반드시 같은 절대 runtime을 사용한다. SQLite+flock CPU mock 직렬화, 실패 후 다음 작업, 중복 방지/장애 복구를 검사했다. 현재 실제 GPU 명령은 미등록이다.
- 웹 **http://127.0.0.1:8765/**: 총괄→담당1·2·3/미배정→선택 보고서/동일 metrics 그래프/근거 미디어/검토/다음 작업. EXP-0001~0007의 실제 기록을 표시하고 과거 미기록 모델·effort와 최종 정확도는 null이다. EXP5/6 영상4개 재생·seek, EXP7 이미지6개 decode, 파일 부재 안내 확인. 미디어는 로컬 브라우저만 읽었다.
- **32개 fixture 통과** 및 실제 queue/web 재시작 smoke 통과. 기존 2,086파일 size/mtime, 선택430파일 SHA256, 두 환경 freeze 일치. 독립 검토가 stale review/수집기 startup/FIFO/재시작 근거 문제를 찾아 수정했고 초기 보고서들을 보존했다. 최종 좁은 재검토에서 R4도 해결로 판정했다. 전체 검증·게시 내역은 LOCAL_SETUP_REPORT를 따른다.
- 신뢰/업데이트는 사용자가 직접 완료했다. WSL bridge 승인, null launch 모델 필드, TIME_WAIT 재시작 실패, 새 터미널의 빈 환경변수 문제와 해결을 기록했다. 완료 작업자는 worker_done 확인→release→ack로 정리한다.
- **남은 문제:** supervisor 사망 중 timeout 강제 불가, 협력하지 않는 외부 GPU 프로세스 제어 불가, 무인 운영/실제 모델 작업 미검증. 사용자 행동 정답과 카메라 독립성은 여전히 미확정이다.
- **다음 결정:** 기존 VLM 실제 입력 시트와 사용자 검수를 기준으로 소규모 비교 배치의 manifest·중단 조건·후보 제한을 제안만 한다. 새 다운로드/추론/학습/CV 연동은 배치 승인 전 실행하지 않는다. 시작·중지·복구 명령은 LOCAL_SETUP_REPORT를 사용한다.

## 최근 확인 결과 — EXP-0007 독립 로컬 VLM (2026-10-28)

- [EXP-0007](experiments/EXP-0007-local-vlm-action-analysis.md), [ADR-0012](decisions/ADR-0012-local-vlm-clip-analysis.md). 이번 사용자 승인으로만 VLM 금지를 제한 해제. Qwen3-VL-2B-Instruct 한 모델, `.venv-vlm` 분리, 기존 `.venv`/CV/추적/경계 변경 없음. EXP-0006 기본 적용 보류 유지.
- 원본5초6클립(007접근/넘기,030넘기,006통행,001넘기,031접촉·가림), 실행 전 manifest/prompt 고정. 전체화면10프레임/약2fps, 실제448×768/1680영상토큰, 원본PTS·추가sampling0·중복0 확인. 익명 독립대화, 라벨/보고서/CV표시 미제공, 로컬 offline 추론.
- BF16 비양자화 RTX3080 GPU 전용, OOM0. run02 로딩1.205초(캐시 warm), 클립 전처리.111~.141초/생성2.805~10.595초, peak allocated 약4.346GiB. 영상 확보/추출 시간을 제외한 생성 시간을 실시간 탐지지연으로 쓰지 않음.
- 접근/보행 일부 부합하지만 넘기를 문 열기/이동으로 설명하고 의도·문 개폐 근거 환각. 030은 반복으로384토큰 중단. 031 가림도 적절한 판단 유보 못함. 모든 strict JSON 파싱 실패(코드펜스;030은본문도미완결). **기본 도입/자동 CV 연동 보류**.
- 최초run01은 생성 후 UnicodeEncodeError로 응답 본문 저장 실패. 로그/빈파일 보존, UTF-8 명시·token IDs 선저장 후 같은조건run02완료. 원응답/실패 로컬 보존, 프롬프트 수정·의미별 재질문 없음.
- 다음: `outputs/vlm_exp0007/run02/clip*/actual_input_review.jpg`와 보고서 요약을 대조해 검수 기준 확정. 정밀GT/범용성/오탐률 미주장. 사용자 선택 클립 분석이지 자동 사건 발견이 아님. 미디어/가중치/원응답 로컬, 코드/manifest/ADR/요약/lock GitHub.

## 최근 확인 결과 — EXP-0006 후보 뒤 박스 일관성 검토

- [EXP-0006](experiments/EXP-0006-candidate-box-consistency.md), [ADR-0011 고정 기준](decisions/ADR-0011-candidate-box-consistency.md). 기존 C 네 구간 2,060프레임/네 후보 그대로 사용. 검출·추적·경계 후보 생성 재실행 없음.
- 후보 전후 .2초 실제 관측, ≤.2초 쌍의 높이/폭 배율≥1.5 및 상하단 이동 차이 검사. 실행 전 한 세트 고정, 결과 보고 튜닝 없음.
- 007 두 후보는 큰 박스 변화 증거가 있으나 대기 중 관측 누락으로 **근거 부족**(56.833333/56.966667 결정). 030 #3/#4 모두 **판단 유보**(90.5 결정). 모두 emission+.2초. 통과 0, 실제 넘기 후보도 유보해 **기본 적용 보류**.
- 기존 후보를 지우지 않고 pending/통과/유보/근거 부족을 별도 부가. 통과≠침입, 유보≠정상. 006/031 후보0은 개선 아님. 새 모듈은 기본 CV 경로에 연결하지 않음.
- 35테스트, disabled 원래 후보 정확 재현·입력 객체 불변·미래 관측 방지 검증. 핵심 영상은 `outputs/cv_phase2g/video{007,030}/raw_C_review_normal_then_quarter.mp4` 두 개. 원본/기존 후보/검토 상태, 정상→.25배속.
- 사용자 메시지의 007 순간 박스 변화 관찰은 대화 속 ChatGPT 프레임 관찰이며 전 구간 사용자 확정 정답 아님. 030은 Codex 초안 유지. 남은 문제: 과도 유보 비용·안정 부분 박스 통과·정밀 사건 정답 부족. 다음은 두 자료의 검토 효용 확인, 자동 설정 교체/추가 튜닝 없음.

## 최근 확인 결과 — EXP-0005 두 후보 구간 집중 검수

- [집중 검수 초안](experiments/EXP-0005-candidate-focus-review.md). 007 55.9~57.0 / 030 89.6~90.5의 62연속 프레임과 저장된 관측·경계 조건 대조. 새 검출/추적 실행 없음.
- 007 #2는 앞 분홍 신발 인물의 부분→긴 신체 박스 변화(②)가 우세. 56.633→56.667 하단 y 114.70px 변화. 명확한 ID 이동은 관찰 못했으며 겹친 신체 소유 범위는 유보.
- 030 #3 오른쪽/#4 중앙 인물 대응 초안. 실제 넘기와 박스 축소가 함께 작용(④=②+③). 두 track이 모두 한 사람 중복이라고 확정하지 않으며 독립 성공 2건으로도 세지 않음.
- 네 후보 anchor~emission 실제 관측 연속. 007 반대 방향 후보는 방향이 바뀌면 cooldown 대기 없이 허용하는 기존 코드로 설명. ID 연결의 적절성과 bbox 하단의 경계 기준 적절성은 별개.
- 로컬 `outputs/cv_phase2f/{007,030}/raw_B_C_normal_then_quarter.mp4`: 각 파일 정상→0.25배속, 원본 PTS/RAW/B/C/ID·H/L·하단 중심점/예측 점선 표시. 각각 ±1초 포함. 자료 2개만 먼저 사용자 검수.
- **남은 문제:** 사용자 확정 정답 아님. 가림/중복 소유 범위/실제 통과 시점 미확정. **다음 결정:** 박스 범위 시간적 일관성을 확인해 경계 후보를 유보하는 방안 한 가지 제안, 미구현·설정 불변. ID 이동이 확인되면 우선순위 재검토.
- 기존 보고서·출력·공식 라벨 보존. 새 코드도 표시/수치 감사만 수행. 전체 35프레임 재검수 요청으로 확대하지 않음.

## 최근 확인 결과 — EXP-0005 ByteTrack 캐시 비교 (2026-10-28)

- [EXP-0005](experiments/EXP-0005-bytetrack-cache-comparison.md), [35프레임·연속 후보 검수](experiments/EXP-0005-visual-review.md), [ADR-0010 사전 설정](decisions/ADR-0010-bytetrack-cache-comparison.md).
- FCOS 재추론/가중치 다운로드 없이 기존 네 구간 2,060 person 캐시 재사용. A=기존 IoU ≥.5, B=ByteTrack high ≥.5, C=B+low ≥.25·<.5의 2차 연결. 신규 ≥.6, buffer30 등 B/C 공통 고정. 공식 MIT tracker subset 고정 SHA·변경 내역·최소 의존성 기록.
- A 전체 레코드와 기존 EXP-0004/0002 결과 정확 일치. 24테스트, 모든 실제 관측의 캐시 대조, 예측 이벤트 금지, 후보 anchor~emission 연속 관측 검사 통과. 이전 출력/캐시/JSON/config 412파일 보존.
- 경계는 ByteTrack ID와 실제 대응 검출 bbox만 사용. Kalman 예측/미확인 상태는 별도 저장하며 경계 입력 제외. 빈 관측 프레임·PTS gap>.1초는 경계 상태 reset.
- B의 007 50→52초 두 사람 연결, C의 030 넘기/006·031 일부 low 관측 연결에서 국소 이점. C의 007 중복·배경 track 유지, 031 후반 누락 및 가림 정체 불확실도 남음.
- 후보는 A/B 모두 0, C 030 2개(90.300초)·007 2개(56.633/56.767초). 030 실제 넘기와 겹치지만 bbox 부분/완료 판정 유보. 007은 문 밖 접근·서기 중 bbox 하단 변화에 의한 실패 의심, 침입 성공으로 세지 않음.
- 로컬 `outputs/cv_phase2e/review{ID}/continuous_ABC.mp4` 네 영상 + 동일 35이미지 + 030/007 후보 전후 62연속 프레임 카드. 원본 상대 PTS/프레임 수 검증. 관측·예측·low·unconfirmed 표시 구분. 전체 영상 사람별 수동 정답은 미완료.
- **남은 문제/다음 결정:** ByteTrack은 후속 검증 후보이며 기본 tracker 교체 보류. 030 #3/#4, 007 #2·중복·배경, 031 #1의 정체/부분 신체를 사용자와 검수. 006 ROI 밖/프레임 불일치, 카메라 누수/G1E 미확정 유지. 최종 IDF1/HOTA/침입 정확도 없음.
- CPU 캐시 추적/경계 시간만 측정, 전체 영상 추론 FPS 아님. 코드·문서·라이선스만 게시, 영상·이미지·캐시·원시 결과 로컬. 상세 다음 작업은 CODEX_NEXT_TASK.

이하 EXP-0004 및 이전 내용은 당시 이력이며 최신 결정은 EXP-0005를 따른다.

## 최근 확인 결과 — EXP-0004 최종 점수 기준 비교 (2026-10-28)

- [EXP-0004](experiments/EXP-0004-fcos-score-threshold-comparison.md), [35프레임 검수 초안](experiments/EXP-0004-visual-review.md), [ADR-0009](decisions/ADR-0009-fcos-threshold-adoption-hold.md).
- 같은 네 구간 2,060프레임을 각 한 번 추론해 모델 반환 person 캐시를 로컬 저장. 내부 score/top-k/NMS/global cap/입력/가중치 고정, 마지막 ≥0.5/0.4/0.3/0.25만 비교. 조건별 tracker 새로 생성.
- 수집 0.5와 캐시 재생 0.5 모두 기존 EXP-0002의 2,060프레임 레코드 정확 일치. 고정 35검수 PTS 동일, 테스트 16개 통과, 이전 출력·공식 JSON·config 258파일 보존 해시 확인.
- 030 90초 0/0/2/4박스: 일부 인물 부근 복원이나 부분·중복 포함, 왼쪽 사람은 누락. 006/031도 일부 복원. 007 중복과 배경 의심 증가. 차량 앞유리 내부의 실제 사람 유무 등 불확실 판정은 확정 오탐으로 계수하지 않음.
- 030 90초 복원 ID는 0.3에서 2~3프레임, 0.25에서 각각 1프레임. 031/0.4 최장 15.967초 ID는 상점 고정 물체 의심 영역. ID 통계를 실제 사람/성공 건수로 해석하지 않음. 16조건 경계 후보 모두 0.
- **남은 문제:** 사용자 정밀 시각 검수·개별 사람의 연속 대응 미완료, 가림·부분 신체·배경 유보, 006 ROI 밖/4006·4011 차이, 031 접촉/공식 시작/미완료 종료, G1E·카메라 분할 미확정.
- **다음 결정:** 기준 하향 채택 보류, 기본 0.5 유지(최적성 주장 아님). 같은 로컬 비교 이미지의 의미 검수와 연속 구간 정답 확정 우선. 재생 FPS를 모델 속도로 쓰지 않음. 모델/VLM/학습/고급 tracker 추가 없음.
- 로컬 `outputs/cv_phase2d/`: cache{ID}, replay{ID}/t050,t040,t030,t025, review{ID}/compare_*.jpg, temporal_review.json. 미디어/캐시/가중치는 Git 제외. 코드·테스트·문서만 게시.

이하 EXP-0003 및 이전 내용은 당시 이력이며 최신 결정은 위 EXP-0004를 따른다.

## 최근 확인 결과 — EXP-0003 FCOS 후보 소실 진단 (2026-10-27)

- [EXP-0003](experiments/EXP-0003-fcos-candidate-diagnostics.md): 사용자 확인 030 84초/90초의 3명 장면을 기준으로 내부 단계 계측. 원인 가설을 확정하지 않음.
- 같은 설정으로 84~96초 포함 361프레임 재실행, 기존 최종 bbox/score/track_id/PTS 전부 동일. 내부 shadow 후처리도 공식 반환과 매 프레임 정확히 일치.
- 90초 실제 사람 위치와 겹치는 낮은 점수 후보가 있었음. raw 최고 0.337676, 내부 통과 57→NMS 후 11→global cap 후 4→최종 ≥0.5 0. 고득점 후보가 NMS에 모두 제거된 경우 아님. ROI 검출 삭제도 아님.
- 사람별 위치 초안, 내부 score/전체 cap/NMS/최종 필터 탈락 및 억제 박스 관계는 보고서·로컬 검수 카드에 기록. 14개 테스트 통과. 진단용 낮은 점수는 최종 검출과 분리.
- **남은 문제:** 자세/가림에 따른 점수 하락의 인과 원인·사람별 정확한 후보 대응은 미확정. 사용자 제공 bbox는 없으며 Codex 위치 사각형은 진단 초안이다.
- **다음 결정:** 같은 설정의 소량 검수에서 score와 위치 회귀/부분 신체 대응을 분리해 조사할지 검토. 모델 채택/threshold/NMS 변경을 승인한 결과가 아님. 계측 FPS를 기존 FPS와 비교하지 않는다.
- 원본·기존 출력·공식 라벨 보존, 미디어/NPZ/원시 JSON/가중치는 로컬에만 둠. 자세한 다음 작업은 CODEX_NEXT_TASK.

## 최근 확인 결과 — Phase 2B 검출기 비교 (2026-10-27)

- [EXP-0002](experiments/EXP-0002-fcos-detector-comparison.md), [ADR-0008](decisions/ADR-0008-fcos-detector-comparison.md): FCOS ResNet50-FPN COCO_V1 추가 1개, 재학습 없이 실행. 실제 내부 749×1333/padded 768×1344, 모델과 해상도가 함께 변한 비교.
- 같은 네 smoke 구간 2,060프레임, 기존 config/추적 유지. PTS/해시 대조 및 테스트 13개 통과. 기존 EXP-0001·출력·원본 라벨 보존.
- 35개 paired frame에서 사람 일부 복원 확인, 030 넘기 자세/031 가림·006 원거리 누락 잔존. 007 중복 bbox와 연결 모호성, 031 상점 앞 고정 물체 오검출 의심을 기록. 원시 bbox 증…4333 tokens truncated…·평가 분할 독립성 확인. 상용/공개 미디어 사용 권리는 별도 해결.
- 실제 안전 담당자 업무 효용·모델 성능·지연·GPU 자원은 미측정. 이번에는 모델 구현·추론·학습을 하지 않음.

## 다음 결정 — 현재

1. 감사 결과와 사용자 검수로 G1B Go / Conditional Go / No-Go 결정.
2. 관찰 가능한 사건 태그·설명·근거 구간의 검수 기준과 첫 MVP 범위 선택. 사람 넘어짐과 물체/구조물 낙하 구분은 후보이며 미확정.
3. 데이터 조건을 보완한 후에만 G2 모델/최소 구조 비교로 이동. UI/API/검색·VLM 서버 구현은 아직 시작하지 않음.

## 제품 목표 및 감사 착수 전 기록 (2026-10-27, ADR-0003)

- **목표:** 안전 담당자가 **이미 선택한 짧은 사건/이상상황 영상**을 AI 보조로 검토·정리하는 제품 시나리오. 행동/사건 태그, 근거 프레임·구간 후보, 검토용 설명을 사람이 수정·확정하는 흐름을 가정한다.
- **아직 미검증:** 실제 안전 담당자의 요구와 소요 시간 절감, 분석 모델, 아키텍처, 실시간 성능, 검색 품질. 검색·보고서 초안은 후속 기능 후보다.
- **현재 우선순위:** iSafetyBench의 영상 접근, 정답 스키마, clip별 다중 행동, 설명/근거 가능성, 라이선스, 중복 출처 검증.
- 공개 배포 데이터셋 카드에 `cc-by-nc-sa-4.0`가 표시되지만 유튜브 원본 영상 권리는 별개라고 안내한다. 실제 사용·재배포 조건과 파일은 Codex에서 다시 확인한다.
- **Codex 다음 파일:** [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md), [iSafetyBench 감사 계획](data/ISAFETYBENCH_AUDIT_PLAN.md). 산출물: `docs/data/ISAFETYBENCH_SAMPLE_AUDIT.md`.
- **의사결정:** [ADR-0003](decisions/ADR-0003-incident-review-product-direction.md) / [업무 흐름](PRODUCT_WORKFLOW.md).
- 감사 착수 당시 iSafetyBench는 미채택·샘플 미확보였으며, 현재 8개 감사 결과는 위 최신 기록을 따른다. 최종 채택은 여전히 보류한다.
- 예전 `SAMPLE_AUDIT.md`는 이력으로 보존하며, 패널 단순 상태 분류를 다시 메인으로 채택하지 않는다.

## 최신 방향 변경 (2026-10-26, ADR-0002)

- 사용자와 함께 앞쪽 프레스의 **왼쪽 전기함 도어가 닫힌 화면과 열린 화면**을 비교해 패널 라벨 대상을 확인함. 이는 업로드된 비교 이미지에 대한 검수이며 8개 영상 전체 재생 검수를 완료했다는 의미가 아님.
- **패널 열림/닫힘의 단순 상태 분류는 SceneGuard 메인 MVP에서 제외**. 상태는 비교적 명확하지만 문을 여는 시간적 행동·위험 원인까지 뒷받침하지 못하며, 복합 위험행동/사고 맥락 분석이라는 포트폴리오 목표와 범위가 다름.
- 기존 `SAMPLE_AUDIT.md`, 8개 원본 영상, 검사 코드, Conditional Go 판정은 역사적 근거로 **유지**. 기존 판정은 당시 데이터 확보·부분적 라벨 확인에 대한 것.
- 다음 검토 대상은 **iSafetyBench**. 복합 산업안전 행동과 사고 영상에 대한 **사후 사건 분석·검토 보조** 가능성을 조사하되, **메인 데이터로 아직 확정하지 않음**.
- 참조: [ADR-0002](decisions/ADR-0002-reconsider-safety-dataset.md), [Codex 다음 작업](CODEX_NEXT_TASK.md), [새 데이터 감사 계획](data/ISAFETYBENCH_AUDIT_PLAN.md).
- 다음 산출물: `docs/data/ISAFETYBENCH_SAMPLE_AUDIT.md`. 원본 영상은 로컬에만 저장.
- 해당 다음 작업 전까지는 모델·학습·VLM·대시보드 구축을 진행하지 않음.

## 지금까지 결정/완료
- 연구 → 데이터 → 요구·평가 정의 → 모델 선택 순서 유지. YOLO/추적기/VLM 등 모델은 미선정.
- 최초 업데이트 검토에서 소량 데이터 감사를 권장했고, 이후 사용자 요청에 따라 실제 다운로드·검사를 수행함.
- **[SAMPLE_AUDIT.md](data/SAMPLE_AUDIT.md)** 작성: 출처/이용 조건, 공식 배포 라벨 연결, 영상별 관찰 시각, 제약, Conditional Go 의견.
- HF revision `7369ff1830b5f6c00f7d7383eeeaa90704bfc5b5`의 samples.json 확인. 691개 레코드, 영상 단위 단일 클래스, train 566/test 125. frames.json은 비어 있음.
- 정상 4개·위험 4개만 다운로드. 통로 정상/이탈, 패널 닫힘/열림 각 train 1개·test 1개. MP4 총 123,152,506 bytes.
- 8개 영상 전체 1,639프레임 디코딩 성공, FFmpeg 오류 없음. 해상도 1920×1080, 표시 FPS 24.80~25.08.
- 12개 시점/영상의 접촉표 96프레임 및 일부 원해상도 프레임을 Codex가 시각 검토. 사람이 전체 재생 검수한 상태는 아님.
- 6개는 관찰 시점에서 라벨 부합, `4_tr32`는 원거리 통로 경계 불명확, `0_tr19`는 설비 작업 구역과 통로 위반 구분에 추가 검수 필요.
- 원본/배포 페이지 CC BY 4.0 표기 확인. 원본 Mendeley 개별 파일과 라벨·해시 대조 및 공개 이미지 별도 권리 검토는 미수행.

## 로컬 파일·재현
- 영상: `data/safe_unsafe_audit/data/` (8개 MP4).
- 메타데이터, 개별 URL·SHA256·실측값: `data/safe_unsafe_audit/manifest.json` 및 동일 폴더 JSON들.
- 접촉표와 추출 이미지: `data/safe_unsafe_audit/previews/`.
- 스크립트: [audit_samples.py](../scripts/audit_samples.py).
- 실행: `uv run --no-project --with imageio-ffmpeg==0.6.0 --with pillow==12.3.0 python scripts/audit_samples.py`
- 시스템 디코더 부재로 uv 임시 도구 환경 사용. 전체 데이터셋·모델 다운로드, 학습, 업로드는 수행하지 않음.

## 이전 Safe and Unsafe Behaviours 감사의 남은 문제
- 사용자 실제 재생 검수와 G1 최종 승인.
- 라벨 대상 사람/패널과 통로 경계 확인. 정상 클래스는 화면 전체가 안전하다는 뜻이 아님.
- 사건 시작/종료·박스·추적 정답이 이 HF 배포에 없음. 추가 수동 라벨 범위 결정 필요.
- train/test에 같은 설비·유사 구도 존재. 원본 세션·카메라 ID가 없으므로 누수 여부 미확인. 감사에 사용한 test 영상은 최종 블라인드 평가용에서 구분해야 함.
- RTX 3080 VRAM·드라이버·추론 성능은 미확인. 이번에는 GPU 사용 안 함.

## 이전 감사 단계의 다음 결정 (현재 지시 아님)
1. 사용자 검수 후 Go / Conditional Go / No-Go 확정. 현재 Codex 의견은 **Conditional Go**.
2. 첫 후보로 패널 열림/닫힘 **상태**를 추천. 패널을 여는 동작의 시각 검증은 이번 영상으로 입증하지 못함.
3. 통로 후보는 ROI·대상 보행자·설비 작업 구역 예외부터 정의.
4. 평가 단위와 추가 라벨링 계획을 확정한 후 새 ADR에서 최소 모델 후보를 비교. 학습·서버 구축은 아직 시작하지 않음.

## 기존 메모에 대한 안내

위의 '다음 결정'에 있던 패널 첫 후보 추천은 **ADR-0002 이후의 현재 작업 지시가 아니라 과거 감사 단계의 제안**이다. 현재 우선순위는 iSafetyBench 후보의 실제 데이터/주석/라이선스 검증이다.
