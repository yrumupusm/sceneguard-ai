"""Synthetic rule/scope checks, not video-level accuracy measurements."""
from copy import deepcopy
import unittest

from sceneguard.outward_crossing import outward_loss_decision
from sceneguard.lifecycle_followup import loss_resolution
from sceneguard.incident_lifecycle import CONFIRMED, SUSPECTED
from sceneguard.incident_outcome_scope import ScopedIncidentLifecycle
from test_visible_crossing import scene, row
from test_incident_outcome_scope import candidate


def inputs():
    seg = dict(id='a',raw_id=1,rows=[row(i/10,x) for i,x in enumerate([.57,.56,.55,.54])])
    prior = dict(status=SUSPECTED,automatic_confirmation=False,
        continuation='unresolved',direction=dict(direction='outward',end_pts=.3),
        decision_time_pts=1.3,last_observed_pts=.3,reason='outward_motion_then_loss')
    return prior,seg,scene()


class OutwardLossTests(unittest.TestCase):
    def test_inside_origin_gate_loss_confirms(self):
        d=outward_loss_decision(*inputs())
        self.assertTrue(d['automatic_confirmation'])
        self.assertEqual(d['crossing_direction'],'inside_to_outside')
        self.assertFalse(d['human_verified'])

    def test_approach_from_outside_then_walk_away_does_not_confirm(self):
        p,s,c=inputs()
        for r in s['rows']:r['bbox']=row(r['pts'],.46)['bbox']
        self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])

    def test_disabled_direction(self):
        p,s,c=inputs();c['directions']=['outside_to_inside']
        self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])

    def test_unknown_stale_or_inward_motion_not_upgraded(self):
        for label,end in [('unknown',.3),('inward',.3),('outward',-5.),('outward',.4)]:
            p,s,c=inputs();p['direction']=dict(direction=label,end_pts=end)
            self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])

    def test_visible_continuation_and_source_gaps_not_loss_confirmation(self):
        for continuation in ['same_side_continuation','cross_side_observation']:
            p,s,c=inputs();p['continuation']=continuation
            self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])
        p,s,c=inputs();p['reason']='source_gap_not_person_loss'
        self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])

    def test_short_absence_or_wrong_segment_clock_rejected(self):
        for changes in [dict(decision_time_pts=.5),dict(last_observed_pts=.2)]:
            p,s,c=inputs();p.update(changes)
            self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])

    def test_far_from_gate_or_gate_extension_rejected(self):
        for x,y in [(.8,.5),(.54,.85)]:
            p,s,c=inputs()
            for r in s['rows']:r['bbox']=row(r['pts'],x,y)['bbox']
            self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])

    def test_short_inside_history_and_disconnected_history_rejected(self):
        p,s,c=inputs();s['rows']=s['rows'][-2:]
        self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])
        p,s,c=inputs();s['rows']=s['rows'][::3]
        self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])

    def test_future_rows_or_predicted_rows_cannot_help(self):
        p,s,c=inputs();s['rows'].append(row(2.,.53))
        self.assertFalse(outward_loss_decision(p,s,c)['automatic_confirmation'])
        p,s,c=inputs();s['rows'][1]['observed']=False
        with self.assertRaises(ValueError):outward_loss_decision(p,s,c)

    def test_existing_inward_confirmation_and_inputs_preserved(self):
        args=inputs();before=deepcopy(args);outward_loss_decision(*args)
        self.assertEqual(args,before)
        args[0]['automatic_confirmation']=True
        self.assertEqual(outward_loss_decision(*args),args[0])

    def test_scoped_outward_crossing_confirms_one_anchor_not_release(self):
        life=ScopedIncidentLifecycle(namespace='outward-test')
        life.process(0.,[candidate('old',0.)]);life.process(.1,[candidate('new',.1)])
        p,s,c=inputs();d=outward_loss_decision(p,s,c)
        a=dict(p,run_id='a',outcome='outward_crossing_loss',loss_wait=1.,
            direction_history_seconds=1.,recent_gate_contact=True,outward_crossing_evidence=d)
        resolution=loss_resolution(a,['old','new'])
        life.process(1.3,resolutions=[resolution])
        self.assertEqual(life.evidence['old']['automatic_status'],SUSPECTED)
        self.assertEqual(life.evidence['new']['automatic_status'],CONFIRMED)
        self.assertEqual(life.export()['counts']['confirmation_notifications'],1)
        life.process(1.4,resolutions=[dict(resolution,resolution_id='retry',
            decision_time_pts=1.4,evidence_until_pts=1.4,
            evidence=dict(a,outward_crossing_evidence=dict(d,decision_time_pts=1.4)))])
        self.assertEqual(life.evidence['old']['automatic_status'],SUSPECTED)

    def test_unsubstantiated_outward_crossing_resolution_rejected(self):
        life=ScopedIncidentLifecycle();life.process(0.,[candidate('old',0.)])
        p,_,_=inputs()
        a=dict(p,run_id='a',outcome='outward_crossing_loss',loss_wait=1.,
            direction_history_seconds=1.,recent_gate_contact=True)
        with self.assertRaises(ValueError):life.process(1.3,resolutions=[loss_resolution(a,['old'])])


if __name__=='__main__':unittest.main()
