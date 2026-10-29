"""Synthetic CPU tests: byte preservation, provenance, pending states and dedup.

The fake image/PNG bytes are intentionally undecodable: this audit must never
open images or construct new media. No dependency on actual private inputs.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location(
    "audit_exp0027_labels", Path(__file__).resolve().parents[1] / "scripts/audit_exp0027_labels.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

RAW = ["0 .5 .5 .8 .8", "1 .1 .2 .7 .2 .4 .8", "1 .5 .5 .2 .2", "2 .2 .2 .6 .2 .4 .6"]
OUTPUT = [None, "0 0.4 0.5 0.6 0.6", "0 .5 .5 .2 .2", "0 0.4 0.4 0.4 0.4"]


def fixture(root):
    dataset, archive = root / "dataset", root / "original.zip"
    dataset.mkdir()
    members = {"data.yaml": b"nc: 3\nnames: [fence, people-jump-fence, person-climbing-fence]\n"}
    for split in sorted(AUDIT.SPLITS):
        members[f"{split}/images/example.rf.abc.jpg"] = b"existing undecodable image bytes: " + split.encode()
        members[f"{split}/labels/example.rf.abc.txt"] = ("\n".join(RAW)+"\n").encode()
    with zipfile.ZipFile(archive,"w") as zipped:
        for name,content in members.items():
            zipped.writestr(name,content)
    member_rows = [{"name":name,"archive_indices":[index],"sha256":AUDIT.sha(content)}
                   for index,(name,content) in enumerate(members.items())]
    member_lookup = {m["name"]:m for m in member_rows}
    samples, panels, rows = [], [], []
    for name,content in members.items():
        source = dataset / "source" / name
        source.parent.mkdir(parents=True,exist_ok=True)
        source.write_bytes(content)
    for split in sorted(AUDIT.SPLITS):
        image, label = f"{split}/images/example.rf.abc.jpg", f"{split}/labels/example.rf.abc.txt"
        for name in (image,label):
            (dataset/name).parent.mkdir(parents=True,exist_ok=True)
        (dataset/image).write_bytes(members[image])
        label_bytes = ("\n".join(x for x in OUTPUT if x)+"\n").encode()
        (dataset/label).write_bytes(label_bytes)
        sample = {"image":image,"image_sha256":AUDIT.sha(members[image]),"source_label":label,
                  "source_label_sha256":AUDIT.sha(members[label]),"output_label_sha256":AUDIT.sha(label_bytes),"person_rows":3}
        samples.append(sample)
        for index,(raw,output) in enumerate(zip(RAW,OUTPUT),1):
            class_id = int(raw[0])
            rows.append({"raw":raw,"raw_sha256":AUDIT.sha(raw.encode()),"output":output,
                         "output_row_sha256":AUDIT.sha(output.encode()) if output else None,
                         "source_class_id":class_id,"source_class_name":AUDIT.CLASSES[class_id],
                         "source_type":"polygon" if index in (2,4) else "bbox",
                         "source_member":label,"source_member_index":member_lookup[label]["archive_indices"][0],
                         "source_row_index":index,"output_row_index":index-1 if output else None,
                         "output_label_sha256":AUDIT.sha(label_bytes)})
        overlay = f"review/{split}/example.rf.abc.png"
        (dataset/overlay).parent.mkdir(parents=True,exist_ok=True)
        panel_bytes = b"existing undecodable PNG panel: " + split.encode()
        (dataset/overlay).write_bytes(panel_bytes)
        panels.append({"overlay":overlay,"sha256":AUDIT.sha(panel_bytes),"source_image":image,
                       "source_label":label,"filename_base":"example"})
    summary = {"archive_sha256":AUDIT.file_sha(archive),"D0_passed":False,"training_approved":False,
               "usable_for_training":False,"semantic_person_approval":False,"status":"review_pending",
               "human_review":"pending","source_classes":AUDIT.CLASSES,"images":3,"labels":3,
               "images_excluded":0,"review_overlays":3,"filename_base_groups":1,
               "counts":{"source_rows":12,"fence_removed":3,"person_bbox":3,"person_polygon":6,
                         "person_rows":9,"test_images":1,"train_images":1,"valid_images":1,
                         "test_person_rows":3,"train_person_rows":3,"valid_person_rows":3}}
    (dataset/"summary.json").write_bytes(AUDIT.json_bytes(summary))
    (dataset/"manifest.json").write_bytes(AUDIT.json_bytes({"samples":samples,"source_members":member_rows,"review_overlays":panels}))
    (dataset/"data.yaml").write_bytes(b"nc: 1\nnames: [person]\n")
    (dataset/"provenance.jsonl").write_text("\n".join(json.dumps(row) for row in rows)+"\n")
    freeze = root/"freeze.json"
    freeze.write_bytes(AUDIT.json_bytes({"dataset/"+name:digest for name,digest in AUDIT.tree_hashes(dataset).items()}))
    return dataset,archive,freeze


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dataset,self.archive,self.freeze = fixture(self.root)
        self.output = self.root/"new-local-audit"
        self.archive_sha = AUDIT.file_sha(self.archive)
        self.freeze_sha = AUDIT.file_sha(self.freeze)

    def reanchor_synthetic_freeze(self):
        self.freeze.write_bytes(AUDIT.json_bytes({"dataset/"+p:h for p,h in AUDIT.tree_hashes(self.dataset).items()}))
        self.freeze_sha = AUDIT.file_sha(self.freeze)

    def run_audit(self):
        return AUDIT.write_audit(self.root,self.dataset,self.archive,self.freeze,self.output,self.archive_sha,self.freeze_sha)

    def alter_json(self, name, change):
        path = self.dataset/name
        value = json.loads(path.read_text())
        change(value)
        path.write_bytes(AUDIT.json_bytes(value))
        self.reanchor_synthetic_freeze()

    def test_success_preserves_all_inputs_and_uses_existing_media_only(self):
        before = AUDIT.tree_hashes(self.dataset)
        counts = self.run_audit()
        self.assertEqual(AUDIT.tree_hashes(self.dataset),before)
        self.assertEqual(AUDIT.file_sha(self.archive),self.archive_sha)
        self.assertEqual(counts["panel_review_status_counts"],{"review_pending":3,"reviewed":0})
        self.assertEqual(counts["row_review_status_counts"],{"review_pending":9,"reviewed":0})
        self.assertEqual(counts["counts"]["person_polygon"],6)
        evidence = json.loads((self.output/"preservation.local.json").read_text())
        self.assertEqual(evidence["dataset_file_hashes_before"],evidence["dataset_file_hashes_after"])
        self.assertTrue(evidence["all_input_bytes_preserved"])
        self.assertFalse(any(p.suffix in (".png",".jpg") for p in self.output.iterdir()))
        self.assertIn("../dataset/source/",(self.output/"index.local.md").read_text())
        for name in ("panel-review-template.local.json","row-review-template.local.json"):
            for row in json.loads((self.output/name).read_text()):
                AUDIT.validate_pending_review(row)
        self.assertFalse(counts["D0_passed"])
        self.assertFalse(counts["model_test_evaluation_performed"])

    def test_overlap_dedup_includes_multiple_rows_per_image_and_shared_risk_row(self):
        counts = self.run_audit()["priority"]
        self.assertEqual(counts["people_jump_fence"],{"rows":6,"unique_images":3,"unique_panels":3})
        self.assertEqual(counts["person_polygon"],{"rows":6,"unique_images":3,"unique_panels":3})
        self.assertEqual(counts["overlap"],{"rows":3,"unique_images":3,"unique_panels":3})
        self.assertEqual(counts["deduplicated"],{"rows":9,"unique_images":3,"unique_panels":3})
        priority = json.loads((self.output/"priority.local.json").read_text())
        self.assertEqual(len(priority["panel_ids"]),3)
        self.assertEqual(len({(r["source_member"],r["source_row_index"]) for r in priority["rows"]}),9)
        self.assertEqual(sum(len(r["reasons"]) == 2 for r in priority["rows"]),3)

    def test_all_semantic_assertions_and_invalid_enum_rejected_during_preparation(self):
        for key in AUDIT.PENDING_VALUES:
            record = dict(AUDIT.PENDING_VALUES)
            record[key] = "invented" if key != "review_pending" else False
            with self.subTest(field=key),self.assertRaises(ValueError):
                AUDIT.validate_pending_review(record)

    def test_preparation_state_changes_rejected_even_with_reanchored_fixture(self):
        self.alter_json("summary.json",lambda s:s.update(D0_passed=True))
        with self.assertRaisesRegex(ValueError,"preparation state"):
            self.run_audit()
        self.assertFalse(self.output.exists())

    def test_all_input_kinds_tamper_rejected_by_pinned_freeze(self):
        for name in ("source/train/images/example.rf.abc.jpg","train/images/example.rf.abc.jpg",
                     "source/train/labels/example.rf.abc.txt","train/labels/example.rf.abc.txt",
                     "review/train/example.rf.abc.png","manifest.json","provenance.jsonl","summary.json","data.yaml"):
            path = self.dataset/name
            original = path.read_bytes()
            path.write_bytes(original+b"tampered")
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,"freeze"):
                self.run_audit()
            self.assertFalse(self.output.exists())
            path.write_bytes(original)

    def test_added_file_and_missing_file_rejected(self):
        extra = self.dataset/"unapproved.cache"
        extra.write_bytes(b"unexpected")
        with self.assertRaises(ValueError):
            self.run_audit()
        extra.unlink()
        victim = self.dataset/"review/train/example.rf.abc.png"
        victim.unlink()
        with self.assertRaises(ValueError):
            self.run_audit()
        self.assertFalse(self.output.exists())

    def test_original_zip_and_freeze_tamper_rejected(self):
        original = self.archive.read_bytes()
        self.archive.write_bytes(original+b"tamper")
        with self.assertRaisesRegex(ValueError,"ZIP SHA256"):
            self.run_audit()
        self.archive.write_bytes(original)
        self.freeze.write_bytes(self.freeze.read_bytes()+b"\n")
        with self.assertRaisesRegex(ValueError,"freeze SHA256"):
            self.run_audit()
        self.assertFalse(self.output.exists())

    def test_panel_to_image_mapping_must_match_even_with_reanchored_fixture(self):
        self.alter_json("manifest.json",lambda m:m["review_overlays"][0].update(source_image="valid/images/wrong.jpg"))
        with self.assertRaisesRegex(ValueError,"matching failure"):
            self.run_audit()
        self.assertFalse(self.output.exists())

    def test_priority_rows_without_panel_rejected_and_row_duplication_rejected(self):
        rows = [{"source_member":"train/labels/x.txt","source_row_index":1,"source_class_id":1,"source_type":"polygon"}]
        with self.assertRaisesRegex(ValueError,"lacks existing panel"):
            AUDIT.priority_inventory(rows,[])
        with self.assertRaisesRegex(ValueError,"Duplicate annotation row"):
            AUDIT.priority_inventory(rows+rows,[])

    def test_independent_provenance_reconstruction_detects_tamper(self):
        path = self.dataset/"provenance.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]["output_row_index"] = 99
        path.write_text("\n".join(json.dumps(row) for row in rows)+"\n")
        self.reanchor_synthetic_freeze()
        with self.assertRaisesRegex(ValueError,"Provenance"):
            self.run_audit()
        self.assertFalse(self.output.exists())

    def test_independent_polygon_and_bbox_rules(self):
        for raw,expected in zip(RAW,OUTPUT):
            self.assertEqual(AUDIT.conversion(raw)["output"],expected)
        self.assertEqual(AUDIT.conversion("1 0.5000 5e-1 .40 .40")["output"],"0 0.5000 5e-1 .40 .40")
        for raw in ("2 .5 .5 nan .2","2 .1 .5 .5 .2","2 .1 .2 .1 .3 .1 .4"):
            with self.assertRaises(ValueError):
                AUDIT.conversion(raw)

    def test_existing_audit_and_protected_output_never_overwritten(self):
        self.run_audit()
        sentinel = self.output/"reviewer-work.txt"
        sentinel.write_text("keep human notes")
        before = AUDIT.tree_hashes(self.output)
        with self.assertRaises(FileExistsError):
            self.run_audit()
        self.assertEqual(AUDIT.tree_hashes(self.output),before)
        self.output = self.dataset/"new-audit"
        with self.assertRaisesRegex(ValueError,"overlaps protected"):
            self.run_audit()
        self.assertFalse(self.output.exists())
        self.output = self.root/"unused"/".."/"dataset"/"new-audit"
        with self.assertRaisesRegex(ValueError,"overlaps protected"):
            self.run_audit()
        self.assertFalse((self.dataset/"new-audit").exists())

    def test_symlink_output_and_input_rejected(self):
        self.output.symlink_to(self.root/"elsewhere",target_is_directory=True)
        with self.assertRaisesRegex(ValueError,"Symlink output"):
            self.run_audit()
        self.output.unlink()
        source = self.dataset/"review/train/example.rf.abc.png"
        target = self.root/"original-panel"
        target.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(target)
        with self.assertRaisesRegex(ValueError,"Symlink dataset"):
            self.run_audit()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
