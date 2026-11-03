import re
import time

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

# Wrong guesses allowed per visitor before the lookup asks them to wait: an
# order number is a short sequence, and the phone or email beside it is what
# keeps someone else's order private.
MAX_FAILED_LOOKUPS = 8
LOOKUP_WINDOW = 15 * 60


def _digits(text):
    return re.sub(r'\D', '', text or '')


class Gif2boxOrderTracking(CustomerPortal):

    # --- Lookup ------------------------------------------------------------

    @http.route('/order/track', type='http', auth='public', website=True,
                methods=['GET', 'POST'], sitemap=True)
    def order_track_lookup(self, order_ref='', contact='', **kw):
        """Find an order by its number and the buyer's or the recipient's
        phone or email, and go to its tracking page. Signed-in customers
        find their phone (or email) already filled in, and see their
        recent orders."""
        values = {'order_ref': order_ref, 'contact': contact, 'contact_prefilled': False, 'error': False}
        if not contact and not request.env.user._is_public():
            partner = request.env.user.partner_id
            values['contact'] = partner.phone or partner.mobile or partner.email or ''
            values['contact_prefilled'] = bool(values['contact'])
        if request.httprequest.method == 'POST':
            if self._g2b_too_many_failures():
                values['error'] = 'wait'
            else:
                order = self._g2b_find_order(order_ref, contact)
                if order:
                    return request.redirect(order._g2b_tracking_url())
                self._g2b_record_failure()
                values['error'] = 'not_found'
        if not request.env.user._is_public():
            partner = request.env.user.partner_id.commercial_partner_id
            values['recent_orders'] = request.env['sale.order'].search([
                ('partner_id', 'child_of', partner.id),
                ('state', 'in', ('sale', 'cancel')),
            ], order='date_order desc', limit=5)
        return request.render('gif2box_order_tracking.order_track_lookup', values)

    def _g2b_find_order(self, order_ref, contact):
        ref = (order_ref or '').strip().upper().replace(' ', '')
        contact = (contact or '').strip()
        if not ref or not contact:
            return None
        order = request.env['sale.order'].sudo().search(
            [('name', '=ilike', ref), ('state', 'in', ('sale', 'sent', 'cancel'))], limit=1)
        if not order:
            return None
        people = order.partner_id | order.partner_shipping_id | order.partner_invoice_id
        if '@' in contact:
            emails = {e.strip().lower() for e in people.mapped('email') if e}
            return order if contact.lower() in emails else None
        # The last nine digits: "0901 234 567", "+84 901 234 567" and
        # "84901234567" are the same number.
        typed = _digits(contact)[-9:]
        if len(typed) < 9:
            return None
        phones = {_digits(p)[-9:] for p in people.mapped('phone') + people.mapped('mobile') if p}
        return order if typed in phones else None

    def _g2b_recent_failures(self):
        now = time.time()
        return [t for t in request.session.get('g2b_track_failures', []) if now - t < LOOKUP_WINDOW]

    def _g2b_too_many_failures(self):
        return len(self._g2b_recent_failures()) >= MAX_FAILED_LOOKUPS

    def _g2b_record_failure(self):
        request.session['g2b_track_failures'] = self._g2b_recent_failures() + [time.time()]

    # --- Tracking page -----------------------------------------------------

    @http.route('/order/track/<int:order_id>', type='http', auth='public', website=True,
                sitemap=False)
    def order_track(self, order_id, access_token=None, **kw):
        """One order's tracking page: the link in the emails and on the
        confirmation page, opened with the order's access token, or by a
        signed-in customer whose order it is."""
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/order/track')
        return request.render('gif2box_order_tracking.order_track_page', {
            'order': order_sudo,
            'tracking_url': order_sudo._g2b_tracking_url(absolute=True),
        })
