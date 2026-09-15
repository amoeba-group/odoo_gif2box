{
    'name': 'Gif2box: Shopping Cart Theme',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Cleaner, friendlier shopping cart page',
    'author': 'Amoeba',
    'license': 'LGPL-3',
    'depends': ['website_sale', 'website_sale_wishlist'],
    'data': [
        'views/cart_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_theme_cart/static/src/scss/cart.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
}
