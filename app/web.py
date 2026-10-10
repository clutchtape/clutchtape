import asyncio
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from aiohttp import ClientSession
from spnkr import HaloInfiniteClient
import hmac
import logging
import hashlib
import os
import re
import secrets
import time
from datetime import datetime, timezone

from flask import Response, g, Flask, abort, jsonify, redirect, render_template, request, session, url_for

import analytics
import capacity
import privacy

import session_review
import session_watch
import analysis_view
import dashboard
import api_config
import archive
import db
import ingest
import twitch
import worker
import xbox

log = logging.getLogger("clutchtape.web")
from werkzeug.middleware.proxy_fix import ProxyFix


def _blocked(value):
    """Removed (privacy policy) or test-only on this host (privacy.hidden)."""
    return privacy.blocked(value) or privacy.hidden(value)
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)      # behind the Cloudflare tunnel: build https:// links
app.config["TRUSTED_HOSTS"] = [h.strip() for h in os.getenv("TRUSTED_HOSTS", "clutchtape.com,www.clutchtape.com,localhost,127.0.0.1").split(",") if h.strip()]
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE","1")!="0", SESSION_COOKIE_HTTPONLY=True, MAX_CONTENT_LENGTH=64 * 1024)

MAX_PLAYERS = int(os.getenv("MAX_PLAYERS", "2000"))
MAX_QUEUE = int(os.getenv("MAX_QUEUE", "25"))
# "Gamertag|twitchlogin,Gamertag2|twitchlogin2" - public example profiles, created automatically at startup.
FEATURED_SPEC = [x.strip() for x in os.getenv("FEATURED_PLAYERS", "CyKul|cykul").split(",") if x.strip() and not _blocked(x.split("|")[0])]
# Test-host-only channel defaults ("gamertag|login,..."). Config, never the DB.
PRIVATE_CHANNEL_SPEC = [x.strip() for x in os.getenv("PRIVATE_CHANNELS", "").split(",") if "|" in x]


def _channel_specs():
    """FEATURED_PLAYERS plus PRIVATE_CHANNELS when the request is on a private (test) host."""
    try:
        test = request.host.split(":", 1)[0].lower() in privacy.PRIVATE_HOSTS
    except Exception:
        test = False
    return FEATURED_SPEC + (PRIVATE_CHANNEL_SPEC if test else [])
ADDS_PER_HOUR = int(os.getenv("ADDS_PER_HOUR", "12"))
MAX_SQUAD = 6          # a 4-stack plus subs (raised from 4 on 2026-10-08 for "add a member")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
GAMERTAG_RE = re.compile(r"^[^\W_](?:[\w .#\-]{0,18})$", re.UNICODE)
_vod_cache = {}


def client_ip():
    import ipaddress
    # Cloudflare overwrites this header at the public edge; normalize before using a limiter key.
    raw=request.headers.get('CF-Connecting-IP') or request.remote_addr or 'unknown'
    try:return str(ipaddress.ip_address(raw))
    except ValueError:return request.remote_addr or 'unknown'


def csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def check_csrf():
    sent = request.form.get("csrf", "")
    if not sent or not hmac.compare_digest(sent.encode(), session.get("csrf", "").encode()):
        abort(400, "Your form expired - go back and try again.")


def slugify(gt):
    s = re.sub(r"[^a-z0-9]+", "-", gt.lower()).strip("-")
    return s or "player"


@app.template_filter("kda")
def kda_filter(v):
    """KDA always shows one decimal (9.0, -2.3)."""
    try:
        return f"{float(v):.1f}"
    except (TypeError, ValueError):
        return "—"


@app.template_filter("ago")
def ago(ts):
    if not ts:
        return "never"
    d = max(0, time.time() - float(ts))
    for n, unit in ((86400, "d"), (3600, "h"), (60, "m")):
        if d >= n:
            return f"{int(d // n)}{unit} ago"
    return "just now"


@app.template_filter("dt")
def fmt_dt(ts, f="%b %-d"):
    return datetime.fromtimestamp(float(ts), timezone.utc).astimezone().strftime(f) if ts else ""


@app.template_filter('utc')
def fmt_utc(ts, f='%b %-d'):
    return datetime.fromtimestamp(float(ts),timezone.utc).strftime(f) if ts else ''


@app.template_filter("dur")
def fmt_dur(s):
    s = int(s or 0)
    return f"{s // 60}:{s % 60:02d}"


@app.template_filter("spark")
def spark(points, w=720, h=180):
    """[(ts, value)] -> inline SVG rating chart with gridlines, peak + latest markers (no JS, no dependency)."""
    from markupsafe import Markup
    pts = [p for p in points if p[1]]
    if len(pts) < 3:
        return Markup('<p class="muted">Play a few more ranked games to see your rating graph.</p>')
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1, lo, hi = min(xs), max(xs), min(ys), max(ys)
    pad = max(15, (hi - lo) * 0.15); lo -= pad; hi += pad
    L, R, T, B = 44, 10, 10, 22
    def sx(x): return L + (x - x0) / max(1, x1 - x0) * (w - L - R)
    def sy(y): return T + (1 - (y - lo) / max(1, hi - lo)) * (h - T - B)
    d = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f} {sy(y):.1f}" for i, (x, y) in enumerate(pts))
    area = d + f" L{sx(x1):.1f} {h - B} L{sx(x0):.1f} {h - B} Z"
    grid = ""
    for k in range(4):
        val = lo + (hi - lo) * k / 3
        y = sy(val)
        grid += f'<line x1="{L}" x2="{w - R}" y1="{y:.1f}" y2="{y:.1f}" class="g"/><text x="{L - 6}" y="{y + 4:.1f}" class="t" text-anchor="end">{int(val)}</text>'
    pk = max(pts, key=lambda p: p[1]); last = pts[-1]
    import datetime as _d
    def dl(ts): return _d.datetime.fromtimestamp(ts).strftime("%b %-d")
    lab = (f'<text x="{L}" y="{h - 5}" class="t">{dl(x0)}</text><text x="{w - R}" y="{h - 5}" class="t" text-anchor="end">{dl(x1)}</text>')
    marks = (f'<circle cx="{sx(pk[0]):.1f}" cy="{sy(pk[1]):.1f}" r="4" class="pk"/>'
             f'<circle cx="{sx(last[0]):.1f}" cy="{sy(last[1]):.1f}" r="4.5" class="now"/>')
    return Markup(f'<svg class="spark" viewBox="0 0 {w} {h}" role="img" aria-label="Rating from {int(ys[0])} to {int(ys[-1])}, '
                  f'peak {int(pk[1])}">{grid}<path d="{area}" class="spark-area"/><path d="{d}" class="spark-line"/>{marks}{lab}</svg>')


@app.context_processor
def inject():
    return {"csp_nonce": getattr(g,"csp_nonce",""), "csrf_token": csrf, "xbox_ok": xbox.status()["connected"], "tip_url": os.getenv("TIP_URL", "")}


@app.before_request
def security_context():
    g.csp_nonce = secrets.token_urlsafe(24)


@app.before_request
def traffic_guard():
    if len(request.query_string)>2048 or len(request.path)>400:abort(414)
    if request.path.startswith('/static/') or request.path in ('/healthz','/readyz'):return
    if not capacity.limiter.allow('web:'+client_ip(),240):return busy_response(429)
    if not capacity.requests.acquire(blocking=False):return busy_response(503)
    g.capacity_slot=True


@app.teardown_request
def release_capacity(error=None):
    if g.pop('capacity_slot',False):capacity.requests.release()


def busy_response(code=503):
    message='Clutchtape is busy. Your saved stats are safe. Please try again shortly.'
    if request.path.startswith('/api/'):
        response=jsonify(error=message,retry_after=15);response.status_code=code
    else:
        response=Response('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Clutchtape · busy</title><main style="max-width:40em;margin:15vh auto;padding:24px;font:18px system-ui"><h1>Lots of Spartans dropping in.</h1><p>'+message+'</p><p><a href="/">Return to Clutchtape</a></p></main>',status=code,mimetype='text/html')
    response.headers['Retry-After']='15';response.headers['Cache-Control']='no-store';return response


@app.errorhandler(capacity.Busy)
def cache_busy(error):return busy_response()


@app.before_request
def old_host_redirect():
    incoming_secure = request.is_secure or "https" in request.headers.get("CF-Visitor", "")
    if "https" in request.headers.get("CF-Visitor", "") or re.search(r"[a-z]\.(xyz|app|com|tv|gg)(:\d+)?$", request.host):
        request.scheme = "https"          # any real domain is served over https by Cloudflare
    if (request.host.split(":", 1)[0].lower() in set(os.getenv("REDIRECT_HOSTS","www.clutchtape.com").split(","))
            or (request.host.split(":", 1)[0].lower() == "clutchtape.com" and not incoming_secure)):
        # Preserve paths, queries, and POST bodies when following old shared links.
        return redirect("https://clutchtape.com" + request.full_path.rstrip("?"), code=308)


@app.after_request
def headers(resp):
    try:
        test_host = request.host.split(":", 1)[0].lower() in privacy.PRIVATE_HOSTS
    except Exception:                       # untrusted Host: the request was already refused with a 400
        test_host = False
    if test_host:
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"        # the owner's test host never enters search results
    resp.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'nonce-" + getattr(g,"csp_nonce",secrets.token_urlsafe(24)) + "' 'strict-dynamic'; script-src-attr 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.ttvnw.net https://*.jtvnw.net; font-src 'self'; connect-src 'self'; worker-src 'self'; frame-src https://player.twitch.tv https://clips.twitch.tv; media-src 'self' blob:; base-uri 'self'; object-src 'none'; frame-ancestors 'self'; form-action 'self'")
    if request.is_secure: resp.headers["Strict-Transport-Security"]="max-age=31536000"
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.path.startswith("/api/companion/"):
        resp.headers["Cache-Control"]="no-store"
    if request.path.startswith("/og/"):resp.headers["Cache-Control"]="no-store"
    if request.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "public, max-age=86400"
    if resp.mimetype=='text/html' or request.path.startswith('/api/'):
        resp.headers['Cache-Control']='no-store'
    return resp


# ------------------------------------------------------------------ public pages
def _home_card():
    """A small live example for the home page: the first demo player's latest session and best auto clips."""
    solo = [x.strip() for x in os.getenv("DEMO_SOLO", "CyKul").split(",") if x.strip()]
    p = db.q1("SELECT id, gamertag, slug FROM players WHERE lower(gamertag)=lower(?)", solo[0]) if solo else None
    if not p:
        return None
    d = analytics.profile(p["id"], "ranked")
    s = next((s for s in d["sessions"] if any(m["outcome"] in ("Win","Loss") for m in s["matches"])),d["latest_session"])
    if not s:
        return None
    stats=analysis_view.measure(s["matches"])
    decided=any(m["outcome"] in ("Win","Loss") for m in s["matches"])
    return {"gamertag": p["gamertag"], "slug": p["slug"], "record": s["record"] if decided else "—", "games": s["games"], "kda": s["kda"],
            "stats": [("Score share", f"{round(stats['sc_pct'])}%" if stats.get("sc_pct") is not None else None),
                      ("Damage / min", round(stats["dmg_pm"]) if stats.get("dmg_pm") is not None else None),
                      ("K/D", round(stats["kd"], 2) if stats.get("kd") is not None else None)], "win_pct": s["win_pct"] if decided else None, "pips": [m["outcome"].lower() for m in reversed(s["matches"])][-24:],
            "clips": d["moments"][:3], "csr": d["csr_now"]}


