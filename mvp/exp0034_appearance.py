"""Frozen local EXP-0034 crop comparison; no action labels enter model input.

The manifest is created by CPU preparation after the coordinator selects pairs.
Its complete candidate graph is provenance for coverage, never a model prompt.
"""
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import traceback

from orchestration.mock_job import atomic_json
from orchestration.queue import digest
from orchestration.vlm_command import file_hash

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'runtime/EXP-0034'
MANIFEST=LOCAL/'appearance_manifest.json'
AUTHORIZATION=LOCAL/'appearance-execution-authorization.json'
IDENTITY=('run_3d23462a014a','task_346d88014dbc','ctx_93298a31e489')
PHASE='appearance-compare'
SOURCE_ROWS={
    'E01_030':('outputs/exp0028/practical-v1/track030/gap/frames.jsonl',
              '2a8006450e18c1d6fe8b5022302cc7d75066ebbe356c6aab453147c5c4f48f88'),
    'E01_007':('outputs/exp0029/replay007/gap/frames.jsonl',
              'df88fcfe8293b5c624a617bb9d36e68fb366acbd0a35835805ee35e31c5b7c04')}


def local_path(name):
    if not isinstance(name,str) or Path(name).is_absolute():
        raise ValueError('Repository-relative local path required')
    p=ROOT/name
    if p.resolve()!=p or not p.is_file():
        raise ValueError('Existing local file without path redirection required')
    return p


def load_manifest():
    m=json.loads(MANIFEST.read_text())
    if (set(m)!={'schema_version','experiment_id','run_id','sources','pairs','candidate_pairs'}
            or m['schema_version']!=1 or m['experiment_id']!='EXP-0034' or m['run_id']!=IDENTITY[0]):
        raise ValueError('Fixed EXP-0034 manifest schema required')
    if not isinstance(m['pairs'],list) or not 1<=len(m['pairs'])<=6:
        raise ValueError('One to six frozen comparison pairs required')
    source_ids=set()
    for s in m['sources']:
        if set(s)!={'source_id','path','source_sha256','frames_path','frames_sha256'}:
            raise ValueError('Only source provenance fields allowed')
        sid=s['source_id']
        if sid not in SOURCE_ROWS or sid in source_ids:
            raise ValueError('Unique existing 030/007 source required')
        source_ids.add(sid)
        if (s['path']!=f'data/TS_침입/{sid}.mp4' or s['source_sha256']!=SOURCE_ROWS[sid][1]
                or s['frames_path']!=SOURCE_ROWS[sid][0]):
            raise ValueError('Frozen source and observation paths required')
    graph={}
    for p in m['candidate_pairs']:
        if (set(p)!={'pair_id','before','after'} or
                any(not isinstance(p[k],str) or not p[k] for k in p)):
            raise ValueError('Complete candidate graph uses opaque IDs only')
        if p['pair_id'] in graph:
            raise ValueError('Duplicate candidate pair ID')
        graph[p['pair_id']]=p
    selected=set()
    image_keys={'path','sha256','rgb_sha256','source_id','raw_id','cache_index',
                'decoded_index','native_pts','time_base','pts','bbox_xyxy',
                'crop_bounds_xyxy','source_size'}
    for p in m['pairs']:
        if set(p)!={'pair_id','before','after','before_images','after_images'}:
            raise ValueError('Only opaque pair IDs and image provenance allowed')
        if p['pair_id'] in selected or graph.get(p['pair_id'])!={k:p[k] for k in ('pair_id','before','after')}:
            raise ValueError('Selected pairs must be unique exported candidates')
        selected.add(p['pair_id'])
        for side in ('before_images','after_images'):
            if not isinstance(p[side],list) or not 1<=len(p[side])<=3:
                raise ValueError('One to three actual crops per side required')
            for im in p[side]:
                if set(im) not in (image_keys,image_keys|{'frame_index'}):
                    raise ValueError('Only crop observation provenance allowed')
                if im['source_id'] not in source_ids or im['source_size']!=[1920,1080]:
                    raise ValueError('Known source and native image size required')
                if any(type(im[k]) is not int or im[k]<0 for k in
                       ('raw_id','cache_index','decoded_index','native_pts')):
                    raise ValueError('Integer actual observation identity required')
                if (type(im['pts']) not in (int,float) or not math.isfinite(im['pts'])
                        or float(im['native_pts']*Fraction(im['time_base']))!=im['pts']):
                    raise ValueError('Exact native PTS required')
                b=im['bbox_xyxy']
                if (not isinstance(b,list) or len(b)!=4 or
                        any(type(v) not in (int,float) or not math.isfinite(v) for v in b)
                        or not (0<=b[0]<b[2]<=1 and 0<=b[1]<b[3]<=1)):
                    raise ValueError('Actual normalized observed bbox required')
                bounds=[math.floor(b[0]*1920),math.floor(b[1]*1080),
                        math.ceil(b[2]*1920),math.ceil(b[3]*1080)]
                if im['crop_bounds_xyxy']!=bounds or min(bounds[2]-bounds[0],bounds[3]-bounds[1])<16:
                    raise ValueError('Exact native bbox crop without resize or margin required')
                if not im['path'].startswith(('runtime/EXP-0034/','outputs/exp0034/')) or not im['path'].endswith('.npy'):
                    raise ValueError('New local native crop array required')
            if len({im['raw_id'] for im in p[side]})!=1 or any(
                    a['pts']>=b['pts'] for a,b in zip(p[side],p[side][1:])):
                raise ValueError('Each side must contain ordered actual crops of one raw ID')
        all_images=p['before_images']+p['after_images']
        if len({i['source_id'] for i in all_images})!=1:
            raise ValueError('A pair must use a single original camera source')
    return m


