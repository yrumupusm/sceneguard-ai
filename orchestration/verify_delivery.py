"""Separate publication and actual local-browser acceptance receipts; never run a model."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request

from webapp.app import safe_open


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(root, path):
    with safe_open(root, path) as stream:
        return stream.read()


def snapshot(config, experiment):
    root = Path(config['repo_root'])
    catalog = json.loads(read(root, 'records/catalog.json'))
    items = [x for x in catalog['experiments'] if x['experiment_id'] == experiment]
    if len(items) != 1:
        raise ValueError('Exactly one registered result required')
    item = items[0]
    paths = [item[k] for k in ('report_path', 'metrics_path', 'review_path', 'review_binding_path')]
    if not (paths[0].startswith('docs/experiments/') and paths[1].startswith(f'records/{experiment}/')
            and all(p.startswith('docs/reviews/') for p in paths[2:])):
        raise ValueError('Invalid public result paths')
    files = {p: read(root, p) for p in paths}
    fingerprints = {p: sha(data) for p, data in files.items()}
    binding = json.loads(files[item['review_binding_path']])
    reviewed = binding['reviewed_sources'][experiment]
    if not (fingerprints[item['report_path']] == item['report_sha256'] == reviewed['report_sha256']
            and fingerprints[item['metrics_path']] == item['metrics_sha256'] == reviewed['metrics_sha256']
            and binding['review_path'] == item['review_path']
            and fingerprints[item['review_path']] == binding['review_sha256']):
        raise ValueError('Result or review changed; register and review the current bytes first')
    assignment = None
    if item.get('slot') != 'unassigned':
        rows = json.loads(read(root, 'records/assignments.json'))['assignments']
        matches = [x for x in rows if x['experiment_id'] == experiment]
        if len(matches) != 1 or matches[0]['slot'] != item['slot']:
            raise ValueError('Result has no matching assignment')
        assignment = matches[0]
        for key in ('run_id', 'task_id', 'dispatch_id'):
            if assignment[key] != item[key]:
                raise ValueError('Assignment and result lifecycle differ')
    return item, assignment, files, fingerprints


def command(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], timeout=20)


def verify_github(config, experiment, expected_commit, remote='origin', branch='main'):
    if not re.fullmatch(r'[0-9a-f]{40}', expected_commit):
        raise ValueError('Expected full commit SHA required')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', remote + '/' + branch):
        raise ValueError('Invalid remote/branch')
    item, assignment, files, fingerprints = snapshot(config, experiment)
    root = config['repo_root']
    url = command(root, 'remote', 'get-url', remote).decode().strip()
    if not (urllib.parse.urlparse(url).hostname == 'github.com' or url.startswith('git@github.com:')):
        raise ValueError('Publication check requires a GitHub remote')
    line = command(root, 'ls-remote', '--exit-code', remote, f'refs/heads/{branch}').decode().strip()
    if line.split()[0] != expected_commit:
        raise ValueError('Remote branch does not match expected commit')
    remote_catalog = json.loads(command(root, 'show', f'{expected_commit}:records/catalog.json'))
    if [x for x in remote_catalog['experiments'] if x['experiment_id'] == experiment] != [item]:
        raise ValueError('Published catalog result differs')
    if assignment:
        remote_assignments = json.loads(command(root, 'show', f'{expected_commit}:records/assignments.json'))
        if [x for x in remote_assignments['assignments'] if x['experiment_id'] == experiment] != [assignment]:
            raise ValueError('Published assignment differs')
    for path, data in files.items():
        if command(root, 'show', f'{expected_commit}:{path}') != data:
            raise ValueError('Published source differs: ' + path)
    return {'domain': 'github', 'passed': True, 'commit': expected_commit, 'remote': remote,
            'branch': branch, 'source_sha256': fingerprints, 'browser_verified': False}


BROWSER_JS = r'''(async()=>{
 const expected=EXPECTED;
 expected.metrics=expected.metrics.map(([k,v])=>[k,v===null?'미측정':String(v)]);
 const wait=async(test,label,ms=6000)=>{const end=Date.now()+ms;while(Date.now()<end){if(test())return;await new Promise(r=>setTimeout(r,30));}throw Error(label);};
 if(location.origin!==expected.origin)throw Error('Wrong browser origin');
 const slot=[...document.querySelectorAll('.slot')].find(x=>x.dataset.slot===expected.slot);
 if(!slot)throw Error('Slot card absent');slot.click();
 await wait(()=>[...document.querySelectorAll('button[data-id]')].some(x=>x.dataset.id===expected.id),'Result button absent');
 [...document.querySelectorAll('button[data-id]')].find(x=>x.dataset.id===expected.id).click();
 await wait(()=>document.querySelector('#detail')?.dataset.id===expected.id&&document.querySelector('#detail')?.dataset.result==='registered'&&document.querySelector('#detail .eyebrow'),'Selected result absent');
 const detail=document.querySelector('#detail');
 if(detail.dataset.executionStatus!==expected.execution)throw Error('Wrong execution state');
 const rows=[...detail.querySelector('table').rows].slice(1).map(x=>[x.cells[0].textContent,x.cells[1].textContent]);
 if(JSON.stringify(rows)!==JSON.stringify(expected.metrics))throw Error('Metric table differs');
 if(detail.querySelectorAll('.graph').length!==expected.graphs)throw Error('Graphs absent or wrong groups');
 if(!detail.querySelector('.original-report')?.textContent.trim())throw Error('Report absent');
 if(!detail.querySelector('[data-section=review]')?.textContent.trim())throw Error('Review absent');
 const results=[];const retained=[];
 for(const id of expected.videos){
  const v=[...detail.querySelectorAll('video')].find(x=>x.getAttribute('src')==='/artifacts/'+id);
  if(!v)throw Error('Registered comparison video absent: '+id);retained.push(v);v.muted=true;
  const event=(name,act)=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error(name+' timeout')),6000);v.addEventListener(name,()=>{clearTimeout(timer);resolve();},{once:true});v.addEventListener('error',()=>{clearTimeout(timer);reject(Error('media decode error'));},{once:true});act();});
  await event('loadedmetadata',()=>v.load());await v.play();await new Promise(r=>setTimeout(r,300));v.pause();
  const played=v.currentTime;if(!(played>0&&v.videoWidth>0&&v.duration>0))throw Error('Playback did not advance');
  const target=Math.min(1.5,v.duration/2);await event('seeked',()=>{v.currentTime=target;});
  if(Math.abs(v.currentTime-target)>.1||v.error)throw Error('Seek failed');
  results.push({id,width:v.videoWidth,height:v.videoHeight,duration:v.duration,played,seek:v.currentTime,decoded_frames:v.getVideoPlaybackQuality().totalVideoFrames});
 }
 await new Promise(r=>setTimeout(r,expected.poll_wait_ms));
 if(retained.some(v=>!v.isConnected||![...document.querySelectorAll('#detail video')].includes(v)))throw Error('Polling replaced video node');
 return JSON.stringify({passed:true,experiment_id:expected.id,slot:expected.slot,card_text:slot.textContent,metrics:rows,graphs:expected.graphs,report_opened:true,review_opened:true,videos:results,poll_preserved_video:true,origin:location.origin});
})()'''


def verify_browser(config, experiment, page, url, cli, poll_wait_ms=16500):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1') or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('Explicit loopback HTTP base URL required')
    base = url.rstrip('/')
    item, _, files, fingerprints = snapshot(config, experiment)
    def fetch(path):
        with urllib.request.urlopen(base + path, timeout=5) as response:
            return response.read()
    api = json.loads(fetch('/api/experiments/' + urllib.parse.quote(experiment, safe='')))
    if any(api.get(k) != item.get(k) for k in ('experiment_id','slot','report_sha256','metrics_sha256','execution_status')):
        raise ValueError('Local server serves another result version')
    if api.get('review_integrity') != 'current' or any(api.get('source_integrity', {}).get(k) is not True for k in ('report_match', 'metrics_match')):
        raise ValueError('Server review/source integrity not current')
    # Check the JavaScript actually served by this URL separately from GitHub.
    js_hash = sha(fetch('/assets/app.js'))
    if js_hash != sha((Path(__file__).resolve().parents[1] / 'webapp/app.js').read_bytes()):
        raise ValueError('Served viewer code differs from verification checkout')
    metrics = json.loads(files[item['metrics_path']])['metrics']
    groups = list(dict.fromkeys((m.get('unit') or '단위 없음', m.get('scope') or '범위 미확인') for m in metrics
                               if isinstance(m['value'], (int,float)) and not isinstance(m['value'],bool) and m['value'] >= 0))
    videos = [e['artifact_id'] for e in item.get('evidence', []) if e['kind'] == 'video']
    if not videos:
        raise ValueError('No registered comparison video; do not report video acceptance')
    expected = {'id': experiment, 'slot': item['slot'], 'origin': base, 'execution': item['execution_status'],
                'metrics': [[m['label'], m['value']] for m in metrics],
                'graphs': min(2,len(groups)), 'videos': videos, 'poll_wait_ms': poll_wait_ms}
    # Numeric formatting is performed by JavaScript in both UI and probe.
    expression = BROWSER_JS.replace('EXPECTED', json.dumps(expected, ensure_ascii=False), 1)
    receipt = json.loads(subprocess.check_output([cli,'eval','--page',page,'--expression',expression,'--json'],timeout=55))
    if receipt.get('ok') is not True:
        raise ValueError('Browser operation failed')
    observed = json.loads(receipt['result']['result'])
    if observed.get('passed') is not True or observed.get('experiment_id') != experiment:
        raise ValueError('Browser receipt did not prove selected result')
    # Detect a source change during the browser operation before accepting it.
    if snapshot(config, experiment)[3] != fingerprints:
        raise ValueError('Result changed during browser check')
    return {'domain':'browser','passed':True,'url':base,'source_sha256':fingerprints,
            'viewer_js_sha256':js_hash,'observations':observed,'github_verified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--experiment', required=True)
    p.add_argument('--output', type=Path, required=True)
    sub=p.add_subparsers(dest='domain', required=True)
    git=sub.add_parser('github');git.add_argument('--expected-commit',required=True)
    git.add_argument('--remote',default='origin');git.add_argument('--branch',default='main')
    web=sub.add_parser('browser');web.add_argument('--page',required=True);web.add_argument('--url',required=True)
    args=p.parse_args()
    config=json.loads(args.config.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves previous observations, even on retry.
    with args.output.open('x', encoding='utf-8') as out:
        result={'domain':args.domain,'experiment_id':args.experiment,'checked_at':datetime.now(timezone.utc).isoformat(),'passed':False}
        try:
            if args.domain=='github':
                result.update(verify_github(config,args.experiment,args.expected_commit,args.remote,args.branch))
            else:
                result.update(verify_browser(config,args.experiment,args.page,args.url,config.get('orca_cli','orca-ide')))
        except Exception as error:
            result['error']=str(error)
        json.dump(result,out,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':
    main()