def _live_demo_slugs():
    """Slugs of demo players whose Twitch channel is live right now (for LIVE badges on the home page)."""
    out = set()
    if not twitch.enabled():
        return out
    for spec in FEATURED_SPEC:
        gt, _, login = spec.partition("|")
        if not login:
            continue
        p = db.q1("SELECT slug FROM players WHERE lower(gamertag)=lower(?)", gt.strip())
        u = _cached("uid", login, 3600, lambda login=login: twitch.lookup_user(login))
        if p and u and _cached("live", u["id"], 60, lambda u=u: twitch.is_live(u["id"])):
            out.add(p["slug"])
    return out


def _live_now(private_host):
    """Tracked streamers who are live right now, with tonight's record (home page strip). Private host adds the owner's squad."""
    if not twitch.enabled():
        return []
    out, done = [], set()
    for spec in FEATURED_SPEC + (PRIVATE_CHANNEL_SPEC if private_host else []):
        gt, _, login = spec.partition("|")
        login = twitch.parse_login(login) if login else None
        p = db.q1("SELECT * FROM players WHERE lower(gamertag)=lower(?)", gt.strip())
        if not login or not p or p["id"] in done or (not private_host and privacy.private(p["gamertag"])):
            continue
        done.add(p["id"])
        u = _cached("uid", login, 3600, lambda login=login: twitch.lookup_user(login))
        st = _cached("stream", u["id"], 60, lambda u=u: twitch.stream(u["id"])) if u else None
        if not st:
            continue
        oa = _onair([(dict(p), [p["id"]] + [a["id"] for a in _alts(p["id"])])], st, login)
        x = oa["per"][0]
        out.append({"gamertag": p["gamertag"], "slug": p["slug"], "channel": login, "title": st["title"], "game": st["game"], "halo": st["halo"],
                    "viewers": st["viewers"], "uptime": oa["uptime"], "games": x["games"], "a": x["a"], "pips": x["pips"], "quiet": oa["quiet"],
                    "halo_s": oa["halo_s"], "switched": oa["switched"], "now_since": oa["now_since"]})
    out.sort(key=lambda c: -(c["viewers"] or 0))
    return out


def _fail(msg):
    """Redisplay this submission without storing player/channel input in cookies."""
    tags = request.form.getlist("gamertag")[:MAX_SQUAD]
    channels = request.form.getlist("twitch")[:MAX_SQUAD]
    rows = [{"gamertag": tag[:20], "twitch": channels[i][:80] if i < len(channels) else ""}
            for i, tag in enumerate(tags)]
    while len(rows) > 1 and not any(rows[-1].values()):
        rows.pop()
    return index(error=msg, form_rows=rows), 400


@app.route("/")
def index(error=None, form_rows=None):
    solo = [x.strip() for x in os.getenv("DEMO_SOLO", "CyKul,LethuL").split(",") if x.strip()]
    feat = [dict(r) for r in (db.q1("SELECT gamertag, slug FROM players WHERE lower(gamertag)=lower(?) "
                                    "AND EXISTS (SELECT 1 FROM matches m WHERE m.player_id=players.id)", g) for g in solo) if r]
    squads = []
    for spec in filter(None, os.getenv("DEMO_SQUADS", "").split(";")):
        label, _, slugs = spec.partition("=")
        if label and slugs and not any(_blocked(s) for s in slugs.split(",")):
            squads.append({"label": label.strip(), "slugs": slugs.strip()})
    demo = _cached("homecard", "x", 300, _home_card)
    live_slugs = _cached("homelive", "x", 60, _live_demo_slugs) or set()
    for f in feat:
        f["live"] = f["slug"] in live_slugs
    for q in squads:
        q["live"] = any(s in live_slugs for s in q["slugs"].split(","))
    private_host = request.host.split(":", 1)[0].lower() in privacy.PRIVATE_HOSTS
    if not private_host:
        feat = [f for f in feat if not any(privacy.private(f[k]) or privacy.blocked(f[k]) for k in ('slug','gamertag'))]
        squads = [q for q in squads if not any(privacy.private(s) for s in q['slugs'].split(','))]
        if demo and (privacy.private(demo['slug']) or privacy.private(demo['gamertag'])):
            demo = None
    live_now = _cached("livenow", "private" if private_host else "public", 60, lambda: _live_now(private_host)) or []
    test_links = []                    # owner's test host only (TEST_HOME_LINKS="label=/path;..."), never on the public site
    if request.host.split(":", 1)[0].lower() in privacy.PRIVATE_HOSTS:
        for spec in filter(None, os.getenv("TEST_HOME_LINKS", "").split(";")):
            label, _, href = spec.partition("=")
            if label.strip() and href.strip().startswith("/"):
                test_links.append({"label": label.strip(), "href": href.strip()})
    return render_template("index.html", live_now=live_now, demo=demo, twitch_on=twitch.enabled(), featured=feat, squads=squads, test_links=test_links,
                           error=error, form_rows=form_rows or [{"gamertag": "", "twitch": ""}])


@app.route("/add", methods=["POST"])
def add():
    check_csrf()
    if request.form.get("website"):                     # honeypot
        return redirect(url_for("index"))
    gts = [re.sub(r"\s+", " ", g.strip()) for g in request.form.getlist("gamertag")]
    tws = request.form.getlist("twitch") + [""] * 4
    pairs = [(g, tws[i].strip()) for i, g in enumerate(gts[:MAX_SQUAD]) if g]
    if not pairs:
        return _fail("Enter at least one gamertag.")
    seen, uniq = set(), []
    for g, tw in pairs:
        if g.lower() in seen:
            return _fail(f"“{g}” is listed twice. Enter each squadmate only once.")
        seen.add(g.lower()); uniq.append((g, tw))
    pairs = uniq
    for g, tw in pairs:
        if not GAMERTAG_RE.match(g):
            return _fail(f"\u201c{g}\u201d doesn't look like a valid gamertag.")
        if tw and not twitch.parse_login(tw):
            return _fail("Couldn't read that Twitch link. Try twitch.tv/yourname.")
    ip = client_ip()
    with db.tx() as c:
        c.execute("DELETE FROM add_log WHERE at<?", (time.time()-86400,))
        limited=c.execute("SELECT COUNT(*) FROM add_log WHERE ip=? AND at>?",(ip,time.time()-3600)).fetchone()[0]+len(pairs)>ADDS_PER_HOUR
        if not limited:
            c.executemany("INSERT INTO add_log(ip,at) VALUES(?,?)", [(ip,time.time()) for _ in pairs])
    if limited:
        response, _ = _fail("Too many lookups from your network. Existing profile links still work. Try again in an hour.")
        return response,429,{'Retry-After':'3600'}
    slugs, chans = [], []
    for g, tw_raw in pairs:
        slug, tw_login, err = _add_one(g, tw_raw)
        if err:
            if err.startswith(('New player lookups','The sync queue','Lots of people','Halo connection','Xbox lookup is having','The demo is full')):
                body,_=_fail(err)
                return body,503,{'Retry-After':'30'}
            return _fail(err)
        slugs.append(slug)
        if tw_login:
            chans.append((slug, tw_login))
    # Twitch links typed here are remembered on this browser only (session cookie), never in the URL or database.
    if chans:
        _tw_save(chans)
    # "+ Add player" on a squad page: keep the current members (existing players only, never re-looked-up)
    keep = [x for x in (request.form.get("squad") or "").lower().split(",") if re.fullmatch(r"[a-z0-9-]+", x)
            and not _blocked(x) and db.q1("SELECT 1 FROM players WHERE slug=?", x)]
    slugs = list(dict.fromkeys(keep + slugs))[:MAX_SQUAD]
    if len(slugs) == 1:
        return redirect(url_for("profile", slug=slugs[0]))
    return redirect(url_for("squad", slugs=",".join(slugs)))


def _add_one(gt, tw_raw):
    if _blocked(gt):return None,None,"This profile is unavailable."
    tw_login=twitch.parse_login(tw_raw) if tw_raw else None
    p=db.q1("SELECT slug FROM players WHERE gamertag=? COLLATE NOCASE",gt)
    if p:return p['slug'],tw_login,None
    if worker.backlog()>=MAX_QUEUE:return None,None,"The sync queue is full. Existing profiles still work; please try again shortly."
    if not xbox.status()['connected']:return None,None,"Halo connection is temporarily unavailable. Existing stats are still available."
    if not capacity.limiter.allow('new-lookups',20) or not capacity.lookups.acquire(blocking=False):
        return None,None,"New player lookups are busy. Please try again in a minute, or explore an existing profile."
    try:return _resolve_new(gt,tw_raw)
    finally:capacity.lookups.release()


def _resolve_new(gt, tw_raw):
    """Look a gamertag up, create + queue its player if new. Returns (slug, twitch_login, error)."""
    tw_login = twitch.parse_login(tw_raw) if tw_raw else None
    try:
        found = asyncio.run(asyncio.wait_for(ingest.resolve_gamertag(gt), timeout=15))
    except Exception:
        log.exception("gamertag lookup failed")
        return None, None, "Xbox lookup is having trouble right now. Try again in a minute."
    if not found:
        return None, None, f"No Xbox account named \u201c{gt}\u201d was found."
    xuid, canonical = found
    if _blocked(xuid) or _blocked(canonical):return None,None,"This profile is unavailable."
    if tw_login and twitch.enabled():
        try:
            u = twitch.lookup_user(tw_login)
        except Exception:
            u = None
        if not u:
            return None, None, f"Twitch channel \u201c{tw_login}\u201d wasn't found."
    with capacity.lookup_write:
        if _blocked(xuid) or _blocked(canonical):return None,None,"This profile is unavailable."
        p = db.q1("SELECT * FROM players WHERE xuid=?", xuid)
        if p:
            return p["slug"], tw_login, None
        if db.q1("SELECT COUNT(*) c FROM players")["c"] >= MAX_PLAYERS:
            return None, None, "The demo is full right now."
        if worker.backlog() >= MAX_QUEUE:
            return None, None, "Lots of people are trying the demo right now. Try again in a few minutes, or open the example."
        slug = slugify(canonical)
        if db.q1("SELECT 1 FROM players WHERE slug=?", slug):
            slug = f"{slug}-{xuid[-4:]}"
        cur = db.run("INSERT INTO players(xuid,gamertag,slug,created_at) VALUES(?,?,?,?)", xuid, canonical, slug, time.time())
        worker.enqueue(cur.lastrowid)
        return slug, tw_login, None


def squad_code(slugs):
    """Short stable code for a squad (/sq/<code>). Stores only the gamertag slugs, never Twitch channels."""
    slugs = ",".join(dict.fromkeys(s for s in slugs.lower().split(",") if s))
    row = db.q1("SELECT code FROM squad_links WHERE slugs=?", slugs)
    if row:
        return row["code"]
    h = hashlib.sha256(slugs.encode()).hexdigest()
    for n in (6, 8, 10, 64):
        code = h[:n]
        db.run("INSERT OR IGNORE INTO squad_links(code,slugs,created) VALUES(?,?,?)", code, slugs, time.time())
        if (db.q1("SELECT slugs FROM squad_links WHERE code=?", code) or {"slugs": None})["slugs"] == slugs:
            return code
    abort(500)


@app.route("/sq/<code>")
def squad_short(code):
    row = db.q1("SELECT slugs FROM squad_links WHERE code=?", code.lower())
    if not row:
        abort(404)
    return squad(row["slugs"], short=True, code=code.lower())


