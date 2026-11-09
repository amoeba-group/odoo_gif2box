import logging
import secrets
import time
from urllib.parse import urlsplit

from werkzeug.exceptions import NotFound
from werkzeug.urls import url_encode

from odoo import _, http
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.tools import consteq

from odoo.addons.auth_oauth.controllers.main import OAuthLogin

from ..models.auth_oauth_provider import SocialSignInError
from ..models.res_users import SESSION_PROOF

_logger = logging.getLogger(__name__)

# The sign-in under way, in the session of the browser that started it.
SESSION_FLOW = 'g2b_social_flow'
FLOW_TTL = 15 * 60

# Apps whose built-in browser Google refuses to sign anyone in from
# ("disallowed_useragent"): Facebook, Messenger, Instagram, Zalo, TikTok, Line.
IN_APP_MARKS = ('FBAN', 'FBAV', 'FB_IAB', 'FBIOS', 'Instagram', 'Zalo', 'musical_ly',
                'BytedanceWebview', 'TikTok', ' Line/')


def _local_url(url):
    """`url` if it stays on this site, else ''."""
    if not url or not url.startswith('/') or url.startswith(('//', '/\\')):
        return ''
    parts = urlsplit(url)
    return '' if parts.scheme or parts.netloc else url


class Gif2boxSocialLoginPages(http.Controller):

    @http.route('/social-login/data-deletion', type='http', auth='public', website=True, sitemap=False)
    def g2b_data_deletion(self, **kw):
        company = request.website.company_id
        phone = request.env['ir.config_parameter'].sudo().get_param(
            'gif2box_order_tracking.support_phone') or company.phone
        return request.render('gif2box_social_login.data_deletion_page', {
            'g2b_email': company.email,
            'g2b_phone': phone,
        })


