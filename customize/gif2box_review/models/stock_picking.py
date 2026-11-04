from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _g2b_thank_cards(self):
        """The cards of the orders these delivery orders ship: the card is
        packed with the parcel, so the packer prints it from here."""
        return self.sale_id._g2b_thank_cards()

    def action_g2b_print_thank_cards(self):
        self.sale_id.order_line._g2b_ensure_review_code()
        return self.env.ref('gif2box_review.action_report_thank_card_picking').report_action(self)
