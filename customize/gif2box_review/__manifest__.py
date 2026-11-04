{
    'name': 'Gif2box: Reviews',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Reviews from the people who give a gift and from the people '
               'who receive it, a thank-you card with a QR code for the box, '
               'and the reviews on the product pages',
    'description': """
Two kinds of reviews
====================

* **Gift givers**: the buyer reviews what it was like to give the gift,
  from the order in "My orders" or from the tracking page, once the order
  has left the shop.
* **Gift recipients**: a thank-you card goes in the box. Its QR code opens
  a page where the recipient rates the gift, shares photos, and can leave
  a private note of thanks for the person who sent it. The shop prints
  the cards from the order or the delivery order (A6, one per page, or
  four to an A4 sheet).

Both may add photos (optional). The shop manages every review in
Website > eCommerce > Reviews: publishes or hides, edits, replies, adds,
deletes. Published reviews show on the product page, with the average,
the breakdown by stars, filters, and the photos.
""",
    'author': 'Amoeba',
    'license': 'LGPL-3',
    'depends': ['website_sale', 'sale_stock', 'gif2box_order_tracking', 'gif2box_theme_home'],
    'data': [
        'security/ir.model.access.csv',
        'security/review_security.xml',
        'data/review_tag_data.xml',
        'report/thank_card_reports.xml',
        'report/thank_card_templates.xml',
        'views/review_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/review_menus.xml',
        'views/review_bits_templates.xml',
        'views/review_form_templates.xml',
        'views/product_review_templates.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_review/static/src/scss/review_common.scss',
            'gif2box_review/static/src/scss/product_reviews.scss',
            'gif2box_review/static/src/scss/review_form.scss',
            'gif2box_review/static/src/js/product_reviews.js',
        ],
        # The form's script, on the two review pages only: their first
        # action is a tap on a star, which should not wait for the lazily
        # loaded bundle. See `review_form.js`.
        'gif2box_review.assets_review_form': [
            'gif2box_review/static/src/js/review_form.js',
        ],
        'web.assets_backend': [
            'gif2box_review/static/src/js/rating_stars_field.js',
            'gif2box_review/static/src/xml/rating_stars_field.xml',
            'gif2box_review/static/src/scss/review_backend.scss',
        ],
        'web.report_assets_common': [
            'gif2box_review/static/src/scss/thank_card.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
}
