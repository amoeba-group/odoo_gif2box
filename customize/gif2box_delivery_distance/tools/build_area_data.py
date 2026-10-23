# -*- coding: utf-8 -*-
"""Regenerate `data/delivery_area_data.xml` and `data/res.country.ward.csv`.

Not imported by Odoo. Run it when the warehouse moves, or the administrative
map changes again:

    python tools/build_area_data.py                       # fetch everything
    python tools/build_area_data.py old.json km.json      # or from saved copies

What it builds
--------------
A courier's price list (Việt Tín, CPN S07/2025) prices by how far a parcel
travels from Hồ Chí Minh City: inner city, under 300 km, over 300 km, and
Hà Nội / Đà Nẵng. Its destinations are the provincial towns as they were
before 1 July 2025 (Thủ Dầu Một, Vũng Tàu, Tân An...), so each of the 63
provinces of that time is one delivery area here, measured from the
warehouse in Thủ Đức to its provincial seat, by road.

Every ward of the current register (`gif2box_vn_address`) is then given the
area it was part of. The 2025 reform kept the GSO code of one of the merged
wards for each new one, so 3,310 of the 3,321 codes are an old ward's code.
The other eleven (new island zones, and five wards renumbered in Hồ Chí Minh
City) take the area of the nearest lower code in the same province.

Sources
-------
- Old register: https://provinces.open-api.vn/api/v1/?depth=3 (the units in
  force until 30 June 2025), the same project the ward list comes from.
- Coordinates of the seats: OpenStreetMap (Nominatim), checked by hand;
  the city centres below replace the answers that came back as a province's
  centroid, up to 40 km off.
- Road distances: OSRM (router.project-osrm.org), one table request from the
  warehouse to all 63 seats.
"""
import bisect
import csv
import json
import os
import sys
import urllib.request
from collections import Counter
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.dirname(HERE)
WARDS_CSV = os.path.join(MODULE, '..', 'gif2box_vn_address', 'data', 'res.country.ward.csv')

OLD_API = 'https://provinces.open-api.vn/api/v1/?depth=3'
OSRM = 'https://router.project-osrm.org/table/v1/driving/%s?sources=0&annotations=distance'
UA = 'gif2box.vn shipping zone setup (https://gif2box.vn)'

# The warehouse: Thủ Đức, Hồ Chí Minh City.
ORIGIN = (10.8505674, 106.7585291)

# Old GSO province code: (seat, latitude, longitude).
SEATS = {
    1: ('Hà Nội', 21.0283, 105.8540), 2: ('Hà Giang', 22.8168, 104.9505),
    4: ('Cao Bằng', 22.6657, 106.2577), 6: ('Bắc Kạn', 22.1470, 105.8348),
    8: ('Tuyên Quang', 21.8233, 105.2140), 10: ('Lào Cai', 22.4856, 103.9707),
    11: ('Điện Biên Phủ', 21.4904, 103.1046), 12: ('Lai Châu', 22.3964, 103.4582),
    14: ('Sơn La', 21.3256, 103.9188), 15: ('Yên Bái', 21.7229, 104.9113),
    17: ('Hòa Bình', 20.8133, 105.3383), 19: ('Thái Nguyên', 21.5928, 105.8442),
    20: ('Lạng Sơn', 21.8537, 106.7615), 22: ('Hạ Long', 20.9516, 107.0784),
    24: ('Bắc Giang', 21.2731, 106.1946), 25: ('Việt Trì', 21.3324, 105.3660),
    26: ('Vĩnh Yên', 21.3064, 105.5986), 27: ('Bắc Ninh', 21.1785, 106.0562),
    30: ('Hải Dương', 20.9373, 106.3146), 31: ('Hải Phòng', 20.8831, 106.6790),
    33: ('Hưng Yên', 20.6464, 106.0511), 34: ('Thái Bình', 20.4463, 106.3366),
    35: ('Phủ Lý', 20.5446, 105.9339), 36: ('Nam Định', 20.4388, 106.1621),
    37: ('Ninh Bình', 20.2572, 105.9719), 38: ('Thanh Hóa', 19.8067, 105.7852),
    40: ('Vinh', 18.7358, 105.6906), 42: ('Hà Tĩnh', 18.3428, 105.9057),
    44: ('Đồng Hới', 17.4495, 106.5912), 45: ('Đông Hà', 16.8025, 107.0953),
    46: ('Huế', 16.4639, 107.5863), 48: ('Đà Nẵng', 16.0685, 108.2240),
    49: ('Tam Kỳ', 15.5756, 108.4994), 51: ('Quảng Ngãi', 15.1214, 108.8044),
    52: ('Quy Nhơn', 13.7550, 109.1768), 54: ('Tuy Hòa', 13.0950, 109.2992),
    56: ('Nha Trang', 12.2085, 109.2871), 58: ('Phan Rang - Tháp Chàm', 11.6039, 108.9653),
    60: ('Phan Thiết', 10.9029, 108.0633), 62: ('Kon Tum', 14.3497, 108.0005),
    64: ('Pleiku', 13.9774, 108.0002), 66: ('Buôn Ma Thuột', 12.6613, 108.0310),
    67: ('Gia Nghĩa', 12.0128, 107.6685), 68: ('Đà Lạt', 11.9083, 108.4572),
    70: ('Đồng Xoài', 11.5271, 106.8626), 72: ('Tây Ninh', 11.3100, 106.0983),
    74: ('Thủ Dầu Một', 10.9809, 106.6537), 75: ('Biên Hòa', 10.9142, 106.8916),
    77: ('Bà Rịa', 10.4933, 107.1789), 79: ('TP. Hồ Chí Minh', 10.7737, 106.7166),
    80: ('Tân An', 10.5261, 106.3990), 82: ('Mỹ Tho', 10.3628, 106.3591),
    83: ('Bến Tre', 10.2415, 106.3759), 84: ('Trà Vinh', 9.9347, 106.3453),
    86: ('Vĩnh Long', 10.2537, 105.9722), 87: ('Cao Lãnh', 10.4602, 105.6123),
    89: ('Long Xuyên', 10.3720, 105.4149), 91: ('Rạch Giá', 10.0272, 105.0905),
    92: ('Cần Thơ', 10.0362, 105.7873), 93: ('Vị Thanh', 9.7529, 105.4493),
    94: ('Sóc Trăng', 9.6025, 105.9739), 95: ('Bạc Liêu', 9.2940, 105.7216),
    96: ('Cà Mau', 9.1769, 105.1524),
}

