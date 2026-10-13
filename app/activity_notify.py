"""Opt-in, aggregate new-profile notifications for the operator; never visitor IPs or names."""
import json
import time
import urllib.request

import db
from halo_paths import data_path

STATE_KEY = 'ops:activity-notify'
INTERVAL = 300


def settings():
    path = data_path('activity-notify.json')
    return json.loads(path.read_text()) if path.exists() else {}


def deliver(url, count):
    noun = 'profile' if count == 1 else 'profiles'
    body = f'{count} new player {noun} added to ClutchTape.'
    request = urllib.request.Request(url, data=body.encode(), headers={
        'Title': 'ClutchTape activity', 'Priority': '2', 'Tags': 'chart_with_upwards_trend',
    })
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status >= 300:
            raise RuntimeError('Activity notification delivery failed')


def poll():
    config = settings()
    if not config.get('enabled') or not config.get('url'):
        return
    now = time.time()
    state = db.kv_get(STATE_KEY)
    if state is None:
        # Activation starts here; never announce old imports or prior tests.
        db.kv_set(STATE_KEY, {'cursor': config.get('since', now), 'sent_at': now, 'attempt_at': 0})
        return
    if now - max(state.get('sent_at', 0), state.get('attempt_at', 0)) < INTERVAL:
        return
    row = db.q1("SELECT COUNT(*) n, MAX(created_at) newest FROM players WHERE created_at>? AND created_at<=?",
                state['cursor'], now)
    if not row['n']:
        return
    # Bound retries too. Leave the cursor unchanged on failure so activity is not lost.
    state['attempt_at'] = now
    db.kv_set(STATE_KEY, state)
    deliver(config['url'], row['n'])
    db.kv_set(STATE_KEY, {'cursor': row['newest'], 'sent_at': now, 'attempt_at': now})
