"""Configuration is private. Only explicitly selected branding enters the API."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

DEFAULT = {'host': '127.0.0.1', 'port': 8900, 'timezone': 'UTC',
           'poll_interval': 30, 'stale_after': 120, 'timeout': 5, 'history_days': 30,
           'data_dir': 'data', 'site': {'title': 'Usage Dashboard',
           'description': 'Model usage, at a glance.', 'language': 'en'},
           'sources': [{'id': 'demo', 'label': 'Demo workspace', 'type': 'demo'}]}


def load_config(path=None):
    base = Path(path).resolve().parent if path else Path.cwd()
    raw = json.loads(Path(path).read_text()) if path else {}
    if not isinstance(raw, dict):
        raise ValueError('Configuration must be an object')
    cfg = {**DEFAULT, **raw, 'site': {**DEFAULT['site'], **raw.get('site', {})}}
    for key, lower, upper in [('port', 1, 65535), ('poll_interval', 1, 3600),
                              ('stale_after', 5, 86400), ('timeout', 1, 30), ('history_days', 1, 365)]:
        value = cfg[key]
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError('Invalid setting: ' + key)
    if not isinstance(cfg['host'], str) or not cfg['host']:
        raise ValueError('Invalid listen host')
    try: ZoneInfo(cfg['timezone'])
    except Exception: raise ValueError('Invalid timezone') from None
    if cfg['site']['language'] not in ('en', 'zh-CN'):
        raise ValueError('Supported languages: en, zh-CN')
    for key in ('title', 'description'):
        if not isinstance(cfg['site'][key], str) or len(cfg['site'][key]) > 200:
            raise ValueError('Invalid site text')
    cfg['data_dir'] = str((base / cfg['data_dir']).resolve())
    if not isinstance(cfg['sources'], list) or not 1 <= len(cfg['sources']) <= 32:
        raise ValueError('Configure between 1 and 32 sources')
    sources, ids = [], set()
    for original in cfg['sources']:
        source = dict(original)
        sid = source.get('id', '')
        if not isinstance(sid, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', sid) or sid in ids:
            raise ValueError('Source IDs must be unique letters, digits, underscores or hyphens')
        ids.add(sid)
        source.setdefault('label', sid)
        if not isinstance(source['label'], str) or not 1 <= len(source['label']) <= 160:
            raise ValueError('Invalid source label')
        if source.get('type') not in ('demo', 'file', 'http', 'naoya'):
            raise ValueError('Unknown source type')
        if type(source.get('enabled', True)) is not bool:
            raise ValueError('Invalid source enabled flag')
        if source['type'] == 'file':
            if not isinstance(source.get('path'), str) or not source['path']:
                raise ValueError('File source needs a path')
            source['path'] = str((base / source['path']).resolve())
        if source['type'] in ('http', 'naoya'):
            url = urlsplit(source.get('url', ''))
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError('Source needs an HTTP(S) URL without embedded credentials or fragments')
            # Explicit remote cleartext is rejected: credentials must not travel over plaintext.
            if url.scheme == 'http' and url.hostname not in ('localhost', '127.0.0.1', '::1'):
                raise ValueError('Remote sources require HTTPS; use a local tunnel for private HTTP')
            for key in ('bearer_env', 'username_env', 'password_env'):
                if key in source and (not isinstance(source[key], str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', source[key])):
                    raise ValueError('Invalid credential environment variable name')
            if source['type'] == 'naoya' and not all(source.get(k) for k in ('username_env', 'password_env')):
                raise ValueError('Naoya source requires username_env and password_env')
        sources.append(source)
    cfg['sources'] = sources
    return cfg
