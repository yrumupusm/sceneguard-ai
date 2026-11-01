"""Actual PortalGate synthetic integration and read-only full-source preflight."""
import json
from pathlib import Path
import unittest
from sceneguard.exp0049_application import prepare_inputs, replay_activity, source_state, sha
from sceneguard.portal_births import PortalGate, make_region
from sceneguard.gate_activity_episodes import CONFIRMED
from test_exp0049_application import make_prior, frames
from test_lifecycle_followup import SCENE


class IntegrationTests(unittest.TestCase):
    def test_saved_actual_prefixes_and_input_bytes_without_replay(self):
        for key in ('007','030'):
            directory=Path('outputs/exp0049')/(key+'-v1')
            if not (directory/'summary.json').exists(): self.skipTest('Actual comparison unavailable')
            read=lambda p:json.loads(Path(p).read_text())
            result=read(directory/'activity-cards.json'); prior=read(directory/'prior-lifecycle-preserved.json')
            self.assertEqual((directory/'prior-lifecycle-preserved.json').read_bytes(),
                Path('outputs/exp0048',key+'-v2','lifecycle-cards.json').read_bytes())
            request=read(directory/'request.json')
            for p,h in {**request['input_sha256'],**request['code_sha256']}.items():
                self.assertEqual(sha(p),h,p)
            self.assertEqual({e['event_id']:e for e in result['events']},
                             {e['event_id']:e for e in prior['events']})
            old={};new={}; oi=ni=0
            for frame in result['activity_audit']:
                at=frame['pts']
                while oi<len(prior['timeline']) and prior['timeline'][oi]['decision_time_pts']<=at+1e-9:
                    old.update({e['event_id']:e for e in prior['timeline'][oi]['evidence']});oi+=1
                while ni<len(result['timeline']) and result['timeline'][ni]['decision_time_pts']<=at+1e-9:
                    new.update({e['event_id']:source_state(e) for e in result['timeline'][ni]['evidence']});ni+=1
                self.assertEqual(old,new,(key,at))
            self.assertEqual(len(result['cards']),1)
            self.assertEqual([n['decision_time_pts'] for n in result['notification_intents'] if n['kind']=='confirmation'],
                [n['decision_time_pts'] for n in prior['notification_intents'] if n['kind']=='confirmation'])
            self.assertEqual(result['counts']['released_cards'],0)
            if key=='007':
                self.assertFalse(any(84.<=e['decision_time_pts']<=104. for e in result['events']))
                self.assertAlmostEqual(result['cards'][0]['observation_closed_pts'],74.56666666666666)
            else:
                self.assertEqual(result['cards'][0]['observation_status'],'open')
                late=[e for e in result['evidence'] if abs(e['opened_pts']-97.43333333333334)<1e-7]
                self.assertTrue(late)
                self.assertTrue(all(e['automatic_status']=='침입 의심' for e in late))

    def test_actual_portal_with_frozen_synthetic_evidence(self):
        region = make_region(SCENE, 'C', [[.3,.1],[.7,.1],[.7,.9],[.3,.9]],
                             reference_pts=0., note='Synthetic integration portal')
        result = replay_activity(make_prior(), frames(), PortalGate(SCENE, region, 'C'))
        self.assertEqual(len(result['cards']), 1)
        self.assertEqual(result['cards'][0]['automatic_status'], CONFIRMED)
        self.assertEqual(result['cards'][0]['unresolved_event_ids'], ['b'])
        self.assertEqual([source_state(e) for e in result['evidence']], make_prior()['evidence'])
        self.assertEqual(result['source_frames_with_portal_presence'], 161)

    def test_full_actual_sources_read_only(self):
        receipts = []
        for key in ('007', '030'):
            previous = Path('outputs/exp0048')/(key+'-v2')
            if not previous.exists(): self.skipTest('Local full sources unavailable')
            prior, fs, gate, policy, floor, protected, code = prepare_inputs(
                previous, Path('outputs/exp0042')/(key+'-v1'), Path('outputs/exp0046')/(key+'-v1'))
            self.assertEqual(len(fs), 1710 if key=='007' else 480)
            self.assertEqual(len(prior['events']), 18 if key=='007' else 20)
            receipts.append(dict(video_id=prior['video_id'], frames=len(fs),
                candidates=len(prior['events']), first_pts=fs[0]['pts'], last_pts=fs[-1]['pts'],
                input_sha256=protected, code_sha256=code, actual_replay_calls=0,
                portal_class=type(gate).__name__, empty_grace_seconds=policy.empty_grace_seconds,
                detection_floor=floor))
        out = Path('outputs/runtime/EXP-0049/preflight-v1.json')
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(dict(experiment='EXP-0049', sources=receipts),indent=2)+'\n')


if __name__=='__main__': unittest.main()
