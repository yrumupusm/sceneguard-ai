# SceneGuard — 다음 작업과 대화 인수인계

- 마지막 정리: 2026-10-27
- 현재 단계: **Phase 2B 소규모 FCOS 비교 완료. 실제 사람 일부 복원, 누락·중복·배경 오검출 의심·연결 실패 잔존. 메인 모델/G1E·정밀 정답 미확정.**
- 저장소: https://github.com/yrumupusm/sceneguard-ai
- 이전 감사 실행 기준 HEAD: `ba43440`. 감사 문서·검사 스크립트는 같은 작업 단위로 GitHub에 기록하며, 원본 영상·추출 이미지·메타데이터는 Git 제외 경로에만 보관.
- 사용자 운영 지시: 이후에도 작업 단위별 코드·실험 결과·기술 선택 근거·오류 해결 기록을 검토 후 커밋·푸시한다. 상세 절차는 `AGENTS.md` 참고.

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
- **지금 GitHub에 업데이트한 것은 작업 지시서·결정 기록·계획이지 로컬 모델 실행 성과가 아님.** Codex 로컬 구현/실험 후 실제 측정 결과를 반영해야 한다.
- 기존 사용자 검수·평가 구성·iSafetyBench/ACCIDENT 등 모든 감사 자료를 보존하고, 다음 실험 결과로 모델/문제 방향을 재검토한다.

## 최근 확인 결과 — 사용자 검수와 baseline 설계 (2026-10-27)

- [별도 사용자 검수](data/AIHUB_INTRUSION_USER_REVIEW.md): 001/007/030 첫 등장≠넘기 시작. 031 약 33초 접촉≠공식 43.600초 시작; 종료까지 모든 사람 완료되지 않음. 미완료 주체 완료 시각은 null로 유지.
- 006 추가로 누적 10개/40,524프레임 디코딩. 약 119~132초 경계 옆 보행 비이벤트 후보를 대조. JSON 4,011 vs 실제 4,006프레임, 표시 FPS 29.97과 PTS 간격 차이 확인. 공식 사건 매핑은 잠정값으로만 기록.
- 후보 `[119,132)`에 실제 390프레임이 있으나 평가 구간 최종 승인 대기. 검수 완료 음성 시간은 아직 0초. 006/007은 새 카메라 중복 후보로 함께 분할.
- [평가 구성안](data/AIHUB_INTRUSION_EVALUATION_PLAN.md): 공식/사용자/평가 레코드 분리, 그룹 누수 방지, 현재 10개는 개발 표본. 최종 blind test 아님.
- [baseline 설계](design/CV_BASELINE.md) / [ADR-0005](decisions/ADR-0005-minimal-boundary-baseline-design.md): 검출+최소 연결+경계 양측 변화 제안. 구현·학습·추론·모델 선택 미실행.
- 실행: `scripts/review_aihub_intrusion_windows.py`, 근거 112프레임 개수/PTS 검사 성공. 공식 JSON 45개 전후 해시와 표본 원본 10개 해시 동일. 원문·이미지 로컬 전용.
- **남은 문제/다음 결정:** 사람별 시작/완료·006 음성 범위 승인, 006 프레임 수 차이 해소, camera/site 그룹 확정, 평가 규칙 동결 후 모델/환경 검토 및 구현 승인. 다음 작업의 구체적 순서는 [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md).

이하 9개 감사 결과는 직전 실행 이력이다.

## 최근 확인 결과 — Phase 1E 실제 JSON 대조 (2026-10-27)

