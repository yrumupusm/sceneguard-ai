# Codex 다음 작업 — EXP-0005 실제 사람 연결 검수 확정

2026-10-28. AGENTS.md, [EXP-0005](experiments/EXP-0005-bytetrack-cache-comparison.md), [검수 초안](experiments/EXP-0005-visual-review.md), [ADR-0010](decisions/ADR-0010-bytetrack-cache-comparison.md)와 EXP-0004를 읽는다.

## 완료한 비교

- 기존 FCOS person 캐시 2,060프레임, A IoU ≥.5 / B ByteTrack high ≥.5 / C B+low ≥.25·<.5. B/C는 low 2차 연결 여부 외 동일. 신규 ≥.6, low로 신규 생성하지 않음. 모델 재추론·가중치 다운로드 없음.
- 공식 ByteTrack tracker subset을 고정 SHA/MIT로 vendor, 의존성은 requirements-tracking.txt. BoundaryRules/ObservedBoundary 분리로 외부 ID를 그대로 사용하고 실제 검출 bbox만 경계 입력. 예측/미확인 상태는 별도 기록.
- A 전 프레임 기존 결과 정확 재현, 테스트 24개 및 관측/후보 연속성/원본 PTS/이전 파일 보존 검증 통과.
- 030·007 일부 실제 사람 연결 및 C의 low 관측 복원은 국소 이점. 중복·배경 track 지속, 부분 신체·가림 정체 불확실, 후반 누락은 잔존. 기본 tracker 교체 보류.
- C에서만 030 90.300초 후보 2개, 007 56.633/56.767초 후보 2개. 실제 넘기/완료 정답으로 계수하지 않음. 특히 007은 문 밖 접근·서기/부분 bbox 변화 사례.

## 다음 순서

1. 재추론 없이 로컬 `outputs/cv_phase2e/review{030,006,007,031}/continuous_ABC.mp4`와 35개 compare 이미지를 사용자와 검수한다. 녹색 high/청록 low 실제 관측, 주황 unconfirmed, 자홍 점선 예측을 구분한다. 예측 유지 시간을 관측 복원으로 세지 않는다.
2. `review030/event_sequence_*.jpg`(89.600~90.500, 28프레임), `review007/event_sequence_*.jpg`(55.900~57.000, 34프레임)를 먼저 확인한다. 030 #3/#4의 개별 사람/부분 신체/중복, 007 #2의 신체 범위 변화와 옆 사람 연결 의심을 별도 검수 기록으로 확정한다. Codex 초안을 정답으로 승격하지 않는다.
3. 007 54·64초 중복 track, 56·66초 배경 track, 031 #1의 가림 뒤 동일 개인 여부/상점 의심 영역, 006 원거리 보행의 실제 정체 대응을 확인한다. 긴 ID·적은 ID만으로 개선 판단 금지. 정밀 tracking GT 전 IDF1/HOTA/침입 정확도 미산출.
4. 경계 후보가 실제 행동 의미와 일치하는지 확인한 뒤 기본 tracker 채택 여부를 판단한다. B↔A는 전체 tracker 정책 차이, C↔B는 low 2차 연결 추가와 그 후속 lifecycle 영향의 비교다. 특정 내부 알고리즘 하나의 효과로 단정하지 않는다.
5. 006 ROI 밖·4006/4011 차이·비이벤트 후보, 031 접촉≠공식 시작·미완료 종료, 동일 C3 카메라의 006/007 그룹 분할을 유지한다. 공식 라벨/기존 출력 수정 금지, 최종 평가 manifest·카메라 분할/G1E는 미확정.

이번 승인 범위의 ByteTrack 도입/캐시 비교는 완료했다. 검출기/재학습/해상도·NMS·경계 튜닝/새 tracker/VLM/UI로 자동 확대하지 않는다. 캐시 추적 시간을 모델 추론 FPS로 보고하지 않는다. 영상·이미지·캐시·원시 결과는 로컬 전용, 코드·라이선스·문서는 GitHub 관리.
