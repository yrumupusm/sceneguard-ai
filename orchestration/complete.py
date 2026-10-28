"""Coordinator-only result registration; never launches work or certifies publication."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import uuid


ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
PRIVATE = re.compile(r"raw[_ -]?(response|output|prediction)|generated_token|access[_ -]?token|refresh[_ -]?token|api[_ -]?key|password|credential|secret", re.I)
ABSOLUTE = re.compile(r"(?:^|[\s\"'=(])(?:/(?:[A-Za-z0-9_.-]+/)+|[A-Za-z]:[\\/]|\\\\|file://)")
TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|Bearer\s+\S+)")
ASSIGNMENT = set("experiment_id slot title run_id task_id dispatch_id agent_model_requested agent_model_effective reasoning_effective assigned_at synthetic".split())
PACKAGE = set("experiment_id attempt_id title summary evaluated_model execution_status review_status decision_status report_path metrics_path review_path reviewed_report_sha256 reviewed_metrics_sha256 worker_opinion next_step limitations evidence".split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    require(isinstance(value, str) and ID.fullmatch(value), "invalid identifier")
    return value


def text(value):
    require(isinstance(value, str) and bool(value.strip()), "nonempty text required")


def public(value):
    """Conservative payload filter, not a replacement for human publication review."""
    if isinstance(value, dict):
        for key, item in value.items():
            require(not PRIVATE.search(key), "private field prohibited")
            public(item)
    elif isinstance(value, list):
        for item in value:
            public(item)
    elif isinstance(value, str):
        require(not ABSOLUTE.search(value) and not value.startswith('/') and not TOKEN.search(value),
                "private path or credential prohibited")
    elif isinstance(value, float):
        require(math.isfinite(value), "nonfinite number prohibited")


def relative(value):
    require(isinstance(value, str) and value and '\\' not in value and ':' not in value,
            "unsafe relative path")
    parts = value.split('/')
    require(all(p and p not in ('.', '..') and not p.startswith('.') for p in parts), "unsafe relative path")
    return parts


@contextmanager
def directory(path, create=False):
    """Walk absolute directories with no-follow fds, including the configured root."""
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, "absolute canonical directory required")
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            require(not part.startswith('.'), "hidden directory prohibited")
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
        yield fd
    finally:
        os.close(fd)


@contextmanager
def regular(path):
    path = Path(path)
    require(path.is_absolute() and not path.name.startswith('.'), "unsafe file path")
    with directory(path.parent) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode), "regular file required")
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                yield stream
        finally:
            os.close(fd)


def read(path):
    with regular(path) as stream:
        require(os.fstat(stream.fileno()).st_size <= 4 * 1024 * 1024, "document too large")
        return stream.read(4 * 1024 * 1024 + 1)


def parse(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def load(path):
    return parse(read(path))


def optional(path, default):
    try:
        return load(path)
    except FileNotFoundError:
        return default


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, value):
    """Replace one regular file atomically; all parent walks reject symlinks."""
    path = Path(path)
    with directory(path.parent, create=True) as parent:
        try:
            info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            require(stat.S_ISREG(info.st_mode), "unsafe write target")
        except FileNotFoundError:
            pass
        temp = 'registration-' + uuid.uuid4().hex + '.tmp'
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(encoded(value))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path.name, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
        finally:
            try:
                os.unlink(temp, dir_fd=parent)
            except FileNotFoundError:
                pass


def assignment(value):
    require(isinstance(value, dict) and set(value) == ASSIGNMENT, "assignment fields differ from contract")
    public(value)
    for key in ('experiment_id', 'run_id', 'task_id', 'dispatch_id'):
        identifier(value[key])
    require(value['slot'] in ('slot1', 'slot2', 'slot3'), "invalid slot")
    require(type(value['synthetic']) is bool, "explicit synthetic boolean required")
    require(bool(re.fullmatch(r'TEST-[A-Za-z0-9_-]+', value['experiment_id'])) if value['synthetic']
            else bool(re.fullmatch(r'EXP-\d{4,}', value['experiment_id'])), "experiment ID/synthetic mismatch")
    require(value['experiment_id'] not in {f'EXP-{i:04}' for i in range(1, 8)}, "historical ID reserved")
    for key in ('title', 'agent_model_requested', 'assigned_at'):
        text(value[key])
    require(datetime.fromisoformat(value['assigned_at'].replace('Z', '+00:00')).tzinfo is not None,
            "assigned_at timezone required")
    for key in ('agent_model_effective', 'reasoning_effective'):
        if value[key] is not None:
            text(value[key])
    return value


def rows(document, key):
    require(isinstance(document, dict) and document.get('schema_version') == 1
            and isinstance(document.get(key), list), "invalid record container")
    result = document[key]
    ids = [identifier(row['experiment_id']) for row in result]
    require(len(ids) == len(set(ids)), "duplicate experiment IDs")
    return result


def metrics(data, eid):
    require(isinstance(data, dict) and data.get('schema_version') == 1
            and data.get('experiment_id') == eid and isinstance(data.get('metrics'), list), "invalid metrics document")
    public(data)
    for row in data['metrics']:
        require(isinstance(row, dict) and set('label value unit sample_n scope source source_sha256 verification'.split()) <= set(row),
                "metric source metadata missing")
        for key in ('label', 'unit', 'scope', 'source', 'verification'):
            text(row[key])
        relative(row['source'])
        value, n, sha = row['value'], row['sample_n'], row['source_sha256']
        require(value is None or (type(value) in (int, float) and (type(value) is int or math.isfinite(value))), "finite numeric metric or null required")
        require(n is None or (type(n) is int and n >= 0), "invalid sample_n")
        require(sha is None or (isinstance(sha, str) and HASH.fullmatch(sha)), "invalid source hash")
        if value is not None:
            require(n is not None and n > 0 and sha is not None and row['verification'] != 'unavailable',
                    "measured value requires sample and verified source hash")


class Registry:
    def __init__(self, config_path):
        self.config_path = Path(config_path).absolute()

    @contextmanager
    def locked(self):
        initial = load(self.config_path)
        runtime = Path(initial['runtime_dir'])
        with directory(runtime) as parent:
            fd = os.open('completion.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
            try:
                require(stat.S_ISREG(os.fstat(fd).st_mode), "unsafe runtime lock")
                fcntl.flock(fd, fcntl.LOCK_EX)
                self.config = load(self.config_path)
                require(self.config['runtime_dir'] == initial['runtime_dir'], "runtime changed while locking")
                self.root = Path(self.config['repo_root'])
                with directory(self.root):
                    yield
            finally:
                os.close(fd)

    def _records(self):
        assignments = optional(self.root / 'records/assignments.json', {'schema_version': 1, 'assignments': []})
        catalog = optional(self.root / 'records/catalog.json', {'schema_version': 1, 'experiments': []})
        rows(assignments, 'assignments'); rows(catalog, 'experiments')
        return assignments, catalog

    def assign(self, value):
        with self.locked():
            value = assignment(value)
            assignments, catalog = self._records()
            existing = next((x for x in assignments['assignments'] if x['experiment_id'] == value['experiment_id']), None)
            if existing is not None:
                require(existing == value, "conflicting assignment ID")
                return {'assignment': 'already_registered', 'experiment_id': value['experiment_id']}
            require(not any(x['experiment_id'] == value['experiment_id'] for x in catalog['experiments']), "result ID already exists")
            require(not any(x['dispatch_id'] == value['dispatch_id'] for x in assignments['assignments']),
                    "dispatch already assigned to another experiment")
            assignments['assignments'].append(value)
            atomic(self.root / 'records/assignments.json', assignments)
            return {'assignment': 'registered', 'experiment_id': value['experiment_id']}

    def complete(self, package, manifest):
        with self.locked():
            require(isinstance(package, dict) and PACKAGE <= set(package)
                    and set(package) <= PACKAGE | {'synthetic'}, "package fields differ from contract")
            public(package)
            eid = identifier(package['experiment_id'])
            identifier(package['attempt_id'])
            assignments, catalog = self._records()
            assigned = next((x for x in assignments['assignments'] if x['experiment_id'] == eid), None)
            require(assigned is not None, "assignment required")
            assignment(assigned)
            require(package.get('synthetic', False) is assigned['synthetic'], "synthetic label mismatch")
            require(package['title'] == assigned['title'], "assignment title mismatch")
            for key in ('title', 'summary', 'evaluated_model', 'worker_opinion', 'next_step'):
                text(package[key])
            require(package['execution_status'] in ('succeeded', 'failed', 'inconclusive'), "invalid execution status")
            require(package['review_status'] in ('accepted_for_comparison', 'needs_revision', 'blocked', 'inconclusive'), "invalid review status")
            require(package['decision_status'] in ('adoption_on_hold', 'rejected'), "invalid decision status")
            require(isinstance(package['limitations'], list) and all(isinstance(x, str) and x.strip() for x in package['limitations']), "invalid limitations")
            sources = {}
            for key, prefix, suffix in [('report_path', 'docs/experiments/', '.md'), ('metrics_path', f'records/{eid}/', '.json'), ('review_path', 'docs/reviews/', '.md')]:
                path = package[key]
                relative(path)
                require(path.startswith(prefix) and path.endswith(suffix), "invalid public document location")
                sources[key] = read(self.root / path)
            require(len({package[k] for k in sources}) == 3, "documents must be separate")
            public(sources['report_path'].decode('utf-8')); public(sources['review_path'].decode('utf-8'))
            metrics(parse(sources['metrics_path']), eid)
            hashes = {name: digest(data) for name, data in sources.items()}
            for name in ('report', 'metrics'):
                supplied = package[f'reviewed_{name}_sha256']
                require(isinstance(supplied, str) and HASH.fullmatch(supplied)
                        and supplied == hashes[f'{name}_path'], "stale review hash")
                require(supplied.encode() in sources['review_path'], "review must explicitly record both source hashes")
            require(isinstance(manifest, dict) and set(manifest) == {'artifacts'} and isinstance(manifest['artifacts'], dict), "invalid artifact manifest")
            require(isinstance(package['evidence'], list), "invalid evidence")
            entries = {}
            for item in package['evidence']:
                require(isinstance(item, dict) and set(item) == {'artifact_id', 'label', 'kind'}, "invalid evidence fields")
                aid = identifier(item['artifact_id']); text(item['label'])
                require(aid not in entries, "duplicate evidence ID")
                entries[aid] = item['kind']
            require(set(entries) == set(manifest['artifacts']), "artifact IDs must match evidence")
            require(not any(e['artifact_id'] in entries for row in catalog['experiments']
                            if row['experiment_id'] != eid for e in row.get('evidence', [])),
                    "artifact ID belongs to another result")
            merged = dict(self.config.get('artifacts', {}))
            allow = Path(self.config['artifact_allow_root'])
            for aid, entry in manifest['artifacts'].items():
                require(isinstance(entry, dict) and set(entry) == {'path', 'kind'}, "invalid artifact fields")
                path = Path(entry['path'])
                require(path.is_absolute() and entry['kind'] == entries[aid], "invalid artifact path/kind")
                relative(path.relative_to(allow).as_posix())
                require((entry['kind'], path.suffix.lower()) in {('video', '.mp4'), ('image', '.jpg'), ('image', '.png')}, "unsupported artifact type")
                with regular(path):
                    pass  # Validate metadata only: never read or copy media bytes.
                require(aid not in merged or merged[aid] == entry, "conflicting artifact ID")
                merged[aid] = entry
            registration = digest(encoded({'assignment': assigned, 'package': package, 'artifacts': manifest,
                                           'review_sha256': hashes['review_path']}))
            binding_path = f"docs/reviews/{eid}-{package['attempt_id']}.binding.json"
            binding = {'schema_version': 1, 'review_path': package['review_path'],
                       'review_sha256': hashes['review_path'], 'review_status': package['review_status'],
                       'synthetic': assigned['synthetic'], 'registration_sha256': registration,
                       'reviewed_sources': {eid: {'report_sha256': hashes['report_path'], 'metrics_sha256': hashes['metrics_path']}}}
            existing_binding = optional(self.root / binding_path, None)
            require(existing_binding is None or existing_binding == binding, "conflicting review binding")
            record = {**assigned, **package, 'synthetic': assigned['synthetic'], 'schema_version': 1,
                      'role': 'experiment_worker', 'report_sha256': hashes['report_path'],
                      'metrics_sha256': hashes['metrics_path'], 'metric_definitions': package['metrics_path'],
                      'review_sha256': hashes['review_path'], 'review_binding_path': binding_path,
                      'registration_sha256': registration}
            existing = next((x for x in catalog['experiments'] if x['experiment_id'] == eid), None)
            require(existing is None or existing == record, "conflicting result ID")
            # All validation precedes writes. Incomplete writes are immutable/retryable;
            # the catalog is the final visibility boundary for a new result.
            if existing_binding is None:
                atomic(self.root / binding_path, binding)
            if merged != self.config.get('artifacts', {}):
                atomic(self.config_path, {**self.config, 'artifacts': merged})
            if existing is None:
                catalog['experiments'].append(record)
                atomic(self.root / 'records/catalog.json', catalog)
            return {'registration': 'already_registered' if existing else 'registered',
                    'experiment_id': eid, 'synthetic': assigned['synthetic'],
                    'github_publication': 'unverified', 'browser_verification': 'unverified'}

    def status(self, eid):
        identifier(eid)
        with self.locked():
            assignments, catalog = self._records()
            assigned = next((x for x in assignments['assignments'] if x['experiment_id'] == eid), None)
            record = next((x for x in catalog['experiments'] if x['experiment_id'] == eid), None)
            result = {'experiment_id': eid, 'assigned': assigned is not None, 'registered': record is not None,
                      'synthetic': assigned.get('synthetic') if assigned else None,
                      'source_integrity': 'unverified', 'review_integrity': 'unverified',
                      'github_publication': 'unverified', 'browser_verification': 'unverified',
                      'native_lifecycle': 'unverified', 'artifact_availability': 'unverified'}
            if record:
                try:
                    actual = {key: digest(read(self.root / '/'.join(relative(record[key + '_path']))))
                              for key in ('report', 'metrics', 'review')}
                    binding = load(self.root / '/'.join(relative(record['review_binding_path'])))
                    result['source_integrity'] = 'current' if all(actual[k] == record.get(k + '_sha256') for k in ('report', 'metrics')) else 'stale'
                    result['review_integrity'] = 'current' if (
                        binding['review_path'] == record['review_path'] and binding['review_sha256'] == actual['review']
                        and binding['reviewed_sources'][eid] == {k + '_sha256': actual[k] for k in ('report', 'metrics')}
                    ) else 'stale'
                except (OSError, ValueError, KeyError, TypeError):
                    result['source_integrity'] = 'unavailable'
            return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('assign').add_argument('--assignment', required=True, type=Path)
    complete = commands.add_parser('complete')
    complete.add_argument('--package', required=True, type=Path)
    complete.add_argument('--artifacts', required=True, type=Path)
    commands.add_parser('status').add_argument('--experiment', required=True)
    args = parser.parse_args(argv)
    try:
        registry = Registry(args.config)
        if args.command == 'assign':
            result = registry.assign(load(args.assignment.absolute()))
        elif args.command == 'complete':
            result = registry.complete(load(args.package.absolute()), load(args.artifacts.absolute()))
        else:
            result = registry.status(args.experiment)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        # Do not echo private input paths, credentials, or payloads into receipts.
        print(json.dumps({'error': 'registration rejected; validate inputs and local permissions'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