@app.route("/sq/<code>/g/<gid>")
def squad_game(code, gid):
    """Shareable link to one game's Watch together view: the squad page opens straight into it."""
    row = db.q1("SELECT slugs FROM squad_links WHERE code=?", code.lower())
    if not row or not re.fullmatch(r"[0-9a-f-]{8,36}", gid.lower()):
        abort(404)
    return squad(row["slugs"], short=True, code=code.lower(), game=gid.lower()[:8])


@app.route("/squad/<slugs>")
def squad(slugs, short=False, code=None, game=None):
    names = list(dict.fromkeys(s for s in slugs.lower().split(",") if s))[:MAX_SQUAD]
    if len(names) == 1:
        return redirect(url_for("profile", slug=names[0], **request.args))
    if not short and len(names) > 1 and all(db.q1("SELECT 1 FROM players WHERE slug=?", n) and not _blocked(n) for n in names):
        args = request.args.to_dict()
        if args.get("session"):
            args["session"] = _short_id(args["session"])
        game = re.sub(r"[^0-9a-f]", "", (args.pop("game", "") or "").lower())[:8]
        if len(game) == 8:                  # /squad/a,b?game=<id> (links from match pages) -> that game's own address
            return redirect("/sq/" + squad_code(",".join(names)) + "/g/" + game)
        return redirect("/sq/" + squad_code(",".join(names)) + ("?" + urlencode(args) if args else ""))
    ps = [_player(s) for s in names]
    if not ps:
        abort(404)
    now = time.time()
    for p in ps:
        db.run("UPDATE players SET views=views+1, last_view=? WHERE id=? AND (last_view IS NULL OR last_view<?)", now, p["id"],now-60)
    kind = _kind()
    data = analytics.squad([p["id"] for p in ps], kind)
    if not data["games"] and "kind" not in request.args:      # squads that only scrim in customs: show those rather than nothing
        kind = "all"
        data = analytics.squad([p["id"] for p in ps], kind)
    if game:                                   # /sq/<code>/g/<game>: open the night that holds this game
        gi = dashboard.select_session(data["nights"], game)
        if gi is None and kind != "all":
            kind = "all"
            data = analytics.squad([p["id"] for p in ps], kind)
            gi = dashboard.select_session(data["nights"], game)
        if gi is None:
            abort(404, "This game is not in the loaded history for this squad.")
        data["s_idx"] = gi
    else:
        data["s_idx"] = _sess_idx(data["nights"])
    if data["nights"]:
        sel = data["nights"][data["s_idx"]]
        data["night"], data["night_rec"], data["night_start"], data["night_per"] = sel["matches"], sel["record"], sel["start"], sel["per"]
    for m, p in zip(data["members"], ps):
        m["p"] = p
        m["live"] = analytics.live_summary(m["rows"]) if m["rows"] else None
        if p["sync_state"] in ("ready", "error") and worker.stale(p, active=bool(m["live"] and m["live"]["active"])):
            worker.enqueue(p["id"])
    if data["clips_pending"]:
        for p in ps:
            if p["sync_state"] in ("ready", "error") and now - (p["last_synced"] or 0) > 45:
                worker.enqueue(p["id"])
    # Twitch channels: this browser's own choices (session), then featured/test-host config
    mine = _tw_map()
    chans = {n: mine[n] for n in names if mine.get(n)}
    for spec in _channel_specs():
        gt, _, login = spec.partition("|")
        for p in ps:
            if login and gt.strip().lower() == p["gamertag"].lower():
                chans.setdefault(p["slug"], twitch.parse_login(login))
    vods, users = {}, {}
    if twitch.enabled():
        for slug, ch in list(chans.items()):
            u = _cached("uid", ch, 3600, lambda ch=ch: twitch.lookup_user(ch))
            if not u:
                chans.pop(slug); continue
            users[slug] = u
            vods[slug] = (_cached("vods", u["id"], 300, lambda u=u: twitch.recent_videos(u["id"])) or [])
    else:
        chans = {}
    slug_of = {p["id"]: p["slug"] for p in ps}
    for m in data["together"]:
        m["vod"] = {}
        for pid in m["members"]:
            v = vods.get(slug_of[pid])
            if v:
                link = twitch.vod_link(v, m["started_at"], m["duration_s"])
                if link:
                    m["vod"][slug_of[pid]] = link
                    mm = re.search(r"videos/(\d+)\?t=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", link)
                    if mm:
                        h, mi, s = (int(x or 0) for x in mm.groups()[1:])
                        m.setdefault("watch", []).append({"who": next(p["gamertag"] for p in ps if p["id"] == pid), "video": mm.group(1),
                                                          "t": f"{h}h{mi}m{s}s", "sec": h * 3600 + mi * 60 + s, "url": link})
    for m in data["members"]:                          # queue film reads for streamed games we haven't read yet
        v = vods.get(m["p"]["slug"])
        if v and m["p"]["sync_state"] == "ready":
            need = [r["match_id"] for r in m["rows"] if not r.get("film_state") and twitch.vod_link(v, r["started_at"], r["duration_s"])]
            if need:
                worker.enqueue_film(m["p"]["id"], need)
            else:
                _queue_vod_films(m["p"], v)
    for mo in data["moments"]:
        v = vods.get(slug_of.get(mo["player_id"]))
        mo["vod"] = twitch.vod_link(v, mo["at"], mo["dur_s"], lead=0) if v else None
        if mo["vod"]:
            _tag_source(mo, v, users.get(slug_of.get(mo["player_id"])))
    data["moments"] = [mo for mo in data["moments"] if mo["vod"]][:14]
    gt_of = {p["id"]: p["gamertag"] for p in ps}
    for c in data["teamwork"]["good"] + data["teamwork"]["bad"]:
        c["key"] = f"{c['match_id'][:8]}-{c['t_ms']}"
        c["watch"] = []
        for pid in c["squad_ids"]:
            v = vods.get(slug_of.get(pid))
            link = twitch.vod_link(v, c["at"], c["dur_s"], lead=0) if v else None
            m = re.search(r"videos/(\d+)\?t=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", link or "")
            if m:
                h, mi, s = (int(x or 0) for x in m.groups()[1:])
                c["watch"].append({"who": gt_of[pid], "channel": chans.get(slug_of[pid]), "video": m.group(1),
                                   "t": f"{h}h{mi}m{s}s", "sec": h * 3600 + mi * 60 + s, "url": link,
                                   "match": c["match_id"], "film_ms": c["t_ms"]})
    first = next(iter(chans.values()), None)
    g.kind_used = kind
    psrc = plabel = pcfg = None
    if first:
        fslug = next(s for s, c in chans.items() if c == first)
        fu = _cached("uid", first, 3600, lambda: twitch.lookup_user(first))
        psrc, plabel, pcfg = _player_src(first, fu, vods.get(fslug) or [], next((p["id"] for p in ps if p["slug"] == fslug), None))
    title = " + ".join(p["gamertag"] for p in ps)
    qs = {k: v for k, v in request.args.items() if k != "watch"}
    share_url = request.base_url + (("?" + urlencode(qs)) if qs else "")
    tw_n = len(data["teamwork"]["good"]) + len(data["teamwork"]["bad"])
    og = {"image": request.host_url + "og/squad/" + ",".join(p["slug"] for p in ps) + ".png", "title": f"{title} — Clutchtape squad",
          "desc": (f"{data['rec']} together over {data['games']} games ({data['win_pct']}% wins). "
                   f"{tw_n} team plays and wipes found, watch every angle at once." if data["games"]
                   else "Squad stats, teamwork moments and synced Twitch playback.")}
    if game:
        gm = next((m for n in data["nights"] for m in n["matches"] if m["match_id"].startswith(game)), None)
        if gm:
            score = f" {gm['team_score']}–{gm['enemy_score']}" if gm.get("team_score") is not None else ""
            og["title"] = f"{gm['map'] or 'Game'} · {gm['mode'] or ''} — {title}"
            og["desc"] = f"{gm['outcome']}{score}. Watch every angle of this game together, synced, with each player's stats."
    vm = {}
    for slug, vl in vods.items():
        pid = next((x["id"] for x in ps if x["slug"] == slug), None)
        if pid and vl:
            vm.update(vod_matches(pid, vl))
    _start_at_latest_match(pcfg, vm)
    comparison = session_review.comparison(data['nights'], data['s_idx'], 'recent' if request.args.get('compare') == 'recent' else 'previous')
    tab = _tab()
    extra = _hub_board(",".join(names)) if tab == "analysis" else {}
    gt = {p["id"]: p["gamertag"] for p in ps}
    kp = _kpis(data.get("night") or [], [(gt[pid], a.get("kda")) for pid, a in (data.get("night_per") or {}).items() if pid in gt]) if data.get("night") else []
    night = data.get("night") or []
    adv = _adv_kpis({gt[pid]: [g["members"][pid] for g in night if pid in g["members"]] for pid in gt},
                    [next(iter(g["members"].values())) for g in night if g["members"]]) if night else []
    together_games = [m for n in data["nights"] for m in n["matches"]]
    periods = _periods({gt[pid]: [m["members"][pid] for m in together_games if pid in m["members"]] for pid in gt},
                       [m["started_at"] for m in together_games]) if tab == "records" else None
    onair = None
    for slug, u in users.items():
        st = _cached("stream", u["id"], 60, lambda u=u: twitch.stream(u["id"]))
        if st:
            onair = _onair([(m, [m["id"]] + [a["id"] for a in _alts(m["id"])]) for m in ps], st, chans.get(slug))
            break
    return render_template("squad.html", session_picks=session_watch.for_sessions(data["nights"], [p["id"] for p in ps], vm) if tab == "sessions" else {}, watch_cues=session_watch.for_matches(night, [p["id"] for p in ps]) if tab == "latest" else {}, tab=tab, kpis=kp, adv=adv, periods=periods, pidgt=gt, onair=onair, **extra, comparison=comparison, recap_matches=session_review.recap_matches(data.get('night') or []), recap_names=[p['gamertag'] for p in ps], gtmap={p["slug"]: p["gamertag"] for p in ps}, pcfg=pcfg, vm=vm, og=og, share_url=share_url, d=data, ps=ps, chans=chans, tw=first, psrc=psrc, plabel=plabel, host=request.host.split(":")[0],
                           slugs=",".join(names), vods=vods, sq_base=("/sq/" + code) if code else None, open_game=game)


def _sess_idx(sessions):
    try:
        old=int(request.args.get('s',0))
    except ValueError:
        old=0
    i=dashboard.select_session(sessions,request.args.get('session'),request.args.get('match'),old,skip_unfinished='s' not in request.args)
    if i is None: abort(404, 'This session is not in the loaded history for this filter.')
    return i


def _short_id(match_id):
    """Session links name a session by one of its match ids; 8 hex characters are unique in practice."""
    return str(match_id)[:8]


@app.context_processor
def sess_helpers():
    def sess_url(i, anchor=None):
        args = {k: v for k, v in request.args.to_dict().items() if k not in ("s", "session", "match", "at", "watch", "vod")}
        if anchor:
            args["session"] = _short_id(anchor)
        elif i:
            args["s"] = i
        return url_for(request.endpoint, **{**(request.view_args or {}), **args}) + "#latest"
    return {"sess_url": sess_url, "squad_url": lambda slugs: "/sq/" + squad_code(slugs)}


def _kind():
    """Game-type filter. Default Ranked (what people want: Ranked Arena); old ?kind=mm links mean the same thing now."""
    k = request.args.get("kind", "ranked")
    return k if k in dict(analytics.KINDS) else "ranked"


