# EXP-0024 사용자 검수 전달 기록

2026-10-29. 완료된 EXP-0023의 새 사용자 관찰을 기록하는 문서 작업이다. 신규 추론·GPU 큐 실행·설정 변경은 없다. 시작 main7347b59는 clean이었고 원래 report/metrics/review/binding와BATCH-0005-summary 해시를 보존 기준으로 기록했다. 기존 검토본은 수정하지 않고 새 EXP-0024를 사용한다.

기존 Run에서 Sol high 담당 task_9c014eca1fc8/ctx_467e2b32ec60, Astra high 독립 검토 task_1f2434dfb816/ctx_b499f7a6ad59의 요청/실효 모델과 live provider를 확인했다. 기존 담당3 카드에 실제배정/진행중 표시를 확인했다. 새 총괄·GPU 큐·UI 기능은 없다.

사용자 답변은84초3명박스/관절정성양호,90초오른쪽1명박스/관절어긋남·다른2명누락,94초보이는2명모두누락이다. 사용자가 임시파일로 제시한 손표시 이미지는 사본·SHA를 로컬 outputs 아래 보존했다. 픽셀을 클라우드에 전송하거나 정밀GT로 가공하지 않았다. 공식 라벨/모델결과/기존검토본을 덮어쓰지 않는다.

이번 등록의 succeeded는 문서 검수 완료를 뜻하고 모델 성능 성공이 아니다. 지표의 신규추론0도 이번 기록 작업 범위이며, 기존EXP-0023의5회 실행을0으로 수정한 것이 아니다. 영상재생/seek는 정지이미지 기록에 해당하지 않는다.

## 독립 검토·등록·실제 화면

Astra high는 사용자 정성 관찰 해석·한 명 표시 제한 없음·이전 기록 보존에 PASS했다. 이미지 자체의 독립 검수나 정밀 성능 인증은 아니다. 기존완료명령으로 EXP-0024를 담당3에 succeeded/accepted_for_comparison/adoption_on_hold로 등록했고 이전23개 catalog 행과EXP-0023 검토본을 보존했다. GPU큐 jobs/attempts는 각각41개로 증가하지 않았다.

2026-10-29 06:04 UTC 실제 브라우저에서 보고서·독립검토·지표3개·그래프1개, 기존비교3장(각5760×1145)과수기참고1장(1643×430)의 decode/render 및polling유지를 확인했다. 각HTTP이미지와로컬해시도일치했다. JS버전은기존그대로이고영상재생/seek는해당없음이다. 픽셀을클라우드로전달하지않았다.

- `docs/experiments/EXP-0024-user-pose-review.md`: `11be179d4f4559f5aed4633b43cf00e4ddea577e9ce92888984f6eca9c58914f`
- `records/EXP-0024/metrics.json`: `2cf69f32a5d3a970a6d54a9d1f0bd25516adbfff5707a2b3812c32f0b6174066`
- `docs/reviews/EXP-0024-independent-review.md`: `f3c4c6b6d859d0cee78877622341581de597406e299c4efaf2828a60d7b6c23e`
- `docs/reviews/EXP-0024.binding.json`: `9d552579c21ea293e2cb9794b8b7947015c68574231a54277b2c8e0837177cab`

실제 화면 receipt는 로컬 runtime/EXP-0024/browser-images.json에 보존했다. GitHub 원격 확인은 별도 기록한다.
