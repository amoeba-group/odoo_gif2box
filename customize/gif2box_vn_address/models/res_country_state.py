from odoo import api, fields, models

from .res_country_ward import vn_sort_key


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

    @api.model
    def _vn_current_provinces(self):
        """The 34 provinces an address can be written against today."""
        provinces = self.sudo().search([
            ('country_id', '=', self.env.ref('base.vn').id),
            ('vn_gso_code', '!=', False),
        ])
        return provinces.sorted(key=lambda state: vn_sort_key(state.name))
