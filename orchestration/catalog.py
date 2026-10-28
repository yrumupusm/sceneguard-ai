"""Export selected historical measurements, never raw predictions or media.

The source JSON files remain local. Missing sources produce null measurements;
the original reports are referenced verbatim, not regenerated from these rows.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


REPORTS = [
    ("EXP-0001-phase2a-cv-baseline.md", "SSDLite 최소 CV 기준선", "SSDLite320 COCO_V1",
     "작은 CCTV 사람의 검출 누락이 먼저 확인됐다.", "검출기 대안을 검토했고 후속 EXP-0002에 기록했다."),
    ("EXP-0002-fcos-detector-comparison.md", "FCOS 검출기 비교", "FCOS ResNet50 FPN COCO_V1",
     "사람 일부를 복원했지만 중복·배경 오검출·연결 단절도 남았다.", "모델과 해상도가 함께 바뀐 비교다. 검출 개수 증가를 정확도 향상으로 해석하지 않는다."),
    ("EXP-0003-fcos-candidate-diagnostics.md", "FCOS 누락 단계 진단", "FCOS (동일 설정 계측)",
     "90초 사람 위치에 낮은 점수 후보가 있었다. 시각적 원인은 미확정이다.", "계측 시간이 추가돼 기존 추론 속도와 직접 비교하지 않는다."),
    ("EXP-0004-fcos-score-threshold-comparison.md", "최종 사람 점수 비교", "FCOS 저장 캐시 / IoU",
     "기준 하향으로 일부 사람을 복원했으나 중복·배경 의심도 증가했다.", "점수 기준 하향 채택 보류. 이 캐시 재생은 모델 추론 속도가 아니다."),
    ("EXP-0005-bytetrack-cache-comparison.md", "ByteTrack 캐시 비교", "FCOS 캐시 / IoU·ByteTrack",
     "국소 연결 개선과 중복·배경·부분 신체 문제가 공존했다.", "기본 추적기 교체 보류. ID 수·후보 수는 실제 사람 수나 성공 건수가 아니다."),
    ("EXP-0006-candidate-box-consistency.md", "박스 일관성 후보 검토", "EXP-0005 C 저장 관측",
     "007은 근거 부족, 030은 판단 유보로 남아 유용한 후보도 함께 막았다.", "기본 적용 보류. 0.2초 대기는 실제 경보 전달 지연을 추가한다."),
    ("EXP-0007-local-vlm-action-analysis.md", "독립 로컬 VLM 행동 분석", "Qwen3-VL-2B-Instruct",
     "통행 일부는 설명했으나 넘기 누락·문 열기 환각·반복·JSON 파싱 실패가 남았다.", "기본 연동 보류. 실제 입력의 행동과 설명을 사람과 검수한 뒤 다음 대조를 설계한다."),
]


def export(source: Path, destination: Path) -> dict:
    experiments = []
    imported_at = dt.datetime.now(dt.timezone.utc).isoformat()
    for number, (filename, title, model, summary, next_step) in enumerate(REPORTS, 1):
        eid = f"EXP-{number:04d}"
        report = "docs/experiments/" + filename
        metrics = []

        def add(rel, pointer, label, unit, sample_n, scope, transform=None):
            path = source / rel
            value = None
            exists = path.is_file()
            if exists:
                value = json.loads(path.read_text(encoding="utf-8"))
                for key in pointer:
                    value = value[key]
                if transform:
                    value = transform(value)
            metrics.append({"label": label, "value": value, "unit": unit,
                            "sample_n": sample_n, "scope": scope,
                            "source": rel, "source_pointer": pointer,
                            "source_sha256": sha(path) if exists else None,
                            "verification": "source_json_checked" if exists else "unavailable"})

        if number in (1, 2):
            for video in ("006", "007", "030", "031"):
                rel = f"outputs/cv_phase2{'a/smoke' if number == 1 else 'b/fcos'}{video}/run.json"
                count = 500 if video == "006" else 600 if video == "007" else 480
                add(rel, ["throughput_fps"], f"{video} 프레임 루프 처리량", "frame/s", count,
                    "워밍업 후 decode~출력·flush; 초기 로딩/preroll 제외. 최종 감지 성능 아님")
        elif number == 3:
            add("outputs/cv_phase2c/diagnostic030/diagnostic_config.json", ["frames_verified"],
                "동일 최종 출력 확인 프레임", "frame", 361, "030 84~96초, 최종 검출 불변 진단")
        elif number == 4:
            for threshold in ("t050", "t040", "t030", "t025"):
                for video in ("006", "007", "030", "031"):
                    add(f"outputs/cv_phase2d/replay{video}/{threshold}/summary.json", ["person_boxes"],
                        f"{video} {threshold} 박스", "box", 500 if video == "006" else 600 if video == "007" else 480,
                        "진단 집계: 사람 수/정확도 아님. 같은 캐시에 최종 기준만 적용")
        elif number == 5:
            for condition in "ABC":
                for video in ("006", "007", "030", "031"):
                    add(f"outputs/cv_phase2e/track{video}/{condition}/summary.json", ["candidates"],
                        f"{video} {condition} 경계 후보", "candidate", 500 if video == "006" else 600 if video == "007" else 480,
                        "진단 집계: 실제 침입/사람 통과 성공 아님")
        elif number == 6:
            for video in ("006", "007", "030", "031"):
                add("outputs/cv_phase2g/comparison/summary.json", ["summary", video, "candidates"],
                    f"{video} 보존한 원래 후보", "candidate", 500 if video == "006" else 600 if video == "007" else 480,
                    "원래 후보 보존, 007 근거 부족2 / 030 유보2. 정확도 아님")
        else:
            for clip in range(1, 7):
                rel = f"outputs/vlm_exp0007/run02/clip{clip:02d}/result.json"
                add(rel, ["generation_seconds"], f"clip{clip:02d} 생성", "s", 10,
                    "5초 선택 클립, 입력10프레임. generate+GPU동기화, 전처리·decode·저장 제외; 탐지 지연 아님")
                add(rel, ["peak_allocated_bytes"], f"clip{clip:02d} GPU 할당 최고", "GiB", 10,
                    "PyTorch 프로세스 peak allocated, 모델 포함, 전체 장치 메모리 아님", lambda x: x / 2**30)
        metrics.append({"label": "최종 행동 정확도", "value": None, "unit": "%", "sample_n": None,
                        "scope": "독립 검수 정답 부족으로 미측정", "source": report,
                        "source_sha256": sha(source / report), "verification": "not_measured"})
        metrics_rel = f"records/{eid}/metrics.json"
        write_json(destination / metrics_rel, {"schema_version": 1, "experiment_id": eid,
                   "comparison_group": eid, "cross_experiment_comparable": False, "metrics": metrics})
        record = {"schema_version": 1, "experiment_id": eid, "title": title, "summary": summary,
                  "run_id": f"historical-{eid}", "task_id": None, "attempt_id": None,
                  "role": "historical_import", "slot": "unassigned", "agent_model_requested": None,
                  "agent_model_effective": None, "reasoning_effective": None, "evaluated_model": model,
                  "config_hash": None, "data_manifest_hash": None, "code_sha": None,
                  "execution_status": "completed_with_recorded_limitations", "review_status": "AI_draft",
                  "decision_status": "adoption_on_hold", "metric_definitions": metrics_rel,
                  "metrics_path": metrics_rel, "report_path": report, "report_sha256": sha(source / report),
                  "limitations": ["개발 표본이며 독립 테스트 아님", "정밀 정답·카메라 독립성 미확정",
                                  "과거 agent model/effort·통합 run 해시가 없는 필드는 null; 측정 원천별 해시는 metrics에 보존"],
                  "evidence": [], "worker_opinion": summary, "next_step": next_step,
                  "review_path": "docs/reviews/ORCA-SETUP-historical-import.md",
                  "created_at": imported_at, "updated_at": imported_at,
                  "timestamp_scope": "record import time; not experiment start or completion time"}
        if number == 5:
            record["evidence"] = [{"artifact_id": "exp5-007", "label": "007 원본/B/C 정상→0.25배속", "kind": "video"},
                                  {"artifact_id": "exp5-030", "label": "030 원본/B/C 정상→0.25배속", "kind": "video"}]
        if number == 6:
            record["evidence"] = [{"artifact_id": "exp6-007", "label": "007 원본/후보/검토", "kind": "video"},
                                  {"artifact_id": "exp6-030", "label": "030 원본/후보/검토", "kind": "video"}]
        if number == 7:
            record["evidence"] = [{"artifact_id": f"exp7-clip{i:02d}", "label": f"clip{i:02d} 실제 모델 입력 검수 시트", "kind": "image"} for i in range(1, 7)]
        experiments.append(record)
    catalog = {"schema_version": 1, "experiments": experiments,
               "note": "기존 보고서 읽기 전용. 실험 모델과 작업자 모델은 서로 다름. TEST 큐는 별도."}
    write_json(destination / "records/catalog.json", catalog)
    return catalog


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--destination", type=Path, required=True)
    args = p.parse_args()
    print(f"Exported {len(export(args.source.resolve(), args.destination.resolve())['experiments'])} historical reports")


if __name__ == "__main__":
    main()
