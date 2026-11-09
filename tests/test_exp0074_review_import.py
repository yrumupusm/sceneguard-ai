"""The current chat completion must not become a general draft-label release."""
import copy
import unittest
from scripts.import_exp0074_review import confirmed_rows, PACKAGE_SHA


class ApprovalScopeTests(unittest.TestCase):
    def setUp(self):
        frames=[dict(frame_id=f'exp0074-p01-frame-{i:06d}',image_sha256=str(i)) for i in (168,175,185)]
        self.package={'frames':frames}
        self.snapshot=dict(frames=copy.deepcopy(frames),package_sha256=PACKAGE_SHA,
            revisions={f['frame_id']:dict(frame_id=f['frame_id'],version=1,status='draft',
                confirmed=True,package_sha256=PACKAGE_SHA,image_sha256=f['image_sha256'],
                note='',boxes=[{'id':'saved'}],empty_confirmed=False) for f in frames})
        self.chat=dict(source='current_user_chat',verbatim='검수완료',package_sha256=PACKAGE_SHA,
            editor_versions={f['frame_id']:1 for f in frames},training_authorized=False)

    def test_exact_saved_drafts_plus_current_completion(self):
        self.assertEqual(len(confirmed_rows(self.package,self.snapshot,self.chat)),3)
        self.assertTrue(all(r['status']=='draft' for r in self.snapshot['revisions'].values()))

    def test_missing_completeness_is_not_completed_by_chat(self):
        next(iter(self.snapshot['revisions'].values()))['confirmed']=False
        with self.assertRaises(ValueError):confirmed_rows(self.package,self.snapshot,self.chat)

    def test_changed_revision_requires_new_binding(self):
        next(iter(self.snapshot['revisions'].values()))['version']=2
        with self.assertRaises(ValueError):confirmed_rows(self.package,self.snapshot,self.chat)

    def test_uncertainty_is_not_overridden(self):
        next(iter(self.snapshot['revisions'].values()))['status']='uncertain'
        with self.assertRaises(ValueError):confirmed_rows(self.package,self.snapshot,self.chat)

    def test_old_memo_is_not_current_completion(self):
        self.chat['source']='historical_memo'
        with self.assertRaises(ValueError):confirmed_rows(self.package,self.snapshot,self.chat)


if __name__=='__main__':unittest.main()
