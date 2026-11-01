"""Real saved-source validation plus synthetic replay using actual direction/portal.

Read-only actual-output assertions never rerun a CCTV classification.
"""
from pathlib import Path
from collections import Counter
import json
import unittest
from sceneguard.exp0048_application import prepare_inputs, replay_scoped
from sceneguard.exp0044_application import sha
from sceneguard.portal_births import make_region
from sceneguard.incident_lifecycle import CONFIRMED, SUSPECTED, RELEASED, lifecycle_cards_at
from test_lifecycle_followup import fixture, SCENE


class IntegrationTests(unittest.TestCase):
    def test_actual_direction_portal_scoped_replay(self):
        region=make_region(SCENE,'C',[[.3,.1],[.7,.1],[.7,.9],[.3,.9]],reference_pts=0.,note='Synthetic test portal')
        for velocity,status in [(-8.,RELEASED),(8.,CONFIRMED),(0.,SUSPECTED)]:
            with self.subTest(velocity=velocity):
                b,h,e,r,f=fixture(velocity=velocity)
                result,audit=replay_scoped(b,h,e,r,f,SCENE,region)
                self.assertEqual(result['cards'][0]['automatic_status'],status)
                self.assertEqual(result['experiment'],'EXP-0048')
                self.assertEqual(sum(audit['run_counts'].values()),len(r))
                self.assertEqual(audit['synthetic_suspicions_created'],0)

    def test_real_saved_source_contract_before_classification(self):
        receipts=[]
        for key,version in [('007','v2'),('030','v1')]:
            if not Path('outputs/exp0047',key+'-'+version,'summary.json').exists():
                self.skipTest('Local frozen sources unavailable')
            b,h,e,r,f,s,region,prior,protected,code=prepare_inputs(
                Path('outputs/exp0035')/(key+'-v1.json'),Path('outputs/exp0042')/(key+'-v1'),
                Path('outputs/exp0046')/(key+'-v1'),Path('outputs/exp0047')/(key+'-'+version))
            self.assertEqual(len(f),1710 if key=='007' else 480)
            self.assertEqual(len(h['events'])+len(e),18 if key=='007' else 20)
            self.assertEqual(len(r),152 if key=='007' else 70)
            self.assertEqual({e['event_id']:e for e in prior['events']},{e['event_id']:e for e in h['events']+e})
            receipts.append(dict(video_id=b['video_id'],frames=len(f),runs=len(r),candidates=len(h['events'])+len(e),
                first_pts=f[0]['pts'],last_pts=f[-1]['pts'],input_sha256=protected,code_sha256=code,
                classifications_run=0))
        out=Path('outputs/exp0048/preflight-v1.json')
        if not out.exists():
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(json.dumps(dict(experiment='EXP-0048',sources=receipts),indent=2)+'\n')

    def test_saved_actual_outputs_without_replay(self):
        for key in ('007','030'):
            directory=Path('outputs/exp0048')/(key+'-v2')
            if not (directory/'summary.json').exists():
                continue
            read=lambda p:json.loads(Path(p).read_text())
            result=read(directory/'lifecycle-cards.json');summary=read(directory/'summary.json')
            portal=Path('outputs/exp0046')/(key+'-v1');history=read(portal/'history-cards.json')
            events=history['events']+read(portal/'inside-birth-events.json')
            self.assertEqual({e['event_id']:e for e in result['events']},{e['event_id']:e for e in events})
            self.assertEqual((directory/'history-preserved.json').read_bytes(),(portal/'history-cards.json').read_bytes())
            prior=Path('outputs/exp0047')/(key+('-v2' if key=='007' else '-v1'))
            self.assertEqual((directory/'prior-lifecycle-preserved.json').read_bytes(),(prior/'lifecycle-cards.json').read_bytes())
            for path,expected in {**summary['input_sha256'],**summary['code_sha256']}.items():
                self.assertEqual(sha(path),expected,path)
            for d in history['decisions']:
                if d['automatic_confirmation']:
                    rr=[r for r in result['resolutions'] if r['kind']=='preserved_confirmation' and d['event_id'] in r['event_ids']]
                    self.assertEqual(len(rr),1);self.assertEqual(rr[0]['source_decision'],d)
                    self.assertAlmostEqual(rr[0]['decision_time_pts'],d['decision_time_pts'],places=6)
            keys=[n['notification_key'] for n in result['notification_intents']]
            self.assertEqual(len(keys),len(set(keys)))
            for c in result['cards']:
                kinds=Counter(n['kind'] for n in result['notification_intents'] if n['incident_id']==c['incident_id'])
                self.assertLessEqual(kinds['confirmation'],1)
            evidence_to_card={e['event_id']:e['incident_id'] for e in result['evidence']}
            owners={};anchors={}
            for r in result['outcome_routing']:
                if r.get('kind') not in ('inward_loss','outward_loss'):continue
                self.assertLessEqual(len({evidence_to_card[e] for e in r['selected_event_ids']}),1)
                self.assertEqual(owners.setdefault(r['outcome_key'],r['owner_incident_id']),r['owner_incident_id'])
                if r['kind']=='inward_loss':
                    self.assertLessEqual(len(r['selected_event_ids']),1)
                    if r['selected_event_ids']:
                        self.assertEqual(anchors.setdefault(r['outcome_key'],r['selected_event_ids'][0]),r['selected_event_ids'][0])
            for n in result['notification_intents']:
                if n['kind']!='confirmation':continue
                at=n['decision_time_pts'];iid=n['incident_id']
                before={c['incident_id']:c for c in lifecycle_cards_at(result['timeline'],at-1e-5)}
                after={c['incident_id']:c for c in lifecycle_cards_at(result['timeline'],at)}
                self.assertNotEqual(before[iid]['automatic_status'],CONFIRMED)
                self.assertEqual(after[iid]['automatic_status'],CONFIRMED)
            audit=read(directory/'all-observations-audit.json');runs=read(portal/'observation-runs.json')
            self.assertEqual({r['run_id'] for r in audit['records']},set(runs))
            self.assertFalse(audit['statuses_changed'])
            self.assertTrue(all(not r['box_motion_diagnostic']['used_for_status'] for r in audit['records']))

if __name__=='__main__':unittest.main()
