"""Shared routing context and safe, persistent provider diagnostics."""
import os
import re
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
import httpx
from db import db
from engine_models import EngineSettings, StoryEngines

generation_context = ContextVar('generation_context', default={})


def redact(value):
    text = str(value)
    for key, secret in os.environ.items():
        if any(s in key for s in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD')) and len(secret) > 5:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'(?i)(key=|bearer\s+|api[_-]?key[=:]\s*)[^\s&\"\']+', r'\1[REDACTED]', text)
    text = re.sub(r'(?:data:[^;]+;base64,)?[A-Za-z0-9+/=]{180,}', '[BINARY OMITTED]', text)
    return text[:6000]


class ProviderFailure(RuntimeError):
    def __init__(self, message, *, model='', code='', http_status=None, action='', request_id=''):
        self.model, self.code, self.http_status = model, code, http_status
        self.action, self.request_id = action, request_id
        super().__init__(redact(message))


def response_failure(response, model=''):
    try:
        body = response.json()
        error = body.get('error', body.get('detail', body))
        message = error.get('message', str(error)) if isinstance(error, dict) else str(error)
        code = error.get('status', error.get('code', '')) if isinstance(error, dict) else ''
    except Exception:
        message, code = response.text[:2000], ''
    status = response.status_code
    action = {
        400: 'Check the request format, model parameters and provider message.',
        401: 'Replace the provider key in Integrations & API Keys.',
        403: 'Check key restrictions, project permissions and model access.',
        404: 'Check that this model or endpoint is available to this key.',
        429: 'Check project billing and model quota; wait only if this is a temporary rate limit.',
    }.get(status, 'Check the provider service and retry when available.')
    if status == 429 and re.search(r'limit:\s*0', message):
        action = 'Image quota is zero. Enable billing for the Google AI Studio project owning this key and check its image-model quota. Replacing the key alone does not add quota.'
    return ProviderFailure(message, model=model, code=str(code or f'HTTP_{status}'), http_status=status,
                           action=action, request_id=response.headers.get('x-request-id', response.headers.get('x-goog-request-id', '')))


async def record_event(kind, provider, status, message='', error=None, segment=None, model=''):
    ctx = generation_context.get()
    if isinstance(error, httpx.HTTPStatusError):
        error = response_failure(error.response, model)
    if error is not None:
        message = str(error) or type(error).__name__
        if isinstance(error, (TimeoutError, httpx.TimeoutException)):
            message = 'Provider request timed out; completion was not confirmed.'
    event = {
        'id': uuid.uuid4().hex, 'story_id': ctx.get('story_id', ''), 'job_id': ctx.get('job_id', ''),
        'segment': segment, 'kind': kind, 'provider': provider, 'model': getattr(error, 'model', model),
        'status': status, 'http_status': getattr(error, 'http_status', None),
        'code': getattr(error, 'code', type(error).__name__ if error else ''),
        'message': redact(message), 'action': redact(getattr(error, 'action', '')),
        'request_id': redact(getattr(error, 'request_id', '')),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.generation_events.insert_one(dict(event))
    return event


async def settings():
    doc = await db.settings.find_one({'key': 'media_engines'}) or {}
    values = doc.get('values', {})
    if not values.get('studio_base_url') and os.environ.get('STUDIO_BASE_URL'):
        values['studio_base_url'] = os.environ['STUDIO_BASE_URL']
    return EngineSettings(**values)


async def preferences(story_id=''):
    doc = await db.story_engines.find_one({'_id': story_id}) or {}
    return StoryEngines(**doc)


async def resolve(kind, segment=None):
    config = await settings()
    prefs = await preferences(generation_context.get().get('story_id', ''))
    override = prefs.segments.get(str(segment)) if segment is not None else None
    return (getattr(override, kind, None) or getattr(prefs, kind) or getattr(config, kind))


def reset_provider_health():
    from services import gemini, imagegen, router
    router.HEALTH.clear()
    imagegen._IMAGE_DEAD_UNTIL = 0
    gemini._record_ok()