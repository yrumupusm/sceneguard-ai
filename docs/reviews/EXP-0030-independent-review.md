# EXP-0030 독립 검토

2026-10-30 KST. Task `task_08b3cadd275c` / Dispatch `ctx_0eef97f00042`. **최종 판정: 로컬 검토 흐름의 실제 실행·근거 기록은 `accepted_for_comparison`, 기본 적용은 `adoption_on_hold`다.** 미해결 실행·기록 blocker는 없지만, 서로 다른 ID의 동일인 복원·안정적인 행동 판단은 입증되지 않았다. 최종 보고서/metrics는 아래 정확한 SHA256 바이트에 한정해 검토한다.

[사용자 후속 지시](../CODEX_MVP_CONTINUATION.md), AGENTS, 프로젝트 목표·작업 계획과 기존 추적/후처리 결정에 따라 검토했다. 현행 사용자 영역만 사용하며 영역 수정 전후 수치·효과 비교는 하지 않았다. 검토자는 모델 추론·GPU 작업·미디어 시각 검사/업로드·소스 수정·Git 변경을 수행하지 않았다. 장면 의미는 총괄의 로컬 시각 검토 초안과 기존 사용자 관찰을 구분한다.

## 실행 전 검토와 수정 확인

기존 FCOS 캐시, ByteTrack 관측, EXP-0029 tracklet·대표·512차원 특징·accepted 연결을 읽기 전용으로 재사용한다. native PTS/time_base, cache index와 bbox/score, 각 실제 관측의 tracklet 분할, 대표 선택과 chain mapping을 대조한다. 예측·미확인 박스는 근거와 표시에서 제외하며 검토 연결은 chain에 추가하지 않는다. 기존 자동 연결의 0.65 기준과 5초 한도는 그대로다.

처음에는 근거 영상 코드·최종 freeze가 없어 실행을 보류했다. 완성 과정에서 후보 발생 시점 banner, 사례별 품질 근거와 원본 구간 참조, Q02/Q08 우려의 초안 출처, feed 준비 UTC와 미디어 가용 UTC 분리를 확인한 뒤 해제했다. Q02/Q08은 `continuation_instruction_previous_review_draft`이며 사용자 확정 정체가 아니다. 007의 56.7초 접근은 `previous_user_observation`으로 따로 남고 알고리즘 후보 수에 들어가지 않는다.

검토자가 36개 기능 테스트를 독립 통과시켰다. 합성 H.264 영상의 저장·flush·프레임 수·PTS, 실제 관측만 표시, 동시에 발생한 후보의 개별 보존, 검토 연결 비병합, 누락/변조 거부, 출력 덮어쓰기 거부, 오류 receipt와 자동 재시도 부재, 원래 emission 이전 banner 부재, 품질 원본 근거 참조를 포함한다. 실제 사람 대응이나 행동 정확도를 검증한 테스트는 아니다.

freeze의 소스 6개와 입력 170개, 별도 보호 대상 390개의 SHA를 실제 파일과 대조했다. 기존 canonical 큐의 jobs 45행·attempts 45행 모든 필드도 snapshot과 같았다. `independent-preflight-cleared.json`에 정확한 manifest를 결속하고 담당 Dispatch `ctx_8c8358922a83`의 한 번 CPU 실행을 허용했다.

| 고정 대상 | SHA256 |
|---|---|
| 실행 manifest | `a9439c8ee74a54e4b098ec055731cdf6e9fa58994f97b714623d90212bbac7d5` |
| `sceneguard/run_mvp_review.py` | `c6a205b4100bc6122be7d5aaa0df97db4d48b01dd28fbcb1bf9b0ebe75556461` |
| `sceneguard/mvp_review_quality.py` | `d613f4f84f69ada88a4edc387c73c5b16422f6129abe95ceebc31b281cd4e5b1` |
| `sceneguard/mvp_review_candidates.py` | `74b71e7f37777e2596f8485fe41e537b8b95b59b04224fd351eaca4665775f2d` |
| `sceneguard/run_tracklet_linking.py` | `d9db649a39678615e8dc178fd7e50adaa146c62bf67ccf7c5002f68a6c939080` |
| `sceneguard/tracklet_linking.py` | `32c163b5d3e1b03d3a2d20e53a287dbcfd3b768773e14af3730b3e052585b8a0` |
| `sceneguard/mvp_review_evidence.py` | `185cbc15ea44b4fae3a349a8341704f826439a4f91732161dddf2333704d5ad6` |

