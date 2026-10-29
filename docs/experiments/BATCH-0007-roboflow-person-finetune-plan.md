# BATCH-0007 — Roboflow 월장 사람 검출 파인튜닝 (준비 계획)

- 작성일: 2026-10-29
- 상태: **데이터 감사/학습 준비만 계획. 실제 데이터 다운로드·학습·GPU 추론·기본 모델 교체 미실행.**
- 근거: BATCH-0006 / EXP-0025의 E01_030 90초 미검출, 94초 일부 검출 및 반대편 사람 누락.
- 목표: **월장 자세의 person bbox 검출 누락을 줄일 수 있는지** 검증. 월장 행동/완료 판정, pose 관절 정확도 및 침입 권한 판정은 대상이 아님.

## 데이터 원출처와 알려진 사실

- 원출처: https://universe.roboflow.com/osborne-rowland-r4w5m/climbing-fence
- 버전: https://universe.roboflow.com/osborne-rowland-r4w5m/climbing-fence/dataset/1
- 공개 프로젝트 개요: 원본 이미지 107장, 6개 클래스, Object Detection, CC BY 4.0.
- 공개 버전 v1: 증강 포함 247장(train 210 / valid 20 / test 17), resize stretch 640x640, 수평 반전/회전/밝기/블러/노이즈 증강. 실제 파일·주석 미다운로드/미감사.
- 원본과 증강본이 train/val/test를 가로질러 중복되었는지 아직 **미확인**.
- 원 클래스: `fence`, `people-jump-fence`, `people-standing`, `person-climbing-fence`, `person-jump-fence`, `person-standing`.
- 사람 1명에 대응하는지 알 수 없는 `people-*`는 일괄 매핑 **금지**. 실제 이미지·bbox를 확인하고 개인별 박스가 아니면 보류/재주석.
- `person-*`도 각 bbox가 사람 전체인지, 부분 신체인지, 사람+울타리 장면 영역인지 시각 검수하기 전에는 일괄 변환하지 않는다.
- `fence` 박스는 학습 `person` 클래스로 매핑하지 않는다. `fence`만 존재하는 이미지에서 사람 누락 라벨이 없는지 점검한다.
- 공식 페이지의 CC BY 4.0 표시 외 원 이미지의 원출처 및 배포 조건/귀속 방식은 추가 확인.

## Gate D0 — 원본 및 라벨 감사 (모델 학습 전)

1. 로컬에서 사용자 권한으로 다운로드 가능한 원본 혹은 v1 YOLO export를 획득하되 비밀키를 공개하거나 외부로 CCTV 프레임을 업로드하지 않는다.
2. 실제 다운로드 파일 수/원본 이미지 수/label 행 수/클래스 ID `data.yaml` 매핑을 기록한다.
3. 6개 클래스 각각의 bbox를 원본 이미지에 시각화하고 전체/부분/복수 인물 여부를 표본 검수한다. `people-*`의 그룹 박스를 개인 `person` 박스로 자동 치환하지 않는다.
4. 동일 원본의 증강 변형이 평가 분할을 넘나드는지 확인한다. 원본 식별이 불가능하면 v1의 val/test를 독립 성능 지표로 쓰지 않고 미확정으로 표기한다.
5. 빈 annotation, 비정상 좌표, 박스 경계, 사람 누락 라벨, 중복을 탐지한다.
6. 검증된 사람별 박스만 `person: 0` 한 클래스로 변환한 **새 사본**을 만든다. 원본 YOLO 라벨을 덮어쓰지 않는다.
7. 공개 가능한 검수 요약(클래스별 수, 수동 수정/제외 건수, split 위험)만 GitHub에 기록한다. 다운로드 원본·라벨·오버레이·모델 가중치는 로컬 전용으로 유지한다.

**Gate D0 통과 조건:** 사람별 bbox 의미/좌표 변환/분할 누수/학습 가능 수량/권리 조건이 확인되어야 함. 미확인 시 파인튜닝 중단.

## Gate T0 — 통제된 파인튜닝

1. Detection 전용 COCO-pretrained YOLO 1종만 사용. Pose 체크포인트에 bbox-only YOLO detection 라벨로 pose 학습을 시도하지 않는다.
2. 동일 checkpoint와 환경으로 **무학습 baseline** 먼저 측정하고, 이어서 동일 detection 구조의 fine-tuned 결과와 비교한다.
3. 작은 월장 데이터만으로 COCO 사람 일반 검출 능력이 저하될 위험을 막기 위해, 사용권 확인된 일반 사람/비월장 검출 자료 혼합을 검토한다. 실제 확보 전에는 혼합했다고 주장하지 않는다.
4. 학습 split을 먼저 고정하고, 그 뒤 train에만 augmentation을 적용한다. 테스트/검증 프레임을 학습에 사용하지 않는다.
5. 첫 학습은 단일 사전등록 설정(모델/epoch/imgsz/batch/seed/freeze 정책)을 사용하고, 결과를 보고 무제한 hyperparameter sweep하지 않는다.
6. 기존 Orca canonical GPU queue, 현재 유효한 자원/lease 게이트 및 job 이력 보존을 준수한다. 학습 작업의 사용시간·GPU 메모리·checkpoint SHA를 별도 기록한다.
7. 모델 가중치·원본 데이터/학습 메타데이터의 민감한 부분을 공개 repo에 업로드하지 않는다. Ultralytics AGPL/Roboflow CC BY 라이선스와 포트폴리오 배포 범위를 점검한다.

## Gate E0 — 기존 SceneGuard 검출 누락과 직접 비교

- **개발 진단:** E01_030 84/90/94초, 같은 native PTS·RGB와 사전 정의한 C6 crop(537:1440,216:864). 기존 YOLO-Pose 실험은 참고자료이며, `Detection baseline` vs `Detection fine-tuned`를 주요 공정 비교로 사용한다. Detector↔Pose의 단순 검출 개수 비교를 동일 모델 성능 개선이라고 하지 않는다.
- **사람별 사용자 시각 검수:** 기대 인물과 박스의 실제 대응, 오른쪽/문 위/이미 넘어간 인물의 누락, 중복/배경 false boxes를 분리 기록. 박스 개수 증가는 실제 사람 복원과 동의어가 아니다.
- **정상/비월장 검증:** 접근만 하는 E01_030 50~55초 및 E01_007 47.5~52.5초 등의 사람 검출 유지·오검출 여부 확인. 검출 모델만으로 행동 오탐을 평가하지 않는다.
- **독립 검증:** 학습·threshold·모델 선택에 쓰지 않은 별도 카메라/장소의 사람이 포함된 CCTV 표본을 확보하고, 개인별 box ground truth가 있을 때만 검출 precision/recall·mAP를 산출한다. 그렇지 않으면 정성 검수로 제한한다.
- **후속 분리:** 사람 박스 개선 후에도 관절 추정/행동 판정은 해결되었다고 주장하지 않는다. Pose·tracking·VLM 결합은 별도 실험.

## 실행·변경 경계

- 이번 단계에서는 **계획 문서만 신규 추가**. 기존 `AGENTS.md`, `docs/CODEX_NEXT_TASK.md`, 실험 결과와 프로덕션 경로·모델 기본값을 변경하지 않는다.
- 실제 로컬 데이터셋 export가 확보되고 시각 검수가 완료되기 전에는 label 변환, GPU 학습, 새 checkpoint 추론을 시작하지 않는다.
- 로컬 CCTV E01_030 샘플은 학습에 넣지 않고 진단용으로 유지한다. 독립 camera/site 검증을 별도로 설계한다.
