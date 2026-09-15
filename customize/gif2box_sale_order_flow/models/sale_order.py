# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    order_payment_date = fields.Datetime(
        string="Ngày thanh toán",
        compute='_compute_order_payment_date',
        store=True,
        copy=False,
        help="Date of the most recent authorized or captured payment transaction "
             "linked to this order.",
    )

    @api.depends('transaction_ids.state', 'transaction_ids.last_state_change')
    def _compute_order_payment_date(self):
        for order in self:
            paid_dates = order.transaction_ids.filtered(
                lambda tx: tx.state in ('authorized', 'done')
            ).mapped('last_state_change')
            order.order_payment_date = max(paid_dates) if paid_dates else False

    def _auto_confirm_new_order(self):
        """Turn a freshly placed eCommerce order into a Sales Order.

        Called at the end of the checkout, once the customer lands on the
        confirmation page. Idempotent: orders that already left the quotation
        stage are skipped, so refreshing the page is harmless.
        """
        for order in self:
            if order.state not in ('draft', 'sent') or not order.order_line:
                continue
            try:
                order.action_confirm()
            except Exception:
                # Never let a confirmation failure break the customer's
                # checkout: the order stays a quotation and is logged instead.
                _logger.exception(
                    "Could not auto-confirm sale order %s (id %s)", order.name, order.id
                )
