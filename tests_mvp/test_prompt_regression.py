"""EXP-0016 CPU contract tests; model libraries are forbidden in this process."""
import importlib.util
import builtins
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from orchestration import mvp_command as command
from orchestration.queue import Queue, digest, source_hash
from mvp import method, runner

ROOT = Path(__file__).resolve().parents[1]
CONFIG = dict(phase='prompt-regression', view='fixed_roi', settings=command.SETTINGS.copy())


class RegressionRegistryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.assets = self.root / 'assets'
        self.runtime = self.root / 'queue'
        for name in command.sources(CONFIG):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.model = self.assets / 'weights/Qwen3-VL-2B-Instruct'
        self.model.mkdir(parents=True)
        (self.model / 'model.safetensors').write_bytes(b'CPU fixture only')
        (self.model / 'config.json').write_text('{}')
        self.interpreter = self.assets / '.venv-vlm/bin/python'
        self.interpreter.parent.mkdir(parents=True)
        self.interpreter.write_text('fixture never executed')
        sources_path = self.root / 'configs/mvp0001_sources.json'
        sources = json.loads(sources_path.read_text())
        for item in sources['continuous_sources']:
            target = self.assets / item['relative_video_path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item['source_id'].encode())
            item['sha256'] = command.file_hash(target)
        sources_path.write_text(json.dumps(sources))
        manifest_path = self.root / 'configs' / command.REGRESSION_MANIFEST
        manifest = json.loads(manifest_path.read_text())
        manifest['sources'] = {r['source_id']: r['sha256'] for r in sources['continuous_sources']
                               if r['source_id'] in manifest['sources']}
        manifest_path.write_text(json.dumps(manifest))
        for name, value in dict(ROOT=self.root, ASSETS=self.assets, MODEL_DIR=self.model,
                RUNTIME=self.runtime, INTERPRETER=self.interpreter,
                PINNED_MODEL_SHA256=command.file_hash(self.model / 'model.safetensors')).items():
            patch = mock.patch.object(command, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.queue = Queue.initialize(self.runtime)
        self.inputs = command.input_contract('prompt-regression')

    def enqueue(self, **changes):
        values = dict(job_key='regression', run_id=command.REGRESSION_RUN, task_id='t',
            dispatch_id='d', owner='o', command='mvp-0001', config=CONFIG,
            input_value=self.inputs, timeout=1800)
        values.update(changes)
        return self.queue.enqueue(**values)

    def test_both_views_same_prompt_hash_fixed_inputs_and_new_attempt_outputs(self):
        self.assertEqual(set(self.inputs['videos']), {'E01_007', 'E01_030'})
        self.assertEqual(set(self.inputs), {'videos', 'configs', 'model_files',
                                         'prompt_sha256', 'window_manifest_sha256'})
        for view in ('full_frame', 'fixed_roi'):
            cfg = {**CONFIG, 'view': view}
            argv = command.command(cfg, self.inputs, self.runtime, 'a'*32, 12)
            self.assertEqual(argv[3:7], ['--phase', 'prompt-regression', '--view', view])
            self.assertEqual(command.validate(cfg, self.inputs, self.runtime), ('prompt-regression', view))
        self.assertEqual(command.output_path('prompt-regression', 'a'*32),
                         self.assets / 'outputs/mvp0001/EXP-0016' / ('a'*32))
        self.assertNotEqual(command.output_path('dev', 'a'*32), command.output_path('prompt-regression', 'a'*32))
        self.assertNotEqual(command.output_path('full', 'a'*32), command.output_path('prompt-regression', 'a'*32))
        for attempt in ('../escape', 'A'*32, 'a'*31, None):
            with self.assertRaises(ValueError):
                command.output_path('prompt-regression', attempt)

    def test_input_and_code_hash_changes_fail_before_execution(self):
        original = source_hash('mvp-0001', CONFIG)
        for relative in ('configs/' + command.REGRESSION_PROMPT,
                         'configs/' + command.REGRESSION_MANIFEST, 'mvp/method.py'):
            path = self.root / relative
            before = path.read_bytes()
            path.write_bytes(before + b'\n')
            self.assertNotEqual(original, source_hash('mvp-0001', CONFIG))
            if not relative.endswith('method.py'):
                with self.assertRaises(ValueError):
                    command.validate(CONFIG, self.inputs, self.runtime)
            path.write_bytes(before)
        for path in (self.model / 'model.safetensors', self.model / 'config.json',
                     self.assets / 'data/TS_침입/E01_007.mp4'):
            before = path.read_bytes()
            path.write_bytes(before + b'changed')
            with self.assertRaises(ValueError):
                command.validate(CONFIG, self.inputs, self.runtime)
            path.write_bytes(before)

    def test_closed_phase_config_generation_window_roi_and_manifest_guards(self):
        for cfg in ({**CONFIG, 'phase': 'other'}, {**CONFIG, 'prompt': 'injected'},
                    {**CONFIG, 'view': 'other'}, {**CONFIG, 'settings': {**command.SETTINGS, 'max_new_tokens': 383}}):
            with self.assertRaises(ValueError):
                command.validate(cfg, self.inputs, self.runtime)
        path = self.root / 'configs' / command.REGRESSION_MANIFEST
        original = path.read_text()
        for field, value in (('windows', []), ('sampling_fps', 4.0),
                             ('rois', {'C3': [0, 0, 1, 1]}), ('labels', 'must not be accepted')):
            manifest = json.loads(original)
            manifest[field] = value
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                command.load_regression_manifest()
        path.write_text(original)
        settings = self.root / 'configs/mvp0001_settings.json'
        value = json.loads(settings.read_text())
        value['minimum_real_frames'] = 3
        settings.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            command.load_configs()

    def test_queue_run_guard_and_historical_rows_are_preserved(self):
        self.queue.enqueue(job_key='history', run_id='old', task_id='t', dispatch_id='d', owner='o')
        before = self.queue.status()
        with self.assertRaisesRegex(ValueError, 'existing Orca run'):
            self.enqueue(run_id='another-run')
        self.assertEqual(before, self.queue.status())
        job = self.enqueue()
        after = self.queue.status()
        self.assertEqual(after['jobs'][0], before['jobs'][0])
        self.assertEqual(before['attempts'], after['attempts'])
        self.assertEqual(job['command'], 'mvp-0001')
        self.assertEqual(job['source_hash'], source_hash('mvp-0001', CONFIG))

    def test_cli_registers_both_views_in_same_command_without_execution(self):
        from mvp.cli import main
        queue = mock.Mock()
        queue.enqueue.return_value = {'status': 'queued'}
        with mock.patch('orchestration.queue.Queue', return_value=queue), mock.patch('builtins.print'):
            for view in ('full_frame', 'fixed_roi'):
                main(['--runtime', str(self.runtime), 'enqueue', '--phase', 'prompt-regression',
                    '--view', view, '--job-key', 'fixture-' + view, '--run-id', command.REGRESSION_RUN,
                    '--task-id', 't', '--dispatch-id', 'd', '--owner', 'o'])
                values = queue.enqueue.call_args.kwargs
                self.assertEqual(values['command'], 'mvp-0001')
                self.assertEqual(values['timeout'], command.EXPECTED_SETTINGS['full_timeout_seconds'])
                self.assertEqual(values['input_value'], self.inputs)
                self.assertEqual(values['config'], {**CONFIG, 'view': view})
            queue.run_once.assert_not_called()

    def test_attempt_output_cannot_overwrite_or_follow_symlink(self):
        path = command.output_path('prompt-regression', 'a'*32)
        path.mkdir(parents=True)
        (path / 'marker').write_text('preserve')
        job = dict(input_json=json.dumps(self.inputs), input_hash=digest(self.inputs),
            config_hash=digest(CONFIG), source_hash=source_hash('mvp-0001', CONFIG),
            job_id='fixture', code_sha='fixture')
        with mock.patch.object(runner, 'verify_lease', return_value=job), \
                mock.patch.object(runner, 'RUNTIME', self.runtime), \
                mock.patch.object(runner, 'check_resources') as resources:
            with self.assertRaises(FileExistsError):
                runner.run('prompt-regression', 'fixed_roi', 'a'*32, 12)
            resources.assert_not_called()
        self.assertEqual((path / 'marker').read_text(), 'preserve')
        other = self.assets / 'redirect'
        other.mkdir()
        link = path.parent / ('b'*32)
        link.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            command.output_path('prompt-regression', 'b'*32)

    def test_resource_failure_keeps_explicit_bindings_without_model_import(self):
        job = dict(input_json=json.dumps(self.inputs), input_hash=digest(self.inputs),
            config_hash=digest(CONFIG), source_hash=source_hash('mvp-0001', CONFIG),
            job_id='fixture', code_sha='fixture')
        with mock.patch.object(runner, 'verify_lease', return_value=job), \
                mock.patch.object(runner, 'RUNTIME', self.runtime), \
                mock.patch.object(runner, 'check_resources', side_effect=ValueError('CPU resource fixture')):
            with self.assertRaisesRegex(ValueError, 'CPU resource fixture'):
                runner.run('prompt-regression', 'fixed_roi', 'a'*32, 12)
        summary = json.loads((command.output_path('prompt-regression', 'a'*32) / 'summary.json').read_text())
        self.assertEqual(summary['status'], 'failed')
        self.assertEqual(summary['bindings']['inputs'], self.inputs)
        self.assertEqual(digest(summary['bindings']['code_files']), job['source_hash'])


class PromptTests(unittest.TestCase):
    def test_old_dev_full_text_is_identical_and_new_schema_is_identical(self):
        old = (ROOT / 'configs/vlm_batch01_prompt.txt').read_text().strip()
        for phase, window_id in (('dev', 'clip01'), ('full', 'w000001')):
            self.assertEqual(method.analyzer_prompt(window_id, phase), f'Clip ID: {window_id}\n' + old)
        revised = method.analyzer_prompt('w000001', 'prompt-regression')
        self.assertEqual(revised.split('Answer briefly in English')[1], old.split('Answer briefly in English')[1])
        for phrase in ('ordered visible body motion', 'gate openness', 'crosswalk', "another person's movement"):
            self.assertIn(phrase, revised)
        for bad_id in ('q01', 'q06', 'E01_007', 'E01_030.mp4', 'w000001\nlabel', 'clip01'):
            with self.assertRaises(ValueError):
                method.analyzer_prompt(bad_id, 'prompt-regression')
        for forbidden in ('q01', 'q02', 'q03', 'q04', 'q05', 'q06', 'E01_', '.mp4',
                          'reference_label', 'official', 'report', 'climbing_present'):
            self.assertNotIn(forbidden, revised)

    def test_imports_prompt_and_preflight_never_import_model_libraries(self):
        code = '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'transformers'}:
        raise AssertionError('model library import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from mvp import method, runner
from orchestration import mvp_command
for phase in mvp_command.PHASES:
    method.analyzer_prompt('w000001', phase)
try:
    runner.run('prompt-regression', 'fixed_roi', 'invalid', -1)
except ValueError:
    pass
else:
    raise AssertionError('lease guard absent')
'''
        subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True)


@unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('av'),
                     'existing CPU video environment required')
class NativeWindowTests(unittest.TestCase):
    def test_prepare_chat_contains_only_selected_prompt_and_anonymous_id(self):
        import numpy as np
        analyzer = object.__new__(method.QwenAnalyzer)
        analyzer.phase = 'prompt-regression'
        analyzer.processor = SimpleNamespace(apply_chat_template=mock.Mock(side_effect=ValueError('captured chat')))
        source = dict(fps=30.0, pts_seconds=[0.0, 0.5], native_pts=[0, 15],
            time_base='1/30', relative_indices=[0, 15], source_size=[160, 96],
            window_start=0, window_end=5, last_decoded_pts=5,
            filename='E01_007.mp4', labels='climbing_present', q_id='q01',
            official_json='OFFICIAL_SENTINEL', report='REPORT_SENTINEL')
        importer = builtins.__import__

        def stub_video_metadata(name, *args, **kwargs):
            if name == 'transformers.video_utils':
                return SimpleNamespace(VideoMetadata=object)
            return importer(name, *args, **kwargs)

        with mock.patch.object(builtins, '__import__', side_effect=stub_video_metadata):
            with self.assertRaisesRegex(ValueError, 'captured chat'):
                analyzer.prepare(np.zeros((2, 96, 160, 3), dtype=np.uint8), source, 'w000001', [0, 0, 1, 1])
        messages = analyzer.processor.apply_chat_template.call_args.args[0]
        self.assertEqual(messages, [{'role': 'user', 'content': [{'type': 'video'},
            {'type': 'text', 'text': method.analyzer_prompt('w000001', 'prompt-regression')}]}])
        for forbidden in ('q01', 'E01_007', '.mp4', 'climbing_present', 'OFFICIAL_SENTINEL', 'REPORT_SENTINEL'):
            self.assertNotIn(forbidden, json.dumps(messages))

    def video(self, path):
        import av
        import numpy as np
        path.parent.mkdir(parents=True, exist_ok=True)
        with av.open(str(path), 'w') as output:
            stream = output.add_stream('libx264', rate=10)
            stream.width, stream.height, stream.pix_fmt = 160, 96, 'yuv420p'
            # Covers the latest frozen window plus real closing frames.
            for i in range(1611):
                frame = av.VideoFrame.from_ndarray(np.full((96, 160, 3), i % 128, dtype=np.uint8), format='rgb24')
                for packet in stream.encode(frame):
                    output.mux(packet)
            for packet in stream.encode():
                output.mux(packet)

    def test_original_pts_decode_calls_only_six_windows_in_both_views(self):
        import numpy as np
        calls = []
        class Spy:
            last_generated_token_ids = []
            last_processor_frames = None
            last_expanded_prompt = None
            last_input_metadata = None

            def analyze(self, rgb, source, window_id, roi):
                method.validate_source(rgb, source, window_id)
                # Deliberately pollute timing metadata; prepare text accepts no metadata.
                source.update(filename='E01_007.mp4', reference_label='climbing_present',
                              review_clip_id='q01', official_json='OFFICIAL_SENTINEL',
                              report_text='REPORT_SENTINEL')
                self.last_expanded_prompt = method.analyzer_prompt(window_id, 'prompt-regression')
                self.last_generated_token_ids = [[1, 2]]
                self.last_processor_frames = rgb.copy()
                calls.append((window_id, source.copy(), list(roi), self.last_expanded_prompt))
                return dict(raw_response='{}', parsed=None, parse={}, timing={}, input_metadata={})

        sources, cameras, _ = command.load_configs()
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            original = assets / 'synthetic.mp4'
            self.video(original)
            for source in sources['continuous_sources'][:2]:
                path = assets / source['relative_video_path']
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(original)
            for view in ('fixed_roi', 'full_frame'):
                calls.clear()
                output = assets / view
                output.mkdir()
                with mock.patch.object(runner, 'ASSETS', assets):
                    results = runner.run_prompt_regression(Spy(), output, sources, cameras, {'view': view})
                self.assertEqual(len(calls), 6)
                self.assertEqual([c[0] for c in calls], [r[2] for r in command.REGRESSION_WINDOWS])
                self.assertTrue(all(r['decode']['eof_reached'] for r in results))
                self.assertEqual(len(list(output.glob('*/windows/*/result.json'))), 6)
                for (window_id, source, roi, text), frozen in zip(calls, command.REGRESSION_WINDOWS):
                    sid, cid, wid, start, end = frozen
                    self.assertEqual(source['pts_seconds'], [start+i/2 for i in range(10)])
                    self.assertEqual(source['relative_indices'], list(range(0, 50, 5)))
                    self.assertEqual(roi, [0, 0, 1, 1] if view == 'full_frame' else cameras['cameras'][cid]['roi'])
                    for forbidden in ('q01', 'climbing_present', 'E01_007', 'E01_030',
                                      'OFFICIAL_SENTINEL', 'REPORT_SENTINEL', '.mp4'):
                        self.assertNotIn(forbidden, text)
                    self.assertIn(f'Clip ID: {wid}\n', text)
                self.assertFalse(any((output / 'E01_013').glob('*')))

    def test_frozen_window_timing_mismatch_never_reaches_analyzer(self):
        import numpy as np
        from mvp.windows import Sample, Window
        source, cameras, _ = command.load_configs()
        frames = tuple(Sample(np.zeros((96, 160, 3), dtype=np.uint8), i/2,
                              i*15, '1/30', i*15, i/2) for i in range(10))
        for window in (Window('w000001', 0, 4.9, 5, frames, 30, (160, 96), 5, False),
                       Window('w000001', 0, 5, 5, frames[:-1], 30, (160, 96), 5, False)):
            with tempfile.TemporaryDirectory() as tmp, mock.patch('mvp.windows.iter_windows', return_value=iter([window])):
                analyzer = SimpleNamespace(analyze=mock.Mock())
                with self.assertRaisesRegex(ValueError, 'PTS/frame-count'):
                    runner.run_prompt_regression(analyzer, Path(tmp), source, cameras, {'view': 'fixed_roi'})
                analyzer.analyze.assert_not_called()


if __name__ == '__main__':
    unittest.main()
