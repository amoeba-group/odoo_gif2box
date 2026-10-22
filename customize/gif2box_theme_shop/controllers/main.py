import json

from markupsafe import Markup

from odoo import http
from odoo.http import request

from odoo.addons.website_sale.controllers.main import WebsiteSale

# --- Budget chips -----------------------------------------------------------
#
# Price is how most people narrow down a present, so the listing offers it as
# a row of one-tap bands rather than Odoo's slider, which is hidden in the
# filter panel and needs two thumbs dragged on a phone. Each band is a link
# to Odoo's own price filter (`min_price` / `max_price` on `list_price`),
# so the result is exactly what the slider would give.
#
# In đồng: (from, up to but not including); 0 is open-ended. Odoo's filter
# includes both ends, so the link asks for one đồng less at the top: "Under
# 500K" leaves a 500,000 ₫ product to the next band, as it says.
BUDGETS = [(0, 500000), (500000, 1000000), (1000000, 2000000), (2000000, 0)]

# The way prices are said in each language, rather than one formula: "500K"
# and "triệu" in Vietnamese, man-yen style units in Japanese and Korean.
BUDGET_LABELS = {
    'vi_VN': ['Dưới 500K', '500K – 1 triệu', '1 – 2 triệu', 'Trên 2 triệu'],
    'en_US': ['Under ₫500K', '₫500K – ₫1M', '₫1M – ₫2M', 'Over ₫2M'],
    'ja_JP': ['50万₫未満', '50万〜100万₫', '100万〜200万₫', '200万₫以上'],
    'ko_KR': ['50만₫ 미만', '50만~100만₫', '100만~200만₫', '200만₫ 이상'],
}

# Category chips that carry the menu's icon, by the category's URL word
# (`seo_name`, pinned by `gif2box_theme_home`).
CHIP_ICONS = {'life': 'life', 'gift': 'gift'}


