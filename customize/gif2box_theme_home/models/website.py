import base64
import logging

from werkzeug.urls import url_join

from odoo import api, models
from odoo.http import request
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

# --- The menu this module owns -------------------------------------------
#
# Menus and pages are normally website content: Odoo keeps them in the
# database and the client edits them from Site -> Menu Editor, which means
# they do not travel with the code. The structure below is declared here
# instead and applied on every update of this module, so a deploy lands the
# same bar on every database.
#
# The trade is the usual one for taking content into code: edits made to
# *these* entries in the Menu Editor are put back the next time the module is
# updated. Anything else the client adds to the bar is left alone.

ABOUT_URL = '/ve-chung-toi'

ABOUT_NAMES = {
    'en_US': 'About Us',
    'vi_VN': 'Về Chúng Tôi',
    'ja_JP': '会社概要',
    'ko_KR': '회사 소개',
}

LIFE_URL = '/shop/category/34'
GIFT_URL = '/shop/category/gift-38'
BLOG_URL = '/blog'

GIFT_NAMES = {
    'en_US': 'Gift Box',
    'vi_VN': 'Hộp quà tặng',
    'ja_JP': 'ギフトボックス',
    'ko_KR': '선물 박스',
}

BLOG_NAMES = {
    'en_US': 'Blog',
    'vi_VN': 'Blog',
    'ja_JP': 'ブログ',
    'ko_KR': '블로그',
}

# The "Policies" dropdown that used to close the bar. It is taken off the
# bar: every one of those pages is linked from the footer, where shoppers
# look for them (and where Vietnamese e-commerce rules want them), and the
# bar is kept for what leads to buying. Only the menu entries go; the pages
# stay, published, at their URLs.
RETIRED_POLICY_PARENT_NAMES = ('Policies', 'Chính sách', 'ポリシー', '정책')

# Top level order.
TOP_ORDER = ['/', ABOUT_URL, LIFE_URL, GIFT_URL, BLOG_URL]

# The icon in front of each entry (`views/header_templates.xml`), by URL.
MENU_ICONS = {
    '/': 'home',
    ABOUT_URL: 'about',
    LIFE_URL: 'life',
    GIFT_URL: 'gift',
    BLOG_URL: 'blog',
    '/shop': 'shop',
    '/contactus': 'contact',
}


# --- The social share card -----------------------------------------------
#
# What Facebook, Zalo and X put beside a link to the site. Odoo falls back to
# the website logo, which is a 95x40 wordmark on transparency: below
# Facebook's 200x200 floor, so the link shared as a bare line of text.
#
# The card is 1200x630, the 1.91:1 every one of them crops to. It is kept in
# the module rather than uploaded through Settings so that a deploy carries
# it, the same bargain the menu above makes.
SOCIAL_SHARE_IMAGE = 'gif2box_theme_home/static/src/img/social_share.png'

# The pages someone had pointed at the logo or at one product's photo through
# the SEO panel. Both are the reason there was no preview; cleared, they fall
# back to the card above. Matched on what the value points at, so a share
# image chosen deliberately later is left alone.
_BROKEN_OG_IMG = ('/web/image/website/', '/web/image/product.template/')


