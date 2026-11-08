import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.serve_person_label_editor import Conflict, Store, digest


class PersonLabelEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        image = self.root/'frame.png'
        image.write_bytes(b'synthetic image binding')
        self.package = self.root/'package.json'
        self.package.write_text(json.dumps(dict(frames=[dict(frame_id='case-01-frame-000099',
            split='train', source_size=[100, 80], image_path=str(image), image_sha256=digest(image),
            candidates=[dict(id='original-0', xyxy=[10, 20, 30, 50])])])) )
        self.store = Store(self.package, self.root/'reviews.sqlite3')
        self.frame = 'case-01-frame-000099'
        self.body = dict(expected_version=0, reviewer='synthetic-test', status='complete',
                         confirmed=True, empty_confirmed=False, note='',
                         boxes=[dict(id='box1', source_id='original-0', xyxy=[10,20,30,50])])

    def test_original_and_proposals_never_auto_accepted(self):
        self.assertEqual(self.store.current(self.frame)['status'], 'pending')
        self.assertEqual(self.store.current(self.frame)['boxes'], [])

    def test_revision_restart_and_training_separation(self):
        result = self.store.save(self.frame, self.body)
        self.assertFalse(result['training_release'])
        reopened = Store(self.package, self.root/'reviews.sqlite3')
        self.assertEqual(reopened.current(self.frame), result)

    def test_stale_save_preserves_revision(self):
        result = self.store.save(self.frame, self.body)
        with self.assertRaises(Conflict):
            self.store.save(self.frame, self.body)
        self.assertEqual(self.store.current(self.frame), result)

    def test_unconfirmed_complete_rejected(self):
        self.body['confirmed'] = False
        with self.assertRaises(ValueError):
            self.store.save(self.frame, self.body)

    def test_empty_frame_requires_own_confirmation(self):
        self.body['boxes'] = []
        with self.assertRaises(ValueError):
            self.store.save(self.frame, self.body)
        self.body['empty_confirmed'] = True
        self.assertEqual(self.store.save(self.frame, self.body)['status'], 'complete')

    def test_invalid_coordinates(self):
        for xy in ([0,0,0,10], [-1,0,10,10], [0,0,101,10], [0,0,float('nan'),10], [True,0,10,10]):
            with self.subTest(xy=xy):
                body = copy.deepcopy(self.body)
                body['boxes'][0]['xyxy'] = xy
                with self.assertRaises(ValueError):
                    self.store.save(self.frame, body)

    def test_unknown_candidate_rejected(self):
        self.body['boxes'][0]['source_id'] = 'unrelated-model-prediction'
        with self.assertRaises(ValueError):
            self.store.save(self.frame, self.body)

    def test_manual_missing_person_addition(self):
        self.body['boxes'].append(dict(id='manual1', source_id=None, xyxy=[40,10,60,70]))
        self.assertEqual(len(self.store.save(self.frame, self.body)['boxes']), 2)

    def test_image_change_rejected(self):
        (self.root/'frame.png').write_bytes(b'changed')
        with self.assertRaises(Conflict):
            self.store.save(self.frame, self.body)

    def test_package_change_rejected(self):
        self.package.write_text(self.package.read_text()+'\n')
        with self.assertRaises(Conflict):
            self.store.save(self.frame, self.body)
        with self.assertRaises(ValueError):
            Store(self.package, self.root/'reviews.sqlite3')

    def test_history_preserved_after_correction(self):
        self.store.save(self.frame, self.body)
        self.body.update(expected_version=1, status='draft', confirmed=False)
        self.body['boxes'][0]['xyxy'][0] = 11
        self.store.save(self.frame, self.body)
        with self.store.connect() as db:
            rows = db.execute('SELECT version,payload FROM revisions ORDER BY version').fetchall()
        self.assertEqual([r[0] for r in rows], [1,2])
        self.assertEqual(json.loads(rows[0][1])['boxes'][0]['xyxy'][0],10)
        self.assertEqual(self.store.current(self.frame)['status'],'draft')


if __name__ == '__main__':
    unittest.main()
