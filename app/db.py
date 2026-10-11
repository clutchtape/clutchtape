"""SQLite storage. One small DB for every visitor: players, their matches, sync jobs, per-IP add limits."""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

from halo_paths import data_path

DB_PATH = os.path.join(os.getenv("DB_DIR") or os.path.dirname(str(data_path("x"))), "clutchtape.db")
_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
  id INTEGER PRIMARY KEY,
  xuid TEXT UNIQUE NOT NULL,
  gamertag TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  twitch_login TEXT,
  twitch_user_id TEXT,
  created_at REAL NOT NULL,
  last_synced REAL,
  sync_state TEXT NOT NULL DEFAULT 'queued',   -- queued | syncing | ready | error | private
  sync_error TEXT,
  matches_total INTEGER NOT NULL DEFAULT 0,
  matches_done INTEGER NOT NULL DEFAULT 0,
  views INTEGER NOT NULL DEFAULT 0,
  last_view REAL
);
CREATE INDEX IF NOT EXISTS idx_players_gamertag ON players(gamertag COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS matches (
  player_id INTEGER NOT NULL,
  match_id TEXT NOT NULL,
  started_at REAL NOT NULL,          -- unix seconds (UTC)
  duration_s INTEGER,
  map TEXT, mode TEXT, playlist TEXT,
  ranked INTEGER NOT NULL DEFAULT 0,
  outcome TEXT,                      -- Win | Loss | Tie | Left
  kills INTEGER, deaths INTEGER, assists INTEGER,
  accuracy REAL, damage_dealt INTEGER, damage_taken INTEGER,
  score INTEGER, personal_score INTEGER, headshots INTEGER, shots_fired INTEGER, shots_hit INTEGER,
  max_spree INTEGER, callouts INTEGER,
  team_score INTEGER, enemy_score INTEGER,
  pre_csr INTEGER, post_csr INTEGER,
  medals TEXT,                       -- JSON {"Double Kill": 3, ...}
  PRIMARY KEY (player_id, match_id)
);
CREATE INDEX IF NOT EXISTS idx_matches_player_time ON matches(player_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_matches_id ON matches(match_id);
CREATE TABLE IF NOT EXISTS moments (
  player_id INTEGER NOT NULL,
  match_id TEXT NOT NULL,
  t_ms INTEGER NOT NULL,             -- clip start, ms from the start of the Theater film
  at REAL NOT NULL,                  -- clip start as a real-world unix time (for Twitch VOD links)
  dur_s INTEGER NOT NULL,
  label TEXT NOT NULL,
  kills INTEGER NOT NULL DEFAULT 0,
  score INTEGER NOT NULL,
  PRIMARY KEY (player_id, match_id, t_ms)
);
CREATE INDEX IF NOT EXISTS idx_moments_player ON moments(player_id, score DESC);
CREATE TABLE IF NOT EXISTS add_log (ip TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_add_log_ip ON add_log(ip, at);
CREATE TABLE IF NOT EXISTS events (       -- Theater-film timeline: kills / deaths / medals for everyone in the match (metadata only)
  match_id TEXT NOT NULL, xuid TEXT NOT NULL, gt TEXT, t_ms INTEGER NOT NULL, k TEXT NOT NULL, medal TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_match ON events(match_id, t_ms);
CREATE TABLE IF NOT EXISTS filmed (match_id TEXT PRIMARY KEY, n INTEGER NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS squad_links (code TEXT PRIMARY KEY, slugs TEXT UNIQUE NOT NULL, created REAL);
CREATE TABLE IF NOT EXISTS alts (alt_id INTEGER PRIMARY KEY, main_id INTEGER NOT NULL, created REAL);   -- admin-linked second accounts
CREATE TABLE IF NOT EXISTS stream_log (login TEXT NOT NULL, stream_start REAL NOT NULL, game TEXT, game_id TEXT, title TEXT,
  first_seen REAL NOT NULL, last_seen REAL NOT NULL);   -- see streamlog.py
CREATE INDEX IF NOT EXISTS idx_stream_log ON stream_log(login, stream_start, first_seen);
"""


def conn():
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=30000")
        _local.c = c
    return c


def init():
    conn().executescript(SCHEMA)
    import alerts
    conn().executescript(alerts.SCHEMA)
    for col in ("film_t0 REAL", "film_state INTEGER NOT NULL DEFAULT 0", "team_pscore INTEGER", "team_id INTEGER", "objectives TEXT", "advanced TEXT"):      # 0 untried, 1 done, 2 unavailable
        try:
            conn().execute("ALTER TABLE matches ADD COLUMN " + col)
        except sqlite3.OperationalError:
            pass
    # Privacy: Twitch channels are never stored (they live only in the page URL). Wipe anything saved by older builds.
    conn().execute("UPDATE players SET twitch_login=NULL, twitch_user_id=NULL")
    # One-time: clip detection used to keep no timeline, so re-read the newest games' films once to store it.
    if not conn().execute("SELECT 1 FROM kv WHERE k='migr_events'").fetchone():
        conn().execute("UPDATE matches SET film_state=0 WHERE film_state=1")
        conn().execute("INSERT INTO kv(k,v) VALUES('migr_events','1')")
    # One-time: objective ('mode') events were not stored at first; re-read the films once to add them.
    if not conn().execute("SELECT 1 FROM kv WHERE k='migr_events2'").fetchone():
        conn().execute("DELETE FROM filmed")
        conn().execute("UPDATE matches SET film_state=0 WHERE film_state=1")
        conn().execute("INSERT INTO kv(k,v) VALUES('migr_events2','1')")
    # One-time backfill: games synced before team_pscore existed are re-pulled so SC% fills in.
    if not conn().execute("SELECT 1 FROM kv WHERE k='migr_team_pscore'").fetchone():
        conn().execute("DELETE FROM matches WHERE team_pscore IS NULL")
        conn().execute("UPDATE players SET last_synced=NULL, matches_done=0, matches_total=0 WHERE sync_state='ready'")
        conn().execute("INSERT INTO kv(k,v) VALUES('migr_team_pscore','1')")

    import player_colors
    player_colors.init()
    import data_rights
    data_rights.init()


def q(sql, *args):
    return conn().execute(sql, args).fetchall()


def q1(sql, *args):
    return conn().execute(sql, args).fetchone()


def run(sql, *args):
    return conn().execute(sql, args)


@contextmanager
def tx():
    c = conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


def kv_get(key, default=None):
    r = q1("SELECT v FROM kv WHERE k=?", key)
    return json.loads(r["v"]) if r else default


def kv_set(key, value):
    run("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", key, json.dumps(value))
