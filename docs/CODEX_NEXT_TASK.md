# Codex 다음 작업 — ACCIDENT 교통 CCTV 데이터 접근·소량 감사 (Phase 1D)

- 이전 SteelBench 공식 배포 경로는 HTTP 401로 **접근 실패**, 원본·감사 기록은 보존한다: [보고서](data/STEELBENCH_SAMPLE_AUDIT.md).
- 이번 검증 후보: [ACCIDENT 공식 프로젝트](https://accidentbench.github.io/) / [코드](https://github.com/accidentbench/ACCIDENT) / [Kaggle 데이터](https://www.kaggle.com/datasets/picekl/accident).
- **교통 CCTV 분야 전환 및 메인 데이터 선정은 아직 확정하지 않음.**

1. 먼저 **실제 접근성**부터 검사해 줘. 공식 링크·Kaggle dataset 메타데이터·파일 목록·각 파일 크기·이용 조건·정답 파일 제공 범위를 확인하고 HTTP 응답·실제 확인 근거를 남겨 줘. 공식 대회([ACCIDENT @ CVPR](https://www.kaggle.com/competitions/accident))에는 실제 영상의 *학습용 라벨 미제공* 안내가 있으므로, 공식 dataset의 다운로드 가능 파일·공개 정답과 **대회 hidden test**를 혼동하지 마.
2. **공식 `dataset/download_dataset.sh`는 전체 데이터셋 ZIP을 받으므로 실행하지 마.** Kaggle CLI 인증은 사용자가 로컬에서만 처리하게 하고 토큰은 읽거나 출력/커밋하지 마. 특정 MP4와 해당 정답 파일을 **개별로 선택해** 받는 방식이 공식적으로 지원되고 사용 조건을 충족한다면 **실제 CCTV MP4 4~6개만** `data/accident_audit/`에 저장해 줘. 전체 ZIP만 가능하거나 인증/권리 문제로 막히면 다운로드하지 말고 제약을 명확히 기록해 줘.
3. 내려받기에 성공한 경우 영상 전체 디코딩과 정답(사고 시점·화면 좌표·충돌 유형)의 실제 스키마·ID 연결을 검증해 줘. CCTV 구도, 사고가 차지하는 크기, 영상 편집/가림, 사건 전후 프레임, 출처·분할 누수 가능성도 기록해 줘. **검증용으로 공개되지 않은 정답은 있다고 가정하지 마.**
4. `docs/data/ACCIDENT_SAMPLE_AUDIT.md`에 접근 결과와 실제 테스트 범위, 영상별 확인 사항, 부족한 정답·라이선스, **Go / Conditional Go / No-Go** 의견을 기록해 줘. 직접 검증하지 못한 정보는 논문 보고와 구분해 줘.
5. 결과에 따라 `docs/HANDOFF.md`·`docs/WORK_PLAN.md`를 갱신하고, **코드·문서만** 검토해 커밋·푸시해 줘. ACCIDENT도 접근 불가라면 대체 후보 **CMA**의 공식 링크/다운로드 가능 여부만 가볍게 조사하고, 승인 없이 대량 다운로드하거나 산업안전→교통 분야를 확정하지 마.

**금지:** 모델 학습·추론·앱 구현, 전체 데이터셋 다운로드, 영상/프레임/정답 원본/개인정보·토큰 GitHub 업로드, 파일 존재를 추정한 성공 보고. 기존 세 데이터셋의 감사 기록과 로컬 파일 삭제 금지.
