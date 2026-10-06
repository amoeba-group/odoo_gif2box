# -*- coding: utf-8 -*-
"""Render the social share card at `static/src/img/social_share.png`.

Not imported by Odoo: it lives outside the module's Python packages and is
only here so the card can be re-rendered when the wording changes.

    python tools/make_social_share.py path/to/logo.png

The size is 1200x630, the 1.91:1 Facebook, Zalo and X all crop to. Everything
that has to survive a square crop stays inside the middle 630px, because the
small previews in a chat list take that square out of the centre.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 630
SQUARE_SAFE = (W - H) // 2, W - (W - H) // 2  # 285 .. 915

CORAL = (253, 115, 82)
BLUE = (11, 136, 253)
INK = (0, 68, 68)
MUTED = (108, 117, 125)

HEADLINE = ['Đồ ăn dặm & quà tặng cho bé', 'chính hãng Hàn Quốc']
FOOTNOTE = 'Đổi trả 30 ngày  ·  Giao hàng 2–3 ngày'

FONT_BOLD = r'C:\Windows\Fonts\segoeuib.ttf'
FONT_REG = r'C:\Windows\Fonts\segoeui.ttf'


def vertical_wash(size, top, bottom):
    """A soft top-to-bottom gradient, drawn one row at a time."""
    w, h = size
    out = Image.new('RGB', size)
    draw = ImageDraw.Draw(out)
    for y in range(h):
        t = y / (h - 1)
        draw.line(
            [(0, y), (w, y)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)),
        )
    return out


def blob(size, centre, radius, colour, alpha):
    """One out-of-focus circle of brand colour, to keep the field from going flat."""
    layer = Image.new('RGBA', size, colour + (0,))
    draw = ImageDraw.Draw(layer)
    x, y = centre
    draw.ellipse(
        [x - radius, y - radius, x + radius, y + radius], fill=colour + (alpha,)
    )
    return layer.filter(ImageFilter.GaussianBlur(radius * 0.45))


def centred(draw, text, font, y, fill, centre=W // 2):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text((centre - (right - left) / 2 - left, y - top), text, font=font, fill=fill)
    return bottom - top


def build(logo_path, out_path):
    card = vertical_wash((W, H), (255, 249, 246), (255, 255, 255)).convert('RGBA')
    card.alpha_composite(blob((W, H), (-40, -40), 520, CORAL, 70))
    card.alpha_composite(blob((W, H), (W + 60, H + 80), 520, BLUE, 55))

    logo = Image.open(logo_path).convert('RGBA')
    logo_w = 600
    logo = logo.resize((logo_w, round(logo.height * logo_w / logo.width)), Image.LANCZOS)
    logo_y = 118
    card.alpha_composite(logo, ((W - logo_w) // 2, logo_y))

    draw = ImageDraw.Draw(card)
    headline_font = ImageFont.truetype(FONT_BOLD, 44)
    foot_font = ImageFont.truetype(FONT_REG, 26)

    y = logo_y + logo.height + 46
    for line in HEADLINE:
        y += centred(draw, line, headline_font, y, INK) + 14

    # A short rule between the promise and the proof, in the logo's two colours.
    rule_w, rule_h = 120, 4
    rule = Image.new('RGBA', (rule_w, rule_h))
    rule_draw = ImageDraw.Draw(rule)
    for x in range(rule_w):
        t = x / (rule_w - 1)
        rule_draw.line(
            [(x, 0), (x, rule_h)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(CORAL, BLUE)) + (255,),
        )
    y += 12
    card.alpha_composite(rule, ((W - rule_w) // 2, y))

    y += rule_h + 26
    centred(draw, FOOTNOTE, foot_font, y, MUTED)

    # A band along the foot, so the card still reads as gif2box's once a feed
    # has scaled it down to a thumbnail.
    band_h = 12
    band = Image.new('RGBA', (W, band_h))
    band_draw = ImageDraw.Draw(band)
    for x in range(W):
        t = x / (W - 1)
        band_draw.line(
            [(x, 0), (x, band_h)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(CORAL, BLUE)) + (255,),
        )
    card.alpha_composite(band, (0, H - band_h))

    card.convert('RGB').save(out_path, 'PNG', optimize=True)
    print('wrote %s (%dx%d, %d bytes)' % (out_path, W, H, os.path.getsize(out_path)))


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    build(sys.argv[1], os.path.join(here, '..', 'static', 'src', 'img', 'social_share.png'))
