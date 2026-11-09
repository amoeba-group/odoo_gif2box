import hashlib
import hmac
import logging

import requests

from odoo import api, fields, models
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

TIMEOUT = 10

# What sign-in with each needs, set on Odoo's own provider records when the
# module is installed (and not after, so a change made by hand stays).
# Facebook's URLs carry no API version: Graph then uses the app's own, which
# Meta moves forward as old ones retire.
SETUP = {
    'google': {
        'xmlid': 'auth_oauth.provider_google',
        'name': 'Google',
        'auth_endpoint': 'https://accounts.google.com/o/oauth2/v2/auth',
        'g2b_token_endpoint': 'https://oauth2.googleapis.com/token',
        'validation_endpoint': 'https://openidconnect.googleapis.com/v1/userinfo',
        'data_endpoint': False,
        'scope': 'openid email profile',
        'css_class': 'fa fa-fw fa-google',
        'body': 'Continue with Google',
        'sequence': 1,
    },
    'facebook': {
        'xmlid': 'auth_oauth.provider_facebook',
        'name': 'Facebook',
        'auth_endpoint': 'https://www.facebook.com/dialog/oauth',
        'g2b_token_endpoint': 'https://graph.facebook.com/oauth/access_token',
        'validation_endpoint': 'https://graph.facebook.com/me',
        'data_endpoint': 'https://graph.facebook.com/me?fields=id,name,email',
        'scope': 'public_profile,email',
        'css_class': 'fa fa-fw fa-facebook',
        'body': 'Continue with Facebook',
        'sequence': 2,
    },
}


class SocialSignInError(Exception):
    """A sign-in that cannot go on; `code` names what the customer is told
    (see the controller's messages)."""

    def __init__(self, code, detail=None):
        super().__init__(code, detail)
        self.code = code
        self.detail = detail


class AuthOAuthProvider(models.Model):
    _inherit = 'auth.oauth.provider'

    g2b_kind = fields.Selection(
        [('google', 'Google'), ('facebook', 'Facebook')], string='Gif2box Sign-in',
        help="Set: customers sign in with this provider through the server (/social-login), "
             "with the client secret below. Odoo's own way in (/auth_oauth/signin) is then closed to it.")
    g2b_client_secret = fields.Char(
        string='Client Secret', copy=False, groups='base.group_system',
        help="Google: the client secret of the OAuth client. Facebook: the App secret.")
    g2b_token_endpoint = fields.Char(
        string='Token URL', help="Where the server trades the one-time code for an access token.")

    # --- Setup ----------------------------------------------------------------

    @api.model
    def _g2b_setup_providers(self):
        """Odoo's Google and Facebook providers, made ready for sign-in through
        the server; Odoo.com's, which a shop's customers have no use for,
        switched off. Only once: a provider already set up is left as it is."""
        for kind, values in SETUP.items():
            values = dict(values)
            provider = self.env.ref(values.pop('xmlid'), raise_if_not_found=False)
            if not provider:
                provider = self.search([('g2b_kind', '=', kind)], limit=1)
            if not provider:
                self.create(dict(values, g2b_kind=kind, enabled=False))
            elif not provider.g2b_kind:
                provider.write(dict(values, g2b_kind=kind))
        odoo_com = self.env.ref('auth_oauth.provider_openerp', raise_if_not_found=False)
        if odoo_com:
            odoo_com.enabled = False

    @api.model
    def _g2b_get(self, kind):
        return self.search([('g2b_kind', '=', kind)], order='enabled desc, sequence, id', limit=1)

    @api.model
    def _g2b_ready_providers(self):
        """The providers whose button shows: switched on, with both keys."""
        return self.search([('g2b_kind', '!=', False), ('enabled', '=', True)]).filtered(
            lambda p: p.client_id and p.sudo().g2b_client_secret and p.g2b_token_endpoint)

    # --- Signing in -------------------------------------------------------------

    def _g2b_http(self, method, url, **kwargs):
        """One call to the provider, its JSON answer back (errors included,
        which both providers answer in JSON). Kept apart for the tests."""
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        try:
            return response.json()
        except ValueError:
            return {'error': 'HTTP %s, not JSON' % response.status_code}

    def _g2b_fetch_profile(self, code, redirect_uri):
        """Trade the one-time code for the customer's profile.

        :return: dict with `uid` (the provider's id for them), `email`
                 (normalized, or False), `email_verified`, `name`
        :raise SocialSignInError: 'failed'
        """
        self.ensure_one()
        secret = self.sudo().g2b_client_secret or ''
        token_params = {
            'client_id': self.client_id,
            'client_secret': secret,
            'redirect_uri': redirect_uri,
            'code': code,
        }
        if self.g2b_kind == 'google':
            token_params['grant_type'] = 'authorization_code'
            answer = self._g2b_http('POST', self.g2b_token_endpoint, data=token_params)
        else:
            answer = self._g2b_http('GET', self.g2b_token_endpoint, params=token_params)
        access_token = answer.get('access_token')
        if not access_token:
            raise SocialSignInError('failed', 'token: %s' % (answer.get('error') or answer))

        if self.g2b_kind == 'google':
            data = self._g2b_http('GET', self.validation_endpoint,
                                  headers={'Authorization': 'Bearer %s' % access_token})
            uid = data.get('sub')
            verified = data.get('email_verified') in (True, 'true')
        else:
            # The proof that the call comes from the app the token was issued to.
            proof = hmac.new(secret.encode(), access_token.encode(), hashlib.sha256).hexdigest()
            data = self._g2b_http('GET', self.data_endpoint or self.validation_endpoint,
                                  params={'access_token': access_token, 'appsecret_proof': proof})
            uid = data.get('id')
            # Facebook only shares an address its owner has confirmed.
            verified = True
        if data.get('error') or not uid:
            raise SocialSignInError('failed', 'profile: %s' % (data.get('error') or 'no id'))
        return {
            'uid': str(uid),
            'email': email_normalize(data.get('email') or '') or False,
            'email_verified': verified,
            'name': (data.get('name') or '').strip(),
        }