@app.context_processor
def kind_helpers():
    def kind_url(k):
        args = {key:value for key,value in request.args.items() if key not in ('s','session','match','at','watch','vod')}
        args['kind']=k
        return url_for(request.endpoint, **{**(request.view_args or {}), **args})
    return {"kinds": analytics.KINDS, "kind_url": kind_url, "cur_kind": g.get("kind_used") or _kind()}


def _player(slug):
    if _blocked(slug):abort(404)
    p = db.q1("SELECT * FROM players WHERE slug=?", slug.lower())
    if not p or any(_blocked(p[k]) for k in ('slug','gamertag','xuid')):
        abort(404)
    return p


_admin_limits = capacity.Limiter(max_keys=2048)


def _cached(kind, key, ttl, fn):
    def safe():
        try:return fn()
        except Exception:return None
    try:return capacity.external.get((kind,key),ttl,safe,stale=True)
    except capacity.Busy:return None


KEEP_DAYS = {"partner": 60, "affiliate": 14}      # Twitch keeps past broadcasts 7 days on regular channels


def _tag_source(mo, vods, user):
    """Mark a clip as playing from the archive, or warn when Twitch is about to delete its VOD."""
    link = mo.get("vod") or ""
    if "/archive/videos/" in link:
        mo["src"] = "archive"
        return
    keep = KEEP_DAYS.get((user or {}).get("broadcaster_type") or "", 7)
    for v in vods or []:
        if not v.get("archive") and v["start"] - 30 <= mo["at"] <= v["start"] + v["dur_s"]:
            left = (v["start"] + keep * 86400 - time.time()) / 86400
            if left < 4:
                mo["expires_days"] = max(0, round(left))
            return


def _queue_vod_films(player, vods, limit=40):
    """Queue Theater-film reads for EVERY unread game a broadcast covers — Twitch VODs and archived copies — not just
    the rows on the page. Archived nights (archive.py) are often 90+ games back, so they were never filmed and their
    clips could not exist. Newest first; the worker caps each batch at 40."""
    if not vods or player["sync_state"] != "ready":
        return 0
    rows = db.q("SELECT match_id, started_at, duration_s FROM matches WHERE player_id=? AND COALESCE(film_state,0)=0 "
                "ORDER BY started_at DESC", player["id"])
    need = [r["match_id"] for r in rows if twitch.vod_link(vods, r["started_at"], r["duration_s"])][:limit]
    if need:
        worker.enqueue_film(player["id"], need)
    return len(need)


def _halo_vod(vods, player_id):
    """Newest broadcast that covers one of this player's Halo games. Streamers play other games too (CyKul's newest
    VOD was Rocket League), so 'newest broadcast' alone can open on something that isn't Halo. Falls back to newest."""
    if not vods or not player_id:
        return vods[0] if vods else None
    lo, hi = min(v["start"] for v in vods), max(v["start"] + v["dur_s"] for v in vods)
    starts = [r["started_at"] for r in db.q("SELECT started_at FROM matches WHERE player_id=? AND started_at BETWEEN ? AND ?",
                                            player_id, lo, hi)]
    return next((v for v in vods if any(v["start"] <= s <= v["start"] + v["dur_s"] for s in starts)), vods[0])


def _player_src(tw, user, vods, player_id=None):
    """Embed URL: the live channel if it is live, else the newest Halo broadcast (an offline channel embed is a dead box)."""
    if not tw:
        return None, None, None
    live = bool(user) and _cached("live", user["id"], 60, lambda: twitch.is_live(user["id"]))
    if not live and vods:
        v = _halo_vod(vods, player_id)
        return (None, f"{tw} is offline · showing a recent Halo broadcast. Click any ▶ to jump to a match.",
                {"video": str(v["id"]), "channel": tw, "live": False})
    return (None, f"{tw} · live now. Click any ▶ to jump to a match." if live else f"{tw} · Click any ▶ to jump to a match.",
            {"video": None, "channel": tw, "live": bool(live)})


def _start_at_latest_match(pcfg, vm):
    """Open the default broadcast at its newest filmed match (so the event log has something), not at 0:00."""
    if pcfg and pcfg.get("video") and vm.get(pcfg["video"]):
        m = max(vm[pcfg["video"]], key=lambda x: x[1])
        s = max(0, int(m[1]) + 30)          # skip the loading screen + intro
        pcfg["start"] = f"{s // 3600}h{s % 3600 // 60}m{s % 60}s"


# ------------------------------------------------------------------ Twitch channels: this browser only (2026-10-10)
# A channel someone attaches to a gamertag is remembered only in THEIR browser (the signed session cookie), never in
# the database and never in a URL, so shared links carry stats only. Featured pros (FEATURED_PLAYERS) and the owner's
# test squad (PRIVATE_CHANNELS, test host only) come from server config instead.
TW_MAX = 40


def _tw_map():
    m = session.get("tw")
    return dict(m) if isinstance(m, dict) else {}


def _tw_save(pairs):
    """pairs: [(slug, login or None)]; None/'' forgets that slug's channel on this browser."""
    m = _tw_map()
    for slug, ch in pairs:
        ch = twitch.parse_login(ch or "") if ch else None
        if ch:
            m.pop(slug, None)
            m[slug] = ch
        else:
            m.pop(slug, None)
    session["tw"] = dict(list(m.items())[-TW_MAX:])


@app.before_request
def _tw_out_of_urls():
    """Old/shared links with ?tw=: remember the channel on this browser and reload the clean address."""
    if request.method != "GET" or "tw" not in request.args or request.path.startswith(("/api/", "/static/", "/og/")):
        return None
    raw, pairs = request.args.get("tw") or "", []
    page_slug = (request.view_args or {}).get("slug") if request.view_args else None
    for part in raw.split(","):
        s_, sep, c = part.partition(":")
        if sep and re.fullmatch(r"[a-z0-9-]+", s_.lower()):
            pairs.append((s_.lower(), c))
        elif not sep and page_slug:
            pairs.append((page_slug.lower(), s_))
    if pairs:
        _tw_save(pairs)
    args = [(k, v) for k, v in request.args.items(multi=True) if k != "tw"]
    return redirect(request.path + ("?" + urlencode(args) if args else ""), code=302)


def _channel_for(p):
    """Twitch channel to show: this browser's own choice for the player, else the featured example's channel."""
    tw = _tw_map().get(p["slug"])
    if tw:
        return tw
    for spec in _channel_specs():
        gt, _, login = spec.partition("|")
        if gt.strip().lower() == p["gamertag"].lower() and login:
            return twitch.parse_login(login)
    return None


# ------------------------------------------------------------------ one page per player / squad (Halo-site layout)
HUB_TABS = [("latest", "⚡ Latest session"), ("sessions", "Sessions"), ("clips", "Clips"), ("analysis", "Analysis"), ("records", "Records")]


def _tab():
    t = request.args.get("tab", "latest")
    return t if t in dict(HUB_TABS) else "latest"


@app.context_processor
def hub_helpers():
    def tab_url(t, **extra):
        args = {k: v for k, v in request.args.items() if k not in ("tab", "watch", *extra)}
        if t != "latest":
            args["tab"] = t
        args.update({k: v for k, v in extra.items() if v is not None})
        if args.get("session"):
            args["session"] = _short_id(args["session"])
        return request.path + (("?" + urlencode(args)) if args else "")
    return {"hub_tabs": HUB_TABS, "tab_url": tab_url}


def _kpis(matches, per=None):
    """Session tiles like the Halo site: record, win rate, games, time played, close games, best KDA.
    per: [(gamertag, kda)] for a squad; a solo page shows its best single game instead."""
    dec = [m for m in matches if m.get("outcome") in ("Win", "Loss")]
    w = sum(1 for m in dec if m["outcome"] == "Win")
    secs = int(sum(m.get("duration_s") or 0 for m in matches))
    close = sum(1 for m in matches if close_games.score(dict(m)))
    tiles = [{"big": f"{w}-{len(dec) - w}", "label": "Record"},
             {"big": f"{round(100 * w / len(dec))}%" if dec else "—", "label": "Win rate"},
             ({"big": len(matches), "label": "Games together"} if per else
              {"big": kda_filter(round(sum(m.get("kda") or 0 for m in matches) / len(matches), 1)) if matches else "—", "label": "KDA / game"}),
             {"big": f"{secs // 3600}h {secs % 3600 // 60}m" if secs >= 3600 else f"{secs // 60}m", "label": "Played"},
             {"big": close, "label": "Close games", "title": "Decided by a kill, a cap or a few points (same rule as Close games)"}]
    if per:
        name, kda = max(per, key=lambda x: x[1] if x[1] is not None else -99)
        tiles.append({"big": name, "label": f"Best KDA · {kda_filter(kda)}", "hot": True})
    elif matches:
        best = max(matches, key=lambda m: m.get("kda") if m.get("kda") is not None else -99)
        tiles.append({"big": kda_filter(best.get("kda")), "label": f"Best game · {analytics.clean_map(best.get('map')) or 'map'}", "hot": True})
    return tiles


def _signed(v, unit=""):
    return None if v is None else f"{v:+g}{unit}"


def _adv_kpis(by_name, games=None):
    """Advanced tile row. by_name: {gamertag: [match rows]} (one entry on a solo page).
    games: one row per game for game-level stats on a squad page (lobby MMR, underdog record); defaults to the rows.
    Tiles without data are dropped (custom games have no expected kills or MMR); at most 8 are shown."""
    rows = [r for rs in by_name.values() for r in rs]
    if not rows:
        return []
    a = analytics._agg(rows)
    g = analytics._agg(games if games is not None else rows)
    ups = g.get("upsets")
    tile = {
        "kd": (a["kd"], "K/D", f"{a['kills_pg']} kills · {a['deaths_pg']} deaths a game"),
        "dpm": (a["dmg_pm"], "Damage / min", None),
        "dka": (a["dmg_ka"], "Damage / (K+A)", "Damage dealt per kill plus assist: how much damage each kill or assist cost"),
        "sc": (f"{a['sc_pct']}%" if a["sc_pct"] is not None else None, "Score share", "Share of the team's personal score"),
        "dd": (_signed(a["dmg_diff_pg"]), "Damage ± / game", "Damage dealt minus damage taken, per game"),
        "share": (f"{a['dmg_share']}%" if a["dmg_share"] is not None else None, "Team damage share", "Share of your team's damage you dealt"),
        "xk": (_signed(a["xk_pg"]), "Kills vs expected", "Kills above or below what Halo expected in that lobby, per game (matchmaking only)"),
        "xd": (_signed(a["xd_pg"]), "Deaths vs expected", "Deaths avoided compared with Halo's expectation, per game (matchmaking only)"),
        "csr": (_signed(a["csr_net"]), "CSR change", "Net ranked CSR over these games"),
        "mmr": (_signed(g["mmr_edge"]), "Lobby MMR edge", "Your team's matchmaking rating minus the enemy's, averaged. Negative = you were the underdog"),
        "dog": (f"{ups['wins']}-{ups['games'] - ups['wins']}" if ups else None, "As underdog", "Record in games where the enemy team's MMR was 25+ higher"),
        "life": (f"{a['life']}s" if a["life"] is not None else None, "Avg life", "Average time alive per spawn"),
        "acc": (f"{a['acc']}%" if a["acc"] is not None else None, "Accuracy", None),
        "hs": (f"{a['hs_pct']}%" if a["hs_pct"] is not None else None, "Headshot kills", None),
        "spree": (a["spree"] or None, "Best spree", None),
    }
    if len(by_name) == 1:
        order = ("dpm", "dka", "dd", "sc", "kd", "share", "xk", "csr", "mmr", "dog", "xd", "life", "acc", "hs", "spree")
    else:                       # squad: CSR is per member (see the table below), so no summed tile
        lead = [(n, analytics._agg(rs)) for n, rs in by_name.items() if rs]
        for key, label, title, fmt in (("dmg_share", "Most team damage", "Highest share of the team's damage", lambda v: f"{v}%"),
                                       ("xk_pg", "Most kills vs expected", "Kills above Halo's expectation per game", lambda v: f"{v:+g}")):
            have = [(n, x[key]) for n, x in lead if x.get(key) is not None]
            if have:
                n, v = max(have, key=lambda x: x[1])
                tile[key] = (n, f"{label} · {fmt(v)}", title)
        order = ("dpm", "dka", "dd", "kd", "dmg_share", "xk_pg", "mmr", "dog", "xk", "life", "acc", "spree")
    t = [tile[k] for k in order if k in tile]
    out = [{"big": big, "label": label, "title": title} for big, label, title in t if big not in (None, "")]
    return out[:8]


