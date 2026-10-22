{
    'name': 'Gif2box: Shop & Category Pages',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Category pages built for shopping: header, category and budget '
               'chips, clearer cards, sold-out last, "show more"',
    'author': 'Amoeba',
    'license': 'LGPL-3',
    # `gif2box_theme_home` styles the product cards and declares the brand
    # variables this stylesheet uses; it must come first in the bundle.
    'depends': ['gif2box_theme_home'],
    'data': [
        'views/shop_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_theme_shop/static/src/scss/shop_page.scss',
            'gif2box_theme_shop/static/src/js/shop_page.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
