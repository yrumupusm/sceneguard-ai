import unittest
from copy import deepcopy

from sceneguard.exp0047_media import grouped_specs, validate_mapping


class MediaTests(unittest.TestCase):
    def test_no_actual_release_means_no_release_video(self):
        self.assertEqual(grouped_specs([{'pts':0.},{'pts':10.}],[]),[])

    def test_release_groups_merge_only_adjacent_actual_outcomes(self):
        frames=[{'pts':0.},{'pts':20.}]
        rows=[dict(kind='outward_loss',changed_event_ids=['a'],last_observed_pts=4.,
                   decision_time_pts=5.,resolution_id='a'),
              dict(kind='outward_loss',changed_event_ids=['b'],last_observed_pts=6.,
                   decision_time_pts=7.,resolution_id='b'),
              dict(kind='outward_loss',changed_event_ids=[],last_observed_pts=12.,
                   decision_time_pts=13.,resolution_id='nochange')]
        specs=grouped_specs(frames,rows)
        self.assertEqual(len(specs),1)
        self.assertEqual(specs[0]['resolution_ids'],['a','b'])
        self.assertEqual((specs[0]['start'],specs[0]['end']),(2.,8.))

    def test_future_state_observation_direction_and_clock_rejected(self):
        row=dict(source_pts=1.,native_pts=30,time_base='1/30',
                 cards=[{'lifecycle_updated_pts':1.}],
                 focus=dict(last={'pts':.9},motion={'end_pts':.8}))
        validate_mapping([row])
        for field in ('state','box','direction','clock'):
            bad=deepcopy(row)
            if field=='state':bad['cards'][0]['lifecycle_updated_pts']=2.
            elif field=='box':bad['focus']['last']['pts']=2.
            elif field=='direction':bad['focus']['motion']['end_pts']=2.
            else:bad['native_pts']=31
            with self.subTest(field=field),self.assertRaises(ValueError):validate_mapping([bad])


if __name__=='__main__':unittest.main()
