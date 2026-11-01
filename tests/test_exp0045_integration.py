"""Real engine/grouping contracts; local preflight validates inputs without classifying CCTV."""
from copy import deepcopy
from pathlib import Path
import unittest

from test_directional_loss import fixture, scene, normalized
from sceneguard.exp0045_application import evaluate, grouping_effects, select_scene
from sceneguard.exp0044_application import prepared_inputs, sha
from sceneguard.directional_loss import SavedGateDirection
from sceneguard.gate_episode_evidence import Gate
from sceneguard.incident_notifications import group_notifications, notification_cards_at


def bundle(events):
    events = deepcopy(events)
    for event in events:
        event.update(session_id='session', camera_id='camera', gate_id='gate')
    return dict(group_notifications(events), video_id='synthetic', source_window=[0., 2.])


class RealEngineContract(unittest.TestCase):
    def test_A_is_independent_of_B_and_preserves_original_payload_and_notice(self):
        frames, seg, raw = fixture()
        event = normalized('loss', raw['decision_time_pts'])
        event['source_event'] = raw
        base = bundle([event]); original = deepcopy(base)
        views, decisions, births, _ = evaluate(
            dict(segments=[seg], policy=dict(loss_wait=1.)), base, frames, scene(), group_notifications)
        self.assertTrue(decisions[0]['automatic_confirmation'])
        self.assertEqual(births, [])
        self.assertEqual(base, original)
        self.assertEqual(views['history']['events'], base['events'])
        self.assertEqual(views['history']['cards'][0]['first_notification_pts'], 1.5)
        self.assertEqual(views['combined']['cards'][0]['first_confirmation_pts'], 1.5)
        self.assertFalse(notification_cards_at(views['combined']['timeline'], 1.49))
        self.assertTrue(notification_cards_at(views['combined']['timeline'], 1.5)[0]['automatic_confirmation'])
        self.assertFalse(notification_cards_at(views['combined']['timeline'], 1.49))
        self.assertEqual(views['birth-only']['decisions'], [])

    def test_B_is_independent_of_A_and_never_confirms(self):
        frames = []
        for index in range(61):
            at = index/30
            boxes = [dict(bbox=[.54,.4,.58,.6], score=.8, cache_index=0, track_ids=[index])]
            frames.append(dict(frame_index=index, pts=at, actual_boxes=boxes if index>=33 else [], point_paths=[]))
        base = bundle([normalized('cross', 1.8, reason='original_crossing')])
        views, decisions, births, _ = evaluate(dict(segments=[], policy=dict(loss_wait=1.)),
            base, frames, scene(), group_notifications)
        self.assertEqual(decisions, [])
        self.assertEqual(len(births), 1)
        self.assertEqual(births[0]['source_ref']['collection'], 'inside_birth_events')
        self.assertEqual(births[0]['track_ids'], [])
        self.assertFalse(views['birth-only']['cards'][0]['automatic_confirmation'])
        self.assertEqual(views['combined']['grouping_effects']['original_notification_intents_absorbed'], 1)
        self.assertEqual(views['history']['grouping_effects']['original_notification_intents_absorbed'], 0)
        self.assertFalse(notification_cards_at(views['birth-only']['timeline'], 1.19))

    def test_changed_loss_wait_rejected(self):
        frames, seg, raw = fixture()
        event = normalized('loss', 1.5); event['source_event'] = raw
        with self.assertRaisesRegex(ValueError, 'waiting time'):
            evaluate(dict(segments=[seg], policy=dict(loss_wait=.5)), bundle([event]), frames, scene(), group_notifications)

    def test_bridging_birth_quantifies_absorbed_baseline_notice(self):
        base = bundle([normalized('a', 1), normalized('b', 6)])
        combined = bundle(base['events'] + [normalized('new', 3.5)])
        effects = grouping_effects(base, combined)
        self.assertEqual(effects['baseline_notification_intents'], 2)
        self.assertEqual(effects['original_notification_intents_absorbed'], 1)
        self.assertEqual(effects['original_rows_with_changed_membership'], 2)

    def test_unapproved_or_030_override_rejected(self):
        for video, override in [('E01_007', None), ('E01_007', Path('other.json')), ('E01_030', Path('other.json'))]:
            with self.subTest(video=video), self.assertRaises(ValueError):
                select_scene(video, scene(), override)
        self.assertEqual(select_scene('E01_030', scene()), scene())


class LocalPreflight(unittest.TestCase):
    @unittest.skipUnless(Path('outputs/exp0042/007-v1/frame-evidence.jsonl').exists(), 'local inputs absent')
    def test_real_saved_schemas_original_bindings_and_approved_scene_without_evaluation(self):
        for key, expected in [('007',1710), ('030',480)]:
            baseline, base, frames, original, group, protected = prepared_inputs(
                f'outputs/exp0035/{key}-v1.json', f'outputs/exp0042/{key}-v1')
            override = Path('runtime/region-revisions/007-inside-20261101-v1/scene007.json') if key=='007' else None
            selected = select_scene(baseline['video_id'], original, override)
            engine = SavedGateDirection(frames, selected)
            self.assertEqual(len(engine.frames), expected)
            self.assertEqual(tuple(engine.geometry['inward_normal']), Gate(selected).normal)
            regrouped = group(base['events'], [])
            for field in ('events','cards','timeline','counts'):
                self.assertEqual(regrouped[field], base[field])
            effects = grouping_effects(base, regrouped)
            self.assertEqual(effects['original_notification_intents_absorbed'], 0)
            self.assertEqual(protected, {p:sha(p) for p in protected})


if __name__ == '__main__':
    unittest.main()
