from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.website_sale_wishlist.controllers.main import WebsiteSaleWishlist

ORDERS_PER_PAGE = 10

# The tabs of "My orders": key, the tracking states it shows.
ORDER_TABS = [
    ('all', None),
    ('processing', ('placed', 'confirmed', 'preparing')),
    ('shipping', ('shipping',)),
    ('delivered', ('delivered',)),
    ('cancelled', ('cancelled',)),
]
UNDER_WAY = ('placed', 'confirmed', 'preparing', 'shipping')


class Gif2boxCustomerPortal(CustomerPortal):
    """The account pages as the shop shows them: its own overview and list
    of orders instead of Odoo's tiles and table, and an order's portal page
    traded for its tracking page."""

    def _g2b_orders_domain(self, partner):
        # Odoo's list shows confirmed orders only; cancelled ones are part of
        # a customer's history too.
        return [
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('state', 'in', ('sale', 'cancel')),
        ]

    def _g2b_state_counts(self, domain):
        return dict(request.env['sale.order']._read_group(domain, ['g2b_tracking_state'], ['__count']))

    # --- My account ---------------------------------------------------------

    @http.route()
    def home(self, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        SaleOrder = request.env['sale.order']
        domain = self._g2b_orders_domain(partner)
        counts = self._g2b_state_counts(domain)
        left = SaleOrder.search(domain + [('g2b_tracking_state', 'in', ('shipping', 'delivered'))],
                                order='date_order desc', limit=40)
        # Found with the customer's own access; shown with the shop's, as
        # showing a card writes the order's access token for its link.
        left = left.sudo()
        to_review = left.filtered(lambda o: (o._g2b_review_status() or {}).get('state') == 'todo')
        values.update({
            'page_name': 'home',
            'g2b_order_count': sum(counts.values()),
            'g2b_under_way': sum(counts.get(state, 0) for state in UNDER_WAY),
            'g2b_to_review': to_review,
            'g2b_wishlist_count': len(request.env['product.wishlist'].current()),
            'g2b_recent_orders': SaleOrder.search(domain, order='date_order desc', limit=3).sudo(),
            'g2b_partner': partner,
            'g2b_support_phone': request.env['ir.config_parameter'].sudo().get_param(
                'gif2box_order_tracking.support_phone') or request.website.company_id.phone,
        })
        return request.render('gif2box_portal.account_home', values)

    # --- My orders ----------------------------------------------------------

    @http.route()
    def portal_my_orders(self, page=1, status='all', **kw):
        partner = request.env.user.partner_id
        SaleOrder = request.env['sale.order']
        base = self._g2b_orders_domain(partner)
        counts = self._g2b_state_counts(base)
        labels = {
            'all': _("All"),
            'processing': _("Being prepared"),
            'shipping': _("On its way"),
            'delivered': _("Delivered"),
            'cancelled': _("Cancelled"),
        }
        tabs = []
        states = None
        for key, tab_states in ORDER_TABS:
            count = sum(counts.values()) if tab_states is None else sum(counts.get(s, 0) for s in tab_states)
            if key == status:
                states = tab_states
            # Empty tabs are left out, but for the one being looked at.
            if count or key in ('all', status):
                tabs.append({'key': key, 'label': labels[key], 'count': count, 'active': key == status})
        if status not in dict(ORDER_TABS):
            status = 'all'
            tabs[0]['active'] = True
        domain = base + ([('g2b_tracking_state', 'in', states)] if states else [])
        total = SaleOrder.search_count(domain)
        pager = portal_pager(
            url='/my/orders', url_args={'status': status} if status != 'all' else None,
            total=total, page=page, step=ORDERS_PER_PAGE)
        # Found with the customer's own access; shown with the shop's (see home).
        orders = SaleOrder.search(domain, order='date_order desc', limit=ORDERS_PER_PAGE,
                                  offset=pager['offset']).sudo()
        request.session['my_orders_history'] = orders.ids[:100]
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'order',
            'orders': orders,
            'pager': pager,
            'default_url': '/my/orders',
            'g2b_tabs': tabs,
            'g2b_status': status,
            'g2b_any_order': bool(sum(counts.values())),
        })
        return request.render('gif2box_portal.account_orders', values)

    @http.route()
    def portal_order_page(self, order_id, report_type=None, access_token=None, message=False,
                          download=False, downpayment=None, **kw):
        """An order that has been confirmed is followed on its tracking page:
        the portal's own page, a quotation's, is for accepting and paying,
        which such an order is past. Its PDF stays where it was, and a
        quotation keeps its page."""
        if not report_type and not download:
            try:
                order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
            except (AccessError, MissingError):
                return request.redirect('/my')
            if order_sudo.state in ('sale', 'cancel'):
                return request.redirect(order_sudo._g2b_tracking_url())
        return super().portal_order_page(
            order_id, report_type=report_type, access_token=access_token, message=message,
            download=download, downpayment=downpayment, **kw)


class Gif2boxWishlist(WebsiteSaleWishlist):
    """The wishlist is a tab of the account. A signed-in customer who opens
    it with nothing saved sees it empty, with the way to the shop, instead of
    being sent to the shop. A guest still is sent there, as before."""

    @http.route()
    def get_wishlist(self, count=False, **kw):
        if count or request.env.user._is_public():
            return super().get_wishlist(count=count, **kw)
        wishes = request.env['product.wishlist'].with_context(display_default_code=False).current()
        return request.render('website_sale_wishlist.product_wishlist', {'wishes': wishes})
