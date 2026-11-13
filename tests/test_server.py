from pathlib import Path
import json
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen, Request

from usage_dashboard.config import load_config
from usage_dashboard.server import Dashboard, make_server
from test_core import NOW, sample


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.input = self.root / 'input.json'
        self.input.write_text(json.dumps(sample()))
        path = self.root / 'config.json'
        path.write_text(json.dumps({'data_dir': 'data', 'sources': [
            {'id': 'alpha', 'label': 'Team Alpha', 'type': 'file', 'path': 'input.json'}]}))
        self.app = Dashboard(load_config(path))
        self.app.poll_once(now=NOW)

    def tearDown(self):
        self.tmp.cleanup()

    def test_failure_discards_current_balance_but_keeps_history(self):
        self.input.write_text('{bad')
        self.app.poll_once(now=NOW + 1)
        view = self.app.snapshot(now=NOW + 1)
        self.assertFalse(view['ok'])
        self.assertEqual(view['models'], [])
        self.assertEqual(view['sources'][0]['status'], 'unavailable')
        self.assertEqual(self.app.history_payload(now=NOW)[0]['data']['models'][0]['used'], 30)

    def test_snapshot_expires_without_another_poll(self):
        view = self.app.snapshot(now=NOW + 121)
        self.assertFalse(view['ok'])
        self.assertEqual(view['sources'][0]['status'], 'stale')
        self.assertEqual(view['models'], [])

    def test_disabled_or_removed_source_history_not_published(self):
        self.app.config['sources'][0]['enabled'] = False
        self.assertEqual(self.app.history_payload(now=NOW), [])
        self.assertEqual(self.app.snapshot(now=NOW)['sources'][0]['status'], 'disabled')
        self.app.config['sources'] = []
        self.assertEqual(self.app.history_payload(now=NOW), [])

    def test_api_routes_never_serve_private_files_or_raw_errors(self):
        # Real HTTP with demo data uses the current clock, not the fixed unit-test date.
        cfg = load_config()
        cfg['data_dir'] = str(self.root / 'http-data')
        app = Dashboard(cfg); app.poll_once()
        server = make_server(app, host='127.0.0.1', port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/api/dashboard') as r:
                raw = r.read().decode(); view = json.loads(raw)
                self.assertTrue(view['ok'])
                self.assertNotIn('data_dir', raw)
                self.assertNotIn('bearer_env', raw)
                self.assertEqual(r.headers['Cache-Control'], 'no-store')
                self.assertIn("default-src 'self'", r.headers['Content-Security-Policy'])
            for route in ['/', '/app.js', '/style.css', '/api/history', '/healthz', '/readyz']:
                with self.subTest(route=route), urlopen(base + route) as r: self.assertEqual(r.status, 200)
            for route in ['/config.json', '/data/history.sqlite', '/../../etc/passwd', '/examples/snapshot.json', '/api/dashboard/']:
                with self.subTest(route=route), self.assertRaises(HTTPError) as e: urlopen(base + route)
                self.assertEqual(e.exception.code, 404)
            with self.assertRaises(HTTPError) as e: urlopen(Request(base + '/api/dashboard', data=b'{}'))
            self.assertEqual(e.exception.code, 405)
        finally:
            server.shutdown(); server.server_close(); thread.join()
