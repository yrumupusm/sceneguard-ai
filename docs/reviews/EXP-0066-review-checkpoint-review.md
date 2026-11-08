# EXP-0066 중간 기록 및 새 라벨 검수 자료 독립 검토

2026-11-08. 검토 상태: **accepted_for_comparison**. 이 판정은 아래 정확한 바이트의 **부분 진행 스냅샷과 새 검수 자료 전달**에 한정한다. 전체11후보 비교 완료, YOLO 추론 성공, 추가 미세조정 효과 또는 사람 검수 정답을 인증하지 않는다.

| 대상 | 정확한 SHA256 |
|---|---|
| 보고서 `docs/experiments/EXP-0066-review-checkpoint.md` | `1b27aae942fdb662f013eda9942573ff0fc7554e3d8d218482d1ecc6353ebb1a` |
| 측정값 `records/EXP-0066/review-checkpoint-metrics.json` | `d1732ce5689b3ecbdf09305067efae8405c6ad90106353ee50b740c2ba129720` |
| 스냅샷 `records/EXP-0066/review-checkpoint.json` | `a385e9bc722ffbf3955b49d509a51e1093ee0c3143838aec8d551404b03be7b2` |

스냅샷 시각은 `2026-11-08T06:06:40.982981+00:00`다. 이후 실행이나 답변으로 이 기록을 소급 성공 처리하지 않는다. 바이트가 바뀌면 해당 새 버전은 이 해시 판정에 포함되지 않는다.

## 진행 수치와 실패 보존

기존 독립 실제 결과 검토 및 이번 바이트 재검증에서 원본45개·184,300native프레임·6,219고정창의8모델 완료, 실제3개 head, 완료11/21단계, 학교 점수2스트림이 일치했다. 세 head result/weight/selection과11개 단계 result/receipt 해시를 대조했다. 보조 head는 고정 backbone 위에 학습한 것으로 detector 추가 학습이나 박스 복구와 구분한다. 정규6,177창과 진단42창을 고유 인원/침입 성공/모든 native프레임 추론으로 표현하지 않는다.

YOLO v1은 실제 체크포인트의 초기 mode guard 오류로 output 생성 전에 실패했고, 수정 v2는 자식 생성 전 GPU 여유6GiB 검사에서 차단됐다. 두 canonical 실패 시도 `028841bc84c24f37a1bd2026d025c0fc`, `30c2ba8b219e4ad2948105d7557004ec`와 영수증을 재대조했다. 기존 큐 행과 STOP를 보존했으며 YOLO 성공 출력0·detector 추가 학습0·backbone 추가 학습0이라는 스냅샷이 맞다. 자원 실패를 수정 모델의 추론 실패나 성공으로 바꾸지 않는다.

측정값16개의 값·분모·단위·평가 범위·스냅샷 SHA 연결을 확인했다. 기존 EXP-0062 AFTER37/52는 새 성공이 아니며, 학교 사람 recall/넘기 precision·recall/전후 학습 효과는 모두null이다. 사람 검수 F1·전체 완전한 정답·독립 일반화 성능으로 확대하는 주장은 없다. 아직 생성되지 않은 전체7head 최종 exporter 결과를 대신했다고 표현하지 않는다.

## 여섯 새 라벨 검수 자료

원본 선택3,984행을 실제 주석 파일에서 독립 재구성했다. 어느 한 origin에서 다른 알려진 actor의 현재 박스가 없는1,346창과1번 origin의 다중 actor1,584창은 후보 선정 신호일 뿐 가시 사람 누락 정답이 아니다. 고정6개 split/action 층의 순서·중복 원본 제외와 이전8검수 원본·15FP 보기 원본 제외를 재현했다. 선택6원본은 서로 다르고 보호 학교45source 및 frozen test source/group과 겹치지 않는다. 검증 음성의 앉기 편중은 해소되지 않았다.

실제6개 MP4의150프레임·3FPS·50초·1920×600, 원본 native PTS/RGB SHA와 두 origin의 모든 주석 기록을 대조했다. 원본 왼쪽의 최대 프레임 평균 절대 픽셀 차이는2.488 RGB level, 주석을 독립 재구성한 오른쪽은2.664 미만으로 압축 미리보기 범위다. 실제 박스 테두리 영역의 최대 평균 차이도21.552 RGB level 미만이며 저장 프레임에 주석이 같이 그려져 있다. 원본·라벨·영상·poster 해시가 일치했다. 미디어를 클라우드로 보내거나 모델을 실행하지 않았다.

정확한 자료 binding:

- `review.json`: `c6a64a9a8cac5f3ca6e6f149b4152cdb82b0f0938d5476695cafed10b40dae0e`
- `selection-v2.json`: `57678e66931dd5ea4f9b0a2ba5c33f7f17f858db31a8da9278334f5c4bd2c5a2`
- `question-specs-draft.json`: `b32fc44262bb06e57b1a1f0c2b62ef33e744a77216a089a775a7dea416a9b462`
- Renderer: `4af778170c86c109ffaa901a8e6227016db10f6555ceeb90df67cb1de47c5105`

질문6개는 해당 source/영상/원본 구간에 맞고, 가시 사람의 박스 전체 누락과 약간의 좌표 어긋남을 구분한다. 판단 어려움 선택지를 두고 행동 종류·시작/끝·frame origin을 같은 응답으로 확정하지 않는다. 표시 origin1은 모든 원본의 시간 정답으로 승격하지 않았고0/1메타데이터를 보존했다. 여섯 답변을 전체797라벨의 완전성으로 확대하거나 모델 박스로 정답을 자동 보충하지 않는 조건이 명시돼 있다.

## 범위와 남은 일

이번 재개 시 WEB pending 조회는 성공했고 비어 있었다. 검토 시 질문은 미등록이며 사용자 답변·의미 검수 완료·training release는false다. 실제 웹 등록, 질문 생성, 브라우저 재생/되감기 및 답변 저장은 별도 전달 검증이 필요하다. 이 문서는 그 작업을 완료했다고 인증하지 않는다.

재현 근거는 `runtime/model-comparison/exp0066/independent-joint-review/detector-label-qa-review-v1.json`(SHA `dc8ee0a5b1367ef43b3a6924451fa58f2da8d46fe6ce8668eb490f058ce6e32e`) 및 `partial-web-checkpoint-review-v1.json`이다. 원본 의미·실제 사람 수·모든 가시 사람의 주석 완전성은 사용자의 후속 검수 전까지 미확정이다. 별도 YOLO v3 준비/자원 대기와 옛 보조 head 보류 상태를 이 부분 게시가 해제하지 않는다.
