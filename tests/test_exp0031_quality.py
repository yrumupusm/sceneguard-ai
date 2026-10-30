"""Only synthetic contract tests. Not evidence of person ID recovery on CCTV."""
import copy
import unittest
import numpy as np
from sceneguard.exp0031_quality import (SelectionPolicy, choose_representatives,
       make_quality_index, build_feature_map, changed_pair_report)


def sample():
    seg = {'id':'t1','raw_id':1,'start':0.0,'end':1.5,'eligible':True,'rows':[]}
    frames=[]
    for i in range(6):
        b=[.1+.01*i,.2,.2+.01*i,.6]
        row=dict(frame_index=i,cache_index=0,pts=i*.3,raw_id=1,bbox=b,score=.7)
        seg['rows'].append(row)
        frames.append(dict(pts=i*.3,detections=[dict(cache_index=0,track_id=1,observed=True,
                                                       confirmed=True,bbox=b,score=.7)]))
    return [seg],frames


class QualityContract(unittest.TestCase):
    def test_unobserved_missing_row_is_rejected(self):
        segs,frames=sample()
        frames[0]['detections'].append(dict(cache_index=1,track_id=2,observed=True,
                                          confirmed=True,bbox=[.3,.2,.4,.5],score=.7))
        with self.assertRaisesRegex(ValueError,'not found'):
            make_quality_index(segs,frames)

    def test_duplicate_key_is_rejected(self):
        segs,frames=sample()
        extra=copy.deepcopy(segs[0])
        extra['id']='t2'
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            make_quality_index([segs[0],extra],frames)

    def test_overlap_warns_without_two_person_claim(self):
        segs,frames=sample()
        extra=copy.deepcopy(segs[0])
        extra.update(id='t2',raw_id=2,rows=[dict(segs[0]['rows'][2],raw_id=2,cache_index=1)])
        extra['start']=extra['end']=.6
        frames[2]['detections'].append(dict(cache_index=1,track_id=2,observed=True,
                                        confirmed=True,bbox=extra['rows'][0]['bbox'],score=.9))
        flags=make_quality_index(segs+[extra],frames)
        self.assertTrue(flags[(2,0)]['overlap_warning'])
        self.assertFalse(flags[(2,0)]['mixed_person_verified'])

    def test_quality_ranks_clean_box_over_high_score_overlap(self):
        segs,frames=sample()
        other=dict(id='t2',raw_id=2,start=.3,end=.3,eligible=False,rows=[
            dict(segs[0]['rows'][1],cache_index=1,raw_id=2)])
        frames[1]['detections'].append(dict(cache_index=1,track_id=2,observed=True,
                                           confirmed=True,bbox=segs[0]['rows'][1]['bbox'],score=.6))
        segs[0]['rows'][1]['score']=.99
        selected,audit=choose_representatives(segs+[other],frames)
        # The first temporal bin contains rows #0 and #1. #0 is preferred.
        self.assertEqual(selected['t1']['head'][0]['frame_index'],0)
        self.assertEqual(selected['t1']['tail'][0]['frame_index'],0)
        self.assertEqual(audit['t1']['head']['pool_observations'],6)

    def test_all_risky_crops_remain_but_are_flagged(self):
        segs,frames=sample()
        other=dict(id='t2',raw_id=2,start=0,end=1.5,eligible=False,rows=[])
        for i in range(6):
            second=dict(segs[0]['rows'][i],cache_index=1,raw_id=2)
            other['rows'].append(second)
            frames[i]['detections'].append(dict(cache_index=1,track_id=2,observed=True,
                                        confirmed=True,bbox=second['bbox'],score=.3))
        selected,audit=choose_representatives(segs+[other],frames)
        self.assertEqual(len(selected['t1']['tail']),3)
        self.assertFalse(audit['t1']['tail']['clean_endpoint_proxy'])
        self.assertIn('not_verified',audit['t1']['tail']['warning'])

    def test_ineligible_tracklet_is_not_selected(self):
        segs,frames=sample()
        segs[0]['eligible']=False
        chosen,audit=choose_representatives(segs,frames)
        self.assertEqual((chosen,audit),({},{}))

    def test_extent_ratio_warns(self):
        segs,frames=sample()
        new=[.11,.2,.2,.35]
        segs[0]['rows'][1]['bbox']=new
        frames[1]['detections'][0]['bbox']=new
        flags=make_quality_index(segs,frames,SelectionPolicy(extent_window_seconds=.35))
        self.assertTrue(flags[(1,0)]['abrupt_extent_warning'])

    def test_same_crop_reused_at_both_endpoints(self):
        old={'s':{'head':[dict(frame_index=0,cache_index=1)],
                   'tail':[dict(frame_index=0,cache_index=1)]}}
        features={'features':{'s':{'head':[[0,3]],'tail':[[0,1]]}}}
        mp=build_feature_map(old,features)
        self.assertEqual(list(mp),[(0,1)])
        self.assertTrue(np.allclose(mp[(0,1)],[0,1]))

    def test_conflicting_reused_feature_is_rejected(self):
        old={'s':{'head':[dict(frame_index=0,cache_index=1)],
                   'tail':[dict(frame_index=0,cache_index=1)]}}
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            build_feature_map(old,{'features':{'s':{'head':[[1,0]],'tail':[[0,1]]}}})

    def test_old_assoc_remains_immutable_and_experimental(self):
        segs=[dict(id='t1',raw_id=1),dict(id='t2',raw_id=9)]
        old=dict(links=[dict(before='t1',after='t2',status='rejected',similarity=.31)])
        new=dict(links=[dict(before='t1',after='t2',status='accepted',similarity=.7)])
        audit={'t1':{'tail':{'clean_endpoint_proxy':True}},
               't2':{'head':{'clean_endpoint_proxy':False}}}
        snapshot=copy.deepcopy(old)
        table=changed_pair_report(segs,old,new,audit)
        self.assertEqual(old,snapshot)
        self.assertFalse(table[0]['identity_verified'])
        self.assertFalse(table[0]['after_head_clean_proxy'])
        self.assertEqual(table[0]['action'],'human_review_only_not_adopted')

    def test_candidate_pair_geometry_cannot_change(self):
        segs=[dict(id='t1',raw_id=1),dict(id='t2',raw_id=9)]
        before=dict(links=[dict(before='t1',after='t2',status='rejected')])
        after=dict(links=[])
        with self.assertRaisesRegex(ValueError,'candidate pairs changed'):
            changed_pair_report(segs,before,after,{})

    def test_policy_rejects_invalid_ranges(self):
        with self.assertRaises(ValueError):
            SelectionPolicy(overlap_iou=1.2).validate()
        with self.assertRaises(ValueError):
            SelectionPolicy(per_endpoint=0).validate()


if __name__=='__main__':
    unittest.main()
