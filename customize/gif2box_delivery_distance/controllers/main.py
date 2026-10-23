from odoo import http
from odoo.http import request


class Gif2boxFreeShipping(http.Controller):

    @http.route('/shop/gif2box/free_shipping', type='json', auth='public',
                website=True, sitemap=False)
    def free_shipping(self):
        """The free shipping bar for the current cart, as HTML, for the
        "added to your cart" popup, which only receives the added lines."""
        order = request.website.sale_get_order()
        html = request.env['ir.ui.view']._render_template(
            'gif2box_delivery_distance.free_shipping_bar',
            {'g2b_order': order, 'website': request.website})
        return {'html': html}
