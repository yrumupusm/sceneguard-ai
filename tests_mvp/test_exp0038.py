"""CPU-only EXP-0038 contracts; no checkpoint, Torch, GPU, or real CCTV used."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mvp import exp0038 as x


def rows():
    return [dict(pair_id=f'p{i}', images=n, frame_groups=[3, n-3],
        timing=dict(generation_seconds=1+i*.1, prepare_seconds=.1),
        parsed=dict(valid=True, comparison=dict(upper='match', lower='unavailable',
            bag='match', decision='compatible')),
        input_metadata=dict(processor_rgb_sha256=['a']*n,
                            image_grid_thw=[[1, 2, 3]]*n,
                            image_budget=dict(min_pixels=65536,max_pixels=262144)),
        output_tokens=22, hit_token_limit=False,
        gpu_memory=dict(peak_allocated_bytes=100+i,peak_reserved_bytes=200+i))
        for i,n in enumerate(x.PAIR_IMAGE_COUNTS)]


class ExperimentContracts(unittest.TestCase):
    def test_model_is_fixed_8b_instruct(self):
        self.assertEqual(x.MODEL_ID,'Qwen/Qwen3-VL-8B-Instruct')
        self.assertEqual(len(x.REVISION),40)

    def test_phase_cannot_reuse_old_2b_attempt(self):
        with self.assertRaises(ValueError):
            x.require_phase(dict(command='mvp-0001',config_json='{"phase":"appearance-compare"}'))

    def test_phase_is_new_canonical_mvp(self):
        x.require_phase(dict(command='mvp-0001',config_json='{"phase":"appearance-8b"}'))
        with self.assertRaises(ValueError):
            x.require_phase(dict(command='other',config_json='{"phase":"appearance-8b"}'))

    def test_nf4_without_cpu_auto_offload(self):
        kw=x.load_kwargs(SimpleNamespace(bfloat16='BF16',uint8='UINT8'),lambda **v:v)
        self.assertEqual(kw['device_map'],{'':'cuda:0'})
        self.assertTrue(kw['local_files_only'])
        self.assertFalse(kw['trust_remote_code'])
        q=kw['quantization_config']
        self.assertTrue(q['load_in_4bit'])
        self.assertTrue(q['bnb_4bit_use_double_quant'])
        self.assertEqual(q['bnb_4bit_quant_type'],'nf4')
        self.assertEqual(q['llm_int8_skip_modules'],['model.visual','lm_head'])
        self.assertFalse(q['llm_int8_enable_fp32_cpu_offload'])

    def test_loader_checks_authority_before_gpu_import(self):
        fake=SimpleNamespace(verify_environment_lease=lambda:dict(command='wrong',config_json='{}'),
                             check_resources=lambda _:None)
        with patch.dict('sys.modules',{'mvp.runner':fake}):
            with self.assertRaisesRegex(ValueError,'canonical'):
                x.load_analyzer(Path('absent'),{})

    def test_six_unique_pairs_required(self):
        with self.assertRaises(ValueError): x.summarize_rows(rows()[:5])
        r=rows();r[-1]['pair_id']=r[0]['pair_id']
        with self.assertRaises(ValueError):x.summarize_rows(r)

    def test_image_count_not_silently_reduced(self):
        r=rows();r[0]['images']=3
        with self.assertRaises(ValueError):x.summarize_rows(r)

    def test_output_statistics_are_not_accuracy(self):
        s=x.summarize_rows(rows())
        self.assertEqual(s['pairs'],6)
        self.assertEqual(s['image_slots'],27)
        self.assertEqual(s['unavailable_parts_in_valid_rows'],6)
        self.assertIsNone(s['semantic_accuracy'])
        self.assertFalse(s['automatic_adoption'])

    def test_invalid_output_is_not_model_abstention(self):
        r=rows();r[0]['parsed']=dict(valid=False,comparison=dict(decision='unknown',
                                  upper='unavailable',lower='unavailable',bag='unavailable'))
        s=x.summarize_rows(r)
        self.assertEqual(s['invalid_response_rows'],1)
        self.assertEqual(s['explicit_valid_unknown'],0)
        self.assertEqual(s['unavailable_parts_in_valid_rows'],5)

    def test_explicit_unknown_is_separate(self):
        r=rows();r[0]['parsed']['comparison']['decision']='unknown'
        self.assertEqual(x.summarize_rows(r)['explicit_valid_unknown'],1)

    def test_nonfinite_or_bool_timing_rejected(self):
        for value in (float('nan'),float('inf'),-1,True):
            r=rows();r[0]['timing']['generation_seconds']=value
            with self.subTest(value=value),self.assertRaises(ValueError):x.summarize_rows(r)

    def test_first_inference_separate_from_remaining(self):
        s=x.summarize_rows(rows())
        self.assertAlmostEqual(s['first_pair_generation_seconds'],1)
        self.assertAlmostEqual(s['remaining_pairs_generation_seconds_median'],1.3)
        self.assertAlmostEqual(s['generation_seconds_sum'],7.5)

    def test_posthoc_comparison_does_not_mutate_or_score(self):
        a=rows();b=rows();saved=deepcopy((a,b))
        report=x.compare_saved_rows(a,b)
        self.assertEqual((a,b),saved)
        self.assertTrue(all(r['processor_image_parity'] for r in report))
        self.assertTrue(all(r['semantic_improvement'] is None for r in report))

    def test_processor_difference_reported_not_hidden(self):
        b=rows();b[0]['input_metadata']['processor_rgb_sha256'][0]='changed'
        self.assertFalse(x.compare_saved_rows(rows(),b)[0]['processor_image_parity'])

    def test_missing_parity_data_is_not_exact_match(self):
        b=rows();del b[0]['input_metadata']['image_grid_thw']
        self.assertFalse(x.compare_saved_rows(rows(),b)[0]['processor_image_parity'])

    def test_different_pairs_or_groups_rejected(self):
        b=rows();b[0]['pair_id']='new'
        with self.assertRaises(ValueError):x.compare_saved_rows(rows(),b)
        b=rows();b[0]['frame_groups']=[2,3]
        with self.assertRaises(ValueError):x.compare_saved_rows(rows(),b)

    def test_exact_manifest_sha_and_slot_order(self):
        m=dict(pairs=[dict(pair_id=str(i),before_images=[{}]*3,after_images=[{}]*(n-3))
                     for i,n in enumerate(x.PAIR_IMAGE_COUNTS)])
        with patch.object(x,'sha256',return_value=x.BASELINE_MANIFEST_SHA256):
            x.verify_pair_manifest(m,Path('fixture'))
            m['pairs'][0]['before_images'].pop()
            with self.assertRaises(ValueError):x.verify_pair_manifest(m,Path('fixture'))
        with patch.object(x,'sha256',return_value='0'*64):
            with self.assertRaises(ValueError):x.verify_pair_manifest(m,Path('fixture'))


class CheckpointContracts(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        config=dict(model_type='qwen3_vl',architectures=['Qwen3VLForConditionalGeneration'],
                    text_config=dict(hidden_size=4096,num_hidden_layers=36),tie_word_embeddings=False)
        index=dict(weight_map={f'p{i}':f'model-{i:05d}-of-00004.safetensors' for i in range(1,5)})
        files={}
        for name in x.REQUIRED_FILES:
            value=json.dumps(config if name=='config.json' else index if name=='model.safetensors.index.json' else {}).encode()
            (self.root/name).write_bytes(value)
            files[name]=dict(bytes=len(value),sha256=hashlib.sha256(value).hexdigest())
        self.receipt=dict(model_id=x.MODEL_ID,revision=x.REVISION,files=files)

    def test_full_fixture_checkpoint(self):
        self.assertEqual(len(x.verify_checkpoint(self.root,self.receipt)),len(x.REQUIRED_FILES))

    def test_wrong_revision(self):
        self.receipt['revision']='main'
        with self.assertRaises(ValueError):x.verify_checkpoint(self.root,self.receipt)

    def test_missing_shard(self):
        self.receipt['files'].pop('model-00001-of-00004.safetensors')
        with self.assertRaises(ValueError):x.verify_checkpoint(self.root,self.receipt)

    def test_tampered_bytes(self):
        (self.root/'config.json').write_text('{}')
        with self.assertRaises(ValueError):x.verify_checkpoint(self.root,self.receipt)

    def test_path_traversal(self):
        self.receipt['files']['../outside']={}
        with self.assertRaises(ValueError):x.verify_checkpoint(self.root,self.receipt)

    def test_symlink_file(self):
        path=self.root/'generation_config.json';path.unlink()
        path.symlink_to(self.root/'config.json')
        with self.assertRaises(ValueError):x.verify_checkpoint(self.root,self.receipt)

    def test_wrong_architecture_with_valid_hash(self):
        p=self.root/'config.json';c=json.loads(p.read_text());c['text_config']['hidden_size']=2048
        p.write_text(json.dumps(c));self.receipt['files'][p.name]=dict(bytes=p.stat().st_size,sha256=x.sha256(p))
        with self.assertRaisesRegex(ValueError,'architecture'):x.verify_checkpoint(self.root,self.receipt)

if __name__=='__main__':unittest.main()