PERIODS = ((30, "Last 30 days"), (90, "Last 90 days"), (None, "All games"))     # None = every game loaded (2026-10-09, was 365 days)


def _periods(by_name, games=None, solo=False):
    """Last 30 / 90 days + all loaded games totals. by_name: {gamertag: [rows]}; games: one start time per game (squad: games together).
    Windows longer than the loaded history are marked partial (we only hold the most recent games per player)."""
    now = time.time()
    starts = [r["started_at"] for rs in by_name.values() for r in rs]
    if not starts:
        return None
    since = min(starts)
    out = []
    for days, label in PERIODS:
        cut = now - days * 86400 if days else 0
        rows = [(n, analytics._agg([r for r in rs if r["started_at"] >= cut])) for n, rs in by_name.items()]
        rows = [(n, a) for n, a in rows if a.get("games")]
        rows.sort(key=lambda x: -(x[1].get("sc_pct") if x[1].get("sc_pct") is not None else -1))
        n_games = len([t for t in (games if games is not None else starts) if t >= cut])
        out.append({"label": label, "rows": rows, "games": n_games, "all": not days,
                    "partial": bool(days) and since > cut + 86400})     # dates are rendered by the template's dt filter (one time zone)
    note = ("Every game loaded for this player" if solo else "Games played together") + " · sorted by score share"
    return {"tables": out, "since": since, "solo": solo, "note": note}


PREGAME_S = 15 * 60      # a game that started up to 15 min before the stream went live still counts as "tonight"


RANK_TIERS = ((1500, "Onyx"), (1200, "Diamond"), (900, "Platinum"), (600, "Gold"), (300, "Silver"), (0, "Bronze"))


def _tier(csr):
    return next((name for floor, name in RANK_TIERS if csr is not None and csr >= floor), None)


def _tonight(main, ids, since, stream_start):
    """One card of the live panel: games on these accounts since `since`, plus lobby read, strip, milestones, best plays."""
    ph = ",".join("?" * len(ids))
    rows = [dict(r) for r in db.q(f"SELECT * FROM matches WHERE player_id IN ({ph}) AND started_at>=? AND COALESCE(duration_s, 999)>={analytics.MIN_GAME_S} ORDER BY started_at DESC", *ids, since)]
    seen = set()
    rows = [r for r in rows if not (r["match_id"] in seen or seen.add(r["match_id"]))]
    for r in rows:
        r["map"], r["mode"] = analytics.clean_map(r["map"]), analytics.clean_mode(r["mode"])
        analytics.derive(r)
    x = {"p": main, "games": len(rows), "a": analytics._agg(rows) if rows else {}, "last": rows[0] if rows else None,
         "pips": [r["outcome"].lower() for r in reversed(rows)], "strip": [], "best": [], "milestones": [], "lobby": None}
    if not rows:
        return x
    last = rows[0]
    x["ended_ago"] = int(time.time() - last["started_at"] - (last["duration_s"] or 0))
    x["csr"] = x["a"].get("csr_net")
    # lobby read: how tonight's lobbies have gone (Halo only publishes MMR after a game ends, so this is never "next game")
    edges = [r for r in rows if r.get("mmr_edge") is not None and r["outcome"] in ("Win", "Loss")]
    if edges:
        rec = lambda rs: f"{sum(r['outcome'] == 'Win' for r in rs)}-{sum(r['outcome'] == 'Loss' for r in rs)}" if rs else None
        x["lobby"] = {"edge": round(sum(r["mmr_edge"] for r in edges) / len(edges)),
                      "fav": rec([r for r in edges if r["mmr_edge"] > 25]), "dog": rec([r for r in edges if r["mmr_edge"] < -25]),
                      "even": rec([r for r in edges if -25 <= r["mmr_edge"] <= 25])}
    # best play per game + the night's best plays (auto clips from the film)
    mids = [r["match_id"] for r in rows]
    mph = ",".join("?" * len(mids))
    mo = [dict(m) for m in db.q(f"SELECT * FROM moments WHERE player_id IN ({ph}) AND match_id IN ({mph}) ORDER BY score DESC", *ids, *mids)]
    best_by = {}
    for m in mo:
        best_by.setdefault(m["match_id"], m)
    x["best"] = mo[:3]
    slug_of = {r["id"]: r["slug"] for r in db.q(f"SELECT id, slug FROM players WHERE id IN ({ph})", *ids)}
    for m in x["best"]:
        g = next(r for r in rows if r["match_id"] == m["match_id"])
        m.update(map=g["map"], mode=g["mode"], outcome=g["outcome"], slug=slug_of.get(m["player_id"], main["slug"]))
    # the strip: each game placed along the broadcast (seconds from stream start; pre-stream games sit slightly left of 0)
    for r in reversed(rows):
        bm = best_by.get(r["match_id"])
        x["strip"].append({"t": r["started_at"] - stream_start, "dur": r["duration_s"] or 600, "outcome": r["outcome"], "match_id": r["match_id"],
                           "label": f"{r['map'] or '?'} · {r['mode'] or ''} · {r['outcome']} · {r['kills']}/{r['deaths']}/{r['assists']}",
                           "best": {"label": bm["label"], "t": bm["t_ms"] / 1000, "score": bm["score"]} if bm else None})
    # milestones: only true, specific statements
    ms = x["milestones"]
    if x["csr"] is not None and abs(x["csr"]) >= 20:
        ms.append(("up" if x["csr"] > 0 else "down", f"{x['csr']:+} CSR tonight"))
    ranked = [r for r in reversed(rows) if r.get("pre_csr") and r.get("post_csr")]
    if ranked and _tier(ranked[0]["pre_csr"]) != _tier(ranked[-1]["post_csr"]):
        up = ranked[-1]["post_csr"] > ranked[0]["pre_csr"]
        ms.append(("up" if up else "down", f"{'Reached' if up else 'Dropped to'} {_tier(ranked[-1]['post_csr'])} ({ranked[-1]['post_csr']})"))
    run = 0
    for r in rows:                      # newest first: current streak
        if r["outcome"] != rows[0]["outcome"] or r["outcome"] not in ("Win", "Loss"):
            break
        run += 1
    if run >= 3:
        ms.append(("up" if rows[0]["outcome"] == "Win" else "down", f"{run}-game {'win' if rows[0]['outcome'] == 'Win' else 'losing'} streak"))
    top_k = max(rows, key=lambda r: r["kills"] or 0)
    prev_k = db.q1(f"SELECT MAX(kills) k FROM matches WHERE player_id IN ({ph}) AND started_at<?", *ids, since)["k"]
    if prev_k is not None and (top_k["kills"] or 0) > prev_k:
        ms.append(("up", f"Most kills in a game on record: {top_k['kills']} ({top_k['map']})"))
    dpm = [r for r in rows if r.get("dmg_pm")]
    if dpm:
        top_d = max(dpm, key=lambda r: r["dmg_pm"])
        prev_d = db.q1(f"SELECT MAX(damage_dealt*60.0/duration_s) d FROM matches WHERE player_id IN ({ph}) AND duration_s>=60 "
                       f"AND started_at BETWEEN ? AND ?", *ids, since - 30 * 86400, since)["d"]
        if prev_d is not None and top_d["dmg_pm"] > prev_d:
            ms.append(("up", f"Best damage/min in 30 days: {top_d['dmg_pm']} ({top_d['map']})"))
    if x["best"] and x["best"][0]["score"] >= 80:
        ms.append(("up", f"Highlight of the night: {x['best'][0]['label']}"))
    return x


def _onair(groups, stream, channel):
    """Live panel: the broadcast (title, game, uptime, viewers), what it has streamed so far (streamlog: Halo vs other
    categories), and one 'Tonight' card per player (alts folded in). groups: [(main player, [player ids incl. alts])].
    Halo publishes a game only when it ends, so 'no games yet' is normal for the first ~15 min of Halo."""
    if not stream:
        return None
    import streamlog
    now = time.time()
    start = stream.get("started") or now
    since = start - PREGAME_S
    segs = []
    if channel and channel in streamlog.channels():
        try:
            streamlog.record(channel, stream, now)
            segs = streamlog.segments(channel, start, now)
        except Exception:
            segs = []
    if not segs:                         # not logged yet: all we know is the current category
        segs = [{"game": stream.get("game") or "Unknown", "halo": bool(stream.get("halo")), "start": start, "end": now, "guess": True}]
    halo_s = int(sum(g["end"] - g["start"] for g in segs if g["halo"]))
    cur = segs[-1]
    per = [_tonight(main, ids, since, start) for main, ids in groups]
    up = int(now - start)
    span = max([up] + [g["t"] + g["dur"] for x in per for g in x["strip"]] + [60])
    lo = min([0] + [g["t"] for x in per for g in x["strip"]])
    for g in segs:
        g["left"] = round((g["start"] - start - lo) / (span - lo) * 100, 2)
        g["width"] = round(max(0.5, (g["end"] - g["start"]) / (span - lo) * 100), 2)
        g["from"], g["to"] = int(g["start"] - start), int(g["end"] - start)
    return {"stream": stream, "channel": channel, "uptime": up, "since": since, "per": per, "span": span - lo, "lo": lo,
            "segs": segs, "halo_s": halo_s, "switched": len([g for g in segs if not g.get("unknown")]) > 1,
            "now_game": cur["game"], "now_since": int(now - cur["start"]),
            "quiet": halo_s >= PREGAME_S and not any(x["games"] for x in per)}


def _alts(main_id):
    """Admin-linked second accounts of a player (games fold into the main profile and its live panel)."""
    return [dict(r) for r in db.q("SELECT p.* FROM alts a JOIN players p ON p.id=a.alt_id WHERE a.main_id=? ORDER BY p.gamertag", main_id)
            if not _blocked(r["slug"])]


def _hub_board(slugs):
    """Analysis tab: the former live dashboard's data and helpers."""
    b = _board_data(slugs)
    return {"b": b, "explanations": analysis_view.explanations(b), "kinds": analytics.KINDS}


