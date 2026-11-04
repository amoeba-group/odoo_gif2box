from odoo import _, models

# How each step of an order looks on its card: under way, on the road,
# arrived, cancelled.
STATUS_TONES = {
    'placed': 'progress',
    'confirmed': 'progress',
    'preparing': 'progress',
    'shipping': 'shipping',
    'delivered': 'done',
    'cancelled': 'cancel',
}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _g2b_status_label(self):
        self.ensure_one()
        return dict(self._fields['g2b_tracking_state']._description_selection(self.env)).get(
            self.g2b_tracking_state, '')

    def _g2b_status_tone(self):
        self.ensure_one()
        return STATUS_TONES.get(self.g2b_tracking_state, 'progress')

    def _g2b_card_summary(self):
        """What an order's card says about its products: the first one's
        name, how many more, and up to three pictures."""
        self.ensure_one()
        lines = self._g2b_display_lines()
        more = len(lines) - 1
        return {
            'lines': lines,
            'images': [line['image'] for line in lines[:3]],
            'extra_images': max(len(lines) - 3, 0),
            'first': lines[0]['name'] if lines else '',
            'more': _("and %s more", more) if more > 0 else '',
        }

    def _g2b_thank_you_texts(self):
        """The thank-you page's sentences that hold a name, translated
        whole."""
        self.ensure_one()
        buyer = self._g2b_giver_name()
        recipient = self._g2b_recipient_name()
        self_gift = self._g2b_recipient_is_buyer() or not recipient
        return {
            'title': _("Thank you, %s!", buyer) if buyer else _("Thank you!"),
            'lead': _("Your order is in good hands: we are getting it ready with care.") if self_gift
            else _("Your gift for %s is in good hands: we are getting it ready with care.", recipient),
            'card': _("%s will find a thank-you card in the box. By scanning its QR code, they can "
                      "send you a thank-you note: you will read it on your order.", recipient),
        }
