"""Read-only local viewer; no execution or arbitrary file APIs."""
import json
import hashlib
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from markdown_it import MarkdownIt
from starlette.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1'])
HERE = Path(__file__).parent
ID = re.compile(r'^[A-Za-z0-9_-]+$')

@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


def config():
    with open(os.environ['SCENEGUARD_LAB_CONFIG'], encoding='utf-8') as f:
        return json.load(f)


def safe_open(root, relative):
    """Open a regular file through directory fds, rejecting every symlink component."""
    root = Path(root)
    rel = Path(relative)
    if not root.is_absolute() or rel.is_absolute() or not rel.parts or any(p in ('.', '..') or p.startswith('.') for p in root.parts[1:] + rel.parts):
        raise ValueError('unsafe path')
    # The configured root itself must not contain symlinks either.
    parts = root.parts[1:] + rel.parts
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for i, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if i < len(parts)-1 else os.O_NONBLOCK)
            new = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = new
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('not a regular file')
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise


def read_json(root, path):
    with safe_open(root, path) as f:
        return json.load(f)


def catalog(c):
    return read_json(c['repo_root'], 'records/catalog.json')


def document(c, path, prefix, suffix):
    if not isinstance(path, str) or not path.startswith(prefix) or not path.endswith(suffix):
        raise ValueError('invalid registered document')
    with safe_open(c['repo_root'], path) as f:
        return f.read().decode('utf-8')


def markdown(source):
    md = MarkdownIt('commonmark', {'html': False, 'linkify': False}).enable('table')
    # No remote or local image requests from untrusted report text.
    md.renderer.rules['image'] = lambda tokens, idx, options, env: ''
    md.disable('link')
    return md.render(source)


def artifact(c, artifact_id):
    if not isinstance(artifact_id, str) or not ID.fullmatch(artifact_id):
        raise ValueError('invalid ID')
    entry = c['artifacts'][artifact_id]
    path = Path(entry['path'])
    root = Path(c['artifact_allow_root'])
    if not path.is_absolute() or not root.is_absolute():
        raise ValueError('absolute paths required')
    relative = path.relative_to(root)
    ext = path.suffix.lower()
    if (entry['kind'], ext) not in {('video', '.mp4'), ('image', '.jpg'), ('image', '.png')}:
        raise ValueError('unsupported media')
    return safe_open(root, relative), ext


def available(c, item):
    try:
        f, _ = artifact(c, item.get('artifact_id'))
        f.close()
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


@app.get('/')
def index():
    return FileResponse(HERE / 'index.html')

@app.get('/assets/{name}')
def assets(name: str):
    if name not in ('app.js', 'style.css'):
        raise HTTPException(404)
    return FileResponse(HERE / name)

@app.get('/api/catalog')
def get_catalog():
    c = config()
    try:
        data = catalog(c)
        data['roles'] = read_json(c['repo_root'], 'records/roles.json')
        try:
            assignments = read_json(c['repo_root'], 'records/assignments.json')
        except FileNotFoundError:
            assignments = {'schema_version': 1, 'assignments': []}
        if assignments.get('schema_version') != 1 or not isinstance(assignments.get('assignments'), list):
            raise ValueError('invalid assignments')
        data['assignments'] = assignments['assignments']
        return data
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(503, 'catalog unavailable')

