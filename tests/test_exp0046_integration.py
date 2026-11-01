"""EXP46 real engine/grouping and byte-copy contracts on synthetic observations."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_directional_loss import fixture, scene, normalized
from test_exp0045_integration import bundle
from sceneguard.exp0044_application import save, sha
from sceneguard.exp0045_application import evaluate
from sceneguard.exp0046_application import execute, build_views, normalize_portal
from sceneguard.gate_episode_evidence import EpisodePolicy
from sceneguard.incident_notifications import group_notifications, notification_cards_at
from sceneguard.portal_births import compare_births, make_region


def synthetic_inputs(directory, birth=False):
    """Disk bundle has EXP45's actual serialization shape, never CCTV pixels."""
    directory=Path(directory); paths=directory/'paths'; paths.mkdir()
    history=directory/'history'; history.mkdir()
    frames,seg,raw=fixture()
    event=normalized('loss',raw['decision_time_pts']);event['source_event']=raw
    if birth:
        frames=[]
        for index in range(61):
            boxes=[dict(bbox=[.64,.2,.68,.3],score=.8,cache_index=0,track_ids=[index])]
            frames.append(dict(frame_index=index,pts=index/30,actual_boxes=boxes if index>=33 else [],point_paths=[]))
        base=bundle([normalized('cross',1.8,reason='original_crossing')]);segments=[]
    else:
        base=bundle([event]);segments=[seg]
    baseline=dict(video_id='synthetic',segments=segments,policy=dict(loss_wait=1.))
    views,decisions,births,audits=evaluate(baseline,base,frames,scene(),group_notifications)
    region=make_region(scene(),'camera',[[.4,.1],[.7,.1],[.7,.7],[.4,.7]],reference_pts=0,note='Synthetic test region')
    save(paths/'baseline-cards.json',base)
    for name,value in [('history-cards',views['history']),('history-decisions',decisions),
                       ('scene-used',scene()),('birth-audits',audits),('inside-birth-events',births),
                       ('summary',dict(video_id='synthetic',frames=len(frames),input_sha256={})),
                       ('request',dict(experiment='EXP-0045',input_sha256={},policy=asdict(EpisodePolicy())))]:
        save(history/(name+'.json'),value)
    save(directory/'portal.json',region)
    return baseline,base,frames,scene(),group_notifications,{},paths,history,region


@contextmanager
def working_directory(path):
    old=Path.cwd();os.chdir(path)
    try:yield
    finally:os.chdir(old)


class FrozenHistoryIntegration(unittest.TestCase):
    def run_application(self, birth=False):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        inputs=synthetic_inputs(root,birth)
        with working_directory(root),patch('sceneguard.exp0044_application.prepared_inputs',return_value=inputs[:6]),patch('sceneguard.exp0045_application.select_scene',return_value=scene()):
            report=execute('baseline.json',inputs[6],inputs[7],root/'portal.json','outputs/result')
        return root,inputs,report

    def test_A_copied_byte_exact_and_original_payloads_preserved(self):
        root,inputs,report=self.run_application()
        output=root/'outputs/result'
        for name in ('history-cards.json','history-decisions.json','scene-used.json'):
            self.assertEqual((output/name).read_bytes(),(inputs[7]/name).read_bytes())
        combined=json.loads((output/'combined-cards.json').read_text())
        self.assertEqual(combined['events'],inputs[1]['events'])
        self.assertEqual(combined['decisions'],json.loads((inputs[7]/'history-decisions.json').read_text()))
        self.assertTrue(report['legacy_B_exactly_reproduced'])
        self.assertTrue(report['observation_bookkeeping_unchanged'])
        self.assertEqual(report['automatic_decision_pts'],[1.5])
        self.assertTrue(all(report['history_bytes_unchanged'].values()))

    def test_portal_only_suspicion_combined_absorption_and_rewind(self):
        root,inputs,report=self.run_application(birth=True)
        output=root/'outputs/result'
        events=json.loads((output/'inside-birth-events.json').read_text())
        self.assertEqual(len(events),1)
        self.assertEqual(report['legacy_birth_candidates'],0)
        self.assertFalse(events[0]['source_event']['automatic_confirmation'])
        combined=json.loads((output/'combined-cards.json').read_text())
        portal=json.loads((output/'portal-only-cards.json').read_text())
        self.assertEqual(portal['decisions'],[])
        self.assertFalse(portal['cards'][0]['automatic_confirmation'])
        self.assertEqual(report['grouping_effects']['original_notification_intents_absorbed'],1)
        at=events[0]['decision_time_pts']
        self.assertFalse(notification_cards_at(portal['timeline'],at-.001))
        self.assertTrue(notification_cards_at(portal['timeline'],at))
        self.assertFalse(notification_cards_at(portal['timeline'],at-.001))
        original={e['event_id']:e for e in inputs[1]['events']}
        self.assertEqual({e['event_id']:e for e in combined['events'] if e['event_id'] in original},original)
        audits=json.loads((output/'case-audit.json').read_text())
        self.assertEqual(len(audits),1)
        self.assertFalse(audits[0]['legacy_eligible'])
        self.assertTrue(audits[0]['portal_eligible'])
        self.assertEqual(len(audits[0]['observation_refs']),28)

    def test_tampered_frozen_legacy_audit_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);inputs=synthetic_inputs(root)
            (inputs[7]/'birth-audits.json').write_text('[]')
            with working_directory(root),patch('sceneguard.exp0044_application.prepared_inputs',return_value=inputs[:6]),patch('sceneguard.exp0045_application.select_scene',return_value=scene()):
                with self.assertRaisesRegex(ValueError,'Legacy B'):
                    execute('baseline.json',inputs[6],inputs[7],root/'portal.json','outputs/result')
            self.assertFalse((root/'outputs/result').exists())

    def test_same_temporal_association_full_observations_with_changed_IDs(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs=synthetic_inputs(temporary,True)
            result=compare_births(inputs[2],inputs[3],inputs[-1],'camera')
            self.assertEqual(len(result['portal_events']),1)
            self.assertEqual(len(result['observation_runs']),1)
            refs=result['observation_runs']['observation-00001']
            self.assertEqual([r['frame_index'] for r in refs],list(range(33,61)))
            self.assertTrue(result['observation_bookkeeping_unchanged'])


if __name__=='__main__':unittest.main()
