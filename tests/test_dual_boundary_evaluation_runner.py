"""Evaluator contracts using synthetic cards; no candidate behavior evaluation."""
from copy import deepcopy
import json
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import evaluate_dual_boundary_passage as runner
from scripts.mvp_full_evaluation_adapter import extract_predictions
from sceneguard.accuracy_evaluation import evaluate, aggregate

API = dict(evaluate=evaluate, aggregate=aggregate, extract=extract_predictions)


def prediction(pid, start=10., confirmed=True, early=False):
    return dict(id=pid, gate_id='C1_fence', suspicion_evidence_pts=[start - 2, start + .25],
        confirmation_evidence_pts=([start - 1, start + .5] if early else [start + .5]) if confirmed else [],
        notifications=[dict(kind='suspicion', pts=start - 2)] +
            ([dict(kind='confirmation', pts=start - 1 if early else start + .5)] if confirmed else []))


def video(vid='E01_010', predictions=None, truth_id='t1', start=10.):
    return dict(video_id=vid, split='synthetic', duration_seconds=100., processed_seconds=100.,
        execution_status='complete', truth_basis='official_reference', unresolved_reference_events=0,
        events=[dict(id=truth_id, gate_id='C1_fence', start=start, end=start + 2,
                     provenance='synthetic fixture, never CCTV truth', onset_precise=False)],
        verified_non_event_intervals=[], predictions=predictions if predictions is not None else [prediction('p1')])


def cards_for(predictions):
    result = dict(contract='gate_activity_episodes_v1', execution_mode='current_input_analysis',
        source_evidence_mode='computed_in_current_run', events=[], evidence=[], cards=[],
        notification_intents=[], timeline=[])
    for pred in predictions:
        pid = pred['id']; confirms = pred['confirmation_evidence_pts']; ids = []
        for index, at in enumerate(pred['suspicion_evidence_pts']):
            eid = f'{pid}-e{index}'; ids.append(eid)
            confirmed = confirms[index] if len(confirms) == 2 else confirms[0] if confirms and index == 1 else None
            result['events'].append(dict(event_id=eid, gate_id=pred['gate_id'], decision_time_pts=at))
            result['evidence'].append(dict(event_id=eid, incident_id=pid, opened_pts=at,
                first_confirmation_pts=confirmed, automatic_status='침입 확인' if confirmed is not None else '침입 의심'))
        result['cards'].append(dict(incident_id=pid, gate_id=pred['gate_id'], event_ids=ids,
            first_confirmation_pts=min(confirms, default=None), suspicion_notified=True,
            confirmation_notified=bool(confirms)))
        for notice in pred['notifications']:
            key = pid + notice['kind']
            result['notification_intents'].append(dict(incident_id=pid, kind=notice['kind'],
                decision_time_pts=notice['pts'], notification_key=key))
            result['timeline'].append(dict(incident_id=pid, notification_kind=notice['kind'],
                decision_time_pts=notice['pts'], notification_key=key, notify=True))
    return result


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


