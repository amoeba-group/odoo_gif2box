"""The QR code of the thank-you card, drawn as SVG.

Vector, so that it prints sharp at any size. The three corner squares are
rounded and the centre carries a small heart: error correction is set to
the highest level ('H', 30 % of the code may be lost) so that the heart,
which covers about 5 %, costs nothing in reading it. Modules are near
black on white, the contrast scanners need.
"""
import qrcode
from markupsafe import Markup
from qrcode.constants import ERROR_CORRECT_H

QUIET_ZONE = 4

HEART = ('M12 21s-7.5-4.6-9.6-9.4C.9 7.9 3.3 4 7 4c2.1 0 3.6 1.1 5 3 1.4-1.9 2.9-3 5-3 '
         '3.7 0 6.1 3.9 4.6 7.6C19.5 16.4 12 21 12 21z')


def qr_svg(data, dark='#0B3535', accent='#FD7352'):
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    size = len(matrix)

    finders = ((0, 0), (0, size - 7), (size - 7, 0))

    def in_finder(row, col):
        return any(r <= row < r + 7 and c <= col < c + 7 for r, c in finders)

    # The heart's square, in the middle. From version 7 on, an alignment
    # pattern sits there, which must stay: no heart then.
    logo = 0
    if qr.version < 7:
        logo = max(5, round(size * 0.22))
        if logo % 2 != size % 2:
            logo += 1
    low = (size - logo) // 2
    high = low + logo

    def in_logo(row, col):
        return logo and low <= row < high and low <= col < high

    def dark_module(row, col):
        return matrix[row][col] and not in_finder(row, col) and not in_logo(row, col)

    # One path, a run of dark modules per segment.
    runs = []
    for row in range(size):
        col = 0
        while col < size:
            if dark_module(row, col):
                start = col
                while col < size and dark_module(row, col):
                    col += 1
                runs.append('M%d %dh%dv1h-%dz' % (start, row, col - start, col - start))
            else:
                col += 1

    eyes = []
    for row, col in finders:
        eyes.append('<rect x="%s" y="%s" width="6" height="6" rx="1.7" fill="none" stroke="%s" stroke-width="1"/>'
                    % (col + .5, row + .5, dark))
        eyes.append('<rect x="%s" y="%s" width="3" height="3" rx=".9" fill="%s"/>' % (col + 2, row + 2, dark))

    heart = ''
    if logo:
        scale = (logo - 1.6) / 24.0
        heart = (
            '<rect x="%(x)s" y="%(x)s" width="%(w)s" height="%(w)s" rx="%(r)s" fill="#fff"/>'
            '<path transform="translate(%(hx)s %(hy)s) scale(%(s)s)" d="%(d)s" fill="%(c)s"/>'
        ) % {
            'x': low, 'w': logo, 'r': logo * .28,
            'hx': low + .8, 'hy': low + .95, 's': round(scale, 4),
            'd': HEART, 'c': accent,
        }

    box = size + 2 * QUIET_ZONE
    return Markup(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%(o)d %(o)d %(b)d %(b)d" '
        'width="100%%" height="100%%" shape-rendering="crispEdges">'
        '<rect x="%(o)d" y="%(o)d" width="%(b)d" height="%(b)d" fill="#fff"/>'
        '<path d="%(p)s" fill="%(c)s"/>'
        '<g shape-rendering="geometricPrecision">%(e)s%(h)s</g>'
        '</svg>'
    ) % {
        'o': -QUIET_ZONE, 'b': box, 'p': ''.join(runs), 'c': dark,
        'e': Markup(''.join(eyes)), 'h': Markup(heart),
    }