@app.route("/p/<slug>")
def profile(slug):
    p = _player(slug)
    db.run("UPDATE players SET views=views+1, last_view=? WHERE id=? AND (last_view IS NULL OR last_view<?)", time.time(), p["id"],time.time()-60)
    kind = _kind()
    alts = _alts(p["id"])
    data = analytics.profile(p["id"], kind, tuple(a["id"] for a in alts))
    if not data["rows"] and "kind" not in request.args:       # no ranked games (casual players): show everything instead of nothing
        kind = "all"
        data = analytics.profile(p["id"], kind, tuple(a["id"] for a in alts))
    g.kind_used = kind
    data["s_idx"] = _sess_idx(data["sessions"])
    if data["sessions"]:
        data["latest_session"] = data["sessions"][data["s_idx"]]
    if p["sync_state"] == "private" and time.time() - (p["last_synced"] or 0) > 3600:
        worker.enqueue(p["id"])                       # privacy settings can change: re-check hourly on view
    if p["sync_state"] in ("ready", "error") and (
            worker.stale(p, active=bool(data["live"] and data["live"]["active"])) or (data["clips_pending"] and time.time() - (p["last_synced"] or 0) > 45)):
        worker.enqueue(p["id"])
    tw = _channel_for(p) if twitch.enabled() else None
    u = None
    vods, clips = [], []
    if tw:
        u = _cached("uid", tw, 3600, lambda: twitch.lookup_user(tw))
        if u:
            vods = (_cached("vods", u["id"], 300, lambda: twitch.recent_videos(u["id"])) or [])
            clips = _cached("clips", u["id"], 300, lambda: twitch.recent_clips(u["id"])) or []
        else:
            tw = None
    onair = _onair([(p, [p["id"]] + [a["id"] for a in alts])], _cached("stream", u["id"], 60, lambda: twitch.stream(u["id"])), tw) if tw and u else None
    for r in data["rows"]:
        r["vod"] = twitch.vod_link(vods, r["started_at"], r["duration_s"]) if vods else None
    data["vod_games"] = [r for r in data["rows"] if r["vod"]][:40]
    need = [r["match_id"] for r in data["rows"] if r["vod"] and not r.get("film_state")]
    if need and p["sync_state"] == "ready":
        worker.enqueue_film(p["id"], need)
        data["clips_pending"] = data["clips_pending"] or len(need)
    elif vods:
        _queue_vod_films(p, vods)       # nothing new on the page: work through older covered games (archived nights)
    for mo in data["moments"]:            # clips already carry their own lead-in: no extra offset
        mo["vod"] = twitch.vod_link(vods, mo["at"], mo["dur_s"], lead=0) if vods else None
        if mo["vod"]:
            _tag_source(mo, vods, u if tw else None)
    data["moments"] = [mo for mo in data["moments"] if mo["vod"]][:12]     # only clips you can actually watch
    psrc, plabel, pcfg = _player_src(tw, u if tw else None, vods, p["id"])
    s = data["latest_session"]
    og = {"image": request.host_url + f"og/p/{p['slug']}.png", "title": f"{p['gamertag']} — Clutchtape",
          "desc": (f"Last session {s['record']} ({s['win_pct']}% wins, KDA {s['kda']})"
                   + (f" · {data['csr_now']} rating" if data["csr_now"] else "")
                   + (f" · {len(data['moments'])} auto clips" if data["moments"] else "")) if s else "Halo Infinite stats, auto clips and VOD-linked matches."}
    vm = vod_matches(p["id"], vods) if vods else {}
    _start_at_latest_match(pcfg, vm)
    comparison = session_review.comparison(data['sessions'], data['s_idx'], 'recent' if request.args.get('compare') == 'recent' else 'previous')
    tab = _tab()
    extra = _hub_board(p["slug"]) if tab == "analysis" else {}
    return render_template("profile.html", session_picks=session_watch.for_sessions(data["sessions"], [p["id"] for p in [p] + alts], vm) if tab == "sessions" else {}, watch_cues=session_watch.for_matches(s["matches"] if s else [], [p["id"]] + [a["id"] for a in alts]) if tab == "latest" else {}, tab=tab, onair=onair, alts=alts, kpis=_kpis(s["matches"]) if s else [], adv=_adv_kpis({p["gamertag"]: s["matches"]}) if s else [], sess_agg=analytics._agg(s["matches"]) if s else None, periods=_periods({p["gamertag"]: data["rows"]}, solo=True) if tab == "records" else None, **extra, comparison=comparison, recap_matches=session_review.recap_matches(s['matches'] if s else []), recap_names=[p['gamertag']], pcfg=pcfg, vm=vm, og=og, p=p, d=data, clips=clips, vods=vods, tw=tw, psrc=psrc, plabel=plabel,
                           host=request.host.split(":")[0])


@app.route("/api/live/<slugs>")
def live_api(slugs):
    """Live 'tonight so far' numbers for one player or a squad; polled every 30s by the page. Also keeps syncs flowing."""
    names = list(dict.fromkeys(s for s in slugs.lower().split(",") if s))[:MAX_SQUAD]
    out = []
    for s in names:
        if _blocked(s):continue
        p = db.q1("SELECT * FROM players WHERE slug=?", s)
        if not p:
            continue
        ids = [p["id"]] + [a["id"] for a in _alts(p["id"])]
        rows = [dict(r) for r in db.q(f"SELECT * FROM matches WHERE player_id IN ({','.join('?' * len(ids))}) AND started_at>? AND COALESCE(duration_s, 999)>={analytics.MIN_GAME_S} ORDER BY started_at DESC",
                                      *ids, time.time() - 12 * 3600)]
        for a in _alts(p["id"]):
            if a["sync_state"] in ("ready", "error") and worker.stale(a, active=True):
                worker.enqueue(a["id"])
        for r in rows:
            r["map"], r["mode"] = analytics.clean_map(r["map"]), analytics.clean_mode(r["mode"])
            analytics.derive(r)
        lv = analytics.live_summary(rows) if rows else None
        if p["sync_state"] in ("ready", "error") and worker.stale(p, active=True):
            worker.enqueue(p["id"])
        out.append({"slug": s, "gamertag": p["gamertag"], "live": lv, "syncing": p["sync_state"] in ("queued", "syncing"),
                    "updated": p["last_synced"]})
    resp = jsonify(players=out, now=time.time())
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/p/<slug>/status")
def status(slug):
    p = _player(slug)
    return jsonify(state=p["sync_state"], done=p["matches_done"], total=p["matches_total"], error=("Halo sync is delayed. Your saved results remain available." if p["sync_error"] else None),
                   place=worker.position(p["id"]))


def vod_matches(player_id, vods):
    """{video id: [[match_id, film_start_s_into_vod, duration_s, label]]} for filmed games that fall inside each saved broadcast."""
    out = {}
    if not vods:
        return out
    lo = min(v["start"] for v in vods)
    rows = db.q("SELECT m.match_id, m.film_t0, m.duration_s, m.map, m.mode, m.outcome FROM matches m "
                "JOIN filmed f ON f.match_id=m.match_id WHERE m.player_id=? AND m.film_t0>=?", player_id, lo)
    for v in vods:
        for r in rows:
            if v["start"] <= r["film_t0"] <= v["start"] + v["dur_s"]:
                label = " · ".join(x for x in (analytics.clean_map(r["map"]), analytics.clean_mode(r["mode"]), r["outcome"]) if x)
                out.setdefault(str(v["id"]), []).append([r["match_id"], round(r["film_t0"] - v["start"], 1), r["duration_s"] or 0, label])
    return out


@app.route("/api/match/<mid>/events")
def match_events(mid):
    """Kill feed for one match from its Theater film: kills paired with the death at the same millisecond, plus medals."""
    if not re.fullmatch(r"[0-9a-f-]{36}", mid) or not db.q1("SELECT 1 FROM filmed WHERE match_id=?", mid):
        return jsonify(e=[]), 404
    import match_detail
    match_detail.known(mid)
    rows = [r for r in db.q("SELECT t_ms, gt, k, medal, xuid FROM events WHERE match_id=? ORDER BY t_ms", mid)
            if not _blocked(r['gt']) and not _blocked(r['xuid'])]
    deaths = {}
    for r in rows:
        if r["k"] == "death":
            deaths.setdefault(r["t_ms"], []).append(r)
    used, out = set(), []
    for r in rows:
        if r["k"] == "kill":
            vic = next((d for d in deaths.get(r["t_ms"], []) if d["xuid"] != r["xuid"] and id(d) not in used), None)
            if vic:
                used.add(id(vic))
            out.append(["k", r["t_ms"], r["gt"], vic["gt"] if vic else None])
        elif r["k"] == "medal" and r["medal"]:
            out.append(["m", r["t_ms"], r["gt"], r["medal"]])
        elif r["k"] == "mode":
            out.append(["o", r["t_ms"], r["gt"], r["medal"]])
    for r in rows:
        if r["k"] == "death" and id(r) not in used:
            out.append(["d", r["t_ms"], None, r["gt"]])
    out.sort(key=lambda x: x[1])
    clips = []
    for row in db.q("SELECT mo.t_ms,mo.dur_s,mo.label,mo.score,p.gamertag,p.slug,p.xuid FROM moments mo JOIN players p ON p.id=mo.player_id WHERE mo.match_id=? ORDER BY mo.score DESC", mid):
        if not any(_blocked(row[k]) for k in ('gamertag','slug','xuid')):
            clips.append(dict(t=row['t_ms'], duration=row['dur_s'], label=row['label'], player=row['gamertag']))
    resp = jsonify(e=out, clips=clips)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@app.route("/api/clientlog", methods=["POST"])
def clientlog():
    # Legacy clients may still send diagnostics; never retain their player names or payloads.
    return "", 204


@app.route("/archive/file/<int:vid>")
@app.route("/archive/videos/<int:vid>")
def archive_file(vid):
    """An archived broadcast (archive.py) as a seekable MP4 — only ids the archive index knows (allowed channels)."""
    from flask import send_file
    path = archive.file_for(vid)
    if not path or not os.path.isfile(path):
        abort(404)
    if request.method=='GET' and not capacity.archive_streams.acquire(blocking=False):return busy_response()
    try:
        resp = send_file(path, mimetype="video/mp4", conditional=True, max_age=86400)
        if request.method=='GET':
            from werkzeug.wsgi import ClosingIterator
            released=[False]
            def release_stream():
                if not released[0]:
                    released[0]=True;capacity.archive_streams.release()
            resp.response=ClosingIterator(resp.response,[release_stream])
    except BaseException:
        if request.method=='GET':capacity.archive_streams.release()
        raise
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp


