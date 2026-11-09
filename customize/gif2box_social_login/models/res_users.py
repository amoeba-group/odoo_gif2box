import time

from odoo import api, models
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.tools import consteq
from odoo.tools.sql import escape_psql

from .auth_oauth_provider import SocialSignInError

# Where the callback leaves, in the server-side session, its word that this
# browser has just proved who it is; `_check_credentials` takes it once.
SESSION_PROOF = 'g2b_social_proof'
PROOF_TTL = 120


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _g2b_social_user(self, provider, profile):
        """The account a profile from Google or Facebook signs in to, found,
        linked or made.

        * the account already linked to this provider's id for them;
        * else the customer account whose login is their email, when the
          provider vouches for the email: it gets linked;
        * else a new customer account, as the sign-up page would make it.

        A staff account is never linked this way: anyone who can sign in to
        an email's Google or Facebook would get into the back office.

        :return: (user, created)
        :raise SocialSignInError: 'closed', 'no_email', 'unverified', 'staff',
            'signup_closed'
        """
        Users = self.sudo().with_context(active_test=False)
        user = Users.search([
            ('oauth_provider_id', '=', provider.id), ('oauth_uid', '=', profile['uid']),
        ], limit=1)
        if user:
            if not user.active:
                raise SocialSignInError('closed')
            return user, False

        email = profile.get('email')
        if not email:
            raise SocialSignInError('no_email')
        if not profile.get('email_verified'):
            raise SocialSignInError('unverified')

        # Logins are emails, typed by hand when signing up: any case.
        website = self.env['website'].get_current_website()
        domain = [('login', '=ilike', escape_psql(email))] + website.website_domain()
        user = Users.search(domain, order=Users._get_login_order(), limit=1)
        if user:
            if not user.active:
                raise SocialSignInError('closed')
            if user._is_internal():
                raise SocialSignInError('staff')
            # One provider per account (Odoo's fields): the latest one used.
            user.write({'oauth_provider_id': provider.id, 'oauth_uid': profile['uid']})
            return user, False

        if Users._get_signup_invitation_scope() != 'b2c':
            raise SocialSignInError('signup_closed')
        values = {
            'name': profile.get('name') or email.split('@')[0],
            'login': email,
            'email': email,
            'oauth_provider_id': provider.id,
            'oauth_uid': profile['uid'],
        }
        lang = request and request.lang and request.lang.code
        if lang and lang in dict(self.env['res.lang'].get_installed()):
            values['lang'] = lang
        login, _password = self.sudo().signup(values)
        return Users.search(Users._get_login_domain(login), order=Users._get_login_order(), limit=1), True

    def _check_credentials(self, credential, env):
        """Sign-in after Google or Facebook: the callback has checked who the
        browser belongs to and left its word in the session, for this user
        and for this one sign-in."""
        try:
            return super()._check_credentials(credential, env)
        except AccessDenied:
            if credential.get('type') != 'g2b_social' or not request:
                raise
            proof = request.session.pop(SESSION_PROOF, None) or {}
            key = credential.get('key') or ''
            if not (
                proof.get('key') and key and consteq(key, proof['key'])
                and proof.get('uid') == self.env.user.id
                and time.time() - proof.get('time', 0) < PROOF_TTL
            ):
                raise
            return {
                'uid': self.env.user.id,
                'auth_method': 'oauth',
                # Two-factor sign-in, for the accounts that have it, still asked.
                'mfa': 'default',
            }

    @api.model
    def auth_oauth(self, provider, params):
        """Odoo's own way in (/auth_oauth/signin): an access token from the
        browser, which it cannot tell was issued to this shop rather than to
        any other app the customer once signed in to. Closed to the providers
        signed in through the server, and to those switched off."""
        try:
            oauth_provider = self.env['auth.oauth.provider'].browse(int(provider)).exists()
        except (TypeError, ValueError):
            raise AccessDenied()
        if not oauth_provider or oauth_provider.g2b_kind or not oauth_provider.enabled:
            raise AccessDenied()
        return super().auth_oauth(provider, params)
