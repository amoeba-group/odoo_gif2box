from odoo import models


class Website(models.Model):
    _inherit = 'website'

    def _g2b_free_shipping_threshold(self):
        """The order amount from which delivery is free on this website: the
        lowest "Free if order amount is above" of its published delivery
        methods, or 0 when none offers it."""
        self.ensure_one()
        carriers = self.env['delivery.carrier'].sudo().search([
            ('is_published', '=', True),
            ('free_over', '=', True),
            ('amount', '>', 0),
            ('website_id', 'in', (False, self.id)),
        ])
        return min(carriers.mapped('amount'), default=0.0)

    def _g2b_free_shipping_status(self, order=None):
        """Where an order stands against free shipping, for the progress bar
        (`views/free_shipping_templates.xml`); None when there is no
        threshold to show.

        The amount is the one Odoo compares to the threshold: the order's
        total, taxes included, delivery left out.
        """
        self.ensure_one()
        threshold = self._g2b_free_shipping_threshold()
        if not threshold:
            return None
        amount = order._compute_amount_total_without_delivery() if order else 0.0
        remaining = max(threshold - amount, 0.0)
        return {
            'threshold': threshold,
            'amount': amount,
            'remaining': remaining,
            'reached': remaining <= 0,
            'progress': min(100, int(amount * 100 / threshold)),
        }
