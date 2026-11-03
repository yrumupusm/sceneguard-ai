"""Delayed loss must bind a measured endpoint, not self-consistent invented refs."""
from copy import deepcopy
import unittest
from tests.test_delayed_loss_ownership_contract import run_shared_endpoint
from sceneguard.incident_lifecycle import IncidentLifecycle,digest


def source_resolution():
    r=run_shared_endpoint(two=False)
    resolution=next(x for x in r['resolutions'] if x.get('source_decision',{}).get('rule_id')=='delayed_raw_gate_loss_v1')
    return r['events'][0],resolution


def apply(event,resolution):
    life=IncidentLifecycle()
    life.process(event['decision_time_pts'],[dict(event=event,observation_key='a')],[])
    life.process(resolution['decision_time_pts'],[],[resolution])
    return life.export()


class DelayedLossBindingContracts(unittest.TestCase):
    def test_original_measured_endpoint_is_valid(self):
        event,resolution=source_resolution()
        self.assertEqual(apply(event,resolution)['counts']['confirmation_notifications'],1)

    def test_invented_cache_ref_cannot_replace_trusted_endpoint(self):
        event,resolution=source_resolution();resolution=deepcopy(resolution)
        resolution['source_decision']['measured_loss_context'][-1]['cache_index']=999
        resolution['physical_loss_ref']['cache_index']=999
        resolution['resolution_id']=digest(resolution)
        with self.assertRaises(ValueError):apply(event,resolution)

    def test_invented_endpoint_geometry_cannot_replace_trusted_box(self):
        event,resolution=source_resolution();resolution=deepcopy(resolution)
        resolution['source_decision']['measured_loss_context'][-1]['bbox']=[.1,.1,.2,.2]
        resolution['resolution_id']=digest(resolution)
        with self.assertRaises(ValueError):apply(event,resolution)


if __name__=='__main__':unittest.main()
