"""Local EXP-0031 comparison boards from stored features; transforms only, no inference.

Run from the repository root with the existing pinned ReID dependency paths.
All images, coordinates, features and manual drafts stay under ignored outputs/.
"""
import argparse
from fractions import Fraction
import hashlib
import html
import inspect
import json
import math
import os
from pathlib import Path
import textwrap
from types import SimpleNamespace

import numpy as np

from .tracklet_linking import unit_features


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def fresh_output(path, root=Path('outputs')):
    path = Path(path)
    if (path.exists() or path.is_symlink() or
            any(p.is_symlink() for p in path.parents) or
            not path.resolve().is_relative_to(root.resolve())):
        raise FileExistsError('Use a fresh non-symlink directory under local outputs/')
    path.mkdir(parents=True, exist_ok=False)
    return path


def cosine_matrix(left, right):
    return np.clip(unit_features(left) @ unit_features(right).T, -1, 1)


def manual_draft(ids):
    return dict(status='unreviewed', identity_ground_truth_created=False,
                field_semantics=dict(before_single_person_crop='baseline representative set',
                    after_single_person_crop='alternative representative set'),
                cases=[dict(id=key, same_person='unknown',
                    before_single_person_crop='unknown', after_single_person_crop='unknown',
                    raw_id_mix_suspected='unknown', reason='Not yet manually reviewed',
                    endpoint_detail={condition:{end:'unknown' for end in ('source_single_person','target_single_person','same_person')}
                                     for condition in ('baseline','alternative')}) for key in ids])


def verify_measurement(row, segment, cached):
    """Reject wrong raw ID, cache box, score, or original PTS before drawing."""
    if row['raw_id'] != segment['raw_id'] or row not in segment['rows']:
        raise ValueError('Representative differs from its observed tracklet')
    frame = cached[row['frame_index']]
    i = row['cache_index']
    width, height = frame['source_size']
    expected = np.clip(np.asarray(frame['boxes'][i]) / [width, height, width, height], 0, 1)
    if (not np.allclose(expected, row['bbox'], atol=1e-7, rtol=0) or
            not math.isclose(frame['scores'][i], row['score'], abs_tol=1e-7, rel_tol=0) or
            row['pts'] != frame['pts'] or
            abs(float(frame['native_pts'] * Fraction(frame['time_base'])) - row['pts']) > 1e-8):
        raise ValueError('Representative frame/bbox/score/PTS binding mismatch')
    return frame


def official_transforms(compatibility):
    """Import only pinned transform methods, never instantiate ReID or a backend."""
    os.environ.update(CUDA_VISIBLE_DEVICES='', YOLO_AUTOINSTALL='false',
                      YOLO_OFFLINE='true', ULTRALYTICS_OFFLINE='true')
    import torch
    from ultralytics.trackers.utils.reid import ReID
    from ultralytics.utils import ops
    from ultralytics.utils.plotting import save_one_box
    if sha(inspect.getfile(ReID)) != compatibility['upstream_reid']['sha256']:
        raise ValueError('Pinned official ReID source mismatch')
    if torch.cuda.is_initialized():
        raise RuntimeError('Review renderer must not initialize CUDA')
    torch.set_num_threads(2)
    sig = inspect.signature(save_one_box)
    if sig.parameters['gain'].default != 1.02 or sig.parameters['pad'].default != 10:
        raise ValueError('Official gain/pad contract changed')
    preprocessor = SimpleNamespace(imgsz=(448, 448), device=torch.device('cpu'), fp16=False)

    def transform(bgr, normalized_box):
        height, width = bgr.shape[:2]
        box = np.asarray(normalized_box, dtype=np.float64) * [width, height, width, height]
        xywh = box.copy()
        xywh[2:] -= xywh[:2]
        xywh[:2] += xywh[2:] / 2
        crop = ReID._crop_detections(bgr, xywh[None, :])[0]
        tensor = ReID._crops_to_tensor(preprocessor, [crop])
        xyxy = ops.xywh2xyxy(torch.from_numpy(xywh[None, :]))[0].to(torch.float32)
        expanded = ops.xyxy2xywh(xyxy.view(-1, 4))
        expanded[:, 2:] = expanded[:, 2:] * 1.02 + 10
        rect = ops.clip_boxes(ops.xywh2xyxy(expanded).long(), bgr.shape)[0].tolist()
        x1, y1, x2, y2 = rect
        if not np.array_equal(crop, bgr[y1:y2, x1:x2]):
            raise ValueError('Official crop does not match annotated expanded rectangle')
        if tensor.shape != (1, 3, 448, 448) or tensor.device.type != 'cpu' or tensor.dtype != torch.float32:
            raise ValueError('Official tensor contract changed')
        pixels = np.rint(tensor[0].permute(1, 2, 0).numpy() * 255).clip(0, 255).astype(np.uint8)
        return box.tolist(), rect, crop[..., ::-1], pixels, tensor.numpy().tobytes()

    return transform, dict(reid_source_sha256=sha(inspect.getfile(ReID)),
        plotting_source_sha256=sha(inspect.getfile(save_one_box)), gain=1.02, pad=10,
        channel_order='BGR crop -> RGB', resize='official torch bilinear448 align_corners=False',
        tensor='CPU FP32 BCHW /255', model_constructions=0, encoder_forwards=0,
        note='Reconstructed actual encoder preprocessing; not a historical tensor dump')


