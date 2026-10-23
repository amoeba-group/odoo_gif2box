from odoo import fields, models


class ResCountryWard(models.Model):
    _inherit = 'res.country.ward'

    # The province before 1 July 2025 this ward was part of, which is what the
    # courier's price list goes by (`data/res.country.ward.csv`, built by
    # `tools/build_area_data.py`).
    g2b_area_id = fields.Many2one(
        'gif2box.delivery.area', string='Delivery Area', index=True,
        help="The area this ward is priced as for delivery: the province it "
             "belonged to before 1 July 2025.")
