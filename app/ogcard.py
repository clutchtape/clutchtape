"""Per-page share images (Open Graph cards) for Discord/Reddit/X previews. 1200x630 PNG drawn with Pillow."""
import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(__file__)
FB = os.path.join(HERE, "static", "fonts", "Inter-Bold.ttf")
FR = os.path.join(HERE, "static", "fonts", "Inter-Regular.ttf")
W, H = 1200, 630
MARK = Image.open(os.path.join(HERE, "static", "brand-mark-80.png")).convert("RGBA")
BG, INK, MUTE, ACC, WIN, LOSS, LINE = (12, 10, 9), (244, 239, 233), (154, 143, 134), (255, 122, 61), (74, 222, 128), (248, 113, 113), (48, 40, 35)


def _f(path, size):
    return ImageFont.truetype(path, size)


def _fit(d, text, path, size, max_w):
    while size > 18:
        f = _f(path, size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return _f(path, size)


def _base():
    im = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG)
    g = ImageDraw.Draw(glow)
    g.ellipse((-200, -260, 700, 420), fill=(70, 32, 14))
    g.ellipse((800, 300, 1500, 900), fill=(40, 22, 14))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(120)), 0.9)
    d = ImageDraw.Draw(im)
    # brand: logo mark (rendered from branding/clutchtape-mark.svg) + wordmark
    im.paste(MARK, (78 - 40, 70 - 40), MARK)
    f = _f(FB, 34)
    d.text((122, 50), "Clutch", font=f, fill=INK)
    d.text((122 + d.textlength("Clutch", font=f), 50), "tape", font=f, fill=ACC)
    d.text((W - 60, 56), "Halo Infinite stats", font=_f(FR, 24), fill=MUTE, anchor="ra")
    return im, d


def _stat(d, x, y, big, label, color=INK):
    d.text((x, y), str(big), font=_f(FB, 64), fill=color)
    d.text((x, y + 78), label.upper(), font=_f(FB, 20), fill=MUTE)


def _pips(d, x, y, outs, size=22, gap=6):
    for o in outs[-24:]:
        col = WIN if o == "win" else LOSS if o == "loss" else (120, 110, 100)
        d.rounded_rectangle((x, y, x + size, y + size * 1.6), radius=5, fill=col)
        x += size + gap


def _png(im):
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def player_card(gamertag, session, csr, kda_all, games, channel=None):
    im, d = _base()
    d.text((60, 150), gamertag, font=_fit(d, gamertag, FB, 96, W - 120), fill=INK)
    sub = f"{games} games tracked" + (f"  ·  twitch.tv/{channel}" if channel else "")
    d.text((62, 268), sub, font=_f(FR, 28), fill=MUTE)
    if session:
        w, l = (int(x) for x in session["record"].split("-"))
        _stat(d, 60, 340, session["record"], "last session", WIN if w > l else LOSS if l > w else INK)
        _stat(d, 360, 340, session["kda"], "KDA / game")
        _stat(d, 620, 340, f"{session['win_pct']:.0f}%", "win rate")
        if csr:
            _stat(d, 880, 340, csr, "rating", ACC)
        _pips(d, 62, 490, [m["outcome"].lower() for m in reversed(session["matches"])])
    d.text((60, H - 56), "Game stats · sessions · rank · optional replays", font=_f(FR, 24), fill=MUTE)
    return _png(im)


def squad_card(names, record, games, win_pct, night, top_moment):
    im, d = _base()
    title = " + ".join(names)
    d.text((60, 150), title, font=_fit(d, title, FB, 80, W - 120), fill=INK)
    d.text((62, 255), "Squad · " + f"{games} games together", font=_f(FR, 28), fill=MUTE)
    w, l = (int(x) for x in record.split("-"))
    _stat(d, 60, 320, record, "together", WIN if w > l else LOSS if l > w else INK)
    _stat(d, 380, 320, f"{win_pct}%", "win rate")
    if night:
        nw, nl = (int(x) for x in night["record"].split("-"))
        _stat(d, 640, 320, night["record"], "last night", WIN if nw > nl else LOSS if nl > nw else INK)
        _pips(d, 62, 470, [m["outcome"].lower() for m in reversed(night["matches"])])
    if top_moment:
        d.text((60, 530), "Best play: " + top_moment, font=_fit(d, "Best play: " + top_moment, FB, 30, W - 120), fill=ACC)
    d.text((60, H - 50), "Your squad. Every game. The whole session.", font=_f(FR, 24), fill=MUTE)
    return _png(im)


