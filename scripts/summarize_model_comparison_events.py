"""Join saved outputs to fixed official event times; never infer person/event success."""
import argparse
import json
from pathlib import Path

if __package__:
    from .comparison_saved_evidence import ROOT, read, sha, checked_rows, checked_head_scores
    from .summarize_model_comparison_heads import verified_raw_models
else:
    from comparison_saved_evidence import ROOT, read, sha, checked_rows, checked_head_scores
    from summarize_model_comparison_heads import verified_raw_models

REFERENCE = ROOT/'outputs/action-recognition/exp0065/coverage-v1/per-video.json'
REFERENCE_SHA = '9d5cc2359cbc1f2bafdea0b9157c57a5d3202e1578ab2c9da3113c713e7b4295'
JOINT = {'evad_vitb_vmaev2', 'evad_vitl', 'stmixer_vitb_vmaev2'}


def in_reference(window, event):
    # Anchor membership is fixed before seeing task-head results. Supplemental
    # diagnostic points do not inflate the primary one-second-grid denominator.
    return window['role'] == 'fullvideo_regular' and event['start'] <= window['anchor_pts'] <= event['end']


def event_diagnostic(event, rows, joint):
    rows = [r for r in rows if in_reference(r['window'], event)]
    action = [r for r in rows if r['action_candidate']]
    combined = [r for r in rows if r['person_and_action_candidate']] if joint else []
    available = combined if joint else action
    state = ('no_regular_anchor_in_reference' if not rows else
             'temporal_candidate_identity_unverified' if available else
             'action_candidate_without_native_person_candidate' if action and joint else
             'input_present_below_action_threshold')
    return dict(**{k: event[k] for k in ('video_id', 'reference_id', 'gate_id', 'start', 'end', 'baseline_confirmation_matched')},
                diagnostic=state, regular_anchor_windows=len(rows), action_candidate_windows=len(action),
                person_and_action_candidate_windows=len(combined) if joint else None,
                window_ids=[r['window']['window_id'] for r in rows],
                candidate_window_ids=[r['window']['window_id'] for r in available],
                first_candidate_input_available_pts=min((r['window']['available_after_pts'] for r in available), default=None),
                maximum_action_score=max((r['maximum_action_score'] for r in rows), default=None),
                same_person_and_gate_verified=False, action_true_positive=None, person_recovery=None,
                intrusion_completed=None, online_detection_delay_seconds=None)


def summarize(raw_summary_path, score_paths):
    if sha(REFERENCE) != REFERENCE_SHA: raise ValueError('Frozen reference context changed')
    videos = read(REFERENCE); events = [e for v in videos for e in v['events']]
    if len(events) != 52 or sum(e['baseline_confirmation_matched'] for e in events) != 37:
        raise ValueError('Official baseline denominator changed')
    cohort_path = ROOT/'outputs/model-comparison/exp0066/cohort-v1/manifest.json'
    cohort = read(cohort_path); raw_models = verified_raw_models(read(raw_summary_path), sha(cohort_path))
    expected = {}
    for video in cohort['videos']:
        if sha(video['plan']['path']) != video['plan']['sha256']: raise ValueError('Input plan changed')
        plan = read(video['plan']['path'])
        for role, windows in [('regular', plan['windows']), ('diagnostic', plan['supplemental_windows'])]:
            for w in windows:
                if w['window_id'] in expected: raise ValueError('Duplicate input window')
                expected[w['window_id']] = dict(role=role, window=w, video_id=video['video_id'], source_sha256=video['source_sha256'])
    scores = {}
    for path in score_paths:
        model = read(path)['model_id']
        if model in scores: raise ValueError('Duplicate head')
        scores[model] = path
    if set(scores) != set(raw_models)-{'r3d18_exp0064'}: raise ValueError('Exact seven heads required')
    models = {}
    for model, (result, proof) in raw_models.items():
        by_video = {}; score_proof = None
        if model == 'r3d18_exp0064':
            def raw_rows():
                for row in checked_rows(Path(proof['result_path']).parent/'windows.jsonl', result, expected):
                    out = row['output']
                    if out['threshold'] != .5: raise ValueError('R3D threshold changed')
                    yield dict(video_id=row['video_id'], window=row['window'], action_candidate=out['climbing_score'] >= .5,
                               maximum_action_score=out['climbing_score'], person_and_action_candidate=None)
            compact_rows = raw_rows()
        else:
            _, _, score_proof = checked_head_scores(scores[model], result, proof, expected)
            def head_rows(path=scores[model]):
                with (path.parent/'scores.jsonl').open(encoding='utf-8') as stream:
                    for line in stream:
                        row = json.loads(line)
                        yield dict(video_id=row['video_id'], window=row['window'],
                                   action_candidate=any(s['climbing_action_candidate'] for s in row['scores']),
                                   maximum_action_score=max(s['climbing_action_score'] for s in row['scores']),
                                   person_and_action_candidate=any(s['person_and_action_candidate'] is True for s in row['scores']))
            compact_rows = head_rows()
        for row in compact_rows: by_video.setdefault(row['video_id'], []).append(row)
        models[model] = dict(raw_provenance=proof, score_provenance=score_proof,
                            events=[event_diagnostic(e, by_video[e['video_id']], model in JOINT) for e in events])
    return dict(status='official_time_context_diagnostic_not_event_evaluation', models=models,
                reference=dict(path=str(REFERENCE), sha256=REFERENCE_SHA),
                raw_summary=dict(path=str(raw_summary_path.resolve()), sha256=sha(raw_summary_path)),
                summarizer_sha256=sha(__file__), official_events=52, baseline_confirmed=37, baseline_missed=15,
                unresolved_reference_events=sum(v['unresolved_reference_events'] for v in videos),
                semantic_evaluation_complete=False, new_intrusion_decisions=0,
                limitations=['One-second-grid anchors inside official intervals; extra diagnostic anchors excluded.',
                             'A temporal candidate may belong to another person or gate and is never a true positive here.',
                             'No regular anchor is a sampling limitation, not proof of absent video or people.',
                             'First input availability excludes compute/queue delay and is not an alarm timestamp.',
                             'Raw joint scores include low-person-score queries; combined candidates apply native person thresholds.',
                             'Unresolved E01_006 reference is excluded from the fixed 52 and remains unresolved.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-summary', type=Path, required=True)
    parser.add_argument('--score', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = summarize(args.raw_summary, args.score)
    with args.output.open('x', encoding='utf-8') as stream: json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
    print(json.dumps(dict(output=str(args.output), events=52, semantic_evaluation_complete=False)))
