{
    'name': 'Gif2box: Sales Order Flow',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Auto-confirm eCommerce orders, track the payment date, skip the payment status page, "Buy now" on its own',
    'author': 'Amoeba',
    'license': 'LGPL-3',
    'depends': ['website_sale'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_sale_order_flow/static/src/js/buy_now.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
