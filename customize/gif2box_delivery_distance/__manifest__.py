{
    'name': 'Gif2box: Shipping by Distance',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Shipping fee by distance from the warehouse, after the courier '
               'price list; free from an amount, with a progress bar',
    'description': """
Shipping priced the way the courier prices it
==============================================

* A delivery method type, "By distance from the warehouse": the price
  columns of the courier's list (Việt Tín CPN S07/2025, section I: inner
  city, under 300 km, over 300 km, Hà Nội & Đà Nẵng), one price each
  whatever the weight, plus the surcharges its notes add (fuel; commune and
  island delivery) and VAT. All of it editable on the delivery method.
* 63 delivery areas, the provinces before 1 July 2025 the courier still
  goes by, with their road distance from the warehouse in Thủ Đức; every
  ward of the current register is given the area it was part of. No map
  service is called at checkout.
* Free shipping from Odoo's own "Free if order amount is above", and a bar
  showing what is left to add: cart page, checkout, the "added to your
  cart" popup, and a note on the product page.
""",
    'author': 'Amoeba',
    'license': 'LGPL-3',
    'depends': ['website_sale', 'gif2box_vn_address'],
    'data': [
        'security/ir.model.access.csv',
        'data/delivery_area_data.xml',
        'data/res.country.ward.csv',
        'views/delivery_area_views.xml',
        'views/delivery_carrier_views.xml',
        'views/free_shipping_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_delivery_distance/static/src/scss/free_shipping.scss',
            'gif2box_delivery_distance/static/src/js/add_to_cart_free_shipping.js',
            'gif2box_delivery_distance/static/src/xml/add_to_cart_free_shipping.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
}
