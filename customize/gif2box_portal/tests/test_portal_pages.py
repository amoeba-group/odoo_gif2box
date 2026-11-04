"""The account pages, the sign-in pages and the thank-you page, through
HTTP. Everything is rolled back: the customer is created by the test and
follows existing orders (no order is created: sequences are not rolled
back)."""
from odoo import Command
from odoo.http import root
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPortalPages(HttpCase):

    def setUp(self):
        super().setUp()
        self.orders = self.env['sale.order'].search([('state', '=', 'sale')], order='date_order desc', limit=4)
        if not self.orders:
            self.skipTest("No confirmed order in this database.")
        self.user = self.env['res.users'].create({
            'name': 'Test Customer',
            'login': 'g2b-portal-test@example.com',
            'email': 'g2b-portal-test@example.com',
            'password': 'g2b-portal-test-Pass1',
            # The website's language: no /en/ in front of the URLs.
            'lang': 'vi_VN',
            'groups_id': [Command.set([self.env.ref('base.group_portal').id])],
        })
        self.orders.message_subscribe(partner_ids=self.user.partner_id.ids)

    def _sign_in(self):
        self.authenticate('g2b-portal-test@example.com', 'g2b-portal-test-Pass1')

    def test_account_overview(self):
        self._sign_in()
        page = self.url_open('/my')
        self.assertEqual(page.status_code, 200)
        self.assertIn('o_g2b_acc_stats', page.text)
        self.assertIn('o_g2b_oc', page.text)
        # Odoo's tiles are gone: no quotations, invoices, "Connection & Security".
        self.assertNotIn('o_portal_docs', page.text)
        self.assertNotIn('/my/invoices', page.text)
        self.assertNotIn('/my/quotes', page.text)
        # The password is still one click away.
        self.assertIn('href="/my/security"', page.text)

    def test_orders_list_and_redirect(self):
        self._sign_in()
        page = self.url_open('/my/orders')
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.text.count('class="o_g2b_oc '), len(self.orders))
        order = self.orders[0]
        self.assertIn('/order/track/%s?access_token=' % order.id, page.text)
        # A tab keeps only its orders.
        state = order.g2b_tracking_state
        tab = {'placed': 'processing', 'confirmed': 'processing', 'preparing': 'processing',
               'shipping': 'shipping', 'delivered': 'delivered'}[state]
        self.assertIn(order.name, self.url_open('/my/orders?status=%s' % tab).text)

        # The order's portal page leads to its tracking page...
        response = self.url_open('/my/orders/%s' % order.id, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn('/order/track/%s?access_token=' % order.id, response.headers['Location'])
        # ...with a guest's token too, and its PDF is still the PDF.
        token = order._portal_ensure_token()
        self.authenticate(None, None)
        response = self.url_open('/my/orders/%s?access_token=%s' % (order.id, token), allow_redirects=False)
        self.assertIn('/order/track/%s?access_token=%s' % (order.id, token), response.headers['Location'])
        pdf = self.url_open('/my/orders/%s?access_token=%s&report_type=pdf' % (order.id, token))
        self.assertEqual(pdf.status_code, 200)

    def test_account_details_and_security(self):
        self._sign_in()
        details = self.url_open('/my/account')
        self.assertEqual(details.status_code, 200)
        self.assertIn('o_g2b_acc_form', details.text)
        self.assertIn('o_g2b_acc_nav', details.text)
        self.assertEqual(self.url_open('/my/security').status_code, 200)

    def test_sign_in_pages(self):
        for url in ('/web/login', '/web/signup', '/web/reset_password'):
            page = self.url_open(url)
            self.assertEqual(page.status_code, 200, url)
            self.assertIn('o_g2b_auth_card', page.text, url)
            self.assertIn('o_g2b_auth_title', page.text, url)
        # Signing in still works.
        page = self.url_open('/web/login')
        csrf = page.text.split('name="csrf_token" value="')[1].split('"')[0]
        response = self.url_open('/web/login', data={
            'login': 'g2b-portal-test@example.com', 'password': 'g2b-portal-test-Pass1',
            'csrf_token': csrf, 'redirect': '/my'})
        self.assertIn('o_g2b_acc_stats', response.text)

    def test_thank_you_page(self):
        order = self.orders[0]
        self.authenticate(None, None)
        self.session['sale_last_order_id'] = order.id
        root.session_store.save(self.session)
        page = self.url_open('/shop/confirmation')
        self.assertEqual(page.status_code, 200)
        self.assertIn('o_g2b_ty_hero', page.text)
        self.assertIn(order.name, page.text)
        # What the analytics read.
        self.assertIn('oe_website_sale_tx_status', page.text)
        self.assertIn('data-order-tracking-info', page.text)
        self.assertIn('/order/track/%s?access_token=' % order.id, page.text)
