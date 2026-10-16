import logging

from odoo import _, api, fields, models

from .product_product import _hover_image_url

_logger = logging.getLogger(__name__)

# Lines of the combo box shown before "Show more", on phones.
COMBO_LINES_FOLDED = 4

# The label, in every language the site runs in.
#
# Not in the `.po` files, where it belongs, because it cannot work there:
# Odoo ships its own translations of "Compare to Price", and a module update
# leaves an existing translation alone unless the server is started with
# `--i18n-overwrite`. That flag is all-or-nothing across every module, which
# is too blunt a tool for one label, so the values are written here instead.
ORIGINAL_PRICE_LABEL = {
    'en_US': 'Original Price',
    # "Giá gốc" is the common phrase but reads as cost price in an ERP, and
    # Cost sits directly under this field on the form.
    'vi_VN': 'Giá trước giảm',
    'ja_JP': '割引前価格',
    'ko_KR': '할인 전 가격',
}


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # "Compare to Price" describes the mechanism, not the number. Sitting
    # directly under "Sales Price" and directly above "Cost", what it needs to
    # say is which price it is: the one the item used to go for.
    #
    # Only the label is changed. Odoo's help text still describes the field
    # accurately and is already translated, so it is left alone.
    compare_list_price = fields.Monetary(string=ORIGINAL_PRICE_LABEL['en_US'])

    @api.model
    def _gif2box_label_original_price(self):
        """Translate the relabelled field. Called from `data/settings_data.xml`."""
        field = self.env['ir.model.fields'].sudo().search([
            ('model', 'in', ('product.template', 'product.product')),
            ('name', '=', 'compare_list_price'),
        ])
        if not field:
            return

        installed = self.env['res.lang'].search([]).mapped('code')
        for code, label in ORIGINAL_PRICE_LABEL.items():
            if code in installed:
                field.with_context(lang=code).write({'field_description': label})
        _logger.info('gif2box: relabelled compare_list_price on %s field(s)', len(field))

    def _is_sold_out(self):
        """A template is sold out only when every one of its variants is.

        Odoo checks `product_variant_id` -- a single variant, the first of the
        recordset in its default order, which is by name and not by anything a
        shopper can see. A ten-variant product with stock on eight of them
        counted as sold out because the one that happened to sort first was
        empty, and `_website_show_quick_add()` then dropped the add-to-cart
        button from the whole card.

        Hit in production on "Thớt Platinum Silicone Firgi Hàn Quốc" (template
        609): variants held 44, 23, 39, 35, 24, 2, 2, 0, 2 and 0 units, and the
        one the check landed on was the last of those.
        """
        self.ensure_one()
        if self.type == 'combo':
            return self._gif2box_combo_sold_out()
        if not self.is_storable:
            return False
        variants = self.product_variant_ids
        if len(variants) <= 1:
            return super()._is_sold_out()

        website = self.env['website'].get_current_website()
        variants = variants.sudo()
        # One query for the whole set. Without this the generator below would
        # compute `free_qty` a variant at a time, which on a grid of cards is
        # a query per variant per product.
        variants.with_context(warehouse_id=website.warehouse_id.id).mapped('free_qty')
        # Still routed through the website helper so that any override of it
        # (click & collect, for one) keeps applying.
        return all(
            website._get_product_available_qty(variant) <= 0 for variant in variants
        )

    def _gif2box_combo_sold_out(self):
        """A combo is sold out when one of its choices has nothing left to pick.

        Odoo never calls a combo sold out: it is not a storable product, so
        the cards kept their add-to-cart button and no "Out of stock" marker.
        Its product page knew better (`max_combo_quantity` in
        `website_sale_stock`) and dropped the whole buy form. This is the same
        rule, read from the stock alone rather than net of what the visitor
        already has in the cart: a choice is available when any one of its
        items is not tracked, can be backordered, or has stock left.
        """
        self.ensure_one()
        return any(
            not self._gif2box_combo_choice_available(combo)
            for combo in self.sudo().combo_ids
        )

    @api.model
    def _gif2box_combo_choice_available(self, combo):
        """Whether any item of a combo choice can still be bought."""
        website = self.env['website'].get_current_website()
        products = combo.combo_item_ids.product_id
        # One query for the choice rather than one per item.
        products.with_context(warehouse_id=website.warehouse_id.id).mapped('free_qty')
        return any(
            not product.is_storable
            or product.allow_out_of_stock_order
            or website._get_product_available_qty(product) > 0
            for product in products
        )

    def _gif2box_combo_contents(self):
        """What the product page's "This set includes" box lists, or None.

        One line per combo choice, as the set is made of one item from each:
        its picture, name and price when bought on its own, how many options
        it comes in, whether it has sold out, and where to read about it.

        A choice usually holds the variants of one product (a chopping board
        in five colours), so the line shows that product: its page is where
        all of them are. A choice spanning several products shows the first,
        priced "from" the cheapest.

        Prices are the shop's own (`_get_combination_info_variant`: the
        website's pricelist and tax display), so they match what the item's
        page says. Their total, against the set's price, is the saving.
        """
        self.ensure_one()
        if self.type != 'combo':
            return None
        website = self.env['website'].get_current_website()
        lines = []
        for combo in self.sudo().combo_ids:
            products = combo.combo_item_ids.product_id
            if not products:
                continue
            templates = products.product_tmpl_id
            first = products[0]
            prices = [p._get_combination_info_variant()['price'] for p in products]
            # One product: its page, where every variant is. Several: the
            # first one's. Nothing for a product the shop does not show.
            target = templates if len(templates) == 1 else first.product_tmpl_id
            url = target.website_url if target.is_published else False
            lines.append({
                'name': target.with_context(lang=self.env.lang).name,
                'url': url,
                'image_url': website.image_url(first if len(products) == 1 else target, 'image_256'),
                'price': min(prices),
                'price_from': min(prices) != max(prices),
                'options_label': len(products) > 1 and _("%s options", len(products)),
                'sold_out': not self._gif2box_combo_choice_available(combo),
            })
        if not lines:
            return None
        set_price = self._get_combination_info()['price']
        retail_total = sum(line['price'] for line in lines)
        saving = retail_total - set_price
        return {
            'lines': lines,
            'count_label': _("%s products", len(lines)),
            'more_label': _("Show %s more", max(len(lines) - COMBO_LINES_FOLDED, 0)),
            'folds': len(lines) > COMBO_LINES_FOLDED,
            'retail_total': retail_total,
            'saving': saving if saving > 0 else 0,
            'saving_percent': round(saving * 100 / retail_total) if saving > 0 and retail_total else 0,
            'currency': website.currency_id,
        }

    @api.model
    def _gif2box_retire_combo_thumbnails(self):
        """Switch off the combo blocks made by hand in the database.

        "Included in this set" thumbnails under the product picture and their
        description modals (`website_sale.product_combo_thumbnails*`) were
        created in the backend on 2026-09-11, not by any module. The box under
        the price replaces them; switched off rather than deleted, so they can
        be turned back on from Settings > Technical > Views. Called on every
        update of this module, harmlessly once done.
        """
        views = self.env['ir.ui.view'].sudo().with_context(active_test=False).search([
            ('key', 'in', ('website_sale.product_combo_thumbnails',
                           'website_sale.product_combo_thumbnails_sticky')),
            ('active', '=', True),
        ])
        views.write({'active': False})
        if views:
            _logger.info('gif2box: switched off %s hand-made combo view(s)', len(views))

    def _gif2box_shows_out_of_stock(self):
        """Whether the shop should mark this product "Out of stock".

        For a combo the flag on the combo itself means nothing (it is never
        tracked); only its items count, and `_is_sold_out` already reads them.
        """
        self.ensure_one()
        if self.type == 'combo':
            return self._is_sold_out()
        return not self.allow_out_of_stock_order and self._is_sold_out()

    def _website_show_quick_add(self):
        """No add-to-cart button on the card of a combo that cannot be bought.

        `website_sale_stock` lets the combo's own `allow_out_of_stock_order`
        through, which is always set on a combo.
        """
        if self.type == 'combo' and self._is_sold_out():
            return False
        return super()._website_show_quick_add()

    def _gif2box_hover_image_url(self, size='image_512'):
        """The picture a product card shows on hover: its first extra image.

        Videos are skipped (an extra "image" can be a video, whose picture is
        only its thumbnail), and so is anything without a picture. Returns
        False when there is no second picture, and the card keeps its own.
        """
        self.ensure_one()
        return _hover_image_url(self, size)
