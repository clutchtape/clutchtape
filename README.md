# Clutchtape

Halo Infinite stats for you and your squad: every game, every session, your CSR, and who carries.
Add Twitch and every game gets auto clips synced to the stream, plus *Watch together* for the whole squad.

Live: https://clutchtape.com

## Run it

```
docker build -t clutchtape .
docker run -p 8140:8140 -e SECRET_KEY=change-me -v clutchtape-db:/db -v clutchtape-data:/data clutchtape
```

Halo data needs an Xbox service login (set up from `/admin` after first start). Twitch features are optional:
set `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET`.

## Tests

```
pip install -r requirements.txt
PYTHONPATH=app:tests python -m unittest discover -s tests -p 'test_*.py'
```

Browser tests (`tests/*.mjs`, Playwright) run against a running instance:
`node tests/e2e.mjs http://localhost:8140`. Several need a seeded squad; the codes in them are placeholders.
