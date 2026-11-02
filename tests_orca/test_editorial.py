import unittest
from pathlib import Path
from webapp.editorial import enrich


class EditorialTests(unittest.TestCase):
    def test_exact_source_and_no_mutation(self):
        source = Path('docs/experiments/EXP-0049-results.md').read_text()
        original = {'conclusion': 'kept'}
        result = enrich(source, {'experiment_id': 'EXP-0049'}, original)
        self.assertEqual(original, {'conclusion': 'kept'})
        self.assertEqual(len(result['comparisons']), 2)
        for comparison in result['comparisons']:
            self.assertEqual([v['value'] for v in comparison['values']], [2, 1])
        self.assertIs(enrich(source + '\nchanged', {'experiment_id': 'EXP-0049'}, original), original)
        self.assertIs(enrich(source, {'experiment_id': 'EXP-0048'}, original), original)
