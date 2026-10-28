"""CPU-only comparison contracts; no queue execution or real model access."""
import builtins
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from mvp import independent, method, runner
from orchestration import mvp_command as command
from orchestration.queue import Queue, digest, source_hash

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {'phase': 'independent-original', 'view': 'full_frame', 'settings': command.SETTINGS.copy()}
EVALUATION = 'configs/mvp_exp0016_independent_evaluation.json'


class IndependentContracts(unittest.TestCase):
    def test_exact_four_intervals_frames_pts_and_fixed_processing(self):
        manifest = independent.load_manifest()
        expected = [('E01_004', 60., 65.), ('E01_004', 0., 5.),
                    ('E01_021', 65., 70.), ('E01_021', 0., 5.)]
        self.assertEqual([(w['source_id'], w['start'], w['end']) for w in manifest['windows']], expected)
        self.assertEqual([w['window_id'] for w in manifest['windows']], [f'w{i:06d}' for i in range(1, 5)])
        for window in manifest['windows']:
            start = window['start']
            timing = window['timing']
            self.assertEqual(timing['pts_seconds'], [start + i/2 for i in range(10)])
            self.assertEqual(timing['native_pts'], [int(start*15360) + i*7680 for i in range(10)])
            self.assertEqual(timing['decoded_indices'], [int(start*30) + i*15 for i in range(10)])
            self.assertEqual(timing['relative_indices'], list(range(0, 150, 15)))
            self.assertEqual(timing['time_base'], ['1/15360']*10)
            self.assertEqual(len(window['frame_sha256']), 10)
        self.assertEqual(manifest['views'], ['full_frame'])
        self.assertEqual(manifest['roi'], [0, 0, 1, 1])
        self.assertEqual(manifest['generation'], command.SETTINGS)
        self.assertEqual(manifest['processor_size'], method.PROCESSOR_SIZE)
        self.assertEqual(manifest['model_sha256'], command.PINNED_MODEL_SHA256)
        self.assertEqual(manifest['run_id'], command.REGRESSION_RUN)

    def test_prompt_is_the_only_changed_axis_and_ids_are_anonymous(self):
        manifest = independent.load_manifest()
        for window in manifest['windows']:
            wid = window['window_id']
            for phase in independent.PHASES:
                selected = manifest['prompts'][phase]
                self.assertEqual(method.analyzer_prompt(wid, phase),
                    f'Clip ID: {wid}\n' + (ROOT / selected['path']).read_text().strip())
        for bad in ('v01', 'v03', 'q01', 'E01_004', 'w000005', 'w000001\nlabel'):
            for phase in independent.PHASES:
                with self.assertRaises(ValueError):
                    method.analyzer_prompt(bad, phase)
        self.assertNotEqual(*[manifest['prompts'][p]['sha256'] for p in independent.PHASES])

    def test_labels_are_sanitized_separate_and_do_not_claim_completion(self):
        evaluation = json.loads((ROOT / EVALUATION).read_text())
        self.assertEqual(evaluation['inference_manifest_sha256'], independent.MANIFEST_SHA256)
        labels = evaluation['labels']
        self.assertEqual([r['review_clip_id'] for r in labels], ['v01', 'v02', 'v03', 'v04'])
        self.assertEqual([r['label'] for r in labels], ['attempt_progress', 'non_event', 'attempt_progress', 'non_event'])
        self.assertEqual(labels[0]['completion'], 'not_assessed')
        self.assertEqual(labels[2]['completion'], 'not_assessed')
        self.assertEqual(labels[2]['location'], 'gap beside gate, not through gate')
        self.assertEqual(labels[2]['boundary_relation'], 'ambiguous')
        self.assertEqual(labels[2]['exact_location'], 'ambiguous')
        for forbidden in ('/home/', 'local_path', '.mp4', 'official_json'):
            self.assertNotIn(forbidden, json.dumps(evaluation))

    def test_evaluation_is_not_read_or_in_source_bindings(self):
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path.name == Path(EVALUATION).name:
                raise AssertionError('inference tried reading evaluation labels')
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', guarded):
            for phase in independent.PHASES:
                files = command.sources({**CONFIG, 'phase': phase})
                self.assertNotIn(EVALUATION, files)
                self.assertIn(independent.MANIFEST, files)
                self.assertIn('mvp/independent.py', files)
                self.assertIn('configs/vlm_batch01_prompt.txt', files)
                self.assertIn('configs/mvp_exp0016_prompt.txt', files)
                text = method.analyzer_prompt('w000001', phase)
                for forbidden in ('v01', 'v03', 'attempt_progress', 'non_event', 'E01_', 'boundary_relation'):
                    self.assertNotIn(forbidden, text)

    def test_manifest_and_both_prompt_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (independent.MANIFEST, 'configs/vlm_batch01_prompt.txt', 'configs/mvp_exp0016_prompt.txt'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, path)
            with mock.patch.object(independent, 'ROOT', root):
                for name in (independent.MANIFEST, 'configs/vlm_batch01_prompt.txt', 'configs/mvp_exp0016_prompt.txt'):
                    path = root / name
                    before = path.read_bytes()
                    path.write_bytes(before + b'\n')
                    with self.assertRaisesRegex(ValueError, 'hash differs'):
                        independent.load_manifest()
                    path.write_bytes(before)

    def test_source_binding_and_tampering_without_model_access(self):
        manifest = independent.load_manifest()
        expected = {sid: row['sha256'] for sid, row in manifest['sources'].items()}
        with mock.patch.object(independent, 'file_hash', side_effect=lambda p: expected[p.stem]), \
                mock.patch.object(independent, 'load_manifest', return_value=manifest):
            inputs = independent.bind_inputs()
        self.assertEqual(inputs['videos'], expected)
        self.assertEqual(set(inputs['prompt_hashes']), set(independent.PHASES))
        with mock.patch.object(independent, 'file_hash', return_value='changed'), \
                mock.patch.object(independent, 'load_manifest', return_value=manifest):
            with self.assertRaisesRegex(ValueError, 'source video hash differs'):
                independent.bind_inputs()

    def test_registry_only_adds_independent_inputs_to_same_model_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp)
            weights = model / 'model.safetensors'
            weights.write_bytes(b'CPU fixture')
            binding = {'videos': {'E01_004': 'a', 'E01_021': 'b'},
                       'window_manifest_sha256': independent.MANIFEST_SHA256,
                       'prompt_hashes': {'independent-original': 'c', 'independent-revised': 'd'}}
            with mock.patch.object(command, 'MODEL_DIR', model), \
                    mock.patch.object(command, 'PINNED_MODEL_SHA256', command.file_hash(weights)), \
                    mock.patch.object(independent, 'bind_inputs', return_value=binding):
                first, second = [command.input_contract(p) for p in independent.PHASES]
            self.assertEqual(first, second)
            self.assertEqual(set(first), {'model_files', 'configs', *binding})

    def test_same_queue_run_generation_and_full_frame_gates(self):
        for phase in independent.PHASES:
            config = {**CONFIG, 'phase': phase}
            command.validate_run(phase, command.REGRESSION_RUN)
            with self.assertRaisesRegex(ValueError, 'existing Orca run'):
                command.validate_run(phase, 'other-run')
            for bad in ({**config, 'view': 'fixed_roi'}, {**config, 'label': 'leak'},
                        {**config, 'settings': {**command.SETTINGS, 'seed': 1}}):
                with self.assertRaises(ValueError):
                    command.validate(bad, {}, command.RUNTIME)
            with self.assertRaisesRegex(ValueError, 'canonical GPU queue'):
                command.validate(config, {}, Path('/tmp/not-the-queue'))
            with mock.patch.object(command, 'input_contract', return_value={'binding': 'fixture'}):
                self.assertEqual(command.validate(config, {'binding': 'fixture'}, command.RUNTIME), (phase, 'full_frame'))
                with self.assertRaisesRegex(ValueError, 'hashes differ'):
                    command.validate(config, {}, command.RUNTIME)

    def test_queue_rejects_other_run_before_database_mutation(self):
        # Call only the rejection path; do not initialize, enqueue or execute a job.
        queue = Queue(command.RUNTIME)
        with mock.patch.object(command, 'validate'), mock.patch.object(queue, 'connection') as connect:
            with self.assertRaisesRegex(ValueError, 'existing Orca run'):
                queue.enqueue(job_key='never-enqueued', run_id='other', task_id='fixture',
                    dispatch_id='fixture', owner='fixture', command='mvp-0001', config=CONFIG, input_value={})
            connect.assert_not_called()

    def test_unique_outputs_and_symlink_rejection(self):
        paths = [command.output_path(p, a*32) for p in (*independent.PHASES, 'prompt-regression', 'dev', 'full') for a in ('a', 'b')]
        self.assertEqual(len(set(paths)), 10)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(command, 'ASSETS', Path(tmp)):
            path = command.output_path(independent.PHASES[0], 'a'*32)
            path.parent.mkdir(parents=True)
            path.symlink_to(Path(tmp), target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                command.output_path(independent.PHASES[0], 'a'*32)
        for attempt in ('../escape', 'A'*32, 'a'*31):
            with self.assertRaises(ValueError):
                command.output_path(independent.PHASES[0], attempt)

    def test_model_imports_and_gpu_probes_forbidden_before_lease(self):
        code = '''
import builtins, subprocess
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'transformers'}:
        raise AssertionError('model import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
subprocess.check_output = lambda *a, **k: (_ for _ in ()).throw(AssertionError('GPU probe'))
from mvp import method, runner
for phase in ('independent-original', 'independent-revised'):
    method.analyzer_prompt('w000001', phase)
    try:
        runner.run(phase, 'full_frame', 'invalid', -1)
    except ValueError:
        pass
    else:
        raise AssertionError('lease guard absent')
'''
        subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True)


