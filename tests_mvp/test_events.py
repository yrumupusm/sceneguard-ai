import copy
import unittest

from mvp.events import EventMerger, classify


def result(actions, completion="not_confirmed"):
    return {"raw_response": "synthetic test only", "parse": "strict",
            "parsed": {"observed_actions": actions, "crossing_completion": completion,
                       "visible_evidence": "synthetic evidence", "uncertainties": ""},
            "timing": {}, "input_metadata": {}, "output_tokens": 1, "gpu_memory": None}


class EventTests(unittest.TestCase):
    def test_completion_only_never_crossing(self):
        self.assertEqual(classify(result(["passage_or_waiting"], "observed")),
                         [("observed_other", "passage_or_waiting")])

    def test_contact_indeterminate_and_parse_failure_are_distinct(self):
        self.assertEqual(classify(result(["contact"])), [("contact_review", "contact")])
        self.assertEqual(classify(result(["indeterminate"])), [("indeterminate", "indeterminate")])
        self.assertEqual(classify({"parsed": None}), [("parse_failed", None)])
        for actions in (["unknown"], [], [None], "contact"):
            self.assertEqual(classify(result(actions)), [("parse_failed", None)])

    def test_multiple_actions_preserve_uncertainty(self):
        self.assertEqual(classify(result(["climbing_attempt_or_in_progress", "contact", "indeterminate"])),
                         [("candidate", "climbing_attempt_or_in_progress"),
                          ("contact_review", "contact"), ("indeterminate", "indeterminate")])

    def test_merge_overlap_same_action_preserves_windows_and_first_emission(self):
        merger = EventMerger("camera-test")
        def record(index, interval, action="stepping_over_boundary"):
            return {"window_id": f"w{index:06d}", "estimated_interval": interval,
                    "states": [("candidate", action)], "emission": {"utc": str(index), "monotonic_ns": index},
                    "available_at_source_time": interval[1], "last_input_pts": interval[1] - .5,
                    "last_arrived_pts": interval[1]}
        original = record(1, [0, 5])
        snapshot = copy.deepcopy(original)
        first = merger.add(original)[0]
        merger.add(record(2, [2.5, 7.5]))
        self.assertEqual(original, snapshot)
        self.assertEqual(first["constituent_windows"], ["w000001"])
        self.assertEqual(merger.events[0]["constituent_windows"], ["w000001", "w000002"])
        self.assertEqual(merger.events[0]["estimated_interval"], [0, 7.5])
        self.assertEqual(merger.events[0]["first_emission"], snapshot["emission"])
        self.assertFalse(merger.events[0]["identity_claim"])
        merger.add(record(3, [7.5, 10]))  # touching is not overlapping
        merger.add(record(4, [8, 11], "climbing_attempt_or_in_progress"))
        self.assertEqual(len(merger.events), 3)


if __name__ == "__main__":
    unittest.main()