- [감사 결과](data/AIHUB_INTRUSION_SAMPLE_AUDIT.md): 사용자 제공 TL/TS를 재사용. JSON 45개/영상 45개 파일명 연결, 라벨 53구간 구조 검사. 추가 다운로드 없음.
- 표본 9개(기존 8개 + 031), 36,518프레임 전체 디코딩. 실제 JSON 12구간을 원본 PTS에 연결하고 근거 83프레임 추가 검토. 사람의 연속 재생 검수는 미완료.
- 004의 공식 구간은 60.100~62.267초 줄 통과. 이전 28~45초 관찰을 라벨 근거로 사용하지 않음. 공원 울타리 유형 후보 031 추가, 사용자 이미지 4/7번 대응은 최종 확인 필요.
- 021/031/045의 event_length 불일치, 031의 검은 마지막 프레임까지 이어지는 이벤트, 036/039/045의 비시간순 배열 기록. 0/1-based 기준 미확정.
- 013/039/045 같은 구도 후보. 카메라 필드 45개 모두 파일명과 같아 물리 카메라 ID로 신뢰 불가. 검수 완료 비이벤트 0개, Validation 중복 미검사.
- **라벨 확보 문제 해결: 다운로드/로그인 추가 조치 불필요.** 다음은 사용자 연속 재생 의미 검수·정상 구간 확정·카메라 그룹 결정.
- Conditional Go 유지. G1E 최종 승인·모델 구현 보류. 원본/JSON/이미지 Git 제외, 이전 감사 보존.
- 재현: `scripts/audit_aihub_intrusion.py --ids 031 --append`, `scripts/audit_aihub_intrusion_labels.py`. 자세한 환경·명령은 감사 문서.

## 가장 최근 결정 및 현재 지시 — AI-Hub 침입 CCTV (2026-10-27)

- **사용자 선택:** 1차 MVP를 카메라별 출입 경계 통과/넘기 행동 감지와 관제 검토 지원으로 **잠정 선택**. 법적 무단침입·출입 권한은 판정하지 않음. [ADR-0004](decisions/ADR-0004-boundary-crossing-cctv-mvp.md).
- 이유: ACCIDENT의 짧은 사고 클립보다 사용자가 검토한 AI-Hub 침입 영상(일부 약 1~2분)에 정상 전후 구간이 있을 가능성. 단, 실제 정상 정답·길이는 미검증.
- **사용자 제공 전체 미리보기:** 학교 출입구/철제 울타리 구도가 반복. **이미지 4번은 줄 넘기**, **7번은 공원처럼 보이는 장소의 울타리 넘기**. 각 특수 유형은 매우 적어 일반화 성능 주장 불가. 4/7은 공식 파일 ID가 아니라 사용자 제공 이미지 순서.
- 새 자료: [AI-Hub 71850](https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71850) 침입 범주. 로컬 MP4 9개·공식 JSON 대조 결과는 위 최신 기록을 따른다.
- **지금 할 일:** [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md), [AI-Hub 데이터 감사 계획](data/AIHUB_INTRUSION_AUDIT_PLAN.md)을 읽고 이용 조건·로컬 접근 → 6~10개 샘플·시점·카메라 독립성·비이벤트 구간 감사. 산출물 `docs/data/AIHUB_INTRUSION_SAMPLE_AUDIT.md`.
- 판단: Gate G1E 후 메인 데이터 확정 및 **공통 CV 모델+카메라별 ROI/가상선 baseline** 설계 여부 결정. VLM은 CV 실패 사례에 효용이 있는지 이후 평가. 모델 학습·서비스 구현 현재 금지.
- **이 아래 이전 '다음 작업' 표현은 당시 작업 지시의 이력이며 현재 지시가 아님**. Safe and Unsafe Behaviours, iSafetyBench, SteelBench, ACCIDENT 감사 결과·로컬 자료는 모두 보존.

## 최근 확인 결과 — Phase 1D ACCIDENT (2026-10-27)

