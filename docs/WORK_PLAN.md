# SceneGuard 단계별 작업 계획

- 상태: **Phase 2A — 최소 CV baseline 구현·첫 로컬 진단 완료, 검출 누락 분석** (2026-10-27). Phase 1E AI-Hub 10개 감사·사용자 검수·평가 계획은 Conditional Go, G1E 최종 승인은 미완료.
- 역할: 사용자 = 문제 선택·영상 의미 검수·최종 승인 / Codex = 조사·로컬 스크립트·실험 지원·문서 기록
- 규칙: 실제 확인된 항목만 완료 처리. 단계별 결정 게이트에서 다음으로 진행할지 판단.

## Phase 0 — 준비
- [x] 프로젝트 목표와 선행연구 요약 문서화
- [x] 모델을 먼저 확정하지 않고 연구·데이터를 우선 확인하기로 결정
- [ ] 사용자 및 Codex가 목표/작업 규칙 검토
- [ ] WSL2/RTX 3080 환경과 VRAM/드라이버 확인 후 기록
- [x] Git 제외 규칙·저장소 디렉터리 확인

## Phase 1 — 데이터 확보 및 샘플 감사 (현재 우선순위)

실행 결과: [SAMPLE_AUDIT.md](data/SAMPLE_AUDIT.md). 정상 4개·위험 4개 확보, 전체 디코딩 및 추출 프레임 감사 완료. 원본 배포 문서와 HF 라벨은 확인했으나 원본 개별 파일 대조는 미수행. 사용자 전체 재생 검수와 G1 승인은 대기 중.

**Codex**
- [ ] Safe and Unsafe Behaviours 원 출처, 배포 버전, 라이선스/재배포 조건, 라벨 및 영상 목록 확인. 출처 URL 기록
- [x] 전체 다운로드 대신 **정상 약 3~5개 + 위험 약 3~5개** 선택
- [x] 파일 재생/디코딩, FPS, 해상도, 길이, 프레임 수 측정
- [x] 영상 ID와 공식 라벨을 정확히 매핑 (파일명만으로 추정 금지)
- [x] 통로 이탈·패널 개방 등의 관찰 단서와 시간적 움직임 필요 여부 기록
- [x] 화면 가림, 객체 크기, 카메라 구도, 라벨 모호성, 데이터 누수 위험 기록
- [x] **docs/data/SAMPLE_AUDIT.md** 작성 및 Go / Conditional Go / No-Go 의견 제시
**사용자**
- [ ] 영상을 직접 살펴보고 관찰 결과·안전 의미 검수
- [ ] 최초 MVP 행동 후보 1개 선택하거나 범위/데이터 교체
- [ ] 검토 의견과 향후 결정을 Git 문서에 반영

**Gate G1:** 최소 1개 관찰 가능 행동 + 실제 재생 가능한 샘플 + 라벨 매핑 + 이용 조건 확인. 미충족 시 데이터/문제 변경.

## Phase 1B — 새 후보 데이터(iSafetyBench) 적합성 확인

결과: [ISAFETYBENCH_SAMPLE_AUDIT.md](data/ISAFETYBENCH_SAMPLE_AUDIT.md). 8개 영상·전체 주석 감사 완료, Conditional Go 제안. 원 영상 개별 권리·사람 검수·G1B 최종 승인은 미완료.

근거: [ADR-0002](decisions/ADR-0002-reconsider-safety-dataset.md), [ADR-0003](decisions/ADR-0003-incident-review-product-direction.md), [제품 업무 흐름](PRODUCT_WORKFLOW.md). 이전 8개 영상의 Conditional Go·검사 결과는 삭제하지 않는다.

- [x] 기존 패널 닫힘/열림 이미지 비교로 상태 감지 대상 확인(일부 이미지 검수)
- [x] **패널 상태 분류를 메인 MVP에서 제외** 결정
- [x] iSafetyBench 공식 배포 접근성과 배포 라이선스 확인·원 영상 권리 미확인 범위 기록
- [ ] 원본 영상 개별 권리·공개/상용 활용 가능 여부 확인
- [x] 영상별 클래스/행동 정답/설명 확인 및 파일명 기반 원 출처 후보·중복 위험 기록(실제 원본 대조 미완료)
- [x] 소량 영상(가능하면 6~10개)만 확보하여 실제 장면과 공식 주석 대조
- [x] 사고·행동 분석을 사람이 검수 가능한 문제로 정의할 수 있는지 확인
- [x] 짧은 영상에서 복수 행동, 사건 설명, 근거 후보, 검토 보조에 쓸 수 있는 필드/추가 라벨 요구 확인
- [x] `docs/data/ISAFETYBENCH_SAMPLE_AUDIT.md` 작성 및 Go / Conditional Go / No-Go 의견
- [ ] 사용자 영상 의미 검수, 메인 데이터/문제 범위 결정