## 실제 출력과 보존 감사

담당자의 한 번 실행은 exit0, 재시도0으로 끝났다. 총 2,190프레임이며 detector/tracker/encoder forward와 polygon A/B는 모두0이다. 실행 뒤 소스6·입력170·보호390개 hash 및 기존 큐45/45행 전체가 그대로임을 검토자가 다시 확인했다. 기존/현행 polygon 효과 비교나 새 연결 재실행은 하지 않았다.

| 실제 출력 | 030 | 007 |
|---|---:|---:|
| 입력 프레임 | 480 | 1,710 |
| 기존 선 움직임 후보 | 2 | 1 |
| 현행 영역 양측 관측 후보 | 1 | 0 |
| 기존 자동 연결, 정체 미검증 | 0 | 1 |
| 별도 possible-match 검토 쌍 | 11 | 11 |
| 서로 다른 raw ID 자동 연결 | 0 | 0 |
| 별도 근거 항목 | 14 | 16 |
| 짧은 원본 근거 영상 | 15 | 19 |
| 영상별 처리·렌더 wall seconds | 84.871550 | 197.478426 |

원래 선 이벤트 객체와 associations가 저장 원본과 정확히 같고, 새 영역 후보 객체가 이번 출력과 일치한다. 2,190개 native PTS 매핑과 모든 근거 참조를 대조했다. 연속 영상8개·짧은 근거34개, 총42개 MP4의 실제 SHA·컨테이너 프레임 수·길이·해상도·H.264/yuv420p 정보가 receipt와 일치한다. 전체 디코딩 검사는 renderer가 수행한 기록이며, 검토자가 독립적으로 확인한 것은 hash·컨테이너 정보와 코드/합성 실행이다. 미디어를 직접 시각 판정했다고 주장하지 않는다.

명령 전체 wall은 282.928931초, 입력 검증 후 처리/렌더 wall은 282.479555초다. 영상별 wall 역시 초기 입력 로딩을 제외한다. 실제 추론 FPS나 실시간 경보 지연으로 바꾸지 않는다. 실행 receipt SHA는 `db25f45639ecdcefd0014887ca13cbc994e29f928aaf91b1a6c53790db54a654`, 외부 명령 receipt SHA는 `1621ae6ca1f2cc2644a51678efdea2086529e0d0c329d48aef83a4a70139e3da`다.

원본 추정 구간, 원래 선 emission, 새 영역 confirmation, 전체 입력을 본 뒤의 사후 가용 PTS, feed 준비 UTC와 미디어 가용 UTC를 구분한다. 영상 앞부분에 보이는 chain/검토 쌍은 사후 표시이며 당시 온라인 복원 결과가 아니다. 030 사후 가용 PTS는99.966667, 007은104.966667이다.

## 후보 의미와 남은 실패

030 선 후보는90.4/90.666667초, 현행 영역 후보는88.2–91.7초 관측을92초에 확인한 같은 t0003/raw3/p0003의 전이다. 새 ID 연결의 결과가 아니며 물리적 월장 완료를 뜻하지 않는다. 007의70.133333초 선 후보는 양측 영역 후보가 없다는 이유로 삭제되지 않았다. 007 자동 연결1개는 기존 raw9의1.2초 공백 연결로, 서로 다른 ID의 전후 동일인 복원 성공이 아니다.

Q01–Q05는 검토 제안이고 Q06/Q07은 각각5.533333/5.7초로 원래5초 한도 밖의 감사용 쌍이다. Q08은 기존 자동 연결이지만 정체 미검증이다. 약한 외형 점수의 상위2개 검토 제안은 신뢰도 보증이 아니며, 제안 수 증가를 복원 성능으로 세지 않는다. 총괄이 030 t0003→t0008의 옷차림 불일치를 관찰한 것은 오제안 가능성에 관한 로컬 초안이며 사람별 정답으로 승격하지 않는다.