def load_crop(im):
    import numpy as np
    path=local_path(im['path'])
    if file_hash(path)!=im['sha256']:
        raise ValueError('Frozen crop file changed')
    arr=np.load(path,allow_pickle=False)
    x0,y0,x1,y1=im['crop_bounds_xyxy']
    if (arr.dtype!=np.uint8 or arr.shape!=(y1-y0,x1-x0,3)
            or hashlib.sha256(arr.tobytes()).hexdigest()!=im['rgb_sha256']):
        raise ValueError('Native RGB crop shape or bytes differ')
    return arr


def bind_inputs():
    m=load_manifest()
    crops={}
    for s in m['sources']:
        if file_hash(local_path(s['path']))!=s['source_sha256'] or file_hash(local_path(s['frames_path']))!=s['frames_sha256']:
            raise ValueError('Frozen source or observed rows changed')
        frames=[json.loads(line) for line in local_path(s['frames_path']).read_text().splitlines() if line.strip()]
        indexed={(f['native_pts'],f['time_base']):(index,f) for index,f in enumerate(frames)}
        for p in m['pairs']:
            for im in p['before_images']+p['after_images']:
                if im['source_id']!=s['source_id']:
                    continue
                index,frame=indexed[(im['native_pts'],im['time_base'])]
                matches=[d for d in frame['detections'] if d.get('observed') is True
                         and d.get('track_id')==im['raw_id'] and d.get('cache_index')==im['cache_index']
                         and d.get('bbox')==im['bbox_xyxy']]
                if len(matches)!=1 or frame['pts']!=im['pts'] or im.get('frame_index',index)!=index:
                    raise ValueError('Crop does not bind to one stored actual observation')
                load_crop(im)
                crops[im['path']]=im['sha256']
    return {'appearance_manifest_sha256':file_hash(MANIFEST),
            'appearance_sources':{s['source_id']:s for s in m['sources']},
            'appearance_crops':crops,
            'appearance_generation':{'do_sample':False,'max_new_tokens':192,'maximum_calls':len(m['pairs']),
                                     'automatic_retry':False},
            'appearance_prompt_sha256':hashlib.sha256(__import__('sceneguard.appearance_support',fromlist=['PROMPT']).PROMPT.encode()).hexdigest()}


def verify_native_crops():
    """Decode exact original frames on CPU once before model construction."""
    import av
    import numpy as np
    m=load_manifest()
    checked=0
    for s in m['sources']:
        wanted={}
        for p in m['pairs']:
            for im in p['before_images']+p['after_images']:
                if im['source_id']==s['source_id']:
                    wanted.setdefault(im['decoded_index'],[]).append(im)
        if not wanted:
            continue
        with av.open(str(local_path(s['path']))) as container:
            for index,frame in enumerate(container.decode(video=0)):
                if index in wanted:
                    rgb=frame.to_ndarray(format='rgb24')
                    for im in wanted.pop(index):
                        if (frame.pts!=im['native_pts'] or str(frame.time_base)!=im['time_base']
                                or rgb.shape!=(1080,1920,3)):
                            raise ValueError('Native decoded frame timing or size differs')
                        x0,y0,x1,y1=im['crop_bounds_xyxy']
                        if not np.array_equal(rgb[y0:y1,x0:x1],load_crop(im)):
                            raise ValueError('Stored crop differs from exact native source pixels')
                        checked+=1
                if not wanted:
                    break
        if wanted:
            raise ValueError('Original source ended before requested native crop')
    return {'native_crops_checked':checked,'resize_before_processor':False,'sampling':False}


