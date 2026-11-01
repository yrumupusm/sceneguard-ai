"""Read-only checks of actual saved outputs; never rerun classification."""
from pathlib import Path
from collections import Counter
import json
import unittest

from sceneguard.exp0044_application import sha
from sceneguard.incident_lifecycle import CONFIRMED, lifecycle_cards_at


class ActualOutputsTests(unittest.TestCase):
    def test_saved_actual_contract_and_preservation(self):
        for key,version in [('007','v2'),('030','v1')]:
            with self.subTest(video=key):
                directory=Path('outputs/exp0047')/(key+'-'+version)
                if not (directory/'summary.json').exists():
                    self.skipTest('Local actual EXP47 outputs unavailable')
                read=lambda p:json.loads(Path(p).read_text())
                portal=Path('outputs/exp0046')/(key+'-v1')
                result=read(directory/'lifecycle-cards.json');summary=read(directory/'summary.json')
                history=read(portal/'history-cards.json');events=history['events']+read(portal/'inside-birth-events.json')
                self.assertEqual({e['event_id']:e for e in result['events']},{e['event_id']:e for e in events})
                self.assertEqual((directory/'history-preserved.json').read_bytes(),(portal/'history-cards.json').read_bytes())
                self.assertEqual((directory/'portal-preserved.json').read_bytes(),(portal/'portal-only-cards.json').read_bytes())
                for p,expected in {**summary['input_sha256'],**summary['code_sha256']}.items():
                    self.assertEqual(sha(p),expected,p)
                keys=[n['notification_key'] for n in result['notification_intents']]
                self.assertEqual(len(keys),len(set(keys)))
                self.assertFalse(result['live_notifications_enabled'])
                for d in history['decisions']:
                    if not d['automatic_confirmation']:continue
                    preserved=[r for r in result['resolutions'] if r['kind']=='preserved_confirmation' and d['event_id'] in r['event_ids']]
                    self.assertEqual(len(preserved),1)
                    self.assertEqual(preserved[0]['source_decision'],d)
                    self.assertAlmostEqual(preserved[0]['decision_time_pts'],d['decision_time_pts'],places=6)
                for at in sorted(set(n['decision_time_pts'] for n in result['notification_intents'] if n['kind']=='confirmation')):
                    before={c['incident_id']:c for c in lifecycle_cards_at(result['timeline'],at-1e-5)}
                    after={c['incident_id']:c for c in lifecycle_cards_at(result['timeline'],at)}
                    for n in result['notification_intents']:
                        if n['kind']=='confirmation' and n['decision_time_pts']==at:
                            self.assertEqual(after[n['incident_id']]['automatic_status'],CONFIRMED)
                            self.assertNotEqual(before[n['incident_id']]['automatic_status'],CONFIRMED)
                for c in result['cards']:
                    kinds=Counter(n['kind'] for n in result['notification_intents'] if n['incident_id']==c['incident_id'])
                    self.assertLessEqual(kinds['suspicion'],1);self.assertLessEqual(kinds['confirmation'],1)


if __name__=='__main__':unittest.main()