@app.route("/og/home.png")
def og_home():
    import ogcard
    png = _cached("og", "home", 900, ogcard.home_card)
    resp = Response(png, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=900"
    return resp


@app.route("/og/p/<slug>.png")
def og_player(slug):
    import ogcard
    p = _player(slug)

    def build():
        d = analytics.profile(p["id"], "ranked")
        tw = None
        for spec in FEATURED_SPEC:
            gt, _, login = spec.partition("|")
            if gt.strip().lower() == p["gamertag"].lower() and login:
                tw = login
        i = dashboard.select_session(d["sessions"], skip_unfinished=True) if d["sessions"] else None
        return ogcard.player_card(p["gamertag"], d["sessions"][i] if i is not None else d["latest_session"], d["csr_now"], d["all"].get("kda"), d["all"].get("games", 0), tw)
    png = _cached("og", "p:" + slug, 900, build)
    resp = Response(png, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=900"
    return resp


@app.route("/og/squad/<slugs>.png")
def og_squad(slugs):
    import ogcard
    names = list(dict.fromkeys(s for s in slugs.lower().split(",") if s))[:MAX_SQUAD]
    ps = [_player(s) for s in names]

    def build():
        d = analytics.squad([p["id"] for p in ps], "ranked")
        if not d["games"]:
            d = analytics.squad([p["id"] for p in ps], "all")
        top = (d["teamwork"]["good"] or [{}])[0].get("label") or ((d["moments"] or [{}])[0].get("label"))
        night = {"record": d["night_rec"], "matches": d["night"]} if d["night"] else None
        return ogcard.squad_card([p["gamertag"] for p in ps], d["rec"], d["games"], d["win_pct"], night, top)
    png = _cached("og", "s:" + ",".join(names), 900, build)
    resp = Response(png, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=900"
    return resp


@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /api/\nDisallow: /admin\n", mimetype="text/plain")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/healthz")
def healthz():
    db.q1("SELECT 1")
    return "ok"


# ------------------------------------------------------------------ admin: connect the shared Xbox login
def _is_admin():
    return (bool(ADMIN_PASSWORD) and session.get("admin") is True
            and 0 <= time.time()-session.get("admin_at",0) < 3600
            and hmac.compare_digest(session.get("admin_version",""), hmac.new(app.secret_key.encode() if isinstance(app.secret_key,str) else app.secret_key, ADMIN_PASSWORD.encode(), "sha256").hexdigest()))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and request.form.get("action") == "login":
        check_csrf()
        if not _admin_limits.allow("ip:"+client_ip(),8,900) or not _admin_limits.allow("global",100,900):
            abort(429)
        if ADMIN_PASSWORD and hmac.compare_digest(request.form.get("password", "").encode(), ADMIN_PASSWORD.encode()):
            session.clear()
            session["admin"] = True
            session["admin_at"] = time.time()
            session["admin_version"] = hmac.new(app.secret_key.encode() if isinstance(app.secret_key,str) else app.secret_key, ADMIN_PASSWORD.encode(), "sha256").hexdigest()
        return redirect(url_for("admin"))
    if not _is_admin():
        return render_template("admin.html", authed=False, msg=None)
    msg = request.args.get("msg")
    return render_template("admin.html", authed=True, msg=msg, xbox=xbox.status(),
                           ops=__import__('maintenance').status(),
                           creds=api_config.credentials_configured(),
                           authorize_url=api_config.build_authorize_url() if api_config.credentials_configured() else None,
                           redirect_uri=api_config.get_redirect_uri(),
                           players=db.q("SELECT gamertag, slug, sync_state, matches_done, last_synced, views FROM players "
                                        "ORDER BY created_at DESC LIMIT 50"),
                           alt_links=db.q("SELECT a.alt_id, m.gamertag main, m.slug main_slug, p.gamertag alt FROM alts a "
                                          "JOIN players m ON m.id=a.main_id JOIN players p ON p.id=a.alt_id ORDER BY m.gamertag"))


@app.route("/admin/delete", methods=["POST"])
def admin_delete():
    if not _is_admin():
        abort(403)
    check_csrf()
    p = db.q1("SELECT id, gamertag FROM players WHERE slug=?", (request.form.get("slug") or "").lower())
    if p:
        db.run("DELETE FROM matches WHERE player_id=?", p["id"])
        db.run("DELETE FROM moments WHERE player_id=?", p["id"])
        db.run("DELETE FROM players WHERE id=?", p["id"])
    return redirect(url_for("admin", msg=f"Removed {p['gamertag']}." if p else "Not found."))


def seed_featured():
    """Create the public example profiles (once the Xbox login works) so the demo always has something to show."""
    import threading
    def run():
        for _ in range(60):
            if xbox.status()["connected"]:
                break
            time.sleep(10)
        for spec in FEATURED_SPEC:
            gt, _, tw = spec.partition("|")
            if _blocked(gt):continue
            try:
                if db.q1("SELECT 1 FROM players WHERE lower(gamertag)=lower(?)", gt):
                    continue
                found = asyncio.run(ingest.resolve_gamertag(gt))
                if not found:
                    continue
                xuid, canon = found
                if _blocked(xuid) or _blocked(canon):continue
                slug = slugify(canon)
                cur = db.run("INSERT OR IGNORE INTO players(xuid,gamertag,slug,created_at) VALUES(?,?,?,?)",
                             xuid, canon, slug, time.time())
                if cur.lastrowid:
                    worker.enqueue(cur.lastrowid)
            except Exception:
                log.exception("seeding featured %s failed", gt)
    threading.Thread(target=run, name="seed-featured", daemon=True).start()


@app.route("/admin/xbox", methods=["POST"])
def admin_xbox():
    if not _is_admin():
        abort(403)
    check_csrf()
    act = request.form.get("action")
    try:
        if act == "creds":
            api_config.save_credentials(request.form["client_id"].strip(), request.form["client_secret"].strip())
            msg = "Azure credentials saved."
        elif act == "code":
            api_config.mint_tokens_from_code(request.form["redirect_url"])
            import time as _t
            db.kv_set("xbox_minted_at", _t.time())
            msg = "Xbox account connected."
        elif act == "remint":
            xbox.ensure_fresh(force=True)
            msg = "Tokens refreshed."
        else:
            msg = "Unknown action."
    except Exception as exc:
        log.exception("admin xbox action failed")
        msg = "Xbox connection failed. Check the server logs and try again."
    return redirect(url_for("admin", msg=msg))


@app.route("/admin/teammates/<slug>")
def admin_teammates(slug):
    """Admin helper: who does this player most often queue with? (used to pick a real squad example)"""
    if not _is_admin():
        abort(403)
    p = _player(slug)

    async def run():
        from collections import Counter
        cnt = Counter()
        async with ClientSession() as s:
            c = HaloInfiniteClient(session=s, requests_per_second=3, **xbox.client_args())
            hist = await (await c.stats.get_match_history(p["xuid"], start=0, count=25)).parse()
            for it in hist.results[:25]:
                ms = await (await c.stats.get_match_stats(str(it.match_id))).parse()
                me = next((x for x in ms.players if ingest.xuid_of(x.player_id) == p["xuid"]), None)
                if not me:
                    continue
                for x in ms.players:
                    xu = ingest.xuid_of(x.player_id)
                    if x.last_team_id == me.last_team_id and xu != p["xuid"] and str(x.player_id).startswith("xuid"):
                        cnt[xu] += 1
            top = cnt.most_common(8)
            names = {}
            if top:
                users = await (await c.profile.get_users_by_id([x for x, _ in top])).parse()
                names = {str(u.xuid): str(u.gamertag) for u in users}
            return [(names.get(x, x), n) for x, n in top]
    try:
        return jsonify(asyncio.run(run()))
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/admin/alts", methods=["POST"])
def admin_alts():
    """Admin: link (or unlink) a second account to a main player. Linking adds the alt as a tracked player if needed."""
    if not _is_admin():
        abort(403)
    check_csrf()
    main = db.q1("SELECT id, slug FROM players WHERE slug=? OR gamertag=? COLLATE NOCASE", (request.form.get("main") or "").strip().lower(),
                 (request.form.get("main") or "").strip())
    if not main:
        return redirect(url_for("admin", msg="Main player not found (use their gamertag or page slug)."))
    if request.form.get("unlink"):
        db.run("DELETE FROM alts WHERE alt_id=? AND main_id=?", int(request.form["unlink"]), main["id"])
        return redirect(url_for("admin", msg="Alt unlinked."))
    slug, _, err = _add_one(re.sub(r"\s+", " ", (request.form.get("alt") or "").strip()), "")
    if err or not slug:
        return redirect(url_for("admin", msg=err or "Alt gamertag not found."))
    alt = db.q1("SELECT id FROM players WHERE slug=?", slug)
    if alt["id"] == main["id"]:
        return redirect(url_for("admin", msg="That is the same account."))
    db.run("INSERT OR REPLACE INTO alts(alt_id, main_id, created) VALUES(?,?,?)", alt["id"], main["id"], time.time())
    return redirect(url_for("admin", msg=f"Linked {slug} as an alt of {main['slug']}."))


@app.route("/admin/add", methods=["POST"])
def admin_add():
    """Admin: add players by exact gamertag, no rate limit (used to seed demo squads)."""
    if not _is_admin():
        abort(403)
    check_csrf()
    out = []
    for g in request.form.getlist("gamertag"):
        slug, _, err = _add_one(re.sub(r"\s+", " ", g.strip()), "")
        out.append(slug or err)
    return jsonify(out)

# ------------------------------------------------------------------ session companion
@app.route('/live')
def live_home():
    """The old dashboard picker: players and squads now open from the home page."""
    return redirect(url_for('index'), code=301)


def _board_players(slugs):
    names=list(dict.fromkeys(slugs.lower().split(',')))
    if not 1 <= len(names) <= MAX_SQUAD or any(not re.fullmatch(r'[a-z0-9-]+',x) for x in names): abort(404)
    return [dict(_player(x)) for x in names]


def _board_data(slugs):
    ps=_board_players(slugs)
    kind=_kind()
    raw=request.args.get('days','30');days=int(raw) if raw in ('30','90') else 0 if raw=='all' else 30
    scope=request.args.get('scope') or ('session' if request.args.get('session') or request.args.get('match') else '30');scope=scope if scope in ('session','30','90','all') else '30'   # Analysis defaults to the last 30 days (2026-10-09)
    baseline=request.args.get('compare','previous');baseline=baseline if baseline in ('previous','recent','month') else 'previous'
    playlist=request.args.get('playlist','')[:160]
    data=dashboard.load(ps,kind,request.args.get('session'),request.args.get('match'),days,scope,playlist,baseline)
    if not data.get('matches') and not request.args.get('kind'):    # no ranked games in range: fall back to everything
        kind='all';data=dashboard.load(ps,kind,request.args.get('session'),request.args.get('match'),days,scope,playlist,baseline)
    g.kind_used=kind
    channels={}
    if len(ps)==1:
        ch=_channel_for(ps[0])
        if ch: channels[ps[0]['id']]=ch
    else:
        supplied=_tw_map()
        for p in ps:
            ch=twitch.parse_login(supplied.get(p['slug'],''))
            if not ch:
                ch=next((twitch.parse_login(s.partition('|')[2]) for s in FEATURED_SPEC if s.partition('|')[0].strip().lower()==p['gamertag'].lower()),None)
            if ch: channels[p['id']]=ch
    vods={}
    if twitch.enabled():
        for pid,ch in channels.items():
            u=_cached('uid',ch,3600,lambda ch=ch:twitch.lookup_user(ch))
            if u: vods[pid]=(_cached('vods',u['id'],300,lambda u=u:twitch.recent_videos(u['id'])) or [])
    for m in data['matches']:
        m['videos']=[]
        for p in ps:
            if p['id'] not in (m.get('members') or {m['player_id']:m}): continue
            v=twitch.vod_link(vods.get(p['id'],[]),m.get('film_t0') or m['started_at'],m['duration_s'])
            if v: m['videos'].append(dict(name=p['gamertag'],url=v))
    data['coverage']['video']=sum(bool(m['videos']) for m in data['matches'])
    for moment in data['moments']:
        m=next(m for m in data['matches'] if m['match_id']==moment['match'])
        moment['video']=next((v for p in ps if (v:=twitch.vod_link(vods.get(p['id'],[]),(m.get('film_t0') or m['started_at'])+moment['at'],moment['duration'],lead=0))),None)
    if any(request.args.get(k) for k in ('scope','playlist','compare')):
        def preserve(url):
            u=urlsplit(url);q=dict(parse_qsl(u.query))
            q.update({k:request.args[k] for k in ('scope','playlist','compare') if request.args.get(k)})
            if 'session' in q and url in [s['url'] for s in data['sessions']]:q['scope']='session'
            return urlunsplit(('', '', u.path, urlencode(q), u.fragment))
        data['stable_url']=preserve(data['stable_url'])
        for group in ('sessions','moments','records','maps'):
            for item in data[group]: item['url']=preserve(item['url'])
        for item in data['matches']: item['review_url']=preserve(item['review_url'])
    data['report_query']=urlencode(dict(kind=kind,session=data['anchor'] or '',scope=scope,playlist=playlist,compare=baseline))
    data['version']=dashboard.version(ps)
    return data


def _hub_url(slugs, **args):
    """One page per player or squad (/p, /squad); every old /live link lands on the matching tab."""
    names = [x for x in dict.fromkeys(slugs.lower().split(",")) if x]
    if not 1 <= len(names) <= MAX_SQUAD or any(not re.fullmatch(r"[a-z0-9-]+", x) for x in names):
        abort(404)
    return url_for("profile", slug=names[0], **args) if len(names) == 1 else url_for("squad", slugs=",".join(names), **args)


@app.route('/live/<slugs>')
def live_board(slugs):
    """Former stats dashboard, now the Analysis tab (a recap deep link opens there too). Filters carry over."""
    args = {k: v for k, v in request.args.items() if k != "tab"}
    return redirect(_hub_url(slugs, tab="analysis", **args), code=301)


@app.route('/api/companion/<slugs>')
def companion_api(slugs):
    ps=_board_players(slugs)
    for p in ps:
        if p['sync_state'] in ('ready','error') and worker.stale(p,active=True): worker.enqueue(p['id'])
    version=dashboard.version(ps)
    if request.args.get('version')==version:
        return jsonify(version=version,changed=False,syncing=any(worker.position(p['id']) for p in ps))
    b=_board_data(slugs)
    return jsonify(version=version,changed=True,latest=({"id":b['latest']['match_id'],"time":b['latest']['started_at'],"outcome":b['latest']['outcome'],"map":b['latest']['map']} if b['latest'] else None),html=render_template('_board_top.html',b=b),syncing=any(worker.position(p['id']) for p in ps))


@app.route('/report/<slugs>.png')
def session_report(slugs):
    b=_board_data(slugs)
    if not b['selected']: abort(404)
    import ogcard
    resp=Response(ogcard.session_card(b),mimetype='image/png')
    if request.args.get('download'): resp.headers['Content-Disposition']='attachment; filename="clutchtape-session.png"'
    resp.headers['Cache-Control']='no-store'
    return resp


@app.route('/live/open',methods=['POST'])
def live_open():
    check_csrf()
    names=list(dict.fromkeys(x.strip().lower() for x in request.form.getlist('player') if re.fullmatch(r'[a-z0-9-]+',x)))
    if not 1<=len(names)<=4: return redirect(url_for('live_home',error='Choose one to four players.'))
    return redirect(_hub_url(','.join(names)))

# ------------------------------------------------------------------ close games to watch
import close_games

CLOSE_DAYS = 45


def _close_games():
    """Ranked close games across the showcase pros (close_games.py has the formula). One entry per match, with
    every tracked pro's point of view: a Twitch/archive timestamp when a broadcast covers it, else the match recap."""
    pros = [g.strip() for g in os.getenv("PRO_GAMERTAGS", ",".join(close_games.PRO_GAMERTAGS)).split(",") if g.strip()]
    pros_l = {g.lower() for g in pros}
    tracked = [p for p in db.q("SELECT id, slug, gamertag FROM players") if p["gamertag"].lower() in pros_l
               and not privacy.blocked(p["slug"]) and not privacy.private(p["slug"])]      # cache is shared by every host
    if not tracked:
        return []
    chans = {s.partition("|")[0].strip().lower(): twitch.parse_login(s.partition("|")[2]) for s in FEATURED_SPEC if "|" in s}
    vods = {}
    for p in tracked:
        login = chans.get(p["gamertag"].lower())
        u = login and twitch.enabled() and _cached("uid", login, 3600, lambda login=login: twitch.lookup_user(login))
        if u:
            vods[p["id"]] = (login, (_cached("vods", u["id"], 300, lambda u=u: twitch.recent_videos(u["id"])) or []))
    ids = [p["id"] for p in tracked]
    by_id = {p["id"]: p for p in tracked}
    rows = db.q(f"SELECT m.*, (SELECT MAX(score) FROM moments mo WHERE mo.match_id=m.match_id) AS best FROM matches m "
                f"WHERE m.player_id IN ({','.join('?' * len(ids))}) AND m.started_at>? AND m.outcome IN ('Win','Loss') "
                f"AND m.team_score IS NOT NULL AND COALESCE(m.duration_s, 999)>={analytics.MIN_GAME_S} ORDER BY m.started_at DESC", *ids, time.time() - CLOSE_DAYS * 86400)
    games = {}
    for r in rows:
        if close_games.family(r["mode"]) is None:
            continue
        g = games.setdefault(r["match_id"], {"row": r, "povs": [], "teams": set(), "best": r["best"] or 0})
        g["teams"].add(r["team_id"])
        p = by_id[r["player_id"]]
        pov = {"gamertag": p["gamertag"], "slug": p["slug"], "recap": f"/match/{r['match_id']}?player={p['slug']}"}
        login, v = vods.get(p["id"], (None, None))
        link = twitch.vod_link(v, r["started_at"], r["duration_s"]) if v else None
        mm = re.search(r"videos/(\d+)\?t=([0-9hms]+)", link or "")
        if mm:
            pov["watch"] = f"/p/{p['slug']}?session={r['match_id']}&vod={mm.group(1)}@{mm.group(2)}"
        g["povs"].append(pov)
    lobby = {}
    if games:
        mids = list(games)
        for i in range(0, len(mids), 400):
            chunk = mids[i:i + 400]
            for e in db.q(f"SELECT DISTINCT match_id, lower(gt) AS gt FROM events WHERE match_id IN ({','.join('?' * len(chunk))}) "
                          f"AND gt IS NOT NULL", *chunk):
                if e["gt"] in pros_l:
                    lobby.setdefault(e["match_id"], set()).add(e["gt"])
    out = []
    for mid, g in games.items():
        r = dict(g["row"])
        pvp = len({t for t in g["teams"] if t is not None}) > 1 or len(lobby.get(mid, ())) >= 4
        sc = close_games.score(r, g["best"], pvp)
        if not sc:
            continue
        g["povs"].sort(key=lambda p: "watch" not in p)
        out.append({**sc, "match_id": mid, "map": analytics.clean_map(r["map"]), "mode": analytics.clean_mode(r["mode"]),
                    "scrim": r["playlist"] is None, "at": r["started_at"], "povs": g["povs"], "film_t0": r["film_t0"],
                    "watchable": any("watch" in p for p in g["povs"]), "pros_in_lobby": len(lobby.get(mid, ()))})
    out.sort(key=lambda x: (-x["rank"], -x["at"]))
    return {"games": out, "finishes": _clutch_finishes(out, games, vods, by_id)}


def _clutch_finishes(ranked, games, vods, by_id):
    """The last 30s of each filmed close game, ranked (close_games.finish). Watch links start 5s before the window."""
    filmed = [x for x in ranked if x["film_t0"]]
    evs = {}
    for i in range(0, len(filmed), 300):
        chunk = [x["match_id"] for x in filmed[i:i + 300]]
        q = ",".join("?" * len(chunk))
        for e in db.q(f"SELECT e.match_id, e.t_ms, e.k, e.gt, e.medal FROM events e JOIN (SELECT match_id, MAX(t_ms) AS mx FROM events "
                      f"WHERE match_id IN ({q}) GROUP BY match_id) z ON z.match_id=e.match_id AND e.t_ms>=z.mx-?", *chunk,
                      close_games.FINISH_WINDOW_MS):
            if privacy.private(e['gt']) or privacy.blocked(e['gt']):
                continue
            evs.setdefault(e["match_id"], []).append((e["t_ms"], e["k"], e["gt"], e["medal"]))
    out = []
    for x in filmed:
        f = close_games.finish(x, evs.get(x["match_id"]))
        if not f:
            continue
        povs = []
        for r in games[x["match_id"]]["povs"]:
            pov = {"gamertag": r["gamertag"], "slug": r["slug"], "recap": r["recap"]}
            pid = next(i for i, p in by_id.items() if p["slug"] == r["slug"])
            login, v = vods.get(pid, (None, None))
            link = twitch.vod_link(v, x["film_t0"] + f["start_ms"] / 1000, 40, lead=0) if v else None
            mm = re.search(r"videos/(\d+)\?t=([0-9hms]+)", link or "")
            if mm:
                pov["watch"] = f"/p/{r['slug']}?session={x['match_id']}&vod={mm.group(1)}@{mm.group(2)}"
            povs.append(pov)
        povs.sort(key=lambda p: "watch" not in p)
        out.append({**{k: x[k] for k in ("match_id", "map", "mode", "scrim", "at", "final", "family", "pros_in_lobby")},
                    **f, "game_rank": x["rank"], "povs": povs, "watchable": any("watch" in p for p in povs)})
    out.sort(key=lambda y: (-y["rank"], -y["at"]))
    return out


@app.route("/close")
def close_page():
    data = _cached("close", "all", 600, _close_games) or {}
    view = "finishes" if request.args.get("view") == "finishes" else "games"
    games = data.get(view) or []
    fam, kind, video = request.args.get("mode", ""), request.args.get("type", ""), request.args.get("video") == "1"
    shown = [x for x in games if (not fam or x["family"] == fam) and (kind != "scrim" or x["scrim"])
             and (kind != "mm" or not x["scrim"]) and (not video or x["watchable"])]
    og = {"title": "Close games to watch — Clutchtape", "desc": "Halo Infinite pro games decided by a kill, a cap or a few points, ranked."}
    return render_template("close.html", games=shown[:40], total=len(shown), fam=fam, kind=kind, video=video, og=og, view=view,
                           families=[("", "All"), ("slayer", "Slayer"), ("ctf", "CTF"), ("oddball", "Oddball"),
                                     ("koth", "King of the Hill"), ("strongholds", "Strongholds"), ("doubles", "Doubles")],
                           days=CLOSE_DAYS)


import growth
app.register_blueprint(growth.bp)
import rooms
rooms.install(app, check_csrf, client_ip)
import player_colors
player_colors.install(app, check_csrf, client_ip)
import data_rights
data_rights.install(app,check_csrf,_is_admin,client_ip)

import match_detail
app.register_blueprint(match_detail.bp)


@app.get('/admin/ops')
def operations():
    if not _is_admin():abort(403)
    import maintenance
    result=maintenance.status()
    result['cache']={'hits':capacity.stats.hits,'misses':capacity.stats.misses,'entries':len(capacity.stats.items),'estimated_bytes':capacity.stats.bytes}
    return jsonify(result)


@app.get('/readyz')
def readyz():
    import maintenance
    try:
        db.q1('SELECT 1');state=maintenance.status()
        heartbeat=db.kv_get('ops:heartbeat',{}).get('at',0)
        degraded=bool(state['alerts']) or time.time()-heartbeat>180
        return jsonify(status='degraded' if degraded else 'ready'),503 if degraded else 200
    except Exception:return jsonify(status='unavailable'),503


@app.post('/p/<slug>/refresh')
def retry_profile(slug):
    check_csrf();p=_player(slug)
    if not capacity.limiter.allow('refresh:'+str(p['id']),1,60):return busy_response(429)
    if not worker.enqueue(p['id'],reset=True):return busy_response(503)
    return redirect(url_for('profile',slug=p['slug']))


import alerts
import home_feed
app.register_blueprint(alerts.bp)

@app.get("/sw.js")
def service_worker():
    response = app.send_static_file("sw.js")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response