class ComparisonTests(unittest.TestCase):
    def compare(self, old, new):
        before = dict(schema_version=1, protocol_id='fixture', analysis_revision='fixture', videos=old)
        after = dict(before, videos=new)
        return runner.comparison(before, after, dict(before=evaluate(before), after=evaluate(after)))

    def test_early_notice_is_retained_even_when_later_evidence_is_tp(self):
        old = video(predictions=[prediction('old', early=True)])
        new = video(predictions=[prediction('new')])
        result = self.compare([old], [new])
        entry = result['per_event'][1]  # confirmation after suspicion
        self.assertEqual(entry['outcome'], 'retained')
        self.assertEqual(entry['before']['first_matching_evidence_pts'], 10.5)
        self.assertEqual(entry['before_first_confirmation_or_suspicion_notice_pts'], 9.)
        self.assertEqual(entry['first_notice_delta_seconds'], 1.5)
        self.assertEqual(entry['matching_evidence_delta_seconds'], 0.)
        self.assertEqual(len(result['early_first_confirmation_notices']['before']), 1)
        self.assertEqual(result['early_first_confirmation_notices']['after'], [])
        self.assertEqual(result['user_010_approximate_onset']['notices']['before'][0]
                         ['offset_from_approximate_user_010_onset_seconds'], -54.)

    def test_gain_loss_and_every_remaining_miss_are_event_scoped(self):
        a = video('E01_036', [prediction('a')], 'early-event')
        a['events'].append(dict(a['events'][0], id='late-event', start=30., end=32.))
        b = deepcopy(a); b['predictions'] = [prediction('b', 30.)]
        result = self.compare([a], [b])
        confirms = [r for r in result['per_event'] if r['mode'] == 'confirmation']
        self.assertEqual([r['outcome'] for r in confirms], ['lost', 'gained'])
        self.assertEqual(result['remaining_confirmation_misses'][0]['id'], 'early-event')
        self.assertIn('early official event', result['outward_focus'][0]['interpretation'])

    def test_unmatched_and_verified_negative_notice_is_never_discarded(self):
        a = video(predictions=[prediction('late', 30.)])
        a['verified_non_event_intervals'] = [dict(gate_id='C1_fence', start=28., end=31., provenance='fixture')]
        result = self.compare([a], [deepcopy(a)])
        notice = result['notices']['after']['confirmation'][0]
        self.assertIsNone(notice['matched_truth_id'])
        self.assertTrue(notice['in_verified_negative'])
        self.assertEqual(len(result['remaining_confirmation_misses']), 1)

    def test_truth_edit_cannot_improve_candidate_score(self):
        a = video(); b = deepcopy(a); b['events'][0]['start'] = 9.
        with self.assertRaisesRegex(ValueError, 'changed frozen truth'):
            self.compare([a], [b])

    def test_unknown_association_and_missing_origin_stay_in_artifacts(self):
        data = dict(seed_decisions=[dict(automatic_confirmation=False, reason='origin_missing'),
                   dict(automatic_confirmation=False, reason='association_ambiguous'),
                   dict(automatic_confirmation=True)], cards=dict(evidence=[dict(first_confirmation_pts=None, binding=None)]))
        result = runner.unconfirmed_evidence(data)
        self.assertEqual([d['reason'] for d in result['seed_decisions']], ['origin_missing', 'association_ambiguous'])
        self.assertIsNone(result['evidence'][0]['binding'])


class BaselineContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        videos = []; count = 0; extras = 8
        for n in range(1, 46):
            item = video(f'E01_{n:03d}', [])
            if n == 6:
                item.update(events=[], truth_basis='unresolved', unresolved_reference_events=1)
            else:
                amount = 2 if extras else 1; extras -= int(bool(extras))
                item['events'] = []; preds = []
                for idx in range(amount):
                    start = 10. + idx * 10
                    item['events'].append(dict(id=f't{idx}', gate_id='C1_fence', start=start, end=start + 2,
                        provenance='fixture', onset_precise=False))
                    if count < 51:
                        preds.append(prediction(f'p{idx}', start, confirmed=count < 39, early=count < 8))
                    count += 1
                cards = cards_for(preds)
                item['predictions'] = extract_predictions(cards)
            if n == 6:
                cards = cards_for([])
            write(self.root / runner.BEFORE / 'videos' / item['video_id'] / 'cards.json', cards)
            videos.append(item)
        self.manifest = dict(schema_version=1, protocol_id='fixture', analysis_revision='fixture', videos=videos)
        write(self.root / runner.BEFORE / 'after-manifest.json', self.manifest)
        self.report = evaluate(self.manifest)
        write(self.root / runner.BEFORE / 'after-report.json', self.report)

    def test_exact_selected_baseline_counts_and_cards_are_required(self):
        _, _, totals = runner.validate_before(self.root, API)
        self.assertEqual(totals['confirmation']['counts']['tp'], 39)
        self.assertEqual(totals['suspicion']['counts']['tp'], 51)
        self.assertEqual(totals['confirmation']['counts']['early_first_notices_for_matched_events'], 8)

    def test_older_32_baseline_cannot_be_selected_by_provenance_label(self):
        self.report['modes']['confirmation']['by_video'][0]['counts']['tp'] = 32
        write(self.root / runner.BEFORE / 'after-report.json', self.report)
        with self.assertRaisesRegex(ValueError, 'after-report differs'):
            runner.validate_before(self.root, API)

    def test_modified_or_missing_selected_card_fails_consistency(self):
        path = self.root / runner.BEFORE / 'videos/E01_001/cards.json'
        data = runner.read(path); data['timeline'] = []
        write(path, data)
        with self.assertRaisesRegex(ValueError, 'timeline'):
            runner.validate_before(self.root, API)

    def test_006_and_008_cannot_be_removed(self):
        self.manifest['videos'][5]['unresolved_reference_events'] = 0
        write(self.root / runner.BEFORE / 'after-manifest.json', self.manifest)
        with self.assertRaisesRegex(ValueError, '006'):
            runner.validate_before(self.root, API)

    def test_008_semantic_hold_cannot_remove_official_event(self):
        # Move the event elsewhere to preserve the denominator while tampering
        # with held008; the dedicated008 contract must still reject it.
        events = self.manifest['videos'][7]['events']
        self.manifest['videos'][7]['events'] = []
        self.manifest['videos'][8]['events'].extend(events)
        write(self.root / runner.BEFORE / 'after-manifest.json', self.manifest)
        with self.assertRaisesRegex(ValueError, '008'):
            runner.validate_before(self.root, API)


