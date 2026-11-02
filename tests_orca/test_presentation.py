import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tests_orca import test_web
from webapp.presentation import APPLICATION_UNAVAILABLE, UNAVAILABLE, presentation


ROOT = Path(__file__).resolve().parents[1]


class PresentationTests(unittest.TestCase):
    def test_sections_are_excerpts_and_conclusion_comes_only_from_catalog(self):
        source = '''# Experiment
## Purpose and hypothesis
Check whether a candidate is observable. Success is not established.
## Changes and setup
Only the region changed; the model stayed fixed.
### Reproduction
python run.py --config secret.json
### Observations
No new success claim.
## Results
This section must not become the conclusion.
## Limitations
The same camera was used; generalization is untested.
## Next steps
Review the missing event before another experiment.
'''
        item = {'summary': 'Adoption remains on hold.', 'limitations': ['catalog fallback'],
                'next_step': 'catalog fallback'}
        original = copy.deepcopy(item)
        result = presentation(source, item)
        self.assertEqual(result['purpose'], 'Check whether a candidate is observable. Success is not established.')
        self.assertEqual(result['change'], 'Only the region changed; the model stayed fixed. No new success claim.')
        self.assertEqual(result['conclusion'], item['summary'])
        self.assertIn('generalization is untested', result['limitations'])
        self.assertIn('missing event', result['next_steps'])
        self.assertNotIn('python', json.dumps(result))
        self.assertEqual(item, original)

    def test_missing_sections_are_explicit_and_never_guessed_from_results(self):
        result = presentation('# Result\n\nAll trials succeeded.\n', {})
        for field, fallback in UNAVAILABLE.items():
            self.assertEqual(result[field], fallback)
        self.assertEqual(result['references'], [])
        self.assertNotIn('succeeded', json.dumps(result))
        result = presentation('', {'summary': 'Not measured.', 'limitations': ['No ground truth.'],
                                    'next_step': 'Obtain human review.'})
        self.assertEqual(result['conclusion'], 'Not measured.')
        self.assertEqual(result['limitations'], 'No ground truth.')
        self.assertEqual(result['next_steps'], 'Obtain human review.')

    def test_html_code_hash_paths_commands_and_tables_do_not_enter_synopsis(self):
        source = '''## 목적
<script>window.evil = true</script>

<iframe src="https://evil.example/steal"></iframe>

&lt;script&gt;entity_attack()&lt;/script&gt;

Safe **prose**; accuracy remains unknown.

Inline <img src="https://evil.example/a" onerror="inline_attack()"> hidden payload.

```python
code_attack = "https://evil.example/code"
```

## 변경
The model stayed fixed. `print("inline_code")` Internal docs/private/file.md and /home/user/secrets.json and C:\\private\\key.txt.

Hash deadbeef1234567890 and a79551d are provenance.

Internal source sceneguard/vendor/bytetrack/ and package/private/cache/ are omitted.

python exploit.py --token DO_NOT_SHOW

| item | value |
| --- | --- |
| technical_secret | raw_payload |

## 한계
Reference recall is 6/7; this is not user accuracy.
'''
        result = presentation(source, {'summary': '<script>catalog_attack()</script>'})
        serialized = json.dumps(result, ensure_ascii=False)
        for forbidden in ('window.evil', 'iframe', 'entity_attack', 'inline_attack', 'code_attack',
                          'inline_code', 'secrets', 'key.txt', 'docs/private', 'deadbeef', 'a79551d',
                          'DO_NOT_SHOW', 'technical_secret', 'raw_payload', 'catalog_attack', '<script>'):
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn('sceneguard/vendor', serialized)
        self.assertNotIn('package/private', serialized)
        self.assertEqual(result['purpose'], 'Safe prose; accuracy remains unknown.')
        self.assertIn('6/7', result['limitations'])
        self.assertEqual(result['references'], [])

    def test_only_public_http_citations_and_unknown_application(self):
        source = '''## Purpose
[Paper](https://arxiv.org/abs/1703.06870)
[Same](https://arxiv.org/abs/1703.06870)
[Reference][ref]
<https://pytorch.org/docs/stable/>
<https://example.org/article_(version)>
Bare https://example.org/article.
![Do not request](https://images.example.org/cctv.png)
[relative](../local.md) [local](/etc/passwd) [mail](mailto:a@example.org)
[script](javascript:alert%281%29) [data](data:text/html,boom) [file](file:///etc/passwd)
[network](//example.org/hidden) [credentials](https://a:b@example.org/private)
[local](http://localhost:8765/) [loopback](http://127.0.0.1/)
[private](http://192.168.1.1/) [ipv6](http://[::1]/)
[short loopback](http://127.1/) [hex loopback](http://0x7f.0x0.0x0.0x1/)
[internal](https://service.internal/) [single](https://service/)
[encoded control](https://example.org/%0asteal) [badport](https://example.org:99999/)

`https://code.example.org/hidden`

```text
[Fake](https://fenced.example.org/hidden)
```

<a href="https://html.example.org/hidden">raw HTML</a>

[ref]: http://openaccess.thecvf.com/content/paper.html
'''
        result = presentation(source, {})
        refs = result['references']
        self.assertEqual({ref['url'] for ref in refs}, {
            'https://arxiv.org/abs/1703.06870', 'http://openaccess.thecvf.com/content/paper.html',
            'https://pytorch.org/docs/stable/', 'https://example.org/article',
            'https://example.org/article_(version)'})
        self.assertEqual(len(refs), 5)
        for ref in refs:
            self.assertEqual(set(ref), {'label', 'url', 'application'})
            self.assertEqual(ref['application'], APPLICATION_UNAVAILABLE)
        self.assertEqual(refs[0]['label'], 'Paper')

    def test_historical_report_and_current_unsectioned_report(self):
        catalog = json.loads((ROOT / 'records/catalog.json').read_text())
        entries = {item['experiment_id']: item for item in catalog['experiments']}
        historical = entries['EXP-0001']
        result = presentation((ROOT / historical['report_path']).read_text(), historical)
        self.assertIn('사전학습 사람 검출', result['purpose'])
        self.assertIn('개발 영상만 사용', result['change'])
        self.assertEqual(result['conclusion'], historical['summary'])
        self.assertTrue(any(ref['url'].startswith('https://download.pytorch.org/') for ref in result['references']))
        current = entries['EXP-0049']
        result = presentation((ROOT / current['report_path']).read_text(), current)
        self.assertTrue(result['purpose'].startswith(UNAVAILABLE['purpose']))
        self.assertTrue(result['change'].startswith(UNAVAILABLE['change']))
        self.assertIn('원문 도입부:', result['purpose'])
        self.assertNotIn('원문 도입부:', result['change'])
        self.assertEqual(result['conclusion'], current['summary'])
        self.assertNotIn('outputs/', json.dumps(result))

    def test_current_structured_report_and_complete_blocks(self):
        source = (ROOT / 'docs/experiments/MVP-0006-results.md').read_text()
        result = presentation(source, {'summary': 'Behavior accuracy remains unverified.'})
        self.assertIn('사용자 수정 그림', result['change'])
        self.assertIn('일반적인 오탐률 0을 주장할 수 없다', result['limitations'])
        self.assertNotIn('```', result['change'])
        self.assertNotIn('runtime/', json.dumps(result))
        long_block = 'A' * 1300 + ' but success is unverified.'
        result = presentation('## Purpose\n' + long_block, {})
        self.assertEqual(result['purpose'], UNAVAILABLE['purpose'])

    def test_all_registered_reports_keep_contract_and_source_bytes(self):
        catalog_path = ROOT / 'records/catalog.json'
        catalog_bytes = catalog_path.read_bytes()
        catalog = json.loads(catalog_bytes)
        for item in catalog['experiments']:
            path = ROOT / item['report_path']
            before = path.read_bytes()
            original = copy.deepcopy(item)
            result = presentation(before.decode(), item)
            self.assertEqual(set(result), {'purpose', 'change', 'conclusion', 'limitations',
                                           'next_steps', 'references', 'evidence_note'})
            for key, value in result.items():
                if key != 'references':
                    self.assertIsInstance(value, str)
                    self.assertTrue(value)
            self.assertEqual(item, original)
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(catalog_path.read_bytes(), catalog_bytes)


    def test_semantic_inline_literals_and_decimals_are_preserved(self):
        result = presentation('## 목적\n확인은 `False`인 후보를 제외한다. 모델은 `FCOS`다. '
                              '`human_verified=false`와 `score>=0.5`를 구분한다. '
                              '검출 수는 `0`, 정밀도는 `0.125`, 표본은 `1234567` 이다.\n'
                              '## 한계\n정밀도는 0.1234567 이다. 표본은 12345678 개다.', {})
        self.assertIn('False인 후보를 제외한다', result['purpose'])
        self.assertIn('FCOS', result['purpose'])
        self.assertIn('human_verified=false', result['purpose'])
        self.assertIn('score>=0.5', result['purpose'])
        self.assertIn('검출 수는 0, 정밀도는 0.125, 표본은 1234567 이다.', result['purpose'])
        self.assertIn('0.1234567', result['limitations'])
        self.assertIn('12345678', result['limitations'])

    def test_reference_explicit_application_retains_only_original_context(self):
        source = '## 변경\n[공식 구현](https://github.com/example/project)의 모듈을 가져와 로컬 좌표에 맞춰 수정했다.\n'
        result = presentation(source, {})
        self.assertEqual(result['references'][0]['application'],
                         '원문 맥락: 공식 구현의 모듈을 가져와 로컬 좌표에 맞춰 수정했다.')

    def test_document_title_does_not_capture_worker_metadata_as_change(self):
        source = '# Experiment setup\n\n- Worker: INTERNAL_WORKER_MODEL\n\n'
        source += '## 실행 전 고정과 실제 전처리\n\n입력 크기만 고정하여 비교했다.\n'
        result = presentation(source, {})
        self.assertEqual(result['change'], '입력 크기만 고정하여 비교했다.')
        self.assertNotIn('INTERNAL_WORKER_MODEL', json.dumps(result))


