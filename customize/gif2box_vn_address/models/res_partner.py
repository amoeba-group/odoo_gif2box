from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ward_id = fields.Many2one(
        'res.country.ward', string='Ward / Commune', index='btree_not_null',
        ondelete='restrict', domain="[('state_id', '=?', state_id)]")

    @api.model
    def _address_fields(self):
        # Synced from a company to its contacts, like the rest of the address.
        return super()._address_fields() + ['ward_id']

    @api.model
    def _formatting_address_fields(self):
        # Not a formatting field: the ward is already printed through `city`,
        # see `_vn_fill_from_ward`. Left in, it would hand a recordset to the
        # address format.
        return [f for f in super()._formatting_address_fields() if f != 'ward_id']

    # --- Keeping `city` and `state_id` in step with the ward -------------
    #
    # Everything in Odoo that prints an address -- invoices, delivery slips,
    # the address cards at checkout, the portal -- reads `city`. Since 2025
    # the commune is the locality line of a Vietnamese address, so the ward's
    # name is written there and none of those places needs to know wards
    # exist. The province is taken from the ward too, so the two can never
    # disagree.

    @api.model
    def _vn_fill_from_ward(self, vals):
        if vals.get('ward_id'):
            ward = self.env['res.country.ward'].browse(vals['ward_id'])
            vals['city'] = ward.name
            vals['state_id'] = ward.state_id.id
            vals['country_id'] = ward.country_id.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        # Copies, so the caller's dicts are not rewritten under it.
        return super().create([self._vn_fill_from_ward(dict(vals)) for vals in vals_list])

    def write(self, vals):
        return super().write(self._vn_fill_from_ward(dict(vals)))

    @api.onchange('ward_id')
    def _onchange_ward_id(self):
        if self.ward_id:
            self.city = self.ward_id.name
            self.state_id = self.ward_id.state_id

    @api.onchange('state_id')
    def _onchange_state_id_clear_ward(self):
        if self.ward_id and self.ward_id.state_id != self.state_id:
            self.ward_id = False
