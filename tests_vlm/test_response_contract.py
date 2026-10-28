import json
import unittest
from scripts.run_local_vlm import parse_response

class ContractTests(unittest.TestCase):
    def valid(self):
        return {'관찰 행동':['판단 불가'],'화면에서 확인되는 근거':'가림','넘기 완료':'판단 불가','불확실한 부분':'작은 크기'}
    def test_valid_unicode(self):
        obj=self.valid();self.assertEqual(parse_response(json.dumps(obj,ensure_ascii=False)),obj)
    def test_fence_is_failure_not_silent_repair(self):
        with self.assertRaises(ValueError):parse_response('```json\n'+json.dumps(self.valid())+'\n```')
    def test_truncation_not_completed(self):
        with self.assertRaises(ValueError):parse_response('{"관찰 행동": [')
    def test_invalid_completion_rejected(self):
        obj=self.valid();obj['넘기 완료']='성공'
        with self.assertRaises(ValueError):parse_response(json.dumps(obj))

if __name__=='__main__':unittest.main()
