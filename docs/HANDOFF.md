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
- 35개 paired frame에서 사람 일부 복원 확인, 030 넘기 자세/031 가림·006 원거리 누락 잔존. 007 중복 bbox와 연결 모호성, 031 상점 앞 고정 물체 오검출 의심을 기록. 원시 bbox 증가를 정확도 개선으로 취급하지 않음.
- 이번 FCOS 처리 15.285~15.967 FPS, peak allocated 약 434.08 MiB. 기존 SSD 8.937~11.428 FPS/85.35MiB와 비교하되 과거 실행·배경 부하 차이 때문에 속도 우위 확정 안 함.
- 모든 경계 후보 0. FCOS는 후속 검증 후보로 유지하되 메인 채택 보류. 모델/해상도 효과 분리 안 됨. 학습·VLM·고급 tracker·UI 없음.
- **남은 문제/다음 결정:** 031 고정 물체 판정, 중복/미탐 검수, 사람별 시점·음성 범위·카메라 그룹/G1E 확정. 다음 순서는 CODEX_NEXT_TASK를 따른다. 영상 끝 완료 상태와 006 프레임 차이는 해결되지 않음.
- 이미지/추론 JSON/가중치 모두 로컬. GitHub에는 코드·선정 근거·실측 집계·제한/다음 계획만 기록한다.

이하 Phase 2A 및 이전 승인·감사 내용은 당시 이력이다.

## 최근 확인 결과 — Phase 2A 첫 CV 진단 (2026-10-27)

- [EXP-0001](experiments/EXP-0001-phase2a-cv-baseline.md): 사전학습 SSDLite320 COCO_V1 한 개 + 인접 IoU 연결 + 카메라별 유한 경계 규칙을 로컬 CLI로 구현. [실행 계약](design/CV_BASELINE_CLI.md), [선정 근거 ADR-0007](decisions/ADR-0007-phase2a-detector.md).
- RTX 3080 10GB, WSL2/Python 3.10.12, torch 2.5.1+cu124 / torchvision 0.20.1+cu124에서 CUDA 실행 확인. `.venv` 격리, 가중치 14,069,355 bytes 로컬 전용. 학습·VLM·UI 없음.
- 006/007/030/031의 4개 짧은 개발 구간 및 007 전체 클립 진단. 실행별 실제 값·실패·속도·메모리·재현 명령은 EXP-0001의 측정 표를 따른다. 인공 규칙 테스트 11개 통과.
- smoke에서 030은 480프레임 중 1프레임만 사람 검출, 031은 검출 0. 007은 접근 시 일부 검출 후 연결 단절. 낮은 후보 수를 정확도나 정상 판별 성공으로 취급하지 않음.
- 006 후기 보행자는 검출되지 않았고 설정한 가까운 출입문 감시 범위 밖이기도 함. 비이벤트 후보 상태·4006/4011 프레임 불일치 유지. 006/007은 같은 카메라 후보, 전부 development.
- **다음 결정:** 현재 SSDLite320을 메인 모델로 채택하지 않음. 검출 해상도/가림/감시 경계 범위를 먼저 검토하고 다음 비교 실험 여부 결정. tracker 복잡화는 검출 문제와 분리해 판단. 사람별 정밀 시점·검수 음성·카메라 분할/G1E 최종 승인은 계속 미완료.
- 원본/정답/이미지/가중치/추론 JSON/환경 캐시 모두 Git 제외. 출력은 통과 후보이며 물리적 완료·법적 무단침입 판단 unknown.

## 최신 승인/실행 지시 — CV baseline 프로토타입 (2026-10-27)

