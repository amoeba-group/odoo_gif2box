{
    'name': 'Gif2box: Homepage & Header Theme',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Restructured header, flag language switcher, full-width slider',
    'author': 'Amoeba',
    'license': 'LGPL-3',
    # `website_sale_stock` is where `_is_sold_out` lives, which
    # `models/product_template.py` overrides.
    'depends': ['website_sale', 'website_sale_wishlist', 'website_sale_stock'],
    'data': [
        'views/header_templates.xml',
        'views/product_templates.xml',
        'views/product_card_templates.xml',
        'views/wishlist_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # header.scss first: it declares the brand variables the others use.
            'gif2box_theme_home/static/src/scss/header.scss',
            'gif2box_theme_home/static/src/scss/footer.scss',
            'gif2box_theme_home/static/src/scss/combo_dialog.scss',
            'gif2box_theme_home/static/src/scss/product_dialog.scss',
            'gif2box_theme_home/static/src/scss/product_page.scss',
            'gif2box_theme_home/static/src/scss/wishlist.scss',
            'gif2box_theme_home/static/src/js/loader.js',
            'gif2box_theme_home/static/src/js/extension_error_filter.js',
            'gif2box_theme_home/static/src/js/product_page.js',
            'gif2box_theme_home/static/src/js/product_configurator_title.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