class ExecutionBoundaryTests(unittest.TestCase):
    def test_replay_requires_revision_and_interface_before_output_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'never-created'
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.main(['--mode', 'replay', '--output', str(target)])
            self.assertFalse(target.exists())

    def test_saved_file_hash_change_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'measurement.json'; path.write_text('{}')
            protected = runner.hashes([path]); path.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'Protected inputs changed'):
                runner.verify_hashes(protected)

    def test_snapshot_imports_reject_already_imported_root_code(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'non-snapshot'):
                runner.load_api(Path(folder))

    def test_subprocess_isolated_worker_uses_explicit_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); (base / 'sceneguard').mkdir(); (base / 'scripts').mkdir()
            (base / 'sceneguard/__init__.py').write_text('')
            (base / 'sceneguard/accuracy_evaluation.py').write_text('def evaluate(x): return x\ndef aggregate(x): return x\n')
            (base / 'scripts/mvp_full_evaluation_adapter.py').write_text('def extract_predictions(x): return x\n')
            code = ('import importlib.util,pathlib; '
                f's=importlib.util.spec_from_file_location("runner",{str(Path(runner.__file__).resolve())!r}); '
                'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                f'a=m.load_api(pathlib.Path({str(base)!r})); assert a["evaluate"](42)==42')
            subprocess.run([sys.executable, '-I', '-c', code], check=True, capture_output=True)

    def test_profile_preserves_bent_polyline_and_archived_geometry(self):
        from sceneguard.portal_births import PortalGate, make_region, digest
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); output = root / 'new'; output.mkdir()
            scene = root / 'scene.json'; portal = root / 'portal.json'
            original_scene = dict(source_size=[1000, 1000], line=[[.45,.2],[.45,.8]],
                approach_polygon=[[.3,.1],[.7,.1],[.7,.9],[.3,.9]],
                zones={'outside':[[0,0],[.44,0],[.44,1],[0,1]],
                       'inside':[[.56,0],[1,0],[1,1],[.56,1]]},
                directions=['outside_to_inside','inside_to_outside'])
            original_portal = make_region(original_scene, 'C5',
                [[.4,.2],[.6,.2],[.6,.8],[.4,.8]], reference_pts=0., note='synthetic fixed portal')
            write(scene, original_scene)
            write(portal, original_portal)
            before = runner.hashes([scene, portal])
            polyline = [[.2, .1], [.3, .2], [.29, .3], [.4, .4], [.8, .7]]
            write(root / runner.DRAFT, dict(cameras=[dict(camera='C5', group_videos=['014'], draft_normalized=polyline)]))
            paths = [scene] * 4 + [scene, portal]
            with patch.object(runner, 'source_paths', return_value=(root, dict(camera='C5'), paths)):
                profiles = runner.build_profiles([14,14], root, output, 'reviewed_boundary')
            actual = runner.read(profiles['C5']['scene'])
            self.assertEqual(actual['reviewed_boundary'], polyline)
            self.assertEqual(actual['line'], runner.read(scene)['line'])
            revised_portal = runner.read(profiles['C5']['portal'])
            PortalGate(actual, revised_portal, 'C5')
            self.assertEqual(revised_portal['scene_digest'], digest(actual))
            self.assertEqual({k:v for k,v in revised_portal.items() if k != 'scene_digest'},
                             {k:v for k,v in original_portal.items() if k != 'scene_digest'})
            with self.assertRaisesRegex(ValueError, 'Portal must bind'):
                PortalGate(actual, original_portal, 'C5')
            runner.verify_hashes(before)
            original_portal['scene_digest'] = '0'*64
            write(portal, original_portal)
            with patch.object(runner, 'source_paths', return_value=(root, dict(camera='C5'), paths)):
                with self.assertRaisesRegex(ValueError, 'Portal must bind'):
                    runner.build_profiles([14], root, root / 'bad', 'reviewed_boundary')

    def test_frozen_revision_rejects_deleted_package_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'sceneguard').mkdir(); (root / 'scripts').mkdir()
            (root / 'sceneguard/__init__.py').write_text('')
            removed = root / 'sceneguard/required.py'; removed.write_text('VALUE=1\n')
            (root / 'scripts/mvp_full_evaluation_adapter.py').write_text('')
            for command in [['git', 'init', '-q'], ['git', 'add', '.'],
                            ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture']]:
                subprocess.run(command, cwd=root, check=True, capture_output=True)
            removed.unlink()
            with self.assertRaisesRegex(ValueError, 'file set differs'):
                runner.snapshot_code(root, root / 'output', 'HEAD')

    def test_isolated_worker_saves_unknown_evidence_and_cpu_provenance(self):
        # Entire pipeline is a stub fixture. This exercises process plumbing,
        # real output adaptation and error handling without candidate replay.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); snapshot = root / 'snapshot'
            (snapshot / 'sceneguard').mkdir(parents=True); (snapshot / 'scripts').mkdir()
            (snapshot / 'sceneguard/__init__.py').write_text('')
            (snapshot / 'sceneguard/accuracy_evaluation.py').write_text('def evaluate(x): return x\ndef aggregate(x): return x\n')
            adapter_source = Path(runner.__file__).with_name('mvp_full_evaluation_adapter.py')
            (snapshot / 'scripts/mvp_full_evaluation_adapter.py').write_bytes(adapter_source.read_bytes())
            (snapshot / 'scripts/evaluate_dual_boundary_passage.py').write_bytes(Path(runner.__file__).read_bytes())
            cards = cards_for([prediction('fixture', confirmed=False)])
            cards['rule_stage_calls'] = dict(detector_calls=0, tracker_calls=0, flow_calls=0, vlm_calls=0)
            fake_result = dict(cards=cards, seed_decisions=[dict(automatic_confirmation=False, reason='origin_missing')])
            (snapshot / 'sceneguard/mvp_pipeline.py').write_text(
                'def analyze_observations(*args):\n    return ' + repr(fake_result) + '\n')
            (snapshot / 'sceneguard/exp0036_application.py').write_text('def make_bundle(*args): return {}\n')
            scene = root / 'runtime/scene.json'; portal = root / 'runtime/portal.json'
            write(scene, {}); write(portal, {})
            archive = root / 'outputs/validation/mvp-all-v3/runs/E01_001/attempt-1'
            write(archive / 'request.json', dict(camera='C1', scene='runtime/scene.json', portal='runtime/portal.json',
                input_sha256={'runtime/scene.json': runner.sha(scene), 'runtime/portal.json': runner.sha(portal)}))
            write(archive / 'source/analysis/analysis.json', {})
            frames = archive / 'image-paths/frame-evidence.jsonl'; frames.parent.mkdir(); frames.write_text('{}\n')
            write(root / runner.BEFORE / 'videos/E01_001/cards.json', cards)
            protected = runner.hashes([scene, portal, frames])
            target = root / 'result'; job = root / 'job.json'
            write(job, dict(snapshot=str(snapshot), data_root=str(root), number=1, target=str(target),
                profile=dict(scene=str(scene), portal=str(portal)), protected_sources=protected))
            summary = runner.run_job(job)
            self.assertGreaterEqual(summary['process_cpu_seconds'], 0)
            self.assertTrue(all(Path(path).is_relative_to(snapshot) for path in summary['imports'].values()))
            self.assertEqual(runner.read(target / 'unconfirmed-evidence.json')['seed_decisions'][0]['reason'], 'origin_missing')
            self.assertEqual(runner.read(target / 'after-predictions.json')[0]['confirmation_evidence_pts'], [])
            runner.verify_hashes(protected)
            # Same frozen binding must fail if the measurement changes.
            frames.write_text('{"tampered":true}\n')
            with self.assertRaisesRegex(RuntimeError, 'exited'):
                runner.run_job(job)
            self.assertIn('Protected inputs changed', Path(str(job) + '.stderr').read_text())


if __name__ == '__main__':
    unittest.main()
