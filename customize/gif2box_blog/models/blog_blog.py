import datetime
import json
import logging

from odoo import api, fields, models
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

# --- The blog itself --------------------------------------------------------
#
# Odoo created one blog on install, "Our blog", which someone had named "Du
# lịch" (travel) in Vietnamese. It is renamed and described here, on every
# update of this module, as the menu and the About page are in
# `gif2box_theme_home`: edits to these texts in the backend are put back.

BLOG_NAMES = {
    'en_US': 'Gif2box Blog',
    'vi_VN': 'Blog Gif2box',
    'ja_JP': 'Gif2boxブログ',
    'ko_KR': 'Gif2box 블로그',
}

BLOG_SUBTITLES = {
    'en_US': 'Gift ideas and feeding tips for little ones',
    'vi_VN': 'Gợi ý quà tặng và bí quyết ăn dặm cho bé',
    'ja_JP': '赤ちゃんへのギフトアイデアと離乳食のヒント',
    'ko_KR': '아기 선물 아이디어와 이유식 팁',
}

BLOG_META_DESCRIPTIONS = {
    'en_US': 'Gift guides for newborns and first birthdays, and practical tips '
             'for starting solids, from the Gif2box team.',
    'vi_VN': 'Cẩm nang chọn quà cho bé sơ sinh, quà thôi nôi và kinh nghiệm cho '
             'bé ăn dặm từ Gif2box.',
    'ja_JP': '出産祝いや1歳の誕生日のギフトガイド、離乳食の始め方のヒントをGif2boxがお届けします。',
    'ko_KR': '출산 선물, 첫돌 선물 가이드와 이유식 시작 팁을 Gif2box가 전해 드립니다.',
}

# The URL word for the blog: /blog/gif2box-1 rather than /blog/our-blog-1.
BLOG_SEO_NAME = 'gif2box'

# Odoo's display options for the blog. The post page uses the "regular"
# cover (title above the picture, which reads as an article rather than a
# poster), with the breadcrumb and the readable column. The index top banner
# options are replaced by this module's header and switched off, so the
# Customize panel does not offer something that no longer shows.
VIEW_OPTIONS = {
    'website_blog.opt_blog_post_regular_cover': True,
    'website_blog.opt_blog_post_breadcrumb': True,
    'website_blog.opt_blog_post_readable': True,
    'website_blog.opt_blog_post_sidebar': False,
    'website_blog.opt_blog_post_read_next': True,
    'website_blog.opt_blog_cover_post': False,
    'website_blog.opt_blog_cover_post_fullwidth_design': False,
    'website_blog.opt_blog_sidebar_show': False,
    'website_blog.opt_blog_list_view': False,
}

# --- Starter posts ----------------------------------------------------------
#
# Created once (`SEEDED_PARAM`), never again: deleted or rewritten in the
# backend, they stay as the client left them. Each body is an HTML file in
# `data/posts/`, in Vietnamese and English; Japanese and Korean visitors
# read the English. Placeholders are filled when the posts are created:
#   {product:ID}  the product page, in the language of the text
#   {img:ID}      the product's picture
#   {gift} {life} the two shop categories
SEEDED_PARAM = 'gif2box_blog.starter_posts_created'

TAGS = {
    'gifts': {'en_US': 'Gift ideas', 'vi_VN': 'Gợi ý quà tặng',
              'ja_JP': 'ギフトのアイデア', 'ko_KR': '선물 아이디어'},
    'solids': {'en_US': 'Starting solids', 'vi_VN': 'Ăn dặm',
               'ja_JP': '離乳食', 'ko_KR': '이유식'},
    'tips': {'en_US': 'Parenting tips', 'vi_VN': 'Mẹo nuôi con',
             'ja_JP': '子育てのヒント', 'ko_KR': '육아 팁'},
}

GIFT_CATEGORY = '/shop/category/gift-38'
LIFE_CATEGORY = '/shop/category/34'

