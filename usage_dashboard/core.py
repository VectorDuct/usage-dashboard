"""Validate aggregate-only samples, combine disjoint sources, retain daily snapshots."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

MAX_MODELS = 200


def integer(value):
    if type(value) is not int or not 0 <= value <= 2**53 - 1:
        raise ValueError('Expected a non-negative safe integer')
    return value


def text(value, maximum=160):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('Invalid text field')
    return value


def timestamp(value):
    dt = datetime.fromisoformat(text(value).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return dt.timestamp()


def normalize(raw, now, stale_after):
    at = timestamp(raw['generated_at'])
    if not -5 <= now - at <= stale_after:
        raise ValueError('Sample is stale or in the future')
    window = raw['window']
    tz = text(window['timezone'])
    day = text(window['date'])
    if day != datetime.fromtimestamp(now, ZoneInfo(tz)).date().isoformat():
        raise ValueError('Sample belongs to another day')
    # The observation must belong to the declared window too (midnight safety).
    if day != datetime.fromtimestamp(at, ZoneInfo(tz)).date().isoformat():
        raise ValueError('Observation and window disagree')
    models = raw['models']
    if not isinstance(models, list) or len(models) > MAX_MODELS:
        raise ValueError('Invalid model list')
    result, seen = [], set()
    for m in models:
        model_id = text(m['id'])
        unit = m['unit']
        if unit not in ('requests', 'tokens') or (model_id, unit) in seen:
            raise ValueError('Invalid unit or duplicate model')
        seen.add((model_id, unit))
        used = integer(m['used']) if m.get('used') is not None else None
        limit = integer(m['limit']) if m.get('limit') is not None else None
        if 'remaining' in m:
            remaining = integer(m['remaining']) if m['remaining'] is not None else None
            if remaining is not None and (limit is None or used is None or remaining > limit):
                raise ValueError('Invalid reported balance')
        else:
            remaining = max(0, limit - used) if limit is not None and used is not None else None
        row = {'id': model_id, 'label': text(m.get('label', model_id)), 'unit': unit,
               'used': used, 'limit': limit,
               'estimated': m.get('estimated', False),
               'remaining': remaining,
               'percent': round(used / limit * 100, 1) if limit and used is not None else None}
        if type(row['estimated']) is not bool:
            raise ValueError('Invalid estimate flag')
        for key in ('requests', 'successes', 'failures'):
            row[key] = integer(m[key]) if m.get(key) is not None else None
        if (row['requests'] is not None and row['successes'] is not None and
                row['failures'] is not None and row['successes'] + row['failures'] > row['requests']):
            raise ValueError('Outcomes exceed requests')
        row['success_rate'] = success_rate(row)
        result.append(row)
    return {'generated_at': datetime.fromtimestamp(at, timezone.utc).isoformat(),
            'window': {'date': day, 'timezone': tz}, 'models': result}


def success_rate(row):
    if (row.get('requests') and row.get('successes') is not None and row.get('failures') is not None
            and row['successes'] + row['failures'] == row['requests']):
        return round(row['successes'] / row['requests'] * 100, 1)
    return None


def aggregate(sources):
    groups = defaultdict(list)
    partial = any(not source['ok'] for source in sources)
    for source in sources:
        if not source['ok']:
            continue
        data = source['data']
        window = data['window']
        for model in data['models']:
            groups[(model['id'], model['unit'], window['date'], window['timezone'])].append(model)
    rows = []
    for (model_id, unit, day, tz), parts in sorted(groups.items()):
        row = {'id': model_id, 'label': parts[0]['label'], 'unit': unit,
               'window': {'date': day, 'timezone': tz}, 'partial': partial,
               'estimated': any(p['estimated'] for p in parts), 'source_count': len(parts)}
        for key in ('used', 'limit', 'remaining', 'requests', 'successes', 'failures'):
            values = [p[key] for p in parts]
            row[key] = sum(values) if all(v is not None for v in values) else None
        if partial:
            row['limit'] = row['remaining'] = None
        row['percent'] = round(row['used'] / row['limit'] * 100, 1) if row['limit'] and row['used'] is not None else None
        row['success_rate'] = success_rate(row)
        rows.append(row)
    return rows


class History:
    """Absolute daily snapshots, not increments; never reads an upstream database."""
    def __init__(self, path, days):
        self.path, self.days = Path(path), days
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS snapshots (source TEXT, day TEXT, timezone TEXT, observed REAL, data TEXT, PRIMARY KEY(source, day, timezone))')

    def save(self, source, data, now):
        at = timestamp(data['generated_at'])
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute('INSERT INTO snapshots VALUES (?, ?, ?, ?, ?) ON CONFLICT(source, day, timezone) DO UPDATE SET observed=excluded.observed, data=excluded.data WHERE excluded.observed >= snapshots.observed',
                       (source, data['window']['date'], data['window']['timezone'], at, json.dumps(data, ensure_ascii=False, allow_nan=False)))
            db.execute('DELETE FROM snapshots WHERE observed < ?', (now - self.days * 86400,))

    def read(self, now):
        with sqlite3.connect(self.path, timeout=10) as db:
            records = db.execute('SELECT source, data FROM snapshots WHERE observed >= ? ORDER BY day DESC, source LIMIT 128', (now - self.days * 86400,)).fetchall()
        return [{'source_id': source, 'data': json.loads(data)} for source, data in records]
