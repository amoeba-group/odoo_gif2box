from odoo import models
from odoo.tools.translate import LazyTranslate

# Bound to this module, so the strings below are looked up in this module's
# own `.po` files rather than `website_sale`'s. That is the whole point of
# renaming them here: Odoo already ships a Vietnamese translation for both of
# the labels being replaced, and a module update leaves an existing
# translation alone unless the server runs with `--i18n-overwrite`, which is
# all-or-nothing across every module. New source strings in our own module
# have no translation to collide with.
_lt = LazyTranslate(__name__)


class Website(models.Model):
    _inherit = 'website'

    def _get_checkout_step_list(self):
        """Relabel the first step of the checkout.

        Odoo calls it "Review Order", translated as "Xem lại đơn hàng", and
        its button "Checkout", translated as "Check-out" -- which is English
        with a hyphen in it, not Vietnamese.

        The step is the cart, and the page it links to says so in its own
        heading, so the step is named after it. The button is given the
        phrase Vietnamese shops actually use for it.
        """
        steps = super()._get_checkout_step_list()

        # Mirrors the condition in `website_sale`: when an account is
        # required, this button signs the shopper in rather than taking them
        # to the delivery step, and its label has to keep saying so.
        redirect_to_sign_in = (
            self.account_on_checkout == 'mandatory' and self.is_public_user()
        )

        for xmlids, values in steps:
            if 'website_sale.cart' not in xmlids:
                continue
            values['name'] = _lt("Cart")
            if not redirect_to_sign_in:
                values['main_button'] = _lt("Proceed to Checkout")

        return steps