def home_card():
    im, d = _base()
    d.text((60, 175), "Every game.", font=_f(FB, 84), fill=INK)
    d.text((60, 275), "Your whole session.", font=_f(FB, 84), fill=INK)
    d.text((64, 407), "Game results · session stats · rank · squads", font=_f(FR, 32), fill=ACC)
    d.text((64, 505), "Just a gamertag. No Twitch required.", font=_f(FB, 32), fill=INK)
    d.text((64, 565), "Add Twitch for optional clips and synced replays.", font=_f(FR, 24), fill=MUTE)
    return _png(im)


def session_card(b):
    """Downloadable report for a stable selected session, including non-streamers."""
    from datetime import datetime, timezone
    im,d=_base(); a=b['summary']
    d.text((60,135), b['title'], font=_fit(d,b['title'],FB,64,W-120),fill=INK)
    date=datetime.fromtimestamp(b['selected']['start'],timezone.utc).strftime('%b %d, %Y · %H:%M UTC')
    d.text((62,220),date+' · '+dict(__import__('analytics').KINDS)[b['kind']],font=_f(FR,24),fill=MUTE)
    _stat(d,60,280,(a['record'] if a['wins']+a['losses'] else '—'),b.get('scope_label','Session record'),ACC)
    _stat(d,360,280,a['games'],'games')
    _stat(d,610,280,a.get('kd','—'),'K/D')
    _stat(d,865,280,str(a.get('dmg_pm','—')),'damage / min')
    _pips(d,62,410,[m['outcome'].lower() for m in reversed(b['matches'])])
    rank=' · '.join(x['name']+f" {x['delta']:+} CSR" for x in b['rank'])
    if not rank:
        m=max(b['matches'],key=lambda m:__import__('analytics').kda(m.get('kills'),m.get('deaths'),m.get('assists')))
        rank='Session spotlight · '+(m['map'] or 'Unknown map')+' · '+(m['mode'] or '')
    d.text((60,475),rank,font=_fit(d,rank,FB,26,W-120),fill=INK)
    detail=(b['records'][0]['name']+' · new '+b['records'][0]['label']+' record in loaded history') if b['records'] else 'Stats for every player. No stream required.'
    d.text((60,525),detail,font=_fit(d,detail,FR,24,W-120),fill=MUTE)
    best=max(b['matches'],key=lambda m:__import__('session_review')._summary([m]).get('kda',0))
    spot='Standout game · '+(best['map'] or 'Unknown map')+' · '+(best['mode'] or '')+' · '+best['outcome']
    d.text((60,558),spot,font=_fit(d,spot,FR,20,W-120),fill=INK)
    d.text((60,600),'CLUTCHTAPE  /  Your Halo night, explained.',font=_f(FR,22),fill=ACC)
    return _png(im)


def weekly_card(b,w):
    from datetime import datetime,timezone
    im,d=_base();a=w['summary']
    d.text((60,135),b['title'],font=_fit(d,b['title'],FB,64,W-120),fill=INK)
    dates=datetime.fromtimestamp(w['start'],timezone.utc).strftime('%b %d')+' → '+w['date']+' · UTC · end exclusive'
    d.text((60,225),dates,font=_f(FR,25),fill=MUTE)
    _stat(d,60,300,a['record'],'weekly record',ACC)
    _stat(d,380,300,a['games'],'games')
    _stat(d,670,300,a['kd'],'K/D')
    _stat(d,915,300,a['dmg_pm'],'dmg / min')
    _pips(d,60,435,[m['outcome'].lower() for m in reversed(w['matches'])])
    detail=f'{len(w["records"])} new damage/min bests in comparable loaded history'
    d.text((60,510),detail,font=_fit(d,detail,FR,27,W-120),fill=INK)
    d.text((60,575),'CLUTCHTAPE  /  Your week. No stream required.',font=_f(FR,25),fill=ACC)
    return _png(im)


