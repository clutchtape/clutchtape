# Clutchtape

Halo Infinite stats for players and squads, with games linked to the right spot in each player's Twitch VOD.

[clutchtape.com](https://clutchtape.com) is a demo. The code is public so people can see how it works and build their
own sites on Halo data. The code is available under the [MIT License](LICENSE).

## How it works

Three data sources, matched up by timestamp:

1. **Match history** from the Halo Infinite web API (via [spnkr](https://github.com/acurtis166/SPNKr)): result,
   stats, medals and start time for each game. `app/ingest.py`
2. **Theater film** for each game: every kill, death, medal and objective event, in milliseconds from the start of
   the match (`read_highlight_events` in spnkr). Used for timelines, clips and team-play detection.
   `app/ingest.py`, `app/clips.py`, `app/teamwork.py`
3. **Twitch VODs** from the Twitch Helix API: each broadcast's start time and length. A game that started at time
   *T* in a broadcast that started at *S* is at offset *T − S* in the VOD. `vod_link` in `app/twitch.py`

With several players in the same game, their VODs can be played side by side at the same moment (Watch together,
`app/templates/squad.html`). No video is downloaded or stored; everything links into Twitch.

## Features

- Game log and sessions: score share (SC%), KDA, damage/min, damage per kill+assist, objective stats, lobby MMR,
  CSR change. Games under 2 minutes (quits/remakes) are left out.
- Squads of up to 6 players: best duos and stacks, win % with and without each player.
- Match pages: full scoreboard, team comparison and an event timeline from the Theater film.
- CSR and stat trends over time, all players on one chart.
- With Twitch set up: clips that open the VOD at the moment, Watch together, and a live panel while someone streams.

Flask, SQLite and plain JavaScript.

## Run it

Needs Docker, a separate Xbox account (not your main one) and a free Azure app registration for the Xbox login.

```sh
git clone https://github.com/clutchtape/clutchtape && cd clutchtape
cp .env.example .env        # set SECRET_KEY and ADMIN_PASSWORD
docker compose up -d --build
```

The site is at http://localhost:8140. To connect Xbox:

1. At https://portal.azure.com go to App registrations → New registration. Account type: personal Microsoft
   accounts. Redirect URI (Web): `http://localhost`. Under Certificates & secrets, create a client secret.
2. Open http://localhost:8140/admin, log in with `ADMIN_PASSWORD` and enter the client ID and secret.
3. Click the Microsoft sign-in link and sign in with the separate Xbox account. The browser ends up on a
   `http://localhost/?code=...` page that doesn't load. Copy that full address into the admin page.

Then search a gamertag on the home page. A new player's latest 200 games load in the background.

### Twitch (optional)

Create an app at https://dev.twitch.tv/console/apps (redirect can be `http://localhost`), set `TWITCH_CLIENT_ID`
and `TWITCH_CLIENT_SECRET` in `.env` and restart.

### Hosting it publicly

Put it behind HTTPS (reverse proxy or Cloudflare Tunnel), set `TRUSTED_HOSTS` to your hostname(s) and
`COOKIE_SECURE=1`. Restricting `/admin` at the proxy is a good idea too.

## Settings

Environment variables. Full list with notes in [`.env.example`](.env.example).

| Setting | Purpose |
|---|---|
| `SECRET_KEY` | Signs sessions. Required. |
| `ADMIN_PASSWORD` | Password for `/admin`. |
| `TRUSTED_HOSTS` | Hostnames the site answers on. |
| `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` | Enables clips, VOD links and live features. |
| `FEATURED_PLAYERS`, `DEMO_SOLO`, `DEMO_SQUADS` | Example players and squads on the home page. |
| `ADDS_PER_HOUR`, `MAX_PLAYERS`, `FIRST_SYNC_MATCHES` | Lookup limits and how many games to load per player. |

## Privacy

- Only public Halo Infinite match data is shown.
- Anyone who types an exact gamertag can see that player's page. There's no list of players (other than the example
  players set in `FEATURED_PLAYERS` / `DEMO_SOLO` / `DEMO_SQUADS`), no recent searches and no sitemap, and player
  pages are marked noindex.
- Twitch channels a visitor adds are kept in that visitor's session cookie only. They aren't saved in the database
  or put in URLs, and other visitors don't see them. Shared links show stats only. The only channels everyone sees
  are the ones in `FEATURED_PLAYERS`.
- Saved players and squads are stored in the browser. Alerts store the followed players (and their channels, for
  stream alerts) for that one device, and can be removed at any time.
- No accounts.
- The Privacy page has a removal request form. Once approved on `/admin`, the gamertag is deleted and blocked from
  future lookups.
- The database is in the `clutchtape-db` volume, with a snapshot in `clutchtape-backups` every 6 hours. The only
  outside requests are to the Halo and Twitch APIs.

Fan-made. Not affiliated with Microsoft, Xbox or 343 Industries.

## Development

```sh
pip install -r requirements.txt
PYTHONPATH=app:tests python -m unittest discover -s tests -p 'test_*.py'
```

Browser tests (`tests/*.mjs`) use Playwright against a running instance, e.g.
`node tests/e2e.mjs http://localhost:8140`. Some need a seeded squad; the squad codes in them are placeholders.

Pull requests are welcome, but forking it and building something of your own is the main point.

## Contact

Questions or feedback: [support@clutchtape.com](mailto:support@clutchtape.com).


## Sync capacity

Viewers of the same gamertag share stored results and a deduplicated sync job.
One worker fetches Halo data; adding HTTP workers alone does not increase Halo
capacity (the scheduler and admission limits are currently single-process).

Accepted new profiles wait durably in SQLite. The worker keeps only a bounded
batch in memory, reserves half its queue for foreground work, and interleaves
new imports with overdue refreshes. Restarting recovers unfinished imports.
New-name resolution still has a shared 20/minute limit and two concurrent
lookups; a burst beyond this receives a retry message, not a guaranteed place.

Open profiles renew a three-minute viewing lease. Their refresh interval scales
with the number of distinct watched players (a two-second budget per player,
with normal 20–30 second minimums). After viewing ends, background checks back
off to 15 minutes, hourly, then daily, and stop after seven days. Featured and
notification-followed players retain hourly checks. These are scheduling
targets; upstream latency, throttling and imports can delay results further.

The latest 25 matches load first; deeper history and Theater work yield to
foreground jobs. A surge can delay historical imports and highlights. Tests
simulate 500 distinct players, bounded admission, duplicate viewers, backoff
and queue recovery without contacting Halo. They are not an end-to-end
500-user load certification.

### Optional operator activity notifications

To receive minimal new-profile summaries, create
`activity-notify.json` in `HALO_DATA_DIR` with
`{"enabled": true, "url": "https://ntfy.example.com/private-topic"}`.
Keep this file private and outside the repository. Existing profiles are
baselined on activation; new additions are batched at most once per five
minutes, at low priority. No names or IPs are sent. Repeat searches and
background syncs do not trigger notices. This counts profiles, not unique
people, and does not count visitors who only browse existing profiles.
Notification state survives restarts and failed deliveries retry later.
