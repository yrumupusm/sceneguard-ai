# ADR-0016 — 고정 카메라 영역을 이용한 Qwen 입력 대조

- 날짜: 2026-10-28
- 상태: CPU 구현·입력 준비 검증 완료; 실제 행동 비교 자원 차단/미시작, C 채택 보류
- 관련: [고정 계획](../experiments/MVP-0001-plan.md), [ADR-0015](ADR-0015-first-vlm-comparison-batch.md), [EXP-0008](../experiments/EXP-0008-qwen-batch01.md), [EXP-0010](../experiments/EXP-0010-qwen-high-pixels.md)

EXP8의 작은 사람 넘기 누락과 근거 없는 완료가 EXP10의 전체 픽셀 예산 증가에서도 해소되지 않았다. 입력에서 사람이 차지하는 크기가 원인이라는 확정 근거는 없다. 다만 기존 정적 배경의 감시 영역을 영상 입력으로 쓰면 경계와 신체 관계를 더 크게 보존할 수 있다는 가설을, 같은 가중치와 질문으로 한 번 비교할 수 있다.

전체 화면 재실행·새 모델·사건별 사람 crop 중에서는 **기존 카메라별 고정 ROI 한 대조**를 선택한다. 개발 기준 B는 EXP8 결과를 재사용하고 C만 같은6클립에 실행한다. 전체 영상은 원본007/030/013의 동일 시간창에서 B/C를 각각 직렬 job으로 실행한다. 사전 지식으로 사건 시간이나 사람 좌표를 선택하지 않는다. C1/C4는 전체 화면 fallback이며 C4의 ROI 일반화 개선을 주장할 수 없다. C3의006 후기 보행은 기존 영역 밖이므로 해당 구간의 무경보를 영역 안 정상 구분 성공으로 세지 않는다.

Qwen 모델 카드는 Apache-2.0을 명시한다. 기존 pinned revision `89644892e4d85e24eaac8bacfd4f463576704203` 및 로컬 가중치·환경을 재사용하며 다운로드·재학습·외부 추론 API를 추가하지 않는다. 라이선스 표시는 모델 이용 조건이고 AI-Hub 미디어 재게시 허가는 아니다. 현 로컬 모델 snapshot에는 별도 LICENSE 파일이 없음을 확인했다. [공식 모델 카드](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)

공식 Qwen 예제는 video metadata와 총 영상 픽셀 예산 제어를 지원한다. 기존 `shortest_edge=16384,longest_edge=3584000`과 greedy/max384/rep1/BF16/SDPA/batch1을 유지한다. ROI는 정규화 원본 좌표를 floor/ceil로 바깥쪽 정수화한 후 공식 processor에 넣는다. [공식 저장소의 영상·pixel control 설명](https://github.com/QwenLM/Qwen3-VL)

설치된 Transformers4.57.1의 공식 구현은 추가 표본추출을 끌 수 있고, 홀수 프레임은 마지막 프레임을 반복해 시간 patch를 맞춘다. 최소2 실제 프레임이 필요하므로1프레임 EOF는 생성 없이 근거 부족이다. 반복은 미래 관측이 아니며 실제 PTS/개수와 반복 수를 구분해 보존한다. 실제 디코딩 순번은 정수 relative_indices/decoded_indices로 보존한다. processor 내부 metadata에는 별도 `(actual PTS-window_start)*fps` 시간 좌표를 넣어 실제 PTS 경과를 전달하며, 공식 구현의 프레임 쌍 평균과0.1초 문자열 반올림을 기록한다. 이 좌표를 디코딩 순번으로 표현하지 않는다. [버전 고정 공식 processor 소스](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/models/qwen3_vl/video_processing_qwen3_vl.py), [timestamp 소스](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/models/qwen3_vl/processing_qwen3_vl.py)

로컬 합성 CPU 검사는 원본10프레임 전체화면 경로의 모든 processor tensor와 실제 resize RGB가 기존 EXP8 adapter와 정확히 같음을 확인했다. 이는 전처리 회귀 근거이며 행동 성능 또는 실제 GPU 실행 성공이 아니다. 전체 영상의 익명 `w000001` 또는 개발의 기존 익명 `clip01`~`clip06` ID와 기존 중립 질문만 모델 text에 넣고 파일명·사건 설명·공식 라벨·이전 답변은 넣지 않는다. 분석기 생성 전에 기존 canonical GPU queue의 살아 있는 상속 lease를 요구한다.

행동 설명·신체 상승 구분·접촉/가림 유보가 나아지지 않거나, 영역 밖 동작을 잃어 실용성이 낮으면 C 채택을 보류한다. 개발 결과 이후 근거 있는 전역 개선 하나만 총괄이 사전 동결할 수 있고 자동 탐색은 하지 않는다. 테스트 통과·생성 성공·정답과 부합·채택을 각각 판단한다. 전체 영상의 검수되지 않은 시간은 음성 정답으로 간주하지 않는다.

개발 C1 clip05는 원본 EXP8 text ID·실제 processor RGB·expanded text·native timing·기존 가중치 해시·생성 설정 및 해당 코드/환경이 모두 같을 때만 성공 EXP8 답을 재사용한다. 전체 C4는 같은 Run의 성공 B attempt와 코드/원본/모델/설정/semantic input hash를 대조하고, B result의 실제 읽은 바이트 SHA를 로컬 reuse manifest로 고정한 뒤 재확인한다. 재사용의 새 생성 시간은 null, 신규 생성 토큰은0이며 과거 비용은 provenance에만 둔다.

실제6 cache CPU 준비에서 C3 608×544/1615, C6 480×704/1650, C1 fallback448×768/1680, C7 736×448/1610 visual tokens를 확인했다. 이는 입력량이며 행동 개선이 아니다. clip05의 과거 코드 바이트 차이는 EXP10의 정확한 budget constant 추출로 한정해 과거/현재 SHA 쌍과 AST diff를 고정하고 원래 adapter 전체 tensor·저장 RGB·expanded text 동일성을 확인했다. 첫 CPU 실패 및 한 번의 수정 준비는 보존한다. 총괄이 자원 차단을 수락해 실제 생성/전체 영상 비교는 시작하지 않았고 자동 재개하지 않는다.
