import datetime
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# The steps a customer follows, in order. "Cancelled" is not one of them: it
# replaces them.
STEPS = ['placed', 'confirmed', 'preparing', 'shipping', 'delivered']

# The courier's transit times (Việt Tín CPN S07/2025, section I, "Hành trình"):
# within 24 hours in Hồ Chí Minh City's inner city, 24 to 48 hours elsewhere,
# and "1 to 2 days more" out to communes and islands. In working days after
# the day of sending; Sundays do not count.
TRANSIT_DAYS = {'inner': (1, 1), 'near': (1, 2), 'far': (1, 2), 'hub': (1, 2)}
OUTLYING_EXTRA_DAYS = (1, 2)


def _add_working_days(start, days):
    """`start` plus `days` days, Sundays skipped."""
    day = start
    while days > 0:
        day += datetime.timedelta(days=1)
        if day.weekday() != 6:
            days -= 1
    return day


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    g2b_tracking_state = fields.Selection(
        [('placed', 'Placed'),
         ('confirmed', 'Confirmed'),
         ('preparing', 'Being prepared'),
         ('shipping', 'On its way'),
         ('delivered', 'Delivered'),
         ('cancelled', 'Cancelled')],
        string='Tracking Status', compute='_compute_g2b_tracking', store=True,
        help="Where the order stands for the customer, as the tracking page "
             "shows it: on its way once its delivery orders are validated, "
             "delivered once they are marked as delivered.")
    g2b_shipped_at = fields.Datetime(
        string='Shipped On', compute='_compute_g2b_tracking', store=True)
    g2b_delivered_at = fields.Datetime(
        string='Delivered On', compute='_compute_g2b_tracking', store=True)

    def _g2b_outgoing_pickings(self):
        self.ensure_one()
        return self.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state != 'cancel')

    @api.depends('state', 'picking_ids.state', 'picking_ids.date_done',
                 'picking_ids.g2b_delivered_at', 'picking_ids.picking_type_code')
    def _compute_g2b_tracking(self):
        for order in self:
            outgoing = order._g2b_outgoing_pickings()
            shipped = outgoing and all(p.state == 'done' for p in outgoing)
            delivered = shipped and all(p.g2b_delivered_at for p in outgoing)
            if order.state == 'cancel':
                state = 'cancelled'
            elif order.state != 'sale':
                state = 'placed'
            elif delivered:
                state = 'delivered'
            elif shipped:
                state = 'shipping'
            elif outgoing:
                state = 'preparing'
            else:
                state = 'confirmed'
            order.g2b_tracking_state = state
            order.g2b_shipped_at = shipped and max(outgoing.mapped('date_done')) or False
            order.g2b_delivered_at = delivered and max(outgoing.mapped('g2b_delivered_at')) or False

    # --- What the tracking page shows ---------------------------------------

    def _g2b_tracking_url(self, absolute=False):
        """The order's tracking page, with its access token: the link the
        customer keeps, and the one the emails carry."""
        self.ensure_one()
        url = '/order/track/%s?access_token=%s' % (self.id, self._portal_ensure_token())
        return self.get_base_url() + url if absolute else url

    def _g2b_recipient_is_buyer(self):
        self.ensure_one()
        return self.partner_shipping_id.commercial_partner_id == self.partner_id.commercial_partner_id \
            and self.partner_shipping_id.name == self.partner_id.name

    def _g2b_payment(self):
        """(label, state) of how the order is paid: 'paid', 'cod' or 'due'."""
        self.ensure_one()
        tx = self.sudo().get_portal_last_transaction()
        if tx.state == 'done' or self.order_payment_date:
            return _("Paid with %s", tx.provider_id.name) if tx else _("Paid"), 'paid'
        if tx.provider_code == 'cod':
            return _("Cash on delivery"), 'cod'
        return _("Awaiting payment"), 'due'

    def _g2b_shipment(self):
        """The parcel as the courier knows it: carrier, number, link."""
        self.ensure_one()
        done = self._g2b_outgoing_pickings().filtered(lambda p: p.state == 'done')
        picking = done.sorted('date_done')[-1:] if done else self._g2b_outgoing_pickings()[-1:]
        carrier = picking.carrier_id or self.carrier_id
        return {
            'carrier': carrier.g2b_courier_name or carrier.name or '',
            'reference': picking.carrier_tracking_ref or '',
            'url': picking.carrier_tracking_url if picking.carrier_tracking_ref else '',
        }

    def _g2b_eta(self):
        """The courier's delivery window for this address: the number of
        working days after sending and, once sent, the dates. None when
        the delivery method is not priced by distance."""
        self.ensure_one()
        carrier = self.carrier_id
        if carrier.delivery_type != 'gif2box_distance' or self.g2b_tracking_state in ('delivered', 'cancelled'):
            return None
        quote = carrier._g2b_quote(self.partner_shipping_id)
        if not quote:
            return None
        low, high = TRANSIT_DAYS[quote['zone']]
        if quote['surcharged']:
            low, high = low + OUTLYING_EXTRA_DAYS[0], high + OUTLYING_EXTRA_DAYS[1]
        eta = {'low': low, 'high': high, 'from': False, 'to': False}
        if self.g2b_shipped_at:
            sent = fields.Datetime.context_timestamp(self, self.g2b_shipped_at).date()
            eta['from'] = _add_working_days(sent, low)
            eta['to'] = _add_working_days(sent, high)
            # A window already behind us promises nothing: say nothing.
            if eta['to'] < fields.Date.context_today(self):
                return None
        return eta

    def _g2b_display_lines(self):
        """The order's products as the customer bought them: a combo is one
        line, priced at what its items add up to (Odoo puts the price on the
        items and none on the combo), with the items named under it."""
        self.ensure_one()
        lines = self.order_line.filtered(lambda l: not l.display_type and not l.is_delivery)
        result = []
        for line in lines.filtered(lambda l: not l.linked_line_id):
            items = lines.filtered(lambda l: l.linked_line_id == line)
            result.append({
                'line': line,
                'name': line.name_short or line.product_id.name,
                'qty': line.product_uom_qty,
                'price': line.price_total + sum(items.mapped('price_total')),
                'items': [i.product_id.name for i in items],
                'image': self.website_id.image_url(line.product_id, 'image_128')
                         if self.website_id else '/web/image/product.product/%s/image_128' % line.product_id.id,
            })
        return result

    def _g2b_delivery_amount(self):
        self.ensure_one()
        return sum(self.order_line.filtered('is_delivery').mapped('price_total'))

    def _g2b_tz(self):
        return self.website_id.company_id.partner_id.tz or self.env.user.tz or 'Asia/Ho_Chi_Minh'

    @staticmethod
    def _g2b_mask_phone(phone):
        """"0901 234 567" as "090****567": enough for the recipient to
        recognise, not enough to copy."""
        digits = ''.join(c for c in phone or '' if c.isdigit())
        if len(digits) < 7:
            return phone or ''
        return digits[:3] + '****' + digits[-3:]

    def _g2b_recipient_name(self):
        self.ensure_one()
        return self.partner_shipping_id.name or self.partner_id.name or ''

    def _g2b_tracking_steps(self):
        """The five steps, each 'done', 'current' or 'todo', with its date
        and a line of detail."""
        self.ensure_one()
        state = self.g2b_tracking_state
        current = STEPS.index(state) if state in STEPS else 0
        shipment = self._g2b_shipment()
        payment_label, _payment_state = self._g2b_payment()
        recipient = self._g2b_recipient_name()
        steps = [
            {'key': 'placed', 'title': _("Order placed"), 'date': self.date_order,
             'note': _("We have received your order.")},
            {'key': 'confirmed', 'title': _("Confirmed"),
             'date': self.state == 'sale' and (self.order_payment_date or self.date_order),
             'note': payment_label},
            {'key': 'preparing', 'title': _("Gift being prepared"), 'date': False,
             'note': _("Checked, boxed and wrapped with care.")},
            {'key': 'shipping', 'title': _("On its way"), 'date': self.g2b_shipped_at,
             'note': shipment['carrier'] and _("Handed to %s", shipment['carrier']) or _("Handed to the courier.")},
            {'key': 'delivered', 'title': _("Delivered"), 'date': self.g2b_delivered_at,
             'note': _("Received by %s", recipient) if recipient else _("Received.")},
        ]
        for index, step in enumerate(steps):
            if index < current or (index == current and state == 'delivered'):
                step['status'] = 'done'
            elif index == current:
                step['status'] = 'current'
            else:
                step['status'] = 'todo'
            # A date only for what has happened.
            if step['status'] == 'todo':
                step['date'] = False
        return steps

    # --- Notifications -----------------------------------------------------

    def _g2b_notify(self, kind):
        """Email the buyer that the order is on its way ('shipped') or has
        been delivered ('delivered'), and keep it in the order's chatter."""
        template = self.env.ref('gif2box_order_tracking.mail_template_order_%s' % kind,
                                raise_if_not_found=False)
        if not template:
            return
        for order in self:
            if not order.partner_id.email:
                order.message_post(body=_(
                    "No email address on the customer: the \"%s\" notification was not sent.",
                    template.name))
                continue
            try:
                order.with_context(lang=order.partner_id.lang).message_post_with_source(
                    template,
                    email_layout_xmlid='mail.mail_notification_light',
                    subtype_xmlid='mail.mt_comment',
                    partner_ids=order.partner_id.ids,
                )
            except Exception:
                # A notification must never undo a delivery being recorded.
                _logger.exception("Could not send the %s notification of %s", kind, order.name)

    # --- Backend actions ---------------------------------------------------

    def action_g2b_mark_delivered(self):
        pickings = self.mapped(lambda o: o._g2b_outgoing_pickings()).filtered(
            lambda p: p.state == 'done' and not p.g2b_delivered_at)
        if not pickings:
            raise UserError(_("There is nothing to mark as delivered: an order is "
                              "delivered once its delivery orders have been "
                              "validated (shipped)."))
        return pickings.action_g2b_mark_delivered()

    def action_g2b_open_tracking(self):
        """The customer's tracking page, for the shop to look at or to send
        the link by chat."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self._g2b_tracking_url(),
            'target': 'new',
        }