class Gif2boxSocialLogin(OAuthLogin):
    """Sign in with Google or Facebook, through the server.

    The button leads to `/social-login/<kind>`, which notes a random `state`
    in the session and sends the customer to the provider. The provider sends
    them back to `/social-login/<kind>/callback` with a one-time code, which
    the server trades, with the shop's secret, for their profile; the account
    is found, linked or made (`res.users._g2b_social_user`), and the session
    signed in to it.
    """

    # --- The buttons ------------------------------------------------------------

    def list_providers(self):
        """The buttons of the sign-in pages: ours, ready, and nothing else.
        (Odoo's own list, with its links to /auth_oauth/signin, is not shown.)"""
        providers = request.env['auth.oauth.provider'].sudo()._g2b_ready_providers()
        redirect = _local_url(request.params.get('redirect'))
        query = '?' + url_encode({'redirect': redirect}) if redirect else ''
        return [{
            'id': provider.id,
            'kind': provider.g2b_kind,
            'name': provider.name,
            'auth_link': '/social-login/%s%s' % (provider.g2b_kind, query),
        } for provider in providers]

    def _g2b_page_values(self):
        user_agent = request.httprequest.user_agent.string or ''
        values = {'g2b_social_in_app': any(mark in user_agent for mark in IN_APP_MARKS)}
        code = request.params.get('g2b_error')
        kind = request.params.get('g2b_provider')
        if code:
            message, retry = self._g2b_error_message(code, kind)
            values['g2b_social_error'] = message
            if retry:
                redirect = _local_url(request.params.get('redirect'))
                values['g2b_social_retry'] = '/social-login/%s?%s' % (
                    kind, url_encode(dict({'rerequest': 1}, **({'redirect': redirect} if redirect else {}))))
        return values

    def _g2b_error_message(self, code, kind):
        """What the customer reads back on the sign-in page, and whether to
        offer to try again (asking Facebook for the email once more)."""
        name = {'google': 'Google', 'facebook': 'Facebook'}.get(kind, '')
        if code == 'cancelled':
            return None, False
        if code == 'expired':
            return _("This sign-in took too long, or was finished in another browser. "
                     "Please try again."), False
        if code == 'no_email':
            return _("%s did not share your email address with us, and we need it to send you "
                     "news of your orders. Try again and allow it, or sign up with your email "
                     "below.", name), kind == 'facebook'
        if code == 'unverified':
            return _("Your %s email address is not verified yet. Verify it with them, or sign "
                     "up with your email below.", name), False
        if code == 'staff':
            return _("This email belongs to a Gif2box staff account: please sign in with its "
                     "password."), False
        if code == 'closed':
            return _("The account with this email has been closed. Contact us if you would "
                     "like it back."), False
        if code == 'signup_closed':
            return _("New accounts are by invitation only for now: no account was created."), False
        if name:
            return _("We could not sign you in with %s. Please try again, or use your email "
                     "below.", name), False
        return None, False

    @http.route()
    def web_login(self, *args, **kw):
        response = super().web_login(*args, **kw)
        if getattr(response, 'is_qweb', False):
            response.qcontext.update(self._g2b_page_values())
        return response

    def get_auth_signup_qcontext(self):
        qcontext = super().get_auth_signup_qcontext()
        qcontext.update(self._g2b_page_values())
        return qcontext

    # --- The way in ---------------------------------------------------------------

    def _g2b_redirect_uri(self, kind):
        # The host the customer is on (gif2box.vn or www.): its session
        # cookie is the one the callback must find.
        return '%ssocial-login/%s/callback' % (request.httprequest.url_root, kind)

    def _g2b_back(self, code, kind, redirect):
        """Back to the sign-in page, saying why."""
        query = {'g2b_error': code, 'g2b_provider': kind}
        if redirect:
            query['redirect'] = redirect
        return request.redirect('/web/login?' + url_encode(query), 303)

    @http.route('/social-login/<string:kind>', type='http', auth='public', website=True,
                multilang=False, sitemap=False, methods=['GET'])
    def g2b_social_start(self, kind, redirect=None, rerequest=None, **kw):
        redirect = _local_url(redirect)
        if request.session.uid:
            return request.redirect(redirect or '/my', 303)
        provider = request.env['auth.oauth.provider'].sudo()._g2b_ready_providers().filtered(
            lambda p: p.g2b_kind == kind)[:1]
        if not provider:
            raise NotFound()
        state = secrets.token_urlsafe(32)
        request.session[SESSION_FLOW] = {
            'state': state,
            'kind': kind,
            'redirect': redirect,
            'time': int(time.time()),
        }
        params = {
            'response_type': 'code',
            'client_id': provider.client_id,
            'redirect_uri': self._g2b_redirect_uri(kind),
            'scope': provider.scope,
            'state': state,
        }
        if kind == 'google':
            # Several Google accounts on one phone: let them pick.
            params['prompt'] = 'select_account'
        elif kind == 'facebook' and rerequest:
            # The email, refused the first time: Facebook asks once more.
            params['auth_type'] = 'rerequest'
        return request.redirect('%s?%s' % (provider.auth_endpoint, url_encode(params)), 303, local=False)

    @http.route('/social-login/<string:kind>/callback', type='http', auth='public', website=True,
                multilang=False, sitemap=False, methods=['GET'])
    def g2b_social_callback(self, kind, code=None, state=None, error=None, **kw):
        flow = request.session.pop(SESSION_FLOW, None) or {}
        redirect = _local_url(flow.get('redirect'))
        if not (
            flow.get('state') and state and consteq(state, flow['state'])
            and flow.get('kind') == kind
            and time.time() - flow.get('time', 0) < FLOW_TTL
        ):
            return self._g2b_back('expired', kind, redirect)
        if error or not code:
            # They said no, or closed the window.
            return self._g2b_back('cancelled', kind, redirect)

        provider = request.env['auth.oauth.provider'].sudo()._g2b_ready_providers().filtered(
            lambda p: p.g2b_kind == kind)[:1]
        if not provider:
            return self._g2b_back('failed', kind, redirect)
        try:
            profile = provider._g2b_fetch_profile(code, self._g2b_redirect_uri(kind))
            user, created = request.env['res.users'].sudo()._g2b_social_user(provider, profile)
        except SocialSignInError as e:
            if e.detail:
                _logger.warning("Sign-in with %s failed: %s", provider.name, e.detail)
            request.env.cr.rollback()
            return self._g2b_back(e.code, kind, redirect)
        except Exception:
            _logger.exception("Sign-in with %s failed", provider.name)
            request.env.cr.rollback()
            return self._g2b_back('failed', kind, redirect)

        key = secrets.token_urlsafe(32)
        request.session[SESSION_PROOF] = {'uid': user.id, 'key': key, 'time': time.time()}
        # The sign-in reads the account with a cursor of its own.
        request.env.cr.commit()
        try:
            auth_info = request.session.authenticate(
                request.db, {'type': 'g2b_social', 'login': user.login, 'key': key})
        except AccessDenied:
            _logger.warning("Sign-in with %s: user %s refused", provider.name, user.id)
            return self._g2b_back('failed', kind, redirect)
        finally:
            request.session.pop(SESSION_PROOF, None)

        if created:
            # As the sign-up page does.
            template = request.env.ref('auth_signup.mail_template_user_signup_account_created',
                                       raise_if_not_found=False)
            if template:
                template.sudo().send_mail(user.id)
        # Where the password would have led: the page they came from, else
        # their account; the two-factor page first, for those who have it.
        # (Not flagged `login_success`: what reads it expects a password.)
        return request.redirect(self._login_redirect(auth_info['uid'], redirect=redirect or None), 303)
