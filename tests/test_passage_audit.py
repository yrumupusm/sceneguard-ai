import unittest
from types import SimpleNamespace
from sceneguard.passage_audit import summarize_runs, audit_all_runs, candidate_links, box_motion
from sceneguard.incident_lifecycle import SUSPECTED, CONFIRMED, RELEASED

G=dict(size=(100,100),inward_normal=(1,0))
def row(i,x=.6):return dict(pts=i*.25,frame_index=i,cache_index=0,bbox=[x,.2,x+.1,.6])
def evidence(eid,key,status=SUSPECTED,source=None,edges=()):
    return dict(event_id=eid,observation_key=key,automatic_status=status,
                binding=dict(source_observation_key=source or key),observation_history=list(edges))

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.frames=[dict(pts=i*.25,frame_index=i) for i in range(13)]
        self.runs={'r':[row(0),row(1,.55),row(2,.5)]}
    def summary(self, ev=(), end=None):
        return summarize_runs(self.runs,self.frames,dict(evidence=list(ev)),end or {},G)
    def test_unalerted_passer_is_not_release(self):
        r=self.summary()['records'][0]
        self.assertEqual(r['state_category'],'no_suspicion')
        self.assertEqual(r['actual_release_event_ids'],[])
    def test_pending_not_assumed_normal(self):
        r=self.summary([evidence('e','r')])['records'][0]
        self.assertEqual(r['state_category'],'pending')
        self.assertFalse(r['normal_pedestrian_verified'])
    def test_released_requires_actual_state(self):
        r=self.summary([evidence('e','r',RELEASED)])['records'][0]
        self.assertEqual(r['actual_release_event_ids'],['e'])
    def test_direction_diagnostic_does_not_release(self):
        r=self.summary([evidence('e','r')])['records'][0]
        self.assertEqual(r['box_motion_diagnostic']['direction'],'outward')
        self.assertEqual(r['state_category'],'pending')
        self.assertFalse(r['box_motion_diagnostic']['used_for_status'])
    def test_box_scale_warning(self):
        rr=[row(0),dict(row(2),bbox=[.6,.2,.65,.3])]
        self.assertGreater(box_motion(rr,G)['box_scale_ratio'],3)
    def test_parallel_is_not_automatically_release(self):
        rr=[row(0),dict(row(2),bbox=[.6,.1,.7,.5])]
        self.assertEqual(box_motion(rr,G)['direction'],'parallel')
    def test_continuity_roots_remain_auditable(self):
        e=evidence('e','c',source='a',edges=[dict(from_key='a',to_key='b'),dict(from_key='b',to_key='c')])
        links=candidate_links(dict(evidence=[e]))
        self.assertEqual(set(links),{'a','b','c'})
    def test_pending_keeps_partial_release_card_work(self):
        r=self.summary([evidence('a','r',RELEASED),evidence('b','r')])['records'][0]
        self.assertEqual(r['state_category'],'pending')
    def test_confirmed_separate_from_passage(self):
        self.assertEqual(self.summary([evidence('e','r',CONFIRMED)])['records'][0]['state_category'],'confirmed_related')
    def test_single_box_diagnostic_unavailable(self):
        self.assertEqual(box_motion([row(0)],G)['direction'],'unavailable')
    def test_frame_clock_mismatch_rejected(self):
        self.runs['r'][0]['pts']=.01
        with self.assertRaises(ValueError):self.summary()
    def test_duplicate_run_time_rejected(self):
        self.runs['r'].append(row(2))
        with self.assertRaises(ValueError):self.summary()
    def test_all_runs_including_unalerted_are_evaluated(self):
        self.runs['tail']=[row(11),row(12)]
        class H:
            def __init__(self,*a):self.indices=[]
            def advance(self,f):self.indices.append(f['frame_index'])
        calls=[]
        def assess(h,e,p,rid,i,**kw):
            calls.append((rid,i,len(h.indices)))
            return dict(outcome=None,reason='unknown')
        eng=SimpleNamespace(policy=SimpleNamespace(loss_wait=1.),geometry=G)
        out=audit_all_runs(self.runs,self.frames,dict(evidence=[]),eng,None,history_factory=H,assessor=assess)
        self.assertEqual(calls,[('r',6,7)])
        self.assertEqual(out['endpoint_reasons']['recording_ends_before_loss_wait'],1)
        self.assertEqual(out['run_counts'],{'no_suspicion':2})
        self.assertEqual(out['synthetic_suspicions_created'],0)
    def test_endpoint_eligible_does_not_manufacture_suspicion(self):
        r=self.summary(end={'r':dict(outcome='outward_loss',reason='outward_motion_then_loss')})['records'][0]
        self.assertEqual(r['state_category'],'no_suspicion')
        self.assertEqual(r['actual_release_event_ids'],[])

if __name__=='__main__':unittest.main()
