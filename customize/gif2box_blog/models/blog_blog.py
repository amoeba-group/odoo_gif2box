import datetime
import json
import logging
import re

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
# `data/posts/`, one per language, all four with the same structure, as the
# English is the source the others are translations of (see
# `_gif2box_translate_post_content`). Placeholders are filled when the posts
# are created:
#   {product:ID}  the product page, in the language of the text
#   {img:ID}      the product's picture
#   {gift} {life} the two shop categories
SEEDED_PARAM = 'gif2box_blog.starter_posts_created'

# The file suffix of each language's body.
BODY_FILES = {'en_US': 'en', 'vi_VN': 'vi', 'ja_JP': 'ja', 'ko_KR': 'ko'}

# The post fields written in each language, and their keys in `POSTS`.
POST_FIELDS = {
    'name': 'name',
    'subtitle': 'subtitle',
    'seo_name': 'seo_name',
    'website_meta_description': 'meta_description',
}

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
            'ja_JP': '出産祝いのギフトアイデア：実用的で安心な贈り物',
            'ko_KR': '출산 선물 아이디어: 실용적이고 안전한 선물',
        },
        'subtitle': {
            'en_US': 'What parents really use in the first months, and how to choose a present that will not be a duplicate.',
            'vi_VN': 'Những món ba mẹ thực sự dùng trong những tháng đầu, và cách chọn quà để không bị trùng.',
            'ja_JP': '生後数か月でご両親が本当に使うものと、ほかの贈り物と重ならない選び方。',
            'ko_KR': '첫 몇 달 동안 부모님이 정말 쓰는 물건과, 다른 선물과 겹치지 않게 고르는 법.',
        },
        'seo_name': {
            'en_US': 'newborn-baby-gift-ideas',
            'vi_VN': 'goi-y-qua-tang-cho-be-so-sinh',
        },
        'meta_description': {
            'en_US': 'Practical newborn gift ideas: silicone teethers, first spoons, freezer trays. How to avoid duplicates, and a gift set ready to give.',
            'vi_VN': 'Gợi ý quà tặng cho bé sơ sinh thiết thực: gặm nướu silicone, muỗng nĩa tập ăn, khay trữ đông. Mẹo chọn quà không trùng và set quà sẵn để tặng.',
            'ja_JP': '実用的な出産祝いのアイデア：シリコーンの歯固め、初めてのスプーン、冷凍トレー。贈り物が重ならないコツと、そのまま贈れるギフトセット。',
            'ko_KR': '실용적인 출산 선물 아이디어: 실리콘 치발기, 첫 숟가락, 냉동 트레이. 선물이 겹치지 않는 팁과 바로 선물하기 좋은 세트.',
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
            'ja_JP': '1歳の誕生日プレゼントのアイデア',
            'ko_KR': '첫돌 선물 아이디어',
        },
        'subtitle': {
            'en_US': 'Gifts that help a one-year-old eat on their own, and leave less to clean up.',
            'vi_VN': 'Những món quà giúp bé 1 tuổi tự lập trong bữa ăn, và giúp ba mẹ đỡ dọn dẹp.',
            'ja_JP': '1歳の赤ちゃんが自分で食べるのを助け、片付けも楽になる贈り物。',
            'ko_KR': '첫돌 아기가 스스로 먹도록 돕고, 뒷정리도 덜어 주는 선물.',
        },
        'seo_name': {
            'en_US': 'first-birthday-gift-ideas',
            'vi_VN': 'qua-thoi-noi-cho-be-1-tuoi',
        },
        'meta_description': {
            'en_US': 'First birthday gift ideas: suction bowls, self-feeding sets and training cups. Tips for choosing, and gift sets ready to give.',
            'vi_VN': 'Gợi ý quà thôi nôi cho bé 1 tuổi: bát có đế hít, bộ dụng cụ tự xúc, cốc tập uống. Mẹo chọn quà và các set quà sẵn sàng để tặng.',
            'ja_JP': '1歳の誕生日プレゼントのアイデア：吸盤ボウル、自分で食べるためのセット、トレーニングカップ。選び方のコツと、そのまま贈れるギフトセット。',
            'ko_KR': '첫돌 선물 아이디어: 흡착 볼, 자기주도 식사 세트, 트레이닝 컵. 고르는 팁과 바로 선물하기 좋은 세트.',
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
            'ja_JP': '離乳食を始めるときに必要なものチェックリスト',
            'ko_KR': '이유식 시작 준비물 체크리스트',
        },
        'subtitle': {
            'en_US': 'The tools to have ready, the materials to choose, and how to keep it all clean.',
            'vi_VN': 'Những dụng cụ cần có, cách chọn chất liệu an toàn và mẹo vệ sinh, bảo quản.',
            'ja_JP': '用意しておきたい道具、安全な素材の選び方、清潔に保つコツ。',
            'ko_KR': '준비해 둘 도구, 안전한 소재 고르는 법, 깨끗하게 관리하는 팁.',
        },
        'seo_name': {
            'en_US': 'starting-solids-checklist',
            'vi_VN': 'bat-dau-an-dam-can-chuan-bi-gi',
        },
        'meta_description': {
            'en_US': 'What you need to start solids: suction bowls, soft spoons, freezer trays, mashers. Safe materials and cleaning tips.',
            'vi_VN': 'Bắt đầu ăn dặm cần chuẩn bị gì: bát đế hít, thìa silicone, khay trữ đông, dụng cụ nghiền. Cách chọn chất liệu an toàn và mẹo vệ sinh.',
            'ja_JP': '離乳食を始めるのに必要なもの：吸盤ボウル、やわらかいスプーン、冷凍トレー、すりつぶし器。安全な素材とお手入れのコツ。',
            'ko_KR': '이유식 시작 준비물: 흡착 볼, 부드러운 숟가락, 냉동 트레이, 매셔. 안전한 소재와 세척 팁.',
        },
    },
]


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
            for code in installed:
                if code == 'en_US':
                    continue
                values = {field: spec[key][code]
                          for field, key in POST_FIELDS.items() if code in spec[key]}
                if values:
                    post.with_context(lang=code).write(values)
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
        """Write a post's body: English as the source, the other languages
        as its translations."""
        en = self._gif2box_post_body(key, 'en_US')
        post.with_context(lang='en_US').write({'content': en})
        self._gif2box_translate_post_content(post, key, [
            code for code in installed if code != 'en_US' and code in BODY_FILES])

    def _gif2box_translate_post_content(self, post, key, langs):
        """Give a post's body in `langs`, term by term, from `data/posts/`.

        A post's body is translated term by term (paragraph, heading, list
        item, picture caption...), as Odoo translates every web page:
        writing a translated body as a whole replaced the English one as
        well. The files keep the English structure for that, so their terms
        pair up by position.

        Odoo also cuts a term at every link, and puts the English spacing
        back around each piece ("danh mục Life , và"). A paragraph holding
        links is marked `o_translate_inline` in the files, which makes it
        one term, so each language places its links where its sentence
        needs them.

        A term whose English has been edited since the post was created
        keeps the translation it has: only terms still reading as the file
        does are given.
        """
        field = post._fields['content']
        stored = field.get_trans_terms(post.with_context(lang='en_US').content)
        source = field.get_trans_terms(self._gif2box_post_body(key, 'en_US'))
        translations = {}
        for code in langs:
            target = field.get_trans_terms(self._gif2box_post_body(key, code))
            if not len(stored) == len(source) == len(target):
                _logger.warning(
                    'gif2box blog: %s: %s terms in the post, %s in the English '
                    'file, %s in the %s one; %s body not applied',
                    key, len(stored), len(source), len(target), code, code)
                continue
            translations[code] = {
                term: translated
                for term, original, translated in zip(stored, source, target)
                if _plain(term) == _plain(original)
            }
        if translations:
            post.update_field_translations('content', translations)

    @api.model
    def _gif2box_refresh_starter_posts(self):
        """Write the starter posts again from `data/posts/`, in every
        language: body, title, subtitle and meta description.

        For posts created by an earlier version of this module, in English
        and Vietnamese only, and cut into pieces at every link. A post whose
        English text has been edited since is left alone. A title, subtitle
        or description given its own text in a language is kept; only those
        still showing the English are written.
        """
        installed = self.env['res.lang'].search([]).mapped('code')
        Post = self.env['blog.post'].with_context(lang='en_US')
        for spec in POSTS:
            post = Post.search([('seo_name', '=', spec['seo_name']['en_US'])], limit=1)
            if not post:
                continue
            if _plain(post.content) != _plain(self._gif2box_post_body(spec['file'], 'en_US')):
                _logger.warning(
                    'gif2box blog: %s: post %s edited since it was created, not rewritten',
                    spec['file'], post.id)
                continue
            self._gif2box_set_post_content(post, spec['file'], installed)
            for code in installed:
                if code == 'en_US':
                    continue
                localized = post.with_context(lang=code)
                values = {
                    field: spec[key][code]
                    for field, key in POST_FIELDS.items()
                    if code in spec[key] and localized[field] == post[field]
                }
                if values:
                    localized.write(values)

    def _gif2box_post_body(self, key, lang):
        """A post body from `data/posts/`, with its placeholders filled in.

        Links are the same in every language, and carry no language prefix:
        Odoo adds the visitor's own (`/en/...`) when it renders the page, and
        the product page redirects to its slug in that language.
        """
        suffix = BODY_FILES.get(lang, 'en')
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


def _plain(term):
    """A term's words, without its markup."""
    return ' '.join(re.sub(r'<[^>]*>', ' ', term).split())
