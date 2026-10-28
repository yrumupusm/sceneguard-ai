import json
import unittest

from vlm_batch.common import parse_pair


class BatchParsingTests(unittest.TestCase):
    def setUp(self):
        self.obj = dict(observed_actions=['passage_or_waiting'], visible_evidence='A person waits.',
                        crossing_completion='not_confirmed', uncertainties='Small person.')
        self.raw = json.dumps(self.obj)

    def test_strict_and_fenced_are_separate(self):
        self.assertEqual(parse_pair(self.raw)['strict_parsed'], self.obj)
        result = parse_pair('```json\n' + self.raw + '\n```')
        self.assertIsNone(result['strict_parsed'])
        self.assertEqual(result['postprocessed_parsed'], self.obj)
        self.assertEqual(result['postprocessing'], 'outer_json_fence_removed')

    def test_does_not_extract_or_repair(self):
        for raw in ('Answer: ' + self.raw, '```json\n' + self.raw, self.raw[:-1],
                    self.raw + '\nDone.', '```json\n' + self.raw + '\n```\n```\n{}\n```'):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_pair(raw)['postprocessed_parsed'])

    def test_rejects_duplicate_keys_enum_and_extra_fields(self):
        duplicate = self.raw[:-1] + ',"crossing_completion":"observed"}'
        self.assertIsNone(parse_pair(duplicate)['postprocessed_parsed'])
        for obj in (dict(self.obj, extra='x'), dict(self.obj, observed_actions=['walking']),
                    dict(self.obj, observed_actions=[]), dict(self.obj, crossing_completion=True)):
            self.assertIsNone(parse_pair(json.dumps(obj))['postprocessed_parsed'])

    def test_fence_does_not_modify_evidence(self):
        self.obj['visible_evidence'] = 'Text includes ``` and unknown movement.'
        raw = json.dumps(self.obj)
        self.assertEqual(parse_pair(' \n```\n' + raw + '\n```\n')['postprocessed_parsed'], self.obj)


if __name__ == '__main__':
    unittest.main()
