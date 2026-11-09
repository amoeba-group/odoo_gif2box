"""Sign in with Google and Facebook, through HTTP, the providers played by
a fake (`_g2b_http`): no call leaves the server. Everything is rolled back."""
import hashlib
import hmac
import json
import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

from odoo import Command
from odoo.exceptions import AccessDenied
from odoo.http import root
from odoo.tests import HttpCase, tagged

GOOGLE_SECRET = 'test-google-secret'
FACEBOOK_SECRET = 'test-facebook-secret'


@tagged('post_install', '-at_install')
class TestSocialLogin(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Provider = cls.env['auth.oauth.provider']
        cls.google = Provider._g2b_get('google')
        cls.facebook = Provider._g2b_get('facebook')
        cls.google.write({'enabled': True, 'client_id': 'test-google-id', 'g2b_client_secret': GOOGLE_SECRET})
        cls.facebook.write({'enabled': True, 'client_id': 'test-facebook-id', 'g2b_client_secret': FACEBOOK_SECRET})
        cls.website = cls.env['website'].get_current_website()
        cls.website.auth_signup_uninvited = 'b2c'
        cls.portal_group = cls.env.ref('base.group_portal')

    def setUp(self):
        super().setUp()
        # What the providers answer; a test changes the profile it needs.
        self.google_profile = {'sub': 'g-1001', 'email': 'New.Customer@Example.com',
                               'email_verified': True, 'name': 'Khách Mới'}
        self.facebook_profile = {'id': 'f-2002', 'email': 'fb.customer@example.com', 'name': 'Bạn Facebook'}
        self.http_calls = []

        def fake_http(provider, method, url, **kwargs):
            return self._fake_http(method, url, **kwargs)
        patcher = patch.object(type(self.env['auth.oauth.provider']), '_g2b_http', fake_http)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- The fake providers -------------------------------------------------------

    def _fake_http(self, method, url, **kwargs):
        self.http_calls.append(url)
        params = kwargs.get('params') or {}
        data = kwargs.get('data') or {}
        if url == 'https://oauth2.googleapis.com/token':
            ok = (method == 'POST' and data.get('code') == 'good-code'
                  and data.get('client_id') == 'test-google-id'
                  and data.get('client_secret') == GOOGLE_SECRET
                  and data.get('grant_type') == 'authorization_code'
                  and data.get('redirect_uri', '').endswith('/social-login/google/callback'))
            return {'access_token': 'g-token'} if ok else {'error': 'invalid_grant'}
        if url == 'https://openidconnect.googleapis.com/v1/userinfo':
            if kwargs.get('headers', {}).get('Authorization') != 'Bearer g-token':
                return {'error': 'invalid_token'}
            return self.google_profile
        if url == 'https://graph.facebook.com/oauth/access_token':
            ok = (params.get('code') == 'good-code' and params.get('client_id') == 'test-facebook-id'
                  and params.get('client_secret') == FACEBOOK_SECRET
                  and params.get('redirect_uri', '').endswith('/social-login/facebook/callback'))
            return {'access_token': 'f-token'} if ok else {'error': {'message': 'Invalid code'}}
        if url == 'https://graph.facebook.com/me?fields=id,name,email':
            proof = hmac.new(FACEBOOK_SECRET.encode(), b'f-token', hashlib.sha256).hexdigest()
            if params.get('access_token') != 'f-token' or params.get('appsecret_proof') != proof:
                return {'error': {'message': 'Invalid appsecret_proof'}}
            return self.facebook_profile
        raise AssertionError("Unexpected call to %s" % url)

    # --- Helpers --------------------------------------------------------------------

    def _session_uid(self):
        sid = self.opener.cookies.get('session_id')
        return sid and root.session_store.get(sid).uid

    def _start(self, kind, redirect=None):
        url = '/social-login/%s' % kind + ('?redirect=%s' % redirect if redirect else '')
        response = self.url_open(url, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        location = urlsplit(response.headers['Location'])
        return location, {k: v[0] for k, v in parse_qs(location.query).items()}

    def _sign_in(self, kind, redirect=None, code='good-code', state=None):
        _location, params = self._start(kind, redirect)
        response = self.url_open('/social-login/%s/callback?code=%s&state=%s' % (
            kind, code, state or params['state']), allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        return urlsplit(response.headers['Location'])

    def _error_of(self, location):
        self.assertEqual(location.path, '/web/login')
        return parse_qs(location.query).get('g2b_error', [None])[0]

    def _user(self, login):
        return self.env['res.users'].with_context(active_test=False).search([('login', '=ilike', login)])

    # --- Tests ------------------------------------------------------------------------

    def test_setup(self):
        self.assertEqual(self.google, self.env.ref('auth_oauth.provider_google'))
        self.assertEqual(self.facebook, self.env.ref('auth_oauth.provider_facebook'))
        self.assertEqual(self.google.g2b_token_endpoint, 'https://oauth2.googleapis.com/token')
        self.assertFalse(self.env.ref('auth_oauth.provider_openerp').enabled)

    def test_buttons(self):
        page = self.url_open('/web/login?redirect=/shop/cart').text
        self.assertIn('o_g2b_social_btn_google', page)
        self.assertIn('href="/social-login/google?redirect=%2Fshop%2Fcart"', page)
        self.assertIn('href="/social-login/facebook?redirect=%2Fshop%2Fcart"', page)
        # Odoo's own list, with its links to /auth_oauth/signin, is gone.
        self.assertNotIn('o_auth_oauth_providers', page)
        self.assertNotIn('/auth_oauth/signin', page)
        self.assertIn('href="/social-login/google"', self.url_open('/web/signup').text)
        self.assertNotIn('o_g2b_social_btn', self.url_open('/web/reset_password').text)
        # A redirect off the site is dropped.
        self.assertIn('href="/social-login/google"', self.url_open('/web/login?redirect=https://evil.example').text)

        # No secret, no button.
        self.facebook.g2b_client_secret = False
        page = self.url_open('/web/login').text
        self.assertIn('o_g2b_social_btn_google', page)
        self.assertNotIn('o_g2b_social_btn_facebook', page)
        self.assertEqual(self.url_open('/social-login/facebook', allow_redirects=False).status_code, 404)
        self.google.enabled = False
        self.assertNotIn('o_g2b_social', self.url_open('/web/login').text)

    def test_in_app_browser(self):
        page = self.url_open('/web/login', headers={
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Zalo iOS/24.1'}).text
        self.assertIn('is-blocked', page)
        self.assertNotIn('href="/social-login/google"', page)
        self.assertIn('href="/social-login/facebook"', page)

    def test_start(self):
        location, params = self._start('google', '/shop/cart')
        self.assertEqual('%s://%s%s' % (location.scheme, location.netloc, location.path),
                         'https://accounts.google.com/o/oauth2/v2/auth')
        self.assertEqual(params['response_type'], 'code')
        self.assertEqual(params['client_id'], 'test-google-id')
        self.assertTrue(params['redirect_uri'].endswith('/social-login/google/callback'))
        self.assertEqual(params['scope'], 'openid email profile')
        self.assertEqual(params['prompt'], 'select_account')
        self.assertGreater(len(params['state']), 30)
        # The secret never goes to the browser.
        self.assertNotIn(GOOGLE_SECRET, location.query)

        location, params = self._start('facebook')
        self.assertEqual(location.netloc, 'www.facebook.com')
        self.assertNotIn('auth_type', params)
        response = self.url_open('/social-login/facebook?rerequest=1', allow_redirects=False)
        self.assertIn('auth_type=rerequest', response.headers['Location'])

    def test_new_customer(self):
        location = self._sign_in('google', '/shop/cart')
        self.assertEqual(location.path, '/shop/cart')
        user = self._user('new.customer@example.com')
        self.assertEqual(len(user), 1)
        self.assertEqual(user.login, 'new.customer@example.com')
        self.assertEqual(user.name, 'Khách Mới')
        self.assertTrue(user.share, "A customer account, not a staff one")
        self.assertEqual((user.oauth_provider_id, user.oauth_uid), (self.google, 'g-1001'))
        self.assertEqual(self._session_uid(), user.id)
        self.assertTrue(self.env['mail.mail'].search([('email_to', 'ilike', 'new.customer@example.com')]),
                        "The welcome email of the sign-up page")

        # Again, from another browser: the same account, to their account page.
        self.opener.cookies.clear()
        self.google_profile['email'] = 'changed@example.com'
        location = self._sign_in('google')
        self.assertEqual(location.path, '/my')
        self.assertEqual(self._session_uid(), user.id)
        self.assertFalse(self._user('changed@example.com'))

    def test_existing_customer_is_linked(self):
        customer = self.env['res.users'].create({
            'name': 'Linh', 'login': 'FB.Customer@example.com', 'email': 'FB.Customer@example.com',
            'password': 'linh-Pass-1234', 'groups_id': [Command.set(self.portal_group.ids)],
        })
        location = self._sign_in('facebook')
        self.assertEqual(location.path, '/my')
        self.assertEqual(self._session_uid(), customer.id)
        self.assertEqual((customer.oauth_provider_id, customer.oauth_uid), (self.facebook, 'f-2002'))
        self.assertEqual(len(self._user('fb.customer@example.com')), 1)
        # The password still works.
        self.opener.cookies.clear()
        self.authenticate('FB.Customer@example.com', 'linh-Pass-1234')
        self.assertEqual(self._session_uid(), customer.id)

    def test_staff_account_is_not_taken(self):
        staff = self.env['res.users'].create({
            'name': 'Staff', 'login': 'staff@example.com', 'email': 'staff@example.com',
            'groups_id': [Command.set(self.env.ref('base.group_user').ids)],
        })
        self.google_profile['email'] = 'staff@example.com'
        location = self._sign_in('google')
        self.assertEqual(self._error_of(location), 'staff')
        self.assertFalse(self._session_uid())
        self.assertFalse(staff.oauth_uid)
        page = self.url_open('%s?%s' % (location.path, location.query)).text
        self.assertIn('o_g2b_social_error', page)

    def test_facebook_without_email(self):
        del self.facebook_profile['email']
        location = self._sign_in('facebook', '/shop/checkout')
        self.assertEqual(self._error_of(location), 'no_email')
        self.assertFalse(self._session_uid())
        page = self.url_open('%s?%s' % (location.path, location.query)).text
        self.assertIn('o_g2b_social_error', page)
        self.assertIn('/social-login/facebook?rerequest=1&amp;redirect=%2Fshop%2Fcheckout', page)

    def test_google_email_not_verified(self):
        self.google_profile['email_verified'] = False
        self.assertEqual(self._error_of(self._sign_in('google')), 'unverified')
        self.assertFalse(self._user('new.customer@example.com'))

    def test_sign_up_closed(self):
        self.website.auth_signup_uninvited = 'b2b'
        self.assertEqual(self._error_of(self._sign_in('google')), 'signup_closed')
        self.assertFalse(self._user('new.customer@example.com'))

    def test_closed_account(self):
        customer = self.env['res.users'].create({
            'name': 'Gone', 'login': 'new.customer@example.com',
            'groups_id': [Command.set(self.portal_group.ids)],
        })
        customer.active = False
        self.assertEqual(self._error_of(self._sign_in('google')), 'closed')
        self.assertFalse(self._session_uid())

    def test_state_is_checked(self):
        # Forged, or from another browser.
        self.assertEqual(self._error_of(self._sign_in('google', state='forged')), 'expired')
        self.assertFalse(self._session_uid())
        # No sign-in started at all.
        response = self.url_open('/social-login/google/callback?code=good-code&state=x', allow_redirects=False)
        self.assertEqual(self._error_of(urlsplit(response.headers['Location'])), 'expired')
        # Started for Google, back from Facebook.
        _location, params = self._start('google')
        response = self.url_open('/social-login/facebook/callback?code=good-code&state=%s' % params['state'],
                                 allow_redirects=False)
        self.assertEqual(self._error_of(urlsplit(response.headers['Location'])), 'expired')
        self.assertFalse(self.http_calls, "Nothing asked of the providers")

    def test_cancelled_and_failed(self):
        _location, params = self._start('google')
        response = self.url_open('/social-login/google/callback?error=access_denied&state=%s' % params['state'],
                                 allow_redirects=False)
        location = urlsplit(response.headers['Location'])
        self.assertEqual(self._error_of(location), 'cancelled')
        self.assertNotIn('o_g2b_social_error', self.url_open('%s?%s' % (location.path, location.query)).text)

        self.assertEqual(self._error_of(self._sign_in('google', code='bad-code')), 'failed')
        self.assertFalse(self._session_uid())

    def test_odoo_way_in_is_closed(self):
        """/auth_oauth/signin takes a token from the browser, from any app:
        not for these providers."""
        with self.assertRaises(AccessDenied):
            self.env['res.users'].auth_oauth(self.google.id, {'access_token': 'stolen', 'state': '{}'})
        state = json.dumps({'d': self.env.cr.dbname, 'p': self.google.id, 'r': '/my'})
        response = self.url_open('/auth_oauth/signin?' + urlencode({'access_token': 'stolen', 'state': state}),
                                 allow_redirects=False)
        self.assertIn('oauth_error=3', response.headers['Location'])
        self.assertFalse(self._session_uid())

    def test_credential_cannot_be_forged(self):
        customer = self.env['res.users'].create({
            'name': 'Victim', 'login': 'victim@example.com',
            'groups_id': [Command.set(self.portal_group.ids)],
        })
        page = self.url_open('/web/login').text
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        self.url_open('/web/login', data={
            'csrf_token': csrf, 'login': customer.login, 'type': 'g2b_social', 'key': 'x', 'password': 'x',
        })
        self.assertFalse(self._session_uid())

    def test_settings(self):
        settings = self.env['res.config.settings'].create({
            'g2b_facebook_enabled': True,
            'g2b_facebook_client_id': ' 998877 \n',
            'g2b_facebook_client_secret': ' abc-secret ',
            'auth_oauth_google_enabled': True,
            'auth_oauth_google_client_id': ' new-id.apps.googleusercontent.com',
            'g2b_google_client_secret': 'GOCSPX-new ',
        })
        settings.execute()
        self.assertEqual((self.facebook.client_id, self.facebook.g2b_client_secret), ('998877', 'abc-secret'))
        self.assertEqual((self.google.client_id, self.google.g2b_client_secret),
                         ('new-id.apps.googleusercontent.com', 'GOCSPX-new'))
        self.assertTrue(settings.g2b_social_uri_google.endswith('/social-login/google/callback'))
        self.assertTrue(settings.g2b_social_uri_facebook.endswith('/social-login/facebook/callback'))
        values = self.env['res.config.settings'].create({})
        self.assertEqual(values.g2b_facebook_client_id, '998877')
        self.assertTrue(values.g2b_facebook_enabled)

    def test_data_deletion_page(self):
        page = self.url_open('/social-login/data-deletion')
        self.assertEqual(page.status_code, 200)
        self.assertIn('o_g2b_social_page_card', page.text)
