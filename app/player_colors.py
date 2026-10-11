"""Browser-only gamertag colors. No shared palette is exposed or changed."""
import re
from flask import Blueprint, abort, render_template
import db
import privacy

bp = Blueprint('player_colors', __name__)
DEFAULT = '#ff7a3d'
PRESETS = ['#ff7a3d', '#ffcc55', '#63dfaa', '#49cce5', '#719bff', '#b78aff', '#f38ac8', '#f47e87']
# 2026-10-10: a much bigger palette, grouped. [(group, [(hex, name or None)])]. The Halo 3 armor colors are close
# approximations (by eye from the game's swatches), named so they're recognizable. Dark ones get lightened for text
# by palette() like any other color.
H3 = [('#626262', 'Steel'), ('#b0b0b0', 'Silver'), ('#e3e3e3', 'White'), ('#9b3332', 'Red'), ('#db6766', 'Mauve'),
      ('#ee807f', 'Salmon'), ('#db9334', 'Orange'), ('#f4c973', 'Coral'), ('#fde6b5', 'Peach'), ('#ccae2c', 'Gold'),
      ('#f3dd5a', 'Yellow'), ('#fdf09f', 'Pale'), ('#57741a', 'Sage'), ('#90a560', 'Green'), ('#d8efa7', 'Olive'),
      ('#31787e', 'Teal'), ('#48d2d3', 'Aqua'), ('#98f2f0', 'Cyan'), ('#325992', 'Blue'), ('#5588db', 'Cobalt'),
      ('#97b5f5', 'Sapphire'), ('#553e8f', 'Violet'), ('#9d83e2', 'Orchid'), ('#d0c1fc', 'Lavender'), ('#830147', 'Crimson'),
      ('#df4886', 'Rubine'), ('#ff8bbc', 'Pink'), ('#513b23', 'Brown'), ('#ac8f6c', 'Tan'), ('#e0c3a1', 'Khaki')]
GROUPS = [
    ('Spartan armor', H3),
    ('Fire', [(c, None) for c in ['#ff3b30', '#ff5a36', '#ff7a3d', '#ff8c42', '#ff9f1c', '#ff6b6b', '#e63946', '#d62828', '#ff4d6d', '#c1121f']]),
    ('Sun & gold', [(c, None) for c in ['#ffd60a', '#ffc300', '#ffcc55', '#f4d35e', '#fcbf49', '#e9c46a', '#ffb703', '#f6bd60', '#ffe66d', '#d4a017']]),
    ('Green', [(c, None) for c in ['#63dfaa', '#2ec4b6', '#38b000', '#70e000', '#9ef01a', '#52b788', '#06d6a0', '#80ed99', '#57cc99', '#b5e48c']]),
    ('Ocean & sky', [(c, None) for c in ['#49cce5', '#00b4d8', '#48cae4', '#4cc9f0', '#4895ef', '#4361ee', '#719bff', '#3a86ff', '#00f5d4', '#90e0ef']]),
    ('Violet & pink', [(c, None) for c in ['#b78aff', '#9d4edd', '#c77dff', '#7b2cbf', '#e0aaff', '#f38ac8', '#ff70a6', '#f72585', '#ff99c8', '#f47e87']]),
    ('Metals & pastels', [('#ffffff', 'White'), ('#e5e5e5', 'Platinum'), ('#c0c0c0', 'Silver'), ('#cd7f32', 'Bronze'), ('#b8a07e', 'Brass'),
                          ('#f1faee', 'Ivory'), ('#ffd6a5', 'Apricot'), ('#caffbf', 'Mint'), ('#9bf6ff', 'Ice'), ('#ffc6ff', 'Lilac')]),
]


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
        return render_template('player_color.html', p=player, color=DEFAULT, presets=PRESETS, groups=GROUPS, error=None)

    app.register_blueprint(bp)
