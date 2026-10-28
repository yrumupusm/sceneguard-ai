"""Shared, meaning-preserving response parsing; no model or media operations."""
import hashlib
import json
import re
from pathlib import Path

ACTIONS = frozenset(('passage_or_waiting', 'contact', 'climbing_attempt_or_in_progress',
                     'stepping_over_boundary', 'indeterminate'))
KEYS = frozenset(('observed_actions', 'visible_evidence', 'crossing_completion', 'uncertainties'))


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_response(raw):
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError('duplicate JSON key')
            obj[k] = v
        return obj
    obj = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(obj, dict) or set(obj) != KEYS:
        raise ValueError('exact response keys required')
    if not isinstance(obj['observed_actions'], list) or not obj['observed_actions'] or any(
            not isinstance(x, str) or x not in ACTIONS for x in obj['observed_actions']):
        raise ValueError('invalid action list')
    if any(not isinstance(obj[k], str) for k in KEYS - {'observed_actions'}):
        raise ValueError('text fields must be strings')
    if obj['crossing_completion'] not in ('observed', 'not_confirmed', 'indeterminate'):
        raise ValueError('invalid completion state')
    return obj


def parse_pair(raw):
    """Record strict parsing and optional whole-response fence removal separately."""
    result = {'strict_parsed': None, 'strict_error': None, 'postprocessed_parsed': None,
              'postprocessed_error': None, 'postprocessing': 'none'}
    try:
        result['strict_parsed'] = parse_response(raw)
    except (ValueError, TypeError) as exc:
        result['strict_error'] = str(exc)
    cleaned = raw.strip()
    match = re.fullmatch(r'```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```', cleaned)
    if match:
        cleaned = match[1].strip()
        result['postprocessing'] = 'outer_json_fence_removed'
    elif cleaned != raw:
        result['postprocessing'] = 'outer_whitespace_removed'
    try:
        result['postprocessed_parsed'] = parse_response(cleaned)
    except (ValueError, TypeError) as exc:
        result['postprocessed_error'] = str(exc)
    return result
