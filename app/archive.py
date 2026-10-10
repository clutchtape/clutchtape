"""Archived broadcasts: when Twitch deletes a VOD (~7 days on small channels), play the moment from MultiTwitch's
co-stream archive instead, so clips and Watch together don't silently vanish a week later.

Source of truth is MultiTwitch (configured archive directory): each session folder under the archive dir has a
manifest.json and per-channel `<channel>_<stamp>_mobile_720p60.mp4` (the browser-safe master; .mkv sources are not
served). The recording is the whole VOD, so second 0 = the broadcast start, which MultiTwitch's sessions.json records
per streamer (`streamers[].startedAt`). Only channels in ARCHIVE_CHANNELS are ever served (explicit operator allowlist);
coverage comes from the actual video duration measured by ffprobe, not the intended manifest duration.
Live recordings use their recording start; VOD downloads use the original broadcast start.

Archived "videos" get numeric ids >= ID_BASE so the existing `videos/<digits>?t=` link parsing and the players work
unchanged; static/archiveplayer.js plays ids >= ID_BASE in an HTML5 <video> instead of the Twitch embed.
Refresh trigger: MultiTwitch changes its archive layout (folder/manifest/mobile file naming or sessions.json shape).
"""
import calendar
import json
import logging
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import time
import zlib

log = logging.getLogger("clutchtape.archive")

ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", "/archive")
SESSIONS_FILE = os.getenv("ARCHIVE_SESSIONS_FILE", "/mt-data/sessions.json")
CHANNELS = {c.strip().lower() for c in os.getenv("ARCHIVE_CHANNELS", "").split(",") if c.strip()}
ID_BASE = 99_000_000_000
TTL_S = 600

_duration_cache = {}
_duration_lock = threading.Lock()
_lock = threading.Lock()
_cache = {"at": 0.0, "by_channel": {}, "by_id": {}}


def enabled():
    return bool(CHANNELS) and os.path.isdir(ARCHIVE_DIR)


def _epoch(iso):
    try:
        return calendar.timegm(time.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def _starts():
    """{(session_id, channel): broadcast start epoch} from MultiTwitch's sessions.json."""
    try:
        with open(SESSIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    sessions = data if isinstance(data, list) else (data.get("completed") or []) + list((data.get("active") or {}).values())
    out = {}
    for s in sessions:
        for st in s.get("streamers") or []:
            t = _epoch(st.get("startedAt"))
            if t and st.get("name"):
                out[(s.get("id"), st["name"].lower())] = t
    return out


def _duration(path):
    """Read the real video length; cache by size/mtime so replacements are re-probed."""
    try:
        stat = os.stat(path)
        fingerprint = (stat.st_size, stat.st_mtime_ns)
    except OSError:
        return None
    with _duration_lock:
        cached = _duration_cache.get(path)
        if cached and cached[0] == fingerprint and (cached[1] is not None or time.time() - cached[2] < 120):
            return cached[1]
    duration = None
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                 '-show_entries', 'stream=duration:format=duration', '-of', 'json', path],
                                capture_output=True, text=True, timeout=5, check=True)
        info = json.loads(result.stdout)
        streams = info.get('streams') or []
        if streams:  # An audio-only file is not playable match coverage.
            values = []
            for raw in (streams[0].get('duration'), info.get('format', {}).get('duration')):
                try:
                    value = float(raw)
                    if math.isfinite(value) and value > 0:
                        values.append(value)
                except (TypeError, ValueError):
                    pass
            duration = min(values) if values else None
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        log.warning('Could not verify archive video duration: %s', os.path.basename(path))
    with _duration_lock:
        _duration_cache[path] = (fingerprint, duration, time.time())
    return duration


def _build():
    by_channel, by_id = {}, {}
    if not enabled():
        return by_channel, by_id
    starts, candidates = _starts(), []
    root = os.path.realpath(ARCHIVE_DIR)
    for d in sorted(os.listdir(ARCHIVE_DIR)):
        folder = os.path.join(root, d)
        mpath = os.path.join(folder, 'manifest.json')
        if d.startswith('_') or not os.path.isfile(mpath):
            continue
        try:
            with open(mpath, encoding='utf-8') as f:
                man = json.load(f)
            if not isinstance(man, dict):
                continue
        except (OSError, ValueError):
            continue
        for ch in man.get('channels') or []:
            if not isinstance(ch, dict):
                continue
            name = str(ch.get('channel') or '').lower()
            # A downloaded VOD starts at broadcast time; a live recording may start hours later.
            start = (starts.get((man.get('sessionId'), name)) if man.get('source') in ('backfill', 'manual')
                     else _epoch(ch.get('startedAt')))
            if name not in CHANNELS or not start:
                continue
            stem = os.path.splitext(os.path.basename(ch.get('filePath') or ''))[0]
            mp4 = os.path.realpath(os.path.join(folder, f'{stem}_mobile_720p60.mp4'))
            if not mp4.startswith(root + os.sep) or not os.path.isfile(mp4):
                continue
            candidates.append((name, start, mp4, ch.get('title') or 'Archived broadcast'))
    # Probes inspect metadata only. Bound concurrency to avoid serial cold-start latency.
    with ThreadPoolExecutor(max_workers=4) as pool:
        durations = list(pool.map(_duration, [c[2] for c in candidates]))
    for (name, start, mp4, title), duration in zip(candidates, durations):
        if duration is None or duration < 60:
            continue  # Fail closed: unknown length and tiny download stubs cannot advertise coverage.
        vid = ID_BASE + zlib.crc32(os.path.relpath(mp4, root).encode()) % 999_999_999
        if vid in by_id and by_id[vid] != mp4:
            log.warning('Archive id collision; skipping %s', os.path.basename(mp4))
            continue
        v = {'id': str(vid), 'start': start, 'dur_s': duration, 'title': title,
             'url': f'/archive/videos/{vid}', 'thumb': '', 'archive': True}
        by_channel.setdefault(name, []).append(v)
        by_id[vid] = mp4
    for vids in by_channel.values():
        vids.sort(key=lambda v: -v['start'])
    return by_channel, by_id


def _index():
    with _lock:
        if time.time() - _cache["at"] > TTL_S:
            try:
                _cache["by_channel"], _cache["by_id"] = _build()
            except Exception:
                log.exception("archive index failed")
            _cache["at"] = time.time()
        return _cache["by_channel"], _cache["by_id"]


def videos_for(login):
    """Archived broadcasts for a Twitch login, newest first ([] if none / not an archived channel)."""
    if not login or login.lower() not in CHANNELS:
        return []
    return list(_index()[0].get(login.lower(), []))


def merge(twitch_videos, login):
    """Twitch's VODs first (they're the originals); archived copies only where Twitch no longer has the broadcast."""
    out = list(twitch_videos or [])
    for a in videos_for(login):
        mid = a["start"] + a["dur_s"] / 2
        if not any(v["start"] - 120 <= mid <= v["start"] + v["dur_s"] + 120 for v in out if not v.get("archive")):
            out.append(a)
    return out


def file_for(video_id):
    try:
        return _index()[1].get(int(video_id))
    except (TypeError, ValueError):
        return None


def is_archive_id(video_id):
    try:
        return int(str(video_id).lstrip("v")) >= ID_BASE
    except ValueError:
        return False
