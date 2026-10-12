"""What a player is doing in Halo right now — matchmaking, a custom game, the menus (2026-10-12).

Halo only publishes a game once it ends, so the stats can't say "in a scrim right now". Xbox Live presence can: the
title's rich-presence line ("Ranked Arena: Slayer on Recharge", "Custom Game", …) is what friends see on Xbox.
We mint an XSTS token for the xboxlive.com relying party from the stored user token (xbox.py keeps it fresh, every
40 min), ask userpresence.xboxlive.com for a batch of xuids, and sort the line into a few kinds. Players whose Xbox
privacy hides it simply come back without a Halo title — then we show nothing (never a guess).

Refresh trigger: if Halo's rich-presence wording changes, update KINDS."""
import logging
import re
import threading
import time

import requests

import xbox

log = logging.getLogger("clutchtape.presence")
HALO_TITLE = re.compile(r"halo infinite", re.I)
TTL_S = 30
# first match wins (most specific first)
KINDS = [("custom", re.compile(r"custom", re.I), "In a custom game"),
         ("ranked", re.compile(r"ranked", re.I), "Ranked"),
         ("firefight", re.compile(r"firefight", re.I), "Firefight"),
         ("forge", re.compile(r"forge", re.I), "Forge"),
         ("campaign", re.compile(r"campaign|zeta halo|mission", re.I), "Campaign"),
         ("training", re.compile(r"academy|training|bot ?boot|weapon drill", re.I), "Training"),
         ("matchmaking", re.compile(r"quick ?play|arena|big team|btb|social|husky|infection|fiesta|swat|slayer|ctf|oddball|strongholds|king of the hill|matchmak", re.I), "Matchmaking"),
         ("menu", re.compile(r"menu|lobby|customi[sz]|armou?r|store|in the hub|looking", re.I), "In the menus")]

_lock = threading.Lock()
_auth = {"hdr": None, "at": 0}
_cache = {}          # xuid -> (at, result)


def _header():
    """XBL3.0 auth header for xboxlive.com, minted from the stored user token (cached 50 min)."""
    with _lock:
        if _auth["hdr"] and time.time() - _auth["at"] < 50 * 60:
            return _auth["hdr"]
    t = xbox._tokens() or {}
    ut = t.get("user_token")
    if not ut:
        return None
    r = requests.post("https://xsts.auth.xboxlive.com/xsts/authorize", headers={"x-xbl-contract-version": "1"}, timeout=8,
                      json={"Properties": {"SandboxId": "RETAIL", "UserTokens": [ut]}, "RelyingParty": "http://xboxlive.com", "TokenType": "JWT"})
    r.raise_for_status()
    j = r.json()
    uhs = (j.get("DisplayClaims", {}).get("xui") or [{}])[0].get("uhs")
    if not j.get("Token") or not uhs:
        return None
    hdr = f"XBL3.0 x={uhs};{j['Token']}"
    with _lock:
        _auth.update(hdr=hdr, at=time.time())
    return hdr


def classify(text):
    """Rich-presence line -> {kind, text}. Unknown wording: kind 'playing' with the line itself."""
    s = (text or "").strip()
    if not s:
        return None
    for kind, rx, label in KINDS:
        if rx.search(s):
            detail = s if kind in ("ranked", "matchmaking", "custom") and len(s) <= 60 else ""
            return {"kind": kind, "label": label, "detail": detail}
    return {"kind": "playing", "label": "In Halo", "detail": s[:60]}


def _parse(entry):
    for d in entry.get("devices") or []:
        for t in d.get("titles") or []:
            if HALO_TITLE.search(t.get("name") or "") and (t.get("state") or "").lower() == "active":
                c = classify((t.get("activity") or {}).get("richPresence"))
                return c or {"kind": "playing", "label": "In Halo", "detail": ""}
    return None


def get(xuids):
    """{xuid: {kind, label, detail} | None} — None = not in Halo or hidden by their privacy settings. Cached 30 s;
    any failure returns what's cached (or nothing) — presence is a nice-to-have, never an error."""
    xuids = [str(x) for x in xuids if x]
    now, out, need = time.time(), {}, []
    for x in xuids:
        hit = _cache.get(x)
        if hit and now - hit[0] < TTL_S:
            out[x] = hit[1]
        else:
            need.append(x)
    if not need:
        return out
    try:
        hdr = _header()
        if not hdr:
            return out
        r = requests.post("https://userpresence.xboxlive.com/users/batch", timeout=3,
                          headers={"Authorization": hdr, "x-xbl-contract-version": "3", "Accept": "application/json"},
                          json={"users": need[:100], "level": "all"})
        if r.status_code == 401:
            with _lock:
                _auth.update(hdr=None, at=0)
        r.raise_for_status()
        got = {str(e.get("xuid")): _parse(e) for e in r.json() or []}
        for x in need:
            _cache[x] = (now, got.get(x))
            out[x] = got.get(x)
    except Exception as e:                       # never break a page over presence
        log.warning("presence lookup failed: %s", type(e).__name__)
        for x in need:                           # and don't retry on every page view while Xbox is slow
            _cache[x] = (now, None)
    return out
