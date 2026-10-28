"""Action states and overlap grouping; no identity or ground-truth heuristics."""

import copy


ACTIONS = frozenset({"passage_or_waiting", "contact", "climbing_attempt_or_in_progress",
                     "stepping_over_boundary", "indeterminate"})
COMPLETIONS = frozenset({"observed", "not_confirmed", "indeterminate"})


def classify(result):
    """Unknown or invalid output can never become a normal/no-event result."""
    parsed = result.get("parsed")
    if not isinstance(parsed, dict):
        return [("parse_failed", None)]
    actions = parsed.get("observed_actions")
    if (not isinstance(actions, list) or not actions
            or any(not isinstance(a, str) or a not in ACTIONS for a in actions)
            or parsed.get("crossing_completion") not in COMPLETIONS
            or not isinstance(parsed.get("visible_evidence"), str)
            or not isinstance(parsed.get("uncertainties"), str)):
        return [("parse_failed", None)]
    states = []
    for action in dict.fromkeys(actions):
        if action in {"climbing_attempt_or_in_progress", "stepping_over_boundary"}:
            states.append(("candidate", action))
        elif action == "contact":
            states.append(("contact_review", action))
        elif action == "indeterminate":
            states.append(("indeterminate", action))
    # Completion=observed alone is deliberately never a crossing candidate.
    return states or [("observed_other", "passage_or_waiting")]


class EventMerger:
    """Only same camera + state + action + strictly overlapping intervals merge.

    Groups are review units, never claims that windows show the same person.
    Every update keeps the original emission and every contributing window.
    """

    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.events = []

    def add(self, record):
        updates = []
        for state, action in record["states"]:
            if state == "observed_other":
                continue
            start, end = record["estimated_interval"]
            found = None
            for event in reversed(self.events):
                if (event["state"], event["action"]) == (state, action) and (
                        start < event["estimated_interval"][1]
                        and end > event["estimated_interval"][0]):
                    found = event
                    break
            if found is None:
                found = dict(event_id=f"event{len(self.events) + 1:06d}",
                             camera_id=self.camera_id, state=state, action=action,
                             estimated_interval=[start, end], constituent_windows=[], constituents=[],
                             first_emission=copy.deepcopy(record["emission"]),
                             first_available_at_source_time=record["available_at_source_time"],
                             first_last_input_pts=record["last_input_pts"],
                             identity_claim=False)
                self.events.append(found)
            found["estimated_interval"][0] = min(start, found["estimated_interval"][0])
            found["estimated_interval"][1] = max(end, found["estimated_interval"][1])
            found["constituent_windows"].append(record["window_id"])
            found["constituents"].append({"window_id": record["window_id"],
                                          "result": record.get("result"),
                                          "window_record": record.get("window_record"),
                                          "model_claims": copy.deepcopy(record.get("model_claims")),
                                          "claims_are_ground_truth": False})
            found["last_input_pts"] = record["last_input_pts"]
            found["last_arrived_pts"] = record["last_arrived_pts"]
            found["updated_at"] = copy.deepcopy(record["emission"])
            updates.append(copy.deepcopy(found))
        return updates