@app.get('/api/experiments/{experiment_id}')
def experiment(experiment_id: str):
    c = config()
    try:
        item = next(x for x in catalog(c)['experiments'] if x['experiment_id'] == experiment_id)
        result = dict(item)
        source = document(c, item['report_path'], 'docs/experiments/', '.md')
        result['report_html'] = markdown(source)
        result['source_integrity'] = {
            'report_match': hashlib.sha256(source.encode('utf-8')).hexdigest() == item['report_sha256']
            if item.get('report_sha256') else None,
        }
        review = item.get('review_path')
        review_source = document(c, review, 'docs/reviews/', '.md') if review else ''
        result['review_html'] = markdown(review_source)
        path = item['metrics_path']
        if not path.startswith('records/' + experiment_id + '/') or not path.endswith('.json'):
            raise ValueError('invalid metric path')
        with safe_open(c['repo_root'], path) as metric_file:
            metric_bytes = metric_file.read()
        result['metrics'] = json.loads(metric_bytes)['metrics']
        metric_hash = hashlib.sha256(metric_bytes).hexdigest()
        report_hash = hashlib.sha256(source.encode('utf-8')).hexdigest()
        result['source_integrity']['metrics_match'] = metric_hash == item['metrics_sha256'] if item.get('metrics_sha256') else None
        # The importer must never refresh this review-owned binding. Catalog
        # hashes describe the current import, not what an old review examined.
        binding_path = item.get('review_binding_path')
        review_state = 'unverified'
        if binding_path:
            try:
                binding = json.loads(document(c, binding_path, 'docs/reviews/', '.json'))
                reviewed = binding['reviewed_sources'][experiment_id]
                review_state = 'current' if (
                    binding['review_path'] == review
                    and binding['review_sha256'] == hashlib.sha256(review_source.encode('utf-8')).hexdigest()
                    and reviewed['report_sha256'] == report_hash
                    and reviewed['metrics_sha256'] == metric_hash
                ) else 'stale'
            except (OSError, ValueError, KeyError, TypeError):
                review_state = 'unverified'
        result['review_integrity'] = review_state
        if review_state != 'current' or False in result['source_integrity'].values():
            result['review_html'] = ('<p><strong>이전 검토: 현재 원문·측정치와의 연결이 오래됐거나 미검증입니다. '
                                     '재검토가 필요하며 아래 의견은 현재 버전 승인으로 사용할 수 없습니다.</strong></p>'
                                     + result['review_html'])
        result['evidence'] = [{**e, 'available': available(c, e)} for e in item.get('evidence', [])]
        return result
    except StopIteration:
        raise HTTPException(404, 'unknown experiment')
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'registered report unavailable')

@app.get('/api/status')
def status():
    try:
        data = read_json(config()['runtime_dir'], 'orca_projection.json')
        observed = datetime.fromisoformat(data['observed_at'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        stale = age < 0 or age > float(data['stale_after_seconds'])
        return {**data, 'stale': stale, 'state': 'stale' if stale else ('connected' if data['connected'] is True else 'disconnected')}
    except (OSError, ValueError, KeyError, TypeError):
        return {'state': 'unverified', 'observed_at': None, 'connected': None, 'stale': None}

@app.api_route('/artifacts/{artifact_id}', methods=['GET', 'HEAD'])
def media(artifact_id: str, request: Request):
    try:
        c = config()
        # An allowlisted file is served only if referenced by a registered experiment.
        if not any(e.get('artifact_id') == artifact_id for x in catalog(c)['experiments'] for e in x.get('evidence', [])):
            raise ValueError('unregistered')
        f, ext = artifact(c, artifact_id)
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(404, 'artifact unavailable')
    size = os.fstat(f.fileno()).st_size
    start, end, code = 0, size - 1, 200
    range_header = request.headers.get('range')
    if range_header:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header.strip())
        if not match or not any(match.groups()) or size == 0:
            f.close()
            return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})
        a, b = match.groups()
        if not a:
            length = int(b)
            start = max(0, size - length)
            end = size - 1
        else:
            start = int(a)
            end = min(int(b), size - 1) if b else size - 1
        if start >= size or start > end:
            f.close()
            return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})
        code = 206
    length = max(0, end - start + 1)
    h = {'Accept-Ranges': 'bytes', 'Content-Length': str(length)}
    if code == 206:
        h['Content-Range'] = f'bytes {start}-{end}/{size}'
    mime = {'.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.png': 'image/png'}[ext]
    if request.method == 'HEAD':
        f.close()
        return Response(status_code=code, headers=h, media_type=mime)
    def stream():
        try:
            f.seek(start)
            remaining = length
            while remaining:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            f.close()
    return StreamingResponse(stream(), status_code=code, headers=h, media_type=mime)
