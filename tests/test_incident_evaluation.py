"""Synthetic EXP-0032 event-window evaluation tests. Never model-accuracy claims."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from sceneguard.incident_evaluation import (
    validate_manifest, evaluate_window_presence, dedup_incidents,
    read_saved_events, digest,
)


def synthetic_video(positive=True):
    return {
        "video_id":"E01_900","source_sha256":"a"*64,"camera_group":"C_SYN",
        "role":"development_only","evaluated_window":[0,20],
        "cache_metadata":"unused", "replay_summary":"unused", "prediction_file":"unused",
        "reference_windows":[
          {"window_id":"negative","interval":[0,5],"status":"confirmed_negative_window",
           "evidence":"user_review:q01","review_basis":"human_confirmed_for_window"},
          {"window_id":"positive","interval":[6,11],"status":"confirmed_positive_window",
           "evidence":"user_review:q04","review_basis":"human_confirmed_for_window"},
          {"window_id":"provisional","interval":[12,19],
           "status":"provisional_positive_window","evidence":"official approximate",
           "review_basis":"official_reference_and_codex_visual_draft"},
        ],
    }


def e(i, pts, raw=7):
    return {"original_row":i,"emitted_at_pts":pts,"estimated_at_pts":pts-.1,
            "raw_track_id":raw,"direction":"a_to_b"}


class IncidentUnitTests(unittest.TestCase):
    def setUp(self):
        self.m={"schema_version":1,"experiment_id":"EXP-0032","videos":[synthetic_video()]}

    def test_confirmed_negative_and_positive_are_scored_only_in_reviewed_windows(self):
        output=evaluate_window_presence(self.m,{"E01_900":[e(1,7),e(2,14)]})
        metrics=output["metrics"]
        self.assertEqual(metrics["positive_window_coverage"],1)
        self.assertEqual(metrics["false_alarm_candidate_episodes_in_confirmed_negative"],0)
        self.assertEqual(metrics["unreviewed_incidents"],1)
        self.assertIsNone(metrics["confirmed_complete_incident_recall"])
        self.assertIsNone(metrics["false_alarms_per_hour"])

    def test_event_after_positive_window_is_missed_not_called_tp(self):
        output=evaluate_window_presence(self.m,{"E01_900":[e(1,11.3)]})
        self.assertEqual(output["metrics"]["positive_windows_with_candidate"],0)
        positive=output["per_video"][0]["reference_windows"][1]
        self.assertEqual(positive["interpretation"],"missed_in_reviewed_window")

    def test_negative_candidate_is_one_fp_episode_not_person_count(self):
        result=evaluate_window_presence(self.m,{"E01_900":[e(1,1.0,2),e(2,1.5,3)]})
        self.assertEqual(result["metrics"]["negative_windows_with_candidate"],1)
        self.assertEqual(result["metrics"]["false_alarm_candidate_episodes_in_confirmed_negative"],1)
        self.assertEqual(result["metrics"]["raw_candidates"],2)

    def test_incidents_more_than_two_seconds_apart_stay_separate(self):
        groups=dedup_incidents([e(1,1.),e(2,3.),e(3,5.01)])
        self.assertEqual([x["original_event_rows"] for x in groups],[[1,2],[3]])

    def test_positive_end_is_exclusive(self):
        result=evaluate_window_presence(self.m,{"E01_900":[e(1,11)]})
        self.assertEqual(result["metrics"]["positive_windows_with_candidate"],0)

    def test_provisional_negative_never_becomes_verified_time(self):
        m=copy.deepcopy(self.m)
        m["videos"][0]["reference_windows"].append({
            "window_id":"might-be-neg","interval":[19,20],
            "status":"provisional_negative_window","evidence":"candidate only",
            "review_basis":"user_proposed"})
        result=evaluate_window_presence(m,{"E01_900":[e(1,19.5)]})
        self.assertEqual(result["metrics"]["verified_negative_seconds"],5)
        self.assertEqual(result["metrics"]["false_alarm_candidate_episodes_in_confirmed_negative"],0)

    def test_no_predictions_yields_missed_positive_not_false_true_negative(self):
        result=evaluate_window_presence(self.m,{"E01_900":[]})
        self.assertEqual(result["metrics"]["confirmed_positive_windows"],1)
        self.assertEqual(result["metrics"]["positive_windows_with_candidate"],0)
        self.assertEqual(result["metrics"]["confirmed_negative_windows"],1)

    def test_missing_complete_source_input_rejected(self):
        with self.assertRaisesRegex(ValueError,"Missing complete"):
            evaluate_window_presence(self.m,{})

    def test_human_reference_requires_human_provenance(self):
        m=copy.deepcopy(self.m)
        m["videos"][0]["reference_windows"][0]["review_basis"]="official_annotation"
        with self.assertRaisesRegex(ValueError,"human-confirmed"):
            validate_manifest(m)

    def test_overlap_of_confirmed_positive_and_negative_rejected(self):
        m=copy.deepcopy(self.m)
        m["videos"][0]["reference_windows"][1]["interval"]=[4,11]
        with self.assertRaisesRegex(ValueError,"Overlapping"):
            validate_manifest(m)

    def test_provisional_and_confirmed_overlap_does_not_change_truth(self):
        m=copy.deepcopy(self.m)
        m["videos"][0]["reference_windows"][2]["interval"]=[8,19]
        result=evaluate_window_presence(m,{"E01_900":[e(1,14)]})
        self.assertEqual(result["metrics"]["positive_windows_with_candidate"],0)

    def test_repeated_video_or_label_ids_rejected(self):
        m=copy.deepcopy(self.m);m["videos"].append(copy.deepcopy(m["videos"][0]))
        with self.assertRaisesRegex(ValueError,"Unique video_id"):
            validate_manifest(m)
        m=copy.deepcopy(self.m)
        m["videos"][0]["reference_windows"][1]["window_id"]="negative"
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            validate_manifest(m)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        cache=root/"cache";cache.mkdir()
        replay=root/"replay";(replay/"gap").mkdir(parents=True)
        self.meta_path=cache/"run.json"
        self.cache_path=cache/"person_cache.jsonl"
        self.events_path=replay/"gap"/"events.jsonl"
        self.summary_path=replay/"summary.json"
        self.cache_path.write_text(json.dumps({"pts":48,"native_pts":0})+"\n")
        self.item={
            "video_id":"E01_900","source_sha256":"a"*64,
            "evaluated_window":[48,60],"cache_metadata":str(self.meta_path),
            "replay_summary":str(self.summary_path),"prediction_file":str(self.events_path)}
        self.meta=dict(status="complete",video_id="E01_900",source_sha256="a"*64,
            requested_window=[48,60],first_pts=48.0,last_pts=59.966667,frames=360,
            person_cache=dict(sha256=digest(self.cache_path),
                              stage="model_return_after_internal_filters_nms_global_cap_before_project_score"))
        self.events=[dict(video_id="E01_900",condition="gap",emitted_at_pts=55.2,
                 candidate_pts=55.05,candidate_interval=[55.0,55.1],track_id=8)]
        self.save()

    def save(self):
        self.meta_path.write_text(json.dumps(self.meta))
        self.events_path.write_text("".join(json.dumps(r)+"\n" for r in self.events))
        self.summary_path.write_text(json.dumps({
            "status":"complete","comparisons":[{"condition":"gap",
               "input_sha256":{"cache":digest(self.cache_path),
                                "metadata":digest(self.meta_path)},
               "candidates":len(self.events)}]}))

    def test_valid_bound_source_and_replay(self):
        events,provenance=read_saved_events(self.item)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["emitted_at_pts"],55.2)
        self.assertEqual(len(provenance["event_sha256"]),64)

    def test_empty_but_complete_prediction_file_is_valid(self):
        self.events=[];self.save()
        events,_=read_saved_events(self.item)
        self.assertEqual(events,[])

    def test_cache_tamper_rejected(self):
        self.cache_path.write_text("tampered\n")
        with self.assertRaisesRegex(ValueError,"person cache"):
            read_saved_events(self.item)

    def test_source_sha_mismatch_rejected(self):
        self.item["source_sha256"]="b"*64
        with self.assertRaisesRegex(ValueError,"wrong video/cache"):
            read_saved_events(self.item)

    def test_replay_summary_mismatch_rejected(self):
        self.summary_path.write_text(json.dumps({"status":"complete","comparisons":[]}))
        with self.assertRaisesRegex(ValueError,"exactly one gap"):
            read_saved_events(self.item)

    def test_strict_events_not_accepted_as_gap(self):
        self.events[0]["condition"]="strict";self.save()
        with self.assertRaisesRegex(ValueError,"Mixed video"):
            read_saved_events(self.item)

    def test_incorrect_source_window_end_rejected(self):
        self.item["evaluated_window"]=[48,62]
        with self.assertRaisesRegex(ValueError,"wrong clip end"):
            read_saved_events(self.item)

    def test_out_of_order_event_times_rejected(self):
        self.events[0]["candidate_pts"]=58
        self.save()
        with self.assertRaisesRegex(ValueError,"timestamps"):
            read_saved_events(self.item)


if __name__=="__main__":
    unittest.main()
