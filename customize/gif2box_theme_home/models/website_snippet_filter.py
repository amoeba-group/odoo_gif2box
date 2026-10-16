from odoo import models

# How many times to go back for more when a batch comes back with sold-out
# products in it. Three batches is up to three times the snippet's limit.
SOLD_OUT_REFILLS = 3


class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _prepare_values(self, limit=None, **kwargs):
        """Leave sold-out products out, and still fill the row.

        Only when asked (`gif2box_hide_sold_out`, see `controllers/main.py`):
        the homepage's rows are there to sell, so a card that cannot be
        bought only takes a place from one that can. "Sold out" is the rule
        the shop's "Out of stock" chip follows, combos included
        (`_gif2box_shows_out_of_stock`).

        Removing them from a single fetch would leave the row short, so the
        filter is asked again for the next ones, past those already seen,
        until the row is full or the catalogue runs out.
        """
        if not self.env.context.get('gif2box_hide_sold_out') \
                or self.model_name not in ('product.product', 'product.template'):
            return super()._prepare_values(limit=limit, **kwargs)

        wanted = limit or self.limit
        base_domain = list(kwargs.pop('search_domain', None) or [])
        # With variants hidden (the snippet's default), the next batches skip
        # whole products, not just the variants already seen: a product's
        # other variants would otherwise come back and show it twice in the
        # row. With variants shown, each variant is a card of its own.
        by_template = self.model_name == 'product.product' and 'hide_variants' in base_domain
        key_field = 'product_tmpl_id' if by_template else 'id'
        values, seen = [], set()
        for _batch in range(SOLD_OUT_REFILLS):
            # A fresh copy every time: `website_sale` removes its
            # `hide_variants` marker from the list it is given.
            domain = list(base_domain)
            if seen:
                domain.append((key_field, 'not in', list(seen)))
            batch = super()._prepare_values(limit=limit, search_domain=domain, **kwargs)
            for data in batch:
                # With variants hidden, `website_sale` hands back the
                # products themselves (`product.template`), not variants.
                record = data['_record']
                if by_template:
                    key = (record.product_tmpl_id if record._name == 'product.product' else record).id
                else:
                    key = record.id
                if key in seen:
                    continue
                seen.add(key)
                if not record._gif2box_shows_out_of_stock():
                    values.append(data)
            if len(values) >= wanted or len(batch) < wanted:
                break
        return values[:wanted]