def validate_authorization():
    from orchestration.mvp_command import sources,input_contract
    a=json.loads(AUTHORIZATION.read_text())
    if tuple(a.get(k) for k in ('run_id','task_id','dispatch_id'))!=IDENTITY:
        raise ValueError('Exact current live task/dispatch authorization required')
    if any(a.get(k) is not True for k in ('confirmed','inference_authorized','independent_review_passed')):
        raise ValueError('Root GO and independent preflight required')
    if a.get('maximum_generate_calls')!=len(load_manifest()['pairs']) or not 1<=a['maximum_generate_calls']<=6:
        raise ValueError('Exact reviewed generation budget required')
    if (a.get('sources')!=sources({'phase':PHASE}) or
            a.get('input_contract_sha256')!=digest(input_contract(PHASE)) or
            a.get('code_sha')!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()):
        raise ValueError('Reviewed source/input/HEAD freeze differs')
    return a


def covered_proposals(candidate_pairs,responses):
    """Never claim uniqueness while a competing edge is untested or unknown."""
    from sceneguard.appearance_support import link_proposals,parse_comparison
    rows=link_proposals(candidate_pairs,responses)
    for row in rows:
        competitors=[p for p in candidate_pairs if p['pair_id']!=row['pair_id'] and
                     (p['before']==row['before'] or p['after']==row['after'])]
        untested=[p['pair_id'] for p in competitors if p['pair_id'] not in responses]
        unknown=[p['pair_id'] for p in competitors if p['pair_id'] in responses and
                 parse_comparison(responses[p['pair_id']])['comparison']['decision']=='unknown']
        tested=row['pair_id'] in responses
        row.update(untested_competitors=untested,unknown_competitors=unknown,
                   comparison_tested=tested,candidate_coverage_complete=tested and not untested,
                   uniqueness_assessed=row['appearance_decision']!='unknown' and not untested and not unknown,
                   raw_ids_merged=False,intrusion_verdict=None)
        if row['link_status']=='review_link_proposed' and (untested or unknown):
            row['link_status']='unresolved_competitor_coverage'
    return rows


def run_appearance(analyzer,folder,context):
    import numpy as np
    from sceneguard.appearance_support import compare_images
    m=load_manifest()
    atomic_json(folder/'appearance_manifest.json',m)
    rows=[]
    responses={}
    for index,pair in enumerate(m['pairs'],1):
        target=folder/f'p{index:06d}'
        target.mkdir()
        atomic_json(target/'input_provenance.json',{'pair':pair,'run_context':context})
        analyzer.last_processor_images=None
        analyzer.last_expanded_prompt=None
        analyzer.last_input_metadata=None
        analyzer.last_generated_token_ids=[]
        def save():
            for j,im in enumerate(getattr(analyzer,'last_processor_images',None) or []):
                np.save(target/f'processor_rgb_{j:02d}.npy',im,allow_pickle=False)
            if analyzer.last_expanded_prompt is not None:
                (target/'expanded_prompt.txt').write_text(analyzer.last_expanded_prompt)
            if analyzer.last_input_metadata is not None:
                atomic_json(target/'processor_metadata.json',analyzer.last_input_metadata)
            if analyzer.last_generated_token_ids:
                np.save(target/'generated_token_ids.npy',np.array(analyzer.last_generated_token_ids,dtype='int64'),allow_pickle=False)
        analyzer.appearance_diagnostics=save
        try:
            result=compare_images(analyzer,[load_crop(im) for im in pair['before_images']],
                                  [load_crop(im) for im in pair['after_images']])
            save()
            (target/'raw_response.txt').write_text(result['raw_response'])
            result.update(pair_id=pair['pair_id'],directory=target.name)
            atomic_json(target/'result.json',result)
            rows.append(result)
            responses[pair['pair_id']]=result['raw_response']
            print(target.name,'generated',flush=True)
        except Exception as exc:
            save()
            atomic_json(target/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'generation_retries':0})
            raise
        finally:
            atomic_json(folder/'appearance_results.json',{'completed':rows,'partial':len(rows)!=len(m['pairs']),
                'proposals':covered_proposals(m['candidate_pairs'],responses),
                'raw_ids_merged':False,'intrusion_verdict':None})
    return rows