POSTS = [
    {
        'file': 'newborn',
        'days_ago': 9,
        'cover_product': 635,
        'tags': ['gifts', 'tips'],
        'name': {
            'en_US': 'Newborn gift ideas: practical, safe and thoughtful',
            'vi_VN': 'Gợi ý quà tặng cho bé sơ sinh thiết thực, an toàn và ý nghĩa',
        },
        'subtitle': {
            'en_US': 'What parents really use in the first months, and how to choose a present that will not be a duplicate.',
            'vi_VN': 'Những món ba mẹ thực sự dùng trong những tháng đầu, và cách chọn quà để không bị trùng.',
        },
        'seo_name': {
            'en_US': 'newborn-baby-gift-ideas',
            'vi_VN': 'goi-y-qua-tang-cho-be-so-sinh',
        },
        'meta_description': {
            'en_US': 'Practical newborn gift ideas: silicone teethers, first spoons, freezer trays. How to avoid duplicates, and a gift set ready to give.',
            'vi_VN': 'Gợi ý quà tặng cho bé sơ sinh thiết thực: gặm nướu silicone, muỗng nĩa tập ăn, khay trữ đông. Mẹo chọn quà không trùng và set quà sẵn để tặng.',
        },
    },
    {
        'file': 'birthday',
        'days_ago': 5,
        'cover_product': 634,
        'tags': ['gifts'],
        'name': {
            'en_US': "First birthday gift ideas for a one-year-old",
            'vi_VN': 'Quà thôi nôi cho bé 1 tuổi: chọn sao cho ý nghĩa và hữu ích',
        },
        'subtitle': {
            'en_US': 'Gifts that help a one-year-old eat on their own, and leave less to clean up.',
            'vi_VN': 'Những món quà giúp bé 1 tuổi tự lập trong bữa ăn, và giúp ba mẹ đỡ dọn dẹp.',
        },
        'seo_name': {
            'en_US': 'first-birthday-gift-ideas',
            'vi_VN': 'qua-thoi-noi-cho-be-1-tuoi',
        },
        'meta_description': {
            'en_US': 'First birthday gift ideas: suction bowls, self-feeding sets and training cups. Tips for choosing, and gift sets ready to give.',
            'vi_VN': 'Gợi ý quà thôi nôi cho bé 1 tuổi: bát có đế hít, bộ dụng cụ tự xúc, cốc tập uống. Mẹo chọn quà và các set quà sẵn sàng để tặng.',
        },
    },
    {
        'file': 'solids',
        'days_ago': 1,
        'cover_product': 633,
        'tags': ['solids', 'tips'],
        'name': {
            'en_US': 'Starting solids: the checklist of what you need',
            'vi_VN': 'Bắt đầu ăn dặm cần chuẩn bị gì? Checklist dụng cụ cho ba mẹ',
        },
        'subtitle': {
            'en_US': 'The tools to have ready, the materials to choose, and how to keep it all clean.',
            'vi_VN': 'Những dụng cụ cần có, cách chọn chất liệu an toàn và mẹo vệ sinh, bảo quản.',
        },
        'seo_name': {
            'en_US': 'starting-solids-checklist',
            'vi_VN': 'bat-dau-an-dam-can-chuan-bi-gi',
        },
        'meta_description': {
            'en_US': 'What you need to start solids: suction bowls, soft spoons, freezer trays, mashers. Safe materials and cleaning tips.',
            'vi_VN': 'Bắt đầu ăn dặm cần chuẩn bị gì: bát đế hít, thìa silicone, khay trữ đông, dụng cụ nghiền. Cách chọn chất liệu an toàn và mẹo vệ sinh.',
        },
    },
]

# Japanese and Korean titles: the bodies are in English, but a title in the
# reader's language tells them what the post is about before they open it.
POST_TITLES_JA_KO = {
    'newborn': ('出産祝いのギフトアイデア：実用的で安心な贈り物', '출산 선물 아이디어: 실용적이고 안전한 선물'),
    'birthday': ('1歳の誕生日プレゼントのアイデア', '첫돌 선물 아이디어'),
    'solids': ('離乳食を始めるときに必要なものチェックリスト', '이유식 시작 준비물 체크리스트'),
}


