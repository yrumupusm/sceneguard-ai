"""Scoped playback keeps the prior experiment identity and causal intents."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from test_exp0047_web import LifecycleWebTests
from webapp.incident import load_bundle, load_lifecycle

class ScopedWebTests(unittest.TestCase):
    def test_scoped_contract_and_prior_identity(self):
        old = LifecycleWebTests().fixture()
        entry = dict(session_id='S', notification_enabled=False, sha256='a'*64)
        self.assertEqual(load_lifecycle(old, entry, 'old', 'video')['experiment'], 'EXP-0047')
        new = deepcopy(old)
        new.update(experiment='EXP-0048', outcome_scope_policy='latest_linked_incident_v1',
                   ownership_is_identity_proof=False, outcome_routing=[dict(reason='latest_linked_incident',
                       decision_time_pts=4., selected_event_ids=['b'*64], excluded_event_ids=['a'*64])])
        loaded = load_lifecycle(new, entry, 'new', 'video')
        self.assertEqual(loaded['experiment'], 'EXP-0048')
        self.assertEqual(loaded['contract'], 'incident_outcome_scope_v1')
        self.assertEqual(loaded['outcome_routing'], new['outcome_routing'])
        self.assertEqual(loaded['notification_intents'], old['notification_intents'])
        new['ownership_is_identity_proof'] = True
        with self.assertRaises(ValueError): load_lifecycle(new, entry, 'new', 'video')

    def test_observation_audit_is_hash_bound(self):
        data = LifecycleWebTests().fixture()
        data.update(experiment='EXP-0048', outcome_scope_policy='latest_linked_incident_v1',
                    ownership_is_identity_proof=False, outcome_routing=[])
        audit = dict(unit='geometric_observation_runs_not_people_or_independent_samples',
                     statuses_changed=False, records=[])
        with TemporaryDirectory() as directory:
            root = Path(directory); bundle = root/'bundle.json'; sidecar = root/'audit.json'; video = root/'video.mp4'
            bundle.write_text(json.dumps(data)); sidecar.write_text(json.dumps(audit)); video.write_bytes(b'video')
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            entry = dict(experiment_id='EXP-0048', path='bundle.json', sha256=digest(bundle),
                         audit_path='audit.json', audit_sha256=digest(sidecar), media_artifact_id='video',
                         session_id='S', notification_enabled=False)
            config = dict(incident_bundles={'scoped':entry}, artifact_allow_root=str(root), repo_root=str(root))
            catalog = {'experiments':[{'experiment_id':'EXP-0048', 'evidence':[{'artifact_id':'video', 'kind':'video'}]}]}
            with patch('webapp.incident.catalog', return_value=catalog), patch('webapp.incident.artifact', side_effect=lambda c, m:(video.open('rb'), '.mp4')):
                self.assertEqual(load_bundle(config, 'scoped')['observation_audit'], audit)
                sidecar.write_text(json.dumps({**audit, 'records':[{}]}))
                with self.assertRaises(ValueError): load_bundle(config, 'scoped')

if __name__ == '__main__': unittest.main()
