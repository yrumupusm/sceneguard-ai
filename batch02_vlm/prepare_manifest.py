"""CPU metadata freeze from existing local, hash-bound readiness/audit evidence."""
import json
from pathlib import Path
from orchestration.vlm_command import file_hash
from orchestration.batch02_vlm_command import ROOT,SETTINGS,QUANTIZATION,REVISION,CONDITIONS


def build():
    root=ROOT;readiness=root/'runtime/BATCH-0002/vlm-readiness'
    baselines=json.loads((readiness/'baseline-reuse-metadata.json').read_text())
    audit=json.loads((root/'records/EXP-0018/input_audit.json').read_text())['inputs']
    rows=[]
    for baseline in baselines:
        identity=baseline['condition'];review,view=identity.split('_',1)
        entry=next(e for e in audit if e['review_id']==review and e['condition']==('q_'+view+'_EXP0017_saved' if review.startswith('q') else 'v_original_EXP0017_saved'))
        bpath=Path(baseline['baseline_result']);source=bpath.with_name('input.json')
        if file_hash(root/bpath)!=baseline['result_sha256']:
            raise ValueError('baseline readiness binding differs')
        if review.startswith('q'):
            attempt={'B':'9555b3da23aa4c10bfd9a8ed0d0dd237','C':'b8de7de3d3e84ee3a2e7d1c4d2af7e63'}[view]
            parity=Path('outputs/mvp0001/EXP-0016')/attempt/entry['source_id']/'windows'/entry['window_id']/'processor_rgb.npy'
        else:
            parity=bpath.with_name('processor_rgb.npy')
        if file_hash(root/parity)!=entry['saved_processor_file_sha256']:
            raise ValueError('EXP18 saved processor binding differs')
        names=[str(bpath),str(source),str(parity)]
        prompt=str(bpath.with_name('expanded_prompt.txt')) if not review.startswith('q') else None
        if prompt:names.append(prompt)
        path='data/TS_침입/'+entry['source_id']+'.mp4'
        files={n:file_hash(root/n) for n in names};files[path]=entry['source_sha256']
        rows.append(dict(condition_id=identity,window_id=entry['window_id'],roi=baseline['input_metadata']['roi'],source_path=path,source_metadata=str(source),source_frame_sha256=entry['source_frame_sha256'],baseline_result=str(bpath),expected_metadata=baseline['input_metadata'],parity_rgb=str(parity),parity_prompt=prompt,files=files))
    rows.sort(key=lambda r: CONDITIONS.index(r['condition_id']))
    api=json.loads((readiness/'hf-model-api.json').read_text());files={}
    for r in api['siblings']:
        name=r['rfilename']
        if name in ('.gitattributes','README.md'):continue
        p=root/'weights/Qwen3-VL-4B-Instruct'/name
        if 'lfs' in r:sha=r['lfs']['sha256']
        elif p.exists():sha=file_hash(p)
        else:
            old=root/'weights/Qwen3-VL-2B-Instruct'/name;cached=readiness/('model-'+name)
            sha=file_hash(cached if cached.exists() else old)
        files[name]=dict(bytes=r['size'],sha256=sha,official_git_blob=r['blobId'])
    pins={n:file_hash(root/n) for n in ('configs/vlm_batch01_prompt.txt','configs/batch0002_user_input_review.json','records/EXP-0018/input_audit.json','runtime/BATCH-0002/vlm-readiness/hf-model-api.json')}
    env_files={}
    environment=root/'runtime/BATCH-0002/vlm/environment.json'
    if environment.exists():
        env_files={str(environment.relative_to(root)):file_hash(environment)}
    return dict(schema_version=1,batch='BATCH-0002',experiment='EXP-0020',model=dict(id=api['id'],revision=REVISION,files=files),settings=SETTINGS,quantization=QUANTIZATION,device_map={'':'cuda:0'},processor_size=dict(shortest_edge=16384,longest_edge=3584000),prompt_sha256=pins['configs/vlm_batch01_prompt.txt'],smoke=['q04_C','q05_B'],conditions=rows,pins=pins,environment=dict(files=env_files,interpreter_sha256=json.loads(environment.read_text())['interpreter_sha256'] if environment.exists() else None,status='installed_verified' if env_files else 'installation_in_progress'),input_gate='coordinator conditional go; uncertainties preserved only in evaluation')


if __name__=='__main__':
    p=ROOT/'configs/batch0002_vlm_manifest.json'
    if p.exists():
        raise ValueError('manifest exists; explicit coordinator pre-freeze update required')
    p.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
