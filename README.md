# Clutchtape

**Halo Infinite stats for you and your squad**, with every game synced to the stream.

**[clutchtape.com](https://clutchtape.com) is a demo.** This repo is public so you can see *how* it's done and
build your own. Clutchtape is one way to look at Halo Infinite data; there are plenty of better ideas out there for
your squad, your league or your stream. Take the method, borrow any code you want, and make your own web app.

## The method in short

The interesting part isn't the stats pages, it's lining up three public sources by **time**:

1. **Halo match history** (Halo Infinite web API, via [spnkr](https://github.com/acurtis166/SPNKr)): every game's
   result, stats, medals, and the start time. See `app/ingest.py`.
2. **The Theater film of each game**: a timeline of every kill, death, medal and objective event, in milliseconds
   from the start of the match (`read_highlight_events` in spnkr). That's what the timelines, best plays and
   team-play detection are built from. See `app/ingest.py`, `app/clips.py`, `app/teamwork.py`.
3. **Twitch VODs** (Twitch Helix API): each broadcast's start time and length. A game that started at time *T*
   inside a broadcast that started at *S* sits at offset *T − S* in the VOD, so any film event can jump straight
   to the right second of the stream. See `vod_link` in `app/twitch.py`.

Do that for several players in the same match and you can play everyone's stream of that game side by side in sync
(**Watch together**, in `app/templates/squad.html`). By default no video is downloaded or stored: it's all links into Twitch.

Ideas this makes easy: a league site with every scrim's angles, a coach's review tool, a stream overlay that
reacts to medals, a "best plays of the week" page for a clan.

## What it does

- **Every game, every session.** Game log with score share, KDA, damage/min, damage per kill+assist, objective
  stats, lobby MMR and CSR change. Sessions are grouped automatically.
- **Squads.** Up to 6 players side by side, best duos and stacks, best partners, win % with or without each player.
- **Match pages.** Full lobby scoreboard, team-vs-team bars and a timeline of every kill, death, medal and
  objective play from the game's Theater file.
- **With Twitch (optional):** auto clips that jump to the moment on the stream, **Watch together** (every
  squadmate's stream of the same game, synced), and a live panel while someone is streaming.
- **Analysis.** CSR and any stat over time, every player on one chart.

Built with Flask, SQLite and plain JavaScript (no frontend framework). Halo data comes from the Halo Infinite
web API via [spnkr](https://github.com/acurtis166/SPNKr).

## Run it

You need Docker, a **dedicated Xbox account** (not your personal one) and a free Azure app registration for the
Xbox login.

```sh
git clone https://github.com/clutchtape/clutchtape && cd clutchtape
cp .env.example .env        # set SECRET_KEY and ADMIN_PASSWORD
docker compose up -d --build
```

Open http://localhost:8140, then connect Xbox:

1. Create an app at https://portal.azure.com → App registrations → New registration.
   Account type: *personal Microsoft accounts*. Redirect URI (Web): `http://localhost`.
   Under *Certificates & secrets*, create a client secret.
2. Go to http://localhost:8140/admin, log in with `ADMIN_PASSWORD`, and paste the client ID and secret.
3. Click the Microsoft sign-in link and sign in **with the dedicated Xbox account**. Your browser ends on a
   `http://localhost/?code=...` page that fails to load: copy that whole address back into the admin page.

That's it: look up a gamertag on the home page. Each new player loads their latest 200 games in the background.

### Twitch (optional)

Create an app at https://dev.twitch.tv/console/apps (any OAuth redirect, e.g. `http://localhost`), then set
`TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` in `.env` and restart. Twitch channels are remembered only in the browser that added them (see Privacy).

### Putting it online

Serve it behind HTTPS (a reverse proxy or a Cloudflare Tunnel), then in `.env` set `TRUSTED_HOSTS` to your
hostname(s) and `COOKIE_SECURE=1`. Consider protecting `/admin` at the proxy as well.

## Settings

All settings are environment variables; see [`.env.example`](.env.example) for the full list with notes.

| Setting | What it does |
|---|---|
| `SECRET_KEY` | Signs sessions. Required, long and random. |
| `ADMIN_PASSWORD` | Password for `/admin`. |
| `TRUSTED_HOSTS` | Hostnames the site answers on. |
| `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` | Turns on clips, synced VODs and live features. |
| `FEATURED_PLAYERS`, `DEMO_SOLO`, `DEMO_SQUADS` | Example players and squads on the home page. |
| `ADDS_PER_HOUR`, `MAX_PLAYERS`, `FIRST_SYNC_MATCHES` | Lookup limits and how much history to load. |

## Privacy

Clutchtape only shows public Halo Infinite match data, and keeps everything else about you off the site.

**Stats are unlisted, not secret.** Anyone who types an exact gamertag can see that player's stats page, the same
as on any Halo stats site. But there is no list of looked-up players, no "recent searches", no sitemap, and player
pages ask search engines not to index them. Looking yourself up doesn't make you easier to find.

**Twitch stays with you.** If you add your Twitch channel, it's remembered only in **your browser** (inside the
site's signed session cookie). It's never written to the database, never put in a link, and never shown to anyone
else. A link you share shows stats only; whoever opens it sees no stream unless they add the channel themselves.
The only channels shown to everyone are the ones the site owner sets in `FEATURED_PLAYERS` (streamers who are
public examples).

**Your saved stuff is yours.** Saved players and squads live in your browser. If you turn on alerts, the players you
follow (and their channels, for "now streaming" alerts) are stored against that one device only, and you can remove
them any time.

**No accounts needed.** Looking people up needs no sign-in. Optional squad rooms use a username and password
(stored hashed) and nothing else.

**Removal.** Anyone can ask to be removed from the site's Privacy page. Once approved on `/admin`, that gamertag
is deleted and blocked from future lookups.

**Your own server.** The database lives in the `clutchtape-db` volume, with a snapshot in `clutchtape-backups`
every 6 hours. Nothing is sent anywhere except requests to the Halo and Twitch APIs.

Fan-made. Not affiliated with Microsoft, Xbox or 343 Industries.

## Development

```sh
pip install -r requirements.txt
PYTHONPATH=app:tests python -m unittest discover -s tests -p 'test_*.py'
```

Browser tests (`tests/*.mjs`) use Playwright against a running instance, e.g. `node tests/e2e.mjs http://localhost:8140`.
Some need a seeded squad; the squad codes in them are placeholders.

Fixes and ideas are welcome as pull requests, but the best use of this repo is to fork it and build your own thing.
If you do, link it back: we would love to see it.
