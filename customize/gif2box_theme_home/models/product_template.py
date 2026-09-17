from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

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