def decode_exact(video, schedule):
    import av
    native, time_base = schedule['native_pts'], Fraction(schedule['time_base'])
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        container.seek(native, stream=stream, backward=True)
        for frame in container.decode(stream):
            if frame.pts is None or frame.pts * frame.time_base < native * time_base:
                continue
            if frame.pts != native or frame.time_base != time_base:
                raise ValueError('Exact native source frame missing')
            bgr = frame.to_ndarray(format='bgr24')
            if list(bgr.shape[:2][::-1]) != schedule['source_size']:
                raise ValueError('Decoded frame dimensions mismatch')
            return bgr
    raise ValueError('Source video ended before required PTS')


def load_sources(prior_root, alternate_root, videos, caches):
    data, protected = {}, {}
    for v in ('030', '007'):
        prior = Path(prior_root) / f'track{v}' / 'v1'
        alternate = Path(alternate_root) / f'track{v}' / 'v1'
        names = {'segments': prior/'tracklets.json', 'old_reps': prior/'representatives.json',
            'old_features': prior/'features.local.json', 'old_associations': prior/'associations.json',
            'summary': prior/'summary.json', 'new_reps': alternate/'selected_representatives.json',
            'new_features': alternate/'alternative_features.local.json',
            'new_associations': alternate/'alternative_associations.json',
            'audit': alternate/'selection_audit.json', 'questions': alternate/'question_comparison.json',
            'warnings': alternate/'raw_id_appearance_warnings.json', 'provenance': alternate/'provenance.json'}
        for p in [*names.values(), videos[v], caches[v]]:
            protected[str(p)] = sha(p)
        d = {name: read(path) for name, path in names.items()}
        if (d['summary']['source_hashes']['video'] != protected[str(videos[v])] or
                d['summary']['source_hashes']['cache'] != protected[str(caches[v])]):
            raise ValueError('Source video/cache hashes differ from original run')
        for p, expected in d['provenance']['input_sha256'].items():
            if sha(p) != expected:
                raise ValueError('EXP31 source provenance mismatch')
        d.update(prior=prior, alternate=alternate, video=videos[v],
            cached=[json.loads(line) for line in Path(caches[v]).read_text().splitlines() if line.strip()])
        d['segments'] = {s['id']: s for s in d['segments']}
        for condition in ('old', 'new'):
            d[f'{condition}_features'] = d[f'{condition}_features']['features']
            for sid, endpoints in d[f'{condition}_reps'].items():
                for end, rows in endpoints.items():
                    if not 1 <= len(rows) <= 3 or len(rows) != len(d[f'{condition}_features'][sid][end]):
                        raise ValueError('Expected one to three bound representative features')
                    for row in rows:
                        verify_measurement(row, d['segments'][sid], d['cached'])
        data[v] = d
    return data, protected