class Website(models.Model):
    _inherit = 'website'

    def _gif2box_write_translations(self, record, field, names):
        """Write one field in every language the database has installed."""
        installed = self.env['res.lang'].search([]).mapped('code')
        for code, value in names.items():
            if code in installed:
                record.with_context(lang=code).write({field: value})

    @api.model
    def _gif2box_set_social_share_image(self):
        """Install the share card, and clear what was standing in its way.

        Called from `data/social_share_data.xml`. A `<record>` on the website
        cannot do this: `website.default_website` is flagged `noupdate`, so it
        would be skipped without a word.
        """
        with file_open(SOCIAL_SHARE_IMAGE, 'rb') as fh:
            card = base64.b64encode(fh.read())

        websites = self.env['website'].sudo().search([])
        websites.write({'social_default_image': card})

        # Per-page overrides win over the website default, so the card would
        # have changed nothing on the pages that carry one. These all point at
        # the logo or at a single product's photo -- the state the site was
        # in -- and are cleared so those pages fall back to the card. The
        # value is visible in the SEO panel, so any of them can be set again.
        views = self.env['ir.ui.view'].sudo().search([
            ('website_meta_og_img', '!=', False),
            ('website_meta_og_img', '!=', ''),
        ])
        stale = views.filtered(
            lambda v: any(part in (v.website_meta_og_img or '') for part in _BROKEN_OG_IMG)
        )
        if stale:
            stale.write({'website_meta_og_img': False})

        _logger.info(
            'gif2box: share card set on %s website(s), %s stale og:image override(s) cleared',
            len(websites), len(stale))

    @api.model
    def _gif2box_setup_menu(self):
        """Lay out the top menu: Home, About, Life, Gift Box, Blog.

        `@api.model` because `<function>` in a data file passes no ids:
        without it `call_kw` treats this as a multi-record method and fails
        reading the record ids out of an empty argument list.

        Called from `data/menu_data.xml` on every install and update, and
        safe to run any number of times: everything is matched on page URLs,
        and a second pass finds its own work already done.

        Runs for every website in the database, so a second site added later
        is covered without touching this file.
        """
        for website in self.env['website'].search([]):
            self._gif2box_setup_menu_one(website)

    def _gif2box_setup_menu_one(self, website):
        env_w = self.env(context=dict(self.env.context, website_id=website.id))
        Menu = env_w['website.menu']
        root = Menu.search(
            [('website_id', '=', website.id), ('parent_id', '=', False)], limit=1)
        if not root:
            _logger.warning('gif2box menu: website %s has no root menu, skipped', website.id)
            return

        # --- About Us page ---------------------------------------------
        page = env_w['website.page'].search(
            [('url', '=', ABOUT_URL), ('website_id', 'in', (website.id, False))], limit=1)
        if not page:
            result = website.with_context(website_id=website.id).new_page(
                name=ABOUT_NAMES['en_US'],
                add_menu=False,
                page_values={'url': ABOUT_URL, 'is_published': True},
            )
            page = env_w['website.page'].browse(result['page_id'])
            page.write({'url': ABOUT_URL, 'is_published': True})
            _logger.info('gif2box menu: created page %s', ABOUT_URL)

        about = Menu.search(
            [('website_id', '=', website.id), ('url', '=', ABOUT_URL)], limit=1)
        if not about:
            about = Menu.create({
                'name': ABOUT_NAMES['en_US'],
                'url': ABOUT_URL,
                'page_id': page.id,
                'parent_id': root.id,
                'website_id': website.id,
            })
        self._gif2box_write_translations(about, 'name', ABOUT_NAMES)

        # --- Gift Box --------------------------------------------------
        gift = Menu.search(
            [('website_id', '=', website.id), ('url', '=', GIFT_URL)], limit=1)
        if gift:
            self._gif2box_write_translations(gift, 'name', GIFT_NAMES)

        # --- Blog -------------------------------------------------------
        blog = Menu.search(
            [('website_id', '=', website.id), ('url', '=', BLOG_URL)], limit=1)
        if not blog:
            blog = Menu.create({
                'name': BLOG_NAMES['en_US'],
                'url': BLOG_URL,
                'parent_id': root.id,
                'website_id': website.id,
            })
        self._gif2box_write_translations(blog, 'name', BLOG_NAMES)

        # --- Policies off the bar -----------------------------------------
        # The dropdown and its entries; the pages themselves are untouched.
        retired = Menu.search([
            ('website_id', '=', website.id),
            ('parent_id', '=', root.id),
            ('url', 'in', (False, '#')),
            ('name', 'in', list(RETIRED_POLICY_PARENT_NAMES)),
        ])
        removed = len(retired.child_id)
        if retired:
            (retired.child_id | retired).unlink()

        # --- Order the top level -----------------------------------------
        for index, url in enumerate(TOP_ORDER):
            menu = Menu.search([
                ('website_id', '=', website.id),
                ('parent_id', '=', root.id),
                ('url', '=', url),
            ], limit=1)
            if menu:
                menu.sequence = index

        _logger.info(
            'gif2box menu: website %s laid out, %s policy entries taken off the bar',
            website.id, removed)


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    def _gif2box_icon(self):
        """The icon drawn before this entry, or False for none."""
        self.ensure_one()
        url = (self.url or '').split('?')[0].rstrip('/') or '/'
        if url in MENU_ICONS:
            return MENU_ICONS[url]
        if url.startswith(BLOG_URL + '/'):
            return 'blog'
        return False


class WebsiteSocialShare(models.AbstractModel):
    """Mixin hook: adds the sizes of the share card to the page head.

    Facebook renders a large card on first sight of a link only if it is told
    the dimensions; without them it waits until it has fetched and measured
    the image, and the first share of a page -- usually the one that matters --
    goes out as a small card or none at all.

    `get_website_meta` rather than `_default_website_meta`, which is where
    Odoo asks for customisation, because the tags are only true when the image
    really is the card: a product page swaps in the product's own photo, and
    claiming 1200x630 for that would be a lie told to every crawler.
    """
    _inherit = 'website.seo.metadata'

    def get_website_meta(self):
        meta = super().get_website_meta()

        website = request.website
        if not website.has_social_default_image:
            return meta

        root_url = website.domain or request.httprequest.url_root.strip('/')
        card_url = url_join(root_url, website.image_url(website, 'social_default_image'))
        if meta['opengraph_meta'].get('og:image') != card_url:
            return meta

        meta['opengraph_meta'].update({
            'og:image:width': '1200',
            'og:image:height': '630',
            'og:image:alt': website.name,
        })
        # Odoo asks X for the card at 300x300, which the image endpoint fits
        # to 300x157 -- the exact floor for `summary_large_image`, and blurry
        # at any size X actually draws it. The card is 1200x630 already.
        meta['twitter_meta']['twitter:image'] = card_url
        return meta