Q02 t0008 head의 평균 유사도는0.492025/0.513165/0.394771이고 least index는2, 차이는0.097254로 고정0.15 조건 미달이다. 따라서 inconsistency flag는 false이며, 총괄이 의심한 첫 대표를 이 규칙이 분리하지 못했다. Q08의 t0007 tail/t0008 head도 false라서 복수 인물 crop 우려를 외형 일관성만으로 해결하지 못한다. 모든 대표와 특징은 보존했고 결과를 본 뒤 임계값을 바꾸지 않았다.

overlap63/237개는 프레임별 박스 쌍 진단, extent11/17개는 인접 관측 크기 변화 진단이다. 사람 수·혼합 정답 수가 아니다. 실제 동작도 flag를 만들 수 있고 안정된 부분 박스·복수 인물 박스·매끄러운 ID drift는 놓칠 수 있다. Q02/Q08 초안 우려와 원본 근거를 함께 제공한 것은 검토 지원 기능이며 자동 단일인 분리/정체 복원 성공이 아니다.

총괄의030 로컬 관찰상92초에도 문 위/주변 동작이 남아 있어 region 후보를 완료 시각으로 확정할 수 없다. 비교 영상의 region banner가 `raw None`을 표시하는 제한도 있다. 근거 index/관측 표시의 raw3/t0003/p0003 대응은 존재하며 검출 누락이 아니다. 이 표시 한계는 기록하고 고정 실행 뒤 재렌더·튜닝으로 이력을 바꾸지 않는다.

총괄의007 원본12시점과 비교56.7/70.133초 시각 초안은 접근·대기 뒤 다리/몸 올림, 후기 기둥 가림과 재등장을 구분한다.70.133초 후보는 부분 상체 박스에 근거하며 몸 올림과 시간상 대응한다는 초안이지, 완료나 전후 인물 대응 정답이 아니다. 검토자가 이 미디어를 독립 시각 확인한 것은 아니다.

## 최종 문서 결속

최종 [보고서](../experiments/EXP-0030-mvp-review-integration.md)의 실측값·후보 해석·Q 사례·한계를 저장 출력과 총괄의 로컬 시각 초안에 대조했다. 과거 영역 효과나 실제 완료/정체 성공을 새로 주장하지 않는 결론이 타당하다. 웹 등록·브라우저 재생/seek·GitHub 확인은 총괄의 별도 전달 기록 대상이며 이 검토 시점에는 별도로 진행 중이다. 이 검토가 새 추론·추가 실험·기본 모델 교체를 승인하거나 예약하지 않는다.

공개 [metrics](../../records/EXP-0030/metrics.json)26항목 중25개 실측값은 source SHA·명시적 pointer·값을 모두 독립 대조해 정확히 일치했다. 나머지 정체/물리 통과 정확도1항목은 독립 정답이 없는 미측정 null이다. 근거는 로컬 `independent-metrics-audit.json`에 보존했다. 보고서의 `output_utc`가 최종 게시 시각처럼 읽히는 문장을 지적했고, 실제 코드의 feed 준비 별칭임을 명시한 정정을 확인했다. 미디어 가용 UTC나 실행 완료 UTC와 같다고 취급하지 않는다.

실행·보존·출력·metrics 감사 receipt와 최종 문서 hash는 로컬 `runtime/EXP-0030/independent-final-binding.json`에 결속한다. 보고서나 metrics가 바뀌면 이 판정을 그대로 재사용하지 않는다.

| 최종 검토 대상 | SHA256 |
|---|---|
| `docs/experiments/EXP-0030-mvp-review-integration.md` | `b0d0f0fa0a1ff2a8691bda3b4ffbf914737ac701fae52ada77fd1dd31ca89188` |
| `records/EXP-0030/metrics.json` | `9e2d800207b1bf91f033795ee5c8ce11e07f1ddf3d04d4b17bb64991ae8140fe` |
