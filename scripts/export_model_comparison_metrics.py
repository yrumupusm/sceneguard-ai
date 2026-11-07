"""Export verified comparison summaries; temporal candidates remain unreviewed."""
import argparse
import json
from pathlib import Path

if __package__:
    from .comparison_saved_evidence import ROOT, read, sha
    from .summarize_model_comparison import MODELS
    from .summarize_model_comparison_events import REFERENCE, REFERENCE_SHA
else:
    from comparison_saved_evidence import ROOT, read, sha
    from summarize_model_comparison import MODELS
    from summarize_model_comparison_events import REFERENCE, REFERENCE_SHA

STATES = {
    'temporal_candidate_identity_unverified': '시간대 후보 있음 · 대상 미확인',
    'input_present_below_action_threshold': '입력 있음 · 행동 점수 미달',
    'action_candidate_without_native_person_candidate': '행동 점수 통과 · 사람 기준 결합 후보 없음',
    'no_regular_anchor_in_reference': '사건 구간 안의 정규 관측 시점 없음',
}


def event_counts(rows):
    if (len(rows) != 52 or any(type(r['baseline_confirmation_matched']) is not bool for r in rows)
            or len({(r['video_id'], r['reference_id']) for r in rows}) != 52
            or sum(r['baseline_confirmation_matched'] for r in rows) != 37):
        raise ValueError('Exact 52 distinct references and unchanged baseline required')
    for row in rows:
        if (row['diagnostic'] not in STATES or row['same_person_and_gate_verified'] is not False
                or any(row[k] is not None for k in ('action_true_positive', 'person_recovery', 'intrusion_completed', 'online_detection_delay_seconds'))):
            raise ValueError('Temporal diagnostics cannot become semantic success')
    return {group: {state: sum(r['diagnostic'] == state for r in selected) for state in STATES}
            for group, selected in [('all52', rows), ('baseline_missed15', [r for r in rows if not r['baseline_confirmation_matched']])]}


def binding(path):
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), sha256=sha(path))


def validate_summary_links(raw, heads, events, references):
    fields = ('video_id', 'reference_id', 'gate_id', 'start', 'end', 'baseline_confirmation_matched')
    expected = {(r['video_id'], r['reference_id']): {k: r[k] for k in fields} for r in references}
    if len(expected) != 52 or len(references) != 52:
        raise ValueError('Exact frozen reference set required')
    for model in MODELS:
        e = events['models'][model]
        score = None if model == 'r3d18_exp0064' else heads['models'][model]['score_provenance']
        if e['raw_provenance'] != raw['models'][model]['provenance'] or e['score_provenance'] != score:
            raise ValueError('Cross-summary raw/score provenance differs')
        actual = {(r['video_id'], r['reference_id']): {k: r[k] for k in fields} for r in e['events']}
        if len(e['events']) != 52 or actual != expected:
            raise ValueError('Event identity/gate/time/baseline differs from frozen references')


