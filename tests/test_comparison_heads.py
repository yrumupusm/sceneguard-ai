"""Synthetic CPU counterexamples; no actual model imports or real head fitting."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scripts.extract_comparison_head_features import match_queries,representations
from scripts.train_comparison_heads import strict_threshold,fit_linear,feature_dataset,score_features,PROTOCOL


def target(label=1,actor=1,box=None):
    return dict(label=label,actor_id=actor,object_id=actor,anchor_boxes_origin0_origin1=box or [[[10,10],[30,50]],[[11,10],[31,50]]],
                source_id='alias'+str(actor),source_path='/source'+str(actor),source_sha256='a'*64,
                label_path='/label'+str(actor),label_sha256=str(actor)*64,source_clip_id='clip'+str(actor),action_class='wall' if label else 'sit')


def output(boxes=None):
    boxes=boxes or [[10,10,30,50],[10,10,30,50],[60,10,80,50]]
    return dict(boxes=boxes,valid_boxes=[True]*len(boxes),person_scores=[.2]*len(boxes),raw_action_logits=[[float(i)]*80 for i in range(len(boxes))])


class MatchingTests(unittest.TestCase):
    def test_both_origins_and_original_geometry_are_required(self):
        t=target();t['anchor_boxes_origin0_origin1'][1]=[[60,10],[80,50]]
        rows,c=match_queries(output(),[t],[100,80]);self.assertEqual(rows,[]);self.assertEqual(c['unknown_queries'],3)
        with self.assertRaisesRegex(ValueError,'geometry'):match_queries(output(),[target(box=[[[10,10],[130,50]]]*2)],[100,80])
        bad=output();bad['boxes'][0]=[10,10,130,50]
        with self.assertRaisesRegex(ValueError,'query box'):match_queries(bad,[target()],[100,80])

    def test_min_iou_ranking_tie_query_index_and_one_query_one_weight(self):
        rows,c=match_queries(output(),[target(),target(),target(actor=2)],[100,80])
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['query_index'],0);self.assertEqual(rows[0]['weight_count'],1)
        self.assertEqual(rows[0]['person_score'],.2)
        self.assertEqual(len(rows[0]['targets']),2);self.assertEqual(c['unknown_queries'],2)
        self.assertEqual(rows[0]['targets'][1]['label_path'],'/label2')
        values=output([[8,8,33,55],[10,10,30,50]])
        self.assertEqual(match_queries(values,[target()],[100,80])[0][0]['query_index'],1)

    def test_conflict_unknown_including_nonbest_target_and_unmatched_query(self):
        rows,c=match_queries(output(),[target(),target(0,2)],[100,80])
        self.assertEqual(rows,[]);self.assertEqual(c['conflicting_queries'],[0,1]);self.assertEqual(c['unknown_queries'],3)
        self.assertEqual(c['ambiguous_targets'],2)
        t=target(0,2,[[[12,10],[32,50]],[[12,10],[32,50]]])
        values=output([[10,10,30,50],[12,10,32,50]])
        self.assertEqual(match_queries(values,[target(),t],[100,80])[0],[])

    def test_empty_invalid_and_nan_model_outputs_fail_closed(self):
        for key,value in [('raw_action_logits',[[float('nan')]*80]*3),('raw_action_logits',[[]]*3),('valid_boxes',[1]*3),('boxes',[])]:
            v=output();v[key]=value
            with self.assertRaises(ValueError):match_queries(v,[target()],[100,80])
        for values in ([],[1,float('inf')]):
            with self.assertRaises(ValueError):representations(dict(label=1),dict(pooled_features=values),False)


class HeadTrainingTests(unittest.TestCase):
    def test_quantile_strict_ties_exact_fpr_and_no_negative_human_claim(self):
        s=strict_threshold([.9]*40+[.99],[0]*40+[1])
        self.assertGreater(s['threshold'],.9);self.assertEqual(s['false_positives'],0);self.assertEqual(s['tp'],1)
        self.assertIsNone(s['human_precision'])
        self.assertEqual(s['threshold_status'],'provisional_official_reference_not_human_calibrated')
        self.assertFalse(s['matched_false_positive_operating_point_verified'])
        boundary=strict_threshold([1.,1.],[0,1])
        self.assertGreater(boundary['threshold'],1.);self.assertEqual(boundary['tp'],0)
        s=strict_threshold(list(np.linspace(0,1,40))+[.99],[0]*40+[1])
        self.assertEqual(s['false_positives'],2);self.assertEqual(s['reference_fpr'],.05)
        for values,labels in [([],[]),([float('nan'),.2],[0,1]),([.2,.3],[0,0])]:
            with self.assertRaises(ValueError):strict_threshold(values,labels)

    def test_fixed_cpu_training_train_only_standardization_and_repeatability(self):
        x=[[-2,5],[-1,5],[1,5],[2,5],[-10,9],[10,9]];y=[0,0,1,1,0,1];splits=['train']*4+['validation']*2
        a=fit_linear(x,y,splits);b=fit_linear(x,y,splits)
        self.assertEqual(PROTOCOL['seed'],66);self.assertEqual(len(a['history']),100)
        self.assertEqual(a['mean'].tolist(),[0,5]);self.assertEqual(a['std'][1].item(),1)
        self.assertEqual(a['history'],b['history']);self.assertEqual(a['selection'],b['selection'])
        self.assertEqual(a['selected_epoch'],min(a['history'],key=lambda r:r['validation_ce'])['epoch'])
        self.assertTrue(all(t.device.type=='cpu' for t in a['state_dict'].values()))
        scores=score_features(a,[[-10,9],[10,9]])
        self.assertTrue(all(s['intrusion_completed'] is None and not s['intrusion_state_changed'] for s in scores))
        self.assertGreater(scores[1]['climbing_action_score'],scores[0]['climbing_action_score'])
        bad=copy.deepcopy(a);bad['std'][0]=0
        with self.assertRaisesRegex(ValueError,'frozen CPU head'):score_features(bad,[[-10,9]])
        for values,labels,sp in [([],[],[]),([[float('nan')]]*4,[0,1,0,1],['train']*2+['validation']*2),
                                 ([[1]]*4,[0,1,0,0],['train']*2+['validation']*2),([[1]]*4,[0,1,0,1],['train']*2+['test']*2)]:
            with self.assertRaises(ValueError):fit_linear(values,labels,sp)

    def test_complete_features_no_silent_missing_duplicate_or_one_class(self):
        plan={'windows':[dict(window_id=str(i),split='train' if i<2 else 'validation',label=i%2,source_sha256='a') for i in range(4)]}
        records=[dict(window_id=w['window_id'],split=w['split'],source_sha256='a',samples=[dict(query_index=None,label=w['label'],weight_count=1,feature=[1,2])]) for w in plan['windows']]
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'features.jsonl'
            def write(rows):p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            write(records);self.assertEqual(len(feature_dataset(p,plan,False)[0]),4)
            for rows in ([],records[:-1],records+[records[0]]):
                write(rows)
                with self.assertRaises(ValueError):feature_dataset(p,plan,False)
            bad=copy.deepcopy(records);bad[0]['samples'][0]['feature']=[float('nan')];write(bad)
            with self.assertRaises(ValueError):feature_dataset(p,plan,False)
            bad=copy.deepcopy(records);bad[0]['samples']=[];write(bad)
            with self.assertRaises(ValueError):feature_dataset(p,plan,False)



class NativeAuditTests(unittest.TestCase):
    def test_every_native_query_preserved_and_matching_recomputed(self):
        import hashlib
        from scripts.extract_comparison_head_features import audit_native_outputs
        window=dict(window_id='w',split='train',label=1,source_size=[100,80],targets=[target()])
        raw=dict(window_id='w',output=output());samples,coverage=representations(window,raw['output'],True)
        row=dict(window_id='w',samples=samples,coverage=coverage,
                 model_output_sha256=hashlib.sha256(json.dumps(raw['output'],sort_keys=True,allow_nan=False).encode()).hexdigest())
        with tempfile.TemporaryDirectory() as t:
            native=Path(t)/'native.jsonl';features=Path(t)/'features.jsonl'
            native.write_text(json.dumps(raw)+'\n',encoding='utf-8');features.write_text(json.dumps(row)+'\n',encoding='utf-8')
            audit=audit_native_outputs(native,features,dict(windows=[window]),True)
            self.assertEqual(audit['train']['query_count'],3);self.assertEqual(audit['train']['unknown_queries'],2)
            changed=copy.deepcopy(raw);changed['output']['raw_action_logits'][2][0]=999
            native.write_text(json.dumps(changed)+'\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'output hash'):audit_native_outputs(native,features,dict(windows=[window]),True)
            native.write_text(json.dumps(raw)+'\n',encoding='utf-8');changed=copy.deepcopy(row);changed['samples'][0]['query_index']=1
            features.write_text(json.dumps(changed)+'\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Recomputed'):audit_native_outputs(native,features,dict(windows=[window]),True)
            features.write_text('',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'coverage'):audit_native_outputs(native,features,dict(windows=[window]),True)


if __name__=='__main__':unittest.main()