# The columns of the price list that are not a distance: Hồ Chí Minh City's
# own inner city, and the Hà Nội / Đà Nẵng rate.
PRICING = {79: 'inner', 1: 'hub', 48: 'hub'}


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def short_name(name):
    for prefix in ('Thành phố ', 'Tỉnh '):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return 'TP. Hồ Chí Minh' if name == 'Hồ Chí Minh' else name


def main(old_path=None, km_path=None):
    old = json.load(open(old_path)) if old_path else fetch_json(OLD_API)
    if len(old) != 63:
        sys.exit('expected the 63 provinces of the old register, got %s' % len(old))

    if km_path:
        km = {int(k): v for k, v in json.load(open(km_path))['km'].items()}
    else:
        codes = sorted(SEATS)
        points = [ORIGIN] + [SEATS[c][1:] for c in codes]
        coords = ';'.join('%.5f,%.5f' % (lon, lat) for lat, lon in points)
        res = fetch_json(OSRM % coords)
        km = {c: round(d / 1000) for c, d in zip(codes, res['distances'][0][1:])}

    old_ward = {}   # old ward code -> old province code
    old_name = {}
    for prov in old:
        old_name[prov['code']] = prov['name']
        for district in prov['districts']:
            for ward in district['wards']:
                old_ward[ward['code']] = prov['code']

    with open(WARDS_CSV, encoding='utf-8') as fh:
        wards = list(csv.DictReader(fh))
    if len(wards) != 3321:
        sys.exit('expected 3,321 wards in %s, got %s' % (WARDS_CSV, len(wards)))

    # Exact matches first, then the nearest lower code in the same province.
    by_state = {}
    for ward in wards:
        by_state.setdefault(ward['state_id:id'], []).append(ward)
    area_of = {}
    for state, members in by_state.items():
        known = sorted((int(w['code']), old_ward[int(w['code'])])
                       for w in members if int(w['code']) in old_ward)
        known_codes = [code for code, _ in known]
        for ward in members:
            code = int(ward['code'])
            if code in old_ward:
                area_of[ward['id']] = old_ward[code]
            else:
                i = bisect.bisect_left(known_codes, code)
                area_of[ward['id']] = known[max(i - 1, 0)][1]

    # Each area belongs to the province most of its wards are in now; an area
    # is "(cũ)" when that province is made of more than one of them.
    state_votes = {}
    for ward in wards:
        state_votes.setdefault(area_of[ward['id']], Counter())[ward['state_id:id']] += 1
    area_state = {code: votes.most_common(1)[0][0] for code, votes in state_votes.items()}
    areas_per_state = Counter(area_state.values())

    # XML rather than CSV for the one reason that it can be `noupdate`: the
    # distances and pricings are the client's to adjust, and an update of
    # the module must not put them back.
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!-- Generated by tools/build_area_data.py: road distances from the',
        '     warehouse (Thu Duc) to the seats of the 63 provinces in force until',
        '     30 June 2025. noupdate: adjusted in Website > Configuration. -->',
        '<odoo noupdate="1">',
    ]
    for code in sorted(old_name):
        name = short_name(old_name[code])
        if areas_per_state[area_state[code]] > 1:
            name += ' (cũ)'
        lines += [
            '    <record id="area_vn_%02d" model="gif2box.delivery.area">' % code,
            '        <field name="name">%s</field>' % escape(name),
            '        <field name="code">%02d</field>' % code,
            '        <field name="seat">%s</field>' % escape(SEATS[code][0]),
            '        <field name="state_id" ref="%s"/>' % area_state[code],
            '        <field name="distance_km">%s</field>' % km[code],
            '        <field name="pricing">%s</field>' % PRICING.get(code, 'distance'),
            '    </record>',
        ]
    lines.append('</odoo>')
    with open(os.path.join(MODULE, 'data', 'delivery_area_data.xml'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')

    with open(os.path.join(MODULE, 'data', 'res.country.ward.csv'), 'w',
              newline='', encoding='utf-8') as fh:
        out = csv.writer(fh)
        out.writerow(['id', 'g2b_area_id:id'])
        for ward in wards:
            out.writerow(['gif2box_vn_address.' + ward['id'], 'area_vn_%02d' % area_of[ward['id']]])

    exact = sum(1 for w in wards if int(w['code']) in old_ward)
    print('63 areas, %s wards (%s by their own code, %s by the nearest one)'
          % (len(wards), exact, len(wards) - exact))


if __name__ == '__main__':
    main(*sys.argv[1:3])
