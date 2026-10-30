"""CPU-only queue integration and temporal isolation for EXP-0038."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from mvp import exp0038 as x, cli, runner
from orchestration import mvp_command as command
from orchestration.queue import digest
from tests_mvp.test_exp0038 import rows


class Registry(unittest.TestCase):
    def test_receipt_all_shards_and_environment_bound_without_baseline(self):
        inputs = {'appearance_manifest_sha256':'native'}
        receipt = {'model_id':x.MODEL_ID,'revision':x.REVISION,'files':{}}
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp)/'checkpoint.json';checkpoint.write_text(json.dumps(receipt))
            with ExitStack() as stack:
                for p in [patch.object(x,'CHECKPOINT',checkpoint),
                    patch.object(x,'ROOT',Path(tmp)),
                    patch.object(x,'MODEL_DIR',Path(tmp)/'weights/8b'),
                    patch.object(x,'verify_checkpoint',return_value={'all_four':'verified'}),
                    patch.object(x,'environment_binding',return_value={'environment':'verified'}),
                    patch.object(x,'verify_pair_manifest'),
                    patch('mvp.exp0034_appearance.load_manifest',return_value={}),
                    patch('mvp.exp0034_appearance.bind_inputs',return_value=inputs)]:
                    stack.enter_context(p)
                bound=x.input_contract()
            self.assertEqual(bound['checkpoint_receipt_sha256'],x.sha256(checkpoint))
            self.assertEqual(bound['model_files'],{'all_four':'verified'})
            self.assertEqual(bound['environment'],{'environment':'verified'})
            self.assertEqual(bound['quantization'],x.QUANTIZATION)
            self.assertNotIn('baseline',bound)

    def test_new_phase_settings_and_interpreter_do_not_change_2b(self):
        self.assertIn(x.PHASE, command.PHASES)
        self.assertEqual(command.settings_for_phase(x.PHASE)['max_new_tokens'], 192)
        self.assertEqual(command.settings_for_phase('appearance-compare')['max_new_tokens'], 384)
        self.assertEqual(command.interpreter_for_phase(x.PHASE), x.INTERPRETER)
        self.assertEqual(command.interpreter_for_phase('appearance-compare'), command.INTERPRETER)
        self.assertEqual(command.output_path(x.PHASE, 'a'*32),
                         command.ASSETS/'outputs/mvp0001/EXP-0038'/('a'*32))

    def test_8b_input_contract_bypasses_old_single_shard_and_roi(self):
        with patch.object(command, 'MODEL_DIR', Path('/missing/old/2b')), \
                patch('mvp.exp0038.input_contract', return_value={'eight': 'bound'}), \
                patch.object(command, 'load_configs', side_effect=AssertionError('old configs read')):
            self.assertEqual(command.input_contract(x.PHASE), {'eight':'bound'})

    def test_phase_source_binding_includes_reused_inventory_and_quantization(self):
        with patch.object(command, 'file_hash', return_value='hash'):
            files = command.sources({'phase':x.PHASE})
        for name in ('mvp/exp0038.py', 'mvp/exp0034_appearance.py',
                     'sceneguard/appearance_support.py', 'batch02_vlm/runner.py',
                     'orchestration/batch02_vlm_command.py', 'requirements-vlm-batch02-lock.txt'):
            self.assertIn(name, files)

    def test_8b_requires_full_frame_and_its_own_generation_settings(self):
        config = dict(phase=x.PHASE, view='full_frame', settings=x.SETTINGS)
        with patch.object(command, 'input_contract', return_value={'eight':True}), \
                patch.object(x, 'INTERPRETER', Path(__file__)):
            self.assertEqual(command.validate(config, {'eight':True}, command.RUNTIME),
                             (x.PHASE, 'full_frame'))
            for key, value in [('settings',command.SETTINGS),('view','fixed_roi')]:
                wrong = dict(config); wrong[key] = value
                with self.assertRaises(ValueError): command.validate(wrong, {'eight':True}, command.RUNTIME)

    def test_command_runs_only_isolated_python_with_inherited_lock(self):
        config = dict(phase=x.PHASE, view='full_frame', settings=x.SETTINGS)
        with patch.object(command, 'validate', return_value=(x.PHASE, 'full_frame')):
            argv = command.command(config, {}, command.RUNTIME, 'a'*32, 11)
        self.assertEqual(argv[:3], [str(x.INTERPRETER), '-I', str(command.ROOT/'mvp/runner.py')])
        self.assertEqual(argv[-2:], ['--lock-fd','11'])

    def test_frontend_preserves_old_default_and_passes_exact_job(self):
        queue = Mock();queue.run_once.return_value = {'status':'synthetic'}
        with patch('orchestration.queue.Queue', return_value=queue), patch('builtins.print'):
            cli.main(['--runtime',str(command.RUNTIME),'run-once','--job-id','selected'])
            queue.run_once.assert_called_once_with('selected')
            queue.reset_mock()
            cli.main(['--runtime',str(command.RUNTIME),'run-once'])
            queue.run_once.assert_called_once_with()


class Authorization(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.checkpoint = self.root/'checkpoint.json';self.checkpoint.write_text('receipt')
        self.authorization = self.root/'authorization.json'
        self.inputs = {'no_answers':'bound'}
        self.identity = dict(run_id='run_current', task_id='task_current', dispatch_id='ctx_current')
        self.auth = dict(self.identity, confirmed=True,inference_authorized=True,
            independent_review_passed=True, maximum_generate_calls=6, model_loads=1,
            warmup_generations=0, sources={'code':'frozen'}, checkpoint_receipt_sha256=x.sha256(self.checkpoint),
            code_sha='head',input_contract_sha256=digest(self.inputs))
        self.job = dict(self.identity, command='mvp-0001',job_id='job',
            config_json=json.dumps({'phase':x.PHASE}), input_json=json.dumps(self.inputs),
            input_hash=digest(self.inputs))
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        for p in [patch.object(x,'CHECKPOINT',self.checkpoint), patch.object(x,'AUTHORIZATION',self.authorization),
                  patch.object(x,'input_contract',return_value=self.inputs),
                  patch.object(command,'sources',return_value={'code':'frozen'}),
                  patch.object(x.subprocess,'check_output',return_value='head\n')]:
            self.stack.enter_context(p)
        self.write()

    def write(self): self.authorization.write_text(json.dumps(self.auth))

    def test_go_binds_current_identity_checkpoint_and_input(self):
        self.assertEqual(x.validate_authorization(),self.auth)
        self.assertEqual(x.validate_authorization(self.job),self.auth)
        self.job['dispatch_id']='other'
        with self.assertRaisesRegex(ValueError,'Task/Dispatch'): x.validate_authorization(self.job)

    def test_old_dispatch_missing_go_or_changed_binding_rejected(self):
        from mvp.exp0034_appearance import IDENTITY
        for key,value in [('dispatch_id',IDENTITY[2]),('task_id',IDENTITY[1]),
                          ('inference_authorized',False),('sources',{}),('model_loads',2),
                          ('warmup_generations',1),('checkpoint_receipt_sha256','bad'),
                          ('input_contract_sha256','bad'),('code_sha','old')]:
            saved = deepcopy(self.auth); self.auth[key]=value;self.write()
            with self.subTest(key=key),self.assertRaises(ValueError): x.validate_authorization()
            self.auth=saved

    def test_per_pair_lease_does_not_rehash_checkpoint_shards_environment(self):
        with patch.object(x,'input_contract',side_effect=AssertionError('expensive revalidation')):
            x.validate_authorization(self.job)

    def test_live_dispatch_and_single_attempt_required(self):
        live = dict(ok=True,result=dict(workers=[dict(taskId='task_current',dispatchId='ctx_current',
                    dispatchStatus='dispatched',projection=dict(liveness=dict(verdict='live')))]))
        previous = [('job','attempt',self.job['config_json'])]
        with patch.object(x,'validate_authorization'), \
                patch.object(x.subprocess,'check_output',return_value=json.dumps(live)):
            x.verify_live_dispatch(self.job,'attempt',previous)
            with self.assertRaisesRegex(ValueError,'one EXP-0038'):
                x.verify_live_dispatch(self.job,'attempt',previous+previous)
            live['result']['workers'][0]['projection']['liveness']['verdict']='unverifiable'
            with patch.object(x.subprocess,'check_output',return_value=json.dumps(live)):
                with self.assertRaisesRegex(ValueError,'must be live'):
                    x.verify_live_dispatch(self.job,'attempt',previous)

    def test_live_dispatch_lookup_follows_native_pagination(self):
        first=dict(ok=True,result=dict(workers=[],page=dict(hasMore=True,nextCursor='next')))
        second=dict(ok=True,result=dict(workers=[dict(taskId='task_current',dispatchId='ctx_current',
            dispatchStatus='dispatched',projection=dict(liveness=dict(verdict='live')))]))
        with patch.object(x,'validate_authorization'), \
                patch.object(x.subprocess,'check_output',side_effect=[json.dumps(first),json.dumps(second)]) as lookup:
            x.verify_live_dispatch(self.job,'attempt',[('job','attempt',self.job['config_json'])])
        self.assertEqual(lookup.call_args_list[1].args[0][-2:],['--cursor','next'])


class PairLoop(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.output=self.root/'outputs/mvp0001/EXP-0038'/'attempt'
        self.baseline=self.root/'historical.json'
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for p in [patch.object(x,'ROOT',self.root),
            patch('mvp.exp0034_appearance.load_manifest',return_value={'pairs':[{}]*6}),
            patch.object(x,'verify_pair_manifest'),
            patch('mvp.exp0034_appearance.bind_inputs',return_value={'bound':True}),
            patch('mvp.exp0034_appearance.verify_native_crops',return_value={'native_crops_checked':27})]:
            self.stack.enter_context(p)

    def test_load_once_six_pair_loop_before_any_baseline_read(self):
        events=[]
        def generate(*_):
            events.append('six sequential generations')
            self.baseline.write_text(json.dumps({'partial':False,'completed':rows()}))
            return rows()
        def load(*_):
            self.assertFalse(self.baseline.exists());events.append('load')
            return object(),dict(loading_and_quantization_seconds=1,checkpoint_validation_seconds=2)
        with patch.object(x,'load_analyzer',side_effect=load) as loader, \
                patch('mvp.exp0034_appearance.run_appearance',side_effect=generate) as loop:
            result=x.run_six_pairs(Path('model'),{},self.output,{},self.baseline)
        self.assertEqual(events,['load','six sequential generations'])
        loader.assert_called_once(); loop.assert_called_once()
        self.assertEqual(result['statistics']['generation_calls'],6)
        self.assertEqual(result['checkpoint_validation_seconds'],2)
        self.assertTrue((self.output/'baseline_comparison.json').is_file())

    def test_partial_failure_preserved_without_baseline_read_or_retry(self):
        def generate(*_):
            (self.output/'appearance_results.json').write_text('{"partial":true,"completed":[]}')
            raise RuntimeError('partial generation failure')
        with patch.object(x,'load_analyzer',return_value=(object(),{})) as loader, \
                patch('mvp.exp0034_appearance.run_appearance',side_effect=generate) as loop:
            with self.assertRaisesRegex(RuntimeError,'partial generation'):
                x.run_six_pairs(Path('model'),{},self.output,{},self.baseline)
        loader.assert_called_once();loop.assert_called_once()
        failure=json.loads((self.output/'exp0038_failure.json').read_text())
        self.assertEqual(failure['stage'],'six_pairs')
        self.assertFalse(failure['automatic_retry'])
        self.assertTrue((self.output/'appearance_results.json').is_file())
        self.assertFalse(self.baseline.exists())

    def test_loader_failure_records_correct_stage_without_pair_call(self):
        with patch.object(x,'load_analyzer',side_effect=RuntimeError('load failed')), \
                patch('mvp.exp0034_appearance.run_appearance') as loop:
            with self.assertRaisesRegex(RuntimeError,'load failed'):
                x.run_six_pairs(Path('model'),{},self.output,{},self.baseline)
        loop.assert_not_called()
        self.assertEqual(json.loads((self.output/'exp0038_failure.json').read_text())['stage'],'model_loading')

    def test_native_validation_failure_prevents_model_load(self):
        with patch('mvp.exp0034_appearance.verify_native_crops',return_value={'native_crops_checked':26}), \
                patch.object(x,'load_analyzer') as loader:
            with self.assertRaisesRegex(ValueError,'Incomplete original'):
                x.run_six_pairs(Path('model'),{},self.output,{},self.baseline)
        loader.assert_not_called()


class Runner(unittest.TestCase):
    def test_new_phase_never_constructs_historical_2b_analyzer(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'attempt'
            config=dict(phase=x.PHASE,view='full_frame',settings=x.SETTINGS)
            inputs={'new':'bound'}
            job=dict(input_json=json.dumps(inputs),input_hash=digest(inputs),config_hash=digest(config),
                source_hash='source',job_id='job',code_sha='head',run_id='run',task_id='task',dispatch_id='ctx')
            with ExitStack() as stack:
                for p in [patch.object(runner,'verify_lease',return_value=job),patch.object(runner,'source_hash',return_value='source'),
                    patch.object(runner,'validate'),patch.object(runner,'load_configs',return_value=({}, {}, {})),
                    patch.object(runner,'output_path',return_value=folder),patch.object(command,'sources',return_value={}),
                    patch('vlm_batch.run.MemoryMonitor',return_value=SimpleNamespace(
                        start=lambda:None,stop=lambda:None,samples=[],errors=[])),
                    patch.object(x,'CHECKPOINT',Path(tmp)/'receipt.json'),
                    patch.object(x,'run_six_pairs',return_value={'completed':True}),
                    patch('mvp.method.QwenAnalyzer',side_effect=AssertionError('old model constructed'))]:
                    stack.enter_context(p)
                (Path(tmp)/'receipt.json').write_text('{}')
                runner.run(x.PHASE,'full_frame','a'*32,10)
            summary=json.loads((folder/'summary.json').read_text())
            self.assertEqual(summary['status'],'succeeded')
            self.assertEqual(summary['config'],config)
            self.assertNotIn('pipeline_settings',summary)
            self.assertEqual(summary['effective_settings']['max_new_tokens'],192)
            self.assertEqual(summary['effective_settings']['minimum_gpu_free_mib'],8192)


if __name__ == '__main__':unittest.main()
