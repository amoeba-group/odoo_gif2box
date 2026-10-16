# -*- coding: utf-8 -*-
import logging

import psycopg2

from odoo import http
from odoo.http import request, route

from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo.addons.website_sale.controllers.combo_configurator import (
    WebsiteSaleComboConfiguratorController,
)
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.controllers.product_configurator import (
    WebsiteSaleProductConfiguratorController,
)

_logger = logging.getLogger(__name__)


class Gif2boxPaymentPostProcessing(PaymentPostProcessing):

    @http.route()
    def display_status(self, **kwargs):
        """Send the customer straight to the landing page, skipping the status page.

        The status page is only a shell whose JavaScript polls
        ``/payment/status/poll``, and that poll is what actually runs
        ``_post_process()`` (order confirmation, invoicing, emails). Since the
        page is no longer rendered, the post-processing has to run here before
        redirecting, otherwise the whole payment pipeline would be skipped.

        Anything unexpected falls back to the standard status page, which keeps
        its own retry mechanism.
        """
        monitored_tx = self._get_monitored_transaction()
        if not monitored_tx or not monitored_tx.landing_route:
            return super().display_status(**kwargs)

        if not monitored_tx.is_post_processed:
            try:
                monitored_tx._post_process()
            except (psycopg2.OperationalError, psycopg2.IntegrityError):
                # The cursor could not be committed; let the status page retry.
                request.env.cr.rollback()
                return super().display_status(**kwargs)
            except Exception:
                # Post-processing is best-effort here: a failure in a late step
                # (invoice PDF rendering, mailing, ...) must not strand the
                # customer on the status page. The order itself is confirmed
                # again, in a fresh transaction, by the confirmation page.
                request.env.cr.rollback()
                _logger.exception(
                    "Error while post-processing transaction with id %s;"
                    " redirecting to %s anyway",
                    monitored_tx.id,
                    monitored_tx.landing_route,
                )

        return request.redirect(monitored_tx.landing_route)


class Gif2boxWebsiteSale(WebsiteSale):

    @http.route()
    def shop_payment_confirmation(self, **post):
        """Confirm the order backing the confirmation page."""
        order_id = request.session.get('sale_last_order_id')
        if order_id:
            order = request.env['sale.order'].sudo().browse(order_id).exists()
            order._auto_confirm_new_order()
        return super().shop_payment_confirmation(**post)

    # === "BUY NOW" === #
    #
    # The product page's "Buy now" posts to `/shop/cart/update` with `express`
    # set, a flag Odoo sends but never reads: the product went into the cart
    # and the customer landed on the cart page. Here it checks the product out
    # on its own, in an order of its own, and leaves the cart untouched; see
    # `Website._gif2box_start_buy_now`.
    #
    # Going back to the cart, or adding anything to it, abandons the buy-now
    # order and brings the cart back.

    @http.route()
    def cart(self, **post):
        request.website._gif2box_end_buy_now()
        return super().cart(**post)

    @http.route()
    def cart_update(self, product_id, add_qty=1, set_qty=0, express=False, **kwargs):
        if not _is_set(express):
            request.website._gif2box_end_buy_now()
            return super().cart_update(product_id, add_qty=add_qty, set_qty=set_qty, **kwargs)

        request.website._gif2box_start_buy_now()
        super().cart_update(product_id, add_qty=add_qty, set_qty=set_qty, **kwargs)
        request.website._gif2box_show_parked_cart_quantity()
        return request.redirect('/shop/checkout?try_skip_step=true')

    @http.route()
    def cart_update_json(self, *args, **kwargs):
        request.website._gif2box_end_buy_now()
        return super().cart_update_json(*args, **kwargs)


class Gif2boxProductConfigurator(WebsiteSaleProductConfiguratorController):

    @route()
    def website_sale_product_configurator_update_cart(self, *args, **kwargs):
        request.website._gif2box_end_buy_now()
        return super().website_sale_product_configurator_update_cart(*args, **kwargs)


class Gif2boxComboConfigurator(WebsiteSaleComboConfiguratorController):

    @route()
    def website_sale_combo_configurator_update_cart(self, *args, gif2box_buy_now=False, **kwargs):
        """Combo products are added by this route, not `/shop/cart/update`,
        even from "Buy now"; `buy_now.js` sends the flag and does the
        redirection to the checkout."""
        if not gif2box_buy_now:
            request.website._gif2box_end_buy_now()
            return super().website_sale_combo_configurator_update_cart(*args, **kwargs)

        request.website._gif2box_start_buy_now()
        values = super().website_sale_combo_configurator_update_cart(*args, **kwargs)
        request.website._gif2box_show_parked_cart_quantity()
        return values


def _is_set(flag):
    """`express` arrives as a form field: the string "true", or absent."""
    return str(flag).lower() in ('1', 'true')