class Gif2boxShop(WebsiteSale):

    def _shop_lookup_products(self, attrib_set, options, post, search, website):
        """Products that can be bought first, sold-out ones after them.

        A sold-out product stays listed, marked "Out of stock", so a shopper
        looking for it finds out; it just no longer takes a front-row place
        from something that can be ordered. The chosen order is kept within
        each group, and the paging follows, as it slices this list.
        """
        term, count, products = super()._shop_lookup_products(
            attrib_set, options, post, search, website)
        sold_out = products.filtered(lambda p: p._gif2box_shows_out_of_stock())
        if sold_out and sold_out != products:
            products = (products - sold_out) + sold_out
        return term, count, products

    @http.route()
    def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, **post):
        response = super().shop(
            page=page, category=category, search=search,
            min_price=min_price, max_price=max_price, ppg=ppg, **post)
        values = getattr(response, 'qcontext', None)
        if values is not None and 'pager' in values:
            values.update(self._gif2box_shop_values(values))
        return response

    # --- Values for `views/shop_templates.xml` ------------------------------

    def _gif2box_shop_values(self, values):
        category = values.get('category') or request.env['product.public.category']
        base_url = '/shop/category/%s' % request.env['ir.http']._slug(category) if category else '/shop'
        return {
            'g2b_base_url': base_url,
            'g2b_chips': self._gif2box_category_chips(category, values['keep']),
            'g2b_budgets': self._gif2box_budgets(values, base_url),
            'g2b_jsonld': self._gif2box_jsonld(
                category, values['products'], values['pager'], values['search_count']),
        }

    def _gif2box_category_chips(self, category, keep):
        """The categories a shopper can switch to in one tap.

        The current category's children; for one without, its siblings; on
        /shop, the top-level categories. Only categories with something to
        buy, and none whose every product is already in the other chips: the
        "All" left over from the import holds nothing Life and Gift Box do
        not, and two buttons to the same products are one too many. With
        fewer than two categories left there is nothing to switch between,
        and the row is not shown.

        The links keep the sort and the search, not the price band: another
        category has other prices.
        """
        website = request.website
        Category = request.env['product.public.category']
        Product = request.env['product.template']
        if category and category.child_id:
            parent, candidates = category, category.child_id
        elif category and category.parent_id:
            parent, candidates = category.parent_id, category.parent_id.child_id
        else:
            parent = Category
            candidates = Category.search([('parent_id', '=', False)] + website.website_domain())
        candidates = candidates.filtered(lambda c: c.can_access_from_current_website())

        domain = website.sale_product_domain()
        members = []
        for categ in candidates:
            ids = set(Product.search(domain + [('public_categ_ids', 'child_of', categ.id)]).ids)
            if ids:
                members.append((categ, ids))
        # One at a time, the largest first: a catch-all covers the real
        # categories too ("Gift Box" is inside "All" plus "Life"), and only
        # once it is gone can they be judged against each other.
        while True:
            covered = [
                (len(ids), index) for index, (_categ, ids) in enumerate(members)
                if ids <= set().union(*(o for i, (_c, o) in enumerate(members) if i != index))
            ]
            if not covered:
                break
            members.pop(max(covered)[1])
        if len(members) < 2:
            return []

        def link(categ):
            path = '/shop/category/%s' % request.env['ir.http']._slug(categ) if categ else '/shop'
            return keep(path, category=0, min_price=0, max_price=0)

        all_domain = domain + ([('public_categ_ids', 'child_of', parent.id)] if parent else [])
        chips = [{
            'category': parent,
            'count': Product.search_count(all_domain),
            'url': link(parent),
            'active': category == parent,
            'icon': None,
            'is_all': True,
        }]
        for categ, ids in members:
            chips.append({
                'category': categ,
                'count': len(ids),
                'url': link(categ),
                'active': categ == category,
                'icon': CHIP_ICONS.get(categ.seo_name),
                'is_all': False,
            })
        return chips

    def _gif2box_budgets(self, values, base_url):
        """The price bands that have something in them, with the one in use.

        Counted over the products the page would list without a price filter,
        so every band says what tapping it gives. Fewer than two bands with
        products: nothing to choose, no row.
        """
        website = request.website
        if website.currency_id.name != 'VND':
            return []
        domain = self._get_shop_domain(
            values.get('search'), values.get('category'), values.get('attrib_values'))
        prices = request.env['product.template'].search_read(domain, ['list_price'])
        prices = [p['list_price'] for p in prices]
        try:
            asked = (float(request.params.get('min_price') or 0),
                     float(request.params.get('max_price') or 0))
        except ValueError:
            asked = (0, 0)
        keep = values['keep']
        labels = BUDGET_LABELS.get(request.lang.code, BUDGET_LABELS['en_US'])
        bands = []
        for (low, high), label in zip(BUDGETS, labels):
            count = sum(1 for p in prices if p >= low and (not high or p < high))
            if not count:
                continue
            top = high - 1 if high else 0
            active = asked == (float(low), float(top))
            bands.append({
                'label': label,
                'count': count,
                # Tapping the band in use takes it off again.
                'url': keep(base_url, category=0,
                            min_price=0 if active else low, max_price=0 if active else top),
                'active': active,
            })
        if len(bands) < 2:
            return []
        return bands

    def _gif2box_jsonld(self, category, products, pager, total):
        """schema.org CollectionPage: the trail to this page, and the products
        on it, for search engines to show the listing as one."""
        website = request.website
        base = website.get_base_url().rstrip('/')
        url_for = request.env['ir.http']._url_for

        def absolute(path):
            return base + url_for(path)

        trail = [(website.name, '/'), (request.env._('Products'), '/shop')]
        for categ in category.parents_and_self if category else []:
            trail.append((categ.name, '/shop/category/%s' % request.env['ir.http']._slug(categ)))
        page_url = base + request.httprequest.path
        data = {
            '@context': 'https://schema.org',
            '@type': 'CollectionPage',
            'name': trail[-1][0],
            'url': page_url,
            'breadcrumb': {
                '@type': 'BreadcrumbList',
                'itemListElement': [
                    {'@type': 'ListItem', 'position': i, 'name': name, 'item': absolute(path)}
                    for i, (name, path) in enumerate(trail, 1)
                ],
            },
            'mainEntity': {
                '@type': 'ItemList',
                'numberOfItems': total,
                'itemListElement': [
                    {'@type': 'ListItem', 'position': pager['offset'] + i,
                     'url': absolute(product.website_url), 'name': product.name}
                    for i, product in enumerate(products, 1)
                ],
            },
        }
        # `</` would close the script tag early in some parsers; escaped, it
        # is still the same JSON.
        return Markup(json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