- [ACCIDENT_SAMPLE_AUDIT](data/ACCIDENT_SAMPLE_AUDIT.md): Kaggle 공식 dataset v9 공개 API 접근·파일별 다운로드 성공. 토큰/인증 파일 접근 없음, 전체 ZIP 미사용.
- 파일 목록 6,452개(33페이지), 실제 MP4 2,027개와 공개 CSV 2,027행 1:1 연결. 대회 hidden test와 별개인 dataset 공개 주석임.
- CCTV 5개만 확보: 2,744,574 bytes, 원본 PTS 유지 전체 420프레임 디코딩 성공. 추출 159프레임과 사고 영역 확대 접촉표 검토, 사람의 연속 재생 검수는 대기.
- 검사 오류 해결: 기본 디코더의 일정 FPS 보정/프레임 복제를 `-fps_mode passthrough`로 해제. 5개 모두 사고 프레임의 PTS와 정답 시각 오차 0.001초 미만. CSV no_frames는 실제 개수보다 1 작음.
- 관찰: 충돌 위치/시점 대체로 부합. A1 전복, A2 single 정의, A3/A4 접촉 부위는 사용자 검수 필요. 전체 2,027개 의미 검수 아님.
- 제약: 원 출처 URL/개별 권리 필드 없음, 정상 영상 유형 없음, 사건 시작/종료·설명 정답 없음. 파일명 출처 후보가 train/test 양쪽에 걸치는 그룹 IID 3개/geographic 1개 발견(실제 사건 누수는 미확정).
- **Conditional Go**: 비상업 로컬 교통 CCTV 사고 검토 연구 후보. 산업→교통 전환·메인 데이터·모델 채택은 미결정. SteelBench와 이전 감사 보존.
- 재현: `uv run --no-project --with imageio-ffmpeg==0.6.0 --with pillow==12.3.0 python scripts/audit_accident.py`. 원본/주석/이미지/응답은 Git 제외 `data/accident_audit/`에만 보관.
- 다음 결정: 5개 영상 사용자 재생 검수 → 권리/평가 분할 보완 → 산업/교통 도메인 및 G1D 판단. 모델 구현 없음.

## ACCIDENT 감사 착수 전 지시 이력 (2026-10-27)

