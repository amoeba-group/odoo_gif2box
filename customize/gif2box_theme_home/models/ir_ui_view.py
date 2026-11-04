import json
import logging
import re
import time

from lxml import html as lxml_html
from markupsafe import Markup

from odoo import api, models
from odoo.http import request

_logger = logging.getLogger(__name__)

# The homepage's product rows, as the page stores them: Odoo's "Products"
# snippet marked `o_g2b_home_products`, and further in, the empty area its
# script fills with the cards.
ROW_RE = re.compile(r'<section\b[^>]*\bo_g2b_home_products\b[^>]*>')
AREA_RE = re.compile(r'<div class="dynamic_snippet_template"[^>]*></div>')
CLASS_RE = re.compile(r'\bclass="([^"]*)"')
# What keeps a dynamic snippet hidden until its script has rendered it.
EMPTY_RE = re.compile(r'\s*\bo_dynamic(?:_snippet)?_empty\b')

# The rendered cards, kept a few minutes in each worker. Rendering a row
# costs some 300 queries and 2 to 3 s, and the homepage is asked for every
# few seconds, monitors and crawlers included: without this, every one of
# those requests paid for both rows, and the page took 4 to 5 s instead of
# half a second to start arriving. A product sold out or repriced meanwhile
# shows as it was for at most that long, on the homepage only.
ROW_CACHE_TTL = 600
ROW_CACHE_MAX = 64
_row_cache = {}


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def _render_template(self, template, values=None):
        """Put the homepage's products in the page itself.

        Odoo's product snippet arrives empty and hidden: its script fetches
        the cards (`/website/snippet/filters`) once the large script bundle
        has loaded, and that bundle only loads after the whole page has.
        The page loader lifted onto sections with no products in them for
        another 15 s on 4G, 35 s on a slow line.

        The cards are rendered here instead, from the snippet's own
        settings, by the same call that request makes, so they show with the
        page. The script, once there, takes them as its data rather than
        asking again (`home_product_sections.js`). The page's stored content
        is untouched: the editor empties the snippet before it edits and
        before it saves.
        """
        result = super()._render_template(template, values)
        if request and getattr(request, 'is_frontend', False) and request.website \
                and 'o_g2b_home_products' in result:
            try:
                result = Markup(self._gif2box_prerender_product_rows(str(result)))
            except Exception:
                # The script fills the rows as before.
                _logger.exception("Could not render the homepage product rows")
        return result

    def _gif2box_prerender_product_rows(self, page):
        rows = list(ROW_RE.finditer(page))
        parts, pos = [], 0
        for index, row in enumerate(rows):
            # The area that belongs to this row: before the next row starts.
            bound = rows[index + 1].start() if index + 1 < len(rows) else len(page)
            area = AREA_RE.search(page, row.end(), bound)
            if not area:
                continue
            attrs = lxml_html.fragment_fromstring(row.group(0) + '</section>').attrib
            items = self._gif2box_product_row_items(attrs)
            if not items:
                # Nothing to show, or a setting only the script can resolve:
                # left to it, hidden until then, as Odoo does.
                continue
            tag = CLASS_RE.sub(lambda m: 'class="%s"' % EMPTY_RE.sub('', m.group(1)), row.group(0), count=1)
            parts += [
                page[pos:row.start()], tag, page[row.end():area.start()],
                area.group(0)[:-len('</div>')], self._gif2box_render_product_row(attrs, items, index), '</div>',
            ]
            pos = area.end()
        parts.append(page[pos:])
        return ''.join(parts)

    def _gif2box_product_row_items(self, attrs):
        """The row's cards, as `/website/snippet/filters` would return them
        to the snippet's script, given the snippet's settings: the search
        domain is built the way `s_dynamic_snippet_products/000.js` builds
        it, and sold-out products are left out as the homepage asks
        (`_getRpcParameters` in `home_product_sections.js`)."""
        try:
            filter_id = int(attrs.get('data-filter-id'))
            limit = int(attrs.get('data-number-of-records'))
        except (TypeError, ValueError):
            return []
        template_key = attrs.get('data-template-key') or ''
        if '.dynamic_filter_template_' not in template_key:
            return []

        domain = []
        category = attrs.get('data-product-category-id')
        if category == 'current':
            # The category of the page's product: only the script knows it.
            return []
        if category and category != 'all':
            try:
                domain.append(('public_categ_ids', 'child_of', int(category)))
            except ValueError:
                return []
        tags = json.loads(attrs.get('data-product-tag-ids') or '[]')
        if tags:
            domain.append(('all_product_tag_ids', 'in', [tag['id'] for tag in tags]))
        names_domain = []
        for name in (attrs.get('data-product-names') or '').split(','):
            if not name:
                continue
            if names_domain:
                names_domain.insert(0, '|')
            names_domain += ['|', '|', ('name', 'ilike', name), ('default_code', '=', name), ('barcode', '=', name)]
        domain += names_domain
        if not attrs.get('data-show-variants'):
            domain.append('hide_variants')

        custom_data = attrs.get('data-custom-template-data') or '{}'
        # Everything the cards depend on: the prices (pricelist, taxes and
        # currency follow the visitor), the language, and the row's settings.
        website = request.website
        key = (
            request.env.cr.dbname, website.id, request.env.lang, request.env.user._is_public(),
            website.pricelist_id.id, website.fiscal_position_id.id, website.currency_id.id,
            filter_id, template_key, limit, repr(domain), custom_data,
        )
        now = time.monotonic()
        cached = _row_cache.get(key)
        if cached and cached[0] > now:
            return cached[1]

        dynamic_filter = request.env['website.snippet.filter'].sudo().search(
            [('id', '=', filter_id)] + website.website_domain())
        if not dynamic_filter:
            return []
        items = dynamic_filter.with_context(gif2box_hide_sold_out=True)._render(
            template_key, limit, domain, False, **json.loads(custom_data))
        if len(_row_cache) >= ROW_CACHE_MAX:
            _row_cache.clear()
        _row_cache[key] = (now + ROW_CACHE_TTL, items)
        return items

    def _gif2box_render_product_row(self, attrs, items, index):
        # One slide, every card on it, as `home_product_sections.js` has the
        # snippet render it; columns sized as Odoo's carousel template does,
        # from the number of records asked for.
        limit = int(attrs.get('data-number-of-records'))
        return str(self.env['ir.qweb'].with_context(inherit_branding=False)._render(
            'gif2box_theme_home.home_product_row', {
                'g2b_row_id': 'o_g2b_home_row_%d' % index,
                'g2b_col_class': 'd-flex flex-grow-0 flex-shrink-0 col-%d' % (12 // max(limit, 1)),
                'g2b_items': [Markup(item) for item in items],
            }))
