"""Explicit reviewed-clip R3D-18 experiment; never changes the SceneGuard pipeline.

Manifest rows contain source_path/source_sha256, source_id, event_group, split,
label (0/1), actor_id, sample_pts, roi_xyxy, and label_evidence. Official
explicit actor annotations require a hash-bound sampled alignment review release; unlabeled video regions never become negative examples.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def validate_manifest(manifest, baseline, frames=16, source_split=None):
    if baseline.get('status') != 'verified' or baseline.get('baseline_experiment') != 'EXP-0062':
        raise ValueError('A verified EXP-0062 baseline lock is required')
    if manifest.get('review_status') != 'sampled_alignment_review_complete':
        raise ValueError('A completed sampled alignment review is required')
    if manifest.get('label_policy') != 'official_actor_action_intervals_sampled_alignment_review':
        raise ValueError('Only explicit actor action interval labels are accepted')
    forbidden = {x['sha256'] for x in baseline['regression_only_videos']}
    forbidden_paths = {str(Path(x['path']).resolve()) for x in baseline['regression_only_videos']}
    memberships, ids, counts = {}, set(), Counter()
    path_hashes = {}
    held_out = set(manifest.get('held_out_test_locations', []))
    clips = manifest['clips']
    frozen_sources = {r['source_id']: r for r in source_split['assignments']} if source_split else None
    if source_split and held_out != set(source_split.get('held_out_test_locations', [])):
        raise ValueError('Held-out location differs from frozen split')
    for row in clips:
        key = row['clip_id']
        if key in ids:
            raise ValueError('Duplicate clip id')
        ids.add(key)
        split = row['split']
        source_path = str(Path(row['source_path']).resolve())
        if source_path in path_hashes and path_hashes[source_path] != row['source_sha256']:
            raise ValueError('Contradictory source path/hash bindings')
        path_hashes[source_path] = row['source_sha256']
        path_group = ('source_path', source_path)
        if path_group in memberships and memberships[path_group] != split:
            raise ValueError('Source path leakage across splits')
        memberships[path_group] = split
        if frozen_sources is not None:
            original = frozen_sources.get(row['source_id'])
            if not original or original.get('excluded') or original['split'] != split:
                raise ValueError('Clip differs from frozen original-video split')
            if (original['source_sha256'] != row['source_sha256'] or original['group_id'] != row['event_group']
                    or original.get('location') != row.get('location')):
                raise ValueError('Clip source/event group differs from frozen split')
            if original.get('label_sha256') and original['label_sha256'] != row.get('label_sha256'):
                raise ValueError('Official annotation differs from frozen split')
        if row.get('location') in held_out and split != 'test':
            raise ValueError('Held-out test location leaked into development')
        if split not in {'train', 'validation', 'test'} or type(row['label']) is not int or row['label'] not in (0, 1):
            raise ValueError('Invalid split or binary label')
        if row['source_sha256'] in forbidden or str(Path(row['source_path']).resolve()) in forbidden_paths:
            raise ValueError('Regression source is forbidden for action data')
        if row.get('scenario_family') == 4 and row.get('scenario_number') in {*range(19, 36), 69, 70}:
            raise ValueError('User-excluded wall-over scenario')
        for field in ('source_id', 'source_sha256', 'event_group'):
            group = (field, row[field])
            if group in memberships and memberships[group] != split:
                raise ValueError('Source/event leakage across splits: ' + field)
            memberships[group] = split
        if not row.get('label_evidence') or row.get('temporal_alignment') != 'annotation_interior_both_origins' or row.get('box_alignment') != 'official_annotations_sampled_alignment_review':
            raise ValueError('Unreviewed labels or temporal/box alignment')
        if row['label'] == 0 and row.get('negative_basis') not in {'explicit_action_annotation', 'human_reviewed_interval'}:
            raise ValueError('Missing explicit negative evidence')
        if row.get('actor_id') is None:
            raise ValueError('Actor association is required for this person-context experiment')
        pts = row['sample_pts']
        if len(pts) != frames or any(not math.isfinite(p) or p < 0 for p in pts):
            raise ValueError('Invalid temporal samples')
        if any(abs(b-a-1/3) > 1e-5 for a, b in zip(pts, pts[1:])):
            raise ValueError('Must use real consecutive 3FPS frames; no padding/interpolation')
        start, end = row['verified_action_interval']
        if not all(math.isfinite(v) for v in (start, end)) or not 0 <= start <= end:
            raise ValueError('Invalid action interval')
        if pts[0] < start or pts[-1] > end:
            raise ValueError('Samples extend beyond the explicit labeled interval')
        x1, y1, x2, y2 = row['roi_xyxy']
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2)) or not (0 <= x1 < x2 and 0 <= y1 < y2):
            raise ValueError('Invalid contextual ROI')
        counts[(split, row['label'])] += 1
    for split in ('train', 'validation'):
        if not all(counts[split, label] for label in (0, 1)):
            raise ValueError('Training and validation each require both explicit classes')
    if not any(counts['test', label] for label in (0, 1)):
        raise ValueError('An untouched test partition is required')
    return {f'{split}:{label}': count for (split, label), count in sorted(counts.items())}


def decode_clip(row, size):
    import av
    import cv2
    import numpy as np
    targets = row['sample_pts']
    result = []
    with av.open(row['source_path']) as container:
        stream = container.streams.video[0]
        container.seek(max(0, int((targets[0] - 1) / float(stream.time_base))), stream=stream)
        for frame in container.decode(stream):
            t = float(frame.time)
            if t < targets[len(result)] - 1e-5:
                continue
            if abs(t - targets[len(result)]) > 1e-5:
                raise ValueError('Native PTS mismatch; no nearest-frame substitution')
            array = frame.to_ndarray(format='rgb24')
            x1, y1, x2, y2 = map(int, row['roi_xyxy'])
            if x2 > frame.width or y2 > frame.height:
                raise ValueError('ROI exceeds source image')
            crop = array[y1:y2, x1:x2]
            height, width = crop.shape[:2]
            scale = size / max(height, width)
            resized = cv2.resize(crop, (max(1, round(width * scale)), max(1, round(height * scale))))
            canvas = np.zeros((size, size, 3), dtype=np.uint8)
            top, left = (size-resized.shape[0])//2, (size-resized.shape[1])//2
            canvas[top:top+resized.shape[0], left:left+resized.shape[1]] = resized
            result.append(canvas)
            if len(result) == len(targets):
                break
    if len(result) != len(targets):
        raise ValueError('Incomplete decoded clip')
    return np.stack(result)


def metrics(rows):
    if any(not math.isfinite(r['score']) for r in rows):
        raise ValueError('Nonfinite action score')
    tp = sum(r['label'] == 1 and r['score'] >= .5 for r in rows)
    fp = sum(r['label'] == 0 and r['score'] >= .5 for r in rows)
    fn = sum(r['label'] == 1 and r['score'] < .5 for r in rows)
    tn = sum(r['label'] == 0 and r['score'] < .5 for r in rows)
    # A positive-only held-out place cannot establish precision or false positives.
    both = bool(tp + fn) and bool(fp + tn)
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': tp/(tp+fp) if both and tp+fp else None,
            'recall': tp/(tp+fn) if tp+fn else None,
            'f1': 2*tp/(2*tp+fp+fn) if both and 2*tp+fp+fn else None,
            'scope': 'official_actor_annotation_reference_only', 'threshold': .5,
            'human_precision': None, 'human_recall': None, 'human_f1': None,
            'intrusion_completion_accuracy': None}


def validate_release(manifest_path, split_path, release_path, expected_hash):
    """Local snapshot bound by content hashes, not a human cryptographic signature."""
    if not expected_hash or sha(release_path) != expected_hash:
        raise ValueError('Review release hash differs')
    release = json.loads(Path(release_path).read_text())
    if (release.get('schema_version') != 1 or release.get('experiment_id') != 'EXP-0063'
            or release.get('manifest_sha256') != sha(manifest_path)
            or release.get('split_manifest_sha256') != sha(split_path)):
        raise ValueError('Review release manifest/split binding differs')
    policy = release['interpretation_policy']
    if sha(policy['path']) != policy['sha256']:
        raise ValueError('Review interpretation policy changed')
    snapshot = release['review_snapshot']
    if sha(snapshot['path']) != snapshot['sha256']:
        raise ValueError('Saved review snapshot changed')
    manifest = json.loads(Path(manifest_path).read_text())
    evidence = manifest.get('review_evidence', {})
    if (evidence.get('review_snapshot') != snapshot or evidence.get('review_policy') != policy
            or evidence.get('reviews') != release.get('reviews')):
        raise ValueError('Manifest and release review provenance differ')
    requests = json.loads(Path(snapshot['path']).read_text())['requests']
    actual = []
    for row in requests:
        if (row.get('experiment_id') != 'EXP-0063' or not row.get('answer')
                or type(row.get('version')) is not int or type(row.get('answer_version')) is not int
                or row['answer_version'] < 1 or not row.get('source_binding_sha256')):
            raise ValueError('Missing exact saved review answer/version/binding')
        actual.append(dict(request_id=row['id'], version=row['version'], answer_version=row['answer_version']))
    declared = release.get('reviews', [])
    if (len(actual) != 8 or len({r['request_id'] for r in actual}) != 8
            or sorted(actual, key=lambda r:r['request_id']) != sorted(declared, key=lambda r:r['request_id'])):
        raise ValueError('Release must bind all eight exact saved review versions')
    return release


def validate_config(config):
    fixed = dict(model='torchvision.models.video.r3d_18', pretrained='R3D_18_Weights.KINETICS400_V1',
                 frames=8, sample_fps=3, image_size=112, seed=6301, accumulation=4, epochs=10,
                 learning_rate=1e-4, weight_decay=1e-4, threshold=.5,
                 selection='minimum_validation_cross_entropy', precision='amp_float16',
                 production_integration=False, minimum_gpu_free_mib=6144)
    if any(config.get(k) != v for k,v in fixed.items()) or config.get('batch_size') not in (1,2,4):
        raise ValueError('Only the frozen first-training configuration is supported')


def prepared_entries(prepared_dir, manifest_path, config_path, rows, verify=True):
    prepared = json.loads((Path(prepared_dir)/'prepared.json').read_text())
    if prepared['manifest_sha256'] != sha(manifest_path) or prepared['config_sha256'] != sha(config_path):
        raise ValueError('Prepared clips have different labels or preprocessing')
    entries = {}
    for row in rows:
        entry = prepared['clips'][row['clip_id']]
        if verify and sha(entry['path']) != entry['sha256']:
            raise ValueError('Prepared pixels changed')
        entries[row['clip_id']] = entry['path']
    return entries


def partition_rows(manifest, mode):
    # Smoke must not load, hash, decode or score any test pixels.
    selected = [r for r in manifest['clips'] if mode != 'smoke' or r['split'] != 'test']
    if mode == 'smoke':
        bounded = []
        for split, per_class in (('train',16),('validation',2)):
            for label in (0,1):
                rows = [r for r in selected if r['split'] == split and r['label'] == label]
                if len(rows) < per_class:
                    raise ValueError('Insufficient real train/validation clips for full smoke microbatch/accumulation')
                bounded.extend(rows[:per_class])
        selected = bounded
    return selected


def evaluation_report(scores, rows, held_out):
    by_id = {r['clip_id']:r for r in rows}
    result = {}
    for cohort in ('same_place','heldout_place'):
        subset = [s for s in scores if (by_id[s['clip_id']]['location'] in held_out) == (cohort == 'heldout_place')]
        metadata = [by_id[s['clip_id']] for s in subset]
        subtypes = {}
        for action in sorted({r.get('action_class','unspecified') for r in metadata}):
            action_scores = [s for s in subset if by_id[s['clip_id']].get('action_class','unspecified') == action]
            action_metrics = metrics(action_scores)
            negatives = action_metrics['fp'] + action_metrics['tn']
            subtypes[action] = dict(clips=len(action_scores),tp=action_metrics['tp'],fn=action_metrics['fn'],
                fp=action_metrics['fp'],tn=action_metrics['tn'],recall=action_metrics['recall'],
                false_positive_rate=action_metrics['fp']/negatives if negatives else None,
                scope='official_actor_annotation_reference_only',human_precision=None)
        result[cohort] = dict(annotation_reference=metrics(subset), by_action_class=subtypes, clips=len(subset),
            sources=len({r['source_id'] for r in metadata}),
            event_groups=len({r['event_group'] for r in metadata}))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--baseline-lock', type=Path, required=True)
    parser.add_argument('--split-manifest', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['preflight', 'prepare', 'smoke', 'train'], default='preflight')
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--weights', type=Path)
    parser.add_argument('--weights-sha256')
    parser.add_argument('--review-release', type=Path, required=True)
    parser.add_argument('--review-release-sha256', required=True)
    parser.add_argument('--queue-config', type=Path)
    parser.add_argument('--queue-config-sha256')
    parser.add_argument('--queue-attempt')
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text())
    baseline = json.loads(args.baseline_lock.read_text())
    config = json.loads(args.config.read_text())
    source_split = json.loads(args.split_manifest.read_text())
    validate_config(config)
    if manifest.get('config_sha256') != sha(args.config):
        raise ValueError('Clip manifest preprocessing config binding differs')
    validate_release(args.manifest, args.split_manifest, args.review_release, args.review_release_sha256)
    if len(baseline.get('regression_only_videos', [])) != 45 or len({r['sha256'] for r in baseline['regression_only_videos']}) != 45:
        raise ValueError('All45 regression source hashes are required')
    if sha(args.split_manifest) != 'bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499':
        raise ValueError('Frozen combined split v3 required')
    if manifest.get('baseline_lock_sha256') != sha(args.baseline_lock):
        raise ValueError('Clip manifest baseline binding differs')
    if manifest.get('source_split_sha256') != sha(args.split_manifest):
        raise ValueError('Clip manifest is not bound to the original-video split')
    counts = validate_manifest(manifest, baseline, config['frames'], source_split)
    selected = partition_rows(manifest, args.mode)
    if args.mode in ('smoke', 'train'):
        # Validate live authorization and inherited canonical lock before creating output/importing torch.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from orchestration.action_training_command import runner_guard
        runner_guard(args)
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output/'contract.json', {'argv': sys.argv, 'manifest_sha256': sha(args.manifest),
                                     'baseline_sha256': sha(args.baseline_lock), 'config': config,
                                     'script_sha256': sha(__file__), 'counts': counts,
                                     'review_release_sha256': args.review_release_sha256,
                                     'queue_attempt': args.queue_attempt, 'mode': args.mode})
    if args.mode in ('preflight','prepare'):
        for path, expected in {(r[k], r[h]) for r in selected
                               for k,h in (('source_path','source_sha256'),('label_path','label_sha256'))}:
            if sha(path) != expected:
                raise ValueError('Source/annotation changed: ' + path)
    if args.mode == 'preflight':
        save(args.output/'result.json', {'status': 'preflight_passed', 'training': 0})
        return
    import numpy as np
    if args.mode == 'prepare':
        paths = {}
        for i, row in enumerate(manifest['clips']):
            path = args.output/f'clip-{i:06d}.npy'
            np.save(path, decode_clip(row, config['image_size']))
            paths[row['clip_id']] = {'path': str(path.resolve()), 'sha256': sha(path)}
        save(args.output/'prepared.json', {'manifest_sha256': sha(args.manifest),
                                         'config_sha256': sha(args.config), 'clips': paths})
        return
    # This script is not a queue registration and cannot launch a GPU job directly.
    # A reviewed canonical queue adapter must supply the inherited GPU lock.
    if not args.weights or not args.weights_sha256 or sha(args.weights) != args.weights_sha256:
        raise ValueError('Pinned pretrained checkpoint is required')
    if args.weights_sha256 != 'b3b3357ead25631ec9c57362ff2128a92d0427e01e2cd184951a44380c3f2e9d':
        raise ValueError('Expected official R3D-18 KINETICS400_V1 checkpoint')
    arrays = prepared_entries(args.prepared, args.manifest, args.config, selected)
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    import torch
    import torchvision
    free_bytes, _ = torch.cuda.mem_get_info()
    if free_bytes < config['minimum_gpu_free_mib'] * 1024**2:
        raise ValueError('GPU resource gate failed')
    torch.set_num_threads(2)
    random.seed(config['seed']); np.random.seed(config['seed']); torch.manual_seed(config['seed'])
    torch.cuda.manual_seed_all(config['seed'])
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True)
    model = torchvision.models.video.r3d_18(weights=None)
    model.load_state_dict(torch.load(args.weights, weights_only=True, map_location='cpu'))
    model.fc = torch.nn.Linear(model.fc.in_features, 2)
    model = model.cuda()
    mean = torch.tensor([.43216, .394666, .37645]).view(1,3,1,1,1).cuda()
    std = torch.tensor([.22803, .22145, .216989]).view(1,3,1,1,1).cuda()
    def batch(rows):
        data = np.stack([np.load(arrays[r['clip_id']], allow_pickle=False) for r in rows])
        x = torch.from_numpy(data).permute(0,4,1,2,3).cuda().float()/255
        return (x-mean)/std, torch.tensor([r['label'] for r in rows], device='cuda')
    def evaluate(rows):
        model.eval(); scores=[]; loss=0.
        with torch.no_grad():
            for i in range(0,len(rows),config['batch_size']):
                subset=rows[i:i+config['batch_size']]; x,y=batch(subset)
                with torch.autocast('cuda', dtype=torch.float16): logits=model(x)
                loss+=torch.nn.functional.cross_entropy(logits.float(),y,reduction='sum').item()
                for row, score in zip(subset,logits.float().softmax(-1)[:,1].cpu().tolist()):
                    scores.append({'clip_id':row['clip_id'],'label':row['label'],'score':score,'source_id':row['source_id'],
                        'event_group':row['event_group'],'location':row['location'],
                        'sample_pts':row['sample_pts'],'label_evidence':row['label_evidence'],
                        'action_class':row.get('action_class'),'actor_id':row['actor_id']})
        average = loss/len(rows)
        if not math.isfinite(average):
            raise ValueError('Nonfinite evaluation loss')
        return average, scores
    train=[r for r in selected if r['split']=='train']
    val=[r for r in selected if r['split']=='validation']
    test=[r for r in selected if r['split']=='test']
    optimizer=torch.optim.AdamW(model.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
    scaler=torch.amp.GradScaler('cuda'); best=float('inf'); history=[]; optimizer_steps=0
    save(args.output/'environment.json', {'torch':torch.__version__,'torchvision':torchvision.__version__,
        'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(),'pretrained_sha256':sha(args.weights)})
    for epoch in range(1 if args.mode == 'smoke' else config['epochs']):
        random.shuffle(train); model.train(); optimizer.zero_grad(set_to_none=True)
        batches=[train[i:i+config['batch_size']] for i in range(0,len(train),config['batch_size'])]
        total=0.
        for i, rows in enumerate(batches):
            x,y=batch(rows)
            group_start=(i//config['accumulation'])*config['accumulation']
            group_samples=sum(len(b) for b in batches[group_start:group_start+config['accumulation']])
            with torch.autocast('cuda',dtype=torch.float16):
                loss=torch.nn.functional.cross_entropy(model(x),y,reduction='sum')
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite real training loss')
            total+=loss.item(); scaler.scale(loss/group_samples).backward()
            if (i+1)%config['accumulation']==0 or i+1==len(batches):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(),float('inf'),error_if_nonfinite=True)
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True); optimizer_steps+=1
        val_loss,scores=evaluate(val)
        if not math.isfinite(val_loss):
            raise ValueError('Nonfinite real validation loss')
        row={'epoch':epoch+1,'train_loss':total/len(train),'validation_loss':val_loss,
             'validation':metrics(scores),'actual_microbatch_sizes':[len(b) for b in batches],
             'optimizer_steps':optimizer_steps,'peak_gpu_bytes':torch.cuda.max_memory_allocated()}
        history.append(row);save(args.output/'history.json',history)
        save(args.output/f'validation-epoch-{epoch+1:03d}-scores.json',scores)
        checkpoint={'model':model.state_dict(),'optimizer':optimizer.state_dict(),'scaler':scaler.state_dict(),
                    'epoch':epoch+1,'config':config,'manifest_sha256':sha(args.manifest),
                    'rng_torch':torch.get_rng_state(),'rng_cuda':torch.cuda.get_rng_state_all(),
                    'rng_python':random.getstate(),'rng_numpy':np.random.get_state()}
        torch.save(checkpoint,args.output/'last.pt')
        if val_loss<best:
            best=val_loss;torch.save(checkpoint,args.output/'best.pt')
            save(args.output/'best-validation-scores.json',scores)
    if args.mode == 'smoke':
        save(args.output/'result.json', dict(status='smoke_passed', real_train_clips=len(train),
            real_validation_clips=len(val), test_accessed=False, epochs=1, training_complete=False,
            actual_microbatch_sizes=[len(b) for b in batches], accumulation=config['accumulation'],
            optimizer_steps=optimizer_steps, manifest_sha256=sha(args.manifest), config_sha256=sha(args.config)))
        return
    # Locally produced trusted checkpoint. Test data is evaluated only after selection.
    checkpoint=torch.load(args.output/'best.pt',weights_only=False,map_location='cpu')
    model.load_state_dict(checkpoint['model']);_,scores=evaluate(test)
    save(args.output/'test-scores.json',scores)
    save(args.output/'test-failures.json',[dict(r,failure_type='annotation_reference_false_positive'
        if r['label']==0 else 'annotation_reference_false_negative')
        for r in scores if (r['score'] >= .5) != bool(r['label'])])
    save(args.output/'result.json',{'status':'trained','best_epoch':checkpoint['epoch'],
        'test':evaluation_report(scores,test,set(manifest.get('held_out_test_locations',[]))),
        'human_precision':None,'human_f1':None,'weights_sha256':sha(args.output/'best.pt'),
        'pipeline_comparison':'not_executed','intrusion_completion_accuracy':None})


if __name__ == '__main__':
    main()
