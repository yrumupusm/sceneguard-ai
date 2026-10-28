import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HistoricalRecordContract(unittest.TestCase):
    def test_report_hashes_and_measurement_provenance(self):
        catalog = json.loads((ROOT / "records/catalog.json").read_text())
        self.assertEqual([x["experiment_id"] for x in catalog["experiments"]], [f"EXP-{i:04d}" for i in range(1, 8)])
        for row in catalog["experiments"]:
            self.assertEqual(hashlib.sha256((ROOT / row["report_path"]).read_bytes()).hexdigest(), row["report_sha256"])
            self.assertIsNone(row["agent_model_effective"])
            self.assertEqual(row["review_status"], "AI_draft")
            data = json.loads((ROOT / row["metrics_path"]).read_text())
            self.assertFalse(data["cross_experiment_comparable"])
            for metric in data["metrics"]:
                self.assertTrue(metric["source"])
                self.assertTrue(metric["scope"])
                self.assertTrue(metric["unit"])
                if metric["value"] is not None:
                    self.assertIsInstance(metric["value"], (float, int))
                    self.assertGreater(metric["sample_n"], 0)
                    self.assertEqual(len(metric["source_sha256"]), 64)
            self.assertIsNone(data["metrics"][-1]["value"])

    def test_public_records_have_no_private_payloads_or_absolute_paths(self):
        prohibited = ("raw_response", "generated_token_ids", "access_token", "refresh_token", "api_key")
        for path in (ROOT / "records").rglob("*.json"):
            value = json.loads(path.read_text())
            def visit(item):
                if isinstance(item, dict):
                    for key, val in item.items():
                        self.assertNotIn(key.lower(), prohibited)
                        visit(val)
                elif isinstance(item, list):
                    for val in item:
                        visit(val)
                elif isinstance(item, str):
                    self.assertFalse(item.startswith(("/home/", "C:\\", "\\\\wsl")))
            visit(value)


if __name__ == "__main__":
    unittest.main()
