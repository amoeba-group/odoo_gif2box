{
    'name': 'Gif2box: Blog',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'A modern, search-friendly design for the Odoo blog, and its first gift guides',
    'description': """
Gif2box blog
============

Odoo's own blog (posts are written, edited and deleted as usual, from the
website editor or Website > Blog > Posts), with:

- an index made for reading on a phone: a header with search and topics, the
  latest post featured, then cards with picture, topic, teaser, date and
  reading time;
- a post page set for long reading: title over the cover, breadcrumb, reading
  time, a table of contents, a reading progress bar, sharing, and a way to the
  gift boxes at the end;
- search engine data: schema.org BlogPosting and BreadcrumbList on every post,
  and a meta description that falls back on the teaser;
- three starter gift guides, in Vietnamese and English, created once.
""",
    'author': 'Amoeba',
    'license': 'LGPL-3',
    # `gif2box_theme_home` for the brand variables the stylesheet uses.
    'depends': ['website_blog', 'gif2box_theme_home'],
    'data': [
        'views/blog_templates.xml',
        # Last: it reads the records the views above render.
        'data/blog_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'gif2box_blog/static/src/scss/blog.scss',
            'gif2box_blog/static/src/js/blog_post.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
