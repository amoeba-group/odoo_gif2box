from odoo import http

from odoo.addons.website.controllers.main import Website


class Gif2boxWebsite(Website):

    @http.route()
    def get_dynamic_filter(self, *args, gif2box_hide_sold_out=False, **kwargs):
        """Let a product snippet ask for in-stock products only.

        Sent by `home_product_sections.js` for the homepage's product rows.
        Taken out of the parameters here: Odoo hands every extra one to the
        card template as a value, and it means nothing there.
        """
        if not gif2box_hide_sold_out:
            return super().get_dynamic_filter(*args, **kwargs)
        request = http.request
        request.update_context(gif2box_hide_sold_out=True)
        return super().get_dynamic_filter(*args, **kwargs)
