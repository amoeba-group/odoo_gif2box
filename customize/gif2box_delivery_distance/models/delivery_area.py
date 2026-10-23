from odoo import api, fields, models

# The four price columns of the courier's list (Việt Tín CPN, section I),
# in the order it prints them.
ZONES = [
    ('inner', 'Inner city'),
    ('near', 'Under the distance limit'),
    ('far', 'Over the distance limit'),
    ('hub', 'Hà Nội & Đà Nẵng'),
]


class Gif2boxDeliveryArea(models.Model):
    """One of the 63 provinces as they were before 1 July 2025.

    The courier prices by how far a parcel travels from Hồ Chí Minh City,
    and its destinations are those provinces' towns (Thủ Dầu Một, Vũng Tàu,
    Tân An...), not the 34 merged provinces of today. So every ward points at
    the area it was part of, and an area holds the road distance from the
    warehouse to its seat. Both come from `tools/build_area_data.py` and are
    the client's to adjust: a distance, or which price an area pays, is one
    edit in the list.
    """
    _name = 'gif2box.delivery.area'
    _description = 'Delivery Area'
    _order = 'distance_km, name'

    name = fields.Char(required=True)
    code = fields.Char(
        string='GSO Code (before 07/2025)', required=True, index=True,
        help="The province's code in the register in force until 30 June 2025.")
    seat = fields.Char(
        string='Measured To',
        help="The town the distance is measured to: the provincial seat.")
    state_id = fields.Many2one(
        'res.country.state', string='Province Today', index=True,
        help="The province or city this area is part of since 1 July 2025.")
    distance_km = fields.Integer(
        string='Road Distance (km)',
        help="By road, from the warehouse to the seat.")
    pricing = fields.Selection(
        [('distance', 'By distance'),
         ('inner', 'Inner city'),
         ('hub', 'Hà Nội & Đà Nẵng')],
        string='Pricing', required=True, default='distance',
        help="By distance: under or over the limit set on the delivery "
             "method (300 km in the price list). Inner city and Hà Nội & Đà "
             "Nẵng are the price list's own columns.")
    zone = fields.Selection(ZONES, string='Price Column', compute='_compute_zone')
    ward_ids = fields.One2many('res.country.ward', 'g2b_area_id', string='Wards')
    ward_count = fields.Integer(string='Number of Wards', compute='_compute_ward_count')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'An area already has this code.'),
    ]

    @api.depends('pricing', 'distance_km')
    def _compute_zone(self):
        limit = self.env['delivery.carrier']._g2b_distance_limit()
        for area in self:
            area.zone = area._g2b_zone(limit)

    def _compute_ward_count(self):
        counts = dict(self.env['res.country.ward']._read_group(
            [('g2b_area_id', 'in', self.ids)], ['g2b_area_id'], ['__count']))
        for area in self:
            area.ward_count = counts.get(area, 0)

    def _g2b_zone(self, limit):
        """The price column this area pays, for a distance limit in km."""
        self.ensure_one()
        if self.pricing in ('inner', 'hub'):
            return self.pricing
        return 'near' if self.distance_km <= limit else 'far'

    def action_view_wards(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'res.country.ward',
            'view_mode': 'list,form',
            'domain': [('g2b_area_id', '=', self.id)],
            'context': {'default_g2b_area_id': self.id},
        }
