{
    'name': 'Gif2box: Sign in with Google & Facebook',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Customers sign in, or create their account, with their Google '
               'or Facebook account: one tap, no password to remember',
    'description': """
Sign in with Google or Facebook
===============================

* **"Continue with Google", "Continue with Facebook"** at the top of the
  sign-in and sign-up pages. A new customer gets their account at once,
  with the name and email the provider shares; a customer who already
  has an account with that email lands in it, and can still sign in with
  their password.
* **Set up in Website > Configuration > Settings**: a client ID and a
  client secret for each, with the addresses to give Google and Facebook.
  A button shows once its keys are in.
* **Signed in by the server**: the browser only carries a one-time code,
  which the server trades for the customer's profile with the shop's
  secret. A token issued to another app is of no use here, and a sign-in
  must finish in the browser that started it.
* Staff accounts are never taken over: an email that belongs to one is
  turned away, and its owner signs in with their password.
* **/social-login/data-deletion**: how a customer deletes what Google or
  Facebook shared, the page Facebook asks for before the app goes live.
* Inside the Zalo, Facebook or Instagram app, where Google refuses to
  sign anyone in, the page says to open it in the browser instead.

Built on Odoo's OAuth module (auth_oauth), whose Google and Facebook
providers it sets up; Odoo's own way in for them (a token from the
browser, /auth_oauth/signin) is closed.
""",
    'author': 'Amoeba',
    'license': 'LGPL-3',
    'depends': ['auth_oauth', 'website', 'gif2box_portal'],
    'data': [
        'data/auth_oauth_provider_data.xml',
        'views/auth_templates.xml',
        'views/data_deletion_templates.xml',
        'views/auth_oauth_provider_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_social_login/static/src/scss/social_login.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
}