**Gate G1B:** 접근·사용 조건·라벨·시각적 정보가 목표와 평가 단위를 뒷받침하는지 확인 후 첫 사건 분석 MVP 채택 여부 결정. 기술 도입은 G2에서 결정.

이 단계의 감사 지시 이력은 Git에서 확인할 수 있다. 현재 [다음 업무 지시](CODEX_NEXT_TASK.md)는 **AI-Hub 침입 CCTV 감사**로 갱신되었다. 기존 자료는 보존한다.

## Phase 1C — SteelBench 산업 CCTV 소량 검증 (접근 제한으로 보류)

자료: [R-003 후보 조사](research/0003-cctv-dataset-shortlist.md) · [SteelBench 접근 감사](data/STEELBENCH_SAMPLE_AUDIT.md). **SteelBench 메인 채택 전**.

실행 결과: [접근 검사 기록](data/STEELBENCH_SAMPLE_AUDIT.md). 공식 경로 HTTP 401, MP4/정답 JSON 확보 0개. 현재 경로 No-Go이며 내용 적합성은 미판정. 공식 접근 복구 후 재개.

- [x] 공개 접근 요청과 오류 재현 기록 작성
- [ ] 데이터 배포 범위, 실제 MP4 접근 및 라이선스·프라이버시 조건 확인
- [ ] 정답 JSON과 매핑되는 CCTV 영상 4~6개만 로컬 검사 (해상도·FPS·디코딩)
- [ ] PPE·행동·안전 태그의 관찰 가능성, CCTV 구도/가림 및 시간 정답 여부 기록
- [x] `docs/data/STEELBENCH_SAMPLE_AUDIT.md`에 접근 실패·현재 경로 No-Go·재개 조건 기록
- [ ] 실제 영상 감사 후 의미 검수 질문·데이터 적합성 의견 작성
- [ ] 사용자 검수 후 메인 데이터/첫 평가 단위 결정

**Gate G1C:** 공개 데이터 범위 내에서 실제 CCTV 영상·주석·이용 조건이 목표와 맞는지 확인한다. 그 전 모델 학습·추론·UI 구현 없음.

## Phase 1D — ACCIDENT 교통 CCTV 접근·샘플 검사 (현재)

근거: [R-003 후보 조사](research/0003-cctv-dataset-shortlist.md) · [Codex 다음 작업](CODEX_NEXT_TASK.md). **5개 소량 감사 완료, 교통 CCTV로 제품 영역 전환 미확정**.

결과: [ACCIDENT_SAMPLE_AUDIT](data/ACCIDENT_SAMPLE_AUDIT.md). 공개 CSV 2,027행·실제 MP4 목록 1:1 매핑, 5개 420프레임 디코딩·추출 프레임 감사. Conditional Go 제안, 사용자 검수와 권리/분할 보완 대기.

- [x] 공식 파일 목록·개별 공개 다운로드·배포 라이선스/연구 제한 확인 (원 출처별 권리는 미확인)
- [ ] 원 출처별 권리·재게시 조건 및 분할 누수 후보 직접 대조
- [x] 대회 hidden test와 dataset의 공개 정답 파일을 구분해 영상별 주석 스키마 확인
- [x] 이용 허용·개별 접근 가능할 때에만 실제 CCTV 영상 4~6개 검증 (FPS/디코딩/사고 시점·위치·유형)
- [x] `docs/data/ACCIDENT_SAMPLE_AUDIT.md`에 실측·미검증·평가누수·Go/Conditional Go/No-Go 문서화
- 해당 없음: ACCIDENT 접근 성공으로 CMA 대체 조사 미실행
- [ ] 사용자 검수 후 교통/산업 CCTV 최종 문제 정의 및 메인 데이터 채택 결정

**Gate G1D:** 실제 파일 접근·원본/정답 매핑·비상업 이용 조건을 확인하고 나서 G2 기술 비교에 진입.