# ---- session recap (2026-10-12): one shareable image per session — record, CSR line per player, best play ------------
SERIES = [(57, 135, 229), (217, 89, 38), (25, 158, 112), (201, 133, 0)]   # sbchart.js default order (validated on dark)


def recap_card(title, when, record, outcomes, players, best, url_text):
    """players: [{name, csr: [rating after each game or None], csr_d, kda}] in squad order; best: (label, who) or None."""
    im, d = _base()
    d.text((60, 118), title, font=_fit(d, title, FB, 58, W - 120), fill=INK)
    d.text((62, 190), f"Session recap · {when} · {len(outcomes)} game{'s' if len(outcomes) != 1 else ''}", font=_f(FR, 26), fill=MUTE)
    w, l = (int(x) for x in record.split("-"))
    d.text((60, 236), record, font=_f(FB, 96), fill=WIN if w > l else LOSS if l > w else INK)
    _pips(d, 64, 352, outcomes, size=20, gap=5)
    # CSR lines (right): each player's rating after every ranked game, own scale, names + change at the line ends
    x0, x1, y0, y1 = 470, 1000, 268, 440          # starts below the subtitle line
    vals = [v for p in players for v in p["csr"] if v is not None]
    if len(vals) >= 2:
        lo, hi = min(vals), max(vals)
        if hi - lo < 20:
            lo, hi = lo - 10, hi + 10
        n = max(len(p["csr"]) for p in players)
        X = lambda i: x0 + (x1 - x0) * (i / max(1, n - 1))
        Y = lambda v: y1 - (y1 - y0) * (v - lo) / (hi - lo)
        for gy in (lo, (lo + hi) / 2, hi):
            d.line((x0, Y(gy), x1, Y(gy)), fill=(38, 32, 28), width=1)
            d.text((x0 - 10, Y(gy)), str(round(gy)), font=_f(FR, 18), fill=MUTE, anchor="rm")
        ends = []
        for i, p in enumerate(players):
            pts = [(X(j), Y(v)) for j, v in enumerate(p["csr"]) if v is not None]
            if len(pts) < 1:
                continue
            col = SERIES[i % len(SERIES)]
            if len(pts) > 1:
                d.line(pts, fill=col, width=4, joint="curve")
            for (px, py) in pts:
                d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=col, outline=BG, width=2)
            ends.append([pts[-1][1], i, pts[-1][0]])
        ends.sort()
        for k in range(1, len(ends)):                       # nudge labels apart
            if ends[k][0] - ends[k - 1][0] < 26:
                ends[k][0] = ends[k - 1][0] + 26
        for y, i, x in ends:
            p = players[i]
            d.text((x + 14, y), p["name"][:14], font=_f(FB, 20), fill=INK, anchor="lm")
        d.text((x0, y0 - 28), "CSR, game by game", font=_f(FB, 18), fill=MUTE)
    # per-player line: name · CSR change · KDA
    for i, p in enumerate(players[:4]):            # two per row under the record
        yy = 462 + (i // 2) * 34
        xx = 60 + (i % 2) * 560
        d.rounded_rectangle((xx, yy + 6, xx + 14, yy + 10), radius=2, fill=SERIES[i % len(SERIES)])
        d.text((xx + 24, yy), p["name"][:18], font=_f(FB, 24), fill=INK)
        cd = p.get("csr_d")
        tx = xx + 24 + d.textlength(p["name"][:18], font=_f(FB, 24)) + 16
        if cd is not None:
            s = f"{cd:+d} CSR"
            d.text((tx, yy), s, font=_f(FB, 24), fill=WIN if cd > 0 else LOSS if cd < 0 else INK); tx += d.textlength(s, font=_f(FB, 24)) + 16
        if p.get("kda") is not None:
            d.text((tx, yy), f"{p['kda']:+.1f} KDA", font=_f(FR, 24), fill=MUTE)
    if best:
        s = "★ Best play: " + best[0] + (f" — {best[1]}" if best[1] else "")
        d.text((60, 545), s, font=_fit(d, s, FB, 28, W - 120), fill=ACC)
    d.text((60, H - 44), url_text, font=_f(FR, 22), fill=MUTE)
    return _png(im)
