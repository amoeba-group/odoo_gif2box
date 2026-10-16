# -*- coding: utf-8 -*-
from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _compute_last_website_so_id(self):
        """Never hand a buy-now order back as the customer's saved cart.

        A signed-in customer without a cart in their session gets their most
        recently changed draft order as the cart. An unfinished buy-now order
        is always the most recent one, and it would have replaced the cart it
        was meant to leave alone.
        """
        super()._compute_last_website_so_id()
        for partner in self.filtered(lambda p: p.last_website_so_id.is_buy_now_order):
            buy_now = partner.last_website_so_id
            partner.last_website_so_id = self.env['sale.order'].search([
                ('partner_id', '=', partner.id),
                ('pricelist_id', '=', buy_now.pricelist_id.id),
                ('website_id', '=', buy_now.website_id.id),
                ('state', '=', 'draft'),
                ('is_buy_now_order', '=', False),
            ], order='write_date desc', limit=1)
