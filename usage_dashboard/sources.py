"""Bounded, read-only aggregate sources. No generation or account-maintenance endpoints."""
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPCookieProcessor, ProxyHandler
from .core import integer

MAX_BYTES = 2 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, 'Redirects are disabled', headers, fp)


def read_json(stream):
    raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Source response too large')
    return json.loads(raw)


def credential(name):
    value = os.environ.get(name, '')
    if not value or '\r' in value or '\n' in value:
        raise ValueError('Missing or invalid credential environment variable')
    return value


def fetch(source, timeout, now):
    kind = source['type']
    if kind == 'demo':
        return {'generated_at': datetime.fromtimestamp(now, timezone.utc).isoformat(),
                'window': {'date': datetime.fromtimestamp(now, timezone.utc).date().isoformat(), 'timezone': 'UTC'},
                'models': [
                    {'id': 'atlas-chat', 'label': 'Atlas Chat', 'unit': 'requests', 'used': 684,
                     'limit': 2400, 'requests': 710, 'successes': 684, 'failures': 26, 'estimated': True},
                    {'id': 'cedar-code', 'label': 'Cedar Code', 'unit': 'tokens', 'used': 1284000,
                     'limit': 5000000, 'requests': 186, 'successes': 184, 'failures': 2},
                    {'id': 'orbit-vision', 'label': 'Orbit Vision', 'unit': 'requests', 'used': 92,
                     'limit': None, 'requests': 92, 'successes': 92, 'failures': 0}]}
    if kind == 'file':
        with Path(source['path']).open('rb') as stream:
            return read_json(stream)
    headers = {'Accept': 'application/json', 'Cache-Control': 'no-cache'}
    if source.get('bearer_env'):
        headers['Authorization'] = 'Bearer ' + credential(source['bearer_env'])
    # Do not inherit machine proxy settings, which may route private traffic externally.
    jar = CookieJar()
    client = build_opener(ProxyHandler({}), NoRedirect(), HTTPCookieProcessor(jar))
    if kind == 'naoya':
        fields = {'username': credential(source['username_env']), 'password': credential(source['password_env'])}
        request = Request(source['url'].rstrip('/') + '/login', data=urlencode(fields).encode())
        try:
            with client.open(request, timeout=timeout) as response:
                response.read(MAX_BYTES + 1)
        except HTTPError as error:
            # Naoya authenticates by setting a session cookie and returning 302 /.
            # Accept that response without following it or forwarding credentials.
            valid_login = error.code in (302, 303) and error.headers.get('Location') == '/'
            error.close()
            if not valid_login:
                raise
        if not list(jar):
            raise ValueError('Console authentication failed')
        url = source['url'].rstrip('/') + '/api/dashboard/realtime'
    else:
        url = source['url']
    with client.open(Request(url, headers=headers), timeout=timeout) as response:
        raw = read_json(response)
    return project_naoya(raw) if kind == 'naoya' else raw


def project_naoya(raw):
    """Project the Naoya realtime-summary dialect into the canonical contract."""
    status = raw['status']
    if status.get('browser_connected') is not True or status.get('service_connected') is not True:
        raise ValueError('Source runtime is disconnected')
    scheduler = raw['scheduler']
    models = {m['model']: m for m in scheduler['models']}
    rows = []
    for quota in scheduler.get('quota_by_model', []):
        model_id = quota['model']
        total, left = integer(quota['total_quota']), integer(quota['estimated_remaining_quota'])
        if left > total:
            raise ValueError('Invalid quota balance')
        rows.append({'id': model_id, 'unit': 'requests', 'used': total - left,
                     'limit': total, 'requests': integer(models[model_id]['daily_requests']), 'estimated': True})
    token_pools = {}
    for quota in scheduler.get('token_quota_by_model', []):
        model_id = quota['model']
        if quota.get('window') != scheduler['usage_window']:
            raise ValueError('Token quota window mismatch')
        scope = quota.get('scope')
        if scope not in ('build/model', 'build/account'):
            continue
        if quota.get('token_metric') != 'total_tokens':
            continue
        usage = quota.get('observed_tokens')
        used = integer(usage['total_tokens']) if usage is not None and quota.get('unknown_usage_requests') == 0 else None
        limit = quota.get('limit') if quota.get('unknown_limit_accounts') == 0 else None
        shared = scope == 'build/account'
        key = 'pool:' + quota['pool'] if shared else model_id
        row = {'id': key, 'label': quota['pool'] + ' (shared pool)' if shared else model_id,
               'unit': 'tokens', 'used': used, 'limit': limit,
               'remaining': quota.get('estimated_remaining') if used is not None and limit is not None else None,
               'requests': None if shared else integer(models[model_id]['daily_requests']), 'estimated': True}
        if key in token_pools and token_pools[key] != row:
            raise ValueError('Inconsistent shared token pool')
        token_pools[key] = row
    rows.extend(token_pools.values())
    return {'generated_at': raw['generated_at'], 'window': scheduler['usage_window'], 'models': rows}
