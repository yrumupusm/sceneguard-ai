# 로컬 개발 시작과 Codex 연결 안내

SceneGuard의 프로젝트 문서들은 GitHub 저장소에 추가되어 있다. 별도 ZIP 파일을 압축 해제할 필요는 없다.

## 로컬에서 최신 문서 받기
이미 클론한 경우:
```bash
cd ~/projects/sceneguard-ai
git status
git pull --ff-only
```

클론하지 않았다면:
```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/yrumupusm/sceneguard-ai.git
cd sceneguard-ai
```

작업 중인 파일이 있으면 `git pull` 전에 변경 사항을 확인·커밋하거나 적절히 보관한다.

## Codex에 전달할 첫 지시
`AGENTS.md`와 `docs/CODEX_FIRST_TASK.md`를 우선 읽고, `docs/data/DATASET_AUDIT_PLAN.md`에 따라 데이터를 **소량만** 점검하도록 한다. 모델 선정, 학습, 전체 데이터 다운로드는 지금 단계의 업무가 아니다.

## 문서 최신화
- 중대한 기술 선택: `docs/decisions/ADR-XXXX-*.md`
- 실제 측정: `docs/experiments/`
- 실패/해결: `docs/troubleshooting/`
- 일과 인수인계: `docs/HANDOFF.md`
- 전체 진행: `docs/WORK_PLAN.md`

## Git 주의
- 원본 CCTV 영상, 학습 모델, 생성 영상, 환경 파일, 인증정보는 Git에 올리지 않는다.
- 공개 가능한 샘플 이미지라도 반드시 출처와 재배포 조건을 확인한다.
- 작업 전후 `git status`, `git diff`를 확인하고 의도한 파일만 커밋한다.

## 첫 번째 완료 기준
정상/위험 샘플과 공식 라벨을 확인하고 `docs/data/SAMPLE_AUDIT.md`를 작성해 사용자 검수를 받으면, 다음 단계에서 모델 선택을 논의한다.
