from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # The homepage's product snippets hand variants to the card templates, so
    # the combo rules in `product_template.py` are mirrored here. A combo has a
    # single variant, and its stock lives on its items, so the variant defers
    # to its template.

    def _is_sold_out(self):
        self.ensure_one()
        if self.type == 'combo':
            return self.product_tmpl_id._is_sold_out()
        return super()._is_sold_out()

    def _gif2box_shows_out_of_stock(self):
        self.ensure_one()
        if self.type == 'combo':
            return self._is_sold_out()
        return not self.allow_out_of_stock_order and self._is_sold_out()

    def _website_show_quick_add(self):
        if self.type == 'combo' and self._is_sold_out():
            return False
        return super()._website_show_quick_add()

    def _gif2box_hover_image_url(self, size='image_512'):
        """See `product.template._gif2box_hover_image_url`. A variant's own
        extra images come first, then its template's."""
        self.ensure_one()
        return _hover_image_url(self, size)


def _hover_image_url(product, size):
    for image in product._get_images()[1:]:
        if image._name != 'product.image' or image.video_url:
            continue
        # `bin_size`: whether there is a picture, without reading it.
        if image.with_context(bin_size=True).image_1920:
            return product.env['website'].image_url(image, size)
    return False
