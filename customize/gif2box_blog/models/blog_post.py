import json
import re
from urllib.parse import quote as url_quote

from markupsafe import Markup

from odoo import _, models
from odoo.http import request
from odoo.tools import html2plaintext
from odoo.tools.json import scriptsafe as json_scriptsafe

# Reading speed for the "N min read" label. Vietnamese is counted in
# syllables, which split on spaces like English words do; 220 a minute is
# an unhurried pace for either.
WORDS_PER_MINUTE = 220

# A meta description is cut by search engines past about this length.
META_DESCRIPTION_LENGTH = 160

_URL_IN_CSS = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""")


class BlogPost(models.Model):
    _inherit = 'blog.post'

    # --- What the cards and the post page show ---------------------------

    def _g2b_cover_url(self):
        """The cover picture's URL, or False when the post has none.

        Odoo keeps the cover as a CSS `background-image` in a JSON blob,
        which the cards turn into a real `<img>`: lazily loaded, sized, and
        with alt text, which a CSS background cannot have.
        """
        self.ensure_one()
        try:
            properties = json_scriptsafe.loads(self.cover_properties or '{}')
        except ValueError:
            return False
        match = _URL_IN_CSS.search(properties.get('background-image') or '')
        return match.group(1) if match else False

    def _g2b_word_count(self):
        self.ensure_one()
        return len(html2plaintext(self.content or '').split())

    def _g2b_reading_minutes(self):
        self.ensure_one()
        return max(1, round(self._g2b_word_count() / WORDS_PER_MINUTE))

    def _g2b_reading_label(self):
        self.ensure_one()
        return _("%s min read", self._g2b_reading_minutes())

    def _g2b_meta_description(self):
        """What search engines show under the title.

        The one set in the SEO panel if there is one; else the subtitle; else
        the opening of the post. Odoo only ever used the subtitle, so a post
        without one went out with no description at all.
        """
        self.ensure_one()
        text = self.website_meta_description or self.subtitle or self.teaser or ''
        text = ' '.join(text.split())
        if len(text) > META_DESCRIPTION_LENGTH:
            text = text[:META_DESCRIPTION_LENGTH - 1].rsplit(' ', 1)[0] + '…'
        return text

    def _default_website_meta(self):
        res = super()._default_website_meta()
        description = self._g2b_meta_description()
        if description:
            res['default_meta_description'] = description
            res['default_opengraph']['og:description'] = description
            res['default_twitter']['twitter:description'] = description
        return res

    # --- Search engine data ----------------------------------------------

    def _g2b_absolute(self, url):
        website = self.env['website'].get_current_website()
        base = (website.domain or request.httprequest.url_root).rstrip('/')
        return url if url.startswith('http') else base + url

    def _g2b_jsonld(self):
        """schema.org BlogPosting and BreadcrumbList for this post.

        What Google reads to show a post as an article: headline, picture,
        dates and author, and the trail above it in the results instead of a
        bare URL.
        """
        self.ensure_one()
        website = self.env['website'].get_current_website()
        url = self._g2b_absolute(request.httprequest.path) if request else ''
        blog_url = self._g2b_absolute(
            '/blog/%s' % self.env['ir.http']._slug(self.blog_id))
        cover = self._g2b_cover_url()
        logo = self._g2b_absolute(website.image_url(website, 'logo'))
        lang = (self.env.lang or 'vi_VN').replace('_', '-')

        post = {
            '@type': 'BlogPosting',
            'headline': (self.name or '')[:110],
            'description': self._g2b_meta_description(),
            'inLanguage': lang,
            'mainEntityOfPage': url,
            'url': url,
            'datePublished': self.post_date and self.post_date.isoformat(),
            'dateModified': self.write_date and self.write_date.isoformat(),
            'wordCount': self._g2b_word_count(),
            'author': {'@type': 'Organization', 'name': self.author_name or website.name},
            'publisher': {
                '@type': 'Organization',
                'name': website.name,
                'logo': {'@type': 'ImageObject', 'url': logo},
            },
        }
        if cover:
            post['image'] = [self._g2b_absolute(cover)]
        if self.tag_ids:
            post['keywords'] = ', '.join(self.tag_ids.mapped('name'))

        crumbs = {
            '@type': 'BreadcrumbList',
            'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': website.name,
                 'item': self._g2b_absolute('/')},
                {'@type': 'ListItem', 'position': 2, 'name': self.blog_id.name,
                 'item': blog_url},
                {'@type': 'ListItem', 'position': 3, 'name': self.name, 'item': url},
            ],
        }
        data = {'@context': 'https://schema.org', '@graph': [post, crumbs]}
        # `</` would end the script tag early; escaped, it is the same JSON.
        return Markup(json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))

    def _g2b_share_url(self, network):
        """A share link for this post, opened in a new tab."""
        self.ensure_one()
        url = self._g2b_absolute(request.httprequest.path) if request else ''
        if network == 'facebook':
            return 'https://www.facebook.com/sharer/sharer.php?u=' + url_quote(url, safe='')
        return url
