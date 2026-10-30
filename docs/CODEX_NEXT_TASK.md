# 최신 승인 — EXP-0038 Qwen 8B NF4 비교

[CODEX_EXP0038.md](CODEX_EXP0038.md)가 현재 우선 작업이다. 사용자는 파인튜닝·데이터 수집·박스 작성 없이 기존 자료로 8B의 품질과 속도를 확인하기를 승인했다.

1. `mvp/exp0038.py`와 `tests_mvp/test_exp0038.py`를 확인하고 기존 8B용 checkpoint 준비와 canonical `appearance-8b` phase를 연결한다. 현재는 지원 코드/CPU 합성 테스트 24개까지이며 GPU 실행은 아직 없다.
2. Qwen3-VL-8B-Instruct pinned revision, 언어 NF4·시각 BF16, 기존 EXP-0034의 같은 6쌍/27 이미지·질문·파서로 모델 한 번 적재/6회 생성한다. 종료된 EXP-0034 task/dispatch나 2B 모델 기본값을 재사용하지 않는다.
3. 저장된 2B 결과와 사후 비교하고 적재 시간·첫 생성·나머지 생성·GPU 메모리·실제 가림/혼합 처리 결과를 구분한다. 4B와 동일 조건 비교라고 쓰지 않는다.
4. CPU/disk offload·입력 축소·새 모델·학습·재질문을 자동 fallback하지 않는다. OOM이면 부분 결과와 원인을 남긴다. 기존 침입 의심·카드·수동 검토 기능은 그대로 유지한다.
5. 실제 실행·원본/processor 검수·기존 화면 등록을 마치고 비식별 결과와 독립 검토를 게시한다. 코드만 추가한 것을 실제 8B 실행 완료라고 하지 않는다.

이전 MVP 기능 마무리는 [EXP-0037 결과](experiments/EXP-0037-results.md), [실행 안내](design/MVP_FINISH_CLI.md), [전달 기록](experiments/EXP-0037-delivery.md)에 보존돼 있다. 이전 중단/종료 문구는 당시 범위 종료이며 이번 명시적 승인에 우선하지 않는다.
