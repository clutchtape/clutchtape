"""Twitch helpers (public data only, app-token auth). Used to validate a channel and to link matches to VODs."""
import calendar
import os
import re
import threading
import time
from urllib.parse import urlsplit

import requests

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
_tok = {"v": None, "exp": 0}
_lock = threading.Lock()
LOGIN_RE = re.compile(r"^[A-Za-z0-9_]{3,25}$")
HALO_INFINITE_GAME_ID = "506416"     # Twitch category id (helix/games?name=Halo Infinite, checked 2026-10-08)


def enabled():
    return bool(CLIENT_ID and CLIENT_SECRET)


def parse_login(raw):
    """Accept 'name', '@name', 'twitch.tv/name', 'https://www.twitch.tv/name/videos' -> 'name' (lowercase) or None."""
    s = (raw or "").strip()
    if not s:
        return None
    if "/" in s or ":" in s:
        try:
            url = urlsplit(s if "://" in s else "https://" + s)
            if url.scheme not in ("http", "https") or url.hostname not in ("twitch.tv", "www.twitch.tv", "m.twitch.tv"):
                return None
            if url.username or url.password or url.port:
                return None
            parts = url.path.strip("/").split("/")
            if len(parts) > 2 or (len(parts) == 2 and parts[1] not in ("videos", "clips", "about", "schedule")):
                return None
            s = parts[0]
        except ValueError:
            return None
    else:
        s = s.lstrip("@")
    if s.lower() in ("videos", "directory", "downloads", "settings", "subscriptions"):
        return None
    return s.lower() if LOGIN_RE.fullmatch(s) else None


def _token():
    with _lock:
        if _tok["v"] and time.time() < _tok["exp"] - 60:
            return _tok["v"]
        r = requests.post("https://id.twitch.tv/oauth2/token", timeout=10, data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "client_credentials"})
        r.raise_for_status()
        j = r.json()
        _tok.update(v=j["access_token"], exp=time.time() + int(j.get("expires_in", 3600)))
        return _tok["v"]


def _get(path, **params):
    r = requests.get("https://api.twitch.tv/helix/" + path, params=params, timeout=12,
                     headers={"Client-Id": CLIENT_ID, "Authorization": "Bearer " + _token()})
    r.raise_for_status()
    return r.json().get("data", [])


def lookup_user(login):
    if not enabled():
        return None
    d = _get("users", login=login)
    return d[0] if d else None


def is_live(user_id):
    if not enabled() or not user_id:
        return False
    return bool(_get("streams", user_id=user_id))


def stream_from(st):
    """Normalize one Helix /streams item."""
    from datetime import datetime
    try:
        started = datetime.fromisoformat(st["started_at"].replace("Z", "+00:00")).timestamp()
    except (KeyError, ValueError):
        started = None
    return {"title": st.get("title") or "", "game": st.get("game_name") or "", "game_id": st.get("game_id"),
            "halo": st.get("game_id") == HALO_INFINITE_GAME_ID, "started": started, "viewers": st.get("viewer_count")}


def stream(user_id):
    """The live broadcast right now: {title, game, game_id, halo, started (epoch), viewers}, or None when offline."""
    if not enabled() or not user_id:
        return None
    d = _get("streams", user_id=user_id)
    return stream_from(d[0]) if d else None


def parse_duration(s):
    """Twitch '3h12m5s' -> seconds."""
    m = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", s or "")
    h, mi, se = (int(x or 0) for x in m.groups()) if m else (0, 0, 0)
    return h * 3600 + mi * 60 + se


def recent_videos(user_id, n=40):
    """Past broadcasts as [{id, start (unix), dur_s, title, url, thumb}] newest first."""
    if not enabled() or not user_id:
        return []
    out = []
    for v in _get("videos", user_id=user_id, type="archive", first=min(n, 100)):
        try:
            start = calendar.timegm(time.strptime(v["created_at"], "%Y-%m-%dT%H:%M:%SZ"))   # UTC epoch, DST-proof
        except Exception:
            continue
        out.append({"id": v["id"], "start": start, "dur_s": parse_duration(v.get("duration")),
                    "title": v.get("title") or "", "url": v["url"],
                    "thumb": (v.get("thumbnail_url") or "").replace("%{width}", "320").replace("%{height}", "180")})
    return out


def recent_clips(user_id, n=12):
    """Top clips, Halo Infinite only: streamers clip other games too, and this is a Halo site."""
    if not enabled() or not user_id:
        return []
    return [{"id": c["id"], "title": c["title"], "url": c["url"], "views": c["view_count"],
             "thumb": c["thumbnail_url"], "created": c["created_at"], "dur": c["duration"]}
            for c in _get("clips", broadcaster_id=user_id, first=min(100, n * 3))
            if c.get("game_id") == HALO_INFINITE_GAME_ID][:n]


def clips_between(user_id, start, end):
    """Viewer clips of this channel made between two unix times (any game): [{id, created, title, url, dur}].
    Used when a channel doesn't save its broadcasts: a clip someone made right after a play can stand in for it."""
    if not enabled() or not user_id:
        return []
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
    out = []
    for c in _get("clips", broadcaster_id=user_id, started_at=iso(start), ended_at=iso(end), first=50):
        try:
            created = calendar.timegm(time.strptime(c["created_at"], "%Y-%m-%dT%H:%M:%SZ"))
        except Exception:
            continue
        out.append({"id": c["id"], "created": created, "title": c.get("title") or "", "url": c["url"], "dur": c.get("duration")})
    return out


def clip_for(clips, at, dur_s):
    """The viewer clip that most likely shows a play that started at `at`: made during it or up to 150s after it
    ended (people press Clip after the moment), closest to its end. None if nothing fits."""
    end = at + (dur_s or 0)
    fits = [c for c in clips if at <= c["created"] <= end + 150]
    return min(fits, key=lambda c: abs(c["created"] - end)) if fits else None


def vod_link(videos, match_start, duration_s, lead=5):
    """If a VOD covers this moment, return a timestamped URL into it (`lead` seconds early)."""
    for v in videos:
        # A verified local archive must cover the entire requested game/clip, not just its first 30s.
        required = max(1, duration_s or 0) if v.get("archive") else min(duration_s or 0, 30)
        tolerance = 0 if v.get("archive") else 30
        if v["start"] - tolerance <= match_start <= v["start"] + v["dur_s"] - required:
            off = max(0, int(match_start - v["start"]) - lead)
            h, rem = divmod(off, 3600)
            m, s = divmod(rem, 60)
            return f"{v['url']}?t={h}h{m}m{s}s"
    return None
