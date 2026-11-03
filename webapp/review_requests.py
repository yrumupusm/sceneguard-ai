"""Read explicit experiment questions and save answers; processing stays local CLI."""
import sqlite3

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from .app import app, config
from .review_request_store import RequestConflict, configured_store, experiment_entry


@app.get('/api/review-requests')
def review_requests(experiment_id: str):
    try:
        c = config()
        experiment_entry(c, experiment_id)
        return {'requests': configured_store(c).list(experiment_id)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except (OSError, KeyError, TypeError, sqlite3.Error):
        raise HTTPException(503, 'review request store unavailable')


@app.get('/api/review-requests/summary')
def review_request_summary():
    try:
        return {'experiments': configured_store(config()).summary()}
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        raise HTTPException(503, 'review request store unavailable')


@app.post('/api/review-requests/{request_id}/answer')
async def answer_review_request(request_id: str, request: Request):
    from .incident import same_origin_json
    same_origin_json(request)
    try:
        body = await request.json()
        if not isinstance(body, dict) or set(body) != {'expected_version', 'reviewer', 'answer', 'note'}:
            raise ValueError('invalid answer fields')
        c = config()
        db = configured_store(c)
        return {'request': db.answer(c, request_id, **body)}
    except RequestConflict as exc:
        return JSONResponse(status_code=409, content={'detail': str(exc), 'request': db.get(request_id)})
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except KeyError:
        raise HTTPException(404, 'unknown review request')
    except (OSError, TypeError, sqlite3.Error):
        raise HTTPException(503, 'review request store unavailable')
