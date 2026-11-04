{
    'name': 'Gif2box: Order Tracking',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Where an order is, for the customer: a tracking page, the '
               'steps on the confirmation and portal pages, and an email when '
               'the gift has been delivered',
    'description': """
Order tracking for the shop
===========================

* Five steps, worked out from the order and its delivery order: placed,
  confirmed (with how it is paid), being prepared, on its way (carrier and
  tracking number), delivered. Cancelled orders say so.
* A tracking page per order (link with the order's access token, no
  account needed) and a lookup page, /order/track, by order number and the
  buyer's or recipient's phone or email.
* The steps on the order confirmation page and on the order in the portal.
* Emails to the buyer: when the parcel leaves, and when it has been
  delivered ("your gift has reached ..."). Delivery is confirmed by the
  shop with "Mark as delivered", on the order or the delivery order, one
  at a time or from the list: the courier has no connection to report it.
* An estimated delivery date from the courier's transit times for the
  address's price column (`gif2box_delivery_distance`).
""",
    'author': 'Amoeba',
    'license': 'LGPL-3',
    'depends': ['website_sale', 'sale_stock', 'stock_delivery', 'gif2box_delivery_distance',
                'gif2box_sale_order_flow', 'gif2box_hero_banner'],
    'data': [
        'data/config_data.xml',
        'data/mail_templates.xml',
        'data/server_actions.xml',
        'views/tracking_templates.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/delivery_carrier_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_order_tracking/static/src/scss/order_tracking.scss',
        ],
        # The copy buttons must answer as soon as the page shows, before the
        # lazily loaded bundle: see `order_tracking.js`. Taken back out of
        # the lazy bundle, which includes the minimal one, as `website` does.
        'web.assets_frontend_minimal': [
            'gif2box_order_tracking/static/src/js/order_tracking.js',
        ],
        'web.assets_frontend_lazy': [
            ('remove', 'gif2box_order_tracking/static/src/js/order_tracking.js'),
        ],
    },
    'installable': True,
    'auto_install': False,
}
