# EXP-0028 전달·종료 확인

2026-10-30 KST. **실제 실행·연속 영상·독립 검토·기존 웹 재생·GitHub 게시 완료 / 일반 적용과 실제 정체 연결 성공은 보류**다. 최신 결과는 [종합 결과](EXP-0028-results.md), [ReID 상세](EXP-0028-reid-comparison.md), [독립 검토](../reviews/EXP-0028-independent-review.md)를 따른다. 원격 초기 구현 문서의 미실행 상태와 ReID 상세 마지막 문단의 영상 제작 중 표현은 그 작성 시점 이력이며, 아래가 최종 전달 상태다.

- main `2e6270f`를 변경 없는 로컬에 fast-forward했다. 이후 작업은 기존 파일·원시 자료를 보존하는 새 경로에서 수행했다.
- 기존 Orca Run `run_3d23462a014a` 사용. 재생/렌더 Sol high `task_6e9c22520b45 / ctx_da00202ebfa3`, ReID Sol high `task_6dab4f8a6634 / ctx_ab3e3474978e`, 독립 Astra high `task_869138bf556d / ctx_e77401504991`의 실효 모델·effort와 worker_done을 확인했다. 세 작업자를 종료 후 release했고 미회수 worker는0이다.
- 030 480프레임(84–99.967초),007 600프레임(48–67.967초) strict/gap CPU 재생. strict는 EXP5C와 바이트 동일, 원본 PTS·관측 cache row·이벤트 재현 확인. 전체 원본 영상 처리가 아닌 기존 연속 캐시 구간 처리다.
- ID 단절이 남아 공식 BoT-SORT + 사전학습 YOLO26n-ReID ONNX 한 구성을 추가 실행했다. 1,080프레임/6,878유효 crop embeddings, CPU18.595+22.591=41.186초, 오류/retry0. GPU초기화false이며 canonical44jobs/attempts는 그대로다. 파인튜닝 모델·Roboflow 검수·재학습·새 검출기·추론API는 사용하지 않았다.
- CPU 테스트43개(경계/재생27,렌더5,ReID11)와 모든 출력 관측/원본 시각/독립 이벤트 재계산을 통과했다. 이는 물리적 정체 GT나 행동 정확도가 아니다.

## 실제 로컬 화면과 영상

주소: `http://127.0.0.1:8765/` → **담당3 → EXP-0028**. 실행 중 배정·실효Sol high·진행 중 카드를 확인했고, 완료 등록 후 보고서·검토·측정값58개(54실측/4미측정)와 그래프2개를 실제 DOM에서 확인했다. 기존 app.js·웹 기능은 변경하지 않았다.

| 로컬 폴더 (`outputs/exp0028/practical-v1/` 기준) | 비교 | 영상 |
|---|---|---|
| `review030/`, `review007/` | 원본 / strict / gap | `continuous_original_strict_gap.mp4`, `focused_original_strict_gap.mp4` |
| `review030_reid/`, `review007_reid/` | 원본 / gap / BoT-ReID | `continuous_original_gap_reid.mp4`, `focused_original_gap_reid.mp4` |

총8개/80,735,153bytes이며 각030은16초,007은20초다. full1920×600,표시확대1800×780이고 확대는 렌더 전용이다. 매 프레임 원본PTS·관측/예측·ID·점수·high/low·경계·후보 emission을 표시한다. 모든 파일을 전부 재디코딩해480/600프레임과 원본 상대 PTS를 검증했다.

웹 검증은8개 각각을 실제 브라우저에서 load/decode/play 후 시각 진행을 확인하고1.5초 seek를 수행했다.16.5초 자동 갱신 후 영상 노드가 유지됐다. HTTP 제공 bytes는 로컬 SHA와 같았다. 원본·미디어는 외부 에이전트/API로 전송하지 않았다. 이 기술 재생 검증을 새 사람별 정체 시각 검수로 해석하지 않는다. 사용자에게 핵심2영상의 ID 대응을 선택적으로 한 번 요청했고 답변 미수신은 실행·전달 중단 조건이 아니다.

## GitHub와 서비스 버전

결과 커밋 `e576b50d1240c1df36ff216e196d59686f860703`을 origin/main에 push했고 원격 HEAD·catalog/assignment·report/metrics/review/binding의 실제 Git bytes를 대조했다. 검증 시각2026-10-29T16:28:57Z(한국10월30일)다. 서비스 review_integrity=current, 서비스/브라우저/원격 파일SHA가 모두 일치한다.

- 종합 보고서: `96f98bbf0f7c91206cfdc542fab4ef51f7e2a2e01b08a3ca24158b59c0d70fb9`
- metrics: `60e5555573767f7a446794af2c7be712e111d6cea49c441f30e53657f91004b5`
- 독립 검토: `b435292cbe3e8825cdaf7e59513297058364b68f612b4b6311ba208e5cde5eff`
- binding: `e13804a5c6d950e80cd0bd9b141fa657bce0fe083c22f9ec3f11f4e061e92807`

코드·문서·비식별 집계16파일을 게시 전 검토했고 media/images/weights/cache/runtime와 인증·DB는 제외했다. 이 전달 문서는 결과 커밋 다음에 추가하며 위 결속을 바꾸지 않는다. 로컬 `runtime/EXP-0028/delivery/`의 progress-browser/browser-videos/github-results와 후속 최신HEAD receipt를 분리 보관한다. 기존 결과·기본 모델·환경과 upstream 보수적 추적/경계 소스는 유지했다.

## 종료 판단

030 후보는 strict/gap/ReID 모두2개지만 전후 ID 단절은 지속된다.007 접근 후보는2→0→1이며 길어진 숫자ID와 관측 재배정을 동일 인물 복원으로 확정하지 않는다. ReID 후보의 공백 표시는 확인 누적 중 누락이지 숨겨진 통과 복원 증명이 아니다. **기능 실행·비교 전달은 완료, 핵심 연결 품질은 미충족/일부 미확정**으로 구분한다. 기본 구성 자동 교체와 추가모델/설정탐색은 하지 않고 이번 한 구성 비교를 종료한다.