class BlogBlog(models.Model):
    _inherit = 'blog.blog'

    @api.model
    def _gif2box_setup_blog(self):
        """Name the blog, set the display options, create the starter posts.

        Called from `data/blog_data.xml` on every install and update.
        """
        installed = self.env['res.lang'].search([]).mapped('code')

        for xmlid, active in VIEW_OPTIONS.items():
            view = self.env.ref(xmlid, raise_if_not_found=False)
            if view and view.active != active:
                view.write({'active': active})

        for blog in self.search([]):
            for code in installed:
                values = {}
                for field, names in (('name', BLOG_NAMES), ('subtitle', BLOG_SUBTITLES),
                                     ('website_meta_description', BLOG_META_DESCRIPTIONS)):
                    if code in names:
                        values[field] = names[code]
                values['seo_name'] = BLOG_SEO_NAME
                blog.with_context(lang=code).write(values)

        blog = self.search([], order='id', limit=1)
        if blog:
            self._gif2box_create_starter_posts(blog, installed)

    # --- Starter posts -----------------------------------------------------

    def _gif2box_create_starter_posts(self, blog, installed):
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(SEEDED_PARAM):
            return

        tags = {key: self._gif2box_tag(names, installed) for key, names in TAGS.items()}
        author = self._gif2box_author()
        created = 0
        for spec in POSTS:
            product = self.env['product.template'].browse(spec['cover_product']).exists()
            cover = product and '/web/image/product.template/%s/image_1024' % product.id
            post_date = fields.Datetime.now() - datetime.timedelta(days=spec['days_ago'])
            post = self.env['blog.post'].with_context(lang='en_US').create({
                'blog_id': blog.id,
                'name': spec['name']['en_US'],
                'subtitle': spec['subtitle']['en_US'],
                'seo_name': spec['seo_name']['en_US'],
                'website_meta_description': spec['meta_description']['en_US'],
                'tag_ids': [(6, 0, [tags[key].id for key in spec['tags']])],
                'author_id': author.id,
                'post_date': post_date,
                'is_published': True,
                'cover_properties': json.dumps({
                    'background-image': "url('%s')" % cover if cover else 'none',
                    'background_color_class': 'o_cc3 o_cc',
                    'background_color_style': '',
                    'opacity': '0',
                    'resize_class': 'o_record_has_cover o_half_screen_height',
                }),
            })
            self._gif2box_set_post_content(post, spec['file'], installed)
            if 'vi_VN' in installed:
                post.with_context(lang='vi_VN').write({
                    'name': spec['name']['vi_VN'],
                    'subtitle': spec['subtitle']['vi_VN'],
                    'seo_name': spec['seo_name']['vi_VN'],
                    'website_meta_description': spec['meta_description']['vi_VN'],
                })
            ja, ko = POST_TITLES_JA_KO.get(spec['file'], (None, None))
            for code, title in (('ja_JP', ja), ('ko_KR', ko)):
                if title and code in installed:
                    post.with_context(lang=code).write({'name': title})
            created += 1

        params.set_param(SEEDED_PARAM, fields.Datetime.now().isoformat())
        _logger.info('gif2box blog: %s starter post(s) created in blog %s', created, blog.id)

    def _gif2box_tag(self, names, installed):
        Tag = self.env['blog.tag'].with_context(lang='en_US')
        tag = Tag.search([('name', '=', names['en_US'])], limit=1)
        if not tag:
            tag = Tag.create({'name': names['en_US']})
        for code, name in names.items():
            if code in installed and code != 'en_US':
                tag.with_context(lang=code).write({'name': name})
        return tag

    def _gif2box_author(self):
        """The posts are signed by the shop, not by whoever ran the update."""
        Partner = self.env['res.partner']
        author = Partner.search([('name', '=', 'Gif2box'), ('is_company', '=', True)], limit=1)
        if not author:
            author = Partner.create({'name': 'Gif2box', 'is_company': True})
        return author

    def _gif2box_set_post_content(self, post, key, installed):
        """Write a post's body: English as the source, Vietnamese over it.

        A post's body is translated term by term (paragraph, heading, list
        item...), as Odoo translates every web page. Writing the Vietnamese
        body as a whole replaced the English one as well, so the English is
        written first and the Vietnamese is given term for term; the two
        files keep the same structure for that, links included.
        """
        field = post._fields['content']
        en = self._gif2box_post_body(key, 'en_US')
        post.with_context(lang='en_US').write({'content': en})
        if 'vi_VN' not in installed:
            return
        vi = self._gif2box_post_body(key, 'vi_VN')
        source = post.with_context(lang='en_US').content
        terms_en = field.get_trans_terms(source)
        terms_vi = field.get_trans_terms(vi)
        if len(terms_en) != len(terms_vi):
            _logger.warning(
                'gif2box blog: %s: %s English terms against %s Vietnamese, '
                'Vietnamese body not applied', key, len(terms_en), len(terms_vi))
            return
        post.update_field_translations('content', {'vi_VN': dict(zip(terms_en, terms_vi))})

    def _gif2box_post_body(self, key, lang):
        """A post body from `data/posts/`, with its placeholders filled in.

        Links are the same in both languages, and carry no language prefix:
        Odoo adds the visitor's own (`/en/...`) when it renders the page, and
        the product page redirects to its slug in that language.
        """
        suffix = 'vi' if lang == 'vi_VN' else 'en'
        with file_open('gif2box_blog/data/posts/%s.%s.html' % (key, suffix)) as fh:
            body = fh.read()
        body = body.replace('{gift}', GIFT_CATEGORY).replace('{life}', LIFE_CATEGORY)
        default_lang = self.env['website'].get_current_website().default_lang_id.code or 'vi_VN'
        for product in self.env['product.template'].search([]):
            token = '{product:%s}' % product.id
            if token in body:
                body = body.replace(token, product.with_context(lang=default_lang).website_url)
            token = '{img:%s}' % product.id
            if token in body:
                body = body.replace(token, '/web/image/product.template/%s/image_1024' % product.id)
        return body

    def _g2b_topics(self):
        """The topics in use on published posts, for the index's chips.

        Called on a blog, or on the empty model for the all-blogs page.
        """
        domain = [('website_published', '=', True)]
        if self:
            domain.append(('blog_id', 'in', self.ids))
        return self.env['blog.post'].search(domain).tag_ids.sorted('name')
