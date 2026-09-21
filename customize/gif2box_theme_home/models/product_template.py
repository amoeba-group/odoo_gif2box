import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

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
