# -*- coding: utf-8 -*-
import logging

import psycopg2

from odoo import http
from odoo.http import request

from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo.addons.website_sale.controllers.main import WebsiteSale

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
