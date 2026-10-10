"""The ONE shared Xbox login that reads every player's public Halo data.

Nobody else signs in to Xbox. An admin connects a dedicated Xbox account once (see /admin/xbox); this module keeps
its Halo token chain fresh. NEVER point this at another app's tokens.json: Microsoft rotates the refresh token on
each refresh, so two apps sharing one login invalidate each other.
"""
import json
import logging
import threading
import time

import auth
import requests
import db
from halo_paths import data_path

log = logging.getLogger("clutchtape.xbox")
_lock = threading.Lock()
REMINT_EVERY = 40 * 60          # the spartan token lives far shorter than the Microsoft access token


def _tokens():
    try:
        return json.loads(data_path("tokens.json").read_text())
    except (OSError, ValueError):
        return None


def status():
    t = _tokens()
    if not t or not t.get("spartan_token"):
        return {"connected": False, "reason": "No Xbox account connected yet."}
    minted = db.kv_get("xbox_minted_at", 0)
    return {"connected": True, "minted_ago_min": int((time.time() - minted) / 60) if minted else None,
            "can_refresh": bool(t.get("refresh_token"))}


def ensure_fresh(force=False):
    """Re-mint the whole chain (user -> XSTS -> spartan) when it is old. Safe to call from any thread."""
    t = _tokens()
    if not t or not t.get("spartan_token"):
        raise RuntimeError("Xbox service login is not connected")
    if not t.get("refresh_token"):        # dev/seeded token: use as-is until it dies
        return t
    with _lock:
        minted = db.kv_get("xbox_minted_at", 0)
        if not force and minted and time.time() - minted < REMINT_EVERY:
            return _tokens()
        log.info("re-minting Xbox/Halo token chain (force=%s)", force)
        try:
            auth.main()                    # refreshes access token if needed, then mints user/xsts/spartan
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code != 401:
                raise
            log.warning("Microsoft rejected the access token (401); forcing a refresh")
            cur = _tokens() or {}
            cur["expires_at"] = 0          # the stored lifetime was wrong: make main() refresh for real
            auth.save_tokens(cur)
            auth.main()
        db.kv_set("xbox_minted_at", time.time())
        return _tokens()


def client_args():
    t = ensure_fresh()
    return {"spartan_token": t["spartan_token"], "clearance_token": t.get("clearance_token") or ""}
