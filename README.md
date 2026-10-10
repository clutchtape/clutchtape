# Clutchtape

**Halo Infinite stats for you and your squad.** Type a gamertag and get every game, every session and your CSR.
Add your squad to see who carries. Add Twitch and every game is synced to the stream.

Live at **https://clutchtape.com**

## What it does

- **Every game, every session.** Game log with score share, KDA, damage/min, damage per kill+assist, objective
  stats, lobby MMR and CSR change. Sessions are grouped automatically.
- **Squads.** Up to 6 players side by side, best duos and stacks, best partners, win % with or without each player.
- **Match pages.** Full lobby scoreboard, team-vs-team bars and a timeline of every kill, death, medal and
  objective play from the game's Theater file.
- **Best plays, no stream needed.** Highlights are found in the game files, so they work for everyone.
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
`TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` in `.env` and restart. Twitch channels are never stored: they ride
in page links (`?tw=channel`) or in `FEATURED_PLAYERS`.

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

## Data and privacy

- Uses public Halo Infinite match data only. Anyone can be looked up by gamertag.
- The database lives in the `clutchtape-db` volume; a snapshot is written to `clutchtape-backups` every 6 hours.
- People can ask to be removed from the site's Privacy page; requests show up on `/admin`.
- Fan-made. Not affiliated with Microsoft, Xbox or 343 Industries.

## Development

```sh
pip install -r requirements.txt
PYTHONPATH=app:tests python -m unittest discover -s tests -p 'test_*.py'
```

Browser tests (`tests/*.mjs`) use Playwright against a running instance, e.g. `node tests/e2e.mjs http://localhost:8140`.
Some need a seeded squad; the squad codes in them are placeholders.

Contributions welcome: fork the repo and open a pull request.
