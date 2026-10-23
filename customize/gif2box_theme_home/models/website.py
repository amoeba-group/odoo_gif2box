import base64
import json
import logging

from werkzeug.urls import url_join

from odoo import api, models
from odoo.http import request
from markupsafe import Markup

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

LIFE_NAMES = {
    'en_US': 'Life',
    'vi_VN': 'Đời sống',
    'ja_JP': 'ライフ',
    'ko_KR': '라이프',
}

BLOG_NAMES = {
    'en_US': 'Blog',
    'vi_VN': 'Blog',
    'ja_JP': 'ブログ',
    'ko_KR': '블로그',
}

# The shop categories behind Life and Gift Box carry the menu's names, so
# the page a shopper lands on, its breadcrumb and the category filter all say
# what the menu said. Their URL part is pinned, so it stays "gift-38" and
# "life-34" whatever the name and the language.
CATEGORIES = {
    34: (LIFE_NAMES, 'life'),
    38: (GIFT_NAMES, 'gift'),
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


# --- The About Us page ----------------------------------------------------
#
# The page record (URL, menu, SEO panel) stays where Odoo keeps it; its view
# is pointed at `gif2box_theme_home.about_us_content` on every update, the
# same bargain as the menu above: the page is code, and an edit made in the
# website editor is put back by the next deploy.
ABOUT_ARCH = """<t name="About Us" t-name="website.about-us">
    <t t-call="website.layout">
        <div id="wrap" class="o_g2b_about">
            <t t-call="gif2box_theme_home.about_us_content"/>
        </div>
    </t>
</t>"""

ABOUT_META_TITLE = {
    'en_US': 'About Gif2box | Baby gift sets, ready to give',
    'vi_VN': 'Về Gif2box | Set quà tặng cho bé, sẵn sàng trao tay',
    'ja_JP': 'Gif2boxについて｜すぐに贈れるベビーギフトセット',
    'ko_KR': 'Gif2box 소개 | 바로 선물하는 아기 선물 세트',
}

ABOUT_META_DESCRIPTION = {
    'en_US': 'Authentic Korean baby feeding essentials in gift sets for every '
             'milestone: newborn, first birthday, starting solids. Boxed and '
             'better value than buying separately.',
    'vi_VN': 'Set quà tặng cho bé từ đồ dùng ăn dặm chính hãng Hàn Quốc: chào '
             'đón bé, thôi nôi, tập ăn dặm. Đóng hộp sẵn, tiết kiệm hơn mua lẻ, '
             'giao toàn quốc.',
    'ja_JP': '韓国の正規ベビー食器・離乳食グッズを、出産祝い・1歳の誕生日・離乳食デビュー'
             'などの節目に合わせたギフトセットに。箱入りで、単品で買うよりお得です。',
    'ko_KR': '한국 정품 이유식·육아 용품으로 구성한 아기 선물 세트. 출산 축하, 첫돌, '
             '이유식 시작에 맞춰 박스 포장으로, 개별 구매보다 알뜰하게.',
}

# "A set for every occasion": one gift set per milestone, by product id,
# each shown only while it is published and on sale. Chosen among the sets
# that are in stock when this was written; change the ids here to change
# the cards.
ABOUT_OCCASIONS = [
    ('newborn', 635),   # Combo Chào Đón Bé Yêu
    ('birthday', 634),  # Combo Bé Tròn 1 Tuổi
    ('kitchen', 633),   # Combo Bếp Nhỏ Của Bé
    ('growing', 639),   # Combo Cùng Bé Lớn Khôn
]

# Who runs the shop, for the page's Organization data. The same facts the
# footer gives.
ORGANIZATION = {
    'legal_name': 'CÔNG TY TNHH BRAND K VINA',
    'tax_id': '3301659169',
    'street': 'Tầng 3, Lô C299 Khu đô thị Phú Mỹ Thượng, Phường Mỹ Thượng',
    'city': 'Thành phố Huế',
    'country': 'VN',
    'email': 'sales@brandkorea.vn',
    'phone': '+84987861697',
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

    # --- About Us ------------------------------------------------------

    @api.model
    def _gif2box_setup_about_page(self):
        """Point the About Us page at its template and set its SEO texts.

        Called from `data/about_page_data.xml` on every install and update.
        The arch carries no words of its own, so it is the same in every
        language; the words are in `about_us_content` and its translations.
        """
        pages = self.env['website.page'].sudo().search([('url', '=', ABOUT_URL)])
        for page in pages:
            view = page.view_id
            if view.with_context(lang='en_US').arch_db.strip() != ABOUT_ARCH:
                view.with_context(lang='en_US').write({'arch_db': ABOUT_ARCH})
            self._gif2box_write_translations(view, 'website_meta_title', ABOUT_META_TITLE)
            self._gif2box_write_translations(
                view, 'website_meta_description', ABOUT_META_DESCRIPTION)
        _logger.info('gif2box: About Us page set on %s page(s)', len(pages))

    def _gif2box_about_occasions(self):
        """The gift sets of "A set for every occasion", in order."""
        self.ensure_one()
        Template = self.env['product.template']
        cards = []
        for key, template_id in ABOUT_OCCASIONS:
            product = Template.browse(template_id).exists()
            if not product or not (product.is_published and product.sale_ok):
                continue
            cards.append({
                'key': key,
                'product': product,
                'price': product._get_combination_info()['price'],
            })
        return cards

    def _gif2box_about_jsonld(self):
        """The shop as a schema.org Organization, for search engines."""
        self.ensure_one()
        base = (self.domain or request.httprequest.url_root).rstrip('/')
        data = {
            '@context': 'https://schema.org',
            '@type': 'Organization',
            'name': self.name,
            'legalName': ORGANIZATION['legal_name'],
            'taxID': ORGANIZATION['tax_id'],
            'url': base + '/',
            'logo': base + self.image_url(self, 'logo'),
            'email': ORGANIZATION['email'],
            'telephone': ORGANIZATION['phone'],
            'address': {
                '@type': 'PostalAddress',
                'streetAddress': ORGANIZATION['street'],
                'addressLocality': ORGANIZATION['city'],
                'addressCountry': ORGANIZATION['country'],
            },
            'contactPoint': {
                '@type': 'ContactPoint',
                'telephone': ORGANIZATION['phone'],
                'contactType': 'customer service',
                'areaServed': 'VN',
                'availableLanguage': ['vi', 'en', 'ja', 'ko'],
            },
        }
        same_as = [url for url in (self.social_facebook, self.social_instagram,
                                   self.social_youtube, self.social_tiktok) if url]
        if same_as:
            data['sameAs'] = same_as
        # `</` closed the script tag early in some parsers; escaped, it is
        # still the same JSON.
        return Markup(json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))


    @api.model
    def _gif2box_setup_menu(self):
        """Lay out the top menu: Home, About, Life, Gift Box, Blog, and name
        the shop categories behind Life and Gift Box to match.

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
        self._gif2box_name_categories()

    def _gif2box_name_categories(self):
        for categ_id, (names, seo_name) in CATEGORIES.items():
            categ = self.env['product.public.category'].browse(categ_id).exists()
            if not categ:
                continue
            self._gif2box_write_translations(categ, 'name', names)
            # Written in English only: the other languages fall back to it.
            categ.with_context(lang='en_US').seo_name = seo_name

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

        # --- Life and Gift Box ---------------------------------------------
        for url, names in ((LIFE_URL, LIFE_NAMES), (GIFT_URL, GIFT_NAMES)):
            menu = Menu.search(
                [('website_id', '=', website.id), ('url', '=', url)], limit=1)
            if menu:
                self._gif2box_write_translations(menu, 'name', names)

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

    def _is_active(self):
        """Odoo's rule, and the Blog entry is active anywhere in the blog.

        Odoo marks an entry active on its own URL only. The Blog entry's is
        /blog, which redirects to the blog itself (/blog/gif2box-1), with the
        posts further down, so it was never highlighted on any blog page.
        """
        active = super()._is_active()
        if active or not request or self.child_id:
            return active
        if (self.url or '').split('?')[0].rstrip('/') != BLOG_URL:
            return False
        path = request.httprequest.path
        # The language prefix, when the page has one (/en/blog/...).
        prefix = '/%s/' % request.lang.url_code
        if path.startswith(prefix):
            path = path[len(prefix) - 1:]
        return path == BLOG_URL or path.startswith(BLOG_URL + '/')


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
