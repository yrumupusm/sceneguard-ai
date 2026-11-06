"""Conservative multi-camera grouping before clip extraction."""
import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from prepare_action_normal_data import combined_split


def row(key,scenario,start,place="park",family=4):
    return dict(source_id=key,source_sha256=key,label_sha256="label-"+key,
                scenario=scenario,scenario_family=family,excluded=False,errors=[],
                label=dict(info=dict(location=place,date_captured=start),event_classes={"wall_over":1}),
                video=dict(stream_duration_seconds=10))

class SplitContracts(unittest.TestCase):
    def test_staggered_cameras_same_scenario(self):
        data=[row("a",1,"2021/09/11 10:00:00"),row("b",1,"2021/09/12 15:00:00")]
        out=combined_split(data)
        self.assertEqual(len(out["groups"]),1)
        self.assertEqual(len({a["split"] for a in out["assignments"]}),1)
    def test_overlap_is_transitive(self):
        data=[row("a",1,"2021/09/11 10:00:00"),row("b",2,"2021/09/11 10:00:09"),row("c",3,"2021/09/11 10:00:18")]
        self.assertEqual(len(combined_split(data)["groups"]),1)
    def test_normal_family_does_not_collide(self):
        data=[row("a",1,"2021/09/11 10:00:00",family=32),row("b",1,"2021/09/11 15:00:00",family=33)]
        self.assertEqual(len(combined_split(data)["groups"]),2)
    def test_exact_copy_conflicting_place_quarantined(self):
        data=[row("a",1,"2021/09/11 10:00:00"),row("b",2,"2021/09/11 15:00:00",place="elsewhere")]
        data[1]["source_sha256"]="a"
        self.assertEqual({a["split"] for a in combined_split(data)["assignments"]},{"quarantine"})
    def test_exclusions_and_errors_stay_out(self):
        data=[row("a",1,"2021/09/11 10:00:00"),row("b",1,"2021/09/11 15:00:00")]
        data[0]["excluded"]=True;data[1]["errors"]=[{"code":"event_reversed"}]
        self.assertEqual({a["split"] for a in combined_split(data)["assignments"]},{"excluded","quarantine"})
    def test_site_holdout(self):
        data=[row("a",1,"2021/09/11 10:00:00",place="busan_children-grand-park")]
        self.assertEqual(combined_split(data)["assignments"][0]["split"],"test")

if __name__=="__main__":unittest.main()
