"""CPU checks for bounded appearance comparisons and incomplete graph coverage."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from mvp import exp0034_appearance as app
from sceneguard.appearance_support import parse_comparison,prepare_images,IMAGE_BUDGET,link_proposals

GOOD='{"upper":"match","lower":"unavailable","bag":"unavailable","decision":"compatible"}'
DIFFERENT='{"upper":"different","lower":"unavailable","bag":"unavailable","decision":"different"}'
UNKNOWN='{"upper":"unavailable","lower":"unavailable","bag":"unavailable","decision":"unknown"}'


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.graph=[dict(pair_id='ab',before='a',after='b'),dict(pair_id='ac',before='a',after='c')]

    def test_untested_competitor_prevents_mutual_uniqueness(self):
        rows=app.covered_proposals(self.graph,{'ab':GOOD})
        self.assertEqual(link_proposals(self.graph,{'ab':GOOD})[0]['link_status'],'unresolved_competitor_coverage')
        self.assertEqual(rows[0]['link_status'],'unresolved_competitor_coverage')
        self.assertEqual(rows[0]['untested_competitors'],['ac'])
        self.assertFalse(rows[0]['uniqueness_assessed'])

    def test_unknown_or_invalid_competitor_remains_unresolved(self):
        for raw in (UNKNOWN,'not JSON',GOOD.replace('compatible','other')):
            rows=app.covered_proposals(self.graph,{'ab':GOOD,'ac':raw})
            self.assertEqual(link_proposals(self.graph,{'ab':GOOD,'ac':raw})[0]['link_status'],'unresolved_competitor_coverage')
            self.assertEqual(rows[0]['link_status'],'unresolved_competitor_coverage')
            self.assertEqual(rows[0]['unknown_competitors'],['ac'])

    def test_only_explicit_difference_eliminates_competitor(self):
        rows=app.covered_proposals(self.graph,{'ab':GOOD,'ac':DIFFERENT})
        self.assertEqual(rows[0]['link_status'],'review_link_proposed')
        self.assertTrue(rows[0]['uniqueness_assessed'])
        self.assertFalse(rows[0]['identity_verified'])
        self.assertFalse(rows[0]['raw_ids_merged'])
        self.assertIsNone(rows[0]['intrusion_verdict'])

    def test_multiple_compatible_edges_are_ambiguous(self):
        rows=app.covered_proposals(self.graph,{'ab':GOOD,'ac':GOOD})
        self.assertTrue(all(r['link_status']=='ambiguous_not_linked' for r in rows))

    def test_untested_isolated_edge_does_not_claim_assessed_coverage(self):
        row=app.covered_proposals(self.graph[:1],{})[0]
        self.assertFalse(row['candidate_coverage_complete'])
        self.assertFalse(row['comparison_tested'])
        self.assertFalse(row['uniqueness_assessed'])


class ManifestTests(unittest.TestCase):
    def manifest(self):
        im=dict(path='runtime/EXP-0034/c.npy',sha256='a'*64,rgb_sha256='b'*64,
                source_id='E01_030',raw_id=1,cache_index=0,decoded_index=2520,
                native_pts=1290240,time_base='1/15360',pts=84.,
                bbox_xyxy=[.25,.25,.5,.5],crop_bounds_xyxy=[480,270,960,540],source_size=[1920,1080])
        graph=dict(pair_id='ab',before='E01_030:s0001',after='E01_030:s0002')
        return dict(schema_version=1,experiment_id='EXP-0034',run_id=app.IDENTITY[0],
            sources=[dict(source_id='E01_030',path='data/TS_침입/E01_030.mp4',
                source_sha256=app.SOURCE_ROWS['E01_030'][1],frames_path=app.SOURCE_ROWS['E01_030'][0],frames_sha256='c'*64)],
            pairs=[dict(graph,before_images=[im],after_images=[dict(im)])],candidate_pairs=[graph])

    def load(self,m):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'manifest.json'
            path.write_text(json.dumps(m))
            with patch.object(app,'MANIFEST',path):
                return app.load_manifest()

    def test_strict_provenance_schema_accepts_no_labels(self):
        m=self.manifest()
        self.assertEqual(self.load(m),m)
        for key in ('human_label','angle','expected_behavior'):
            m=self.manifest()
            m['pairs'][0][key]='forbidden'
            with self.assertRaises(ValueError):self.load(m)

    def test_fixed_generate_budget_and_duplicate_pairs(self):
        for n in (0,7):
            m=self.manifest();m['pairs']=m['pairs']*n
            with self.assertRaises(ValueError):self.load(m)
        m=self.manifest();m['pairs']*=2
        with self.assertRaises(ValueError):self.load(m)

    def test_wrong_native_timing_bounds_and_cross_camera_rejected(self):
        for key,value in [('pts',84.1),('crop_bounds_xyxy',[480,270,961,540]),('source_id','E01_007')]:
            m=self.manifest();m['pairs'][0]['after_images'][0][key]=value
            with self.assertRaises(ValueError):self.load(m)

    def test_crop_bytes_shape_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'runtime/EXP-0034').mkdir(parents=True)
            im=self.manifest()['pairs'][0]['before_images'][0]
            arr=np.zeros((270,480,3),dtype=np.uint8)
            path=root/im['path'];np.save(path,arr,allow_pickle=False)
            im['sha256']=app.file_hash(path);im['rgb_sha256']=hashlib.sha256(arr.tobytes()).hexdigest()
            with patch.object(app,'ROOT',root):
                self.assertTrue(np.array_equal(app.load_crop(im),arr))
                arr[0,0]=1;np.save(path,arr,allow_pickle=False)
                with self.assertRaises(ValueError):app.load_crop(im)


class PipelineTests(unittest.TestCase):
    def test_one_call_per_pair_and_partial_failure_kept(self):
        m=ManifestTests().manifest()
        second=dict(m['pairs'][0],pair_id='cd',before='c',after='d')
        m['pairs'].append(second);m['candidate_pairs'].append({k:second[k] for k in ('pair_id','before','after')})
        class Analyzer:
            last_processor_images=None
            last_expanded_prompt=None
            last_input_metadata=None
            last_generated_token_ids=[]
        a=Analyzer()
        calls=[]
        def compare(*args):
            calls.append(1)
            a.last_processor_images=[np.zeros((32,32,3),dtype=np.uint8)]
            a.last_expanded_prompt='anonymous image comparison'
            a.last_input_metadata={'synthetic':True}
            a.last_generated_token_ids=[[1,2]]
            a.appearance_diagnostics()
            if len(calls)==2:raise RuntimeError('generation failed')
            return {'raw_response':GOOD,'parsed':parse_comparison(GOOD)}
        with tempfile.TemporaryDirectory() as tmp,patch.object(app,'load_manifest',return_value=m),\
                patch.object(app,'load_crop',return_value=np.zeros((32,32,3),dtype=np.uint8)),\
                patch('sceneguard.appearance_support.compare_images',side_effect=compare):
            root=Path(tmp)
            with self.assertRaisesRegex(RuntimeError,'generation failed'):
                app.run_appearance(a,root,{'synthetic':True})
            self.assertEqual(len(calls),2)
            self.assertTrue((root/'p000002/failure.json').is_file())
            self.assertTrue((root/'p000002/generated_token_ids.npy').is_file())
            self.assertTrue(json.loads((root/'appearance_results.json').read_text())['partial'])


class AuthorizationTests(unittest.TestCase):
    def test_missing_or_wrong_go_freeze_fails_before_model_construction(self):
        inputs={'synthetic':'input'}
        sources={'synthetic.py':'frozen'}
        authorization=dict(zip(('run_id','task_id','dispatch_id'),app.IDENTITY))
        authorization.update(confirmed=True,inference_authorized=True,independent_review_passed=True,
            maximum_generate_calls=1,sources=sources,input_contract_sha256=app.digest(inputs),code_sha='head')
        with tempfile.TemporaryDirectory() as tmp,patch.object(app,'load_manifest',return_value={'pairs':[{}]}),\
                patch('orchestration.mvp_command.sources',return_value=sources),\
                patch('orchestration.mvp_command.input_contract',return_value=inputs),\
                patch.object(app.subprocess,'check_output',return_value='head\n'):
            path=Path(tmp)/'authorization.json'
            with patch.object(app,'AUTHORIZATION',path):
                with self.assertRaises(FileNotFoundError):app.validate_authorization()
                path.write_text(json.dumps(authorization))
                self.assertEqual(app.validate_authorization(),authorization)
                for key,value in [('dispatch_id','old'),('confirmed',False),('independent_review_passed',False),
                                  ('maximum_generate_calls',2),('sources',{}),('input_contract_sha256','other'),
                                  ('code_sha','other')]:
                    wrong=dict(authorization);wrong[key]=value
                    path.write_text(json.dumps(wrong))
                    with self.assertRaises(ValueError):app.validate_authorization()


class PinnedProcessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from transformers import AutoProcessor
        cls.processor=AutoProcessor.from_pretrained(app.ROOT/'weights/Qwen3-VL-2B-Instruct',local_files_only=True)

    def test_actual_multi_image_kwargs_order_budget_and_capture(self):
        arrays=[np.full((160,80,3),i*30,dtype=np.uint8) for i in range(3)]
        arrays += [np.full((192,96,3),i*30,dtype=np.uint8) for i in range(3,6)]
        inputs,metadata,actual,text=prepare_images(self.processor,arrays[:3],arrays[3:])
        self.assertEqual(len(actual),6)
        self.assertEqual(metadata['image_budget'],IMAGE_BUDGET)
        self.assertEqual(metadata['frame_groups'],[3,3])
        self.assertTrue(all(int(im[0,0,0])==i*30 for i,im in enumerate(actual)))
        self.assertEqual(len(inputs['image_grid_thw']),6)
        for im in actual:
            self.assertGreaterEqual(im.shape[0]*im.shape[1],IMAGE_BUDGET['min_pixels'])
            self.assertLessEqual(im.shape[0]*im.shape[1],IMAGE_BUDGET['max_pixels'])
        self.assertIn('upper',text)
        self.assertNotIn('E01_',text)
        self.assertEqual(metadata['static_image_temporal_patch_repeats'],1)
        self.assertFalse(metadata['extra_sampling'])

    def test_invalid_crop_or_group_count_rejected(self):
        good=np.zeros((32,32,3),dtype=np.uint8)
        for before in ([],[good]*4,[np.zeros((12,32,3),dtype=np.uint8)]):
            with self.assertRaises(ValueError):prepare_images(self.processor,before,[good])

    def test_two_images_keep_independent_groups_without_video_prompt(self):
        a=np.full((96,64,3),30,dtype=np.uint8)
        b=np.full((96,64,3),90,dtype=np.uint8)
        inputs,metadata,actual,text=prepare_images(self.processor,[a],[b])
        self.assertEqual(metadata['frame_groups'],[1,1])
        self.assertEqual(len(inputs['image_grid_thw']),2)
        self.assertEqual([int(im[0,0,0]) for im in actual],[30,90])
        self.assertNotIn('<|video_pad|>',text)


if __name__=='__main__':unittest.main()
