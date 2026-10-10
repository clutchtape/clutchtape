"""Browser-only gamertag colors. No shared palette is exposed or changed."""
import re
from flask import Blueprint, abort, render_template
import db
import privacy

bp = Blueprint('player_colors', __name__)
DEFAULT = '#ff7a3d'
PRESETS = ['#ff7a3d', '#ffcc55', '#63dfaa', '#49cce5', '#719bff', '#b78aff', '#f38ac8', '#f47e87']


def init():
    db.conn().execute('CREATE TABLE IF NOT EXISTS player_colors(player_id INTEGER PRIMARY KEY, color TEXT NOT NULL, updated REAL NOT NULL)')


def palette(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('Choose a six-digit hex color, such as #719bff.')
    color = value.lower()
    rgb = [int(color[i:i+2], 16) for i in (1, 3, 5)]
    # Lift dark colors for readable text on the app's dark cards; preserve the chosen hue in accents.
    ink = list(rgb)
    def luminance(channels):
        vals = [c / 255 for c in channels]
        vals = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in vals]
        return sum(c * w for c, w in zip(vals, (.2126, .7152, .0722)))
    while (luminance(ink) + .05) / (luminance([40, 35, 32]) + .05) < 4.5:
        ink = [min(255, c + max(1, round((255-c) * .08))) for c in ink]
    return dict(color=color, ink='#' + ''.join(f'{c:02x}' for c in ink), rgb=', '.join(map(str, rgb)))


def visible(player):
    return not any(privacy.blocked(player[k]) or privacy.hidden(player[k]) for k in ('slug', 'gamertag', 'xuid'))


def install(app, csrf, ip):
    # Legacy shared colors remain inert in storage; never export or write them.
    @bp.get('/p/<slug>/color')
    def edit(slug):
        player = db.q1('SELECT * FROM players WHERE slug=?', slug)
        if not player or not visible(player):
            abort(404)
        return render_template('player_color.html', p=player, color=DEFAULT, presets=PRESETS, error=None)

    app.register_blueprint(bp)
