from odoo import _, api, fields, models

from .res_country_ward import vn_sort_key

# The provinces merged into each of today's, by GSO code: what a shopper may
# still call the place they live in. Searched on in the province picker, and
# shown under the new name ("incl. former Bình Dương, ..."), so that someone
# typing "Bình Dương" finds Hồ Chí Minh City.
MERGED_PROVINCES = {
    '08': ['Hà Giang'],
    '15': ['Yên Bái'],
    '19': ['Bắc Kạn'],
    '24': ['Bắc Giang'],
    '25': ['Hòa Bình', 'Vĩnh Phúc'],
    '31': ['Hải Dương'],
    '33': ['Thái Bình'],
    '37': ['Hà Nam', 'Nam Định'],
    '44': ['Quảng Bình'],
    '48': ['Quảng Nam'],
    '51': ['Kon Tum'],
    '52': ['Bình Định'],
    '56': ['Ninh Thuận'],
    '66': ['Phú Yên'],
    '68': ['Bình Thuận', 'Đắk Nông'],
    '75': ['Bình Phước'],
    '79': ['Bình Dương', 'Bà Rịa - Vũng Tàu'],
    '80': ['Long An'],
    '82': ['Tiền Giang'],
    '86': ['Bến Tre', 'Trà Vinh'],
    '91': ['Kiên Giang'],
    '92': ['Hậu Giang', 'Sóc Trăng'],
    '96': ['Bạc Liêu'],
}

# Names in everyday use that the official one does not contain.
PROVINCE_ALIASES = {
    '01': 'HN',
    '31': 'HP',
    '48': 'DN',
    '79': 'HCM TPHCM Sài Gòn Saigon SG',
    '92': 'CT',
}


class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    # Set on the 34 provinces in force since 1 July 2025, empty on the 29 that
    # were merged into them. The merged ones stay in the database because
    # existing addresses point at them; they are only kept out of the
    # address form, so no new address is written against a province that no
    # longer exists.
    vn_gso_code = fields.Char(
        string='GSO code', index=True, copy=False,
        help="Code of the province in the General Statistics Office register, for the provinces in force since 1 July 2025.")
    ward_ids = fields.One2many('res.country.ward', 'state_id', string='Wards / Communes')

    def _vn_search_hint(self):
        """A line under the province's name: what it absorbed in 2025, or,
        for one of the 29 merged away, what it is part of now."""
        self.ensure_one()
        if self.vn_gso_code:
            merged = MERGED_PROVINCES.get(self.vn_gso_code)
            return _("incl. former %s", ', '.join(merged)) if merged else ''
        today = self._vn_merged_into()
        return _("merged into %s", today.name) if today else ''

    def _vn_merged_into(self):
        """For a province merged away in 2025, the one it is part of now."""
        self.ensure_one()
        if self.vn_gso_code or self.country_id != self.env.ref('base.vn'):
            return self.browse()
        key = vn_sort_key(self.name)
        for code, names in MERGED_PROVINCES.items():
            if key in {vn_sort_key(name) for name in names}:
                return self.sudo().search([('vn_gso_code', '=', code)], limit=1)
        return self.browse()

    def _vn_search_keywords(self):
        """Other names this province is looked up by."""
        self.ensure_one()
        code = self.vn_gso_code or ''
        return ' '.join(MERGED_PROVINCES.get(code, []) + [PROVINCE_ALIASES.get(code, '')]).strip()

    @api.model
    def _vn_portal_states(self, states, current=None):
        """The provinces the portal's details form offers: every country's,
        less Vietnam's 29 merged ones (unless the contact still has one, so
        that it shows until changed), Vietnam's in reading order."""
        states = states or self.browse()
        vietnam = self.env.ref('base.vn')
        kept = states.filtered(
            lambda s: s.country_id != vietnam or s.vn_gso_code or s == current)
        others = kept.filtered(lambda s: s.country_id != vietnam)
        ours = (kept - others).sorted(key=lambda s: vn_sort_key(s.name))
        return others + ours

    @api.model
    def _vn_current_provinces(self):
        """The 34 provinces an address can be written against today."""
        provinces = self.sudo().search([
            ('country_id', '=', self.env.ref('base.vn').id),
            ('vn_gso_code', '!=', False),
        ])
        return provinces.sorted(key=lambda state: vn_sort_key(state.name))