- **사용자 "응 시작하자" 승인:** [ADR-0006](decisions/ADR-0006-limited-cv-baseline-prototype.md)의 범위에서 **사전학습 사람 검출 1개 + 최소 IoU 연결 + 카메라별 경계 양측 이동**을 소규모로 구현/로컬 실행한다. 이는 **개발 진단 허용**이며 AI-Hub 메인 데이터 최종 G1E 승인, 모델 채택, 정량 성능 검증을 의미하지 않는다.
- Codex가 수행할 지시: [CODEX_NEXT_TASK.md](CODEX_NEXT_TASK.md) (Phase 2A). RTX 3080/WSL2 환경 확인 → 모델·가중치 출처/라이선스 검토 → 최소 Python CLI·PTS 기반 후보 기록·synthetic test → **006,007,030,031 중 2~4개** 로컬 짧은 테스트 → 실패·처리시간 결과 기록/커밋.
- **특히 주의:** 006 공식 JSON frame_count 4,011 vs 실제 디코딩 4,006. 119~132초 근처 보행은 검수된 '정상 정답'이 아니라 **비이벤트 후보**; 사람별 정밀 시작과 카메라 분할 미확정. 초기 실험을 final test나 FP/hour 최종 성능으로 표현 금지.
- 울타리 넘기 시도/물리적 완료·법적 무단침입을 baseline의 단순 2D 선 통과와 동일시하지 않는다. VLM, 재학습, 웹 UI, 대량 추가 자료는 현 범위 밖.
- **지금 GitHub에 업데이트한 것은 …15548 tokens truncated… "exp6-007",
          "kind": "video",
          "label": "007 원본/후보/검토"
        },
        {
          "artifact_id": "exp6-030",
          "kind": "video",
          "label": "030 원본/후보/검토"
        }
      ],
      "execution_status": "completed_with_recorded_limitations",
      "experiment_id": "EXP-0006",
      "limitations": [
        "개발 표본이며 독립 테스트 아님",
        "정밀 정답·카메라 독립성 미확정",
        "과거 agent model/effort·통합 run 해시가 없는 필드는 null; 측정 원천별 해시는 metrics에 보존"
      ],
      "metric_definitions": "records/EXP-0006/metrics.json",
      "metrics_path": "records/EXP-0006/metrics.json",
      "metrics_sha256": "df8cfd45383b23ffbe561c5ac5a39aacf45ed2f8e61b91d1baf3e82efb4be742",
      "next_step": "기본 적용 보류. 0.2초 대기는 실제 경보 전달 지연을 추가한다.",
      "reasoning_effective": null,
      "report_path": "docs/experiments/EXP-0006-candidate-box-consistency.md",
      "report_sha256": "6aea3068b517b90cc8512a0e207c2487767b9d04d2f7b30808f5ba73f3231ea5",
      "review_binding_path": "docs/reviews/ORCA-SETUP-historical-import.binding.json",
      "review_path": "docs/reviews/ORCA-SETUP-historical-import.md",
      "review_status": "AI_draft",
      "role": "historical_import",
      "run_id": "historical-EXP-0006",
      "schema_version": 1,
      "slot": "unassigned",
      "summary": "007은 근거 부족, 030은 판단 유보로 남아 유용한 후보도 함께 막았다.",
      "task_id": null,
      "timestamp_scope": "record import time; not experiment start or completion time",
      "title": "박스 일관성 후보 검토",
      "updated_at": "2026-10-28T06:10:10.469768+00:00",
      "worker_opinion": "007은 근거 부족, 030은 판단 유보로 남아 유용한 후보도 함께 막았다."
    },
    {
      "agent_model_effective": null,
      "agent_model_requested": null,
      "attempt_id": null,
      "code_sha": null,
      "config_hash": null,
      "created_at": "2026-10-28T06:10:10.469768+00:00",
      "data_manifest_hash": null,
      "decision_status": "adoption_on_hold",
      "evaluated_model": "Qwen3-VL-2B-Instruct",
      "evidence": [
        {
          "artifact_id": "exp7-clip01",
          "kind": "image",
          "label": "clip01 실제 모델 입력 검수 시트"
        },
        {
          "artifact_id": "exp7-clip02",
          "kind": "image",
          "label": "clip02 실제 모델 입력 검수 시트"
        },
        {
          "artifact_id": "exp7-clip03",
          "kind": "image",
          "label": "clip03 실제 모델 입력 검수 시트"
        },
        {
          "artifact_id": "exp7-clip04",
          "kind": "image",
          "label": "clip04 실제 모델 입력 검수 시트"
        },
        {
          "artifact_id": "exp7-clip05",
          "kind": "image",
          "label": "clip05 실제 모델 입력 검수 시트"
        },
        {
          "artifact_id": "exp7-clip06",
          "kind": "image",
          "label": "clip06 실제 모델 입력 검수 시트"
        }
      ],
      "execution_status": "completed_with_recorded_limitations",
      "experiment_id": "EXP-0007",
      "limitations": [
        "개발 표본이며 독립 테스트 아님",
        "정밀 정답·카메라 독립성 미확정",
        "과거 agent model/effort·통합 run 해시가 없는 필드는 null; 측정 원천별 해시는 metrics에 보존"
      ],
      "metric_definitions": "records/EXP-0007/metrics.json",
      "metrics_path": "records/EXP-0007/metrics.json",
      "metrics_sha256": "270fd6fcba459880a8e31e30f5058fb048858298aad8d8be124ca5fc59f4fc6d",
      "next_step": "기본 연동 보류. 실제 입력의 행동과 설명을 사람과 검수한 뒤 다음 대조를 설계한다.",
      "reasoning_effective": null,
      "report_path": "docs/experiments/EXP-0007-local-vlm-action-analysis.md",
      "report_sha256": "6e0547b4c298de232cac9532e1abebd315c9e6c1f6d9b1c3dee37c235317eda7",
      "review_binding_path": "docs/reviews/ORCA-SETUP-historical-import.binding.json",
      "review_path": "docs/reviews/ORCA-SETUP-historical-import.md",
      "review_status": "AI_draft",
      "role": "historical_import",
      "run_id": "historical-EXP-0007",
      "schema_version": 1,
      "slot": "unassigned",
      "summary": "통행 일부는 설명했으나 넘기 누락·문 열기 환각·반복·JSON 파싱 실패가 남았다.",
      "task_id": null,
      "timestamp_scope": "record import time; not experiment start or completion time",
      "title": "독립 로컬 VLM 행동 분석",
      "updated_at": "2026-10-28T06:10:10.469768+00:00",
      "worker_opinion": "통행 일부는 설명했으나 넘기 누락·문 열기 환각·반복·JSON 파싱 실패가 남았다."
    },
    {
      "agent_model_effective": "gpt-6.1-sol",
      "agent_model_requested": "gpt-6.1-sol",
      "assigned_at": "2026-10-28T08:44:12.571516+00:00",
      "attempt_id": "8b93c06304724009b8ca5a0d15a28288",
      "decision_status": "adoption_on_hold",
      "dispatch_id": "ctx_c9acf995dc40",
      "evaluated_model": "Qwen/Qwen3-VL-2B-Instruct",
      "evidence": [
        {
          "artifact_id": "exp8-clip02-source",
          "kind": "video",
          "label": "clip02 · 사람 확인 우선 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp8-clip02-actual",
          "kind": "image",
          "label": "clip02 · 실제 Qwen 입력 시트"
        },
        {
          "artifact_id": "exp8-clip06-source",
          "kind": "video",
          "label": "clip06 · 사람 확인 우선 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp8-clip06-actual",
          "kind": "image",
          "label": "clip06 · 실제 Qwen 입력 시트"
        },
        {
          "artifact_id": "exp8-clip01-source",
          "kind": "video",
          "label": "clip01 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp8-clip01-actual",
          "kind": "image",
          "label": "clip01 · 실제 Qwen 입력 시트"
        },
        {
          "artifact_id": "exp8-clip03-source",
          "kind": "video",
          "label": "clip03 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp8-clip03-actual",
          "kind": "image",
          "label": "clip03 · 실제 Qwen 입력 시트"
        },
        {
          "artifact_id": "exp8-clip04-source",
          "kind": "video",
          "label": "clip04 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp8-clip04-actual",
          "kind": "image",
          "label": "clip04 · 실제 Qwen 입력 시트"
        },
        {
          "artifact_id": "exp8-clip05-source",
          "kind": "video",
          "label": "clip05 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp8-clip05-actual",
          "kind": "image",
          "label": "clip05 · 실제 Qwen 입력 시트"
        }
      ],
      "execution_status": "succeeded",
      "experiment_id": "EXP-0008",
      "limitations": [
        "기존6개 개발 클립; 독립 테스트·확정 정답 아님",
        "원문2/6·펜스 제거6/6은 행동 정확도가 아님",
        "새 CCTV 픽셀 검수 없이 기존 초안과 텍스트를 대조"
      ],
      "metric_definitions": "records/EXP-0008/metrics.json",
      "metrics_path": "records/EXP-0008/metrics.json",
      "metrics_sha256": "c3e4601b8e4f22184046f638e7625b2c1d0c1feab70e84050e6562c4999d7c53",
      "next_step": "사전 고정 EXP-0010 대조 한 번 및 02/06 로컬 사람 확인.",
      "reasoning_effective": "high",
      "registration_sha256": "d4dc380f67c655fccc3f939fb6bbc29c5bde8946da175b530e864b49a6cd3244",
      "report_path": "docs/experiments/EXP-0008-qwen-batch01.md",
      "report_sha256": "23e7ecd38efe894bc82e0db241ef4f010273654be17750c5c0d4708bedf9e7dd",
      "review_binding_path": "docs/reviews/EXP-0008.binding.json",
      "review_path": "docs/reviews/EXP-0008-coordinator-review.md",
      "review_sha256": "99cd5e633b6057adc6c38a198bcdd4863d114d28108e54185d6fd7901879d08d",
      "review_status": "accepted_for_comparison",
      "reviewed_metrics_sha256": "c3e4601b8e4f22184046f638e7625b2c1d0c1feab70e84050e6562c4999d7c53",
      "reviewed_report_sha256": "23e7ecd38efe894bc82e0db241ef4f010273654be17750c5c0d4708bedf9e7dd",
      "role": "experiment_worker",
      "run_id": "run_3d23462a014a",
      "schema_version": 1,
      "slot": "slot1",
      "summary": "6클립 생성 완료. 형식과 행동 이해를 분리: 완료 근거 부족·넘기 누락이 남아 채택 보류.",
      "synthetic": false,
      "task_id": "task_0bfc2bc3eafc",
      "title": "Qwen3-VL-2B 기준 실행",
      "worker_opinion": "실행 가능하지만 행동 구분 근거가 부족하다."
    },
    {
      "agent_model_effective": "gpt-6.1-sol",
      "agent_model_requested": "gpt-6.1-sol",
      "assigned_at": "2026-10-28T08:44:12.571596+00:00",
      "attempt_id": "ef353740b07d46d79ddb030e8d22ecd5",
      "decision_status": "adoption_on_hold",
      "dispatch_id": "ctx_b06f6387b019",
      "evaluated_model": "HuggingFaceTB/SmolVLM2-2.2B-Instruct",
      "evidence": [
        {
          "artifact_id": "exp9-clip02-source",
          "kind": "video",
          "label": "clip02 · 사람 확인 우선 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp9-clip02-actual",
          "kind": "image",
          "label": "clip02 · 실제 Smol 입력 시트"
        },
        {
          "artifact_id": "exp9-clip06-source",
          "kind": "video",
          "label": "clip06 · 사람 확인 우선 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp9-clip06-actual",
          "kind": "image",
          "label": "clip06 · 실제 Smol 입력 시트"
        },
        {
          "artifact_id": "exp9-clip01-source",
          "kind": "video",
          "label": "clip01 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp9-clip01-actual",
          "kind": "image",
          "label": "clip01 · 실제 Smol 입력 시트"
        },
        {
          "artifact_id": "exp9-clip03-source",
          "kind": "video",
          "label": "clip03 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp9-clip03-actual",
          "kind": "image",
          "label": "clip03 · 실제 Smol 입력 시트"
        },
        {
          "artifact_id": "exp9-clip04-source",
          "kind": "video",
          "label": "clip04 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp9-clip04-actual",
          "kind": "image",
          "label": "clip04 · 실제 Smol 입력 시트"
        },
        {
          "artifact_id": "exp9-clip05-source",
          "kind": "video",
          "label": "clip05 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp9-clip05-actual",
          "kind": "image",
          "label": "clip05 · 실제 Smol 입력 시트"
        }
      ],
      "execution_status": "succeeded",
      "experiment_id": "EXP-0009",
      "limitations": [
        "동일6개 개발 클립; 독립 테스트·확정 정답 아님",
        "형식·비용과 행동 이해는 별도이며 최종 정확도/F1 미산출",
        "현재 에이전트의 새 픽셀 검수 없이 기존 초안과 응답 근거 대조"
      ],
      "metric_definitions": "records/EXP-0009/metrics.json",
      "metrics_path": "records/EXP-0009/metrics.json",
      "metrics_sha256": "933d5598f37860e04b7aacaa669e4459ab7b3af789ec22380760a9935b9851a7",
      "next_step": "배치 종료. 02/06 로컬 사람 확인 후 별도 후속 범위 결정; 추가 자동 실행 없음.",
      "reasoning_effective": "high",
      "registration_sha256": "0f152b90001a1462dda4e50acb61ea042810387c407ae793134f20128febf14f",
      "report_path": "docs/experiments/EXP-0009-smol-batch01.md",
      "report_sha256": "14b2e95f45a07e34c6ad555350adf1ac5948862556bf58edfb0c29f142af69f0",
      "review_binding_path": "docs/reviews/EXP-0009.binding.json",
      "review_path": "docs/reviews/EXP-0009-coordinator-review.md",
      "review_sha256": "1d914e4c01b179ef871d2cdd4c0089ec92c7920b56f059ac5b75e54512ff450b",
      "review_status": "accepted_for_comparison",
      "reviewed_metrics_sha256": "933d5598f37860e04b7aacaa669e4459ab7b3af789ec22380760a9935b9851a7",
      "reviewed_report_sha256": "14b2e95f45a07e34c6ad555350adf1ac5948862556bf58edfb0c29f142af69f0",
      "role": "experiment_worker",
      "run_id": "run_3d23462a014a",
      "schema_version": 1,
      "slot": "slot2",
      "summary": "6클립 생성·원문 형식 통과. 선택지 반복·근거 모순·넘기 누락으로 채택 보류.",
      "synthetic": false,
      "task_id": "task_e56ab41484b8",
      "title": "SmolVLM2-2.2B 기준 실행",
      "worker_opinion": "짧은 생성 시간·형식 준수는 확인했으나 행동 이해의 효용은 확인 못함."
    },
    {
      "agent_model_effective": "gpt-6.1-sol",
      "agent_model_requested": "gpt-6.1-sol",
      "assigned_at": "2026-10-28T09:05:07.192448+00:00",
      "attempt_id": "c0fd8f0c63154c5d837d5c149bf948b5",
      "decision_status": "adoption_on_hold",
      "dispatch_id": "ctx_735ddbea9bba",
      "evaluated_model": "Qwen/Qwen3-VL-2B-Instruct",
      "evidence": [
        {
          "artifact_id": "exp10-clip02-source",
          "kind": "video",
          "label": "clip02 · 사람 확인 우선 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp10-clip02-actual",
          "kind": "image",
          "label": "clip02 · 실제 Qwen 큰 입력 입력 시트"
        },
        {
          "artifact_id": "exp10-clip06-source",
          "kind": "video",
          "label": "clip06 · 사람 확인 우선 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp10-clip06-actual",
          "kind": "image",
          "label": "clip06 · 실제 Qwen 큰 입력 입력 시트"
        },
        {
          "artifact_id": "exp10-clip01-source",
          "kind": "video",
          "label": "clip01 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp10-clip01-actual",
          "kind": "image",
          "label": "clip01 · 실제 Qwen 큰 입력 입력 시트"
        },
        {
          "artifact_id": "exp10-clip03-source",
          "kind": "video",
          "label": "clip03 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp10-clip03-actual",
          "kind": "image",
          "label": "clip03 · 실제 Qwen 큰 입력 입력 시트"
        },
        {
          "artifact_id": "exp10-clip04-source",
          "kind": "video",
          "label": "clip04 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp10-clip04-actual",
          "kind": "image",
          "label": "clip04 · 실제 Qwen 큰 입력 입력 시트"
        },
        {
          "artifact_id": "exp10-clip05-source",
          "kind": "video",
          "label": "clip05 · 원본 연속/2fps 입력 표본 비교"
        },
        {
          "artifact_id": "exp10-clip05-actual",
          "kind": "image",
          "label": "clip05 · 실제 Qwen 큰 입력 입력 시트"
        }
      ],
      "execution_status": "succeeded",
      "experiment_id": "EXP-0010",
      "limitations": [
        "동일6개 개발 클립; 독립 테스트·확정 정답 아님",
        "형식·비용과 행동 이해는 별도이며 최종 정확도/F1 미산출",
        "현재 에이전트의 새 픽셀 검수 없이 기존 초안과 응답 근거 대조"
      ],
      "metric_definitions": "records/EXP-0010/metrics.json",
      "metrics_path": "records/EXP-0010/metrics.json",
      "metrics_sha256": "5709e9b0163e8f61613191f082299f77d93ad699ce869e26d5aa408a0d7ead41",
      "next_step": "배치 종료. 02/06 로컬 사람 확인 후 별도 후속 범위 결정; 추가 자동 실행 없음.",
      "reasoning_effective": "high",
      "registration_sha256": "9836859a9ab21cc81742dd6f6302c04039832376a0ed6e769c47c43218aa68ae",
      "report_path": "docs/experiments/EXP-0010-qwen-high-pixels.md",
      "report_sha256": "1fca3eb7f7dce826140db2b80978e1c65a9b9b64ba762d8a35f7d5124a9e9ff7",
      "review_binding_path": "docs/reviews/EXP-0010.binding.json",
      "review_path": "docs/reviews/EXP-0010-coordinator-review.md",
      "review_sha256": "eeb5c7e1d96d2ac9a04eddc677ff665553dbc595f292f02e30524ff4450db91a",
      "review_status": "accepted_for_comparison",
      "reviewed_metrics_sha256": "5709e9b0163e8f61613191f082299f77d93ad699ce869e26d5aa408a0d7ead41",
      "reviewed_report_sha256": "1fca3eb7f7dce826140db2b80978e1c65a9b9b64ba762d8a35f7d5124a9e9ff7",
      "role": "experiment_worker",
      "run_id": "run_3d23462a014a",
      "schema_version": 1,
      "slot": "slot1",
      "summary": "전체 화면 픽셀 예산 대조 6클립 완료. 비용이 늘었고 행동 개선은 입증되지 않아 채택 보류.",
      "synthetic": false,
      "task_id": "task_be6c4ddef130",
      "title": "Qwen3-VL-2B 픽셀 예산 대조",
      "worker_opinion": "큰 입력에서도 넘기 누락·완료 근거 부족이 남음."
    },
    {
      "agent_model_effective": "gpt-6.1-sol",
      "agent_model_requested": "gpt-6.1-sol",
      "assigned_at": "2026-10-28T10:35:16.578963+00:00",
      "attempt_id": "mvp0001-resource-blocked-no-gpu-attempt",
      "decision_status": "adoption_on_hold",
      "dispatch_id": "ctx_63a22ac17659",
      "evaluated_model": "Qwen3-VL-2B-Instruct — 실행 예정, 이번 추론 미실시",
      "evidence": [
        {
          "artifact_id": "mvp12-reference-007",
          "kind": "video",
          "label": "007 기존 원본·표본 참고 — 새 MVP 결과 아님"
        },
        {
          "artifact_id": "mvp12-reference-030",
          "kind": "video",
          "label": "030 기존 원본·표본 참고 — 새 MVP 결과 아님"
        }
      ],
      "execution_status": "inconclusive",
      "experiment_id": "EXP-0012",
      "limitations": [
        "GPU job/attempt0; package attempt_id는 미실행 전달 식별자이며 GPU attempt가 아님",
        "원본 CPU EOF 확인은 모델 기능 통합 성공이 아님",
        "영상은 기존 입력 참고이며 새 MVP 비교 결과가 아님",
        "예약013은 과거 감사 노출과 전체화면 fallback; 행동 평가 미실시"
      ],
      "metric_definitions": "records/EXP-0012/metrics.json",
      "metrics_path": "records/EXP-0012/metrics.json",
      "metrics_sha256": "2162b11232d45311a040e49f8940c3106cb6ec3cdd54d4988a2cc124aa45db8c",
      "next_step": "GPU 여유6,144MiB 이상 확보 후 동결 조건·남은 한도에서 새 실행 ID로 실제 B/C 전체 원본 비교.",
      "reasoning_effective": "high",
      "registration_sha256": "c6943bf4fad5fbe12a4788703cfad87eed6db130f4e92c93b80afc11e8cac37e",
      "report_path": "docs/experiments/EXP-0012-continuous-mvp.md",
      "report_sha256": "aba34d897902fda29f42afa0264f10d58de55089310b45695009228bd97d83b5",
      "review_binding_path": "docs/reviews/EXP-0012.binding.json",
      "review_path": "docs/reviews/EXP-0012-coordinator-review.md",
      "review_sha256": "e419cd294980d67ca96d7e5b2064593fbaaa7f8eb7aa97a8426d8a0bef0bd952",
      "review_status": "blocked",
      "reviewed_metrics_sha256": "2162b11232d45311a040e49f8940c3106cb6ec3cdd54d4988a2cc124aa45db8c",
      "reviewed_report_sha256": "aba34d897902fda29f42afa0264f10d58de55089310b45695009228bd97d83b5",
      "role": "experiment_worker",
      "run_id": "run_3d23462a014a",
      "schema_version": 1,
      "slot": "slot2",
      "summary": "CPU 코드·원본3개 시간창 준비 확인. GPU 자원 부족으로 실제 모델 실행과 행동 평가는 미실시.",
      "synthetic": false,
      "task_id": "task_c466b62bf289",
      "title": "원본 CCTV 전체 처리 MVP 비교",
      "worker_opinion": "CPU 구현·준비 완료, 실제 원본 모델 목표는 자원 차단으로 미완료."
    },
    {
      "agent_model_effective": "gpt-6.1-sol",
      "agent_model_requested": "gpt-6.1-sol",
      "assigned_at": "2026-10-28T10:35:16.578776+00:00",
      "attempt_id": "mvp0001-resource-blocked-no-gpu-attempt",
      "decision_status": "adoption_on_hold",
      "dispatch_id": "ctx_7aacfaf52678",
      "evaluated_model": "Qwen3-VL-2B-Instruct — processor CPU 준비만, 이번 추론 미실시",
      "evidence": [
        {
          "artifact_id": "mvp11-reference-007",
          "kind": "video",
          "label": "007 기존 원본·표본 참고 — 새 C 결과 아님"
        },
        {
          "artifact_id": "mvp11-prepared-007",
          "kind": "image",
          "label": "007 고정 영역 CPU 입력 시트 — 모델 미실행"
        },
        {
          "artifact_id": "mvp11-reference-030",
          "kind": "video",
          "label": "030 기존 원본·표본 참고 — 새 C 결과 아님"
        },
        {
          "artifact_id": "mvp11-prepared-030",
          "kind": "image",
          "label": "030 고정 영역 CPU 입력 시트 — 모델 미실행"
        }
      ],
      "execution_status": "inconclusive",
      "experiment_id": "EXP-0011",
      "limitations": [
        "GPU job/attempt0; package attempt_id는 미실행 전달 식별자이며 GPU attempt가 아님",
        "CPU 전처리 성공은 행동 성능 또는 실제 모델 기능 통합 성공이 아님",
        "영상은 기존 원본 참고, 이미지는 CPU 입력이며 새 C 결과가 아님",
        "006 후기 보행은 ROI 밖; 정밀 정답/독립 카메라 평가 부족"
      ],
      "metric_definitions": "records/EXP-0011/metrics.json",
      "metrics_path": "records/EXP-0011/metrics.json",
      "metrics_sha256": "de09a649bf210fbc0808b38f23c45e7d652a996fd69eee4fd506f1fcf193e5a9",
      "next_step": "GPU 여유6,144MiB 이상 확보 후 동일 고정 조건·남은 한도에서 새 실행 ID로 C baseline 비교.",
      "reasoning_effective": "high",
      "registration_sha256": "41c5404557edf00c34aa594177f1a734543a145ab005493f5bedea07f2cbd4f5",
      "report_path": "docs/experiments/EXP-0011-fixed-camera-input.md",
      "report_sha256": "1cc727e272c4b2e7c16bd510f9dce23aaf76c9d5df22f89f91300b64035d01c6",
      "review_binding_path": "docs/reviews/EXP-0011.binding.json",
      "review_path": "docs/reviews/EXP-0011-coordinator-review.md",
      "review_sha256": "48578496419783bce56af1f4e6694ddfdf3e07271dbe29099ffa5275c9507998",
      "review_status": "blocked",
      "reviewed_metrics_sha256": "de09a649bf210fbc0808b38f23c45e7d652a996fd69eee4fd506f1fcf193e5a9",
      "reviewed_report_sha256": "1cc727e272c4b2e7c16bd510f9dce23aaf76c9d5df22f89f91300b64035d01c6",
      "role": "experiment_worker",
      "run_id": "run_3d23462a014a",
      "schema_version": 1,
      "slot": "slot1",
      "summary": "기존6클립 고정 영역 CPU 입력 준비와 C1 동등성 확인. 실제 행동 비교는 GPU 자원 부족으로 미실시.",
      "synthetic": false,
      "task_id": "task_d32fef262394",
      "title": "고정 카메라 영역 입력 비교",
      "worker_opinion": "입력/재사용 조건은 확인했지만 행동 개선 근거는 아직 없음."
    }
  ],
  "note": "기존 보고서 읽기 전용. 실험 모델과 작업자 모델은 서로 다름. TEST 큐는 별도.",
  "schema_version": 1
}
