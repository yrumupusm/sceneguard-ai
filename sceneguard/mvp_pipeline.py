"""MVP-1 release candidate: selected video -> current rules -> activity episodes.

No dependency on an EXP result directory. The existing video front-end supplies
validated FCOS observations and ByteTrack results. The same-run image paths feed
the adopted direction, portal, lifecycle and activity rules; rejected action
scores never become candidates. Offline analysis only; this module sends no
notifications and never changes a review DB or the service default.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any

VERSION = 'MVP-1.0-rc4'
CONTRACT = 'gate_activity_episodes_v1'
STATES = {'침입 의심', '침입 확인', '의심 해제'}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def finite(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite source timestamp required')
    return float(value)


def validate_frames(frames: list[dict], *, source_size: list[int] | None = None) -> None:
    if not frames:
        raise ValueError('An empty analysis window is not a successful negative result')
    previous = -1.0
    for i, frame in enumerate(frames):
        at = finite(frame['pts'])
        if frame['frame_index'] != i or at < 0 or at <= previous:
            raise ValueError('Use the complete ordered original source frame partition')
        if type(frame['native_pts']) is not int or frame['native_pts'] < 0:
            raise ValueError('Nonnegative integer native PTS required')
        tb = Fraction(frame['time_base'])
        if tb <= 0 or abs(float(frame['native_pts'] * tb) - at) > 1e-7:
            raise ValueError('Native PTS and original timestamp differ')
        keys = []
        for box in frame['actual_boxes']:
            ci, score, b = box['cache_index'], box['score'], box['bbox']
            if type(ci) is not int or ci < 0 or not 0 <= finite(score) <= 1:
                raise ValueError('Actual detector reference and bounded score required')
            if (len(b) != 4 or any(not 0 <= finite(v) <= 1 for v in b)
                    or not (b[0] < b[2] and b[1] < b[3])):
                raise ValueError('Normalized actual xyxy box required')
            keys.append(ci)
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate actual detector reference')
        if source_size is not None and frame.get('source_size', source_size) != source_size:
            raise ValueError('Feature source size differs')
        previous = at


def normalize_portal(raw: dict, scope: dict, video_id: str, run_id: str) -> dict:
    """A candidate may exist even when the older detector rules emitted none."""
    first, at = finite(raw['birth_pts']), finite(raw['decision_time_pts'])
    if (not 0 <= first <= at or raw['evidence_until_pts'] != at
            or raw.get('automatic_confirmation') is not False
            or raw.get('status') != '침입 의심'
            or not raw['birth_site']['inside_birth_site']):
        raise ValueError('Causal portal suspicion required, not automatic confirmation')
    refs = raw['observation_refs']
    if not refs or any(not first <= finite(r['pts']) <= at for r in refs):
        raise ValueError('Portal candidate has missing or future observations')
    eid = digest(dict(version=VERSION, run_id=run_id, scope=scope, evidence=raw))
    return dict(**scope, event_id=eid, video_id=video_id, status='침입 의심',
        decision_time_pts=at, track_ids=[],
        source_ref=dict(collection='inside_birth_events',
            source_pointer='/inside_birth_events/' + eid,
            segment=raw['run_id'], raw_id=None), source_event=deepcopy(raw))


@dataclass
class RuleBackend:
    """Compose the existing implementations; do not copy their thresholds here."""
    def __post_init__(self) -> None:
        from .directional_loss import SavedGateDirection
        from .gate_episode_evidence import history_decision
        from .portal_births import PortalGate, compare_births
        from .exp0048_application import replay_scoped
        from .exp0049_application import replay_activity, activity_references
        from .incident_outcome_scope import ScopedIncidentLifecycle
        from .gate_activity_episodes import GateActivityEpisodes
        self.direction_class = SavedGateDirection
        self.history_decision = history_decision
        self.portal_class = PortalGate
        self.compare_births = compare_births
        self.replay_scoped = replay_scoped
        self.replay_activity = replay_activity
        self.activity_references = activity_references
        self.empty_lifecycle = ScopedIncidentLifecycle
        self.empty_activity = GateActivityEpisodes

    def prepare(self, frames, scene, region, camera):
        return self.direction_class(frames, scene), self.portal_class(scene, region, camera)

    def confirmations(self, baseline, bundle, scene, engine, run_id):
        if abs(baseline['policy']['loss_wait'] - engine.policy.loss_wait) > 1e-6:
            raise ValueError('Do not change the adopted loss wait during integration')
        from .approach_disappearance import Policy
        from .visible_crossing import visible_crossing_decision
        from .outward_crossing import outward_loss_decision
        from .existing_alert_crossing import existing_alert_crossing_decision
        segments = {s['id']: s for s in baseline['segments']}
        policy = Policy(**baseline['policy'])
        decisions = []
        for event in bundle['events']:
            source = event['source_event']
            reason = source.get('reason')
            if event['source_ref'].get('collection') == 'existing_alerts':
                d = existing_alert_crossing_decision(source, baseline['segments'], scene, policy)
                if d['decision_time_pts'] != event['decision_time_pts']:
                    raise ValueError('Existing crossing emission and candidate clock differ')
                d.update(event_id=event['event_id'], source_ref=deepcopy(event['source_ref']),
                    analysis_run_id=run_id, computed_in_current_run=True, rule_implementation=d['rule_id'])
                decisions.append(d)
                continue
            if reason not in ('recent_gate_presence_then_loss', 'observed_side_transition'):
                continue
            segment = segments[source['segment']]
            if (segment['raw_id'] != source['raw_id']
                    or source['decision_time_pts'] != event['decision_time_pts']):
                raise ValueError('Candidate source does not match the current analysis')
            if reason == 'observed_side_transition':
                d = visible_crossing_decision(source, segment, scene, policy)
            else:
                d = engine.classify(source, segment)
                if d.get('rule_id') != 'observed_gate_continuation_v1':
                    d = self.history_decision(d, segment, scene)
                    if d.get('automatic_confirmation') and d.get('continuation_assessment',{}).get('status')=='ambiguous':
                        d.update(rule_id='ambiguous_gate_loss_v1',association_ambiguous=True)
                    d = outward_loss_decision(d, segment, scene, policy)
            d.update(event_id=event['event_id'], source_ref=deepcopy(event['source_ref']),
                analysis_run_id=run_id, computed_in_current_run=True,
                rule_implementation=d.get('rule_id', 'gate_history_loss_v1'))
            decisions.append(d)
        return decisions

    def births(self, frames, scene, region, camera):
        return self.compare_births(frames, scene, region, camera)

    def lifecycle(self, baseline, history, events, runs, frames, scene, region, engine, portal, scope):
        if history['events'] or events:
            result, _ = self.replay_scoped(baseline, history, events, runs, frames,
                scene, region, direction_engine=engine, portal_gate=portal,
                confirm_outward_crossings=True, observe_gate_crossings=False)
            return result
        # Negative clips are valid inputs. Never insert a dummy suspicion.
        result = self.empty_lifecycle(namespace=scope['session_id']).export()
        result.update(video_id=history['video_id'], source_window=history['source_window'],
            available_after_pts=frames[-1]['pts'], resolutions=[], outcome_routing=[],
            preserved_confirmation_source_pts={})
        return result

    def activity(self, prior, frames, portal, scope, run_id):
        if prior['events']:
            return self.replay_activity(prior, frames, portal, namespace=run_id)
        life = self.empty_activity(scope, namespace=run_id)
        for frame in frames:
            life.step(frame['frame_index'], frame['pts'],
                portal_refs=self.activity_references(frame, portal))
        result = life.export()
        result.update(video_id=prior['video_id'], source_window=prior['source_window'],
            source_end_pts=frames[-1]['pts'], available_after_pts=frames[-1]['pts'],
            source_resolution_log=[], source_outcome_routing=[],
            preserved_confirmation_source_pts={}, source_evidence_states_preserved=True)
        return result


def analyze_observations(baseline: dict, bundle: dict, frames: list[dict],
        scene: dict, region: dict, scope: dict, run_id: str,
        *, backend=None) -> dict:
    """Current-run analysis from real measurements, not historical EXP outputs.

    An injected backend is for wiring tests only. Production uses RuleBackend.
    Internal EXP labels in reused functions denote implementation compatibility,
    not a claim that this run reuses an earlier experiment's measured result.
    """
    validate_frames(frames, source_size=scene['source_size'])
    if (set(scope) != {'session_id', 'camera_id', 'gate_id'}
            or any(not isinstance(v, str) or not v for v in scope.values())
            or not isinstance(run_id, str) or not run_id):
        raise ValueError('Explicit analysis and recording/camera/gate scope required')
    if (bundle['video_id'] != baseline['video_id']
            or any(any(e[k] != scope[k] for k in scope) for e in bundle['events'])):
        raise ValueError('Current source bundle scope differs')
    original = digest(dict(baseline=baseline, bundle=bundle, frames=frames,
                          scene=scene, region=region))
    rules = RuleBackend() if backend is None else backend
    engine, portal = rules.prepare(frames, scene, region, scope['camera_id'])
    decisions = rules.confirmations(baseline, bundle, scene, engine, run_id)
    history = dict(deepcopy(bundle), decisions=decisions)
    comparison = rules.births(frames, scene, region, scope['camera_id'])
    events = [normalize_portal(r, scope, bundle['video_id'], run_id)
              for r in comparison['portal_events']]
    combined = list(bundle['events']) + events
    if len({e['event_id'] for e in combined}) != len(combined):
        raise ValueError('Original and portal candidate IDs collide')
    scoped = rules.lifecycle(baseline, history, events, comparison['observation_runs'],
        frames, scene, region, engine, portal, scope)
    final = rules.activity(scoped, frames, portal, scope, run_id)
    if {e['event_id']: e for e in final['events']} != {e['event_id']: e for e in combined}:
        raise ValueError('Final episodes lost or edited current-run candidate payloads')
    if digest(dict(baseline=baseline, bundle=bundle, frames=frames,
                   scene=scene, region=region)) != original:
        raise ValueError('Rule integration mutated source measurements')
    # No final-time flush: recording end is not empty-gate evidence or a release.
    # Reused replay helpers report zero inference *inside their own rule stage*.
    # They cannot describe this invocation's upstream tracker and image work.
    for result in (scoped, final):
        result['rule_stage_calls'] = {name: result.pop(name, 0) for name in
            ('detector_calls', 'tracker_calls', 'flow_calls', 'vlm_calls')}
        result.update(analysis_run_id=run_id, execution_mode='current_input_analysis',
            source_evidence_mode='computed_in_current_run',
            historical_experiment_results_required=False)
    final.update(experiment='MVP-0002', pipeline_version=VERSION, analysis_run_id=run_id,
        execution_mode='current_input_analysis', source_evidence_mode='computed_in_current_run',
        source_algorithm_versions=['EXP-0035', 'EXP-0045', 'EXP-0046', 'EXP-0048', 'EXP-0049',
            'visible_gate_crossing_v1', 'outward_gate_loss_v1', 'existing_alert_gate_crossing_v1'],
        positive_crossing_directions=['outside_to_inside', 'inside_to_outside'],
        direction_rule_changed=True, release_rule_changed=False,
        continuation_observation_rules_enabled=False,
        activity_grouping_changed_decision_rules=False,
        historical_experiment_results_required=False, rejected_transition_candidates_used=False,
        candidate_generation_changed=True, evidence_decisions_changed=True,
        live_notifications_enabled=False, notification_delivery_measured=False,
        manual_reviews_modified=False, realtime=False, accuracy=None,
        release_video_validation='not_established', human_verified=False)
    final['source_experiment'] = 'MVP-0002-current-lifecycle'
    for card in final['cards']:
        card['decision_source'] = 'automatic_rule_current_run'
    for row in final['timeline']:
        row['card']['decision_source'] = 'automatic_rule_current_run'
    for name in ('active_cards', 'closed_cards', 'released_cards'):
        for card in final.get(name, []):
            card['decision_source'] = 'automatic_rule_current_run'
    return dict(cards=final, seed_decisions=decisions, portal_events=events,
                scoped_lifecycle=scoped, observation_runs=comparison['observation_runs'])


def collect_paths(video, cache_frames, tracked, seed_scene, output):
    """Use the existing CPU image tracker; discard its rejected action proposals."""
    import cv2
    from dataclasses import asdict
    from .gate_transition import GateTransition
    from .gap_observation_support import catalog_frame
    from .run_tracklet_linking import decode_native
    if len(cache_frames) != len(tracked):
        raise ValueError('Tracking and detector frame partitions differ')
    engine, count = GateTransition(seed_scene), 0
    wall, cpu = time.perf_counter(), time.process_time()
    with (output / 'frame-evidence.jsonl').open('x', encoding='utf-8') as sink:
        for index, bgr in decode_native(video, cache_frames):
            if index != count:
                raise ValueError('Source decoder skipped or reordered a frame')
            cache, track = cache_frames[index], tracked[index]
            if any(cache[k] != track[k] for k in ('pts', 'native_pts', 'time_base')):
                raise ValueError('Detector and tracker source clocks differ')
            boxes = catalog_frame(cache, track)
            row = engine.step(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cache['pts'], boxes, index)
            # Track image points only. Do NOT revive EXP42/43's rejected action rule.
            row.pop('event', None); row.pop('signals', None)
            row.update(actual_boxes=boxes, native_pts=cache['native_pts'], time_base=cache['time_base'])
            sink.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
            count += 1
    if count != len(cache_frames):
        raise ValueError('Incomplete native image path extraction')
    metrics = dict(frames=count,
        elapsed_seconds=time.perf_counter()-wall, cpu_seconds=time.process_time()-cpu,
        cpu_image_path_frames=count, detector_calls=0, tracker_calls=0,
        image_path_implementation='GateTransition', seed_scene_digest=digest(seed_scene),
        policy=asdict(engine.policy), rejected_transition_candidates_used=False,
        opencv_version=cv2.__version__, opencv_threads=cv2.getNumThreads())
    with (output / 'metrics.json').open('x', encoding='utf-8') as sink:
        json.dump(metrics, sink, ensure_ascii=False, indent=2, allow_nan=False)
        sink.write('\n')


def load_lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def execute(video, camera, output, *, scene_path, portal_path, cache=None,
            start=None, end=None, whole=False, queue_context=None, camera_registry=None):
    """A single local invocation; registration is a separate explicit adapter step."""
    import fcntl
    from . import video_cards as vc
    from .gate_episode_evidence import revised_scene
    from .portal_births import PortalGate
    wall, cpu = time.perf_counter(), time.process_time()
    video, output = Path(video).absolute(), Path(output).absolute()
    scene_path, portal_path = Path(scene_path).absolute(), Path(portal_path).absolute()
    if (output.is_symlink() or any(p.is_symlink() for p in output.parents)
            or not output.resolve().is_relative_to((vc.ROOT / 'outputs').resolve())):
        raise ValueError('Use a local non-symlink outputs directory')
    cameras_path = vc.CAMERAS
    if camera_registry is None:
        if camera not in vc.SCENES:
            raise ValueError('Select an existing calibrated C3 or C6 camera')
        base_path = vc.SCENES[camera]
    else:
        _, frozen_scene, frozen_portal, cameras_path = vc.camera_profile(camera, video, camera_registry)
        if scene_path != frozen_scene or portal_path != frozen_portal:
            raise ValueError('Explicit scene/portal paths differ from frozen camera registry')
        base_path = vc.SCENES.get(camera, frozen_scene)
    scene, region, base_scene = read(scene_path), read(portal_path), read(base_path)
    revised_scene(base_scene, scene)  # inside-only approved geometry; no moving the line.
    if camera == 'C6' and scene != base_scene:
        raise ValueError('C6 must retain its current approved scene')
    PortalGate(scene, region, camera)  # explicit binding, no whole-inside fallback.
    code = {str(p.relative_to(vc.ROOT)): vc.sha256(p)
            for p in sorted((vc.ROOT / 'sceneguard').rglob('*.py'))}
    inputs = {str(p): vc.sha256(p) for p in (video, scene_path, portal_path, base_path, cameras_path)}
    request = dict(version=VERSION, video=str(video), camera=camera,
        scene=str(scene_path), portal=str(portal_path), window=[start, end], whole=whole,
        cache=None if cache is None else str(Path(cache).absolute()), queue_context=queue_context,
        input_sha256=inputs, code_sha256=code, realtime=False)
    if camera_registry is not None:
        request['camera_registry'] = str(cameras_path)
    output.mkdir(parents=True, exist_ok=True)
    for name in ('.mvp.lock', 'request.json', 'status.json', 'viewer-manifest.json'):
        if (output / name).is_symlink():
            raise ValueError('State files must not be symlinks')
    with (output / '.mvp.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        reqpath = output / 'request.json'
        if reqpath.exists():
            if read(reqpath) != request:
                raise ValueError('Source/configuration/code changed; choose a new output directory')
        else:
            if any(p.name != '.mvp.lock' for p in output.iterdir()):
                raise ValueError('Existing output lacks a matching request')
            vc.save(reqpath, request)
        run_id = 'mvp-' + digest(request)[:24]
        try:
            vc.status(output / 'status.json', state='analyzing', version=VERSION)
            profile_args = {} if camera_registry is None else dict(camera_registry=cameras_path)
            front = vc.execute(video, camera, output / 'source', cache=cache, start=start,
                               end=end, whole=whole, queue_context=queue_context, **profile_args)
            if front['state'] != 'complete':
                vc.status(output / 'status.json', state='blocked', upstream=front)
                return read(output / 'status.json')
            baseline = read(output / 'source/analysis/analysis.json')
            bundle = read(output / 'source/analysis/cards.json')
            camera_config = vc.read(cameras_path)['cameras'][camera]
            info = vc.probe(video)
            begin, finish = (0.0, info.get('source_end_exclusive', info['duration'])) if whole else (start, end)
            _, frames, interval, cache_hashes = vc.validate_cached(video, camera_config,
                baseline['source_paths']['cache'], begin, finish, info)
            tracked = load_lines(output / 'source/tracking/frames.jsonl')
            binding = dict(request_sha256=vc.sha256(reqpath), cache_sha256=cache_hashes,
                analysis_sha256=vc.sha256(output / 'source/analysis/analysis.json'),
                tracking_sha256=vc.sha256(output / 'source/tracking/frames.jsonl'))
            paths, reused_paths = vc.stage(output, 'image-paths', binding,
                lambda p: collect_paths(video, frames, tracked, base_scene, p))
            observations = load_lines(paths / 'frame-evidence.jsonl')
            scope = dict(session_id=run_id, camera_id=camera,
                         gate_id=camera_config['legacy_boundary_config']['boundary_id'])
            # Preserve raw candidate IDs/payload within this invocation, but scope
            # the current analysis independently from legacy demo sessions.
            from .exp0036_application import make_bundle
            bundle = make_bundle(baseline, camera, scope['gate_id'], run_id)
            def decide(folder):
                results = analyze_observations(baseline, bundle, observations,
                    scene, region, scope, run_id)
                for key, value in results.items():
                    vc.save(folder / (key + '.json'), value)
            decision, reused_decisions = vc.stage(output, 'decision',
                binding | dict(paths=vc.sha256(paths / 'stage.json')), decide)
            final = read(decision / 'cards.json')
            def render(folder):
                cards = deepcopy(final['cards'])
                for card in cards:
                    card['last_alert_pts'] = max(v for v in
                        (card['last_alert_pts'], card.get('first_confirmation_pts'),
                         card.get('observation_closed_pts'), card.get('last_gate_observation_pts'))
                        if v is not None)
                vc.evidence(video, frames, cards, folder, interval)
            media_path, reused_media = vc.stage(output, 'evidence',
                binding | dict(cards=vc.sha256(decision / 'cards.json')), render)
            if inputs != {p: vc.sha256(p) for p in inputs} or code != {
                    str(p.relative_to(vc.ROOT)): vc.sha256(p)
                    for p in sorted((vc.ROOT / 'sceneguard').rglob('*.py'))}:
                raise ValueError('Source or code changed during analysis')
            if cache_hashes != dict(cache=vc.sha256(Path(baseline['source_paths']['cache']) / 'person_cache.jsonl'),
                                    metadata=vc.sha256(Path(baseline['source_paths']['cache']) / 'run.json')):
                raise ValueError('Detector cache changed during analysis')
            media = read(media_path / 'media.json')
            manifest = dict(schema_version=1, kind='sceneguard_mvp_viewer_v1', version=VERSION,
                experiment='MVP-0002', contract=CONTRACT, run_id=run_id, **scope,
                video_id=baseline['video_id'], source_path=str(video), source_sha256=inputs[str(video)],
                source_window=final['source_window'], requested_window=[begin, finish],
                source_pts_origin=frames[0]['pts'], playback_pts_origin=0.0,
                cards_path=str(decision / 'cards.json'), cards_sha256=vc.sha256(decision / 'cards.json'),
                source_frames_path=str(media_path / 'source-frames.json'),
                source_frames_sha256=vc.sha256(media_path / 'source-frames.json'),
                media=[m | dict(path=str(media_path / m['file']), sha256=vc.sha256(media_path / m['file']))
                       for m in media], counts=final['counts'], execution_mode=front['mode'],
                paths_mode='saved_same_request' if reused_paths else 'current_video_cpu_paths',
                predictions_mode='saved_same_request' if reused_decisions else 'current_run_rules',
                realtime=False, live_notifications_enabled=False,
                manual_reviews_modified=False, registration_status='adapter_required',
                accuracy=None, release_video_validation='not_established')
            target = output / 'viewer-manifest.json'
            # Reuse flags belong in status, not in an immutable registration manifest.
            manifest.pop('paths_mode'); manifest.pop('predictions_mode')
            if target.exists():
                if read(target) != manifest:
                    raise ValueError('Completed viewer manifest differs')
            else:
                vc.save(target, manifest)
            vc.status(output / 'status.json', state='analysis_complete', version=VERSION,
                manifest_path=str(target), counts=final['counts'],
                reused=dict(paths=reused_paths, decisions=reused_decisions, media=reused_media),
                source_mode=front['mode'], service_registered=False, browser_verified=False,
                overall_release_complete=False, detector_frames_this_execution=front.get('detector_frames_this_execution', 0),
                current_cpu_flow_computed=not reused_paths,
                cpu_image_path_frames_this_execution=0 if reused_paths else len(frames),
                tracker_frames_this_execution=0 if front.get('reused_stages', {}).get('tracking') else len(frames),
                frames=len(frames), elapsed_seconds=time.perf_counter()-wall,
                cpu_seconds=time.process_time()-cpu, realtime=False)
            return read(output / 'status.json')
        except Exception as exc:
            vc.status(output / 'status.json', state='failed', error_type=type(exc).__name__, error=str(exc))
            raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('video', 'scene', 'portal', 'output'):
        p.add_argument('--' + flag, type=Path, required=True)
    p.add_argument('--camera', required=True)
    p.add_argument('--camera-registry', type=Path)
    p.add_argument('--cache', type=Path); p.add_argument('--start', type=float); p.add_argument('--end', type=float)
    p.add_argument('--whole', action='store_true')
    p.add_argument('--register-config', type=Path)
    p.add_argument('--registration-id')
    p.add_argument('--registration-python', type=Path,
                   help='Existing service Python environment for the registration adapter')
    for flag in ('run-id', 'task-id', 'dispatch-id', 'owner'):
        p.add_argument('--' + flag)
    a = p.parse_args()
    if bool(a.register_config) != bool(a.registration_id):
        p.error('Use --register-config and --registration-id together')
    if a.registration_python and not a.register_config:
        p.error('--registration-python requires --register-config and --registration-id')
    ids = (a.run_id, a.task_id, a.dispatch_id, a.owner)
    if any(ids) and not all(ids):
        p.error('Use all four existing canonical queue identity fields or none')
    if a.whole == (a.start is not None or a.end is not None) or (
            not a.whole and (a.start is None or a.end is None)):
        p.error('Choose --whole or both --start and --end')
    context = dict(zip(('run_id', 'task_id', 'dispatch_id', 'owner'), ids)) if all(ids) else None
    result = execute(a.video, a.camera, a.output, scene_path=a.scene, portal_path=a.portal,
        cache=a.cache, start=a.start, end=a.end, whole=a.whole, queue_context=context,
        camera_registry=a.camera_registry)
    if a.register_config and result['state'] == 'analysis_complete':
        import subprocess
        import sys
        registered = subprocess.run([str(a.registration_python or sys.executable),
            '-m', 'webapp.mvp_registration', '--config', str(a.register_config),
            '--manifest', result['manifest_path'], '--registration-id', a.registration_id],
            check=True, capture_output=True, text=True)
        result['registration'] = json.loads(registered.stdout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['state'] != 'analysis_complete':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
