import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('failure_render',Path(__file__).parents[1]/'scripts/render_action_failures.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class FailureEvidence(unittest.TestCase):
    def setUp(self):
        self.manifest={'clips':[{'clip_id':'a','split':'test','label':0},{'clip_id':'b','split':'test','label':1},{'clip_id':'train','split':'train','label':0}]}
        self.scores=[{'clip_id':'a','label':0,'score':.9},{'clip_id':'b','label':1,'score':.1}]
    def test_reference_error_direction(self):
        rows,counts=module.select_failures(self.manifest,self.scores)
        self.assertEqual(counts,{'false_positive':1,'false_negative':1})
        self.assertEqual([(r['clip_id'],r['reference_disagreement']) for r in rows],[('a','false_positive'),('b','false_negative')])
    def test_incomplete_or_duplicate_evaluation_rejected(self):
        for scores in [self.scores[:1],self.scores+[self.scores[0]]]:
            with self.assertRaises(ValueError):module.select_failures(self.manifest,scores)
    def test_labels_and_score_bounds_not_silently_changed(self):
        for replacement in [dict(clip_id='a',label=1,score=.9),dict(clip_id='a',label=0,score=float('nan')),dict(clip_id='train',label=0,score=.9)]:
            with self.assertRaises(ValueError):module.select_failures(self.manifest,[replacement,self.scores[1]])

if __name__=='__main__':unittest.main()
