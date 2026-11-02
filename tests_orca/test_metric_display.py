import copy
import json
from pathlib import Path
import unittest

from webapp.metric_display import SCOPES, UNITS, metric_groups


class MetricDisplayTests(unittest.TestCase):
    def test_whole_catalog_coverage_and_value_preservation(self):
        root = Path(__file__).resolve().parents[1]
        items = json.loads((root / 'records/catalog.json').read_text())['experiments']
        total = 0
        for item in items:
            source = json.loads((root / item['metrics_path']).read_text())['metrics']
            before = copy.deepcopy(source)
            groups = metric_groups(source)
            self.assertEqual(source, before)
            self.assertEqual(sum(len(g['metrics']) for g in groups), len(source))
            for group in groups:
                self.assertRegex(group['scope_text'], '[가-힣]')
                expected = [m for m in source if (m.get('scope') or '측정 범위가 기록되지 않았습니다.') == group['scope']]
                self.assertEqual([{k:v for k,v in m.items() if k not in ('display_label','display_unit')} for m in group['metrics']], expected)
                for m in group['metrics']:
                    self.assertIn(m['unit'], UNITS)
            total += len(source)
        self.assertGreater(total, 1000)

    def test_unknown_scope_preserved_not_guessed(self):
        m = dict(label='future metric', value=None, unit='unknown', sample_n=None, scope='Unreviewed new scope')
        group = metric_groups([m])[0]
        self.assertEqual(group['scope_text'], m['scope'])
        self.assertIsNone(group['metrics'][0]['value'])
        self.assertEqual(group['metrics'][0]['display_unit'], 'unknown')

    def test_critical_evaluation_limits_not_dropped(self):
        self.assertIn('조기 오경보', SCOPES['Official reference event matching on two development videos only; does not measure early false notices.'])
        scope = 'Official reference. Headline precision/F1 remain null when unknown predictions exist; only scored-subset precision excludes unknowns.'
        self.assertIn('전체 정밀도·F1은 미측정', SCOPES[scope])
        source = [dict(label='의심 공식 사건 TP',value=2,unit='incidents',sample_n=2,scope=scope),
                  dict(label='전체 F1',value=None,unit='ratio',sample_n=2,scope=scope)]
        group = metric_groups(source)[0]
        self.assertEqual(group['title'], '공식 사건 기준 평가')
        self.assertEqual(group['metrics'][0]['display_label'], '의심 공식 기준 잡은 사건')
        self.assertIsNone(group['metrics'][1]['value'])

    def test_same_units_do_not_merge_different_scopes(self):
        source=[dict(label='x', value=0, unit='count',scope='A'),dict(label='y',value=3,unit='count',scope='B')]
        self.assertEqual(len(metric_groups(source)),2)


if __name__ == '__main__':
    unittest.main()
