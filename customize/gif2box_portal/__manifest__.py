{
    'name': 'Gif2box: Customer Account & Sign-in',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'The customer account as a modern shop has it: an overview, '
               'orders as cards, the sign-in and sign-up pages, and the '
               'thank-you page after an order',
    'description': """
The customer's side of the shop, redesigned
===========================================

* **My account** (/my): a greeting, what is under way, the orders to
  review, the latest orders, the account's details. Odoo's tiles for
  quotations, invoices, payment methods and "Connection & Security" are
  gone; the password is changed from the account's details.
* **My orders** (/my/orders): one card per order, with its pictures, its
  status and the delivery date, filtered by status. A card opens the
  order's tracking page, which is also where the order's own portal page
  (/my/orders/<id>) now leads, from the emails as from anywhere else.
* One frame for every account page: the customer's name and tabs.
  The wishlist, one of the tabs, wears it too once signed in, and is
  shown empty rather than sent on to the shop.
* **Sign in, sign up, forgotten password**: one card on a warm page, the
  brand beside it on a computer.
* **Thank you** (/shop/confirmation): what was ordered, where it goes,
  how it is paid, the delivery steps, and the way to follow it.
""",
    'author': 'Amoeba',
    'license': 'LGPL-3',
    'depends': [
        'portal', 'auth_signup', 'website_sale', 'website_sale_wishlist',
        'gif2box_order_tracking', 'gif2box_review', 'gif2box_vn_address',
    ],
    'data': [
        'views/account_templates.xml',
        'views/auth_templates.xml',
        'views/confirmation_templates.xml',
        'views/wishlist_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_portal/static/src/scss/account.scss',
            'gif2box_portal/static/src/scss/auth.scss',
            'gif2box_portal/static/src/scss/confirmation.scss',
        ],
        # The sign-in pages' script (show the password), on those pages only.
        'gif2box_portal.assets_auth': [
            'gif2box_portal/static/src/js/auth.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
