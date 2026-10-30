"""After all six generations, audit saved responses and render local evidence.

No inference or new annotation. All generated images/raw summaries stay local.
Historical answers are read only after the new run is confirmed complete.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import numpy as np
    from PIL import Image, ImageDraw
    from mvp.exp0038 import BASELINE_OUTPUT, compare_saved_rows, summarize_rows
    from mvp.exp0034_appearance import load_manifest, load_crop

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    folder = args.attempt_dir.resolve()
    out = args.output.resolve()
    if not folder.is_relative_to(ROOT/'outputs/mvp0001/EXP-0038'):
        raise ValueError('Expected an EXP-0038 execution directory')
    if not out.is_relative_to(ROOT/'outputs/exp0038') or out.exists():
        raise ValueError('Fresh local review directory required')
    summary = json.loads((folder/'exp0038_summary.json').read_text())
    new = json.loads((folder/'appearance_results.json').read_text())
    if summary['model_loads'] != 1 or new['partial'] is not False or len(new['completed']) != 6:
        raise ValueError('Six completed generations required before opening baseline answers')
    old = json.loads(BASELINE_OUTPUT.read_text())
    if old['partial'] is not False:
        raise ValueError('Incomplete historical baseline')
    comparisons = compare_saved_rows(old['completed'], new['completed'])
    manifest = load_manifest()
    out.mkdir(parents=True)
    rows = []
    for number, (pair, before, after, comparison) in enumerate(zip(
            manifest['pairs'], old['completed'], new['completed'], comparisons), 1):
        if not pair['pair_id'] == before['pair_id'] == after['pair_id']:
            raise ValueError('Pair order changed')
        board = Image.new('RGB', (280*after['images'], 1690), '#101722')
        draw = ImageDraw.Draw(board)
        draw.text((10, 8), f'P{number} LOCAL ONLY: same native inputs / actual 2B / actual 8B NF4', fill='white')
        draw.text((10, 28), 'Model statements are not identity truth. Display resizing only; original PTS below.', fill='#ffd880')
        arrays_equal = []
        for j, native in enumerate(pair['before_images']+pair['after_images']):
            a = np.load(BASELINE_OUTPUT.parent/before['directory']/f'processor_rgb_{j:02d}.npy', allow_pickle=False)
            b = np.load(folder/after['directory']/f'processor_rgb_{j:02d}.npy', allow_pickle=False)
            for array, result in ((a, before), (b, after)):
                if hashlib.sha256(array.tobytes()).hexdigest() != result['input_metadata']['processor_rgb_sha256'][j]:
                    raise ValueError('Stored actual processor RGB differs')
            arrays_equal.append(bool(np.array_equal(a, b)))
            for row, (array, label) in enumerate(((load_crop(native), 'native'), (a, 'actual 2B'), (b, 'actual 8B NF4'))):
                x, y = j*280+5, 55+row*490
                side = 'A' if j < len(pair['before_images']) else 'B'
                draw.text((x, y), f'{side} {j+1}: {label} {array.shape[1]}x{array.shape[0]}\nPTS {native["pts"]:.6f}', fill='white')
                pic = Image.fromarray(array)
                scale = min(265/pic.width, 430/pic.height)
                pic = pic.resize((round(pic.width*scale), round(pic.height*scale)), Image.Resampling.NEAREST)
                board.paste(pic, (x+(265-pic.width)//2, y+42))
        strict = []
        for j, (label, result) in enumerate((('2B BF16', before), ('8B NF4', after))):
            try:
                strict.append(isinstance(json.loads(result['raw_response']), dict))
            except ValueError:
                strict.append(False)
            parsed = result['parsed']
            draw.text((10, 1535+j*65), label+': '+json.dumps(parsed['comparison'])+
                      f'\nparser valid={parsed["valid"]}; raw JSON={strict[-1]}; generation={result["timing"]["generation_seconds"]:.3f}s', fill='white')
        name = f'p{number}-native-2b-8b.jpg'
        board.save(out/name, quality=93)
        prompt_equal = (BASELINE_OUTPUT.parent/before['directory']/'expanded_prompt.txt').read_bytes() == (folder/after['directory']/'expanded_prompt.txt').read_bytes()
        rows.append(dict(comparison, processor_rgb_exact=arrays_equal,
                         expanded_prompt_bytes_equal=prompt_equal,
                         strict_json_baseline=strict[0], strict_json_candidate=strict[1],
                         local_panel=name, new_identity_ground_truth=False))
    result = dict(baseline=summarize_rows(old['completed']), candidate=summarize_rows(new['completed']),
                  pairs=rows, semantic_audit='Reuse historical visual drafts separately; no new identity truth',
                  inference_calls=0, model_input_edits=0)
    (out/'comparison.local.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'pairs':6, 'processor_equal':all(all(r['processor_rgb_exact']) for r in rows),
                      'expanded_prompts_equal':all(r['expanded_prompt_bytes_equal'] for r in rows),
                      'output':str(out.relative_to(ROOT))}))


if __name__ == '__main__':
    main()
