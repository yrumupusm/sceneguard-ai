"""Meaningful display-only native clock and detached causal timeline checks."""
import copy
import unittest
from sceneguard.exp0043_comparison_media import frame_metadata, validate_clocks, clip_specs


def bundle(times):
    return dict(events=[dict(decision_time_pts=t) for t in times],timeline=[
        dict(decision_time_pts=t,notify=True,action='create',incident_id=str(t),
             card=dict(accept_until_pts=t+3,notification_eligible=True)) for t in times])


def row(at,score=.25):
    return dict(pts=at,native_pts=round(at*300),time_base='1/300',frame_index=round(at*30),
                score=score,signals=[])


class ComparisonMediaTests(unittest.TestCase):
    def test_three_timelines_are_independent_and_prefix_only(self):
        bundles=dict(original=bundle([56,70.1]),exp42=bundle([54.7]),exp43=bundle([55,65.5]))
        saved=copy.deepcopy(bundles)
        m=frame_metadata(row(65),row(65,.5),bundles,48)
        self.assertEqual(m['statuses']['original']['latest_candidate_pts'],56)
        self.assertEqual(m['statuses']['exp42']['latest_candidate_pts'],54.7)
        self.assertEqual(m['statuses']['exp43']['latest_candidate_pts'],55)
        self.assertEqual(m['statuses']['exp43']['first_notification_pts'],55)
        self.assertNotEqual(m['statuses']['original']['first_notification_pts'],55)
        self.assertEqual(bundles,saved)

    def test_rewind_reconstructs_prefix_without_future_first_notice(self):
        bundles=dict(original=bundle([56]),exp42=bundle([54.7]),exp43=bundle([55]))
        late=frame_metadata(row(57),row(57),bundles,48)
        early=frame_metadata(row(54),row(54),bundles,48)
        self.assertEqual(late['statuses']['exp43']['candidate_rows'],1)
        self.assertEqual(early['statuses']['exp43']['candidate_rows'],0)
        self.assertIsNone(early['statuses']['exp43']['first_notification_pts'])

    def test_exact_native_clock_and_source_pair_match(self):
        validate_clocks([row(48),row(48.1)],[row(48),row(48.1,.6)])
        wrong=row(48.1);wrong['native_pts']+=1
        with self.assertRaises(ValueError): validate_clocks([row(48.1)],[wrong])
        with self.assertRaises(ValueError): validate_clocks([row(48.1),row(48)],[row(48.1),row(48)])
        with self.assertRaises(ValueError): validate_clocks([row(48)],[])

    def test_core_presentation_clock_is_relative_to_core_first_native(self):
        bundles={k:bundle([]) for k in ('original','exp42','exp43')}
        m=frame_metadata(row(65),row(65),bundles,64)
        self.assertEqual(m['presentation_pts'],1)
        self.assertEqual(m['source_pts'],65)
        self.assertEqual(m['source_native_pts'],19500)
        self.assertEqual(m['baseline_score'],.25)
        self.assertEqual(m['candidate_score'],.25)

    def test_requested_four_clips_include_entire_windows_and_fixed_cores(self):
        seven=clip_specs('007',[row(48),row(104.9)])
        thirty=clip_specs('030',[row(84),row(99.9)])
        self.assertEqual(len(seven+thirty),4)
        self.assertEqual(seven[0]['range'],[48,104.9])
        self.assertEqual(seven[1]['range'],[64,74])
        self.assertEqual(thirty[1]['range'],[90,94])


if __name__=='__main__': unittest.main()
