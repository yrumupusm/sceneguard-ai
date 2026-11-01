import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from webapp.app import app
from pathlib import Path

from sceneguard.gate_activity_episodes import GateActivityEpisodes
from webapp.mvp_registration import register
from webapp.incident import load_bundle


def write(path, value):
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RegistrationTests(unittest.TestCase):
    def test_empty_run_registers_without_replacing_existing_data_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); scope = dict(session_id='run1', camera_id='C3', gate_id='gate')
            bundle = GateActivityEpisodes(scope, namespace='run1').export()
            bundle.update(experiment='MVP-0002', analysis_run_id='run1', source_evidence_mode='computed_in_current_run',
                          source_window=[0, 1], video_id='video', source_resolution_log=[])
            (root/'decision').mkdir(); cards = root/'decision'/'cards.json'; cards_hash = write(cards, bundle)
            frames = root/'frames.json'; frames_hash = write(frames, [])
            video = root/'original.mp4'; video.write_bytes(b'video'); video_hash = hashlib.sha256(video.read_bytes()).hexdigest()
            manifest = root/'viewer-manifest.json'
            write(manifest, dict(kind='sceneguard_mvp_viewer_v1', experiment='MVP-0002', contract='gate_activity_episodes_v1',
                live_notifications_enabled=False, manual_reviews_modified=False, session_id='run1', run_id='run1',
                source_window=[0,1], video_id='video', source_path='/source/test.mp4', source_sha256='a'*64, camera_id='C3', execution_mode='saved_cache',
                cards_path=str(cards), cards_sha256=cards_hash, source_frames_path=str(frames), source_frames_sha256=frames_hash,
                media=[dict(key='original', path=str(video), sha256=video_hash, source_start_pts=0)]))
            write(root/'request.json', dict(video='/source/test.mp4', camera='C3', input_sha256={'/source/test.mp4':'a'*64}))
            write(root/'status.json', dict(state='analysis_complete', manifest_path=str(manifest)))
            repo = root/'repo'; (repo/'records').mkdir(parents=True); write(repo/'records'/'catalog.json', {'experiments': []})
            config = root/'config.json'; old = {'artifact_allow_root':str(root), 'repo_root':str(repo), 'runtime_dir':str(root),
                'artifacts':{'old':{'kind':'video','path':'unchanged'}}, 'incident_bundles':{'old':{'experiment_id':'OLD'}}}
            write(config, old)
            write(root/'status.json', dict(state='analyzing', manifest_path=str(manifest)))
            with self.assertRaises(ValueError): register(config, manifest, 'run1')
            self.assertEqual(json.loads(config.read_text()), old)
            write(root/'status.json', dict(state='analysis_complete', manifest_path=str(manifest)))
            register(config, manifest, 'run1')
            current = json.loads(config.read_text())
            self.assertEqual(current['incident_bundles']['old'], old['incident_bundles']['old'])
            self.assertEqual(current['artifacts']['old'], old['artifacts']['old'])
            loaded = load_bundle(current, 'run1')
            self.assertEqual(loaded['timeline'], [])
            with patch.dict('os.environ', {'SCENEGUARD_LAB_CONFIG':str(config)}):
                response = TestClient(app, base_url='http://localhost').get('/artifacts/run1-video', headers={'Range':'bytes=0-2'})
                self.assertEqual(response.status_code, 206)
                self.assertEqual(response.content, b'vid')
            self.assertEqual(loaded['provenance_label'], '저장 검출 기반 분석')
            register(config, manifest, 'run1', make_default=True)
            self.assertEqual(json.loads(config.read_text())['mvp_default_registration'], 'run1')
            cards.write_text('{}')
            with self.assertRaises(ValueError): load_bundle(current, 'run1')
            with self.assertRaises(ValueError): register(config, manifest, 'run1')


if __name__ == '__main__': unittest.main()
