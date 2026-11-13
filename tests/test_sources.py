from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import tempfile
import threading
import unittest

from usage_dashboard.config import load_config
from usage_dashboard.sources import fetch, project_naoya
from test_core import NOW, sample


class SourcesTests(unittest.TestCase):
    def test_config_defaults_and_relative_paths(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'config.json'
            p.write_text(json.dumps({'sources': [{'id': 'a', 'type': 'file', 'path': 'snapshot.json'}]}))
            cfg = load_config(p)
            self.assertEqual(cfg['sources'][0]['path'], str(Path(d) / 'snapshot.json'))
            self.assertEqual(cfg['host'], '127.0.0.1')
            self.assertEqual(cfg['port'], 8900)

    def test_bad_config_fails_before_serving(self):
        cases = [{'poll_interval': 0}, {'timezone': 'Not/AZone'}, {'port': True},
                 {'sources': [{'id': 'a', 'type': 'mystery'}]},
                 {'sources': [{'id': 'a', 'type': 'demo'}, {'id': 'a', 'type': 'demo'}]},
                 {'sources': [{'id': 'a', 'type': 'http', 'url': 'https://user:pass@example.test/data'}]}]
        for raw in cases:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as d:
                p = Path(d) / 'c.json'; p.write_text(json.dumps(raw))
                with self.assertRaises(ValueError): load_config(p)

    def test_demo_has_current_window_and_no_generation(self):
        raw = fetch({'id': 'demo', 'type': 'demo'}, timeout=1, now=NOW)
        self.assertEqual(raw['window'], {'date': '2026-11-13', 'timezone': 'UTC'})
        self.assertGreater(len(raw['models']), 0)

    def test_file_adapter_reads_only_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'snapshot.json'; p.write_text(json.dumps(sample()))
            self.assertEqual(fetch({'type': 'file', 'path': str(p)}, 1, NOW), sample())

    def test_http_credential_env_and_no_redirect_forwarding(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append((self.path, self.headers.get('Authorization')))
                if self.path == '/redirect':
                    self.send_response(302); self.send_header('Location', '/secret-target'); self.end_headers()
                else:
                    self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(sample()).encode())
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        os.environ['TEST_USAGE_TOKEN'] = 'synthetic-token'
        try:
            source = {'type': 'http', 'url': f'http://127.0.0.1:{server.server_port}/data',
                      'bearer_env': 'TEST_USAGE_TOKEN'}
            self.assertEqual(fetch(source, 1, NOW)['models'][0]['used'], 30)
            self.assertEqual(received, [('/data', 'Bearer synthetic-token')])
            source['url'] = f'http://127.0.0.1:{server.server_port}/redirect'
            with self.assertRaises(Exception): fetch(source, 1, NOW)
            self.assertEqual(len(received), 2)
        finally:
            os.environ.pop('TEST_USAGE_TOKEN', None)
            server.shutdown(); server.server_close(); thread.join()

    def test_naoya_projection_uses_runtime_quota_and_excludes_accounts(self):
        summary = {'generated_at': '2026-11-13T12:00:00Z',
                   'status': {'browser_connected': True, 'service_connected': True},
                   'accounts': [{'email': 'private@example.test'}],
                   'scheduler': {'usage_window': {'date': '2026-11-13', 'timezone': 'America/Los_Angeles'},
                                 'models': [{'model': 'model-a', 'daily_requests': 42}],
                                 'quota_by_model': [{'model': 'model-a', 'total_quota': 100,
                                                     'estimated_remaining_quota': 65}],
                                 'token_quota_by_model': []}}
        result = project_naoya(summary)
        self.assertEqual(result['models'][0]['used'], 35)
        self.assertEqual(result['models'][0]['requests'], 42)
        self.assertNotIn('accounts', str(result))
        summary['status']['browser_connected'] = False
        with self.assertRaises(ValueError): project_naoya(summary)

class TokenPoolTests(unittest.TestCase):
    def test_shared_token_pool_appears_once_and_unknown_usage_stays_unknown(self):
        from usage_dashboard.core import normalize
        window = {'date': '2026-11-13', 'timezone': 'UTC'}
        quota = {'model': 'model-a', 'pool': 'build', 'scope': 'build/account',
                 'token_metric': 'total_tokens', 'window': window,
                 'unknown_usage_requests': 0, 'unknown_limit_accounts': 0,
                 'observed_tokens': {'total_tokens': 1200}, 'limit': 2000,
                 'estimated_remaining': 1000}
        raw = {'generated_at': '2026-11-13T12:00:00Z',
               'status': {'browser_connected': True, 'service_connected': True},
               'scheduler': {'usage_window': window, 'models': [
                   {'model': 'model-a', 'daily_requests': 3}, {'model': 'model-b', 'daily_requests': 5}],
                   'quota_by_model': [], 'token_quota_by_model': [quota, {**quota, 'model': 'model-b'}]}}
        rows = normalize(project_naoya(raw), NOW, 120)['models']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'pool:build')
        self.assertEqual(rows[0]['remaining'], 1000)
        self.assertIsNone(rows[0]['requests'])
        for entry in raw['scheduler']['token_quota_by_model']: entry['unknown_usage_requests'] = 1
        row = normalize(project_naoya(raw), NOW, 120)['models'][0]
        self.assertIsNone(row['used'])
        self.assertIsNone(row['remaining'])

class NaoyaLoginTests(unittest.TestCase):
    def test_successful_console_redirect_sets_cookie_without_following_redirect(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append(self.path)
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(302)
                self.send_header('Set-Cookie', 'console=synthetic; Path=/; HttpOnly')
                self.send_header('Location', '/')
                self.end_headers()
            def do_GET(self):
                seen.append(self.path)
                if self.path != '/api/dashboard/realtime' or self.headers.get('Cookie') != 'console=synthetic':
                    self.send_response(403); self.end_headers(); return
                raw = {'generated_at': '2026-11-13T12:00:00Z',
                       'status': {'browser_connected': True, 'service_connected': True},
                       'scheduler': {'usage_window': {'date': '2026-11-13', 'timezone': 'UTC'},
                                     'models': [], 'quota_by_model': [], 'token_quota_by_model': []}}
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(raw).encode())
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        os.environ.update(TEST_NAOYA_USER='synthetic-user', TEST_NAOYA_PASS='synthetic-pass')
        try:
            source = {'type': 'naoya', 'url': f'http://127.0.0.1:{server.server_port}',
                      'username_env': 'TEST_NAOYA_USER', 'password_env': 'TEST_NAOYA_PASS'}
            self.assertEqual(fetch(source, 1, NOW)['models'], [])
            self.assertEqual(seen, ['/login', '/api/dashboard/realtime'])
        finally:
            os.environ.pop('TEST_NAOYA_USER', None);os.environ.pop('TEST_NAOYA_PASS', None)
            server.shutdown();server.server_close();thread.join()
