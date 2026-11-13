import copy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from usage_dashboard.core import normalize, aggregate, History

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc).timestamp()


def sample(used=30, limit=100):
    return {'generated_at': '2026-11-13T12:00:00Z',
            'window': {'date': '2026-11-13', 'timezone': 'UTC'},
            'models': [{'id': 'model-a', 'label': 'Model A', 'unit': 'requests',
                        'used': used, 'limit': limit, 'requests': 42,
                        'successes': 39, 'failures': 3}]}


class CoreTests(unittest.TestCase):
    def test_whitelist_omits_account_and_secret_fields(self):
        raw = sample()
        raw['credentials'] = 'never-public'
        raw['models'][0]['accounts'] = [{'email': 'private@example.test'}]
        data = normalize(raw, NOW, 120)
        self.assertNotIn('never-public', str(data))
        self.assertNotIn('accounts', str(data))
        self.assertEqual(data['models'][0]['remaining'], 70)

    def test_unknown_quota_is_not_zero_or_guessed(self):
        item = normalize(sample(limit=None), NOW, 120)['models'][0]
        self.assertIsNone(item['limit'])
        self.assertIsNone(item['remaining'])
        self.assertIsNone(item['percent'])

    def test_over_limit_attempts_do_not_become_negative_balance(self):
        item = normalize(sample(used=120), NOW, 120)['models'][0]
        self.assertEqual(item['used'], 120)
        self.assertEqual(item['remaining'], 0)
        self.assertEqual(item['percent'], 120)

    def test_invalid_numbers_and_duplicate_models_rejected(self):
        for value in [-1, True, 1.5, '30']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize(sample(used=value), NOW, 120)
        raw = sample()
        raw['models'].append(copy.deepcopy(raw['models'][0]))
        with self.assertRaises(ValueError):
            normalize(raw, NOW, 120)

    def test_stale_future_and_wrong_day_are_rejected(self):
        for timestamp in ['2026-11-13T11:00:00Z', '2026-11-13T12:01:00Z', '2026-11-13T12:00:00']:
            raw = sample(); raw['generated_at'] = timestamp
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                normalize(raw, NOW, 120)
        raw = sample(); raw['window']['date'] = '2026-11-12'
        with self.assertRaises(ValueError):
            normalize(raw, NOW, 120)

    def test_aggregation_sums_independent_balances_not_attempts(self):
        a = normalize(sample(used=120), NOW, 120)
        b = normalize(sample(used=10, limit=20), NOW, 120)
        rows = aggregate([{'ok': True, 'data': a}, {'ok': True, 'data': b}])
        self.assertEqual(rows[0]['used'], 130)
        self.assertEqual(rows[0]['limit'], 120)
        self.assertEqual(rows[0]['remaining'], 10)
        self.assertEqual(rows[0]['requests'], 84)

    def test_partial_source_hides_total_balance(self):
        rows = aggregate([{'ok': True, 'data': normalize(sample(), NOW, 120)}, {'ok': False, 'data': None}])
        self.assertIsNone(rows[0]['remaining'])
        self.assertTrue(rows[0]['partial'])

    def test_missing_limit_propagates_to_aggregate(self):
        rows = aggregate([{'ok': True, 'data': normalize(sample(), NOW, 120)},
                          {'ok': True, 'data': normalize(sample(limit=None), NOW, 120)}])
        self.assertIsNone(rows[0]['limit'])
        self.assertIsNone(rows[0]['remaining'])

    def test_timezone_and_units_never_merge(self):
        a = normalize(sample(), NOW, 120)
        b = sample(); b['window']['timezone'] = 'America/Los_Angeles'
        c = sample(); c['models'][0]['unit'] = 'tokens'
        rows = aggregate([{'ok': True, 'data': x} for x in [a, normalize(b, NOW, 120), normalize(c, NOW, 120)]])
        self.assertEqual(len(rows), 3)

    def test_success_rate_requires_all_outcomes(self):
        raw = sample(); raw['models'][0].pop('successes')
        row = normalize(raw, NOW, 120)['models'][0]
        self.assertIsNone(row['success_rate'])
        self.assertEqual(normalize(sample(), NOW, 120)['models'][0]['success_rate'], 92.9)

    def test_history_replaces_same_day_snapshot_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'history.sqlite'
            history = History(path, 30)
            history.save('source-a', normalize(sample(), NOW, 120), NOW)
            history.save('source-a', normalize(sample(used=35), NOW, 120), NOW)
            rows = History(path, 30).read(NOW)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['data']['models'][0]['used'], 35)
            self.assertNotIn('accounts', str(rows))

    def test_history_ignores_older_samples_and_expires(self):
        with tempfile.TemporaryDirectory() as d:
            history = History(Path(d) / 'h.sqlite', 2)
            fresh = normalize(sample(used=40), NOW, 120)
            history.save('a', fresh, NOW)
            older = normalize(sample(used=30), NOW, 120)
            older['generated_at'] = '2026-11-13T11:59:30Z'
            history.save('a', older, NOW)
            self.assertEqual(history.read(NOW)[0]['data']['models'][0]['used'], 40)
            self.assertEqual(history.read(NOW + 3 * 86400), [])

class BalanceTests(unittest.TestCase):
    def test_reported_capped_balance_survives_revalidation(self):
        raw = sample(used=120)
        raw['models'][0]['remaining'] = 25
        data = normalize(raw, NOW, 120)
        self.assertEqual(data['models'][0]['remaining'], 25)
        self.assertEqual(normalize(data, NOW, 120)['models'][0]['remaining'], 25)

    def test_invalid_reported_balance_rejected(self):
        for left in [-1, 101, True]:
            raw = sample(); raw['models'][0]['remaining'] = left
            with self.subTest(left=left), self.assertRaises(ValueError):
                normalize(raw, NOW, 120)
