# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, models
from odoo.http import request

# Session keys of a "Buy now" in progress: the order holding the one product,
# and the cart it displaced, to be put back once the order is done with.
BUY_NOW_ORDER_KEY = 'gif2box_buy_now_order_id'
PARKED_CART_KEY = 'gif2box_parked_cart_id'


class Website(models.Model):
    _inherit = 'website'

    def _gif2box_start_buy_now(self):
        """Set the visitor's cart aside and make a new, empty order current.

        "Buy now" checks out the one product on its own. The website knows a
        single current order, the one in the session, so the cart is moved out
        of the way rather than added to, and put back by `_gif2box_end_buy_now`.
        """
        self.ensure_one()
        # Pressed twice, or again on another product: start over, so the new
        # order holds the new product alone.
        self._gif2box_end_buy_now()

        cart_sudo = self.sale_get_order()
        if cart_sudo and cart_sudo.state == 'draft' and cart_sudo.order_line:
            request.session[PARKED_CART_KEY] = cart_sudo.id

        # Created directly: `sale_get_order(force_create=True)` would hand a
        # signed-in customer their saved cart back instead of a new order.
        partner_sudo = self.env.user.partner_id
        order_sudo = self.env['sale.order'].sudo().with_user(SUPERUSER_ID).create({
            **self._prepare_sale_order_values(partner_sudo),
            'is_buy_now_order': True,
        })
        request.session['sale_order_id'] = order_sudo.id
        request.session[BUY_NOW_ORDER_KEY] = order_sudo.id

    def _gif2box_show_parked_cart_quantity(self):
        """Keep the header's cart counter on the cart, not the buy-now order.

        The counter reads the session's quantity, which Odoo sets from
        whichever order was just added to. Called once the buy-now product is
        in; nothing on the checkout pages sets it again.
        """
        parked_id = request.session.get(PARKED_CART_KEY)
        parked_sudo = self.env['sale.order'].sudo().browse(parked_id).exists() if parked_id else None
        request.session['website_sale_cart_quantity'] = parked_sudo.cart_quantity if parked_sudo else 0

    def _gif2box_end_buy_now(self):
        """Put back the cart set aside by "Buy now", if one is in progress.

        The buy-now order is deleted when nothing was paid on it: it was only
        ever a vehicle for one checkout. Once a payment exists it stays, as any
        order would.
        """
        session = request.session
        buy_now_id = session.pop(BUY_NOW_ORDER_KEY, None)
        parked_id = session.pop(PARKED_CART_KEY, None)
        if not buy_now_id:
            return

        SaleOrder = self.env['sale.order'].sudo()
        buy_now_sudo = SaleOrder.browse(buy_now_id).exists()
        if buy_now_sudo and buy_now_sudo.state == 'draft' and not buy_now_sudo.transaction_ids:
            buy_now_sudo.unlink()

        # Only take the session's cart over if it is still the buy-now order
        # (or nothing): anything else was put there since, and wins.
        if session.get('sale_order_id') not in (None, buy_now_id):
            return
        session.pop('sale_order_id', None)
        session.pop('website_sale_cart_quantity', None)

        parked_sudo = SaleOrder.browse(parked_id).exists() if parked_id else SaleOrder
        if parked_sudo and parked_sudo.state == 'draft':
            session['sale_order_id'] = parked_sudo.id
            session['website_sale_cart_quantity'] = parked_sudo.cart_quantity

    def sale_reset(self):
        """Bring the set-aside cart back when the buy-now order is finished.

        Odoo resets the session's order once the order is paid (or its
        payment abandoned) and when the order is emptied; for a buy-now order
        that is the moment the customer's own cart is theirs again.
        """
        super().sale_reset()
        if request.session.get(BUY_NOW_ORDER_KEY):
            self._gif2box_end_buy_now()
