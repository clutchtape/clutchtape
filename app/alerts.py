"""Opt-in device alerts: durable inbox, background Web Push and session recaps."""
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlsplit, parse_qs, urlencode
from flask import Blueprint, abort, jsonify, request, session
import db
import privacy
import twitch
from halo_paths import data_path

bp = Blueprint('alerts', __name__)
log = logging.getLogger(__name__)
GAP = 1800
RETENTION = 90 * 86400
_KEY_LOCK = threading.Lock()

SCHEMA = '''
CREATE TABLE IF NOT EXISTS alert_devices (
 id TEXT PRIMARY KEY, host TEXT NOT NULL, subscription TEXT,
 follows TEXT NOT NULL DEFAULT '[]', settings TEXT NOT NULL DEFAULT '{}',
 created REAL NOT NULL, updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_events (
 id INTEGER PRIMARY KEY, device TEXT NOT NULL, event_key TEXT NOT NULL,
 payload TEXT NOT NULL, created REAL NOT NULL, delivered INTEGER NOT NULL DEFAULT 0,
 attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
 UNIQUE(device,event_key)
);
CREATE INDEX IF NOT EXISTS alert_delivery ON alert_events(delivered,next_attempt);
CREATE INDEX IF NOT EXISTS alert_inbox ON alert_events(device,id DESC);
'''

def keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    import fcntl
    path = data_path('clutchtape-vapid.pem')
    with _KEY_LOCK, open(data_path('clutchtape-vapid.lock'), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        else:
            key = ec.generate_private_key(ec.SECP256R1())
            raw = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as out:
                out.write(raw)
        public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(public).rstrip(b'=').decode(), str(path)


def identity():
    token = request.cookies.get('ct_alert_device', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        token = secrets.token_urlsafe(32)
    host = request.host.split(':')[0].lower()
    return hashlib.sha256((host + ':' + token).encode()).hexdigest(), token, host


def visible(player, host):
    values = [player[k] for k in ('slug', 'gamertag', 'xuid')]
    return not any(privacy.blocked(v) for v in values)


def resolve(target, host):
    if not isinstance(target, str) or len(target) > 1000:
        abort(400, 'Choose a player or squad.')
    try:
        u = urlsplit(target)
    except ValueError:
        abort(400, 'Use a valid ClutchTape player or squad link.')
    if u.netloc and u.netloc != request.host or u.scheme and u.scheme != 'https':
        abort(400, 'Use a ClutchTape player or squad link.')
    parts = u.path.strip('/').split('/')
    if parts[0] == 'sq' and len(parts) > 1:
        row = db.q1('SELECT slugs FROM squad_links WHERE code=?', parts[1])
        names = row['slugs'].split(',') if row else []
        url = '/sq/' + parts[1]
    elif parts[0] in ('p', 'squad', 'live', 'history', 'weekly', 'practice', 'scrims') and len(parts) > 1:
        names = parts[1].split(',')
        url = '/p/' + names[0] if len(names) == 1 else '/squad/' + ','.join(names)
    else:
        row = db.q1('SELECT slug FROM players WHERE gamertag=? COLLATE NOCASE OR slug=?', target, target)
        names = [row['slug']] if row else []
        url = '/p/' + names[0] if names else ''
    if not 1 <= len(names) <= 6:
        abort(404, 'Open or look up that player or squad first.')
    players = [db.q1('SELECT * FROM players WHERE slug=?', slug) for slug in dict.fromkeys(names)]
    if any(not p or not visible(p, host) for p in players):
        abort(404, 'That player or squad is unavailable.')
    configured = {}
    for name in ('FEATURED_PLAYERS', 'PRIVATE_CHANNELS'):
        if name == 'PRIVATE_CHANNELS' and host not in privacy.PRIVATE_HOSTS:
            continue
        for spec in os.getenv(name, 'CyKul|cykul' if name == 'FEATURED_PLAYERS' else '').split(','):
            gt, _, ch = spec.partition('|')
            configured[gt.strip().casefold()] = twitch.parse_login(ch.strip()) if ch else None
    raw = parse_qs(u.query).get('tw', [''])[0]
    channels = {}
    for value in raw.split(','):
        slug, sep, channel = value.partition(':')
        if sep:
            channels[slug] = twitch.parse_login(channel)
        elif len(players) == 1 and value:
            channels[players[0]['slug']] = twitch.parse_login(value)
    members = []
    for p in players:
        channel = channels.get(p['slug']) or configured.get(p['gamertag'].casefold())
        if channel and privacy.blocked(channel):
            channel = None
        members.append(dict(slug=p['slug'], name=p['gamertag'], channel=channel))
    mapping = ','.join(p['slug']+':'+p['channel'] for p in members if p['channel'])
    if mapping:
        url += '?' + urlencode({'tw': mapping})
    return dict(key=','.join(p['slug'] for p in members), label=' + '.join(p['name'] for p in members), url=url, players=members)


def subscription(value):
    if not isinstance(value, dict):
        abort(400, 'Invalid push subscription.')
    endpoint = value.get('endpoint', '')
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        abort(400)
    try:
        u = urlsplit(endpoint)
        port = u.port
    except ValueError:
        abort(400, 'Invalid push endpoint.')
    allowed = u.hostname in ('fcm.googleapis.com', 'updates.push.services.mozilla.com', 'web.push.apple.com') or bool(u.hostname and (u.hostname.endswith('.notify.windows.com') or u.hostname.endswith('.push.apple.com')))
    if u.scheme != 'https' or not allowed or u.username or u.password or port not in (None, 443) or u.fragment:
        abort(400, 'Unsupported push service.')
    try:
        k = value['keys']
        if not isinstance(k, dict) or any(not isinstance(k.get(n), str) or len(k[n]) > 100 for n in ('p256dh','auth')):
            raise ValueError()
        public = base64.urlsafe_b64decode(k['p256dh'] + '=' * (-len(k['p256dh']) % 4))
        auth = base64.urlsafe_b64decode(k['auth'] + '=' * (-len(k['auth']) % 4))
        if len(public) != 65 or public[0] != 4 or len(auth) != 16:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        abort(400, 'Invalid push keys.')
    return dict(endpoint=endpoint, keys=dict(p256dh=k['p256dh'], auth=k['auth']))


def check_write(scope="alerts", budget=30):
    from web import client_ip
    import capacity
    sent = request.headers.get('X-CSRF-Token', '')
    if not sent or not hmac.compare_digest(sent.encode(), session.get('csrf', '').encode()):
        abort(400, 'Reload this page and try again.')
    if not capacity.limiter.allow(scope+':'+client_ip(), budget, 60):
        abort(429, 'Please wait a minute before trying again.')


def clean_settings(options):
    if not isinstance(options, dict):
        abort(400, 'Invalid alert settings.')
    settings = {k: options.get(k) is True for k in ('streams', 'results', 'games')}
    quiet = options.get('quiet') or {}
    if not isinstance(quiet, dict):
        abort(400, 'Invalid quiet hours.')
    zone = quiet.get('zone', 'UTC')
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        abort(400, 'Choose a valid time zone.')
    start, end = quiet.get('start', '22:00'), quiet.get('end', '08:00')
    if any(not isinstance(v, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', v) for v in (start, end)):
        abort(400, 'Choose valid quiet hours.')
    if quiet.get('enabled') and start == end:
        abort(400, 'Quiet hours must have different start and end times.')
    settings['quiet'] = dict(enabled=quiet.get('enabled') is True, start=start, end=end, zone=zone)
    return settings


def wants(settings, follow, kind):
    return bool(settings.get(kind)) and follow.get('options', {}).get(kind, True)


def quiet_until(settings, now):
    quiet = settings.get('quiet', {})
    if not quiet.get('enabled'):
        return None
    local = datetime.fromtimestamp(now, ZoneInfo(quiet['zone']))
    clock = local.strftime('%H:%M'); start, end = quiet['start'], quiet['end']
    active = start <= clock < end if start < end else clock >= start or clock < end
    if not active:
        return None
    finish = local.replace(hour=int(end[:2]), minute=int(end[3:]), second=0, microsecond=0)
    if finish <= local:
        finish += timedelta(days=1)
    return finish.timestamp()


def reply(identifier, token, host):
    row = db.q1('SELECT * FROM alert_devices WHERE id=?', identifier)
    public, _ = keys()
    def allowed(slugs):
        return all((p := db.q1('SELECT * FROM players WHERE slug=?', slug)) and visible(p, host) for slug in slugs)
    follows = [f for f in json.loads(row['follows']) if allowed([p['slug'] for p in f['players']])] if row else []
    events = []
    for r in db.q('SELECT id,created,payload FROM alert_events WHERE device=? ORDER BY id DESC LIMIT 30', identifier):
        payload = json.loads(r['payload'])
        if allowed(payload.get('players', [])):
            events.append(dict(id=r['id'], at=r['created'], **payload))
    response = jsonify(key=public, enabled=bool(row and row['subscription']), follows=follows, settings=json.loads(row['settings']) if row else dict(streams=True, results=True), events=events)
    response.set_cookie('ct_alert_device', token, max_age=RETENTION, secure=request.is_secure, httponly=True, samesite='Lax')
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/api/alerts/state')
def state():
    identifier, token, host = identity()
    db.run('UPDATE alert_devices SET updated=? WHERE id=?', time.time(), identifier)
    return reply(identifier, token, host)


@bp.get('/api/alerts/resolve')
def target():
    return jsonify(resolve(request.args.get('target', ''), identity()[2]))


@bp.post('/api/alerts/preferences')
def preferences():
    check_write()
    identifier, token, host = identity()
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        abort(400)
    targets = data.get('targets', [])
    if not isinstance(targets, list) or len(targets) > 10:
        abort(400, 'Follow up to 10 players or squads.')
    follows = list({r['key']: r for r in (resolve(t, host) for t in targets)}.values())
    options = data.get('settings', {})
    if not isinstance(options, dict):
        abort(400)
    settings = clean_settings(options)
    overrides = data.get('overrides', {})
    if not isinstance(overrides, dict):
        abort(400, 'Invalid player preferences.')
    now = time.time()
    previous = db.q1('SELECT follows,settings FROM alert_devices WHERE id=?', identifier)
    old = {f['key']: f for f in json.loads(previous['follows'])} if previous else {}
    for f in follows:
        f['since'] = old.get(f['key'], {}).get('since', now)
        choice = overrides.get(f['key'], old.get(f['key'], {}).get('options', {}))
        if not isinstance(choice, dict):
            abort(400, 'Invalid player preferences.')
        f['options'] = {k: choice.get(k, True) is True for k in ('streams', 'results', 'games')}
        f['game_since'] = old.get(f['key'], {}).get('game_since', now)
        previous_settings = json.loads(previous['settings']) if previous else {}
        if wants(settings, f, 'games') and not wants(previous_settings, old.get(f['key'], {}), 'games'):
            f['game_since'] = now
    if not previous and db.q1('SELECT COUNT(*) AS n FROM alert_devices')['n'] >= 10000:
        abort(503, 'Alerts are busy. Please try again later.')
    db.run('UPDATE alert_events SET delivered=1 WHERE device=? AND delivered=0', identifier)
    db.run('INSERT INTO alert_devices(id,host,follows,settings,created,updated) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET follows=excluded.follows,settings=excluded.settings,updated=excluded.updated', identifier, host, json.dumps(follows), json.dumps(settings), now, now)
    return reply(identifier, token, host)


@bp.post('/api/alerts/subscribe')
def subscribe():
    check_write()
    identifier, token, host = identity()
    row = db.q1('SELECT * FROM alert_devices WHERE id=?', identifier)
    if not row or not json.loads(row['follows']):
        abort(400, 'Follow a player or squad first.')
    sub = subscription(request.get_json(silent=True))
    # An existing browser endpoint cannot be claimed by a different device cookie.
    for other in db.q('SELECT id,subscription FROM alert_devices WHERE subscription IS NOT NULL AND id<>?', identifier):
        if json.loads(other['subscription'])['endpoint'] == sub['endpoint']:
            abort(409, 'Reset this browser’s notification permission, then enable alerts again.')
    db.run('UPDATE alert_devices SET subscription=?,updated=? WHERE id=?', json.dumps(sub), time.time(), identifier)
    return reply(identifier, token, host)


@bp.post('/api/alerts/unsubscribe')
def unsubscribe():
    check_write()
    identifier, token, host = identity()
    db.run('UPDATE alert_devices SET subscription=NULL WHERE id=?', identifier)
    db.run('UPDATE alert_events SET delivered=1 WHERE device=?', identifier)
    return reply(identifier, token, host)


def enqueue(identifier, event_key, payload, now):
    db.run('INSERT OR IGNORE INTO alert_events(device,event_key,payload,created) VALUES(?,?,?,?)', identifier, event_key, json.dumps(payload), now)


@bp.post('/api/alerts/test')
def test_alert():
    check_write()
    identifier, _, _ = identity()
    row = db.q1('SELECT subscription FROM alert_devices WHERE id=?', identifier)
    if not row or not row['subscription']:
        abort(400, 'Enable phone alerts first.')
    from web import client_ip
    import capacity
    if not capacity.limiter.allow('alert-test:'+client_ip(), 2, 60):
        abort(429, 'Please wait a minute before sending another test.')
    enqueue(identifier, 'test:'+secrets.token_hex(8), dict(title='ClutchTape alerts are ready', body='Streaming and session results will arrive here for the players you follow.', url='/', tag='ct-test'), time.time())
    return jsonify(queued=True)


def followed_slugs():
    return {p['slug'] for r in db.q('SELECT follows,settings FROM alert_devices WHERE updated>?', time.time()-RETENTION) if any(json.loads(r['settings']).get(k) for k in ('results','games')) for f in json.loads(r['follows']) for p in f['players']}


def result_events(follow, since, now, host):
    players = [db.q1('SELECT * FROM players WHERE slug=?', p['slug']) for p in follow['players']]
    players = [p for p in players if p and visible(p, host)]
    if not players or any(p['sync_state'] in ('queued','syncing') for p in players):
        return []
    ids = [p['id'] for p in players]
    rows = db.q('SELECT * FROM matches WHERE player_id IN ('+','.join('?' for _ in ids)+') AND started_at>? ORDER BY started_at', *ids, max(since-86400, now-3*86400))
    games = {}
    for r in rows:
        if r['outcome'] not in ('Win', 'Loss', 'Tie'):
            continue
        games.setdefault(r['match_id'], []).append(dict(r))
    sessions = []
    for match in games.values():
        start = match[0]['started_at']
        end = max(r['started_at']+(r['duration_s'] or 0) for r in match)
        if not sessions or start-sessions[-1]['end'] >= GAP:
            sessions.append(dict(start=start, end=end, games=[]))
        sessions[-1]['end'] = max(sessions[-1]['end'], end)
        sessions[-1]['games'].append(match)
    out = []
    for s in sessions:
        if s['end'] < since or s['end']+GAP > now:
            continue
        lines = []
        for p in players:
            rs = [r for m in s['games'] for r in m if r['player_id'] == p['id']]
            if not rs:
                continue
            wins = sum(r['outcome']=='Win' for r in rs)
            losses = sum(r['outcome']=='Loss' for r in rs)
            ties = sum(r['outcome']=='Tie' for r in rs)
            kda = '/'.join(str(sum(r[k] or 0 for r in rs)) for k in ('kills','deaths','assists'))
            lines.append(f"{p['gamertag']}: {wins}W–{losses}L"+(f'–{ties}T' if ties else '')+f' · {kda} K/D/A')
        event_key = 'result:'+follow['key']+':'+str(int(s['start']))
        out.append((event_key, dict(kind='results', players=[p['slug'] for p in players], title=f"Session results · {len(s['games'])} games", body='\n'.join(lines), url=follow['url']+('&' if '?' in follow['url'] else '?')+urlencode({'session':s['games'][0][0]['match_id'],'tab':'sessions'}), tag=event_key)))
    return out


def game_events(follow, since, now, host):
    groups = {}
    for member in follow['players']:
        p = db.q1('SELECT * FROM players WHERE slug=?', member['slug'])
        if not p or not visible(p, host) or p['sync_state'] in ('queued', 'syncing'):
            continue
        for row in db.q("SELECT * FROM matches WHERE player_id=? AND started_at>? AND outcome IN ('Win','Loss','Tie') ORDER BY started_at DESC LIMIT 30", p['id'], max(since-7200, now-86400)):
            if row['started_at']+(row['duration_s'] or 0) < since or row['started_at']+(row['duration_s'] or 0) > now:
                continue
            groups.setdefault(row['match_id'], []).append((p, row))
    for mid, rows in groups.items():
        key = 'game:'+follow['key']+':'+mid
        body = '\n'.join(f"{p['gamertag']}: {r['outcome']} · {r['kills'] or 0}/{r['deaths'] or 0}/{r['assists'] or 0} K/D/A" for p, r in rows)
        yield key, dict(kind='games', follow=follow['key'], players=[p['slug'] for p, _ in rows], title='Game result · '+(rows[0][1]['map'] or 'Halo Infinite'), body=body, url='/match/'+mid+'?'+urlencode({'player':rows[0][0]['slug']}), tag=key)


def collect(now=None):
    now = now or time.time()
    devices = [dict(r) for r in db.q('SELECT * FROM alert_devices WHERE updated>?', now-RETENTION)]
    channels = set()
    for d in devices:
        d['follows'] = json.loads(d['follows']); d['settings'] = json.loads(d['settings'])
        if d['settings'].get('streams'):
            channels.update(p['channel'] for f in d['follows'] if wants(d['settings'], f, 'streams') for p in f['players'] if p.get('channel'))
    live = {}
    if channels and twitch.enabled():
        try:
            names = sorted(channels)
            for i in range(0, len(names), 100):
                for st in twitch._get('streams', user_login=names[i:i+100]):
                    live[st['user_login'].lower()] = st
        except Exception:
            log.warning('Alert stream lookup temporarily unavailable')
    for d in devices:
        for f in d['follows']:
            if wants(d['settings'], f, 'results'):
                for key, payload in result_events(f, f.get('since', d['created']), now, d['host']):
                    payload['follow'] = f['key']
                    enqueue(d['id'], key, payload, now)
            if wants(d['settings'], f, 'games'):
                for key, payload in game_events(f, f.get('game_since', f.get('since', d['created'])), now, d['host']):
                    enqueue(d['id'], key, payload, now)
            if wants(d['settings'], f, 'streams'):
                for p in f['players']:
                    player = db.q1('SELECT * FROM players WHERE slug=?', p['slug'])
                    st = live.get(p.get('channel'))
                    if not st or not player or not visible(player, d['host']) or privacy.blocked(p.get('channel')):
                        continue
                    key = 'stream:'+p['channel']+':'+str(st['id'])
                    enqueue(d['id'], key, dict(kind='streams', players=[p['slug']], title=p['name']+' is streaming', body=(st.get('title') or 'Live on Twitch')[:180], url='/p/'+p['slug']+'?'+urlencode({'tw':p['channel']}), tag=key), now)
    db.run('DELETE FROM alert_events WHERE created<?', now-RETENTION)
    db.run('DELETE FROM alert_devices WHERE updated<?', now-RETENTION)
    db.run('DELETE FROM alert_events WHERE device NOT IN (SELECT id FROM alert_devices)')


def deliver(now=None):
    from pywebpush import webpush, WebPushException
    import requests
    now = now or time.time()
    _, private = keys()
    class NoRedirects(requests.Session):
        def post(self, *args, **kwargs):
            kwargs['allow_redirects'] = False
            return super().post(*args, **kwargs)
    for e in db.q('SELECT e.*,d.subscription,d.host,d.follows,d.settings FROM alert_events e JOIN alert_devices d ON d.id=e.device WHERE e.delivered=0 AND e.next_attempt<=? ORDER BY e.id LIMIT 20', now):
        payload = json.loads(e['payload'])
        following = {p['slug'] for f in json.loads(e['follows']) for p in f['players']}
        allowed = all(slug in following and (p := db.q1('SELECT * FROM players WHERE slug=?', slug)) and visible(p, e['host']) for slug in payload.get('players', []))
        settings = json.loads(e['settings'])
        enabled = settings.get(payload.get('kind'), True)
        if payload.get('kind'):
            enabled = any(wants(settings, f, payload['kind']) and (f['key'] == payload['follow'] if payload.get('follow') else set(payload.get('players', [])) <= {p['slug'] for p in f['players']}) for f in json.loads(e['follows']))
        if not allowed or not enabled or not e['subscription'] or e['created'] < now-12*3600:
            db.run('UPDATE alert_events SET delivered=1 WHERE id=?', e['id']); continue
        until = quiet_until(settings, now) if payload.get('kind') else None
        if until:
            db.run('UPDATE alert_events SET next_attempt=? WHERE id=?', until, e['id']); continue
        try:
            # A delayed 'now streaming' alert is useful only while that broadcast is live.
            if payload.get('kind') == 'streams' and e['created'] < now-300:
                _, channel, broadcast = e['event_key'].split(':', 2)
                streams = twitch._get('streams', user_login=[channel])
                if not any(str(st['id']) == broadcast for st in streams):
                    db.run('UPDATE alert_events SET delivered=1 WHERE id=?', e['id']); continue
            with NoRedirects() as transport:
                response = webpush(subscription_info=json.loads(e['subscription']), data=e['payload'], vapid_private_key=private, vapid_claims={'sub': 'https://'+e['host']}, ttl=43200, headers={'Urgency':'high'}, timeout=10, requests_session=transport)
            if not 200 <= response.status_code < 300:
                raise RuntimeError('Push service did not accept the notification')
            db.run('UPDATE alert_events SET delivered=1 WHERE id=?', e['id'])
        except Exception as error:
            code = getattr(getattr(error, 'response', None), 'status_code', None)
            if code in (404,410):
                db.run('UPDATE alert_devices SET subscription=NULL WHERE id=? AND subscription=?', e['device'], e['subscription'])
                db.run('UPDATE alert_events SET delivered=1 WHERE device=?', e['device'])
            else:
                attempts = e['attempts']+1
                db.run('UPDATE alert_events SET attempts=?,next_attempt=?,delivered=? WHERE id=?', attempts, now+min(3600,60*2**min(attempts,6)), int(attempts>=8), e['id'])
                log.warning('Push delivery retry scheduled (status=%s)', code)


def start():
    def loop():
        while True:
            try:
                collect(); deliver()
            except Exception:
                log.exception('Alert worker cycle failed')
            time.sleep(30)
    threading.Thread(target=loop, name='alerts', daemon=True).start()


for code in (400, 404, 409, 429, 503):
    bp.register_error_handler(code, lambda error: (jsonify(error=error.description), error.code))
