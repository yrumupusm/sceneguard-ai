# 로컬 읽기 전용 결과 뷰어

이 화면은 Orca 상태 projection과 등록된 기존 보고서만 보여준다. 실험 실행·승인·큐 제어 기능은 없으며 세팅 작업자와 향후 실험 슬롯은 별도다. 과거 실험은 미배정이고 첫 선택은 EXP-0007이다. 표와 그래프는 같은 metrics JSON을 사용하며 null은 미측정이다. 서로 다른 실험의 처리 시간은 측정 범위가 달라 순위로 비교하지 않는다.

총괄이 기존 결과를 가져오고 Git 제외 로컬 설정을 준비한 후, 예를 들어 다음과 같이 로컬에서 시작한다. 포트 충돌 여부는 실행 환경에서 확인한다.

```sh
SCENEGUARD_LAB_CONFIG=/absolute/path/to/local-config.json /home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m uvicorn webapp.app:app --host 127.0.0.1 --port 8765
```

주소는 `http://127.0.0.1:8765/`이며 Ctrl-C로 서버를 중지한다. 서버 중지는 Orca 작업을 중지하지 않는다. 외부 공개·포트 포워딩은 이 범위에 포함되지 않는다.

설정 JSON의 `repo_root`, `runtime_dir`, `artifact_allow_root`는 절대 경로이며 `artifacts`는 ID를 `{ "path": "절대 경로", "kind": "video" 또는 "image" }`에 대응시킨다. 실제 경로는 로컬 설정에만 두고 Git에 추가하지 않는다. 미디어는 카탈로그에 참조되고 설정에 등록된 파일만 제공하며, 허용 루트 아래의 mp4/jpg/png 정규 파일이어야 한다. 각 경로의 숨김 요소와 심볼릭 링크를 거부한다. 미디어 루트나 원본 데이터는 정적 마운트하지 않는다. 누락된 미디어는 사용할 수 없음으로 표시한다.

`GET /api/catalog`, `GET /api/experiments/{id}`, `GET /api/status`, `GET/HEAD /artifacts/{id}`가 조회 계약이다. 상태 파일이 없거나 읽을 수 없으면 미검증으로 표시하고 관측 시각이 만료되면 오래된 상태로 표시한다. 보고서 Markdown의 HTML과 이미지를 비활성화한다. 외부 CDN과 원격 이미지 없이 동작한다. 이 구현은 로컬에서 신뢰할 수 있는 설정 및 공개 카탈로그를 전제로 하며 인증·공개 호스팅 기능은 없다.

검증 명령:

```sh
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m unittest tests_orca.test_web -v
```

테스트는 임시 파일만 사용한다. 실제 자료 import와 브라우저 카드 전환·미디어 재생은 총괄이 별도로 확인해야 한다. 이 문서만으로 전체 Orca 세팅의 성공이나 실험 성능을 입증하지 않는다.
