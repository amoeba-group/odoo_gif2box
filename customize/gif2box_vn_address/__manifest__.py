{
    'name': 'Gif2box: Vietnamese Address',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Province, ward and street, in the order a Vietnamese address is written',
    'description': """
Vietnamese addresses after the 1 July 2025 reform
=================================================

Vietnam has two administrative levels since 1 July 2025: 34 provinces and
centrally-run cities, and 3,321 wards, communes and special zones under
them. Districts were abolished.

* Adds the ward level (`res.country.ward`) with the full register, and a
  ward on every contact, kept in step with its province and city.
* Marks the 34 current provinces among the 63 Odoo ships, and keeps the 29
  merged ones out of the address form. Existing addresses are not touched.
* Reorders the checkout address form for Vietnam: country, province, ward,
  then one line for the detailed address. Other countries keep Odoo's form.
* The same on the portal's "Your details" form, which had no ward and still
  listed the 63 provinces of before the merger.
* Province, ward and country are picked by typing, accents optional, a
  province also by the names it absorbed in 2025; full screen on a phone.
""",
    'author': 'Amoeba',
    'license': 'LGPL-3',
    'depends': ['website_sale', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        # Provinces before wards: the wards point at them.
        'data/res.country.state.csv',
        'data/res_country_state_data.xml',
        'data/res.country.ward.csv',
        'views/res_country_ward_views.xml',
        'views/website_sale_templates.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_vn_address/static/src/scss/address_vn.scss',
            'gif2box_vn_address/static/src/scss/searchable_select.scss',
            'gif2box_vn_address/static/src/js/address_vn.js',
            'gif2box_vn_address/static/src/js/searchable_select.js',
            'gif2box_vn_address/static/src/js/portal_address_vn.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
