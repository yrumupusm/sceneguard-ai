"""Synthetic EXP46 viewer contract; no local CCTV or registered state."""
from copy import deepcopy
import unittest

from test_portal_births import box, collect, config, sequence
from test_directional_loss import normalized
from test_exp0045_integration import bundle
from sceneguard.exp0045_application import evaluate
from sceneguard.exp0046_application import build_views, normalize_portal
from sceneguard.incident_notifications import group_notifications, notification_cards_at
from webapp.incident import load_exp0041


class PortalWebContract(unittest.TestCase):
    def setUp(self):
        original = normalized('a'*64, 1.8, reason='original_crossing')
        original['source_ref']['source_pointer'] = '/events/0'
        base = bundle([original])
        views, _, _, _ = evaluate(dict(segments=[], policy=dict(loss_wait=1.)), base, [],
                                   __import__('test_directional_loss').scene(), group_notifications)
        self.history = views['history']
        raw = collect(sequence({11: [box()], 12: [box()]}))[0][0]
        self.event = normalize_portal(raw, self.history, config())
        self.entry = dict(session_id='session', notification_enabled=False, sha256='a'*64)

    def load(self, mode, event=None):
        views = build_views(self.history, [event or self.event], config(), group_notifications)
        return load_exp0041(views[mode], self.entry, 'synthetic', 'synthetic-media')

    def test_positive_portal_causal_rewind_and_first_box(self):
        result = self.load('portal-only')
        event = result['events'][0]
        birth = event['source_event']
        self.assertEqual(birth['birth_pts'], 1.1)
        self.assertEqual(birth['first_actual_bbox'], [.47, .3, .51, .34])
        self.assertTrue(birth['birth_site']['portal_center_inside'])
        self.assertFalse(notification_cards_at(result['timeline'], 1.19))
        self.assertFalse(notification_cards_at(result['timeline'], 1.2)[0]['automatic_confirmation'])
        self.assertFalse(notification_cards_at(result['timeline'], 1.19))
        self.assertEqual(len(self.load('combined')['events']), 2)

    def test_reject_invalid_portal_membership(self):
        event = deepcopy(self.event)
        event['source_event']['birth_site']['portal_center_inside'] = False
        event['source_event']['birth_site']['portal_box_overlap'] = .1
        with self.assertRaisesRegex(ValueError, 'portal geometry'):
            self.load('portal-only', event)

    def test_reject_future_first_observation(self):
        event = deepcopy(self.event)
        event['source_event']['birth_pts'] = 1.3
        with self.assertRaisesRegex(ValueError, 'birth candidate'):
            self.load('portal-only', event)


if __name__ == '__main__':
    unittest.main()