## Phase 1E — AI-Hub 침입 CCTV 감사 (현재 우선 작업)

결과: [AIHUB_INTRUSION_SAMPLE_AUDIT](data/AIHUB_INTRUSION_SAMPLE_AUDIT.md). 로컬 9개 36,518프레임 디코딩, 실제 JSON 12구간 PTS 대조·추출 프레임 감사. Conditional Go 제안. event_length 불일치·검수된 정상 시간 0·카메라 독립성 미확정, G1E 미통과.

- [x] 기존 로컬 파일·공식 공개 목록·비로그인 권한 확인
- [x] 9개 전체 디코딩과 추출 프레임 감사 및 카메라 중복 후보 기록
- [x] 사용자 TL_침입 JSON 45개 확보 및 파일명 연결
- [ ] 사용자 이미지 4/7번 실제 파일명 연결

- 결정: [ADR-0004](decisions/ADR-0004-boundary-crossing-cctv-mvp.md)
- 데이터: [AI-Hub 71850](https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71850) 침입 범주 (공식 소개 약 55영상, 로컬 Training 폴더 45개 발견·9개 검사; 전체 배포 구성 대조 미완료)
- 감사 기준: [AIHUB_INTRUSION_AUDIT_PLAN](data/AIHUB_INTRUSION_AUDIT_PLAN.md) / [Codex 지시](CODEX_NEXT_TASK.md)

- [x] 사용자 제공 미리보기에서 유사한 학교 출입구 구도 편중 및 특수 사례 **줄 넘기(4번), 공원 울타리 넘기(7번)** 구분
- [x] **'무단침입 확정'이 아니라 '설정된 경계의 통과/넘기 행동 후보'**를 잠정 MVP로 정의
- [ ] AI-Hub 접근·다운로드 승인·재배포/개인정보 정책 확인
- [x] 9개 MP4와 공식 JSON 실제 연결·구간 PTS 매핑 (의미 경계 최종 검수 대기)
- [ ] 길이·정상/비이벤트 구간 검수, 카메라/장소별 중복/분할 단위 파악
- [x] `docs/data/AIHUB_INTRUSION_SAMPLE_AUDIT.md` 및 사람 검수 질문 기록
- [ ] Gate G1E Go / Conditional Go / No-Go. 최종 메인 데이터 승인

**Gate G1E:** 적법한 로컬 영상 접근, 시각적으로 검수 가능한 이벤트/정상구간, 평가 분할과 최소 baseline 설계가 가능한 수준인지 판단.

### 사용자 검수 후속 (2026-10-27)

- [x] [사용자 검수 기록](data/AIHUB_INTRUSION_USER_REVIEW.md)을 공식 라벨과 분리
- [x] 006 추가로 총 10개 디코딩, 119~132초 비이벤트 후보와 공식 JSON 대조; 프레임 수 불일치 기록
- [x] 001/007/030 등장·시작 구분 및 031 접촉·미완료 종료 반영
- [x] [평가 구성안](data/AIHUB_INTRUSION_EVALUATION_PLAN.md): 006/007 및 013/039/045 그룹 누수 방지
- [x] [최소 CV baseline 설계](design/CV_BASELINE.md), [ADR-0005](decisions/ADR-0005-minimal-boundary-baseline-design.md) 제안 작성
- [ ] 정밀 시간·완료·음성 범위 사용자 확정, 006 메타데이터 차이 해소
- [ ] camera/site 그룹·평가 manifest·매칭 허용 오차 동결
- [ ] 모델/라이선스/환경 선정 및 구현 승인 (현재 학습·추론·구현 없음)

## Phase 2A — 최소 CV baseline 구현·진단 (현재 승인된 작업)

- 승인: [ADR-0006](decisions/ADR-0006-limited-cv-baseline-prototype.md) · [Codex 지시](CODEX_NEXT_TASK.md) · [설계](design/CV_BASELINE.md)
- **범위:** 개발 표본에서 소규모 구현·실측만. 모델 학습·VLM·UI·대량 다운로드 및 검수 완료 전 최종 성능 주장은 제외.
- [x] 사용자 소규모 CV 실험 착수 승인 (2026-10-27)
- [x] 로컬 RTX 3080/CUDA/기존 도구·모델 후보 라이선스/출처 확인
- [x] 사전학습 사람 검출기 1개 + 인접 IoU 연결 + 카메라별 경계 양측 관측 규칙 구현
- [x] 경계/ROI 설정 파일, PTS 정확성, synthetic regression 테스트 (평행 보행·접촉·통과·ID 단절)
- [x] E01_006/007/030/031 중 2~4개에서 짧은 smoke test 후 가능한 범위 로컬 진단
- [x] 원시 후보 시각·오류·경보 원인·처리 시간/FPS/VRAM 측정 및 `docs/experiments/` 기록
- [x] G1E 미완료·006 프레임 불일치·카메라 중복·비이벤트 정답 미확정의 한계 명시