def export(raw_path, heads_path, events_path, output):
    raw, heads, events = map(read, (raw_path, heads_path, events_path))
    raw_binding = dict(path=str(raw_path.resolve()), sha256=sha(raw_path))
    if (raw['all_eight_full_passes_complete'] is not True or set(raw['models']) != set(MODELS)
            or heads['all_seven_heads_scored'] is not True or set(heads['models']) != set(MODELS)-{'r3d18_exp0064'}
            or heads['r3d_threshold'] != .5
            or set(events['models']) != set(MODELS) or events['official_events'] != 52
            or events['baseline_confirmed'] != 37 or events['baseline_missed'] != 15
            or any(x['semantic_evaluation_complete'] is not False for x in (raw, heads, events))
            or heads['raw_summary'] != raw_binding or events['raw_summary'] != raw_binding):
        raise ValueError('Complete, consistent, non-semantic source summaries required')
    if (sha(REFERENCE) != REFERENCE_SHA
            or events['reference'] != dict(path=str(REFERENCE), sha256=REFERENCE_SHA)):
        raise ValueError('Frozen event reference binding differs')
    references = [e for video in read(REFERENCE) for e in video['events']]
    validate_summary_links(raw, heads, events, references)
    public = dict(experiment_id='EXP-0066', exporter_sha256=sha(__file__),
                  sources={k: binding(p) for k, p in [('raw', raw_path), ('heads', heads_path), ('events', events_path)]},
                  semantic_evaluation_complete=False, baseline_confirmed=37, official_events=52,
                  unresolved_reference_events=events['unresolved_reference_events'], models={})
    event_fields = ('video_id', 'reference_id', 'gate_id', 'start', 'end', 'baseline_confirmation_matched',
                    'diagnostic', 'regular_anchor_windows', 'action_candidate_windows', 'person_and_action_candidate_windows',
                    'first_candidate_input_available_pts', 'same_person_and_gate_verified', 'action_true_positive',
                    'person_recovery', 'intrusion_completed', 'online_detection_delay_seconds')
    for model in MODELS:
        r = raw['models'][model]
        if r['status'] != 'inference_complete' or r['windows'] != 6219 or r['decoded_native_frames'] != 184300:
            raise ValueError('Incomplete raw model')
        item = {k: r[k] for k in ('elapsed_seconds', 'load_seconds', 'peak_gpu_allocated_bytes', 'peak_gpu_reserved_bytes',
                                   'windows', 'decoded_native_frames', 'model_spec_sha256', 'source_hash')}
        item['raw_result_sha256'] = r['provenance']['result_sha256']
        item['event_counts'] = event_counts(events['models'][model]['events'])
        item['events'] = [{k: e[k] for k in event_fields} for e in events['models'][model]['events']]
        if model != 'r3d18_exp0064':
            h = heads['models'][model]
            if (h['status'] != 'frozen_head_scoring_complete' or h['official_reference_only'] is not True
                    or h['human_calibration_complete'] is not False
                    or any(h[k] is not None for k in ('person_recall', 'climbing_precision', 'climbing_recall', 'intrusion_improvement'))):
                raise ValueError('Completed weak-reference head required without human-performance claims')
            item['head'] = {k: h[k] for k in ('head_sha256', 'selected_epoch', 'selection', 'sample_count', 'feature_dimension',
                'coverage_by_split', 'validation_metric_scope', 'validation_normal_subtypes', 'groups',
                'cpu_head_scoring_seconds', 'scoring_elapsed_seconds', 'timing_scope')}
            item['head']['score_result_sha256'] = h['score_provenance']['sha256']
        else:
            item['fixed_r3d_threshold'] = .5
        public['models'][model] = item
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output/'comparison-summary.json'
    metrics_path = output/'metrics.json'
    if summary_path.exists() or metrics_path.exists(): raise ValueError('Preserve prior public result files')
    with summary_path.open('x', encoding='utf-8') as stream: json.dump(public, stream, ensure_ascii=False, indent=2, allow_nan=False)
    source = binding(summary_path)
    rows = []
    def add(label, value, unit, n, scope, verification='saved_output_recomputed'):
        rows.append(dict(label=label, value=value, unit=unit, sample_n=n, scope=scope,
                         source=source['path'], source_sha256=source['sha256'], verification=verification))
    for model, r in public['models'].items():
        scope = '동일 45영상 전구간 읽기 · 정규 6,177창/진단 42창 · 학습/준비 시간 제외'
        add(model+' · 원본 처리 시간', r['elapsed_seconds'], '초', 45, scope)
        add(model+' · GPU 최대 allocated', r['peak_gpu_allocated_bytes']/2**30, 'GiB', 6219, scope+' · PyTorch allocator')
        add(model+' · GPU 최대 reserved', r['peak_gpu_reserved_bytes']/2**30, 'GiB', 6219, scope+' · GPU 전체 사용량 아님')
        for group, n, label in [('all52', 52, '공식 참조 전체'), ('baseline_missed15', 15, '기존 확인 누락')]:
            for state, count in r['event_counts'][group].items():
                add(model+' · '+label+' · '+STATES[state], count, '참조 사건', n,
                    '정규 anchor가 공식 사건 구간 안에 있음 · 대상/문 대응 미확인 · TP/복구율 아님')
        if 'head' in r:
            h = r['head']; selection = h['selection']
            detail = {'conditional_on_matched_automatic_queries': '자동 대응된 사람 후보에 한정',
                      'weak_full_scene_not_actor_specific': '장면 전체의 약한 정답 · 사람 특정 불가'}[h['validation_metric_scope']]
            scope = '별도 검증 공식 라벨 참조 · 정상은 앉기만 · 학교 성능 아님 · '+detail
            for key, title, n in [('reference_precision', '참조 정밀도', selection['tp']+selection['fp']),
                                  ('reference_recall', '참조 재현율', selection['tp']+selection['fn']),
                                  ('reference_fpr', '참조 음성 통과율', selection['negative_count'])]:
                value = selection[key]
                add(model+' · '+title, None if value is None else 100*value, '%', n, scope, 'official_reference_only')
    add('EXP-0062 AFTER 기존 확인 대응', 37, '참조 사건', 52, '기존 기준선 보존 · 새 침입 판단 없음')
    for label in ['학교 사람 누락 복구율', '학교 넘기 정밀도', '학교 넘기 재현율', '침입 완료 성능 개선', '실제 보행/대기 오경보율']:
        add(label, None, '%', None, '관심 인물/행동의 정답 검수 부족 · 미측정', 'unavailable')
    with metrics_path.open('x', encoding='utf-8') as stream:
        json.dump(dict(schema_version=1, experiment_id='EXP-0066', metrics=rows), stream, ensure_ascii=False, indent=2, allow_nan=False)
    return dict(summary=binding(summary_path), metrics=binding(metrics_path), metric_rows=len(rows), semantic_evaluation_complete=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('raw-summary', 'head-summary', 'events', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.raw_summary, args.head_summary, args.events, args.output)))
