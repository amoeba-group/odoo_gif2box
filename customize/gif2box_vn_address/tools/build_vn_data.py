# -*- coding: utf-8 -*-
"""Regenerate `data/res.country.state.csv` and `data/res.country.ward.csv`.

Not imported by Odoo. Run it when the administrative map changes again:

    python tools/build_vn_data.py                 # fetch from the API
    python tools/build_vn_data.py snapshot.json   # or from a saved copy

Source: https://provinces.open-api.vn/api/v2/?depth=2, the units in force
since 1 July 2025 (Resolution 202/2025/QH15 for the provinces, and the
commune-level arrangement that followed). The build refuses to write unless
the totals are the published ones: 34 provinces, and 3,321 communes made of
2,621 xa, 687 phuong and 13 dac khu.
"""
import csv
import json
import os
import sys
import urllib.request

API = 'https://provinces.open-api.vn/api/v2/?depth=2'

# Every one of the 34 provinces kept the name of a province that already
# existed, so each maps onto a record Odoo ships in `base`. Reusing those
# records keeps every customer address that points at them. Keyed by the
# GSO code of the new province.
#
# Built by matching names against base, diacritics-insensitive, and checked
# 34 for 34; Hue is the one whose name moved (Thua Thien - Hue).
PROVINCE_XMLID = {
    '01': 'VN-HN', '04': 'VN-04', '08': 'VN-07', '11': 'VN-71', '12': 'VN-01',
    '14': 'VN-05', '15': 'VN-02', '19': 'VN-69', '20': 'VN-09', '22': 'VN-13',
    '24': 'VN-56', '25': 'VN-68', '31': 'VN-HP', '33': 'VN-66', '37': 'VN-18',
    '38': 'VN-21', '40': 'VN-22', '42': 'VN-23', '44': 'VN-25', '46': 'VN-26',
    '48': 'VN-DN', '51': 'VN-29', '52': 'VN-30', '56': 'VN-34', '66': 'VN-33',
    '68': 'VN-35', '75': 'VN-39', '79': 'VN-SG', '80': 'VN-37', '82': 'VN-45',
    '86': 'VN-49', '91': 'VN-44', '92': 'VN-CT', '96': 'VN-59',
}

DIVISION = {
    'phường': ('phuong', 'Phường'),
    'xã': ('xa', 'Xã'),
    'đặc khu': ('dac_khu', 'Đặc khu'),
}

EXPECTED = {'provinces': 34, 'wards': 3321, 'xa': 2621, 'phuong': 687, 'dac_khu': 13}


def load(argv):
    if len(argv) > 1:
        with open(argv[1], encoding='utf-8') as fh:
            return json.load(fh)
    with urllib.request.urlopen(API, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8'))


def ward_name(raw, prefix):
    # The source carries at least one lower-case prefix ("xã Bắc Sơn").
    if raw[:len(prefix)].lower() == prefix.lower():
        return prefix + raw[len(prefix):]
    return raw


def main(argv):
    provinces = load(argv)
    here = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(here, '..', 'data')

    states, wards = [], []
    counts = {'xa': 0, 'phuong': 0, 'dac_khu': 0}
    for province in sorted(provinces, key=lambda p: p['code']):
        gso = '%02d' % province['code']
        xmlid = 'base.state_vn_' + PROVINCE_XMLID[gso]
        states.append((xmlid, gso))
        for ward in sorted(province['wards'], key=lambda w: w['code']):
            key, prefix = DIVISION[ward['division_type']]
            counts[key] += 1
            code = '%05d' % ward['code']
            wards.append(('ward_vn_' + code, ward_name(ward['name'], prefix), code, key, xmlid))

    found = dict(counts, provinces=len(states), wards=len(wards))
    if found != EXPECTED:
        sys.exit('refusing to write: totals %r, expected %r' % (found, EXPECTED))

    with open(os.path.join(data_dir, 'res.country.state.csv'), 'w', encoding='utf-8', newline='') as fh:
        out = csv.writer(fh, lineterminator='\n')
        out.writerow(['id', 'vn_gso_code'])
        out.writerows(states)

    with open(os.path.join(data_dir, 'res.country.ward.csv'), 'w', encoding='utf-8', newline='') as fh:
        out = csv.writer(fh, lineterminator='\n')
        out.writerow(['id', 'name', 'code', 'division_type', 'state_id:id'])
        out.writerows(wards)

    print('wrote %(provinces)d provinces and %(wards)d wards '
          '(%(xa)d xa, %(phuong)d phuong, %(dac_khu)d dac khu)' % found)


if __name__ == '__main__':
    main(sys.argv)
