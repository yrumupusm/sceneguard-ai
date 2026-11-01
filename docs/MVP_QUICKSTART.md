# SceneGuard 실행 안내

실제 성공한 기본 실행과 관리 방법이다. 자동 폴링 중 연속 재생은 브라우저 절전 오류로 미검증이며 [검증 결과](MVP_VALIDATION.md)에 구분했다.

지원 범위는 로컬 고정 C3/C6 카메라의 native 30fps 녹화 영상이다. 원본과 카메라·scene·문 구역을 명시한다. 카메라를 파일명으로 추정하지 않는다. 기존 FCOS 검출 캐시를 입력과 대조해 재사용하거나 기존 canonical 큐에서 같은 모델을 실행한다. VLM·새 모델·학습은 기본 경로에 없다.

## 실행 모드

- 저장 결과 재생: 이미 끝난 결과를 화면에 표시한다. 새 분석이 아니다.
- 저장 검출 기반 분석: 원본과 맞는 검출만 재사용하고 현재 추적·영상 특징·규칙으로 결과를 계산한다.
- 기존 모델 새 검출 분석: 필요한 검출을 기존 GPU 큐에서 실행하고 같은 후속 분석으로 연결한다.

같은 요청의 완료 단계는 해시 검증 뒤 재사용한다. 입력·설정·버전 변경은 새 출력 폴더로 분리한다. 영상 전체를 처리한 뒤 검토하는 비실시간 분석이며 추론/CPU 처리 시간과 사건 원본 시각은 서로 다르다.

## 기존 서비스 관리

저장소 루트에서 이미 사용 중인 설정으로 관리한다. 중지 전 웹 영상 재생을 닫는다. 중지/시작은 기존 웹 서비스만 대상으로 하며 Orca나 GPU 큐를 초기화하지 않는다.

```bash
export SCENEGUARD_LAB_CONFIG=/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json
../sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.lab --config "$SCENEGUARD_LAB_CONFIG" status
../sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.lab --config "$SCENEGUARD_LAB_CONFIG" stop
../sceneguard-orca-lab/.venv-orca-lab/bin/python -m orchestration.lab --config "$SCENEGUARD_LAB_CONFIG" start
```

미지원 영상·잘못된 구역·해시 불일치는 실패 또는 차단으로 표시하며 완료로 바꾸지 않는다. 검토 메모는 자동 상태와 별도이며 기존 DB/영수증을 삭제하지 않는다.

## 단일 분석·등록 명령

저장소 `/home/jhc7484/dev/sceneguard-ai`에서 기존 CV 환경으로 실행한다. 등록만 기존 웹 환경을 사용하며 두 환경을 합치지 않는다. 아래 `my-007`은 새 출력/등록 예시이며, 실제 검증 출력은 검증 문서에서 구분한다.

```bash
.venv-cv-batch02/bin/python -m sceneguard.mvp_pipeline \
  --video data/TS_침입/E01_007.mp4 --camera C3 \
  --scene runtime/region-revisions/007-inside-20261101-v1/scene007.json \
  --portal runtime/portal-regions/exp0046/C3.json \
  --cache outputs/exp0029/cache007 --start 48 --end 105 \
  --output outputs/mvp-v1/my-007 \
  --register-config /home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json \
  --registration-id my-007 \
  --registration-python /home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python
```

030은 `--video data/TS_침입/E01_030.mp4 --camera C6`, `--scene runtime/EXP-0034/scene030.json`, `--portal runtime/portal-regions/exp0046/C6.json`, `--cache outputs/cv_phase2d/cache030`, `--start 84 --end 100`으로 바꾸고 별도 output/registration-id를 쓴다. 최종 카메라 설정 출처와 SHA는 로컬 `runtime/MVP-0002/camera-profiles.local.json`에 기록했다. 공개 문서에는 실제 좌표를 넣지 않는다.

`--whole`은 start/end 대신 사용한다. 전체 원본 새 추론을 이번에 검증했다고 뜻하지 않는다. 캐시 없는 실행은 기존 canonical GPU 큐의 활성 `--run-id --task-id --dispatch-id --owner`를 모두 요구하며 실행 권한과 GPU 자원 제한을 따른다. 임의 식별자나 과거 종료 dispatch로 새 검출을 우회하지 않는다.

출력의 `status.json`은 분석 단계, `decision/cards.json`은 현재 판정, `viewer-manifest.json`은 불변 표시 근거다. 등록 성공은 CLI 응답과 서비스 등록 목록에서 별도로 확인한다. 분석 성공만으로 브라우저 검증/전체 배포 완료를 뜻하지 않는다.

## 기본 보기와 이전 결과로 돌아가기

http://127.0.0.1:8765/ 첫 화면의 **영상 분석**에서007 개발 회귀를 기본 선택한다. 직접 고른 결과는 MVP 전용 로컬 저장키에 유지된다. 선택 목록에는 원본 범위를 함께 표시한다. 영상 시계는 원본 PTS로 환산되고, 상태는 해당 시각까지의 관측만 표시한다. 과거 LAST 박스를 현재 관측으로 쓰지 않으며 기본 근거 영상은 박스 없는 원본임을 표시한다.

**이전 실험 및 비교 이력**을 펼치면 기존 EXP 결과/담당 카드에 접근할 수 있다. 이는 과거 완료 결과 재생이다. 기본 지정값은 로컬 config의 `mvp_default_registration`이며 기존 설정 snapshot을 보존했다. 다른 기본 결과를 지정할 때에는 등록된 manifest/ID를 기존 등록 CLI의 `--make-default`로 명시한다. 기존 DB를 삭제하거나 snapshot 전체를 덮어써 최근 검토를 잃지 않는다. 이전 코드 시연이 필요하면 현재 변경을 보존한 별도 체크아웃에서 운영자가 선택하며 강제 reset은 하지 않는다.