class IndependentDecodeTests(unittest.TestCase):
    def test_processor_chat_ignores_polluted_metadata_for_both_prompts(self):
        import numpy as np
        source = {'fps':30., 'pts_seconds':[0.,.5], 'native_pts':[0,7680],
                  'time_base':'1/15360', 'relative_indices':[0,15], 'source_size':[32,32],
                  'window_start':0., 'window_end':5., 'last_decoded_pts':5.,
                  'review_clip_id':'v01', 'reference_label':'LABEL_SENTINEL',
                  'filename':'E01_004.mp4', 'report':'REPORT_SENTINEL', 'location':'GAP_SENTINEL'}
        importer = builtins.__import__
        def stub(name, *args, **kwargs):
            if name == 'transformers.video_utils':
                return SimpleNamespace(VideoMetadata=object)
            return importer(name, *args, **kwargs)
        for phase in independent.PHASES:
            analyzer = object.__new__(method.QwenAnalyzer)
            analyzer.phase = phase
            analyzer.processor = SimpleNamespace(apply_chat_template=mock.Mock(side_effect=ValueError('captured')))
            with mock.patch.object(builtins, '__import__', side_effect=stub):
                with self.assertRaisesRegex(ValueError, 'captured'):
                    analyzer.prepare(np.zeros((2,32,32,3), dtype=np.uint8), source, 'w000001', [0,0,1,1])
            messages = analyzer.processor.apply_chat_template.call_args.args[0]
            self.assertEqual(messages, [{'role':'user', 'content':[
                {'type':'video'}, {'type':'text', 'text':method.analyzer_prompt('w000001', phase)}]}])
            for forbidden in ('LABEL_SENTINEL', 'REPORT_SENTINEL', 'GAP_SENTINEL', 'v01', 'E01_004'):
                self.assertNotIn(forbidden, json.dumps(messages))

    def fixture(self):
        import numpy as np
        from mvp.windows import Sample, Window
        manifest = copy.deepcopy(independent.load_manifest())
        windows = []
        for row in manifest['windows']:
            samples = tuple(Sample(np.zeros((32, 32, 3), dtype=np.uint8), row['start']+i/2,
                int(row['start']*15360)+i*7680, '1/15360', int(row['start']*30)+i*15, row['start']+i/2) for i in range(10))
            w = Window('w000999', row['start'], row['end'], row['end'], samples, 30., (32,32), row['end'], False)
            row['timing'] = w.source()
            row['frame_sha256'] = [hashlib.sha256(s.rgb.tobytes()).hexdigest() for s in samples]
            windows.append(w)
        return manifest, windows

    def test_cpu_spy_exact_four_calls_and_outputs_same_across_prompts(self):
        import numpy as np
        manifest, windows = self.fixture()
        captured = []
        for phase in independent.PHASES:
            calls = []
            def analyze(rgb, source, wid, roi):
                calls.append((rgb.copy(), copy.deepcopy(source), wid, roi))
                spy.last_expanded_prompt = method.analyzer_prompt(wid, phase)
                spy.last_processor_frames = rgb.copy()
                return {'raw_response': '{}'}
            spy = SimpleNamespace(analyze=analyze, last_generated_token_ids=[], last_expanded_prompt=None,
                                  last_processor_frames=None, last_input_metadata=None)
            def decode(path, stats):
                stats['eof_reached'] = True
                return iter([w for w, row in zip(windows, manifest['windows']) if row['source_id'] == path.stem])
            with tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(independent, 'load_manifest', return_value=manifest), \
                    mock.patch.object(independent, 'bind_inputs', return_value={
                        'videos': {'E01_004':'a', 'E01_021':'b'}, 'prompt_hashes': {phase:'c'}}), \
                    mock.patch.object(independent, 'validate_decoder'), \
                    mock.patch('mvp.windows.iter_windows', side_effect=decode):
                folder = Path(tmp)
                results = independent.run_comparison(spy, folder, {'phase':phase, 'view':'full_frame', 'run_id':command.REGRESSION_RUN})
                self.assertEqual(results, [f'w{i:06d}' for i in range(1,5)])
                self.assertEqual(len(list(folder.glob('windows/*/result.json'))), 4)
                self.assertEqual(len(list(folder.glob('windows/*/processor_rgb.npy'))), 4)
                self.assertTrue(all(c[3] == [0,0,1,1] for c in calls))
                for c in calls:
                    self.assertEqual(set(c[1]), set(manifest['windows'][0]['timing']))
                with self.assertRaises(FileExistsError):
                    independent.run_comparison(spy, folder, {'phase':phase, 'view':'full_frame', 'run_id':command.REGRESSION_RUN})
            captured.append(calls)
        for first, second in zip(*captured):
            np.testing.assert_array_equal(first[0], second[0])
            self.assertEqual(first[1:], second[1:])

    def test_changed_frame_pts_index_dimensions_and_count_rejected(self):
        manifest, windows = self.fixture()
        row, window = manifest['windows'][0], windows[0]
        independent.validate_window(window, row, window.rgb)
        rgb = window.rgb
        rgb[0,0,0,0] = 1
        with self.assertRaisesRegex(ValueError, 'RGB frame hashes'):
            independent.validate_window(window, row, rgb)
        for key in ('native_pts', 'decoded_indices', 'pts_seconds', 'source_size'):
            changed = copy.deepcopy(row)
            changed['timing'][key][0] += 1
            with self.assertRaisesRegex(ValueError, 'frame indices/PTS/timing'):
                independent.validate_window(window, changed, window.rgb)
        with self.assertRaises(ValueError):
            independent.validate_window(window, row, window.rgb[:-1])

    def test_decoder_and_run_view_drift_rejected_before_analyzer(self):
        manifest = independent.load_manifest()
        independent.validate_decoder(manifest)
        changed = copy.deepcopy(manifest)
        changed['decoder']['pyav'] = 'other'
        with self.assertRaisesRegex(ValueError, 'decoder differs'):
            independent.validate_decoder(changed)
        spy = SimpleNamespace(analyze=mock.Mock())
        for change in ({'run_id':'other'}, {'view':'fixed_roi'}, {'phase':'prompt-regression'}):
            context = {'phase':independent.PHASES[0], 'view':'full_frame', 'run_id':command.REGRESSION_RUN, **change}
            with self.assertRaises(ValueError):
                independent.run_comparison(spy, Path('/unused'), context)
        spy.analyze.assert_not_called()


if __name__ == '__main__':
    unittest.main()
