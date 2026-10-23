import math

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.tools import format_amount

from .delivery_area import ZONES

# Divisions charged the courier's 20% surcharge "phát tận nơi đến các địa chỉ
# tuyến ngoại thành, tuyến huyện, tuyến xã, vùng sâu, vùng xa, hải đảo": since
# 1 July 2025 every rural commune is a "xã", and the islands are "đặc khu".
# Hồ Chí Minh City's own outskirts (Củ Chi, Cần Giờ...) are xã too.
SURCHARGED_DIVISIONS = ('xa', 'dac_khu')


class DeliveryCarrier(models.Model):
    """Shipping priced by distance from the warehouse, as the courier does.

    The courier's list (Việt Tín, CPN S07/2025, section I) has four columns:
    Hồ Chí Minh City's inner city, under 300 km, over 300 km, and Hà Nội &
    Đà Nẵng. Its rows are weights; the shop's parcels are light, so one price
    per column is used, whatever the weight (defaults: the "500 g to 1 kg"
    row, which covers an order under the free shipping threshold).

    The column comes from the delivery address: its ward gives the area
    (`gif2box.delivery.area`), the area its distance from the warehouse. On
    top, the surcharges the list's notes add: fuel, and delivery out to a
    commune or an island. VAT, which the list does not include either, is
    the delivery product's tax, as on every other line of the order (10%
    here): adding it here as well charged it twice. The fee is rounded up to
    the thousand đồng as the customer sees it, tax included.

    Free shipping above an amount is Odoo's own `free_over` / `amount`.
    """
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('gif2box_distance', 'By distance from the warehouse')],
        ondelete={'gif2box_distance': lambda recs: recs.write(
            {'delivery_type': 'fixed', 'fixed_price': 0})})

    g2b_origin = fields.Char(
        string='Ships From', default='Thủ Đức, TP. Hồ Chí Minh',
        help="Where parcels leave from. The distances of the delivery areas "
             "are measured from here.")
    g2b_price_inner = fields.Monetary(
        string='Inner City', default=14000,
        help="Hồ Chí Minh City's inner city (column \"Nội thành\").")
    g2b_price_near = fields.Monetary(
        string='Under the Limit', default=32500,
        help="Areas closer than the distance limit (column \"Dưới 300 Km\").")
    g2b_price_far = fields.Monetary(
        string='Over the Limit', default=43000,
        help="Areas further than the distance limit (column \"Trên 300 Km\").")
    g2b_price_hub = fields.Monetary(
        string='Hà Nội & Đà Nẵng', default=39000,
        help="Column \"Hà Nội & Đà Nẵng\".")
    g2b_near_km = fields.Integer(
        string='Distance Limit (km)', default=300,
        help="Areas up to this distance pay the \"under\" price, the others "
             "the \"over\" price.")
    g2b_fuel_pct = fields.Float(
        string='Fuel Surcharge (%)', default=20.0,
        help="Added to every price; the courier's list does not include it.")
    g2b_remote_pct = fields.Float(
        string='Commune & Island Surcharge (%)', default=20.0,
        help="Added for a delivery to a commune (xã) or a special zone "
             "(đặc khu, the islands), outer Hồ Chí Minh City included.")
    g2b_tax_ids = fields.Many2many(
        related='product_id.taxes_id', string='VAT on the Fee',
        help="The taxes of the delivery product, which Odoo adds to the fee "
             "like on any order line. The courier's prices exclude VAT.")
    g2b_rounding = fields.Integer(
        string='Round Up To', default=1000,
        help="The fee is rounded up to a multiple of this amount.")
    g2b_preview = fields.Html(
        string='Prices Charged', compute='_compute_g2b_preview', sanitize=False)
    g2b_area_count = fields.Integer(compute='_compute_g2b_area_count')

    # --- Pricing ------------------------------------------------------------

    def _g2b_base_price(self, zone):
        return {
            'inner': self.g2b_price_inner,
            'near': self.g2b_price_near,
            'far': self.g2b_price_far,
            'hub': self.g2b_price_hub,
        }[zone]

    def _g2b_tax_factor(self):
        """(multiplier, included): what the delivery product's taxes add to
        a price, and whether its prices already include them."""
        self.ensure_one()
        company = self.company_id or self.env.company
        taxes = self.product_id.sudo().taxes_id.filtered(
            lambda t: not t.company_id or t.company_id == company)
        if not taxes:
            return 1.0, False
        res = taxes.compute_all(1000.0, product=self.product_id.sudo())
        if not res['total_excluded']:
            return 1.0, False
        return res['total_included'] / res['total_excluded'], any(taxes.mapped('price_include'))

    def _g2b_customer_price(self, zone, surcharged):
        """What the customer pays for a price column, tax included, rounded up."""
        self.ensure_one()
        price = self._g2b_base_price(zone) * (1 + self.g2b_fuel_pct / 100)
        if surcharged:
            price *= 1 + self.g2b_remote_pct / 100
        price *= self._g2b_tax_factor()[0]
        step = self.g2b_rounding if self.g2b_rounding > 0 else 1
        # Rounded to the cent first, so that 15,000.000000002 stays 15,000.
        return math.ceil(round(price, 2) / step) * step

    def _g2b_price(self, zone, surcharged):
        """The fee as Odoo expects it from a rate: in the delivery product's
        terms, before its taxes unless its prices include them. Odoo adds
        them back, and the customer sees `_g2b_customer_price`."""
        total = self._g2b_customer_price(zone, surcharged)
        factor, included = self._g2b_tax_factor()
        return total if included else total / factor

    def _g2b_quote(self, partner):
        """The fee to deliver to `partner`, or None when it cannot be told.

        The ward decides; an address without one (written before the ward
        level existed) is priced as its province's own area, without the
        commune surcharge.
        """
        self.ensure_one()
        partner = partner.sudo()
        if not partner or (partner.country_id and partner.country_id.code != 'VN'):
            return None
        ward = partner.ward_id
        area = ward.g2b_area_id
        if not area and partner.state_id.vn_gso_code:
            area = self.env['gif2box.delivery.area'].sudo().search(
                [('code', '=', partner.state_id.vn_gso_code)], limit=1)
        if not area:
            return None
        zone = area._g2b_zone(self.g2b_near_km)
        surcharged = ward.division_type in SURCHARGED_DIVISIONS
        return {
            'price': self._g2b_price(zone, surcharged),
            'zone': zone,
            'area': area,
            'surcharged': surcharged,
        }

    def gif2box_distance_rate_shipment(self, order):
        quote = self._g2b_quote(order.partner_shipping_id)
        if quote is None:
            return {
                'success': False,
                'price': 0.0,
                'error_message': _(
                    "Choose the province and the ward of the delivery address "
                    "to see the shipping fee."),
                'warning_message': False,
            }
        return {
            'success': True,
            'price': quote['price'],
            'error_message': False,
            'warning_message': False,
        }

    def gif2box_distance_send_shipping(self, pickings):
        # Only reached with "Get Rate and Create Shipment"; the price is
        # recorded as it would have been quoted.
        res = []
        for picking in pickings:
            quote = picking.carrier_id._g2b_quote(picking.partner_id)
            res.append({'exact_price': quote['price'] if quote else 0.0,
                        'tracking_number': False})
        return res

    @api.model
    def _g2b_distance_limit(self):
        carrier = self.sudo().search([('delivery_type', '=', 'gif2box_distance')], limit=1)
        return carrier.g2b_near_km or 300

    # --- Backend ------------------------------------------------------------

    @api.depends('g2b_price_inner', 'g2b_price_near', 'g2b_price_far', 'g2b_price_hub',
                 'g2b_fuel_pct', 'g2b_remote_pct', 'g2b_rounding', 'g2b_near_km',
                 'currency_id', 'product_id.taxes_id')
    def _compute_g2b_preview(self):
        """The price list as customers will be charged, tax included, for
        every column."""
        labels = dict(self.env['gif2box.delivery.area']._fields['zone']._description_selection(self.env))
        for carrier in self:
            if carrier.delivery_type != 'gif2box_distance':
                carrier.g2b_preview = False
                continue
            currency = carrier.currency_id or self.env.company.currency_id
            rows = []
            for zone, _label in ZONES:
                label = labels[zone]
                if zone in ('near', 'far'):
                    label = '%s (%s km)' % (label, carrier.g2b_near_km)
                rows.append(Markup(
                    '<tr><td>%s</td><td class="text-end">%s</td>'
                    '<td class="text-end">%s</td><td class="text-end">%s</td></tr>'
                ) % (label,
                     format_amount(self.env, carrier._g2b_base_price(zone), currency),
                     format_amount(self.env, carrier._g2b_customer_price(zone, False), currency),
                     format_amount(self.env, carrier._g2b_customer_price(zone, True), currency)))
            carrier.g2b_preview = Markup(
                '<table class="table table-sm mb-0"><thead><tr>'
                '<th>%s</th><th class="text-end">%s</th><th class="text-end">%s</th>'
                '<th class="text-end">%s</th></tr></thead><tbody>%s</tbody></table>'
            ) % (escape(_('Price column')), escape(_('Price list')),
                 escape(_('Ward (phường)')), escape(_('Commune or island (xã, đặc khu)')),
                 Markup('').join(rows))

    def _compute_g2b_area_count(self):
        count = self.env['gif2box.delivery.area'].search_count([])
        for carrier in self:
            carrier.g2b_area_count = count

    def action_g2b_view_areas(self):
        return self.env['ir.actions.act_window']._for_xml_id(
            'gif2box_delivery_distance.action_delivery_area')
