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
