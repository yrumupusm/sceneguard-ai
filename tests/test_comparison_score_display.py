import unittest
from scripts.render_model_comparison_panels import score_rows,threshold_text


class ScoreDisplayTest(unittest.TestCase):
    def test_joint_maximum_excludes_low_person_and_invalid_boxes(self):
        name='evad_vitl'
        out=dict(person_scores=[.2,.9,.95],valid_boxes=[True,True,False],task_head_threshold=.5,
                 task_head_scores=[dict(query_index=i,climbing_action_score=s,person_and_action_candidate=c)
                                   for i,s,c in [(0,.99,False),(1,.7,True),(2,.98,False)]])
        row=next(r for r in score_rows(dict(outputs={name:out}),{name:.7}) if r['model']==name)
        self.assertEqual(row['query_index'],1);self.assertEqual(row['score'],.7);self.assertTrue(row['candidate'])

    def test_missing_head_is_unknown_scene_is_not_localized(self):
        outputs={'vjepa2_l':dict(feature_dimension=1024),
                 'videomaev2_b':dict(task_head_threshold=.6,task_head_scores=[dict(query_index=None,climbing_action_score=.8,climbing_action_candidate=True)])}
        rows={r['model']:r for r in score_rows(dict(outputs=outputs),{})}
        self.assertIsNone(rows['vjepa2_l']['candidate']);self.assertIsNone(rows['vjepa2_l']['score'])
        self.assertIn('사람 위치 없음',rows['videomaev2_b']['scope']);self.assertIsNone(rows['videomaev2_b']['query_index'])
        self.assertEqual(threshold_text(1.0000000000000002),'1 초과 · 모든 점수 제외')


if __name__=='__main__':unittest.main()