class PresentationAPITests(unittest.TestCase):
    setUp = test_web.ViewerTests.setUp
    tearDown = test_web.ViewerTests.tearDown
    write_catalog = test_web.ViewerTests.write_catalog
    write_config = test_web.ViewerTests.write_config

    def test_presentation_is_additive_and_preserves_integrity_and_original_fields(self):
        source = '## 가설과 목적\n\n행동 후보를 관찰할 수 있는지 확인한다.\n'
        self.report.write_text(source, encoding='utf-8')
        self.item['summary'] = '성능 충족은 미확인이다.'
        self.item['report_sha256'] = hashlib.sha256(self.report.read_bytes()).hexdigest()
        metric_path = self.root / self.item['metrics_path']
        self.item['metrics_sha256'] = hashlib.sha256(metric_path.read_bytes()).hexdigest()
        self.write_catalog()
        originals = {path: path.read_bytes() for path in (self.report, metric_path, self.catalog_path)}
        with patch('socket.create_connection', side_effect=AssertionError('no external fetch')):
            body = self.client.get('/api/experiments/EXP-0007').json()
        self.assertEqual(body['presentation']['purpose'], '행동 후보를 관찰할 수 있는지 확인한다.')
        self.assertEqual(body['presentation']['conclusion'], self.item['summary'])
        for key, value in self.item.items():
            if key != 'evidence':
                self.assertEqual(body[key], value)
        self.assertEqual(body['metrics'], self.metrics['metrics'])
        self.assertEqual(body['source_integrity'], {'report_match': True, 'metrics_match': True})
        self.assertIn('<h2>', body['report_html'])
        self.assertIn('review_integrity', body)
        self.assertIn('review_html', body)
        self.assertEqual(body['current_source_sha256'][self.item['report_path']], self.item['report_sha256'])
        for path, before in originals.items():
            self.assertEqual(path.read_bytes(), before)
        self.assertNotIn('presentation', self.client.get('/api/catalog').json()['experiments'][0])


if __name__ == '__main__':
    unittest.main()
