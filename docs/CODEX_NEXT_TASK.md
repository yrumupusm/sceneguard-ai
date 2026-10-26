# Codex 다음 작업 — SteelBench CCTV 데이터 소량 검증

- 기준: [CCTV 데이터셋 후보 조사](research/0003-cctv-dataset-shortlist.md)
- 대상: https://huggingface.co/datasets/steelbench/SteelBench
- **SteelBench는 아직 메인 데이터로 확정하지 않음.**

1. 데이터 카드·LICENSE·ethics·샘플 목록과 어노테이션 구조를 먼저 확인해 줘. **전체 1,345개 MP4가 공개된 것으로 가정하지 마.** 배포 버전, 실제 접근 가능한 파일 및 공개·재배포 제한도 기록해 줘.
2. 이용 조건을 확인한 후, **정답 JSON과 연결되는 공개 CCTV MP4 4~6개만** 로컬 `data/steelbench_audit/`에 받아 전체 재생·디코딩·라벨 매핑을 검증해 줘. 어렵다면 왜 불가능한지 기록해 줘.
3. 고정 카메라 여부, 사람·장비 크기, PPE/행동/안전 관련 태그의 실제 영상 부합성, 시간 흐름이 필요한 사건 여부, 가림·화질, 사건 시점 정답 유무를 확인해 줘.
4. **CCTV 사건 분석 → VLM 상황 설명 → 사람의 검토**라는 SceneGuard 목표에 활용 가능한지, 추가 라벨링·영상 확보가 필요한 부분과 누수 위험을 평가해 줘.
5. `docs/data/STEELBENCH_SAMPLE_AUDIT.md`에 **Go / Conditional Go / No-Go** 의견과 근거를 정리하고, `docs/HANDOFF.md`, `docs/WORK_PLAN.md`를 갱신해 코드·문서만 커밋·푸시해 줘.

**이번에는 모델 학습·추론·서버 구현, 전체 데이터 다운로드, 영상·프레임 GitHub 업로드를 하지 마.** 기존 두 데이터셋의 감사 기록과 로컬 파일은 보존해 줘. 미확인 사실은 미확인으로 표기하고, 최종 데이터 채택은 사용자 검수 후 결정하자.