실행 결과: [EXP-0001](experiments/EXP-0001-phase2a-cv-baseline.md). 4개 smoke + 007 전체 클립. 검출 누락이 먼저 확인되어 고급 tracker 도입 보류. 최종 F1/FP-hour 미산출.

**Gate P2A:** 재현 가능한 CLI 및 로컬 진단 결과가 있고, 후보 이벤트와 정답/행동 완료 판정을 혼동하지 않는다. 다음 구조·추적기/VLM 필요성을 실제 실패 근거로 판단.

## Phase 2B — 추가 검출기 소규모 비교 (완료)

- [x] 공식 후보 비교 후 FCOS COCO_V1 하나 추가, 라이선스·버전·입력 크기 기록
- [x] 기존 네 smoke 2,060프레임, 추적/경계/config 고정·PTS/해시 검증
- [x] 35개 paired frame에서 실제 사람 복원·누락·중복 및 비사람 오검출 의심 검토
- [x] 시간/GPU 메모리/연결 실패와 모델·해상도 동시 변경 한계 기록: [EXP-0002](experiments/EXP-0002-fcos-detector-comparison.md)
- [ ] 사용자 의미 검수·카메라/평가 정답/G1E 확정; 메인 모델 채택은 보류
- 학습·VLM·고급 tracker·UI 미추가. 원본/기존 출력 보존.

## Phase 2 — 요구·평가 정의와 모델 선택
- [ ] 목표: 영상 분류 / 이벤트 구간 / 객체별 추적 중 평가 단위 확정
- [ ] 카메라·세션 편향과 유사 영상 누수 방지 분할 설계
- [ ] 문헌 근거에 따라 후보 2~3개만 비교(정확도, 지연, 모델 크기, 라벨 비용, 구현 난이도)
- [ ] 필요한 기술만 선택하고 선택/보류 이유를 새 ADR에 기록
- [ ] 모델/데이터 라이선스·환경 확인
**Gate G2:** 선택된 문제, 최소 구조, 측정 방법과 재검토 조건 설명 가능.

## Phase 3 — MVP 구현·성능 검증
- [ ] 데이터 로더와 최소 추론 파이프라인 작성
- [ ] 재현 명령·결과 포맷·테스트 추가
- [ ] 공식/검수 라벨로 성능 측정, 오탐·미탐 기록
- [ ] VLM을 쓰면 감지 품질과 상황 설명 품질 별도 평가
- [ ] 실험은 docs/experiments/, 문제 해결은 docs/troubleshooting/에 기록
**Gate G3:** 결과 재현 가능, 한계와 성능을 실측 근거로 설명 가능.

## Phase 4 — 필요 시 최적화·운영
- [ ] 프로파일링으로 실제 병목 확인
- [ ] ONNX/TensorRT, 비동기 처리, 프레임 샘플링 등 후보 비교
- [ ] 같은 데이터·환경에서 품질 변화와 지연/자원 변화 측정
- [ ] 필요 시 FastAPI/Docker/영상 스트림 도입과 장시간 장애 복구 검증

## Phase 5 — 포트폴리오
- [ ] 배경·연구·대안·선택·실험·실패·개선·한계 스토리 구성
- [ ] ADR, 코드 커밋, 실험 표, 공개 가능한 화면/영상 연결
- [ ] 논문 수치 vs 자체 성능, 미완성 vs 완성 기능 구분

## 다음 회의에 필요한 것
현재 Codex가 Phase 2A **작은 사전학습 사람 탐지·경계 통과 후보 baseline**을 구현·진단한다. 병행 과제인 006 검수 정상 시간, 001/007/030 정밀 시작 시각, 031 관측 종료, 중복 카메라 및 평가 manifest 동결은 미완료로 유지. 결과에서 실제 실패 근거를 얻은 후 다음 기술/평가로 이동.
