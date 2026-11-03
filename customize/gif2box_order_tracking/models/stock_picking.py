from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    g2b_delivered_at = fields.Datetime(
        string='Delivered to Recipient', copy=False, readonly=True, tracking=True,
        help="When the recipient received the parcel, as the courier reported "
             "it. Set with \"Mark as delivered\"; the buyer is emailed then.")
    g2b_shipped_notified = fields.Boolean(copy=False, readonly=True)

    def _action_done(self):
        res = super()._action_done()
        self._g2b_notify_shipped()
        return res

    def _g2b_notify_shipped(self):
        """Once the last delivery order of a web order is validated, the
        parcel has left: tell the buyer, once."""
        pickings = self.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state == 'done'
            and not p.g2b_shipped_notified and p.sale_id.website_id)
        if not pickings:
            return
        pickings.g2b_shipped_notified = True
        for order in pickings.sale_id:
            if order.g2b_tracking_state == 'shipping':
                order._g2b_notify('shipped')

    def action_g2b_mark_delivered(self):
        """The courier reports the parcel received: record it, and once an
        order's every delivery order is, tell the buyer."""
        todo = self.filtered(lambda p: p.picking_type_code == 'outgoing'
                             and p.state == 'done' and not p.g2b_delivered_at)
        if not todo:
            raise UserError(_("Only delivery orders that have been validated (shipped) "
                              "and not yet marked as delivered can be marked as delivered."))
        todo.g2b_delivered_at = fields.Datetime.now()
        notified = self.env['sale.order']
        for order in todo.sale_id:
            if order.g2b_tracking_state == 'delivered':
                order._g2b_notify('delivered')
                notified |= order
        if notified:
            message = _("%(count)s order(s) marked as delivered: %(names)s. The buyers have been emailed.",
                        count=len(notified), names=', '.join(notified.mapped('name')))
        else:
            message = _("%s delivery order(s) marked as delivered.", len(todo))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': message,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
