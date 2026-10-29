# ADR-0022 — 기존 C6 고정 ROI에서 YOLO26m-Pose 비교

2026-10-29. 상태: CPU·독립 사전 PASS 후 신규5회 정상 완료, 실제 사람·관절 대응 미확정·채택 보류. [승인 계획](../experiments/BATCH-0005-c6-pose-roi-comparison-plan.md)의 BATCH-0005 / EXP-0023 한정이다.

EXP-0022의 030:90 전체화면은 정상 Results이나 0행으로, 기존 사용자 관찰의 사람·문 올라탐에 관절 근거를 제공하지 못했다. 모델 교체·임계값 조정 대신 기존 정지 배경 기반 C6 ROI 입력 한 축을 비교한다. 입력상 인물 크기가 커질 수 있다는 가설이며 실제 복원 성공은 미확정이다. 같은 640에서도 원본 범위·resize/letterbox가 달라져 이 효과들을 분리한 비교는 아니다.

기존 camera C6 [0.28,0.20,0.75,0.80]를 floor/ceil로 x537:1440,y216:864에 고정한다. 원본 RGB[216:864,537:1440] 903×648을 기존 batch04 BGR utility로 변환한다. 공식 8.4.192 YOLO.predict의 모든 kwargs·환경·체크포인트를 유지한다. 030:90 C6부터 84 full/C6,94 full/C6의 정확히 5개 새 예측을 한 모델 로드로 순차 실행한다. 90 full은 EXP-0022의 실제 native Results·hash를 재사용하며 새 예측/비용에 넣지 않는다. 정상 empty는 재시도나 84/94 생략 사유가 아니다.

공식 Results는 입력 crop의 좌표이므로 기존 result_rows로 local bounds/confidence/(0,0) unknown을 먼저 판단한다. 원본 표현에는 (+537,+216)을 한 번만 적용하고 local/raw를 별도 보존한다. unknown sentinel이 이동해도 retained가 되지 않는다. 전체화면에는 이동/재스케일이 없다. source SHA/native PTS/RGB/crop/config/cache provenance를 동결하고 CPU 계약 검사·source commit·독립 review·총괄 허가 후 canonical queue/상속 lease/RunTaskDispatch/free≥6144MiB에서만 실행한다. 기존 유틸·실패·환경·가중치·기본 설정을 수정하지 않는다.

선택을 뒤집을 근거는 세 시점 원본/전체/ROI overlay에서 실제 bbox·손목/골반/무릎/발목 대응과 누락·중복·가림·절단에 대한 사람 검수다. 출력 수 증가만으로 성공을 선언하지 않는다. C6 calibrated는 물리적 fence top/far-side 교정이 아니다. tracker·행동규칙·CV+VLM·전체267·추가조건은 범위 밖이다. 정확도/F1/FPR/완료/위법성은 미평가다.

AGPL-3.0-only와 기존 ADR-0020/0021의 공식 출처·라이선스 조건을 유지한다. 새 가중치/설치/학습/외부 API는 없으며 CCTV/native Results/raw 좌표·tensor·overlay·runtime은 로컬만 보관한다. 공개물은 코드·비식별 진단 수치·해석이고 웹/remote 검증은 총괄이 별도 수행한다.

실제 실행은 source62fe072bdd70f4e3eeb8c51a4984b96f221fea41에서 신규5회/모델생성1회/별도warmup1회,오류0/retry0였다. 84초 full2행/24관절 대비 C6 3행/38관절,90초 cached full0 대비 C6 1행/12관절,94초 양쪽0이다. 출력 증가를 사람/관절 복원 성공으로 확정하지 않고 세 시점의 원본/overlay 사용자 검수를 다음 한 선택으로 둔다. 실제 수치·비용 범위·보존 근거는 [EXP-0023](../experiments/EXP-0023-c6-pose-roi-comparison.md)를 따른다. 신규5개 한도는 종료했고 추가 GPU 실행은 없다.