- **사용자 승인:** SteelBench 공식 접근 불가가 확인되어 다음 후보 ACCIDENT의 접근 여부부터 검증한다. 산업안전에서 교통 사고 관제로 제품 목표를 최종 변경한 것은 아니다.
- 문서: [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md) · [R-003 데이터셋 후보 조사](research/0003-cctv-dataset-shortlist.md) · [ACCIDENT 공식 GitHub](https://github.com/accidentbench/ACCIDENT).
- 외부 확인: ACCIDENT 논문은 실제 CCTV 2,027개와 합성 영상 2,211개 및 사고 시점·위치·충돌 유형을 보고. 공식 GitHub `dataset/download_dataset.sh`는 Kaggle `picekl/accident` **전체 ZIP 다운로드**, 사전 Kaggle 인증을 요구한다. 착수 전에는 실제 개별 다운로드·정답 범위가 미확인이었으며, 현재 결과는 위 Phase 1D 기록을 따른다.
- 공식 Kaggle **대회**는 실제 영상에 대한 라벨 있는 **학습 데이터**를 제공하지 않는다고 고지. Kaggle 별도 **dataset** 파일 목록 및 공개 정답을 별도 검증해야 한다.
- **Codex 다음 산출물:** `docs/data/ACCIDENT_SAMPLE_AUDIT.md`. 접근 허용·권리·소량 개별 파일 확보 여부를 먼저 검사하고, 가능하면 4~6개 영상만 로컬 감사. 전체 다운로드·모델 구현 금지.
- ACCIDENT도 접근 제약이 크면 CMA 공식 배포 접근만 조사; 전환·모델 선정은 사용자 승인 이후.

## 최근 확인 결과 — Phase 1C 접근 실패 (2026-10-27)

- [STEELBENCH_SAMPLE_AUDIT](data/STEELBENCH_SAMPLE_AUDIT.md): 공식 API·카드·LICENSE·ethics·sample 목록 모두 HTTP 401. 논문의 `SteelBench-release` 주소도 401.
- MP4·정답 JSON 다운로드 0개, 디코딩·시각 감사 미실행. **현재 접근 경로 No-Go**, 데이터 내용 부적합 판정은 아님.
- 공개 복제 후보 `ThinkingHub/PP`의 API/카드는 접근되지만 공식 이전·배포 권한·원본 동일성 미확인. 대체 미디어 다운로드하지 않음.
- 재현: `python3 scripts/check_steelbench_access.py`; 원문 응답/해시/실행 정보는 Git 제외 `data/steelbench_audit/access/`에만 보관.
- 남은 문제: 접근 가능한 공식 경로 또는 작성자 확인 대체본 확보. 이후 조건·revision·주석 확인 후 4~6개 감사 재개. G1C와 모델 단계 보류.
- 이전 두 데이터셋의 결과와 로컬 파일은 보존.

## 다음 우선 작업 — SteelBench (2026-10-27)

- 노타 AI 영상 관제 직무와 촬영 환경 정합성을 고려해 **고정형 산업 CCTV** 샘플을 우선 검증하기로 함. iSafetyBench를 삭제하거나 공식 No-Go로 판단한 것은 아님.
- 조사 기록: [R-003 CCTV 데이터셋 후보](research/0003-cctv-dataset-shortlist.md). 우선 후보: [SteelBench](https://huggingface.co/datasets/steelbench/SteelBench).
- SteelBench의 공개 MP4는 전체 1,345개가 아니라 **50개 샘플**, 그중 정답 JSON이 연결되는 것은 **47개**라고 배포 문서에 기재. 현재 공식 경로는 HTTP 401로 접근 실패. 수량은 기존 조사 기록이며 이번 실측값이 아님.
- **실행 지시:** [CODEX_NEXT_TASK](CODEX_NEXT_TASK.md). 데이터 카드·권리·주석 확인 후 **공개 MP4 4~6개만** 로컬로 검수하고 [STEELBENCH_SAMPLE_AUDIT](data/STEELBENCH_SAMPLE_AUDIT.md)에 기록. 접근 실패와 재개 조건을 해당 문서에 기록했으며 영상 감사는 미완료.
- 과거 Safe and Unsafe Behaviours·iSafetyBench 자료는 보존, 영상/프레임은 Git 제외. **모델 선정·학습·서비스 구현 보류**.

## 최근 확인 결과 — Phase 1B (2026-10-27)

- [Issue #1](https://github.com/yrumupusm/sceneguard-ai/issues/1)과 최신 지시에 따라 [ISAFETYBENCH_SAMPLE_AUDIT.md](data/ISAFETYBENCH_SAMPLE_AUDIT.md) 작성. 실행 기준 HEAD `c15ba05`.
- 공식 GitHub 주석 1,100개와 HF 영상 목록 1:1 연결, 8개(위험 4·정상 4)만 확보. 총 6,437,874 bytes, 전체 1,469프레임 디코딩 성공, 배포 LFS SHA256과 일치.
- 기본 PTS 프레임 103개와 상세 창 62개(중복 시점 포함)를 추출해 시각 감사. 사람의 전체 연속 재생 검수는 미완료.
- 사건 시작·종료, 객체/추적, 공식 학습/평가 분할, 명시적 원 출처 URL 필드는 없음.
- normal 영상에도 사람 넘어짐이 존재하고, 물체 낙하를 `falling down`으로 태깅한 의미 불일치 후보가 있음. 화재 클립 후반에는 별개 차량 장면 혼입. 사람 검수 없이 정상/위험을 사고 이진 정답으로 전환하지 않음.
- MCQ multi 90문항은 전체 행동의 부분집합을 정답으로 묻는다. MCQ 점수와 전체 사건 설명 품질을 분리해야 함.
- 원 출처 후보 151개(1개 ID 형식 불일치). 반복 출처 그룹 소속 클립 1,077개. 공개 LFS 해시상 완전 중복 없음과 사건/시간 중복 없음은 다른 의미임.
- 권리: CC BY-NC-SA 4.0 배포 조건 확인, 원본 YouTube 개별 권리 허가는 미확인. 비상업 로컬 연구 감사만 진행, 영상/이미지는 공개하지 않음.
- 의견: **Conditional Go**. 행동·순서·근거·불확실성을 사람이 수정하는 연구 과제에 적합성이 있으나 원 주석 의미 검수·근거 구간·출처별 분할 보완 필요. 데이터·모델 최종 채택 아님.
- 재현: `uv run --no-project --with imageio-ffmpeg==0.6.0 --with pillow==12.3.0 python scripts/audit_isafetybench.py`.
- 로컬: `data/isafetybench_audit/`의 videos, previews, details, manifest.json, annotation_report.json. 전부 Git 제외. 이전 Safe and Unsafe Behaviours 자료는 보존.

## 남은 문제 — 현재 Phase 1B

- 사용자에게 감사 문서 H1~H4/N1~N4의 실제 재생·태그/주체·근거 시점 검수를 요청. N3/N4 의미 차이, H3 구조/도망, H4 장면 전환이 우선.
- 원 주석과 사람 보정본을 별도로 유지하고 검수자를 기록할 평가 기준 결정.
- 출처 후보를 실제 원본/같은 사건으로 대조하고 개발·평가 분할 독립성 확인. 상용/공개 미디어 사용 권리는 별도 해결.
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
