"""Background sampling with a cache-only, allowlisted read interface."""
from copy import deepcopy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
from .core import normalize, aggregate, History
from .sources import fetch

STATIC = Path(__file__).with_name('static')
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}


def iso(now):
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


class Dashboard:
    def __init__(self, config):
        self.config = config
        self.history = History(Path(config['data_dir']) / 'history.sqlite', config['history_days'])
        self.lock = threading.Lock()
        self.states = {}
        self.history_ok = True
        self.stop = threading.Event()

    def poll_once(self, now=None):
        fixed = now
        states, history_ok = {}, True
        for source in self.config['sources']:
            if not source.get('enabled', True):
                continue
            at = time.time() if fixed is None else fixed
            try:
                raw = fetch(source, self.config['timeout'], at)
                observed = time.time() if fixed is None else fixed
                data = normalize(raw, observed, self.config['stale_after'])
                states[source['id']] = {'ok': True, 'data': data, 'sampled_at': iso(observed)}
            except Exception:
                # Never put upstream errors, URLs or authentication responses in the API/log.
                states[source['id']] = {'ok': False, 'data': None, 'sampled_at': iso(at)}
                continue
            try:
                self.history.save(source['id'], data, observed)
            except Exception:
                history_ok = False
        with self.lock:
            self.states, self.history_ok = states, history_ok

    def run(self):
        while not self.stop.is_set():
            self.poll_once()
            self.stop.wait(self.config['poll_interval'])

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            states, history_ok = deepcopy(self.states), self.history_ok
        sources, enabled = [], []
        for source in self.config['sources']:
            item = {'id': source['id'], 'label': source['label'], 'demo': source['type'] == 'demo',
                    'ok': False, 'data': None, 'sampled_at': None}
            if not source.get('enabled', True):
                item['status'] = 'disabled'
            else:
                state = states.get(source['id'])
                item['status'] = 'waiting' if state is None else 'unavailable'
                if state:
                    item['sampled_at'] = state['sampled_at']
                    if state['ok']:
                        try:
                            item['data'] = normalize(state['data'], now, self.config['stale_after'])
                            item.update(ok=True, status='ok')
                        except Exception:
                            item['status'] = 'stale'
                enabled.append(item)
            sources.append(item)
        return {'version': 1, 'generated_at': iso(now), 'site': {k: self.config['site'][k]
                for k in ('title', 'description', 'language')}, 'timezone': self.config['timezone'],
                'poll_interval': self.config['poll_interval'], 'ok': bool(enabled) and all(s['ok'] for s in enabled),
                'demo': any(s['demo'] for s in enabled), 'history_ok': history_ok,
                'sources': sources, 'models': aggregate(enabled)}

    def history_payload(self, now=None):
        now = time.time() if now is None else now
        visible = {s['id'] for s in self.config['sources'] if s.get('enabled', True)}
        return [row for row in self.history.read(now) if row['source_id'] in visible]


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(10)
        return sock, address


def make_server(app, host=None, port=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body, mime='application/json; charset=utf-8', head=False):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def do_GET(self, head=False):
            path = urlsplit(self.path).path
            if path in ASSETS:
                name, mime = ASSETS[path]
                self.respond(200, (STATIC / name).read_bytes(), mime, head)
            elif path == '/api/dashboard':
                self.respond(200, app.snapshot(), head=head)
            elif path == '/api/history':
                try: self.respond(200, {'snapshots': app.history_payload()}, head=head)
                except Exception: self.respond(503, {'error': 'history_unavailable'}, head=head)
            elif path == '/healthz':
                self.respond(200, {'status': 'ok'}, head=head)
            elif path == '/readyz':
                ok = app.snapshot()['ok']
                self.respond(200 if ok else 503, {'ready': ok}, head=head)
            else:
                self.respond(404, {'error': 'not_found'}, head=head)

        def do_HEAD(self): self.do_GET(head=True)
        def do_POST(self): self.respond(405, {'error': 'method_not_allowed'})
        do_PUT = do_DELETE = do_PATCH = do_POST

    return Server((host if host is not None else app.config['host'],
                   port if port is not None else app.config['port']), Handler)
