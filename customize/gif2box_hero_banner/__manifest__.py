{
    'name': 'Gif2box: Homepage Hero Banner',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Edit the homepage hero from the backend: picture, title, description, button',
    'description': """
Homepage hero banner
====================

The banners at the top of the homepage had their headline and button painted
into the image. This module draws the hero from records instead: a background
picture (with an optional one for phones), a title, a description and a button
with its link, all translatable, edited under Website > Site > Hero Banners
with a live preview on the form.

Several active banners slide; one stands still. Nothing is shown until a banner
is active, so installing the module changes nothing on its own.
""",
    'author': 'Amoeba',
    'license': 'LGPL-3',
    'depends': ['website'],
    'data': [
        'security/ir.model.access.csv',
        'views/website_hero_banner_templates.xml',
        'views/website_hero_banner_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_hero_banner/static/src/scss/hero_banner.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
}
