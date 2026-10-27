"""Probe public SteelBench metadata only; never download media or use credentials."""
import hashlib
import json
import platform
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/steelbench_audit/access'
BASE = 'https://huggingface.co'
ENDPOINTS = {
    'official_api': f'{BASE}/api/datasets/steelbench/SteelBench',
    'official_card': f'{BASE}/datasets/steelbench/SteelBench/raw/main/README.md',
    'official_license': f'{BASE}/datasets/steelbench/SteelBench/raw/main/LICENSE',
    'official_ethics': f'{BASE}/datasets/steelbench/SteelBench/raw/main/ethics.md',
    'official_samples': f'{BASE}/api/datasets/steelbench/SteelBench/tree/main/sample',
    'paper_release_api': f'{BASE}/api/datasets/steelbench/SteelBench-release',
    'public_search': f'{BASE}/api/datasets?search=SteelBench',
    'control_isafetybench': f'{BASE}/api/datasets/raiyaanabdullah/isafety-bench',
    'unverified_copy_api': f'{BASE}/api/datasets/ThinkingHub/PP',
    'unverified_copy_card': f'{BASE}/datasets/ThinkingHub/PP/raw/2a927fb86450332942fb5f4ffac8a20700cd539a/README.md',
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'code_base_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'python': platform.python_version(), 'platform': platform.platform(),
        'authentication': 'none', 'media_downloads': 0, 'checks': [],
    }
    for name, url in ENDPOINTS.items():
        entry = {'name': name, 'url': url}
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                body = response.read(8_000_001)
                if len(body) > 8_000_000:
                    raise ValueError('Metadata response exceeds 8 MB limit')
                entry['status'] = response.status
        except urllib.error.HTTPError as error:
            entry['status'] = error.code
            body = error.read(4096)
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            entry['error'] = str(error)
            body = b''
        (OUT / f'{name}.txt').write_bytes(body)
        entry.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        report['checks'].append(entry)
        print(name, entry.get('status', entry.get('error')))
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    # Zero means the probes ran, NOT that media were acquired or audited.
    print('Metadata probe finished; media downloads: 0. See', OUT / 'report.json')


if __name__ == '__main__':
    main()