class Renderer:
    def __init__(self, out, data, transform):
        from PIL import ImageFont
        self.out, self.data, self.transform = out, data, transform
        self.assets, self.frames = {}, {}
        self.font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
        (out/'assets').mkdir()
        (out/'cases').mkdir()

    def frame(self, v, row):
        key = v, row['frame_index']
        if key not in self.frames:
            self.frames[key] = decode_exact(self.data[v]['video'], self.data[v]['cached'][key[1]])
        return self.frames[key]

    def asset(self, v, sid, row, condition):
        from PIL import Image, ImageDraw
        key = f"{v}-f{row['frame_index']:06d}-d{row['cache_index']}"
        if key in self.assets:
            return self.assets[key]
        d = self.data[v]
        schedule = verify_measurement(row, d['segments'][sid], d['cached'])
        bgr = self.frame(v, row)
        box, expanded, crop_rgb, input_rgb, tensor_bytes = self.transform(bgr, row['bbox'])
        full = Image.fromarray(bgr[..., ::-1])
        draw = ImageDraw.Draw(full)
        draw.rectangle(tuple(box), outline='#ffdf32', width=4)
        draw.rectangle(tuple(expanded), outline='#ff66bb', width=3)
        draw.text((box[0], max(0, box[1]-24)), f"raw {row['raw_id']} {sid} PTS {row['pts']:.6f}",
                  font=self.font, fill='yellow', stroke_width=2, stroke_fill='black')
        x1,y1,x2,y2 = expanded
        zoom = full.crop((max(0,x1-100), max(0,y1-65), min(full.width,x2+100), min(full.height,y2+65)))
        tight_box = (max(0,math.floor(box[0])), max(0,math.floor(box[1])),
                     min(full.width,math.ceil(box[2])), min(full.height,math.ceil(box[3])))
        tight = Image.fromarray(bgr[..., ::-1]).crop(tight_box)
        paths = {}
        for label, im in [('source',full), ('zoom',zoom), ('expanded',Image.fromarray(crop_rgb)),
                          ('input448',Image.fromarray(input_rgb)), ('tight',tight)]:
            path = f'assets/{key}-{label}.png'
            im.save(self.out/path)
            paths[label] = path
        stored = d['prior']/'representatives'/f"f{row['frame_index']:06d}-d{row['cache_index']}.jpg"
        if not stored.exists():
            stored = d['alternate']/'new_representative_crops'/f"frame{row['frame_index']:06d}_cache{row['cache_index']:03d}.jpg"
        if not stored.exists():
            raise ValueError('No original saved tight representative JPEG for selected crop')
        with Image.open(stored) as im:
            if im.size != tight.size:
                raise ValueError('Stored tight representative extent differs from bound bbox')
            path = f'assets/{key}-stored-tight.png'
            im.convert('RGB').save(self.out/path)
            paths['stored_tight'] = path
        info = dict(key=key, video=v, tracklet=sid, raw_id=row['raw_id'], pts=row['pts'],
            frame_index=row['frame_index'], cache_index=row['cache_index'],
            native_pts=schedule['native_pts'], time_base=schedule['time_base'],
            bbox_normalized=row['bbox'], bbox_pixels=box, expanded_box_pixels=expanded,
            tight_box_pixels=list(tight_box), crop_hw=list(crop_rgb.shape[:2]),
            source_bgr_sha256=hashlib.sha256(bgr.tobytes()).hexdigest(),
            tensor_sha256=hashlib.sha256(tensor_bytes).hexdigest(),
            stored_tight_source=str(stored), stored_tight_sha256=sha(stored), paths=paths,
            file_sha256={name:sha(self.out/path) for name,path in paths.items()})
        self.assets[key] = info
        return info

    def board(self, key, v, left, right, ends, condition, similarity, status, risks):
        from PIL import Image, ImageDraw
        d = self.data[v]
        board = Image.new('RGB', (1920, 1220), '#111b29')
        draw = ImageDraw.Draw(board)
        def text(x,y,s,fill='#e9eef7'):
            draw.text((x,y),s,font=self.font,fill=fill)
        text(15,10,f'{key} E01_{v} {condition} | {left} -> {right} | cosine median {similarity:.6f} | {status}')
        text(15,40,'Stored feature cosine is NOT identity probability; all identity/crop-person-count review fields remain unknown.')
        text(15,70,'Yellow: measured bbox. Pink: official gain1.02 + pad10 crop. Reconstructed preprocessing only; no forward.')
        text(15,100,'Source full context + bbox / display zoom / saved tight JPEG (NOT encoder input) / actual preprocessing RGB 448x448')
        text(15,130,'Priority: Q02 first raw11 drift/mixing concern; Q08 multiple-person crop concern. Geometry flags are proxies.')
        reps = d[f'{condition}_reps']
        assets = []
        for offset, (sid,end) in enumerate(zip((left,right),ends)):
            for j,row in enumerate(reps[sid][end]):
                info = self.asset(v,sid,row,condition)
                assets.append(info['key'])
                x = (offset*3+j)*320+8
                text(x,175,f'{"source" if offset==0 else "target"} {end} {j+1} {sid} raw{row["raw_id"]}')
                text(x,200,f'PTS {row["pts"]:.6f}')
                text(x,225,f'native {info["native_pts"]} * {info["time_base"]}')
                r = risks.get((sid,end,row['frame_index'],row['cache_index']))
                names={'overlap_warning':'overlap','abrupt_extent_warning':'extent','small_relative_box_warning':'small'}
                label='flags: '+(','.join(names[k] for k in names if r.get(k)) or 'none (proxy only)' if r else 'unknown / absent new audit')
                for line_no,line in enumerate(textwrap.wrap(label,30)):
                    text(x,250+line_no*18,line,'#ffd878')
                for label,y,w,h in [('source',290,304,171),('zoom',490,304,205),('stored_tight',735,304,120),('input448',900,304,304)]:
                    if label=='stored_tight':text(x,y-25,'Saved tight JPEG: NOT encoder input')
                    if label=='input448':text(x,y-25,'Official RGB encoder input reconstruction')
                    with Image.open(self.out/info['paths'][label]) as im:
                        im=im.copy();im.thumbnail((w,h),Image.Resampling.LANCZOS)
                        board.paste(im,(x+(w-im.width)//2,y))
        path=f'cases/{key}-{condition}.jpg'
        board.save(self.out/path,quality=95)
        return dict(image=path,assets=assets,similarity=similarity,status=status)


def render(out, data, protected, protocol, compatibility):
    from PIL import Image, ImageDraw
    transform, transform_provenance = official_transforms(compatibility)
    out=fresh_output(out)
    renderer=Renderer(out,data,transform)
    cases=[]
    for v,d in data.items():
        risks={(sid,end,r['frame_index'],r['cache_index']):r['risk']
               for sid,ends in d['audit'].items() for end,a in ends.items() for r in a['selected']}
        questions=list(d['questions'])
        old_links={(a['before'],a['after']):a for a in d['old_associations']['links']}
        new_links={(a['before'],a['after']):a for a in d['new_associations']['links']}
        for pair,link in new_links.items():
            if link['status']=='accepted' and old_links[pair]['status']!='accepted':
                left,right=pair
                q=dict(question=f'A{1+sum(c.get("kind")=="new_algorithm_acceptance" for c in cases):02d}',
                    before_tracklet=left,after_tracklet=right,
                    before_raw_id=d['segments'][left]['raw_id'],after_raw_id=d['segments'][right]['raw_id'],
                    baseline_similarity=float(np.median(cosine_matrix(d['old_features'][left]['tail'],d['old_features'][right]['head']))),
                    alternate_similarity=float(np.median(cosine_matrix(d['new_features'][left]['tail'],d['new_features'][right]['head']))),
                    baseline_status=old_links[pair]['status'],alternate_status=link['status'],
                    adopted=False,identity_verified=False,requires_human_review=True,
                    kind='new_algorithm_acceptance')
                questions.append(q)
        # Q02 and Q08 lead the local page, but preserve original question IDs.
        for q in sorted(questions,key=lambda q:(q['question'] not in ('Q02','Q08'),q['question'])):
            key,left,right=q['question'],q['before_tracklet'],q['after_tracklet']
            case=dict(q,video=v,kind=q.get('kind','original_question'),conditions={},
                      baseline_decision=old_links.get((left,right)),alternate_decision=new_links.get((left,right)))
            for cond,prefix in [('old','baseline'),('new','alternate')]:
                matrix=cosine_matrix(d[f'{cond}_features'][left]['tail'],d[f'{cond}_features'][right]['head'])
                similarity=float(np.median(matrix))
                if abs(similarity-q[f'{prefix}_similarity'])>1e-10:
                    raise ValueError('Stored question similarity inconsistent with bound features')
                decision=(old_links if cond=='old' else new_links).get((left,right))
                status=q[f'{prefix}_status']+(f' ({decision.get("reason")})' if decision else '')
                rec=renderer.board(key,v,left,right,('tail','head'),cond,similarity,status,risks)
                rec['cosine_matrix']=matrix.tolist()
                case['conditions'][cond]=rec
            cases.append(case)
    for c in protocol['controls']:
        v,left,right=c['video'],c['before_tracklet'],c['after_tracklet'];d=data[v]
        if not c['simultaneous_observations']:
            raise ValueError('Preselected control lacks simultaneous observed source boxes')
        if sha(d['prior']/'tracklets.json') != c['tracklets_sha256']:
            raise ValueError('Control protocol tracklets changed after preselection')
        observed=c['simultaneous_observations']
        if observed[0]['frame_index'] != observed[1]['frame_index'] or observed[0]['raw_id']==observed[1]['raw_id']:
            raise ValueError('Temporal negative controls must be distinct simultaneous raw IDs')
        case=dict(c,kind='temporal_negative_control_candidate',identity_verified=False,conditions={},
            note='Different simultaneously observed raw IDs require manual distinct-person confirmation. Head reps may be at different PTS. Temporal overlap excludes association regardless of cosine.')
        # Same-frame two-box context, chosen before inspecting features.
        from PIL import ImageDraw
        row=c['simultaneous_observations'][0]
        im=Image.fromarray(renderer.frame(v,row)[...,::-1]);draw=ImageDraw.Draw(im)
        for sid,r,color in zip((left,right),c['simultaneous_observations'],('yellow','cyan')):
            verify_measurement(r,d['segments'][sid],d['cached'])
            box=np.array(r['bbox'])*[im.width,im.height,im.width,im.height]
            draw.rectangle(tuple(box),outline=color,width=4)
            draw.text((box[0],max(0,box[1]-24)),f'{sid} raw{r["raw_id"]}',font=renderer.font,fill=color,stroke_width=2,stroke_fill='black')
        path=f'cases/{c["id"]}-simultaneous-source.png';im.save(out/path);case['simultaneous_source']=path
        for cond in ('old','new'):
            matrix=cosine_matrix(d[f'{cond}_features'][left]['head'],d[f'{cond}_features'][right]['head'])
            rec=renderer.board(c['id'],v,left,right,('head','head'),cond,float(np.median(matrix)),
                               'NOT A LINK CANDIDATE: overlapping observed time',{})
            rec['cosine_matrix']=matrix.tolist();case['conditions'][cond]=rec
        cases.append(case)
    cases.sort(key=lambda c:(c.get('question',c.get('id')) not in ('Q02','Q08'),c.get('question',c.get('id'))))
    write(out/'manual-review-draft.json',manual_draft([c.get('question',c.get('id')) for c in cases]))
    write(out/'manual-review-schema.json',dict(type='object',required=['cases'],properties=dict(cases=dict(type='array',items=dict(type='object',required=['id','same_person','before_single_person_crop','after_single_person_crop','raw_id_mix_suspected','reason'],properties={**{k:dict(type='string',enum=['yes','no','unknown']) for k in ('same_person','before_single_person_crop','after_single_person_crop','raw_id_mix_suspected')},'reason':dict(type='string'),'id':dict(type='string')})))))
    gallery=[]
    overview=Image.new('RGB',(1920,len(cases)*360),'#111b29')
    draw=ImageDraw.Draw(overview)
    for i,c in enumerate(cases):
        key=c.get('question',c.get('id'));gallery.append(f'<h2 id="{key}">{key} E01_{c["video"]}</h2>')
        draw.text((10,i*360),f'{key} E01_{c["video"]} old / new | identity unknown',font=renderer.font,fill='white')
        if c.get('simultaneous_source'):gallery.append(f'<a href="{c["simultaneous_source"]}">Simultaneous source context, both observed boxes</a>')
        for j,cond in enumerate(('old','new')):
            path=c['conditions'][cond]['image'];gallery.append(f'<p>{cond}</p><a href="{path}"><img src="{path}" loading="lazy"></a>')
            with Image.open(out/path) as im:
                im.thumbnail((950,320));overview.paste(im,(j*960,i*360+30))
    overview.save(out/'overview.jpg',quality=95)
    assets_html=''.join(f'<details><summary>{html.escape(key)}</summary>'+''.join(f'<p>{label}</p><a href="{path}"><img src="{path}" loading="lazy"></a>' for label,path in a['paths'].items())+'</details>' for key,a in renderer.assets.items())
    page='<!doctype html><meta charset="utf-8"><title>EXP-0031 local review</title><style>body{background:#111b29;color:#eee;font:18px sans-serif;margin:24px}img{max-width:100%}a{color:#91d5ff}</style><h1>EXP-0031 local comparison review</h1><p>Q02 raw11 and Q08 crop mixing are highest priority. Cosine is not identity probability; geometry risk flags are not visual ground truth. No identities have been approved.</p><p>Yellow observed bbox / pink gain1.02 pad10 actual encoder crop. Tight saved JPEG is not the encoder input. Input448 reconstructs official RGB bilinear preprocessing, not a historical tensor dump. All images and coordinates are local only.</p><p>Overlapping observed intervals exclude controls from linking. Control head crops can have different PTS; same-time context is linked separately.</p><p><a href="manual-review-draft.json">Unknown manual draft</a> | <a href="manual-review-schema.json">Review schema</a> | <a href="manifest.json">Provenance / matrices / flags</a> | <a href="overview.jpg">Overview</a></p><img src="overview.jpg">'+''.join(gallery)+'<h2>Every full asset</h2>'+assets_html
    with (out/'index.html').open('x',encoding='utf-8') as stream:stream.write(page)
    if any(sha(p)!=expected for p,expected in protected.items()):
        raise ValueError('Source files changed while assembling review')
    manifest=dict(experiment='EXP-0031',status='materials_complete_manual_review_pending',
        transform=transform_provenance,control_protocol=protocol,cases=cases,assets=renderer.assets,
        selection_audit={v:d['audit'] for v,d in data.items()},
        raw_id_appearance_warnings={v:d['warnings'] for v,d in data.items()},
        source_sha256=protected,source_files_unchanged=True,identity_ground_truth_created=False,
        renderer_source_sha256=sha(__file__),output_sha256={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
    write(out/'manifest.json',manifest)
    return dict(output=str(out),questions=8,controls=len(protocol['controls']),unique_crops=len(renderer.assets),
                boards=len(cases)*2,encoder_forwards=0,identity_review='unknown')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prior-root',type=Path,default=Path('outputs/exp0029'))
    p.add_argument('--alternate-root',type=Path,default=Path('outputs/exp0031'))
    p.add_argument('--output',type=Path,default=Path('outputs/exp0031/review-v1'))
    p.add_argument('--control-protocol',type=Path,default=Path('runtime/EXP-0031/material-control-protocol.json'))
    p.add_argument('--encoder-compatibility',type=Path,default=Path('runtime/EXP-0029/encoder-compatibility.json'))
    a=p.parse_args()
    videos={v:Path(f'data/TS_침입/E01_{v}.mp4') for v in ('030','007')}
    caches={'030':Path('outputs/cv_phase2d/cache030/person_cache.jsonl'),
            '007':Path('outputs/exp0029/cache007/person_cache.jsonl')}
    protocol=read(a.control_protocol)  # frozen before any similarities are computed
    data,protected=load_sources(a.prior_root,a.alternate_root,videos,caches)
    protected[str(a.control_protocol)]=sha(a.control_protocol)
    protected[str(a.encoder_compatibility)]=sha(a.encoder_compatibility)
    print(json.dumps(render(a.output,data,protected,protocol,read(a.encoder_compatibility)),allow_nan=False))


if __name__=='__main__':
    main()
