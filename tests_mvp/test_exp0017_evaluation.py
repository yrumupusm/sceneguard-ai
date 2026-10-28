"""Fail-closed evaluation contract tests: synthetic metadata, never GPU/media."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import evaluate_exp0017 as ev
from vlm_batch.common import parse_pair


def response(actions=('passage_or_waiting',), completion='not_confirmed', fence=False):
    parsed = dict(observed_actions=list(actions), visible_evidence='synthetic claim',
                  crossing_completion=completion, uncertainties='')
    raw = json.dumps(parsed)
    if fence:
        raw = '```json\n'+raw+'\n```'
    return dict(raw_response=raw,parsed=parsed,parse=parse_pair(raw),
                timing={'prepare_seconds':0.25,'generation_seconds':1.5},output_tokens=20,
                gpu_memory={'peak_allocated_bytes':100,'peak_reserved_bytes':200},hit_token_limit=False)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(ev.encoded(value))


def rgb_file(path):
    # The NPY specification, constructed without numpy or real image data.
    header = repr({'descr':'|u1','fortran_order':False,'shape':(10,2,2,3)})+'\n'
    path.write_bytes(b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header.encode()+bytes(120))


def info(source):
    return {'source_pts':source['pts_seconds'],'native_pts':source['native_pts'],
            'time_base':source['time_base'],'roi':source['roi'],'source_size':source['source_size'],
            'relative_indices':source['relative_indices'],'source_fps':source['fps'],
            'window_start':source['window_start'],'window_end':source['window_end'],
            'observed_frames':10,'processor_frames':10,'extra_sampling':False,'temporal_padding_frames':0,
            'processor_timestamp_coordinates':[(p-source['window_start'])*source['fps'] for p in source['pts_seconds']],
            'processor_size':{'shortest_edge':16384,'longest_edge':3584000},'resized_shape':[10,3,2,2],
            'input_tokens':100,'visual_tokens':10}


class Fixture:
    """A complete four-job receipt with public labels and fabricated measurements."""
    def __init__(self,root):
        self.root=root
        for rel in ev.PINS:
            write(root/rel,json.loads((ev.ROOT/rel).read_bytes()))
        for filename in ('vlm_batch01_prompt.txt','mvp_exp0016_prompt.txt'):
            (root/'configs'/filename).write_bytes((ev.ROOT/'configs'/filename).read_bytes())
        self.paths={key:root/'outputs'/key for key in ev.GROUPS}
        self.baseline={key:root/'outputs'/('baseline_'+key) for key in ('B','C')}
        self.settings=json.loads((root/'configs/mvp0001_settings.json').read_bytes())
        self.manifest=json.loads((root/'configs/mvp_exp0016_independent_manifest.json').read_bytes())
        parent=json.loads((root/'records/EXP-0015/window_reviews.json').read_bytes())
        for ordinal,(group,(phase,view,_)) in enumerate(ev.GROUPS.items(),1):
            binding={'model_files':{'model.safetensors':ev.MODEL_SHA,'video_preprocessor_config.json':'d'*64},
                     'videos':{sid:s['sha256'] for sid,s in self.manifest['sources'].items()},
                     'prompt_hashes':{p:ev.PROMPTS['original' if p.endswith('original') else 'revised'] for p in ('independent-original','independent-revised')}}
            if group.startswith('q_'):
                binding.update(prompt_sha256=ev.PROMPTS['revised'], videos={r['source_id']:r['source_sha256'] for r in parent})
            config={'phase':phase,'view':view,'settings':self.settings['generation']}
            summary={'status':'succeeded','attempt_id':str(ordinal)*32,'config':config,'pipeline_settings':self.settings,
                     'config_hash':ev.sha(ev.canonical(config)),'input_hash':ev.sha(ev.canonical(binding)),
                     'bindings':{'inputs':binding,'code_files':{}},'packages':{'fixture':'1'},
                     'torch_version':'fixture','cuda_version':'fixture','model_parameter_devices':['cuda:0'],
                     'results':[r['window_id'] for r in self.manifest['windows']]}
            write(self.paths[group]/'summary.json',summary)
        for method,view in [('B','full_frame'),('C','fixed_roi')]:
            folder=self.baseline[method]
            loading={'config':{'settings':self.settings['generation']}}
            write(folder/'loading.json',loading)
            for qid,cid,sid,wid,start,end in ev.Q:
                r=next(r for r in parent if r['method']==method and r['case_id']==cid)
                source={'pts_seconds':r['actual_sampled_pts_seconds'],'native_pts':r['actual_native_pts'],
                        'time_base':r['actual_time_base'],'source_sha256':r['source_sha256'],
                        'rgb_sha256':r['decoded_source_rgb_sha256'],'window_start':start,'window_end':end,
                        'roi':[0,0,1,1] if view=='full_frame' else [0.6,0,0.9,0.6],
                        'relative_indices':list(range(0,150,15)),'fps':30,'source_size':[1920,1080]}
                result=response(r['observed_output']['actions'],r['observed_output']['completion_claim'])
                result['input_metadata']=info(source)
                old=folder/sid/'windows'/wid
                write(old/'input.json',source); write(old/'result.json',result)
                write(folder/sid/'run.json',{'source':{'sha256':r['source_sha256']},'camera':{'roi':source['roi']}})
                for key,path in [('input_file_sha256',old/'input.json'),('result_file_sha256',old/'result.json'),
                                 ('loading_metadata_sha256',folder/'loading.json'),('source_run_metadata_sha256',folder/sid/'run.json')]:
                    r['provenance'][key]=ev.sha(path.read_bytes())
                target=self.paths['q_'+view]/sid/'windows'/wid
                self.window(target,source,result,wid,'revised')
            for sid in ('E01_007','E01_030'):
                write(self.paths['q_'+view]/sid/'summary.json',
                      {'completed_windows':[q[3] for q in ev.Q if q[2]==sid], 'decode':{'eof_reached':True}})
        write(root/'records/EXP-0015/window_reviews.json',parent)
        self.pins={rel:ev.sha((root/rel).read_bytes()) for rel in ev.PINS}
        for group in ('v_original','v_revised'):
            kind='original' if group=='v_original' else 'revised'
            for frozen in self.manifest['windows']:
                sid,wid=frozen['source_id'],frozen['window_id']
                source={**frozen['timing'],'source_sha256':self.manifest['sources'][sid]['sha256'],
                        'frame_sha256':frozen['frame_sha256'],'roi':[0,0,1,1],'prompt_sha256':ev.PROMPTS[kind]}
                result=response();result['input_metadata']=info(source)
                self.window(self.paths[group]/'windows'/wid,source,result,wid,kind)
            for sid in self.manifest['sources']:
                write(self.paths[group]/(sid+'_summary.json'),{'completed_windows':[r['window_id'] for r in self.manifest['windows'] if r['source_id']==sid], 'decode':{'eof_reached':True}})

    def window(self,target,source,result,wid,kind):
        write(target/'input.json',source); write(target/'result.json',result)
        prompt=(self.root/'configs'/('vlm_batch01_prompt.txt' if kind=='original' else 'mvp_exp0016_prompt.txt')).read_text().strip()
        (target/'expanded_prompt.txt').write_text('template\nClip ID: '+wid+'\n'+prompt+'\nassistant')
        rgb_file(target/'processor_rgb.npy')

    def evaluate(self):
        with patch.dict(ev.PINS,self.pins,clear=True):
            return ev.evaluate(self.root,self.paths,baseline_paths=self.baseline)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.f=Fixture(Path(self.temp.name))

    def mutate(self,group,relative,change):
        path=self.f.paths[group]/relative
        data=json.loads(path.read_bytes());change(data);write(path,data)

    def test_complete_fixture_reproducible_and_sanitized(self):
        a,reader=self.f.evaluate();b,_=self.f.evaluate()
        self.assertEqual(ev.encoded(a),ev.encoded(b));self.assertEqual(len(a['q']),12)
        self.assertEqual(len(a['v']),4);self.assertEqual(a['v_grouping']['source_group_count'],2)
        self.assertEqual(a['v_grouping']['groups'],{'E01_004':['v01','v02'],'E01_021':['v03','v04']})
        for row in a['v']:
            if row['review_clip_id'] in ('v01','v03'):
                self.assertEqual(row['completion_reference'],'not_assessed')
                self.assertEqual(row['completion_evaluation'],'not_assessed')
        v3=next(r for r in a['v'] if r['review_clip_id']=='v03')
        self.assertEqual(v3['location_reference'],'gap beside gate, not through gate')
        self.assertEqual(v3['boundary_relation_reference'],'ambiguous')
        text=ev.encoded(a).decode()
        for forbidden in ('raw_response','generated_token_ids','synthetic claim',str(self.f.root)):
            self.assertNotIn(forbidden,text)
        self.assertTrue(all(x is None for x in a['performance_metrics'].values()))
        reader.verify()

    def test_same_named_window_changed_frame_is_rejected(self):
        self.mutate('v_revised','windows/w000001/input.json',lambda d:d['frame_sha256'].__setitem__(0,'0'*64))
        with self.assertRaisesRegex(ValueError,'RGB'):self.f.evaluate()

    def test_q_changed_source_or_native_pts_rejected(self):
        for field,value in [('source_sha256','0'*64),('native_pts',[0]*10)]:
            with self.subTest(field=field):
                path=self.f.paths['q_full_frame']/'E01_007/windows/w000020/input.json'
                original=path.read_bytes()
                self.mutate('q_full_frame','E01_007/windows/w000020/input.json',lambda d:d.__setitem__(field,value))
                with self.assertRaisesRegex(ValueError,'input mismatch'):self.f.evaluate()
                path.write_bytes(original)

    def test_prompt_hash_and_expanded_nonprompt_change_rejected(self):
        p=self.f.paths['v_revised']/'windows/w000001/expanded_prompt.txt'
        p.write_text(p.read_text()+' unexpected message')
        with self.assertRaisesRegex(ValueError,'nonprompt difference'):self.f.evaluate()

    def test_generation_change_rejected_even_with_rehashed_config(self):
        def change(d):
            d['config']['settings']['max_new_tokens']=385
            d['config_hash']=ev.sha(ev.canonical(d['config']))
        self.mutate('v_revised','summary.json',change)
        with self.assertRaisesRegex(ValueError,'config mismatch'):self.f.evaluate()

    def test_wrong_prompt_binding_rejected_even_with_rehashed_input(self):
        def change(d):
            d['bindings']['inputs']['prompt_hashes']['independent-revised']=ev.PROMPTS['original']
            d['input_hash']=ev.sha(ev.canonical(d['bindings']['inputs']))
        self.mutate('v_revised','summary.json',change)
        with self.assertRaisesRegex(ValueError,'prompt binding'):self.f.evaluate()

    def test_processor_pixels_differ_despite_same_metadata_rejected(self):
        p=self.f.paths['v_revised']/'windows/w000001/processor_rgb.npy'
        raw=p.read_bytes();p.write_bytes(raw[:-1]+b'\x01')
        with self.assertRaisesRegex(ValueError,'processor RGB differs'):self.f.evaluate()

    def test_missing_output_and_incomplete_group_fail_closed(self):
        p=self.f.paths['q_full_frame']/'E01_007/windows/w000001/result.json'
        p.unlink()
        with self.assertRaises(FileNotFoundError):self.f.evaluate()

    def test_unfinished_source_not_successful_despite_job_receipt(self):
        self.mutate('q_full_frame','E01_007/summary.json',lambda d:d.__setitem__('completed_windows',['w000001']))
        with self.assertRaisesRegex(ValueError,'coverage'):self.f.evaluate()

    def test_bad_stored_parse_rejected(self):
        self.mutate('q_full_frame','E01_007/windows/w000001/result.json',lambda d:d.__setitem__('parsed',None))
        with self.assertRaisesRegex(ValueError,'stored parser'):self.f.evaluate()

    def test_read_set_mutation_detected(self):
        _,reader=self.f.evaluate()
        p=self.f.paths['v_original']/'summary.json';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'input changed'):reader.verify()

    def test_parse_failure_stays_in_denominator_without_negative_label(self):
        def change(d):
            d.update(raw_response='broken',parsed=None,parse=parse_pair('broken'))
        self.mutate('v_revised','windows/w000002/result.json',change)
        result,_=self.f.evaluate()
        row=next(r for r in result['v'] if r['review_clip_id']=='v02')
        self.assertEqual(row['new']['status'],'parse_failed')
        table=next(t for t in result['output_status_tables'] if t['group']=='v_full_frame' and t['condition']=='new')
        self.assertEqual(table['denominator'],4);self.assertEqual(table['parse_failed'],1)
        self.assertEqual(table['other'],3)

    def test_completion_claim_does_not_create_assessed_completion(self):
        def change(d):
            d.update(response(['indeterminate'],completion='observed'))
        self.mutate('v_revised','windows/w000001/result.json',change)
        result,_=self.f.evaluate()
        row=next(r for r in result['v'] if r['review_clip_id']=='v01')
        self.assertEqual(row['new']['status'],'indeterminate')
        self.assertEqual(row['new']['completion_claim'],'observed')
        self.assertEqual(row['completion_evaluation'],'not_assessed')
        self.assertEqual(row['completion_reference'],'not_assessed')

    def test_manifest_listing_order_is_not_decode_order(self):
        self.mutate('v_original','summary.json',lambda d:d.__setitem__('results',list(reversed(d['results']))))
        result,_=self.f.evaluate()
        self.assertEqual(len(result['v']),4)


class OutcomeTests(unittest.TestCase):
    def test_raw_json_and_whole_fence_are_separate(self):
        a,b=ev.outcome(response()),ev.outcome(response(fence=True))
        self.assertTrue(a['strict_json_valid']);self.assertFalse(b['strict_json_valid'])
        self.assertTrue(b['common_parse_valid']);self.assertEqual(b['status'],'other')
        self.assertEqual(b['common_postprocessing'],'outer_json_fence_removed')

    def test_missing_parse_failure_and_indeterminate_never_become_other(self):
        invalid=response();invalid.update(raw_response='broken',parsed=None,parse=parse_pair('broken'))
        self.assertEqual(ev.outcome(None)['status'],'missing')
        self.assertEqual(ev.outcome(invalid)['status'],'parse_failed')
        self.assertEqual(ev.outcome(response(['indeterminate']))['status'],'indeterminate')
        self.assertEqual(ev.outcome(response(['indeterminate','stepping_over_boundary']))['status'],'candidate')
        self.assertEqual(ev.outcome(response(completion='observed'))['status'],'other')

    def test_candidate_reduction_cannot_hide_q04_loss_or_indeterminate(self):
        rows=[{'review_clip_id':q[0],'view':view,'old':{'status':'candidate'},'new':{'status':'other'}}
              for q in ev.Q for view in ('full_frame','fixed_roi')]
        for assessment in ev.q_assessment(rows).values():
            self.assertEqual(assessment['status'],'not_improvement_q04_candidate_missing')
            self.assertFalse(assessment['candidate_reduction_alone_is_success'])
        for r in rows:
            if r['review_clip_id']=='q04':r['new']['status']='candidate'
            if r['review_clip_id']=='q02':r['new']['status']='indeterminate'
        for assessment in ev.q_assessment(rows).values():
            self.assertEqual(assessment['status'],'unresolved_outputs_prevent_improvement_claim')

    def test_partial_index_unknown_or_duplicate_group_rejected(self):
        with self.assertRaises(ValueError):ev.index_paths({'experiment':'EXP-0017','jobs':[]})
        jobs=[dict(phase=p,view=v,expected_records=n,state='running') for p,v,n in ev.GROUPS.values()]
        with self.assertRaisesRegex(ValueError,'not finalized'):ev.index_paths({'experiment':'EXP-0017','jobs':jobs})

    def test_duplicate_nonfinite_metadata_rejected(self):
        for raw in ('{"a":1,"a":2}','{"a":NaN}'):
            with self.assertRaises(ValueError):ev.strict_json(raw)

    def test_cli_imports_no_model_or_decoder(self):
        code='from scripts import evaluate_exp0017; import sys; assert not set(("torch","transformers","av","numpy","mvp.runner","mvp.method")) & set(sys.modules)'
        subprocess.run([sys.executable,'-B','-c',code],cwd=ev.ROOT,check=True,capture_output=True)

    def test_write_once_refuses_replacement_and_preserves_identical_mtime(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'result.json';ev.write_once(p,b'one');stamp=p.stat().st_mtime_ns
            ev.write_once(p,b'one');self.assertEqual(p.stat().st_mtime_ns,stamp)
            with self.assertRaisesRegex(ValueError,'overwrite'):ev.write_once(p,b'two')


if __name__=='__main__':unittest.main()
