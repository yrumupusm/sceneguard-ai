# SceneGuard — 다음 작업과 대화 인수인계

- 마지막 정리: 2026-10-27
- 현재 단계: **ACCIDENT Phase 1D 공개 주석·CCTV 5개 감사 완료, Conditional Go 제안. 사용자 검수·도메인/메인 데이터 결정 대기**
- 저장소: https://github.com/yrumupusm/sceneguard-ai
- 이전 감사 실행 기준 HEAD: `ba43440`. 감사 문서·검사 스크립트는 같은 작업 단위로 GitHub에 기록하며, 원본 영상·추출 이미지·메타데이터는 Git 제외 경로에만 보관.
- 사용자 운영 지시: 이후에도 작업 단위별 코드·실험 결과·기술 선택 근거·오류 해결 기록을 검토 후 커밋·푸시한다. 상세 절차는 `AGENTS.md` 참고.

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
