from urllib.parse import urlsplit

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """Website > Settings > Sign in with Google & Facebook. Google's switch
    and client ID are Odoo's own fields (auth_oauth), shown there again with
    the secret; Facebook's are ours. All of them live on the providers."""
    _inherit = 'res.config.settings'

    g2b_google_client_secret = fields.Char(string='Google Client Secret')
    g2b_facebook_enabled = fields.Boolean(string='Sign in with Facebook')
    g2b_facebook_client_id = fields.Char(string='Facebook App ID')
    g2b_facebook_client_secret = fields.Char(string='Facebook App Secret')
    # The addresses to give Google and Facebook, for each host of the site.
    g2b_social_uri_google = fields.Char(string='Google Redirect URI', compute='_compute_g2b_social_uris')
    g2b_social_uri_google_alt = fields.Char(string='Google Redirect URI (other host)',
                                            compute='_compute_g2b_social_uris')
    g2b_social_uri_facebook = fields.Char(string='Facebook Redirect URI', compute='_compute_g2b_social_uris')
    g2b_social_uri_facebook_alt = fields.Char(string='Facebook Redirect URI (other host)',
                                              compute='_compute_g2b_social_uris')

    @api.depends('website_id')
    def _compute_g2b_social_uris(self):
        for settings in self:
            base = (settings.website_id or self.env['website'].get_current_website()).get_base_url()
            parts = urlsplit(base)
            host = parts.netloc
            alt_host = host[4:] if host.startswith('www.') else 'www.' + host
            # No second host for an address like localhost:8069.
            alt = '%s://%s' % (parts.scheme, alt_host) if '.' in host and ':' not in host else False
            for kind in ('google', 'facebook'):
                path = '/social-login/%s/callback' % kind
                settings['g2b_social_uri_%s' % kind] = '%s://%s%s' % (parts.scheme, host, path)
                settings['g2b_social_uri_%s_alt' % kind] = alt and alt + path

    @api.model
    def get_values(self):
        res = super().get_values()
        Provider = self.env['auth.oauth.provider'].sudo()
        google, facebook = Provider._g2b_get('google'), Provider._g2b_get('facebook')
        res.update(
            g2b_google_client_secret=google.g2b_client_secret,
            g2b_facebook_enabled=facebook.enabled,
            g2b_facebook_client_id=facebook.client_id,
            g2b_facebook_client_secret=facebook.g2b_client_secret,
        )
        return res

    def set_values(self):
        super().set_values()
        Provider = self.env['auth.oauth.provider'].sudo()
        google, facebook = Provider._g2b_get('google'), Provider._g2b_get('facebook')

        def clean(value):
            # Pasted keys often bring a space or a line break along.
            return (value or '').strip() or False

        if google:
            google.write({
                # Odoo's own field, written by auth_oauth just before: trimmed.
                'client_id': clean(self.auth_oauth_google_client_id),
                'g2b_client_secret': clean(self.g2b_google_client_secret),
            })
        if facebook:
            facebook.write({
                'enabled': self.g2b_facebook_enabled,
                'client_id': clean(self.g2b_facebook_client_id),
                'g2b_client_secret': clean(self.g2b_facebook_client_secret),
            })
